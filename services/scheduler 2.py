"""
Scheduled Task Service with Cron Expression Support

Provides cron-based task scheduling with:
- Standard cron expression parsing (minute hour day month weekday)
- Extended syntax (@hourly, @daily, @weekly, @monthly)
- Next run time calculation
- Task execution via task queue
- Execution history tracking

Cron Expression Format:
    ┌───────────── minute (0-59)
    │ ┌───────────── hour (0-23)
    │ │ ┌───────────── day of month (1-31)
    │ │ │ ┌───────────── month (1-12)
    │ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
    │ │ │ │ │
    * * * * *

Special Characters:
    * - any value
    , - value list separator (1,3,5)
    - - range of values (1-5)
    / - step values (*/15 = every 15)

Predefined Schedules:
    @yearly    - 0 0 1 1 *
    @monthly   - 0 0 1 * *
    @weekly    - 0 0 * * 0
    @daily     - 0 0 * * *
    @hourly    - 0 * * * *
    @every_5m  - */5 * * * *
    @every_15m - */15 * * * *
    @every_30m - */30 * * * *

Usage:
    from services.scheduler import SchedulerService, CronExpression

    # Parse and validate cron expression
    cron = CronExpression('*/15 * * * *')
    next_run = cron.next_run()

    # Use scheduler service
    scheduler = SchedulerService(db_path)
    scheduler.create_scheduled_task(
        name='cleanup_logs',
        cron_expression='0 2 * * *',  # Daily at 2 AM
        task_type='shell',
        task_data={'command': 'rm -f /tmp/*.log'}
    )
"""

import json
import logging
import re
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add parent directory for imports
SERVICE_DIR = Path(__file__).parent
BASE_DIR = SERVICE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import ServiceConnectionPool

logger = logging.getLogger(__name__)


# Predefined cron schedules
PREDEFINED_SCHEDULES = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
    "@every_5m": "*/5 * * * *",
    "@every_10m": "*/10 * * * *",
    "@every_15m": "*/15 * * * *",
    "@every_30m": "*/30 * * * *",
}


class CronError(Exception):
    """Raised when cron expression parsing fails."""

    pass


@dataclass
class CronField:
    """Represents a single cron field with valid values."""

    name: str
    min_val: int
    max_val: int
    values: Set[int] = field(default_factory=set)

    def matches(self, value: int) -> bool:
        """Check if value matches this field."""
        return value in self.values

    def next_value(self, current: int) -> Tuple[int, bool]:
        """Get next matching value. Returns (value, wrapped)."""
        sorted_vals = sorted(self.values)
        for v in sorted_vals:
            if v >= current:
                return v, False
        # Wrap around to first value
        return sorted_vals[0], True


