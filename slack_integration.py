"""
Slack Integration Module

Provides Slack webhook integration for sending notifications about:
- Task updates (created, completed, failed)
- Error alerts
- Deployment notifications
- Milestone progress
- Bug reports
- System health alerts

Supports:
- Multiple webhook configurations (different channels for different events)
- Message formatting with Block Kit
- Event filtering
- Rate limiting
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Event types that can trigger Slack notifications
EVENT_TYPES = {
    "task_created": {
        "name": "Task Created",
        "description": "When a new task is added to the queue",
        "default_enabled": False,
    },
    "task_completed": {
        "name": "Task Completed",
        "description": "When a task is successfully completed",
        "default_enabled": True,
    },
    "task_failed": {
        "name": "Task Failed",
        "description": "When a task fails (all retries exhausted)",
        "default_enabled": True,
    },
    "error_logged": {
        "name": "Error Logged",
        "description": "When a new error is logged",
        "default_enabled": True,
    },
    "error_spike": {
        "name": "Error Spike",
        "description": "When error rate exceeds threshold",
        "default_enabled": True,
    },
    "deployment_started": {
        "name": "Deployment Started",
        "description": "When a deployment task begins",
        "default_enabled": True,
    },
    "deployment_completed": {
        "name": "Deployment Completed",
        "description": "When a deployment succeeds",
        "default_enabled": True,
    },
    "deployment_failed": {
        "name": "Deployment Failed",
        "description": "When a deployment fails",
        "default_enabled": True,
    },
    "milestone_completed": {
        "name": "Milestone Completed",
        "description": "When a milestone reaches 100% completion",
        "default_enabled": True,
    },
    "bug_critical": {
        "name": "Critical Bug",
        "description": "When a critical severity bug is reported",
        "default_enabled": True,
    },
    "node_down": {
        "name": "Node Down",
        "description": "When a cluster node becomes unresponsive",
        "default_enabled": True,
    },
    "worker_stuck": {
        "name": "Worker Stuck",
        "description": "When a worker appears stuck on a task",
        "default_enabled": True,
    },
    "sla_breach": {
        "name": "SLA Breach",
        "description": "When a task exceeds its SLA time",
        "default_enabled": True,
    },
    "daily_summary": {
        "name": "Daily Summary",
        "description": "Daily digest of activity",
        "default_enabled": False,
    },
}

# Severity levels for color coding
SEVERITY_COLORS = {
    "success": "#36a64f",  # Green
    "info": "#2196F3",  # Blue
    "warning": "#ff9800",  # Orange
    "error": "#f44336",  # Red
    "critical": "#9c27b0",  # Purple
}


def init_slack_tables(conn):
    """Initialize Slack integration tables."""
    conn.executescript(
        """
        -- Slack integration configuration
        CREATE TABLE IF NOT EXISTS slack_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            webhook_url TEXT NOT NULL,
            channel TEXT,
            username TEXT DEFAULT 'Architect Bot',
            icon_emoji TEXT DEFAULT ':robot_face:',
            enabled INTEGER DEFAULT 1,
            events TEXT DEFAULT '[]',
            filters TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Slack message history
        CREATE TABLE IF NOT EXISTS slack_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            message_text TEXT,
            payload TEXT,
            response_status INTEGER,
            response_body TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (config_id) REFERENCES slack_config(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_slack_messages_config ON slack_messages(config_id);
        CREATE INDEX IF NOT EXISTS idx_slack_messages_event ON slack_messages(event_type);
        CREATE INDEX IF NOT EXISTS idx_slack_messages_sent ON slack_messages(sent_at);

        -- Rate limiting tracking
        CREATE TABLE IF NOT EXISTS slack_rate_limits (
            config_id INTEGER PRIMARY KEY,
            last_message_at TIMESTAMP,
            messages_this_minute INTEGER DEFAULT 0,
            messages_this_hour INTEGER DEFAULT 0,
            minute_reset_at TIMESTAMP,
            hour_reset_at TIMESTAMP,
            FOREIGN KEY (config_id) REFERENCES slack_config(id) ON DELETE CASCADE
        );
    """
    )


def get_slack_configs(conn) -> List[Dict]:
    """Get all Slack configurations."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT sc.*,
               (SELECT COUNT(*) FROM slack_messages WHERE config_id = sc.id) as message_count,
               (SELECT MAX(sent_at) FROM slack_messages WHERE config_id = sc.id) as last_message_at
        FROM slack_config sc
        ORDER BY sc.name
    """
    ).fetchall()

    configs = []
    for row in rows:
        config = dict(row)
        config["events"] = json.loads(config["events"]) if config["events"] else []
        config["filters"] = json.loads(config["filters"]) if config["filters"] else {}
        # Mask webhook URL for security (show only last 8 chars)
        if config["webhook_url"]:
            config["webhook_url_masked"] = "..." + config["webhook_url"][-8:]
        configs.append(config)
    return configs


def get_slack_config(conn, config_id: int = None, name: str = None) -> Optional[Dict]:
    """Get a specific Slack configuration."""
    conn.row_factory = sqlite3.Row

    if config_id:
        row = conn.execute("SELECT * FROM slack_config WHERE id = ?", (config_id,)).fetchone()
    elif name:
        row = conn.execute("SELECT * FROM slack_config WHERE name = ?", (name,)).fetchone()
    else:
        return None

    if not row:
        return None

    config = dict(row)
    config["events"] = json.loads(config["events"]) if config["events"] else []
    config["filters"] = json.loads(config["filters"]) if config["filters"] else {}
    return config


def create_slack_config(
    conn,
    name: str,
    webhook_url: str,
    channel: str = None,
    username: str = "Architect Bot",
    icon_emoji: str = ":robot_face:",
    events: List[str] = None,
    filters: Dict = None,
) -> int:
    """Create a new Slack configuration.

    Args:
        conn: Database connection
        name: Configuration name (for reference)
        webhook_url: Slack webhook URL
        channel: Override channel (optional)
        username: Bot username
        icon_emoji: Bot icon emoji
        events: List of event types to notify on
        filters: Event filters (e.g., {'project_id': 1})

    Returns:
        ID of created configuration
    """
    # Validate webhook URL format
    if not webhook_url.startswith("https://hooks.slack.com/"):
        raise ValueError("Invalid Slack webhook URL format")

    # Validate events
    if events:
        for event in events:
            if event not in EVENT_TYPES:
                raise ValueError(f"Unknown event type: {event}")

    cursor = conn.execute(
        """
        INSERT INTO slack_config (name, webhook_url, channel, username, icon_emoji, events, filters)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            name,
            webhook_url,
            channel,
            username,
            icon_emoji,
            json.dumps(events or []),
            json.dumps(filters or {}),
        ),
    )

    return cursor.lastrowid


