#!/usr/bin/env python3
"""
Delegator - Central task assignment coordinator with file-based locking.

Prevents database race conditions by:
1. Using file-based locks (fcntl.flock) for exclusive access
2. Queueing tasks instead of direct DB writes
3. Rate limiting worker spawning
4. Serializing database operations

Usage:
    # Queue a task
    python3 delegator.py --queue "task_type" "task_data_json"

    # Process queue (run as daemon)
    python3 delegator.py --daemon

    # Check status
    python3 delegator.py --status
"""

import fcntl
import json
import logging
import os
import signal
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data" / "prod"
DB_PATH = DATA_DIR / "architect.db"
LOCK_DIR = PROJECT_DIR / "data" / "locks"
QUEUE_DIR = PROJECT_DIR / "data" / "queue"
LOG_FILE = Path("/tmp/delegator.log")
PID_FILE = Path("/tmp/delegator.pid")

# Rate limiting
MAX_TASKS_PER_SECOND = 10
MIN_TASK_INTERVAL = 1.0 / MAX_TASKS_PER_SECOND
WORKER_SPAWN_COOLDOWN = 5.0  # seconds between worker spawns

# Ensure directories exist
LOCK_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class FileLock:
    """File-based lock using fcntl.flock for cross-process synchronization."""

    def __init__(self, name: str, timeout: float = 30.0):
        self.name = name
        self.timeout = timeout
        self.lock_path = LOCK_DIR / f"{name}.lock"
        self.lock_file = None
        self.acquired = False

    def acquire(self) -> bool:
        """Acquire the lock with timeout."""
        start_time = time.time()
        self.lock_file = open(self.lock_path, "w")

        while True:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.acquired = True
                self.lock_file.write(f"{os.getpid()}\n{datetime.now().isoformat()}")
                self.lock_file.flush()
                return True
            except (IOError, OSError):
                if time.time() - start_time > self.timeout:
                    logger.warning(f"Lock acquisition timeout for {self.name}")
                    self.lock_file.close()
                    return False
                time.sleep(0.1)

    def release(self):
        """Release the lock."""
        if self.lock_file and self.acquired:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                self.acquired = False
            except Exception as e:
                logger.error(f"Error releasing lock {self.name}: {e}")

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Failed to acquire lock: {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


@contextmanager
def database_lock(operation: str = "db"):
    """Context manager for database operations with locking."""
    lock = FileLock(f"db_{operation}")
    try:
        if lock.acquire():
            yield
        else:
            raise RuntimeError(f"Database lock timeout: {operation}")
    finally:
        lock.release()


def get_db_connection():
    """Get a database connection with proper timeout settings."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


class TaskQueue:
    """File-based task queue for serialized processing."""

    def __init__(self):
        self.queue_file = QUEUE_DIR / "tasks.json"
        self.lock = FileLock("task_queue")

    def add(self, task_type: str, data: Dict[str, Any], priority: int = 5) -> str:
        """Add a task to the queue."""
        task_id = f"{int(time.time() * 1000)}_{os.getpid()}"
        task = {
            "id": task_id,
            "type": task_type,
            "data": data,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "attempts": 0,
        }

        with self.lock:
            tasks = self._load_tasks()
            tasks.append(task)
            self._save_tasks(tasks)

        logger.info(f"Queued task {task_id}: {task_type}")
        return task_id

    def get_next(self) -> Optional[Dict]:
        """Get the next pending task (highest priority first)."""
        with self.lock:
            tasks = self._load_tasks()
            pending = [t for t in tasks if t["status"] == "pending"]

            if not pending:
                return None

            # Sort by priority (higher first), then by creation time
            # Handle both numeric priorities and string priorities ("high", "medium", "low")
            def get_priority(t):
                p = t.get("priority", 5)
                if isinstance(p, int):
                    return -p
                # Map string priorities to numbers
                priority_map = {"critical": -10, "high": -8, "medium": -5, "low": -2}
                return priority_map.get(str(p).lower(), -5)

            pending.sort(key=lambda t: (get_priority(t), t["created_at"]))
            task = pending[0]

            # Mark as processing
            for t in tasks:
                if t["id"] == task["id"]:
                    t["status"] = "processing"
                    t["started_at"] = datetime.now().isoformat()
                    t["attempts"] = t.get("attempts", 0) + 1
                    break

            self._save_tasks(tasks)
            return task

    def complete(self, task_id: str, success: bool = True, result: Any = None):
        """Mark a task as completed or failed."""
        with self.lock:
            tasks = self._load_tasks()
            for task in tasks:
                if task["id"] == task_id:
                    task["status"] = "completed" if success else "failed"
                    task["completed_at"] = datetime.now().isoformat()
                    task["result"] = result
                    break
            self._save_tasks(tasks)

        logger.info(f"Task {task_id} {'completed' if success else 'failed'}")

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        with self.lock:
            tasks = self._load_tasks()

        stats = {
            "total": len(tasks),
            "pending": len([t for t in tasks if t["status"] == "pending"]),
            "processing": len([t for t in tasks if t["status"] == "processing"]),
            "completed": len([t for t in tasks if t["status"] == "completed"]),
            "failed": len([t for t in tasks if t["status"] == "failed"]),
        }
        return stats

    def cleanup(self, max_age_hours: int = 24):
        """Remove old completed/failed tasks."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        with self.lock:
            tasks = self._load_tasks()
            tasks = [
                t
                for t in tasks
                if (
                    t["status"] in ("pending", "processing")
                    or datetime.fromisoformat(t["created_at"]).timestamp() > cutoff
                )
            ]
            self._save_tasks(tasks)

    def _load_tasks(self) -> list:
        """Load tasks from file."""
        if self.queue_file.exists():
            try:
                return json.loads(self.queue_file.read_text())
            except:
                return []
        return []

    def _save_tasks(self, tasks: list):
        """Save tasks to file."""
        self.queue_file.write_text(json.dumps(tasks, indent=2))


class Delegator:
    """Central coordinator for task delegation with rate limiting."""

    def __init__(self):
        self.queue = TaskQueue()
        self.last_task_time = 0
        self.last_worker_spawn = 0
        self.running = False

    def delegate_db_write(self, table: str, operation: str, data: Dict) -> bool:
        """Delegate a database write operation with locking."""
        with database_lock(f"write_{table}"):
            try:
                with get_db_connection() as conn:
                    if operation == "insert":
                        columns = ", ".join(data.keys())
                        placeholders = ", ".join("?" * len(data))
                        conn.execute(
                            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                            list(data.values()),
                        )
                    elif operation == "update":
                        where_id = data.pop("id")
                        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
                        conn.execute(
                            f"UPDATE {table} SET {set_clause} WHERE id = ?",
                            list(data.values()) + [where_id],
                        )
                    elif operation == "delete":
                        conn.execute(f"DELETE FROM {table} WHERE id = ?", [data["id"]])

                    conn.commit()
                    return True
            except Exception as e:
                logger.error(f"DB write failed: {e}")
                return False

    def rate_limit(self):
        """Enforce rate limiting between tasks."""
        elapsed = time.time() - self.last_task_time
        if elapsed < MIN_TASK_INTERVAL:
            time.sleep(MIN_TASK_INTERVAL - elapsed)
        self.last_task_time = time.time()

    def can_spawn_worker(self) -> bool:
        """Check if enough time has passed to spawn another worker."""
        return time.time() - self.last_worker_spawn >= WORKER_SPAWN_COOLDOWN

    def record_worker_spawn(self):
        """Record that a worker was spawned."""
        self.last_worker_spawn = time.time()

    def process_task(self, task: Dict) -> bool:
        """Process a single task."""
        task_type = task.get("type", "unknown")
        data = task.get("data", {})

        try:
            if task_type == "db_write":
                return self.delegate_db_write(data["table"], data["operation"], data["values"])
            elif task_type == "spawn_worker":
                if self.can_spawn_worker():
                    self.record_worker_spawn()
                    logger.info(f"Worker spawn allowed: {data}")
                    return True
                else:
                    logger.warning("Worker spawn rate limited")
                    return False
            elif task_type == "shell" and task.get("command"):
                # Handle shell command tasks from queue
                import subprocess

                cmd = task["command"]
                logger.info(f"Executing shell task: {task.get('title', cmd[:50])}")
                result = subprocess.run(cmd, shell=True, capture_output=True, timeout=300)
                if result.returncode != 0:
                    logger.warning(
                        f"Shell task returned {result.returncode}: {result.stderr.decode()[:200]}"
                    )
                return result.returncode == 0
            elif task_type in ("feature", "bug"):
                # Feature/bug tasks are informational - mark as processed
                logger.info(f"Task recorded: {task.get('title', 'unknown')}")
                return True
            else:
                logger.warning(f"Unknown task type: {task_type}")
                return False
        except Exception as e:
            logger.error(f"Task processing error: {e}")
            return False

    def run_daemon(self):
        """Run as a daemon processing the task queue."""
        self.running = True
        logger.info("Delegator daemon started")

        while self.running:
            try:
                task = self.queue.get_next()

                if task:
                    self.rate_limit()
                    success = self.process_task(task)
                    self.queue.complete(task["id"], success)
                else:
                    time.sleep(0.5)

                # Periodic cleanup
                if int(time.time()) % 3600 == 0:
                    self.queue.cleanup()

            except Exception as e:
                logger.error(f"Daemon error: {e}")
                time.sleep(1)

    def stop(self):
        """Stop the daemon."""
        self.running = False


# Global delegator instance
_delegator = None


def get_delegator() -> Delegator:
    """Get the global delegator instance."""
    global _delegator
    if _delegator is None:
        _delegator = Delegator()
    return _delegator


def write_pid():
    """Write PID file."""
    PID_FILE.write_text(str(os.getpid()))


def cleanup(signum=None, frame=None):
    """Clean up on exit."""
    logger.info("Delegator stopping...")
    if _delegator:
        _delegator.stop()
    if PID_FILE.exists():
        PID_FILE.unlink()
    sys.exit(0)


def is_running() -> Optional[int]:
    """Check if delegator is already running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return pid
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink()
    return None


def start_daemon():
    """Start as background daemon."""
    pid = is_running()
    if pid:
        print(f"Delegator already running (PID: {pid})")
        return

    if os.fork() > 0:
        print("Delegator started in background")
        print(f"Log: {LOG_FILE}")
        return

    os.setsid()

    if os.fork() > 0:
        os._exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    write_pid()
    get_delegator().run_daemon()


def stop_daemon():
    """Stop the background daemon."""
    pid = is_running()
    if pid:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped delegator (PID: {pid})")
    else:
        print("Delegator is not running")


def show_status():
    """Show current status."""
    pid = is_running()
    if pid:
        print(f"Delegator is running (PID: {pid})")
    else:
        print("Delegator is not running")

    print("\nQueue Stats:")
    stats = TaskQueue().get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print(f"\nLock files in {LOCK_DIR}:")
    for lock_file in LOCK_DIR.glob("*.lock"):
        print(f"  {lock_file.name}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: delegator.py [--daemon|--stop|--status|--queue]")
        print("  --daemon           Start as background daemon")
        print("  --stop             Stop the daemon")
        print("  --status           Show status and queue stats")
        print("  --queue TYPE DATA  Add task to queue")
        return

    cmd = sys.argv[1]

    if cmd == "--daemon":
        start_daemon()
    elif cmd == "--stop":
        stop_daemon()
    elif cmd == "--status":
        show_status()
    elif cmd == "--queue" and len(sys.argv) >= 4:
        task_type = sys.argv[2]
        data = json.loads(sys.argv[3])
        task_id = TaskQueue().add(task_type, data)
        print(f"Queued: {task_id}")
    else:
        print("Invalid command")


if __name__ == "__main__":
    main()
