"""
Task Assignment Alerts API Routes

Flask blueprint for task assignment alert endpoints.
"""

import logging

from flask import Blueprint, jsonify, request, session

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("task_alerts", __name__, url_prefix="/api/alerts")


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


@alerts_bp.route("", methods=["GET"])
@require_auth
def get_alerts():
    """Get task assignment alerts for current user."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        user_id = session.get("user")
        unread_only = request.args.get("unread", "false").lower() == "true"
        limit = request.args.get("limit", 50, type=int)

        alerts = service.get_alerts(user_id=user_id, unread_only=unread_only, limit=limit)

        return jsonify(
            {
                "alerts": alerts,
                "count": len(alerts),
                "unread_count": service.get_unread_count(user_id),
            }
        )
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/unread-count", methods=["GET"])
@require_auth
def get_unread_count():
    """Get count of unread alerts for current user."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        user_id = session.get("user")
        count = service.get_unread_count(user_id)

        return jsonify({"count": count})
    except Exception as e:
        logger.error(f"Failed to get unread count: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/<int:alert_id>/read", methods=["POST"])
@require_auth
def mark_alert_read(alert_id):
    """Mark an alert as read."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        success = service.mark_read(alert_id)

        if success:
            return jsonify({"success": True, "alert_id": alert_id})
        return jsonify({"error": "Alert not found or already read"}), 404
    except Exception as e:
        logger.error(f"Failed to mark alert read: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/read-all", methods=["POST"])
@require_auth
def mark_all_read():
    """Mark all alerts as read for current user."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        user_id = session.get("user")
        count = service.mark_all_read(user_id)

        return jsonify({"success": True, "count": count})
    except Exception as e:
        logger.error(f"Failed to mark all read: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/<int:alert_id>/dismiss", methods=["POST"])
@require_auth
def dismiss_alert(alert_id):
    """Dismiss an alert."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        success = service.dismiss_alert(alert_id)

        if success:
            return jsonify({"success": True, "alert_id": alert_id})
        return jsonify({"error": "Alert not found or already dismissed"}), 404
    except Exception as e:
        logger.error(f"Failed to dismiss alert: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/dismiss-all", methods=["POST"])
@require_auth
def dismiss_all_alerts():
    """Dismiss all alerts for current user."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        user_id = session.get("user")
        count = service.dismiss_all(user_id)

        return jsonify({"success": True, "count": count})
    except Exception as e:
        logger.error(f"Failed to dismiss all: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/preferences", methods=["GET"])
@require_auth
def get_preferences():
    """Get alert preferences for current user."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        user_id = session.get("user")
        prefs = service.get_preferences(user_id)

        return jsonify(prefs)
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/preferences", methods=["PUT"])
@require_auth
def update_preferences():
    """Update alert preferences for current user."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        user_id = session.get("user")
        data = request.get_json()

        prefs = service.update_preferences(user_id, **data)

        return jsonify(prefs)
    except Exception as e:
        logger.error(f"Failed to update preferences: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/stats", methods=["GET"])
@require_auth
def get_stats():
    """Get alert statistics for current user."""
    try:
        from services.task_alerts import get_alert_service

        service = get_alert_service(get_db_path())
        user_id = session.get("user")
        stats = service.get_stats(user_id)

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/send", methods=["POST"])
@require_auth
def send_assignment_alert():
    """Manually send a task assignment alert."""
    try:
        from services.task_alerts import get_alert_service

        data = request.get_json()

        required = ["task_id", "task_type", "task_title", "assigned_to"]
        for field in required:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        service = get_alert_service(get_db_path())
        alert = service.create_alert(
            task_id=data["task_id"],
            task_type=data["task_type"],
            task_title=data["task_title"],
            assigned_to=data["assigned_to"],
            assigned_by=session.get("user"),
            priority=data.get("priority", "normal"),
            message=data.get("message"),
        )

        return jsonify(alert), 201
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return jsonify({"error": str(e)}), 500
