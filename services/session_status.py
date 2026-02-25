#!/usr/bin/env python3
"""
Session Status Manager for GAIA

Provides centralized status reporting and querying for all AI sessions.
Sessions report their status here instead of relying on stdout parsing.

Usage:
    # Report status (from any session/worker)
    from services.session_status import report_status, SessionState
    report_status("my_session", SessionState.BUSY, task="Fixing bug in auth.py")

    # Query status (from GAIA or dashboard)
    from services.session_status import get_all_status, get_session_status
    all_status = get_all_status()
    session = get_session_status("my_session")
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Status database location
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "gaia"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DB = DATA_DIR / "session_status.db"

# Thread-local storage for connections
_local = threading.local()


class SessionState(Enum):
    """Session states."""

    IDLE = "idle"  # Waiting for input
    BUSY = "busy"  # Processing a task
    THINKING = "thinking"  # AI is generating response
    ERROR = "error"  # Error state
    OFFLINE = "offline"  # Session not running
    STARTING = "starting"  # Session starting up
    STOPPING = "stopping"  # Session shutting down


class SessionStatus:
    """Status information for a session."""

    def __init__(
        self,
        session_name: str,
        provider: str = "unknown",
        state: SessionState = SessionState.OFFLINE,
        task: str = "",
        progress: int = 0,
        tokens_used: int = 0,
        tokens_limit: int = 100000,
        cost: float = 0.0,
        last_activity: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.session_name = session_name
        self.provider = provider
        self.state = state
        self.task = task
        self.progress = progress  # 0-100
        self.tokens_used = tokens_used
        self.tokens_limit = tokens_limit
        self.cost = cost
        self.last_activity = last_activity or datetime.now()
        self.started_at = started_at or datetime.now()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_name": self.session_name,
            "provider": self.provider,
            "state": self.state.value,
            "task": self.task,
            "progress": self.progress,
            "tokens_used": self.tokens_used,
            "tokens_limit": self.tokens_limit,
            "cost": self.cost,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionStatus":
        """Create from dictionary."""
        return cls(
            session_name=data.get("session_name", "unknown"),
            provider=data.get("provider", "unknown"),
            state=SessionState(data.get("state", "offline")),
            task=data.get("task", ""),
            progress=data.get("progress", 0),
            tokens_used=data.get("tokens_used", 0),
            tokens_limit=data.get("tokens_limit", 100000),
            cost=data.get("cost", 0.0),
            last_activity=(
                datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else None
            ),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            metadata=data.get("metadata", {}),
        )


@contextmanager
def get_db():
    """Get database connection (thread-safe)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(STATUS_DB), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _init_db(_local.conn)
    try:
        yield _local.conn
    except Exception:
        _local.conn.rollback()
        raise


def _init_db(conn: sqlite3.Connection):
    """Initialize database schema."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_status (
            session_name TEXT PRIMARY KEY,
            provider TEXT DEFAULT 'unknown',
            state TEXT DEFAULT 'offline',
            task TEXT DEFAULT '',
            progress INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            tokens_limit INTEGER DEFAULT 100000,
            cost REAL DEFAULT 0.0,
            last_activity TEXT,
            started_at TEXT,
            metadata TEXT DEFAULT '{}'
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_history_session
        ON session_history(session_name, timestamp DESC)
    """
    )
    conn.commit()


