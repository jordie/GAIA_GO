"""
Custom Report Builder Module

Provides functions for creating, managing, and running custom reports
that can query across projects, tasks, bugs, and other entities.

Features:
- Multiple data sources (projects, features, bugs, tasks, errors, nodes, etc.)
- Flexible filtering with multiple operators
- Aggregation functions (COUNT, SUM, AVG, MIN, MAX, GROUP_CONCAT)
- JOIN support for cross-table queries
- Time range presets and custom date ranges
- Report scheduling and history
- CSV/JSON export
- Report templates
"""

import csv
import io
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Available data sources for reports
REPORT_DATA_SOURCES = {
    "projects": {
        "table": "projects",
        "fields": [
            "id",
            "name",
            "description",
            "status",
            "priority",
            "source_path",
            "created_at",
            "updated_at",
        ],
        "description": "Project data",
        "joins": {
            "milestones": "LEFT JOIN milestones ON milestones.project_id = projects.id",
            "features": "LEFT JOIN features ON features.project_id = projects.id",
            "bugs": "LEFT JOIN bugs ON bugs.project_id = projects.id",
        },
    },
    "milestones": {
        "table": "milestones",
        "fields": [
            "id",
            "project_id",
            "name",
            "description",
            "status",
            "target_date",
            "priority",
            "created_at",
        ],
        "description": "Milestone data",
        "joins": {
            "projects": "LEFT JOIN projects ON projects.id = milestones.project_id",
            "features": "LEFT JOIN features ON features.milestone_id = milestones.id",
            "bugs": "LEFT JOIN bugs ON bugs.milestone_id = milestones.id",
        },
    },
    "features": {
        "table": "features",
        "fields": [
            "id",
            "project_id",
            "milestone_id",
            "name",
            "description",
            "status",
            "priority",
            "effort",
            "assigned_to",
            "created_at",
            "updated_at",
        ],
        "description": "Feature data",
        "joins": {
            "projects": "LEFT JOIN projects ON projects.id = features.project_id",
            "milestones": "LEFT JOIN milestones ON milestones.id = features.milestone_id",
        },
    },
    "bugs": {
        "table": "bugs",
        "fields": [
            "id",
            "project_id",
            "milestone_id",
            "title",
            "description",
            "status",
            "severity",
            "priority",
            "assigned_to",
            "created_at",
            "updated_at",
            "resolved_at",
        ],
        "description": "Bug data",
        "joins": {
            "projects": "LEFT JOIN projects ON projects.id = bugs.project_id",
            "milestones": "LEFT JOIN milestones ON milestones.id = bugs.milestone_id",
        },
    },
    "tasks": {
        "table": "task_queue",
        "fields": [
            "id",
            "task_type",
            "name",
            "description",
            "status",
            "priority",
            "assigned_worker",
            "created_at",
            "started_at",
            "completed_at",
            "result",
            "retries",
        ],
        "description": "Task queue data",
        "joins": {"workers": "LEFT JOIN workers ON workers.id = task_queue.assigned_worker"},
    },
    "errors": {
        "table": "errors",
        "fields": [
            "id",
            "node_id",
            "project_id",
            "error_type",
            "message",
            "source",
            "status",
            "occurrence_count",
            "first_seen",
            "last_seen",
            "resolved_at",
        ],
        "description": "Error log data",
        "joins": {
            "projects": "LEFT JOIN projects ON projects.id = errors.project_id",
            "nodes": "LEFT JOIN nodes ON nodes.id = errors.node_id",
        },
    },
    "nodes": {
        "table": "nodes",
        "fields": [
            "id",
            "name",
            "hostname",
            "ip_address",
            "status",
            "cpu_usage",
            "memory_usage",
            "disk_usage",
            "last_heartbeat",
            "created_at",
        ],
        "description": "Cluster node data",
        "joins": {"workers": "LEFT JOIN workers ON workers.node_id = nodes.id"},
    },
    "workers": {
        "table": "workers",
        "fields": [
            "id",
            "worker_type",
            "node_id",
            "status",
            "current_task_id",
            "tasks_completed",
            "tasks_failed",
            "last_heartbeat",
            "created_at",
        ],
        "description": "Worker data",
        "joins": {
            "nodes": "LEFT JOIN nodes ON nodes.id = workers.node_id",
            "tasks": "LEFT JOIN task_queue ON task_queue.id = workers.current_task_id",
        },
    },
    "activity": {
        "table": "activity_log",
        "fields": [
            "id",
            "user_id",
            "action",
            "entity_type",
            "entity_id",
            "details",
            "ip_address",
            "created_at",
        ],
        "description": "Activity log data",
        "joins": {},
    },
    "devops_tasks": {
        "table": "devops_tasks",
        "fields": [
            "id",
            "project_id",
            "title",
            "description",
            "task_type",
            "status",
            "priority",
            "assigned_to",
            "schedule",
            "last_run",
            "next_run",
            "created_at",
        ],
        "description": "DevOps tasks and automation",
        "joins": {"projects": "LEFT JOIN projects ON projects.id = devops_tasks.project_id"},
    },
    "deployments": {
        "table": "deployments",
        "fields": [
            "id",
            "deployment_id",
            "tag",
            "target_environment",
            "status",
            "tests_required",
            "tests_passed",
            "deployed_by",
            "error_message",
            "started_at",
            "completed_at",
        ],
        "description": "Deployment history",
        "joins": {},
    },
    "tmux_sessions": {
        "table": "tmux_sessions",
        "fields": [
            "id",
            "session_name",
            "node_id",
            "status",
            "window_count",
            "created_at",
            "last_activity",
        ],
        "description": "tmux session data",
        "joins": {"nodes": "LEFT JOIN nodes ON nodes.id = tmux_sessions.node_id"},
    },
    "sprints": {
        "table": "sprints",
        "fields": [
            "id",
            "project_id",
            "name",
            "goal",
            "status",
            "start_date",
            "end_date",
            "velocity",
            "created_at",
        ],
        "description": "Sprint data",
        "joins": {"projects": "LEFT JOIN projects ON projects.id = sprints.project_id"},
    },
    "worklogs": {
        "table": "worklogs",
        "fields": [
            "id",
            "user_id",
            "entity_type",
            "entity_id",
            "hours",
            "description",
            "date",
            "created_at",
        ],
        "description": "Time tracking worklogs",
        "joins": {},
    },
}

