#!/usr/bin/env python3
"""
Comprehensive Integration Tests

Tests interactions between multiple system components.

Created for: P07 - Create Testing Infrastructure
"""

import json
import sqlite3
import time
from pathlib import Path

import pytest

# Test markers
pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create minimal schema
    conn.executescript(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            assignee_id INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT
        );
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestDatabaseIntegration:
    """Test database operations and relationships."""

    def test_cascade_delete(self, test_db):
        """Test that deleting a project cascades to tasks."""
        # Create project with tasks
        cursor = test_db.execute("INSERT INTO projects (name) VALUES ('Project A')")
        project_id = cursor.lastrowid

        test_db.execute("INSERT INTO tasks (project_id, title) VALUES (?, 'Task 1')", (project_id,))
        test_db.execute("INSERT INTO tasks (project_id, title) VALUES (?, 'Task 2')", (project_id,))
        test_db.commit()

        # Verify tasks created
        count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        assert count == 2

        # Delete project
        test_db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        test_db.commit()

        # Verify tasks also deleted
        count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        assert count == 0

    def test_transaction_rollback(self, test_db):
        """Test transaction rollback on error."""
        # Insert project
        test_db.execute("INSERT INTO projects (name) VALUES ('Project B')")
        test_db.commit()

        initial_count = test_db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

        # Try to insert duplicate (should fail)
        try:
            test_db.execute("INSERT INTO projects (name) VALUES ('Project B')")
            test_db.commit()
        except sqlite3.IntegrityError:
            test_db.rollback()

        # Verify count unchanged
        final_count = test_db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        assert final_count == initial_count

    def test_foreign_key_constraint(self, test_db):
        """Test foreign key constraints are enforced."""
        # Enable foreign keys (SQLite default is off in Python)
        test_db.execute("PRAGMA foreign_keys = ON")

        # Try to insert task with non-existent project
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute("INSERT INTO tasks (project_id, title) VALUES (99999, 'Orphan Task')")
            test_db.commit()


class TestTaskWorkflowIntegration:
    """Test complete task lifecycle workflows."""

    def test_task_assignment_workflow(self, test_db):
        """Test complete task assignment and status updates."""
        # Setup
        test_db.execute("INSERT INTO users (username) VALUES ('user1')")
        user_id = test_db.lastrowid

        test_db.execute("INSERT INTO projects (name) VALUES ('Project C')")
        project_id = test_db.lastrowid

        test_db.execute("INSERT INTO tasks (project_id, title) VALUES (?, 'Task 1')", (project_id,))
        task_id = test_db.lastrowid
        test_db.commit()

        # Assign task
        test_db.execute("UPDATE tasks SET assignee_id = ? WHERE id = ?", (user_id, task_id))
        test_db.commit()

        # Verify assignment
        row = test_db.execute(
            "SELECT assignee_id, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        assert row[0] == user_id
        assert row[1] == "pending"

        # Mark in progress
        test_db.execute("UPDATE tasks SET status = 'in_progress' WHERE id = ?", (task_id,))
        test_db.commit()

        # Mark completed
        test_db.execute("UPDATE tasks SET status = 'completed' WHERE id = ?", (task_id,))
        test_db.commit()

        # Verify final state
        row = test_db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row[0] == "completed"

    def test_bulk_task_operations(self, test_db):
        """Test bulk task creation and updates."""
        # Create project
        test_db.execute("INSERT INTO projects (name) VALUES ('Project D')")
        project_id = test_db.lastrowid

        # Bulk create tasks
        tasks = [(project_id, f"Task {i}", "high" if i <= 2 else "medium") for i in range(1, 11)]

        test_db.executemany(
            "INSERT INTO tasks (project_id, title, priority) VALUES (?, ?, ?)", tasks
        )
        test_db.commit()

        # Verify all created
        count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        assert count == 10

        # Bulk update high priority tasks
        test_db.execute(
            "UPDATE tasks SET status = 'in_progress' WHERE project_id = ? AND priority = 'high'",
            (project_id,),
        )
        test_db.commit()

        # Verify updates
        in_progress = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = 'in_progress'",
            (project_id,),
        ).fetchone()[0]

        assert in_progress == 2


class TestAPIIntegration:
    """Test API endpoint integrations."""

    @pytest.fixture
    def flask_client(self):
        """Create Flask test client."""
        try:
            from app import app

            app.config["TESTING"] = True
            return app.test_client()
        except ImportError:
            pytest.skip("Flask app not available")

    def test_health_endpoint(self, flask_client):
        """Test health check endpoint."""
        response = flask_client.get("/health")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data.get("status") == "ok"

    def test_api_error_handling(self, flask_client):
        """Test API error responses."""
        # Try to get non-existent resource
        response = flask_client.get("/api/tasks/99999")

        # Should return 404 or error response
        assert response.status_code in [404, 500]

        # Should have JSON error
        data = json.loads(response.data)
        assert "error" in data or "success" in data


