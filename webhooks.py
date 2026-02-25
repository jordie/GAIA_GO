"""
Webhook Management Module for Task Events

Provides functions for managing webhooks that receive notifications
when task events occur (created, started, completed, failed, etc.).
"""

import hashlib
import hmac
import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Available task events that can trigger webhooks
TASK_EVENTS = {
    "task.created": "Triggered when a new task is created",
    "task.started": "Triggered when a task starts running",
    "task.completed": "Triggered when a task completes successfully",
    "task.failed": "Triggered when a task fails",
    "task.retrying": "Triggered when a task is being retried",
    "task.cancelled": "Triggered when a task is cancelled",
    "task.timeout": "Triggered when a task times out",
    "task.claimed": "Triggered when a worker claims a task",
    "task.priority_changed": "Triggered when task priority changes",
    "task.assigned": "Triggered when a task is assigned to a node",
}

# Map status changes to events
STATUS_TO_EVENT = {
    "pending": "task.created",
    "running": "task.started",
    "completed": "task.completed",
    "failed": "task.failed",
    "cancelled": "task.cancelled",
    "timeout": "task.timeout",
}


def get_webhooks(conn, enabled_only: bool = True) -> List[Dict]:
    """Get all webhooks for task events.

    Args:
        conn: Database connection
        enabled_only: If True, only return enabled webhooks

    Returns:
        List of webhook configurations
    """
    conn.row_factory = sqlite3.Row
    query = """
        SELECT id, name, url, secret, events, task_types, enabled,
               retry_count, timeout_seconds, created_at, updated_at
        FROM task_webhooks
    """
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY name"

    rows = conn.execute(query).fetchall()
    webhooks = []
    for row in rows:
        webhook = dict(row)
        webhook["events"] = json.loads(webhook["events"]) if webhook["events"] else []
        webhook["task_types"] = json.loads(webhook["task_types"]) if webhook["task_types"] else []
        # Mask the secret
        if webhook.get("secret"):
            webhook["has_secret"] = True
            webhook["secret"] = "***"
        else:
            webhook["has_secret"] = False
        webhooks.append(webhook)
    return webhooks


def get_webhook(conn, webhook_id: int) -> Optional[Dict]:
    """Get a specific webhook by ID."""
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM task_webhooks WHERE id = ?", (webhook_id,)).fetchone()

    if not row:
        return None

    webhook = dict(row)
    webhook["events"] = json.loads(webhook["events"]) if webhook["events"] else []
    webhook["task_types"] = json.loads(webhook["task_types"]) if webhook["task_types"] else []
    if webhook.get("secret"):
        webhook["has_secret"] = True
        webhook["secret"] = "***"
    return webhook


