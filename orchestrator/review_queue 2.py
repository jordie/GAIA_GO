"""
Review Queue Manager - Manages items awaiting user action

The review queue is the primary interface for user interaction:
- Ready for approval (milestones)
- Incidents (errors, regressions)
- Blocked (need input)
- Needs input (clarifying questions)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths
ORCHESTRATOR_DIR = Path(__file__).parent
BASE_DIR = ORCHESTRATOR_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import get_connection


class ReviewQueueManager:
    def __init__(self, db_path: str = None):
        """Initialize ReviewQueueManager. db_path kept for backward compatibility."""
        self.db_path = db_path

    def _get_conn(self):
        """Get a database connection context manager."""
        return get_connection()

    def get_queue_summary(self) -> Dict[str, int]:
        """Get counts of items by type for the queue header."""
        with self._get_conn() as conn:
            result = {
                "ready_for_approval": 0,
                "incidents": 0,
                "blocked": 0,
                "needs_input": 0,
                "total": 0,
            }

            # Count by item type
            rows = conn.execute(
                """
                SELECT item_type, COUNT(*) as count
                FROM review_queue
                WHERE status = 'pending'
                GROUP BY item_type
            """
            ).fetchall()

            for row in rows:
                if row["item_type"] == "milestone":
                    result["ready_for_approval"] = row["count"]
                elif row["item_type"] == "incident":
                    result["incidents"] = row["count"]
                elif row["item_type"] == "blocked":
                    result["blocked"] = row["count"]
                elif row["item_type"] == "input_needed":
                    result["needs_input"] = row["count"]

            result["total"] = sum(
                [
                    result["ready_for_approval"],
                    result["incidents"],
                    result["blocked"],
                    result["needs_input"],
                ]
            )

            return result

    def get_queue_items(
        self, item_type: str = None, app_id: int = None, status: str = "pending"
    ) -> List[Dict[str, Any]]:
        """Get items from the review queue."""
        with self._get_conn() as conn:
            query = """
                SELECT rq.*, a.name as app_name, a.source_path
                FROM review_queue rq
                JOIN apps a ON rq.app_id = a.id
                WHERE rq.status = ?
            """
            params = [status]

            if item_type:
                query += " AND rq.item_type = ?"
                params.append(item_type)

            if app_id:
                query += " AND rq.app_id = ?"
                params.append(app_id)

            query += " ORDER BY rq.priority DESC, rq.created_at ASC"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def add_to_queue(
        self,
        item_type: str,
        item_id: int,
        app_id: int,
        title: str,
        summary: str = None,
        priority: str = "normal",
        run_id: int = None,
        available_actions: List[str] = None,
    ) -> int:
        """Add an item to the review queue."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO review_queue (item_type, item_id, app_id, run_id, priority, title, summary, available_actions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item_type,
                    item_id,
                    app_id,
                    run_id,
                    priority,
                    title,
                    summary,
                    json.dumps(available_actions) if available_actions else None,
                ),
            )
            return cursor.lastrowid

    def resolve_item(self, queue_id: int, resolution: str, resolved_by: str = None) -> bool:
        """Resolve an item in the queue."""
        with self._get_conn() as conn:
            now = datetime.utcnow().isoformat()
            conn.execute(
                """
                UPDATE review_queue
                SET status = 'resolved',
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution = ?
                WHERE id = ?
            """,
                (now, resolved_by, resolution, queue_id),
            )
            return True

    def dismiss_item(self, queue_id: int, resolved_by: str = None) -> bool:
        """Dismiss an item from the queue."""
        with self._get_conn() as conn:
            now = datetime.utcnow().isoformat()
            conn.execute(
                """
                UPDATE review_queue
                SET status = 'dismissed',
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution = 'dismissed'
                WHERE id = ?
            """,
                (now, resolved_by, queue_id),
            )
            return True

    def add_incident(
        self,
        app_id: int,
        title: str,
        description: str,
        severity: str = "warning",
        source: str = None,
        source_details: Dict = None,
        suspected_commit: str = None,
        run_id: int = None,
        proposed_fix: str = None,
        fix_confidence: int = None,
    ) -> int:
        """Add an incident and put it in the review queue."""
        with self._get_conn() as conn:
            # Create incident
            cursor = conn.execute(
                """
                INSERT INTO incidents (app_id, run_id, severity, title, description,
                                       source, source_details, suspected_commit,
                                       proposed_fix, fix_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    app_id,
                    run_id,
                    severity,
                    title,
                    description,
                    source,
                    json.dumps(source_details) if source_details else None,
                    suspected_commit,
                    proposed_fix,
                    fix_confidence,
                ),
            )
            incident_id = cursor.lastrowid

            # Determine priority
            priority = "normal"
            if severity == "critical":
                priority = "critical"
            elif severity == "error":
                priority = "high"

            # Add to review queue
            actions = ["investigate", "resolve", "dismiss"]
            if proposed_fix:
                actions.insert(0, "apply_fix")

            conn.execute(
                """
                INSERT INTO review_queue (item_type, item_id, app_id, run_id, priority, title, summary, available_actions)
                VALUES ('incident', ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    incident_id,
                    app_id,
                    run_id,
                    priority,
                    title,
                    description[:200] if description else None,
                    json.dumps(actions),
                ),
            )

            return incident_id

    def add_blocked_item(
        self,
        app_id: int,
        run_id: int,
        title: str,
        reason: str,
        question: str = None,
        options: List[Dict] = None,
    ) -> int:
        """Add a blocked item to the queue with a specific question."""
        with self._get_conn() as conn:
            # Create a record in review_queue
            actions = ["unblock", "pause", "cancel_run"]
            if options:
                actions = [o.get("action", "select") for o in options] + actions

            cursor = conn.execute(
                """
                INSERT INTO review_queue (item_type, item_id, app_id, run_id, priority, title, summary, available_actions)
                VALUES ('blocked', ?, ?, ?, 'high', ?, ?, ?)
            """,
                (
                    0,  # No separate table for blocked items yet
                    app_id,
                    run_id,
                    title,
                    json.dumps({"reason": reason, "question": question, "options": options}),
                    json.dumps(actions),
                ),
            )
            return cursor.lastrowid

    def get_item_details(self, queue_id: int) -> Optional[Dict[str, Any]]:
        """Get full details for a queue item including related data."""
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT rq.*, a.name as app_name, a.source_path, a.current_phase
                FROM review_queue rq
                JOIN apps a ON rq.app_id = a.id
                WHERE rq.id = ?
            """,
                (queue_id,),
            ).fetchone()

            if not row:
                return None

            item = self._row_to_dict(row)

            # Get related data based on item type
            if item["item_type"] == "milestone":
                milestone = conn.execute(
                    "SELECT * FROM milestones WHERE id = ?", (item["item_id"],)
                ).fetchone()
                if milestone:
                    item["milestone"] = dict(milestone)

                    # Get artifacts for this milestone
                    artifacts = conn.execute(
                        """
                        SELECT * FROM artifacts WHERE milestone_id = ?
                    """,
                        (item["item_id"],),
                    ).fetchall()
                    item["artifacts"] = [dict(a) for a in artifacts]

            elif item["item_type"] == "incident":
                incident = conn.execute(
                    "SELECT * FROM incidents WHERE id = ?", (item["item_id"],)
                ).fetchone()
                if incident:
                    item["incident"] = dict(incident)

            # Get run info if available
            if item.get("run_id"):
                run = conn.execute("SELECT * FROM runs WHERE id = ?", (item["run_id"],)).fetchone()
                if run:
                    item["run"] = dict(run)

            return item

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite Row to a dictionary."""
        d = dict(row)
        for field in ["available_actions", "summary"]:
            if field in d and d[field]:
                try:
                    # Try to parse as JSON
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
