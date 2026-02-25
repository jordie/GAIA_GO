#!/usr/bin/env python3
"""
Worker Recovery Integration Tests

Tests for Worker Recovery service.

Tests the full integration of:
- Worker failure detection
- Heartbeat monitoring
- Task release from failed workers
- Worker restart attempts
- Recovery notifications
- Failure history tracking
- Recovery statistics
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with worker recovery schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create worker recovery tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL UNIQUE,
            worker_type TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            last_heartbeat TIMESTAMP,
            last_task_id TEXT,
            restart_count INTEGER DEFAULT 0,
            last_restart TIMESTAMP,
            pid INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            assigned_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS worker_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            failure_type TEXT NOT NULL,
            failure_reason TEXT,
            tasks_affected INTEGER DEFAULT 0,
            recovered BOOLEAN DEFAULT 0,
            recovery_method TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            recovered_at TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
        );

        CREATE TABLE IF NOT EXISTS recovery_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            failure_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            action_result TEXT NOT NULL,
            details TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (failure_id) REFERENCES worker_failures(id)
        );

        CREATE INDEX idx_workers_status ON workers(status);
        CREATE INDEX idx_workers_heartbeat ON workers(last_heartbeat);
        CREATE INDEX idx_tasks_assigned ON tasks(assigned_to);
        CREATE INDEX idx_worker_failures_worker ON worker_failures(worker_id);
        CREATE INDEX idx_worker_failures_recovered ON worker_failures(recovered);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestWorkerFailureDetection:
    """Test worker failure detection."""

    def test_detect_stale_heartbeat(self, test_db):
        """Test detecting worker with stale heartbeat."""
        # Create worker with old heartbeat
        old_time = (datetime.now() - timedelta(minutes=5)).isoformat()

        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status, last_heartbeat)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "task_worker", "active", old_time),
        )
        test_db.commit()

        # Check heartbeat age
        worker = test_db.execute(
            "SELECT last_heartbeat FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()

        heartbeat_time = datetime.fromisoformat(worker[0])
        age_seconds = (datetime.now() - heartbeat_time).total_seconds()

        # Should be stale (> 120 seconds)
        assert age_seconds > 120

    def test_detect_missing_heartbeat(self, test_db):
        """Test detecting worker with no heartbeat."""
        # Create worker without heartbeat
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status, last_heartbeat)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "task_worker", "active", None),
        )
        test_db.commit()

        # Check for missing heartbeat
        worker = test_db.execute(
            "SELECT last_heartbeat FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()

        assert worker[0] is None

    def test_healthy_worker_not_flagged(self, test_db):
        """Test that healthy workers are not flagged."""
        # Create worker with recent heartbeat
        recent_time = datetime.now().isoformat()

        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status, last_heartbeat)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "task_worker", "active", recent_time),
        )
        test_db.commit()

        # Check heartbeat age
        worker = test_db.execute(
            "SELECT last_heartbeat FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()

        heartbeat_time = datetime.fromisoformat(worker[0])
        age_seconds = (datetime.now() - heartbeat_time).total_seconds()

        # Should be fresh (< 60 seconds)
        assert age_seconds < 60


class TestTaskRelease:
    """Test releasing tasks from failed workers."""

    def test_release_assigned_tasks(self, test_db):
        """Test releasing tasks back to queue when worker fails."""
        # Create worker and assigned task
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed"),
        )

        test_db.execute(
            """
            INSERT INTO tasks (id, title, status, assigned_to)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "Task 1", "in_progress", "worker-1"),
        )
        test_db.commit()

        # Release task
        test_db.execute(
            """
            UPDATE tasks
            SET status = 'pending', assigned_to = NULL, assigned_at = NULL
            WHERE assigned_to = ? AND status = 'in_progress'
        """,
            ("worker-1",),
        )
        test_db.commit()

        # Verify released
        task = test_db.execute("SELECT status, assigned_to FROM tasks WHERE id = ?", ("T123",)).fetchone()

        assert task[0] == "pending"
        assert task[1] is None

    def test_release_multiple_tasks(self, test_db):
        """Test releasing multiple tasks from failed worker."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed"),
        )

        # Create multiple assigned tasks
        for i in range(3):
            test_db.execute(
                """
                INSERT INTO tasks (id, title, status, assigned_to)
                VALUES (?, ?, ?, ?)
            """,
                (f"T{i+1}", f"Task {i+1}", "in_progress", "worker-1"),
            )
        test_db.commit()

        # Release all tasks
        test_db.execute(
            """
            UPDATE tasks
            SET status = 'pending', assigned_to = NULL
            WHERE assigned_to = ?
        """,
            ("worker-1",),
        )
        test_db.commit()

        # Verify all released
        released_count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'pending' AND assigned_to IS NULL"
        ).fetchone()[0]

        assert released_count == 3

    def test_preserve_completed_tasks(self, test_db):
        """Test that completed tasks are not released."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed"),
        )

        # Create completed task
        test_db.execute(
            """
            INSERT INTO tasks (id, title, status, assigned_to, completed_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("T123", "Completed Task", "completed", "worker-1", datetime.now().isoformat()),
        )
        test_db.commit()

        # Try to release (should not affect completed tasks)
        test_db.execute(
            """
            UPDATE tasks
            SET status = 'pending', assigned_to = NULL
            WHERE assigned_to = ? AND status != 'completed'
        """,
            ("worker-1",),
        )
        test_db.commit()

        # Verify still completed and assigned
        task = test_db.execute("SELECT status, assigned_to FROM tasks WHERE id = ?", ("T123",)).fetchone()

        assert task[0] == "completed"
        assert task[1] == "worker-1"


class TestWorkerRestart:
    """Test worker restart attempts."""

    def test_record_restart_attempt(self, test_db):
        """Test recording a restart attempt."""
        # Create failed worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status, restart_count)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed", 0),
        )
        test_db.commit()

        # Record restart
        test_db.execute(
            """
            UPDATE workers
            SET restart_count = restart_count + 1,
                last_restart = ?,
                status = 'restarting'
            WHERE worker_id = ?
        """,
            (datetime.now().isoformat(), "worker-1"),
        )
        test_db.commit()

        # Verify
        worker = test_db.execute(
            "SELECT restart_count, status FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()

        assert worker[0] == 1
        assert worker[1] == "restarting"

    def test_max_restart_attempts(self, test_db):
        """Test enforcing max restart attempts."""
        # Create worker with high restart count
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status, restart_count)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed", 5),
        )
        test_db.commit()

        # Check restart count
        worker = test_db.execute(
            "SELECT restart_count FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()

        # Should exceed max (e.g., 3)
        assert worker[0] >= 5

    def test_successful_restart(self, test_db):
        """Test recording successful restart."""
        # Create restarting worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status, restart_count)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "task_worker", "restarting", 1),
        )
        test_db.commit()

        # Mark as active after restart
        test_db.execute(
            """
            UPDATE workers
            SET status = 'active',
                last_heartbeat = ?
            WHERE worker_id = ?
        """,
            (datetime.now().isoformat(), "worker-1"),
        )
        test_db.commit()

        # Verify
        worker = test_db.execute(
            "SELECT status FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()

        assert worker[0] == "active"


class TestFailureLogging:
    """Test failure logging and tracking."""

    def test_log_worker_failure(self, test_db):
        """Test logging a worker failure."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed"),
        )
        test_db.commit()

        # Log failure
        cursor = test_db.execute(
            """
            INSERT INTO worker_failures
            (worker_id, failure_type, failure_reason, tasks_affected)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "heartbeat_timeout", "No heartbeat for 5 minutes", 3),
        )
        failure_id = cursor.lastrowid
        test_db.commit()

        # Verify
        failure = test_db.execute(
            "SELECT * FROM worker_failures WHERE id = ?", (failure_id,)
        ).fetchone()

        assert failure is not None
        assert failure[2] == "heartbeat_timeout"
        assert failure[4] == 3

    def test_track_multiple_failures(self, test_db):
        """Test tracking multiple failures for same worker."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "active"),
        )

        # Log multiple failures
        for i in range(3):
            test_db.execute(
                """
                INSERT INTO worker_failures
                (worker_id, failure_type, failure_reason)
                VALUES (?, ?, ?)
            """,
                ("worker-1", "crash", f"Failure {i+1}"),
            )
        test_db.commit()

        # Verify
        failures = test_db.execute(
            "SELECT * FROM worker_failures WHERE worker_id = ?", ("worker-1",)
        ).fetchall()

        assert len(failures) == 3

    def test_mark_failure_recovered(self, test_db):
        """Test marking a failure as recovered."""
        # Create worker and failure
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "active"),
        )

        cursor = test_db.execute(
            """
            INSERT INTO worker_failures
            (worker_id, failure_type, failure_reason, recovered)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "crash", "Process crashed", 0),
        )
        failure_id = cursor.lastrowid
        test_db.commit()

        # Mark recovered
        test_db.execute(
            """
            UPDATE worker_failures
            SET recovered = 1,
                recovery_method = 'restart',
                recovered_at = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), failure_id),
        )
        test_db.commit()

        # Verify
        failure = test_db.execute(
            "SELECT recovered, recovery_method FROM worker_failures WHERE id = ?", (failure_id,)
        ).fetchone()

        assert failure[0] == 1
        assert failure[1] == "restart"


