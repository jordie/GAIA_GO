#!/usr/bin/env python3
"""
Offline Task Worker

A background worker that processes tasks from the task queue.
Can run on any node in the cluster and claims tasks to execute.

Usage:
    python3 task_worker.py                # Run worker
    python3 task_worker.py --daemon       # Run as daemon
    python3 task_worker.py --stop         # Stop daemon
    python3 task_worker.py --status       # Check status
"""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import get_connection, get_db_path
from graceful_shutdown import GracefulShutdown, ShutdownPhase, ShutdownReason
from graceful_shutdown import task_context as shutdown_task_context
from session_state_manager import SessionStateManager

# Worker configuration
PID_FILE = Path("/tmp/architect_worker.pid")
STATE_FILE = Path("/tmp/architect_worker_state.json")
LOG_FILE = Path("/tmp/architect_worker.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("TaskWorker")


class TaskWorker:
    """
    Background worker that processes tasks from the queue.

    Supports multiple task types with custom handlers.
    Features graceful shutdown with in-progress task completion.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        node_id: str = "local",
        worker_type: str = "general",
        poll_interval: int = 5,
        heartbeat_interval: int = 30,
        dashboard_url: str = "http://100.112.58.92:8080",
        shutdown_timeout: int = 30,
        drain_timeout: int = 60,
        use_load_balancing: bool = False,
        load_balancing_strategy: str = "least_loaded",
    ):
        self.worker_id = worker_id or str(uuid.uuid4())
        self.node_id = node_id
        self.worker_type = worker_type
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.dashboard_url = dashboard_url
        self.use_load_balancing = use_load_balancing
        self.load_balancing_strategy = load_balancing_strategy

        self._running = False
        self._current_task = None
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._start_time = None

        # Session state management for real-time monitoring
        self.session_name = worker_id or f"task-worker-{worker_type}"
        self.state_manager = SessionStateManager(self.session_name)
        self.state_manager.set_tool_info("task_worker", "offline")

        # Task handlers by type
        self._handlers: Dict[str, Callable] = {
            "shell": self._handle_shell_task,
            "python": self._handle_python_task,
            "git": self._handle_git_task,
            "deploy": self._handle_deploy_task,
            "test": self._handle_test_task,
            "build": self._handle_build_task,
            "tmux": self._handle_tmux_task,
        }

        self._lock = threading.Lock()

        # Graceful shutdown handler
        self._shutdown = GracefulShutdown(
            worker_id=self.worker_id,
            worker_type=f"task-worker-{worker_type}",
            shutdown_timeout=shutdown_timeout,
            drain_timeout=drain_timeout,
            on_shutdown=self._on_shutdown,
            on_drain_start=self._on_drain_start,
            on_cleanup=self._on_cleanup,
            notify_dashboard=True,
            dashboard_url=dashboard_url,
            pid_file=PID_FILE,
            state_file=STATE_FILE,
        )

    def register_handler(self, task_type: str, handler: Callable):
        """Register a custom task handler."""
        self._handlers[task_type] = handler

    # =========================================================================
    # Graceful Shutdown Callbacks
    # =========================================================================

    def _on_shutdown(self):
        """Called when shutdown signal is received."""
        logger.info(f"Worker {self.worker_id} received shutdown signal")
        self._running = False

        # Notify dashboard we're shutting down
        try:
            import requests

            requests.post(
                f"{self.dashboard_url}/api/workers/{self.worker_id}/status",
                json={"status": "shutting_down"},
                timeout=5,
            )
        except Exception:
            pass

    def _on_drain_start(self):
        """Called when drain phase starts (waiting for in-progress tasks)."""
        if self._current_task:
            logger.info(f"Draining: waiting for task {self._current_task.get('id')} to complete")

    def _on_cleanup(self):
        """Called during final cleanup phase."""
        logger.info(f"Cleaning up worker {self.worker_id}")

        # Update session state to stopped
        self.state_manager.set_status("stopped")
        self.state_manager.cleanup()

        # Release any claimed but unstarted tasks back to the queue
        if self._current_task and self._shutdown.phase == ShutdownPhase.CLEANUP:
            task_id = self._current_task.get("id")
            logger.info(f"Releasing task {task_id} back to queue")
            try:
                with get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE task_queue SET
                            status = 'pending',
                            assigned_worker = NULL,
                            started_at = NULL
                        WHERE id = ? AND status = 'running'
                    """,
                        (task_id,),
                    )
            except Exception as e:
                logger.error(f"Failed to release task: {e}")

        # Update worker status to offline
        try:
            import requests

            requests.post(
                f"{self.dashboard_url}/api/workers/{self.worker_id}/status",
                json={"status": "offline"},
                timeout=5,
            )
        except Exception:
            pass

        self._save_state()

    def _register_with_server(self):
        """Register this worker with the dashboard server."""
        try:
            import requests

            response = requests.post(
                f"{self.dashboard_url}/api/workers/register",
                json={
                    "id": self.worker_id,
                    "node_id": self.node_id,
                    "worker_type": self.worker_type,
                },
                timeout=5,
            )

            if response.status_code == 200:
                logger.info(f"Registered with server as {self.worker_id}")
                return True
            else:
                logger.warning(f"Failed to register: {response.status_code}")
                return False

        except Exception as e:
            logger.warning(f"Could not register with server: {e}")
            return False

    def _send_heartbeat(self):
        """Send heartbeat to the dashboard server."""
        try:
            import requests

            requests.post(
                f"{self.dashboard_url}/api/workers/{self.worker_id}/heartbeat",
                json={
                    "status": "busy" if self._current_task else "idle",
                    "current_task_id": self._current_task.get("id") if self._current_task else None,
                    "tasks_completed": self._tasks_completed,
                    "tasks_failed": self._tasks_failed,
                },
                timeout=5,
            )
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")

    def _claim_task(self) -> Optional[Dict]:
        """Claim a pending task from the queue.

        If use_load_balancing is enabled, uses the load-balanced endpoint
        which selects the best worker based on current load distribution.
        """
        try:
            import requests

            if self.use_load_balancing:
                # Use load-balanced endpoint for automatic worker selection
                response = requests.post(
                    f"{self.dashboard_url}/api/tasks/claim-balanced",
                    json={
                        "task_types": list(self._handlers.keys()),
                        "strategy": self.load_balancing_strategy,
                        "worker_type": self.worker_type,
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    task = data.get("task")
                    if task and data.get("worker"):
                        # Update worker_id if the load balancer selected this worker
                        selected_worker = data["worker"].get("worker_id")
                        if selected_worker:
                            logger.debug(f"Load balancer selected worker: {selected_worker}")
                    return task
            else:
                # Use standard endpoint with explicit worker_id
                response = requests.post(
                    f"{self.dashboard_url}/api/tasks/claim",
                    json={"worker_id": self.worker_id, "task_types": list(self._handlers.keys())},
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("task")

        except Exception as e:
            logger.debug(f"Could not claim task from server: {e}")

        # Fallback to direct database access
        return self._claim_task_from_db()

    def _claim_task_from_db(self) -> Optional[Dict]:
        """Claim a task directly from the database."""
        try:
            with get_connection() as conn:
                # Find pending task
                task = conn.execute(
                    """
                    SELECT * FROM task_queue
                    WHERE status = 'pending'
                      AND retries < max_retries
                      AND task_type IN ({})
                    ORDER BY priority DESC, created_at
                    LIMIT 1
                """.format(
                        ",".join("?" * len(self._handlers))
                    ),
                    list(self._handlers.keys()),
                ).fetchone()

                if task:
                    # Claim it
                    conn.execute(
                        """
                        UPDATE task_queue SET
                            status = 'running',
                            assigned_worker = ?,
                            started_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND status = 'pending'
                    """,
                        (self.worker_id, task["id"]),
                    )

                    return dict(task)

        except Exception as e:
            logger.error(f"Database error: {e}")

        return None

    def _complete_task(self, task_id: int, result: Any = None):
        """Mark a task as completed."""
        try:
            import requests

            requests.post(
                f"{self.dashboard_url}/api/tasks/{task_id}/complete",
                json={"worker_id": self.worker_id, "result": result},
                timeout=5,
            )
        except Exception as e:
            # Fallback to direct DB
            logger.debug(f"API call failed, falling back to direct DB: {e}")
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE task_queue SET
                        status = 'completed',
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (task_id,),
                )

    def _fail_task(self, task_id: int, error: str):
        """Mark a task as failed."""
        try:
            import requests

            requests.post(
                f"{self.dashboard_url}/api/tasks/{task_id}/fail",
                json={"worker_id": self.worker_id, "error": error},
                timeout=5,
            )
        except Exception as e:
            # Fallback to direct DB
            logger.debug(f"API call failed, falling back to direct DB: {e}")
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE task_queue SET
                        status = CASE WHEN retries + 1 >= max_retries THEN 'failed' ELSE 'pending' END,
                        retries = retries + 1,
                        error_message = ?,
                        assigned_worker = NULL,
                        started_at = NULL
                    WHERE id = ?
                """,
                    (error, task_id),
                )

    def _process_task(self, task: Dict) -> bool:
        """Process a single task."""
        task_id = task["id"]
        task_type = task["task_type"]
        task_data = json.loads(task.get("task_data", "{}"))

        logger.info(f"Processing task {task_id} ({task_type})")

        # Update session state: mark as working
        task_description = f"Task #{task_id} ({task_type})"
        self.state_manager.set_task(task_description)
        self.state_manager.increment_prompts()

        handler = self._handlers.get(task_type)
        if not handler:
            self._fail_task(task_id, f"No handler for task type: {task_type}")
            self.state_manager.set_status("idle")
            return False

        try:
            with self._lock:
                self._current_task = task

            result = handler(task_data)

            self._complete_task(task_id, result)
            self._tasks_completed += 1
            logger.info(f"Task {task_id} completed successfully")
            return True

        except Exception as e:
            error_msg = str(e)
            self._fail_task(task_id, error_msg)
            self._tasks_failed += 1
            self.state_manager.increment_errors()
            self.state_manager.set_metadata("last_error", error_msg)
            logger.error(f"Task {task_id} failed: {error_msg}")
            return False

        finally:
            with self._lock:
                self._current_task = None

            # Update session state: mark as idle
            self.state_manager.clear_task()

    # =========================================================================
    # Task Handlers
    # =========================================================================

    def _handle_shell_task(self, data: Dict) -> Dict:
        """Execute a shell command."""
        command = data.get("command")
        cwd = data.get("cwd")
        timeout = data.get("timeout", 300)

        if not command:
            raise ValueError("No command specified")

        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )

        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def _handle_python_task(self, data: Dict) -> Dict:
        """Execute a Python script or code."""
        script = data.get("script")
        code = data.get("code")
        args = data.get("args", [])
        cwd = data.get("cwd")

        if script:
            cmd = ["python3", script] + args
        elif code:
            cmd = ["python3", "-c", code]
        else:
            raise ValueError("No script or code specified")

        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=data.get("timeout", 300)
        )

        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def _handle_git_task(self, data: Dict) -> Dict:
        """Execute a git operation."""
        operation = data.get("operation")  # clone, pull, push, commit, etc.
        repo_path = data.get("repo_path")

        if operation == "clone":
            url = data.get("url")
            target = data.get("target", repo_path)
            cmd = ["git", "clone", url, target]
        elif operation == "pull":
            cmd = ["git", "-C", repo_path, "pull"]
        elif operation == "push":
            cmd = ["git", "-C", repo_path, "push"]
        elif operation == "commit":
            message = data.get("message", "Automated commit")
            subprocess.run(["git", "-C", repo_path, "add", "-A"], check=True)
            cmd = ["git", "-C", repo_path, "commit", "-m", message]
        elif operation == "status":
            cmd = ["git", "-C", repo_path, "status", "--porcelain"]
        else:
            raise ValueError(f"Unknown git operation: {operation}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def _handle_deploy_task(self, data: Dict) -> Dict:
        """Handle deployment tasks."""
        deploy_script = data.get("script")
        environment = data.get("environment", "dev")
        version = data.get("version")

        if deploy_script and Path(deploy_script).exists():
            cmd = [deploy_script, environment]
            if version:
                cmd.append(version)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        else:
            raise ValueError(f"Deploy script not found: {deploy_script}")

    def _handle_test_task(self, data: Dict) -> Dict:
        """Run tests."""
        test_command = data.get("command", "pytest")
        test_path = data.get("path", ".")
        cwd = data.get("cwd")

        cmd = f"{test_command} {test_path}"

        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=data.get("timeout", 600),
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0,
        }

    def _handle_build_task(self, data: Dict) -> Dict:
        """Handle build tasks."""
        build_command = data.get("command", "make")
        cwd = data.get("cwd")

        result = subprocess.run(
            build_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=data.get("timeout", 600),
        )

        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def _handle_tmux_task(self, data: Dict) -> Dict:
        """Handle tmux operations."""
        operation = data.get("operation")  # send, capture, create, kill
        session = data.get("session")

        if operation == "send":
            message = data.get("message")
            subprocess.run(
                ["tmux", "send-keys", "-t", session, message, "Enter"], check=True, timeout=5
            )
            return {"success": True}

        elif operation == "capture":
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return {"output": result.stdout}

        elif operation == "create":
            command = data.get("command")
            cmd = ["tmux", "new-session", "-d", "-s", session]
            if command:
                cmd.append(command)
            subprocess.run(cmd, check=True, timeout=10)
            return {"success": True}

        elif operation == "kill":
            subprocess.run(["tmux", "kill-session", "-t", session], check=True, timeout=5)
            return {"success": True}

        else:
            raise ValueError(f"Unknown tmux operation: {operation}")

    # =========================================================================
    # Worker Lifecycle
    # =========================================================================

    def _heartbeat_loop(self):
        """Background thread for sending heartbeats."""
        while self._running:
            self._send_heartbeat()
            time.sleep(self.heartbeat_interval)

    def _save_state(self):
        """Save worker state to file."""
        state = {
            "worker_id": self.worker_id,
            "node_id": self.node_id,
            "worker_type": self.worker_type,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "current_task": self._current_task,
            "running": self._running,
            "timestamp": datetime.now().isoformat(),
        }

        STATE_FILE.write_text(json.dumps(state, indent=2))

    def start(self):
        """Start the worker with graceful shutdown support."""
        self._running = True
        self._start_time = datetime.now()

        logger.info(f"Starting worker {self.worker_id} with graceful shutdown")

        # Update session state to indicate worker is initialized
        self.state_manager.set_status("idle")
        logger.debug(f"Session state initialized for {self.session_name}")

        # Register graceful shutdown handler
        self._shutdown.register()

        # Register with server
        self._register_with_server()

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat"
        )
        heartbeat_thread.start()

        # Main loop with graceful shutdown support
        try:
            while self._running and self._shutdown.should_run:
                # Don't claim new tasks if shutting down
                if self._shutdown.is_shutting_down:
                    logger.info("Shutdown in progress, not claiming new tasks")
                    time.sleep(1)
                    continue

                task = self._claim_task()

                if task:
                    # Track task with graceful shutdown
                    task_id = str(task.get("id", "unknown"))
                    with self._shutdown.task_context(task_id):
                        self._process_task(task)
                else:
                    time.sleep(self.poll_interval)

                self._save_state()

        except KeyboardInterrupt:
            logger.info("Worker interrupted")
            self._shutdown.request_shutdown(ShutdownReason.SIGINT)
        finally:
            self._running = False
            self._save_state()
            logger.info("Worker stopped")

    def stop(self):
        """Stop the worker gracefully."""
        logger.info(f"Stop requested for worker {self.worker_id}")
        self._shutdown.request_shutdown(ShutdownReason.MANUAL)


def run_daemon():
    """Run worker as a daemon with graceful shutdown support."""
    # Check if already running
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Worker already running (PID {pid})")
            return
        except ProcessLookupError:
            PID_FILE.unlink()

    # Fork
    pid = os.fork()
    if pid > 0:
        print(f"Worker started (PID {pid})")
        return

    # Daemon setup
    os.setsid()
    os.chdir("/")

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    # Start worker - GracefulShutdown handles signals internally
    worker = TaskWorker()
    worker.start()
    # Note: Worker's graceful shutdown will clean up PID file


def stop_daemon():
    """Stop the daemon."""
    if not PID_FILE.exists():
        print("Worker not running")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent stop signal to worker (PID {pid})")

        # Wait for process to stop
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print("Worker stopped")
                PID_FILE.unlink()
                return

        print("Worker did not stop, sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
        PID_FILE.unlink()

    except ProcessLookupError:
        print("Worker not running")
        PID_FILE.unlink()


def show_status():
    """Show worker status."""
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

        print(
            f"""
Worker Status
=============
ID:              {state.get('worker_id', 'N/A')}
Node:            {state.get('node_id', 'N/A')}
Type:            {state.get('worker_type', 'N/A')}
Running:         {state.get('running', False)}
Started:         {state.get('start_time', 'N/A')}
Tasks Completed: {state.get('tasks_completed', 0)}
Tasks Failed:    {state.get('tasks_failed', 0)}
Current Task:    {(state.get('current_task') or {}).get('id', 'None')}
Last Update:     {state.get('timestamp', 'N/A')}
"""
        )
    else:
        print("No worker state found")
        state = {}  # Initialize empty state for PID check below

    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Process: Running (PID {pid})")
        except ProcessLookupError:
            print("Process: Not running (stale PID file)")
    else:
        print("Process: Not running")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Task Worker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--worker-id", help="Worker ID")
    parser.add_argument("--node-id", default="local", help="Node ID")
    parser.add_argument("--worker-type", default="general", help="Worker type")
    parser.add_argument("--poll-interval", type=int, default=5, help="Poll interval in seconds")
    parser.add_argument(
        "--dashboard-url", default="http://100.112.58.92:8080", help="Dashboard URL"
    )
    parser.add_argument(
        "--load-balanced", action="store_true", help="Use load-balanced task claiming"
    )
    parser.add_argument(
        "--lb-strategy",
        default="least_loaded",
        choices=["round_robin", "least_loaded", "weighted", "skill_based", "adaptive"],
        help="Load balancing strategy (default: least_loaded)",
    )

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        show_status()
    elif args.daemon:
        run_daemon()
    else:
        # Run in foreground
        worker = TaskWorker(
            worker_id=args.worker_id,
            node_id=args.node_id,
            worker_type=args.worker_type,
            poll_interval=args.poll_interval,
            dashboard_url=args.dashboard_url,
            use_load_balancing=args.load_balanced,
            load_balancing_strategy=args.lb_strategy,
        )
        worker.start()


if __name__ == "__main__":
    main()
