#!/usr/bin/env python3
"""
Graceful Shutdown Handler for Workers

Provides consistent, safe shutdown handling for all workers and services.

Features:
- Signal handling (SIGTERM, SIGINT, SIGHUP)
- In-progress task completion before shutdown
- Configurable shutdown timeout
- Resource cleanup hooks
- Dashboard notification on shutdown
- Thread-safe shutdown coordination
- Support for multiple shutdown phases

Usage:
    from graceful_shutdown import GracefulShutdown, shutdown_handler

    # Create shutdown handler
    shutdown = GracefulShutdown(
        worker_id="my-worker",
        shutdown_timeout=30,
        on_shutdown=cleanup_function
    )

    # Use as context manager
    with shutdown:
        while shutdown.should_run:
            process_work()

    # Or use decorator
    @shutdown_handler(timeout=30)
    def main():
        while True:
            process_work()
"""

import atexit
import json
import logging
import os
import signal
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """Phases of graceful shutdown."""

    RUNNING = "running"
    STOPPING = "stopping"  # Received shutdown signal
    DRAINING = "draining"  # Waiting for in-progress tasks
    CLEANUP = "cleanup"  # Running cleanup hooks
    TERMINATED = "terminated"  # Shutdown complete


class ShutdownReason(Enum):
    """Reason for shutdown."""

    SIGTERM = "SIGTERM"
    SIGINT = "SIGINT"
    SIGHUP = "SIGHUP"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    ERROR = "error"
    PARENT_EXIT = "parent_exit"


@dataclass
class ShutdownState:
    """Current shutdown state."""

    phase: ShutdownPhase = ShutdownPhase.RUNNING
    reason: Optional[ShutdownReason] = None
    signal_received_at: Optional[datetime] = None
    shutdown_started_at: Optional[datetime] = None
    shutdown_completed_at: Optional[datetime] = None
    in_progress_tasks: Set[str] = field(default_factory=set)
    cleanup_errors: List[str] = field(default_factory=list)