# Available aggregation functions
AGGREGATION_FUNCTIONS = ["COUNT", "SUM", "AVG", "MIN", "MAX", "GROUP_CONCAT"]

# Available filter operators
FILTER_OPERATORS = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "not_like": "NOT LIKE",
    "in": "IN",
    "not_in": "NOT IN",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
    "between": "BETWEEN",
}

# Time range presets
TIME_RANGES = {
    "today": {"days": 0},
    "yesterday": {"days": 1, "offset": 1},
    "last_7_days": {"days": 7},
    "last_30_days": {"days": 30},
    "last_90_days": {"days": 90},
    "this_week": {"week": True},
    "this_month": {"month": True},
    "this_quarter": {"quarter": True},
    "this_year": {"year": True},
}


def get_data_sources() -> Dict:
    """Get available data sources for reports."""
    return REPORT_DATA_SOURCES


def get_reports(conn, user_id: str = None, include_shared: bool = True) -> List[Dict]:
    """Get all custom reports.

    Args:
        conn: Database connection
        user_id: Filter by owner (optional)
        include_shared: Include reports shared with user

    Returns:
        List of report configurations
    """
    conn.row_factory = sqlite3.Row

    query = """
        SELECT r.*, u.username as owner_name,
               (SELECT COUNT(*) FROM report_runs WHERE report_id = r.id) as run_count,
               (SELECT MAX(run_at) FROM report_runs WHERE report_id = r.id) as last_run
        FROM custom_reports r
        LEFT JOIN users u ON r.owner_id = u.id
        WHERE 1=1
    """
    params = []

    if user_id is not None:
        if include_shared:
            query += " AND (r.owner_id = ? OR r.is_public = 1)"
        else:
            query += " AND r.owner_id = ?"
        params.append(user_id)

    query += " ORDER BY r.name"

    rows = conn.execute(query, params).fetchall()
    reports = []
    for row in rows:
        report = dict(row)
        report["config"] = json.loads(report["config"]) if report.get("config") else {}
        report["columns"] = json.loads(report["columns"]) if report.get("columns") else []
        report["filters"] = json.loads(report["filters"]) if report.get("filters") else []
        report["schedule"] = json.loads(report["schedule"]) if report.get("schedule") else None
        reports.append(report)
    return reports


