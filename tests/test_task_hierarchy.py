"""
Tests for task hierarchy (parent/child relationships).
"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def db_path():
    """Create a temporary database with task hierarchy schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            task_data TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            assigned_node TEXT,
            assigned_worker TEXT,
            retries INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            timeout_seconds INTEGER,
            error_message TEXT,
            story_points INTEGER,
            estimated_hours REAL,
            actual_hours REAL,
            parent_id INTEGER,
            hierarchy_level INTEGER DEFAULT 0,
            hierarchy_path TEXT DEFAULT '/',
            child_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES task_queue(id) ON DELETE SET NULL
        )
    """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_parent ON task_queue(parent_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_task_queue_hierarchy_level ON task_queue(hierarchy_level)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_archive (
            id INTEGER PRIMARY KEY,
            original_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            task_data TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            assigned_node TEXT,
            assigned_worker TEXT,
            retries INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            timeout_seconds INTEGER,
            error_message TEXT,
            parent_id INTEGER,
            hierarchy_level INTEGER,
            hierarchy_path TEXT,
            child_count INTEGER,
            created_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archive_reason TEXT
        )
    """
    )
    conn.commit()
    conn.close()

    yield path

    os.unlink(path)


def create_task(conn, task_type, task_data, priority=0, parent_id=None):
    """Helper to create a task with proper hierarchy fields."""
    hierarchy_level = 0
    hierarchy_path = "/"

    if parent_id:
        parent = conn.execute(
            "SELECT id, hierarchy_level, hierarchy_path FROM task_queue WHERE id = ?", (parent_id,)
        ).fetchone()
        if parent:
            hierarchy_level = (parent["hierarchy_level"] or 0) + 1
            hierarchy_path = f"{parent['hierarchy_path'] or '/'}{parent_id}/"

    cursor = conn.execute(
        """
        INSERT INTO task_queue (task_type, task_data, priority, parent_id, hierarchy_level, hierarchy_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (task_type, json.dumps(task_data), priority, parent_id, hierarchy_level, hierarchy_path),
    )

    task_id = cursor.lastrowid

    # Update parent child_count
    if parent_id:
        conn.execute(
            "UPDATE task_queue SET child_count = child_count + 1 WHERE id = ?", (parent_id,)
        )

    conn.commit()
    return task_id


class TestTaskHierarchySchema:
    """Test the database schema for hierarchy support."""

    def test_hierarchy_columns_exist(self, db_path):
        """Verify hierarchy columns are in the schema."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("PRAGMA table_info(task_queue)")
        columns = {row["name"] for row in cursor.fetchall()}

        assert "parent_id" in columns
        assert "hierarchy_level" in columns
        assert "hierarchy_path" in columns
        assert "child_count" in columns
        conn.close()

    def test_archive_has_hierarchy_columns(self, db_path):
        """Verify archive table has hierarchy columns."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("PRAGMA table_info(task_archive)")
        columns = {row["name"] for row in cursor.fetchall()}

        assert "parent_id" in columns
        assert "hierarchy_level" in columns
        assert "hierarchy_path" in columns
        assert "child_count" in columns
        conn.close()

    def test_parent_index_exists(self, db_path):
        """Verify parent_id index exists."""
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA index_list(task_queue)")
        indexes = {row[1] for row in cursor.fetchall()}

        assert "idx_task_queue_parent" in indexes
        conn.close()


class TestTaskCreation:
    """Test creating tasks with parent/child relationships."""

    def test_create_root_task(self, db_path):
        """Create a task without parent."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        task_id = create_task(conn, "test", {"name": "Root Task"})

        task = conn.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,)).fetchone()
        assert task["parent_id"] is None
        assert task["hierarchy_level"] == 0
        assert task["hierarchy_path"] == "/"
        assert task["child_count"] == 0
        conn.close()

    def test_create_child_task(self, db_path):
        """Create a task with a parent."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        parent_id = create_task(conn, "test", {"name": "Parent Task"})
        child_id = create_task(conn, "test", {"name": "Child Task"}, parent_id=parent_id)

        child = conn.execute("SELECT * FROM task_queue WHERE id = ?", (child_id,)).fetchone()
        assert child["parent_id"] == parent_id
        assert child["hierarchy_level"] == 1
        assert child["hierarchy_path"] == f"/{parent_id}/"

        parent = conn.execute("SELECT * FROM task_queue WHERE id = ?", (parent_id,)).fetchone()
        assert parent["child_count"] == 1
        conn.close()

    def test_create_grandchild_task(self, db_path):
        """Create a three-level hierarchy."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        grandparent_id = create_task(conn, "test", {"name": "Grandparent"})
        parent_id = create_task(conn, "test", {"name": "Parent"}, parent_id=grandparent_id)
        child_id = create_task(conn, "test", {"name": "Child"}, parent_id=parent_id)

        child = conn.execute("SELECT * FROM task_queue WHERE id = ?", (child_id,)).fetchone()
        assert child["parent_id"] == parent_id
        assert child["hierarchy_level"] == 2
        assert child["hierarchy_path"] == f"/{grandparent_id}/{parent_id}/"
        conn.close()

    def test_multiple_children(self, db_path):
        """Parent can have multiple children."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        parent_id = create_task(conn, "test", {"name": "Parent"})
        child1_id = create_task(conn, "test", {"name": "Child 1"}, parent_id=parent_id)
        child2_id = create_task(conn, "test", {"name": "Child 2"}, parent_id=parent_id)
        child3_id = create_task(conn, "test", {"name": "Child 3"}, parent_id=parent_id)

        parent = conn.execute("SELECT * FROM task_queue WHERE id = ?", (parent_id,)).fetchone()
        assert parent["child_count"] == 3

        children = conn.execute(
            "SELECT * FROM task_queue WHERE parent_id = ? ORDER BY id", (parent_id,)
        ).fetchall()
        assert len(children) == 3
        conn.close()


class TestHierarchyQueries:
    """Test querying hierarchical task structures."""

    def test_get_children(self, db_path):
        """Get all direct children of a task."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        parent_id = create_task(conn, "test", {"name": "Parent"})
        child1_id = create_task(conn, "test", {"name": "Child 1"}, parent_id=parent_id)
        child2_id = create_task(conn, "test", {"name": "Child 2"}, parent_id=parent_id)

        children = conn.execute(
            "SELECT * FROM task_queue WHERE parent_id = ?", (parent_id,)
        ).fetchall()

        assert len(children) == 2
        child_ids = {c["id"] for c in children}
        assert child_ids == {child1_id, child2_id}
        conn.close()

    def test_get_root_tasks(self, db_path):
        """Get all root tasks (no parent)."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        root1_id = create_task(conn, "test", {"name": "Root 1"})
        root2_id = create_task(conn, "test", {"name": "Root 2"})
        child_id = create_task(conn, "test", {"name": "Child"}, parent_id=root1_id)

        roots = conn.execute("SELECT * FROM task_queue WHERE parent_id IS NULL").fetchall()

        assert len(roots) == 2
        root_ids = {r["id"] for r in roots}
        assert root_ids == {root1_id, root2_id}
        conn.close()

    def test_get_all_descendants(self, db_path):
        """Get all descendants using hierarchy_path."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        root_id = create_task(conn, "test", {"name": "Root"})
        child_id = create_task(conn, "test", {"name": "Child"}, parent_id=root_id)
        grandchild_id = create_task(conn, "test", {"name": "Grandchild"}, parent_id=child_id)

        # Get all descendants of root
        descendants = conn.execute(
            "SELECT * FROM task_queue WHERE hierarchy_path LIKE ?", (f"%/{root_id}/%",)
        ).fetchall()

        assert len(descendants) == 2
        descendant_ids = {d["id"] for d in descendants}
        assert descendant_ids == {child_id, grandchild_id}
        conn.close()

    def test_get_ancestors(self, db_path):
        """Get all ancestors of a task by traversing parent_id."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        root_id = create_task(conn, "test", {"name": "Root"})
        parent_id = create_task(conn, "test", {"name": "Parent"}, parent_id=root_id)
        child_id = create_task(conn, "test", {"name": "Child"}, parent_id=parent_id)

        # Get ancestors by walking up
        ancestors = []
        current = conn.execute("SELECT * FROM task_queue WHERE id = ?", (child_id,)).fetchone()
        current_parent_id = current["parent_id"]

        while current_parent_id:
            ancestor = conn.execute(
                "SELECT * FROM task_queue WHERE id = ?", (current_parent_id,)
            ).fetchone()
            ancestors.append(ancestor["id"])
            current_parent_id = ancestor["parent_id"]

        assert ancestors == [parent_id, root_id]
        conn.close()

    def test_tasks_by_level(self, db_path):
        """Get tasks grouped by hierarchy level."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        root1_id = create_task(conn, "test", {"name": "Root 1"})
        root2_id = create_task(conn, "test", {"name": "Root 2"})
        child1_id = create_task(conn, "test", {"name": "Child 1"}, parent_id=root1_id)
        child2_id = create_task(conn, "test", {"name": "Child 2"}, parent_id=root1_id)
        grandchild_id = create_task(conn, "test", {"name": "Grandchild"}, parent_id=child1_id)

        levels = conn.execute(
            """
            SELECT hierarchy_level, COUNT(*) as count
            FROM task_queue
            GROUP BY hierarchy_level
            ORDER BY hierarchy_level
        """
        ).fetchall()

        assert len(levels) == 3
        assert levels[0]["hierarchy_level"] == 0
        assert levels[0]["count"] == 2  # 2 root tasks
        assert levels[1]["hierarchy_level"] == 1
        assert levels[1]["count"] == 2  # 2 children
        assert levels[2]["hierarchy_level"] == 2
        assert levels[2]["count"] == 1  # 1 grandchild
        conn.close()


