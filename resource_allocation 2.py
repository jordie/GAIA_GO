"""
Resource Allocation Module
Reports and planning for resource allocation across projects and tasks
"""

import json
from datetime import datetime, timedelta


def get_user_allocation(conn, user_id, start_date=None, end_date=None):
    """Get resource allocation for a specific user."""
    cursor = conn.cursor()

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Get assigned tasks
    cursor.execute(
        """
        SELECT t.id, t.title, t.status, t.priority, t.task_type,
               t.estimated_hours, t.due_date, t.project_id,
               p.name as project_name
        FROM task_queue t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.assigned_to = ?
          AND t.status NOT IN ('completed', 'cancelled', 'archived')
          AND (t.due_date IS NULL OR t.due_date >= ?)
        ORDER BY t.priority DESC, t.due_date ASC
    """,
        (user_id, start_date),
    )

    tasks = [dict(row) for row in cursor.fetchall()]

    # Calculate allocation metrics
    total_estimated_hours = sum(t.get("estimated_hours") or 0 for t in tasks)
    tasks_by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    tasks_by_project = {}

    for task in tasks:
        priority = task.get("priority", "medium")
        if priority in tasks_by_priority:
            tasks_by_priority[priority] += 1

        project = task.get("project_name") or "Unassigned"
        if project not in tasks_by_project:
            tasks_by_project[project] = {"count": 0, "hours": 0}
        tasks_by_project[project]["count"] += 1
        tasks_by_project[project]["hours"] += task.get("estimated_hours") or 0

    # Get worklog data if available
    cursor.execute(
        """
        SELECT SUM(time_spent_minutes) as total_minutes
        FROM task_worklog
        WHERE user_id = ? AND work_date BETWEEN ? AND ?
    """,
        (user_id, start_date, end_date),
    )
    worklog = cursor.fetchone()
    logged_hours = (worklog["total_minutes"] or 0) / 60 if worklog else 0

    return {
        "user_id": user_id,
        "period": {"start": start_date, "end": end_date},
        "tasks": tasks,
        "metrics": {
            "total_tasks": len(tasks),
            "total_estimated_hours": total_estimated_hours,
            "logged_hours": round(logged_hours, 2),
            "tasks_by_priority": tasks_by_priority,
            "tasks_by_project": tasks_by_project,
        },
    }


