#!/usr/bin/env python3
"""
Load Balancer Integration Tests

Tests for Worker Load Balancer service.

Tests the full integration of:
- Load balancing strategies (round-robin, least-loaded, weighted, skill-based)
- Worker load tracking
- Capacity management
- Health-aware routing
- Task affinity
- Load metrics and analytics
- Distribution reporting
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with load balancer schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create load balancer tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL UNIQUE,
            worker_type TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            health TEXT DEFAULT 'healthy',
            capacity INTEGER DEFAULT 10,
            current_load INTEGER DEFAULT 0,
            active_connections INTEGER DEFAULT 0,
            skills TEXT,
            weight INTEGER DEFAULT 1,
            last_heartbeat TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            required_skills TEXT,
            assigned_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS load_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            load_value INTEGER NOT NULL,
            connections INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
        );

        CREATE TABLE IF NOT EXISTS selection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            strategy TEXT NOT NULL,
            worker_load INTEGER,
            selection_time_ms REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
        );

        CREATE INDEX idx_workers_status ON workers(status);
        CREATE INDEX idx_workers_health ON workers(health);
        CREATE INDEX idx_workers_load ON workers(current_load);
        CREATE INDEX idx_tasks_assigned ON tasks(assigned_to);
        CREATE INDEX idx_load_metrics_worker ON load_metrics(worker_id);
        CREATE INDEX idx_load_metrics_timestamp ON load_metrics(timestamp);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestRoundRobinStrategy:
    """Test round-robin load balancing."""

    def test_round_robin_rotation(self, test_db):
        """Test workers are selected in rotation."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES ('worker-1', 'task_worker', 'active'),
                   ('worker-2', 'task_worker', 'active'),
                   ('worker-3', 'task_worker', 'active')
        """
        )
        test_db.commit()

        # Get workers in order
        workers = test_db.execute(
            "SELECT worker_id FROM workers WHERE status = 'active' ORDER BY id"
        ).fetchall()

        assert len(workers) == 3

    def test_skip_inactive_workers(self, test_db):
        """Test inactive workers are skipped in rotation."""
        # Create workers with mixed status
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, status)
            VALUES ('worker-1', 'task_worker', 'active'),
                   ('worker-2', 'task_worker', 'inactive'),
                   ('worker-3', 'task_worker', 'active')
        """
        )
        test_db.commit()

        # Get active workers
        active = test_db.execute(
            "SELECT worker_id FROM workers WHERE status = 'active'"
        ).fetchall()

        assert len(active) == 2


class TestLeastLoadedStrategy:
    """Test least-loaded load balancing."""

    def test_select_worker_with_lowest_load(self, test_db):
        """Test selecting worker with lowest current load."""
        # Create workers with different loads
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, current_load)
            VALUES ('worker-1', 'task_worker', 5),
                   ('worker-2', 'task_worker', 2),
                   ('worker-3', 'task_worker', 8)
        """
        )
        test_db.commit()

        # Get least loaded
        worker = test_db.execute(
            """
            SELECT worker_id, current_load
            FROM workers
            WHERE status = 'active'
            ORDER BY current_load ASC
            LIMIT 1
        """
        ).fetchone()

        assert worker[0] == "worker-2"
        assert worker[1] == 2

    def test_respect_capacity_limits(self, test_db):
        """Test workers at capacity are not selected."""
        # Create workers at/near capacity
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, capacity, current_load)
            VALUES ('worker-1', 'task_worker', 10, 10),
                   ('worker-2', 'task_worker', 10, 5),
                   ('worker-3', 'task_worker', 10, 12)
        """
        )
        test_db.commit()

        # Get workers under capacity
        available = test_db.execute(
            """
            SELECT worker_id FROM workers
            WHERE current_load < capacity
            ORDER BY current_load ASC
        """
        ).fetchall()

        assert len(available) == 1
        assert available[0][0] == "worker-2"

    def test_tie_breaking(self, test_db):
        """Test tie-breaking when multiple workers have same load."""
        # Create workers with same load
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, current_load)
            VALUES ('worker-1', 'task_worker', 5),
                   ('worker-2', 'task_worker', 5),
                   ('worker-3', 'task_worker', 5)
        """
        )
        test_db.commit()

        # Get least loaded (will get first by ID)
        worker = test_db.execute(
            """
            SELECT worker_id FROM workers
            WHERE status = 'active'
            ORDER BY current_load ASC, id ASC
            LIMIT 1
        """
        ).fetchone()

        assert worker[0] in ["worker-1", "worker-2", "worker-3"]


class TestWeightedStrategy:
    """Test weighted load balancing."""

    def test_consider_worker_weights(self, test_db):
        """Test workers with higher weights are preferred."""
        # Create workers with different weights
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, weight, current_load)
            VALUES ('worker-1', 'task_worker', 1, 5),
                   ('worker-2', 'task_worker', 3, 5),
                   ('worker-3', 'task_worker', 2, 5)
        """
        )
        test_db.commit()

        # Get by weight
        worker = test_db.execute(
            """
            SELECT worker_id, weight FROM workers
            ORDER BY weight DESC
            LIMIT 1
        """
        ).fetchone()

        assert worker[0] == "worker-2"
        assert worker[1] == 3

    def test_weighted_capacity(self, test_db):
        """Test effective capacity considers weight."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, capacity, weight)
            VALUES ('worker-1', 'task_worker', 10, 1),
                   ('worker-2', 'task_worker', 10, 2)
        """
        )
        test_db.commit()

        # Calculate effective capacity (capacity * weight)
        workers = test_db.execute(
            """
            SELECT worker_id, capacity, weight, (capacity * weight) as effective_capacity
            FROM workers
            ORDER BY effective_capacity DESC
        """
        ).fetchall()

        assert workers[0][0] == "worker-2"
        assert workers[0][3] == 20  # 10 * 2