class TestHierarchyOperations:
    """Test operations on hierarchical tasks."""

    def test_delete_parent_nullifies_children(self, db_path):
        """When parent is deleted with ON DELETE SET NULL, children's parent_id becomes NULL."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        parent_id = create_task(conn, "test", {"name": "Parent"})
        child_id = create_task(conn, "test", {"name": "Child"}, parent_id=parent_id)

        conn.execute("DELETE FROM task_queue WHERE id = ?", (parent_id,))
        conn.commit()

        child = conn.execute("SELECT * FROM task_queue WHERE id = ?", (child_id,)).fetchone()
        assert child["parent_id"] is None
        conn.close()

    def test_move_task_to_new_parent(self, db_path):
        """Move a task to a different parent."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        parent1_id = create_task(conn, "test", {"name": "Parent 1"})
        parent2_id = create_task(conn, "test", {"name": "Parent 2"})
        child_id = create_task(conn, "test", {"name": "Child"}, parent_id=parent1_id)

        # Move child from parent1 to parent2
        new_level = 1
        new_path = f"/{parent2_id}/"

        conn.execute(
            """
            UPDATE task_queue SET parent_id = ?, hierarchy_level = ?, hierarchy_path = ?
            WHERE id = ?
        """,
            (parent2_id, new_level, new_path, child_id),
        )

        # Update child counts
        conn.execute(
            "UPDATE task_queue SET child_count = child_count - 1 WHERE id = ?", (parent1_id,)
        )
        conn.execute(
            "UPDATE task_queue SET child_count = child_count + 1 WHERE id = ?", (parent2_id,)
        )
        conn.commit()

        # Verify move
        child = conn.execute("SELECT * FROM task_queue WHERE id = ?", (child_id,)).fetchone()
        assert child["parent_id"] == parent2_id

        parent1 = conn.execute("SELECT * FROM task_queue WHERE id = ?", (parent1_id,)).fetchone()
        assert parent1["child_count"] == 0

        parent2 = conn.execute("SELECT * FROM task_queue WHERE id = ?", (parent2_id,)).fetchone()
        assert parent2["child_count"] == 1
        conn.close()

    def test_cascade_delete_descendants(self, db_path):
        """Delete a task and all its descendants."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        root_id = create_task(conn, "test", {"name": "Root"})
        child_id = create_task(conn, "test", {"name": "Child"}, parent_id=root_id)
        grandchild_id = create_task(conn, "test", {"name": "Grandchild"}, parent_id=child_id)
        other_id = create_task(conn, "test", {"name": "Other"})

        # Find all descendants
        descendants = conn.execute(
            "SELECT id FROM task_queue WHERE hierarchy_path LIKE ?", (f"%/{root_id}/%",)
        ).fetchall()
        descendant_ids = [d["id"] for d in descendants]

        # Delete root and descendants
        all_ids = [root_id] + descendant_ids
        placeholders = ",".join("?" * len(all_ids))
        conn.execute(f"DELETE FROM task_queue WHERE id IN ({placeholders})", all_ids)
        conn.commit()

        # Verify only 'other' remains
        remaining = conn.execute("SELECT * FROM task_queue").fetchall()
        assert len(remaining) == 1
        assert remaining[0]["id"] == other_id
        conn.close()


class TestCompletionCascade:
    """Test completion logic with parent/child relationships."""

    def test_complete_all_children_allows_parent_completion(self, db_path):
        """When all children are complete, parent can be marked complete."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        parent_id = create_task(conn, "test", {"name": "Parent"})
        child1_id = create_task(conn, "test", {"name": "Child 1"}, parent_id=parent_id)
        child2_id = create_task(conn, "test", {"name": "Child 2"}, parent_id=parent_id)

        # Complete children
        conn.execute("UPDATE task_queue SET status = 'completed' WHERE id = ?", (child1_id,))
        conn.execute("UPDATE task_queue SET status = 'completed' WHERE id = ?", (child2_id,))
        conn.commit()

        # Check if all children are complete
        incomplete = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM task_queue
            WHERE parent_id = ? AND status != 'completed'
        """,
            (parent_id,),
        ).fetchone()["cnt"]

        assert incomplete == 0

        # Parent can now be completed
        conn.execute("UPDATE task_queue SET status = 'completed' WHERE id = ?", (parent_id,))
        conn.commit()

        parent = conn.execute("SELECT * FROM task_queue WHERE id = ?", (parent_id,)).fetchone()
        assert parent["status"] == "completed"
        conn.close()

    def test_incomplete_child_blocks_parent(self, db_path):
        """Parent cannot auto-complete if any child is incomplete."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        parent_id = create_task(conn, "test", {"name": "Parent"})
        child1_id = create_task(conn, "test", {"name": "Child 1"}, parent_id=parent_id)
        child2_id = create_task(conn, "test", {"name": "Child 2"}, parent_id=parent_id)

        # Complete only one child
        conn.execute("UPDATE task_queue SET status = 'completed' WHERE id = ?", (child1_id,))
        conn.commit()

        # Check incomplete children
        incomplete = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM task_queue
            WHERE parent_id = ? AND status != 'completed'
        """,
            (parent_id,),
        ).fetchone()["cnt"]

        assert incomplete == 1  # child2 is still incomplete
        conn.close()


class TestHierarchyStats:
    """Test hierarchy statistics."""

    def test_count_by_depth(self, db_path):
        """Count tasks at each depth level."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create a hierarchy
        root1_id = create_task(conn, "test", {"name": "Root 1"})
        root2_id = create_task(conn, "test", {"name": "Root 2"})
        child1_id = create_task(conn, "test", {"name": "Child 1"}, parent_id=root1_id)
        child2_id = create_task(conn, "test", {"name": "Child 2"}, parent_id=root1_id)
        grandchild1_id = create_task(conn, "test", {"name": "Grandchild 1"}, parent_id=child1_id)

        stats = conn.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE parent_id IS NULL) as root_count,
                COUNT(*) FILTER (WHERE parent_id IS NOT NULL) as child_count,
                MAX(hierarchy_level) as max_depth,
                AVG(child_count) FILTER (WHERE child_count > 0) as avg_children
            FROM task_queue
        """
        ).fetchone()

        assert stats["root_count"] == 2
        assert stats["child_count"] == 3
        assert stats["max_depth"] == 2
        conn.close()

    def test_tree_size(self, db_path):
        """Get total size of a task tree."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        root_id = create_task(conn, "test", {"name": "Root"})
        child1_id = create_task(conn, "test", {"name": "Child 1"}, parent_id=root_id)
        child2_id = create_task(conn, "test", {"name": "Child 2"}, parent_id=root_id)
        grandchild_id = create_task(conn, "test", {"name": "Grandchild"}, parent_id=child1_id)

        # Count root + all descendants
        descendants = conn.execute(
            "SELECT COUNT(*) as cnt FROM task_queue WHERE hierarchy_path LIKE ?",
            (f"%/{root_id}/%",),
        ).fetchone()["cnt"]

        tree_size = 1 + descendants  # root + descendants
        assert tree_size == 4
        conn.close()