def get_project_allocation(conn, project_id, start_date=None, end_date=None):
    """Get resource allocation for a specific project."""
    cursor = conn.cursor()

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Get project info
    cursor.execute("SELECT id, name, status FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()
    if not project:
        return {"error": "Project not found"}

    # Get all tasks for project
    cursor.execute(
        """
        SELECT t.id, t.title, t.status, t.priority, t.task_type,
               t.estimated_hours, t.due_date, t.assigned_to
        FROM task_queue t
        WHERE t.project_id = ?
          AND t.status NOT IN ('completed', 'cancelled', 'archived')
        ORDER BY t.priority DESC, t.due_date ASC
    """,
        (project_id,),
    )

    tasks = [dict(row) for row in cursor.fetchall()]

    # Group by assignee
    by_assignee = {}
    unassigned = []

    for task in tasks:
        assignee = task.get("assigned_to")
        if not assignee:
            unassigned.append(task)
        else:
            if assignee not in by_assignee:
                by_assignee[assignee] = {"tasks": [], "total_hours": 0}
            by_assignee[assignee]["tasks"].append(task)
            by_assignee[assignee]["total_hours"] += task.get("estimated_hours") or 0

    # Calculate totals
    total_hours = sum(t.get("estimated_hours") or 0 for t in tasks)
    assigned_hours = sum(a["total_hours"] for a in by_assignee.values())
    unassigned_hours = sum(t.get("estimated_hours") or 0 for t in unassigned)

    return {
        "project": dict(project),
        "period": {"start": start_date, "end": end_date},
        "allocation": {"by_assignee": by_assignee, "unassigned": unassigned},
        "metrics": {
            "total_tasks": len(tasks),
            "assigned_tasks": len(tasks) - len(unassigned),
            "unassigned_tasks": len(unassigned),
            "total_estimated_hours": total_hours,
            "assigned_hours": assigned_hours,
            "unassigned_hours": unassigned_hours,
            "team_size": len(by_assignee),
        },
    }


def get_team_allocation(conn, start_date=None, end_date=None, include_unassigned=True):
    """Get resource allocation across all team members."""
    cursor = conn.cursor()

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Get all active tasks grouped by assignee
    cursor.execute(
        """
        SELECT t.assigned_to,
               COUNT(*) as task_count,
               SUM(CASE WHEN t.priority = 'critical' THEN 1 ELSE 0 END) as critical_count,
               SUM(CASE WHEN t.priority = 'high' THEN 1 ELSE 0 END) as high_count,
               SUM(COALESCE(t.estimated_hours, 0)) as total_hours,
               COUNT(DISTINCT t.project_id) as project_count
        FROM task_queue t
        WHERE t.status NOT IN ('completed', 'cancelled', 'archived')
          AND (t.due_date IS NULL OR t.due_date >= ?)
        GROUP BY t.assigned_to
        ORDER BY total_hours DESC
    """,
        (start_date,),
    )

    allocations = []
    for row in cursor.fetchall():
        data = dict(row)
        if not data["assigned_to"] and not include_unassigned:
            continue
        data["user_id"] = data.pop("assigned_to") or "unassigned"
        allocations.append(data)

    # Calculate team totals
    total_tasks = sum(a["task_count"] for a in allocations)
    total_hours = sum(a["total_hours"] for a in allocations)
    team_members = [a for a in allocations if a["user_id"] != "unassigned"]

    return {
        "period": {"start": start_date, "end": end_date},
        "allocations": allocations,
        "summary": {
            "total_team_members": len(team_members),
            "total_tasks": total_tasks,
            "total_estimated_hours": total_hours,
            "avg_tasks_per_member": round(total_tasks / len(team_members), 1)
            if team_members
            else 0,
            "avg_hours_per_member": round(total_hours / len(team_members), 1)
            if team_members
            else 0,
        },
    }


def get_capacity_report(conn, start_date=None, end_date=None, hours_per_day=8):
    """Get capacity vs allocation report."""
    cursor = conn.cursor()

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Calculate working days in period
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    working_days = sum(
        1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5
    )

    # Get team allocation
    cursor.execute(
        """
        SELECT t.assigned_to as user_id,
               COUNT(*) as task_count,
               SUM(COALESCE(t.estimated_hours, 0)) as allocated_hours
        FROM task_queue t
        WHERE t.assigned_to IS NOT NULL
          AND t.status NOT IN ('completed', 'cancelled', 'archived')
          AND (t.due_date IS NULL OR t.due_date BETWEEN ? AND ?)
        GROUP BY t.assigned_to
    """,
        (start_date, end_date),
    )

    capacity_data = []
    total_capacity = 0
    total_allocated = 0

    for row in cursor.fetchall():
        data = dict(row)
        capacity = working_days * hours_per_day
        allocated = data["allocated_hours"]
        utilization = (allocated / capacity * 100) if capacity > 0 else 0

        capacity_data.append(
            {
                "user_id": data["user_id"],
                "task_count": data["task_count"],
                "capacity_hours": capacity,
                "allocated_hours": allocated,
                "available_hours": max(0, capacity - allocated),
                "utilization_percent": round(utilization, 1),
                "status": "overallocated"
                if utilization > 100
                else "available"
                if utilization < 80
                else "optimal",
            }
        )

        total_capacity += capacity
        total_allocated += allocated

    # Sort by utilization (highest first)
    capacity_data.sort(key=lambda x: x["utilization_percent"], reverse=True)

    return {
        "period": {
            "start": start_date,
            "end": end_date,
            "working_days": working_days,
            "hours_per_day": hours_per_day,
        },
        "capacity": capacity_data,
        "summary": {
            "team_size": len(capacity_data),
            "total_capacity_hours": total_capacity,
            "total_allocated_hours": total_allocated,
            "total_available_hours": max(0, total_capacity - total_allocated),
            "team_utilization_percent": round(total_allocated / total_capacity * 100, 1)
            if total_capacity > 0
            else 0,
            "overallocated_count": sum(1 for c in capacity_data if c["status"] == "overallocated"),
            "available_count": sum(1 for c in capacity_data if c["status"] == "available"),
        },
    }


def get_workload_forecast(conn, weeks=4, hours_per_day=8):
    """Get workload forecast for upcoming weeks."""
    cursor = conn.cursor()

    forecasts = []
    today = datetime.now()

    for week in range(weeks):
        week_start = today + timedelta(weeks=week, days=-today.weekday())
        week_end = week_start + timedelta(days=6)

        start_str = week_start.strftime("%Y-%m-%d")
        end_str = week_end.strftime("%Y-%m-%d")

        # Count tasks due this week
        cursor.execute(
            """
            SELECT COUNT(*) as task_count,
                   SUM(COALESCE(estimated_hours, 0)) as total_hours,
                   COUNT(DISTINCT assigned_to) as assignee_count
            FROM task_queue
            WHERE status NOT IN ('completed', 'cancelled', 'archived')
              AND due_date BETWEEN ? AND ?
        """,
            (start_str, end_str),
        )

        row = cursor.fetchone()
        data = dict(row) if row else {}

        # Calculate capacity (5 working days)
        working_days = 5
        team_capacity = (data.get("assignee_count") or 1) * working_days * hours_per_day

        forecasts.append(
            {
                "week": week + 1,
                "start_date": start_str,
                "end_date": end_str,
                "tasks_due": data.get("task_count") or 0,
                "estimated_hours": data.get("total_hours") or 0,
                "team_capacity": team_capacity,
                "utilization_percent": round(
                    (data.get("total_hours") or 0) / team_capacity * 100, 1
                )
                if team_capacity > 0
                else 0,
            }
        )

    return {"forecast_weeks": weeks, "hours_per_day": hours_per_day, "forecasts": forecasts}


def get_resource_conflicts(conn, start_date=None, end_date=None):
    """Identify resource conflicts (overallocated users, conflicting deadlines)."""
    cursor = conn.cursor()

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    conflicts = []

    # Find overallocated users (more than 8 hours of tasks due same day)
    cursor.execute(
        """
        SELECT t.assigned_to, t.due_date,
               COUNT(*) as task_count,
               SUM(COALESCE(t.estimated_hours, 0)) as total_hours,
               GROUP_CONCAT(t.id) as task_ids
        FROM task_queue t
        WHERE t.assigned_to IS NOT NULL
          AND t.due_date BETWEEN ? AND ?
          AND t.status NOT IN ('completed', 'cancelled', 'archived')
        GROUP BY t.assigned_to, t.due_date
        HAVING total_hours > 8
        ORDER BY t.due_date, total_hours DESC
    """,
        (start_date, end_date),
    )

    for row in cursor.fetchall():
        conflicts.append(
            {
                "type": "overallocation",
                "severity": "high" if row["total_hours"] > 16 else "medium",
                "user_id": row["assigned_to"],
                "date": row["due_date"],
                "details": {
                    "task_count": row["task_count"],
                    "total_hours": row["total_hours"],
                    "task_ids": row["task_ids"].split(",") if row["task_ids"] else [],
                },
                "recommendation": f"Redistribute {row['total_hours'] - 8:.1f} hours of work",
            }
        )

    # Find unassigned critical/high priority tasks due soon
    cursor.execute(
        """
        SELECT t.id, t.title, t.due_date, t.priority, t.estimated_hours
        FROM task_queue t
        WHERE t.assigned_to IS NULL
          AND t.priority IN ('critical', 'high')
          AND t.due_date BETWEEN ? AND ?
          AND t.status NOT IN ('completed', 'cancelled', 'archived')
        ORDER BY t.due_date
    """,
        (start_date, end_date),
    )

    for row in cursor.fetchall():
        conflicts.append(
            {
                "type": "unassigned_priority",
                "severity": "critical" if row["priority"] == "critical" else "high",
                "task_id": row["id"],
                "task_title": row["title"],
                "due_date": row["due_date"],
                "details": {"priority": row["priority"], "estimated_hours": row["estimated_hours"]},
                "recommendation": "Assign to available team member immediately",
            }
        )

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    conflicts.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return {
        "period": {"start": start_date, "end": end_date},
        "conflicts": conflicts,
        "summary": {
            "total_conflicts": len(conflicts),
            "critical": sum(1 for c in conflicts if c["severity"] == "critical"),
            "high": sum(1 for c in conflicts if c["severity"] == "high"),
            "medium": sum(1 for c in conflicts if c["severity"] == "medium"),
        },
    }


def get_allocation_by_skill(conn, start_date=None, end_date=None):
    """Get resource allocation grouped by required skills/task types."""
    cursor = conn.cursor()

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    cursor.execute(
        """
        SELECT t.task_type,
               COUNT(*) as task_count,
               SUM(COALESCE(t.estimated_hours, 0)) as total_hours,
               COUNT(DISTINCT t.assigned_to) as assignee_count,
               SUM(CASE WHEN t.assigned_to IS NULL THEN 1 ELSE 0 END) as unassigned_count
        FROM task_queue t
        WHERE t.status NOT IN ('completed', 'cancelled', 'archived')
          AND (t.due_date IS NULL OR t.due_date BETWEEN ? AND ?)
        GROUP BY t.task_type
        ORDER BY total_hours DESC
    """,
        (start_date, end_date),
    )

    skills = [dict(row) for row in cursor.fetchall()]

    return {
        "period": {"start": start_date, "end": end_date},
        "by_skill": skills,
        "summary": {
            "total_task_types": len(skills),
            "total_hours": sum(s["total_hours"] for s in skills),
            "most_demanding": skills[0]["task_type"] if skills else None,
        },
    }


def suggest_reallocation(conn, user_id=None):
    """Suggest task reallocations to balance workload."""
    cursor = conn.cursor()

    suggestions = []

    # Find overallocated users
    cursor.execute(
        """
        SELECT assigned_to, SUM(COALESCE(estimated_hours, 0)) as total_hours
        FROM task_queue
        WHERE assigned_to IS NOT NULL
          AND status NOT IN ('completed', 'cancelled', 'archived')
        GROUP BY assigned_to
        HAVING total_hours > 40
    """
    )

    overallocated = {row["assigned_to"]: row["total_hours"] for row in cursor.fetchall()}

    # Find underallocated users
    cursor.execute(
        """
        SELECT assigned_to, SUM(COALESCE(estimated_hours, 0)) as total_hours
        FROM task_queue
        WHERE assigned_to IS NOT NULL
          AND status NOT IN ('completed', 'cancelled', 'archived')
        GROUP BY assigned_to
        HAVING total_hours < 20
    """
    )

    underallocated = {row["assigned_to"]: row["total_hours"] for row in cursor.fetchall()}

    # For each overallocated user, find tasks that could be moved
    for over_user, over_hours in overallocated.items():
        if user_id and over_user != user_id:
            continue

        cursor.execute(
            """
            SELECT id, title, priority, estimated_hours, task_type
            FROM task_queue
            WHERE assigned_to = ?
              AND status NOT IN ('completed', 'cancelled', 'archived', 'in_progress')
              AND priority NOT IN ('critical')
            ORDER BY priority ASC, estimated_hours DESC
            LIMIT 5
        """,
            (over_user,),
        )

        movable_tasks = [dict(row) for row in cursor.fetchall()]

        for task in movable_tasks:
            # Find potential recipients
            for under_user, under_hours in underallocated.items():
                if under_hours + (task["estimated_hours"] or 0) <= 40:
                    suggestions.append(
                        {
                            "action": "reassign",
                            "task_id": task["id"],
                            "task_title": task["title"],
                            "from_user": over_user,
                            "to_user": under_user,
                            "reason": f"{over_user} is overallocated ({over_hours:.0f}h), {under_user} has capacity ({under_hours:.0f}h)",
                            "impact": {
                                "hours_moved": task["estimated_hours"] or 0,
                                "from_new_total": over_hours - (task["estimated_hours"] or 0),
                                "to_new_total": under_hours + (task["estimated_hours"] or 0),
                            },
                        }
                    )
                    break

    return {
        "suggestions": suggestions[:10],  # Limit to top 10
        "overallocated_users": list(overallocated.keys()),
        "underallocated_users": list(underallocated.keys()),
    }