def get_report(conn, report_id: int) -> Optional[Dict]:
    """Get a specific report by ID."""
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT r.*, u.username as owner_name
        FROM custom_reports r
        LEFT JOIN users u ON r.owner_id = u.id
        WHERE r.id = ?
    """,
        (report_id,),
    ).fetchone()

    if not row:
        return None

    report = dict(row)
    report["config"] = json.loads(report["config"]) if report.get("config") else {}
    report["columns"] = json.loads(report["columns"]) if report.get("columns") else []
    report["filters"] = json.loads(report["filters"]) if report.get("filters") else []
    report["schedule"] = json.loads(report["schedule"]) if report.get("schedule") else None
    return report


def create_report(
    conn,
    name: str,
    data_source: str,
    columns: List[Dict],
    owner_id: int = None,
    description: str = None,
    filters: List[Dict] = None,
    group_by: List[str] = None,
    order_by: List[Dict] = None,
    limit: int = None,
    is_public: bool = False,
    config: Dict = None,
) -> int:
    """Create a new custom report.

    Args:
        conn: Database connection
        name: Report name
        data_source: Primary data source (table)
        columns: List of column definitions
        owner_id: Owner user ID
        description: Report description
        filters: List of filter conditions
        group_by: Fields to group by
        order_by: Sort order
        limit: Result limit
        is_public: Whether report is public
        config: Additional configuration

    Returns:
        ID of created report
    """
    if data_source not in REPORT_DATA_SOURCES:
        raise ValueError(f"Invalid data source: {data_source}")

    # Validate columns
    valid_fields = REPORT_DATA_SOURCES[data_source]["fields"]
    for col in columns:
        field = col.get("field", "").split(".")[-1]  # Handle table.field format
        if field not in valid_fields and not col.get("aggregate"):
            # Allow aggregate functions
            pass

    full_config = config or {}
    full_config["data_source"] = data_source
    full_config["group_by"] = group_by or []
    full_config["order_by"] = order_by or []
    full_config["limit"] = limit

    cursor = conn.execute(
        """
        INSERT INTO custom_reports
        (name, description, data_source, columns, filters, config, owner_id, is_public)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            name,
            description,
            data_source,
            json.dumps(columns),
            json.dumps(filters or []),
            json.dumps(full_config),
            owner_id,
            1 if is_public else 0,
        ),
    )
    return cursor.lastrowid


def update_report(conn, report_id: int, **kwargs) -> bool:
    """Update a report.

    Args:
        conn: Database connection
        report_id: Report ID
        **kwargs: Fields to update

    Returns:
        True if updated, False if not found
    """
    updates = []
    params = []

    field_mapping = {
        "name": "name",
        "description": "description",
        "data_source": "data_source",
        "is_public": "is_public",
    }

    for key, column in field_mapping.items():
        if key in kwargs:
            updates.append(f"{column} = ?")
            value = kwargs[key]
            if key == "is_public":
                value = 1 if value else 0
            params.append(value)

    if "columns" in kwargs:
        updates.append("columns = ?")
        params.append(json.dumps(kwargs["columns"]))

    if "filters" in kwargs:
        updates.append("filters = ?")
        params.append(json.dumps(kwargs["filters"]))

    if "config" in kwargs:
        updates.append("config = ?")
        params.append(json.dumps(kwargs["config"]))

    if "schedule" in kwargs:
        updates.append("schedule = ?")
        params.append(json.dumps(kwargs["schedule"]) if kwargs["schedule"] else None)

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(report_id)

    result = conn.execute(f"UPDATE custom_reports SET {', '.join(updates)} WHERE id = ?", params)
    return result.rowcount > 0


def delete_report(conn, report_id: int) -> bool:
    """Delete a report."""
    result = conn.execute("DELETE FROM custom_reports WHERE id = ?", (report_id,))
    return result.rowcount > 0


def build_report_query(report: Dict) -> tuple:
    """Build SQL query from report configuration.

    Args:
        report: Report configuration

    Returns:
        Tuple of (query string, parameters)
    """
    config = report.get("config", {})
    data_source = report.get("data_source") or config.get("data_source")

    if data_source not in REPORT_DATA_SOURCES:
        raise ValueError(f"Invalid data source: {data_source}")

    source_config = REPORT_DATA_SOURCES[data_source]
    table = source_config["table"]
    columns = report.get("columns", [])
    filters = report.get("filters", [])
    group_by = config.get("group_by", [])
    order_by = config.get("order_by", [])
    limit = config.get("limit")

    # Build SELECT clause
    select_parts = []
    for col in columns:
        field = col.get("field", "")
        alias = col.get("alias", "")
        aggregate = col.get("aggregate")

        if aggregate and aggregate.upper() in AGGREGATION_FUNCTIONS:
            if field == "*":
                select_parts.append(f"{aggregate.upper()}(*) AS {alias or 'count'}")
            else:
                select_parts.append(f"{aggregate.upper()}({field}) AS {alias or field}")
        else:
            if alias:
                select_parts.append(f"{field} AS {alias}")
            else:
                select_parts.append(field)

    if not select_parts:
        select_parts = ["*"]

    # Build WHERE clause
    where_parts = []
    params = []

    for f in filters:
        field = f.get("field")
        operator = f.get("operator", "eq")
        value = f.get("value")

        if not field:
            continue

        sql_op = FILTER_OPERATORS.get(operator, "=")

        if operator in ("is_null", "is_not_null"):
            where_parts.append(f"{field} {sql_op}")
        elif operator == "in":
            if isinstance(value, list):
                placeholders = ",".join(["?"] * len(value))
                where_parts.append(f"{field} IN ({placeholders})")
                params.extend(value)
        elif operator == "not_in":
            if isinstance(value, list):
                placeholders = ",".join(["?"] * len(value))
                where_parts.append(f"{field} NOT IN ({placeholders})")
                params.extend(value)
        elif operator == "between":
            if isinstance(value, list) and len(value) == 2:
                where_parts.append(f"{field} BETWEEN ? AND ?")
                params.extend(value)
        elif operator in ("like", "not_like"):
            where_parts.append(f"{field} {sql_op} ?")
            params.append(f"%{value}%")
        else:
            where_parts.append(f"{field} {sql_op} ?")
            params.append(value)

    # Build query
    query = f"SELECT {', '.join(select_parts)} FROM {table}"

    if where_parts:
        query += f" WHERE {' AND '.join(where_parts)}"

    if group_by:
        query += f" GROUP BY {', '.join(group_by)}"

    if order_by:
        order_parts = []
        for o in order_by:
            field = o.get("field")
            direction = "DESC" if o.get("desc") else "ASC"
            if field:
                order_parts.append(f"{field} {direction}")
        if order_parts:
            query += f" ORDER BY {', '.join(order_parts)}"

    if limit:
        query += f" LIMIT {int(limit)}"

    return query, params


