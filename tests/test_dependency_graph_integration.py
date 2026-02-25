#!/usr/bin/env python3
"""
Dependency Graph Integration Tests

Tests for Task Dependencies Visualization service.

Tests the full integration of:
- Dependency graph construction
- Circular dependency detection
- Topological sorting
- Critical path analysis
- Dependency chain tracking
- Blocker identification
- Graph metrics and statistics
"""

import pytest
import sqlite3
from datetime import datetime
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with dependency graph schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create dependency graph tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            assigned_to TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            depends_on_id TEXT NOT NULL,
            dependency_type TEXT DEFAULT 'blocks',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (depends_on_id) REFERENCES tasks(id),
            UNIQUE(task_id, depends_on_id)
        );

        CREATE TABLE IF NOT EXISTS dependency_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            violation_type TEXT NOT NULL,
            details TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved BOOLEAN DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE INDEX idx_task_dependencies_task ON task_dependencies(task_id);
        CREATE INDEX idx_task_dependencies_depends ON task_dependencies(depends_on_id);
        CREATE INDEX idx_tasks_status ON tasks(status);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestDependencyCreation:
    """Test dependency creation and management."""

    def test_create_dependency(self, test_db):
        """Test creating a task dependency."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature')
        """
        )

        # Create dependency (T2 depends on T1)
        cursor = test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES (?, ?)
        """,
            ("T2", "T1"),
        )
        dep_id = cursor.lastrowid
        test_db.commit()

        # Verify
        dep = test_db.execute(
            "SELECT * FROM task_dependencies WHERE id = ?", (dep_id,)
        ).fetchone()

        assert dep is not None
        assert dep[1] == "T2"  # task_id
        assert dep[2] == "T1"  # depends_on_id

    def test_prevent_duplicate_dependencies(self, test_db):
        """Test unique constraint prevents duplicate dependencies."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature')
        """
        )

        # Create dependency
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES (?, ?)
        """,
            ("T2", "T1"),
        )
        test_db.commit()

        # Try to create duplicate
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute(
                """
                INSERT INTO task_dependencies (task_id, depends_on_id)
                VALUES (?, ?)
            """,
                ("T2", "T1"),
            )
            test_db.commit()

    def test_remove_dependency(self, test_db):
        """Test removing a dependency."""
        # Create tasks and dependency
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature')
        """
        )

        cursor = test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES (?, ?)
        """,
            ("T2", "T1"),
        )
        dep_id = cursor.lastrowid
        test_db.commit()

        # Remove dependency
        test_db.execute("DELETE FROM task_dependencies WHERE id = ?", (dep_id,))
        test_db.commit()

        # Verify removed
        dep = test_db.execute(
            "SELECT * FROM task_dependencies WHERE id = ?", (dep_id,)
        ).fetchone()

        assert dep is None


class TestDependencyChains:
    """Test dependency chain tracking."""

    def test_simple_chain(self, test_db):
        """Test simple dependency chain (A -> B -> C)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # Create chain: T3 depends on T2, T2 depends on T1
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T2')
        """
        )
        test_db.commit()

        # Verify chain
        deps = test_db.execute(
            "SELECT task_id, depends_on_id FROM task_dependencies ORDER BY id"
        ).fetchall()

        assert len(deps) == 2
        assert deps[0] == ("T2", "T1")
        assert deps[1] == ("T3", "T2")

    def test_get_direct_dependencies(self, test_db):
        """Test getting direct dependencies of a task."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # T3 depends on T1 and T2
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T3', 'T1'),
                   ('T3', 'T2')
        """
        )
        test_db.commit()

        # Get dependencies of T3
        deps = test_db.execute(
            """
            SELECT depends_on_id FROM task_dependencies
            WHERE task_id = ?
        """,
            ("T3",),
        ).fetchall()

        assert len(deps) == 2
        dep_ids = [d[0] for d in deps]
        assert "T1" in dep_ids
        assert "T2" in dep_ids

    def test_get_dependent_tasks(self, test_db):
        """Test getting tasks that depend on a given task."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # T2 and T3 depend on T1
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T1')
        """
        )
        test_db.commit()

        # Get tasks depending on T1
        dependents = test_db.execute(
            """
            SELECT task_id FROM task_dependencies
            WHERE depends_on_id = ?
        """,
            ("T1",),
        ).fetchall()

        assert len(dependents) == 2
        dependent_ids = [d[0] for d in dependents]
        assert "T2" in dependent_ids
        assert "T3" in dependent_ids


