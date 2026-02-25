# ============================================================================
# BULK IMPORT FROM CSV WITH FIELD MAPPING
# ============================================================================

import csv
import io
import json
from datetime import datetime

IMPORT_ENTITY_SCHEMAS = {
    "projects": {
        "table": "projects",
        "required": ["name"],
        "fields": {
            "name": {"type": "string", "max_length": 255, "description": "Project name"},
            "description": {"type": "string", "description": "Project description"},
            "status": {
                "type": "enum",
                "values": ["active", "paused", "completed", "archived"],
                "default": "active",
            },
            "priority": {"type": "integer", "min": 1, "max": 5, "default": 3},
            "source_path": {"type": "string", "description": "Path to source code"},
            "repository_url": {"type": "string", "description": "Git repository URL"},
            "start_date": {"type": "date", "description": "Project start date"},
            "target_end_date": {"type": "date", "description": "Target completion date"},
        },
    },
    "features": {
        "table": "features",
        "required": ["name", "project_id"],
        "fields": {
            "name": {"type": "string", "max_length": 255, "description": "Feature name"},
            "description": {"type": "string", "description": "Feature description"},
            "spec": {"type": "string", "description": "Technical specification"},
            "project_id": {"type": "integer", "description": "Project ID"},
            "project_name": {
                "type": "lookup",
                "lookup_table": "projects",
                "lookup_field": "name",
                "target_field": "project_id",
            },
            "milestone_id": {"type": "integer", "description": "Milestone ID (optional)"},
            "milestone_name": {
                "type": "lookup",
                "lookup_table": "milestones",
                "lookup_field": "name",
                "target_field": "milestone_id",
            },
            "status": {
                "type": "enum",
                "values": [
                    "draft",
                    "spec",
                    "in_progress",
                    "review",
                    "completed",
                    "blocked",
                    "cancelled",
                ],
                "default": "draft",
            },
            "priority": {"type": "integer", "min": 0, "max": 5, "default": 0},
            "assigned_to": {"type": "string", "description": "Assigned user"},
            "assigned_node": {"type": "string", "description": "Assigned node"},
            "tmux_session": {"type": "string", "description": "Linked tmux session"},
            "estimated_hours": {"type": "float", "min": 0, "description": "Estimated hours"},
            "actual_hours": {"type": "float", "min": 0, "description": "Actual hours"},
            "completed_at": {"type": "date", "description": "Completion date (YYYY-MM-DD)"},
        },
    },
    "bugs": {
        "table": "bugs",
        "required": ["title", "project_id"],
        "fields": {
            "title": {"type": "string", "max_length": 255, "description": "Bug title"},
            "description": {"type": "string", "description": "Bug description"},
            "project_id": {"type": "integer", "description": "Project ID"},
            "project_name": {
                "type": "lookup",
                "lookup_table": "projects",
                "lookup_field": "name",
                "target_field": "project_id",
            },
            "severity": {
                "type": "enum",
                "values": ["low", "medium", "high", "critical"],
                "default": "medium",
            },
            "status": {
                "type": "enum",
                "values": ["open", "in_progress", "resolved", "closed", "blocked"],
                "default": "open",
            },
            "assignee": {"type": "string"},
            "reporter": {"type": "string"},
            "steps_to_reproduce": {"type": "string"},
            "expected_behavior": {"type": "string"},
            "actual_behavior": {"type": "string"},
            "environment": {"type": "string"},
            "due_date": {"type": "date"},
        },
    },
    "milestones": {
        "table": "milestones",
        "required": ["name", "project_id"],
        "fields": {
            "name": {"type": "string", "max_length": 255, "description": "Milestone name"},
            "description": {"type": "string"},
            "project_id": {"type": "integer"},
            "project_name": {
                "type": "lookup",
                "lookup_table": "projects",
                "lookup_field": "name",
                "target_field": "project_id",
            },
            "target_date": {"type": "date", "description": "Target completion date"},
            "status": {
                "type": "enum",
                "values": ["planned", "in_progress", "completed", "cancelled"],
                "default": "planned",
            },
        },
    },
    "tasks": {
        "table": "task_queue",
        "required": ["task_type"],
        "fields": {
            "task_type": {
                "type": "enum",
                "values": ["shell", "python", "git", "deploy", "test", "build", "tmux"],
            },
            "priority": {"type": "integer", "min": 0, "max": 10, "default": 0},
            "max_retries": {"type": "integer", "min": 0, "max": 10, "default": 3},
            "timeout_seconds": {"type": "integer", "min": 1},
            "command": {"type": "string", "description": "Command to execute (for shell tasks)"},
            "script": {"type": "string", "description": "Script content (for python tasks)"},
            "project_id": {"type": "integer"},
            "project_name": {
                "type": "lookup",
                "lookup_table": "projects",
                "lookup_field": "name",
                "target_field": "project_id",
            },
        },
    },
}


