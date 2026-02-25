"""
Dashboard Layout Module
Save and manage custom dashboard layouts for users
"""

import json
from datetime import datetime

# Default panel configurations
DEFAULT_PANELS = {
    "projects": {"title": "Projects", "size": "medium", "order": 1, "visible": True},
    "tasks": {"title": "Tasks", "size": "large", "order": 2, "visible": True},
    "bugs": {"title": "Bugs", "size": "medium", "order": 3, "visible": True},
    "features": {"title": "Features", "size": "medium", "order": 4, "visible": True},
    "milestones": {"title": "Milestones", "size": "medium", "order": 5, "visible": True},
    "activity": {"title": "Activity", "size": "small", "order": 6, "visible": True},
    "errors": {"title": "Errors", "size": "medium", "order": 7, "visible": True},
    "nodes": {"title": "Nodes", "size": "small", "order": 8, "visible": True},
    "workers": {"title": "Workers", "size": "small", "order": 9, "visible": True},
    "tmux": {"title": "Tmux Sessions", "size": "medium", "order": 10, "visible": True},
    "queue": {"title": "Task Queue", "size": "medium", "order": 11, "visible": True},
    "stats": {"title": "Statistics", "size": "small", "order": 12, "visible": True},
}

# Panel size options
PANEL_SIZES = ["small", "medium", "large", "full"]

# Layout presets
LAYOUT_PRESETS = {
    "default": {
        "name": "Default",
        "description": "Standard dashboard layout with all panels",
        "columns": 3,
        "panels": DEFAULT_PANELS,
    },
    "compact": {
        "name": "Compact",
        "description": "Minimal layout for quick overview",
        "columns": 2,
        "panels": {
            "projects": {"title": "Projects", "size": "medium", "order": 1, "visible": True},
            "tasks": {"title": "Tasks", "size": "large", "order": 2, "visible": True},
            "activity": {"title": "Activity", "size": "small", "order": 3, "visible": True},
            "stats": {"title": "Statistics", "size": "small", "order": 4, "visible": True},
        },
    },
    "developer": {
        "name": "Developer",
        "description": "Focus on tasks, bugs, and code",
        "columns": 3,
        "panels": {
            "tasks": {"title": "Tasks", "size": "large", "order": 1, "visible": True},
            "bugs": {"title": "Bugs", "size": "large", "order": 2, "visible": True},
            "features": {"title": "Features", "size": "medium", "order": 3, "visible": True},
            "tmux": {"title": "Tmux Sessions", "size": "medium", "order": 4, "visible": True},
            "errors": {"title": "Errors", "size": "medium", "order": 5, "visible": True},
            "activity": {"title": "Activity", "size": "small", "order": 6, "visible": True},
        },
    },
    "manager": {
        "name": "Manager",
        "description": "Focus on projects, milestones, and progress",
        "columns": 3,
        "panels": {
            "projects": {"title": "Projects", "size": "large", "order": 1, "visible": True},
            "milestones": {"title": "Milestones", "size": "large", "order": 2, "visible": True},
            "stats": {"title": "Statistics", "size": "medium", "order": 3, "visible": True},
            "activity": {"title": "Activity", "size": "medium", "order": 4, "visible": True},
            "tasks": {"title": "Tasks", "size": "medium", "order": 5, "visible": True},
        },
    },
    "devops": {
        "name": "DevOps",
        "description": "Focus on infrastructure and monitoring",
        "columns": 3,
        "panels": {
            "nodes": {"title": "Nodes", "size": "large", "order": 1, "visible": True},
            "workers": {"title": "Workers", "size": "medium", "order": 2, "visible": True},
            "errors": {"title": "Errors", "size": "large", "order": 3, "visible": True},
            "queue": {"title": "Task Queue", "size": "medium", "order": 4, "visible": True},
            "tmux": {"title": "Tmux Sessions", "size": "medium", "order": 5, "visible": True},
            "activity": {"title": "Activity", "size": "small", "order": 6, "visible": True},
        },
    },
}


