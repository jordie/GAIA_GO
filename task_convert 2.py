"""
Task Conversion Module
Convert tasks between different types (task, bug, feature, etc.)
"""

import json
from datetime import datetime

# Supported task types and their target tables
TASK_TYPES = {
    "task": {
        "table": "task_queue",
        "display": "Task",
        "fields": [
            "title",
            "description",
            "status",
            "priority",
            "project_id",
            "assigned_to",
            "due_date",
            "estimated_hours",
            "tags",
        ],
    },
    "bug": {
        "table": "bugs",
        "display": "Bug",
        "fields": [
            "title",
            "description",
            "status",
            "severity",
            "project_id",
            "assigned_to",
            "due_date",
            "steps_to_reproduce",
            "environment",
        ],
    },
    "feature": {
        "table": "features",
        "display": "Feature",
        "fields": [
            "title",
            "description",
            "status",
            "priority",
            "project_id",
            "assigned_to",
            "due_date",
            "acceptance_criteria",
            "estimated_effort",
        ],
    },
    "devops_task": {
        "table": "devops_tasks",
        "display": "DevOps Task",
        "fields": [
            "title",
            "description",
            "status",
            "priority",
            "project_id",
            "assigned_to",
            "due_date",
            "task_type",
            "environment",
        ],
    },
}

# Field mappings between types
FIELD_MAPPINGS = {
    # Priority to severity mapping
    ("task", "bug"): {
        "priority": lambda v: {
            "critical": "critical",
            "high": "major",
            "medium": "minor",
            "low": "trivial",
        }.get(v, "minor")
    },
    ("feature", "bug"): {
        "priority": lambda v: {
            "critical": "critical",
            "high": "major",
            "medium": "minor",
            "low": "trivial",
        }.get(v, "minor")
    },
    # Severity to priority mapping
    ("bug", "task"): {
        "severity": lambda v: {
            "critical": "critical",
            "major": "high",
            "minor": "medium",
            "trivial": "low",
        }.get(v, "medium")
    },
    ("bug", "feature"): {
        "severity": lambda v: {
            "critical": "critical",
            "major": "high",
            "minor": "medium",
            "trivial": "low",
        }.get(v, "medium")
    },
}

# Status mappings between types
STATUS_MAPPINGS = {
    "task": {
        "open": "pending",
        "in_progress": "in_progress",
        "resolved": "completed",
        "closed": "completed",
        "new": "pending",
        "planning": "pending",
        "development": "in_progress",
        "testing": "in_progress",
        "done": "completed",
    },
    "bug": {
        "pending": "open",
        "in_progress": "in_progress",
        "completed": "resolved",
        "new": "open",
        "planning": "open",
        "development": "in_progress",
        "testing": "in_progress",
        "done": "resolved",
    },
    "feature": {
        "open": "planning",
        "pending": "planning",
        "in_progress": "development",
        "resolved": "done",
        "closed": "done",
        "completed": "done",
    },
    "devops_task": {
        "open": "pending",
        "in_progress": "in_progress",
        "resolved": "completed",
        "closed": "completed",
        "planning": "pending",
        "development": "in_progress",
        "done": "completed",
    },
}


def get_convertible_types(source_type):
    """Get list of types a source type can be converted to."""
    if source_type not in TASK_TYPES:
        return []
    return [t for t in TASK_TYPES.keys() if t != source_type]


def get_source_item(conn, source_type, source_id):
    """Get the source item to be converted."""
    if source_type not in TASK_TYPES:
        return None

    cursor = conn.cursor()
    table = TASK_TYPES[source_type]["table"]

    cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (source_id,))
    row = cursor.fetchone()

    return dict(row) if row else None


def map_field_value(source_type, target_type, field, value):
    """Map a field value from source type to target type."""
    # Check for custom mapping
    mapping_key = (source_type, target_type)
    if mapping_key in FIELD_MAPPINGS:
        field_mapper = FIELD_MAPPINGS[mapping_key].get(field)
        if field_mapper:
            return field_mapper(value)

    # Map status
    if field == "status" and target_type in STATUS_MAPPINGS:
        return STATUS_MAPPINGS[target_type].get(value, value)

    # Direct mapping for common fields
    return value


