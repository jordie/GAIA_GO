"""
Task Effort Rollup Module
Aggregate effort metrics from subtasks to parent tasks
"""

import json
from datetime import datetime


def get_subtasks(conn, parent_id):
    """Get all direct subtasks of a parent task."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, status, priority, estimated_hours, actual_hours,
               progress_percent, parent_task_id
        FROM task_queue
        WHERE parent_task_id = ?
        ORDER BY id
    """,
        (parent_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_all_descendants(conn, parent_id, max_depth=10):
    """Get all descendant tasks (subtasks, sub-subtasks, etc.)."""
    descendants = []
    to_process = [(parent_id, 0)]
    processed = set()

    while to_process:
        task_id, depth = to_process.pop(0)

        if task_id in processed or depth > max_depth:
            continue

        processed.add(task_id)
        subtasks = get_subtasks(conn, task_id)

        for subtask in subtasks:
            subtask["depth"] = depth + 1
            descendants.append(subtask)
            to_process.append((subtask["id"], depth + 1))

    return descendants


def calculate_effort_rollup(conn, task_id, include_worklog=True):
    """Calculate rolled-up effort metrics for a task."""
    cursor = conn.cursor()

    # Get the task itself
    cursor.execute(
        """
        SELECT id, title, status, estimated_hours, actual_hours, progress_percent
        FROM task_queue WHERE id = ?
    """,
        (task_id,),
    )

    task = cursor.fetchone()
    if not task:
        return {"error": "Task not found"}

    task = dict(task)

    # Get all descendants
    descendants = get_all_descendants(conn, task_id)

    if not descendants:
        # No subtasks, return task's own values
        rollup = {
            "task_id": task_id,
            "task_title": task["title"],
            "has_subtasks": False,
            "own_estimated_hours": task["estimated_hours"] or 0,
            "own_actual_hours": task["actual_hours"] or 0,
            "own_progress": task["progress_percent"] or 0,
            "rollup_estimated_hours": task["estimated_hours"] or 0,
            "rollup_actual_hours": task["actual_hours"] or 0,
            "rollup_progress": task["progress_percent"] or 0,
            "subtask_count": 0,
            "completed_subtasks": 0,
        }

        if include_worklog:
            worklog = get_worklog_hours(conn, task_id)
            rollup["worklog_hours"] = worklog

        return rollup

    # Calculate rollup from descendants
    total_estimated = task["estimated_hours"] or 0
    total_actual = task["actual_hours"] or 0
    completed_count = 0
    total_progress = 0

    for subtask in descendants:
        total_estimated += subtask["estimated_hours"] or 0
        total_actual += subtask["actual_hours"] or 0
        total_progress += subtask["progress_percent"] or 0

        if subtask["status"] in ("completed", "done", "closed"):
            completed_count += 1

    # Calculate weighted progress
    if descendants:
        avg_progress = total_progress / len(descendants)
    else:
        avg_progress = task["progress_percent"] or 0

    rollup = {
        "task_id": task_id,
        "task_title": task["title"],
        "has_subtasks": True,
        "own_estimated_hours": task["estimated_hours"] or 0,
        "own_actual_hours": task["actual_hours"] or 0,
        "own_progress": task["progress_percent"] or 0,
        "rollup_estimated_hours": total_estimated,
        "rollup_actual_hours": total_actual,
        "rollup_progress": round(avg_progress, 1),
        "subtask_count": len(descendants),
        "completed_subtasks": completed_count,
        "completion_rate": round(completed_count / len(descendants) * 100, 1) if descendants else 0,
    }

    if include_worklog:
        # Get worklog hours for task and all descendants
        task_ids = [task_id] + [d["id"] for d in descendants]
        worklog = get_worklog_hours_bulk(conn, task_ids)
        rollup["worklog_hours"] = worklog

    return rollup


def get_worklog_hours(conn, task_id):
    """Get total worklog hours for a single task."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT SUM(time_spent_minutes) as total_minutes,
               SUM(CASE WHEN billable THEN time_spent_minutes ELSE 0 END) as billable_minutes
        FROM task_worklog
        WHERE task_id = ?
    """,
        (task_id,),
    )

    row = cursor.fetchone()
    if row and row["total_minutes"]:
        return {
            "total_hours": round(row["total_minutes"] / 60, 2),
            "billable_hours": round((row["billable_minutes"] or 0) / 60, 2),
        }
    return {"total_hours": 0, "billable_hours": 0}


