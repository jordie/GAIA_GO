"""
App Manager - Manages application lifecycle and autopilot state

Each app can be in one of these autopilot modes:
- observe: Detect + propose changes (no automatic action)
- fix_forward: Auto PR + auto test (no deploy)
- auto_staging: Auto deploy to staging after tests pass
- auto_prod: Auto deploy to prod (with approval gates)
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


class AppManager:
    def __init__(self, db_path: str = None):
        """Initialize AppManager. db_path is kept for backward compatibility but not used."""
        self.db_path = db_path  # Kept for compatibility, actual path from db module

    def _get_conn(self):
        """Get a database connection context manager."""
        return get_connection()

    def create_app(self, name: str, source_path: str, **kwargs) -> int:
        """Create a new managed application."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO apps (name, source_path, description, repo_url, goal, constraints,
                                  dev_url, staging_url, prod_url, autopilot_mode, risk_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    name,
                    source_path,
                    kwargs.get("description"),
                    kwargs.get("repo_url"),
                    kwargs.get("goal"),
                    json.dumps(kwargs.get("constraints", {})),
                    kwargs.get("dev_url"),
                    kwargs.get("staging_url"),
                    kwargs.get("prod_url"),
                    kwargs.get("autopilot_mode", "observe"),
                    kwargs.get("risk_level", "medium"),
                ),
            )
            return cursor.lastrowid

    def get_app(self, app_id: int) -> Optional[Dict[str, Any]]:
        """Get app by ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM apps WHERE id = ?", (app_id,)).fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def list_apps(self, autopilot_enabled: Optional[bool] = None) -> List[Dict[str, Any]]:
        """List all apps, optionally filtered by autopilot status."""
        with self._get_conn() as conn:
            if autopilot_enabled is not None:
                rows = conn.execute(
                    "SELECT * FROM apps WHERE autopilot_enabled = ? ORDER BY updated_at DESC",
                    (1 if autopilot_enabled else 0,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM apps ORDER BY updated_at DESC").fetchall()
            return [self._row_to_dict(row) for row in rows]

    def update_app(self, app_id: int, **kwargs) -> bool:
        """Update app configuration."""
        allowed_fields = {
            "name",
            "description",
            "source_path",
            "repo_url",
            "goal",
            "constraints",
            "autopilot_mode",
            "autopilot_enabled",
            "risk_level",
            "dev_url",
            "staging_url",
            "prod_url",
            "current_phase",
            "current_run_id",
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        # Handle JSON fields
        if "constraints" in updates and isinstance(updates["constraints"], dict):
            updates["constraints"] = json.dumps(updates["constraints"])

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [app_id]

        with self._get_conn() as conn:
            conn.execute(f"UPDATE apps SET {set_clause} WHERE id = ?", values)
            return True

    def enable_autopilot(self, app_id: int, mode: str = "observe") -> bool:
        """Enable autopilot for an app."""
        return self.update_app(app_id, autopilot_enabled=True, autopilot_mode=mode)

    def disable_autopilot(self, app_id: int) -> bool:
        """Disable autopilot for an app."""
        return self.update_app(app_id, autopilot_enabled=False, current_phase="idle")

    def set_goal(self, app_id: int, goal: str, constraints: Optional[Dict] = None) -> bool:
        """Set the improvement goal for an app."""
        updates = {"goal": goal}
        if constraints:
            updates["constraints"] = constraints
        return self.update_app(app_id, **updates)

    def update_phase(self, app_id: int, phase: str) -> bool:
        """Update the current phase of an app."""
        valid_phases = [
            "idle",
            "planning",
            "implementing",
            "testing",
            "deploying",
            "monitoring",
            "investigating",
        ]
        if phase not in valid_phases:
            raise ValueError(f"Invalid phase: {phase}")
        return self.update_app(app_id, current_phase=phase)

    def get_apps_needing_runs(self) -> List[Dict[str, Any]]:
        """Get apps that are enabled for autopilot and not currently running."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT a.* FROM apps a
                LEFT JOIN runs r ON a.current_run_id = r.id
                WHERE a.autopilot_enabled = 1
                AND (a.current_phase = 'idle' OR a.current_phase = 'monitoring')
                AND (r.id IS NULL OR r.status IN ('completed', 'failed', 'cancelled'))
            """
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def get_app_status(self, app_id: int) -> Dict[str, Any]:
        """Get detailed status for an app including current run and recent milestones."""
        app = self.get_app(app_id)
        if not app:
            return None

        with self._get_conn() as conn:
            # Get current run if any
            if app["current_run_id"]:
                run = conn.execute(
                    "SELECT * FROM runs WHERE id = ?", (app["current_run_id"],)
                ).fetchone()
                app["current_run"] = self._row_to_dict(run) if run else None

            # Get recent milestones
            milestones = conn.execute(
                """
                SELECT * FROM milestones
                WHERE app_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            """,
                (app_id,),
            ).fetchall()
            app["recent_milestones"] = [self._row_to_dict(m) for m in milestones]

            # Get pending review items
            review_items = conn.execute(
                """
                SELECT * FROM review_queue
                WHERE app_id = ? AND status = 'pending'
                ORDER BY priority DESC, created_at ASC
            """,
                (app_id,),
            ).fetchall()
            app["pending_reviews"] = [self._row_to_dict(r) for r in review_items]

            # Get recent incidents
            incidents = conn.execute(
                """
                SELECT * FROM incidents
                WHERE app_id = ? AND status IN ('open', 'investigating')
                ORDER BY severity DESC, created_at DESC
                LIMIT 5
            """,
                (app_id,),
            ).fetchall()
            app["active_incidents"] = [self._row_to_dict(i) for i in incidents]

            return app

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite Row to a dictionary, parsing JSON fields."""
        d = dict(row)
        # Parse JSON fields
        for field in ["constraints", "risk_factors", "blast_radius", "rollback_steps", "metadata"]:
            if field in d and d[field]:
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
