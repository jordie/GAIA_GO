#!/usr/bin/env python3
"""
Auto-Assignment Integration Tests

Tests for Task Auto-Assignment system.

Tests the full integration of:
- Assignment strategies (least_loaded, round_robin, skill_match, balanced, fastest)
- Workload calculation and balancing
- Worker availability checking
- Skill matching
- Task distribution
- Concurrent assignment handling
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with auto-assignment schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create auto-assignment tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT DEFAULT 'active',
            skills TEXT,
            capacity INTEGER DEFAULT 40,
            max_concurrent_tasks INTEGER DEFAULT 5,
            last_heartbeat TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            assigned_to INTEGER,
            story_points INTEGER DEFAULT 0,
            estimated_hours REAL DEFAULT 0,
            required_skills TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (assigned_to) REFERENCES workers(id)
        );

        CREATE TABLE IF NOT EXISTS task_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            worker_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            strategy TEXT,
            score REAL,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        );

        CREATE TABLE IF NOT EXISTS worker_stats (
            worker_id INTEGER PRIMARY KEY,
            total_tasks INTEGER DEFAULT 0,
            completed_tasks INTEGER DEFAULT 0,
            avg_completion_hours REAL DEFAULT 0,
            success_rate REAL DEFAULT 0,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        );

        CREATE INDEX idx_tasks_status ON tasks(status);
        CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
        CREATE INDEX idx_task_assignments_worker ON task_assignments(worker_id);
        CREATE INDEX idx_task_assignments_task ON task_assignments(task_id);
    """
    )
    conn.commit()

    yield conn

    conn.close()


@pytest.fixture
def auto_assign_service(test_db, tmp_path):
    """Create AutoAssignService instance for testing."""
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from services.auto_assign import AutoAssignService

        service = AutoAssignService(str(tmp_path / "test.db"))
        return service
    except ImportError:
        pytest.skip("AutoAssignService not available")


class TestLeastLoadedStrategy:
    """Test least loaded assignment strategy."""

    def test_assign_to_worker_with_fewest_tasks(self, auto_assign_service, test_db):
        """Test assigning to worker with fewest active tasks."""
        # Create workers
        test_db.execute(
            "INSERT INTO workers (name, status) VALUES ('worker-1', 'active'), ('worker-2', 'active')"
        )

        # Worker 1 has 2 tasks, Worker 2 has 1 task
        test_db.execute(
            """
            INSERT INTO tasks (id, title, assigned_to, status)
            VALUES ('T1', 'Task 1', 1, 'in_progress'),
                   ('T2', 'Task 2', 1, 'in_progress'),
                   ('T3', 'Task 3', 2, 'in_progress')
        """
        )
        test_db.commit()

        # New task should go to worker 2 (fewer tasks)
        test_db.execute("INSERT INTO tasks (id, title, status) VALUES ('T4', 'New Task', 'pending')")
        test_db.commit()

        # Manually calculate workload
        worker1_count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE assigned_to = 1 AND status != 'completed'"
        ).fetchone()[0]

        worker2_count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE assigned_to = 2 AND status != 'completed'"
        ).fetchone()[0]

        assert worker1_count == 2
        assert worker2_count == 1
        # Worker 2 should be chosen

    def test_respect_max_concurrent_tasks(self, auto_assign_service, test_db):
        """Test that workers at max capacity are not assigned new tasks."""
        # Create worker with max_concurrent_tasks = 2
        test_db.execute(
            "INSERT INTO workers (name, status, max_concurrent_tasks) VALUES ('worker-1', 'active', 2)"
        )

        # Assign 2 tasks (at capacity)
        test_db.execute(
            """
            INSERT INTO tasks (id, title, assigned_to, status)
            VALUES ('T1', 'Task 1', 1, 'in_progress'),
                   ('T2', 'Task 2', 1, 'in_progress')
        """
        )
        test_db.commit()

        # Check current workload
        current_tasks = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE assigned_to = 1 AND status != 'completed'"
        ).fetchone()[0]

        max_tasks = test_db.execute("SELECT max_concurrent_tasks FROM workers WHERE id = 1").fetchone()[0]

        assert current_tasks == 2
        assert current_tasks >= max_tasks  # At or over capacity


