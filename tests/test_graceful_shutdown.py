#!/usr/bin/env python3
"""
Tests for Graceful Shutdown Module

Verifies:
- Signal handling
- Shutdown phases
- In-progress task tracking
- Cleanup hooks
- Coordinator functionality
"""

import os
import signal
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graceful_shutdown import (
    GracefulShutdown,
    ShutdownCoordinator,
    ShutdownPhase,
    ShutdownReason,
    ShutdownState,
    is_shutting_down,
    request_shutdown,
    setup_graceful_shutdown,
    should_run,
    shutdown_handler,
    task_context,
)


class TestShutdownPhase(unittest.TestCase):
    """Test ShutdownPhase enum."""

    def test_phase_values(self):
        """Test phase enum values."""
        self.assertEqual(ShutdownPhase.RUNNING.value, "running")
        self.assertEqual(ShutdownPhase.STOPPING.value, "stopping")
        self.assertEqual(ShutdownPhase.DRAINING.value, "draining")
        self.assertEqual(ShutdownPhase.CLEANUP.value, "cleanup")
        self.assertEqual(ShutdownPhase.TERMINATED.value, "terminated")


class TestShutdownReason(unittest.TestCase):
    """Test ShutdownReason enum."""

    def test_reason_values(self):
        """Test reason enum values."""
        self.assertEqual(ShutdownReason.SIGTERM.value, "SIGTERM")
        self.assertEqual(ShutdownReason.SIGINT.value, "SIGINT")
        self.assertEqual(ShutdownReason.MANUAL.value, "manual")
        self.assertEqual(ShutdownReason.TIMEOUT.value, "timeout")


class TestShutdownState(unittest.TestCase):
    """Test ShutdownState dataclass."""

    def test_default_state(self):
        """Test default state values."""
        state = ShutdownState()
        self.assertEqual(state.phase, ShutdownPhase.RUNNING)
        self.assertIsNone(state.reason)
        self.assertIsNone(state.signal_received_at)
        self.assertEqual(len(state.in_progress_tasks), 0)

    def test_state_modification(self):
        """Test state modification."""
        state = ShutdownState()
        state.phase = ShutdownPhase.STOPPING
        state.reason = ShutdownReason.SIGTERM
        state.in_progress_tasks.add("task-1")

        self.assertEqual(state.phase, ShutdownPhase.STOPPING)
        self.assertEqual(state.reason, ShutdownReason.SIGTERM)
        self.assertIn("task-1", state.in_progress_tasks)


class TestGracefulShutdown(unittest.TestCase):
    """Test GracefulShutdown class."""

    def setUp(self):
        """Set up test fixtures."""
        self.shutdown = GracefulShutdown(
            worker_id="test-worker",
            shutdown_timeout=5,
            drain_timeout=5,
            notify_dashboard=False,
            force_exit=False,
        )

    def tearDown(self):
        """Clean up after tests."""
        self.shutdown.unregister()

    def test_initialization(self):
        """Test initialization."""
        self.assertEqual(self.shutdown.worker_id, "test-worker")
        self.assertTrue(self.shutdown.should_run)
        self.assertFalse(self.shutdown.is_shutting_down)
        self.assertFalse(self.shutdown.is_terminated)

    def test_should_run_property(self):
        """Test should_run property."""
        self.assertTrue(self.shutdown.should_run)
        self.shutdown._state.phase = ShutdownPhase.STOPPING
        self.assertFalse(self.shutdown.should_run)

    def test_is_shutting_down_property(self):
        """Test is_shutting_down property."""
        self.assertFalse(self.shutdown.is_shutting_down)

        self.shutdown._state.phase = ShutdownPhase.STOPPING
        self.assertTrue(self.shutdown.is_shutting_down)

        self.shutdown._state.phase = ShutdownPhase.DRAINING
        self.assertTrue(self.shutdown.is_shutting_down)

        self.shutdown._state.phase = ShutdownPhase.CLEANUP
        self.assertTrue(self.shutdown.is_shutting_down)

        self.shutdown._state.phase = ShutdownPhase.TERMINATED
        self.assertFalse(self.shutdown.is_shutting_down)

    def test_phase_property(self):
        """Test phase property."""
        self.assertEqual(self.shutdown.phase, ShutdownPhase.RUNNING)

    def test_in_progress_count(self):
        """Test in_progress_count property."""
        self.assertEqual(self.shutdown.in_progress_count, 0)
        self.shutdown._state.in_progress_tasks.add("task-1")
        self.assertEqual(self.shutdown.in_progress_count, 1)

    def test_register_unregister(self):
        """Test register and unregister."""
        shutdown = GracefulShutdown(force_exit=False)
        self.assertFalse(shutdown._registered)

        shutdown.register()
        self.assertTrue(shutdown._registered)

        shutdown.unregister()
        self.assertFalse(shutdown._registered)

    def test_add_cleanup_hook(self):
        """Test adding cleanup hooks."""
        hook = MagicMock()
        self.shutdown.add_cleanup_hook(hook)
        self.assertIn(hook, self.shutdown._cleanup_hooks)

    def test_remove_cleanup_hook(self):
        """Test removing cleanup hooks."""
        hook = MagicMock()
        self.shutdown.add_cleanup_hook(hook)
        self.shutdown.remove_cleanup_hook(hook)
        self.assertNotIn(hook, self.shutdown._cleanup_hooks)

    def test_task_context(self):
        """Test task_context context manager."""
        self.assertEqual(self.shutdown.in_progress_count, 0)

        with self.shutdown.task_context("task-1"):
            self.assertEqual(self.shutdown.in_progress_count, 1)
            self.assertIn("task-1", self.shutdown._state.in_progress_tasks)

        self.assertEqual(self.shutdown.in_progress_count, 0)

    def test_task_context_auto_id(self):
        """Test task_context with auto-generated ID."""
        with self.shutdown.task_context() as task_id:
            self.assertIsNotNone(task_id)
            self.assertTrue(task_id.startswith("task-"))

    def test_start_finish_task(self):
        """Test start_task and finish_task."""
        task_id = self.shutdown.start_task("my-task")
        self.assertEqual(task_id, "my-task")
        self.assertEqual(self.shutdown.in_progress_count, 1)

        self.shutdown.finish_task(task_id)
        self.assertEqual(self.shutdown.in_progress_count, 0)

    def test_start_task_auto_id(self):
        """Test start_task with auto-generated ID."""
        task_id = self.shutdown.start_task()
        self.assertTrue(task_id.startswith("task-"))
        self.shutdown.finish_task(task_id)

    def test_context_manager(self):
        """Test using GracefulShutdown as context manager."""
        with GracefulShutdown(force_exit=False, notify_dashboard=False) as shutdown:
            self.assertTrue(shutdown._registered)
            self.assertTrue(shutdown.should_run)