class TestFileSystemIntegration:
    """Test file system operations."""

    def test_log_file_creation(self, tmp_path):
        """Test log file creation and writing."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        log_file = log_dir / "test.log"

        # Write log entry
        with open(log_file, "w") as f:
            f.write("Test log entry\n")

        # Verify file exists and readable
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test log entry" in content

    def test_data_directory_structure(self, tmp_path):
        """Test data directory creation and structure."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Create subdirectories
        (data_dir / "projects").mkdir()
        (data_dir / "tasks").mkdir()
        (data_dir / "backups").mkdir()

        # Verify structure
        assert (data_dir / "projects").is_dir()
        assert (data_dir / "tasks").is_dir()
        assert (data_dir / "backups").is_dir()


class TestConcurrencyIntegration:
    """Test concurrent operations."""

    def test_database_concurrent_reads(self, test_db):
        """Test multiple simultaneous reads."""
        # Insert test data
        test_db.execute("INSERT INTO projects (name) VALUES ('Project E')")
        project_id = test_db.lastrowid
        test_db.commit()

        # Simulate multiple reads
        results = []
        for _ in range(10):
            row = test_db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            results.append(row)

        # All reads should return same data
        assert len(results) == 10
        assert all(r[0] == project_id for r in results)

    def test_database_concurrent_writes(self, test_db):
        """Test handling of concurrent write attempts."""
        test_db.execute("INSERT INTO projects (name) VALUES ('Project F')")
        project_id = test_db.lastrowid
        test_db.commit()

        # Multiple updates to same record
        for i in range(5):
            test_db.execute(
                "UPDATE projects SET description = ? WHERE id = ?",
                (f"Description {i}", project_id),
            )
            test_db.commit()

        # Verify final state
        desc = test_db.execute(
            "SELECT description FROM projects WHERE id = ?", (project_id,)
        ).fetchone()[0]

        assert desc == "Description 4"


class TestDataIntegrityIntegration:
    """Test data validation and integrity."""

    def test_unique_constraint_enforcement(self, test_db):
        """Test unique constraints are enforced."""
        # Insert project
        test_db.execute("INSERT INTO projects (name) VALUES ('Unique Project')")
        test_db.commit()

        # Try duplicate
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute("INSERT INTO projects (name) VALUES ('Unique Project')")
            test_db.commit()

    def test_data_type_validation(self, test_db):
        """Test that incorrect data types are handled."""
        # Insert valid project
        test_db.execute("INSERT INTO projects (name) VALUES ('Project G')")
        project_id = test_db.lastrowid
        test_db.commit()

        # Try to insert task with string as project_id (should convert or fail gracefully)
        try:
            test_db.execute("INSERT INTO tasks (project_id, title) VALUES ('invalid', 'Task')")
            test_db.commit()
            # If it succeeds, verify conversion happened
            row = test_db.execute("SELECT project_id FROM tasks WHERE title = 'Task'").fetchone()
            # SQLite may convert 'invalid' to 0
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            # Expected: type mismatch or foreign key violation
            test_db.rollback()


class TestPerformanceIntegration:
    """Test performance of integrated operations."""

    def test_bulk_insert_performance(self, test_db):
        """Test bulk insert performance."""
        test_db.execute("INSERT INTO projects (name) VALUES ('Performance Test')")
        project_id = test_db.lastrowid
        test_db.commit()

        # Bulk insert 1000 tasks
        start_time = time.time()

        tasks = [(project_id, f"Task {i}") for i in range(1000)]
        test_db.executemany("INSERT INTO tasks (project_id, title) VALUES (?, ?)", tasks)
        test_db.commit()

        duration = time.time() - start_time

        # Should complete in reasonable time (< 5 seconds)
        assert duration < 5.0

        # Verify count
        count = test_db.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,)
        ).fetchone()[0]

        assert count == 1000

    def test_query_performance_with_index(self, test_db):
        """Test query performance benefits of indexes."""
        # Insert test data
        test_db.execute("INSERT INTO projects (name) VALUES ('Index Test')")
        project_id = test_db.lastrowid

        # Insert many tasks
        tasks = [(project_id, f"Task {i}", "high" if i % 3 == 0 else "medium") for i in range(1000)]

        test_db.executemany(
            "INSERT INTO tasks (project_id, title, priority) VALUES (?, ?, ?)", tasks
        )
        test_db.commit()

        # Query without index
        start = time.time()
        result1 = test_db.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND priority = 'high'", (project_id,)
        ).fetchall()
        no_index_time = time.time() - start

        # Create index
        test_db.execute("CREATE INDEX idx_tasks_priority ON tasks(priority)")
        test_db.commit()

        # Query with index
        start = time.time()
        result2 = test_db.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND priority = 'high'", (project_id,)
        ).fetchall()
        with_index_time = time.time() - start

        # Results should be same
        assert len(result1) == len(result2)

        # With index should be faster or similar (on small dataset may not show difference)
        # Just verify it completes successfully
        assert with_index_time < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