def get_worklog_hours_bulk(conn, task_ids):
    """Get total worklog hours for multiple tasks."""
    if not task_ids:
        return {"total_hours": 0, "billable_hours": 0}

    cursor = conn.cursor()
    placeholders = ",".join(["?" for _ in task_ids])
    cursor.execute(
        f"""
        SELECT SUM(time_spent_minutes) as total_minutes,
               SUM(CASE WHEN billable THEN time_spent_minutes ELSE 0 END) as billable_minutes
        FROM task_worklog
        WHERE task_id IN ({placeholders})
    """,
        task_ids,
    )

    row = cursor.fetchone()
    if row and row["total_minutes"]:
        return {
            "total_hours": round(row["total_minutes"] / 60, 2),
            "billable_hours": round((row["billable_minutes"] or 0) / 60, 2),
        }
    return {"total_hours": 0, "billable_hours": 0}


def update_parent_rollup(conn, task_id):
    """Update a parent task's rolled-up values from its subtasks."""
    cursor = conn.cursor()

    # Get subtasks
    subtasks = get_subtasks(conn, task_id)

    if not subtasks:
        return {"updated": False, "reason": "No subtasks"}

    # Calculate totals
    total_estimated = sum(s["estimated_hours"] or 0 for s in subtasks)
    total_actual = sum(s["actual_hours"] or 0 for s in subtasks)
    total_progress = sum(s["progress_percent"] or 0 for s in subtasks)
    avg_progress = total_progress / len(subtasks) if subtasks else 0

    # Update parent task
    cursor.execute(
        """
        UPDATE task_queue
        SET rollup_estimated_hours = ?,
            rollup_actual_hours = ?,
            rollup_progress = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (total_estimated, total_actual, round(avg_progress, 1), task_id),
    )

    conn.commit()

    return {
        "updated": True,
        "task_id": task_id,
        "subtask_count": len(subtasks),
        "rollup_estimated_hours": total_estimated,
        "rollup_actual_hours": total_actual,
        "rollup_progress": round(avg_progress, 1),
    }


def propagate_rollup_to_ancestors(conn, task_id):
    """Propagate effort rollup up the task hierarchy."""
    cursor = conn.cursor()
    updated_tasks = []
    current_id = task_id
    max_iterations = 20  # Prevent infinite loops

    for _ in range(max_iterations):
        # Get parent task
        cursor.execute("SELECT parent_task_id FROM task_queue WHERE id = ?", (current_id,))
        row = cursor.fetchone()

        if not row or not row["parent_task_id"]:
            break

        parent_id = row["parent_task_id"]
        result = update_parent_rollup(conn, parent_id)

        if result.get("updated"):
            updated_tasks.append(result)

        current_id = parent_id

    return {
        "source_task_id": task_id,
        "updated_ancestors": updated_tasks,
        "count": len(updated_tasks),
    }


def get_effort_breakdown(conn, task_id):
    """Get detailed effort breakdown for a task and its subtasks."""
    cursor = conn.cursor()

    # Get the task
    cursor.execute(
        """
        SELECT id, title, status, estimated_hours, actual_hours, progress_percent
        FROM task_queue WHERE id = ?
    """,
        (task_id,),
    )

    task = cursor.fetchone()
    if not task:
        return {"error": "Task not found"}

    task = dict(task)

    # Get worklog for this task
    task["worklog"] = get_worklog_hours(conn, task_id)

    # Get all descendants with their worklogs
    descendants = get_all_descendants(conn, task_id)

    breakdown = {"task": task, "subtasks": []}

    for subtask in descendants:
        subtask["worklog"] = get_worklog_hours(conn, subtask["id"])
        breakdown["subtasks"].append(subtask)

    # Calculate totals
    all_tasks = [task] + descendants
    breakdown["totals"] = {
        "estimated_hours": sum(t["estimated_hours"] or 0 for t in all_tasks),
        "actual_hours": sum(t["actual_hours"] or 0 for t in all_tasks),
        "worklog_hours": sum(t["worklog"]["total_hours"] for t in all_tasks),
        "billable_hours": sum(t["worklog"]["billable_hours"] for t in all_tasks),
        "task_count": len(all_tasks),
        "completed_count": sum(
            1 for t in all_tasks if t["status"] in ("completed", "done", "closed")
        ),
    }

    # Variance analysis
    totals = breakdown["totals"]
    if totals["estimated_hours"] > 0:
        totals["variance_hours"] = totals["actual_hours"] - totals["estimated_hours"]
        totals["variance_percent"] = round(
            (totals["actual_hours"] - totals["estimated_hours"]) / totals["estimated_hours"] * 100,
            1,
        )
    else:
        totals["variance_hours"] = totals["actual_hours"]
        totals["variance_percent"] = 0

    return breakdown


def get_project_effort_summary(conn, project_id):
    """Get effort summary for all parent tasks in a project."""
    cursor = conn.cursor()

    # Get all parent tasks (tasks with subtasks)
    cursor.execute(
        """
        SELECT DISTINCT t.id, t.title, t.status, t.estimated_hours, t.actual_hours
        FROM task_queue t
        WHERE t.project_id = ?
          AND EXISTS (SELECT 1 FROM task_queue st WHERE st.parent_task_id = t.id)
        ORDER BY t.id
    """,
        (project_id,),
    )

    parent_tasks = [dict(row) for row in cursor.fetchall()]

    summaries = []
    for task in parent_tasks:
        rollup = calculate_effort_rollup(conn, task["id"], include_worklog=True)
        summaries.append(rollup)

    # Calculate project totals
    project_totals = {
        "total_estimated_hours": sum(s["rollup_estimated_hours"] for s in summaries),
        "total_actual_hours": sum(s["rollup_actual_hours"] for s in summaries),
        "total_worklog_hours": sum(
            s.get("worklog_hours", {}).get("total_hours", 0) for s in summaries
        ),
        "parent_task_count": len(summaries),
        "total_subtask_count": sum(s["subtask_count"] for s in summaries),
        "avg_completion_rate": round(
            sum(s.get("completion_rate", 0) for s in summaries) / len(summaries), 1
        )
        if summaries
        else 0,
    }

    return {"project_id": project_id, "parent_tasks": summaries, "totals": project_totals}


def recalculate_all_rollups(conn, project_id=None):
    """Recalculate rollups for all parent tasks."""
    cursor = conn.cursor()

    if project_id:
        cursor.execute(
            """
            SELECT DISTINCT t.id
            FROM task_queue t
            WHERE t.project_id = ?
              AND EXISTS (SELECT 1 FROM task_queue st WHERE st.parent_task_id = t.id)
        """,
            (project_id,),
        )
    else:
        cursor.execute(
            """
            SELECT DISTINCT t.id
            FROM task_queue t
            WHERE EXISTS (SELECT 1 FROM task_queue st WHERE st.parent_task_id = t.id)
        """
        )

    parent_ids = [row["id"] for row in cursor.fetchall()]

    updated = []
    for task_id in parent_ids:
        result = update_parent_rollup(conn, task_id)
        if result.get("updated"):
            updated.append(result)

    return {"recalculated_count": len(updated), "updated_tasks": updated}


def get_effort_comparison(conn, task_ids):
    """Compare effort metrics across multiple tasks."""
    comparisons = []

    for task_id in task_ids:
        rollup = calculate_effort_rollup(conn, task_id, include_worklog=True)
        if "error" not in rollup:
            comparisons.append(rollup)

    if not comparisons:
        return {"error": "No valid tasks found"}

    # Calculate averages
    avg_estimated = sum(c["rollup_estimated_hours"] for c in comparisons) / len(comparisons)
    avg_actual = sum(c["rollup_actual_hours"] for c in comparisons) / len(comparisons)
    avg_progress = sum(c["rollup_progress"] for c in comparisons) / len(comparisons)

    return {
        "tasks": comparisons,
        "averages": {
            "estimated_hours": round(avg_estimated, 2),
            "actual_hours": round(avg_actual, 2),
            "progress": round(avg_progress, 1),
        },
        "totals": {
            "estimated_hours": sum(c["rollup_estimated_hours"] for c in comparisons),
            "actual_hours": sum(c["rollup_actual_hours"] for c in comparisons),
            "subtask_count": sum(c["subtask_count"] for c in comparisons),
        },
    }


def estimate_remaining_effort(conn, task_id):
    """Estimate remaining effort based on current progress and actuals."""
    rollup = calculate_effort_rollup(conn, task_id, include_worklog=True)

    if "error" in rollup:
        return rollup

    progress = rollup["rollup_progress"]
    actual = rollup["rollup_actual_hours"]
    estimated = rollup["rollup_estimated_hours"]

    # Calculate remaining based on progress
    if progress > 0:
        # Extrapolate based on current rate
        projected_total = (actual / progress) * 100 if progress > 0 else estimated
        remaining_by_rate = max(0, projected_total - actual)
    else:
        remaining_by_rate = estimated

    # Calculate remaining based on estimate
    remaining_by_estimate = max(0, estimated - actual)

    return {
        "task_id": task_id,
        "current_progress": progress,
        "actual_hours": actual,
        "estimated_hours": estimated,
        "remaining_by_estimate": round(remaining_by_estimate, 2),
        "remaining_by_rate": round(remaining_by_rate, 2),
        "projected_total": round(actual + remaining_by_rate, 2) if progress > 0 else estimated,
        "is_over_estimate": actual > estimated,
        "efficiency": round((estimated / actual) * 100, 1) if actual > 0 else 100,
    }
