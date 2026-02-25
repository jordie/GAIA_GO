"""
Scheduled Tasks API Routes

Flask blueprint for scheduled task management endpoints.
Import and register in app.py with:
    from services.scheduler_routes import scheduler_bp
    app.register_blueprint(scheduler_bp)
"""

import logging

from flask import Blueprint, jsonify, request, session

logger = logging.getLogger(__name__)

scheduler_bp = Blueprint("scheduler", __name__, url_prefix="/api/scheduled-tasks")


def get_db_path():
    """Get database path from app config."""
    from flask import current_app

    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


def require_auth(f):
    """Decorator to require authentication."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


def log_activity(action, entity_type, entity_id, details=None):
    """Log activity."""
    try:
        from flask import current_app

        if hasattr(current_app, "log_activity"):
            current_app.log_activity(action, entity_type, entity_id, details)
    except Exception:
        pass


@scheduler_bp.route("", methods=["GET"])
@require_auth
def list_scheduled_tasks():
    """List all scheduled tasks."""
    try:
        from services.scheduler import get_scheduler_service

        service = get_scheduler_service(get_db_path())
        enabled_only = request.args.get("enabled", "false").lower() == "true"
        task_type = request.args.get("type")
        limit = request.args.get("limit", 100, type=int)
        tasks = service.list_scheduled_tasks(
            enabled_only=enabled_only, task_type=task_type, limit=limit
        )
        return jsonify({"tasks": tasks, "count": len(tasks)})
    except Exception as e:
        logger.error(f"Failed to list scheduled tasks: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("", methods=["POST"])
@require_auth
def create_scheduled_task():
    """Create a new scheduled task."""
    try:
        from services.scheduler import CronError, get_scheduler_service

        data = request.get_json()
        for field in ["name", "cron_expression", "task_type"]:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400
        service = get_scheduler_service(get_db_path())
        task = service.create_scheduled_task(
            name=data["name"],
            cron_expression=data["cron_expression"],
            task_type=data["task_type"],
            task_data=data.get("task_data"),
            description=data.get("description", ""),
            priority=data.get("priority", 0),
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 300),
            enabled=data.get("enabled", True),
            created_by=session.get("user"),
        )
        log_activity("create", "scheduled_task", task["id"], task["name"])
        return jsonify(task), 201
    except (CronError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create scheduled task: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/<int:task_id>", methods=["GET"])
@require_auth
def get_scheduled_task(task_id):
    """Get a scheduled task by ID."""
    try:
        from services.scheduler import get_scheduler_service

        service = get_scheduler_service(get_db_path())
        task = service.get_scheduled_task(task_id)
        if not task:
            return jsonify({"error": "Scheduled task not found"}), 404
        return jsonify(task)
    except Exception as e:
        logger.error(f"Failed to get scheduled task: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/<int:task_id>", methods=["PUT"])
@require_auth
def update_scheduled_task(task_id):
    """Update a scheduled task."""
    try:
        from services.scheduler import CronError, get_scheduler_service

        service = get_scheduler_service(get_db_path())
        data = request.get_json()
        task = service.update_scheduled_task(task_id, **data)
        if not task:
            return jsonify({"error": "Scheduled task not found"}), 404
        log_activity("update", "scheduled_task", task_id, task["name"])
        return jsonify(task)
    except (CronError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update scheduled task: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_scheduled_task(task_id):
    """Delete a scheduled task."""
    try:
        from services.scheduler import get_scheduler_service

        service = get_scheduler_service(get_db_path())
        task = service.get_scheduled_task(task_id)
        if not task:
            return jsonify({"error": "Scheduled task not found"}), 404
        if service.delete_scheduled_task(task_id):
            log_activity("delete", "scheduled_task", task_id, task["name"])
            return jsonify({"success": True, "message": f"Deleted scheduled task '{task['name']}'"})
        return jsonify({"error": "Failed to delete task"}), 500
    except Exception as e:
        logger.error(f"Failed to delete scheduled task: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/<int:task_id>/enable", methods=["POST"])
@require_auth
def enable_scheduled_task(task_id):
    """Enable a scheduled task."""
    try:
        from services.scheduler import get_scheduler_service

        service = get_scheduler_service(get_db_path())
        task = service.enable_task(task_id)
        if not task:
            return jsonify({"error": "Scheduled task not found"}), 404
        log_activity("enable", "scheduled_task", task_id, task["name"])
        return jsonify(task)
    except Exception as e:
        logger.error(f"Failed to enable scheduled task: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/<int:task_id>/disable", methods=["POST"])
@require_auth
def disable_scheduled_task(task_id):
    """Disable a scheduled task."""
    try:
        from services.scheduler import get_scheduler_service

        service = get_scheduler_service(get_db_path())
        task = service.disable_task(task_id)
        if not task:
            return jsonify({"error": "Scheduled task not found"}), 404
        log_activity("disable", "scheduled_task", task_id, task["name"])
        return jsonify(task)
    except Exception as e:
        logger.error(f"Failed to disable scheduled task: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/<int:task_id>/history", methods=["GET"])
@require_auth
def get_scheduled_task_history(task_id):
    """Get execution history for a scheduled task."""
    try:
        from services.scheduler import get_scheduler_service

        service = get_scheduler_service(get_db_path())
        limit = request.args.get("limit", 50, type=int)
        history = service.get_run_history(task_id=task_id, limit=limit)
        return jsonify({"history": history, "count": len(history)})
    except Exception as e:
        logger.error(f"Failed to get scheduled task history: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/validate", methods=["POST"])
@require_auth
def validate_cron_expression_api():
    """Validate a cron expression."""
    try:
        from services.scheduler import CronExpression, validate_cron_expression

        data = request.get_json()
        expression = data.get("expression", "")
        if not expression:
            return jsonify({"error": "Expression is required"}), 400
        is_valid, message = validate_cron_expression(expression)
        result = {"expression": expression, "valid": is_valid, "message": message}
        if is_valid:
            cron = CronExpression(expression)
            result["next_runs"] = [dt.isoformat() for dt in cron.next_runs(5)]
        return jsonify(result)
    except Exception as e:
        return jsonify({"expression": "", "valid": False, "message": str(e)})


@scheduler_bp.route("/stats", methods=["GET"])
@require_auth
def get_scheduler_stats():
    """Get scheduler statistics."""
    try:
        from services.scheduler import get_scheduler_service

        service = get_scheduler_service(get_db_path())
        return jsonify(service.get_stats())
    except Exception as e:
        logger.error(f"Failed to get scheduler stats: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/presets", methods=["GET"])
@require_auth
def get_cron_presets():
    """Get predefined cron expression presets."""
    from services.scheduler import PREDEFINED_SCHEDULES, CronExpression

    presets = []
    descriptions = {
        "@yearly": "Once a year at midnight on January 1",
        "@annually": "Once a year at midnight on January 1",
        "@monthly": "Once a month at midnight on the 1st",
        "@weekly": "Once a week at midnight on Sunday",
        "@daily": "Once a day at midnight",
        "@midnight": "Once a day at midnight",
        "@hourly": "Once an hour at the beginning of the hour",
        "@every_5m": "Every 5 minutes",
        "@every_10m": "Every 10 minutes",
        "@every_15m": "Every 15 minutes",
        "@every_30m": "Every 30 minutes",
    }
    for name, expression in PREDEFINED_SCHEDULES.items():
        try:
            cron = CronExpression(expression)
            presets.append(
                {
                    "name": name,
                    "expression": expression,
                    "next_run": cron.next_run().isoformat(),
                    "description": descriptions.get(name, name),
                }
            )
        except Exception:
            pass
    return jsonify({"presets": presets})