def get_schemas():
    """Get all available import schemas."""
    schemas = {}
    for entity, schema in IMPORT_ENTITY_SCHEMAS.items():
        schemas[entity] = {"required_fields": schema["required"], "fields": schema["fields"]}
    return {"schemas": schemas, "supported_entities": list(IMPORT_ENTITY_SCHEMAS.keys())}


def generate_csv_template(entity_type):
    """Generate CSV template for an entity type."""
    if entity_type not in IMPORT_ENTITY_SCHEMAS:
        return None, f"Unknown entity type. Supported: {', '.join(IMPORT_ENTITY_SCHEMAS.keys())}"

    schema = IMPORT_ENTITY_SCHEMAS[entity_type]
    headers = list(schema["fields"].keys())

    example_row = []
    for field_name, field_def in schema["fields"].items():
        ftype = field_def.get("type")
        if ftype == "enum":
            example_row.append(field_def.get("values", [""])[0])
        elif ftype == "integer":
            example_row.append(str(field_def.get("default", field_def.get("min", 1))))
        elif ftype == "float":
            example_row.append(str(field_def.get("default", field_def.get("min", 1.0))))
        elif ftype == "date":
            example_row.append("2025-01-15")
        elif ftype == "lookup":
            example_row.append(f'Example {field_def["lookup_table"][:-1].title()}')
        else:
            example_row.append(f"Example {field_name}")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerow(example_row)

    return output.getvalue(), None


def auto_detect_mapping(csv_headers, schema):
    """Auto-detect field mapping from CSV headers."""
    mapping = {}
    for col in csv_headers:
        normalized = col.lower().strip().replace(" ", "_").replace("-", "_")
        if normalized in schema["fields"]:
            mapping[col] = normalized
        elif col.lower().strip() in schema["fields"]:
            mapping[col] = col.lower().strip()
    return mapping


def validate_value(value, field_def, conn=None):
    """Validate and convert a value according to field definition."""
    ftype = field_def.get("type")
    errors = []
    result = None

    if ftype == "integer":
        try:
            int_val = int(value)
            if "min" in field_def and int_val < field_def["min"]:
                errors.append(f"value {int_val} below minimum {field_def['min']}")
            elif "max" in field_def and int_val > field_def["max"]:
                errors.append(f"value {int_val} above maximum {field_def['max']}")
            else:
                result = int_val
        except ValueError:
            errors.append(f"'{value}' is not a valid integer")

    elif ftype == "float":
        try:
            float_val = float(value)
            if "min" in field_def and float_val < field_def["min"]:
                errors.append(f"value {float_val} below minimum {field_def['min']}")
            elif "max" in field_def and float_val > field_def["max"]:
                errors.append(f"value {float_val} above maximum {field_def['max']}")
            else:
                result = float_val
        except ValueError:
            errors.append(f"'{value}' is not a valid number")

    elif ftype == "enum":
        valid_values = [v.lower() for v in field_def.get("values", [])]
        if value.lower() in valid_values:
            result = value.lower()
        else:
            errors.append(f"'{value}' not in {field_def.get('values')}")

    elif ftype == "date":
        try:
            datetime.strptime(value, "%Y-%m-%d")
            result = value
        except ValueError:
            errors.append(f"'{value}' is not a valid date (use YYYY-MM-DD)")

    elif ftype == "lookup":
        if conn:
            lookup_table = field_def["lookup_table"]
            lookup_field = field_def["lookup_field"]
            query_result = conn.execute(
                f"SELECT id FROM {lookup_table} WHERE LOWER({lookup_field}) = LOWER(?)", (value,)
            ).fetchone()
            if query_result:
                result = query_result[0]
            else:
                errors.append(f"'{value}' not found in {lookup_table}")
        else:
            errors.append("Database connection required for lookup")

    else:
        # String type
        if "max_length" in field_def and len(value) > field_def["max_length"]:
            errors.append(f"exceeds max length of {field_def['max_length']}")
        else:
            result = value

    return result, errors


