"""
tmux Session Cleanup Module

Provides functions for automatic cleanup of stale tmux sessions.
"""

import subprocess
from datetime import datetime


def get_active_tmux_sessions() -> set:
    """Get set of currently active tmux session names."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return {s.strip() for s in result.stdout.strip().split("\n") if s.strip()}
    except Exception:
        pass
    return set()


def is_session_protected(session_name: str, protected_patterns: list) -> bool:
    """Check if a session is protected from auto-cleanup."""
    session_lower = session_name.lower()
    return any(pattern.lower() in session_lower for pattern in protected_patterns)


def cleanup_stale_sessions(
    conn, config: dict, dry_run: bool = False, force_kill: bool = False, log_activity_fn=None
) -> dict:
    """
    Clean up stale tmux sessions from database and optionally kill them.

    Args:
        conn: Database connection
        config: TMUX_SESSION_CLEANUP_CONFIG dictionary
        dry_run: If True, only report what would be cleaned without making changes
        force_kill: If True, kill actual tmux sessions (not just DB entries)
        log_activity_fn: Function to call for logging activity

    Returns:
        Dictionary with cleanup results
    """
    results = {
        "orphaned_db_entries": [],
        "stale_sessions": [],
        "killed_sessions": [],
        "protected_sessions": [],
        "errors": [],
        "dry_run": dry_run,
    }

    now = datetime.now()
    stale_hours = config.get("stale_threshold_hours", 24)
    kill_after_hours = config.get("kill_unattached_after_hours", 72)
    protected_patterns = config.get("protected_session_patterns", [])

    # Get active tmux sessions
    active_sessions = get_active_tmux_sessions()

    import sqlite3

    conn.row_factory = sqlite3.Row

    # Get all DB sessions
    db_sessions = conn.execute(
        """
        SELECT id, node_id, session_name, attached, last_activity,
               is_worker, assigned_task_type, assigned_task_id, purpose
        FROM tmux_sessions
    """
    ).fetchall()

    for session in db_sessions:
        session_name = session["session_name"]
        node_id = session["node_id"]

        # Check if session exists in tmux (for local node)
        if node_id == "local" and session_name not in active_sessions:
            if config.get("cleanup_orphaned_db_entries", True):
                results["orphaned_db_entries"].append(
                    {
                        "id": session["id"],
                        "name": session_name,
                        "node_id": node_id,
                        "reason": "Session no longer exists in tmux",
                    }
                )
                if not dry_run:
                    conn.execute("DELETE FROM tmux_sessions WHERE id = ?", (session["id"],))
            continue

        # Check for stale sessions
        last_activity = session["last_activity"]
        if last_activity:
            try:
                last_act = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                hours_inactive = (now - last_act.replace(tzinfo=None)).total_seconds() / 3600
            except (ValueError, AttributeError):
                hours_inactive = 0
        else:
            hours_inactive = stale_hours + 1  # Treat no activity as stale

        if hours_inactive > stale_hours:
            is_protected = is_session_protected(session_name, protected_patterns)
            is_worker = session["is_worker"]
            has_assignment = session["assigned_task_id"] is not None
            is_attached = session["attached"]

            session_info = {
                "id": session["id"],
                "name": session_name,
                "node_id": node_id,
                "hours_inactive": round(hours_inactive, 1),
                "is_worker": bool(is_worker),
                "has_assignment": has_assignment,
                "is_attached": bool(is_attached),
                "is_protected": is_protected,
            }

            # Determine if we should kill this session
            should_kill = False
            kill_reason = None

            if is_protected:
                results["protected_sessions"].append(session_info)
            elif config.get("preserve_worker_sessions", True) and is_worker:
                session_info["skip_reason"] = "Worker session preserved"
                results["stale_sessions"].append(session_info)
            elif config.get("preserve_assigned_sessions", True) and has_assignment:
                session_info["skip_reason"] = "Has assigned task"
                results["stale_sessions"].append(session_info)
            elif is_attached:
                session_info["skip_reason"] = "Currently attached"
                results["stale_sessions"].append(session_info)
            elif kill_after_hours > 0 and hours_inactive > kill_after_hours and force_kill:
                should_kill = True
                kill_reason = f"Unattached for {round(hours_inactive, 1)} hours"
            else:
                results["stale_sessions"].append(session_info)

            if should_kill and node_id == "local":
                session_info["kill_reason"] = kill_reason
                if not dry_run:
                    try:
                        subprocess.run(
                            ["tmux", "kill-session", "-t", session_name],
                            capture_output=True,
                            timeout=5,
                        )
                        conn.execute("DELETE FROM tmux_sessions WHERE id = ?", (session["id"],))
                        results["killed_sessions"].append(session_info)
                        if log_activity_fn:
                            log_activity_fn(
                                "auto_kill_session",
                                "tmux",
                                session["id"],
                                f"Killed stale session: {session_name} ({kill_reason})",
                            )
                    except Exception as e:
                        results["errors"].append({"session": session_name, "error": str(e)})
                else:
                    results["killed_sessions"].append(session_info)

    # Log cleanup activity
    if not dry_run and (results["orphaned_db_entries"] or results["killed_sessions"]):
        if log_activity_fn:
            log_activity_fn(
                "tmux_cleanup",
                "tmux",
                None,
                f"Cleaned {len(results['orphaned_db_entries'])} orphaned, "
                f"killed {len(results['killed_sessions'])} stale sessions",
            )

    results["summary"] = {
        "orphaned_removed": len(results["orphaned_db_entries"]),
        "stale_found": len(results["stale_sessions"]),
        "killed": len(results["killed_sessions"]),
        "protected": len(results["protected_sessions"]),
        "errors": len(results["errors"]),
    }

    return results