def run_report(conn, report_id: int, runtime_filters: Dict = None) -> Dict:
    """Run a custom report and return results.

    Args:
        conn: Database connection
        report_id: Report ID
        runtime_filters: Additional filters to apply at runtime

    Returns:
        Dict with results, metadata, and timing
    """
    report = get_report(conn, report_id)
    if not report:
        return {"error": "Report not found", "results": []}

    # Apply runtime filters
    if runtime_filters:
        filters = report.get("filters", [])
        for key, value in runtime_filters.items():
            if value is not None:
                filters.append({"field": key, "operator": "eq", "value": value})
        report["filters"] = filters

    start_time = datetime.now()

    try:
        query, params = build_report_query(report)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        results = [dict(row) for row in rows]

        duration = (datetime.now() - start_time).total_seconds()

        # Log the run
        conn.execute(
            """
            INSERT INTO report_runs (report_id, row_count, duration_seconds, status)
            VALUES (?, ?, ?, 'success')
        """,
            (report_id, len(results), duration),
        )

        return {
            "report_id": report_id,
            "report_name": report["name"],
            "data_source": report.get("data_source"),
            "results": results,
            "row_count": len(results),
            "duration_seconds": round(duration, 3),
            "run_at": datetime.now().isoformat(),
            "columns": report.get("columns", []),
        }

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()

        # Log the failed run
        conn.execute(
            """
            INSERT INTO report_runs (report_id, row_count, duration_seconds, status, error)
            VALUES (?, 0, ?, 'failed', ?)
        """,
            (report_id, duration, str(e)),
        )

        logger.error(f"Report {report_id} failed: {e}")
        return {
            "report_id": report_id,
            "report_name": report.get("name"),
            "error": str(e),
            "results": [],
            "row_count": 0,
            "duration_seconds": round(duration, 3),
        }


def preview_report(conn, report_config: Dict, limit: int = 10) -> Dict:
    """Preview a report without saving it.

    Args:
        conn: Database connection
        report_config: Report configuration (same format as create_report)
        limit: Maximum rows to return

    Returns:
        Dict with preview results
    """
    # Build temporary report structure
    report = {
        "data_source": report_config.get("data_source"),
        "columns": report_config.get("columns", []),
        "filters": report_config.get("filters", []),
        "config": {
            "data_source": report_config.get("data_source"),
            "group_by": report_config.get("group_by", []),
            "order_by": report_config.get("order_by", []),
            "limit": min(limit, 100),  # Cap preview at 100 rows
        },
    }

    start_time = datetime.now()

    try:
        query, params = build_report_query(report)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        results = [dict(row) for row in rows]

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "preview": True,
            "results": results,
            "row_count": len(results),
            "duration_seconds": round(duration, 3),
            "query": query,  # Include query for debugging
        }

    except Exception as e:
        logger.error(f"Report preview failed: {e}")
        return {"preview": True, "error": str(e), "results": [], "row_count": 0}


def get_report_history(conn, report_id: int, limit: int = 20) -> List[Dict]:
    """Get run history for a report.

    Args:
        conn: Database connection
        report_id: Report ID
        limit: Maximum records to return

    Returns:
        List of run records
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT * FROM report_runs
        WHERE report_id = ?
        ORDER BY run_at DESC
        LIMIT ?
    """,
        (report_id, limit),
    ).fetchall()

    return [dict(row) for row in rows]