def preview_import(conn, entity_type, csv_data, mapping=None, skip_header=True, max_rows=100):
    """Preview CSV import with validation."""
    if entity_type not in IMPORT_ENTITY_SCHEMAS:
        return None, f"Unknown entity type"

    schema = IMPORT_ENTITY_SCHEMAS[entity_type]
    rows = list(csv.reader(io.StringIO(csv_data)))

    if not rows:
        return None, "CSV is empty"

    csv_headers = rows[0] if rows else []
    data_rows = rows[1:] if skip_header else rows

    # Auto-detect mapping if not provided
    if not mapping:
        mapping = auto_detect_mapping(csv_headers, schema)

    preview_rows = []
    validation_errors = []
    valid_count = 0

    for row_idx, row in enumerate(data_rows[:max_rows]):
        row_data = {}
        row_errors = []

        for csv_idx, csv_col in enumerate(csv_headers):
            if csv_idx < len(row) and csv_col in mapping:
                value = row[csv_idx].strip()
                if not value:
                    continue

                db_field = mapping[csv_col]
                field_def = schema["fields"].get(db_field, {})

                if field_def.get("type") == "lookup":
                    result, errors = validate_value(value, field_def, conn)
                    if result is not None:
                        row_data[field_def["target_field"]] = result
                    row_errors.extend([f"{db_field}: {e}" for e in errors])
                else:
                    result, errors = validate_value(value, field_def)
                    if result is not None:
                        row_data[db_field] = result
                    row_errors.extend([f"{db_field}: {e}" for e in errors])

        # Check required fields
        for req_field in schema["required"]:
            if req_field not in row_data:
                row_errors.append(f"Missing required field: {req_field}")

        is_valid = len(row_errors) == 0
        if is_valid:
            valid_count += 1

        preview_rows.append(
            {
                "row_number": row_idx + 1,
                "original": dict(zip(csv_headers, row)),
                "mapped": row_data,
                "errors": row_errors,
                "is_valid": is_valid,
            }
        )

        if row_errors:
            validation_errors.extend([{"row": row_idx + 1, "error": e} for e in row_errors])

    return {
        "entity_type": entity_type,
        "csv_headers": csv_headers,
        "mapping": mapping,
        "schema_fields": list(schema["fields"].keys()),
        "required_fields": schema["required"],
        "total_rows": len(data_rows),
        "preview_rows": preview_rows,
        "valid_count": valid_count,
        "invalid_count": len(data_rows[:max_rows]) - valid_count,
        "validation_errors": validation_errors[:50],
    }, None


