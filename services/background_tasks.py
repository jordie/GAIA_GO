"""Background task manager for rate limiting and resource monitoring.

Handles periodic cleanup, monitoring, and metrics collection.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for rate limiting and monitoring."""

    def __init__(self):
        """Initialize the background task manager."""
        self.tasks: dict = {}
        self._running = False
        self._threads: dict = {}
        self._lock = threading.Lock()

    def register_task(
        self,
        task_name: str,
        task_func: Callable,
        interval_seconds: int,
        start_immediately: bool = False
    ) -> bool:
        """Register a background task.

        Args:
            task_name: Unique name for the task
            task_func: Callable to execute (no arguments)
            interval_seconds: How often to run the task
            start_immediately: If True, run immediately on first execution

        Returns:
            True if registered successfully
        """
        try:
            with self._lock:
                if task_name in self.tasks:
                    logger.warning(f"Task already registered: {task_name}")
                    return False

                self.tasks[task_name] = {
                    "func": task_func,
                    "interval": interval_seconds,
                    "start_immediately": start_immediately,
                    "last_run": None,
                    "failures": 0,
                    "total_runs": 0,
                    "total_time_ms": 0
                }

                logger.info(f"Registered task: {task_name} (interval: {interval_seconds}s)")
                return True
        except Exception as e:
            logger.error(f"Error registering task {task_name}: {e}")
            return False

    def start(self) -> None:
        """Start all registered background tasks."""
        try:
            with self._lock:
                if self._running:
                    logger.warning("Background tasks already running")
                    return

                self._running = True

            # Start a worker thread for each task
            for task_name in list(self.tasks.keys()):
                thread = threading.Thread(
                    target=self._task_worker,
                    args=(task_name,),
                    daemon=True,
                    name=f"BGTask-{task_name}"
                )
                self._threads[task_name] = thread
                thread.start()

            logger.info(f"Started {len(self.tasks)} background tasks")
        except Exception as e:
            logger.error(f"Error starting background tasks: {e}")

    def stop(self) -> None:
        """Stop all background tasks."""
        try:
            with self._lock:
                self._running = False

            # Wait for threads to finish (with timeout)
            for task_name, thread in self._threads.items():
                if thread.is_alive():
                    thread.join(timeout=5)

            self._threads.clear()
            logger.info("Stopped background tasks")
        except Exception as e:
            logger.error(f"Error stopping background tasks: {e}")

    def _task_worker(self, task_name: str) -> None:
        """Worker thread for a single background task.

        Args:
            task_name: Name of the task to execute
        """
        task_info = self.tasks.get(task_name)
        if not task_info:
            return

        if task_info["start_immediately"]:
            time.sleep(1)  # Small delay to ensure system is ready

        logger.info(f"Started task worker: {task_name}")

        while self._running:
            try:
                # Check if it's time to run
                now = datetime.now()
                last_run = task_info["last_run"]

                if last_run is None or \
                   (now - last_run).total_seconds() >= task_info["interval"]:
                    # Run the task
                    start_time = time.time()
                    try:
                        task_info["func"]()
                        task_info["last_run"] = now
                        task_info["total_runs"] += 1
                        elapsed_ms = (time.time() - start_time) * 1000
                        task_info["total_time_ms"] += elapsed_ms

                        logger.debug(f"Task executed: {task_name} ({elapsed_ms:.1f}ms)")
                    except Exception as e:
                        task_info["failures"] += 1
                        logger.error(f"Task failed: {task_name}: {e}")
                else:
                    # Sleep until next run
                    time.sleep(min(1, task_info["interval"]))
            except Exception as e:
                logger.error(f"Error in task worker {task_name}: {e}")
                time.sleep(5)  # Back off on error

    def get_stats(self) -> dict:
        """Get statistics about all tasks.

        Returns:
            Dictionary with task statistics
        """
        with self._lock:
            stats = {
                "running": self._running,
                "total_tasks": len(self.tasks),
                "tasks": {}
            }

            for task_name, task_info in self.tasks.items():
                avg_time = 0
                if task_info["total_runs"] > 0:
                    avg_time = task_info["total_time_ms"] / task_info["total_runs"]

                stats["tasks"][task_name] = {
                    "interval_seconds": task_info["interval"],
                    "last_run": task_info["last_run"].isoformat() if task_info["last_run"] else None,
                    "total_runs": task_info["total_runs"],
                    "failures": task_info["failures"],
                    "avg_time_ms": round(avg_time, 2),
                    "status": "running" if self._running else "stopped"
                }

            return stats


# Global instance
_background_task_manager: Optional[BackgroundTaskManager] = None


def get_background_task_manager() -> BackgroundTaskManager:
    """Get the global background task manager instance."""
    global _background_task_manager
    if _background_task_manager is None:
        _background_task_manager = BackgroundTaskManager()
    return _background_task_manager
