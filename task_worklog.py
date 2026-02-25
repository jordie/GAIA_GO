"""
Task Worklog Module
Tracks time and work entries for tasks
"""

import json
from datetime import datetime, timedelta


def create_worklog_entry(
    conn,
    task_id,
    user_id,
    description,
    time_spent_minutes,
    work_date=None,
    work_type="general",
    billable=True,
    metadata=None,
):
    """Create a new worklog entry for a task"""
    cursor = conn.cursor()

    # Verify task exists
    cursor.execute("SELECT id, title, status FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        return {"error": "Task not found"}

    work_date = work_date or datetime.now().strftime("%Y-%m-%d")

    cursor.execute(
        """
        INSERT INTO task_worklog (task_id, user_id, description, time_spent_minutes,
                                  work_date, work_type, billable, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            task_id,
            user_id,
            description,
            time_spent_minutes,
            work_date,
            work_type,
            billable,
            json.dumps(metadata) if metadata else None,
        ),
    )

    worklog_id = cursor.lastrowid
    conn.commit()

    return {
        "id": worklog_id,
        "task_id": task_id,
        "user_id": user_id,
        "description": description,
        "time_spent_minutes": time_spent_minutes,
        "work_date": work_date,
        "work_type": work_type,
        "billable": billable,
    }


def get_worklog_entry(conn, worklog_id):
    """Get a single worklog entry by ID"""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT w.*, t.title as task_title, t.status as task_status
        FROM task_worklog w
        JOIN tasks t ON w.task_id = t.id
        WHERE w.id = ?
    """,
        (worklog_id,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    return dict(row)


def get_task_worklog(conn, task_id, start_date=None, end_date=None, user_id=None):
    """Get all worklog entries for a task"""
    cursor = conn.cursor()

    query = """
        SELECT w.*, t.title as task_title
        FROM task_worklog w
        JOIN tasks t ON w.task_id = t.id
        WHERE w.task_id = ?
    """
    params = [task_id]

    if start_date:
        query += " AND w.work_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND w.work_date <= ?"
        params.append(end_date)

    if user_id:
        query += " AND w.user_id = ?"
        params.append(user_id)

    query += " ORDER BY w.work_date DESC, w.created_at DESC"

    cursor.execute(query, params)
    entries = [dict(row) for row in cursor.fetchall()]

    # Calculate totals
    total_minutes = sum(e["time_spent_minutes"] for e in entries)
    billable_minutes = sum(e["time_spent_minutes"] for e in entries if e["billable"])

    return {
        "entries": entries,
        "total_entries": len(entries),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 2),
        "billable_minutes": billable_minutes,
        "billable_hours": round(billable_minutes / 60, 2),
    }


def get_user_worklog(conn, user_id, start_date=None, end_date=None, task_id=None):
    """Get all worklog entries for a user"""
    cursor = conn.cursor()

    query = """
        SELECT w.*, t.title as task_title, t.status as task_status,
               p.name as project_name
        FROM task_worklog w
        JOIN tasks t ON w.task_id = t.id
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE w.user_id = ?
    """
    params = [user_id]

    if start_date:
        query += " AND w.work_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND w.work_date <= ?"
        params.append(end_date)

    if task_id:
        query += " AND w.task_id = ?"
        params.append(task_id)

    query += " ORDER BY w.work_date DESC, w.created_at DESC"

    cursor.execute(query, params)
    entries = [dict(row) for row in cursor.fetchall()]

    # Calculate totals
    total_minutes = sum(e["time_spent_minutes"] for e in entries)
    billable_minutes = sum(e["time_spent_minutes"] for e in entries if e["billable"])

    # Group by date
    by_date = {}
    for entry in entries:
        date = entry["work_date"]
        if date not in by_date:
            by_date[date] = {"entries": [], "total_minutes": 0}
        by_date[date]["entries"].append(entry)
        by_date[date]["total_minutes"] += entry["time_spent_minutes"]

    return {
        "entries": entries,
        "total_entries": len(entries),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 2),
        "billable_minutes": billable_minutes,
        "billable_hours": round(billable_minutes / 60, 2),
        "by_date": by_date,
    }


def update_worklog_entry(conn, worklog_id, user_id, updates):
    """Update a worklog entry (only by the creator)"""
    cursor = conn.cursor()

    # Verify ownership
    cursor.execute("SELECT user_id FROM task_worklog WHERE id = ?", (worklog_id,))
    row = cursor.fetchone()
    if not row:
        return {"error": "Worklog entry not found"}

    if row["user_id"] != user_id:
        return {"error": "Can only update your own worklog entries"}

    allowed_fields = [
        "description",
        "time_spent_minutes",
        "work_date",
        "work_type",
        "billable",
        "metadata",
    ]

    set_clauses = []
    params = []

    for field in allowed_fields:
        if field in updates:
            value = updates[field]
            if field == "metadata" and value is not None:
                value = json.dumps(value)
            set_clauses.append(f"{field} = ?")
            params.append(value)

    if not set_clauses:
        return {"error": "No valid fields to update"}

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(worklog_id)

    query = f'UPDATE task_worklog SET {", ".join(set_clauses)} WHERE id = ?'
    cursor.execute(query, params)
    conn.commit()

    return get_worklog_entry(conn, worklog_id)


def delete_worklog_entry(conn, worklog_id, user_id, force=False):
    """Delete a worklog entry (only by creator unless force)"""
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM task_worklog WHERE id = ?", (worklog_id,))
    row = cursor.fetchone()
    if not row:
        return {"error": "Worklog entry not found"}

    if not force and row["user_id"] != user_id:
        return {"error": "Can only delete your own worklog entries"}

    cursor.execute("DELETE FROM task_worklog WHERE id = ?", (worklog_id,))
    conn.commit()

    return {"success": True, "deleted_id": worklog_id}


def get_worklog_summary(conn, start_date=None, end_date=None, group_by="task"):
    """Get worklog summary grouped by task, user, project, or date"""
    cursor = conn.cursor()

    # Default to current week
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    if group_by == "task":
        cursor.execute(
            """
            SELECT t.id as task_id, t.title as task_title, t.status,
                   p.name as project_name,
                   COUNT(w.id) as entry_count,
                   SUM(w.time_spent_minutes) as total_minutes,
                   SUM(CASE WHEN w.billable THEN w.time_spent_minutes ELSE 0 END) as billable_minutes,
                   COUNT(DISTINCT w.user_id) as contributor_count,
                   MIN(w.work_date) as first_entry,
                   MAX(w.work_date) as last_entry
            FROM task_worklog w
            JOIN tasks t ON w.task_id = t.id
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE w.work_date BETWEEN ? AND ?
            GROUP BY t.id
            ORDER BY total_minutes DESC
        """,
            (start_date, end_date),
        )

    elif group_by == "user":
        cursor.execute(
            """
            SELECT w.user_id,
                   COUNT(w.id) as entry_count,
                   COUNT(DISTINCT w.task_id) as task_count,
                   SUM(w.time_spent_minutes) as total_minutes,
                   SUM(CASE WHEN w.billable THEN w.time_spent_minutes ELSE 0 END) as billable_minutes,
                   MIN(w.work_date) as first_entry,
                   MAX(w.work_date) as last_entry
            FROM task_worklog w
            WHERE w.work_date BETWEEN ? AND ?
            GROUP BY w.user_id
            ORDER BY total_minutes DESC
        """,
            (start_date, end_date),
        )

    elif group_by == "project":
        cursor.execute(
            """
            SELECT p.id as project_id, p.name as project_name,
                   COUNT(w.id) as entry_count,
                   COUNT(DISTINCT w.task_id) as task_count,
                   COUNT(DISTINCT w.user_id) as contributor_count,
                   SUM(w.time_spent_minutes) as total_minutes,
                   SUM(CASE WHEN w.billable THEN w.time_spent_minutes ELSE 0 END) as billable_minutes
            FROM task_worklog w
            JOIN tasks t ON w.task_id = t.id
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE w.work_date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY total_minutes DESC
        """,
            (start_date, end_date),
        )

    elif group_by == "date":
        cursor.execute(
            """
            SELECT w.work_date,
                   COUNT(w.id) as entry_count,
                   COUNT(DISTINCT w.task_id) as task_count,
                   COUNT(DISTINCT w.user_id) as user_count,
                   SUM(w.time_spent_minutes) as total_minutes,
                   SUM(CASE WHEN w.billable THEN w.time_spent_minutes ELSE 0 END) as billable_minutes
            FROM task_worklog w
            WHERE w.work_date BETWEEN ? AND ?
            GROUP BY w.work_date
            ORDER BY w.work_date DESC
        """,
            (start_date, end_date),
        )

    elif group_by == "work_type":
        cursor.execute(
            """
            SELECT w.work_type,
                   COUNT(w.id) as entry_count,
                   COUNT(DISTINCT w.task_id) as task_count,
                   COUNT(DISTINCT w.user_id) as user_count,
                   SUM(w.time_spent_minutes) as total_minutes,
                   SUM(CASE WHEN w.billable THEN w.time_spent_minutes ELSE 0 END) as billable_minutes
            FROM task_worklog w
            WHERE w.work_date BETWEEN ? AND ?
            GROUP BY w.work_type
            ORDER BY total_minutes DESC
        """,
            (start_date, end_date),
        )

    else:
        return {"error": f"Invalid group_by value: {group_by}"}

    results = [dict(row) for row in cursor.fetchall()]

    # Add hours calculation
    for r in results:
        if "total_minutes" in r:
            r["total_hours"] = round(r["total_minutes"] / 60, 2) if r["total_minutes"] else 0
        if "billable_minutes" in r:
            r["billable_hours"] = (
                round(r["billable_minutes"] / 60, 2) if r["billable_minutes"] else 0
            )

    # Calculate grand totals
    total_minutes = sum(r.get("total_minutes", 0) or 0 for r in results)
    billable_minutes = sum(r.get("billable_minutes", 0) or 0 for r in results)

    return {
        "group_by": group_by,
        "start_date": start_date,
        "end_date": end_date,
        "results": results,
        "totals": {
            "total_minutes": total_minutes,
            "total_hours": round(total_minutes / 60, 2),
            "billable_minutes": billable_minutes,
            "billable_hours": round(billable_minutes / 60, 2),
        },
    }


def start_timer(conn, task_id, user_id, description=None, work_type="general"):
    """Start a timer for a task"""
    cursor = conn.cursor()

    # Check for existing active timer
    cursor.execute(
        """
        SELECT id, task_id FROM task_timers
        WHERE user_id = ? AND end_time IS NULL
    """,
        (user_id,),
    )

    existing = cursor.fetchone()
    if existing:
        return {
            "error": "Timer already running",
            "active_timer_id": existing["id"],
            "active_task_id": existing["task_id"],
        }

    # Verify task exists
    cursor.execute("SELECT id, title FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        return {"error": "Task not found"}

    cursor.execute(
        """
        INSERT INTO task_timers (task_id, user_id, description, work_type, start_time)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """,
        (task_id, user_id, description, work_type),
    )

    timer_id = cursor.lastrowid
    conn.commit()

    return {
        "timer_id": timer_id,
        "task_id": task_id,
        "task_title": task["title"],
        "user_id": user_id,
        "description": description,
        "work_type": work_type,
        "started": True,
    }


def stop_timer(conn, user_id, billable=True, description=None):
    """Stop the active timer and create worklog entry"""
    cursor = conn.cursor()

    # Find active timer
    cursor.execute(
        """
        SELECT t.*, tk.title as task_title
        FROM task_timers t
        JOIN tasks tk ON t.task_id = tk.id
        WHERE t.user_id = ? AND t.end_time IS NULL
    """,
        (user_id,),
    )

    timer = cursor.fetchone()
    if not timer:
        return {"error": "No active timer found"}

    # Calculate duration
    start_time = datetime.fromisoformat(timer["start_time"].replace("Z", "+00:00"))
    end_time = datetime.now()
    duration_minutes = int((end_time - start_time).total_seconds() / 60)

    # Update timer
    cursor.execute(
        """
        UPDATE task_timers SET end_time = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (timer["id"],),
    )

    # Create worklog entry
    final_description = (
        description or timer["description"] or f"Timer session for {timer['task_title']}"
    )

    cursor.execute(
        """
        INSERT INTO task_worklog (task_id, user_id, description, time_spent_minutes,
                                  work_date, work_type, billable, metadata)
        VALUES (?, ?, ?, ?, DATE('now'), ?, ?, ?)
    """,
        (
            timer["task_id"],
            user_id,
            final_description,
            duration_minutes,
            timer["work_type"],
            billable,
            json.dumps({"timer_id": timer["id"]}),
        ),
    )

    worklog_id = cursor.lastrowid
    conn.commit()

    return {
        "timer_id": timer["id"],
        "worklog_id": worklog_id,
        "task_id": timer["task_id"],
        "task_title": timer["task_title"],
        "duration_minutes": duration_minutes,
        "duration_hours": round(duration_minutes / 60, 2),
        "stopped": True,
    }


def get_active_timer(conn, user_id):
    """Get user's active timer if any"""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT t.*, tk.title as task_title, tk.status as task_status
        FROM task_timers t
        JOIN tasks tk ON t.task_id = tk.id
        WHERE t.user_id = ? AND t.end_time IS NULL
    """,
        (user_id,),
    )

    timer = cursor.fetchone()
    if not timer:
        return None

    result = dict(timer)

    # Calculate running duration
    start_time = datetime.fromisoformat(timer["start_time"].replace("Z", "+00:00"))
    duration = datetime.now() - start_time
    result["running_minutes"] = int(duration.total_seconds() / 60)
    result["running_hours"] = round(result["running_minutes"] / 60, 2)

    return result


def discard_timer(conn, user_id):
    """Discard active timer without creating worklog entry"""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id FROM task_timers
        WHERE user_id = ? AND end_time IS NULL
    """,
        (user_id,),
    )

    timer = cursor.fetchone()
    if not timer:
        return {"error": "No active timer found"}

    cursor.execute("DELETE FROM task_timers WHERE id = ?", (timer["id"],))
    conn.commit()

    return {"success": True, "discarded_timer_id": timer["id"]}


# Work type definitions
WORK_TYPES = {
    "general": "General work",
    "development": "Development/coding",
    "review": "Code review",
    "testing": "Testing/QA",
    "documentation": "Documentation",
    "meeting": "Meetings/discussions",
    "research": "Research/investigation",
    "planning": "Planning/design",
    "bugfix": "Bug fixing",
    "support": "Support/troubleshooting",
    "deployment": "Deployment/release",
    "maintenance": "Maintenance",
}


def get_work_types():
    """Get available work types"""
    return WORK_TYPES
