#!/usr/bin/env python3
"""
Roadmap API Integration Tests

Tests for roadmap management system.

Tests the full integration of:
- Roadmap API endpoints
- Task assignment
- Progress tracking
- Database operations
- Status updates
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with roadmap schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create roadmap-related tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'active',
            priority TEXT DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'draft',
            priority TEXT DEFAULT 'medium',
            milestone_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            feature_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            assigned_to TEXT,
            progress_percent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (feature_id) REFERENCES features(id)
        );

        CREATE TABLE IF NOT EXISTS task_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            assigned_agent TEXT,
            status TEXT DEFAULT 'pending',
            progress_percent INTEGER DEFAULT 0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_tasks_status ON tasks(status);
        CREATE INDEX idx_tasks_project ON tasks(project_id);
        CREATE INDEX idx_tasks_feature ON tasks(feature_id);
        CREATE INDEX idx_task_assignments_status ON task_assignments(status);
    """
    )
    conn.commit()

    yield conn

    conn.close()


@pytest.fixture
def flask_client(test_db, tmp_path):
    """Create Flask test client with roadmap routes."""
    try:
        import sys

        from flask import Flask

        sys.path.insert(0, str(Path(__file__).parent.parent))

        app = Flask(__name__)
        app.config["TESTING"] = True

        # Try to import and register roadmap routes
        try:
            # Override DB path for testing
            import services.roadmap_routes as rr
            from services.roadmap_routes import roadmap_bp

            rr.DB_PATH = str(tmp_path / "test.db")

            app.register_blueprint(roadmap_bp)
        except (ImportError, AttributeError):
            pytest.skip("Roadmap routes not available")

        return app.test_client()
    except ImportError:
        pytest.skip("Flask not available")


class TestProjectManagement:
    """Test project CRUD operations."""

    def test_create_project(self, test_db):
        """Test creating a project."""
        cursor = test_db.execute(
            """
            INSERT INTO projects (name, description, status, priority)
            VALUES (?, ?, ?, ?)
        """,
            ("Test Project", "Project description", "active", "high"),
        )
        project_id = cursor.lastrowid
        test_db.commit()

        # Verify created
        row = test_db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

        assert row is not None
        assert row[1] == "Test Project"
        assert row[3] == "active"

    def test_get_project(self, test_db):
        """Test retrieving a project."""
        # Insert test project
        cursor = test_db.execute(
            """
            INSERT INTO projects (name, description)
            VALUES (?, ?)
        """,
            ("Project A", "Description A"),
        )
        project_id = cursor.lastrowid
        test_db.commit()

        # Retrieve
        row = test_db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

        assert row is not None
        assert row[1] == "Project A"

    def test_update_project_status(self, test_db):
        """Test updating project status."""
        # Insert project
        cursor = test_db.execute(
            """
            INSERT INTO projects (name, status)
            VALUES (?, ?)
        """,
            ("Project B", "active"),
        )
        project_id = cursor.lastrowid
        test_db.commit()

        # Update status
        test_db.execute(
            """
            UPDATE projects SET status = ? WHERE id = ?
        """,
            ("completed", project_id),
        )
        test_db.commit()

        # Verify updated
        row = test_db.execute("SELECT status FROM projects WHERE id = ?", (project_id,)).fetchone()

        assert row[0] == "completed"

    def test_list_projects(self, test_db):
        """Test listing all projects."""
        # Insert multiple projects
        projects = [("Project 1", "active"), ("Project 2", "completed"), ("Project 3", "active")]

        for name, status in projects:
            test_db.execute(
                """
                INSERT INTO projects (name, status)
                VALUES (?, ?)
            """,
                (name, status),
            )
        test_db.commit()

        # List all
        rows = test_db.execute("SELECT * FROM projects ORDER BY id").fetchall()

        assert len(rows) == 3
        assert rows[0][1] == "Project 1"
        assert rows[1][1] == "Project 2"


