"""
Integration tests for workers/health_monitor.py

Tests self-healing system including worker monitoring, session health,
database integrity checks, disk space monitoring, and auto-recovery.
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """Create test environment for health monitor."""
    # Create test directories
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    assigner_dir = data_dir / "assigner"
    assigner_dir.mkdir(exist_ok=True)

    db_path = data_dir / "architect.db"
    assigner_db = assigner_dir / "assigner.db"
    pid_file = tmp_path / "health_monitor.pid"

    # Create test databases
    for path in [db_path, assigner_db]:
        conn = sqlite3.connect(path)
        conn.close()

    # Patch paths
    monkeypatch.setattr("workers.health_monitor.Path.cwd", lambda: tmp_path)

    # Import after patching
    import workers.health_monitor as hm

    # Mock psutil.pid_exists
    monkeypatch.setattr("psutil.pid_exists", lambda pid: False)

    yield {
        "tmp_path": tmp_path,
        "data_dir": data_dir,
        "db_path": db_path,
        "assigner_db": assigner_db,
        "pid_file": pid_file,
        "module": hm,
    }


@pytest.mark.integration
class TestMonitorInitialization:
    """Test health monitor initialization."""

    def test_create_monitor_default_config(self, test_env):
        """Test creating monitor with default configuration."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()

        assert monitor.check_interval == 60
        assert monitor.running is False
        assert monitor.session_stuck_threshold == 30 * 60
        assert monitor.worker_restart_delay == 5
        assert monitor.disk_warning_threshold == 90
        assert monitor.disk_critical_threshold == 95

    def test_create_monitor_custom_interval(self, test_env):
        """Test creating monitor with custom interval."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor(check_interval=30)

        assert monitor.check_interval == 30

    def test_monitor_has_worker_configs(self, test_env):
        """Test monitor has worker configurations."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()

        assert "assigner" in monitor.workers
        assert "task_worker" in monitor.workers
        assert "milestone" in monitor.workers

        # Check assigner config
        assigner = monitor.workers["assigner"]
        assert "script" in assigner
        assert "pid_file" in assigner
        assert assigner["critical"] is True

    def test_monitor_initializes_metrics(self, test_env):
        """Test monitor initializes metrics."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()

        assert monitor.metrics["total_checks"] == 0
        assert monitor.metrics["workers_restarted"] == 0
        assert monitor.metrics["sessions_cleared"] == 0
        assert monitor.metrics["tasks_requeued"] == 0
        assert monitor.metrics["locks_cleared"] == 0
        assert monitor.metrics["alerts_sent"] == 0


@pytest.mark.integration
class TestDatabaseInitialization:
    """Test database initialization."""

    def test_init_database_creates_tables(self, test_env):
        """Test database initialization creates tables."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]

        monitor._init_database()

        # Verify tables exist
        conn = sqlite3.connect(test_env["db_path"])
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='health_metrics'"
        )
        assert cursor.fetchone() is not None

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='health_alerts'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_init_database_creates_indexes(self, test_env):
        """Test database initialization creates indexes."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]

        monitor._init_database()

        # Verify indexes exist
        conn = sqlite3.connect(test_env["db_path"])
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_health_metrics_timestamp'"
        )
        assert cursor.fetchone() is not None

        conn.close()


@pytest.mark.integration
class TestWorkerChecking:
    """Test worker process checking."""

    def test_is_worker_running_pid_file_missing(self, test_env):
        """Test checking worker when PID file doesn't exist."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()

        pid_file = test_env["tmp_path"] / "nonexistent.pid"
        result = monitor._is_worker_running(pid_file)

        assert result is False

    def test_is_worker_running_with_pid_file(self, test_env):
        """Test checking worker with PID file."""
        hm = test_env["module"]

        # Create PID file
        pid_file = test_env["tmp_path"] / "worker.pid"
        pid_file.write_text("12345")

        # Mock psutil to simulate running process
        mock_process = MagicMock()
        mock_process.is_running.return_value = True
        mock_process.status.return_value = "running"

        with patch("psutil.pid_exists", return_value=True):
            with patch("psutil.Process", return_value=mock_process):
                monitor = hm.HealthMonitor()
                result = monitor._is_worker_running(pid_file)

                assert result is True

    def test_is_worker_running_stale_pid(self, test_env):
        """Test checking worker with stale PID."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()

        # Create PID file
        pid_file = test_env["tmp_path"] / "worker.pid"
        pid_file.write_text("99999")

        # pid_exists mocked to return False
        result = monitor._is_worker_running(pid_file)

        assert result is False


@pytest.mark.integration
class TestSessionChecking:
    """Test Claude session health checking."""

    def test_check_sessions_no_database(self, test_env):
        """Test checking sessions when database doesn't exist."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.assigner_db = test_env["tmp_path"] / "nonexistent.db"

        # Should not crash
        monitor._check_sessions()

    def test_check_sessions_with_stuck_task(self, test_env):
        """Test detecting stuck sessions."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.assigner_db = test_env["assigner_db"]

        # Create tables
        conn = sqlite3.connect(test_env["assigner_db"])
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY,
                content TEXT,
                assigned_session TEXT,
                assigned_at TIMESTAMP,
                status TEXT,
                error TEXT
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                name TEXT PRIMARY KEY,
                status TEXT,
                current_task_id INTEGER,
                updated_at TIMESTAMP
            )
        """
        )

        # Insert stuck task
        stuck_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute(
            """
            INSERT INTO prompts (id, content, assigned_session, assigned_at, status)
            VALUES (1, 'Test task', 'test-session', ?, 'in_progress')
        """,
            (stuck_time,),
        )
        conn.execute(
            """
            INSERT INTO sessions (name, status) VALUES ('test-session', 'busy')
        """
        )
        conn.commit()
        conn.close()

        # Check sessions
        monitor._check_sessions()

        # Verify task was requeued
        conn = sqlite3.connect(test_env["assigner_db"])
        cursor = conn.execute("SELECT status FROM prompts WHERE id = 1")
        status = cursor.fetchone()[0]
        conn.close()

        assert status == "pending"


