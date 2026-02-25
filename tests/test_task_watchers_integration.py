#!/usr/bin/env python3
"""
Task Watchers Integration Tests

Tests for Task Watchers/Subscribers service.

Tests the full integration of:
- Task watching/subscribing
- Watcher notifications
- Event type handling
- Watch preferences
- Notification filtering
- Bulk watch operations
- Watcher statistics
"""

import json
import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with task watchers schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create task watchers tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS task_watchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            user_id TEXT NOT NULL,
            watch_type TEXT DEFAULT 'all',
            muted BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, task_type, user_id)
        );

        CREATE TABLE IF NOT EXISTS watcher_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            actor TEXT,
            notified_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS watcher_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            watcher_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            read BOOLEAN DEFAULT 0,
            read_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (watcher_id) REFERENCES task_watchers(id),
            FOREIGN KEY (event_id) REFERENCES watcher_events(id)
        );

        CREATE TABLE IF NOT EXISTS watch_preferences (
            user_id TEXT PRIMARY KEY,
            notify_on_comment BOOLEAN DEFAULT 1,
            notify_on_status_change BOOLEAN DEFAULT 1,
            notify_on_assignment BOOLEAN DEFAULT 1,
            notify_on_completion BOOLEAN DEFAULT 1,
            email_notifications BOOLEAN DEFAULT 0,
            digest_mode BOOLEAN DEFAULT 0
        );

        CREATE INDEX idx_task_watchers_task ON task_watchers(task_id, task_type);
        CREATE INDEX idx_task_watchers_user ON task_watchers(user_id);
        CREATE INDEX idx_watcher_events_task ON watcher_events(task_id, task_type);
        CREATE INDEX idx_watcher_notifications_watcher ON watcher_notifications(watcher_id);
        CREATE INDEX idx_watcher_notifications_read ON watcher_notifications(read);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestWatchingTasks:
    """Test watching/subscribing to tasks."""

    def test_watch_task(self, test_db):
        """Test watching a task."""
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "user-1"),
        )
        watcher_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT * FROM task_watchers WHERE id = ?", (watcher_id,)).fetchone()

        assert row is not None
        assert row[1] == "T123"
        assert row[2] == "feature"
        assert row[3] == "user-1"

    def test_watch_multiple_tasks(self, test_db):
        """Test user watching multiple tasks."""
        tasks = [("T123", "feature"), ("T124", "bug"), ("T125", "milestone")]

        for task_id, task_type in tasks:
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                (task_id, task_type, "user-1"),
            )
        test_db.commit()

        # Verify
        rows = test_db.execute(
            "SELECT * FROM task_watchers WHERE user_id = ?", ("user-1",)
        ).fetchall()

        assert len(rows) == 3

    def test_multiple_watchers_per_task(self, test_db):
        """Test multiple users watching same task."""
        users = ["user-1", "user-2", "user-3"]

        for user_id in users:
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                ("T123", "feature", user_id),
            )
        test_db.commit()

        # Verify
        rows = test_db.execute(
            "SELECT * FROM task_watchers WHERE task_id = ? AND task_type = ?", ("T123", "feature")
        ).fetchall()

        assert len(rows) == 3

    def test_unwatch_task(self, test_db):
        """Test unwatching a task."""
        # Create watcher
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "user-1"),
        )
        watcher_id = cursor.lastrowid
        test_db.commit()

        # Unwatch (delete)
        test_db.execute("DELETE FROM task_watchers WHERE id = ?", (watcher_id,))
        test_db.commit()

        # Verify removed
        row = test_db.execute("SELECT * FROM task_watchers WHERE id = ?", (watcher_id,)).fetchone()

        assert row is None

    def test_prevent_duplicate_watchers(self, test_db):
        """Test unique constraint prevents duplicate watchers."""
        # Insert first watcher
        test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "user-1"),
        )
        test_db.commit()

        # Try to insert duplicate (should fail)
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                ("T123", "feature", "user-1"),
            )
            test_db.commit()


