"""
Notification Rules Module
Configure rules for when and how notifications are sent
"""

import json
import re
from datetime import datetime, timedelta

# Notification channels
CHANNELS = {
    "email": "Email",
    "slack": "Slack",
    "webhook": "Webhook",
    "in_app": "In-App",
    "sms": "SMS",
}

# Event types that can trigger notifications
EVENT_TYPES = {
    "task_created": "Task Created",
    "task_assigned": "Task Assigned",
    "task_status_changed": "Task Status Changed",
    "task_completed": "Task Completed",
    "task_overdue": "Task Overdue",
    "task_due_soon": "Task Due Soon",
    "task_comment": "Task Comment Added",
    "bug_created": "Bug Created",
    "bug_resolved": "Bug Resolved",
    "bug_severity_changed": "Bug Severity Changed",
    "feature_created": "Feature Created",
    "feature_status_changed": "Feature Status Changed",
    "milestone_created": "Milestone Created",
    "milestone_completed": "Milestone Completed",
    "milestone_due_soon": "Milestone Due Soon",
    "project_created": "Project Created",
    "project_status_changed": "Project Status Changed",
    "error_logged": "Error Logged",
    "error_threshold": "Error Threshold Exceeded",
    "worker_offline": "Worker Offline",
    "node_offline": "Node Offline",
    "budget_threshold": "Budget Threshold Exceeded",
    "mention": "User Mentioned",
    "assignment_change": "Assignment Changed",
}

# Condition operators
OPERATORS = {
    "equals": "Equals",
    "not_equals": "Not Equals",
    "contains": "Contains",
    "not_contains": "Does Not Contain",
    "greater_than": "Greater Than",
    "less_than": "Less Than",
    "in_list": "In List",
    "not_in_list": "Not In List",
    "is_empty": "Is Empty",
    "is_not_empty": "Is Not Empty",
    "matches_regex": "Matches Regex",
}

# Frequency options
FREQUENCIES = {
    "immediate": "Immediate",
    "hourly": "Hourly Digest",
    "daily": "Daily Digest",
    "weekly": "Weekly Digest",
}


def create_rule(
    conn,
    name,
    event_type,
    channels,
    user_id=None,
    project_id=None,
    conditions=None,
    frequency="immediate",
    enabled=True,
    quiet_hours_start=None,
    quiet_hours_end=None,
    description=None,
    created_by=None,
):
    """Create a new notification rule."""
    cursor = conn.cursor()

    if event_type not in EVENT_TYPES:
        return {"error": f'Invalid event_type. Must be one of: {", ".join(EVENT_TYPES.keys())}'}

    # Validate channels
    if not channels:
        return {"error": "At least one channel is required"}

    for ch in channels:
        if ch not in CHANNELS:
            return {"error": f"Invalid channel: {ch}"}

    if frequency not in FREQUENCIES:
        return {"error": f'Invalid frequency. Must be one of: {", ".join(FREQUENCIES.keys())}'}

    # Validate conditions if provided
    if conditions:
        for cond in conditions:
            if "field" not in cond or "operator" not in cond:
                return {"error": "Each condition must have field and operator"}
            if cond["operator"] not in OPERATORS:
                return {"error": f'Invalid operator: {cond["operator"]}'}

    cursor.execute(
        """
        INSERT INTO notification_rules (name, event_type, channels, user_id, project_id,
                                        conditions, frequency, enabled, quiet_hours_start,
                                        quiet_hours_end, description, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            name,
            event_type,
            json.dumps(channels),
            user_id,
            project_id,
            json.dumps(conditions) if conditions else None,
            frequency,
            enabled,
            quiet_hours_start,
            quiet_hours_end,
            description,
            created_by,
        ),
    )

    rule_id = cursor.lastrowid
    conn.commit()

    return {
        "id": rule_id,
        "name": name,
        "event_type": event_type,
        "channels": channels,
        "frequency": frequency,
        "enabled": enabled,
    }


def get_rule(conn, rule_id):
    """Get a single notification rule."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.*, p.name as project_name
        FROM notification_rules r
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE r.id = ?
    """,
        (rule_id,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    result = dict(row)
    if result.get("channels"):
        result["channels"] = json.loads(result["channels"])
    if result.get("conditions"):
        result["conditions"] = json.loads(result["conditions"])

    return result


def list_rules(conn, user_id=None, project_id=None, event_type=None, enabled=None):
    """List notification rules with optional filters."""
    cursor = conn.cursor()

    query = """
        SELECT r.*, p.name as project_name
        FROM notification_rules r
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE 1=1
    """
    params = []

    if user_id:
        query += " AND (r.user_id = ? OR r.user_id IS NULL)"
        params.append(user_id)

    if project_id:
        query += " AND (r.project_id = ? OR r.project_id IS NULL)"
        params.append(project_id)

    if event_type:
        query += " AND r.event_type = ?"
        params.append(event_type)

    if enabled is not None:
        query += " AND r.enabled = ?"
        params.append(enabled)

    query += " ORDER BY r.name"

    cursor.execute(query, params)
    rules = []

    for row in cursor.fetchall():
        rule = dict(row)
        if rule.get("channels"):
            rule["channels"] = json.loads(rule["channels"])
        if rule.get("conditions"):
            rule["conditions"] = json.loads(rule["conditions"])
        rules.append(rule)

    return {"rules": rules, "count": len(rules)}


def update_rule(conn, rule_id, updates):
    """Update a notification rule."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM notification_rules WHERE id = ?", (rule_id,))
    if not cursor.fetchone():
        return {"error": "Rule not found"}

    allowed_fields = [
        "name",
        "event_type",
        "channels",
        "user_id",
        "project_id",
        "conditions",
        "frequency",
        "enabled",
        "quiet_hours_start",
        "quiet_hours_end",
        "description",
    ]

    set_clauses = []
    params = []

    for field in allowed_fields:
        if field in updates:
            value = updates[field]

            if field == "event_type" and value not in EVENT_TYPES:
                return {"error": f"Invalid event_type"}

            if field == "channels":
                if not value:
                    return {"error": "At least one channel is required"}
                for ch in value:
                    if ch not in CHANNELS:
                        return {"error": f"Invalid channel: {ch}"}
                value = json.dumps(value)

            if field == "conditions" and value is not None:
                value = json.dumps(value)

            if field == "frequency" and value not in FREQUENCIES:
                return {"error": f"Invalid frequency"}

            set_clauses.append(f"{field} = ?")
            params.append(value)

    if not set_clauses:
        return {"error": "No valid fields to update"}

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(rule_id)

    query = f'UPDATE notification_rules SET {", ".join(set_clauses)} WHERE id = ?'
    cursor.execute(query, params)
    conn.commit()

    return get_rule(conn, rule_id)