def save_layout(conn, user_id, name, layout_config, is_default=False, description=None):
    """Save a custom dashboard layout for a user."""
    cursor = conn.cursor()

    # Validate layout config
    if "panels" not in layout_config:
        return {"error": "Layout must include panels configuration"}

    # Validate panels
    for panel_id, panel_config in layout_config.get("panels", {}).items():
        if "size" in panel_config and panel_config["size"] not in PANEL_SIZES:
            return {"error": f'Invalid panel size: {panel_config["size"]}'}

    # If setting as default, unset other defaults for this user
    if is_default:
        cursor.execute(
            """
            UPDATE dashboard_layouts SET is_default = 0
            WHERE user_id = ? AND is_default = 1
        """,
            (user_id,),
        )

    # Check if layout with same name exists
    cursor.execute(
        """
        SELECT id FROM dashboard_layouts
        WHERE user_id = ? AND name = ?
    """,
        (user_id, name),
    )

    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE dashboard_layouts
            SET layout_config = ?, is_default = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (json.dumps(layout_config), is_default, description, existing["id"]),
        )
        layout_id = existing["id"]
    else:
        cursor.execute(
            """
            INSERT INTO dashboard_layouts (user_id, name, layout_config, is_default, description)
            VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, name, json.dumps(layout_config), is_default, description),
        )
        layout_id = cursor.lastrowid

    conn.commit()

    return {
        "id": layout_id,
        "user_id": user_id,
        "name": name,
        "is_default": is_default,
        "layout_config": layout_config,
    }


def get_layout(conn, layout_id):
    """Get a specific layout by ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dashboard_layouts WHERE id = ?", (layout_id,))

    row = cursor.fetchone()
    if not row:
        return None

    result = dict(row)
    if result.get("layout_config"):
        result["layout_config"] = json.loads(result["layout_config"])

    return result


def get_user_layouts(conn, user_id, include_presets=True):
    """Get all layouts for a user."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM dashboard_layouts
        WHERE user_id = ?
        ORDER BY is_default DESC, name
    """,
        (user_id,),
    )

    layouts = []
    for row in cursor.fetchall():
        layout = dict(row)
        if layout.get("layout_config"):
            layout["layout_config"] = json.loads(layout["layout_config"])
        layout["is_preset"] = False
        layouts.append(layout)

    # Add presets if requested
    if include_presets:
        for preset_id, preset in LAYOUT_PRESETS.items():
            layouts.append(
                {
                    "id": f"preset_{preset_id}",
                    "name": preset["name"],
                    "description": preset["description"],
                    "is_preset": True,
                    "is_default": False,
                    "layout_config": {"columns": preset["columns"], "panels": preset["panels"]},
                }
            )

    return {"layouts": layouts, "count": len(layouts)}


def get_default_layout(conn, user_id):
    """Get the default layout for a user."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM dashboard_layouts
        WHERE user_id = ? AND is_default = 1
    """,
        (user_id,),
    )

    row = cursor.fetchone()

    if row:
        result = dict(row)
        if result.get("layout_config"):
            result["layout_config"] = json.loads(result["layout_config"])
        return result

    # Return default preset if no custom default
    return {
        "id": "preset_default",
        "name": "Default",
        "is_preset": True,
        "is_default": True,
        "layout_config": {
            "columns": LAYOUT_PRESETS["default"]["columns"],
            "panels": LAYOUT_PRESETS["default"]["panels"],
        },
    }


def delete_layout(conn, layout_id, user_id):
    """Delete a layout (only by owner)."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, user_id FROM dashboard_layouts WHERE id = ?
    """,
        (layout_id,),
    )

    row = cursor.fetchone()
    if not row:
        return {"error": "Layout not found"}

    if row["user_id"] != user_id:
        return {"error": "Can only delete your own layouts"}

    cursor.execute("DELETE FROM dashboard_layouts WHERE id = ?", (layout_id,))
    conn.commit()

    return {"success": True, "deleted_id": layout_id}


