#!/usr/bin/env python3
"""
Session Groups Integration Tests

Tests for Session Groups Management system.

Tests the full integration of:
- Session grouping by project
- Group CRUD operations
- Session membership management
- Collapsible group state
- Session sorting and filtering
- Group statistics
- Tmux integration
"""

import json
import pytest
import sqlite3
from datetime import datetime
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with session groups schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create session groups tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS session_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT,
            description TEXT,
            color TEXT DEFAULT '#3b82f6',
            icon TEXT,
            collapsed BOOLEAN DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmux_name TEXT NOT NULL UNIQUE,
            display_name TEXT,
            group_id INTEGER,
            status TEXT DEFAULT 'stopped',
            role TEXT DEFAULT 'worker',
            last_activity TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES session_groups(id)
        );

        CREATE TABLE IF NOT EXISTS group_preferences (
            group_id INTEGER PRIMARY KEY,
            auto_expand BOOLEAN DEFAULT 0,
            show_inactive BOOLEAN DEFAULT 1,
            sort_by TEXT DEFAULT 'name',
            FOREIGN KEY (group_id) REFERENCES session_groups(id)
        );

        CREATE INDEX idx_sessions_group ON sessions(group_id);
        CREATE INDEX idx_sessions_status ON sessions(status);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestGroupCRUD:
    """Test group CRUD operations."""

    def test_create_group(self, test_db):
        """Test creating a session group."""
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, description, color)
            VALUES (?, ?, ?, ?)
        """,
            ("feature-auth", "Authentication Feature", "Auth system development", "#10b981"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Verify created
        row = test_db.execute("SELECT * FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row is not None
        assert row[1] == "feature-auth"
        assert row[2] == "Authentication Feature"
        assert row[4] == "#10b981"

    def test_get_group(self, test_db):
        """Test retrieving a group."""
        # Insert group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("project-api", "API Development"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Retrieve
        row = test_db.execute("SELECT * FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row is not None
        assert row[1] == "project-api"
        assert row[2] == "API Development"

    def test_update_group(self, test_db):
        """Test updating group properties."""
        # Insert group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, description)
            VALUES (?, ?, ?)
        """,
            ("frontend", "Frontend Work", "UI development"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Update
        test_db.execute(
            """
            UPDATE session_groups
            SET display_name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            ("Frontend Development", "React UI components", group_id),
        )
        test_db.commit()

        # Verify updated
        row = test_db.execute(
            "SELECT display_name, description FROM session_groups WHERE id = ?", (group_id,)
        ).fetchone()

        assert row[0] == "Frontend Development"
        assert row[1] == "React UI components"

    def test_delete_group(self, test_db):
        """Test deleting a group."""
        # Insert group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("old-project", "Old Project"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Delete
        test_db.execute("DELETE FROM session_groups WHERE id = ?", (group_id,))
        test_db.commit()

        # Verify deleted
        row = test_db.execute("SELECT * FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row is None

    def test_list_all_groups(self, test_db):
        """Test listing all groups."""
        # Insert multiple groups
        test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, sort_order)
            VALUES ('backend', 'Backend Services', 1),
                   ('frontend', 'Frontend Apps', 2),
                   ('testing', 'Test Suite', 3)
        """
        )
        test_db.commit()

        # List all ordered
        rows = test_db.execute(
            "SELECT name FROM session_groups ORDER BY sort_order"
        ).fetchall()

        assert len(rows) == 3
        assert rows[0][0] == "backend"
        assert rows[1][0] == "frontend"
        assert rows[2][0] == "testing"


class TestSessionMembership:
    """Test session membership in groups."""

    def test_add_session_to_group(self, test_db):
        """Test adding a session to a group."""
        # Create group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("api-dev", "API Development"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Add session
        cursor = test_db.execute(
            """
            INSERT INTO sessions (tmux_name, display_name, group_id, status)
            VALUES (?, ?, ?, ?)
        """,
            ("claude-api-worker-1", "API Worker 1", group_id, "running"),
        )
        session_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

        assert row is not None
        assert row[1] == "claude-api-worker-1"
        assert row[3] == group_id

    def test_get_sessions_in_group(self, test_db):
        """Test retrieving all sessions in a group."""
        # Create group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("database", "Database Work"),
        )
        group_id = cursor.lastrowid

        # Add multiple sessions
        test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id, status)
            VALUES ('session-1', ?, 'running'),
                   ('session-2', ?, 'running'),
                   ('session-3', ?, 'stopped')
        """,
            (group_id, group_id, group_id),
        )
        test_db.commit()

        # Get sessions
        rows = test_db.execute(
            "SELECT * FROM sessions WHERE group_id = ?", (group_id,)
        ).fetchall()

        assert len(rows) == 3

    def test_move_session_between_groups(self, test_db):
        """Test moving a session from one group to another."""
        # Create groups
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES ('group-a', 'Group A'), ('group-b', 'Group B')
        """
        )
        test_db.commit()

        group_a_id = test_db.execute("SELECT id FROM session_groups WHERE name = 'group-a'").fetchone()[0]
        group_b_id = test_db.execute("SELECT id FROM session_groups WHERE name = 'group-b'").fetchone()[0]

        # Create session in group A
        cursor = test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id)
            VALUES (?, ?)
        """,
            ("movable-session", group_a_id),
        )
        session_id = cursor.lastrowid
        test_db.commit()

        # Move to group B
        test_db.execute(
            """
            UPDATE sessions
            SET group_id = ?
            WHERE id = ?
        """,
            (group_b_id, session_id),
        )
        test_db.commit()

        # Verify moved
        row = test_db.execute("SELECT group_id FROM sessions WHERE id = ?", (session_id,)).fetchone()

        assert row[0] == group_b_id

    def test_remove_session_from_group(self, test_db):
        """Test removing a session from a group (set to NULL)."""
        # Create group and session
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("temp-group", "Temporary Group"),
        )
        group_id = cursor.lastrowid

        cursor = test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id)
            VALUES (?, ?)
        """,
            ("temp-session", group_id),
        )
        session_id = cursor.lastrowid
        test_db.commit()

        # Remove from group
        test_db.execute(
            """
            UPDATE sessions
            SET group_id = NULL
            WHERE id = ?
        """,
            (session_id,),
        )
        test_db.commit()

        # Verify removed
        row = test_db.execute("SELECT group_id FROM sessions WHERE id = ?", (session_id,)).fetchone()

        assert row[0] is None