def create_webhook(
    conn,
    name: str,
    url: str,
    events: List[str] = None,
    task_types: List[str] = None,
    secret: str = None,
    enabled: bool = True,
    retry_count: int = 3,
    timeout_seconds: int = 10,
) -> int:
    """Create a new webhook.

    Args:
        conn: Database connection
        name: Webhook name
        url: Webhook URL to POST to
        events: List of events to subscribe to (default: all)
        task_types: List of task types to filter (default: all)
        secret: Secret for signing payloads (optional)
        enabled: Whether webhook is enabled
        retry_count: Number of retries on failure
        timeout_seconds: Request timeout

    Returns:
        ID of created webhook
    """
    if events is None:
        events = list(TASK_EVENTS.keys())

    # Validate events
    invalid_events = [e for e in events if e not in TASK_EVENTS]
    if invalid_events:
        raise ValueError(f"Invalid events: {invalid_events}")

    cursor = conn.execute(
        """
        INSERT INTO task_webhooks (name, url, secret, events, task_types, enabled, retry_count, timeout_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            name,
            url,
            secret,
            json.dumps(events),
            json.dumps(task_types or []),
            1 if enabled else 0,
            retry_count,
            timeout_seconds,
        ),
    )
    return cursor.lastrowid


def update_webhook(conn, webhook_id: int, **kwargs) -> bool:
    """Update a webhook.

    Args:
        conn: Database connection
        webhook_id: Webhook ID
        **kwargs: Fields to update (name, url, secret, events, task_types, enabled, etc.)

    Returns:
        True if updated, False if not found
    """
    updates = []
    params = []

    field_mapping = {
        "name": "name",
        "url": "url",
        "secret": "secret",
        "enabled": "enabled",
        "retry_count": "retry_count",
        "timeout_seconds": "timeout_seconds",
    }

    for key, column in field_mapping.items():
        if key in kwargs:
            updates.append(f"{column} = ?")
            value = kwargs[key]
            if key == "enabled":
                value = 1 if value else 0
            params.append(value)

    if "events" in kwargs:
        events = kwargs["events"]
        if events is not None:
            invalid = [e for e in events if e not in TASK_EVENTS]
            if invalid:
                raise ValueError(f"Invalid events: {invalid}")
        updates.append("events = ?")
        params.append(json.dumps(events) if events else None)

    if "task_types" in kwargs:
        updates.append("task_types = ?")
        params.append(json.dumps(kwargs["task_types"]) if kwargs["task_types"] else None)

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(webhook_id)

    result = conn.execute(f"UPDATE task_webhooks SET {', '.join(updates)} WHERE id = ?", params)
    return result.rowcount > 0


def delete_webhook(conn, webhook_id: int) -> bool:
    """Delete a webhook."""
    result = conn.execute("DELETE FROM task_webhooks WHERE id = ?", (webhook_id,))
    return result.rowcount > 0


def sign_payload(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature for payload."""
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def deliver_webhook(
    url: str, payload: Dict, secret: str = None, timeout: int = 10, headers: Dict = None
) -> Dict:
    """Deliver a webhook payload to a URL.

    Args:
        url: Webhook URL
        payload: Payload to send
        secret: Secret for signing (optional)
        timeout: Request timeout in seconds
        headers: Additional headers

    Returns:
        Dict with delivery result
    """
    payload_json = json.dumps(payload)
    request_headers = {
        "Content-Type": "application/json",
        "User-Agent": "Architect-Webhook/1.0",
        "X-Webhook-Event": payload.get("event", "unknown"),
        "X-Webhook-Timestamp": datetime.now().isoformat(),
    }

    if secret:
        signature = sign_payload(payload_json, secret)
        request_headers["X-Webhook-Signature"] = f"sha256={signature}"

    if headers:
        request_headers.update(headers)

    req = Request(url, data=payload_json.encode("utf-8"), headers=request_headers, method="POST")

    start_time = datetime.now()
    try:
        with urlopen(req, timeout=timeout) as response:
            duration = (datetime.now() - start_time).total_seconds()
            return {
                "success": True,
                "status_code": response.status,
                "duration_seconds": duration,
                "response_body": response.read().decode("utf-8")[:1000],
            }
    except HTTPError as e:
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "success": False,
            "status_code": e.code,
            "duration_seconds": duration,
            "error": str(e),
            "response_body": e.read().decode("utf-8")[:1000] if e.fp else None,
        }
    except URLError as e:
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "success": False,
            "status_code": None,
            "duration_seconds": duration,
            "error": str(e),
        }
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "success": False,
            "status_code": None,
            "duration_seconds": duration,
            "error": str(e),
        }


