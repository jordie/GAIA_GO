"""
Recurring Tasks Module

Provides functions for managing recurring/scheduled tasks.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


def calculate_next_run(
    recurrence_type: str,
    interval: int = 1,
    days: str = None,
    run_time: str = "00:00",
    last_run: datetime = None,
    cron_expr: str = None,
) -> datetime:
    """
    Calculate the next run time for a recurring task.

    Args:
        recurrence_type: hourly, daily, weekly, monthly, or cron
        interval: Number of units between runs (default: 1)
        days: Comma-separated days for weekly (0=Mon, 6=Sun)
        run_time: Time to run in HH:MM format (default: 00:00)
        last_run: Last run timestamp (default: now)
        cron_expr: Cron expression for type=cron

    Returns:
        datetime of next scheduled run
    """
    now = datetime.now()
    base_time = last_run if last_run else now

    # Parse time
    try:
        hour, minute = map(int, run_time.split(":"))
    except:
        hour, minute = 0, 0

    if recurrence_type == "hourly":
        next_run = base_time + timedelta(hours=interval)
        next_run = next_run.replace(minute=minute, second=0, microsecond=0)
    elif recurrence_type == "daily":
        next_run = base_time + timedelta(days=interval)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
    elif recurrence_type == "weekly":
        next_run = base_time + timedelta(weeks=interval)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Adjust to specific days if provided
        if days:
            try:
                day_list = [int(d) for d in days.split(",")]  # 0=Mon, 6=Sun
                current_day = next_run.weekday()
                for d in sorted(day_list):
                    if d >= current_day:
                        next_run += timedelta(days=d - current_day)
                        break
            except:
                pass
    elif recurrence_type == "monthly":
        # Add months by incrementing month number
        month = base_time.month + interval
        year = base_time.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        day = min(base_time.day, 28)  # Safe day for all months
        next_run = base_time.replace(
            year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0
        )
    elif recurrence_type == "cron" and cron_expr:
        # Simple cron parsing (minute hour day month weekday)
        try:
            parts = cron_expr.split()
            if len(parts) >= 5:
                cron_min = int(parts[0]) if parts[0] != "*" else now.minute
                cron_hour = int(parts[1]) if parts[1] != "*" else now.hour
                next_run = now.replace(hour=cron_hour, minute=cron_min, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
            else:
                next_run = now + timedelta(hours=1)
        except:
            next_run = now + timedelta(hours=1)
    else:
        # Default to daily
        next_run = base_time + timedelta(days=1)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Ensure next_run is in the future
    while next_run <= now:
        if recurrence_type == "hourly":
            next_run += timedelta(hours=interval)
        elif recurrence_type == "daily":
            next_run += timedelta(days=interval)
        elif recurrence_type == "weekly":
            next_run += timedelta(weeks=interval)
        elif recurrence_type == "monthly":
            next_run += timedelta(days=30 * interval)
        else:
            next_run += timedelta(days=1)

    return next_run


def spawn_recurring_task(recurring_task: dict, conn, log_activity_fn=None) -> Optional[int]:
    """
    Create a task instance from a recurring task definition.

    Args:
        recurring_task: Dictionary with recurring task configuration
        conn: Database connection
        log_activity_fn: Optional function to log activity

    Returns:
        Task ID if spawned, None if max instances reached
    """
    # Check if max instances would be exceeded
    if recurring_task.get("max_instances", 1) > 0:
        active_count = conn.execute(
            """
            SELECT COUNT(*) as c FROM task_queue
            WHERE task_type = ? AND status IN ('pending', 'running')
            AND task_data LIKE ?
        """,
            (recurring_task["task_type"], f'%"recurring_task_id": {recurring_task["id"]}%'),
        ).fetchone()

        if hasattr(active_count, "__getitem__"):
            count = active_count["c"] if isinstance(active_count, dict) else active_count[0]
        else:
            count = 0

        if count >= recurring_task.get("max_instances", 1):
            return None

    # Create task data with recurring task reference
    task_data = json.loads(recurring_task.get("task_data") or "{}")
    task_data["recurring_task_id"] = recurring_task["id"]
    task_data["recurring_task_name"] = recurring_task.get("name", "")

    cursor = conn.execute(
        """
        INSERT INTO task_queue (task_type, task_data, priority, max_retries, timeout_seconds)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            recurring_task["task_type"],
            json.dumps(task_data),
            recurring_task.get("priority", 0),
            recurring_task.get("max_retries", 3),
            recurring_task.get("timeout_seconds"),
        ),
    )

    task_id = cursor.lastrowid

    # Calculate next run time
    next_run = calculate_next_run(
        recurring_task.get("recurrence_type", "daily"),
        recurring_task.get("recurrence_interval", 1),
        recurring_task.get("recurrence_days"),
        recurring_task.get("recurrence_time", "00:00"),
        datetime.now(),
        recurring_task.get("cron_expression"),
    )

    # Update recurring task record
    conn.execute(
        """
        UPDATE recurring_tasks SET
            last_run_at = CURRENT_TIMESTAMP,
            next_run_at = ?,
            last_task_id = ?,
            run_count = run_count + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (next_run.isoformat(), task_id, recurring_task["id"]),
    )

    return task_id


def check_due_recurring_tasks(conn, spawn_fn=None, log_activity_fn=None) -> dict:
    """
    Check all enabled recurring tasks and spawn any that are due.

    Args:
        conn: Database connection
        spawn_fn: Optional custom spawn function
        log_activity_fn: Optional function to log activity

    Returns:
        Dictionary with 'spawned' and 'errors' lists
    """
    import sqlite3

    spawned = []
    errors = []

    conn.row_factory = sqlite3.Row

    # Find tasks that are due
    due_tasks = conn.execute(
        """
        SELECT * FROM recurring_tasks
        WHERE enabled = 1 AND next_run_at <= datetime('now')
        ORDER BY next_run_at
    """
    ).fetchall()

    for task in due_tasks:
        try:
            task_dict = dict(task)
            if spawn_fn:
                spawned_id = spawn_fn(task_dict, conn, log_activity_fn)
            else:
                spawned_id = spawn_recurring_task(task_dict, conn, log_activity_fn)

            if spawned_id:
                spawned.append(
                    {
                        "recurring_task_id": task["id"],
                        "recurring_task_name": task["name"],
                        "spawned_task_id": spawned_id,
                    }
                )
        except Exception as e:
            errors.append({"recurring_task_id": task["id"], "error": str(e)})
            try:
                conn.execute(
                    """
                    UPDATE recurring_tasks SET failure_count = failure_count + 1 WHERE id = ?
                """,
                    (task["id"],),
                )
            except:
                pass

    return {"checked": len(due_tasks), "spawned": spawned, "errors": errors}
