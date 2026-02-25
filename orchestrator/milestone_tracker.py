"""
Milestone Tracker - Creates and manages Milestone Evidence Packets

A milestone evidence packet contains:
1. What changed (diff summary, commits, files touched)
2. Why it changed (plan → decision trail)
3. Proof it works (test results, metrics)
4. Risk & rollback (risk score, rollback steps)
5. Actions (approve, reject, request changes)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths
ORCHESTRATOR_DIR = Path(__file__).parent
BASE_DIR = ORCHESTRATOR_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import get_connection


class MilestoneTracker:
    def __init__(self, db_path: str = None):
        """Initialize MilestoneTracker. db_path kept for backward compatibility."""
        self.db_path = db_path

    def _get_conn(self):
        """Get a database connection context manager."""
        return get_connection()

    def create_milestone(
        self,
        app_id: int,
        name: str,
        milestone_type: str = "feature",
        description: str = None,
        run_id: int = None,
    ) -> int:
        """Create a new milestone."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO milestones (app_id, run_id, name, description, milestone_type, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """,
                (app_id, run_id, name, description, milestone_type),
            )
            return cursor.lastrowid

    def get_milestone(self, milestone_id: int) -> Optional[Dict[str, Any]]:
        """Get milestone by ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_evidence_packet(self, milestone_id: int) -> Dict[str, Any]:
        """Get complete evidence packet for a milestone."""
        milestone = self.get_milestone(milestone_id)
        if not milestone:
            return None

        with self._get_conn() as conn:
            # Get app info
            app = conn.execute("SELECT * FROM apps WHERE id = ?", (milestone["app_id"],)).fetchone()
            milestone["app"] = dict(app) if app else None

            # Get related artifacts
            artifacts = conn.execute(
                """
                SELECT * FROM artifacts WHERE milestone_id = ? ORDER BY created_at
            """,
                (milestone_id,),
            ).fetchall()
            milestone["artifacts"] = [self._row_to_dict(a) for a in artifacts]

            # Group artifacts by type
            milestone["evidence"] = {
                "what_changed": self._get_what_changed(milestone["artifacts"]),
                "why_changed": self._get_why_changed(milestone["artifacts"]),
                "proof": self._get_proof(milestone["artifacts"]),
                "risk": {
                    "score": milestone.get("risk_score", 0),
                    "factors": milestone.get("risk_factors", []),
                    "blast_radius": milestone.get("blast_radius", {}),
                    "rollback_steps": milestone.get("rollback_steps", []),
                    "rollback_available": milestone.get("rollback_available", True),
                },
            }

            # Get run info if available
            if milestone.get("run_id"):
                run = conn.execute(
                    "SELECT * FROM runs WHERE id = ?", (milestone["run_id"],)
                ).fetchone()
                milestone["run"] = dict(run) if run else None

            return milestone

    def _get_what_changed(self, artifacts: List[Dict]) -> Dict[str, Any]:
        """Extract 'what changed' evidence from artifacts."""
        result = {
            "commits": [],
            "prs": [],
            "files_changed": [],
            "diff_summary": None,
            "config_changes": [],
            "migrations": [],
        }

        for a in artifacts:
            if a["artifact_type"] == "commit":
                result["commits"].append(
                    {
                        "sha": a.get("metadata", {}).get("sha"),
                        "message": a["title"],
                        "url": a.get("url"),
                    }
                )
            elif a["artifact_type"] == "pr":
                result["prs"].append(
                    {
                        "number": a.get("metadata", {}).get("number"),
                        "title": a["title"],
                        "url": a.get("url"),
                    }
                )
            elif a["artifact_type"] == "diff_summary":
                result["diff_summary"] = a["content"]
                result["files_changed"] = a.get("metadata", {}).get("files", [])

        return result

    def _get_why_changed(self, artifacts: List[Dict]) -> Dict[str, Any]:
        """Extract 'why changed' evidence from artifacts."""
        result = {"goal": None, "plan": None, "decision_trail": [], "alternatives_considered": []}

        for a in artifacts:
            if a["artifact_type"] == "plan":
                result["plan"] = a["content"]
            elif a["artifact_type"] == "decision_trail":
                result["decision_trail"].append(
                    {
                        "title": a["title"],
                        "content": a["content"],
                        "metadata": a.get("metadata", {}),
                    }
                )

        return result

    def _get_proof(self, artifacts: List[Dict]) -> Dict[str, Any]:
        """Extract 'proof it works' evidence from artifacts."""
        result = {
            "test_reports": [],
            "screenshots": [],
            "benchmarks": [],
            "metric_deltas": [],
            "error_rate_comparison": None,
        }

        for a in artifacts:
            if a["artifact_type"] == "test_report":
                result["test_reports"].append(
                    {
                        "title": a["title"],
                        "content": a["content"],
                        "passed": a.get("metadata", {}).get("passed", 0),
                        "failed": a.get("metadata", {}).get("failed", 0),
                        "skipped": a.get("metadata", {}).get("skipped", 0),
                    }
                )
            elif a["artifact_type"] == "screenshot":
                result["screenshots"].append(
                    {"title": a["title"], "file_path": a.get("file_path"), "url": a.get("url")}
                )
            elif a["artifact_type"] == "benchmark":
                result["benchmarks"].append(
                    {
                        "title": a["title"],
                        "content": a["content"],
                        "metadata": a.get("metadata", {}),
                    }
                )

        return result

    def mark_ready_for_review(
        self,
        milestone_id: int,
        risk_score: int = 0,
        risk_factors: List[str] = None,
        blast_radius: Dict = None,
        rollback_steps: List[str] = None,
    ) -> bool:
        """Mark a milestone as ready for review and add to review queue."""
        with self._get_conn() as conn:
            now = datetime.utcnow().isoformat()

            conn.execute(
                """
                UPDATE milestones
                SET status = 'ready_for_review',
                    ready_at = ?,
                    risk_score = ?,
                    risk_factors = ?,
                    blast_radius = ?,
                    rollback_steps = ?
                WHERE id = ?
            """,
                (
                    now,
                    risk_score,
                    json.dumps(risk_factors) if risk_factors else None,
                    json.dumps(blast_radius) if blast_radius else None,
                    json.dumps(rollback_steps) if rollback_steps else None,
                    milestone_id,
                ),
            )

            # Get milestone info for review queue
            milestone = conn.execute(
                "SELECT * FROM milestones WHERE id = ?", (milestone_id,)
            ).fetchone()

            # Determine priority based on risk
            priority = "normal"
            if risk_score >= 80:
                priority = "critical"
            elif risk_score >= 60:
                priority = "high"

            # Add to review queue
            conn.execute(
                """
                INSERT INTO review_queue (item_type, item_id, app_id, run_id, priority, title, summary, available_actions)
                VALUES ('milestone', ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    milestone_id,
                    milestone["app_id"],
                    milestone["run_id"],
                    priority,
                    milestone["name"],
                    milestone["description"] or f"Milestone ready for review: {milestone['name']}",
                    json.dumps(["approve", "reject", "request_changes"]),
                ),
            )

            return True

    def approve_milestone(self, milestone_id: int, reviewer: str = None, notes: str = None) -> bool:
        """Approve a milestone."""
        with self._get_conn() as conn:
            now = datetime.utcnow().isoformat()

            conn.execute(
                """
                UPDATE milestones
                SET status = 'approved',
                    reviewed_at = ?,
                    reviewed_by = ?,
                    reviewer_notes = ?
                WHERE id = ?
            """,
                (now, reviewer, notes, milestone_id),
            )

            # Resolve review queue item
            conn.execute(
                """
                UPDATE review_queue
                SET status = 'resolved',
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution = 'approved'
                WHERE item_type = 'milestone' AND item_id = ?
            """,
                (now, reviewer, milestone_id),
            )

            return True

    def reject_milestone(self, milestone_id: int, reviewer: str = None, notes: str = None) -> bool:
        """Reject a milestone."""
        with self._get_conn() as conn:
            now = datetime.utcnow().isoformat()

            conn.execute(
                """
                UPDATE milestones
                SET status = 'rejected',
                    reviewed_at = ?,
                    reviewed_by = ?,
                    reviewer_notes = ?
                WHERE id = ?
            """,
                (now, reviewer, notes, milestone_id),
            )

            # Resolve review queue item
            conn.execute(
                """
                UPDATE review_queue
                SET status = 'resolved',
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution = 'rejected'
                WHERE item_type = 'milestone' AND item_id = ?
            """,
                (now, reviewer, milestone_id),
            )

            return True

    def request_changes(self, milestone_id: int, reviewer: str = None, notes: str = None) -> bool:
        """Request changes on a milestone."""
        with self._get_conn() as conn:
            now = datetime.utcnow().isoformat()

            conn.execute(
                """
                UPDATE milestones
                SET status = 'changes_requested',
                    reviewed_at = ?,
                    reviewed_by = ?,
                    reviewer_notes = ?
                WHERE id = ?
            """,
                (now, reviewer, notes, milestone_id),
            )

            # Update review queue item status
            conn.execute(
                """
                UPDATE review_queue
                SET status = 'resolved',
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution = 'changes_requested'
                WHERE item_type = 'milestone' AND item_id = ?
            """,
                (now, reviewer, milestone_id),
            )

            return True

    def get_pending_milestones(self, app_id: int = None) -> List[Dict[str, Any]]:
        """Get milestones awaiting review."""
        with self._get_conn() as conn:
            if app_id:
                rows = conn.execute(
                    """
                    SELECT m.*, a.name as app_name
                    FROM milestones m
                    JOIN apps a ON m.app_id = a.id
                    WHERE m.app_id = ? AND m.status = 'ready_for_review'
                    ORDER BY m.ready_at DESC
                """,
                    (app_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT m.*, a.name as app_name
                    FROM milestones m
                    JOIN apps a ON m.app_id = a.id
                    WHERE m.status = 'ready_for_review'
                    ORDER BY m.ready_at DESC
                """
                ).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite Row to a dictionary."""
        d = dict(row)
        for field in ["risk_factors", "blast_radius", "rollback_steps", "metadata"]:
            if field in d and d[field]:
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
