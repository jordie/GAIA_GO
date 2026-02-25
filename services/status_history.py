"""
Status History Service

Tracks and queries status changes for features, bugs, tasks, and milestones.

Usage:
    from services.status_history import get_status_history_service

    service = get_status_history_service(db_path)
    service.record_change('feature', 123, 'draft', 'in_progress', user='admin')
    history = service.get_entity_history('feature', 123)
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Valid entity types
ENTITY_TYPES = {"feature", "bug", "task", "milestone", "devops_task"}

# Change sources
SOURCE_MANUAL = "manual"
SOURCE_API = "api"
SOURCE_AUTO = "auto"
SOURCE_WEBHOOK = "webhook"
SOURCE_WORKER = "worker"


class StatusHistoryService:
    """Service for tracking status change history."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
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
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_change(
        self,
        entity_type: str,
        entity_id: int,
        old_status: Optional[str],
        new_status: str,
        changed_by: str = None,
        change_reason: str = None,
        change_source: str = SOURCE_API,
        metadata: Dict = None,
    ) -> Dict:
        """Record a status change.

        Args:
            entity_type: Type of entity ('feature', 'bug', 'task', etc.)
            entity_id: ID of the entity
            old_status: Previous status (None for new entities)
            new_status: New status
            changed_by: User who made the change
            change_reason: Optional reason for the change
            change_source: Source of change ('manual', 'api', 'auto', etc.)
            metadata: Additional context as dict

        Returns:
            The created history record
        """
        if entity_type not in ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type: {entity_type}")

        if old_status == new_status:
            # No actual change
            return None

        with self._get_connection() as conn:
            metadata_json = json.dumps(metadata) if metadata else None

            conn.execute(
                """
                INSERT INTO status_history
                (entity_type, entity_id, old_status, new_status,
                 changed_by, change_reason, change_source, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entity_type,
                    entity_id,
                    old_status,
                    new_status,
                    changed_by,
                    change_reason,
                    change_source,
                    metadata_json,
                ),
            )
            conn.commit()

            record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            record = conn.execute(
                "SELECT * FROM status_history WHERE id = ?", (record_id,)
            ).fetchone()

            logger.info(
                f"Recorded status change: {entity_type}#{entity_id} "
                f"{old_status or 'NULL'} -> {new_status} by {changed_by}"
            )

            return dict(record)

    def get_entity_history(self, entity_type: str, entity_id: int, limit: int = 50) -> List[Dict]:
        """Get status history for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            limit: Maximum records to return

        Returns:
            List of history records, newest first
        """
        with self._get_connection() as conn:
            records = conn.execute(
                """
                SELECT * FROM status_history
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (entity_type, entity_id, limit),
            ).fetchall()

            return [self._parse_record(r) for r in records]

    def get_recent_changes(
        self, entity_type: str = None, hours: int = 24, limit: int = 100
    ) -> List[Dict]:
        """Get recent status changes.

        Args:
            entity_type: Filter by entity type (optional)
            hours: Look back period in hours
            limit: Maximum records to return

        Returns:
            List of recent changes, newest first
        """
        since = datetime.now() - timedelta(hours=hours)

        with self._get_connection() as conn:
            if entity_type:
                records = conn.execute(
                    """
                    SELECT * FROM status_history
                    WHERE entity_type = ? AND created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (entity_type, since.isoformat(), limit),
                ).fetchall()
            else:
                records = conn.execute(
                    """
                    SELECT * FROM status_history
                    WHERE created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (since.isoformat(), limit),
                ).fetchall()

            return [self._parse_record(r) for r in records]

    def get_user_changes(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get status changes made by a specific user.

        Args:
            user_id: User identifier
            limit: Maximum records to return

        Returns:
            List of changes by the user
        """
        with self._get_connection() as conn:
            records = conn.execute(
                """
                SELECT * FROM status_history
                WHERE changed_by = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (user_id, limit),
            ).fetchall()

            return [self._parse_record(r) for r in records]

    def get_status_transitions(
        self, entity_type: str, status: str, direction: str = "to"
    ) -> List[Dict]:
        """Get transitions to or from a specific status.

        Args:
            entity_type: Type of entity
            status: Status to check
            direction: 'to' for transitions TO this status, 'from' for FROM

        Returns:
            List of transition records
        """
        with self._get_connection() as conn:
            if direction == "to":
                records = conn.execute(
                    """
                    SELECT * FROM status_history
                    WHERE entity_type = ? AND new_status = ?
                    ORDER BY created_at DESC
                    LIMIT 100
                """,
                    (entity_type, status),
                ).fetchall()
            else:
                records = conn.execute(
                    """
                    SELECT * FROM status_history
                    WHERE entity_type = ? AND old_status = ?
                    ORDER BY created_at DESC
                    LIMIT 100
                """,
                    (entity_type, status),
                ).fetchall()

            return [self._parse_record(r) for r in records]

    def get_transition_stats(self, entity_type: str = None, days: int = 30) -> Dict:
        """Get statistics about status transitions.

        Args:
            entity_type: Filter by entity type (optional)
            days: Look back period in days

        Returns:
            Statistics about transitions
        """
        since = datetime.now() - timedelta(days=days)

        with self._get_connection() as conn:
            conditions = ["created_at >= ?"]
            params = [since.isoformat()]

            if entity_type:
                conditions.append("entity_type = ?")
                params.append(entity_type)

            where_clause = " AND ".join(conditions)

            # Total changes
            total = conn.execute(
                f"""
                SELECT COUNT(*) as count FROM status_history
                WHERE {where_clause}
            """,
                params,
            ).fetchone()["count"]

            # By entity type
            by_type = conn.execute(
                f"""
                SELECT entity_type, COUNT(*) as count
                FROM status_history
                WHERE {where_clause}
                GROUP BY entity_type
                ORDER BY count DESC
            """,
                params,
            ).fetchall()

            # By new status
            by_status = conn.execute(
                f"""
                SELECT new_status, COUNT(*) as count
                FROM status_history
                WHERE {where_clause}
                GROUP BY new_status
                ORDER BY count DESC
            """,
                params,
            ).fetchall()

            # By user
            by_user = conn.execute(
                f"""
                SELECT changed_by, COUNT(*) as count
                FROM status_history
                WHERE {where_clause} AND changed_by IS NOT NULL
                GROUP BY changed_by
                ORDER BY count DESC
                LIMIT 10
            """,
                params,
            ).fetchall()

            # Common transitions
            transitions = conn.execute(
                f"""
                SELECT old_status, new_status, COUNT(*) as count
                FROM status_history
                WHERE {where_clause} AND old_status IS NOT NULL
                GROUP BY old_status, new_status
                ORDER BY count DESC
                LIMIT 20
            """,
                params,
            ).fetchall()

            # Average time in status
            avg_time = conn.execute(
                f"""
                SELECT
                    h1.entity_type,
                    h1.old_status as status,
                    AVG(
                        CAST((julianday(h1.created_at) - julianday(h2.created_at)) * 24 AS REAL)
                    ) as avg_hours
                FROM status_history h1
                JOIN status_history h2 ON
                    h1.entity_type = h2.entity_type AND
                    h1.entity_id = h2.entity_id AND
                    h1.old_status = h2.new_status AND
                    h1.created_at > h2.created_at
                WHERE h1.created_at >= ?
                {' AND h1.entity_type = ?' if entity_type else ''}
                GROUP BY h1.entity_type, h1.old_status
                ORDER BY avg_hours DESC
            """,
                params[:2] if entity_type else params[:1],
            ).fetchall()

            return {
                "period_days": days,
                "total_changes": total,
                "by_entity_type": [dict(r) for r in by_type],
                "by_status": [dict(r) for r in by_status],
                "top_users": [dict(r) for r in by_user],
                "common_transitions": [
                    {"from": r["old_status"], "to": r["new_status"], "count": r["count"]}
                    for r in transitions
                ],
                "avg_time_in_status": [
                    {
                        "entity_type": r["entity_type"],
                        "status": r["status"],
                        "avg_hours": round(r["avg_hours"], 2) if r["avg_hours"] else None,
                    }
                    for r in avg_time
                    if r["avg_hours"]
                ],
            }

    def get_time_in_status(self, entity_type: str, entity_id: int) -> List[Dict]:
        """Calculate time spent in each status for an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            List of status durations
        """
        history = self.get_entity_history(entity_type, entity_id, limit=1000)

        if not history:
            return []

        # History is newest first, reverse for chronological order
        history = list(reversed(history))

        durations = []
        for i, record in enumerate(history):
            start_time = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))

            if i + 1 < len(history):
                end_time = datetime.fromisoformat(
                    history[i + 1]["created_at"].replace("Z", "+00:00")
                )
            else:
                end_time = datetime.now()

            duration = (end_time - start_time).total_seconds()

            durations.append(
                {
                    "status": record["new_status"],
                    "started_at": record["created_at"],
                    "ended_at": history[i + 1]["created_at"] if i + 1 < len(history) else None,
                    "duration_seconds": duration,
                    "duration_hours": round(duration / 3600, 2),
                    "is_current": i + 1 >= len(history),
                }
            )

        return durations

    def is_transition_allowed(self, entity_type: str, from_status: str, to_status: str) -> Dict:
        """Check if a status transition is allowed.

        Args:
            entity_type: Type of entity
            from_status: Current status
            to_status: Target status

        Returns:
            Dict with is_allowed and requires_reason flags
        """
        with self._get_connection() as conn:
            rule = conn.execute(
                """
                SELECT is_allowed, requires_reason
                FROM status_transitions
                WHERE entity_type = ? AND from_status = ? AND to_status = ?
            """,
                (entity_type, from_status, to_status),
            ).fetchone()

            if rule:
                return {
                    "is_allowed": bool(rule["is_allowed"]),
                    "requires_reason": bool(rule["requires_reason"]),
                    "rule_defined": True,
                }
            else:
                # No rule defined - allow by default
                return {"is_allowed": True, "requires_reason": False, "rule_defined": False}

    def get_allowed_transitions(self, entity_type: str, current_status: str) -> List[str]:
        """Get list of allowed next statuses.

        Args:
            entity_type: Type of entity
            current_status: Current status

        Returns:
            List of allowed target statuses
        """
        with self._get_connection() as conn:
            transitions = conn.execute(
                """
                SELECT to_status
                FROM status_transitions
                WHERE entity_type = ? AND from_status = ? AND is_allowed = 1
                ORDER BY to_status
            """,
                (entity_type, current_status),
            ).fetchall()

            return [t["to_status"] for t in transitions]

    def _parse_record(self, record: sqlite3.Row) -> Dict:
        """Parse a history record, deserializing metadata."""
        result = dict(record)
        if result.get("metadata"):
            try:
                result["metadata"] = json.loads(result["metadata"])
            except json.JSONDecodeError:
                pass
        return result


# Singleton getter
_service_instance = None
_service_lock = threading.Lock()


def get_status_history_service(db_path: str = None) -> StatusHistoryService:
    global _service_instance
    if _service_instance is None or db_path:
        with _service_lock:
            if _service_instance is None or db_path:
                _service_instance = StatusHistoryService(db_path)
    return _service_instance


# Convenience function for recording changes
def record_status_change(
    db_path: str,
    entity_type: str,
    entity_id: int,
    old_status: str,
    new_status: str,
    changed_by: str = None,
    change_source: str = SOURCE_API,
) -> Optional[Dict]:
    """Convenience function to record a status change."""
    service = get_status_history_service(db_path)
    return service.record_change(
        entity_type=entity_type,
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        change_source=change_source,
    )