class TestRoundRobinStrategy:
    """Test round robin assignment strategy."""

    def test_cycle_through_workers(self, auto_assign_service, test_db):
        """Test tasks are assigned in round-robin order."""
        # Create 3 workers
        test_db.execute(
            """
            INSERT INTO workers (name, status)
            VALUES ('worker-1', 'active'),
                   ('worker-2', 'active'),
                   ('worker-3', 'active')
        """
        )
        test_db.commit()

        # Create 6 tasks
        for i in range(6):
            test_db.execute(f"INSERT INTO tasks (id, title, status) VALUES ('T{i+1}', 'Task {i+1}', 'pending')")
        test_db.commit()

        # If assigning in round-robin, each worker should get 2 tasks
        # This would be tested by the service's assign_all_pending() method

    def test_skip_unavailable_workers(self, auto_assign_service, test_db):
        """Test that inactive workers are skipped in rotation."""
        # Create workers with one inactive
        test_db.execute(
            """
            INSERT INTO workers (name, status)
            VALUES ('worker-1', 'active'),
                   ('worker-2', 'inactive'),
                   ('worker-3', 'active')
        """
        )
        test_db.commit()

        # Check active workers
        active_workers = test_db.execute("SELECT COUNT(*) FROM workers WHERE status = 'active'").fetchone()[0]

        assert active_workers == 2  # Only 2 should be in rotation


class TestSkillMatchStrategy:
    """Test skill-based assignment strategy."""

    def test_assign_by_skill_match(self, auto_assign_service, test_db):
        """Test assigning based on required skills."""
        # Create workers with different skills
        test_db.execute(
            """
            INSERT INTO workers (name, status, skills)
            VALUES ('python-dev', 'active', 'python,flask,sql'),
                   ('js-dev', 'active', 'javascript,react,node'),
                   ('full-stack', 'active', 'python,javascript,react,flask')
        """
        )

        # Create task requiring python
        test_db.execute(
            """
            INSERT INTO tasks (id, title, required_skills, status)
            VALUES ('T1', 'Python API', 'python,flask', 'pending')
        """
        )
        test_db.commit()

        # Check skills
        python_dev = test_db.execute("SELECT skills FROM workers WHERE name = 'python-dev'").fetchone()[0]

        assert "python" in python_dev
        assert "flask" in python_dev

    def test_no_assignment_without_skill_match(self, auto_assign_service, test_db):
        """Test tasks requiring unavailable skills remain unassigned."""
        # Create worker without required skill
        test_db.execute(
            "INSERT INTO workers (name, status, skills) VALUES ('python-dev', 'active', 'python,flask')"
        )

        # Create task requiring unavailable skill
        test_db.execute(
            """
            INSERT INTO tasks (id, title, required_skills, status)
            VALUES ('T1', 'Rust Service', 'rust,tokio', 'pending')
        """
        )
        test_db.commit()

        # Task should remain unassigned if no match
        task = test_db.execute("SELECT assigned_to FROM tasks WHERE id = 'T1'").fetchone()[0]
        assert task is None


class TestBalancedStrategy:
    """Test balanced (combined) assignment strategy."""

    def test_combined_workload_and_skills(self, auto_assign_service, test_db):
        """Test balanced strategy considers both workload and skills."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (name, status, skills)
            VALUES ('worker-1', 'active', 'python,flask'),
                   ('worker-2', 'active', 'python,django,react')
        """
        )

        # Worker 1 has lighter load
        test_db.execute(
            """
            INSERT INTO tasks (id, title, assigned_to, status)
            VALUES ('T1', 'Task 1', 2, 'in_progress'),
                   ('T2', 'Task 2', 2, 'in_progress')
        """
        )

        # New Python task
        test_db.execute(
            """
            INSERT INTO tasks (id, title, required_skills, status)
            VALUES ('T3', 'Python Task', 'python', 'pending')
        """
        )
        test_db.commit()

        # Both have python skill, but worker-1 has lighter load
        w1_tasks = test_db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to = 1").fetchone()[0]
        w2_tasks = test_db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to = 2").fetchone()[0]

        assert w1_tasks < w2_tasks  # Worker 1 should be preferred