def update_slack_config(
    conn,
    config_id: int,
    name: str = None,
    webhook_url: str = None,
    channel: str = None,
    username: str = None,
    icon_emoji: str = None,
    enabled: bool = None,
    events: List[str] = None,
    filters: Dict = None,
) -> bool:
    """Update a Slack configuration."""
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if webhook_url is not None:
        if not webhook_url.startswith("https://hooks.slack.com/"):
            raise ValueError("Invalid Slack webhook URL format")
        updates.append("webhook_url = ?")
        params.append(webhook_url)
    if channel is not None:
        updates.append("channel = ?")
        params.append(channel)
    if username is not None:
        updates.append("username = ?")
        params.append(username)
    if icon_emoji is not None:
        updates.append("icon_emoji = ?")
        params.append(icon_emoji)
    if enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if enabled else 0)
    if events is not None:
        for event in events:
            if event not in EVENT_TYPES:
                raise ValueError(f"Unknown event type: {event}")
        updates.append("events = ?")
        params.append(json.dumps(events))
    if filters is not None:
        updates.append("filters = ?")
        params.append(json.dumps(filters))

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(config_id)

    conn.execute(f"UPDATE slack_config SET {', '.join(updates)} WHERE id = ?", params)
    return True


def delete_slack_config(conn, config_id: int) -> bool:
    """Delete a Slack configuration."""
    result = conn.execute("DELETE FROM slack_config WHERE id = ?", (config_id,))
    return result.rowcount > 0