def delete_rule(conn, rule_id):
    """Delete a notification rule."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM notification_rules WHERE id = ?", (rule_id,))
    if not cursor.fetchone():
        return {"error": "Rule not found"}

    cursor.execute("DELETE FROM notification_rules WHERE id = ?", (rule_id,))
    conn.commit()

    return {"success": True, "deleted_id": rule_id}


def toggle_rule(conn, rule_id, enabled):
    """Enable or disable a rule."""
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE notification_rules SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (enabled, rule_id),
    )

    if cursor.rowcount == 0:
        return {"error": "Rule not found"}

    conn.commit()
    return {"id": rule_id, "enabled": enabled}


def evaluate_condition(condition, event_data):
    """Evaluate a single condition against event data."""
    field = condition.get("field")
    operator = condition.get("operator")
    value = condition.get("value")

    # Get field value from event data (supports nested fields with dot notation)
    field_value = event_data
    for part in field.split("."):
        if isinstance(field_value, dict):
            field_value = field_value.get(part)
        else:
            field_value = None
            break

    if operator == "equals":
        return field_value == value
    elif operator == "not_equals":
        return field_value != value
    elif operator == "contains":
        return value in str(field_value) if field_value else False
    elif operator == "not_contains":
        return value not in str(field_value) if field_value else True
    elif operator == "greater_than":
        try:
            return float(field_value) > float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "less_than":
        try:
            return float(field_value) < float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "in_list":
        return field_value in (value if isinstance(value, list) else [value])
    elif operator == "not_in_list":
        return field_value not in (value if isinstance(value, list) else [value])
    elif operator == "is_empty":
        return not field_value
    elif operator == "is_not_empty":
        return bool(field_value)
    elif operator == "matches_regex":
        try:
            return bool(re.match(value, str(field_value))) if field_value else False
        except re.error:
            return False

    return False


def check_quiet_hours(rule):
    """Check if current time is within quiet hours."""
    quiet_start = rule.get("quiet_hours_start")
    quiet_end = rule.get("quiet_hours_end")

    if not quiet_start or not quiet_end:
        return False

    now = datetime.now().time()
    start = datetime.strptime(quiet_start, "%H:%M").time()
    end = datetime.strptime(quiet_end, "%H:%M").time()

    if start <= end:
        return start <= now <= end
    else:
        # Quiet hours span midnight
        return now >= start or now <= end


def find_matching_rules(conn, event_type, event_data, user_id=None, project_id=None):
    """Find all rules that match a given event."""
    cursor = conn.cursor()

    query = """
        SELECT * FROM notification_rules
        WHERE event_type = ? AND enabled = 1
    """
    params = [event_type]

    # Include global rules and user/project specific rules
    if user_id:
        query += " AND (user_id = ? OR user_id IS NULL)"
        params.append(user_id)
    else:
        query += " AND user_id IS NULL"

    if project_id:
        query += " AND (project_id = ? OR project_id IS NULL)"
        params.append(project_id)
    else:
        query += " AND project_id IS NULL"

    cursor.execute(query, params)

    matching_rules = []

    for row in cursor.fetchall():
        rule = dict(row)

        # Parse JSON fields
        if rule.get("channels"):
            rule["channels"] = json.loads(rule["channels"])
        if rule.get("conditions"):
            rule["conditions"] = json.loads(rule["conditions"])

        # Check quiet hours
        if check_quiet_hours(rule):
            continue

        # Check conditions
        conditions = rule.get("conditions") or []
        all_conditions_met = True

        for condition in conditions:
            if not evaluate_condition(condition, event_data):
                all_conditions_met = False
                break

        if all_conditions_met:
            matching_rules.append(rule)

    return matching_rules


def queue_notification(conn, rule_id, event_type, event_data, channels, user_id=None):
    """Queue a notification for delivery."""
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO notification_queue (rule_id, event_type, event_data, channels,
                                        user_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
    """,
        (rule_id, event_type, json.dumps(event_data), json.dumps(channels), user_id),
    )

    notification_id = cursor.lastrowid
    conn.commit()

    return notification_id