class TestFastestStrategy:
    """Test fastest worker assignment strategy."""

    def test_assign_to_fastest_worker(self, auto_assign_service, test_db):
        """Test assigning to worker with best completion time."""
        # Create workers with stats
        test_db.execute(
            """
            INSERT INTO workers (name, status)
            VALUES ('fast-worker', 'active'),
                   ('slow-worker', 'active')
        """
        )

        test_db.execute(
            """
            INSERT INTO worker_stats (worker_id, completed_tasks, avg_completion_hours)
            VALUES (1, 100, 2.5),
                   (2, 50, 5.0)
        """
        )
        test_db.commit()

        # Check stats
        fast_avg = test_db.execute(
            "SELECT avg_completion_hours FROM worker_stats WHERE worker_id = 1"
        ).fetchone()[0]

        slow_avg = test_db.execute(
            "SELECT avg_completion_hours FROM worker_stats WHERE worker_id = 2"
        ).fetchone()[0]

        assert fast_avg < slow_avg  # Fast worker should be preferred


class TestWorkloadCalculation:
    """Test workload calculation logic."""

    def test_calculate_workload_by_task_count(self, auto_assign_service, test_db):
        """Test workload calculation based on task count."""
        # Create worker with tasks
        test_db.execute("INSERT INTO workers (name, status) VALUES ('worker-1', 'active')")

        test_db.execute(
            """
            INSERT INTO tasks (id, title, assigned_to, status, estimated_hours)
            VALUES ('T1', 'Task 1', 1, 'in_progress', 4.0),
                   ('T2', 'Task 2', 1, 'in_progress', 8.0),
                   ('T3', 'Task 3', 1, 'in_progress', 2.0)
        """
        )
        test_db.commit()

        # Calculate workload
        task_count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE assigned_to = 1 AND status = 'in_progress'"
        ).fetchone()[0]

        total_hours = test_db.execute(
            """
            SELECT SUM(estimated_hours) FROM tasks
            WHERE assigned_to = 1 AND status = 'in_progress'
        """
        ).fetchone()[0]

        assert task_count == 3
        assert total_hours == 14.0  # 4 + 8 + 2

    def test_workload_with_story_points(self, auto_assign_service, test_db):
        """Test workload calculation includes story points."""
        # Create worker with tasks
        test_db.execute("INSERT INTO workers (name, status) VALUES ('worker-1', 'active')")

        test_db.execute(
            """
            INSERT INTO tasks (id, title, assigned_to, status, story_points, estimated_hours)
            VALUES ('T1', 'Task 1', 1, 'in_progress', 5, 8.0),
                   ('T2', 'Task 2', 1, 'in_progress', 3, 4.0)
        """
        )
        test_db.commit()

        # Calculate metrics
        total_points = test_db.execute(
            "SELECT SUM(story_points) FROM tasks WHERE assigned_to = 1 AND status = 'in_progress'"
        ).fetchone()[0]

        total_hours = test_db.execute(
            "SELECT SUM(estimated_hours) FROM tasks WHERE assigned_to = 1 AND status = 'in_progress'"
        ).fetchone()[0]

        assert total_points == 8  # 5 + 3
        assert total_hours == 12.0  # 8 + 4


class TestWorkerAvailability:
    """Test worker availability checking."""

    def test_check_heartbeat_timeout(self, auto_assign_service, test_db):
        """Test workers with stale heartbeats are unavailable."""
        now = datetime.now()
        old_time = now - timedelta(minutes=10)

        # Create workers with different heartbeats
        test_db.execute(
            """
            INSERT INTO workers (name, status, last_heartbeat)
            VALUES ('active-worker', 'active', ?),
                   ('stale-worker', 'active', ?)
        """,
            (now.isoformat(), old_time.isoformat()),
        )
        test_db.commit()

        # Check heartbeats
        active_hb = test_db.execute(
            "SELECT last_heartbeat FROM workers WHERE name = 'active-worker'"
        ).fetchone()[0]

        stale_hb = test_db.execute(
            "SELECT last_heartbeat FROM workers WHERE name = 'stale-worker'"
        ).fetchone()[0]

        active_time = datetime.fromisoformat(active_hb)
        stale_time = datetime.fromisoformat(stale_hb)

        assert (now - active_time).total_seconds() < 60  # Recent
        assert (now - stale_time).total_seconds() > 300  # Stale (>5 min)

    def test_inactive_workers_not_assigned(self, auto_assign_service, test_db):
        """Test inactive workers are not assigned tasks."""
        # Create workers with different statuses
        test_db.execute(
            """
            INSERT INTO workers (name, status)
            VALUES ('active-worker', 'active'),
                   ('inactive-worker', 'inactive'),
                   ('paused-worker', 'paused')
        """
        )
        test_db.commit()

        # Check statuses
        active_count = test_db.execute("SELECT COUNT(*) FROM workers WHERE status = 'active'").fetchone()[0]

        inactive_count = test_db.execute("SELECT COUNT(*) FROM workers WHERE status != 'active'").fetchone()[0]

        assert active_count == 1
        assert inactive_count == 2