class TestCollapsibleState:
    """Test collapsible group state management."""

    def test_toggle_collapsed(self, test_db):
        """Test toggling group collapsed state."""
        # Create group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, collapsed)
            VALUES (?, ?, ?)
        """,
            ("toggleable", "Toggleable Group", 0),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Collapse
        test_db.execute(
            """
            UPDATE session_groups
            SET collapsed = 1
            WHERE id = ?
        """,
            (group_id,),
        )
        test_db.commit()

        # Verify collapsed
        row = test_db.execute("SELECT collapsed FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row[0] == 1

        # Expand
        test_db.execute(
            """
            UPDATE session_groups
            SET collapsed = 0
            WHERE id = ?
        """,
            (group_id,),
        )
        test_db.commit()

        # Verify expanded
        row = test_db.execute("SELECT collapsed FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row[0] == 0

    def test_persist_collapsed_state(self, test_db):
        """Test collapsed state persists across queries."""
        # Create collapsed group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, collapsed)
            VALUES (?, ?, ?)
        """,
            ("persistent", "Persistent Group", 1),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Retrieve in separate query
        row = test_db.execute("SELECT collapsed FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row[0] == 1  # Should still be collapsed


class TestGroupSorting:
    """Test group sorting and ordering."""

    def test_custom_sort_order(self, test_db):
        """Test custom sort order for groups."""
        # Create groups with sort order
        test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, sort_order)
            VALUES ('low', 'Low Priority', 3),
                   ('high', 'High Priority', 1),
                   ('medium', 'Medium Priority', 2)
        """
        )
        test_db.commit()

        # Retrieve ordered
        rows = test_db.execute(
            "SELECT name FROM session_groups ORDER BY sort_order"
        ).fetchall()

        assert rows[0][0] == "high"
        assert rows[1][0] == "medium"
        assert rows[2][0] == "low"

    def test_reorder_groups(self, test_db):
        """Test reordering groups."""
        # Create groups
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, sort_order)
            VALUES ('group-1', 'Group 1', 1)
        """
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Update sort order
        test_db.execute(
            """
            UPDATE session_groups
            SET sort_order = 5
            WHERE id = ?
        """,
            (group_id,),
        )
        test_db.commit()

        # Verify updated
        row = test_db.execute("SELECT sort_order FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row[0] == 5


class TestGroupStatistics:
    """Test group statistics calculations."""

    def test_count_sessions_per_group(self, test_db):
        """Test counting sessions in each group."""
        # Create groups
        test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES ('group-a', 'Group A'), ('group-b', 'Group B')
        """
        )
        test_db.commit()

        group_a = test_db.execute("SELECT id FROM session_groups WHERE name = 'group-a'").fetchone()[0]
        group_b = test_db.execute("SELECT id FROM session_groups WHERE name = 'group-b'").fetchone()[0]

        # Add sessions
        test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id)
            VALUES ('s1', ?), ('s2', ?), ('s3', ?)
        """,
            (group_a, group_a, group_b),
        )
        test_db.commit()

        # Count sessions
        count_a = test_db.execute("SELECT COUNT(*) FROM sessions WHERE group_id = ?", (group_a,)).fetchone()[0]

        count_b = test_db.execute("SELECT COUNT(*) FROM sessions WHERE group_id = ?", (group_b,)).fetchone()[0]

        assert count_a == 2
        assert count_b == 1

    def test_count_active_sessions(self, test_db):
        """Test counting only active sessions."""
        # Create group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("active-group", "Active Group"),
        )
        group_id = cursor.lastrowid

        # Add sessions with different statuses
        test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id, status)
            VALUES ('s1', ?, 'running'),
                   ('s2', ?, 'running'),
                   ('s3', ?, 'stopped')
        """,
            (group_id, group_id, group_id),
        )
        test_db.commit()

        # Count active
        active_count = test_db.execute(
            "SELECT COUNT(*) FROM sessions WHERE group_id = ? AND status = 'running'", (group_id,)
        ).fetchone()[0]

        assert active_count == 2

    def test_get_group_activity_summary(self, test_db):
        """Test getting group activity summary."""
        # Create group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("summary-group", "Summary Group"),
        )
        group_id = cursor.lastrowid

        # Add sessions
        now = datetime.now()
        test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id, status, last_activity)
            VALUES ('s1', ?, 'running', ?),
                   ('s2', ?, 'running', ?),
                   ('s3', ?, 'stopped', NULL)
        """,
            (group_id, now.isoformat(), group_id, now.isoformat(), group_id),
        )
        test_db.commit()

        # Get summary
        total = test_db.execute("SELECT COUNT(*) FROM sessions WHERE group_id = ?", (group_id,)).fetchone()[0]

        active = test_db.execute(
            "SELECT COUNT(*) FROM sessions WHERE group_id = ? AND status = 'running'", (group_id,)
        ).fetchone()[0]

        assert total == 3
        assert active == 2