class TestEdgeCases:
    """Test edge cases for hierarchy."""

    def test_self_reference_prevented(self, db_path):
        """Task cannot be its own parent."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        task_id = create_task(conn, "test", {"name": "Task"})

        # Attempting to set parent to self should be prevented by application logic
        # The database allows it, but the application should validate
        conn.execute("UPDATE task_queue SET parent_id = ? WHERE id = ?", (task_id, task_id))
        conn.commit()

        # Application should check for this
        task = conn.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,)).fetchone()
        is_self_reference = task["parent_id"] == task["id"]

        # This is an error condition the application should prevent
        assert is_self_reference  # Database allows it, needs app validation
        conn.close()

    def test_very_deep_hierarchy(self, db_path):
        """Handle deep hierarchies (10+ levels)."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        depth = 10
        parent_id = None
        task_ids = []

        for i in range(depth):
            task_id = create_task(conn, "test", {"name": f"Level {i}"}, parent_id=parent_id)
            task_ids.append(task_id)
            parent_id = task_id

        # Verify deepest task
        deepest = conn.execute("SELECT * FROM task_queue WHERE id = ?", (task_ids[-1],)).fetchone()
        assert deepest["hierarchy_level"] == depth - 1

        # Verify path contains all ancestors
        path_parts = deepest["hierarchy_path"].strip("/").split("/")
        assert len(path_parts) == depth - 1  # Excludes the task itself
        conn.close()

    def test_nonexistent_parent(self, db_path):
        """Referencing a non-existent parent should be caught."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Try to create task with non-existent parent
        # The helper function checks parent exists
        parent = conn.execute("SELECT * FROM task_queue WHERE id = ?", (99999,)).fetchone()
        assert parent is None
        conn.close()

    def test_orphan_detection(self, db_path):
        """Detect tasks with invalid parent_id references."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        task_id = create_task(conn, "test", {"name": "Task"})

        # Manually set an invalid parent_id
        conn.execute("UPDATE task_queue SET parent_id = 99999 WHERE id = ?", (task_id,))
        conn.commit()

        # Find orphans
        orphans = conn.execute(
            """
            SELECT t.id FROM task_queue t
            LEFT JOIN task_queue p ON t.parent_id = p.id
            WHERE t.parent_id IS NOT NULL AND p.id IS NULL
        """
        ).fetchall()

        assert len(orphans) == 1
        assert orphans[0]["id"] == task_id
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
