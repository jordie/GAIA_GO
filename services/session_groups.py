"""
Session Groups Service

Manages tmux session grouping by project with collapsible sections.
"""

import json
import logging
import sqlite3
import threading
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionGroupService:
    """Service for managing tmux session groups."""

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

    def get_sessions_grouped(self, user_id: str = None) -> Dict:
        """Get all sessions grouped by project.

        Returns:
            Dict with groups and their sessions
        """
        with self._get_connection() as conn:
            # Get sessions with project info
            sessions = conn.execute(
                """
                SELECT ts.*,
                       p.name as project_name,
                       n.hostname as node_hostname
                FROM tmux_sessions ts
                LEFT JOIN projects p ON ts.project_id = p.id
                LEFT JOIN nodes n ON ts.node_id = n.id
                ORDER BY ts.project_id, ts.session_name
            """
            ).fetchall()

            # Get user's collapsed preferences
            collapsed_groups = set()
            if user_id:
                prefs = conn.execute(
                    """
                    SELECT group_id FROM session_group_prefs
                    WHERE user_id = ? AND collapsed = 1
                """,
                    (user_id,),
                ).fetchall()
                collapsed_groups = {p["group_id"] for p in prefs}

            # Group sessions
            groups = {}
            for s in sessions:
                s_dict = dict(s)

                # Determine group
                if s_dict.get("is_worker"):
                    group_id = "workers"
                    group_name = "Workers"
                    group_icon = "⚙️"
                elif s_dict.get("project_id"):
                    group_id = f"project_{s_dict['project_id']}"
                    group_name = s_dict.get("project_name") or "Unknown Project"
                    group_icon = "📂"
                elif s_dict.get("environment"):
                    group_id = f"env_{s_dict['environment']}"
                    group_name = s_dict["environment"].title()
                    group_icon = "🌍"
                else:
                    group_id = "unassigned"
                    group_name = "Unassigned"
                    group_icon = "📁"

                if group_id not in groups:
                    groups[group_id] = {
                        "id": group_id,
                        "name": group_name,
                        "icon": group_icon,
                        "collapsed": group_id in collapsed_groups,
                        "sessions": [],
                        "attached_count": 0,
                        "total_count": 0,
                    }

                groups[group_id]["sessions"].append(s_dict)
                groups[group_id]["total_count"] += 1
                if s_dict.get("attached"):
                    groups[group_id]["attached_count"] += 1

            # Sort groups: projects first, then env, then workers, then unassigned
            sorted_groups = sorted(
                groups.values(),
                key=lambda g: (
                    0
                    if g["id"].startswith("project_")
                    else 1
                    if g["id"].startswith("env_")
                    else 2
                    if g["id"] == "workers"
                    else 3,
                    g["name"].lower(),
                ),
            )

            return {
                "groups": sorted_groups,
                "total_sessions": sum(g["total_count"] for g in sorted_groups),
                "total_attached": sum(g["attached_count"] for g in sorted_groups),
            }

    def assign_session_to_project(
        self, session_id: int = None, session_name: str = None, project_id: int = None
    ) -> bool:
        """Assign a tmux session to a project."""
        with self._get_connection() as conn:
            if session_id:
                conn.execute(
                    """
                    UPDATE tmux_sessions SET project_id = ? WHERE id = ?
                """,
                    (project_id, session_id),
                )
            elif session_name:
                conn.execute(
                    """
                    UPDATE tmux_sessions SET project_id = ? WHERE session_name = ?
                """,
                    (project_id, session_name),
                )
            else:
                return False

            conn.commit()
            return True

    def set_session_environment(
        self, session_id: int = None, session_name: str = None, environment: str = None
    ) -> bool:
        """Set environment for a session."""
        with self._get_connection() as conn:
            if session_id:
                conn.execute(
                    """
                    UPDATE tmux_sessions SET environment = ? WHERE id = ?
                """,
                    (environment, session_id),
                )
            elif session_name:
                conn.execute(
                    """
                    UPDATE tmux_sessions SET environment = ? WHERE session_name = ?
                """,
                    (environment, session_name),
                )
            else:
                return False

            conn.commit()
            return True

    def set_session_worker(
        self, session_id: int = None, session_name: str = None, is_worker: bool = True
    ) -> bool:
        """Mark/unmark session as worker."""
        with self._get_connection() as conn:
            if session_id:
                conn.execute(
                    """
                    UPDATE tmux_sessions SET is_worker = ? WHERE id = ?
                """,
                    (is_worker, session_id),
                )
            elif session_name:
                conn.execute(
                    """
                    UPDATE tmux_sessions SET is_worker = ? WHERE session_name = ?
                """,
                    (is_worker, session_name),
                )
            else:
                return False

            conn.commit()
            return True

    def toggle_group_collapsed(self, user_id: str, group_id: str) -> bool:
        """Toggle collapsed state of a group."""
        with self._get_connection() as conn:
            existing = conn.execute(
                """
                SELECT collapsed FROM session_group_prefs
                WHERE user_id = ? AND group_id = ?
            """,
                (user_id, group_id),
            ).fetchone()

            if existing:
                new_state = not existing["collapsed"]
                conn.execute(
                    """
                    UPDATE session_group_prefs
                    SET collapsed = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND group_id = ?
                """,
                    (new_state, user_id, group_id),
                )
            else:
                new_state = True
                conn.execute(
                    """
                    INSERT INTO session_group_prefs (user_id, group_id, collapsed)
                    VALUES (?, ?, ?)
                """,
                    (user_id, group_id, new_state),
                )

            conn.commit()
            return new_state

    def set_group_collapsed(self, user_id: str, group_id: str, collapsed: bool) -> None:
        """Set collapsed state of a group."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO session_group_prefs (user_id, group_id, collapsed)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, group_id) DO UPDATE SET
                    collapsed = excluded.collapsed,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (user_id, group_id, collapsed),
            )
            conn.commit()

    def collapse_all_groups(self, user_id: str) -> int:
        """Collapse all groups for a user."""
        groups = self.get_sessions_grouped(user_id)
        count = 0
        for group in groups["groups"]:
            self.set_group_collapsed(user_id, group["id"], True)
            count += 1
        return count

    def expand_all_groups(self, user_id: str) -> int:
        """Expand all groups for a user."""
        with self._get_connection() as conn:
            result = conn.execute(
                """
                DELETE FROM session_group_prefs WHERE user_id = ?
            """,
                (user_id,),
            )
            conn.commit()
            return result.rowcount

    def get_collapsed_groups(self, user_id: str) -> List[str]:
        """Get list of collapsed group IDs for a user."""
        with self._get_connection() as conn:
            prefs = conn.execute(
                """
                SELECT group_id FROM session_group_prefs
                WHERE user_id = ? AND collapsed = 1
            """,
                (user_id,),
            ).fetchall()
            return [p["group_id"] for p in prefs]

    def auto_assign_sessions(self) -> Dict:
        """Auto-assign sessions to projects based on naming patterns."""
        with self._get_connection() as conn:
            # Get all projects
            projects = conn.execute(
                """
                SELECT id, name, source_path FROM projects WHERE status = 'active'
            """
            ).fetchall()

            # Get unassigned sessions
            sessions = conn.execute(
                """
                SELECT id, session_name FROM tmux_sessions
                WHERE project_id IS NULL AND is_worker = 0
            """
            ).fetchall()

            assigned = 0
            for session in sessions:
                session_name = session["session_name"].lower()

                # Try to match by project name
                for project in projects:
                    project_name = project["name"].lower()
                    # Check if session name contains project name
                    if project_name in session_name or session_name in project_name:
                        conn.execute(
                            """
                            UPDATE tmux_sessions SET project_id = ? WHERE id = ?
                        """,
                            (project["id"], session["id"]),
                        )
                        assigned += 1
                        break

                # Check for worker patterns
                worker_patterns = ["worker", "task-worker", "queue", "daemon"]
                if any(p in session_name for p in worker_patterns):
                    conn.execute(
                        """
                        UPDATE tmux_sessions SET is_worker = 1 WHERE id = ?
                    """,
                        (session["id"],),
                    )

            conn.commit()
            return {"assigned": assigned, "total_sessions": len(sessions)}

    def get_available_projects(self) -> List[Dict]:
        """Get list of projects available for session assignment."""
        with self._get_connection() as conn:
            projects = conn.execute(
                """
                SELECT id, name, status FROM projects
                WHERE status = 'active'
                ORDER BY name
            """
            ).fetchall()
            return [dict(p) for p in projects]


# Singleton getter
_service_instance = None
_service_lock = threading.Lock()


def get_session_group_service(db_path: str = None) -> SessionGroupService:
    global _service_instance
    if _service_instance is None or db_path:
        with _service_lock:
            if _service_instance is None or db_path:
                _service_instance = SessionGroupService(db_path)
    return _service_instance
