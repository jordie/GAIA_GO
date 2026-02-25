"""
Task Watchers/Subscribers Service

Allows users to subscribe to tasks and receive notifications on updates.

Usage:
    from services.task_watchers import get_watcher_service, notify_watchers

    # Get service instance
    service = get_watcher_service(db_path)

    # Watch a task
    service.watch_task(task_id=123, task_type='feature', user_id='developer1')

    # Notify watchers of an update
    notify_watchers(
        task_id=123,
        task_type='feature',
        event_type='status_change',
        event_data={'old_status': 'open', 'new_status': 'in_progress'},
        actor='developer1'
    )
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Valid task types that can be watched
WATCHABLE_TASK_TYPES = ["task_queue", "feature", "bug", "milestone", "devops_task", "project"]

# Event types
EVENT_TYPES = [
    "status_change",
    "comment_added",
    "assigned",
    "unassigned",
    "updated",
    "completed",
    "created",
    "deleted",
    "priority_change",
]

# Watch types (what events to notify about)
WATCH_TYPES = {
    "all": EVENT_TYPES,
    "status": ["status_change", "completed"],
    "comments": ["comment_added"],
    "assignment": ["assigned", "unassigned"],
}


class TaskWatcherService:
    """Service for managing task watchers and notifications."""

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

    def watch_task(
        self,
        task_id: int,
        task_type: str,
        user_id: str,
        watch_type: str = "all",
        notify_email: bool = False,
        notify_dashboard: bool = True,
    ) -> Dict:
        """Add a watcher to a task.

        Args:
            task_id: ID of the task to watch
            task_type: Type of task ('feature', 'bug', 'task_queue', etc.)
            user_id: User ID of the watcher
            watch_type: Type of events to watch ('all', 'status', 'comments', 'assignment')
            notify_email: Whether to send email notifications
            notify_dashboard: Whether to send dashboard notifications

        Returns:
            Dict with watcher info
        """
        if task_type not in WATCHABLE_TASK_TYPES:
            raise ValueError(f"Invalid task type: {task_type}")

        if watch_type not in WATCH_TYPES:
            raise ValueError(f"Invalid watch type: {watch_type}")

        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO task_watchers
                    (task_id, task_type, user_id, watch_type, notify_email, notify_dashboard)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (task_id, task_type, user_id, watch_type, notify_email, notify_dashboard),
                )
                conn.commit()

                watcher_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                logger.info(f"User {user_id} watching {task_type} {task_id}")

                return {
                    "id": watcher_id,
                    "task_id": task_id,
                    "task_type": task_type,
                    "user_id": user_id,
                    "watch_type": watch_type,
                    "notify_email": notify_email,
                    "notify_dashboard": notify_dashboard,
                }

            except sqlite3.IntegrityError:
                # Already watching - update the watch settings
                conn.execute(
                    """
                    UPDATE task_watchers
                    SET watch_type = ?, notify_email = ?, notify_dashboard = ?
                    WHERE task_id = ? AND task_type = ? AND user_id = ?
                """,
                    (watch_type, notify_email, notify_dashboard, task_id, task_type, user_id),
                )
                conn.commit()

                watcher = conn.execute(
                    """
                    SELECT * FROM task_watchers
                    WHERE task_id = ? AND task_type = ? AND user_id = ?
                """,
                    (task_id, task_type, user_id),
                ).fetchone()

                return dict(watcher)

    def unwatch_task(self, task_id: int, task_type: str, user_id: str) -> bool:
        """Remove a watcher from a task.

        Returns:
            True if watcher was removed, False if not found
        """
        with self._get_connection() as conn:
            result = conn.execute(
                """
                DELETE FROM task_watchers
                WHERE task_id = ? AND task_type = ? AND user_id = ?
            """,
                (task_id, task_type, user_id),
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"User {user_id} unwatched {task_type} {task_id}")
                return True
            return False

    def get_watchers(self, task_id: int, task_type: str) -> List[Dict]:
        """Get all watchers for a task."""
        with self._get_connection() as conn:
            watchers = conn.execute(
                """
                SELECT * FROM task_watchers
                WHERE task_id = ? AND task_type = ?
                ORDER BY created_at
            """,
                (task_id, task_type),
            ).fetchall()

            return [dict(w) for w in watchers]

    def get_user_watches(self, user_id: str, task_type: str = None) -> List[Dict]:
        """Get all tasks a user is watching."""
        with self._get_connection() as conn:
            if task_type:
                watches = conn.execute(
                    """
                    SELECT * FROM task_watchers
                    WHERE user_id = ? AND task_type = ?
                    ORDER BY created_at DESC
                """,
                    (user_id, task_type),
                ).fetchall()
            else:
                watches = conn.execute(
                    """
                    SELECT * FROM task_watchers
                    WHERE user_id = ?
                    ORDER BY task_type, created_at DESC
                """,
                    (user_id,),
                ).fetchall()

            return [dict(w) for w in watches]

    def is_watching(self, task_id: int, task_type: str, user_id: str) -> bool:
        """Check if a user is watching a task."""
        with self._get_connection() as conn:
            result = conn.execute(
                """
                SELECT 1 FROM task_watchers
                WHERE task_id = ? AND task_type = ? AND user_id = ?
            """,
                (task_id, task_type, user_id),
            ).fetchone()

            return result is not None

    def notify_watchers(
        self,
        task_id: int,
        task_type: str,
        event_type: str,
        event_data: Dict = None,
        actor: str = None,
        exclude_actor: bool = True,
    ) -> int:
        """Send notifications to all watchers of a task.

        Args:
            task_id: ID of the task
            task_type: Type of task
            event_type: Type of event that occurred
            event_data: Additional event details
            actor: User who triggered the event (optional)
            exclude_actor: Whether to exclude the actor from notifications

        Returns:
            Number of watchers notified
        """
        if event_type not in EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")

        with self._get_connection() as conn:
            # Get watchers who should be notified for this event type
            watchers = conn.execute(
                """
                SELECT * FROM task_watchers
                WHERE task_id = ? AND task_type = ?
            """,
                (task_id, task_type),
            ).fetchall()

            notified_count = 0
            event_data_json = json.dumps(event_data) if event_data else None

            for watcher in watchers:
                w = dict(watcher)

                # Skip actor if requested
                if exclude_actor and actor and w["user_id"] == actor:
                    continue

                # Check if this watch type should receive this event
                watched_events = WATCH_TYPES.get(w["watch_type"], [])
                if event_type not in watched_events:
                    continue

                # Record the watch event
                conn.execute(
                    """
                    INSERT INTO watch_events
                    (watcher_id, task_id, task_type, event_type, event_data)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (w["id"], task_id, task_type, event_type, event_data_json),
                )

                # Send real-time notification if dashboard notifications enabled
                if w["notify_dashboard"] and self._socketio:
                    self._send_realtime_notification(w, task_id, task_type, event_type, event_data)

                notified_count += 1

            conn.commit()

            logger.info(
                f"Notified {notified_count} watchers of {event_type} on {task_type} {task_id}"
            )
            return notified_count

    def _send_realtime_notification(
        self, watcher: Dict, task_id: int, task_type: str, event_type: str, event_data: Dict
    ):
        """Send real-time notification via SocketIO."""
        try:
            notification = {
                "type": "watch_notification",
                "task_id": task_id,
                "task_type": task_type,
                "event_type": event_type,
                "event_data": event_data,
                "timestamp": datetime.now().isoformat(),
            }

            # Emit to user-specific room
            self._socketio.emit(
                "watch_notification", notification, room=f"user_{watcher['user_id']}"
            )
        except Exception as e:
            logger.warning(f"Failed to send realtime notification: {e}")

    def get_unread_events(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get unread watch events for a user."""
        with self._get_connection() as conn:
            events = conn.execute(
                """
                SELECT we.*, tw.user_id
                FROM watch_events we
                JOIN task_watchers tw ON we.watcher_id = tw.id
                WHERE tw.user_id = ? AND we.read_at IS NULL
                ORDER BY we.notified_at DESC
                LIMIT ?
            """,
                (user_id, limit),
            ).fetchall()

            return [dict(e) for e in events]

    def mark_events_read(self, user_id: str, event_ids: List[int] = None) -> int:
        """Mark watch events as read.

        Args:
            user_id: User to mark events for
            event_ids: Specific event IDs to mark (or None for all)

        Returns:
            Number of events marked as read
        """
        with self._get_connection() as conn:
            if event_ids:
                placeholders = ",".join("?" * len(event_ids))
                result = conn.execute(
                    f"""
                    UPDATE watch_events
                    SET read_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                    AND watcher_id IN (SELECT id FROM task_watchers WHERE user_id = ?)
                    AND read_at IS NULL
                """,
                    event_ids + [user_id],
                )
            else:
                result = conn.execute(
                    """
                    UPDATE watch_events
                    SET read_at = CURRENT_TIMESTAMP
                    WHERE watcher_id IN (SELECT id FROM task_watchers WHERE user_id = ?)
                    AND read_at IS NULL
                """,
                    (user_id,),
                )

            conn.commit()
            return result.rowcount

    def get_watch_preferences(self, user_id: str) -> Dict:
        """Get user's watch preferences."""
        with self._get_connection() as conn:
            prefs = conn.execute(
                """
                SELECT * FROM watch_preferences WHERE user_id = ?
            """,
                (user_id,),
            ).fetchone()

            if prefs:
                return dict(prefs)

            # Return defaults if no preferences set
            return {
                "user_id": user_id,
                "auto_watch_created": True,
                "auto_watch_assigned": True,
                "auto_watch_commented": False,
                "quiet_hours_start": None,
                "quiet_hours_end": None,
                "digest_frequency": "instant",
            }

    def set_watch_preferences(self, user_id: str, **preferences) -> Dict:
        """Set user's watch preferences."""
        valid_prefs = [
            "auto_watch_created",
            "auto_watch_assigned",
            "auto_watch_commented",
            "quiet_hours_start",
            "quiet_hours_end",
            "digest_frequency",
        ]

        updates = {k: v for k, v in preferences.items() if k in valid_prefs}

        if not updates:
            return self.get_watch_preferences(user_id)

        with self._get_connection() as conn:
            # Check if preferences exist
            existing = conn.execute(
                "SELECT 1 FROM watch_preferences WHERE user_id = ?", (user_id,)
            ).fetchone()

            if existing:
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                conn.execute(
                    f"""
                    UPDATE watch_preferences
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """,
                    list(updates.values()) + [user_id],
                )
            else:
                columns = ["user_id"] + list(updates.keys())
                placeholders = ", ".join("?" * len(columns))
                conn.execute(
                    f"""
                    INSERT INTO watch_preferences ({', '.join(columns)})
                    VALUES ({placeholders})
                """,
                    [user_id] + list(updates.values()),
                )

            conn.commit()

            return self.get_watch_preferences(user_id)

    def get_watcher_stats(self, user_id: str = None) -> Dict:
        """Get statistics about watchers.

        Args:
            user_id: Get stats for specific user, or overall stats if None
        """
        with self._get_connection() as conn:
            if user_id:
                # User-specific stats
                watches = conn.execute(
                    """
                    SELECT task_type, COUNT(*) as count
                    FROM task_watchers WHERE user_id = ?
                    GROUP BY task_type
                """,
                    (user_id,),
                ).fetchall()

                unread = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM watch_events we
                    JOIN task_watchers tw ON we.watcher_id = tw.id
                    WHERE tw.user_id = ? AND we.read_at IS NULL
                """,
                    (user_id,),
                ).fetchone()

                total_events = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM watch_events we
                    JOIN task_watchers tw ON we.watcher_id = tw.id
                    WHERE tw.user_id = ?
                """,
                    (user_id,),
                ).fetchone()

                return {
                    "user_id": user_id,
                    "watches_by_type": {w["task_type"]: w["count"] for w in watches},
                    "total_watches": sum(w["count"] for w in watches),
                    "unread_events": unread["count"],
                    "total_events": total_events["count"],
                }

            else:
                # Overall stats
                total_watchers = conn.execute(
                    "SELECT COUNT(DISTINCT user_id) as count FROM task_watchers"
                ).fetchone()

                total_watches = conn.execute(
                    "SELECT COUNT(*) as count FROM task_watchers"
                ).fetchone()

                watches_by_type = conn.execute(
                    """
                    SELECT task_type, COUNT(*) as count
                    FROM task_watchers GROUP BY task_type
                """
                ).fetchall()

                recent_events = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM watch_events
                    WHERE notified_at > datetime('now', '-24 hours')
                """
                ).fetchone()

                return {
                    "total_watchers": total_watchers["count"],
                    "total_watches": total_watches["count"],
                    "watches_by_type": {w["task_type"]: w["count"] for w in watches_by_type},
                    "events_last_24h": recent_events["count"],
                }

    def bulk_watch(self, user_id: str, tasks: List[Dict], watch_type: str = "all") -> List[Dict]:
        """Watch multiple tasks at once.

        Args:
            user_id: User ID
            tasks: List of {'task_id': int, 'task_type': str}
            watch_type: Watch type to apply to all

        Returns:
            List of created watchers
        """
        results = []
        for task in tasks:
            try:
                result = self.watch_task(
                    task_id=task["task_id"],
                    task_type=task["task_type"],
                    user_id=user_id,
                    watch_type=watch_type,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to watch task {task}: {e}")
                results.append({"error": str(e), **task})

        return results

    def bulk_unwatch(self, user_id: str, tasks: List[Dict]) -> int:
        """Unwatch multiple tasks at once.

        Returns:
            Number of tasks unwatched
        """
        count = 0
        for task in tasks:
            if self.unwatch_task(
                task_id=task["task_id"], task_type=task["task_type"], user_id=user_id
            ):
                count += 1
        return count


# Singleton instance getter
_service_instance = None
_service_lock = threading.Lock()


def get_watcher_service(db_path: str = None) -> TaskWatcherService:
    """Get the TaskWatcherService singleton instance."""
    global _service_instance
    if _service_instance is None or db_path:
        with _service_lock:
            if _service_instance is None or db_path:
                _service_instance = TaskWatcherService(db_path)
    return _service_instance


def notify_watchers(
    task_id: int,
    task_type: str,
    event_type: str,
    event_data: Dict = None,
    actor: str = None,
    db_path: str = None,
) -> int:
    """Convenience function to notify watchers.

    Args:
        task_id: ID of the task
        task_type: Type of task
        event_type: Type of event
        event_data: Additional event details
        actor: User who triggered the event
        db_path: Database path (uses default if not provided)

    Returns:
        Number of watchers notified
    """
    service = get_watcher_service(db_path)
    return service.notify_watchers(
        task_id=task_id,
        task_type=task_type,
        event_type=event_type,
        event_data=event_data,
        actor=actor,
    )
