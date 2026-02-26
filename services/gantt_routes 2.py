"""
Gantt Chart Data Routes

Flask blueprint for Gantt chart visualization endpoints.
"""

import logging
import sqlite3
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

gantt_bp = Blueprint("gantt", __name__, url_prefix="/api/milestones")


def get_db_connection():
    """Get database connection."""
    from flask import g

    db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))
    if "db" not in g:
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db


def require_auth(f):
    """Decorator to require authentication."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        # Check API key first
        api_key = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        elif request.headers.get("X-API-Key"):
            api_key = request.headers.get("X-API-Key")
        elif request.args.get("api_key"):
            api_key = request.args.get("api_key")

        if api_key:
            try:
                from services.api_keys import get_api_key_service

                db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))
                service = get_api_key_service(db_path)
                result = service.validate_key(api_key)
                if result["valid"]:
                    return f(*args, **kwargs)
            except Exception:
                pass

        # Fall back to session auth
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


# Status to color mapping
STATUS_COLORS = {
    # Milestone statuses
    "open": "#3498db",  # Blue
    "in_progress": "#f39c12",  # Orange
    "completed": "#27ae60",  # Green
    "on_hold": "#95a5a6",  # Gray
    # Feature statuses
    "draft": "#bdc3c7",  # Light gray
    "spec": "#9b59b6",  # Purple
    "review": "#e67e22",  # Dark orange
    "blocked": "#e74c3c",  # Red
    "cancelled": "#7f8c8d",  # Dark gray
    # Bug statuses
    "resolved": "#27ae60",  # Green
    # Severity colors for bugs
    "critical": "#c0392b",
    "high": "#e74c3c",
    "medium": "#f39c12",
    "low": "#3498db",
}


def parse_date(date_str, default=None):
    """Parse a date string to date format YYYY-MM-DD."""
    if not date_str:
        return default

    if isinstance(date_str, date):
        return str(date_str)

    if isinstance(date_str, str):
        # Handle datetime strings
        if "T" in date_str:
            date_str = date_str.split("T")[0]
        elif " " in date_str:
            date_str = date_str.split(" ")[0]
        return date_str

    return default


@gantt_bp.route("/gantt", methods=["GET"])
@require_auth
def get_milestones_gantt():
    """Get Gantt chart data for milestones and their items.

    Query params:
        project_id: Filter by project (optional)
        start_date: Filter tasks starting after this date (optional, YYYY-MM-DD)
        end_date: Filter tasks ending before this date (optional, YYYY-MM-DD)
        include_completed: Include completed items (default true)
        group_by: Grouping mode - 'milestone' (default), 'project', or 'status'

    Returns:
        Gantt chart compatible data structure with:
        - tasks: Array of task objects with id, name, start, end, progress, dependencies
        - links: Array of dependency links between tasks
        - config: Chart configuration and color mappings
    """
    project_id = request.args.get("project_id", type=int)
    start_date_filter = request.args.get("start_date")
    end_date_filter = request.args.get("end_date")
    include_completed = request.args.get("include_completed", "true").lower() == "true"
    group_by = request.args.get("group_by", "milestone")

    conn = get_db_connection()
    today = date.today()

    # Build where clauses
    milestone_conditions = []
    milestone_params = []

    if project_id:
        milestone_conditions.append("m.project_id = ?")
        milestone_params.append(project_id)

    if not include_completed:
        milestone_conditions.append("m.status != 'completed'")

    milestone_where = "WHERE " + " AND ".join(milestone_conditions) if milestone_conditions else ""

    # Get milestones with project info
    milestones = conn.execute(
        f"""
        SELECT m.*, p.name as project_name
        FROM milestones m
        LEFT JOIN projects p ON m.project_id = p.id
        {milestone_where}
        ORDER BY m.project_id, m.target_date, m.name
    """,
        milestone_params,
    ).fetchall()

    tasks = []
    links = []

    for m in milestones:
        m_dict = dict(m)
        milestone_id = f"m_{m_dict['id']}"

        # Determine milestone dates
        m_start = parse_date(m_dict.get("created_at"), str(today))
        m_end = parse_date(m_dict.get("target_date"), str(today + timedelta(days=30)))

        # Get child items
        features = conn.execute(
            """
            SELECT id, name, description, status, priority,
                   created_at, updated_at, estimated_hours, actual_hours
            FROM features WHERE milestone_id = ?
            ORDER BY priority, name
        """,
            (m_dict["id"],),
        ).fetchall()

        bugs = conn.execute(
            """
            SELECT id, title, description, status, severity,
                   created_at, updated_at, resolved_at
            FROM bugs WHERE milestone_id = ?
            ORDER BY CASE severity
                WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4
            END, title
        """,
            (m_dict["id"],),
        ).fetchall()

        # Calculate progress
        total_items = len(features) + len(bugs)
        completed_items = sum(1 for f in features if f["status"] == "completed")
        completed_items += sum(1 for b in bugs if b["status"] == "resolved")
        milestone_progress = round((completed_items / total_items * 100) if total_items > 0 else 0)

        # Check overdue
        is_overdue = False
        if m_dict.get("target_date") and m_dict["status"] != "completed":
            try:
                target = datetime.strptime(m_end, "%Y-%m-%d").date()
                is_overdue = target < today
            except (ValueError, TypeError):
                pass

        # Add milestone task
        tasks.append(
            {
                "id": milestone_id,
                "name": m_dict["name"],
                "description": m_dict.get("description", ""),
                "type": "milestone",
                "project_id": m_dict["project_id"],
                "project_name": m_dict.get("project_name", ""),
                "start": m_start,
                "end": m_end,
                "progress": milestone_progress,
                "status": m_dict["status"] or "open",
                "color": STATUS_COLORS.get(m_dict["status"] or "open", "#3498db"),
                "is_group": True,
                "is_overdue": is_overdue,
                "parent": None,
                "children_count": total_items,
                "completed_count": completed_items,
            }
        )

        # Add features
        for f in features:
            f_dict = dict(f)
            if not include_completed and f_dict["status"] == "completed":
                continue

            f_start = parse_date(f_dict.get("created_at"), m_start)

            # Estimate end date based on hours
            est_hours = f_dict.get("estimated_hours") or 8
            est_days = max(1, est_hours // 8)
            try:
                f_end_date = datetime.strptime(f_start, "%Y-%m-%d").date() + timedelta(
                    days=est_days
                )
                m_end_date = datetime.strptime(m_end, "%Y-%m-%d").date()
                f_end = str(min(f_end_date, m_end_date))
            except (ValueError, TypeError):
                f_end = m_end

            # Feature progress based on status
            f_progress = (
                100
                if f_dict["status"] == "completed"
                else (
                    75
                    if f_dict["status"] == "review"
                    else (
                        50
                        if f_dict["status"] == "in_progress"
                        else (25 if f_dict["status"] == "spec" else 0)
                    )
                )
            )

            tasks.append(
                {
                    "id": f"f_{f_dict['id']}",
                    "name": f_dict["name"],
                    "description": f_dict.get("description", ""),
                    "type": "feature",
                    "start": f_start,
                    "end": f_end,
                    "progress": f_progress,
                    "status": f_dict["status"] or "draft",
                    "priority": f_dict.get("priority", "medium"),
                    "color": STATUS_COLORS.get(f_dict["status"] or "draft", "#bdc3c7"),
                    "is_group": False,
                    "parent": milestone_id,
                    "estimated_hours": f_dict.get("estimated_hours"),
                    "actual_hours": f_dict.get("actual_hours"),
                }
            )

        # Add bugs
        for b in bugs:
            b_dict = dict(b)
            if not include_completed and b_dict["status"] == "resolved":
                continue

            b_start = parse_date(b_dict.get("created_at"), m_start)

            if b_dict.get("resolved_at"):
                b_end = parse_date(b_dict["resolved_at"], m_end)
            else:
                # Estimate based on severity
                severity_days = {"critical": 1, "high": 2, "medium": 5, "low": 10}
                est_days = severity_days.get(b_dict.get("severity", "medium"), 5)
                try:
                    b_end_date = datetime.strptime(b_start, "%Y-%m-%d").date() + timedelta(
                        days=est_days
                    )
                    m_end_date = datetime.strptime(m_end, "%Y-%m-%d").date()
                    b_end = str(min(b_end_date, m_end_date))
                except (ValueError, TypeError):
                    b_end = m_end

            b_progress = (
                100
                if b_dict["status"] == "resolved"
                else (50 if b_dict["status"] == "in_progress" else 0)
            )

            tasks.append(
                {
                    "id": f"b_{b_dict['id']}",
                    "name": f"[BUG] {b_dict['title']}",
                    "description": b_dict.get("description", ""),
                    "type": "bug",
                    "start": b_start,
                    "end": b_end,
                    "progress": b_progress,
                    "status": b_dict["status"] or "open",
                    "severity": b_dict.get("severity", "medium"),
                    "color": STATUS_COLORS.get(b_dict.get("severity", "medium"), "#f39c12"),
                    "is_group": False,
                    "parent": milestone_id,
                }
            )

    # Filter by date range
    if start_date_filter or end_date_filter:
        filtered_tasks = []
        for t in tasks:
            task_start = t.get("start", "")
            task_end = t.get("end", "")

            include = True
            if start_date_filter and task_end < start_date_filter:
                include = False
            if end_date_filter and task_start > end_date_filter:
                include = False

            if include:
                filtered_tasks.append(t)
        tasks = filtered_tasks

    # Calculate chart range
    if tasks:
        all_starts = [t["start"] for t in tasks if t.get("start")]
        all_ends = [t["end"] for t in tasks if t.get("end")]
        chart_start = min(all_starts) if all_starts else str(today)
        chart_end = max(all_ends) if all_ends else str(today + timedelta(days=90))
    else:
        chart_start = str(today)
        chart_end = str(today + timedelta(days=90))

    # Build summary
    summary = {
        "total_tasks": len(tasks),
        "milestones": len([t for t in tasks if t["type"] == "milestone"]),
        "features": len([t for t in tasks if t["type"] == "feature"]),
        "bugs": len([t for t in tasks if t["type"] == "bug"]),
        "completed": len([t for t in tasks if t.get("progress", 0) == 100]),
        "in_progress": len([t for t in tasks if 0 < t.get("progress", 0) < 100]),
        "not_started": len(
            [t for t in tasks if t.get("progress", 0) == 0 and not t.get("is_group")]
        ),
        "overdue": len([t for t in tasks if t.get("is_overdue")]),
    }

    return jsonify(
        {
            "tasks": tasks,
            "links": links,
            "config": {
                "status_colors": STATUS_COLORS,
                "today": str(today),
                "group_by": group_by,
                "filters": {
                    "project_id": project_id,
                    "start_date": start_date_filter,
                    "end_date": end_date_filter,
                    "include_completed": include_completed,
                },
            },
            "chart_range": {"start": chart_start, "end": chart_end},
            "summary": summary,
        }
    )


@gantt_bp.route("/gantt/export", methods=["GET"])
@require_auth
def export_gantt_data():
    """Export Gantt data in various formats.

    Query params:
        format: Export format - 'json' (default), 'csv', or 'ical'
        project_id: Filter by project (optional)

    Returns:
        Data in requested format
    """
    export_format = request.args.get("format", "json").lower()
    project_id = request.args.get("project_id", type=int)

    # Get base gantt data
    conn = get_db_connection()
    today = date.today()

    conditions = []
    params = []

    if project_id:
        conditions.append("m.project_id = ?")
        params.append(project_id)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    milestones = conn.execute(
        f"""
        SELECT m.*, p.name as project_name
        FROM milestones m
        LEFT JOIN projects p ON m.project_id = p.id
        {where_clause}
        ORDER BY m.target_date, m.name
    """,
        params,
    ).fetchall()

    if export_format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "Type",
                "ID",
                "Name",
                "Project",
                "Status",
                "Start Date",
                "End Date",
                "Progress %",
                "Parent",
            ]
        )

        for m in milestones:
            m_dict = dict(m)
            m_start = parse_date(m_dict.get("created_at"), str(today))
            m_end = parse_date(m_dict.get("target_date"), str(today + timedelta(days=30)))

            # Milestone row
            writer.writerow(
                [
                    "Milestone",
                    m_dict["id"],
                    m_dict["name"],
                    m_dict.get("project_name", ""),
                    m_dict["status"],
                    m_start,
                    m_end,
                    m_dict.get("progress", 0),
                    "",
                ]
            )

            # Features
            features = conn.execute(
                """
                SELECT * FROM features WHERE milestone_id = ?
            """,
                (m_dict["id"],),
            ).fetchall()

            for f in features:
                f_dict = dict(f)
                writer.writerow(
                    [
                        "Feature",
                        f_dict["id"],
                        f_dict["name"],
                        m_dict.get("project_name", ""),
                        f_dict["status"],
                        parse_date(f_dict.get("created_at"), m_start),
                        m_end,
                        "",
                        f"Milestone {m_dict['id']}",
                    ]
                )

            # Bugs
            bugs = conn.execute(
                """
                SELECT * FROM bugs WHERE milestone_id = ?
            """,
                (m_dict["id"],),
            ).fetchall()

            for b in bugs:
                b_dict = dict(b)
                writer.writerow(
                    [
                        "Bug",
                        b_dict["id"],
                        b_dict["title"],
                        m_dict.get("project_name", ""),
                        b_dict["status"],
                        parse_date(b_dict.get("created_at"), m_start),
                        parse_date(b_dict.get("resolved_at"), m_end),
                        "",
                        f"Milestone {m_dict['id']}",
                    ]
                )

        csv_data = output.getvalue()
        output.close()

        from flask import Response

        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=gantt_export.csv"},
        )

    elif export_format == "ical":
        # iCalendar format
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Architect Dashboard//Gantt Export//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        for m in milestones:
            m_dict = dict(m)
            m_start = parse_date(m_dict.get("created_at"), str(today))
            m_end = parse_date(m_dict.get("target_date"), str(today + timedelta(days=30)))

            # Format dates for iCal (YYYYMMDD)
            start_ical = m_start.replace("-", "")
            end_ical = m_end.replace("-", "")

            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f'UID:milestone-{m_dict["id"]}@architect',
                    f"DTSTART;VALUE=DATE:{start_ical}",
                    f"DTEND;VALUE=DATE:{end_ical}",
                    f'SUMMARY:[Milestone] {m_dict["name"]}',
                    f'DESCRIPTION:{m_dict.get("description", "")}',
                    f'STATUS:{m_dict["status"].upper() if m_dict.get("status") else "TENTATIVE"}',
                    "END:VEVENT",
                ]
            )

        lines.append("END:VCALENDAR")
        ical_data = "\r\n".join(lines)

        from flask import Response

        return Response(
            ical_data,
            mimetype="text/calendar",
            headers={"Content-Disposition": "attachment; filename=gantt_export.ics"},
        )

    else:
        # Default JSON format - just redirect to main endpoint
        return get_milestones_gantt()


@gantt_bp.route("/gantt/timeline", methods=["GET"])
@require_auth
def get_gantt_timeline():
    """Get timeline view data optimized for horizontal timeline display.

    Query params:
        project_id: Filter by project (optional)
        months: Number of months to display (default 3)
        start_month: Starting month offset from today (default 0)

    Returns:
        Timeline optimized data with month/week markers
    """
    project_id = request.args.get("project_id", type=int)
    months = request.args.get("months", 3, type=int)
    start_month_offset = request.args.get("start_month", 0, type=int)

    conn = get_db_connection()
    today = date.today()

    # Calculate date range
    start_date = today.replace(day=1)
    for _ in range(start_month_offset):
        start_date = (start_date - timedelta(days=1)).replace(day=1)

    end_date = start_date
    for _ in range(months):
        next_month = end_date.replace(day=28) + timedelta(days=4)
        end_date = next_month.replace(day=1) - timedelta(days=1)
        end_date = (end_date + timedelta(days=1)).replace(day=1)

    # Build month markers
    month_markers = []
    current = start_date
    while current < end_date:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_markers.append(
            {
                "month": current.strftime("%B %Y"),
                "start": str(current),
                "end": str(next_month - timedelta(days=1)),
                "weeks": [],
            }
        )

        # Add week markers
        week_start = current
        while week_start < next_month:
            week_end = min(week_start + timedelta(days=6), next_month - timedelta(days=1))
            month_markers[-1]["weeks"].append(
                {
                    "start": str(week_start),
                    "end": str(week_end),
                    "week_number": week_start.isocalendar()[1],
                }
            )
            week_start = week_end + timedelta(days=1)

        current = next_month

    # Get milestones in range
    conditions = [
        "(m.target_date >= ? OR m.target_date IS NULL)",
        "(m.created_at <= ? OR m.created_at IS NULL)",
    ]
    params = [str(start_date), str(end_date)]

    if project_id:
        conditions.append("m.project_id = ?")
        params.append(project_id)

    where_clause = "WHERE " + " AND ".join(conditions)

    milestones = conn.execute(
        f"""
        SELECT m.*, p.name as project_name,
               (SELECT COUNT(*) FROM features WHERE milestone_id = m.id) as feature_count,
               (SELECT COUNT(*) FROM bugs WHERE milestone_id = m.id) as bug_count
        FROM milestones m
        LEFT JOIN projects p ON m.project_id = p.id
        {where_clause}
        ORDER BY m.target_date, m.name
    """,
        params,
    ).fetchall()

    timeline_items = []
    for m in milestones:
        m_dict = dict(m)
        m_start = parse_date(m_dict.get("created_at"), str(today))
        m_end = parse_date(m_dict.get("target_date"), str(today + timedelta(days=30)))

        timeline_items.append(
            {
                "id": f"m_{m_dict['id']}",
                "name": m_dict["name"],
                "type": "milestone",
                "project_name": m_dict.get("project_name", ""),
                "start": m_start,
                "end": m_end,
                "status": m_dict["status"] or "open",
                "color": STATUS_COLORS.get(m_dict["status"] or "open", "#3498db"),
                "progress": m_dict.get("progress", 0),
                "feature_count": m_dict.get("feature_count", 0),
                "bug_count": m_dict.get("bug_count", 0),
            }
        )

    return jsonify(
        {
            "timeline": {"start": str(start_date), "end": str(end_date), "months": month_markers},
            "items": timeline_items,
            "today": str(today),
            "config": {"months_displayed": months, "start_month_offset": start_month_offset},
        }
    )


@gantt_bp.route("/burnup", methods=["GET"])
@require_auth
def get_burnup_chart():
    """Get burnup chart data for a milestone or project.

    A burnup chart shows:
    - Total scope (work to be done) over time
    - Work completed over time
    - Helps visualize progress and scope changes

    Query params:
        milestone_id: Filter by milestone (optional, but recommended)
        project_id: Filter by project (optional)
        start_date: Start date for chart (optional, YYYY-MM-DD)
        end_date: End date for chart (optional, YYYY-MM-DD)
        granularity: Data point granularity - 'day', 'week', 'month' (default 'day')
        metric: What to measure - 'count', 'story_points', 'hours' (default 'count')

    Returns:
        Burnup chart data with scope and completed series
    """
    milestone_id = request.args.get("milestone_id", type=int)
    project_id = request.args.get("project_id", type=int)
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    granularity = request.args.get("granularity", "day")
    metric = request.args.get("metric", "count")

    if granularity not in ("day", "week", "month"):
        return jsonify({"error": "granularity must be 'day', 'week', or 'month'"}), 400

    if metric not in ("count", "story_points", "hours"):
        return jsonify({"error": "metric must be 'count', 'story_points', or 'hours'"}), 400

    conn = get_db_connection()
    today = date.today()

    # Determine date range
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid start_date format"}), 400
    else:
        # Default to 30 days ago or milestone start
        start_date = today - timedelta(days=30)

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid end_date format"}), 400
    else:
        end_date = today

    # Build query conditions
    feature_conditions = []
    bug_conditions = []
    params = []

    if milestone_id:
        feature_conditions.append("milestone_id = ?")
        bug_conditions.append("milestone_id = ?")
        params.append(milestone_id)
    elif project_id:
        feature_conditions.append("project_id = ?")
        bug_conditions.append("project_id = ?")
        params.append(project_id)

    feature_where = "WHERE " + " AND ".join(feature_conditions) if feature_conditions else ""
    bug_where = "WHERE " + " AND ".join(bug_conditions) if bug_conditions else ""

    # Get all features and bugs with their creation and completion dates
    features = conn.execute(
        f"""
        SELECT id, name, status, created_at, updated_at,
               story_points, estimated_hours, actual_hours
        FROM features
        {feature_where}
        ORDER BY created_at
    """,
        params if milestone_id or project_id else [],
    ).fetchall()

    bugs = conn.execute(
        f"""
        SELECT id, title, status, created_at, updated_at, resolved_at
        FROM bugs
        {bug_where}
        ORDER BY created_at
    """,
        params if milestone_id or project_id else [],
    ).fetchall()

    # Adjust start_date to earliest item if needed
    all_created_dates = []
    for f in features:
        if f["created_at"]:
            try:
                d = datetime.strptime(
                    str(f["created_at"]).split("T")[0].split(" ")[0], "%Y-%m-%d"
                ).date()
                all_created_dates.append(d)
            except ValueError:
                pass
    for b in bugs:
        if b["created_at"]:
            try:
                d = datetime.strptime(
                    str(b["created_at"]).split("T")[0].split(" ")[0], "%Y-%m-%d"
                ).date()
                all_created_dates.append(d)
            except ValueError:
                pass

    if all_created_dates and not start_date_str:
        start_date = min(min(all_created_dates), start_date)

    # Generate date points based on granularity
    date_points = []
    current = start_date

    if granularity == "day":
        while current <= end_date:
            date_points.append(current)
            current += timedelta(days=1)
    elif granularity == "week":
        # Start from Monday
        current = current - timedelta(days=current.weekday())
        while current <= end_date:
            date_points.append(current)
            current += timedelta(weeks=1)
    elif granularity == "month":
        current = current.replace(day=1)
        while current <= end_date:
            date_points.append(current)
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

    # Calculate cumulative scope and completed for each date point
    data_points = []

    for point_date in date_points:
        # Calculate scope (items created up to this date)
        scope_count = 0
        scope_points = 0
        scope_hours = 0

        completed_count = 0
        completed_points = 0
        completed_hours = 0

        for f in features:
            f_dict = dict(f)
            created = None
            completed_date = None

            if f_dict["created_at"]:
                try:
                    created = datetime.strptime(
                        str(f_dict["created_at"]).split("T")[0].split(" ")[0], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    created = start_date

            # Check if feature was in scope by this date
            if created and created <= point_date:
                scope_count += 1
                scope_points += f_dict.get("story_points") or 0
                scope_hours += f_dict.get("estimated_hours") or 0

                # Check if completed by this date
                if f_dict["status"] == "completed" and f_dict.get("updated_at"):
                    try:
                        completed_date = datetime.strptime(
                            str(f_dict["updated_at"]).split("T")[0].split(" ")[0], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        pass

                    if completed_date and completed_date <= point_date:
                        completed_count += 1
                        completed_points += f_dict.get("story_points") or 0
                        completed_hours += (
                            f_dict.get("actual_hours") or f_dict.get("estimated_hours") or 0
                        )

        for b in bugs:
            b_dict = dict(b)
            created = None
            resolved_date = None

            if b_dict["created_at"]:
                try:
                    created = datetime.strptime(
                        str(b_dict["created_at"]).split("T")[0].split(" ")[0], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    created = start_date

            # Check if bug was in scope by this date
            if created and created <= point_date:
                scope_count += 1
                scope_points += 1  # Bugs count as 1 point
                scope_hours += 4  # Estimate 4 hours per bug

                # Check if resolved by this date
                if b_dict["status"] in ("resolved", "closed"):
                    if b_dict.get("resolved_at"):
                        try:
                            resolved_date = datetime.strptime(
                                str(b_dict["resolved_at"]).split("T")[0].split(" ")[0], "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            pass
                    elif b_dict.get("updated_at"):
                        try:
                            resolved_date = datetime.strptime(
                                str(b_dict["updated_at"]).split("T")[0].split(" ")[0], "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            pass

                    if resolved_date and resolved_date <= point_date:
                        completed_count += 1
                        completed_points += 1
                        completed_hours += 4

        # Select values based on metric
        if metric == "count":
            scope_value = scope_count
            completed_value = completed_count
        elif metric == "story_points":
            scope_value = scope_points
            completed_value = completed_points
        else:  # hours
            scope_value = scope_hours
            completed_value = completed_hours

        data_points.append(
            {
                "date": str(point_date),
                "scope": scope_value,
                "completed": completed_value,
                "remaining": scope_value - completed_value,
                "progress_percent": round(
                    (completed_value / scope_value * 100) if scope_value > 0 else 0, 1
                ),
            }
        )

    # Calculate summary statistics
    total_features = len(features)
    total_bugs = len(bugs)
    completed_features = sum(1 for f in features if f["status"] == "completed")
    completed_bugs = sum(1 for b in bugs if b["status"] in ("resolved", "closed"))

    # Calculate velocity (items completed per period)
    if len(data_points) > 1:
        periods_with_progress = sum(
            1
            for i in range(1, len(data_points))
            if data_points[i]["completed"] > data_points[i - 1]["completed"]
        )
        total_completed = data_points[-1]["completed"] if data_points else 0
        avg_velocity = round(total_completed / len(data_points), 2) if data_points else 0
    else:
        avg_velocity = 0

    # Predict completion date based on velocity
    prediction = None
    if data_points and avg_velocity > 0:
        remaining = data_points[-1]["remaining"]
        if remaining > 0:
            periods_to_complete = remaining / avg_velocity
            if granularity == "day":
                predicted_date = end_date + timedelta(days=int(periods_to_complete))
            elif granularity == "week":
                predicted_date = end_date + timedelta(weeks=int(periods_to_complete))
            else:
                predicted_date = end_date + timedelta(days=int(periods_to_complete * 30))

            prediction = {
                "estimated_completion": str(predicted_date),
                "remaining_items": remaining,
                "periods_to_complete": round(periods_to_complete, 1),
            }

    # Build ideal line (linear progress from start to target)
    ideal_line = []
    if data_points:
        total_scope = data_points[-1]["scope"]
        for i, point in enumerate(data_points):
            ideal_progress = round((i + 1) / len(data_points) * total_scope, 1)
            ideal_line.append({"date": point["date"], "ideal": ideal_progress})

    return jsonify(
        {
            "data_points": data_points,
            "ideal_line": ideal_line,
            "config": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "granularity": granularity,
                "metric": metric,
                "milestone_id": milestone_id,
                "project_id": project_id,
            },
            "summary": {
                "total_items": total_features + total_bugs,
                "total_features": total_features,
                "total_bugs": total_bugs,
                "completed_features": completed_features,
                "completed_bugs": completed_bugs,
                "total_completed": completed_features + completed_bugs,
                "completion_percent": round(
                    ((completed_features + completed_bugs) / (total_features + total_bugs) * 100)
                    if (total_features + total_bugs) > 0
                    else 0,
                    1,
                ),
                "avg_velocity": avg_velocity,
                "velocity_unit": f"items/{granularity}",
            },
            "prediction": prediction,
        }
    )


@gantt_bp.route("/burnup/<int:milestone_id>", methods=["GET"])
@require_auth
def get_milestone_burnup(milestone_id):
    """Get burnup chart data for a specific milestone.

    Convenience endpoint that calls /burnup with milestone_id preset.

    Query params:
        start_date: Start date for chart (optional)
        end_date: End date for chart (optional)
        granularity: 'day', 'week', 'month' (default 'day')
        metric: 'count', 'story_points', 'hours' (default 'count')

    Returns:
        Burnup chart data for the milestone
    """
    conn = get_db_connection()

    # Verify milestone exists
    milestone = conn.execute(
        "SELECT id, name, target_date, created_at FROM milestones WHERE id = ?", (milestone_id,)
    ).fetchone()

    if not milestone:
        return jsonify({"error": "Milestone not found"}), 404

    # Set default dates based on milestone
    args = request.args.to_dict()
    args["milestone_id"] = str(milestone_id)

    # Use milestone dates if not specified
    if not args.get("start_date") and milestone["created_at"]:
        start = str(milestone["created_at"]).split("T")[0].split(" ")[0]
        args["start_date"] = start

    if not args.get("end_date") and milestone["target_date"]:
        args["end_date"] = str(milestone["target_date"])

    # Reconstruct request args and call main endpoint
    from flask import request as flask_request
    from werkzeug.datastructures import ImmutableMultiDict

    # We need to modify the request args temporarily
    original_args = flask_request.args
    try:
        # This is a workaround - call the logic directly instead
        request.args = ImmutableMultiDict(args)
        return get_burnup_chart()
    finally:
        request.args = original_args


@gantt_bp.route("/burndown", methods=["GET"])
@require_auth
def get_burndown_chart():
    """Get burndown chart data (inverse of burnup).

    Shows remaining work over time instead of completed work.

    Query params:
        Same as /burnup endpoint

    Returns:
        Burndown chart data with remaining work series
    """
    # Get burnup data first
    milestone_id = request.args.get("milestone_id", type=int)
    project_id = request.args.get("project_id", type=int)
    granularity = request.args.get("granularity", "day")
    metric = request.args.get("metric", "count")

    # Call burnup logic to get base data
    from flask import g

    # Store current response
    burnup_response = get_burnup_chart()
    burnup_data = burnup_response.get_json()

    if "error" in burnup_data:
        return burnup_response

    # Transform to burndown format
    data_points = burnup_data.get("data_points", [])
    burndown_points = []

    # Get initial scope (first point where scope > 0)
    initial_scope = data_points[0]["scope"] if data_points else 0

    for point in data_points:
        burndown_points.append(
            {
                "date": point["date"],
                "remaining": point["remaining"],
                "scope_change": point["scope"] - initial_scope,
                "completed": point["completed"],
                "ideal_remaining": initial_scope
                - (
                    burnup_data["ideal_line"][data_points.index(point)]["ideal"]
                    if data_points.index(point) < len(burnup_data["ideal_line"])
                    else 0
                ),
            }
        )

    return jsonify(
        {
            "data_points": burndown_points,
            "config": burnup_data["config"],
            "summary": burnup_data["summary"],
            "prediction": burnup_data["prediction"],
            "initial_scope": initial_scope,
        }
    )