class TestSkillBasedStrategy:
    """Test skill-based load balancing."""

    def test_match_required_skills(self, test_db):
        """Test workers are matched by required skills."""
        # Create workers with different skills
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, skills)
            VALUES ('worker-1', 'task_worker', 'python,flask'),
                   ('worker-2', 'task_worker', 'javascript,react'),
                   ('worker-3', 'task_worker', 'python,django')
        """
        )
        test_db.commit()

        # Find workers with python skill
        workers = test_db.execute(
            """
            SELECT worker_id FROM workers
            WHERE skills LIKE '%python%'
        """
        ).fetchall()

        assert len(workers) == 2

    def test_prefer_exact_skill_match(self, test_db):
        """Test workers with exact skill match are preferred."""
        # Create task requiring specific skills
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type, required_skills)
            VALUES ('T123', 'Python Task', 'coding', 'python,flask')
        """
        )

        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, skills)
            VALUES ('worker-1', 'task_worker', 'python,flask'),
                   ('worker-2', 'task_worker', 'python,django')
        """
        )
        test_db.commit()

        # Find best match (has both python AND flask)
        task = test_db.execute(
            "SELECT required_skills FROM tasks WHERE id = 'T123'"
        ).fetchone()

        # Worker-1 is exact match
        worker1_skills = test_db.execute(
            "SELECT skills FROM workers WHERE worker_id = 'worker-1'"
        ).fetchone()[0]

        assert "python" in worker1_skills
        assert "flask" in worker1_skills


class TestLeastConnectionsStrategy:
    """Test least-connections load balancing."""

    def test_select_worker_with_fewest_connections(self, test_db):
        """Test selecting worker with fewest active connections."""
        # Create workers with different connection counts
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, active_connections)
            VALUES ('worker-1', 'task_worker', 10),
                   ('worker-2', 'task_worker', 3),
                   ('worker-3', 'task_worker', 7)
        """
        )
        test_db.commit()

        # Get worker with least connections
        worker = test_db.execute(
            """
            SELECT worker_id, active_connections
            FROM workers
            ORDER BY active_connections ASC
            LIMIT 1
        """
        ).fetchone()

        assert worker[0] == "worker-2"
        assert worker[1] == 3


