#!/usr/bin/env python3
"""
Auto-Confirm Worker

A background worker that handles auto-confirmation tasks for Claude prompts
and other automation that requires confirmations.

Usage:
    python3 confirm_worker.py                # Run worker
    python3 confirm_worker.py --daemon       # Run as daemon
    python3 confirm_worker.py --stop         # Stop daemon
    python3 confirm_worker.py --status       # Check status
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import get_connection

# Worker configuration
PID_FILE = Path("/tmp/architect_confirm_worker.pid")
STATE_FILE = Path("/tmp/architect_confirm_worker_state.json")
LOG_FILE = Path("/tmp/architect_confirm_worker.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("ConfirmWorker")


class ConfirmWorker:
    """
    Background worker for auto-confirmation tasks.
    """

    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self.running = False
        self.worker_id = f"confirm-{os.getpid()}"

    def start(self):
        """Start the worker."""
        self.running = True
        logger.info(f"Starting ConfirmWorker {self.worker_id}")
        self._register()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        try:
            while self.running:
                self._process_confirmations()
                self._heartbeat()
                time.sleep(self.poll_interval)
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            self._unregister()

    def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("Stopping ConfirmWorker")

    def _handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop()

    def _register(self):
        """Register worker in database."""
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO workers (id, worker_type, status, last_heartbeat)
                    VALUES (?, 'confirm', 'running', ?)
                """,
                    (self.worker_id, datetime.now().isoformat()),
                )
        except Exception as e:
            logger.error(f"Failed to register: {e}")

    def _unregister(self):
        """Unregister worker from database."""
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM workers WHERE id = ?", (self.worker_id,))
        except Exception as e:
            logger.error(f"Failed to unregister: {e}")

    def _heartbeat(self):
        """Update heartbeat."""
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE workers SET last_heartbeat = ? WHERE id = ?
                """,
                    (datetime.now().isoformat(), self.worker_id),
                )
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")

    def _process_confirmations(self):
        """Process pending confirmation tasks."""
        try:
            with get_connection() as conn:
                # Get pending confirm tasks
                tasks = conn.execute(
                    """
                    SELECT * FROM task_queue
                    WHERE task_type = 'confirm' AND status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 5
                """
                ).fetchall()

                for task in tasks:
                    self._handle_confirm_task(conn, task)

        except Exception as e:
            logger.error(f"Error processing confirmations: {e}")

    def _handle_confirm_task(self, conn, task):
        """Handle a single confirmation task."""
        try:
            task_id = task["id"]
            data = json.loads(task["data"]) if task["data"] else {}

            logger.info(f"Processing confirm task {task_id}: {data.get('action', 'unknown')}")

            # Mark as in progress
            conn.execute(
                """
                UPDATE task_queue SET status = 'running', claimed_by = ?, claimed_at = ?
                WHERE id = ?
            """,
                (self.worker_id, datetime.now().isoformat(), task_id),
            )
            conn.commit()

            # Process based on action type
            action = data.get("action", "")
            result = {"success": True}

            if action == "tmux_confirm":
                result = self._confirm_tmux(data)
            elif action == "approve_all":
                result = self._approve_all(data)
            else:
                result = {"success": True, "message": "Auto-confirmed"}

            # Mark complete
            conn.execute(
                """
                UPDATE task_queue SET status = 'completed', completed_at = ?, result = ?
                WHERE id = ?
            """,
                (datetime.now().isoformat(), json.dumps(result), task_id),
            )
            conn.commit()

            logger.info(f"Completed task {task_id}")

        except Exception as e:
            logger.error(f"Failed to handle task: {e}")
            conn.execute(
                """
                UPDATE task_queue SET status = 'failed', error = ?
                WHERE id = ?
            """,
                (str(e), task["id"]),
            )
            conn.commit()

    def _confirm_tmux(self, data):
        """Send confirmation to a tmux session."""
        session = data.get("session")
        response = data.get("response", "y")

        if session:
            try:
                subprocess.run(
                    ["tmux", "send-keys", "-t", session, response, "Enter"],
                    check=True,
                    capture_output=True,
                )
                return {"success": True, "session": session, "response": response}
            except subprocess.CalledProcessError as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "No session specified"}

    def _approve_all(self, data):
        """Approve all pending items of a type."""
        return {"success": True, "message": "Approved all"}


def daemonize():
    """Run as daemon process."""
    if os.fork() > 0:
        sys.exit(0)

    os.setsid()

    if os.fork() > 0:
        sys.exit(0)

    # Write PID file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    with open(str(LOG_FILE), "a") as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())


def stop_daemon():
    """Stop the daemon process."""
    if PID_FILE.exists():
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink()
            print(f"Stopped daemon (PID {pid})")
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink()
            print("Daemon not running")
    else:
        print("No PID file found")


def check_status():
    """Check daemon status."""
    if PID_FILE.exists():
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            print(f"Daemon running (PID {pid})")
            return True
        except (ProcessLookupError, ValueError):
            print("Daemon not running (stale PID file)")
            return False
    else:
        print("Daemon not running")
        return False


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        print("Starting confirm worker daemon...")
        daemonize()
        worker = ConfirmWorker()
        worker.start()
    elif "--stop" in sys.argv:
        stop_daemon()
    elif "--status" in sys.argv:
        check_status()
    else:
        # Run in foreground
        worker = ConfirmWorker()
        worker.start()