class CronExpression:
    """
    Parses and evaluates cron expressions.

    Supports standard 5-field cron format and predefined schedules.
    """

    def __init__(self, expression: str):
        self.original = expression.strip()
        self.expression = self._expand_predefined(self.original)
        self.fields = self._parse()

    def _expand_predefined(self, expr: str) -> str:
        """Expand predefined schedules like @daily."""
        if expr.startswith("@"):
            if expr.lower() in PREDEFINED_SCHEDULES:
                return PREDEFINED_SCHEDULES[expr.lower()]
            raise CronError(f"Unknown predefined schedule: {expr}")
        return expr

    def _parse(self) -> List[CronField]:
        """Parse cron expression into fields."""
        parts = self.expression.split()
        if len(parts) != 5:
            raise CronError(
                f"Invalid cron expression: expected 5 fields, got {len(parts)}. "
                f"Format: minute hour day month weekday"
            )

        field_specs = [
            ("minute", 0, 59),
            ("hour", 0, 23),
            ("day", 1, 31),
            ("month", 1, 12),
            ("weekday", 0, 6),
        ]

        fields = []
        for i, (name, min_val, max_val) in enumerate(field_specs):
            try:
                values = self._parse_field(parts[i], min_val, max_val)
                fields.append(CronField(name, min_val, max_val, values))
            except Exception as e:
                raise CronError(f"Invalid {name} field '{parts[i]}': {e}")

        return fields

    def _parse_field(self, field: str, min_val: int, max_val: int) -> Set[int]:
        """Parse a single cron field into set of values."""
        values = set()

        for part in field.split(","):
            part = part.strip()

            # Handle step values (*/5 or 1-10/2)
            step = 1
            if "/" in part:
                part, step_str = part.split("/", 1)
                step = int(step_str)
                if step < 1:
                    raise ValueError("Step must be >= 1")

            # Handle wildcards
            if part == "*":
                values.update(range(min_val, max_val + 1, step))
                continue

            # Handle ranges (1-5)
            if "-" in part:
                start, end = part.split("-", 1)
                start, end = int(start), int(end)
                if start < min_val or end > max_val or start > end:
                    raise ValueError(f"Range {start}-{end} out of bounds ({min_val}-{max_val})")
                values.update(range(start, end + 1, step))
                continue

            # Single value
            val = int(part)
            if val < min_val or val > max_val:
                raise ValueError(f"Value {val} out of bounds ({min_val}-{max_val})")
            values.add(val)

        return values

    def matches(self, dt: datetime) -> bool:
        """Check if datetime matches this cron expression."""
        # Convert Python weekday (Mon=0, Sun=6) to cron weekday (Sun=0, Sat=6)
        cron_weekday = (dt.weekday() + 1) % 7
        return (
            self.fields[0].matches(dt.minute)
            and self.fields[1].matches(dt.hour)
            and self.fields[2].matches(dt.day)
            and self.fields[3].matches(dt.month)
            and self.fields[4].matches(cron_weekday)
        )

    def next_run(
        self, from_dt: Optional[datetime] = None, max_iterations: int = 525600
    ) -> datetime:
        """
        Calculate next run time from given datetime.

        Args:
            from_dt: Starting datetime (default: now)
            max_iterations: Max minutes to search (prevent infinite loop)

        Returns:
            Next matching datetime
        """
        if from_dt is None:
            from_dt = datetime.now()

        # Start from next minute
        dt = from_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for _ in range(max_iterations):
            if self.matches(dt):
                return dt
            dt += timedelta(minutes=1)

        raise CronError(f"Could not find next run within {max_iterations} minutes")

    def next_runs(self, count: int = 5, from_dt: Optional[datetime] = None) -> List[datetime]:
        """Get next N run times."""
        runs = []
        current = from_dt or datetime.now()
        for _ in range(count):
            next_dt = self.next_run(current)
            runs.append(next_dt)
            current = next_dt
        return runs

    def __str__(self) -> str:
        return self.original

    def __repr__(self) -> str:
        return f"CronExpression('{self.original}')"


def validate_cron_expression(expression: str) -> Tuple[bool, str]:
    """
    Validate a cron expression.

    Returns:
        (is_valid, error_message)
    """
    try:
        cron = CronExpression(expression)
        # Try to get next run to ensure it's schedulable
        next_run = cron.next_run()
        return True, f"Valid. Next run: {next_run.strftime('%Y-%m-%d %H:%M')}"
    except CronError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


