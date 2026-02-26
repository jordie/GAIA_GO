"""
AI Task Suggestions Service

Provides intelligent task recommendations based on project state,
priorities, dependencies, and historical patterns.

Usage:
    from services.task_suggestions import get_suggestion_service

    service = get_suggestion_service(db_path)
    suggestions = service.get_suggestions()
"""

import json
import logging
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Suggestion types
SUGGESTION_NEXT_TASK = "next_task"  # What to work on next
SUGGESTION_BLOCKED = "blocked"  # Unblock a blocked item
SUGGESTION_OVERDUE = "overdue"  # Address overdue items
SUGGESTION_DEPENDENCY = "dependency"  # Complete dependencies first
SUGGESTION_HIGH_PRIORITY = "high_priority"  # High priority items
SUGGESTION_QUICK_WIN = "quick_win"  # Easy wins to build momentum
SUGGESTION_STALE = "stale"  # Items needing attention
SUGGESTION_REVIEW = "review"  # Items ready for review
SUGGESTION_BOTTLENECK = "bottleneck"  # Bottleneck resolution
SUGGESTION_BALANCE = "balance"  # Workload balancing


class TaskSuggestionService:
    """Service for generating intelligent task suggestions."""

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

    def get_suggestions(
        self,
        project_id: int = None,
        user_id: str = None,
        limit: int = 10,
        include_types: List[str] = None,
    ) -> Dict:
        """Get AI-powered task suggestions.

        Args:
            project_id: Filter by project (optional)
            user_id: Personalize for user (optional)
            limit: Maximum suggestions to return
            include_types: Filter by suggestion types (optional)

        Returns:
            Dict with suggestions and reasoning
        """
        with self._get_connection() as conn:
            suggestions = []

            # Gather all suggestion types
            if not include_types or SUGGESTION_HIGH_PRIORITY in include_types:
                suggestions.extend(self._get_high_priority_suggestions(conn, project_id))

            if not include_types or SUGGESTION_BLOCKED in include_types:
                suggestions.extend(self._get_blocked_suggestions(conn, project_id))

            if not include_types or SUGGESTION_OVERDUE in include_types:
                suggestions.extend(self._get_overdue_suggestions(conn, project_id))

            if not include_types or SUGGESTION_DEPENDENCY in include_types:
                suggestions.extend(self._get_dependency_suggestions(conn, project_id))

            if not include_types or SUGGESTION_QUICK_WIN in include_types:
                suggestions.extend(self._get_quick_win_suggestions(conn, project_id))

            if not include_types or SUGGESTION_STALE in include_types:
                suggestions.extend(self._get_stale_suggestions(conn, project_id))

            if not include_types or SUGGESTION_REVIEW in include_types:
                suggestions.extend(self._get_review_suggestions(conn, project_id))

            if not include_types or SUGGESTION_BOTTLENECK in include_types:
                suggestions.extend(self._get_bottleneck_suggestions(conn, project_id))

            if not include_types or SUGGESTION_NEXT_TASK in include_types:
                suggestions.extend(self._get_next_task_suggestions(conn, project_id, user_id))

            # Score and rank suggestions
            scored = self._score_suggestions(suggestions, user_id, conn)

            # Sort by score and limit
            scored.sort(key=lambda x: x["score"], reverse=True)
            top_suggestions = scored[:limit]

            # Get summary stats
            summary = self._get_suggestion_summary(conn, project_id)

            return {
                "suggestions": top_suggestions,
                "count": len(top_suggestions),
                "total_candidates": len(suggestions),
                "summary": summary,
                "generated_at": datetime.now().isoformat(),
            }

    def _get_high_priority_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for high priority items."""
        suggestions = []

        # High priority features not started
        conditions = ["status IN ('planned', 'draft')", "priority IN ('critical', 'high')"]
        params = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        features = conn.execute(
            f"""
            SELECT f.*, p.name as project_name
            FROM features f
            LEFT JOIN projects p ON f.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 END,
                created_at ASC
            LIMIT 5
        """,
            params,
        ).fetchall()

        for f in features:
            suggestions.append(
                {
                    "type": SUGGESTION_HIGH_PRIORITY,
                    "entity_type": "feature",
                    "entity_id": f["id"],
                    "title": f["name"],
                    "description": f"High priority feature waiting to be started",
                    "reason": f"Priority: {f['priority']}. Created {self._time_ago(f['created_at'])}",
                    "action": "Start working on this feature",
                    "priority": f["priority"],
                    "project_name": f["project_name"],
                    "base_score": 90 if f["priority"] == "critical" else 80,
                }
            )

        # Critical bugs
        conditions = ["status = 'open'", "severity IN ('critical', 'high')"]
        params = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        bugs = conn.execute(
            f"""
            SELECT b.*, p.name as project_name
            FROM bugs b
            LEFT JOIN projects p ON b.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 END,
                created_at ASC
            LIMIT 5
        """,
            params,
        ).fetchall()

        for b in bugs:
            suggestions.append(
                {
                    "type": SUGGESTION_HIGH_PRIORITY,
                    "entity_type": "bug",
                    "entity_id": b["id"],
                    "title": b["title"],
                    "description": f"Critical bug needs immediate attention",
                    "reason": f"Severity: {b['severity']}. Reported {self._time_ago(b['created_at'])}",
                    "action": "Fix this bug",
                    "priority": b["severity"],
                    "project_name": b["project_name"],
                    "base_score": 95 if b["severity"] == "critical" else 85,
                }
            )

        return suggestions

    def _get_blocked_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for blocked items that need unblocking."""
        suggestions = []

        conditions = ["status = 'blocked'"]
        params = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        features = conn.execute(
            f"""
            SELECT f.*, p.name as project_name
            FROM features f
            LEFT JOIN projects p ON f.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                updated_at ASC
            LIMIT 5
        """,
            params,
        ).fetchall()

        for f in features:
            blocked_duration = self._time_ago(f["updated_at"])
            suggestions.append(
                {
                    "type": SUGGESTION_BLOCKED,
                    "entity_type": "feature",
                    "entity_id": f["id"],
                    "title": f["name"],
                    "description": f"Feature blocked for {blocked_duration}",
                    "reason": f"Blocked items slow down the entire project",
                    "action": "Investigate and resolve the blocker",
                    "priority": f["priority"] or "medium",
                    "project_name": f["project_name"],
                    "base_score": 75,
                }
            )

        return suggestions

    def _get_overdue_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for overdue milestones and tasks."""
        suggestions = []
        today = datetime.now().date()

        # Overdue milestones
        conditions = ["target_date < ?", "status != 'completed'"]
        params = [str(today)]
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        milestones = conn.execute(
            f"""
            SELECT m.*, p.name as project_name,
                   (SELECT COUNT(*) FROM features WHERE milestone_id = m.id AND status != 'completed') as pending_features,
                   (SELECT COUNT(*) FROM bugs WHERE milestone_id = m.id AND status NOT IN ('resolved', 'closed')) as pending_bugs
            FROM milestones m
            LEFT JOIN projects p ON m.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY target_date ASC
            LIMIT 5
        """,
            params,
        ).fetchall()

        for m in milestones:
            days_overdue = (today - datetime.strptime(m["target_date"], "%Y-%m-%d").date()).days
            suggestions.append(
                {
                    "type": SUGGESTION_OVERDUE,
                    "entity_type": "milestone",
                    "entity_id": m["id"],
                    "title": m["name"],
                    "description": f"Milestone is {days_overdue} days overdue",
                    "reason": f"{m['pending_features']} features and {m['pending_bugs']} bugs remaining",
                    "action": "Prioritize remaining items or adjust target date",
                    "priority": "high",
                    "project_name": m["project_name"],
                    "base_score": min(70 + days_overdue, 90),
                    "days_overdue": days_overdue,
                }
            )

        return suggestions

    def _get_dependency_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for completing dependencies."""
        suggestions = []

        # Find tasks that block other tasks
        try:
            blockers = conn.execute(
                """
                SELECT
                    tq.id, tq.task_type, tq.status, tq.priority,
                    COUNT(td.dependent_task_id) as blocks_count
                FROM task_queue tq
                JOIN task_dependencies td ON tq.id = td.blocking_task_id
                WHERE tq.status IN ('pending', 'running')
                GROUP BY tq.id
                HAVING blocks_count > 0
                ORDER BY blocks_count DESC, priority DESC
                LIMIT 5
            """
            ).fetchall()

            for t in blockers:
                suggestions.append(
                    {
                        "type": SUGGESTION_DEPENDENCY,
                        "entity_type": "task",
                        "entity_id": t["id"],
                        "title": f"Task #{t['id']} ({t['task_type']})",
                        "description": f"Blocks {t['blocks_count']} other task(s)",
                        "reason": "Completing this will unblock dependent tasks",
                        "action": "Prioritize this blocking task",
                        "priority": "high",
                        "base_score": 70 + min(t["blocks_count"] * 5, 20),
                    }
                )
        except sqlite3.OperationalError:
            # task_dependencies table might not exist
            pass

        return suggestions

    def _get_quick_win_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for quick wins (easy tasks)."""
        suggestions = []

        # Low complexity features not started
        conditions = [
            "status IN ('planned', 'draft')",
            "(estimated_hours IS NULL OR estimated_hours <= 4)",
            "priority NOT IN ('critical')",
        ]
        params = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        features = conn.execute(
            f"""
            SELECT f.*, p.name as project_name
            FROM features f
            LEFT JOIN projects p ON f.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY estimated_hours ASC NULLS FIRST, created_at ASC
            LIMIT 5
        """,
            params,
        ).fetchall()

        for f in features:
            hours = f["estimated_hours"] or "few"
            suggestions.append(
                {
                    "type": SUGGESTION_QUICK_WIN,
                    "entity_type": "feature",
                    "entity_id": f["id"],
                    "title": f["name"],
                    "description": f"Quick win - estimated {hours} hours",
                    "reason": "Easy tasks build momentum and show progress",
                    "action": "Complete this for a quick win",
                    "priority": f["priority"] or "medium",
                    "project_name": f["project_name"],
                    "base_score": 50,
                    "estimated_hours": f["estimated_hours"],
                }
            )

        # Low severity bugs
        conditions = ["status = 'open'", "severity = 'low'"]
        params = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        bugs = conn.execute(
            f"""
            SELECT b.*, p.name as project_name
            FROM bugs b
            LEFT JOIN projects p ON b.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at ASC
            LIMIT 3
        """,
            params,
        ).fetchall()

        for b in bugs:
            suggestions.append(
                {
                    "type": SUGGESTION_QUICK_WIN,
                    "entity_type": "bug",
                    "entity_id": b["id"],
                    "title": b["title"],
                    "description": "Low severity bug - good for quick resolution",
                    "reason": "Clearing small bugs improves overall quality",
                    "action": "Fix this minor bug",
                    "priority": "low",
                    "project_name": b["project_name"],
                    "base_score": 40,
                }
            )

        return suggestions

    def _get_stale_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for stale items needing attention."""
        suggestions = []
        stale_threshold = datetime.now() - timedelta(days=14)

        # In-progress features with no recent updates
        conditions = ["status = 'in_progress'", "updated_at < ?"]
        params = [stale_threshold.isoformat()]
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        features = conn.execute(
            f"""
            SELECT f.*, p.name as project_name
            FROM features f
            LEFT JOIN projects p ON f.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY updated_at ASC
            LIMIT 5
        """,
            params,
        ).fetchall()

        for f in features:
            days_stale = (
                datetime.now()
                - datetime.fromisoformat(
                    f["updated_at"].replace("Z", "+00:00")
                    if "Z" in str(f["updated_at"])
                    else f["updated_at"]
                )
            ).days
            suggestions.append(
                {
                    "type": SUGGESTION_STALE,
                    "entity_type": "feature",
                    "entity_id": f["id"],
                    "title": f["name"],
                    "description": f"No updates for {days_stale} days",
                    "reason": "Stale items may need reassignment or have hidden blockers",
                    "action": "Check status and update or reassign",
                    "priority": f["priority"] or "medium",
                    "project_name": f["project_name"],
                    "base_score": 55,
                    "days_stale": days_stale,
                }
            )

        return suggestions

    def _get_review_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for items ready for review."""
        suggestions = []

        conditions = ["status = 'review'"]
        params = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        features = conn.execute(
            f"""
            SELECT f.*, p.name as project_name
            FROM features f
            LEFT JOIN projects p ON f.project_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY updated_at ASC
            LIMIT 5
        """,
            params,
        ).fetchall()

        for f in features:
            waiting_time = self._time_ago(f["updated_at"])
            suggestions.append(
                {
                    "type": SUGGESTION_REVIEW,
                    "entity_type": "feature",
                    "entity_id": f["id"],
                    "title": f["name"],
                    "description": f"Waiting for review since {waiting_time}",
                    "reason": "Reviews prevent bottlenecks in the pipeline",
                    "action": "Review and approve or request changes",
                    "priority": f["priority"] or "medium",
                    "project_name": f["project_name"],
                    "base_score": 65,
                }
            )

        return suggestions

    def _get_bottleneck_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None
    ) -> List[Dict]:
        """Get suggestions for resolving bottlenecks."""
        suggestions = []

        # Find status with most items (potential bottleneck)
        status_counts = conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM features
            WHERE status NOT IN ('completed', 'cancelled')
            GROUP BY status
            ORDER BY count DESC
            LIMIT 3
        """
        ).fetchall()

        if status_counts and len(status_counts) > 0:
            top_status = status_counts[0]
            if top_status["count"] >= 5:
                suggestions.append(
                    {
                        "type": SUGGESTION_BOTTLENECK,
                        "entity_type": "status",
                        "entity_id": None,
                        "title": f"Bottleneck: {top_status['count']} features in '{top_status['status']}'",
                        "description": f"Many items stuck in {top_status['status']} status",
                        "reason": "Bottlenecks slow down overall throughput",
                        "action": f"Focus on moving items out of {top_status['status']}",
                        "priority": "high",
                        "base_score": 60,
                        "bottleneck_status": top_status["status"],
                        "item_count": top_status["count"],
                    }
                )

        return suggestions

    def _get_next_task_suggestions(
        self, conn: sqlite3.Connection, project_id: int = None, user_id: str = None
    ) -> List[Dict]:
        """Get suggestions for what to work on next."""
        suggestions = []

        # Get pending tasks ordered by priority and age
        conditions = ["status = 'pending'"]
        params = []
        if project_id:
            # This would need project association for tasks
            pass

        tasks = conn.execute(
            f"""
            SELECT *,
                   (julianday('now') - julianday(created_at)) as age_days
            FROM task_queue
            WHERE status = 'pending'
            AND (assigned_worker IS NULL OR assigned_worker = '')
            ORDER BY priority DESC, created_at ASC
            LIMIT 5
        """
        ).fetchall()

        for t in tasks:
            try:
                task_data = json.loads(t["task_data"]) if t["task_data"] else {}
                task_desc = task_data.get("description", task_data.get("name", f"Task #{t['id']}"))
            except json.JSONDecodeError:
                task_desc = f"Task #{t['id']}"

            suggestions.append(
                {
                    "type": SUGGESTION_NEXT_TASK,
                    "entity_type": "task",
                    "entity_id": t["id"],
                    "title": f"{t['task_type']}: {task_desc[:50]}",
                    "description": f"Priority {t['priority']}, waiting {round(t['age_days'], 1)} days",
                    "reason": "Unassigned task ready to be claimed",
                    "action": "Claim and complete this task",
                    "priority": "high" if t["priority"] >= 5 else "medium",
                    "base_score": 45 + min(t["priority"] * 3, 30),
                }
            )

        return suggestions

    def _score_suggestions(
        self, suggestions: List[Dict], user_id: str, conn: sqlite3.Connection
    ) -> List[Dict]:
        """Score and enhance suggestions."""
        for s in suggestions:
            score = s.get("base_score", 50)

            # Boost based on priority
            priority = s.get("priority", "medium")
            if priority == "critical":
                score += 15
            elif priority == "high":
                score += 10
            elif priority == "low":
                score -= 5

            # Boost for overdue items
            if s.get("days_overdue"):
                score += min(s["days_overdue"], 10)

            # Boost for stale items
            if s.get("days_stale"):
                score += min(s["days_stale"] // 2, 10)

            # Personalization boost (if user has worked on similar items)
            if user_id and s.get("entity_type") in ("feature", "bug"):
                # Could check user's history here
                pass

            s["score"] = min(max(score, 0), 100)

        return suggestions

    def _get_suggestion_summary(self, conn: sqlite3.Connection, project_id: int = None) -> Dict:
        """Get summary statistics for context."""
        conditions = []
        params = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Feature stats
        features = conn.execute(
            f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked,
                SUM(CASE WHEN status = 'review' THEN 1 ELSE 0 END) as in_review,
                SUM(CASE WHEN status IN ('planned', 'draft') THEN 1 ELSE 0 END) as not_started
            FROM features
            {where_clause}
        """,
            params,
        ).fetchone()

        # Bug stats
        bugs = conn.execute(
            f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
                SUM(CASE WHEN severity IN ('critical', 'high') AND status = 'open' THEN 1 ELSE 0 END) as critical_open
            FROM bugs
            {where_clause}
        """,
            params,
        ).fetchone()

        # Task stats
        tasks = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running
            FROM task_queue
        """
        ).fetchone()

        return {"features": dict(features), "bugs": dict(bugs), "tasks": dict(tasks)}

    def _time_ago(self, timestamp: str) -> str:
        """Convert timestamp to human-readable 'time ago' string."""
        if not timestamp:
            return "unknown time"

        try:
            if "T" in str(timestamp):
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(timestamp)

            delta = datetime.now() - dt.replace(tzinfo=None)

            if delta.days > 30:
                return f"{delta.days // 30} months ago"
            elif delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            else:
                return "recently"
        except (ValueError, TypeError):
            return "unknown time"

    def get_personalized_suggestions(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get personalized suggestions based on user's work history."""
        with self._get_connection() as conn:
            suggestions = []

            # Get user's recent work patterns
            recent_features = conn.execute(
                """
                SELECT project_id, COUNT(*) as count
                FROM features
                WHERE assigned_to = ?
                AND updated_at > datetime('now', '-30 days')
                GROUP BY project_id
                ORDER BY count DESC
                LIMIT 3
            """,
                (user_id,),
            ).fetchall()

            # Suggest items from projects user works on
            for pf in recent_features:
                project_features = conn.execute(
                    """
                    SELECT f.*, p.name as project_name
                    FROM features f
                    LEFT JOIN projects p ON f.project_id = p.id
                    WHERE f.project_id = ?
                    AND f.status IN ('planned', 'draft')
                    AND (f.assigned_to IS NULL OR f.assigned_to = '' OR f.assigned_to = ?)
                    ORDER BY
                        CASE f.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                        f.created_at ASC
                    LIMIT 2
                """,
                    (pf["project_id"], user_id),
                ).fetchall()

                for f in project_features:
                    suggestions.append(
                        {
                            "type": "personalized",
                            "entity_type": "feature",
                            "entity_id": f["id"],
                            "title": f["name"],
                            "description": f"From a project you've been working on",
                            "reason": f"You've worked on {pf['count']} items in {f['project_name']} recently",
                            "action": "Continue work on this project",
                            "priority": f["priority"] or "medium",
                            "project_name": f["project_name"],
                            "score": 70,
                        }
                    )

            return suggestions[:limit]


# Singleton getter
_service_instance = None
_service_lock = threading.Lock()


def get_suggestion_service(db_path: str = None) -> TaskSuggestionService:
    global _service_instance
    if _service_instance is None or db_path:
        with _service_lock:
            if _service_instance is None or db_path:
                _service_instance = TaskSuggestionService(db_path)
    return _service_instance
