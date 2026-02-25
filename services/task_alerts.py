"""
Task Assignment Alerts Service

Provides real-time notifications for task assignments via dashboard alerts.
Supports:
- Real-time WebSocket notifications
- In-app alert badges
- Assignment history tracking
- User notification preferences

Usage:
    from services.task_alerts import TaskAlertService, notify_task_assignment

    # Quick notification
    notify_task_assignment(
        task_id=123,
        task_type='feature',
        task_title='Implement login page',
        assigned_to='developer1',
        assigned_by='manager1',
        priority='high'
    )

    # Or use the service directly
    service = TaskAlertService(db_path)
    service.create_alert(...)
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from datetime import time as dt_time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Alert priority levels
PRIORITY_LEVELS = ["critical", "high", "normal", "low"]

# Task types that support assignment
ASSIGNABLE_TASK_TYPES = [
    "feature",
    "bug",
    "task",
    "devops_task",
    "milestone",
    "shell",
    "python",
    "git",
    "deploy",
    "test",
    "build",
]


class TaskAlertService:
    """Service for managing task assignment alerts."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            if db_path:
                self.db_path = db_path
            return

        self.db_path = db_path
        self._socketio = None
        self._initialized = True

    def set_socketio(self, socketio):
        """Set SocketIO instance for real-time notifications."""
        self._socketio = socketio

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_alert(
        self,
        task_id: int,
        task_type: str,
        task_title: str,
        assigned_to: str,
        assigned_by: str = None,
        priority: str = "normal",
        message: str = None,
    ) -> Dict[str, Any]:
        """
        Create a task assignment alert.

        Args:
            task_id: ID of the assigned task
            task_type: Type of task (feature, bug, task, etc.)
            task_title: Title/description of the task
            assigned_to: User/worker the task is assigned to
            assigned_by: User who made the assignment
            priority: Alert priority (critical, high, normal, low)
            message: Optional custom message

        Returns:
            Created alert record
        """
        if priority not in PRIORITY_LEVELS:
            priority = "normal"

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_assignment_alerts
                (task_id, task_type, task_title, assigned_to, assigned_by, priority, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (task_id, task_type, task_title, assigned_to, assigned_by, priority, message),
            )
            conn.commit()
            alert_id = cursor.lastrowid

        alert = {
            "id": alert_id,
            "task_id": task_id,
            "task_type": task_type,
            "task_title": task_title,
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "priority": priority,
            "message": message,
            "created_at": datetime.now().isoformat(),
        }

        # Check if user wants notifications
        if self._should_notify(assigned_to):
            self._broadcast_alert(alert)

        logger.info(f"Task assignment alert created: task {task_id} -> {assigned_to}")
        return alert

    def _should_notify(self, user_id: str) -> bool:
        """Check if user should receive notification based on preferences."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT notify_on_assignment, quiet_hours_start, quiet_hours_end
                    FROM user_alert_preferences
                    WHERE user_id = ?
                """,
                    (user_id,),
                ).fetchone()

                if not row:
                    return True  # Default to notify

                if not row["notify_on_assignment"]:
                    return False

                # Check quiet hours
                if row["quiet_hours_start"] and row["quiet_hours_end"]:
                    now = datetime.now().time()
                    try:
                        start = dt_time.fromisoformat(row["quiet_hours_start"])
                        end = dt_time.fromisoformat(row["quiet_hours_end"])

                        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
                        if start > end:
                            if now >= start or now <= end:
                                return False
                        else:
                            if start <= now <= end:
                                return False
                    except ValueError:
                        pass

                return True
        except Exception as e:
            logger.debug(f"Error checking notification preferences: {e}")
            return True

    def _broadcast_alert(self, alert: Dict):
        """Broadcast alert via WebSocket."""
        if self._socketio:
            try:
                # Emit to user-specific room
                self._socketio.emit("task_assignment", alert, room=f"user:{alert['assigned_to']}")

                # Also emit to general alerts room
                self._socketio.emit(
                    "dashboard_alert",
                    {
                        "type": "task_assignment",
                        "alert": alert,
                        "timestamp": datetime.now().isoformat(),
                    },
                    room="alerts",
                )

                logger.debug(f"Broadcast alert to user:{alert['assigned_to']}")
            except Exception as e:
                logger.error(f"Failed to broadcast alert: {e}")

    def get_alerts(
        self, user_id: str = None, unread_only: bool = False, limit: int = 50
    ) -> List[Dict]:
        """Get task assignment alerts."""
        query = "SELECT * FROM task_assignment_alerts WHERE 1=1"
        params = []

        if user_id:
            query += " AND assigned_to = ?"
            params.append(user_id)

        if unread_only:
            query += " AND read_at IS NULL AND dismissed_at IS NULL"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread alerts for a user."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM task_assignment_alerts
                WHERE assigned_to = ? AND read_at IS NULL AND dismissed_at IS NULL
            """,
                (user_id,),
            ).fetchone()
            return row["count"] if row else 0

    def mark_read(self, alert_id: int) -> bool:
        """Mark an alert as read."""
        with self._get_connection() as conn:
            result = conn.execute(
                """
                UPDATE task_assignment_alerts
                SET read_at = CURRENT_TIMESTAMP
                WHERE id = ? AND read_at IS NULL
            """,
                (alert_id,),
            )
            conn.commit()
            return result.rowcount > 0

    def mark_all_read(self, user_id: str) -> int:
        """Mark all alerts as read for a user."""
        with self._get_connection() as conn:
            result = conn.execute(
                """
                UPDATE task_assignment_alerts
                SET read_at = CURRENT_TIMESTAMP
                WHERE assigned_to = ? AND read_at IS NULL
            """,
                (user_id,),
            )
            conn.commit()
            return result.rowcount

    def dismiss_alert(self, alert_id: int) -> bool:
        """Dismiss an alert."""
        with self._get_connection() as conn:
            result = conn.execute(
                """
                UPDATE task_assignment_alerts
                SET dismissed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND dismissed_at IS NULL
            """,
                (alert_id,),
            )
            conn.commit()
            return result.rowcount > 0

    def dismiss_all(self, user_id: str) -> int:
        """Dismiss all alerts for a user."""
        with self._get_connection() as conn:
            result = conn.execute(
                """
                UPDATE task_assignment_alerts
                SET dismissed_at = CURRENT_TIMESTAMP
                WHERE assigned_to = ? AND dismissed_at IS NULL
            """,
                (user_id,),
            )
            conn.commit()
            return result.rowcount

    def get_preferences(self, user_id: str) -> Dict:
        """Get user notification preferences."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM user_alert_preferences WHERE user_id = ?
            """,
                (user_id,),
            ).fetchone()

            if row:
                return dict(row)

            # Return defaults
            return {
                "user_id": user_id,
                "notify_on_assignment": True,
                "notify_on_completion": True,
                "notify_on_error": True,
                "sound_enabled": True,
                "desktop_notifications": True,
                "email_notifications": False,
                "quiet_hours_start": None,
                "quiet_hours_end": None,
            }

    def update_preferences(self, user_id: str, **kwargs) -> Dict:
        """Update user notification preferences."""
        allowed_fields = {
            "notify_on_assignment",
            "notify_on_completion",
            "notify_on_error",
            "sound_enabled",
            "desktop_notifications",
            "email_notifications",
            "quiet_hours_start",
            "quiet_hours_end",
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return self.get_preferences(user_id)

        with self._get_connection() as conn:
            # Check if preferences exist
            exists = conn.execute(
                "SELECT 1 FROM user_alert_preferences WHERE user_id = ?", (user_id,)
            ).fetchone()

            if exists:
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [user_id]
                conn.execute(
                    f"""
                    UPDATE user_alert_preferences
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """,
                    values,
                )
            else:
                # Insert with defaults
                prefs = self.get_preferences(user_id)
                prefs.update(updates)
                conn.execute(
                    """
                    INSERT INTO user_alert_preferences
                    (user_id, notify_on_assignment, notify_on_completion, notify_on_error,
                     sound_enabled, desktop_notifications, email_notifications,
                     quiet_hours_start, quiet_hours_end)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        prefs["notify_on_assignment"],
                        prefs["notify_on_completion"],
                        prefs["notify_on_error"],
                        prefs["sound_enabled"],
                        prefs["desktop_notifications"],
                        prefs["email_notifications"],
                        prefs.get("quiet_hours_start"),
                        prefs.get("quiet_hours_end"),
                    ),
                )

            conn.commit()

        return self.get_preferences(user_id)

    def get_stats(self, user_id: str = None) -> Dict:
        """Get alert statistics."""
        with self._get_connection() as conn:
            query = "SELECT * FROM task_assignment_alerts"
            params = []

            if user_id:
                query += " WHERE assigned_to = ?"
                params.append(user_id)

            rows = conn.execute(query, params).fetchall()

            total = len(rows)
            unread = sum(1 for r in rows if not r["read_at"] and not r["dismissed_at"])
            read = sum(1 for r in rows if r["read_at"])
            dismissed = sum(1 for r in rows if r["dismissed_at"])

            by_priority = {}
            by_type = {}
            for row in rows:
                priority = row["priority"] or "normal"
                task_type = row["task_type"] or "unknown"
                by_priority[priority] = by_priority.get(priority, 0) + 1
                by_type[task_type] = by_type.get(task_type, 0) + 1

            return {
                "total": total,
                "unread": unread,
                "read": read,
                "dismissed": dismissed,
                "by_priority": by_priority,
                "by_type": by_type,
            }