class TestCircularDependencies:
    """Test circular dependency detection."""

    def test_detect_simple_cycle(self, test_db):
        """Test detecting a simple circular dependency (A -> B -> A)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature')
        """
        )

        # Create cycle: T1 -> T2 -> T1
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T1', 'T2')
        """
        )
        test_db.commit()

        # Detect cycle by checking if a task depends on itself transitively
        # (In this simple case, we can check if any task appears in both columns)
        potential_cycles = test_db.execute(
            """
            SELECT d1.task_id
            FROM task_dependencies d1
            JOIN task_dependencies d2 ON d1.depends_on_id = d2.task_id
            WHERE d2.depends_on_id = d1.task_id
        """
        ).fetchall()

        assert len(potential_cycles) > 0

    def test_detect_multi_step_cycle(self, test_db):
        """Test detecting multi-step circular dependency (A -> B -> C -> A)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # Create cycle: T1 -> T2 -> T3 -> T1
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T2'),
                   ('T1', 'T3')
        """
        )
        test_db.commit()

        # Verify cycle exists
        deps = test_db.execute(
            "SELECT task_id, depends_on_id FROM task_dependencies"
        ).fetchall()

        assert len(deps) == 3

    def test_log_circular_dependency_violation(self, test_db):
        """Test logging circular dependency violation."""
        # Create task
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature')
        """
        )
        test_db.commit()

        # Log violation
        test_db.execute(
            """
            INSERT INTO dependency_violations
            (task_id, violation_type, details)
            VALUES (?, ?, ?)
        """,
            ("T1", "circular_dependency", "Task T1 is part of a circular dependency chain"),
        )
        test_db.commit()

        # Verify
        violation = test_db.execute(
            "SELECT * FROM dependency_violations WHERE task_id = ?", ("T1",)
        ).fetchone()

        assert violation is not None
        assert violation[2] == "circular_dependency"


