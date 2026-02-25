"""
Quick Access Sidebar API Module

Provides endpoints for managing pinned and recent projects
for the sidebar quick access menu.
"""

import json

from flask import Blueprint, jsonify, request, session

quick_access_bp = Blueprint("quick_access", __name__)


def get_quick_access_data(conn, user_id: str) -> dict:
    """Get all quick access data for a user."""
    import sqlite3

    conn.row_factory = sqlite3.Row

    # Get pinned project IDs
    pinned_row = conn.execute(
        "SELECT preference_value FROM user_preferences WHERE user_id=? AND preference_key='pinned_projects' AND category='quick_access'",
        (user_id,),
    ).fetchone()
    pinned_ids = json.loads(pinned_row["preference_value"]) if pinned_row else []

    # Get pinned projects with details
    pinned_projects = []
    if pinned_ids:
        placeholders = ",".join("?" * len(pinned_ids))
        rows = conn.execute(
            f"SELECT id, name, status, priority FROM projects WHERE id IN ({placeholders}) ORDER BY name",
            pinned_ids,
        ).fetchall()
        pinned_projects = [
            {
                "id": r["id"],
                "name": r["name"],
                "status": r["status"],
                "priority": r["priority"],
                "pinned": True,
            }
            for r in rows
        ]

    # Get recent projects from activity log (last 10 unique projects accessed)
    recent_rows = conn.execute(
        """
        SELECT DISTINCT CAST(entity_id AS INTEGER) as project_id
        FROM activity_log
        WHERE entity_type='project' AND entity_id IS NOT NULL
        AND action IN ('view_project', 'update_project', 'get_project')
        ORDER BY timestamp DESC LIMIT 20
    """
    ).fetchall()
    recent_ids = [
        r["project_id"]
        for r in recent_rows
        if r["project_id"] and r["project_id"] not in pinned_ids
    ][:10]

    recent_projects = []
    if recent_ids:
        placeholders = ",".join("?" * len(recent_ids))
        rows = conn.execute(
            f"SELECT id, name, status, priority FROM projects WHERE id IN ({placeholders})",
            recent_ids,
        ).fetchall()
        proj_map = {r["id"]: r for r in rows}
        recent_projects = [
            {
                "id": proj_map[pid]["id"],
                "name": proj_map[pid]["name"],
                "status": proj_map[pid]["status"],
                "priority": proj_map[pid]["priority"],
                "pinned": False,
            }
            for pid in recent_ids
            if pid in proj_map
        ]

    # Get favorite projects (high priority active projects)
    favorites = conn.execute(
        """
        SELECT id, name, status, priority FROM projects
        WHERE status='active' AND priority >= 7
        ORDER BY priority DESC, name LIMIT 5
    """
    ).fetchall()
    favorite_projects = [
        {"id": r["id"], "name": r["name"], "status": r["status"], "priority": r["priority"]}
        for r in favorites
        if r["id"] not in pinned_ids
    ]

    return {
        "pinned": pinned_projects,
        "recent": recent_projects,
        "favorites": favorite_projects,
        "pinned_count": len(pinned_projects),
        "recent_count": len(recent_projects),
    }


def get_pinned_ids(conn, user_id: str) -> list:
    """Get list of pinned project IDs for a user."""
    row = conn.execute(
        "SELECT preference_value FROM user_preferences WHERE user_id=? AND preference_key='pinned_projects' AND category='quick_access'",
        (user_id,),
    ).fetchone()
    return json.loads(row["preference_value"]) if row else []


def save_pinned_ids(conn, user_id: str, pinned_ids: list):
    """Save pinned project IDs for a user."""
    conn.execute(
        """INSERT INTO user_preferences (user_id, preference_key, preference_value, category, updated_at)
           VALUES (?, 'pinned_projects', ?, 'quick_access', CURRENT_TIMESTAMP)
           ON CONFLICT(user_id, preference_key) DO UPDATE SET
           preference_value = excluded.preference_value, updated_at = CURRENT_TIMESTAMP""",
        (user_id, json.dumps(pinned_ids)),
    )