# Singleton instance
_alert_service: Optional[TaskAlertService] = None


def get_alert_service(db_path: str = None) -> TaskAlertService:
    """Get or create the alert service singleton."""
    global _alert_service
    if _alert_service is None:
        if db_path is None:
            raise ValueError("db_path required for first initialization")
        _alert_service = TaskAlertService(db_path)
    elif db_path:
        _alert_service.db_path = db_path
    return _alert_service


def notify_task_assignment(
    task_id: int,
    task_type: str,
    task_title: str,
    assigned_to: str,
    assigned_by: str = None,
    priority: str = "normal",
    message: str = None,
    db_path: str = None,
) -> Dict:
    """
    Convenience function to create a task assignment notification.

    Args:
        task_id: ID of the task
        task_type: Type of task (feature, bug, etc.)
        task_title: Title of the task
        assigned_to: User/worker being assigned
        assigned_by: User making the assignment
        priority: Alert priority
        message: Optional custom message
        db_path: Database path (uses default if not provided)

    Returns:
        Created alert record
    """
    service = get_alert_service(db_path)
    return service.create_alert(
        task_id=task_id,
        task_type=task_type,
        task_title=task_title,
        assigned_to=assigned_to,
        assigned_by=assigned_by,
        priority=priority,
        message=message,
    )


def notify_task_completion(
    task_id: int,
    task_type: str,
    task_title: str,
    assigned_to: str,
    completed_by: str = None,
    status: str = "completed",
    db_path: str = None,
) -> Dict:
    """Create a task completion notification."""
    service = get_alert_service(db_path)
    return service.create_alert(
        task_id=task_id,
        task_type=task_type,
        task_title=f"[{status.upper()}] {task_title}",
        assigned_to=assigned_to,
        assigned_by=completed_by,
        priority="normal",
        message=f"Task has been marked as {status}",
    )


def notify_task_error(
    task_id: int,
    task_type: str,
    task_title: str,
    assigned_to: str,
    error_message: str,
    db_path: str = None,
) -> Dict:
    """Create a task error notification."""
    service = get_alert_service(db_path)
    return service.create_alert(
        task_id=task_id,
        task_type=task_type,
        task_title=f"[ERROR] {task_title}",
        assigned_to=assigned_to,
        priority="high",
        message=error_message,
    )
