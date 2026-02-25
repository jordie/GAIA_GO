"""
Batch Task Creation Module

Provides functions for creating multiple tasks from templates,
with support for variable substitution, scheduling, and batch tracking.
"""

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from string import Template
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Variable pattern for template substitution
VARIABLE_PATTERN = re.compile(r"\$\{(\w+)\}|\$(\w+)")


def get_template(conn, template_id: int) -> Optional[Dict]:
    """Get a task template by ID.

    Args:
        conn: Database connection
        template_id: Template ID

    Returns:
        Template dict or None
    """
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM task_templates WHERE id = ? AND is_active = 1", (template_id,)
    ).fetchone()

    if not row:
        return None

    template = dict(row)
    template["task_data_template"] = json.loads(template["task_data_template"] or "{}")
    return template


def get_template_by_name(conn, name: str) -> Optional[Dict]:
    """Get a task template by name.

    Args:
        conn: Database connection
        name: Template name

    Returns:
        Template dict or None
    """
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM task_templates WHERE name = ? AND is_active = 1", (name,)
    ).fetchone()

    if not row:
        return None

    template = dict(row)
    template["task_data_template"] = json.loads(template["task_data_template"] or "{}")
    return template


def list_templates(
    conn, category: str = None, task_type: str = None, active_only: bool = True
) -> List[Dict]:
    """List available task templates.

    Args:
        conn: Database connection
        category: Filter by category
        task_type: Filter by task type
        active_only: Only return active templates

    Returns:
        List of templates
    """
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM task_templates WHERE 1=1"
    params = []

    if active_only:
        query += " AND is_active = 1"

    if category:
        query += " AND category = ?"
        params.append(category)

    if task_type:
        query += " AND task_type = ?"
        params.append(task_type)

    query += " ORDER BY category, name"

    rows = conn.execute(query, params).fetchall()
    templates = []
    for row in rows:
        t = dict(row)
        t["task_data_template"] = json.loads(t["task_data_template"] or "{}")
        templates.append(t)

    return templates


def extract_variables(template_data: Dict) -> List[str]:
    """Extract variable names from a template.

    Args:
        template_data: Template data dictionary

    Returns:
        List of variable names
    """
    variables = set()

    def extract_from_value(value):
        if isinstance(value, str):
            matches = VARIABLE_PATTERN.findall(value)
            for match in matches:
                var_name = match[0] or match[1]
                variables.add(var_name)
        elif isinstance(value, dict):
            for v in value.values():
                extract_from_value(v)
        elif isinstance(value, list):
            for item in value:
                extract_from_value(item)

    extract_from_value(template_data)
    return sorted(list(variables))


