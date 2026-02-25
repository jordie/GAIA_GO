"""
Worker Recovery Service

Automatically detects and recovers from worker failures:
- Monitors worker heartbeats for staleness
- Releases tasks assigned to failed workers back to the queue
- Sends notifications about worker failures
- Optionally attempts to restart failed workers

Usage:
    from services.worker_recovery import start_recovery_service, stop_recovery_service

    # Start the recovery service (runs in background thread)
    start_recovery_service(db_path, check_interval=60)

    # Stop the service
    stop_recovery_service()
"""

import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
SERVICE_DIR = Path(__file__).parent
BASE_DIR = SERVICE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from graceful_shutdown import GracefulShutdown, ShutdownReason

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_HEARTBEAT_TIMEOUT = 120  # seconds before worker considered stale
DEFAULT_CHECK_INTERVAL = 60  # seconds between recovery checks
DEFAULT_TASK_TIMEOUT = 600  # seconds before running task considered stuck

# Known worker definitions for restart capability
KNOWN_WORKERS = {
    "project_orchestrator": {
        "pid_file": "/tmp/project_orchestrator.pid",
        "start_cmd": ["python3", "workers/project_orchestrator.py", "--daemon"],
        "description": "Project Orchestrator",
    },
    "auto_confirm": {
        "pid_file": "/tmp/auto_confirm.lock",
        "start_cmd": ["python3", "workers/auto_confirm_worker.py", "--daemon"],
        "description": "Auto Confirm Worker",
    },
    "task_worker": {
        "pid_file": "/tmp/task_worker.pid",
        "start_cmd": ["python3", "workers/task_worker.py", "--daemon"],
        "description": "Task Worker",
    },
    "service_checker": {
        "pid_file": "/tmp/service_checker.pid",
        "start_cmd": ["python3", "workers/service_checker.py", "--daemon"],
        "description": "Service Checker",
    },
}