def duplicate_report(conn, report_id: int, new_name: str, owner_id: int = None) -> int:
    """Duplicate an existing report.

    Args:
        conn: Database connection
        report_id: Report ID to duplicate
        new_name: Name for the new report
        owner_id: Owner of the new report

    Returns:
        ID of the new report
    """
    original = get_report(conn, report_id)
    if not original:
        raise ValueError("Report not found")

    return create_report(
        conn,
        name=new_name,
        data_source=original.get("data_source"),
        columns=original.get("columns", []),
        owner_id=owner_id,
        description=f"Copy of {original['name']}",
        filters=original.get("filters", []),
        group_by=original.get("config", {}).get("group_by", []),
        order_by=original.get("config", {}).get("order_by", []),
        limit=original.get("config", {}).get("limit"),
        is_public=False,
        config=original.get("config", {}),
    )


def schedule_report(
    conn,
    report_id: int,
    frequency: str,
    time_of_day: str = "08:00",
    day_of_week: int = None,
    day_of_month: int = None,
    recipients: List[str] = None,
    enabled: bool = True,
) -> bool:
    """Schedule a report for automatic execution.

    Args:
        conn: Database connection
        report_id: Report ID
        frequency: 'daily', 'weekly', 'monthly'
        time_of_day: Time to run (HH:MM)
        day_of_week: Day of week for weekly (0=Monday)
        day_of_month: Day of month for monthly
        recipients: List of email addresses
        enabled: Whether schedule is enabled

    Returns:
        True if updated
    """
    schedule = {"frequency": frequency, "time_of_day": time_of_day, "enabled": enabled}

    if frequency == "weekly" and day_of_week is not None:
        schedule["day_of_week"] = day_of_week
    elif frequency == "monthly" and day_of_month is not None:
        schedule["day_of_month"] = day_of_month

    if recipients:
        schedule["recipients"] = recipients

    return update_report(conn, report_id, schedule=schedule)


def export_report_config(conn, report_id: int) -> Dict:
    """Export report configuration for backup or sharing.

    Args:
        conn: Database connection
        report_id: Report ID

    Returns:
        Exportable report configuration
    """
    report = get_report(conn, report_id)
    if not report:
        return None

    # Remove internal fields
    export = {
        "name": report["name"],
        "description": report.get("description"),
        "data_source": report.get("data_source"),
        "columns": report.get("columns", []),
        "filters": report.get("filters", []),
        "config": report.get("config", {}),
        "exported_at": datetime.now().isoformat(),
        "version": "1.0",
    }

    return export


def import_report_config(conn, config: Dict, owner_id: int) -> int:
    """Import a report configuration.

    Args:
        conn: Database connection
        config: Exported report configuration
        owner_id: Owner of the imported report

    Returns:
        ID of the created report
    """
    return create_report(
        conn,
        name=config.get("name", "Imported Report"),
        data_source=config.get("data_source", "projects"),
        columns=config.get("columns", []),
        owner_id=owner_id,
        description=config.get("description"),
        filters=config.get("filters", []),
        group_by=config.get("config", {}).get("group_by", []),
        order_by=config.get("config", {}).get("order_by", []),
        limit=config.get("config", {}).get("limit"),
        is_public=False,
        config=config.get("config", {}),
    )


# =============================================================================
# Time Range Helpers
# =============================================================================


def get_time_range_dates(time_range: str) -> Tuple[datetime, datetime]:
    """Convert a time range preset to start and end dates.

    Args:
        time_range: One of the TIME_RANGES keys

    Returns:
        Tuple of (start_date, end_date)
    """
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if time_range == "today":
        return today, now
    elif time_range == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, today
    elif time_range == "last_7_days":
        return today - timedelta(days=7), now
    elif time_range == "last_30_days":
        return today - timedelta(days=30), now
    elif time_range == "last_90_days":
        return today - timedelta(days=90), now
    elif time_range == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, now
    elif time_range == "this_month":
        start = today.replace(day=1)
        return start, now
    elif time_range == "this_quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_month, day=1)
        return start, now
    elif time_range == "this_year":
        start = today.replace(month=1, day=1)
        return start, now
    else:
        # Default to last 30 days
        return today - timedelta(days=30), now


def apply_time_range_filter(filters: List[Dict], date_field: str, time_range: str) -> List[Dict]:
    """Add a time range filter to the filter list.

    Args:
        filters: Existing list of filters
        date_field: Field name to filter on
        time_range: Time range preset name

    Returns:
        Updated filter list
    """
    start, end = get_time_range_dates(time_range)
    filters.append(
        {"field": date_field, "operator": "between", "value": [start.isoformat(), end.isoformat()]}
    )
    return filters


# =============================================================================
# CSV Export
# =============================================================================