def convert_task(
    conn,
    source_type,
    source_id,
    target_type,
    additional_fields=None,
    keep_original=False,
    created_by=None,
):
    """Convert a task from one type to another."""
    cursor = conn.cursor()

    # Validate types
    if source_type not in TASK_TYPES:
        return {"error": f"Invalid source type: {source_type}"}
    if target_type not in TASK_TYPES:
        return {"error": f"Invalid target type: {target_type}"}
    if source_type == target_type:
        return {"error": "Source and target types must be different"}

    # Get source item
    source_item = get_source_item(conn, source_type, source_id)
    if not source_item:
        return {"error": f'{TASK_TYPES[source_type]["display"]} not found'}

    # Build target item
    target_data = {}
    source_fields = TASK_TYPES[source_type]["fields"]
    target_fields = TASK_TYPES[target_type]["fields"]

    # Map common fields
    common_fields = ["title", "description", "project_id", "assigned_to", "due_date"]
    for field in common_fields:
        if field in source_item and source_item[field] is not None:
            target_data[field] = source_item[field]

    # Map status
    if "status" in source_item:
        target_data["status"] = map_field_value(
            source_type, target_type, "status", source_item["status"]
        )

    # Map priority/severity
    if source_type == "bug" and "severity" in source_item:
        if target_type in ["task", "feature", "devops_task"]:
            target_data["priority"] = map_field_value(
                source_type, target_type, "severity", source_item["severity"]
            )
    elif "priority" in source_item:
        if target_type == "bug":
            target_data["severity"] = map_field_value(
                source_type, target_type, "priority", source_item["priority"]
            )
        else:
            target_data["priority"] = source_item["priority"]

    # Map estimated hours/effort
    if "estimated_hours" in source_item and source_item["estimated_hours"]:
        if target_type == "feature":
            target_data["estimated_effort"] = source_item["estimated_hours"]
        else:
            target_data["estimated_hours"] = source_item["estimated_hours"]
    elif "estimated_effort" in source_item and source_item["estimated_effort"]:
        if target_type != "feature":
            target_data["estimated_hours"] = source_item["estimated_effort"]
        else:
            target_data["estimated_effort"] = source_item["estimated_effort"]

    # Apply additional fields
    if additional_fields:
        target_data.update(additional_fields)

    # Add conversion metadata
    conversion_note = f"Converted from {TASK_TYPES[source_type]['display']} #{source_id}"
    if "description" in target_data and target_data["description"]:
        target_data["description"] = f"{target_data['description']}\n\n---\n{conversion_note}"
    else:
        target_data["description"] = conversion_note

    # Insert into target table
    target_table = TASK_TYPES[target_type]["table"]
    columns = list(target_data.keys())
    placeholders = ", ".join(["?" for _ in columns])
    columns_str = ", ".join(columns)

    cursor.execute(
        f"""
        INSERT INTO {target_table} ({columns_str}, created_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP)
    """,
        list(target_data.values()),
    )

    new_id = cursor.lastrowid

    # Handle original item
    if not keep_original:
        source_table = TASK_TYPES[source_type]["table"]
        # Mark as converted instead of deleting
        if source_type == "task":
            cursor.execute(
                f"""
                UPDATE {source_table}
                SET status = 'converted', metadata = ?
                WHERE id = ?
            """,
                (json.dumps({"converted_to": target_type, "converted_id": new_id}), source_id),
            )
        else:
            # For bugs/features, update status
            cursor.execute(
                f"""
                UPDATE {source_table}
                SET status = 'converted'
                WHERE id = ?
            """,
                (source_id,),
            )

    # Log conversion
    cursor.execute(
        """
        INSERT INTO task_conversions (source_type, source_id, target_type, target_id,
                                      converted_by, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """,
        (source_type, source_id, target_type, new_id, created_by),
    )

    conn.commit()

    return {
        "success": True,
        "source": {"type": source_type, "id": source_id, "title": source_item.get("title")},
        "target": {"type": target_type, "id": new_id, "title": target_data.get("title")},
        "kept_original": keep_original,
    }


def bulk_convert(
    conn,
    source_type,
    source_ids,
    target_type,
    additional_fields=None,
    keep_original=False,
    created_by=None,
):
    """Convert multiple items at once."""
    results = {"successful": [], "failed": []}

    for source_id in source_ids:
        result = convert_task(
            conn, source_type, source_id, target_type, additional_fields, keep_original, created_by
        )
        if "error" in result:
            results["failed"].append({"id": source_id, "error": result["error"]})
        else:
            results["successful"].append(result)

    return {
        "total": len(source_ids),
        "successful_count": len(results["successful"]),
        "failed_count": len(results["failed"]),
        "results": results,
    }