def set_default_layout(conn, layout_id, user_id):
    """Set a layout as the user's default."""
    cursor = conn.cursor()

    # Handle preset layouts
    if isinstance(layout_id, str) and layout_id.startswith("preset_"):
        preset_id = layout_id.replace("preset_", "")
        if preset_id not in LAYOUT_PRESETS:
            return {"error": "Preset not found"}

        # Clear existing defaults
        cursor.execute(
            """
            UPDATE dashboard_layouts SET is_default = 0
            WHERE user_id = ? AND is_default = 1
        """,
            (user_id,),
        )

        # Save preset as user's default
        preset = LAYOUT_PRESETS[preset_id]
        return save_layout(
            conn,
            user_id,
            preset["name"],
            {"columns": preset["columns"], "panels": preset["panels"]},
            is_default=True,
            description=preset["description"],
        )

    # Handle custom layouts
    cursor.execute(
        """
        SELECT id, user_id FROM dashboard_layouts WHERE id = ?
    """,
        (layout_id,),
    )

    row = cursor.fetchone()
    if not row:
        return {"error": "Layout not found"}

    if row["user_id"] != user_id:
        return {"error": "Can only set your own layouts as default"}

    # Clear existing defaults
    cursor.execute(
        """
        UPDATE dashboard_layouts SET is_default = 0
        WHERE user_id = ? AND is_default = 1
    """,
        (user_id,),
    )

    # Set new default
    cursor.execute(
        """
        UPDATE dashboard_layouts SET is_default = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (layout_id,),
    )

    conn.commit()

    return get_layout(conn, layout_id)


def update_panel(conn, user_id, panel_id, updates):
    """Update a single panel in the user's current layout."""
    cursor = conn.cursor()

    # Get current default layout
    layout = get_default_layout(conn, user_id)

    if layout.get("is_preset"):
        # Create a copy from preset
        layout_config = layout["layout_config"].copy()
    else:
        layout_config = layout["layout_config"]

    # Update panel
    if "panels" not in layout_config:
        layout_config["panels"] = {}

    if panel_id not in layout_config["panels"]:
        layout_config["panels"][panel_id] = DEFAULT_PANELS.get(
            panel_id,
            {
                "title": panel_id.title(),
                "size": "medium",
                "order": len(layout_config["panels"]) + 1,
                "visible": True,
            },
        )

    for key, value in updates.items():
        if key in ["size", "order", "visible", "title", "collapsed"]:
            layout_config["panels"][panel_id][key] = value

    # Save updated layout
    return save_layout(conn, user_id, layout.get("name", "Custom"), layout_config, is_default=True)


def reorder_panels(conn, user_id, panel_order):
    """Reorder panels based on a list of panel IDs."""
    cursor = conn.cursor()

    layout = get_default_layout(conn, user_id)

    if layout.get("is_preset"):
        layout_config = layout["layout_config"].copy()
    else:
        layout_config = layout["layout_config"]

    # Update order for each panel
    for idx, panel_id in enumerate(panel_order):
        if panel_id in layout_config.get("panels", {}):
            layout_config["panels"][panel_id]["order"] = idx + 1

    return save_layout(conn, user_id, layout.get("name", "Custom"), layout_config, is_default=True)


def toggle_panel(conn, user_id, panel_id, visible=None):
    """Toggle panel visibility."""
    layout = get_default_layout(conn, user_id)

    if layout.get("is_preset"):
        layout_config = layout["layout_config"].copy()
    else:
        layout_config = layout["layout_config"]

    if panel_id not in layout_config.get("panels", {}):
        return {"error": "Panel not found"}

    current_visible = layout_config["panels"][panel_id].get("visible", True)
    new_visible = visible if visible is not None else not current_visible

    return update_panel(conn, user_id, panel_id, {"visible": new_visible})


def duplicate_layout(conn, layout_id, user_id, new_name):
    """Duplicate an existing layout."""
    cursor = conn.cursor()

    # Handle preset layouts
    if isinstance(layout_id, str) and layout_id.startswith("preset_"):
        preset_id = layout_id.replace("preset_", "")
        if preset_id not in LAYOUT_PRESETS:
            return {"error": "Preset not found"}

        preset = LAYOUT_PRESETS[preset_id]
        return save_layout(
            conn,
            user_id,
            new_name,
            {"columns": preset["columns"], "panels": preset["panels"]},
            description=f"Copy of {preset['name']}",
        )

    # Handle custom layouts
    source_layout = get_layout(conn, layout_id)
    if not source_layout:
        return {"error": "Layout not found"}

    return save_layout(
        conn,
        user_id,
        new_name,
        source_layout["layout_config"],
        description=f"Copy of {source_layout['name']}",
    )


def share_layout(conn, layout_id, user_id, share_with_user=None, make_public=False):
    """Share a layout with another user or make it public."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM dashboard_layouts WHERE id = ? AND user_id = ?
    """,
        (layout_id, user_id),
    )

    row = cursor.fetchone()
    if not row:
        return {"error": "Layout not found or not owned by you"}

    if make_public:
        cursor.execute(
            """
            UPDATE dashboard_layouts SET is_public = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (layout_id,),
        )
    elif share_with_user:
        # Create a copy for the other user
        layout = dict(row)
        layout_config = json.loads(layout["layout_config"])
        return save_layout(
            conn,
            share_with_user,
            f"{layout['name']} (shared)",
            layout_config,
            description=f"Shared by {user_id}",
        )

    conn.commit()
    return {"success": True, "layout_id": layout_id}


def get_public_layouts(conn, limit=20):
    """Get publicly shared layouts."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM dashboard_layouts
        WHERE is_public = 1
        ORDER BY updated_at DESC
        LIMIT ?
    """,
        (limit,),
    )

    layouts = []
    for row in cursor.fetchall():
        layout = dict(row)
        if layout.get("layout_config"):
            layout["layout_config"] = json.loads(layout["layout_config"])
        layouts.append(layout)

    return {"layouts": layouts, "count": len(layouts)}


def get_presets():
    """Get available layout presets."""
    return LAYOUT_PRESETS


def get_available_panels():
    """Get list of available panels."""
    return DEFAULT_PANELS


def get_panel_sizes():
    """Get available panel sizes."""
    return PANEL_SIZES
