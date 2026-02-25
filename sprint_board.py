"""
Sprint Planning Board Module
Manage sprints and provide board view for task planning
"""

import json
from datetime import datetime, timedelta

# Sprint statuses
SPRINT_STATUSES = ["planning", "active", "completed", "cancelled"]

# Default board columns
DEFAULT_COLUMNS = [
    {"id": "backlog", "name": "Backlog", "order": 1, "wip_limit": None},
    {"id": "todo", "name": "To Do", "order": 2, "wip_limit": None},
    {"id": "in_progress", "name": "In Progress", "order": 3, "wip_limit": 5},
    {"id": "review", "name": "Review", "order": 4, "wip_limit": 3},
    {"id": "done", "name": "Done", "order": 5, "wip_limit": None},
]

# Status to column mapping
STATUS_TO_COLUMN = {
    "pending": "todo",
    "queued": "todo",
    "in_progress": "in_progress",
    "running": "in_progress",
    "review": "review",
    "testing": "review",
    "completed": "done",
    "done": "done",
    "closed": "done",
    "cancelled": "done",
    "failed": "done",
}


def create_sprint(
    conn, name, project_id, start_date, end_date, goal=None, capacity_hours=None, created_by=None
):
    """Create a new sprint."""
    cursor = conn.cursor()

    # Validate project exists
    cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cursor.fetchone():
        return {"error": "Project not found"}

    # Check for overlapping active sprints
    cursor.execute(
        """
        SELECT id, name FROM sprints
        WHERE project_id = ? AND status = 'active'
          AND ((start_date <= ? AND end_date >= ?) OR (start_date <= ? AND end_date >= ?))
    """,
        (project_id, end_date, start_date, start_date, end_date),
    )

    overlap = cursor.fetchone()
    if overlap:
        return {"error": f'Overlaps with active sprint: {overlap["name"]}'}

    cursor.execute(
        """
        INSERT INTO sprints (name, project_id, start_date, end_date, goal,
                            capacity_hours, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, 'planning', ?)
    """,
        (name, project_id, start_date, end_date, goal, capacity_hours, created_by),
    )

    sprint_id = cursor.lastrowid
    conn.commit()

    return {
        "id": sprint_id,
        "name": name,
        "project_id": project_id,
        "start_date": start_date,
        "end_date": end_date,
        "status": "planning",
    }


