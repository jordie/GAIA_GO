# ============================================================================
# SPRINT RETROSPECTIVES MODULE
# ============================================================================
"""
Sprint retrospective management for the Architect Dashboard.
Provides functions for creating, managing, and analyzing sprint retrospectives.
"""

import json
from datetime import datetime

# Category definitions for retrospective items
RETRO_CATEGORIES = {
    "went_well": {"label": "What Went Well", "icon": "thumbs-up", "color": "#4CAF50"},
    "needs_improvement": {
        "label": "Needs Improvement",
        "icon": "alert-triangle",
        "color": "#FF9800",
    },
    "action_item": {"label": "Action Items", "icon": "check-square", "color": "#2196F3"},
    "kudos": {"label": "Kudos & Recognition", "icon": "award", "color": "#9C27B0"},
    "question": {"label": "Questions", "icon": "help-circle", "color": "#00BCD4"},
    "blocker": {"label": "Blockers", "icon": "x-octagon", "color": "#F44336"},
}


def get_retrospectives(conn, project_id=None, milestone_id=None, status=None, limit=50, offset=0):
    """Get retrospectives with optional filters."""
    conn.row_factory = __import__("sqlite3").Row

    query = """
        SELECT r.*, m.name as milestone_name, p.name as project_name,
               (SELECT COUNT(*) FROM retrospective_items WHERE retrospective_id = r.id) as item_count,
               (SELECT COUNT(*) FROM retrospective_items WHERE retrospective_id = r.id AND is_action_item = 1) as action_count
        FROM sprint_retrospectives r
        LEFT JOIN milestones m ON r.milestone_id = m.id
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE 1=1
    """
    params = []

    if project_id:
        query += " AND r.project_id = ?"
        params.append(project_id)
    if milestone_id:
        query += " AND r.milestone_id = ?"
        params.append(milestone_id)
    if status:
        query += " AND r.status = ?"
        params.append(status)

    query += " ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    retrospectives = []
    for row in rows:
        retro = dict(row)
        if retro.get("participants"):
            retro["participants"] = json.loads(retro["participants"])
        retrospectives.append(retro)

    return retrospectives


def get_retrospective(conn, retro_id):
    """Get a single retrospective with all items."""
    conn.row_factory = __import__("sqlite3").Row

    row = conn.execute(
        """
        SELECT r.*, m.name as milestone_name, p.name as project_name
        FROM sprint_retrospectives r
        LEFT JOIN milestones m ON r.milestone_id = m.id
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE r.id = ?
    """,
        (retro_id,),
    ).fetchone()

    if not row:
        return None

    retro = dict(row)
    if retro.get("participants"):
        retro["participants"] = json.loads(retro["participants"])

    # Get all items grouped by category
    items = conn.execute(
        """
        SELECT * FROM retrospective_items
        WHERE retrospective_id = ?
        ORDER BY votes DESC, created_at ASC
    """,
        (retro_id,),
    ).fetchall()

    retro["items"] = {}
    for cat in RETRO_CATEGORIES:
        retro["items"][cat] = []

    for item in items:
        item_dict = dict(item)
        cat = item_dict.get("category", "went_well")
        if cat in retro["items"]:
            retro["items"][cat].append(item_dict)

    return retro


def create_retrospective(
    conn,
    milestone_id,
    project_id,
    sprint_name=None,
    start_date=None,
    end_date=None,
    facilitator=None,
    participants=None,
):
    """Create a new retrospective."""
    participants_json = json.dumps(participants) if participants else None

    cursor = conn.execute(
        """
        INSERT INTO sprint_retrospectives
        (milestone_id, project_id, sprint_name, start_date, end_date, facilitator, participants)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            milestone_id,
            project_id,
            sprint_name,
            start_date,
            end_date,
            facilitator,
            participants_json,
        ),
    )

    return cursor.lastrowid


def update_retrospective(conn, retro_id, **kwargs):
    """Update a retrospective."""
    allowed_fields = [
        "sprint_name",
        "start_date",
        "end_date",
        "status",
        "facilitator",
        "participants",
        "summary",
        "mood_score",
        "velocity_planned",
        "velocity_achieved",
        "completed_at",
    ]

    updates = []
    params = []

    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            value = kwargs[field]
            if field == "participants" and isinstance(value, list):
                value = json.dumps(value)
            updates.append(f"{field} = ?")
            params.append(value)

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(retro_id)

    result = conn.execute(
        f"UPDATE sprint_retrospectives SET {', '.join(updates)} WHERE id = ?", params
    )
    return result.rowcount > 0


def delete_retrospective(conn, retro_id):
    """Delete a retrospective and its items."""
    conn.execute("DELETE FROM retrospective_items WHERE retrospective_id = ?", (retro_id,))
    result = conn.execute("DELETE FROM sprint_retrospectives WHERE id = ?", (retro_id,))
    return result.rowcount > 0


def get_retrospective_items(conn, retro_id, category=None):
    """Get items for a retrospective."""
    conn.row_factory = __import__("sqlite3").Row

    query = "SELECT * FROM retrospective_items WHERE retrospective_id = ?"
    params = [retro_id]

    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY votes DESC, created_at ASC"

    return [dict(row) for row in conn.execute(query, params).fetchall()]


def add_retrospective_item(
    conn,
    retro_id,
    category,
    content,
    is_action_item=False,
    action_assignee=None,
    action_due_date=None,
    created_by=None,
):
    """Add an item to a retrospective."""
    if category not in RETRO_CATEGORIES:
        raise ValueError(f"Invalid category: {category}")

    cursor = conn.execute(
        """
        INSERT INTO retrospective_items
        (retrospective_id, category, content, is_action_item, action_assignee, action_due_date, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            retro_id,
            category,
            content,
            1 if is_action_item else 0,
            action_assignee,
            action_due_date,
            created_by,
        ),
    )

    return cursor.lastrowid