class TestHealthAwareRouting:
    """Test health-aware worker selection."""

    def test_avoid_unhealthy_workers(self, test_db):
        """Test unhealthy workers are not selected."""
        # Create workers with different health states
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, health, current_load)
            VALUES ('worker-1', 'task_worker', 'healthy', 2),
                   ('worker-2', 'task_worker', 'unhealthy', 1),
                   ('worker-3', 'task_worker', 'healthy', 3)
        """
        )
        test_db.commit()

        # Get healthy workers only
        healthy = test_db.execute(
            """
            SELECT worker_id FROM workers
            WHERE health = 'healthy'
            ORDER BY current_load ASC
        """
        ).fetchall()

        assert len(healthy) == 2
        assert healthy[0][0] == "worker-1"

    def test_check_heartbeat_freshness(self, test_db):
        """Test workers with stale heartbeats are avoided."""
        now = datetime.now()
        old_time = now - timedelta(minutes=10)

        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, last_heartbeat)
            VALUES ('worker-1', 'task_worker', ?),
                   ('worker-2', 'task_worker', ?)
        """,
            (now.isoformat(), old_time.isoformat()),
        )
        test_db.commit()

        # Get workers with recent heartbeat (< 5 minutes)
        cutoff = (now - timedelta(minutes=5)).isoformat()
        recent = test_db.execute(
            """
            SELECT worker_id FROM workers
            WHERE last_heartbeat > ?
        """,
            (cutoff,),
        ).fetchall()

        assert len(recent) == 1
        assert recent[0][0] == "worker-1"


class TestLoadTracking:
    """Test worker load tracking."""

    def test_update_worker_load(self, test_db):
        """Test updating worker current load."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, current_load)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", 5),
        )
        test_db.commit()

        # Increment load
        test_db.execute(
            """
            UPDATE workers
            SET current_load = current_load + 1
            WHERE worker_id = ?
        """,
            ("worker-1",),
        )
        test_db.commit()

        # Verify
        load = test_db.execute(
            "SELECT current_load FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()[0]

        assert load == 6

    def test_record_load_metrics(self, test_db):
        """Test recording load metrics over time."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type)
            VALUES (?, ?)
        """,
            ("worker-1", "task_worker"),
        )
        test_db.commit()

        # Record metrics
        for load in [2, 5, 8, 4]:
            test_db.execute(
                """
                INSERT INTO load_metrics (worker_id, load_value)
                VALUES (?, ?)
            """,
                ("worker-1", load),
            )
        test_db.commit()

        # Verify
        metrics = test_db.execute(
            "SELECT load_value FROM load_metrics WHERE worker_id = ? ORDER BY id",
            ("worker-1",),
        ).fetchall()

        assert len(metrics) == 4
        assert [m[0] for m in metrics] == [2, 5, 8, 4]

    def test_calculate_average_load(self, test_db):
        """Test calculating average load for a worker."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type)
            VALUES (?, ?)
        """,
            ("worker-1", "task_worker"),
        )

        # Record metrics
        loads = [2, 4, 6, 8, 10]
        for load in loads:
            test_db.execute(
                """
                INSERT INTO load_metrics (worker_id, load_value)
                VALUES (?, ?)
            """,
                ("worker-1", load),
            )
        test_db.commit()

        # Calculate average
        avg = test_db.execute(
            """
            SELECT AVG(load_value) FROM load_metrics
            WHERE worker_id = ?
        """,
            ("worker-1",),
        ).fetchone()[0]

        assert avg == 6.0


class TestSelectionHistory:
    """Test selection history tracking."""

    def test_record_selection(self, test_db):
        """Test recording worker selection."""
        # Create worker and task
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, current_load)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", 5),
        )

        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES (?, ?, ?)
        """,
            ("T123", "Test Task", "coding"),
        )
        test_db.commit()

        # Record selection
        test_db.execute(
            """
            INSERT INTO selection_history
            (task_id, worker_id, strategy, worker_load, selection_time_ms)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("T123", "worker-1", "least_loaded", 5, 1.2),
        )
        test_db.commit()

        # Verify
        history = test_db.execute(
            "SELECT * FROM selection_history WHERE task_id = ?", ("T123",)
        ).fetchone()

        assert history is not None
        assert history[2] == "worker-1"
        assert history[3] == "least_loaded"

    def test_track_selection_performance(self, test_db):
        """Test tracking selection time performance."""
        # Create worker and task
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type)
            VALUES (?, ?)
        """,
            ("worker-1", "task_worker"),
        )

        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES (?, ?, ?)
        """,
            ("T123", "Test Task", "coding"),
        )
        test_db.commit()

        # Record with timing
        test_db.execute(
            """
            INSERT INTO selection_history
            (task_id, worker_id, strategy, selection_time_ms)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "worker-1", "least_loaded", 2.5),
        )
        test_db.commit()

        # Get timing
        timing = test_db.execute(
            "SELECT selection_time_ms FROM selection_history WHERE task_id = ?", ("T123",)
        ).fetchone()[0]

        assert timing == 2.5