def log_delivery(
    conn, webhook_id: int, event: str, payload: Dict, result: Dict, task_id: int = None
):
    """Log a webhook delivery attempt."""
    conn.execute(
        """
        INSERT INTO webhook_deliveries
        (webhook_id, event, task_id, payload, status_code, success, duration_seconds, response_body, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            webhook_id,
            event,
            task_id,
            json.dumps(payload),
            result.get("status_code"),
            1 if result.get("success") else 0,
            result.get("duration_seconds"),
            result.get("response_body"),
            result.get("error"),
        ),
    )


def get_deliveries(
    conn,
    webhook_id: int = None,
    task_id: int = None,
    event: str = None,
    success: bool = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """Get webhook delivery history.

    Args:
        conn: Database connection
        webhook_id: Filter by webhook ID
        task_id: Filter by task ID
        event: Filter by event type
        success: Filter by success status
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of delivery records
    """
    conn.row_factory = sqlite3.Row
    query = """
        SELECT d.*, w.name as webhook_name, w.url as webhook_url
        FROM webhook_deliveries d
        LEFT JOIN task_webhooks w ON d.webhook_id = w.id
        WHERE 1=1
    """
    params = []

    if webhook_id is not None:
        query += " AND d.webhook_id = ?"
        params.append(webhook_id)
    if task_id is not None:
        query += " AND d.task_id = ?"
        params.append(task_id)
    if event:
        query += " AND d.event = ?"
        params.append(event)
    if success is not None:
        query += " AND d.success = ?"
        params.append(1 if success else 0)

    query += " ORDER BY d.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    deliveries = []
    for row in rows:
        delivery = dict(row)
        if delivery.get("payload"):
            try:
                delivery["payload"] = json.loads(delivery["payload"])
            except json.JSONDecodeError:
                pass
        deliveries.append(delivery)
    return deliveries


def trigger_task_event(
    db_path: str,
    task_id: int,
    event: str,
    task_type: str,
    task_data: Dict = None,
    old_status: str = None,
    new_status: str = None,
    worker_id: str = None,
    result: str = None,
    error: str = None,
):
    """Trigger webhooks for a task event.

    This runs in a background thread to avoid blocking.

    Args:
        db_path: Database path
        task_id: Task ID
        event: Event name (e.g., 'task.completed')
        task_type: Type of task
        task_data: Additional task data
        old_status: Previous status
        new_status: New status
        worker_id: Worker ID if applicable
        result: Task result for completed tasks
        error: Error message for failed tasks
    """

    def _trigger():
        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            # Get all enabled webhooks
            webhooks = conn.execute(
                """
                SELECT id, name, url, secret, events, task_types, retry_count, timeout_seconds
                FROM task_webhooks WHERE enabled = 1
            """
            ).fetchall()

            for webhook in webhooks:
                # Check if webhook subscribes to this event
                events = json.loads(webhook["events"]) if webhook["events"] else []
                if events and event not in events:
                    continue

                # Check if webhook filters by task type
                task_types = json.loads(webhook["task_types"]) if webhook["task_types"] else []
                if task_types and task_type not in task_types:
                    continue

                # Build payload
                payload = {
                    "event": event,
                    "timestamp": datetime.now().isoformat(),
                    "task": {
                        "id": task_id,
                        "type": task_type,
                        "status": new_status,
                        "previous_status": old_status,
                    },
                }

                if worker_id:
                    payload["task"]["worker_id"] = worker_id
                if result:
                    payload["task"]["result"] = (
                        result[:2000] if isinstance(result, str) else str(result)[:2000]
                    )
                if error:
                    payload["task"]["error"] = (
                        error[:2000] if isinstance(error, str) else str(error)[:2000]
                    )
                if task_data:
                    # Include safe task data fields
                    safe_fields = ["priority", "description", "max_retries", "timeout_seconds"]
                    payload["task"]["data"] = {
                        k: v for k, v in task_data.items() if k in safe_fields
                    }

                # Deliver with retries
                retry_count = webhook["retry_count"] or 3
                timeout = webhook["timeout_seconds"] or 10

                for attempt in range(retry_count):
                    delivery_result = deliver_webhook(
                        url=webhook["url"],
                        payload=payload,
                        secret=webhook["secret"],
                        timeout=timeout,
                    )

                    # Log delivery
                    log_delivery(conn, webhook["id"], event, payload, delivery_result, task_id)
                    conn.commit()

                    if delivery_result["success"]:
                        break

                    # Wait before retry (exponential backoff)
                    if attempt < retry_count - 1:
                        import time

                        time.sleep(2**attempt)

            conn.close()
        except Exception as e:
            logger.error(f"Failed to trigger webhooks for task {task_id}: {e}")

    thread = threading.Thread(target=_trigger, daemon=True)
    thread.start()


def test_webhook(conn, webhook_id: int) -> Dict:
    """Send a test event to a webhook.

    Args:
        conn: Database connection
        webhook_id: Webhook ID to test

    Returns:
        Delivery result
    """
    webhook = conn.execute(
        "SELECT url, secret, timeout_seconds FROM task_webhooks WHERE id = ?", (webhook_id,)
    ).fetchone()

    if not webhook:
        return {"success": False, "error": "Webhook not found"}

    payload = {
        "event": "test",
        "timestamp": datetime.now().isoformat(),
        "message": "This is a test webhook from Architect Dashboard",
        "task": {"id": 0, "type": "test", "status": "completed", "previous_status": "running"},
    }

    result = deliver_webhook(
        url=webhook["url"],
        payload=payload,
        secret=webhook["secret"],
        timeout=webhook["timeout_seconds"] or 10,
    )

    # Log the test delivery
    log_delivery(conn, webhook_id, "test", payload, result, None)

    return result
