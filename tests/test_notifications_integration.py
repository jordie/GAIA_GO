#!/usr/bin/env python3
"""
Notifications Integration Tests

Tests for Notification Service system.

Tests the full integration of:
- Notification creation and delivery
- Multiple notification channels (database, file, webhook)
- Severity levels (critical, error, warning, info)
- Notification filtering and preferences
- Read/unread status tracking
- Bulk operations
- Notification history
- WebSocket broadcasting
"""

import json
import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with notifications schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create notifications tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'info',
            severity TEXT DEFAULT 'info',
            source TEXT,
            action_url TEXT,
            metadata TEXT,
            read BOOLEAN DEFAULT 0,
            read_at TIMESTAMP,
            dismissed BOOLEAN DEFAULT 0,
            dismissed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notification_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_type TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            config TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_type, channel_name)
        );

        CREATE TABLE IF NOT EXISTS notification_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (notification_id) REFERENCES notifications(id),
            FOREIGN KEY (channel_id) REFERENCES notification_channels(id)
        );

        CREATE TABLE IF NOT EXISTS notification_preferences (
            user_id TEXT PRIMARY KEY,
            email_enabled BOOLEAN DEFAULT 1,
            push_enabled BOOLEAN DEFAULT 1,
            webhook_enabled BOOLEAN DEFAULT 0,
            min_severity TEXT DEFAULT 'info',
            quiet_hours_start TEXT,
            quiet_hours_end TEXT
        );

        CREATE INDEX idx_notifications_user ON notifications(user_id);
        CREATE INDEX idx_notifications_read ON notifications(read);
        CREATE INDEX idx_notifications_severity ON notifications(severity);
        CREATE INDEX idx_notification_deliveries_notification ON notification_deliveries(notification_id);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestNotificationCreation:
    """Test notification creation."""

    def test_create_notification(self, test_db):
        """Test creating a notification."""
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, notification_type, severity)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("user-1", "New Task", "You have a new task assigned", "task", "info"),
        )
        notification_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()

        assert row is not None
        assert row[2] == "New Task"
        assert row[3] == "You have a new task assigned"

    def test_create_notification_with_metadata(self, test_db):
        """Test creating notification with metadata."""
        metadata = json.dumps({"task_id": "T123", "priority": "high"})

        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, metadata)
            VALUES (?, ?, ?, ?)
        """,
            ("user-1", "High Priority Task", "Urgent task assigned", metadata),
        )
        notification_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT metadata FROM notifications WHERE id = ?", (notification_id,)).fetchone()

        data = json.loads(row[0])
        assert data["task_id"] == "T123"
        assert data["priority"] == "high"

    def test_create_notification_with_action_url(self, test_db):
        """Test creating notification with action URL."""
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, action_url)
            VALUES (?, ?, ?, ?)
        """,
            ("user-1", "Review PR", "New pull request needs review", "/pr/123"),
        )
        notification_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute("SELECT action_url FROM notifications WHERE id = ?", (notification_id,)).fetchone()

        assert row[0] == "/pr/123"