def pin_project_for_user(conn, user_id: str, project_id: int, position: int = None) -> dict:
    """Pin a project to quick access for a user.

    Args:
        conn: Database connection
        user_id: User identifier
        project_id: Project to pin
        position: Optional position in the pinned list

    Returns:
        dict with success status and updated pinned_ids
    """
    import sqlite3

    conn.row_factory = sqlite3.Row

    # Verify project exists
    project = conn.execute("SELECT id, name FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        return {"success": False, "error": "Project not found"}

    # Get current pinned list
    pinned_ids = get_pinned_ids(conn, user_id)

    if project_id in pinned_ids:
        return {"success": True, "message": "Already pinned", "pinned_ids": pinned_ids}

    # Add to pinned list
    if position is not None and 0 <= position <= len(pinned_ids):
        pinned_ids.insert(position, project_id)
    else:
        pinned_ids.append(project_id)

    # Save updated list
    save_pinned_ids(conn, user_id, pinned_ids)

    return {
        "success": True,
        "pinned_ids": pinned_ids,
        "project": {"id": project["id"], "name": project["name"]},
    }


def unpin_project_for_user(conn, user_id: str, project_id: int) -> dict:
    """Unpin a project from quick access for a user.

    Args:
        conn: Database connection
        user_id: User identifier
        project_id: Project to unpin

    Returns:
        dict with success status and updated pinned_ids
    """
    pinned_ids = get_pinned_ids(conn, user_id)

    if project_id not in pinned_ids:
        return {"success": True, "message": "Not pinned", "pinned_ids": pinned_ids}

    pinned_ids.remove(project_id)
    save_pinned_ids(conn, user_id, pinned_ids)

    return {"success": True, "pinned_ids": pinned_ids}


def reorder_pinned_for_user(conn, user_id: str, new_order: list) -> dict:
    """Reorder pinned projects for a user.

    Args:
        conn: Database connection
        user_id: User identifier
        new_order: List of project IDs in desired order

    Returns:
        dict with success status and updated pinned_ids
    """
    if not isinstance(new_order, list):
        return {"success": False, "error": "Order must be a list of project IDs"}

    # Verify all IDs are valid projects
    if new_order:
        placeholders = ",".join("?" * len(new_order))
        existing = conn.execute(
            f"SELECT id FROM projects WHERE id IN ({placeholders})", new_order
        ).fetchall()
        existing_ids = {r[0] for r in existing}
        new_order = [pid for pid in new_order if pid in existing_ids]

    save_pinned_ids(conn, user_id, new_order)
    return {"success": True, "pinned_ids": new_order}


def get_recent_projects_for_user(conn, user_id: str, limit: int = 10) -> list:
    """Get recently accessed projects for a user.

    Args:
        conn: Database connection
        user_id: User identifier
        limit: Maximum number of recent projects to return

    Returns:
        List of project dicts
    """
    import sqlite3

    conn.row_factory = sqlite3.Row

    # Get pinned to exclude from recent
    pinned_ids = set(get_pinned_ids(conn, user_id))

    # Get recent projects from activity
    recent_rows = conn.execute(
        """
        SELECT DISTINCT CAST(entity_id AS INTEGER) as project_id, MAX(timestamp) as last_access
        FROM activity_log
        WHERE entity_type='project' AND entity_id IS NOT NULL
        AND action IN ('view_project', 'update_project', 'get_project', 'create_feature', 'create_bug')
        GROUP BY entity_id
        ORDER BY last_access DESC
        LIMIT ?
    """,
        (limit + len(pinned_ids),),
    ).fetchall()

    recent_ids = [
        r["project_id"]
        for r in recent_rows
        if r["project_id"] and r["project_id"] not in pinned_ids
    ][:limit]

    if not recent_ids:
        return []

    placeholders = ",".join("?" * len(recent_ids))
    rows = conn.execute(
        f"SELECT id, name, description, status, priority FROM projects WHERE id IN ({placeholders})",
        recent_ids,
    ).fetchall()
    proj_map = {r["id"]: dict(r) for r in rows}

    return [proj_map[pid] for pid in recent_ids if pid in proj_map]