def export_to_csv(results: List[Dict], columns: List[Dict] = None) -> str:
    """Export report results to CSV format.

    Args:
        results: List of result dictionaries
        columns: Optional column definitions for header names

    Returns:
        CSV string
    """
    if not results:
        return ""

    output = io.StringIO()

    # Determine headers
    if columns:
        headers = [col.get("alias") or col.get("field") for col in columns]
    else:
        headers = list(results[0].keys())

    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()

    for row in results:
        # Map column aliases if needed
        if columns:
            mapped_row = {}
            for col in columns:
                field = col.get("field")
                alias = col.get("alias") or field
                if field in row:
                    mapped_row[alias] = row[field]
                elif alias in row:
                    mapped_row[alias] = row[alias]
            writer.writerow(mapped_row)
        else:
            writer.writerow(row)

    return output.getvalue()


def run_report_csv(conn, report_id: int, runtime_filters: Dict = None) -> str:
    """Run a report and return results as CSV.

    Args:
        conn: Database connection
        report_id: Report ID
        runtime_filters: Additional runtime filters

    Returns:
        CSV string of results
    """
    result = run_report(conn, report_id, runtime_filters)
    if result.get("error"):
        return f"Error: {result['error']}"

    return export_to_csv(result.get("results", []), result.get("columns", []))


# =============================================================================
# Computed Fields
# =============================================================================

COMPUTED_FIELDS = {
    "age_days": {
        "expression": "CAST((julianday('now') - julianday(created_at)) AS INTEGER)",
        "description": "Days since creation",
    },
    "age_hours": {
        "expression": "CAST((julianday('now') - julianday(created_at)) * 24 AS INTEGER)",
        "description": "Hours since creation",
    },
    "resolution_time_days": {
        "expression": "CAST((julianday(resolved_at) - julianday(created_at)) AS INTEGER)",
        "description": "Days to resolution (bugs/errors)",
        "requires_fields": ["resolved_at", "created_at"],
    },
    "completion_time_hours": {
        "expression": "CAST((julianday(completed_at) - julianday(started_at)) * 24 AS REAL)",
        "description": "Hours to completion (tasks)",
        "requires_fields": ["completed_at", "started_at"],
    },
    "is_overdue": {
        "expression": "CASE WHEN target_date < date('now') AND status NOT IN ('completed', 'done', 'closed') THEN 1 ELSE 0 END",
        "description": "Whether item is past due date",
        "requires_fields": ["target_date", "status"],
    },
    "days_until_due": {
        "expression": "CAST((julianday(target_date) - julianday('now')) AS INTEGER)",
        "description": "Days until target date",
        "requires_fields": ["target_date"],
    },
    "success_rate": {
        "expression": "CAST(tasks_completed AS REAL) / NULLIF(tasks_completed + tasks_failed, 0) * 100",
        "description": "Task success percentage",
        "requires_fields": ["tasks_completed", "tasks_failed"],
    },
}


def get_computed_fields() -> Dict:
    """Get available computed fields."""
    return COMPUTED_FIELDS


# =============================================================================
# Report Templates
# =============================================================================