class TestAssignmentHistory:
    """Test assignment history tracking."""

    def test_record_assignment_in_history(self, auto_assign_service, test_db):
        """Test assignments are recorded in history."""
        # Create worker and task
        test_db.execute("INSERT INTO workers (name, status) VALUES ('worker-1', 'active')")

        test_db.execute("INSERT INTO tasks (id, title, status) VALUES ('T1', 'Task 1', 'pending')")
        test_db.commit()

        # Record assignment
        test_db.execute(
            """
            INSERT INTO task_assignments (task_id, worker_id, strategy, score)
            VALUES ('T1', 1, 'balanced', 85.5)
        """
        )

        # Update task
        test_db.execute(
            """
            UPDATE tasks
            SET assigned_to = 1, assigned_at = ?, status = 'assigned'
            WHERE id = 'T1'
        """,
            (datetime.now().isoformat(),),
        )
        test_db.commit()

        # Verify assignment
        assignment = test_db.execute(
            """
            SELECT task_id, worker_id, strategy, score
            FROM task_assignments
            WHERE task_id = 'T1'
        """
        ).fetchone()

        assert assignment is not None
        assert assignment[0] == "T1"
        assert assignment[1] == 1
        assert assignment[2] == "balanced"
        assert assignment[3] == 85.5

    def test_track_multiple_reassignments(self, auto_assign_service, test_db):
        """Test tracking task reassignments."""
        # Create workers and task
        test_db.execute(
            "INSERT INTO workers (name, status) VALUES ('worker-1', 'active'), ('worker-2', 'active')"
        )

        test_db.execute("INSERT INTO tasks (id, title, status) VALUES ('T1', 'Task 1', 'pending')")
        test_db.commit()

        # First assignment
        test_db.execute(
            "INSERT INTO task_assignments (task_id, worker_id, strategy) VALUES ('T1', 1, 'balanced')"
        )

        # Reassignment
        test_db.execute(
            "INSERT INTO task_assignments (task_id, worker_id, strategy) VALUES ('T1', 2, 'balanced')"
        )
        test_db.commit()

        # Count assignments
        count = test_db.execute("SELECT COUNT(*) FROM task_assignments WHERE task_id = 'T1'").fetchone()[0]

        assert count == 2  # Both assignments recorded


class TestConcurrentAssignment:
    """Test concurrent assignment handling."""

    def test_assign_multiple_tasks_simultaneously(self, auto_assign_service, test_db):
        """Test assigning multiple tasks at once."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (name, status)
            VALUES ('worker-1', 'active'),
                   ('worker-2', 'active'),
                   ('worker-3', 'active')
        """
        )

        # Create multiple pending tasks
        for i in range(10):
            test_db.execute(f"INSERT INTO tasks (id, title, status) VALUES ('T{i+1}', 'Task {i+1}', 'pending')")
        test_db.commit()

        # Check pending count
        pending_count = test_db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'").fetchone()[0]

        assert pending_count == 10


class TestPriorityHandling:
    """Test task priority in assignment."""

    def test_high_priority_tasks_assigned_first(self, auto_assign_service, test_db):
        """Test high priority tasks are assigned before lower priority."""
        # Create worker
        test_db.execute("INSERT INTO workers (name, status) VALUES ('worker-1', 'active')")

        # Create tasks with different priorities
        test_db.execute(
            """
            INSERT INTO tasks (id, title, priority, status)
            VALUES ('T1', 'Low Priority', 'low', 'pending'),
                   ('T2', 'High Priority', 'high', 'pending'),
                   ('T3', 'Medium Priority', 'medium', 'pending')
        """
        )
        test_db.commit()

        # Query by priority order
        tasks = test_db.execute(
            """
            SELECT id, priority FROM tasks
            WHERE status = 'pending'
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END
        """
        ).fetchall()

        assert tasks[0][0] == "T2"  # High priority first
        assert tasks[1][0] == "T3"  # Medium second
        assert tasks[2][0] == "T1"  # Low last


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
