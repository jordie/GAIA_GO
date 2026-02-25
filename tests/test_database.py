"""
Database Tests for Architect Dashboard
"""
import os
import sqlite3
import tempfile

import pytest


class TestDatabaseConnection:
    """Tests for database connectivity."""

    def test_database_exists(self, app):
        """Test that database file exists after app init."""
        db_path = os.environ.get("DB_PATH")
        assert db_path is not None
        assert os.path.exists(db_path)

    def test_database_connection(self, app):
        """Test that we can connect to the database."""
        db_path = os.environ.get("DB_PATH")
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        conn.close()


class TestDatabaseSchema:
    """Tests for database schema."""

    def test_required_tables_exist(self, app):
        """Test that all required tables exist."""
        db_path = os.environ.get("DB_PATH")
        conn = sqlite3.connect(db_path)

        required_tables = [
            "users",
            "projects",
            "milestones",
            "features",
            "bugs",
            "errors",
            "nodes",
            "tmux_sessions",
            "task_queue",
            "workers",
            "activity_log",
        ]

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]

        for table in required_tables:
            assert table in existing_tables, f"Table {table} not found"

        conn.close()

    def test_projects_table_columns(self, app):
        """Test projects table has required columns."""
        db_path = os.environ.get("DB_PATH")
        conn = sqlite3.connect(db_path)

        cursor = conn.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = ["id", "name", "description", "status"]
        for col in required_columns:
            assert col in columns, f"Column {col} not found in projects"

        conn.close()

    def test_features_table_columns(self, app):
        """Test features table has required columns."""
        db_path = os.environ.get("DB_PATH")
        conn = sqlite3.connect(db_path)

        cursor = conn.execute("PRAGMA table_info(features)")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = ["id", "project_id", "name", "status"]
        for col in required_columns:
            assert col in columns, f"Column {col} not found in features"

        conn.close()


class TestDatabaseOperations:
    """Tests for database CRUD operations."""

    def test_insert_project(self, test_db):
        """Test inserting a project."""
        conn, db_path = test_db

        conn.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)",
            ("Test Project", "Description"),
        )
        conn.commit()

        cursor = conn.execute("SELECT * FROM projects WHERE name = ?", ("Test Project",))
        row = cursor.fetchone()

        assert row is not None
        assert row["name"] == "Test Project"

    def test_update_project(self, test_db):
        """Test updating a project."""
        conn, db_path = test_db

        conn.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)", ("Update Test", "Original")
        )
        conn.commit()

        conn.execute(
            "UPDATE projects SET description = ? WHERE name = ?", ("Updated", "Update Test")
        )
        conn.commit()

        cursor = conn.execute("SELECT description FROM projects WHERE name = ?", ("Update Test",))
        row = cursor.fetchone()
        assert row["description"] == "Updated"

    def test_delete_project(self, test_db):
        """Test deleting a project."""
        conn, db_path = test_db

        conn.execute("INSERT INTO projects (name) VALUES (?)", ("Delete Test",))
        conn.commit()

        conn.execute("DELETE FROM projects WHERE name = ?", ("Delete Test",))
        conn.commit()

        cursor = conn.execute("SELECT * FROM projects WHERE name = ?", ("Delete Test",))
        row = cursor.fetchone()
        assert row is None

    def test_unique_constraint(self, test_db):
        """Test unique constraint on project name."""
        conn, db_path = test_db

        conn.execute("INSERT INTO projects (name) VALUES (?)", ("Unique Test",))
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO projects (name) VALUES (?)", ("Unique Test",))
            conn.commit()


class TestMigrations:
    """Tests for migration system."""

    def test_migration_manager_import(self):
        """Test migration manager can be imported."""
        from migrations.manager import MigrationManager

        assert MigrationManager is not None

    def test_migration_status(self):
        """Test getting migration status."""
        from migrations.manager import MigrationManager

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            manager = MigrationManager(db_path)
            status = manager.get_status()

            assert "database" in status
            assert "applied_count" in status
            assert "pending_count" in status
        finally:
            os.unlink(db_path)

    def test_migration_files_exist(self):
        """Test that migration files exist."""
        from pathlib import Path

        migrations_dir = Path(__file__).parent.parent / "migrations"
        migration_files = list(migrations_dir.glob("[0-9][0-9][0-9]_*.py"))

        assert len(migration_files) >= 2, "Expected at least 2 migration files"
