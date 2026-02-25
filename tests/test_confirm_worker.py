"""
Unit tests for confirm_worker module.

Feature #30: Confirm Worker - Background worker for auto-confirmation tasks.
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workers.confirm_worker import ConfirmWorker


class TestConfirmWorkerInit:
    """Tests for ConfirmWorker initialization."""

    def test_default_poll_interval(self):
        """Test default poll interval is 5 seconds."""
        worker = ConfirmWorker()
        assert worker.poll_interval == 5

    def test_custom_poll_interval(self):
        """Test custom poll interval is set."""
        worker = ConfirmWorker(poll_interval=10)
        assert worker.poll_interval == 10

    def test_initial_state(self):
        """Test worker starts in stopped state."""
        worker = ConfirmWorker()
        assert worker.running is False

    def test_worker_id_contains_pid(self):
        """Test worker ID includes process ID."""
        worker = ConfirmWorker()
        assert "confirm-" in worker.worker_id
        assert str(os.getpid()) in worker.worker_id


class TestConfirmWorkerSignals:
    """Tests for signal handling."""

    def test_handle_signal_stops_worker(self):
        """Test signal handler stops the worker."""
        worker = ConfirmWorker()
        worker.running = True

        worker._handle_signal(15, None)  # SIGTERM

        assert worker.running is False


class TestConfirmWorkerDatabase:
    """Tests for database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE workers (
                id TEXT PRIMARY KEY,
                worker_type TEXT,
                status TEXT,
                last_heartbeat TEXT
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE task_queue (
                id INTEGER PRIMARY KEY,
                task_type TEXT,
                status TEXT,
                priority INTEGER DEFAULT 0,
                data TEXT,
                created_at TEXT,
                claimed_by TEXT,
                claimed_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT
            )
        """
        )
        conn.commit()
        conn.close()

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    def test_register_creates_worker_record(self, temp_db):
        """Test registration creates database record."""
        worker = ConfirmWorker()

        with patch("workers.confirm_worker.DB_PATH", temp_db):
            worker._register()

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker.worker_id,)).fetchone()
        conn.close()

        assert row is not None
        assert row[1] == "confirm"  # worker_type
        assert row[2] == "running"  # status

    def test_unregister_removes_worker_record(self, temp_db):
        """Test unregistration removes database record."""
        worker = ConfirmWorker()

        with patch("workers.confirm_worker.DB_PATH", temp_db):
            worker._register()
            worker._unregister()

        conn = sqlite3.connect(temp_db)
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker.worker_id,)).fetchone()
        conn.close()

        assert row is None

    def test_heartbeat_updates_timestamp(self, temp_db):
        """Test heartbeat updates last_heartbeat."""
        worker = ConfirmWorker()

        with patch("workers.confirm_worker.DB_PATH", temp_db):
            worker._register()
            initial_time = (
                sqlite3.connect(temp_db)
                .execute("SELECT last_heartbeat FROM workers WHERE id = ?", (worker.worker_id,))
                .fetchone()[0]
            )

            import time

            time.sleep(0.01)
            worker._heartbeat()

            new_time = (
                sqlite3.connect(temp_db)
                .execute("SELECT last_heartbeat FROM workers WHERE id = ?", (worker.worker_id,))
                .fetchone()[0]
            )

        assert new_time >= initial_time


class TestConfirmWorkerTasks:
    """Tests for task processing."""

    @pytest.fixture
    def temp_db_with_tasks(self):
        """Create database with test tasks."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE workers (
                id TEXT PRIMARY KEY,
                worker_type TEXT,
                status TEXT,
                last_heartbeat TEXT
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE task_queue (
                id INTEGER PRIMARY KEY,
                task_type TEXT,
                status TEXT,
                priority INTEGER DEFAULT 0,
                data TEXT,
                created_at TEXT,
                claimed_by TEXT,
                claimed_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT
            )
        """
        )

        # Add test tasks
        conn.execute(
            """
            INSERT INTO task_queue (task_type, status, priority, data, created_at)
            VALUES ('confirm', 'pending', 1, '{"action": "test"}', datetime('now'))
        """
        )
        conn.commit()
        conn.close()

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    def test_process_confirmations_finds_pending_tasks(self, temp_db_with_tasks):
        """Test process_confirmations finds pending confirm tasks."""
        worker = ConfirmWorker()

        with patch("workers.confirm_worker.DB_PATH", temp_db_with_tasks):
            worker._process_confirmations()

        conn = sqlite3.connect(temp_db_with_tasks)
        task = conn.execute("SELECT status FROM task_queue WHERE id = 1").fetchone()
        conn.close()

        assert task[0] == "completed"


class TestConfirmTmux:
    """Tests for tmux confirmation."""

    def test_confirm_tmux_with_session(self):
        """Test tmux confirmation with valid session."""
        worker = ConfirmWorker()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = worker._confirm_tmux({"session": "test-session", "response": "y"})

        assert result["success"] is True
        assert result["session"] == "test-session"
        mock_run.assert_called_once()

    def test_confirm_tmux_without_session(self):
        """Test tmux confirmation without session fails."""
        worker = ConfirmWorker()

        result = worker._confirm_tmux({})

        assert result["success"] is False
        assert "No session specified" in result["error"]

    def test_confirm_tmux_subprocess_error(self):
        """Test tmux confirmation handles subprocess errors."""
        import subprocess

        worker = ConfirmWorker()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "tmux", stderr=b"error")
            result = worker._confirm_tmux({"session": "test", "response": "y"})

        # Should handle error gracefully
        assert result["success"] is False
        assert "error" in result


class TestApproveAll:
    """Tests for approve all functionality."""

    def test_approve_all_returns_success(self):
        """Test approve_all returns success."""
        worker = ConfirmWorker()

        result = worker._approve_all({})

        assert result["success"] is True
        assert "Approved all" in result["message"]


class TestWorkerLifecycle:
    """Tests for worker start/stop lifecycle."""

    def test_stop_sets_running_false(self):
        """Test stop method sets running to False."""
        worker = ConfirmWorker()
        worker.running = True

        worker.stop()

        assert worker.running is False