@pytest.mark.integration
class TestDatabaseHealth:
    """Test database health checking."""

    def test_check_db_file_integrity(self, test_env):
        """Test database integrity check."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]

        # Should not crash
        monitor._check_db_file(test_env["db_path"], "test")

    def test_check_database_main_and_assigner(self, test_env):
        """Test checking both databases."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]
        monitor.assigner_db = test_env["assigner_db"]

        # Should not crash
        monitor._check_database()


@pytest.mark.integration
class TestHealthEventLogging:
    """Test health event logging."""

    def test_log_health_event(self, test_env):
        """Test logging health event to database."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]
        monitor._init_database()

        monitor._log_health_event(
            component="test_worker",
            status="failed",
            details="Worker crashed",
            action_taken="restarted",
            recovery_successful=True,
        )

        # Verify event logged
        conn = sqlite3.connect(test_env["db_path"])
        cursor = conn.execute("SELECT * FROM health_metrics")
        event = cursor.fetchone()
        conn.close()

        assert event is not None
        assert event[2] == "test_worker"  # component
        assert event[3] == "failed"  # status
        assert event[6] == 1  # recovery_successful


@pytest.mark.integration
class TestAlerting:
    """Test health alerting system."""

    def test_send_alert(self, test_env):
        """Test sending health alert."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]
        monitor._init_database()

        monitor._send_alert("critical", "Worker down", component="assigner")

        # Verify alert logged
        conn = sqlite3.connect(test_env["db_path"])
        cursor = conn.execute("SELECT * FROM health_alerts")
        alert = cursor.fetchone()
        conn.close()

        assert alert is not None
        assert alert[2] == "critical"  # severity
        assert alert[3] == "Worker down"  # message
        assert alert[4] == "assigner"  # component

    def test_send_alert_increments_metric(self, test_env):
        """Test alert increments metrics counter."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]
        monitor._init_database()

        initial_count = monitor.metrics["alerts_sent"]

        monitor._send_alert("warning", "High failure rate")

        assert monitor.metrics["alerts_sent"] == initial_count + 1


@pytest.mark.integration
class TestTaskQueueChecking:
    """Test task queue health checking."""

    def test_check_task_queue_no_database(self, test_env):
        """Test checking task queue when database doesn't exist."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.assigner_db = test_env["tmp_path"] / "nonexistent.db"

        # Should not crash
        monitor._check_task_queue()

    def test_check_task_queue_with_stuck_tasks(self, test_env):
        """Test detecting stuck pending tasks."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.assigner_db = test_env["assigner_db"]

        # Create table
        conn = sqlite3.connect(test_env["assigner_db"])
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY,
                status TEXT,
                created_at TIMESTAMP
            )
        """
        )

        # Insert old pending task
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        conn.execute(
            """
            INSERT INTO prompts (id, status, created_at)
            VALUES (1, 'pending', ?)
        """,
            (old_time,),
        )
        conn.commit()
        conn.close()

        # Check task queue - should detect stuck task
        monitor._check_task_queue()


