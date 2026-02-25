"""
Tests for soft delete functionality.
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.soft_delete import (
    SOFT_DELETE_TABLES,
    add_soft_delete_columns,
    build_active_filter,
    cascade_soft_delete,
    count_deleted,
    get_deleted,
    get_deletion_stats,
    hard_delete,
    purge_deleted,
    restore,
    restore_many,
    soft_delete,
    soft_delete_many,
)


@pytest.fixture
def db_path():
    """Create a temporary database with soft delete schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Create tables with soft delete columns
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP,
            deleted_by TEXT
        )
    """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_deleted ON projects(deleted_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP,
            deleted_by TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_milestones_deleted ON milestones(deleted_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP,
            deleted_by TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_deleted ON features(deleted_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP,
            deleted_by TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bugs_deleted ON bugs(deleted_at)")

    conn.commit()
    conn.close()

    yield path

    os.unlink(path)


@pytest.fixture
def conn(db_path):
    """Get database connection."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def create_project(conn, name, status="active"):
    """Helper to create a project."""
    cursor = conn.execute("INSERT INTO projects (name, status) VALUES (?, ?)", (name, status))
    conn.commit()
    return cursor.lastrowid


def create_feature(conn, project_id, name, status="draft"):
    """Helper to create a feature."""
    cursor = conn.execute(
        "INSERT INTO features (project_id, name, status) VALUES (?, ?, ?)",
        (project_id, name, status),
    )
    conn.commit()
    return cursor.lastrowid


class TestSoftDelete:
    """Test basic soft delete functionality."""

    def test_soft_delete_single_record(self, conn):
        """Soft delete sets deleted_at timestamp."""
        project_id = create_project(conn, "Test Project")

        result = soft_delete(conn, "projects", project_id)
        assert result is True

        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row["deleted_at"] is not None
        assert row["deleted_by"] is None

    def test_soft_delete_with_user(self, conn):
        """Soft delete records who deleted the record."""
        project_id = create_project(conn, "Test Project")

        result = soft_delete(conn, "projects", project_id, deleted_by="admin")

        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row["deleted_at"] is not None
        assert row["deleted_by"] == "admin"

    def test_soft_delete_nonexistent_record(self, conn):
        """Soft delete returns False for non-existent record."""
        result = soft_delete(conn, "projects", 99999)
        assert result is False

    def test_soft_delete_already_deleted(self, conn):
        """Soft delete returns False for already deleted record."""
        project_id = create_project(conn, "Test Project")

        soft_delete(conn, "projects", project_id)
        result = soft_delete(conn, "projects", project_id)

        assert result is False

    def test_soft_delete_invalid_table(self, conn):
        """Soft delete raises error for invalid table."""
        with pytest.raises(ValueError, match="does not support soft delete"):
            soft_delete(conn, "invalid_table", 1)


class TestSoftDeleteMany:
    """Test bulk soft delete functionality."""

    def test_soft_delete_many(self, conn):
        """Soft delete multiple records at once."""
        ids = [create_project(conn, f"Project {i}") for i in range(5)]

        deleted_count = soft_delete_many(conn, "projects", ids)
        assert deleted_count == 5

        for pid in ids:
            row = conn.execute("SELECT deleted_at FROM projects WHERE id = ?", (pid,)).fetchone()
            assert row["deleted_at"] is not None

    def test_soft_delete_many_partial(self, conn):
        """Soft delete only deletes active records."""
        ids = [create_project(conn, f"Project {i}") for i in range(3)]

        # Pre-delete one
        soft_delete(conn, "projects", ids[0])

        deleted_count = soft_delete_many(conn, "projects", ids)
        assert deleted_count == 2

    def test_soft_delete_many_empty_list(self, conn):
        """Soft delete with empty list returns 0."""
        deleted_count = soft_delete_many(conn, "projects", [])
        assert deleted_count == 0


class TestRestore:
    """Test restore functionality."""

    def test_restore_deleted_record(self, conn):
        """Restore clears deleted_at and deleted_by."""
        project_id = create_project(conn, "Test Project")
        soft_delete(conn, "projects", project_id, deleted_by="admin")

        result = restore(conn, "projects", project_id)
        assert result is True

        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row["deleted_at"] is None
        assert row["deleted_by"] is None

    def test_restore_non_deleted_record(self, conn):
        """Restore returns False for non-deleted record."""
        project_id = create_project(conn, "Test Project")

        result = restore(conn, "projects", project_id)
        assert result is False

    def test_restore_nonexistent_record(self, conn):
        """Restore returns False for non-existent record."""
        result = restore(conn, "projects", 99999)
        assert result is False