class SchedulerService:
    """
    Manages scheduled tasks with cron expressions.

    Handles CRUD operations for scheduled tasks and
    calculates next run times.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        # Use connection pooling for better performance
        self._pool = ServiceConnectionPool.get_or_create(
            db_path, min_connections=1, max_connections=3
        )

    def _get_connection(self):
        """Get database connection from pool."""
        return self._pool.connection()

    def create_scheduled_task(
        self,
        name: str,
        cron_expression: str,
        task_type: str,
        task_data: Optional[Dict] = None,
        description: str = "",
        priority: int = 0,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        enabled: bool = True,
        created_by: str = None,
    ) -> Dict:
        """
        Create a new scheduled task.

        Args:
            name: Unique task name
            cron_expression: Cron schedule (e.g., '*/15 * * * *')
            task_type: Type of task (shell, python, git, etc.)
            task_data: Task parameters as dict
            description: Human-readable description
            priority: Task priority (higher = more important)
            max_retries: Max retry attempts on failure
            timeout_seconds: Task timeout
            enabled: Whether task is active
            created_by: User who created the task

        Returns:
            Created task record
        """
        # Validate cron expression
        is_valid, error = validate_cron_expression(cron_expression)
        if not is_valid:
            raise CronError(f"Invalid cron expression: {error}")

        # Calculate next run
        cron = CronExpression(cron_expression)
        next_run = cron.next_run()

        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO scheduled_tasks
                    (name, description, cron_expression, task_type, task_data,
                     priority, max_retries, timeout_seconds, enabled, next_run_at, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        name,
                        description,
                        cron_expression,
                        task_type,
                        json.dumps(task_data) if task_data else None,
                        priority,
                        max_retries,
                        timeout_seconds,
                        enabled,
                        next_run.isoformat(),
                        created_by,
                    ),
                )
                conn.commit()

                task_id = cursor.lastrowid
                logger.info(f"Created scheduled task '{name}' (id={task_id}), next run: {next_run}")

                return self.get_scheduled_task(task_id)

            except sqlite3.IntegrityError:
                raise ValueError(f"Scheduled task with name '{name}' already exists")

    def get_scheduled_task(self, task_id: int) -> Optional[Dict]:
        """Get scheduled task by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def get_scheduled_task_by_name(self, name: str) -> Optional[Dict]:
        """Get scheduled task by name."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM scheduled_tasks WHERE name = ?", (name,)).fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def list_scheduled_tasks(
        self, enabled_only: bool = False, task_type: str = None, limit: int = 100
    ) -> List[Dict]:
        """List scheduled tasks."""
        query = "SELECT * FROM scheduled_tasks WHERE 1=1"
        params = []

        if enabled_only:
            query += " AND enabled = 1"
        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)

        query += " ORDER BY next_run_at ASC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def update_scheduled_task(self, task_id: int, **kwargs) -> Dict:
        """
        Update a scheduled task.

        Allowed fields: name, description, cron_expression, task_type,
        task_data, priority, max_retries, timeout_seconds, enabled
        """
        allowed_fields = {
            "name",
            "description",
            "cron_expression",
            "task_type",
            "task_data",
            "priority",
            "max_retries",
            "timeout_seconds",
            "enabled",
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            raise ValueError("No valid fields to update")

        # Validate cron if being updated
        if "cron_expression" in updates:
            is_valid, error = validate_cron_expression(updates["cron_expression"])
            if not is_valid:
                raise CronError(f"Invalid cron expression: {error}")

            # Recalculate next run
            cron = CronExpression(updates["cron_expression"])
            updates["next_run_at"] = cron.next_run().isoformat()

        # Serialize task_data if present
        if "task_data" in updates and updates["task_data"] is not None:
            updates["task_data"] = json.dumps(updates["task_data"])

        updates["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [task_id]

        with self._get_connection() as conn:
            conn.execute(f"UPDATE scheduled_tasks SET {set_clause} WHERE id = ?", values)
            conn.commit()

        logger.info(f"Updated scheduled task {task_id}: {list(updates.keys())}")
        return self.get_scheduled_task(task_id)

    def delete_scheduled_task(self, task_id: int) -> bool:
        """Delete a scheduled task."""
        with self._get_connection() as conn:
            result = conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted scheduled task {task_id}")
                return True
            return False

    def enable_task(self, task_id: int) -> Dict:
        """Enable a scheduled task."""
        return self.update_scheduled_task(task_id, enabled=True)

    def disable_task(self, task_id: int) -> Dict:
        """Disable a scheduled task."""
        return self.update_scheduled_task(task_id, enabled=False)

    def get_due_tasks(self) -> List[Dict]:
        """Get tasks that are due to run."""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scheduled_tasks
                WHERE enabled = 1 AND next_run_at <= ?
                ORDER BY priority DESC, next_run_at ASC
            """,
                (now,),
            ).fetchall()

            return [self._row_to_dict(row) for row in rows]

    def record_run(self, task_id: int, task_queue_id: int = None, status: str = "pending") -> int:
        """Record a task run in history."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scheduled_task_runs
                (scheduled_task_id, task_queue_id, status, started_at)
                VALUES (?, ?, ?, ?)
            """,
                (task_id, task_queue_id, status, datetime.now().isoformat()),
            )
            conn.commit()
            return cursor.lastrowid

    def complete_run(self, run_id: int, status: str, output: str = None, error_message: str = None):
        """Complete a task run record."""
        now = datetime.now()

        with self._get_connection() as conn:
            # Get start time to calculate duration
            row = conn.execute(
                "SELECT started_at FROM scheduled_task_runs WHERE id = ?", (run_id,)
            ).fetchone()

            duration_ms = None
            if row and row["started_at"]:
                start = datetime.fromisoformat(row["started_at"])
                duration_ms = int((now - start).total_seconds() * 1000)

            conn.execute(
                """
                UPDATE scheduled_task_runs
                SET status = ?, completed_at = ?, duration_ms = ?, output = ?, error_message = ?
                WHERE id = ?
            """,
                (status, now.isoformat(), duration_ms, output, error_message, run_id),
            )
            conn.commit()

    def update_task_after_run(self, task_id: int, status: str, duration_ms: int = None):
        """Update scheduled task after a run."""
        now = datetime.now()

        # Calculate next run
        task = self.get_scheduled_task(task_id)
        if not task:
            return

        cron = CronExpression(task["cron_expression"])
        next_run = cron.next_run(now)

        with self._get_connection() as conn:
            if status == "completed":
                conn.execute(
                    """
                    UPDATE scheduled_tasks
                    SET last_run_at = ?, last_run_status = ?, last_run_duration_ms = ?,
                        next_run_at = ?, run_count = run_count + 1, updated_at = ?
                    WHERE id = ?
                """,
                    (
                        now.isoformat(),
                        status,
                        duration_ms,
                        next_run.isoformat(),
                        now.isoformat(),
                        task_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE scheduled_tasks
                    SET last_run_at = ?, last_run_status = ?, last_run_duration_ms = ?,
                        next_run_at = ?, run_count = run_count + 1, error_count = error_count + 1,
                        updated_at = ?
                    WHERE id = ?
                """,
                    (
                        now.isoformat(),
                        status,
                        duration_ms,
                        next_run.isoformat(),
                        now.isoformat(),
                        task_id,
                    ),
                )
            conn.commit()

    def get_run_history(
        self, task_id: int = None, status: str = None, limit: int = 50
    ) -> List[Dict]:
        """Get task run history."""
        query = "SELECT * FROM scheduled_task_runs WHERE 1=1"
        params = []

        if task_id:
            query += " AND scheduled_task_id = ?"
            params.append(task_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict:
        """Get scheduler statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) as count FROM scheduled_tasks").fetchone()[
                "count"
            ]

            enabled = conn.execute(
                "SELECT COUNT(*) as count FROM scheduled_tasks WHERE enabled = 1"
            ).fetchone()["count"]

            due = conn.execute(
                "SELECT COUNT(*) as count FROM scheduled_tasks WHERE enabled = 1 AND next_run_at <= ?",
                (datetime.now().isoformat(),),
            ).fetchone()["count"]

            # Run stats from last 24 hours
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            runs_24h = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM scheduled_task_runs
                WHERE created_at >= ?
                GROUP BY status
            """,
                (yesterday,),
            ).fetchall()

            run_stats = {row["status"]: row["count"] for row in runs_24h}

            return {
                "total_tasks": total,
                "enabled_tasks": enabled,
                "disabled_tasks": total - enabled,
                "due_tasks": due,
                "runs_24h": run_stats,
                "total_runs_24h": sum(run_stats.values()),
            }

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert row to dict with parsed task_data."""
        d = dict(row)
        if d.get("task_data"):
            try:
                d["task_data"] = json.loads(d["task_data"])
            except json.JSONDecodeError:
                pass

        # Add next runs preview
        if d.get("cron_expression") and d.get("enabled"):
            try:
                cron = CronExpression(d["cron_expression"])
                d["next_runs"] = [dt.isoformat() for dt in cron.next_runs(3)]
            except CronError:
                d["next_runs"] = []

        return d