class TestShutdownCallbacks(unittest.TestCase):
    """Test shutdown callbacks."""

    def test_on_shutdown_callback(self):
        """Test on_shutdown callback is called."""
        callback = MagicMock()
        shutdown = GracefulShutdown(
            on_shutdown=callback, shutdown_timeout=1, notify_dashboard=False, force_exit=False
        )

        shutdown.request_shutdown(ShutdownReason.MANUAL)
        time.sleep(0.5)

        callback.assert_called_once()

    def test_on_cleanup_callback(self):
        """Test on_cleanup callback is called."""
        callback = MagicMock()
        shutdown = GracefulShutdown(
            on_cleanup=callback, shutdown_timeout=1, notify_dashboard=False, force_exit=False
        )

        shutdown.request_shutdown(ShutdownReason.MANUAL)
        time.sleep(0.5)

        callback.assert_called_once()

    def test_cleanup_hooks_called_in_lifo_order(self):
        """Test cleanup hooks are called in LIFO order."""
        call_order = []

        def hook1():
            call_order.append(1)

        def hook2():
            call_order.append(2)

        def hook3():
            call_order.append(3)

        shutdown = GracefulShutdown(shutdown_timeout=1, notify_dashboard=False, force_exit=False)
        shutdown.add_cleanup_hook(hook1)
        shutdown.add_cleanup_hook(hook2)
        shutdown.add_cleanup_hook(hook3)

        shutdown.request_shutdown(ShutdownReason.MANUAL)
        time.sleep(0.5)

        self.assertEqual(call_order, [3, 2, 1])


class TestShutdownRequest(unittest.TestCase):
    """Test shutdown request handling."""

    def test_request_shutdown(self):
        """Test request_shutdown method."""
        shutdown = GracefulShutdown(shutdown_timeout=1, notify_dashboard=False, force_exit=False)

        shutdown.request_shutdown(ShutdownReason.MANUAL)

        self.assertEqual(shutdown.reason, ShutdownReason.MANUAL)
        self.assertFalse(shutdown.should_run)

    def test_duplicate_shutdown_request(self):
        """Test duplicate shutdown requests are ignored."""
        shutdown = GracefulShutdown(shutdown_timeout=1, notify_dashboard=False, force_exit=False)

        shutdown.request_shutdown(ShutdownReason.SIGTERM)
        shutdown.request_shutdown(ShutdownReason.SIGINT)  # Should be ignored

        self.assertEqual(shutdown.reason, ShutdownReason.SIGTERM)