class TestRestoreMany:
    """Test bulk restore functionality."""

    def test_restore_many(self, conn):
        """Restore multiple records at once."""
        ids = [create_project(conn, f"Project {i}") for i in range(3)]
        soft_delete_many(conn, "projects", ids)

        restored_count = restore_many(conn, "projects", ids)
        assert restored_count == 3

        for pid in ids:
            row = conn.execute("SELECT deleted_at FROM projects WHERE id = ?", (pid,)).fetchone()
            assert row["deleted_at"] is None

    def test_restore_many_partial(self, conn):
        """Restore only restores deleted records."""
        ids = [create_project(conn, f"Project {i}") for i in range(3)]

        # Only delete 2
        soft_delete_many(conn, "projects", ids[:2])

        restored_count = restore_many(conn, "projects", ids)
        assert restored_count == 2


class TestHardDelete:
    """Test permanent delete functionality."""

    def test_hard_delete(self, conn):
        """Hard delete permanently removes record."""
        project_id = create_project(conn, "Test Project")

        result = hard_delete(conn, "projects", project_id)
        assert result is True

        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row is None

    def test_hard_delete_nonexistent(self, conn):
        """Hard delete returns False for non-existent record."""
        result = hard_delete(conn, "projects", 99999)
        assert result is False


class TestPurgeDeleted:
    """Test purging old deleted records."""

    def test_purge_deleted_old_records(self, conn):
        """Purge removes records deleted more than N days ago."""
        project_id = create_project(conn, "Test Project")

        # Manually set old deleted_at
        conn.execute(
            """
            UPDATE projects SET deleted_at = datetime('now', '-31 days')
            WHERE id = ?
        """,
            (project_id,),
        )
        conn.commit()

        purged_count = purge_deleted(conn, "projects", older_than_days=30)
        assert purged_count == 1

        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row is None

    def test_purge_deleted_keeps_recent(self, conn):
        """Purge keeps recently deleted records."""
        project_id = create_project(conn, "Test Project")
        soft_delete(conn, "projects", project_id)

        purged_count = purge_deleted(conn, "projects", older_than_days=30)
        assert purged_count == 0

        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row is not None


class TestGetDeleted:
    """Test querying deleted records."""

    def test_get_deleted_records(self, conn):
        """Get deleted returns only deleted records."""
        active_id = create_project(conn, "Active Project")
        deleted_id = create_project(conn, "Deleted Project")
        soft_delete(conn, "projects", deleted_id)

        deleted = get_deleted(conn, "projects")
        assert len(deleted) == 1
        assert deleted[0]["id"] == deleted_id

    def test_get_deleted_with_limit(self, conn):
        """Get deleted respects limit parameter."""
        for i in range(10):
            pid = create_project(conn, f"Project {i}")
            soft_delete(conn, "projects", pid)

        deleted = get_deleted(conn, "projects", limit=5)
        assert len(deleted) == 5

    def test_get_deleted_with_offset(self, conn):
        """Get deleted supports pagination with offset."""
        ids = []
        for i in range(10):
            pid = create_project(conn, f"Project {i}")
            soft_delete(conn, "projects", pid)
            ids.append(pid)

        deleted = get_deleted(conn, "projects", limit=5, offset=5)
        assert len(deleted) == 5


class TestCountDeleted:
    """Test counting deleted records."""

    def test_count_deleted(self, conn):
        """Count deleted returns correct count."""
        for i in range(5):
            pid = create_project(conn, f"Project {i}")
            if i % 2 == 0:
                soft_delete(conn, "projects", pid)

        count = count_deleted(conn, "projects")
        assert count == 3  # 0, 2, 4


class TestDeletionStats:
    """Test deletion statistics."""

    def test_get_deletion_stats(self, conn):
        """Get stats for all tables."""
        # Create some data
        project_id = create_project(conn, "Active Project")
        deleted_id = create_project(conn, "Deleted Project")
        soft_delete(conn, "projects", deleted_id)

        stats = get_deletion_stats(conn)

        assert "projects" in stats
        assert stats["projects"]["total"] == 2
        assert stats["projects"]["active"] == 1
        assert stats["projects"]["deleted"] == 1