def get_sprint(conn, sprint_id):
    """Get sprint details."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.*, p.name as project_name
        FROM sprints s
        JOIN projects p ON s.project_id = p.id
        WHERE s.id = ?
    """,
        (sprint_id,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    sprint = dict(row)

    # Get task counts
    cursor.execute(
        """
        SELECT status, COUNT(*) as count
        FROM task_queue
        WHERE sprint_id = ?
        GROUP BY status
    """,
        (sprint_id,),
    )

    sprint["task_counts"] = {row["status"]: row["count"] for row in cursor.fetchall()}
    sprint["total_tasks"] = sum(sprint["task_counts"].values())

    # Get effort totals
    cursor.execute(
        """
        SELECT SUM(estimated_hours) as estimated,
               SUM(actual_hours) as actual
        FROM task_queue
        WHERE sprint_id = ?
    """,
        (sprint_id,),
    )

    effort = cursor.fetchone()
    sprint["estimated_hours"] = effort["estimated"] or 0
    sprint["actual_hours"] = effort["actual"] or 0

    return sprint


def list_sprints(conn, project_id=None, status=None, limit=20):
    """List sprints with optional filters."""
    cursor = conn.cursor()

    query = """
        SELECT s.*, p.name as project_name
        FROM sprints s
        JOIN projects p ON s.project_id = p.id
        WHERE 1=1
    """
    params = []

    if project_id:
        query += " AND s.project_id = ?"
        params.append(project_id)

    if status:
        query += " AND s.status = ?"
        params.append(status)

    query += " ORDER BY s.start_date DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    sprints = [dict(row) for row in cursor.fetchall()]

    return {"sprints": sprints, "count": len(sprints)}


def update_sprint(conn, sprint_id, updates):
    """Update sprint details."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM sprints WHERE id = ?", (sprint_id,))
    if not cursor.fetchone():
        return {"error": "Sprint not found"}

    allowed_fields = ["name", "start_date", "end_date", "goal", "capacity_hours", "status"]

    set_clauses = []
    params = []

    for field in allowed_fields:
        if field in updates:
            value = updates[field]
            if field == "status" and value not in SPRINT_STATUSES:
                return {"error": f"Invalid status: {value}"}
            set_clauses.append(f"{field} = ?")
            params.append(value)

    if not set_clauses:
        return {"error": "No valid fields to update"}

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(sprint_id)

    query = f'UPDATE sprints SET {", ".join(set_clauses)} WHERE id = ?'
    cursor.execute(query, params)
    conn.commit()

    return get_sprint(conn, sprint_id)


def delete_sprint(conn, sprint_id):
    """Delete a sprint (unassigns tasks, doesn't delete them)."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM sprints WHERE id = ?", (sprint_id,))
    if not cursor.fetchone():
        return {"error": "Sprint not found"}

    # Unassign tasks from sprint
    cursor.execute("UPDATE task_queue SET sprint_id = NULL WHERE sprint_id = ?", (sprint_id,))

    # Delete sprint
    cursor.execute("DELETE FROM sprints WHERE id = ?", (sprint_id,))
    conn.commit()

    return {"success": True, "deleted_id": sprint_id}


def start_sprint(conn, sprint_id):
    """Start a sprint (set status to active)."""
    cursor = conn.cursor()

    cursor.execute("SELECT project_id, status FROM sprints WHERE id = ?", (sprint_id,))
    sprint = cursor.fetchone()

    if not sprint:
        return {"error": "Sprint not found"}

    if sprint["status"] == "active":
        return {"error": "Sprint is already active"}

    if sprint["status"] in ("completed", "cancelled"):
        return {"error": "Cannot start a completed or cancelled sprint"}

    # Check for other active sprints in the project
    cursor.execute(
        """
        SELECT id, name FROM sprints
        WHERE project_id = ? AND status = 'active' AND id != ?
    """,
        (sprint["project_id"], sprint_id),
    )

    other_active = cursor.fetchone()
    if other_active:
        return {"error": f'Another sprint is active: {other_active["name"]}'}

    cursor.execute(
        """
        UPDATE sprints SET status = 'active', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (sprint_id,),
    )
    conn.commit()

    return get_sprint(conn, sprint_id)


def complete_sprint(conn, sprint_id, move_incomplete_to=None):
    """Complete a sprint, optionally moving incomplete tasks."""
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM sprints WHERE id = ?", (sprint_id,))
    sprint = cursor.fetchone()

    if not sprint:
        return {"error": "Sprint not found"}

    if sprint["status"] != "active":
        return {"error": "Can only complete an active sprint"}

    # Get incomplete tasks
    cursor.execute(
        """
        SELECT id FROM task_queue
        WHERE sprint_id = ? AND status NOT IN ('completed', 'done', 'closed', 'cancelled')
    """,
        (sprint_id,),
    )

    incomplete_tasks = [row["id"] for row in cursor.fetchall()]

    # Move incomplete tasks if target sprint specified
    if move_incomplete_to and incomplete_tasks:
        cursor.execute("SELECT id FROM sprints WHERE id = ?", (move_incomplete_to,))
        if not cursor.fetchone():
            return {"error": "Target sprint not found"}

        cursor.execute(
            """
            UPDATE task_queue SET sprint_id = ?
            WHERE id IN ({})
        """.format(
                ",".join(["?" for _ in incomplete_tasks])
            ),
            [move_incomplete_to] + incomplete_tasks,
        )

    # Complete the sprint
    cursor.execute(
        """
        UPDATE sprints SET status = 'completed', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (sprint_id,),
    )
    conn.commit()

    return {
        "sprint_id": sprint_id,
        "status": "completed",
        "incomplete_tasks": len(incomplete_tasks),
        "moved_to": move_incomplete_to,
    }


def add_task_to_sprint(conn, sprint_id, task_id):
    """Add a task to a sprint."""
    cursor = conn.cursor()

    cursor.execute("SELECT id, status FROM sprints WHERE id = ?", (sprint_id,))
    sprint = cursor.fetchone()
    if not sprint:
        return {"error": "Sprint not found"}

    if sprint["status"] in ("completed", "cancelled"):
        return {"error": "Cannot add tasks to a completed or cancelled sprint"}

    cursor.execute("SELECT id, title FROM task_queue WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        return {"error": "Task not found"}

    cursor.execute("UPDATE task_queue SET sprint_id = ? WHERE id = ?", (sprint_id, task_id))
    conn.commit()

    return {
        "success": True,
        "sprint_id": sprint_id,
        "task_id": task_id,
        "task_title": task["title"],
    }


def remove_task_from_sprint(conn, task_id):
    """Remove a task from its sprint."""
    cursor = conn.cursor()

    cursor.execute("SELECT sprint_id FROM task_queue WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        return {"error": "Task not found"}

    if not task["sprint_id"]:
        return {"error": "Task is not in a sprint"}

    cursor.execute("UPDATE task_queue SET sprint_id = NULL WHERE id = ?", (task_id,))
    conn.commit()

    return {"success": True, "task_id": task_id, "removed_from_sprint": task["sprint_id"]}


def get_board_view(conn, sprint_id, columns=None):
    """Get sprint board view with tasks organized by columns."""
    cursor = conn.cursor()

    sprint = get_sprint(conn, sprint_id)
    if not sprint:
        return {"error": "Sprint not found"}

    # Use default columns if not specified
    board_columns = columns or DEFAULT_COLUMNS

    # Get all tasks in sprint
    cursor.execute(
        """
        SELECT t.*, p.name as project_name
        FROM task_queue t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.sprint_id = ?
        ORDER BY t.priority DESC, t.id
    """,
        (sprint_id,),
    )

    tasks = [dict(row) for row in cursor.fetchall()]

    # Organize tasks into columns
    board = {col["id"]: {"column": col, "tasks": [], "count": 0} for col in board_columns}

    for task in tasks:
        status = task["status"]
        column_id = STATUS_TO_COLUMN.get(status, "backlog")

        if column_id in board:
            board[column_id]["tasks"].append(task)
            board[column_id]["count"] += 1

    # Check WIP limits
    for col_id, col_data in board.items():
        wip_limit = col_data["column"].get("wip_limit")
        if wip_limit:
            col_data["over_wip"] = col_data["count"] > wip_limit

    return {"sprint": sprint, "columns": list(board.values()), "total_tasks": len(tasks)}


def get_backlog(conn, project_id, exclude_sprint_tasks=True):
    """Get project backlog (tasks not in any sprint)."""
    cursor = conn.cursor()

    query = """
        SELECT t.*, p.name as project_name
        FROM task_queue t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.project_id = ?
          AND t.status NOT IN ('completed', 'done', 'closed', 'cancelled')
    """
    params = [project_id]

    if exclude_sprint_tasks:
        query += " AND t.sprint_id IS NULL"

    query += " ORDER BY t.priority DESC, t.created_at"

    cursor.execute(query, params)
    tasks = [dict(row) for row in cursor.fetchall()]

    # Calculate totals
    total_estimated = sum(t["estimated_hours"] or 0 for t in tasks)

    return {
        "project_id": project_id,
        "tasks": tasks,
        "count": len(tasks),
        "total_estimated_hours": total_estimated,
    }


def move_task_on_board(conn, task_id, target_column, position=None):
    """Move a task to a different column on the board."""
    cursor = conn.cursor()

    cursor.execute("SELECT id, status, sprint_id FROM task_queue WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        return {"error": "Task not found"}

    # Map column to status
    column_to_status = {
        "backlog": "pending",
        "todo": "pending",
        "in_progress": "in_progress",
        "review": "review",
        "done": "completed",
    }

    new_status = column_to_status.get(target_column)
    if not new_status:
        return {"error": f"Invalid column: {target_column}"}

    cursor.execute(
        """
        UPDATE task_queue SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (new_status, task_id),
    )
    conn.commit()

    return {"task_id": task_id, "new_column": target_column, "new_status": new_status}


def get_sprint_burndown(conn, sprint_id):
    """Get burndown chart data for a sprint."""
    cursor = conn.cursor()

    sprint = get_sprint(conn, sprint_id)
    if not sprint:
        return {"error": "Sprint not found"}

    start_date = datetime.strptime(sprint["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(sprint["end_date"], "%Y-%m-%d")
    total_days = (end_date - start_date).days + 1

    # Get total story points/hours at sprint start
    total_effort = sprint["estimated_hours"] or 0

    # Calculate ideal burndown
    ideal_burndown = []
    daily_burn = total_effort / total_days if total_days > 0 else 0

    for day in range(total_days + 1):
        date = start_date + timedelta(days=day)
        ideal_burndown.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "remaining": round(total_effort - (daily_burn * day), 2),
            }
        )

    # Get actual burndown from task completions
    cursor.execute(
        """
        SELECT DATE(updated_at) as date, SUM(estimated_hours) as completed
        FROM task_queue
        WHERE sprint_id = ? AND status IN ('completed', 'done', 'closed')
        GROUP BY DATE(updated_at)
        ORDER BY date
    """,
        (sprint_id,),
    )

    completions = {row["date"]: row["completed"] or 0 for row in cursor.fetchall()}

    actual_burndown = []
    remaining = total_effort
    current_date = start_date

    while current_date <= min(end_date, datetime.now()):
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str in completions:
            remaining -= completions[date_str]

        actual_burndown.append({"date": date_str, "remaining": round(remaining, 2)})
        current_date += timedelta(days=1)

    return {
        "sprint": {
            "id": sprint_id,
            "name": sprint["name"],
            "start_date": sprint["start_date"],
            "end_date": sprint["end_date"],
        },
        "total_effort": total_effort,
        "ideal_burndown": ideal_burndown,
        "actual_burndown": actual_burndown,
    }


def get_sprint_velocity(conn, project_id, num_sprints=5):
    """Get velocity data for recent sprints."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT s.id, s.name, s.start_date, s.end_date,
               SUM(CASE WHEN t.status IN ('completed', 'done', 'closed') THEN t.estimated_hours ELSE 0 END) as completed_hours,
               SUM(t.estimated_hours) as planned_hours,
               COUNT(CASE WHEN t.status IN ('completed', 'done', 'closed') THEN 1 END) as completed_tasks,
               COUNT(t.id) as total_tasks
        FROM sprints s
        LEFT JOIN task_queue t ON t.sprint_id = s.id
        WHERE s.project_id = ? AND s.status = 'completed'
        GROUP BY s.id
        ORDER BY s.end_date DESC
        LIMIT ?
    """,
        (project_id, num_sprints),
    )

    sprints = [dict(row) for row in cursor.fetchall()]

    if not sprints:
        return {"project_id": project_id, "sprints": [], "average_velocity": 0}

    # Calculate average velocity
    avg_velocity = sum(s["completed_hours"] or 0 for s in sprints) / len(sprints)

    return {
        "project_id": project_id,
        "sprints": sprints,
        "average_velocity": round(avg_velocity, 2),
        "sprint_count": len(sprints),
    }


def get_active_sprint(conn, project_id):
    """Get the currently active sprint for a project."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM sprints
        WHERE project_id = ? AND status = 'active'
        ORDER BY start_date DESC
        LIMIT 1
    """,
        (project_id,),
    )

    row = cursor.fetchone()
    if row:
        return get_sprint(conn, row["id"])
    return None


def bulk_add_tasks_to_sprint(conn, sprint_id, task_ids):
    """Add multiple tasks to a sprint."""
    cursor = conn.cursor()

    cursor.execute("SELECT id, status FROM sprints WHERE id = ?", (sprint_id,))
    sprint = cursor.fetchone()
    if not sprint:
        return {"error": "Sprint not found"}

    if sprint["status"] in ("completed", "cancelled"):
        return {"error": "Cannot add tasks to a completed or cancelled sprint"}

    added = []
    failed = []

    for task_id in task_ids:
        cursor.execute("SELECT id FROM task_queue WHERE id = ?", (task_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE task_queue SET sprint_id = ? WHERE id = ?", (sprint_id, task_id))
            added.append(task_id)
        else:
            failed.append({"id": task_id, "error": "Task not found"})

    conn.commit()

    return {"sprint_id": sprint_id, "added": added, "added_count": len(added), "failed": failed}


def get_sprint_statuses():
    """Get available sprint statuses."""
    return SPRINT_STATUSES


def get_default_columns():
    """Get default board columns."""
    return DEFAULT_COLUMNS