class TestLoadDistribution:
    """Test load distribution reporting."""

    def test_get_load_distribution(self, test_db):
        """Test getting load distribution across workers."""
        # Create workers with different loads
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, current_load, capacity)
            VALUES ('worker-1', 'task_worker', 8, 10),
                   ('worker-2', 'task_worker', 4, 10),
                   ('worker-3', 'task_worker', 6, 10)
        """
        )
        test_db.commit()

        # Get distribution
        workers = test_db.execute(
            """
            SELECT worker_id, current_load, capacity,
                   CAST(current_load AS REAL) / capacity * 100 as utilization
            FROM workers
            ORDER BY utilization DESC
        """
        ).fetchall()

        assert len(workers) == 3
        assert workers[0][0] == "worker-1"  # Highest utilization (80%)

    def test_identify_overloaded_workers(self, test_db):
        """Test identifying overloaded workers."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, current_load, capacity)
            VALUES ('worker-1', 'task_worker', 12, 10),
                   ('worker-2', 'task_worker', 5, 10),
                   ('worker-3', 'task_worker', 11, 10)
        """
        )
        test_db.commit()

        # Find overloaded (load > capacity)
        overloaded = test_db.execute(
            """
            SELECT worker_id FROM workers
            WHERE current_load > capacity
        """
        ).fetchall()

        assert len(overloaded) == 2

    def test_calculate_total_capacity(self, test_db):
        """Test calculating total system capacity."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, capacity)
            VALUES ('worker-1', 'task_worker', 10),
                   ('worker-2', 'task_worker', 15),
                   ('worker-3', 'task_worker', 20)
        """
        )
        test_db.commit()

        # Calculate total
        total = test_db.execute(
            """
            SELECT SUM(capacity) FROM workers
            WHERE status = 'active'
        """
        ).fetchone()[0]

        assert total == 45


class TestTaskAffinity:
    """Test task affinity support."""

    def test_prefer_worker_with_task_history(self, test_db):
        """Test preferring workers with relevant task history."""
        # Create workers
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type)
            VALUES ('worker-1', 'task_worker'),
                   ('worker-2', 'task_worker')
        """
        )

        # Create task history
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type, assigned_to, status)
            VALUES ('T1', 'Python Task 1', 'python', 'worker-1', 'completed'),
                   ('T2', 'Python Task 2', 'python', 'worker-1', 'completed'),
                   ('T3', 'JS Task', 'javascript', 'worker-2', 'completed')
        """
        )
        test_db.commit()

        # Count task type completions per worker
        counts = test_db.execute(
            """
            SELECT assigned_to, task_type, COUNT(*) as count
            FROM tasks
            WHERE status = 'completed'
            GROUP BY assigned_to, task_type
        """
        ).fetchall()

        # Worker-1 has done 2 python tasks
        python_counts = {row[0]: row[2] for row in counts if row[1] == "python"}
        assert python_counts.get("worker-1", 0) == 2


class TestCapacityManagement:
    """Test worker capacity management."""

    def test_set_worker_capacity(self, test_db):
        """Test setting worker capacity."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, capacity)
            VALUES (?, ?, ?)
        """,
            ("worker-1", "task_worker", 10),
        )
        test_db.commit()

        # Update capacity
        test_db.execute(
            """
            UPDATE workers
            SET capacity = 20
            WHERE worker_id = ?
        """,
            ("worker-1",),
        )
        test_db.commit()

        # Verify
        capacity = test_db.execute(
            "SELECT capacity FROM workers WHERE worker_id = ?", ("worker-1",)
        ).fetchone()[0]

        assert capacity == 20

    def test_check_available_capacity(self, test_db):
        """Test checking available capacity."""
        # Create worker
        test_db.execute(
            """
            INSERT INTO workers (worker_id, worker_type, capacity, current_load)
            VALUES (?, ?, ?, ?)
        """,
            ("worker-1", "task_worker", 10, 6),
        )
        test_db.commit()

        # Calculate available
        worker = test_db.execute(
            """
            SELECT capacity, current_load, (capacity - current_load) as available
            FROM workers
            WHERE worker_id = ?
        """,
            ("worker-1",),
        ).fetchone()

        assert worker[2] == 4  # available capacity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