class GracefulShutdown:
    """
    Graceful shutdown handler for workers and services.

    Provides:
    - Signal handling for SIGTERM, SIGINT, SIGHUP
    - Coordinated shutdown with in-progress task completion
    - Configurable timeout for forced shutdown
    - Cleanup hooks for resource cleanup
    - Dashboard notification on shutdown
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        worker_type: str = "worker",
        shutdown_timeout: int = 30,
        drain_timeout: int = 60,
        on_shutdown: Optional[Callable[[], None]] = None,
        on_drain_start: Optional[Callable[[], None]] = None,
        on_cleanup: Optional[Callable[[], None]] = None,
        notify_dashboard: bool = True,
        dashboard_url: str = "http://100.112.58.92:8080",
        pid_file: Optional[Path] = None,
        state_file: Optional[Path] = None,
        force_exit: bool = True,
        log_level: int = logging.INFO,
    ):
        """
        Initialize graceful shutdown handler.

        Args:
            worker_id: Unique identifier for this worker
            worker_type: Type of worker (for logging/reporting)
            shutdown_timeout: Max seconds to wait for graceful shutdown
            drain_timeout: Max seconds to wait for in-progress tasks
            on_shutdown: Callback when shutdown signal received
            on_drain_start: Callback when drain phase starts
            on_cleanup: Callback for final cleanup
            notify_dashboard: Whether to notify dashboard of shutdown
            dashboard_url: URL of the dashboard API
            pid_file: Path to PID file (cleaned up on shutdown)
            state_file: Path to state file (updated during shutdown)
            force_exit: Whether to force exit after timeout
            log_level: Logging level for shutdown messages
        """
        self.worker_id = worker_id or f"{worker_type}-{os.getpid()}"
        self.worker_type = worker_type
        self.shutdown_timeout = shutdown_timeout
        self.drain_timeout = drain_timeout
        self.on_shutdown = on_shutdown
        self.on_drain_start = on_drain_start
        self.on_cleanup = on_cleanup
        self.notify_dashboard = notify_dashboard
        self.dashboard_url = dashboard_url.rstrip("/")
        self.pid_file = Path(pid_file) if pid_file else None
        self.state_file = Path(state_file) if state_file else None
        self.force_exit = force_exit
        self.log_level = log_level

        # State
        self._state = ShutdownState()
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._drain_complete = threading.Event()
        self._cleanup_hooks: List[Callable[[], None]] = []
        self._original_handlers: Dict[int, Any] = {}
        self._registered = False

        # Task tracking
        self._task_counter = 0

    @property
    def should_run(self) -> bool:
        """Check if the worker should continue running."""
        return self._state.phase == ShutdownPhase.RUNNING

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._state.phase in (
            ShutdownPhase.STOPPING,
            ShutdownPhase.DRAINING,
            ShutdownPhase.CLEANUP,
        )

    @property
    def is_terminated(self) -> bool:
        """Check if shutdown is complete."""
        return self._state.phase == ShutdownPhase.TERMINATED

    @property
    def phase(self) -> ShutdownPhase:
        """Get current shutdown phase."""
        return self._state.phase

    @property
    def reason(self) -> Optional[ShutdownReason]:
        """Get shutdown reason if shutting down."""
        return self._state.reason

    @property
    def in_progress_count(self) -> int:
        """Get count of in-progress tasks."""
        return len(self._state.in_progress_tasks)

    def register(self) -> "GracefulShutdown":
        """
        Register signal handlers.

        Returns self for chaining.
        """
        if self._registered:
            return self

        # Save original handlers
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try:
                self._original_handlers[sig] = signal.signal(sig, self._signal_handler)
            except (OSError, ValueError) as e:
                # Can't set handler (e.g., in a thread)
                logger.debug(f"Could not register handler for {sig}: {e}")

        # Register atexit handler
        atexit.register(self._atexit_handler)

        self._registered = True
        logger.log(self.log_level, f"Graceful shutdown registered for {self.worker_id}")

        return self

    def unregister(self):
        """Restore original signal handlers."""
        if not self._registered:
            return

        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except (OSError, ValueError):
                pass

        self._original_handlers.clear()
        self._registered = False

    def add_cleanup_hook(self, hook: Callable[[], None]):
        """
        Add a cleanup hook to run during shutdown.

        Hooks are run in LIFO order (last added, first run).
        """
        self._cleanup_hooks.append(hook)

    def remove_cleanup_hook(self, hook: Callable[[], None]):
        """Remove a cleanup hook."""
        try:
            self._cleanup_hooks.remove(hook)
        except ValueError:
            pass

    @contextmanager
    def task_context(self, task_id: Optional[str] = None):
        """
        Context manager for tracking in-progress tasks.

        Usage:
            with shutdown.task_context("task-123"):
                process_task()
        """
        with self._lock:
            self._task_counter += 1
            actual_id = task_id or f"task-{self._task_counter}"
            self._state.in_progress_tasks.add(actual_id)

        try:
            yield actual_id
        finally:
            with self._lock:
                self._state.in_progress_tasks.discard(actual_id)
                if not self._state.in_progress_tasks and self.is_shutting_down:
                    self._drain_complete.set()

    def start_task(self, task_id: Optional[str] = None) -> str:
        """
        Mark a task as starting.

        Returns the task ID (generated if not provided).
        """
        with self._lock:
            self._task_counter += 1
            actual_id = task_id or f"task-{self._task_counter}"
            self._state.in_progress_tasks.add(actual_id)
            return actual_id

    def finish_task(self, task_id: str):
        """Mark a task as finished."""
        with self._lock:
            self._state.in_progress_tasks.discard(task_id)
            if not self._state.in_progress_tasks and self.is_shutting_down:
                self._drain_complete.set()

    def request_shutdown(self, reason: ShutdownReason = ShutdownReason.MANUAL):
        """
        Request a graceful shutdown.

        Can be called from any thread.
        """
        with self._lock:
            if self._state.phase != ShutdownPhase.RUNNING:
                logger.debug(f"Shutdown already in progress (phase: {self._state.phase})")
                return

            self._state.phase = ShutdownPhase.STOPPING
            self._state.reason = reason
            self._state.signal_received_at = datetime.now()

        logger.log(self.log_level, f"Shutdown requested: {reason.value}")
        self._shutdown_event.set()

        # Start shutdown thread
        shutdown_thread = threading.Thread(
            target=self._run_shutdown, name="graceful-shutdown", daemon=True
        )
        shutdown_thread.start()

    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown to complete.

        Returns True if shutdown completed, False if timeout.
        """
        return self._shutdown_event.wait(timeout)

    def _signal_handler(self, signum: int, frame):
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.log(self.log_level, f"Received {sig_name}")

        reason_map = {
            signal.SIGTERM: ShutdownReason.SIGTERM,
            signal.SIGINT: ShutdownReason.SIGINT,
            signal.SIGHUP: ShutdownReason.SIGHUP,
        }

        self.request_shutdown(reason_map.get(signum, ShutdownReason.SIGTERM))

    def _atexit_handler(self):
        """Handle process exit."""
        if self._state.phase == ShutdownPhase.RUNNING:
            self.request_shutdown(ShutdownReason.PARENT_EXIT)

    def _run_shutdown(self):
        """Execute the shutdown sequence."""
        self._state.shutdown_started_at = datetime.now()

        try:
            # Phase 1: Call on_shutdown callback
            if self.on_shutdown:
                try:
                    self.on_shutdown()
                except Exception as e:
                    logger.error(f"Error in on_shutdown callback: {e}")
                    self._state.cleanup_errors.append(str(e))

            # Phase 2: Drain - wait for in-progress tasks
            self._state.phase = ShutdownPhase.DRAINING

            if self.on_drain_start:
                try:
                    self.on_drain_start()
                except Exception as e:
                    logger.error(f"Error in on_drain_start callback: {e}")
                    self._state.cleanup_errors.append(str(e))

            if self._state.in_progress_tasks:
                logger.log(
                    self.log_level,
                    f"Waiting for {len(self._state.in_progress_tasks)} in-progress tasks...",
                )
                self._save_state()

                # Wait for drain with timeout
                if not self._drain_complete.wait(timeout=self.drain_timeout):
                    remaining = list(self._state.in_progress_tasks)
                    logger.warning(
                        f"Drain timeout - {len(remaining)} tasks still in progress: {remaining[:5]}"
                    )

            # Phase 3: Cleanup
            self._state.phase = ShutdownPhase.CLEANUP
            self._run_cleanup()

            # Phase 4: Terminated
            self._state.phase = ShutdownPhase.TERMINATED
            self._state.shutdown_completed_at = datetime.now()

            self._save_state()
            self._cleanup_files()

            duration = (
                self._state.shutdown_completed_at - self._state.shutdown_started_at
            ).total_seconds()
            logger.log(
                self.log_level,
                f"Shutdown complete ({duration:.1f}s, {len(self._state.cleanup_errors)} errors)",
            )

            # Notify dashboard
            if self.notify_dashboard:
                self._notify_dashboard_shutdown()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            self._state.cleanup_errors.append(str(e))

        finally:
            # Force exit if configured
            if self.force_exit:
                os._exit(0)

    def _run_cleanup(self):
        """Run all cleanup hooks."""
        # Run on_cleanup callback
        if self.on_cleanup:
            try:
                self.on_cleanup()
            except Exception as e:
                logger.error(f"Error in on_cleanup callback: {e}")
                self._state.cleanup_errors.append(str(e))

        # Run cleanup hooks in reverse order (LIFO)
        for hook in reversed(self._cleanup_hooks):
            try:
                hook()
            except Exception as e:
                logger.error(f"Error in cleanup hook: {e}")
                self._state.cleanup_errors.append(str(e))

    def _save_state(self):
        """Save shutdown state to file."""
        if not self.state_file:
            return

        try:
            state = {
                "worker_id": self.worker_id,
                "worker_type": self.worker_type,
                "phase": self._state.phase.value,
                "reason": self._state.reason.value if self._state.reason else None,
                "signal_received_at": self._state.signal_received_at.isoformat()
                if self._state.signal_received_at
                else None,
                "shutdown_started_at": self._state.shutdown_started_at.isoformat()
                if self._state.shutdown_started_at
                else None,
                "in_progress_tasks": list(self._state.in_progress_tasks),
                "cleanup_errors": self._state.cleanup_errors,
                "timestamp": datetime.now().isoformat(),
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"Could not save state: {e}")

    def _cleanup_files(self):
        """Clean up PID and state files."""
        if self.pid_file and self.pid_file.exists():
            try:
                self.pid_file.unlink()
            except Exception as e:
                logger.debug(f"Could not remove PID file: {e}")

    def _notify_dashboard_shutdown(self):
        """Notify the dashboard that this worker is shutting down."""
        try:
            import urllib.error
            import urllib.request

            data = json.dumps(
                {
                    "status": "offline",
                    "shutdown_reason": self._state.reason.value
                    if self._state.reason
                    else "unknown",
                    "shutdown_time": datetime.now().isoformat(),
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                f"{self.dashboard_url}/api/workers/{self.worker_id}/shutdown",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                pass

        except Exception as e:
            logger.debug(f"Could not notify dashboard: {e}")

    def __enter__(self):
        """Enter context manager."""
        self.register()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if not self.is_terminated:
            reason = ShutdownReason.ERROR if exc_type else ShutdownReason.MANUAL
            self.request_shutdown(reason)
            self.wait_for_shutdown(timeout=self.shutdown_timeout)
        self.unregister()
        return False


def shutdown_handler(
    timeout: int = 30, worker_type: str = "worker", notify_dashboard: bool = True, **kwargs
):
    """
    Decorator for adding graceful shutdown to main functions.

    Usage:
        @shutdown_handler(timeout=30)
        def main():
            while True:
                process_work()
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **func_kwargs):
            shutdown = GracefulShutdown(
                worker_type=worker_type,
                shutdown_timeout=timeout,
                notify_dashboard=notify_dashboard,
                **kwargs,
            )

            with shutdown:
                # Inject shutdown into function if it accepts it
                import inspect

                sig = inspect.signature(func)
                if "shutdown" in sig.parameters:
                    func_kwargs["shutdown"] = shutdown

                return func(*args, **func_kwargs)

        return wrapper

    return decorator


class ShutdownCoordinator:
    """
    Coordinator for managing shutdown of multiple workers/services.

    Useful for applications with multiple background threads/workers.
    """

    def __init__(self, shutdown_timeout: int = 60, parallel_shutdown: bool = True):
        """
        Initialize shutdown coordinator.

        Args:
            shutdown_timeout: Total time allowed for all shutdowns
            parallel_shutdown: Whether to shutdown workers in parallel
        """
        self.shutdown_timeout = shutdown_timeout
        self.parallel_shutdown = parallel_shutdown
        self._workers: Dict[str, GracefulShutdown] = {}
        self._lock = threading.Lock()
        self._master_shutdown = GracefulShutdown(
            worker_id="coordinator",
            worker_type="coordinator",
            shutdown_timeout=shutdown_timeout,
            on_shutdown=self._coordinate_shutdown,
            force_exit=False,
        )

    def register_worker(self, shutdown: GracefulShutdown):
        """Register a worker's shutdown handler."""
        with self._lock:
            self._workers[shutdown.worker_id] = shutdown

    def unregister_worker(self, worker_id: str):
        """Unregister a worker's shutdown handler."""
        with self._lock:
            self._workers.pop(worker_id, None)

    def start(self):
        """Start the coordinator."""
        self._master_shutdown.register()

    def stop(self):
        """Stop all workers gracefully."""
        self._master_shutdown.request_shutdown(ShutdownReason.MANUAL)

    def _coordinate_shutdown(self):
        """Coordinate shutdown of all workers."""
        workers = list(self._workers.values())

        if not workers:
            return

        logger.info(f"Coordinating shutdown of {len(workers)} workers")

        if self.parallel_shutdown:
            # Shutdown all workers in parallel
            threads = []
            for worker in workers:
                t = threading.Thread(
                    target=worker.request_shutdown, args=(ShutdownReason.PARENT_EXIT,)
                )
                t.start()
                threads.append(t)

            # Wait for all shutdowns
            for t in threads:
                t.join(timeout=self.shutdown_timeout / len(workers))
        else:
            # Shutdown workers sequentially
            for worker in workers:
                worker.request_shutdown(ShutdownReason.PARENT_EXIT)
                worker.wait_for_shutdown(timeout=self.shutdown_timeout / len(workers))


# Convenience functions

_default_shutdown: Optional[GracefulShutdown] = None


def get_default_shutdown() -> GracefulShutdown:
    """Get or create the default shutdown handler."""
    global _default_shutdown
    if _default_shutdown is None:
        _default_shutdown = GracefulShutdown()
    return _default_shutdown


def setup_graceful_shutdown(worker_id: Optional[str] = None, **kwargs) -> GracefulShutdown:
    """
    Set up graceful shutdown for the current process.

    Returns the shutdown handler.
    """
    global _default_shutdown
    _default_shutdown = GracefulShutdown(worker_id=worker_id, **kwargs)
    _default_shutdown.register()
    return _default_shutdown


def should_run() -> bool:
    """Check if the process should continue running."""
    return get_default_shutdown().should_run


def is_shutting_down() -> bool:
    """Check if shutdown is in progress."""
    return get_default_shutdown().is_shutting_down


def request_shutdown(reason: ShutdownReason = ShutdownReason.MANUAL):
    """Request a graceful shutdown."""
    get_default_shutdown().request_shutdown(reason)


@contextmanager
def task_context(task_id: Optional[str] = None):
    """Context manager for tracking in-progress tasks."""
    with get_default_shutdown().task_context(task_id) as tid:
        yield tid


# Export all public symbols
__all__ = [
    "GracefulShutdown",
    "ShutdownPhase",
    "ShutdownReason",
    "ShutdownState",
    "ShutdownCoordinator",
    "shutdown_handler",
    "setup_graceful_shutdown",
    "get_default_shutdown",
    "should_run",
    "is_shutting_down",
    "request_shutdown",
    "task_context",
]