def substitute_variables(template_data: Dict, variables: Dict) -> Dict:
    """Substitute variables in template data.

    Args:
        template_data: Template data with ${var} placeholders
        variables: Variable values to substitute

    Returns:
        Data with variables substituted
    """

    def substitute_value(value):
        if isinstance(value, str):
            # Use Template for safe substitution
            try:
                # Handle both ${var} and $var patterns
                result = value
                for var_name, var_value in variables.items():
                    result = result.replace(f"${{{var_name}}}", str(var_value))
                    result = result.replace(f"${var_name}", str(var_value))
                return result
            except Exception:
                return value
        elif isinstance(value, dict):
            return {k: substitute_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [substitute_value(item) for item in value]
        else:
            return value

    return substitute_value(template_data)


def create_task_from_template(
    conn,
    template_id: int,
    variables: Dict = None,
    priority_override: int = None,
    max_retries_override: int = None,
    timeout_override: int = None,
    scheduled_for: datetime = None,
    batch_id: str = None,
) -> Dict:
    """Create a single task from a template.

    Args:
        conn: Database connection
        template_id: Template ID
        variables: Variable values for substitution
        priority_override: Override default priority
        max_retries_override: Override default max retries
        timeout_override: Override default timeout
        scheduled_for: Schedule task for later
        batch_id: Batch ID for grouping

    Returns:
        Created task dict
    """
    template = get_template(conn, template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found or inactive")

    # Prepare task data
    task_data = template["task_data_template"].copy()
    if variables:
        task_data = substitute_variables(task_data, variables)

    # Add batch info to task data
    if batch_id:
        task_data["_batch_id"] = batch_id

    # Determine final values
    priority = priority_override if priority_override is not None else template["default_priority"]
    max_retries = (
        max_retries_override
        if max_retries_override is not None
        else template["default_max_retries"]
    )
    timeout = (
        timeout_override if timeout_override is not None else template["default_timeout_seconds"]
    )

    # Set status based on scheduling
    status = "scheduled" if scheduled_for else "pending"

    # Insert task
    cursor = conn.execute(
        """
        INSERT INTO task_queue
        (task_type, task_data, priority, status, max_retries, timeout_seconds, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            template["task_type"],
            json.dumps(task_data),
            priority,
            status,
            max_retries,
            timeout,
            scheduled_for.isoformat() if scheduled_for else datetime.now().isoformat(),
        ),
    )

    task_id = cursor.lastrowid

    # Update template usage count
    conn.execute(
        "UPDATE task_templates SET usage_count = usage_count + 1 WHERE id = ?", (template_id,)
    )

    return {
        "id": task_id,
        "task_type": template["task_type"],
        "template_id": template_id,
        "template_name": template["name"],
        "priority": priority,
        "status": status,
        "batch_id": batch_id,
        "variables": variables,
    }


def create_batch_from_template(
    conn,
    template_id: int,
    items: List[Dict],
    batch_name: str = None,
    batch_description: str = None,
    default_priority: int = None,
    stagger_seconds: int = 0,
    created_by: str = None,
) -> Dict:
    """Create multiple tasks from a template.

    Args:
        conn: Database connection
        template_id: Template ID
        items: List of variable dicts for each task
        batch_name: Name for this batch
        batch_description: Description
        default_priority: Default priority for all tasks
        stagger_seconds: Seconds between each task start
        created_by: User creating the batch

    Returns:
        Batch creation result
    """
    template = get_template(conn, template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found or inactive")

    # Generate batch ID
    batch_id = str(uuid.uuid4())[:8]

    # Create batch record
    cursor = conn.execute(
        """
        INSERT INTO task_batches
        (batch_id, name, description, template_id, total_tasks, status, created_by)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """,
        (
            batch_id,
            batch_name or f"Batch from {template['name']}",
            batch_description,
            template_id,
            len(items),
            created_by,
        ),
    )

    # Create tasks
    created_tasks = []
    failed_items = []
    scheduled_time = None

    for i, item in enumerate(items):
        try:
            # Calculate scheduled time if staggering
            if stagger_seconds > 0:
                scheduled_time = datetime.now() + timedelta(seconds=stagger_seconds * i)

            # Get item-specific overrides
            variables = item.get("variables", item)
            priority = item.get("priority", default_priority)
            max_retries = item.get("max_retries")
            timeout = item.get("timeout_seconds")

            task = create_task_from_template(
                conn,
                template_id=template_id,
                variables=variables,
                priority_override=priority,
                max_retries_override=max_retries,
                timeout_override=timeout,
                scheduled_for=scheduled_time,
                batch_id=batch_id,
            )
            created_tasks.append(task)

        except Exception as e:
            failed_items.append({"index": i, "item": item, "error": str(e)})

    # Update batch status
    status = "created" if not failed_items else "partial" if created_tasks else "failed"
    conn.execute(
        """
        UPDATE task_batches
        SET status = ?, created_count = ?, failed_count = ?
        WHERE batch_id = ?
    """,
        (status, len(created_tasks), len(failed_items), batch_id),
    )

    return {
        "batch_id": batch_id,
        "template_id": template_id,
        "template_name": template["name"],
        "total_requested": len(items),
        "created_count": len(created_tasks),
        "failed_count": len(failed_items),
        "status": status,
        "tasks": created_tasks,
        "failed": failed_items,
        "stagger_seconds": stagger_seconds,
    }


def get_batch(conn, batch_id: str) -> Optional[Dict]:
    """Get batch information.

    Args:
        conn: Database connection
        batch_id: Batch ID

    Returns:
        Batch info dict
    """
    conn.row_factory = sqlite3.Row

    row = conn.execute("SELECT * FROM task_batches WHERE batch_id = ?", (batch_id,)).fetchone()

    if not row:
        return None

    batch = dict(row)

    # Get task status counts
    stats = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM task_queue
        WHERE task_data LIKE ?
        GROUP BY status
    """,
        (f'%"_batch_id": "{batch_id}"%',),
    ).fetchall()

    batch["task_stats"] = {row["status"]: row["count"] for row in stats}

    return batch


def list_batches(
    conn, status: str = None, template_id: int = None, created_by: str = None, limit: int = 50
) -> List[Dict]:
    """List task batches.

    Args:
        conn: Database connection
        status: Filter by status
        template_id: Filter by template
        created_by: Filter by creator
        limit: Maximum results

    Returns:
        List of batches
    """
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM task_batches WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if template_id:
        query += " AND template_id = ?"
        params.append(template_id)

    if created_by:
        query += " AND created_by = ?"
        params.append(created_by)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_batch_tasks(conn, batch_id: str) -> List[Dict]:
    """Get all tasks in a batch.

    Args:
        conn: Database connection
        batch_id: Batch ID

    Returns:
        List of tasks
    """
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT * FROM task_queue
        WHERE task_data LIKE ?
        ORDER BY id
    """,
        (f'%"_batch_id": "{batch_id}"%',),
    ).fetchall()

    tasks = []
    for row in rows:
        task = dict(row)
        task["task_data"] = json.loads(task["task_data"] or "{}")
        tasks.append(task)

    return tasks


def cancel_batch(conn, batch_id: str) -> Dict:
    """Cancel all pending tasks in a batch.

    Args:
        conn: Database connection
        batch_id: Batch ID

    Returns:
        Cancellation result
    """
    # Cancel pending and scheduled tasks
    result = conn.execute(
        """
        UPDATE task_queue
        SET status = 'cancelled'
        WHERE task_data LIKE ?
        AND status IN ('pending', 'scheduled')
    """,
        (f'%"_batch_id": "{batch_id}"%',),
    )

    cancelled_count = result.rowcount

    # Update batch status
    conn.execute(
        """
        UPDATE task_batches
        SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
        WHERE batch_id = ?
    """,
        (batch_id,),
    )

    return {"batch_id": batch_id, "cancelled_count": cancelled_count, "status": "cancelled"}


def retry_failed_batch_tasks(conn, batch_id: str) -> Dict:
    """Retry all failed tasks in a batch.

    Args:
        conn: Database connection
        batch_id: Batch ID

    Returns:
        Retry result
    """
    # Reset failed tasks to pending
    result = conn.execute(
        """
        UPDATE task_queue
        SET status = 'pending', error_message = NULL, retries = 0
        WHERE task_data LIKE ?
        AND status = 'failed'
    """,
        (f'%"_batch_id": "{batch_id}"%',),
    )

    retried_count = result.rowcount

    # Update batch status
    if retried_count > 0:
        conn.execute(
            """
            UPDATE task_batches
            SET status = 'retrying', updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = ?
        """,
            (batch_id,),
        )

    return {"batch_id": batch_id, "retried_count": retried_count}


def create_template(
    conn,
    name: str,
    task_type: str,
    task_data_template: Dict,
    description: str = None,
    default_priority: int = 0,
    default_max_retries: int = 3,
    default_timeout_seconds: int = None,
    category: str = "general",
    icon: str = None,
    created_by: int = None,
) -> int:
    """Create a new task template.

    Args:
        conn: Database connection
        name: Template name
        task_type: Type of task
        task_data_template: Template data with variables
        description: Template description
        default_priority: Default priority
        default_max_retries: Default max retries
        default_timeout_seconds: Default timeout
        category: Template category
        icon: Icon identifier
        created_by: Creating user ID

    Returns:
        Created template ID
    """
    cursor = conn.execute(
        """
        INSERT INTO task_templates
        (name, description, task_type, task_data_template, default_priority,
         default_max_retries, default_timeout_seconds, category, icon, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            name,
            description,
            task_type,
            json.dumps(task_data_template),
            default_priority,
            default_max_retries,
            default_timeout_seconds,
            category,
            icon,
            created_by,
        ),
    )

    return cursor.lastrowid


def update_template(conn, template_id: int, **kwargs) -> bool:
    """Update a task template.

    Args:
        conn: Database connection
        template_id: Template ID
        **kwargs: Fields to update

    Returns:
        True if updated
    """
    updates = []
    params = []

    field_mapping = {
        "name": "name",
        "description": "description",
        "task_type": "task_type",
        "default_priority": "default_priority",
        "default_max_retries": "default_max_retries",
        "default_timeout_seconds": "default_timeout_seconds",
        "category": "category",
        "icon": "icon",
        "is_active": "is_active",
    }

    for key, column in field_mapping.items():
        if key in kwargs:
            updates.append(f"{column} = ?")
            params.append(kwargs[key])

    if "task_data_template" in kwargs:
        updates.append("task_data_template = ?")
        params.append(json.dumps(kwargs["task_data_template"]))

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(template_id)

    result = conn.execute(f"UPDATE task_templates SET {', '.join(updates)} WHERE id = ?", params)

    return result.rowcount > 0


def delete_template(conn, template_id: int, hard_delete: bool = False) -> bool:
    """Delete or deactivate a template.

    Args:
        conn: Database connection
        template_id: Template ID
        hard_delete: If True, permanently delete

    Returns:
        True if deleted/deactivated
    """
    if hard_delete:
        result = conn.execute("DELETE FROM task_templates WHERE id = ?", (template_id,))
    else:
        result = conn.execute(
            "UPDATE task_templates SET is_active = 0 WHERE id = ?", (template_id,)
        )

    return result.rowcount > 0


def get_template_stats(conn, template_id: int) -> Dict:
    """Get usage statistics for a template.

    Args:
        conn: Database connection
        template_id: Template ID

    Returns:
        Statistics dict
    """
    conn.row_factory = sqlite3.Row

    template = get_template(conn, template_id)
    if not template:
        return None

    # Count tasks by status
    stats = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM task_queue
        WHERE task_type = ?
        GROUP BY status
    """,
        (template["task_type"],),
    ).fetchall()

    status_counts = {row["status"]: row["count"] for row in stats}

    # Get batch count
    batch_count = conn.execute(
        """
        SELECT COUNT(*) as count FROM task_batches WHERE template_id = ?
    """,
        (template_id,),
    ).fetchone()["count"]

    return {
        "template_id": template_id,
        "template_name": template["name"],
        "usage_count": template["usage_count"],
        "batch_count": batch_count,
        "task_status_counts": status_counts,
        "total_tasks": sum(status_counts.values()),
    }