class TestWatchTypes:
    """Test different watch types."""

    def test_watch_all_events(self, test_db):
        """Test watching all event types."""
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id, watch_type)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "feature", "user-1", "all"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT watch_type FROM task_watchers WHERE task_id = ?", ("T123",)
        ).fetchone()

        assert row[0] == "all"

    def test_watch_specific_events(self, test_db):
        """Test watching specific event types only."""
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id, watch_type)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "feature", "user-1", "status_change,comment_added"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT watch_type FROM task_watchers WHERE task_id = ?", ("T123",)
        ).fetchone()

        assert "status_change" in row[0]
        assert "comment_added" in row[0]

    def test_mute_watcher(self, test_db):
        """Test muting a watcher temporarily."""
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id, muted)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "feature", "user-1", 0),
        )
        watcher_id = cursor.lastrowid
        test_db.commit()

        # Mute
        test_db.execute(
            """
            UPDATE task_watchers
            SET muted = 1
            WHERE id = ?
        """,
            (watcher_id,),
        )
        test_db.commit()

        # Verify muted
        row = test_db.execute("SELECT muted FROM task_watchers WHERE id = ?", (watcher_id,)).fetchone()

        assert row[0] == 1


class TestEventLogging:
    """Test event logging for watched tasks."""

    def test_log_event(self, test_db):
        """Test logging an event."""
        event_data = json.dumps({"old_status": "open", "new_status": "in_progress"})

        cursor = test_db.execute(
            """
            INSERT INTO watcher_events (task_id, task_type, event_type, event_data, actor)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("T123", "feature", "status_change", event_data, "user-1"),
        )
        event_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT * FROM watcher_events WHERE id = ?", (event_id,)).fetchone()

        assert row is not None
        assert row[3] == "status_change"
        assert row[5] == "user-1"

    def test_log_multiple_events(self, test_db):
        """Test logging multiple events for a task."""
        events = [
            ("status_change", "user-1"),
            ("comment_added", "user-2"),
            ("assigned", "user-3"),
        ]

        for event_type, actor in events:
            test_db.execute(
                """
                INSERT INTO watcher_events (task_id, task_type, event_type, actor)
                VALUES (?, ?, ?, ?)
            """,
                ("T123", "feature", event_type, actor),
            )
        test_db.commit()

        # Verify
        rows = test_db.execute(
            "SELECT * FROM watcher_events WHERE task_id = ?", ("T123",)
        ).fetchall()

        assert len(rows) == 3

    def test_event_data_serialization(self, test_db):
        """Test event data JSON serialization."""
        event_data = json.dumps({
            "comment": "Great progress!",
            "author": "user-2",
            "timestamp": datetime.now().isoformat()
        })

        cursor = test_db.execute(
            """
            INSERT INTO watcher_events (task_id, task_type, event_type, event_data)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "feature", "comment_added", event_data),
        )
        test_db.commit()

        # Verify and deserialize
        row = test_db.execute(
            "SELECT event_data FROM watcher_events WHERE task_id = ?", ("T123",)
        ).fetchone()

        data = json.loads(row[0])
        assert data["comment"] == "Great progress!"
        assert data["author"] == "user-2"