def report_status(
    session_name: str,
    state: SessionState,
    task: str = "",
    progress: int = 0,
    provider: str = None,
    tokens_used: int = None,
    tokens_limit: int = None,
    cost: float = None,
    metadata: Dict[str, Any] = None,
) -> bool:
    """
    Report session status to the central store.

    Args:
        session_name: Name of the tmux session
        state: Current state (IDLE, BUSY, THINKING, ERROR, etc.)
        task: Current task description
        progress: Progress percentage (0-100)
        provider: LLM provider (claude, ollama, etc.)
        tokens_used: Tokens used in current session
        tokens_limit: Token limit for session
        cost: Total cost incurred
        metadata: Additional metadata

    Returns:
        True if status was reported successfully
    """
    try:
        with get_db() as conn:
            now = datetime.now().isoformat()

            # Check if session exists
            existing = conn.execute(
                "SELECT * FROM session_status WHERE session_name = ?", (session_name,)
            ).fetchone()

            if existing:
                # Update existing
                updates = ["state = ?", "task = ?", "progress = ?", "last_activity = ?"]
                values = [state.value, task, progress, now]

                if provider is not None:
                    updates.append("provider = ?")
                    values.append(provider)
                if tokens_used is not None:
                    updates.append("tokens_used = ?")
                    values.append(tokens_used)
                if tokens_limit is not None:
                    updates.append("tokens_limit = ?")
                    values.append(tokens_limit)
                if cost is not None:
                    updates.append("cost = ?")
                    values.append(cost)
                if metadata is not None:
                    updates.append("metadata = ?")
                    values.append(json.dumps(metadata))

                values.append(session_name)
                conn.execute(
                    f"UPDATE session_status SET {', '.join(updates)} WHERE session_name = ?",
                    values,
                )
            else:
                # Insert new
                conn.execute(
                    """
                    INSERT INTO session_status
                    (session_name, provider, state, task, progress, tokens_used,
                     tokens_limit, cost, last_activity, started_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_name,
                        provider or "unknown",
                        state.value,
                        task,
                        progress,
                        tokens_used or 0,
                        tokens_limit or 100000,
                        cost or 0.0,
                        now,
                        now,
                        json.dumps(metadata or {}),
                    ),
                )

            # Log to history
            conn.execute(
                """
                INSERT INTO session_history (session_name, event_type, event_data)
                VALUES (?, ?, ?)
                """,
                (session_name, state.value, json.dumps({"task": task, "progress": progress})),
            )

            conn.commit()
            return True

    except Exception as e:
        print(f"Error reporting status: {e}")
        return False


def get_session_status(session_name: str) -> Optional[SessionStatus]:
    """Get status for a specific session."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM session_status WHERE session_name = ?", (session_name,)
            ).fetchone()

            if row:
                return SessionStatus.from_dict(dict(row))
            return None

    except Exception:
        return None


def get_all_status() -> List[SessionStatus]:
    """Get status for all sessions."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM session_status ORDER BY last_activity DESC"
            ).fetchall()
            return [SessionStatus.from_dict(dict(row)) for row in rows]

    except Exception:
        return []


def get_active_sessions() -> List[SessionStatus]:
    """Get only active (non-offline) sessions."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM session_status
                WHERE state != 'offline'
                ORDER BY last_activity DESC
                """
            ).fetchall()
            return [SessionStatus.from_dict(dict(row)) for row in rows]

    except Exception:
        return []


def get_busy_sessions() -> List[SessionStatus]:
    """Get sessions that are currently busy."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM session_status
                WHERE state IN ('busy', 'thinking')
                ORDER BY last_activity DESC
                """
            ).fetchall()
            return [SessionStatus.from_dict(dict(row)) for row in rows]

    except Exception:
        return []


def get_idle_sessions() -> List[SessionStatus]:
    """Get sessions that are idle and available."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM session_status
                WHERE state = 'idle'
                ORDER BY last_activity DESC
                """
            ).fetchall()
            return [SessionStatus.from_dict(dict(row)) for row in rows]

    except Exception:
        return []


def get_session_history(session_name: str, limit: int = 50) -> List[Dict]:
    """Get recent history for a session."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM session_history
                WHERE session_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_name, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    except Exception:
        return []


def mark_session_offline(session_name: str) -> bool:
    """Mark a session as offline."""
    return report_status(session_name, SessionState.OFFLINE)


def mark_session_idle(session_name: str, provider: str = None) -> bool:
    """Mark a session as idle and available."""
    return report_status(session_name, SessionState.IDLE, provider=provider)


def mark_session_busy(session_name: str, task: str, provider: str = None) -> bool:
    """Mark a session as busy with a task."""
    return report_status(session_name, SessionState.BUSY, task=task, provider=provider)


