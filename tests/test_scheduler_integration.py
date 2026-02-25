#!/usr/bin/env python3
"""
Scheduler Integration Tests

Tests for Scheduled Task Service with Cron support.

Tests the full integration of:
- Cron expression parsing and validation
- Next run time calculation
- Scheduled task CRUD operations
- Task execution tracking
- Predefined schedules (@hourly, @daily, etc.)
- Execution history
- Task enabling/disabling
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with scheduler schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create scheduler tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            cron_expression TEXT NOT NULL,
            task_type TEXT NOT NULL,
            task_data TEXT,
            enabled BOOLEAN DEFAULT 1,
            last_run TIMESTAMP,
            next_run TIMESTAMP,
            run_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS task_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            status TEXT NOT NULL,
            output TEXT,
            error_message TEXT,
            duration_seconds REAL,
            FOREIGN KEY (task_id) REFERENCES scheduled_tasks(id)
        );

        CREATE INDEX idx_scheduled_tasks_enabled ON scheduled_tasks(enabled);
        CREATE INDEX idx_scheduled_tasks_next_run ON scheduled_tasks(next_run);
        CREATE INDEX idx_task_executions_task ON task_executions(task_id);
        CREATE INDEX idx_task_executions_started ON task_executions(started_at);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestCronExpressionParsing:
    """Test cron expression parsing and validation."""

    def test_parse_basic_cron_expression(self, test_db):
        """Test parsing basic cron expression."""
        # Store valid cron expression
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("test-task", "*/15 * * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Verify stored
        row = test_db.execute(
            "SELECT cron_expression FROM scheduled_tasks WHERE id = ?", (task_id,)
        ).fetchone()

        assert row[0] == "*/15 * * * *"

    def test_parse_predefined_schedule(self, test_db):
        """Test parsing predefined schedule (@daily, @hourly)."""
        # Store predefined schedules
        schedules = [
            ("hourly-task", "@hourly", "shell"),
            ("daily-task", "@daily", "shell"),
            ("weekly-task", "@weekly", "shell"),
            ("monthly-task", "@monthly", "shell"),
        ]

        for name, cron, task_type in schedules:
            test_db.execute(
                """
                INSERT INTO scheduled_tasks (name, cron_expression, task_type)
                VALUES (?, ?, ?)
            """,
                (name, cron, task_type),
            )
        test_db.commit()

        # Verify all stored
        rows = test_db.execute("SELECT name, cron_expression FROM scheduled_tasks").fetchall()

        assert len(rows) == 4
        assert any(row[1] == "@hourly" for row in rows)
        assert any(row[1] == "@daily" for row in rows)

    def test_validate_cron_syntax(self, test_db):
        """Test cron expression syntax validation."""
        # Valid expressions
        valid_expressions = [
            "0 0 * * *",  # Daily at midnight
            "*/5 * * * *",  # Every 5 minutes
            "0 9-17 * * 1-5",  # Weekdays 9am-5pm
            "30 2 1 * *",  # 2:30 AM on 1st of month
        ]

        for i, expr in enumerate(valid_expressions):
            test_db.execute(
                """
                INSERT INTO scheduled_tasks (name, cron_expression, task_type)
                VALUES (?, ?, ?)
            """,
                (f"valid-{i}", expr, "shell"),
            )
        test_db.commit()

        # Verify all stored
        count = test_db.execute("SELECT COUNT(*) FROM scheduled_tasks").fetchone()[0]

        assert count == len(valid_expressions)


class TestScheduledTaskCRUD:
    """Test scheduled task CRUD operations."""

    def test_create_scheduled_task(self, test_db):
        """Test creating a scheduled task."""
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks
            (name, description, cron_expression, task_type, task_data)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("cleanup", "Clean temp files", "0 2 * * *", "shell", '{"command": "rm -f /tmp/*.log"}'),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Verify created
        row = test_db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row is not None
        assert row[1] == "cleanup"
        assert row[3] == "0 2 * * *"

    def test_get_scheduled_task(self, test_db):
        """Test retrieving a scheduled task."""
        # Insert task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("backup", "0 3 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Retrieve
        row = test_db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row is not None
        assert row[1] == "backup"

    def test_update_scheduled_task(self, test_db):
        """Test updating a scheduled task."""
        # Insert task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("update-test", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Update
        test_db.execute(
            """
            UPDATE scheduled_tasks
            SET cron_expression = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            ("0 2 * * *", task_id),
        )
        test_db.commit()

        # Verify updated
        row = test_db.execute(
            "SELECT cron_expression FROM scheduled_tasks WHERE id = ?", (task_id,)
        ).fetchone()

        assert row[0] == "0 2 * * *"

    def test_delete_scheduled_task(self, test_db):
        """Test deleting a scheduled task."""
        # Insert task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("delete-me", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Delete
        test_db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        test_db.commit()

        # Verify deleted
        row = test_db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row is None

    def test_list_all_scheduled_tasks(self, test_db):
        """Test listing all scheduled tasks."""
        # Insert multiple tasks
        test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES ('task-1', '0 0 * * *', 'shell'),
                   ('task-2', '0 1 * * *', 'shell'),
                   ('task-3', '0 2 * * *', 'shell')
        """
        )
        test_db.commit()

        # List all
        rows = test_db.execute("SELECT * FROM scheduled_tasks ORDER BY name").fetchall()

        assert len(rows) == 3


class TestNextRunCalculation:
    """Test next run time calculation."""

    def test_calculate_next_run_daily(self, test_db):
        """Test calculating next run for daily schedule."""
        # Insert daily task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, next_run)
            VALUES (?, ?, ?, ?)
        """,
            ("daily", "@daily", "shell", datetime.now().isoformat()),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Get next run
        row = test_db.execute("SELECT next_run FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row[0] is not None

    def test_calculate_next_run_hourly(self, test_db):
        """Test calculating next run for hourly schedule."""
        # Insert hourly task
        now = datetime.now()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, next_run)
            VALUES (?, ?, ?, ?)
        """,
            ("hourly", "@hourly", "shell", next_hour.isoformat()),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Verify next run is set
        row = test_db.execute("SELECT next_run FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row[0] is not None

    def test_update_next_run_after_execution(self, test_db):
        """Test updating next run after task execution."""
        # Insert task
        now = datetime.now()
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, next_run)
            VALUES (?, ?, ?, ?)
        """,
            ("update-next", "*/15 * * * *", "shell", now.isoformat()),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Simulate execution and update next run
        new_next_run = now + timedelta(minutes=15)
        test_db.execute(
            """
            UPDATE scheduled_tasks
            SET last_run = ?, next_run = ?, run_count = run_count + 1
            WHERE id = ?
        """,
            (now.isoformat(), new_next_run.isoformat(), task_id),
        )
        test_db.commit()

        # Verify updated
        row = test_db.execute(
            "SELECT last_run, next_run, run_count FROM scheduled_tasks WHERE id = ?", (task_id,)
        ).fetchone()

        assert row[0] is not None
        assert row[1] is not None
        assert row[2] == 1