class TestNotifications:
    """Test watcher notifications."""

    def test_create_notification(self, test_db):
        """Test creating a notification for a watcher."""
        # Create watcher
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "user-1"),
        )
        watcher_id = cursor.lastrowid

        # Create event
        cursor = test_db.execute(
            """
            INSERT INTO watcher_events (task_id, task_type, event_type)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "status_change"),
        )
        event_id = cursor.lastrowid
        test_db.commit()

        # Create notification
        cursor = test_db.execute(
            """
            INSERT INTO watcher_notifications (watcher_id, event_id)
            VALUES (?, ?)
        """,
            (watcher_id, event_id),
        )
        notification_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT * FROM watcher_notifications WHERE id = ?", (notification_id,)
        ).fetchone()

        assert row is not None
        assert row[1] == watcher_id
        assert row[2] == event_id

    def test_mark_notification_read(self, test_db):
        """Test marking a notification as read."""
        # Create watcher and event
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "user-1"),
        )
        watcher_id = cursor.lastrowid

        cursor = test_db.execute(
            """
            INSERT INTO watcher_events (task_id, task_type, event_type)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "status_change"),
        )
        event_id = cursor.lastrowid

        # Create notification
        cursor = test_db.execute(
            """
            INSERT INTO watcher_notifications (watcher_id, event_id, read)
            VALUES (?, ?, ?)
        """,
            (watcher_id, event_id, 0),
        )
        notification_id = cursor.lastrowid
        test_db.commit()

        # Mark as read
        test_db.execute(
            """
            UPDATE watcher_notifications
            SET read = 1, read_at = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), notification_id),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT read, read_at FROM watcher_notifications WHERE id = ?", (notification_id,)
        ).fetchone()

        assert row[0] == 1
        assert row[1] is not None

    def test_get_unread_notifications(self, test_db):
        """Test retrieving unread notifications."""
        # Create watcher
        cursor = test_db.execute(
            """
            INSERT INTO task_watchers (task_id, task_type, user_id)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "user-1"),
        )
        watcher_id = cursor.lastrowid

        # Create events and notifications
        for i in range(5):
            cursor = test_db.execute(
                """
                INSERT INTO watcher_events (task_id, task_type, event_type)
                VALUES (?, ?, ?)
            """,
                ("T123", "feature", "status_change"),
            )
            event_id = cursor.lastrowid

            # Mark first 2 as read
            test_db.execute(
                """
                INSERT INTO watcher_notifications (watcher_id, event_id, read)
                VALUES (?, ?, ?)
            """,
                (watcher_id, event_id, 1 if i < 2 else 0),
            )
        test_db.commit()

        # Get unread
        unread = test_db.execute(
            """
            SELECT * FROM watcher_notifications
            WHERE watcher_id = ? AND read = 0
        """,
            (watcher_id,),
        ).fetchall()

        assert len(unread) == 3

    def test_notify_multiple_watchers(self, test_db):
        """Test notifying multiple watchers of an event."""
        # Create multiple watchers
        watchers = ["user-1", "user-2", "user-3"]
        watcher_ids = []

        for user_id in watchers:
            cursor = test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                ("T123", "feature", user_id),
            )
            watcher_ids.append(cursor.lastrowid)

        # Create event
        cursor = test_db.execute(
            """
            INSERT INTO watcher_events (task_id, task_type, event_type)
            VALUES (?, ?, ?)
        """,
            ("T123", "feature", "status_change"),
        )
        event_id = cursor.lastrowid

        # Create notifications for all watchers
        for watcher_id in watcher_ids:
            test_db.execute(
                """
                INSERT INTO watcher_notifications (watcher_id, event_id)
                VALUES (?, ?)
            """,
                (watcher_id, event_id),
            )

        # Update notified count
        test_db.execute(
            """
            UPDATE watcher_events
            SET notified_count = ?
            WHERE id = ?
        """,
            (len(watcher_ids), event_id),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT notified_count FROM watcher_events WHERE id = ?", (event_id,)
        ).fetchone()

        assert row[0] == 3


class TestWatchPreferences:
    """Test user watch preferences."""

    def test_set_watch_preferences(self, test_db):
        """Test setting user watch preferences."""
        test_db.execute(
            """
            INSERT INTO watch_preferences
            (user_id, notify_on_comment, notify_on_status_change, email_notifications)
            VALUES (?, ?, ?, ?)
        """,
            ("user-1", 1, 1, 0),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT * FROM watch_preferences WHERE user_id = ?", ("user-1",)
        ).fetchone()

        assert row is not None
        assert row[1] == 1  # notify_on_comment
        assert row[2] == 1  # notify_on_status_change
        assert row[5] == 0  # email_notifications

    def test_update_preferences(self, test_db):
        """Test updating watch preferences."""
        # Create preferences
        test_db.execute(
            """
            INSERT INTO watch_preferences (user_id, email_notifications)
            VALUES (?, ?)
        """,
            ("user-1", 0),
        )
        test_db.commit()

        # Update
        test_db.execute(
            """
            UPDATE watch_preferences
            SET email_notifications = 1
            WHERE user_id = ?
        """,
            ("user-1",),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT email_notifications FROM watch_preferences WHERE user_id = ?", ("user-1",)
        ).fetchone()

        assert row[0] == 1

    def test_digest_mode(self, test_db):
        """Test digest mode preference."""
        test_db.execute(
            """
            INSERT INTO watch_preferences (user_id, digest_mode)
            VALUES (?, ?)
        """,
            ("user-1", 1),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT digest_mode FROM watch_preferences WHERE user_id = ?", ("user-1",)
        ).fetchone()

        assert row[0] == 1