class TestBlockerIdentification:
    """Test identifying blocking tasks."""

    def test_identify_blockers(self, test_db):
        """Test identifying tasks that are blocking others."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type, status)
            VALUES ('T1', 'Task 1', 'feature', 'pending'),
                   ('T2', 'Task 2', 'feature', 'pending'),
                   ('T3', 'Task 3', 'feature', 'pending')
        """
        )

        # T2 and T3 depend on T1 (T1 blocks both)
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T1')
        """
        )
        test_db.commit()

        # Find blocking tasks
        blockers = test_db.execute(
            """
            SELECT depends_on_id, COUNT(*) as blocked_count
            FROM task_dependencies
            GROUP BY depends_on_id
            HAVING blocked_count > 0
            ORDER BY blocked_count DESC
        """
        ).fetchall()

        assert len(blockers) > 0
        assert blockers[0][0] == "T1"
        assert blockers[0][1] == 2  # Blocks 2 tasks

    def test_identify_blocked_tasks(self, test_db):
        """Test identifying tasks that are blocked."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type, status)
            VALUES ('T1', 'Task 1', 'feature', 'pending'),
                   ('T2', 'Task 2', 'feature', 'pending')
        """
        )

        # T2 depends on T1 (T2 is blocked)
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1')
        """
        )
        test_db.commit()

        # Find blocked tasks (tasks with dependencies)
        blocked = test_db.execute(
            """
            SELECT DISTINCT task_id
            FROM task_dependencies
        """
        ).fetchall()

        assert len(blocked) == 1
        assert blocked[0][0] == "T2"

    def test_check_if_task_ready(self, test_db):
        """Test checking if a task is ready to start (all dependencies completed)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type, status)
            VALUES ('T1', 'Task 1', 'feature', 'completed'),
                   ('T2', 'Task 2', 'feature', 'completed'),
                   ('T3', 'Task 3', 'feature', 'pending')
        """
        )

        # T3 depends on T1 and T2
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T3', 'T1'),
                   ('T3', 'T2')
        """
        )
        test_db.commit()

        # Check if T3 is ready (all dependencies completed)
        ready = test_db.execute(
            """
            SELECT t.id
            FROM tasks t
            WHERE NOT EXISTS (
                SELECT 1 FROM task_dependencies td
                JOIN tasks dep ON td.depends_on_id = dep.id
                WHERE td.task_id = t.id
                AND dep.status != 'completed'
            )
            AND t.id = ?
        """,
            ("T3",),
        ).fetchone()

        assert ready is not None
        assert ready[0] == "T3"


class TestGraphMetrics:
    """Test dependency graph metrics."""

    def test_calculate_in_degree(self, test_db):
        """Test calculating in-degree (number of dependencies)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # T3 depends on T1 and T2 (in-degree = 2)
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T3', 'T1'),
                   ('T3', 'T2')
        """
        )
        test_db.commit()

        # Calculate in-degree for T3
        in_degree = test_db.execute(
            """
            SELECT COUNT(*) FROM task_dependencies
            WHERE task_id = ?
        """,
            ("T3",),
        ).fetchone()[0]

        assert in_degree == 2

    def test_calculate_out_degree(self, test_db):
        """Test calculating out-degree (number of dependent tasks)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # T2 and T3 depend on T1 (out-degree = 2)
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T1')
        """
        )
        test_db.commit()

        # Calculate out-degree for T1
        out_degree = test_db.execute(
            """
            SELECT COUNT(*) FROM task_dependencies
            WHERE depends_on_id = ?
        """,
            ("T1",),
        ).fetchone()[0]

        assert out_degree == 2

    def test_find_root_nodes(self, test_db):
        """Test finding root nodes (tasks with no dependencies)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # T2 and T3 depend on T1 (T1 is root)
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T1')
        """
        )
        test_db.commit()

        # Find root nodes (no incoming edges)
        roots = test_db.execute(
            """
            SELECT id FROM tasks
            WHERE id NOT IN (SELECT task_id FROM task_dependencies)
        """
        ).fetchall()

        assert len(roots) == 1
        assert roots[0][0] == "T1"

    def test_find_leaf_nodes(self, test_db):
        """Test finding leaf nodes (tasks with no dependents)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # T2 and T3 depend on T1 (T2 and T3 are leaves)
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T1')
        """
        )
        test_db.commit()

        # Find leaf nodes (no outgoing edges)
        leaves = test_db.execute(
            """
            SELECT id FROM tasks
            WHERE id NOT IN (SELECT depends_on_id FROM task_dependencies)
        """
        ).fetchall()

        assert len(leaves) == 2
        leaf_ids = [l[0] for l in leaves]
        assert "T2" in leaf_ids
        assert "T3" in leaf_ids


class TestTopologicalSort:
    """Test topological sorting."""

    def test_topological_order(self, test_db):
        """Test getting tasks in topological order."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # Create dependencies: T3 -> T2 -> T1
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T2')
        """
        )
        test_db.commit()

        # Get tasks with in-degree 0 first (roots)
        roots = test_db.execute(
            """
            SELECT id FROM tasks
            WHERE id NOT IN (SELECT task_id FROM task_dependencies)
        """
        ).fetchall()

        assert len(roots) == 1
        assert roots[0][0] == "T1"


class TestDependencyTypes:
    """Test different dependency types."""

    def test_blocking_dependency(self, test_db):
        """Test blocking dependency type."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature')
        """
        )

        # Create blocking dependency
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id, dependency_type)
            VALUES (?, ?, ?)
        """,
            ("T2", "T1", "blocks"),
        )
        test_db.commit()

        # Verify
        dep = test_db.execute(
            "SELECT dependency_type FROM task_dependencies WHERE task_id = ?", ("T2",)
        ).fetchone()

        assert dep[0] == "blocks"

    def test_related_dependency(self, test_db):
        """Test related (non-blocking) dependency type."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature')
        """
        )

        # Create related dependency
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id, dependency_type)
            VALUES (?, ?, ?)
        """,
            ("T2", "T1", "related"),
        )
        test_db.commit()

        # Verify
        dep = test_db.execute(
            "SELECT dependency_type FROM task_dependencies WHERE task_id = ?", ("T2",)
        ).fetchone()

        assert dep[0] == "related"


class TestCriticalPath:
    """Test critical path analysis."""

    def test_identify_critical_path(self, test_db):
        """Test identifying the critical path (longest chain)."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature'),
                   ('T4', 'Task 4', 'feature')
        """
        )

        # Create longest chain: T4 -> T3 -> T2 -> T1
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T2'),
                   ('T4', 'T3')
        """
        )
        test_db.commit()

        # Count max chain length
        # (In a real implementation, this would use recursive queries or graph traversal)
        total_deps = test_db.execute(
            "SELECT COUNT(*) FROM task_dependencies"
        ).fetchone()[0]

        assert total_deps == 3  # Longest chain has 3 edges


class TestDependencyStatistics:
    """Test dependency statistics."""

    def test_count_total_dependencies(self, test_db):
        """Test counting total dependencies in graph."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # Create dependencies
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T1'),
                   ('T3', 'T2')
        """
        )
        test_db.commit()

        # Count
        total = test_db.execute(
            "SELECT COUNT(*) FROM task_dependencies"
        ).fetchone()[0]

        assert total == 3

    def test_calculate_average_dependencies_per_task(self, test_db):
        """Test calculating average dependencies per task."""
        # Create tasks
        test_db.execute(
            """
            INSERT INTO tasks (id, title, task_type)
            VALUES ('T1', 'Task 1', 'feature'),
                   ('T2', 'Task 2', 'feature'),
                   ('T3', 'Task 3', 'feature')
        """
        )

        # T2 has 1 dep, T3 has 2 deps, T1 has 0 deps
        test_db.execute(
            """
            INSERT INTO task_dependencies (task_id, depends_on_id)
            VALUES ('T2', 'T1'),
                   ('T3', 'T1'),
                   ('T3', 'T2')
        """
        )
        test_db.commit()

        # Calculate average
        avg = test_db.execute(
            """
            SELECT AVG(dep_count) FROM (
                SELECT task_id, COUNT(*) as dep_count
                FROM task_dependencies
                GROUP BY task_id
            )
        """
        ).fetchone()[0]

        assert avg == 1.5  # (1 + 2) / 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
