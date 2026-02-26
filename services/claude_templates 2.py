"""
Project-specific CLAUDE.md Templates Service

Provides management of CLAUDE.md templates for each project.
"""

import json

from flask import jsonify, request, session

DEFAULT_CLAUDE_TEMPLATE = """# CLAUDE.md

This file provides guidance to Claude Code when working with this project.

## Project Overview

{project_name} - {project_description}

## Quick Start

```bash
# Add your quick start commands here
```

## Architecture

Describe your project architecture here.

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main application entry point |

## Development Guidelines

- Follow existing code style
- Write tests for new features
- Update documentation as needed

## Common Operations

### Running Tests
```bash
# Add test commands
```

### Building
```bash
# Add build commands
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | false | Enable debug mode |

## Troubleshooting

Add common issues and solutions here.
"""


def register_claude_template_routes(app, get_db_connection, require_auth, api_error, log_activity):
    """Register all CLAUDE.md template routes with the Flask app."""

    @app.route("/api/projects/<int:project_id>/claude-template", methods=["GET"])
    @require_auth
    def get_project_claude_template(project_id):
        """Get the CLAUDE.md template for a project."""
        import sqlite3

        include_history = request.args.get("include_history", "false").lower() == "true"
        render = request.args.get("render", "true").lower() == "true"
        version = request.args.get("version", type=int)

        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row

            project = conn.execute(
                "SELECT id, name, description, source_path FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()

            if not project:
                return api_error("Project not found", 404, "not_found")

            if version:
                template = conn.execute(
                    """
                    SELECT * FROM project_claude_templates
                    WHERE project_id = ? AND version = ?
                    ORDER BY created_at DESC LIMIT 1
                """,
                    (project_id, version),
                ).fetchone()
            else:
                template = conn.execute(
                    """
                    SELECT * FROM project_claude_templates
                    WHERE project_id = ? AND is_active = 1
                    ORDER BY version DESC LIMIT 1
                """,
                    (project_id,),
                ).fetchone()

            if not template:
                content = DEFAULT_CLAUDE_TEMPLATE
                if render:
                    content = content.replace("{project_name}", project["name"] or "")
                    content = content.replace("{project_description}", project["description"] or "")
                return jsonify(
                    {
                        "project_id": project_id,
                        "template": {"content": content, "is_default": True, "version": 0},
                        "project_name": project["name"],
                    }
                )

            content = template["content"]
            variables = json.loads(template["variables"] or "{}")

            if render:
                content = content.replace("{project_name}", project["name"] or "")
                content = content.replace("{project_description}", project["description"] or "")
                for key, value in variables.items():
                    content = content.replace("{" + key + "}", str(value))

            result = {
                "project_id": project_id,
                "template": {
                    "id": template["id"],
                    "template_name": template["template_name"],
                    "content": content,
                    "description": template["description"],
                    "version": template["version"],
                    "is_active": bool(template["is_active"]),
                    "variables": variables,
                    "created_by": template["created_by"],
                    "created_at": template["created_at"],
                    "updated_at": template["updated_at"],
                    "is_default": False,
                },
                "project_name": project["name"],
            }

            if include_history:
                history = conn.execute(
                    """
                    SELECT id, version, description, created_by, created_at, is_active
                    FROM project_claude_templates WHERE project_id = ? ORDER BY version DESC
                """,
                    (project_id,),
                ).fetchall()
                result["history"] = [dict(h) for h in history]

            return jsonify(result)

    @app.route("/api/projects/<int:project_id>/claude-template", methods=["POST"])
    @require_auth
    def create_project_claude_template(project_id):
        """Create or update a CLAUDE.md template for a project."""
        import sqlite3

        data = request.get_json() or {}
        content = data.get("content")

        if not content:
            return api_error("content is required", 400, "missing_field")

        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row

            project = conn.execute(
                "SELECT id, name FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not project:
                return api_error("Project not found", 404, "not_found")

            current = conn.execute(
                """
                SELECT MAX(version) as max_version FROM project_claude_templates WHERE project_id = ?
            """,
                (project_id,),
            ).fetchone()
            new_version = (current["max_version"] or 0) + 1

            user_id = session.get("user", "anonymous")
            template_name = data.get("template_name", "CLAUDE.md")
            description = data.get("description", f"Version {new_version}")
            variables = json.dumps(data.get("variables", {}))
            set_active = data.get("set_active", True)

            if set_active:
                conn.execute(
                    "UPDATE project_claude_templates SET is_active = 0 WHERE project_id = ?",
                    (project_id,),
                )

            cursor = conn.execute(
                """
                INSERT INTO project_claude_templates
                    (project_id, template_name, content, description, version, is_active, variables, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    project_id,
                    template_name,
                    content,
                    description,
                    new_version,
                    1 if set_active else 0,
                    variables,
                    user_id,
                ),
            )

            log_activity(
                conn,
                "create_claude_template",
                "project",
                project_id,
                f"Created CLAUDE.md template v{new_version}",
            )

            return jsonify(
                {
                    "success": True,
                    "template_id": cursor.lastrowid,
                    "version": new_version,
                    "project_id": project_id,
                    "is_active": set_active,
                }
            )

    @app.route("/api/projects/<int:project_id>/claude-template/<int:template_id>", methods=["PUT"])
    @require_auth
    def update_project_claude_template(project_id, template_id):
        """Update a CLAUDE.md template (creates new version if content changed)."""
        import sqlite3

        data = request.get_json() or {}

        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row

            template = conn.execute(
                """
                SELECT * FROM project_claude_templates WHERE id = ? AND project_id = ?
            """,
                (template_id, project_id),
            ).fetchone()

            if not template:
                return api_error("Template not found", 404, "not_found")

            if "content" in data and data["content"] != template["content"]:
                new_version = template["version"] + 1
                user_id = session.get("user", "anonymous")

                if data.get("set_active", True):
                    conn.execute(
                        "UPDATE project_claude_templates SET is_active = 0 WHERE project_id = ?",
                        (project_id,),
                    )

                cursor = conn.execute(
                    """
                    INSERT INTO project_claude_templates
                        (project_id, template_name, content, description, version, is_active, variables, parent_template_id, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        project_id,
                        template["template_name"],
                        data["content"],
                        data.get("description", f"Version {new_version}"),
                        new_version,
                        1 if data.get("set_active", True) else 0,
                        json.dumps(
                            data.get("variables", json.loads(template["variables"] or "{}"))
                        ),
                        template_id,
                        user_id,
                    ),
                )

                return jsonify(
                    {
                        "success": True,
                        "template_id": cursor.lastrowid,
                        "version": new_version,
                        "action": "new_version",
                    }
                )

            updates, params = [], []
            if "description" in data:
                updates.append("description = ?")
                params.append(data["description"])
            if "variables" in data:
                updates.append("variables = ?")
                params.append(json.dumps(data["variables"]))
            if data.get("set_active"):
                conn.execute(
                    "UPDATE project_claude_templates SET is_active = 0 WHERE project_id = ?",
                    (project_id,),
                )
                updates.append("is_active = 1")

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(template_id)
                conn.execute(
                    f"UPDATE project_claude_templates SET {', '.join(updates)} WHERE id = ?", params
                )

            return jsonify({"success": True, "template_id": template_id, "action": "updated"})

    @app.route(
        "/api/projects/<int:project_id>/claude-template/<int:template_id>", methods=["DELETE"]
    )
    @require_auth
    def delete_project_claude_template(project_id, template_id):
        """Delete a CLAUDE.md template version."""
        import sqlite3

        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row

            template = conn.execute(
                """
                SELECT id, version, is_active FROM project_claude_templates WHERE id = ? AND project_id = ?
            """,
                (template_id, project_id),
            ).fetchone()

            if not template:
                return api_error("Template not found", 404, "not_found")

            conn.execute("DELETE FROM project_claude_templates WHERE id = ?", (template_id,))

            if template["is_active"]:
                conn.execute(
                    """
                    UPDATE project_claude_templates SET is_active = 1
                    WHERE project_id = ? AND id = (
                        SELECT id FROM project_claude_templates WHERE project_id = ? ORDER BY version DESC LIMIT 1
                    )
                """,
                    (project_id, project_id),
                )

            log_activity(
                conn,
                "delete_claude_template",
                "project",
                project_id,
                f"Deleted CLAUDE.md template v{template['version']}",
            )
            return jsonify({"success": True, "deleted_version": template["version"]})

    @app.route("/api/projects/<int:project_id>/claude-template/export", methods=["GET"])
    @require_auth
    def export_project_claude_template(project_id):
        """Export the CLAUDE.md template as a downloadable file."""
        import sqlite3

        version = request.args.get("version", type=int)

        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row

            project = conn.execute(
                "SELECT name, description FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not project:
                return api_error("Project not found", 404, "not_found")

            if version:
                template = conn.execute(
                    """
                    SELECT content, template_name, variables FROM project_claude_templates
                    WHERE project_id = ? AND version = ?
                """,
                    (project_id, version),
                ).fetchone()
            else:
                template = conn.execute(
                    """
                    SELECT content, template_name, variables FROM project_claude_templates
                    WHERE project_id = ? AND is_active = 1
                """,
                    (project_id,),
                ).fetchone()

            if template:
                content, filename = template["content"], template["template_name"]
                variables = json.loads(template["variables"] or "{}")
            else:
                content, filename, variables = DEFAULT_CLAUDE_TEMPLATE, "CLAUDE.md", {}

            content = content.replace("{project_name}", project["name"] or "")
            content = content.replace("{project_description}", project["description"] or "")
            for key, value in variables.items():
                content = content.replace("{" + key + "}", str(value))

            return (
                content,
                200,
                {
                    "Content-Type": "text/markdown",
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
            )

    @app.route("/api/projects/<int:project_id>/claude-template/sync", methods=["POST"])
    @require_auth
    def sync_project_claude_template(project_id):
        """Sync CLAUDE.md template to the project's source directory."""
        import sqlite3
        from pathlib import Path

        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row

            project = conn.execute(
                "SELECT name, description, source_path FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not project:
                return api_error("Project not found", 404, "not_found")
            if not project["source_path"]:
                return api_error("Project has no source_path configured", 400, "no_source_path")

            template = conn.execute(
                """
                SELECT content, template_name, variables FROM project_claude_templates
                WHERE project_id = ? AND is_active = 1
            """,
                (project_id,),
            ).fetchone()

            if template:
                content, filename = template["content"], template["template_name"]
                variables = json.loads(template["variables"] or "{}")
            else:
                content, filename, variables = DEFAULT_CLAUDE_TEMPLATE, "CLAUDE.md", {}

            content = content.replace("{project_name}", project["name"] or "")
            content = content.replace("{project_description}", project["description"] or "")
            for key, value in variables.items():
                content = content.replace("{" + key + "}", str(value))

            target_path = Path(project["source_path"]) / filename

            try:
                target_path.write_text(content)
                log_activity(
                    conn,
                    "sync_claude_template",
                    "project",
                    project_id,
                    f"Synced CLAUDE.md to {target_path}",
                )
                return jsonify(
                    {"success": True, "path": str(target_path), "project_id": project_id}
                )
            except Exception as e:
                return api_error(f"Failed to write file: {str(e)}", 500, "write_error")

    @app.route("/api/claude-templates/default", methods=["GET"])
    @require_auth
    def get_default_claude_template():
        """Get the default CLAUDE.md template."""
        return jsonify(
            {
                "template": DEFAULT_CLAUDE_TEMPLATE,
                "variables": ["{project_name}", "{project_description}"],
            }
        )
