"""
Notification Service for Service Failures

Provides centralized notification handling with support for:
- File logging (JSON format)
- Database logging
- WebSocket broadcasting
- Optional webhooks (Slack, Discord, custom)

Usage:
    from services.notifications import notify_service_failure

    notify_service_failure(
        title="Worker crashed",
        message="Task worker stopped responding",
        source="task_worker",
        severity="critical",
        metadata={"worker_id": "w123", "last_task": 42}
    )
"""

import json
import logging
import os
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Add parent directory for imports
SERVICE_DIR = Path(__file__).parent
BASE_DIR = SERVICE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import ServiceConnectionPool

logger = logging.getLogger(__name__)

# Severity levels (in order of importance)
SEVERITY_LEVELS = ["critical", "error", "warning", "info"]

# Default log file path
DEFAULT_LOG_PATH = "/tmp/architect_notifications.log"


class NotificationService:
    """Centralized notification service for service failures."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        """Singleton pattern to ensure single instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        """Initialize the notification service."""
        if self._initialized:
            return

        self.db_path = db_path
        self._pool = None
        self._settings_cache = {}
        self._cache_time = None
        self._cache_ttl = 60  # Refresh settings every 60 seconds
        self._socketio = None  # Set by app.py
        self._initialized = True

        # Ensure log directory exists
        log_dir = os.path.dirname(DEFAULT_LOG_PATH)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Initialize connection pool if db_path provided
        if self.db_path:
            self._init_pool()

    def _init_pool(self):
        """Initialize the connection pool."""
        if self.db_path:
            self._pool = ServiceConnectionPool.get_or_create(
                self.db_path, min_connections=1, max_connections=3
            )

    def set_socketio(self, socketio):
        """Set the SocketIO instance for broadcasting."""
        self._socketio = socketio

    def set_db_path(self, db_path: str):
        """Set the database path."""
        self.db_path = db_path
        self._settings_cache = {}  # Clear cache when DB changes
        self._init_pool()  # Reinitialize pool

    def _get_db_connection(self):
        """Get a database connection from pool."""
        if not self.db_path:
            return None
        if self._pool:
            return self._pool.connection()
        # Fallback for backwards compatibility
        return sqlite3.connect(self.db_path)

    def _load_settings(self) -> Dict[str, Dict]:
        """Load notification settings from database."""
        now = datetime.now()

        # Use cached settings if still valid
        if (
            self._cache_time
            and (now - self._cache_time).total_seconds() < self._cache_ttl
            and self._settings_cache
        ):
            return self._settings_cache

        settings = {}
        conn = self._get_db_connection()
        if not conn:
            return settings

        try:
            cursor = conn.execute(
                """
                SELECT name, category, config, enabled, notify_on
                FROM notification_settings
                WHERE enabled = 1
            """
            )
            for row in cursor.fetchall():
                name, category, config_json, enabled, notify_on = row
                try:
                    config = json.loads(config_json)
                except json.JSONDecodeError:
                    config = {}
                settings[name] = {
                    "category": category,
                    "config": config,
                    "enabled": bool(enabled),
                    "notify_on": notify_on,
                }
            self._settings_cache = settings
            self._cache_time = now
        except sqlite3.Error as e:
            logger.error(f"Failed to load notification settings: {e}")
        finally:
            conn.close()

        return settings

    def _should_notify(self, setting: Dict, severity: str) -> bool:
        """Check if notification should be sent based on severity filter."""
        notify_on = setting.get("notify_on", "all")
        if notify_on == "all":
            return True

        # Get severity index (lower = more severe)
        try:
            setting_idx = SEVERITY_LEVELS.index(notify_on)
            severity_idx = SEVERITY_LEVELS.index(severity)
            return severity_idx <= setting_idx
        except ValueError:
            return True  # Default to notify if unknown severity

    def notify(
        self,
        notification_type: str,
        title: str,
        message: str = None,
        source: str = None,
        severity: str = "error",
        metadata: Dict = None,
    ) -> Dict[str, Any]:
        """
        Send a notification through all enabled channels.

        Args:
            notification_type: Type of notification (service_failure, worker_down, etc.)
            title: Short title/subject
            message: Detailed message
            source: Source service/worker name
            severity: critical, error, warning, or info
            metadata: Additional context data

        Returns:
            Dict with notification results
        """
        if severity not in SEVERITY_LEVELS:
            severity = "error"

        notification = {
            "type": notification_type,
            "title": title,
            "message": message or "",
            "source": source or "unknown",
            "severity": severity,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }

        results = {"channels_notified": [], "webhook_responses": {}, "errors": []}

        settings = self._load_settings()

        for name, setting in settings.items():
            if not self._should_notify(setting, severity):
                continue

            category = setting["category"]
            config = setting["config"]

            try:
                if category == "log":
                    self._notify_log(notification, config)
                    results["channels_notified"].append(f"log:{name}")

                elif category == "webhook":
                    response = self._notify_webhook(notification, config)
                    results["webhook_responses"][name] = response
                    results["channels_notified"].append(f"webhook:{name}")

                elif category == "socket":
                    self._notify_socket(notification, config)
                    results["channels_notified"].append(f"socket:{name}")

            except Exception as e:
                error_msg = f"Failed to notify {name}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        # Always log to database
        self._log_to_database(notification, results)

        return results

    def _notify_log(self, notification: Dict, config: Dict):
        """Write notification to log file."""
        log_path = config.get("path", DEFAULT_LOG_PATH)
        log_format = config.get("format", "json")

        if log_format == "json":
            log_line = json.dumps(notification) + "\n"
        else:
            log_line = (
                f"[{notification['timestamp']}] "
                f"[{notification['severity'].upper()}] "
                f"[{notification['source']}] "
                f"{notification['title']}: {notification['message']}\n"
            )

        with open(log_path, "a") as f:
            f.write(log_line)

    def _notify_webhook(self, notification: Dict, config: Dict) -> Dict:
        """Send notification to webhook URL."""
        url = config.get("url")
        if not url:
            raise ValueError("Webhook URL not configured")

        headers = config.get("headers", {})
        headers.setdefault("Content-Type", "application/json")

        # Build payload based on webhook type
        webhook_type = config.get("type", "generic")

        if webhook_type == "slack":
            payload = self._format_slack_payload(notification, config)
        elif webhook_type == "discord":
            payload = self._format_discord_payload(notification, config)
        elif webhook_type == "teams":
            payload = self._format_teams_payload(notification, config)
        else:
            # Generic webhook - send full notification
            template = config.get("template")
            if template:
                payload = self._apply_template(template, notification)
            else:
                payload = notification

        # Send the request
        request = Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )

        try:
            with urlopen(request, timeout=10) as response:
                return {"status": response.status, "success": True}
        except HTTPError as e:
            return {"status": e.code, "success": False, "error": str(e)}
        except URLError as e:
            return {"status": None, "success": False, "error": str(e)}

    def _format_slack_payload(self, notification: Dict, config: Dict) -> Dict:
        """Format notification for Slack webhook."""
        severity_colors = {
            "critical": "#dc3545",
            "error": "#f85149",
            "warning": "#d29922",
            "info": "#58a6ff",
        }

        severity_emoji = {
            "critical": ":rotating_light:",
            "error": ":x:",
            "warning": ":warning:",
            "info": ":information_source:",
        }

        severity = notification["severity"]
        emoji = severity_emoji.get(severity, ":bell:")
        color = severity_colors.get(severity, "#30363d")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {notification['title']}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                    {"type": "mrkdwn", "text": f"*Source:*\n{notification['source']}"},
                ],
            },
        ]

        if notification["message"]:
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": notification["message"]}}
            )

        if notification.get("metadata"):
            metadata_text = "\n".join(f"• *{k}:* {v}" for k, v in notification["metadata"].items())
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Details:*\n{metadata_text}"},
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Architect Dashboard | {notification['timestamp']}"}
                ],
            }
        )

        return {"attachments": [{"color": color, "blocks": blocks}]}

    def _format_discord_payload(self, notification: Dict, config: Dict) -> Dict:
        """Format notification for Discord webhook."""
        severity_colors = {
            "critical": 0xDC3545,
            "error": 0xF85149,
            "warning": 0xD29922,
            "info": 0x58A6FF,
        }

        severity = notification["severity"]
        color = severity_colors.get(severity, 0x30363D)

        embed = {
            "title": notification["title"],
            "description": notification["message"] or "No details provided",
            "color": color,
            "fields": [
                {"name": "Severity", "value": severity.upper(), "inline": True},
                {"name": "Source", "value": notification["source"], "inline": True},
                {"name": "Type", "value": notification["type"], "inline": True},
            ],
            "footer": {"text": "Architect Dashboard"},
            "timestamp": notification["timestamp"],
        }

        if notification.get("metadata"):
            for key, value in list(notification["metadata"].items())[:5]:
                embed["fields"].append(
                    {"name": str(key), "value": str(value)[:1024], "inline": True}
                )

        return {"embeds": [embed]}

    def _format_teams_payload(self, notification: Dict, config: Dict) -> Dict:
        """Format notification for Microsoft Teams webhook."""
        severity_colors = {
            "critical": "attention",
            "error": "attention",
            "warning": "warning",
            "info": "good",
        }

        severity = notification["severity"]
        color = severity_colors.get(severity, "default")

        facts = [
            {"title": "Severity", "value": severity.upper()},
            {"title": "Source", "value": notification["source"]},
            {"title": "Type", "value": notification["type"]},
        ]

        if notification.get("metadata"):
            for key, value in list(notification["metadata"].items())[:5]:
                facts.append({"title": str(key), "value": str(value)})

        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": {"attention": "dc3545", "warning": "d29922", "good": "58a6ff"}.get(
                color, "30363d"
            ),
            "summary": notification["title"],
            "sections": [
                {
                    "activityTitle": notification["title"],
                    "activitySubtitle": notification["timestamp"],
                    "facts": facts,
                    "text": notification["message"] or "",
                }
            ],
        }

    def _apply_template(self, template: Dict, notification: Dict) -> Dict:
        """Apply a custom template to the notification."""

        def replace_vars(obj, data):
            if isinstance(obj, str):
                for key, value in data.items():
                    obj = obj.replace(f"{{{key}}}", str(value))
                    if isinstance(value, dict):
                        for k, v in value.items():
                            obj = obj.replace(f"{{{key}.{k}}}", str(v))
                return obj
            elif isinstance(obj, dict):
                return {k: replace_vars(v, data) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_vars(item, data) for item in obj]
            return obj

        return replace_vars(template, notification)

    def _notify_socket(self, notification: Dict, config: Dict):
        """Broadcast notification via WebSocket."""
        if not self._socketio:
            logger.warning("SocketIO not configured, skipping socket notification")
            return

        room = config.get("room", "notifications")
        event = config.get("event", "service_alert")

        self._socketio.emit(event, notification, room=room)

    def _log_to_database(self, notification: Dict, results: Dict):
        """Log the notification to the database."""
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            conn.execute(
                """
                INSERT INTO notification_log
                (notification_type, severity, title, message, source, metadata,
                 channels_notified, webhook_responses)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    notification["type"],
                    notification["severity"],
                    notification["title"],
                    notification["message"],
                    notification["source"],
                    json.dumps(notification.get("metadata", {})),
                    json.dumps(results.get("channels_notified", [])),
                    json.dumps(results.get("webhook_responses", {})),
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to log notification to database: {e}")
        finally:
            conn.close()

    def get_notification_log(
        self,
        limit: int = 50,
        offset: int = 0,
        severity: str = None,
        notification_type: str = None,
        source: str = None,
        acknowledged: bool = None,
    ) -> List[Dict]:
        """Retrieve notification log entries."""
        conn = self._get_db_connection()
        if not conn:
            return []

        try:
            query = "SELECT * FROM notification_log WHERE 1=1"
            params = []

            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if notification_type:
                query += " AND notification_type = ?"
                params.append(notification_type)
            if source:
                query += " AND source = ?"
                params.append(source)
            if acknowledged is not None:
                query += " AND acknowledged = ?"
                params.append(1 if acknowledged else 0)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)

            results = []
            for row in cursor.fetchall():
                entry = dict(row)
                # Parse JSON fields
                for field in ["metadata", "channels_notified", "webhook_responses"]:
                    if entry.get(field):
                        try:
                            entry[field] = json.loads(entry[field])
                        except json.JSONDecodeError:
                            pass
                results.append(entry)

            return results
        except sqlite3.Error as e:
            logger.error(f"Failed to get notification log: {e}")
            return []
        finally:
            conn.close()

    def acknowledge_notification(self, notification_id: int, acknowledged_by: str = None) -> bool:
        """Mark a notification as acknowledged."""
        conn = self._get_db_connection()
        if not conn:
            return False

        try:
            conn.execute(
                """
                UPDATE notification_log
                SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = ?
                WHERE id = ?
            """,
                (acknowledged_by, datetime.now().isoformat(), notification_id),
            )
            conn.commit()
            return conn.total_changes > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to acknowledge notification: {e}")
            return False
        finally:
            conn.close()

    def add_webhook(
        self,
        name: str,
        url: str,
        webhook_type: str = "generic",
        notify_on: str = "all",
        headers: Dict = None,
        template: Dict = None,
    ) -> bool:
        """Add a new webhook notification setting."""
        conn = self._get_db_connection()
        if not conn:
            return False

        config = {
            "url": url,
            "type": webhook_type,
            "headers": headers or {},
        }
        if template:
            config["template"] = template

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO notification_settings
                (name, category, config, enabled, notify_on, updated_at)
                VALUES (?, 'webhook', ?, 1, ?, CURRENT_TIMESTAMP)
            """,
                (name, json.dumps(config), notify_on),
            )
            conn.commit()
            self._settings_cache = {}  # Clear cache
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to add webhook: {e}")
            return False
        finally:
            conn.close()

    def remove_webhook(self, name: str) -> bool:
        """Remove a webhook notification setting."""
        conn = self._get_db_connection()
        if not conn:
            return False

        try:
            conn.execute(
                "DELETE FROM notification_settings WHERE name = ? AND category = 'webhook'", (name,)
            )
            conn.commit()
            self._settings_cache = {}
            return conn.total_changes > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to remove webhook: {e}")
            return False
        finally:
            conn.close()

    def test_webhook(self, name: str) -> Dict:
        """Send a test notification to a specific webhook."""
        settings = self._load_settings()
        if name not in settings:
            return {"success": False, "error": "Webhook not found"}

        setting = settings[name]
        if setting["category"] != "webhook":
            return {"success": False, "error": "Not a webhook setting"}

        test_notification = {
            "type": "test",
            "title": "Test Notification",
            "message": "This is a test notification from Architect Dashboard",
            "source": "notification_service",
            "severity": "info",
            "metadata": {"test": True},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            return self._notify_webhook(test_notification, setting["config"])
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global instance
_notification_service = None


def get_notification_service(db_path: str = None) -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService(db_path)
    elif db_path and _notification_service.db_path != db_path:
        _notification_service.set_db_path(db_path)
    return _notification_service


def notify_service_failure(
    title: str,
    message: str = None,
    source: str = None,
    severity: str = "error",
    metadata: Dict = None,
    db_path: str = None,
) -> Dict:
    """
    Convenience function to notify about a service failure.

    Args:
        title: Short description of the failure
        message: Detailed message
        source: Service/worker name that failed
        severity: critical, error, warning, or info
        metadata: Additional context
        db_path: Database path (optional, uses default if not provided)

    Returns:
        Dict with notification results
    """
    service = get_notification_service(db_path)
    return service.notify(
        notification_type="service_failure",
        title=title,
        message=message,
        source=source,
        severity=severity,
        metadata=metadata,
    )


def notify_worker_down(
    worker_name: str,
    worker_id: str = None,
    last_seen: str = None,
    error: str = None,
    db_path: str = None,
) -> Dict:
    """Notify about a worker going offline."""
    service = get_notification_service(db_path)
    return service.notify(
        notification_type="worker_down",
        title=f"Worker Offline: {worker_name}",
        message=error or f"Worker {worker_name} has stopped responding",
        source=worker_name,
        severity="error",
        metadata={"worker_id": worker_id, "last_seen": last_seen},
    )


def notify_health_alert(
    component: str, status: str, details: str = None, metrics: Dict = None, db_path: str = None
) -> Dict:
    """Notify about a health check failure."""
    severity = "critical" if status == "unhealthy" else "warning"
    service = get_notification_service(db_path)
    return service.notify(
        notification_type="health_alert",
        title=f"Health Alert: {component}",
        message=details or f"{component} is {status}",
        source="health_monitor",
        severity=severity,
        metadata=metrics or {},
    )


def notify_task_status(
    task_id: int,
    task_type: str,
    old_status: str,
    new_status: str,
    worker_id: str = None,
    session_name: str = None,
    result: str = None,
    error: str = None,
    task_data: Dict = None,
    db_path: str = None,
) -> Dict:
    """
    Notify about a task status change via webhooks.

    Args:
        task_id: The task ID
        task_type: Type of task (shell, git, deploy, etc.)
        old_status: Previous status (pending, running, etc.)
        new_status: New status (running, completed, failed, etc.)
        worker_id: ID of the worker processing the task
        session_name: Name of the session (if applicable)
        result: Task result (for completed tasks)
        error: Error message (for failed tasks)
        task_data: Additional task data
        db_path: Database path

    Returns:
        Dict with notification results
    """
    # Determine severity based on status
    severity_map = {
        "failed": "error",
        "completed": "info",
        "running": "info",
        "pending": "info",
        "timeout": "warning",
        "cancelled": "warning",
    }
    severity = severity_map.get(new_status, "info")

    # Build title based on status change
    status_emoji = {
        "pending": "clock",
        "running": "gear",
        "completed": "white_check_mark",
        "failed": "x",
        "timeout": "hourglass",
        "cancelled": "stop_sign",
    }

    title = f"Task #{task_id} {new_status.upper()}"
    if new_status == "completed":
        message = f"Task {task_id} ({task_type}) completed successfully"
    elif new_status == "failed":
        message = f"Task {task_id} ({task_type}) failed: {error or 'Unknown error'}"
    elif new_status == "running":
        message = f"Task {task_id} ({task_type}) started processing"
        if worker_id:
            message += f" by worker {worker_id}"
    else:
        message = f"Task {task_id} ({task_type}) status changed: {old_status} -> {new_status}"

    metadata = {
        "task_id": task_id,
        "task_type": task_type,
        "old_status": old_status,
        "new_status": new_status,
    }

    if worker_id:
        metadata["worker_id"] = worker_id
    if session_name:
        metadata["session_name"] = session_name
    if result:
        metadata["result"] = result[:500] if isinstance(result, str) else str(result)[:500]
    if error:
        metadata["error"] = error[:500] if isinstance(error, str) else str(error)[:500]
    if task_data:
        # Include limited task data
        for key in ["priority", "description", "command"]:
            if key in task_data:
                metadata[key] = str(task_data[key])[:200]

    service = get_notification_service(db_path)
    return service.notify(
        notification_type="task_status",
        title=title,
        message=message,
        source="task_queue",
        severity=severity,
        metadata=metadata,
    )


def trigger_task_webhook(
    task_id: int,
    task_type: str,
    new_status: str,
    old_status: str = None,
    worker_id: str = None,
    session_name: str = None,
    result: str = None,
    error: str = None,
    task_data: Dict = None,
    db_path: str = None,
):
    """
    Trigger task status webhook in background thread.

    This is a non-blocking wrapper around notify_task_status that runs
    in a background thread to avoid slowing down API responses.
    """

    def _notify():
        try:
            notify_task_status(
                task_id=task_id,
                task_type=task_type,
                old_status=old_status or "unknown",
                new_status=new_status,
                worker_id=worker_id,
                session_name=session_name,
                result=result,
                error=error,
                task_data=task_data,
                db_path=db_path,
            )
        except Exception as e:
            logger.warning(f"Failed to trigger task webhook for task {task_id}: {e}")

    thread = threading.Thread(target=_notify, daemon=True)
    thread.start()