class TestBuildActiveFilter:
    """Test SQL filter builder."""

    def test_build_filter_no_alias(self):
        """Build filter without table alias."""
        filter_sql = build_active_filter()
        assert filter_sql == "deleted_at IS NULL"

    def test_build_filter_with_alias(self):
        """Build filter with table alias."""
        filter_sql = build_active_filter("p")
        assert filter_sql == "p.deleted_at IS NULL"


class TestAddSoftDeleteColumns:
    """Test adding soft delete columns to existing tables."""

    def test_add_columns_to_new_table(self, db_path):
        """Add soft delete columns to table without them."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create table without soft delete columns
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """
        )
        conn.commit()

        result = add_soft_delete_columns(conn, "test_table")
        assert result is True

        # Verify columns exist
        cursor = conn.execute("PRAGMA table_info(test_table)")
        columns = {row["name"] for row in cursor.fetchall()}
        assert "deleted_at" in columns
        assert "deleted_by" in columns
        conn.close()

    def test_add_columns_idempotent(self, conn):
        """Adding columns to table that already has them is safe."""
        result = add_soft_delete_columns(conn, "projects")
        assert result is False  # Columns already exist


class TestCascadeSoftDelete:
    """Test cascade soft delete functionality."""

    def test_cascade_soft_delete(self, conn):
        """Cascade delete parent and children."""
        project_id = create_project(conn, "Test Project")
        feature1 = create_feature(conn, project_id, "Feature 1")
        feature2 = create_feature(conn, project_id, "Feature 2")

        result = cascade_soft_delete(
            conn, "projects", project_id, [("features", "project_id")], deleted_by="admin"
        )

        assert result["projects"] == 1
        assert result["features"] == 2

        # Verify parent deleted
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert project["deleted_at"] is not None

        # Verify children deleted
        features = conn.execute(
            "SELECT * FROM features WHERE project_id = ?", (project_id,)
        ).fetchall()
        for f in features:
            assert f["deleted_at"] is not None
            assert f["deleted_by"] == "admin"


class TestSoftDeleteQueries:
    """Test querying with soft delete filters."""

    def test_filter_excludes_deleted(self, conn):
        """Standard queries exclude deleted records."""
        active_id = create_project(conn, "Active")
        deleted_id = create_project(conn, "Deleted")
        soft_delete(conn, "projects", deleted_id)

        rows = conn.execute("SELECT * FROM projects WHERE deleted_at IS NULL").fetchall()

        assert len(rows) == 1
        assert rows[0]["id"] == active_id

    def test_include_deleted_query(self, conn):
        """Query can include deleted records."""
        active_id = create_project(conn, "Active")
        deleted_id = create_project(conn, "Deleted")
        soft_delete(conn, "projects", deleted_id)

        rows = conn.execute("SELECT * FROM projects").fetchall()

        assert len(rows) == 2

    def test_deleted_only_query(self, conn):
        """Query can target only deleted records."""
        active_id = create_project(conn, "Active")
        deleted_id = create_project(conn, "Deleted")
        soft_delete(conn, "projects", deleted_id)

        rows = conn.execute("SELECT * FROM projects WHERE deleted_at IS NOT NULL").fetchall()

        assert len(rows) == 1
        assert rows[0]["id"] == deleted_id


class TestEdgeCases:
    """Test edge cases for soft delete."""

    def test_delete_restore_delete(self, conn):
        """Record can be deleted, restored, and deleted again."""
        project_id = create_project(conn, "Test Project")

        # First delete
        soft_delete(conn, "projects", project_id)
        row = conn.execute("SELECT deleted_at FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row["deleted_at"] is not None

        # Restore
        restore(conn, "projects", project_id)
        row = conn.execute("SELECT deleted_at FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row["deleted_at"] is None

        # Second delete
        soft_delete(conn, "projects", project_id)
        row = conn.execute("SELECT deleted_at FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert row["deleted_at"] is not None

    def test_foreign_key_references_preserved(self, conn):
        """Soft delete preserves foreign key references."""
        project_id = create_project(conn, "Test Project")
        feature_id = create_feature(conn, project_id, "Feature")

        soft_delete(conn, "projects", project_id)

        # Feature still references the project
        feature = conn.execute("SELECT * FROM features WHERE id = ?", (feature_id,)).fetchone()
        assert feature["project_id"] == project_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