def get_pending_notifications(conn, frequency="immediate", limit=100):
    """Get pending notifications for delivery."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT nq.*, nr.frequency, nr.name as rule_name
        FROM notification_queue nq
        JOIN notification_rules nr ON nq.rule_id = nr.id
        WHERE nq.status = 'pending' AND nr.frequency = ?
        ORDER BY nq.created_at
        LIMIT ?
    """,
        (frequency, limit),
    )

    notifications = []
    for row in cursor.fetchall():
        notif = dict(row)
        if notif.get("event_data"):
            notif["event_data"] = json.loads(notif["event_data"])
        if notif.get("channels"):
            notif["channels"] = json.loads(notif["channels"])
        notifications.append(notif)

    return notifications


def mark_notification_sent(conn, notification_id, channel, success=True, error_message=None):
    """Mark a notification as sent or failed."""
    cursor = conn.cursor()

    status = "sent" if success else "failed"

    cursor.execute(
        """
        UPDATE notification_queue
        SET status = ?, sent_at = CURRENT_TIMESTAMP, error_message = ?
        WHERE id = ?
    """,
        (status, error_message, notification_id),
    )

    # Log delivery attempt
    cursor.execute(
        """
        INSERT INTO notification_log (notification_id, channel, status, error_message, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """,
        (notification_id, channel, status, error_message),
    )

    conn.commit()


def get_notification_stats(conn, start_date=None, end_date=None, user_id=None):
    """Get notification delivery statistics."""
    cursor = conn.cursor()

    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    query = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
        FROM notification_queue
        WHERE DATE(created_at) BETWEEN ? AND ?
    """
    params = [start_date, end_date]

    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    cursor.execute(query, params)
    totals = dict(cursor.fetchone())

    # Get by event type
    cursor.execute(
        """
        SELECT event_type, COUNT(*) as count
        FROM notification_queue
        WHERE DATE(created_at) BETWEEN ? AND ?
        GROUP BY event_type
        ORDER BY count DESC
    """,
        (start_date, end_date),
    )

    by_event = [dict(row) for row in cursor.fetchall()]

    # Get by channel
    cursor.execute(
        """
        SELECT channel, status, COUNT(*) as count
        FROM notification_log
        WHERE DATE(created_at) BETWEEN ? AND ?
        GROUP BY channel, status
    """,
        (start_date, end_date),
    )

    by_channel = {}
    for row in cursor.fetchall():
        ch = row["channel"]
        if ch not in by_channel:
            by_channel[ch] = {"sent": 0, "failed": 0}
        by_channel[ch][row["status"]] = row["count"]

    return {
        "period": {"start": start_date, "end": end_date},
        "totals": totals,
        "by_event_type": by_event,
        "by_channel": by_channel,
    }


def create_default_rules(conn, user_id):
    """Create default notification rules for a user."""
    defaults = [
        {
            "name": "Task Assigned to Me",
            "event_type": "task_assigned",
            "channels": ["in_app", "email"],
            "frequency": "immediate",
        },
        {
            "name": "Task Due Soon",
            "event_type": "task_due_soon",
            "channels": ["in_app"],
            "frequency": "daily",
        },
        {
            "name": "Mentioned in Comment",
            "event_type": "mention",
            "channels": ["in_app", "email"],
            "frequency": "immediate",
        },
        {
            "name": "Critical Bug Created",
            "event_type": "bug_created",
            "channels": ["in_app", "slack"],
            "conditions": [{"field": "severity", "operator": "equals", "value": "critical"}],
            "frequency": "immediate",
        },
    ]

    created = []
    for rule_def in defaults:
        result = create_rule(
            conn,
            name=rule_def["name"],
            event_type=rule_def["event_type"],
            channels=rule_def["channels"],
            user_id=user_id,
            conditions=rule_def.get("conditions"),
            frequency=rule_def.get("frequency", "immediate"),
            created_by="system",
        )
        if "id" in result:
            created.append(result)

    return {"created": created, "count": len(created)}


def get_event_types():
    """Get available event types."""
    return EVENT_TYPES


def get_channels():
    """Get available notification channels."""
    return CHANNELS


def get_operators():
    """Get available condition operators."""
    return OPERATORS


def get_frequencies():
    """Get available notification frequencies."""
    return FREQUENCIES