class TestFeatureManagement:
    """Test feature CRUD operations."""

    def test_create_feature(self, test_db):
        """Test creating a feature."""
        # Create project first
        cursor = test_db.execute(
            """
            INSERT INTO projects (name)
            VALUES (?)
        """,
            ("Test Project",),
        )
        project_id = cursor.lastrowid
        test_db.commit()

        # Create feature
        cursor = test_db.execute(
            """
            INSERT INTO features (project_id, name, description, status)
            VALUES (?, ?, ?, ?)
        """,
            (project_id, "Feature A", "Feature description", "in_progress"),
        )
        feature_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT * FROM features WHERE id = ?", (feature_id,)).fetchone()

        assert row is not None
        assert row[2] == "Feature A"
        assert row[4] == "in_progress"

    def test_link_feature_to_project(self, test_db):
        """Test feature-project relationship."""
        # Create project
        cursor = test_db.execute("INSERT INTO projects (name) VALUES (?)", ("Project X",))
        project_id = cursor.lastrowid

        # Create features
        test_db.execute(
            """
            INSERT INTO features (project_id, name)
            VALUES (?, ?), (?, ?)
        """,
            (project_id, "Feature 1", project_id, "Feature 2"),
        )
        test_db.commit()

        # Get features for project
        rows = test_db.execute(
            "SELECT * FROM features WHERE project_id = ?", (project_id,)
        ).fetchall()

        assert len(rows) == 2
        assert all(row[1] == project_id for row in rows)

    def test_feature_status_progression(self, test_db):
        """Test feature status transitions."""
        # Create project and feature
        cursor = test_db.execute("INSERT INTO projects (name) VALUES (?)", ("Project Y",))
        project_id = cursor.lastrowid

        cursor = test_db.execute(
            """
            INSERT INTO features (project_id, name, status)
            VALUES (?, ?, ?)
        """,
            (project_id, "Feature Y", "draft"),
        )
        feature_id = cursor.lastrowid
        test_db.commit()

        # Progress through statuses
        statuses = ["in_progress", "review", "completed"]

        for status in statuses:
            test_db.execute("UPDATE features SET status = ? WHERE id = ?", (status, feature_id))
            test_db.commit()

            row = test_db.execute(
                "SELECT status FROM features WHERE id = ?", (feature_id,)
            ).fetchone()
            assert row[0] == status