class TestTaskDraining(unittest.TestCase):
    """Test task draining during shutdown."""

    def test_drain_waits_for_tasks(self):
        """Test that drain phase waits for in-progress tasks."""
        shutdown = GracefulShutdown(
            shutdown_timeout=5, drain_timeout=5, notify_dashboard=False, force_exit=False
        )

        # Start a task
        task_id = shutdown.start_task("long-task")

        # Request shutdown
        shutdown.request_shutdown(ShutdownReason.MANUAL)
        time.sleep(0.2)

        # Should be in draining phase
        self.assertEqual(shutdown.phase, ShutdownPhase.DRAINING)

        # Finish the task
        shutdown.finish_task(task_id)
        time.sleep(0.5)

        # Should have completed shutdown
        self.assertIn(shutdown.phase, [ShutdownPhase.CLEANUP, ShutdownPhase.TERMINATED])

    def test_drain_timeout(self):
        """Test that drain times out if tasks don't complete."""
        shutdown = GracefulShutdown(
            shutdown_timeout=1, drain_timeout=0.5, notify_dashboard=False, force_exit=False
        )

        # Start a task that won't complete
        shutdown.start_task("stuck-task")

        # Request shutdown
        shutdown.request_shutdown(ShutdownReason.MANUAL)

        # Wait for drain timeout
        time.sleep(1)

        # Should have moved past draining despite stuck task
        self.assertIn(shutdown.phase, [ShutdownPhase.CLEANUP, ShutdownPhase.TERMINATED])


class TestShutdownCoordinator(unittest.TestCase):
    """Test ShutdownCoordinator class."""

    def test_coordinator_initialization(self):
        """Test coordinator initialization."""
        coordinator = ShutdownCoordinator(shutdown_timeout=30)
        self.assertEqual(coordinator.shutdown_timeout, 30)
        self.assertTrue(coordinator.parallel_shutdown)

    def test_register_worker(self):
        """Test registering workers."""
        coordinator = ShutdownCoordinator()
        shutdown = GracefulShutdown(worker_id="worker-1", force_exit=False)

        coordinator.register_worker(shutdown)
        self.assertIn("worker-1", coordinator._workers)

    def test_unregister_worker(self):
        """Test unregistering workers."""
        coordinator = ShutdownCoordinator()
        shutdown = GracefulShutdown(worker_id="worker-1", force_exit=False)

        coordinator.register_worker(shutdown)
        coordinator.unregister_worker("worker-1")
        self.assertNotIn("worker-1", coordinator._workers)


class TestShutdownDecorator(unittest.TestCase):
    """Test shutdown_handler decorator."""

    def test_decorator_basic(self):
        """Test basic decorator usage."""

        @shutdown_handler(timeout=1, notify_dashboard=False, force_exit=False)
        def test_func(shutdown):
            self.assertIsInstance(shutdown, GracefulShutdown)
            shutdown.request_shutdown(ShutdownReason.MANUAL)

        test_func()

    def test_decorator_without_shutdown_param(self):
        """Test decorator with function that doesn't accept shutdown."""

        @shutdown_handler(timeout=1, notify_dashboard=False, force_exit=False)
        def test_func():
            return "result"

        # Function should still work (shutdown happens automatically)
        # Note: This will block briefly due to shutdown


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    def test_setup_graceful_shutdown(self):
        """Test setup_graceful_shutdown function."""
        shutdown = setup_graceful_shutdown(
            worker_id="test-worker", notify_dashboard=False, force_exit=False
        )

        self.assertEqual(shutdown.worker_id, "test-worker")
        shutdown.unregister()

    def test_should_run_function(self):
        """Test should_run convenience function."""
        # This uses the global default shutdown
        result = should_run()
        self.assertIsInstance(result, bool)

    def test_is_shutting_down_function(self):
        """Test is_shutting_down convenience function."""
        result = is_shutting_down()
        self.assertIsInstance(result, bool)


class TestStateFile(unittest.TestCase):
    """Test state file handling."""

    def test_save_state(self):
        """Test state file is saved during shutdown."""
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            state_file = Path(f.name)

        try:
            shutdown = GracefulShutdown(
                worker_id="state-test",
                state_file=state_file,
                shutdown_timeout=1,
                notify_dashboard=False,
                force_exit=False,
            )

            shutdown.request_shutdown(ShutdownReason.MANUAL)
            time.sleep(0.5)

            # State file should exist
            self.assertTrue(state_file.exists())

            # Read and verify state
            state = json.loads(state_file.read_text())
            self.assertEqual(state["worker_id"], "state-test")

        finally:
            if state_file.exists():
                state_file.unlink()


class TestErrorHandling(unittest.TestCase):
    """Test error handling during shutdown."""

    def test_callback_error_captured(self):
        """Test that callback errors are captured."""

        def bad_callback():
            raise ValueError("Test error")

        shutdown = GracefulShutdown(
            on_shutdown=bad_callback, shutdown_timeout=1, notify_dashboard=False, force_exit=False
        )

        shutdown.request_shutdown(ShutdownReason.MANUAL)
        time.sleep(0.5)

        # Error should be recorded
        self.assertGreater(len(shutdown._state.cleanup_errors), 0)
        self.assertIn("Test error", shutdown._state.cleanup_errors[0])

    def test_cleanup_hook_error_captured(self):
        """Test that cleanup hook errors are captured."""

        def bad_hook():
            raise RuntimeError("Hook error")

        shutdown = GracefulShutdown(shutdown_timeout=1, notify_dashboard=False, force_exit=False)
        shutdown.add_cleanup_hook(bad_hook)

        shutdown.request_shutdown(ShutdownReason.MANUAL)
        time.sleep(0.5)

        self.assertGreater(len(shutdown._state.cleanup_errors), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