@pytest.mark.integration
class TestCleanup:
    """Test file cleanup operations."""

    def test_cleanup_old_files(self, test_env):
        """Test cleaning up old log files runs without error."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()

        # Run cleanup - should not crash even if directories don't exist
        monitor._cleanup_old_files(aggressive=False)
        monitor._cleanup_old_files(aggressive=True)

    def test_cleanup_preserves_recent_files(self, test_env):
        """Test cleanup preserves recent files."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()

        # Create recent log file
        log_dir = test_env["tmp_path"]
        recent_log = log_dir / "recent.log"
        recent_log.write_text("recent log content")

        # Run cleanup
        monitor._cleanup_old_files(aggressive=False)

        # Recent file should still exist
        assert recent_log.exists()


@pytest.mark.integration
class TestMonitorLifecycle:
    """Test monitor daemon lifecycle."""

    def test_is_running_no_pid_file(self, test_env):
        """Test is_running when PID file doesn't exist."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.pid_file = test_env["tmp_path"] / "nonexistent.pid"

        assert monitor.is_running() is False

    def test_is_running_with_stale_pid(self, test_env):
        """Test is_running with stale PID file."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.pid_file = test_env["tmp_path"] / "monitor.pid"
        monitor.pid_file.write_text("99999")

        # pid_exists mocked to return False
        assert monitor.is_running() is False

    def test_stop_removes_pid_file(self, test_env):
        """Test stop removes PID file."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.pid_file = test_env["tmp_path"] / "monitor.pid"
        monitor.pid_file.write_text("12345")

        monitor.stop()

        assert not monitor.pid_file.exists()


@pytest.mark.integration
class TestMetrics:
    """Test metrics tracking."""

    def test_metrics_increment_on_health_check(self, test_env, monkeypatch):
        """Test metrics increment during health check."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]
        monitor.assigner_db = test_env["assigner_db"]
        monitor._init_database()

        # Mock subprocess to avoid actual worker restarts
        monkeypatch.setattr("subprocess.Popen", MagicMock())
        monkeypatch.setattr("subprocess.run", MagicMock())

        initial_checks = monitor.metrics["total_checks"]

        monitor._run_health_check()

        assert monitor.metrics["total_checks"] == initial_checks + 1
        assert monitor.metrics["last_check"] is not None


@pytest.mark.integration
class TestDiskSpaceChecking:
    """Test disk space monitoring."""

    @patch("psutil.disk_usage")
    def test_check_disk_space_warning(self, mock_disk_usage, test_env):
        """Test disk space warning threshold."""
        hm = test_env["module"]

        # Mock disk usage at warning level
        mock_usage = MagicMock()
        mock_usage.percent = 91
        mock_disk_usage.return_value = mock_usage

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]
        monitor._init_database()

        # Should not crash, may log warning
        monitor._check_disk_space()

    @patch("psutil.disk_usage")
    def test_check_disk_space_critical(self, mock_disk_usage, test_env):
        """Test disk space critical threshold."""
        hm = test_env["module"]

        # Mock disk usage at critical level
        mock_usage = MagicMock()
        mock_usage.percent = 96
        mock_disk_usage.return_value = mock_usage

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["db_path"]
        monitor._init_database()

        initial_alerts = monitor.metrics["alerts_sent"]

        monitor._check_disk_space()

        # Critical level should trigger alert
        assert monitor.metrics["alerts_sent"] > initial_alerts


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_check_sessions_with_empty_database(self, test_env):
        """Test checking sessions with empty database."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.assigner_db = test_env["assigner_db"]

        # Should not crash with empty database
        monitor._check_sessions()

    def test_log_event_to_missing_database(self, test_env):
        """Test logging event when database missing."""
        hm = test_env["module"]

        monitor = hm.HealthMonitor()
        monitor.db_path = test_env["tmp_path"] / "nonexistent.db"

        # Should not crash, just log error
        monitor._log_health_event("test", "status", "details", "action")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
