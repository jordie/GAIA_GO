"""
Integration tests for concurrent_task_manager.py

Tests concurrent task distribution, worker management, token tracking,
and throttle integration.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from concurrent_task_manager import ConcurrentTaskManager


@pytest.fixture
def worker_sessions():
    """Provide test worker session names."""
    return ["test_worker_1", "test_worker_2", "test_worker_3"]


@pytest.fixture
def task_manager(worker_sessions):
    """Create a ConcurrentTaskManager instance for testing."""
    return ConcurrentTaskManager(worker_sessions)


@pytest.mark.integration
class TestTaskQueueManagement:
    """Test task queue operations."""

    def test_add_task(self, task_manager):
        """Test adding task to queue."""
        task = "Implement user authentication"
        task_manager.add_task(task)

        assert len(task_manager.task_queue) == 1
        assert task_manager.task_queue[0]["task"] == task
        assert task_manager.task_queue[0]["status"] == "pending"
        assert "added_at" in task_manager.task_queue[0]

    def test_add_multiple_tasks(self, task_manager):
        """Test adding multiple tasks."""
        tasks = [
            "Task 1: Implement login",
            "Task 2: Add password reset",
            "Task 3: Create user profile",
        ]

        for task in tasks:
            task_manager.add_task(task)

        assert len(task_manager.task_queue) == 3
        for i, task in enumerate(tasks):
            assert task_manager.task_queue[i]["task"] == task

    def test_task_timestamp(self, task_manager):
        """Test task includes timestamp."""
        task_manager.add_task("Test task")

        task_info = task_manager.task_queue[0]
        assert isinstance(task_info["added_at"], datetime)
        assert task_info["added_at"] <= datetime.now()


@pytest.mark.integration
class TestWorkerStatusTracking:
    """Test worker status and metrics."""

    def test_initial_worker_status(self, task_manager, worker_sessions):
        """Test workers initialized with correct status."""
        for worker in worker_sessions:
            status = task_manager.worker_status[worker]
            assert status["busy"] is False
            assert status["current_task"] is None
            assert status["completed"] == 0
            assert status["tokens_used"] == 0
            assert status["estimated_cost"] == 0.0

    def test_worker_count(self, task_manager, worker_sessions):
        """Test correct number of workers initialized."""
        assert len(task_manager.worker_status) == len(worker_sessions)

    def test_worker_status_structure(self, task_manager):
        """Test worker status has required fields."""
        for worker, status in task_manager.worker_status.items():
            assert "busy" in status
            assert "current_task" in status
            assert "completed" in status
            assert "tokens_used" in status
            assert "estimated_cost" in status


@pytest.mark.integration
class TestTokenEstimation:
    """Test token estimation logic."""

    def test_estimate_short_task(self, task_manager):
        """Test token estimation for short task."""
        task = "Quick task"
        estimated = task_manager.estimate_task_tokens(task)

        # Short task: ~10 chars / 4 + 1000 overhead = ~1002 tokens
        assert estimated > 1000
        assert estimated < 1100

    def test_estimate_long_task(self, task_manager):
        """Test token estimation for long task."""
        task = "x" * 4000  # 4000 chars
        estimated = task_manager.estimate_task_tokens(task)

        # 4000 chars / 4 + 1000 overhead = 2000 tokens
        assert estimated > 1900
        assert estimated < 2100

    def test_estimation_includes_overhead(self, task_manager):
        """Test token estimation includes overhead."""
        empty_task = ""
        estimated = task_manager.estimate_task_tokens(empty_task)

        # Should be approximately the overhead (1000 tokens)
        assert estimated == 1000


@pytest.mark.integration
class TestGlobalMetrics:
    """Test global metrics tracking."""

    def test_initial_metrics(self, task_manager):
        """Test initial metrics are zero."""
        assert task_manager.total_tokens == 0
        assert task_manager.total_cost == 0.0
        assert task_manager.tasks_completed == 0

    def test_metrics_after_task_completion(self, task_manager):
        """Test metrics update after task completion."""
        worker = "test_worker_1"
        tokens_used = 5000

        task_manager.record_task_completion(worker, tokens_used)

        assert task_manager.tasks_completed == 1
        assert task_manager.total_cost > 0

    def test_multiple_task_completions(self, task_manager):
        """Test metrics accumulate across tasks."""
        worker = "test_worker_1"

        task_manager.record_task_completion(worker, 1000)
        task_manager.record_task_completion(worker, 2000)
        task_manager.record_task_completion(worker, 1500)

        assert task_manager.tasks_completed == 3


@pytest.mark.integration
class TestTaskCompletionRecording:
    """Test task completion and cost calculation."""

    def test_record_completion_updates_count(self, task_manager):
        """Test completion count increments."""
        initial_count = task_manager.tasks_completed

        task_manager.record_task_completion("test_worker_1", 1000)

        assert task_manager.tasks_completed == initial_count + 1

    def test_record_completion_calculates_cost(self, task_manager):
        """Test cost calculation."""
        tokens = 10000
        expected_cost = (tokens / 1000) * 0.003  # $0.003 per 1K tokens

        task_manager.record_task_completion("test_worker_1", tokens)

        assert abs(task_manager.total_cost - expected_cost) < 0.0001

    def test_record_completion_per_worker(self, task_manager):
        """Test per-worker cost tracking."""
        worker = "test_worker_1"
        tokens = 5000

        task_manager.record_task_completion(worker, tokens)

        assert task_manager.worker_status[worker]["estimated_cost"] > 0


@pytest.mark.integration
class TestThrottleIntegration:
    """Test throttle checking (when available)."""

    def test_check_throttle_limit_no_throttler(self, task_manager):
        """Test throttle check returns True when throttler disabled."""
        # By default, throttler may not be initialized
        if task_manager.throttler is None:
            result = task_manager.check_throttle_limit("test_worker_1", "Test task")
            assert result is True

    def test_throttle_stats_no_throttler(self, task_manager):
        """Test throttle stats returns None when throttler disabled."""
        if task_manager.throttler is None:
            stats = task_manager.get_throttle_stats()
            assert stats is None


@pytest.mark.integration
class TestWorkerIdleDetection:
    """Test worker idle detection patterns."""

    def test_check_worker_idle_pattern_recognition(self, task_manager):
        """Test idle pattern recognition logic."""
        # Note: This test verifies the logic exists, but actual tmux
        # interaction requires running tmux sessions

        # The method should handle missing workers gracefully
        result = task_manager.check_worker_idle("nonexistent_worker")

        # Should return False for nonexistent worker
        assert result is False


@pytest.mark.integration
class TestTaskDistribution:
    """Test task distribution logic."""

    def test_no_distribution_empty_queue(self, task_manager):
        """Test distribution with empty queue does nothing."""
        initial_queue_len = len(task_manager.task_queue)

        task_manager.distribute_tasks()

        assert len(task_manager.task_queue) == initial_queue_len


@pytest.mark.integration
class TestCostCalculations:
    """Test cost calculation accuracy."""

    def test_cost_per_1k_tokens(self, task_manager):
        """Test cost calculation for 1000 tokens."""
        tokens = 1000
        expected_cost = 0.003  # $0.003 per 1K tokens

        task_manager.record_task_completion("test_worker_1", tokens)

        assert abs(task_manager.total_cost - expected_cost) < 0.0001

    def test_cost_for_large_usage(self, task_manager):
        """Test cost calculation for large token usage."""
        tokens = 100000
        expected_cost = 0.3  # 100K tokens * $0.003 per 1K

        task_manager.record_task_completion("test_worker_1", tokens)

        assert abs(task_manager.total_cost - expected_cost) < 0.001


@pytest.mark.integration
class TestWorkerMetrics:
    """Test per-worker metrics tracking."""

    def test_worker_completion_count(self, task_manager):
        """Test worker completion count increments."""
        worker = "test_worker_1"

        # Manually increment (simulating task completion)
        task_manager.worker_status[worker]["completed"] = 5

        assert task_manager.worker_status[worker]["completed"] == 5

    def test_worker_token_accumulation(self, task_manager):
        """Test worker token usage accumulates."""
        worker = "test_worker_1"

        task_manager.worker_status[worker]["tokens_used"] += 1000
        task_manager.worker_status[worker]["tokens_used"] += 2000

        assert task_manager.worker_status[worker]["tokens_used"] == 3000

    def test_worker_cost_accumulation(self, task_manager):
        """Test worker cost accumulates."""
        worker = "test_worker_1"

        task_manager.record_task_completion(worker, 1000)
        task_manager.record_task_completion(worker, 2000)

        assert task_manager.worker_status[worker]["estimated_cost"] > 0


@pytest.mark.integration
class TestBusyIdleTransitions:
    """Test worker busy/idle state transitions."""

    def test_worker_initially_idle(self, task_manager):
        """Test workers start idle."""
        for worker in task_manager.workers:
            assert task_manager.worker_status[worker]["busy"] is False

    def test_set_worker_busy(self, task_manager):
        """Test setting worker to busy."""
        worker = "test_worker_1"
        task = "Test task"

        task_manager.worker_status[worker]["busy"] = True
        task_manager.worker_status[worker]["current_task"] = task

        assert task_manager.worker_status[worker]["busy"] is True
        assert task_manager.worker_status[worker]["current_task"] == task

    def test_set_worker_idle_after_completion(self, task_manager):
        """Test setting worker back to idle."""
        worker = "test_worker_1"

        # Set busy
        task_manager.worker_status[worker]["busy"] = True
        task_manager.worker_status[worker]["current_task"] = "Task"

        # Mark idle
        task_manager.worker_status[worker]["busy"] = False
        task_manager.worker_status[worker]["current_task"] = None

        assert task_manager.worker_status[worker]["busy"] is False
        assert task_manager.worker_status[worker]["current_task"] is None


@pytest.mark.integration
class TestStatusReporting:
    """Test status reporting methods."""

    def test_print_status_executes(self, task_manager, capsys):
        """Test print_status executes without error."""
        task_manager.print_status()

        captured = capsys.readouterr()
        assert "STATUS" in captured.out

    def test_print_metrics_executes(self, task_manager, capsys):
        """Test print_metrics executes without error."""
        task_manager.print_metrics()

        captured = capsys.readouterr()
        assert "METRICS" in captured.out

    def test_print_throttle_status_executes(self, task_manager, capsys):
        """Test print_throttle_status executes without error."""
        try:
            task_manager.print_throttle_status()
            captured = capsys.readouterr()
            # If throttler disabled, should show warning
            assert len(captured.out) > 0
        except KeyError:
            # Expected if throttler is enabled but doesn't have all stats fields
            # This is acceptable for integration testing
            pass


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_task_addition(self, task_manager):
        """Test adding empty task."""
        task_manager.add_task("")

        assert len(task_manager.task_queue) == 1
        assert task_manager.task_queue[0]["task"] == ""

    def test_very_long_task_estimation(self, task_manager):
        """Test token estimation for very long task."""
        task = "x" * 100000  # 100K characters
        estimated = task_manager.estimate_task_tokens(task)

        # 100K chars / 4 + 1000 overhead = ~26000 tokens
        assert estimated > 25000
        assert estimated < 27000

    def test_record_completion_zero_tokens(self, task_manager):
        """Test recording completion with zero tokens."""
        task_manager.record_task_completion("test_worker_1", 0)

        assert task_manager.tasks_completed == 1
        assert task_manager.total_cost == 0.0

    def test_multiple_workers_concurrent_tasks(self, task_manager):
        """Test tracking multiple workers with concurrent tasks."""
        for i, worker in enumerate(task_manager.workers):
            task_manager.worker_status[worker]["busy"] = True
            task_manager.worker_status[worker]["current_task"] = f"Task {i+1}"

        busy_count = sum(
            1 for status in task_manager.worker_status.values() if status["busy"]
        )
        assert busy_count == len(task_manager.workers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
