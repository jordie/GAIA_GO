"""
Activity Timeline Module

Provides functions for generating activity timelines with
grouping, filtering, aggregation, and enrichment of activities.
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Activity action categories
ACTION_CATEGORIES = {
    "create": ["create", "add", "insert", "new", "register"],
    "update": ["update", "edit", "modify", "change", "set"],
    "delete": ["delete", "remove", "archive", "deactivate"],
    "view": ["view", "get", "read", "list", "fetch"],
    "status": ["complete", "start", "stop", "pause", "resume", "cancel", "fail"],
    "auth": ["login", "logout", "authenticate", "authorize"],
    "system": ["refresh", "sync", "import", "export", "backup", "restore"],
}

# Entity type display names
ENTITY_DISPLAY_NAMES = {
    "project": "Project",
    "milestone": "Milestone",
    "feature": "Feature",
    "bug": "Bug",
    "task": "Task",
    "error": "Error",
    "node": "Node",
    "worker": "Worker",
    "user": "User",
    "tmux_session": "tmux Session",
    "report": "Report",
    "template": "Template",
    "setting": "Setting",
    "webhook": "Webhook",
    "deployment": "Deployment",
}

# Time grouping options
TIME_GROUPS = ["hour", "day", "week", "month"]


def get_action_category(action: str) -> str:
    """Get the category for an action.

    Args:
        action: Action name

    Returns:
        Category name
    """
    action_lower = action.lower()
    for category, actions in ACTION_CATEGORIES.items():
        for a in actions:
            if a in action_lower:
                return category
    return "other"


def get_timeline(
    conn,
    start_date: datetime = None,
    end_date: datetime = None,
    user_id: int = None,
    entity_type: str = None,
    entity_id: int = None,
    action: str = None,
    action_category: str = None,
    limit: int = 100,
    offset: int = 0,
    include_details: bool = True,
) -> Dict:
    """Get activity timeline with filtering.

    Args:
        conn: Database connection
        start_date: Filter from date
        end_date: Filter to date
        user_id: Filter by user
        entity_type: Filter by entity type
        entity_id: Filter by entity ID
        action: Filter by action (supports wildcards)
        action_category: Filter by action category
        limit: Maximum results
        offset: Pagination offset
        include_details: Include activity details

    Returns:
        Timeline data with activities
    """
    conn.row_factory = sqlite3.Row

    # Build query
    query = """
        SELECT a.*, u.username
        FROM activity_log a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND a.created_at >= ?"
        params.append(start_date.isoformat())

    if end_date:
        query += " AND a.created_at <= ?"
        params.append(end_date.isoformat())

    if user_id:
        query += " AND a.user_id = ?"
        params.append(user_id)

    if entity_type:
        query += " AND a.entity_type = ?"
        params.append(entity_type)

    if entity_id:
        query += " AND a.entity_id = ?"
        params.append(entity_id)

    if action:
        if "%" in action or "*" in action:
            query += " AND a.action LIKE ?"
            params.append(action.replace("*", "%"))
        else:
            query += " AND a.action = ?"
            params.append(action)

    if action_category:
        actions = ACTION_CATEGORIES.get(action_category, [])
        if actions:
            placeholders = " OR ".join(["a.action LIKE ?" for _ in actions])
            query += f" AND ({placeholders})"
            params.extend([f"%{a}%" for a in actions])

    # Count total
    count_query = query.replace("SELECT a.*, u.username", "SELECT COUNT(*) as total")
    total = conn.execute(count_query, params).fetchone()["total"]

    # Add ordering and pagination
    query += " ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()

    activities = []
    for row in rows:
        activity = {
            "id": row["id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "action": row["action"],
            "action_category": get_action_category(row["action"]),
            "entity_type": row["entity_type"],
            "entity_type_display": ENTITY_DISPLAY_NAMES.get(row["entity_type"], row["entity_type"]),
            "entity_id": row["entity_id"],
            "created_at": row["created_at"],
            "ip_address": row["ip_address"],
        }

        if include_details and row["details"]:
            try:
                activity["details"] = json.loads(row["details"])
            except json.JSONDecodeError:
                activity["details"] = row["details"]

        activities.append(activity)

    return {
        "activities": activities,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(activities) < total,
    }


def get_timeline_grouped(
    conn,
    group_by: str = "day",
    start_date: datetime = None,
    end_date: datetime = None,
    user_id: int = None,
    entity_type: str = None,
    limit_per_group: int = 10,
) -> Dict:
    """Get activity timeline grouped by time period.

    Args:
        conn: Database connection
        group_by: Grouping period ('hour', 'day', 'week', 'month')
        start_date: Filter from date
        end_date: Filter to date
        user_id: Filter by user
        entity_type: Filter by entity type
        limit_per_group: Max activities per group

    Returns:
        Grouped timeline data
    """
    if group_by not in TIME_GROUPS:
        group_by = "day"

    # Set default date range
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        if group_by == "hour":
            start_date = end_date - timedelta(hours=24)
        elif group_by == "day":
            start_date = end_date - timedelta(days=7)
        elif group_by == "week":
            start_date = end_date - timedelta(weeks=4)
        else:
            start_date = end_date - timedelta(days=90)

    # Get all activities in range
    result = get_timeline(
        conn,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        entity_type=entity_type,
        limit=1000,
        include_details=False,
    )

    # Group activities
    groups = defaultdict(list)
    for activity in result["activities"]:
        created = datetime.fromisoformat(activity["created_at"].replace("Z", "+00:00"))

        if group_by == "hour":
            key = created.strftime("%Y-%m-%d %H:00")
        elif group_by == "day":
            key = created.strftime("%Y-%m-%d")
        elif group_by == "week":
            # Start of week (Monday)
            week_start = created - timedelta(days=created.weekday())
            key = week_start.strftime("%Y-%m-%d")
        else:  # month
            key = created.strftime("%Y-%m")

        if len(groups[key]) < limit_per_group:
            groups[key].append(activity)

    # Convert to sorted list
    grouped_timeline = []
    for key in sorted(groups.keys(), reverse=True):
        grouped_timeline.append(
            {
                "period": key,
                "group_by": group_by,
                "activities": groups[key],
                "count": len(groups[key]),
            }
        )

    return {
        "groups": grouped_timeline,
        "group_by": group_by,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_groups": len(grouped_timeline),
        "total_activities": result["total"],
    }


def get_activity_stats(
    conn, start_date: datetime = None, end_date: datetime = None, user_id: int = None
) -> Dict:
    """Get activity statistics.

    Args:
        conn: Database connection
        start_date: Filter from date
        end_date: Filter to date
        user_id: Filter by user

    Returns:
        Activity statistics
    """
    conn.row_factory = sqlite3.Row

    # Set defaults
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    base_where = "WHERE created_at >= ? AND created_at <= ?"
    params = [start_date.isoformat(), end_date.isoformat()]

    if user_id:
        base_where += " AND user_id = ?"
        params.append(user_id)

    # Total count
    total = conn.execute(
        f"SELECT COUNT(*) as count FROM activity_log {base_where}", params
    ).fetchone()["count"]

    # By action
    by_action = conn.execute(
        f"""
        SELECT action, COUNT(*) as count
        FROM activity_log {base_where}
        GROUP BY action
        ORDER BY count DESC
        LIMIT 20
    """,
        params,
    ).fetchall()

    # By entity type
    by_entity = conn.execute(
        f"""
        SELECT entity_type, COUNT(*) as count
        FROM activity_log {base_where}
        GROUP BY entity_type
        ORDER BY count DESC
    """,
        params,
    ).fetchall()

    # By user (top 10)
    by_user = conn.execute(
        f"""
        SELECT a.user_id, u.username, COUNT(*) as count
        FROM activity_log a
        LEFT JOIN users u ON a.user_id = u.id
        {base_where}
        GROUP BY a.user_id
        ORDER BY count DESC
        LIMIT 10
    """,
        params,
    ).fetchall()

    # By hour of day
    by_hour = conn.execute(
        f"""
        SELECT strftime('%H', created_at) as hour, COUNT(*) as count
        FROM activity_log {base_where}
        GROUP BY hour
        ORDER BY hour
    """,
        params,
    ).fetchall()

    # By day of week
    by_day = conn.execute(
        f"""
        SELECT strftime('%w', created_at) as day, COUNT(*) as count
        FROM activity_log {base_where}
        GROUP BY day
        ORDER BY day
    """,
        params,
    ).fetchall()

    # Daily trend
    daily_trend = conn.execute(
        f"""
        SELECT date(created_at) as date, COUNT(*) as count
        FROM activity_log {base_where}
        GROUP BY date
        ORDER BY date
    """,
        params,
    ).fetchall()

    # Categorize actions
    action_categories = defaultdict(int)
    for row in by_action:
        category = get_action_category(row["action"])
        action_categories[category] += row["count"]

    return {
        "total": total,
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": (end_date - start_date).days,
        },
        "by_action": [{"action": r["action"], "count": r["count"]} for r in by_action],
        "by_action_category": dict(action_categories),
        "by_entity_type": [
            {"entity_type": r["entity_type"], "count": r["count"]} for r in by_entity
        ],
        "by_user": [
            {"user_id": r["user_id"], "username": r["username"], "count": r["count"]}
            for r in by_user
        ],
        "by_hour": [{"hour": int(r["hour"]), "count": r["count"]} for r in by_hour],
        "by_day_of_week": [{"day": int(r["day"]), "count": r["count"]} for r in by_day],
        "daily_trend": [{"date": r["date"], "count": r["count"]} for r in daily_trend],
        "avg_per_day": round(total / max((end_date - start_date).days, 1), 1),
    }


