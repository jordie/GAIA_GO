"""
Kudos / Team Recognition Module

Provides functions for creating and listing kudos between team members.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from utils import sanitize_string

KUDOS_CATEGORIES = {
    "general": {"label": "General", "icon": "star", "color": "#607D8B"},
    "teamwork": {"label": "Teamwork", "icon": "users", "color": "#4CAF50"},
    "leadership": {"label": "Leadership", "icon": "flag", "color": "#3F51B5"},
    "innovation": {"label": "Innovation", "icon": "zap", "color": "#FFC107"},
    "helpfulness": {"label": "Helpfulness", "icon": "hand-heart", "color": "#E91E63"},
    "delivery": {"label": "Delivery", "icon": "rocket", "color": "#FF5722"},
    "quality": {"label": "Quality", "icon": "check-circle", "color": "#009688"},
    "mentorship": {"label": "Mentorship", "icon": "book-open", "color": "#795548"},
    "ownership": {"label": "Ownership", "icon": "shield", "color": "#9C27B0"},
}

DEFAULT_CATEGORY = "general"
MAX_MESSAGE_LENGTH = 1000
MAX_CATEGORY_LENGTH = 50


def get_categories() -> Dict[str, Dict[str, str]]:
    """Return available kudos categories."""
    return KUDOS_CATEGORIES


def _user_exists(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    return row is not None


def _project_exists(conn: sqlite3.Connection, project_id: int) -> bool:
    row = conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row is not None


def _normalize_category(category: Optional[str]) -> str:
    if category is None:
        return DEFAULT_CATEGORY
    if not isinstance(category, str):
        category = str(category)
    category = sanitize_string(category, max_length=MAX_CATEGORY_LENGTH).lower()
    return category or DEFAULT_CATEGORY


def _normalize_message(message: Any) -> str:
    if not isinstance(message, str):
        message = str(message)
    return sanitize_string(message, max_length=MAX_MESSAGE_LENGTH)


def _normalize_points(points: Any) -> Tuple[Optional[int], Optional[str]]:
    try:
        points_int = int(points)
    except (TypeError, ValueError):
        return None, "points must be an integer"
    if points_int < 1:
        return None, "points must be >= 1"
    if points_int > 100:
        points_int = 100
    return points_int, None


def create_kudos(
    conn: sqlite3.Connection,
    sender_user_id: int,
    recipient_user_id: int,
    message: Any,
    project_id: Optional[int] = None,
    category: Optional[str] = None,
    points: Any = 1,
    metadata: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create a new kudos entry."""
    if sender_user_id is None:
        return {"error": "Sender user is required"}
    if recipient_user_id is None:
        return {"error": "Recipient user is required"}
    if not _user_exists(conn, sender_user_id):
        return {"error": "Sender user not found"}
    if not _user_exists(conn, recipient_user_id):
        return {"error": "Recipient user not found"}
    if project_id is not None and not _project_exists(conn, project_id):
        return {"error": "Project not found"}

    normalized_message = _normalize_message(message)
    if not normalized_message:
        return {"error": "message is required"}

    normalized_category = _normalize_category(category)
    if normalized_category not in KUDOS_CATEGORIES:
        return {"error": f'Invalid category. Must be one of: {", ".join(KUDOS_CATEGORIES.keys())}'}

    normalized_points, points_error = _normalize_points(points)
    if points_error:
        return {"error": points_error}

    metadata_json = None
    if metadata is not None:
        if not isinstance(metadata, (dict, list)):
            return {"error": "metadata must be an object or array"}
        metadata_json = json.dumps(metadata)

    cursor = conn.execute(
        """
        INSERT INTO kudos (
            sender_user_id, recipient_user_id, project_id,
            category, message, points, metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sender_user_id,
            recipient_user_id,
            project_id,
            normalized_category,
            normalized_message,
            normalized_points,
            metadata_json,
        ),
    )
    conn.commit()

    return get_kudos(conn, cursor.lastrowid) or {"id": cursor.lastrowid}


def get_kudos(conn: sqlite3.Connection, kudos_id: int) -> Optional[Dict[str, Any]]:
    """Get a single kudos entry with user and project details."""
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT k.*, s.username as sender_username,
               r.username as recipient_username,
               p.name as project_name
        FROM kudos k
        JOIN users s ON k.sender_user_id = s.id
        JOIN users r ON k.recipient_user_id = r.id
        LEFT JOIN projects p ON k.project_id = p.id
        WHERE k.id = ?
        """,
        (kudos_id,),
    ).fetchone()

    if not row:
        return None

    result = dict(row)
    if result.get("metadata"):
        try:
            result["metadata"] = json.loads(result["metadata"])
        except json.JSONDecodeError:
            pass
    return result


def list_kudos(
    conn: sqlite3.Connection,
    sender_user_id: Optional[int] = None,
    recipient_user_id: Optional[int] = None,
    project_id: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List kudos entries with optional filters."""
    conn.row_factory = sqlite3.Row

    conditions: List[str] = []
    params: List[Any] = []

    if sender_user_id:
        conditions.append("k.sender_user_id = ?")
        params.append(sender_user_id)
    if recipient_user_id:
        conditions.append("k.recipient_user_id = ?")
        params.append(recipient_user_id)
    if project_id:
        conditions.append("k.project_id = ?")
        params.append(project_id)
    if category:
        conditions.append("k.category = ?")
        params.append(category)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) as total FROM kudos k {where_clause}", params
    ).fetchone()
    total = count_row["total"] if count_row else 0

    rows = conn.execute(
        f"""
        SELECT k.*, s.username as sender_username,
               r.username as recipient_username,
               p.name as project_name
        FROM kudos k
        JOIN users s ON k.sender_user_id = s.id
        JOIN users r ON k.recipient_user_id = r.id
        LEFT JOIN projects p ON k.project_id = p.id
        {where_clause}
        ORDER BY k.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        if item.get("metadata"):
            try:
                item["metadata"] = json.loads(item["metadata"])
            except json.JSONDecodeError:
                pass
        items.append(item)

    return {
        "kudos": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "categories": KUDOS_CATEGORIES,
    }


def delete_kudos(conn: sqlite3.Connection, kudos_id: int) -> bool:
    """Delete a kudos entry."""
    result = conn.execute("DELETE FROM kudos WHERE id = ?", (kudos_id,))
    conn.commit()
    return result.rowcount > 0