REPORT_TEMPLATES = {
    "project_summary": {
        "name": "Project Summary",
        "description": "Overview of all projects with feature and bug counts",
        "data_source": "projects",
        "columns": [
            {"field": "projects.name", "alias": "project_name"},
            {"field": "projects.status", "alias": "status"},
            {
                "field": "*",
                "aggregate": "COUNT",
                "alias": "feature_count",
                "join_table": "features",
            },
        ],
        "config": {
            "group_by": ["projects.id", "projects.name", "projects.status"],
            "order_by": [{"field": "projects.name", "desc": False}],
        },
    },
    "bug_status_report": {
        "name": "Bug Status Report",
        "description": "Bugs grouped by status and severity",
        "data_source": "bugs",
        "columns": [
            {"field": "status"},
            {"field": "severity"},
            {"field": "*", "aggregate": "COUNT", "alias": "count"},
        ],
        "config": {
            "group_by": ["status", "severity"],
            "order_by": [{"field": "count", "desc": True}],
        },
    },
    "task_performance": {
        "name": "Task Performance Report",
        "description": "Task completion metrics by type",
        "data_source": "tasks",
        "columns": [
            {"field": "task_type"},
            {"field": "status"},
            {"field": "*", "aggregate": "COUNT", "alias": "count"},
            {"field": "retries", "aggregate": "AVG", "alias": "avg_retries"},
        ],
        "config": {
            "group_by": ["task_type", "status"],
            "order_by": [{"field": "task_type", "desc": False}],
        },
    },
    "error_trends": {
        "name": "Error Trends",
        "description": "Error occurrences by type and source",
        "data_source": "errors",
        "columns": [
            {"field": "error_type"},
            {"field": "source"},
            {"field": "occurrence_count", "aggregate": "SUM", "alias": "total_occurrences"},
            {"field": "*", "aggregate": "COUNT", "alias": "unique_errors"},
        ],
        "filters": [{"field": "status", "operator": "ne", "value": "resolved"}],
        "config": {
            "group_by": ["error_type", "source"],
            "order_by": [{"field": "total_occurrences", "desc": True}],
            "limit": 50,
        },
    },
    "node_health": {
        "name": "Node Health Report",
        "description": "Current health metrics for all cluster nodes",
        "data_source": "nodes",
        "columns": [
            {"field": "name"},
            {"field": "hostname"},
            {"field": "status"},
            {"field": "cpu_usage"},
            {"field": "memory_usage"},
            {"field": "disk_usage"},
            {"field": "last_heartbeat"},
        ],
        "config": {"order_by": [{"field": "name", "desc": False}]},
    },
    "worker_productivity": {
        "name": "Worker Productivity",
        "description": "Task completion statistics per worker",
        "data_source": "workers",
        "columns": [
            {"field": "workers.id", "alias": "worker_id"},
            {"field": "workers.worker_type"},
            {"field": "workers.status"},
            {"field": "workers.tasks_completed"},
            {"field": "workers.tasks_failed"},
        ],
        "config": {"order_by": [{"field": "tasks_completed", "desc": True}]},
    },
    "activity_audit": {
        "name": "Activity Audit Log",
        "description": "Recent user activities for audit purposes",
        "data_source": "activity",
        "columns": [
            {"field": "created_at"},
            {"field": "action"},
            {"field": "entity_type"},
            {"field": "entity_id"},
            {"field": "user_id"},
            {"field": "ip_address"},
        ],
        "config": {"order_by": [{"field": "created_at", "desc": True}], "limit": 100},
    },
    "deployment_history": {
        "name": "Deployment History",
        "description": "Recent deployments with status",
        "data_source": "deployments",
        "columns": [
            {"field": "deployment_id"},
            {"field": "tag"},
            {"field": "target_environment"},
            {"field": "status"},
            {"field": "deployed_by"},
            {"field": "started_at"},
            {"field": "completed_at"},
        ],
        "config": {"order_by": [{"field": "started_at", "desc": True}], "limit": 50},
    },
    "milestone_progress": {
        "name": "Milestone Progress",
        "description": "Milestone status with feature counts",
        "data_source": "milestones",
        "columns": [
            {"field": "milestones.name", "alias": "milestone"},
            {"field": "milestones.status"},
            {"field": "milestones.target_date"},
            {"field": "projects.name", "alias": "project"},
        ],
        "config": {"joins": ["projects"], "order_by": [{"field": "target_date", "desc": False}]},
    },
    "sprint_velocity": {
        "name": "Sprint Velocity",
        "description": "Sprint performance metrics",
        "data_source": "sprints",
        "columns": [
            {"field": "name"},
            {"field": "status"},
            {"field": "start_date"},
            {"field": "end_date"},
            {"field": "velocity"},
            {"field": "goal"},
        ],
        "config": {"order_by": [{"field": "start_date", "desc": True}], "limit": 20},
    },
}


def get_report_templates() -> Dict:
    """Get available report templates."""
    return {
        key: {
            "id": key,
            "name": template["name"],
            "description": template["description"],
            "data_source": template["data_source"],
        }
        for key, template in REPORT_TEMPLATES.items()
    }


def create_report_from_template(
    conn, template_id: str, name: str = None, owner_id: int = None, **overrides
) -> int:
    """Create a new report from a template.

    Args:
        conn: Database connection
        template_id: Template identifier
        name: Custom name for the report (optional)
        owner_id: Owner user ID
        **overrides: Override any template settings

    Returns:
        ID of created report
    """
    if template_id not in REPORT_TEMPLATES:
        raise ValueError(f"Unknown template: {template_id}")

    template = REPORT_TEMPLATES[template_id]

    return create_report(
        conn,
        name=name or template["name"],
        data_source=overrides.get("data_source", template["data_source"]),
        columns=overrides.get("columns", template.get("columns", [])),
        owner_id=owner_id,
        description=template.get("description"),
        filters=overrides.get("filters", template.get("filters", [])),
        group_by=overrides.get("group_by", template.get("config", {}).get("group_by", [])),
        order_by=overrides.get("order_by", template.get("config", {}).get("order_by", [])),
        limit=overrides.get("limit", template.get("config", {}).get("limit")),
        is_public=overrides.get("is_public", False),
        config=template.get("config", {}),
    )


# =============================================================================
# Enhanced Query Builder with JOINs
# =============================================================================