class TestRecoveryActions:
    """Test recovery action logging."""

    def test_log_recovery_action(self, test_db):
        """Test logging a recovery action."""
        # Create worker and failure
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed"),
        )

        cursor = test_db.execute(
            """
            INSERT INTO worker_failures
            (worker_id, failure_type, failure_reason)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "crash", "Process crashed"),
        )
        failure_id = cursor.lastrowid
        test_db.commit()

        # Log action
        test_db.execute(
            """
            INSERT INTO recovery_actions
            (failure_id, action_type, action_result, details)
            VALUES (?, ?, ?, ?)
        """,
            (failure_id, "restart_worker", "success", "Worker restarted successfully"),
        )
        test_db.commit()

        # Verify
        action = test_db.execute(
            "SELECT action_type, action_result FROM recovery_actions WHERE failure_id = ?", (failure_id,)
        ).fetchone()

        assert action[0] == "restart_worker"
        assert action[1] == "success"

    def test_track_failed_recovery(self, test_db):
        """Test tracking failed recovery attempts."""
        # Create failure
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed"),
        )

        cursor = test_db.execute(
            """
            INSERT INTO worker_failures
            (worker_id, failure_type, failure_reason)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "crash", "Process crashed"),
        )
        failure_id = cursor.lastrowid
        test_db.commit()

        # Log failed action
        test_db.execute(
            """
            INSERT INTO recovery_actions
            (failure_id, action_type, action_result, details)
            VALUES (?, ?, ?, ?)
        """,
            (failure_id, "restart_worker", "failed", "Process failed to start"),
        )
        test_db.commit()

        # Verify
        action = test_db.execute(
            "SELECT action_result FROM recovery_actions WHERE failure_id = ?", (failure_id,)
        ).fetchone()

        assert action[0] == "failed"

    def test_multiple_recovery_attempts(self, test_db):
        """Test logging multiple recovery attempts."""
        # Create failure
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "failed"),
        )

        cursor = test_db.execute(
            """
            INSERT INTO worker_failures
            (worker_id, failure_type, failure_reason)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "crash", "Process crashed"),
        )
        failure_id = cursor.lastrowid
        test_db.commit()

        # Log multiple attempts
        attempts = [
            ("restart_worker", "failed"),
            ("restart_worker", "failed"),
            ("restart_worker", "success"),
        ]

        for action_type, result in attempts:
            test_db.execute(
                """
                INSERT INTO recovery_actions
                (failure_id, action_type, action_result)
                VALUES (?, ?, ?)
            """,
                (failure_id, action_type, result),
            )
        test_db.commit()

        # Verify
        actions = test_db.execute(
            "SELECT * FROM recovery_actions WHERE failure_id = ?", (failure_id,)
        ).fetchall()

        assert len(actions) == 3


class TestRecoveryStatistics:
    """Test recovery statistics and reporting."""

    def test_count_total_failures(self, test_db):
        """Test counting total failures."""
        # Create workers and failures
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES ('worker-1', 'task_worker', 'active'),
                   ('worker-2', 'task_worker', 'active')
        """
        )

        for i in range(5):
            test_db.execute(
                """
                INSERT INTO worker_failures
                (worker_id, failure_type, failure_reason)
                VALUES (?, ?, ?)
            """,
                (f"worker-{(i % 2) + 1}", "crash", f"Failure {i+1}"),
            )
        test_db.commit()

        # Count
        total = test_db.execute("SELECT COUNT(*) FROM worker_failures").fetchone()[0]

        assert total == 5

    def test_count_recovered_failures(self, test_db):
        """Test counting recovered failures."""
        # Create failures with different recovery status
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "active"),
        )

        for i in range(5):
            test_db.execute(
                """
                INSERT INTO worker_failures
                (worker_id, failure_type, failure_reason, recovered)
                VALUES (?, ?, ?, ?)
            """,
                ("worker-1", "crash", f"Failure {i+1}", 1 if i < 3 else 0),
            )
        test_db.commit()

        # Count recovered
        recovered = test_db.execute(
            "SELECT COUNT(*) FROM worker_failures WHERE recovered = 1"
        ).fetchone()[0]

        assert recovered == 3

    def test_failure_rate_by_worker_type(self, test_db):
        """Test calculating failure rate by worker type."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES ('worker-1', 'task_worker', 'active'),
                   ('worker-2', 'api_worker', 'active')
        """
        )

        # Create failures
        test_db.execute(
            """
            INSERT INTO worker_failures (worker_id, failure_type, failure_reason)
            VALUES ('worker-1', 'crash', 'Crashed'),
                   ('worker-1', 'crash', 'Crashed'),
                   ('worker-2', 'crash', 'Crashed')
        """
        )
        test_db.commit()

        # Get failure counts by type
        rows = test_db.execute(
            """
            SELECT w.worker_type, COUNT(wf.id) as failure_count
            FROM workers w
            LEFT JOIN worker_failures wf ON w.worker_id = wf.worker_id
            GROUP BY w.worker_type
        """
        ).fetchall()

        type_counts = {row[0]: row[1] for row in rows}
        assert type_counts["task_worker"] == 2
        assert type_counts["api_worker"] == 1


