"""
App-Wide Settings Module

Provides functions for managing application-wide settings
that control system behavior, defaults, and configurations.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default settings with their types and descriptions
DEFAULT_SETTINGS = {
    # General settings
    "app.name": {
        "value": "Architect Dashboard",
        "type": "string",
        "category": "general",
        "description": "Application display name",
        "editable": True,
    },
    "app.timezone": {
        "value": "UTC",
        "type": "string",
        "category": "general",
        "description": "Default timezone for the application",
        "editable": True,
    },
    "app.date_format": {
        "value": "YYYY-MM-DD",
        "type": "string",
        "category": "general",
        "description": "Default date format",
        "editable": True,
    },
    "app.datetime_format": {
        "value": "YYYY-MM-DD HH:mm:ss",
        "type": "string",
        "category": "general",
        "description": "Default datetime format",
        "editable": True,
    },
    # Session settings
    "session.timeout_minutes": {
        "value": 60,
        "type": "integer",
        "category": "security",
        "description": "Session timeout in minutes",
        "editable": True,
        "min": 5,
        "max": 1440,
    },
    "session.max_concurrent": {
        "value": 5,
        "type": "integer",
        "category": "security",
        "description": "Maximum concurrent sessions per user",
        "editable": True,
        "min": 1,
        "max": 20,
    },
    # Task queue settings
    "tasks.default_priority": {
        "value": 5,
        "type": "integer",
        "category": "tasks",
        "description": "Default priority for new tasks (1-10)",
        "editable": True,
        "min": 1,
        "max": 10,
    },
    "tasks.max_retries": {
        "value": 3,
        "type": "integer",
        "category": "tasks",
        "description": "Maximum retry attempts for failed tasks",
        "editable": True,
        "min": 0,
        "max": 10,
    },
    "tasks.default_timeout_seconds": {
        "value": 600,
        "type": "integer",
        "category": "tasks",
        "description": "Default task timeout in seconds",
        "editable": True,
        "min": 30,
        "max": 7200,
    },
    "tasks.auto_archive_days": {
        "value": 7,
        "type": "integer",
        "category": "tasks",
        "description": "Days before completed tasks are archived",
        "editable": True,
        "min": 1,
        "max": 365,
    },
    "tasks.priority_aging_enabled": {
        "value": True,
        "type": "boolean",
        "category": "tasks",
        "description": "Enable priority aging for waiting tasks",
        "editable": True,
    },
    # Worker settings
    "workers.heartbeat_interval": {
        "value": 30,
        "type": "integer",
        "category": "workers",
        "description": "Worker heartbeat interval in seconds",
        "editable": True,
        "min": 10,
        "max": 300,
    },
    "workers.stale_threshold_seconds": {
        "value": 120,
        "type": "integer",
        "category": "workers",
        "description": "Seconds before a worker is considered stale",
        "editable": True,
        "min": 60,
        "max": 600,
    },
    "workers.auto_reassign_tasks": {
        "value": True,
        "type": "boolean",
        "category": "workers",
        "description": "Automatically reassign tasks from stale workers",
        "editable": True,
    },
    # Node settings
    "nodes.heartbeat_interval": {
        "value": 30,
        "type": "integer",
        "category": "nodes",
        "description": "Node heartbeat interval in seconds",
        "editable": True,
        "min": 10,
        "max": 300,
    },
    "nodes.stale_threshold_seconds": {
        "value": 180,
        "type": "integer",
        "category": "nodes",
        "description": "Seconds before a node is considered offline",
        "editable": True,
        "min": 60,
        "max": 600,
    },
    # Error handling settings
    "errors.retention_days": {
        "value": 30,
        "type": "integer",
        "category": "errors",
        "description": "Days to retain resolved errors",
        "editable": True,
        "min": 1,
        "max": 365,
    },
    "errors.auto_group": {
        "value": True,
        "type": "boolean",
        "category": "errors",
        "description": "Automatically group similar errors",
        "editable": True,
    },
    "errors.notification_threshold": {
        "value": 5,
        "type": "integer",
        "category": "errors",
        "description": "Error count threshold for notifications",
        "editable": True,
        "min": 1,
        "max": 100,
    },
    # Notification settings
    "notifications.enabled": {
        "value": True,
        "type": "boolean",
        "category": "notifications",
        "description": "Enable system notifications",
        "editable": True,
    },
    "notifications.email_enabled": {
        "value": False,
        "type": "boolean",
        "category": "notifications",
        "description": "Enable email notifications",
        "editable": True,
    },
    "notifications.slack_enabled": {
        "value": False,
        "type": "boolean",
        "category": "notifications",
        "description": "Enable Slack notifications",
        "editable": True,
    },
    "notifications.webhook_enabled": {
        "value": True,
        "type": "boolean",
        "category": "notifications",
        "description": "Enable webhook notifications",
        "editable": True,
    },
    # UI settings
    "ui.default_page_size": {
        "value": 25,
        "type": "integer",
        "category": "ui",
        "description": "Default number of items per page",
        "editable": True,
        "min": 10,
        "max": 100,
    },
    "ui.theme": {
        "value": "system",
        "type": "string",
        "category": "ui",
        "description": "Default theme (light, dark, system)",
        "editable": True,
        "options": ["light", "dark", "system"],
    },
    "ui.refresh_interval": {
        "value": 30,
        "type": "integer",
        "category": "ui",
        "description": "Auto-refresh interval in seconds (0 to disable)",
        "editable": True,
        "min": 0,
        "max": 300,
    },
    # API settings
    "api.rate_limit_requests": {
        "value": 100,
        "type": "integer",
        "category": "api",
        "description": "Maximum API requests per minute",
        "editable": True,
        "min": 10,
        "max": 1000,
    },
    "api.max_page_size": {
        "value": 100,
        "type": "integer",
        "category": "api",
        "description": "Maximum items per API request",
        "editable": True,
        "min": 10,
        "max": 500,
    },
    # Backup settings
    "backup.enabled": {
        "value": False,
        "type": "boolean",
        "category": "backup",
        "description": "Enable automatic backups",
        "editable": True,
    },
    "backup.retention_days": {
        "value": 30,
        "type": "integer",
        "category": "backup",
        "description": "Days to retain backups",
        "editable": True,
        "min": 1,
        "max": 365,
    },
    "backup.schedule": {
        "value": "0 2 * * *",
        "type": "string",
        "category": "backup",
        "description": "Backup schedule in cron format",
        "editable": True,
    },
    # Feature flags
    "features.autopilot_enabled": {
        "value": True,
        "type": "boolean",
        "category": "features",
        "description": "Enable autopilot features",
        "editable": True,
    },
    "features.webhooks_enabled": {
        "value": True,
        "type": "boolean",
        "category": "features",
        "description": "Enable webhook integrations",
        "editable": True,
    },
    "features.custom_reports_enabled": {
        "value": True,
        "type": "boolean",
        "category": "features",
        "description": "Enable custom report builder",
        "editable": True,
    },
}

# Setting categories with descriptions
SETTING_CATEGORIES = {
    "general": "General application settings",
    "security": "Security and session settings",
    "tasks": "Task queue configuration",
    "workers": "Worker management settings",
    "nodes": "Cluster node settings",
    "errors": "Error handling configuration",
    "notifications": "Notification settings",
    "ui": "User interface settings",
    "api": "API configuration",
    "backup": "Backup settings",
    "features": "Feature flags",
}


def get_settings(conn, category: str = None, include_metadata: bool = False) -> Dict:
    """Get all settings or settings by category.

    Args:
        conn: Database connection
        category: Optional category filter
        include_metadata: Include type, description, etc.

    Returns:
        Dict of setting key -> value (or full metadata)
    """
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM app_settings"
    params = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY key"

    rows = conn.execute(query, params).fetchall()

    # Build settings dict starting with defaults
    settings = {}
    for key, default in DEFAULT_SETTINGS.items():
        if category and default.get("category") != category:
            continue

        if include_metadata:
            settings[key] = {
                "value": default["value"],
                "type": default["type"],
                "category": default.get("category", "general"),
                "description": default.get("description", ""),
                "editable": default.get("editable", True),
                "is_default": True,
            }
            if "min" in default:
                settings[key]["min"] = default["min"]
            if "max" in default:
                settings[key]["max"] = default["max"]
            if "options" in default:
                settings[key]["options"] = default["options"]
        else:
            settings[key] = default["value"]

    # Override with database values
    for row in rows:
        key = row["key"]
        if key in settings:
            value = _parse_value(row["value"], row["type"])
            if include_metadata:
                settings[key]["value"] = value
                settings[key]["is_default"] = False
                settings[key]["updated_at"] = row["updated_at"]
                settings[key]["updated_by"] = row["updated_by"]
            else:
                settings[key] = value

    return settings


def get_setting(conn, key: str) -> Any:
    """Get a single setting value.

    Args:
        conn: Database connection
        key: Setting key

    Returns:
        Setting value (uses default if not set)
    """
    # Check database first
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT value, type FROM app_settings WHERE key = ?", (key,)).fetchone()

    if row:
        return _parse_value(row["value"], row["type"])

    # Fall back to default
    if key in DEFAULT_SETTINGS:
        return DEFAULT_SETTINGS[key]["value"]

    return None


def set_setting(conn, key: str, value: Any, updated_by: str = None) -> bool:
    """Set a setting value.

    Args:
        conn: Database connection
        key: Setting key
        value: New value
        updated_by: User making the change

    Returns:
        True if successful
    """
    # Validate key exists
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown setting: {key}")

    default = DEFAULT_SETTINGS[key]

    # Check if editable
    if not default.get("editable", True):
        raise ValueError(f"Setting {key} is not editable")

    # Validate type
    setting_type = default["type"]
    validated_value = _validate_value(value, setting_type, default)

    # Store as string
    str_value = _serialize_value(validated_value, setting_type)

    conn.execute(
        """
        INSERT INTO app_settings (key, value, type, category, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP,
            updated_by = excluded.updated_by
    """,
        (key, str_value, setting_type, default.get("category", "general"), updated_by),
    )

    return True


def set_settings(conn, settings: Dict[str, Any], updated_by: str = None) -> Dict:
    """Set multiple settings at once.

    Args:
        conn: Database connection
        settings: Dict of key -> value
        updated_by: User making the change

    Returns:
        Dict with success status and any errors
    """
    results = {"success": [], "errors": []}

    for key, value in settings.items():
        try:
            set_setting(conn, key, value, updated_by)
            results["success"].append(key)
        except Exception as e:
            results["errors"].append({"key": key, "error": str(e)})

    return results


def reset_setting(conn, key: str, updated_by: str = None) -> bool:
    """Reset a setting to its default value.

    Args:
        conn: Database connection
        key: Setting key
        updated_by: User making the change

    Returns:
        True if reset
    """
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown setting: {key}")

    result = conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))

    return result.rowcount > 0


def reset_category(conn, category: str, updated_by: str = None) -> int:
    """Reset all settings in a category to defaults.

    Args:
        conn: Database connection
        category: Category to reset
        updated_by: User making the change

    Returns:
        Number of settings reset
    """
    if category not in SETTING_CATEGORIES:
        raise ValueError(f"Unknown category: {category}")

    result = conn.execute("DELETE FROM app_settings WHERE category = ?", (category,))

    return result.rowcount


def get_categories() -> Dict:
    """Get all setting categories with descriptions."""
    return SETTING_CATEGORIES


def get_setting_metadata(key: str) -> Optional[Dict]:
    """Get metadata for a setting.

    Args:
        key: Setting key

    Returns:
        Dict with type, description, etc.
    """
    if key not in DEFAULT_SETTINGS:
        return None

    default = DEFAULT_SETTINGS[key]
    metadata = {
        "key": key,
        "default_value": default["value"],
        "type": default["type"],
        "category": default.get("category", "general"),
        "description": default.get("description", ""),
        "editable": default.get("editable", True),
    }

    if "min" in default:
        metadata["min"] = default["min"]
    if "max" in default:
        metadata["max"] = default["max"]
    if "options" in default:
        metadata["options"] = default["options"]

    return metadata


def export_settings(conn) -> Dict:
    """Export all non-default settings.

    Args:
        conn: Database connection

    Returns:
        Dict with settings for export
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM app_settings").fetchall()

    settings = {}
    for row in rows:
        settings[row["key"]] = {
            "value": _parse_value(row["value"], row["type"]),
            "type": row["type"],
            "category": row["category"],
        }

    return {"settings": settings, "exported_at": datetime.now().isoformat(), "version": "1.0"}


def import_settings(conn, data: Dict, updated_by: str = None) -> Dict:
    """Import settings from export.

    Args:
        conn: Database connection
        data: Exported settings data
        updated_by: User making the import

    Returns:
        Import result with success/error counts
    """
    settings = data.get("settings", {})
    return set_settings(conn, {k: v["value"] for k, v in settings.items()}, updated_by)


def get_settings_history(conn, key: str = None, limit: int = 50) -> List[Dict]:
    """Get settings change history.

    Args:
        conn: Database connection
        key: Optional filter by setting key
        limit: Maximum records to return

    Returns:
        List of history records
    """
    conn.row_factory = sqlite3.Row

    query = """
        SELECT * FROM settings_history
        WHERE 1=1
    """
    params = []

    if key:
        query += " AND key = ?"
        params.append(key)

    query += " ORDER BY changed_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _parse_value(value: str, value_type: str) -> Any:
    """Parse a stored value to its proper type."""
    if value is None:
        return None

    if value_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    elif value_type == "integer":
        return int(value)
    elif value_type == "float":
        return float(value)
    elif value_type == "json":
        return json.loads(value)
    else:
        return value


def _serialize_value(value: Any, value_type: str) -> str:
    """Serialize a value for storage."""
    if value is None:
        return None

    if value_type == "boolean":
        return "true" if value else "false"
    elif value_type == "json":
        return json.dumps(value)
    else:
        return str(value)


def _validate_value(value: Any, value_type: str, default: Dict) -> Any:
    """Validate and convert a value."""
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    elif value_type == "integer":
        try:
            int_val = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"Expected integer, got {type(value).__name__}")

        if "min" in default and int_val < default["min"]:
            raise ValueError(f"Value must be at least {default['min']}")
        if "max" in default and int_val > default["max"]:
            raise ValueError(f"Value must be at most {default['max']}")

        return int_val

    elif value_type == "float":
        try:
            float_val = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Expected number, got {type(value).__name__}")

        if "min" in default and float_val < default["min"]:
            raise ValueError(f"Value must be at least {default['min']}")
        if "max" in default and float_val > default["max"]:
            raise ValueError(f"Value must be at most {default['max']}")

        return float_val

    elif value_type == "string":
        str_val = str(value)

        if "options" in default and str_val not in default["options"]:
            raise ValueError(f"Value must be one of: {default['options']}")

        return str_val

    elif value_type == "json":
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON")
        return value

    return value