def build_report_query_with_joins(report: Dict) -> Tuple[str, List]:
    """Build SQL query with JOIN support.

    Args:
        report: Report configuration with optional joins

    Returns:
        Tuple of (query string, parameters)
    """
    config = report.get("config", {})
    data_source = report.get("data_source") or config.get("data_source")

    if data_source not in REPORT_DATA_SOURCES:
        raise ValueError(f"Invalid data source: {data_source}")

    source_config = REPORT_DATA_SOURCES[data_source]
    table = source_config["table"]
    columns = report.get("columns", [])
    filters = report.get("filters", [])
    group_by = config.get("group_by", [])
    order_by = config.get("order_by", [])
    joins = config.get("joins", [])
    limit = config.get("limit")

    # Build SELECT clause
    select_parts = []
    for col in columns:
        field = col.get("field", "")
        alias = col.get("alias", "")
        aggregate = col.get("aggregate")

        if aggregate and aggregate.upper() in AGGREGATION_FUNCTIONS:
            if field == "*":
                select_parts.append(f"{aggregate.upper()}(*) AS {alias or 'count'}")
            else:
                select_parts.append(
                    f"{aggregate.upper()}({field}) AS {alias or field.replace('.', '_')}"
                )
        else:
            if alias:
                select_parts.append(f"{field} AS {alias}")
            else:
                select_parts.append(field)

    if not select_parts:
        select_parts = [f"{table}.*"]

    # Build FROM clause with JOINs
    from_clause = table
    available_joins = source_config.get("joins", {})

    for join_table in joins:
        if join_table in available_joins:
            from_clause += f" {available_joins[join_table]}"

    # Build WHERE clause
    where_parts = []
    params = []

    for f in filters:
        field = f.get("field")
        operator = f.get("operator", "eq")
        value = f.get("value")

        if not field:
            continue

        sql_op = FILTER_OPERATORS.get(operator, "=")

        if operator in ("is_null", "is_not_null"):
            where_parts.append(f"{field} {sql_op}")
        elif operator == "in":
            if isinstance(value, list):
                placeholders = ",".join(["?"] * len(value))
                where_parts.append(f"{field} IN ({placeholders})")
                params.extend(value)
        elif operator == "not_in":
            if isinstance(value, list):
                placeholders = ",".join(["?"] * len(value))
                where_parts.append(f"{field} NOT IN ({placeholders})")
                params.extend(value)
        elif operator == "between":
            if isinstance(value, list) and len(value) == 2:
                where_parts.append(f"{field} BETWEEN ? AND ?")
                params.extend(value)
        elif operator in ("like", "not_like"):
            where_parts.append(f"{field} {sql_op} ?")
            params.append(f"%{value}%")
        else:
            where_parts.append(f"{field} {sql_op} ?")
            params.append(value)

    # Build complete query
    query = f"SELECT {', '.join(select_parts)} FROM {from_clause}"

    if where_parts:
        query += f" WHERE {' AND '.join(where_parts)}"

    if group_by:
        query += f" GROUP BY {', '.join(group_by)}"

    if order_by:
        order_parts = []
        for o in order_by:
            field = o.get("field")
            direction = "DESC" if o.get("desc") else "ASC"
            if field:
                order_parts.append(f"{field} {direction}")
        if order_parts:
            query += f" ORDER BY {', '.join(order_parts)}"

    if limit:
        query += f" LIMIT {int(limit)}"

    return query, params


# =============================================================================
# Quick Report Builder (Convenience Functions)
# =============================================================================


def quick_count(conn, data_source: str, filters: List[Dict] = None) -> int:
    """Quick count of records matching filters.

    Args:
        conn: Database connection
        data_source: Data source name
        filters: Optional filters

    Returns:
        Count of matching records
    """
    report = {
        "data_source": data_source,
        "columns": [{"field": "*", "aggregate": "COUNT", "alias": "count"}],
        "filters": filters or [],
        "config": {"data_source": data_source},
    }

    query, params = build_report_query(report)
    result = conn.execute(query, params).fetchone()
    return result[0] if result else 0


def quick_aggregate(
    conn,
    data_source: str,
    field: str,
    aggregate: str = "COUNT",
    filters: List[Dict] = None,
    group_by: str = None,
) -> List[Dict]:
    """Quick aggregation query.

    Args:
        conn: Database connection
        data_source: Data source name
        field: Field to aggregate
        aggregate: Aggregation function
        filters: Optional filters
        group_by: Optional grouping field

    Returns:
        List of aggregated results
    """
    columns = [{"field": field, "aggregate": aggregate, "alias": "value"}]

    if group_by:
        columns.insert(0, {"field": group_by})

    report = {
        "data_source": data_source,
        "columns": columns,
        "filters": filters or [],
        "config": {
            "data_source": data_source,
            "group_by": [group_by] if group_by else [],
            "order_by": [{"field": "value", "desc": True}],
        },
    }

    query, params = build_report_query(report)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