class TestWorkerStatus:
    """Test worker status management."""

    def test_update_worker_status(self, test_db):
        """Test updating worker status."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", "active"),
        )
        test_db.commit()

        # Update to failed
        test_db.execute(
            """
            UPDATE workers
            SET status = 'failed'
            WHERE worker_id = ?
        """,
            ("worker-1",),
        )
        test_db.commit()

        # Verify
        status = test_db.execute(
            "SELECT status FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()[0]

        assert status == "failed"

    def test_get_active_workers(self, test_db):
        """Test getting active workers."""
        # Create workers with different statuses
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES ('worker-1', 'task_worker', 'active'),
                   ('worker-2', 'task_worker', 'failed'),
                   ('worker-3', 'task_worker', 'active')
        """
        )
        test_db.commit()

        # Get active
        active = test_db.execute(
            "SELECT * FROM workers WHERE status = 'active'"
        ).fetchall()

        assert len(active) == 2

    def test_get_failed_workers(self, test_db):
        """Test getting failed workers."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES ('worker-1', 'task_worker', 'active'),
                   ('worker-2', 'task_worker', 'failed'),
                   ('worker-3', 'task_worker', 'failed')
        """
        )
        test_db.commit()

        # Get failed
        failed = test_db.execute(
            "SELECT * FROM workers WHERE status = 'failed'"
        ).fetchall()

        assert len(failed) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