def get_conversion_history(conn, source_type=None, source_id=None, target_type=None, limit=50):
    """Get history of task conversions."""
    cursor = conn.cursor()

    query = "SELECT * FROM task_conversions WHERE 1=1"
    params = []

    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)

    if source_id:
        query += " AND source_id = ?"
        params.append(source_id)

    if target_type:
        query += " AND target_type = ?"
        params.append(target_type)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    conversions = [dict(row) for row in cursor.fetchall()]

    return {"conversions": conversions, "count": len(conversions)}


def get_conversion_stats(conn, start_date=None, end_date=None):
    """Get statistics on task conversions."""
    cursor = conn.cursor()

    params = []
    date_filter = ""

    if start_date:
        date_filter += " AND DATE(created_at) >= ?"
        params.append(start_date)
    if end_date:
        date_filter += " AND DATE(created_at) <= ?"
        params.append(end_date)

    # Total conversions
    cursor.execute(
        f"SELECT COUNT(*) as total FROM task_conversions WHERE 1=1 {date_filter}", params
    )
    total = cursor.fetchone()["total"]

    # By source type
    cursor.execute(
        f"""
        SELECT source_type, COUNT(*) as count
        FROM task_conversions
        WHERE 1=1 {date_filter}
        GROUP BY source_type
        ORDER BY count DESC
    """,
        params,
    )
    by_source = [dict(row) for row in cursor.fetchall()]

    # By target type
    cursor.execute(
        f"""
        SELECT target_type, COUNT(*) as count
        FROM task_conversions
        WHERE 1=1 {date_filter}
        GROUP BY target_type
        ORDER BY count DESC
    """,
        params,
    )
    by_target = [dict(row) for row in cursor.fetchall()]

    # Conversion paths
    cursor.execute(
        f"""
        SELECT source_type, target_type, COUNT(*) as count
        FROM task_conversions
        WHERE 1=1 {date_filter}
        GROUP BY source_type, target_type
        ORDER BY count DESC
    """,
        params,
    )
    paths = [dict(row) for row in cursor.fetchall()]

    return {
        "total_conversions": total,
        "by_source_type": by_source,
        "by_target_type": by_target,
        "conversion_paths": paths,
    }


def preview_conversion(conn, source_type, source_id, target_type):
    """Preview what a conversion would look like without executing it."""
    if source_type not in TASK_TYPES:
        return {"error": f"Invalid source type: {source_type}"}
    if target_type not in TASK_TYPES:
        return {"error": f"Invalid target type: {target_type}"}

    source_item = get_source_item(conn, source_type, source_id)
    if not source_item:
        return {"error": f'{TASK_TYPES[source_type]["display"]} not found'}

    # Build preview
    preview = {
        "title": source_item.get("title"),
        "description": source_item.get("description"),
        "project_id": source_item.get("project_id"),
        "assigned_to": source_item.get("assigned_to"),
        "due_date": source_item.get("due_date"),
    }

    # Map status
    if "status" in source_item:
        preview["status"] = map_field_value(
            source_type, target_type, "status", source_item["status"]
        )
        preview["original_status"] = source_item["status"]

    # Map priority/severity
    if source_type == "bug" and "severity" in source_item:
        if target_type in ["task", "feature", "devops_task"]:
            preview["priority"] = map_field_value(
                source_type, target_type, "severity", source_item["severity"]
            )
            preview["original_severity"] = source_item["severity"]
    elif "priority" in source_item:
        if target_type == "bug":
            preview["severity"] = map_field_value(
                source_type, target_type, "priority", source_item["priority"]
            )
            preview["original_priority"] = source_item["priority"]
        else:
            preview["priority"] = source_item["priority"]

    return {
        "source": {
            "type": source_type,
            "type_display": TASK_TYPES[source_type]["display"],
            "id": source_id,
            "data": source_item,
        },
        "target": {
            "type": target_type,
            "type_display": TASK_TYPES[target_type]["display"],
            "preview": preview,
            "available_fields": TASK_TYPES[target_type]["fields"],
        },
    }


def get_task_types():
    """Get available task types for conversion."""
    return {k: v["display"] for k, v in TASK_TYPES.items()}