def update_progress(session_name: str, progress: int, task: str = None) -> bool:
    """Update task progress for a session."""
    return report_status(
        session_name, SessionState.BUSY, task=task or "", progress=min(100, max(0, progress))
    )


def record_tokens(session_name: str, tokens: int, cost: float = 0.0) -> bool:
    """Record token usage for a session."""
    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE session_status
                SET tokens_used = tokens_used + ?, cost = cost + ?
                WHERE session_name = ?
                """,
                (tokens, cost, session_name),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_system_summary() -> Dict[str, Any]:
    """Get overall system status summary."""
    try:
        with get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM session_status").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM session_status WHERE state != 'offline'"
            ).fetchone()[0]
            busy = conn.execute(
                "SELECT COUNT(*) FROM session_status WHERE state IN ('busy', 'thinking')"
            ).fetchone()[0]
            idle = conn.execute(
                "SELECT COUNT(*) FROM session_status WHERE state = 'idle'"
            ).fetchone()[0]
            errors = conn.execute(
                "SELECT COUNT(*) FROM session_status WHERE state = 'error'"
            ).fetchone()[0]

            total_tokens = conn.execute(
                "SELECT COALESCE(SUM(tokens_used), 0) FROM session_status"
            ).fetchone()[0]
            total_cost = conn.execute(
                "SELECT COALESCE(SUM(cost), 0) FROM session_status"
            ).fetchone()[0]

            # Provider breakdown
            providers = {}
            for row in conn.execute(
                """
                SELECT provider, COUNT(*) as count,
                       SUM(CASE WHEN state IN ('busy', 'thinking') THEN 1 ELSE 0 END) as busy
                FROM session_status
                WHERE state != 'offline'
                GROUP BY provider
                """
            ):
                providers[row["provider"]] = {"count": row["count"], "busy": row["busy"]}

            return {
                "total_sessions": total,
                "active_sessions": active,
                "busy_sessions": busy,
                "idle_sessions": idle,
                "error_sessions": errors,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "providers": providers,
                "timestamp": datetime.now().isoformat(),
            }

    except Exception as e:
        return {"error": str(e)}


def cleanup_stale_sessions(max_age_minutes: int = 60) -> int:
    """Mark sessions as offline if they haven't reported in a while."""
    try:
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(minutes=max_age_minutes)).isoformat()

        with get_db() as conn:
            result = conn.execute(
                """
                UPDATE session_status
                SET state = 'offline'
                WHERE state != 'offline' AND last_activity < ?
                """,
                (cutoff,),
            )
            conn.commit()
            return result.rowcount

    except Exception:
        return 0


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "status":
            summary = get_system_summary()
            print("\nSystem Status:")
            print(f"  Active: {summary.get('active_sessions', 0)}")
            print(f"  Busy: {summary.get('busy_sessions', 0)}")
            print(f"  Idle: {summary.get('idle_sessions', 0)}")
            print(f"  Errors: {summary.get('error_sessions', 0)}")
            print(f"  Total Tokens: {summary.get('total_tokens', 0):,}")
            print(f"  Total Cost: ${summary.get('total_cost', 0):.4f}")

        elif cmd == "list":
            sessions = get_all_status()
            print(f"\nAll Sessions ({len(sessions)}):")
            for s in sessions:
                state_icon = {
                    "idle": "🟢",
                    "busy": "🔵",
                    "thinking": "🟡",
                    "error": "🔴",
                    "offline": "⚫",
                }.get(s.state.value, "⚪")
                print(f"  {state_icon} {s.session_name:20} {s.provider:10} {s.task[:30]}")

        elif cmd == "report" and len(sys.argv) >= 4:
            session = sys.argv[2]
            state = SessionState(sys.argv[3])
            task = sys.argv[4] if len(sys.argv) > 4 else ""
            report_status(session, state, task)
            print(f"Reported: {session} -> {state.value}")

        else:
            print("Usage:")
            print("  python session_status.py status          - Show system summary")
            print("  python session_status.py list            - List all sessions")
            print("  python session_status.py report <session> <state> [task]")
    else:
        # Default: show status
        summary = get_system_summary()
        print(json.dumps(summary, indent=2))