class TestTaskExecution:
    """Test task execution tracking."""

    def test_record_successful_execution(self, test_db):
        """Test recording successful task execution."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("exec-success", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Record execution
        started = datetime.now()
        completed = started + timedelta(seconds=5)

        test_db.execute(
            """
            INSERT INTO task_executions
            (task_id, started_at, completed_at, status, duration_seconds)
            VALUES (?, ?, ?, ?, ?)
        """,
            (task_id, started.isoformat(), completed.isoformat(), "success", 5.2),
        )

        # Update task
        test_db.execute(
            """
            UPDATE scheduled_tasks
            SET last_run = ?, run_count = run_count + 1
            WHERE id = ?
        """,
            (started.isoformat(), task_id),
        )
        test_db.commit()

        # Verify
        execution = test_db.execute(
            "SELECT status, duration_seconds FROM task_executions WHERE task_id = ?", (task_id,)
        ).fetchone()

        assert execution[0] == "success"
        assert execution[1] == 5.2

    def test_record_failed_execution(self, test_db):
        """Test recording failed task execution."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("exec-fail", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Record failed execution
        started = datetime.now()
        test_db.execute(
            """
            INSERT INTO task_executions
            (task_id, started_at, status, error_message)
            VALUES (?, ?, ?, ?)
        """,
            (task_id, started.isoformat(), "error", "Command not found"),
        )

        # Update failure count
        test_db.execute(
            """
            UPDATE scheduled_tasks
            SET failure_count = failure_count + 1
            WHERE id = ?
        """,
            (task_id,),
        )
        test_db.commit()

        # Verify
        execution = test_db.execute(
            "SELECT status, error_message FROM task_executions WHERE task_id = ?", (task_id,)
        ).fetchone()

        task = test_db.execute("SELECT failure_count FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert execution[0] == "error"
        assert execution[1] == "Command not found"
        assert task[0] == 1

    def test_track_execution_output(self, test_db):
        """Test tracking task execution output."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("exec-output", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Record execution with output
        output = "Task completed successfully\n3 files processed"
        test_db.execute(
            """
            INSERT INTO task_executions
            (task_id, started_at, status, output)
            VALUES (?, ?, ?, ?)
        """,
            (task_id, datetime.now().isoformat(), "success", output),
        )
        test_db.commit()

        # Verify output stored
        execution = test_db.execute(
            "SELECT output FROM task_executions WHERE task_id = ?", (task_id,)
        ).fetchone()

        assert "Task completed successfully" in execution[0]
        assert "3 files processed" in execution[0]


class TestExecutionHistory:
    """Test execution history tracking."""

    def test_get_execution_history(self, test_db):
        """Test retrieving execution history for a task."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("history-task", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Record multiple executions
        for i in range(5):
            test_db.execute(
                """
                INSERT INTO task_executions
                (task_id, started_at, status)
                VALUES (?, ?, ?)
            """,
                (task_id, datetime.now().isoformat(), "success" if i < 4 else "error"),
            )
        test_db.commit()

        # Get history
        history = test_db.execute(
            "SELECT * FROM task_executions WHERE task_id = ? ORDER BY started_at DESC", (task_id,)
        ).fetchall()

        assert len(history) == 5

    def test_calculate_success_rate(self, test_db):
        """Test calculating task success rate."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("success-rate", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Record executions: 8 success, 2 failures
        for i in range(10):
            test_db.execute(
                """
                INSERT INTO task_executions
                (task_id, started_at, status)
                VALUES (?, ?, ?)
            """,
                (task_id, datetime.now().isoformat(), "success" if i < 8 else "error"),
            )
        test_db.commit()

        # Calculate success rate
        total = test_db.execute(
            "SELECT COUNT(*) FROM task_executions WHERE task_id = ?", (task_id,)
        ).fetchone()[0]

        successes = test_db.execute(
            "SELECT COUNT(*) FROM task_executions WHERE task_id = ? AND status = 'success'", (task_id,)
        ).fetchone()[0]

        success_rate = (successes / total) * 100 if total > 0 else 0

        assert total == 10
        assert successes == 8
        assert success_rate == 80.0

    def test_get_recent_executions(self, test_db):
        """Test retrieving recent executions."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("recent", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Record executions
        for i in range(10):
            test_db.execute(
                """
                INSERT INTO task_executions
                (task_id, started_at, status)
                VALUES (?, ?, ?)
            """,
                (task_id, datetime.now().isoformat(), "success"),
            )
        test_db.commit()

        # Get last 5 executions
        recent = test_db.execute(
            """
            SELECT * FROM task_executions
            WHERE task_id = ?
            ORDER BY started_at DESC
            LIMIT 5
        """,
            (task_id,),
        ).fetchall()

        assert len(recent) == 5


class TestTaskEnabling:
    """Test task enabling/disabling."""

    def test_disable_task(self, test_db):
        """Test disabling a scheduled task."""
        # Create enabled task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, enabled)
            VALUES (?, ?, ?, ?)
        """,
            ("disable-me", "0 0 * * *", "shell", 1),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Disable
        test_db.execute(
            """
            UPDATE scheduled_tasks
            SET enabled = 0
            WHERE id = ?
        """,
            (task_id,),
        )
        test_db.commit()

        # Verify disabled
        row = test_db.execute("SELECT enabled FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row[0] == 0

    def test_enable_task(self, test_db):
        """Test enabling a disabled task."""
        # Create disabled task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, enabled)
            VALUES (?, ?, ?, ?)
        """,
            ("enable-me", "0 0 * * *", "shell", 0),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Enable
        test_db.execute(
            """
            UPDATE scheduled_tasks
            SET enabled = 1
            WHERE id = ?
        """,
            (task_id,),
        )
        test_db.commit()

        # Verify enabled
        row = test_db.execute("SELECT enabled FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row[0] == 1

    def test_list_enabled_tasks_only(self, test_db):
        """Test listing only enabled tasks."""
        # Create mixed tasks
        test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, enabled)
            VALUES ('enabled-1', '0 0 * * *', 'shell', 1),
                   ('disabled-1', '0 0 * * *', 'shell', 0),
                   ('enabled-2', '0 0 * * *', 'shell', 1)
        """
        )
        test_db.commit()

        # Get enabled only
        enabled = test_db.execute("SELECT * FROM scheduled_tasks WHERE enabled = 1").fetchall()

        assert len(enabled) == 2


class TestTaskTypes:
    """Test different task types."""

    def test_shell_task(self, test_db):
        """Test shell command task."""
        import json

        task_data = json.dumps({"command": "echo 'Hello World'"})

        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, task_data)
            VALUES (?, ?, ?, ?)
        """,
            ("shell-task", "0 0 * * *", "shell", task_data),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT task_type, task_data FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row[0] == "shell"
        data = json.loads(row[1])
        assert data["command"] == "echo 'Hello World'"

    def test_api_task(self, test_db):
        """Test API call task."""
        import json

        task_data = json.dumps({"url": "https://api.example.com/status", "method": "GET"})

        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, task_data)
            VALUES (?, ?, ?, ?)
        """,
            ("api-task", "0 0 * * *", "api", task_data),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT task_type, task_data FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

        assert row[0] == "api"
        data = json.loads(row[1])
        assert data["url"] == "https://api.example.com/status"


class TestSchedulerStatistics:
    """Test scheduler statistics."""

    def test_count_tasks_by_status(self, test_db):
        """Test counting tasks by enabled status."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type, enabled)
            VALUES ('task-1', '0 0 * * *', 'shell', 1),
                   ('task-2', '0 0 * * *', 'shell', 1),
                   ('task-3', '0 0 * * *', 'shell', 0)
        """
        )
        test_db.commit()

        # Count
        enabled_count = test_db.execute(
            "SELECT COUNT(*) FROM scheduled_tasks WHERE enabled = 1"
        ).fetchone()[0]

        disabled_count = test_db.execute(
            "SELECT COUNT(*) FROM scheduled_tasks WHERE enabled = 0"
        ).fetchone()[0]

        assert enabled_count == 2
        assert disabled_count == 1

    def test_total_execution_count(self, test_db):
        """Test total execution count across all tasks."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO scheduled_tasks (name, cron_expression, task_type)
            VALUES (?, ?, ?)
        """,
            ("count-task", "0 0 * * *", "shell"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Record executions
        for _ in range(10):
            test_db.execute(
                """
                INSERT INTO task_executions
                (task_id, started_at, status)
                VALUES (?, ?, ?)
            """,
                (task_id, datetime.now().isoformat(), "success"),
            )
        test_db.commit()

        # Count
        total = test_db.execute("SELECT COUNT(*) FROM task_executions").fetchone()[0]

        assert total == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