def execute_import(
    conn,
    entity_type,
    csv_data,
    mapping,
    skip_header=True,
    skip_errors=False,
    update_existing=False,
    unique_field=None,
):
    """Execute CSV import with field mapping."""
    if entity_type not in IMPORT_ENTITY_SCHEMAS:
        return None, "Unknown entity type"

    schema = IMPORT_ENTITY_SCHEMAS[entity_type]
    table = schema["table"]
    rows = list(csv.reader(io.StringIO(csv_data)))

    csv_headers = rows[0] if rows else []
    data_rows = rows[1:] if skip_header else rows

    imported = []
    updated = []
    errors = []

    for row_idx, row in enumerate(data_rows):
        try:
            row_data = {}
            row_errors = []

            for csv_idx, csv_col in enumerate(csv_headers):
                if csv_idx < len(row) and csv_col in mapping:
                    value = row[csv_idx].strip()
                    if not value:
                        continue

                    db_field = mapping[csv_col]
                    field_def = schema["fields"].get(db_field, {})

                    if field_def.get("type") == "lookup":
                        result, errs = validate_value(value, field_def, conn)
                        if result is not None:
                            row_data[field_def["target_field"]] = result
                        row_errors.extend(errs)
                    else:
                        result, errs = validate_value(value, field_def)
                        if result is not None:
                            row_data[db_field] = result
                        row_errors.extend(errs)

            # Apply defaults
            for field_name, field_def in schema["fields"].items():
                if field_name not in row_data and "default" in field_def:
                    row_data[field_name] = field_def["default"]

            # Check required fields
            for req in schema["required"]:
                if req not in row_data:
                    row_errors.append(f"Missing: {req}")

            if row_errors:
                if skip_errors:
                    errors.append({"row": row_idx + 1, "errors": row_errors})
                    continue
                else:
                    return None, f"Row {row_idx + 1}: {', '.join(row_errors)}"

            # Handle special task_data for tasks
            if entity_type == "tasks" and "command" in row_data:
                task_data = {"command": row_data.pop("command", "")}
                if "script" in row_data:
                    task_data["script"] = row_data.pop("script")
                row_data["task_data"] = json.dumps(task_data)

            # Check for existing record
            existing_id = None
            if update_existing and unique_field and unique_field in row_data:
                existing = conn.execute(
                    f"SELECT id FROM {table} WHERE {unique_field} = ?", (row_data[unique_field],)
                ).fetchone()
                if existing:
                    existing_id = existing[0]

            if existing_id:
                # Update existing
                set_clause = ", ".join([f"{k} = ?" for k in row_data.keys()])
                conn.execute(
                    f"UPDATE {table} SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    list(row_data.values()) + [existing_id],
                )
                updated.append({"id": existing_id, "row": row_idx + 1})
            else:
                # Insert new
                columns = ", ".join(row_data.keys())
                placeholders = ", ".join(["?" for _ in row_data])
                cursor = conn.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                    list(row_data.values()),
                )
                imported.append({"id": cursor.lastrowid, "row": row_idx + 1})

        except Exception as e:
            if skip_errors:
                errors.append({"row": row_idx + 1, "error": str(e)})
            else:
                return None, f"Row {row_idx + 1}: {str(e)}"

    return {
        "success": True,
        "entity_type": entity_type,
        "imported_count": len(imported),
        "updated_count": len(updated),
        "error_count": len(errors),
        "imported": imported,
        "updated": updated,
        "errors": errors,
    }, None


def validate_mapping(entity_type, mapping):
    """Validate a field mapping configuration."""
    if entity_type not in IMPORT_ENTITY_SCHEMAS:
        return None, "Invalid entity type"

    schema = IMPORT_ENTITY_SCHEMAS[entity_type]
    valid_fields = set(schema["fields"].keys())
    required_fields = set(schema["required"])
    mapped_fields = set(mapping.values())

    invalid_mappings = []
    for csv_col, db_field in mapping.items():
        if db_field not in valid_fields:
            invalid_mappings.append(
                {"csv_column": csv_col, "db_field": db_field, "error": "Unknown field"}
            )

    missing_required = []
    for req in required_fields:
        if req not in mapped_fields:
            # Check if a lookup field maps to this
            satisfied = False
            for db_field in mapped_fields:
                field_def = schema["fields"].get(db_field, {})
                if field_def.get("type") == "lookup" and field_def.get("target_field") == req:
                    satisfied = True
                    break
            if not satisfied:
                missing_required.append(req)

    is_valid = len(invalid_mappings) == 0 and len(missing_required) == 0

    return {
        "is_valid": is_valid,
        "invalid_mappings": invalid_mappings,
        "missing_required": missing_required,
        "mapped_fields": list(mapped_fields),
        "available_fields": list(valid_fields),
        "required_fields": list(required_fields),
    }, None