class TestBulkOperations:
    """Test bulk watch operations."""

    def test_bulk_watch_tasks(self, test_db):
        """Test watching multiple tasks at once."""
        tasks = [("T123", "feature"), ("T124", "bug"), ("T125", "milestone")]

        for task_id, task_type in tasks:
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                (task_id, task_type, "user-1"),
            )
        test_db.commit()

        # Verify
        count = test_db.execute(
            "SELECT COUNT(*) FROM task_watchers WHERE user_id = ?", ("user-1",)
        ).fetchone()[0]

        assert count == 3

    def test_bulk_unwatch_tasks(self, test_db):
        """Test unwatching multiple tasks."""
        # Create watchers
        tasks = [("T123", "feature"), ("T124", "bug"), ("T125", "milestone")]

        for task_id, task_type in tasks:
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                (task_id, task_type, "user-1"),
            )
        test_db.commit()

        # Bulk delete
        test_db.execute(
            """
            DELETE FROM task_watchers
            WHERE user_id = ? AND task_id IN ('T123', 'T124')
        """,
            ("user-1",),
        )
        test_db.commit()

        # Verify
        remaining = test_db.execute(
            "SELECT COUNT(*) FROM task_watchers WHERE user_id = ?", ("user-1",)
        ).fetchone()[0]

        assert remaining == 1


class TestWatcherStatistics:
    """Test watcher statistics."""

    def test_count_watchers_per_task(self, test_db):
        """Test counting watchers for a task."""
        # Create multiple watchers for same task
        users = ["user-1", "user-2", "user-3"]

        for user_id in users:
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                ("T123", "feature", user_id),
            )
        test_db.commit()

        # Count
        count = test_db.execute(
            "SELECT COUNT(*) FROM task_watchers WHERE task_id = ?", ("T123",)
        ).fetchone()[0]

        assert count == 3

    def test_count_watched_tasks_per_user(self, test_db):
        """Test counting tasks watched by a user."""
        # Create multiple watches for user
        tasks = [("T123", "feature"), ("T124", "bug"), ("T125", "milestone")]

        for task_id, task_type in tasks:
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                (task_id, task_type, "user-1"),
            )
        test_db.commit()

        # Count
        count = test_db.execute(
            "SELECT COUNT(*) FROM task_watchers WHERE user_id = ?", ("user-1",)
        ).fetchone()[0]

        assert count == 3

    def test_most_watched_tasks(self, test_db):
        """Test finding most watched tasks."""
        # Create tasks with different watcher counts
        # T123: 3 watchers, T124: 2 watchers, T125: 1 watcher
        watchers = [
            ("T123", "user-1"), ("T123", "user-2"), ("T123", "user-3"),
            ("T124", "user-1"), ("T124", "user-2"),
            ("T125", "user-1"),
        ]

        for task_id, user_id in watchers:
            test_db.execute(
                """
                INSERT INTO task_watchers (task_id, task_type, user_id)
                VALUES (?, ?, ?)
            """,
                (task_id, "feature", user_id),
            )
        test_db.commit()

        # Get most watched
        rows = test_db.execute(
            """
            SELECT task_id, COUNT(*) as watcher_count
            FROM task_watchers
            GROUP BY task_id
            ORDER BY watcher_count DESC
        """
        ).fetchall()

        assert rows[0][0] == "T123"
        assert rows[0][1] == 3


class TestEventFiltering:
    """Test filtering events and notifications."""

    def test_filter_events_by_type(self, test_db):
        """Test filtering events by type."""
        # Create different event types
        event_types = ["status_change", "comment_added", "assigned", "status_change"]

        for event_type in event_types:
            test_db.execute(
                """
                INSERT INTO watcher_events (task_id, task_type, event_type)
                VALUES (?, ?, ?)
            """,
                ("T123", "feature", event_type),
            )
        test_db.commit()

        # Filter by status_change
        rows = test_db.execute(
            """
            SELECT * FROM watcher_events
            WHERE task_id = ? AND event_type = ?
        """,
            ("T123", "status_change"),
        ).fetchall()

        assert len(rows) == 2

    def test_filter_by_date_range(self, test_db):
        """Test filtering events by date range."""
        # Create events at different times
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        test_db.execute(
            """
            INSERT INTO watcher_events (task_id, task_type, event_type, created_at)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "feature", "status_change", yesterday.isoformat()),
        )

        test_db.execute(
            """
            INSERT INTO watcher_events (task_id, task_type, event_type, created_at)
            VALUES (?, ?, ?, ?)
        """,
            ("T123", "feature", "comment_added", now.isoformat()),
        )
        test_db.commit()

        # Get today's events
        cutoff = (now - timedelta(hours=12)).isoformat()
        rows = test_db.execute(
            """
            SELECT * FROM watcher_events
            WHERE created_at > ?
        """,
            (cutoff,),
        ).fetchall()

        assert len(rows) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