class WorkerRecoveryService:
    """Service for automatic worker failure detection and recovery."""

    def __init__(
        self,
        db_path: str,
        heartbeat_timeout: int = DEFAULT_HEARTBEAT_TIMEOUT,
        task_timeout: int = DEFAULT_TASK_TIMEOUT,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        auto_restart: bool = False,
        notify_on_failure: bool = True,
    ):
        """
        Initialize the worker recovery service.

        Args:
            db_path: Path to the SQLite database
            heartbeat_timeout: Seconds before a worker is considered stale
            task_timeout: Seconds before a running task is considered stuck
            check_interval: Seconds between recovery checks
            auto_restart: Whether to attempt automatic worker restarts
            notify_on_failure: Whether to send notifications on worker failures
        """
        self.db_path = db_path
        self.heartbeat_timeout = heartbeat_timeout
        self.task_timeout = task_timeout
        self.check_interval = check_interval
        self.auto_restart = auto_restart
        self.notify_on_failure = notify_on_failure

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Track recovery actions to avoid spam
        self._last_recovery: Dict[str, datetime] = {}
        self._recovery_cooldown = 300  # 5 minutes between recovery attempts

        # Graceful shutdown handler
        self._shutdown = GracefulShutdown(
            worker_id="worker-recovery-service",
            worker_type="recovery-service",
            shutdown_timeout=10,
            on_shutdown=self._on_shutdown,
            notify_dashboard=False,
            force_exit=False,
        )

    def _on_shutdown(self):
        """Called when shutdown signal is received."""
        logger.info("Worker recovery service received shutdown signal")
        self._running = False

    def start(self):
        """Start the recovery service in a background thread."""
        with self._lock:
            if self._running:
                logger.warning("Worker recovery service already running")
                return

            self._running = True
            self._shutdown.register()
            self._thread = threading.Thread(
                target=self._run_loop, name="WorkerRecoveryService", daemon=True
            )
            self._thread.start()
            logger.info(f"Worker recovery service started (interval: {self.check_interval}s)")

    def stop(self):
        """Stop the recovery service gracefully."""
        logger.info("Stopping worker recovery service...")
        self._shutdown.request_shutdown(ShutdownReason.MANUAL)
        with self._lock:
            self._running = False
            if self._thread:
                self._thread.join(timeout=5)
                self._thread = None
            logger.info("Worker recovery service stopped")

    def is_running(self) -> bool:
        """Check if the service is running."""
        return self._running and self._shutdown.should_run

    def _run_loop(self):
        """Main recovery loop with graceful shutdown support."""
        while self._running and self._shutdown.should_run:
            try:
                self._check_and_recover()
            except Exception as e:
                logger.error(f"Error in recovery check: {e}")

            # Sleep in small increments to respond to stop quickly
            for _ in range(self.check_interval):
                if not self._running or not self._shutdown.should_run:
                    break
                time.sleep(1)

    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _check_and_recover(self):
        """Check for failed workers and recover."""
        results = {
            "stale_workers": [],
            "stuck_tasks": [],
            "recovered_tasks": [],
            "restarted_workers": [],
            "notifications_sent": [],
        }

        try:
            # Check for stale workers (no heartbeat)
            stale_workers = self._find_stale_workers()
            results["stale_workers"] = stale_workers

            if stale_workers:
                logger.warning(f"Found {len(stale_workers)} stale workers")

                for worker in stale_workers:
                    self._handle_stale_worker(worker, results)

            # Check for stuck tasks (running too long)
            stuck_tasks = self._find_stuck_tasks()
            results["stuck_tasks"] = stuck_tasks

            if stuck_tasks:
                logger.warning(f"Found {len(stuck_tasks)} stuck tasks")

                for task in stuck_tasks:
                    self._handle_stuck_task(task, results)

            # Check PID-based workers
            self._check_pid_workers(results)

            # Log summary
            if any(results.values()):
                logger.info(
                    f"Recovery check complete: "
                    f"{len(results['recovered_tasks'])} tasks recovered, "
                    f"{len(results['restarted_workers'])} workers restarted"
                )

        except sqlite3.Error as e:
            logger.error(f"Database error in recovery check: {e}")

    def _find_stale_workers(self) -> List[Dict]:
        """Find workers with stale heartbeats."""
        cutoff = datetime.now() - timedelta(seconds=self.heartbeat_timeout)
        cutoff_str = cutoff.isoformat()

        with self._get_db_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, node_id, worker_type, status, current_task_id, last_heartbeat
                FROM workers
                WHERE status IN ('busy', 'idle')
                  AND last_heartbeat < ?
            """,
                (cutoff_str,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def _find_stuck_tasks(self) -> List[Dict]:
        """Find tasks that have been running too long.

        Uses per-task-type timeouts when available (timeout_seconds column),
        otherwise falls back to the default task_timeout.
        """
        now = datetime.now()

        with self._get_db_connection() as conn:
            # Get all running tasks with their timeout configuration
            cursor = conn.execute(
                """
                SELECT id, task_type, assigned_worker, started_at, retries, max_retries, timeout_seconds
                FROM task_queue
                WHERE status = 'running'
            """
            )

            stuck_tasks = []
            for row in cursor.fetchall():
                task = dict(row)
                started_at = task.get("started_at")
                if not started_at:
                    continue

                # Parse started_at timestamp
                try:
                    if isinstance(started_at, str):
                        started_time = datetime.fromisoformat(
                            started_at.replace("Z", "+00:00").replace("+00:00", "")
                        )
                    else:
                        started_time = started_at
                except (ValueError, TypeError):
                    continue

                # Get timeout - use task-specific timeout, or type default, or global default
                task_timeout = task.get("timeout_seconds")
                if not task_timeout:
                    # Try to get from app config (import dynamically to avoid circular import)
                    try:
                        from app import get_task_timeout

                        task_timeout = get_task_timeout(task.get("task_type", "default"))
                    except ImportError:
                        task_timeout = self.task_timeout

                # Check if task has exceeded its timeout
                elapsed = (now - started_time).total_seconds()
                if elapsed > task_timeout:
                    task["elapsed_seconds"] = int(elapsed)
                    task["timeout_used"] = task_timeout
                    stuck_tasks.append(task)

            return stuck_tasks

    def _handle_stale_worker(self, worker: Dict, results: Dict):
        """Handle a stale worker - release its tasks and mark as offline."""
        worker_id = worker["id"]

        # Check cooldown
        if self._is_in_cooldown(f"worker:{worker_id}"):
            return

        with self._get_db_connection() as conn:
            # Mark worker as offline
            conn.execute(
                """
                UPDATE workers SET
                    status = 'offline',
                    current_task_id = NULL
                WHERE id = ?
            """,
                (worker_id,),
            )

            # Release any tasks assigned to this worker
            cursor = conn.execute(
                """
                UPDATE task_queue SET
                    status = 'pending',
                    assigned_worker = NULL,
                    started_at = NULL,
                    error_message = 'Worker went offline - task reassigned'
                WHERE assigned_worker = ? AND status = 'running'
                RETURNING id
            """,
                (worker_id,),
            )

            released_tasks = [row["id"] for row in cursor.fetchall()]
            conn.commit()

            results["recovered_tasks"].extend(released_tasks)

        logger.info(f"Worker {worker_id} marked offline, released {len(released_tasks)} tasks")
        self._set_cooldown(f"worker:{worker_id}")

        # Send notification
        if self.notify_on_failure and released_tasks:
            self._notify_worker_failure(worker, released_tasks)
            results["notifications_sent"].append(worker_id)

    def _handle_stuck_task(self, task: Dict, results: Dict):
        """Handle a stuck task - release it back to the queue."""
        task_id = task["id"]

        # Check cooldown
        if self._is_in_cooldown(f"task:{task_id}"):
            return

        with self._get_db_connection() as conn:
            # Check if task should be retried or marked as failed
            retries = task.get("retries", 0)
            max_retries = task.get("max_retries", 3)

            if retries < max_retries:
                # Release back to queue for retry
                conn.execute(
                    """
                    UPDATE task_queue SET
                        status = 'pending',
                        assigned_worker = NULL,
                        started_at = NULL,
                        retries = retries + 1,
                        error_message = 'Task timed out - will retry'
                    WHERE id = ?
                """,
                    (task_id,),
                )
                logger.info(
                    f"Task {task_id} timed out, released for retry ({retries + 1}/{max_retries})"
                )
            else:
                # Mark as failed
                conn.execute(
                    """
                    UPDATE task_queue SET
                        status = 'failed',
                        error_message = 'Task timed out after max retries'
                    WHERE id = ?
                """,
                    (task_id,),
                )
                logger.warning(f"Task {task_id} failed after {max_retries} retries")

            conn.commit()
            results["recovered_tasks"].append(task_id)

        self._set_cooldown(f"task:{task_id}")

    def _check_pid_workers(self, results: Dict):
        """Check PID-based workers and optionally restart them."""
        for worker_name, config in KNOWN_WORKERS.items():
            pid_file = Path(config["pid_file"])

            if not pid_file.exists():
                continue  # Worker not started

            try:
                pid = int(pid_file.read_text().strip())

                # Check if process is running
                try:
                    os.kill(pid, 0)
                    # Process is running
                    continue
                except OSError:
                    # Process is dead but PID file exists
                    logger.warning(f"Worker {worker_name} (PID {pid}) is dead but PID file exists")

                    # Clean up PID file
                    pid_file.unlink(missing_ok=True)

                    # Attempt restart if enabled
                    if self.auto_restart:
                        if self._is_in_cooldown(f"restart:{worker_name}"):
                            continue

                        if self._restart_worker(worker_name, config):
                            results["restarted_workers"].append(worker_name)
                            self._set_cooldown(f"restart:{worker_name}")

                    # Notify about failure
                    if self.notify_on_failure:
                        self._notify_worker_crash(worker_name, config)

            except (ValueError, IOError) as e:
                logger.debug(f"Could not check worker {worker_name}: {e}")

    def _restart_worker(self, worker_name: str, config: Dict) -> bool:
        """Attempt to restart a worker."""
        try:
            start_cmd = config.get("start_cmd")
            if not start_cmd:
                logger.warning(f"No start command for worker {worker_name}")
                return False

            # Run the start command
            result = subprocess.run(
                start_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(__file__).parent.parent),
            )

            if result.returncode == 0:
                logger.info(f"Successfully restarted worker {worker_name}")
                return True
            else:
                logger.error(f"Failed to restart {worker_name}: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout restarting worker {worker_name}")
            return False
        except Exception as e:
            logger.error(f"Error restarting worker {worker_name}: {e}")
            return False

    def _notify_worker_failure(self, worker: Dict, released_tasks: List[int]):
        """Send notification about worker failure."""
        try:
            from services.notifications import notify_worker_down

            notify_worker_down(
                worker_name=worker.get("worker_type", "Unknown"),
                worker_id=worker.get("id"),
                last_seen=worker.get("last_heartbeat"),
                error=f"Worker went offline. Released {len(released_tasks)} tasks.",
                db_path=self.db_path,
            )
        except Exception as e:
            logger.warning(f"Could not send worker failure notification: {e}")

    def _notify_worker_crash(self, worker_name: str, config: Dict):
        """Send notification about worker crash."""
        try:
            from services.notifications import notify_worker_down

            notify_worker_down(
                worker_name=config.get("description", worker_name),
                worker_id=worker_name,
                error="Worker process crashed unexpectedly",
                db_path=self.db_path,
            )
        except Exception as e:
            logger.warning(f"Could not send worker crash notification: {e}")

    def _is_in_cooldown(self, key: str) -> bool:
        """Check if a recovery action is in cooldown."""
        last_time = self._last_recovery.get(key)
        if not last_time:
            return False
        return (datetime.now() - last_time).total_seconds() < self._recovery_cooldown

    def _set_cooldown(self, key: str):
        """Set cooldown for a recovery action."""
        self._last_recovery[key] = datetime.now()

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the recovery service."""
        return {
            "running": self._running,
            "heartbeat_timeout": self.heartbeat_timeout,
            "task_timeout": self.task_timeout,
            "check_interval": self.check_interval,
            "auto_restart": self.auto_restart,
            "notify_on_failure": self.notify_on_failure,
            "recent_recoveries": len(self._last_recovery),
            "thread_alive": self._thread.is_alive() if self._thread else False,
        }

    def run_check_now(self) -> Dict[str, Any]:
        """Run a recovery check immediately and return results."""
        results = {
            "stale_workers": [],
            "stuck_tasks": [],
            "recovered_tasks": [],
            "restarted_workers": [],
            "notifications_sent": [],
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Find issues
            results["stale_workers"] = self._find_stale_workers()
            results["stuck_tasks"] = self._find_stuck_tasks()

            # Handle them
            for worker in results["stale_workers"]:
                self._handle_stale_worker(worker, results)

            for task in results["stuck_tasks"]:
                self._handle_stuck_task(task, results)

            self._check_pid_workers(results)

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Error in manual recovery check: {e}")

        return results


# Global instance
_recovery_service: Optional[WorkerRecoveryService] = None


def get_recovery_service() -> Optional[WorkerRecoveryService]:
    """Get the global recovery service instance."""
    return _recovery_service


def start_recovery_service(
    db_path: str,
    heartbeat_timeout: int = DEFAULT_HEARTBEAT_TIMEOUT,
    task_timeout: int = DEFAULT_TASK_TIMEOUT,
    check_interval: int = DEFAULT_CHECK_INTERVAL,
    auto_restart: bool = False,
    notify_on_failure: bool = True,
) -> WorkerRecoveryService:
    """Start the global worker recovery service."""
    global _recovery_service

    if _recovery_service and _recovery_service.is_running():
        logger.warning("Recovery service already running")
        return _recovery_service

    _recovery_service = WorkerRecoveryService(
        db_path=db_path,
        heartbeat_timeout=heartbeat_timeout,
        task_timeout=task_timeout,
        check_interval=check_interval,
        auto_restart=auto_restart,
        notify_on_failure=notify_on_failure,
    )
    _recovery_service.start()
    return _recovery_service


def stop_recovery_service():
    """Stop the global worker recovery service."""
    global _recovery_service

    if _recovery_service:
        _recovery_service.stop()
        _recovery_service = None