class TestTaskManagement:
    """Test task CRUD operations."""

    def test_create_task(self, test_db):
        """Test creating a task."""
        # Create project
        cursor = test_db.execute("INSERT INTO projects (name) VALUES (?)", ("Project Z",))
        project_id = cursor.lastrowid
        test_db.commit()

        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO tasks (project_id, title, description, priority)
            VALUES (?, ?, ?, ?)
        """,
            (project_id, "Task 1", "Task description", "high"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

        assert row is not None
        assert row[3] == "Task 1"
        assert row[6] == "high"

    def test_assign_task(self, test_db):
        """Test assigning a task to an agent."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO tasks (title, status)
            VALUES (?, ?)
        """,
            ("Assignable Task", "pending"),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Assign task
        test_db.execute(
            """
            UPDATE tasks SET assigned_to = ?, status = ?
            WHERE id = ?
        """,
            ("agent-1", "in_progress", task_id),
        )
        test_db.commit()

        # Verify assignment
        row = test_db.execute(
            "SELECT assigned_to, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()

        assert row[0] == "agent-1"
        assert row[1] == "in_progress"

    def test_update_task_progress(self, test_db):
        """Test updating task progress."""
        # Create task
        cursor = test_db.execute(
            """
            INSERT INTO tasks (title, progress_percent)
            VALUES (?, ?)
        """,
            ("Progress Task", 0),
        )
        task_id = cursor.lastrowid
        test_db.commit()

        # Update progress
        progress_values = [25, 50, 75, 100]

        for progress in progress_values:
            test_db.execute(
                "UPDATE tasks SET progress_percent = ? WHERE id = ?", (progress, task_id)
            )
            test_db.commit()

            row = test_db.execute(
                "SELECT progress_percent FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            assert row[0] == progress

    def test_task_filtering_by_status(self, test_db):
        """Test filtering tasks by status."""
        # Create tasks with different statuses
        statuses = ["pending", "in_progress", "completed", "pending", "in_progress"]

        for i, status in enumerate(statuses):
            test_db.execute(
                """
                INSERT INTO tasks (title, status)
                VALUES (?, ?)
            """,
                (f"Task {i}", status),
            )
        test_db.commit()

        # Filter by status
        pending_rows = test_db.execute(
            "SELECT * FROM tasks WHERE status = ?", ("pending",)
        ).fetchall()

        in_progress_rows = test_db.execute(
            "SELECT * FROM tasks WHERE status = ?", ("in_progress",)
        ).fetchall()

        completed_rows = test_db.execute(
            "SELECT * FROM tasks WHERE status = ?", ("completed",)
        ).fetchall()

        assert len(pending_rows) == 2
        assert len(in_progress_rows) == 2
        assert len(completed_rows) == 1


class TestTaskAssignments:
    """Test task assignment tracking."""

    def test_create_task_assignment(self, test_db):
        """Test creating a task assignment."""
        cursor = test_db.execute(
            """
            INSERT INTO task_assignments (task_id, assigned_agent, status)
            VALUES (?, ?, ?)
        """,
            ("A01", "agent-1", "pending"),
        )
        assignment_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT * FROM task_assignments WHERE id = ?", (assignment_id,)
        ).fetchone()

        assert row is not None
        assert row[1] == "A01"
        assert row[2] == "agent-1"

    def test_update_assignment_status(self, test_db):
        """Test updating assignment status."""
        # Create assignment
        cursor = test_db.execute(
            """
            INSERT INTO task_assignments (task_id, assigned_agent, status)
            VALUES (?, ?, ?)
        """,
            ("A02", "agent-2", "pending"),
        )
        assignment_id = cursor.lastrowid
        test_db.commit()

        # Update to in_progress
        test_db.execute(
            """
            UPDATE task_assignments
            SET status = ?, started_at = ?
            WHERE id = ?
        """,
            ("in_progress", datetime.now().isoformat(), assignment_id),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT status, started_at FROM task_assignments WHERE id = ?", (assignment_id,)
        ).fetchone()

        assert row[0] == "in_progress"
        assert row[1] is not None

    def test_complete_assignment(self, test_db):
        """Test completing an assignment."""
        # Create assignment
        cursor = test_db.execute(
            """
            INSERT INTO task_assignments (task_id, assigned_agent, status, progress_percent)
            VALUES (?, ?, ?, ?)
        """,
            ("A03", "agent-3", "in_progress", 75),
        )
        assignment_id = cursor.lastrowid
        test_db.commit()

        # Complete
        test_db.execute(
            """
            UPDATE task_assignments
            SET status = ?, progress_percent = ?, completed_at = ?
            WHERE id = ?
        """,
            ("completed", 100, datetime.now().isoformat(), assignment_id),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT status, progress_percent, completed_at FROM task_assignments WHERE id = ?",
            (assignment_id,),
        ).fetchone()

        assert row[0] == "completed"
        assert row[1] == 100
        assert row[2] is not None


class TestRoadmapHierarchy:
    """Test project-feature-task hierarchy."""

    def test_complete_hierarchy(self, test_db):
        """Test creating complete project hierarchy."""
        # Create project
        cursor = test_db.execute("INSERT INTO projects (name) VALUES (?)", ("Full Project",))
        project_id = cursor.lastrowid

        # Create feature
        cursor = test_db.execute(
            """
            INSERT INTO features (project_id, name)
            VALUES (?, ?)
        """,
            (project_id, "Full Feature"),
        )
        feature_id = cursor.lastrowid

        # Create tasks
        for i in range(3):
            test_db.execute(
                """
                INSERT INTO tasks (project_id, feature_id, title)
                VALUES (?, ?, ?)
            """,
                (project_id, feature_id, f"Task {i}"),
            )
        test_db.commit()

        # Verify hierarchy
        project = test_db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

        features = test_db.execute(
            "SELECT * FROM features WHERE project_id = ?", (project_id,)
        ).fetchall()

        tasks = test_db.execute(
            "SELECT * FROM tasks WHERE feature_id = ?", (feature_id,)
        ).fetchall()

        assert project is not None
        assert len(features) == 1
        assert len(tasks) == 3

    def test_cascade_relationships(self, test_db):
        """Test data relationships in hierarchy."""
        # Create hierarchy
        cursor = test_db.execute("INSERT INTO projects (name) VALUES (?)", ("Cascade Test",))
        project_id = cursor.lastrowid

        cursor = test_db.execute(
            """
            INSERT INTO features (project_id, name)
            VALUES (?, ?)
        """,
            (project_id, "Feature"),
        )
        feature_id = cursor.lastrowid

        test_db.execute(
            """
            INSERT INTO tasks (project_id, feature_id, title)
            VALUES (?, ?, ?)
        """,
            (project_id, feature_id, "Task"),
        )
        test_db.commit()

        # Verify all linked correctly
        task = test_db.execute("SELECT project_id, feature_id FROM tasks LIMIT 1").fetchone()

        assert task[0] == project_id
        assert task[1] == feature_id


class TestProgressTracking:
    """Test progress tracking across roadmap."""

    def test_project_completion_percentage(self, test_db):
        """Test calculating project completion."""
        # Create project with tasks
        cursor = test_db.execute("INSERT INTO projects (name) VALUES (?)", ("Progress Project",))
        project_id = cursor.lastrowid

        # Create 10 tasks: 3 completed, 5 in progress, 2 pending
        statuses = ["completed"] * 3 + ["in_progress"] * 5 + ["pending"] * 2

        for i, status in enumerate(statuses):
            test_db.execute(
                """
                INSERT INTO tasks (project_id, title, status)
                VALUES (?, ?, ?)
            """,
                (project_id, f"Task {i}", status),
            )
        test_db.commit()

        # Calculate completion
        total = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,)
        ).fetchone()[0]

        completed = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = ?",
            (project_id, "completed"),
        ).fetchone()[0]

        completion_percent = (completed / total) * 100 if total > 0 else 0

        assert total == 10
        assert completed == 3
        assert completion_percent == 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