class SchedulerDaemon:
    """
    Background daemon that executes scheduled tasks.

    Polls for due tasks and creates queue entries for execution.
    """

    def __init__(self, db_path: str, poll_interval: int = 60):
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.service = SchedulerService(db_path)
        self._running = False
        self._thread = None
        # Use connection pooling
        self._pool = ServiceConnectionPool.get_or_create(
            db_path, min_connections=1, max_connections=3
        )

    def start(self):
        """Start the scheduler daemon."""
        if self._running:
            logger.warning("Scheduler daemon already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Scheduler daemon started (poll_interval={self.poll_interval}s)")

    def stop(self):
        """Stop the scheduler daemon."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Scheduler daemon stopped")

    def _run_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                self._process_due_tasks()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Sleep in small increments to allow quick shutdown
            for _ in range(self.poll_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _process_due_tasks(self):
        """Process all due scheduled tasks."""
        due_tasks = self.service.get_due_tasks()

        for task in due_tasks:
            try:
                self._execute_task(task)
            except Exception as e:
                logger.error(f"Failed to execute scheduled task {task['id']}: {e}")

    def _execute_task(self, task: Dict):
        """Execute a scheduled task by adding to queue."""
        logger.info(f"Executing scheduled task: {task['name']} (id={task['id']})")

        # Record the run
        run_id = self.service.record_run(task["id"], status="running")

        try:
            # Add to task queue using pooled connection
            with self._pool.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO task_queue
                    (task_type, task_data, priority, status)
                    VALUES (?, ?, ?, 'pending')
                """,
                    (
                        task["task_type"],
                        json.dumps(task["task_data"]) if task["task_data"] else None,
                        task["priority"],
                    ),
                )
                queue_id = cursor.lastrowid

                # Update run with queue ID
                conn.execute(
                    "UPDATE scheduled_task_runs SET task_queue_id = ? WHERE id = ?",
                    (queue_id, run_id),
                )

            # Update task for next run
            self.service.update_task_after_run(task["id"], "queued")

            logger.info(f"Scheduled task {task['name']} added to queue (queue_id={queue_id})")

        except Exception as e:
            self.service.complete_run(run_id, "failed", error_message=str(e))
            self.service.update_task_after_run(task["id"], "failed")
            raise


# Singleton instance for easy access
_scheduler_service: Optional[SchedulerService] = None
_scheduler_daemon: Optional[SchedulerDaemon] = None


def get_scheduler_service(db_path: str = None) -> SchedulerService:
    """Get or create scheduler service singleton."""
    global _scheduler_service
    if _scheduler_service is None:
        if db_path is None:
            raise ValueError("db_path required for first initialization")
        _scheduler_service = SchedulerService(db_path)
    return _scheduler_service


def get_scheduler_daemon(db_path: str = None, poll_interval: int = 60) -> SchedulerDaemon:
    """Get or create scheduler daemon singleton."""
    global _scheduler_daemon
    if _scheduler_daemon is None:
        if db_path is None:
            raise ValueError("db_path required for first initialization")
        _scheduler_daemon = SchedulerDaemon(db_path, poll_interval)
    return _scheduler_daemon