def get_entity_activity(conn, entity_type: str, entity_id: int, limit: int = 50) -> Dict:
    """Get activity history for a specific entity.

    Args:
        conn: Database connection
        entity_type: Entity type
        entity_id: Entity ID
        limit: Maximum results

    Returns:
        Entity activity history
    """
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT a.*, u.username
        FROM activity_log a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.entity_type = ? AND a.entity_id = ?
        ORDER BY a.created_at DESC
        LIMIT ?
    """,
        (entity_type, entity_id, limit),
    ).fetchall()

    activities = []
    for row in rows:
        activity = {
            "id": row["id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "action": row["action"],
            "action_category": get_action_category(row["action"]),
            "created_at": row["created_at"],
            "ip_address": row["ip_address"],
        }

        if row["details"]:
            try:
                activity["details"] = json.loads(row["details"])
            except json.JSONDecodeError:
                activity["details"] = row["details"]

        activities.append(activity)

    # Get first and last activity
    first_activity = activities[-1] if activities else None
    last_activity = activities[0] if activities else None

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "activities": activities,
        "total": len(activities),
        "first_activity": first_activity,
        "last_activity": last_activity,
    }


def get_user_activity(
    conn, user_id: int, start_date: datetime = None, end_date: datetime = None, limit: int = 100
) -> Dict:
    """Get activity history for a specific user.

    Args:
        conn: Database connection
        user_id: User ID
        start_date: Filter from date
        end_date: Filter to date
        limit: Maximum results

    Returns:
        User activity history with stats
    """
    conn.row_factory = sqlite3.Row

    # Get user info
    user = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        return None

    # Get activities
    result = get_timeline(
        conn, user_id=user_id, start_date=start_date, end_date=end_date, limit=limit
    )

    # Get stats
    stats = get_activity_stats(conn, start_date, end_date, user_id)

    return {
        "user_id": user_id,
        "username": user["username"],
        "activities": result["activities"],
        "total": result["total"],
        "stats": stats,
    }


def get_recent_activity_feed(
    conn, limit: int = 50, user_id: int = None, exclude_actions: List[str] = None
) -> List[Dict]:
    """Get a feed of recent activities with enriched data.

    Args:
        conn: Database connection
        limit: Maximum results
        user_id: Optional user filter
        exclude_actions: Actions to exclude

    Returns:
        List of enriched activities
    """
    conn.row_factory = sqlite3.Row

    query = """
        SELECT a.*, u.username
        FROM activity_log a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    """
    params = []

    if user_id:
        query += " AND a.user_id = ?"
        params.append(user_id)

    if exclude_actions:
        placeholders = ",".join(["?" for _ in exclude_actions])
        query += f" AND a.action NOT IN ({placeholders})"
        params.extend(exclude_actions)

    query += " ORDER BY a.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    feed = []
    for row in rows:
        activity = {
            "id": row["id"],
            "user_id": row["user_id"],
            "username": row["username"] or "System",
            "action": row["action"],
            "action_category": get_action_category(row["action"]),
            "entity_type": row["entity_type"],
            "entity_type_display": ENTITY_DISPLAY_NAMES.get(row["entity_type"], row["entity_type"]),
            "entity_id": row["entity_id"],
            "created_at": row["created_at"],
            "time_ago": _time_ago(row["created_at"]),
        }

        # Parse details
        if row["details"]:
            try:
                details = json.loads(row["details"])
                activity["details"] = details
                # Extract entity name if present
                if "name" in details:
                    activity["entity_name"] = details["name"]
                elif "title" in details:
                    activity["entity_name"] = details["title"]
            except json.JSONDecodeError:
                activity["details"] = row["details"]

        # Generate description
        activity["description"] = _generate_description(activity)

        feed.append(activity)

    return feed


def search_activity(
    conn, query: str, start_date: datetime = None, end_date: datetime = None, limit: int = 50
) -> List[Dict]:
    """Search activity log.

    Args:
        conn: Database connection
        query: Search query
        start_date: Filter from date
        end_date: Filter to date
        limit: Maximum results

    Returns:
        Matching activities
    """
    conn.row_factory = sqlite3.Row

    sql = """
        SELECT a.*, u.username
        FROM activity_log a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE (a.action LIKE ? OR a.entity_type LIKE ? OR a.details LIKE ?)
    """
    search_term = f"%{query}%"
    params = [search_term, search_term, search_term]

    if start_date:
        sql += " AND a.created_at >= ?"
        params.append(start_date.isoformat())

    if end_date:
        sql += " AND a.created_at <= ?"
        params.append(end_date.isoformat())

    sql += " ORDER BY a.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()

    results = []
    for row in rows:
        activity = {
            "id": row["id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "action": row["action"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "created_at": row["created_at"],
        }

        if row["details"]:
            try:
                activity["details"] = json.loads(row["details"])
            except json.JSONDecodeError:
                activity["details"] = row["details"]

        results.append(activity)

    return results


def _time_ago(timestamp: str) -> str:
    """Convert timestamp to human-readable time ago string."""
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt

        if diff.days > 30:
            return f"{diff.days // 30} months ago"
        elif diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600} hours ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60} minutes ago"
        else:
            return "just now"
    except Exception:
        return timestamp


def _generate_description(activity: Dict) -> str:
    """Generate a human-readable description for an activity."""
    username = activity.get("username", "Someone")
    action = activity.get("action", "").replace("_", " ")
    entity_type = activity.get("entity_type_display", activity.get("entity_type", "item"))
    entity_name = activity.get("entity_name", f"#{activity.get('entity_id', '')}")

    # Handle common action patterns
    if "create" in action.lower():
        return f"{username} created {entity_type} {entity_name}"
    elif "update" in action.lower() or "edit" in action.lower():
        return f"{username} updated {entity_type} {entity_name}"
    elif "delete" in action.lower():
        return f"{username} deleted {entity_type} {entity_name}"
    elif "complete" in action.lower():
        return f"{username} completed {entity_type} {entity_name}"
    elif "login" in action.lower():
        return f"{username} logged in"
    elif "logout" in action.lower():
        return f"{username} logged out"
    else:
        return f"{username} {action} {entity_type} {entity_name}"


def export_activity(conn, start_date: datetime, end_date: datetime, format: str = "json") -> Any:
    """Export activity log.

    Args:
        conn: Database connection
        start_date: Start date
        end_date: End date
        format: Export format ('json' or 'csv')

    Returns:
        Exported data
    """
    result = get_timeline(
        conn, start_date=start_date, end_date=end_date, limit=10000, include_details=True
    )

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "user_id",
                "username",
                "action",
                "entity_type",
                "entity_id",
                "created_at",
                "details",
            ]
        )

        for activity in result["activities"]:
            writer.writerow(
                [
                    activity["id"],
                    activity["user_id"],
                    activity["username"],
                    activity["action"],
                    activity["entity_type"],
                    activity["entity_id"],
                    activity["created_at"],
                    json.dumps(activity.get("details", "")),
                ]
            )

        return output.getvalue()

    return result