class TestGroupPreferences:
    """Test group preferences."""

    def test_set_group_preferences(self, test_db):
        """Test setting group preferences."""
        # Create group
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("pref-group", "Preferences Group"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Set preferences
        test_db.execute(
            """
            INSERT INTO group_preferences (group_id, auto_expand, show_inactive, sort_by)
            VALUES (?, ?, ?, ?)
        """,
            (group_id, 1, 0, "status"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT auto_expand, show_inactive, sort_by FROM group_preferences WHERE group_id = ?",
            (group_id,),
        ).fetchone()

        assert row[0] == 1  # auto_expand
        assert row[1] == 0  # show_inactive
        assert row[2] == "status"

    def test_update_group_preferences(self, test_db):
        """Test updating group preferences."""
        # Create group and preferences
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("update-pref", "Update Preferences"),
        )
        group_id = cursor.lastrowid

        test_db.execute(
            """
            INSERT INTO group_preferences (group_id, auto_expand)
            VALUES (?, ?)
        """,
            (group_id, 0),
        )
        test_db.commit()

        # Update
        test_db.execute(
            """
            UPDATE group_preferences
            SET auto_expand = 1
            WHERE group_id = ?
        """,
            (group_id,),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT auto_expand FROM group_preferences WHERE group_id = ?", (group_id,)
        ).fetchone()

        assert row[0] == 1


class TestGroupFiltering:
    """Test filtering groups and sessions."""

    def test_filter_groups_by_status(self, test_db):
        """Test filtering groups based on session status."""
        # Create groups
        test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES ('active-group', 'Active'), ('inactive-group', 'Inactive')
        """
        )
        test_db.commit()

        active_id = test_db.execute(
            "SELECT id FROM session_groups WHERE name = 'active-group'"
        ).fetchone()[0]
        inactive_id = test_db.execute(
            "SELECT id FROM session_groups WHERE name = 'inactive-group'"
        ).fetchone()[0]

        # Add sessions
        test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id, status)
            VALUES ('s1', ?, 'running'),
                   ('s2', ?, 'stopped')
        """,
            (active_id, inactive_id),
        )
        test_db.commit()

        # Get groups with running sessions
        groups = test_db.execute(
            """
            SELECT DISTINCT g.name
            FROM session_groups g
            JOIN sessions s ON s.group_id = g.id
            WHERE s.status = 'running'
        """
        ).fetchall()

        assert len(groups) == 1
        assert groups[0][0] == "active-group"

    def test_get_ungrouped_sessions(self, test_db):
        """Test retrieving sessions not in any group."""
        # Create some sessions with and without groups
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name)
            VALUES (?, ?)
        """,
            ("grouped", "Grouped"),
        )
        group_id = cursor.lastrowid

        test_db.execute(
            """
            INSERT INTO sessions (tmux_name, group_id)
            VALUES ('grouped-session', ?),
                   ('orphan-session', NULL)
        """,
            (group_id,),
        )
        test_db.commit()

        # Get ungrouped
        ungrouped = test_db.execute("SELECT * FROM sessions WHERE group_id IS NULL").fetchall()

        assert len(ungrouped) == 1
        assert ungrouped[0][1] == "orphan-session"


class TestGroupVisualization:
    """Test group visualization properties."""

    def test_set_group_color(self, test_db):
        """Test setting group color."""
        # Create group with color
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, color)
            VALUES (?, ?, ?)
        """,
            ("colored-group", "Colored Group", "#ef4444"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Verify color
        row = test_db.execute("SELECT color FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row[0] == "#ef4444"

    def test_set_group_icon(self, test_db):
        """Test setting group icon."""
        # Create group with icon
        cursor = test_db.execute(
            """
            INSERT INTO session_groups (name, display_name, icon)
            VALUES (?, ?, ?)
        """,
            ("icon-group", "Icon Group", "🚀"),
        )
        group_id = cursor.lastrowid
        test_db.commit()

        # Verify icon
        row = test_db.execute("SELECT icon FROM session_groups WHERE id = ?", (group_id,)).fetchone()

        assert row[0] == "🚀"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