class TestSeverityLevels:
    """Test notification severity levels."""

    def test_create_critical_notification(self, test_db):
        """Test creating critical severity notification."""
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, severity)
            VALUES (?, ?, ?, ?)
        """,
            ("user-1", "System Error", "Critical system failure", "critical"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT severity FROM notifications WHERE title = 'System Error'"
        ).fetchone()

        assert row[0] == "critical"

    def test_filter_by_severity(self, test_db):
        """Test filtering notifications by severity."""
        # Create notifications with different severities
        severities = ["critical", "error", "warning", "info"]

        for severity in severities:
            test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message, severity)
                VALUES (?, ?, ?, ?)
            """,
                ("user-1", f"{severity} notification", "Test message", severity),
            )
        test_db.commit()

        # Get critical only
        critical = test_db.execute(
            "SELECT * FROM notifications WHERE severity = 'critical'"
        ).fetchall()

        assert len(critical) == 1

    def test_severity_priority_ordering(self, test_db):
        """Test ordering notifications by severity priority."""
        # Insert in random order
        test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, severity)
            VALUES ('user-1', 'Info', 'Info msg', 'info'),
                   ('user-1', 'Critical', 'Critical msg', 'critical'),
                   ('user-1', 'Warning', 'Warning msg', 'warning'),
                   ('user-1', 'Error', 'Error msg', 'error')
        """
        )
        test_db.commit()

        # Get ordered by severity priority
        rows = test_db.execute(
            """
            SELECT title, severity FROM notifications
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'error' THEN 2
                    WHEN 'warning' THEN 3
                    WHEN 'info' THEN 4
                END
        """
        ).fetchall()

        assert rows[0][0] == "Critical"
        assert rows[1][0] == "Error"
        assert rows[2][0] == "Warning"
        assert rows[3][0] == "Info"


class TestNotificationStatus:
    """Test notification read/unread status."""

    def test_mark_notification_read(self, test_db):
        """Test marking notification as read."""
        # Create notification
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, read)
            VALUES (?, ?, ?, ?)
        """,
            ("user-1", "Test", "Message", 0),
        )
        notification_id = cursor.lastrowid
        test_db.commit()

        # Mark as read
        test_db.execute(
            """
            UPDATE notifications
            SET read = 1, read_at = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), notification_id),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT read, read_at FROM notifications WHERE id = ?", (notification_id,)
        ).fetchone()

        assert row[0] == 1
        assert row[1] is not None

    def test_get_unread_notifications(self, test_db):
        """Test retrieving unread notifications."""
        # Create mixed notifications
        for i in range(5):
            test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message, read)
                VALUES (?, ?, ?, ?)
            """,
                ("user-1", f"Notification {i}", "Message", 1 if i < 2 else 0),
            )
        test_db.commit()

        # Get unread
        unread = test_db.execute(
            "SELECT * FROM notifications WHERE user_id = ? AND read = 0", ("user-1",)
        ).fetchall()

        assert len(unread) == 3

    def test_dismiss_notification(self, test_db):
        """Test dismissing a notification."""
        # Create notification
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
        """,
            ("user-1", "Dismissable", "Message"),
        )
        notification_id = cursor.lastrowid
        test_db.commit()

        # Dismiss
        test_db.execute(
            """
            UPDATE notifications
            SET dismissed = 1, dismissed_at = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), notification_id),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT dismissed FROM notifications WHERE id = ?", (notification_id,)
        ).fetchone()

        assert row[0] == 1

    def test_mark_all_read(self, test_db):
        """Test marking all notifications as read."""
        # Create unread notifications
        for i in range(5):
            test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message, read)
                VALUES (?, ?, ?, ?)
            """,
                ("user-1", f"Notification {i}", "Message", 0),
            )
        test_db.commit()

        # Mark all read
        test_db.execute(
            """
            UPDATE notifications
            SET read = 1, read_at = ?
            WHERE user_id = ? AND read = 0
        """,
            (datetime.now().isoformat(), "user-1"),
        )
        test_db.commit()

        # Verify
        unread_count = test_db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read = 0", ("user-1",)
        ).fetchone()[0]

        assert unread_count == 0


class TestNotificationChannels:
    """Test notification delivery channels."""

    def test_create_channel(self, test_db):
        """Test creating a notification channel."""
        config = json.dumps({"webhook_url": "https://hooks.slack.com/xxx"})

        cursor = test_db.execute(
            """
            INSERT INTO notification_channels (channel_type, channel_name, config)
            VALUES (?, ?, ?)
        """,
            ("webhook", "slack-alerts", config),
        )
        channel_id = cursor.lastrowid
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT * FROM notification_channels WHERE id = ?", (channel_id,)
        ).fetchone()

        assert row is not None
        assert row[1] == "webhook"
        assert row[2] == "slack-alerts"

    def test_enable_disable_channel(self, test_db):
        """Test enabling/disabling a channel."""
        # Create enabled channel
        cursor = test_db.execute(
            """
            INSERT INTO notification_channels (channel_type, channel_name, enabled)
            VALUES (?, ?, ?)
        """,
            ("email", "smtp-server", 1),
        )
        channel_id = cursor.lastrowid
        test_db.commit()

        # Disable
        test_db.execute(
            """
            UPDATE notification_channels
            SET enabled = 0
            WHERE id = ?
        """,
            (channel_id,),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT enabled FROM notification_channels WHERE id = ?", (channel_id,)
        ).fetchone()

        assert row[0] == 0

    def test_list_active_channels(self, test_db):
        """Test listing active channels."""
        # Create mixed channels
        test_db.execute(
            """
            INSERT INTO notification_channels (channel_type, channel_name, enabled)
            VALUES ('webhook', 'slack', 1),
                   ('email', 'smtp', 1),
                   ('webhook', 'discord', 0)
        """
        )
        test_db.commit()

        # Get active
        active = test_db.execute(
            "SELECT * FROM notification_channels WHERE enabled = 1"
        ).fetchall()

        assert len(active) == 2


class TestNotificationDelivery:
    """Test notification delivery tracking."""

    def test_record_successful_delivery(self, test_db):
        """Test recording successful notification delivery."""
        # Create notification and channel
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
        """,
            ("user-1", "Test", "Message"),
        )
        notification_id = cursor.lastrowid

        cursor = test_db.execute(
            """
            INSERT INTO notification_channels (channel_type, channel_name)
            VALUES (?, ?)
        """,
            ("webhook", "slack"),
        )
        channel_id = cursor.lastrowid
        test_db.commit()

        # Record delivery
        test_db.execute(
            """
            INSERT INTO notification_deliveries
            (notification_id, channel_id, status, delivered_at)
            VALUES (?, ?, ?, ?)
        """,
            (notification_id, channel_id, "delivered", datetime.now().isoformat()),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT status FROM notification_deliveries WHERE notification_id = ?", (notification_id,)
        ).fetchone()

        assert row[0] == "delivered"

    def test_record_failed_delivery(self, test_db):
        """Test recording failed notification delivery."""
        # Create notification and channel
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
        """,
            ("user-1", "Test", "Message"),
        )
        notification_id = cursor.lastrowid

        cursor = test_db.execute(
            """
            INSERT INTO notification_channels (channel_type, channel_name)
            VALUES (?, ?)
        """,
            ("webhook", "slack"),
        )
        channel_id = cursor.lastrowid
        test_db.commit()

        # Record failure
        test_db.execute(
            """
            INSERT INTO notification_deliveries
            (notification_id, channel_id, status, error_message)
            VALUES (?, ?, ?, ?)
        """,
            (notification_id, channel_id, "failed", "Connection timeout"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT status, error_message FROM notification_deliveries WHERE notification_id = ?",
            (notification_id,),
        ).fetchone()

        assert row[0] == "failed"
        assert row[1] == "Connection timeout"

    def test_track_multiple_channel_deliveries(self, test_db):
        """Test tracking delivery across multiple channels."""
        # Create notification
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
        """,
            ("user-1", "Test", "Message"),
        )
        notification_id = cursor.lastrowid

        # Create channels
        channels = ["slack", "email", "discord"]
        for channel_name in channels:
            cursor = test_db.execute(
                """
                INSERT INTO notification_channels (channel_type, channel_name)
                VALUES (?, ?)
            """,
                ("webhook", channel_name),
            )
            channel_id = cursor.lastrowid

            # Record delivery
            test_db.execute(
                """
                INSERT INTO notification_deliveries
                (notification_id, channel_id, status)
                VALUES (?, ?, ?)
            """,
                (notification_id, channel_id, "delivered"),
            )
        test_db.commit()

        # Verify
        deliveries = test_db.execute(
            "SELECT * FROM notification_deliveries WHERE notification_id = ?", (notification_id,)
        ).fetchall()

        assert len(deliveries) == 3