def format_slack_message(event_type: str, data: Dict, severity: str = "info") -> Dict:
    """Format a message for Slack using Block Kit.

    Args:
        event_type: Type of event
        data: Event data
        severity: Message severity (success, info, warning, error, critical)

    Returns:
        Slack message payload
    """
    color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["info"])
    event_info = EVENT_TYPES.get(event_type, {"name": event_type})

    # Build the message blocks
    blocks = []

    # Header
    title = data.get("title", event_info["name"])
    blocks.append({"type": "header", "text": {"type": "plain_text", "text": title, "emoji": True}})

    # Main content section
    if data.get("message"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": data["message"]}})

    # Fields for additional data
    fields = []
    if data.get("project"):
        fields.append({"type": "mrkdwn", "text": f"*Project:*\n{data['project']}"})
    if data.get("status"):
        fields.append({"type": "mrkdwn", "text": f"*Status:*\n{data['status']}"})
    if data.get("assignee"):
        fields.append({"type": "mrkdwn", "text": f"*Assignee:*\n{data['assignee']}"})
    if data.get("priority"):
        fields.append({"type": "mrkdwn", "text": f"*Priority:*\n{data['priority']}"})
    if data.get("duration"):
        fields.append({"type": "mrkdwn", "text": f"*Duration:*\n{data['duration']}"})
    if data.get("error_count"):
        fields.append({"type": "mrkdwn", "text": f"*Errors:*\n{data['error_count']}"})

    if fields:
        blocks.append({"type": "section", "fields": fields[:10]})  # Slack limits to 10 fields

    # Details/description
    if data.get("details"):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{data['details'][:2900]}```",  # Limit length
                },
            }
        )

    # Link button
    if data.get("url"):
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": data.get("url_text", "View Details"),
                            "emoji": True,
                        },
                        "url": data["url"],
                        "action_id": "view_details",
                    }
                ],
            }
        )

    # Context footer
    context_elements = []
    if data.get("source"):
        context_elements.append({"type": "mrkdwn", "text": f"Source: {data['source']}"})
    context_elements.append(
        {
            "type": "mrkdwn",
            "text": f"<!date^{int(datetime.now().timestamp())}^{{date_short_pretty}} at {{time}}|{datetime.now().isoformat()}>",
        }
    )

    blocks.append({"type": "context", "elements": context_elements})

    # Build the attachment for color stripe
    return {"attachments": [{"color": color, "blocks": blocks}]}


def format_simple_message(text: str, severity: str = "info") -> Dict:
    """Format a simple text message."""
    color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["info"])
    return {"attachments": [{"color": color, "text": text}]}


def check_rate_limit(
    conn, config_id: int, max_per_minute: int = 10, max_per_hour: int = 100
) -> bool:
    """Check if we're within rate limits.

    Args:
        conn: Database connection
        config_id: Slack config ID
        max_per_minute: Max messages per minute
        max_per_hour: Max messages per hour

    Returns:
        True if within limits, False if rate limited
    """
    now = datetime.now()

    conn.row_factory = sqlite3.Row
    rate = conn.execute(
        "SELECT * FROM slack_rate_limits WHERE config_id = ?", (config_id,)
    ).fetchone()

    if not rate:
        # Initialize rate limit tracking
        conn.execute(
            """
            INSERT INTO slack_rate_limits (config_id, last_message_at, messages_this_minute,
                                          messages_this_hour, minute_reset_at, hour_reset_at)
            VALUES (?, ?, 1, 1, ?, ?)
        """,
            (
                config_id,
                now.isoformat(),
                (now + timedelta(minutes=1)).isoformat(),
                (now + timedelta(hours=1)).isoformat(),
            ),
        )
        return True

    rate = dict(rate)

    # Reset counters if time has passed
    minute_reset = (
        datetime.fromisoformat(rate["minute_reset_at"]) if rate["minute_reset_at"] else now
    )
    hour_reset = datetime.fromisoformat(rate["hour_reset_at"]) if rate["hour_reset_at"] else now

    messages_minute = rate["messages_this_minute"] or 0
    messages_hour = rate["messages_this_hour"] or 0

    if now >= minute_reset:
        messages_minute = 0
        minute_reset = now + timedelta(minutes=1)
    if now >= hour_reset:
        messages_hour = 0
        hour_reset = now + timedelta(hours=1)

    # Check limits
    if messages_minute >= max_per_minute or messages_hour >= max_per_hour:
        return False

    # Update counters
    conn.execute(
        """
        UPDATE slack_rate_limits
        SET last_message_at = ?,
            messages_this_minute = ?,
            messages_this_hour = ?,
            minute_reset_at = ?,
            hour_reset_at = ?
        WHERE config_id = ?
    """,
        (
            now.isoformat(),
            messages_minute + 1,
            messages_hour + 1,
            minute_reset.isoformat(),
            hour_reset.isoformat(),
            config_id,
        ),
    )

    return True


def send_slack_message(
    conn, config_id: int, event_type: str, data: Dict, severity: str = "info", force: bool = False
) -> Dict:
    """Send a message to Slack.

    Args:
        conn: Database connection
        config_id: Slack configuration ID
        event_type: Type of event
        data: Event data for formatting
        severity: Message severity
        force: Skip rate limiting

    Returns:
        Dict with success status and response info
    """
    config = get_slack_config(conn, config_id=config_id)
    if not config:
        return {"success": False, "error": "Configuration not found"}

    if not config["enabled"]:
        return {"success": False, "error": "Configuration is disabled"}

    # Check if event type is enabled for this config
    if config["events"] and event_type not in config["events"]:
        return {"success": False, "error": f"Event type {event_type} not enabled"}

    # Check rate limits
    if not force and not check_rate_limit(conn, config_id):
        return {"success": False, "error": "Rate limited"}

    # Format the message
    payload = format_slack_message(event_type, data, severity)

    # Add channel override if configured
    if config["channel"]:
        payload["channel"] = config["channel"]
    if config["username"]:
        payload["username"] = config["username"]
    if config["icon_emoji"]:
        payload["icon_emoji"] = config["icon_emoji"]

    # Send to Slack
    try:
        response = requests.post(config["webhook_url"], json=payload, timeout=10)

        # Log the message
        conn.execute(
            """
            INSERT INTO slack_messages (config_id, event_type, message_text, payload,
                                       response_status, response_body)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                config_id,
                event_type,
                data.get("message", data.get("title", "")),
                json.dumps(payload),
                response.status_code,
                response.text[:500] if response.text else None,
            ),
        )

        if response.status_code == 200:
            return {"success": True, "status_code": 200}
        else:
            return {
                "success": False,
                "error": f"Slack returned {response.status_code}",
                "status_code": response.status_code,
                "response": response.text,
            }

    except requests.Timeout:
        return {"success": False, "error": "Request timed out"}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def send_to_all_configs(
    conn, event_type: str, data: Dict, severity: str = "info", project_id: int = None
) -> List[Dict]:
    """Send a message to all enabled configurations that have this event type.

    Args:
        conn: Database connection
        event_type: Type of event
        data: Event data
        severity: Message severity
        project_id: Optional project ID for filtering

    Returns:
        List of results for each config
    """
    configs = get_slack_configs(conn)
    results = []

    for config in configs:
        if not config["enabled"]:
            continue

        # Check if event is enabled
        if config["events"] and event_type not in config["events"]:
            continue

        # Check project filter
        if config["filters"].get("project_id"):
            if project_id and config["filters"]["project_id"] != project_id:
                continue

        result = send_slack_message(conn, config["id"], event_type, data, severity)
        result["config_id"] = config["id"]
        result["config_name"] = config["name"]
        results.append(result)

    return results


def test_slack_webhook(webhook_url: str, channel: str = None) -> Dict:
    """Test a Slack webhook URL.

    Args:
        webhook_url: Slack webhook URL to test
        channel: Optional channel override

    Returns:
        Dict with success status
    """
    if not webhook_url.startswith("https://hooks.slack.com/"):
        return {"success": False, "error": "Invalid webhook URL format"}

    payload = {
        "text": "Test message from Architect Dashboard",
        "attachments": [
            {
                "color": SEVERITY_COLORS["info"],
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Webhook Test*\nThis is a test message to verify your Slack integration is working correctly.",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f'Sent at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                            }
                        ],
                    },
                ],
            }
        ],
    }

    if channel:
        payload["channel"] = channel

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            return {"success": True, "message": "Test message sent successfully"}
        else:
            return {
                "success": False,
                "error": f"Slack returned status {response.status_code}",
                "response": response.text,
            }
    except requests.Timeout:
        return {"success": False, "error": "Request timed out"}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def get_message_history(
    conn, config_id: int = None, event_type: str = None, limit: int = 50, offset: int = 0
) -> List[Dict]:
    """Get Slack message history.

    Args:
        conn: Database connection
        config_id: Filter by config
        event_type: Filter by event type
        limit: Max entries
        offset: Pagination offset

    Returns:
        List of message history entries
    """
    conn.row_factory = sqlite3.Row

    query = """
        SELECT sm.*, sc.name as config_name
        FROM slack_messages sm
        JOIN slack_config sc ON sm.config_id = sc.id
        WHERE 1=1
    """
    params = []

    if config_id:
        query += " AND sm.config_id = ?"
        params.append(config_id)
    if event_type:
        query += " AND sm.event_type = ?"
        params.append(event_type)

    query += " ORDER BY sm.sent_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    messages = []
    for row in rows:
        msg = dict(row)
        if msg.get("payload"):
            try:
                msg["payload"] = json.loads(msg["payload"])
            except json.JSONDecodeError:
                pass
        messages.append(msg)
    return messages


def get_slack_stats(conn, config_id: int = None, days: int = 7) -> Dict:
    """Get Slack integration statistics.

    Args:
        conn: Database connection
        config_id: Filter by config (optional)
        days: Number of days to analyze

    Returns:
        Statistics dict
    """
    conn.row_factory = sqlite3.Row

    # Build WHERE clause
    where_clause = "WHERE sent_at >= datetime('now', ?)"
    params = [f"-{days} days"]

    if config_id:
        where_clause += " AND config_id = ?"
        params.append(config_id)

    # Total messages
    total = conn.execute(f"SELECT COUNT(*) FROM slack_messages {where_clause}", params).fetchone()[
        0
    ]

    # Success rate
    success = conn.execute(
        f"SELECT COUNT(*) FROM slack_messages {where_clause} AND response_status = 200", params
    ).fetchone()[0]

    # By event type
    by_event = conn.execute(
        f"""
        SELECT event_type, COUNT(*) as count,
               SUM(CASE WHEN response_status = 200 THEN 1 ELSE 0 END) as success_count
        FROM slack_messages {where_clause}
        GROUP BY event_type
        ORDER BY count DESC
    """,
        params,
    ).fetchall()

    # By day
    by_day = conn.execute(
        f"""
        SELECT DATE(sent_at) as date, COUNT(*) as count
        FROM slack_messages {where_clause}
        GROUP BY DATE(sent_at)
        ORDER BY date
    """,
        params,
    ).fetchall()

    return {
        "period_days": days,
        "total_messages": total,
        "successful_messages": success,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        "by_event_type": [dict(row) for row in by_event],
        "by_day": [dict(row) for row in by_day],
    }


# Convenience functions for common notifications


def notify_task_completed(conn, task: Dict, duration_seconds: int = None):
    """Send notification for completed task."""
    data = {
        "title": "Task Completed",
        "message": f"*{task.get('name', 'Task')}* has been completed successfully.",
        "project": task.get("project_name"),
        "status": "Completed",
        "priority": task.get("priority"),
    }
    if duration_seconds:
        minutes = duration_seconds // 60
        data["duration"] = f"{minutes} min" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"

    return send_to_all_configs(
        conn, "task_completed", data, "success", project_id=task.get("project_id")
    )


def notify_task_failed(conn, task: Dict, error_message: str = None):
    """Send notification for failed task."""
    data = {
        "title": "Task Failed",
        "message": f"*{task.get('name', 'Task')}* has failed.",
        "project": task.get("project_name"),
        "status": "Failed",
        "priority": task.get("priority"),
    }
    if error_message:
        data["details"] = error_message[:500]

    return send_to_all_configs(
        conn, "task_failed", data, "error", project_id=task.get("project_id")
    )


def notify_error(conn, error: Dict):
    """Send notification for logged error."""
    data = {
        "title": "Error Logged",
        "message": f"*{error.get('error_type', 'Error')}*: {error.get('message', 'Unknown error')}",
        "source": error.get("source"),
        "error_count": error.get("occurrence_count", 1),
    }
    if error.get("stack_trace"):
        data["details"] = error["stack_trace"][:500]

    severity = "critical" if error.get("severity") == "critical" else "error"
    return send_to_all_configs(
        conn, "error_logged", data, severity, project_id=error.get("project_id")
    )


def notify_deployment(conn, status: str, project_name: str, details: str = None, url: str = None):
    """Send deployment notification."""
    event_type = f"deployment_{status}"
    severity_map = {"started": "info", "completed": "success", "failed": "error"}

    data = {
        "title": f"Deployment {status.title()}",
        "message": f"Deployment for *{project_name}* has {status}.",
        "project": project_name,
        "status": status.title(),
    }
    if details:
        data["details"] = details
    if url:
        data["url"] = url
        data["url_text"] = "View Deployment"

    return send_to_all_configs(conn, event_type, data, severity_map.get(status, "info"))


def notify_critical_bug(conn, bug: Dict):
    """Send notification for critical bug."""
    data = {
        "title": "Critical Bug Reported",
        "message": f"*{bug.get('title', 'Bug')}*",
        "project": bug.get("project_name"),
        "status": bug.get("status", "Open"),
        "priority": "Critical",
    }
    if bug.get("description"):
        data["details"] = bug["description"][:500]

    return send_to_all_configs(
        conn, "bug_critical", data, "critical", project_id=bug.get("project_id")
    )