def update_retrospective_item(conn, item_id, **kwargs):
    """Update a retrospective item."""
    allowed_fields = [
        "category",
        "content",
        "is_action_item",
        "action_assignee",
        "action_due_date",
        "action_status",
    ]

    updates = []
    params = []

    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            value = kwargs[field]
            if field == "is_action_item":
                value = 1 if value else 0
            if field == "category" and value not in RETRO_CATEGORIES:
                raise ValueError(f"Invalid category: {value}")
            updates.append(f"{field} = ?")
            params.append(value)

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(item_id)

    result = conn.execute(
        f"UPDATE retrospective_items SET {', '.join(updates)} WHERE id = ?", params
    )
    return result.rowcount > 0


def delete_retrospective_item(conn, item_id):
    """Delete a retrospective item."""
    result = conn.execute("DELETE FROM retrospective_items WHERE id = ?", (item_id,))
    return result.rowcount > 0


def vote_item(conn, item_id, increment=1):
    """Vote on a retrospective item."""
    result = conn.execute(
        "UPDATE retrospective_items SET votes = votes + ? WHERE id = ?", (increment, item_id)
    )
    if result.rowcount > 0:
        row = conn.execute(
            "SELECT votes FROM retrospective_items WHERE id = ?", (item_id,)
        ).fetchone()
        return row[0] if row else 0
    return None


def get_action_items(conn, retro_id=None, status=None, assignee=None, project_id=None):
    """Get action items with filters."""
    conn.row_factory = __import__("sqlite3").Row

    query = """
        SELECT i.*, r.sprint_name, r.project_id, p.name as project_name
        FROM retrospective_items i
        JOIN sprint_retrospectives r ON i.retrospective_id = r.id
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE i.is_action_item = 1
    """
    params = []

    if retro_id:
        query += " AND i.retrospective_id = ?"
        params.append(retro_id)
    if status:
        query += " AND i.action_status = ?"
        params.append(status)
    if assignee:
        query += " AND i.action_assignee = ?"
        params.append(assignee)
    if project_id:
        query += " AND r.project_id = ?"
        params.append(project_id)

    query += " ORDER BY i.action_due_date ASC NULLS LAST, i.created_at ASC"

    return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_pending_action_items(conn, project_id=None):
    """Get all pending action items across retrospectives."""
    return get_action_items(conn, status="pending", project_id=project_id)


def get_retrospective_summary(conn, project_id=None, days=90):
    """Get summary statistics for retrospectives."""
    conn.row_factory = __import__("sqlite3").Row

    base_filter = ""
    params = []
    if project_id:
        base_filter = " AND r.project_id = ?"
        params.append(project_id)

    # Total retrospectives
    total = conn.execute(
        f"""
        SELECT COUNT(*) FROM sprint_retrospectives r
        WHERE r.created_at >= datetime('now', '-{days} days') {base_filter}
    """,
        params,
    ).fetchone()[0]

    # Average mood score
    avg_mood = conn.execute(
        f"""
        SELECT AVG(mood_score) FROM sprint_retrospectives r
        WHERE mood_score IS NOT NULL
        AND r.created_at >= datetime('now', '-{days} days') {base_filter}
    """,
        params,
    ).fetchone()[0]

    # Items by category
    category_counts = conn.execute(
        f"""
        SELECT i.category, COUNT(*) as count
        FROM retrospective_items i
        JOIN sprint_retrospectives r ON i.retrospective_id = r.id
        WHERE r.created_at >= datetime('now', '-{days} days') {base_filter}
        GROUP BY i.category
    """,
        params,
    ).fetchall()

    # Action item stats
    action_stats = conn.execute(
        f"""
        SELECT i.action_status, COUNT(*) as count
        FROM retrospective_items i
        JOIN sprint_retrospectives r ON i.retrospective_id = r.id
        WHERE i.is_action_item = 1
        AND r.created_at >= datetime('now', '-{days} days') {base_filter}
        GROUP BY i.action_status
    """,
        params,
    ).fetchall()

    # Velocity trends
    velocity = conn.execute(
        f"""
        SELECT sprint_name, velocity_planned, velocity_achieved, mood_score
        FROM sprint_retrospectives r
        WHERE velocity_planned IS NOT NULL
        AND r.created_at >= datetime('now', '-{days} days') {base_filter}
        ORDER BY r.created_at ASC
    """,
        params,
    ).fetchall()

    return {
        "total_retrospectives": total,
        "average_mood": round(avg_mood, 1) if avg_mood else None,
        "items_by_category": {row["category"]: row["count"] for row in category_counts},
        "action_items": {row["action_status"]: row["count"] for row in action_stats},
        "velocity_trends": [dict(row) for row in velocity],
        "categories": RETRO_CATEGORIES,
    }


def get_milestone_retrospective(conn, milestone_id):
    """Get retrospective for a specific milestone."""
    conn.row_factory = __import__("sqlite3").Row

    row = conn.execute(
        """
        SELECT r.*, m.name as milestone_name, p.name as project_name
        FROM sprint_retrospectives r
        LEFT JOIN milestones m ON r.milestone_id = m.id
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE r.milestone_id = ?
        ORDER BY r.created_at DESC
        LIMIT 1
    """,
        (milestone_id,),
    ).fetchone()

    if not row:
        return None

    return get_retrospective(conn, row["id"])