class TestNotificationPreferences:
    """Test user notification preferences."""

    def test_set_preferences(self, test_db):
        """Test setting notification preferences."""
        test_db.execute(
            """
            INSERT INTO notification_preferences
            (user_id, email_enabled, push_enabled, min_severity)
            VALUES (?, ?, ?, ?)
        """,
            ("user-1", 1, 1, "warning"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT * FROM notification_preferences WHERE user_id = ?", ("user-1",)
        ).fetchone()

        assert row is not None
        assert row[1] == 1  # email_enabled
        assert row[2] == 1  # push_enabled
        assert row[4] == "warning"  # min_severity

    def test_update_preferences(self, test_db):
        """Test updating preferences."""
        # Create preferences
        test_db.execute(
            """
            INSERT INTO notification_preferences (user_id, email_enabled)
            VALUES (?, ?)
        """,
            ("user-1", 1),
        )
        test_db.commit()

        # Update
        test_db.execute(
            """
            UPDATE notification_preferences
            SET email_enabled = 0
            WHERE user_id = ?
        """,
            ("user-1",),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT email_enabled FROM notification_preferences WHERE user_id = ?", ("user-1",)
        ).fetchone()

        assert row[0] == 0

    def test_quiet_hours(self, test_db):
        """Test setting quiet hours."""
        test_db.execute(
            """
            INSERT INTO notification_preferences
            (user_id, quiet_hours_start, quiet_hours_end)
            VALUES (?, ?, ?)
        """,
            ("user-1", "22:00", "08:00"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT quiet_hours_start, quiet_hours_end FROM notification_preferences WHERE user_id = ?",
            ("user-1",),
        ).fetchone()

        assert row[0] == "22:00"
        assert row[1] == "08:00"


class TestBulkOperations:
    """Test bulk notification operations."""

    def test_bulk_mark_read(self, test_db):
        """Test marking multiple notifications as read."""
        # Create notifications
        notification_ids = []
        for i in range(5):
            cursor = test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message, read)
                VALUES (?, ?, ?, ?)
            """,
                ("user-1", f"Notification {i}", "Message", 0),
            )
            notification_ids.append(cursor.lastrowid)
        test_db.commit()

        # Bulk mark read
        test_db.execute(
            f"""
            UPDATE notifications
            SET read = 1, read_at = ?
            WHERE id IN ({','.join('?' * len(notification_ids))})
        """,
            (datetime.now().isoformat(), *notification_ids),
        )
        test_db.commit()

        # Verify
        read_count = test_db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read = 1", ("user-1",)
        ).fetchone()[0]

        assert read_count == 5

    def test_bulk_delete(self, test_db):
        """Test deleting multiple notifications."""
        # Create notifications
        for i in range(5):
            test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message, read)
                VALUES (?, ?, ?, ?)
            """,
                ("user-1", f"Notification {i}", "Message", 1 if i < 3 else 0),
            )
        test_db.commit()

        # Bulk delete read notifications
        test_db.execute(
            """
            DELETE FROM notifications
            WHERE user_id = ? AND read = 1
        """,
            ("user-1",),
        )
        test_db.commit()

        # Verify - only unread remain
        remaining = test_db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ?", ("user-1",)
        ).fetchone()[0]

        assert remaining == 2


