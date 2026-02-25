"""
Tests for Worker Load Balancer Service

Tests the load balancing functionality including:
- Worker load tracking
- Multiple load balancing strategies
- Load distribution analysis
- Worker configuration
- Task rebalancing
"""

import os
import sqlite3

# Add parent directory to path for imports
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.load_balancer import (
    LoadBalancer,
    LoadBalancingStrategy,
    LoadDistribution,
    WorkerLoad,
    WorkerSelection,
    get_load_balancer,
    init_load_balancer_schema,
    select_worker_for_task,
)


class TestLoadBalancer:
    """Test the LoadBalancer class."""

    @pytest.fixture
    def db_path(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def db_with_schema(self, db_path):
        """Create database with full schema for testing."""
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            -- Workers table
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                worker_type TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                current_task_id INTEGER,
                last_heartbeat TIMESTAMP,
                tasks_completed INTEGER DEFAULT 0,
                tasks_failed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Task queue table
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                name TEXT,
                description TEXT,
                data TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                assigned_worker TEXT,
                retries INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            );

            -- Worker config table
            CREATE TABLE IF NOT EXISTS worker_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(worker_id, key)
            );
            CREATE INDEX IF NOT EXISTS idx_worker_config_worker ON worker_config(worker_id);
        """
        )
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def load_balancer(self, db_with_schema):
        """Create a LoadBalancer instance."""
        return LoadBalancer(db_with_schema)

    @pytest.fixture
    def populated_db(self, db_with_schema):
        """Create database with test workers and tasks."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()

        # Add workers with different statuses
        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES
                ('worker-1', 'node-1', 'general', 'idle', ?),
                ('worker-2', 'node-1', 'general', 'busy', ?),
                ('worker-3', 'node-2', 'shell', 'idle', ?),
                ('worker-4', 'node-2', 'python', 'draining', ?)
        """,
            (now, now, now, now),
        )

        # Add some tasks
        conn.execute(
            """
            INSERT INTO task_queue (task_type, status, assigned_worker, priority)
            VALUES
                ('shell', 'running', 'worker-1', 5),
                ('shell', 'running', 'worker-2', 5),
                ('shell', 'running', 'worker-2', 5),
                ('python', 'pending', 'worker-1', 3),
                ('shell', 'pending', NULL, 5),
                ('python', 'completed', 'worker-1', 5)
        """
        )

        # Set worker capacities
        conn.execute(
            """
            INSERT INTO worker_config (worker_id, key, value)
            VALUES
                ('worker-1', 'capacity', '10'),
                ('worker-2', 'capacity', '5'),
                ('worker-3', 'capacity', '15'),
                ('worker-1', 'weight', '1.5')
        """
        )

        conn.commit()
        conn.close()
        return db_with_schema

    # =========================================================================
    # Worker Load Tests
    # =========================================================================

    def test_get_worker_load(self, populated_db):
        """Test getting load for a single worker."""
        lb = LoadBalancer(populated_db)
        load = lb.get_worker_load("worker-1")

        assert load is not None
        assert load.worker_id == "worker-1"
        assert load.worker_type == "general"
        assert load.node_id == "node-1"
        assert load.current_tasks == 1
        assert load.pending_tasks == 1
        assert load.capacity == 10
        assert load.weight == 1.5
        assert load.is_healthy is True
        assert load.is_draining is False

    def test_get_worker_load_not_found(self, db_with_schema):
        """Test getting load for non-existent worker."""
        lb = LoadBalancer(db_with_schema)
        load = lb.get_worker_load("nonexistent")
        assert load is None

    def test_get_worker_load_draining(self, populated_db):
        """Test that draining workers are identified."""
        lb = LoadBalancer(populated_db)
        load = lb.get_worker_load("worker-4")

        assert load is not None
        assert load.is_draining is True
        assert load.effective_weight == 0.0

    def test_get_all_worker_loads(self, populated_db):
        """Test getting loads for all workers."""
        lb = LoadBalancer(populated_db)
        loads = lb.get_all_worker_loads(include_unhealthy=False)

        # Should exclude draining worker
        assert len(loads) == 3
        worker_ids = [l.worker_id for l in loads]
        assert "worker-4" not in worker_ids

    def test_get_all_worker_loads_include_unhealthy(self, populated_db):
        """Test getting all workers including unhealthy ones."""
        lb = LoadBalancer(populated_db)
        loads = lb.get_all_worker_loads(include_unhealthy=True)

        assert len(loads) == 4

    def test_get_all_worker_loads_by_type(self, populated_db):
        """Test filtering workers by type."""
        lb = LoadBalancer(populated_db)
        loads = lb.get_all_worker_loads(worker_type="general")

        assert len(loads) == 2
        for load in loads:
            assert load.worker_type == "general"

    # =========================================================================
    # Load Balancing Strategy Tests
    # =========================================================================

    def test_select_worker_round_robin(self, populated_db):
        """Test round-robin worker selection."""
        lb = LoadBalancer(populated_db)

        # Make multiple selections
        selections = []
        for _ in range(5):
            selection = lb.select_worker(strategy=LoadBalancingStrategy.ROUND_ROBIN)
            if selection.worker_id:
                selections.append(selection.worker_id)

        # Should rotate through workers
        assert len(selections) == 5
        assert len(set(selections)) > 1  # Not all same worker

    def test_select_worker_least_loaded(self, populated_db):
        """Test least-loaded worker selection."""
        lb = LoadBalancer(populated_db)
        selection = lb.select_worker(strategy=LoadBalancingStrategy.LEAST_LOADED)

        assert selection.worker_id is not None
        # worker-3 should be selected (0 tasks, highest capacity)
        assert selection.worker_id == "worker-3"
        assert selection.strategy_used == "least_loaded"
        assert selection.load_before == 0.0

    def test_select_worker_weighted(self, populated_db):
        """Test weighted worker selection."""
        lb = LoadBalancer(populated_db)
        selection = lb.select_worker(strategy=LoadBalancingStrategy.WEIGHTED)

        assert selection.worker_id is not None
        assert selection.strategy_used == "weighted"

    def test_select_worker_adaptive(self, populated_db):
        """Test adaptive worker selection."""
        lb = LoadBalancer(populated_db)
        selection = lb.select_worker(task_type="shell", strategy=LoadBalancingStrategy.ADAPTIVE)

        assert selection.worker_id is not None
        assert selection.strategy_used == "adaptive"

    def test_select_worker_excludes_draining(self, populated_db):
        """Test that draining workers are excluded."""
        lb = LoadBalancer(populated_db)
        selection = lb.select_worker(worker_type="python")

        # worker-4 is python type but draining, so should not be selected
        # No other python workers available
        assert selection.worker_id is None or selection.worker_id != "worker-4"

    def test_select_worker_exclude_list(self, populated_db):
        """Test excluding specific workers."""
        lb = LoadBalancer(populated_db)
        selection = lb.select_worker(
            strategy=LoadBalancingStrategy.LEAST_LOADED, exclude_workers=["worker-3"]
        )

        assert selection.worker_id != "worker-3"

    def test_select_worker_no_capacity(self, db_with_schema):
        """Test selection when no workers have capacity."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()

        # Add a worker with full capacity
        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES ('worker-full', 'node-1', 'general', 'idle', ?)
        """,
            (now,),
        )
        conn.execute(
            """
            INSERT INTO worker_config (worker_id, key, value)
            VALUES ('worker-full', 'capacity', '1')
        """
        )
        # Add a running task to fill capacity
        conn.execute(
            """
            INSERT INTO task_queue (task_type, status, assigned_worker)
            VALUES ('shell', 'running', 'worker-full')
        """
        )
        conn.commit()
        conn.close()

        lb = LoadBalancer(db_with_schema)
        selection = lb.select_worker()

        assert selection.worker_id is None
        assert "capacity" in selection.reason.lower()

    def test_select_worker_alternatives(self, populated_db):
        """Test that alternatives are provided."""
        lb = LoadBalancer(populated_db)
        selection = lb.select_worker(strategy=LoadBalancingStrategy.LEAST_LOADED)

        assert selection.worker_id is not None
        assert len(selection.alternatives) > 0
        # Alternatives should be sorted by load
        if len(selection.alternatives) > 1:
            assert (
                selection.alternatives[0]["load_percentage"]
                <= selection.alternatives[1]["load_percentage"]
            )

    # =========================================================================
    # Load Distribution Tests
    # =========================================================================

    def test_get_load_distribution(self, populated_db):
        """Test getting load distribution across all workers."""
        lb = LoadBalancer(populated_db)
        dist = lb.get_load_distribution()

        assert dist.total_workers == 4
        assert dist.healthy_workers >= 3
        assert dist.total_capacity > 0
        assert dist.total_current_tasks > 0
        assert 0 <= dist.avg_load_percentage <= 100

    def test_load_distribution_by_node(self, populated_db):
        """Test load distribution grouped by node."""
        lb = LoadBalancer(populated_db)
        dist = lb.get_load_distribution()

        assert "node-1" in dist.by_node
        assert "node-2" in dist.by_node
        assert dist.by_node["node-1"]["workers"] == 2
        assert dist.by_node["node-2"]["workers"] == 2

    def test_load_distribution_by_type(self, populated_db):
        """Test load distribution grouped by worker type."""
        lb = LoadBalancer(populated_db)
        dist = lb.get_load_distribution()

        assert "general" in dist.by_type
        assert "shell" in dist.by_type
        assert dist.by_type["general"]["workers"] == 2

    def test_load_distribution_imbalance(self, db_with_schema):
        """Test imbalance score calculation."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()

        # Create highly imbalanced scenario
        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES
                ('w1', 'n1', 'general', 'idle', ?),
                ('w2', 'n1', 'general', 'idle', ?)
        """,
            (now, now),
        )

        conn.execute(
            """
            INSERT INTO worker_config (worker_id, key, value)
            VALUES
                ('w1', 'capacity', '10'),
                ('w2', 'capacity', '10')
        """
        )

        # Give w1 10 tasks (100% load) and w2 0 tasks (0% load)
        for i in range(10):
            conn.execute(
                """
                INSERT INTO task_queue (task_type, status, assigned_worker)
                VALUES ('shell', 'running', 'w1')
            """
            )

        conn.commit()
        conn.close()

        lb = LoadBalancer(db_with_schema)
        dist = lb.get_load_distribution()

        # High imbalance expected (one worker at 100%, other at 0%)
        assert dist.imbalance_score > 30

    def test_load_distribution_recommendations(self, db_with_schema):
        """Test that recommendations are generated for imbalanced loads."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()

        # Create scenario with overloaded worker
        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES ('overloaded', 'n1', 'general', 'idle', ?)
        """,
            (now,),
        )
        conn.execute(
            """
            INSERT INTO worker_config (worker_id, key, value)
            VALUES ('overloaded', 'capacity', '5')
        """
        )
        for i in range(5):
            conn.execute(
                """
                INSERT INTO task_queue (task_type, status, assigned_worker)
                VALUES ('shell', 'running', 'overloaded')
            """
            )
        conn.commit()
        conn.close()

        lb = LoadBalancer(db_with_schema)
        dist = lb.get_load_distribution()

        assert len(dist.recommendations) > 0

    # =========================================================================
    # Worker Configuration Tests
    # =========================================================================

    def test_set_worker_capacity(self, db_with_schema):
        """Test setting worker capacity."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES ('test-worker', 'node-1', 'general', 'idle', ?)
        """,
            (now,),
        )
        conn.commit()
        conn.close()

        lb = LoadBalancer(db_with_schema)
        success = lb.set_worker_capacity("test-worker", 20)

        assert success is True

        load = lb.get_worker_load("test-worker")
        assert load.capacity == 20

    def test_set_worker_weight(self, db_with_schema):
        """Test setting worker weight."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES ('test-worker', 'node-1', 'general', 'idle', ?)
        """,
            (now,),
        )
        conn.commit()
        conn.close()

        lb = LoadBalancer(db_with_schema)
        success = lb.set_worker_weight("test-worker", 2.5)

        assert success is True

        load = lb.get_worker_load("test-worker")
        assert load.weight == 2.5

    def test_drain_worker(self, populated_db):
        """Test draining a worker."""
        lb = LoadBalancer(populated_db)
        success = lb.drain_worker("worker-1")

        assert success is True

        load = lb.get_worker_load("worker-1")
        assert load.is_draining is True

    def test_undrain_worker(self, populated_db):
        """Test undraining a worker."""
        lb = LoadBalancer(populated_db)

        # First drain the worker
        lb.drain_worker("worker-1")

        # Then undrain
        success = lb.undrain_worker("worker-1")
        assert success is True

        load = lb.get_worker_load("worker-1")
        assert load.is_draining is False

    # =========================================================================
    # Rebalancing Tests
    # =========================================================================

    def test_suggest_rebalance(self, db_with_schema):
        """Test rebalance suggestions."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()

        # Create imbalanced workers
        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES
                ('overloaded', 'n1', 'general', 'idle', ?),
                ('underloaded', 'n1', 'general', 'idle', ?)
        """,
            (now, now),
        )

        conn.execute(
            """
            INSERT INTO worker_config (worker_id, key, value)
            VALUES
                ('overloaded', 'capacity', '5'),
                ('underloaded', 'capacity', '10')
        """
        )

        # Give overloaded worker 5 running + 3 pending tasks
        for i in range(5):
            conn.execute(
                """
                INSERT INTO task_queue (task_type, status, assigned_worker, priority)
                VALUES ('shell', 'running', 'overloaded', 5)
            """
            )
        for i in range(3):
            conn.execute(
                """
                INSERT INTO task_queue (task_type, status, assigned_worker, priority)
                VALUES ('shell', 'pending', 'overloaded', 5)
            """
            )

        conn.commit()
        conn.close()

        lb = LoadBalancer(db_with_schema)
        suggestions = lb.suggest_rebalance()

        assert len(suggestions) > 0
        for suggestion in suggestions:
            assert "task_id" in suggestion
            assert suggestion["from_worker"] == "overloaded"
            assert suggestion["to_worker"] == "underloaded"

    def test_suggest_rebalance_balanced(self, populated_db):
        """Test that no suggestions when balanced."""
        # Default populated_db is reasonably balanced
        lb = LoadBalancer(populated_db)

        # First check distribution
        dist = lb.get_load_distribution()
        if dist.imbalance_score < 20:
            suggestions = lb.suggest_rebalance()
            # Should have few or no suggestions
            assert len(suggestions) <= 2

    def test_execute_rebalance(self, db_with_schema):
        """Test executing a rebalance move."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()

        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES
                ('from-worker', 'n1', 'general', 'idle', ?),
                ('to-worker', 'n1', 'general', 'idle', ?)
        """,
            (now, now),
        )

        # Add a pending task
        conn.execute(
            """
            INSERT INTO task_queue (task_type, status, assigned_worker)
            VALUES ('shell', 'pending', 'from-worker')
        """
        )

        conn.commit()
        task_id = conn.execute("SELECT id FROM task_queue LIMIT 1").fetchone()[0]
        conn.close()

        lb = LoadBalancer(db_with_schema)
        success = lb.execute_rebalance(task_id, "to-worker")

        assert success is True

        # Verify the task was moved
        conn = sqlite3.connect(db_with_schema)
        task = conn.execute(
            "SELECT assigned_worker FROM task_queue WHERE id = ?", (task_id,)
        ).fetchone()
        conn.close()

        assert task[0] == "to-worker"

    def test_execute_rebalance_running_task(self, db_with_schema):
        """Test that running tasks cannot be rebalanced."""
        conn = sqlite3.connect(db_with_schema)
        now = datetime.now().isoformat()

        conn.execute(
            """
            INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
            VALUES ('w1', 'n1', 'general', 'idle', ?)
        """,
            (now,),
        )

        # Add a running task
        conn.execute(
            """
            INSERT INTO task_queue (task_type, status, assigned_worker)
            VALUES ('shell', 'running', 'w1')
        """
        )

        conn.commit()
        task_id = conn.execute("SELECT id FROM task_queue LIMIT 1").fetchone()[0]
        conn.close()

        lb = LoadBalancer(db_with_schema)
        success = lb.execute_rebalance(task_id, "w2")

        assert success is False

    # =========================================================================
    # WorkerLoad Dataclass Tests
    # =========================================================================

    def test_worker_load_percentage(self):
        """Test load percentage calculation."""
        load = WorkerLoad(
            worker_id="test",
            worker_type="general",
            node_id="node-1",
            status="idle",
            current_tasks=3,
            capacity=10,
        )

        assert load.load_percentage == 30.0

    def test_worker_load_available_capacity(self):
        """Test available capacity calculation."""
        load = WorkerLoad(
            worker_id="test",
            worker_type="general",
            node_id="node-1",
            status="idle",
            current_tasks=3,
            capacity=10,
        )

        assert load.available_capacity == 7

    def test_worker_load_effective_weight(self):
        """Test effective weight calculation."""
        load = WorkerLoad(
            worker_id="test",
            worker_type="general",
            node_id="node-1",
            status="idle",
            current_tasks=0,
            capacity=10,
            weight=2.0,
            success_rate=100.0,
            is_healthy=True,
            is_draining=False,
        )

        # With 0% load and 100% success rate: weight * 1.0 * 1.0 = 2.0
        assert load.effective_weight == 2.0

    def test_worker_load_effective_weight_unhealthy(self):
        """Test effective weight is 0 for unhealthy workers."""
        load = WorkerLoad(
            worker_id="test",
            worker_type="general",
            node_id="node-1",
            status="idle",
            is_healthy=False,
        )

        assert load.effective_weight == 0.0

    # =========================================================================
    # Convenience Function Tests
    # =========================================================================

    def test_get_load_balancer_default_path(self):
        """Test getting load balancer with default path."""
        # This will try to use the default path
        lb = get_load_balancer()
        assert isinstance(lb, LoadBalancer)

    def test_select_worker_for_task_convenience(self, populated_db):
        """Test the convenience function for selecting workers."""
        worker_id = select_worker_for_task("shell", populated_db, "least_loaded")
        assert worker_id is not None

    # =========================================================================
    # Schema Initialization Tests
    # =========================================================================

    def test_init_load_balancer_schema(self, db_path):
        """Test schema initialization."""
        init_load_balancer_schema(db_path)

        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()

        table_names = [t[0] for t in tables]
        assert "worker_config" in table_names


class TestLoadBalancerStrategies:
    """Focused tests for each load balancing strategy."""

    @pytest.fixture
    def db_path(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def balanced_setup(self, db_path):
        """Create a balanced setup with multiple workers."""
        conn = sqlite3.connect(db_path)
        now = datetime.now().isoformat()

        conn.executescript(
            """
            CREATE TABLE workers (
                id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                worker_type TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                last_heartbeat TIMESTAMP
            );
            CREATE TABLE task_queue (
                id INTEGER PRIMARY KEY,
                task_type TEXT,
                status TEXT,
                assigned_worker TEXT,
                priority INTEGER DEFAULT 5,
                retries INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            );
            CREATE TABLE worker_config (
                id INTEGER PRIMARY KEY,
                worker_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                UNIQUE(worker_id, key)
            );
        """
        )

        # Add 5 workers with varying loads
        workers = [
            ("w1", "n1", "general", "idle", 10, 1.0, 2),  # 20% load
            ("w2", "n1", "general", "idle", 10, 1.0, 5),  # 50% load
            ("w3", "n2", "general", "idle", 10, 2.0, 3),  # 30% load, higher weight
            ("w4", "n2", "shell", "idle", 20, 1.0, 0),  # 0% load, high capacity
            ("w5", "n1", "shell", "idle", 5, 1.0, 4),  # 80% load
        ]

        for wid, node, wtype, status, cap, weight, task_count in workers:
            conn.execute(
                """
                INSERT INTO workers (id, node_id, worker_type, status, last_heartbeat)
                VALUES (?, ?, ?, ?, ?)
            """,
                (wid, node, wtype, status, now),
            )
            conn.execute(
                """
                INSERT INTO worker_config (worker_id, key, value)
                VALUES (?, 'capacity', ?)
            """,
                (wid, str(cap)),
            )
            conn.execute(
                """
                INSERT INTO worker_config (worker_id, key, value)
                VALUES (?, 'weight', ?)
            """,
                (wid, str(weight)),
            )
            for _ in range(task_count):
                conn.execute(
                    """
                    INSERT INTO task_queue (task_type, status, assigned_worker)
                    VALUES ('shell', 'running', ?)
                """,
                    (wid,),
                )

        conn.commit()
        conn.close()
        return db_path

    def test_strategy_comparison(self, balanced_setup):
        """Compare different strategies on the same setup."""
        lb = LoadBalancer(balanced_setup)

        results = {}
        for strategy in LoadBalancingStrategy:
            selection = lb.select_worker(strategy=strategy)
            results[strategy.value] = selection.worker_id

        # Least loaded should pick w4 (0% load)
        assert results["least_loaded"] == "w4"

        # Weighted might pick differently based on effective weight
        assert results["weighted"] is not None

    def test_strategy_consistency(self, balanced_setup):
        """Test that deterministic strategies are consistent."""
        lb = LoadBalancer(balanced_setup)

        # Least loaded should always pick the same worker
        selections = [
            lb.select_worker(strategy=LoadBalancingStrategy.LEAST_LOADED).worker_id
            for _ in range(5)
        ]
        assert len(set(selections)) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
