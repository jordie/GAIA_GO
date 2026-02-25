#!/usr/bin/env python3
"""
Session Pool Management Service

Provides health monitoring and management for Claude agent sessions.

Task: P04 - Add Session Pool Management
"""

import logging
import sqlite3
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = "data/architect.db"


class SessionPoolService:
    """Manages session pool members and their health status."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def save_pool_member(
        self,
        name: str,
        tmux_name: str,
        role: str = "worker",
        status: str = "stopped",
        health: str = "unknown",
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Save or update a pool member.

        Args:
            name: Unique session name
            tmux_name: Tmux session name
            role: Session role (worker, coordinator, etc.)
            status: Current status (stopped, starting, running, stopping)
            health: Health status (unknown, healthy, degraded, unhealthy)
            metadata: Optional metadata as dict

        Returns:
            Session ID
        """
        import json

        metadata_json = json.dumps(metadata) if metadata else None

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO session_pool (name, tmux_name, role, status, health, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    tmux_name = excluded.tmux_name,
                    role = excluded.role,
                    status = excluded.status,
                    health = excluded.health,
                    metadata = excluded.metadata,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (name, tmux_name, role, status, health, metadata_json),
            )
            conn.commit()

            # Get the ID
            session_id = cursor.execute(
                "SELECT id FROM session_pool WHERE name = ?", (name,)
            ).fetchone()[0]

            logger.info(f"Saved pool member: {name} (ID: {session_id}, status: {status})")
            return session_id

    def get_pool_members(
        self, role: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all pool members with optional filtering.

        Args:
            role: Filter by role
            status: Filter by status

        Returns:
            List of pool member dictionaries
        """
        import json

        query = "SELECT * FROM session_pool WHERE 1=1"
        params = []

        if role:
            query += " AND role = ?"
            params.append(role)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            members = []
            for row in rows:
                member = dict(row)
                # Parse metadata JSON
                if member.get("metadata"):
                    try:
                        member["metadata"] = json.loads(member["metadata"])
                    except json.JSONDecodeError:
                        member["metadata"] = None
                members.append(member)

            return members

    def get_pool_member(self, name: str) -> Optional[Dict]:
        """Get a specific pool member by name."""
        members = self.get_pool_members()
        for member in members:
            if member["name"] == name:
                return member
        return None

    def update_heartbeat(self, name: str, health: Optional[str] = None) -> bool:
        """
        Update last_heartbeat timestamp for a session.

        Args:
            name: Session name
            health: Optional health status update

        Returns:
            True if successful
        """
        with self._get_connection() as conn:
            if health:
                conn.execute(
                    """
                    UPDATE session_pool
                    SET last_heartbeat = CURRENT_TIMESTAMP,
                        health = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                    """,
                    (health, name),
                )
            else:
                conn.execute(
                    """
                    UPDATE session_pool
                    SET last_heartbeat = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                    """,
                    (name,),
                )
            conn.commit()
            return conn.total_changes > 0

    def update_status(self, name: str, status: str, health: Optional[str] = None) -> bool:
        """
        Update session status.

        Args:
            name: Session name
            status: New status
            health: Optional health status

        Returns:
            True if successful
        """
        with self._get_connection() as conn:
            if health:
                conn.execute(
                    """
                    UPDATE session_pool
                    SET status = ?, health = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                    """,
                    (status, health, name),
                )
            else:
                conn.execute(
                    """
                    UPDATE session_pool
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                    """,
                    (status, name),
                )
            conn.commit()
            return conn.total_changes > 0

    def increment_restart_count(self, name: str) -> int:
        """
        Increment restart counter for a session.

        Args:
            name: Session name

        Returns:
            New restart count
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE session_pool
                SET restart_count = restart_count + 1,
                    last_restart = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
                """,
                (name,),
            )
            conn.commit()

            result = conn.execute(
                "SELECT restart_count FROM session_pool WHERE name = ?", (name,)
            ).fetchone()

            return result[0] if result else 0

    def log_pool_event(
        self, session_name: str, event_type: str, details: Optional[str] = None
    ) -> int:
        """
        Log an event for a pool session.

        Args:
            session_name: Name of the session
            event_type: Type of event (started, stopped, restarted, health_check, error)
            details: Optional event details

        Returns:
            Event ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pool_events (session_name, event_type, details)
                VALUES (?, ?, ?)
                """,
                (session_name, event_type, details),
            )
            conn.commit()
            event_id = cursor.lastrowid
            logger.info(f"Logged event for {session_name}: {event_type} (ID: {event_id})")
            return event_id

    def get_pool_events(
        self, session_name: Optional[str] = None, event_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get pool events with optional filtering.

        Args:
            session_name: Filter by session name
            event_type: Filter by event type
            limit: Max events to return

        Returns:
            List of event dictionaries
        """
        query = "SELECT * FROM pool_events WHERE 1=1"
        params = []

        if session_name:
            query += " AND session_name = ?"
            params.append(session_name)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def check_tmux_session(self, tmux_name: str) -> bool:
        """
        Check if tmux session is actually running.

        Args:
            tmux_name: Tmux session name

        Returns:
            True if session exists and is running
        """
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", tmux_name],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking tmux session {tmux_name}: {e}")
            return False

    def health_check_session(self, name: str) -> Dict:
        """
        Perform health check on a session.

        Args:
            name: Session name

        Returns:
            Health check result dict with status, issues, and recommendations
        """
        member = self.get_pool_member(name)
        if not member:
            return {
                "healthy": False,
                "status": "not_found",
                "issues": ["Session not found in pool"],
            }

        issues = []
        recommendations = []
        tmux_running = self.check_tmux_session(member["tmux_name"])

        # Check if tmux session exists
        if not tmux_running:
            issues.append(f"Tmux session '{member['tmux_name']}' not running")
            recommendations.append("Restart the session")

        # Check heartbeat freshness
        if member.get("last_heartbeat"):
            from datetime import datetime, timedelta

            last_hb = datetime.fromisoformat(member["last_heartbeat"])
            age_minutes = (datetime.now() - last_hb).total_seconds() / 60

            if age_minutes > 15:
                issues.append(f"No heartbeat for {age_minutes:.1f} minutes")
                recommendations.append("Check if session is stuck")

        # Check restart count
        if member.get("restart_count", 0) > 5:
            issues.append(f"High restart count: {member['restart_count']}")
            recommendations.append("Investigate recurring failures")

        # Determine health status
        if len(issues) == 0:
            health = "healthy"
        elif len(issues) >= 3:
            health = "unhealthy"
        else:
            health = "degraded"

        return {
            "healthy": health == "healthy",
            "status": health,
            "tmux_running": tmux_running,
            "issues": issues,
            "recommendations": recommendations,
            "last_heartbeat": member.get("last_heartbeat"),
            "restart_count": member.get("restart_count", 0),
        }

    def auto_restart_session(self, name: str) -> Dict:
        """
        Attempt to auto-restart a failed session.

        Args:
            name: Session name

        Returns:
            Result dict with success status and message
        """
        member = self.get_pool_member(name)
        if not member:
            return {"success": False, "error": "Session not found"}

        # Check current status
        health = self.health_check_session(name)
        if health["healthy"]:
            return {
                "success": False,
                "message": "Session is already healthy, no restart needed",
            }

        # Increment restart counter
        restart_count = self.increment_restart_count(name)

        # Log restart attempt
        self.log_pool_event(name, "restart_attempt", f"Auto-restart #{restart_count}")

        # Check if restart count is too high
        if restart_count > 10:
            self.log_pool_event(name, "restart_failed", "Too many restart attempts, giving up")
            self.update_status(name, "failed", "unhealthy")
            return {
                "success": False,
                "error": "Too many restart attempts (>10), manual intervention required",
            }

        # Kill existing tmux session if it exists
        if health.get("tmux_running"):
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", member["tmux_name"]],
                    timeout=10,
                    check=True,
                )
                self.log_pool_event(name, "session_killed", "Killed stale tmux session")
            except Exception as e:
                logger.error(f"Error killing tmux session: {e}")

        # Start new tmux session
        try:
            # Update status to starting
            self.update_status(name, "starting", "unknown")

            # Create tmux session
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", member["tmux_name"]],
                timeout=10,
                check=True,
            )

            # Update status to running
            self.update_status(name, "running", "healthy")
            self.log_pool_event(
                name, "restarted", f"Successfully restarted (attempt #{restart_count})"
            )

            return {
                "success": True,
                "message": f"Session restarted successfully (attempt #{restart_count})",
                "restart_count": restart_count,
            }

        except Exception as e:
            self.log_pool_event(name, "restart_failed", str(e))
            self.update_status(name, "failed", "unhealthy")
            return {"success": False, "error": f"Failed to restart: {e}"}


# Singleton instance
_service = SessionPoolService()


def get_service() -> SessionPoolService:
    """Get the singleton service instance."""
    return _service