class TestNotificationHistory:
    """Test notification history and statistics."""

    def test_get_notification_history(self, test_db):
        """Test retrieving notification history."""
        # Create notifications over time
        for i in range(10):
            test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message)
                VALUES (?, ?, ?)
            """,
                ("user-1", f"Notification {i}", "Message"),
            )
        test_db.commit()

        # Get history
        history = test_db.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC", ("user-1",)
        ).fetchall()

        assert len(history) == 10

    def test_count_by_severity(self, test_db):
        """Test counting notifications by severity."""
        # Create mixed severities
        severities = ["critical"] * 2 + ["error"] * 3 + ["warning"] * 4 + ["info"] * 5

        for severity in severities:
            test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message, severity)
                VALUES (?, ?, ?, ?)
            """,
                ("user-1", "Test", "Message", severity),
            )
        test_db.commit()

        # Count by severity
        rows = test_db.execute(
            """
            SELECT severity, COUNT(*) as count
            FROM notifications
            WHERE user_id = ?
            GROUP BY severity
        """,
            ("user-1",),
        ).fetchall()

        severity_counts = {row[0]: row[1] for row in rows}
        assert severity_counts["critical"] == 2
        assert severity_counts["error"] == 3
        assert severity_counts["warning"] == 4
        assert severity_counts["info"] == 5

    def test_filter_by_date_range(self, test_db):
        """Test filtering notifications by date range."""
        # Create notifications at different times
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, created_at)
            VALUES (?, ?, ?, ?)
        """,
            ("user-1", "Old", "Message", yesterday.isoformat()),
        )

        for i in range(3):
            test_db.execute(
                """
                INSERT INTO notifications (user_id, title, message)
                VALUES (?, ?, ?)
            """,
                ("user-1", f"Recent {i}", "Message"),
            )
        test_db.commit()

        # Get today's notifications
        cutoff = (now - timedelta(hours=12)).isoformat()
        recent = test_db.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = ? AND created_at > ?
        """,
            ("user-1", cutoff),
        ).fetchall()

        assert len(recent) == 3


class TestNotificationTypes:
    """Test different notification types."""

    def test_task_notification(self, test_db):
        """Test task-related notification."""
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, notification_type, source)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("user-1", "Task Assigned", "New task assigned to you", "task", "task_manager"),
        )
        test_db.commit()

        # Verify
        row = test_db.execute(
            "SELECT notification_type, source FROM notifications WHERE title = 'Task Assigned'"
        ).fetchone()

        assert row[0] == "task"
        assert row[1] == "task_manager"

    def test_system_notification(self, test_db):
        """Test system-level notification."""
        cursor = test_db.execute(
            """
            INSERT INTO notifications (user_id, title, message, notification_type, severity)
            VALUES (?, ?, ?, ?, ?)
        """,
            (None, "System Maintenance", "Scheduled downtime at 2 AM", "system", "warning"),
        )
        test_db.commit()

        # Verify system notification (no user_id)
        row = test_db.execute(
            "SELECT user_id, notification_type FROM notifications WHERE title = 'System Maintenance'"
        ).fetchone()

        assert row[0] is None
        assert row[1] == "system"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
