"""
Task Watchers/Subscribers Routes

Flask blueprint for managing task watchers and notifications.
"""

import logging

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

watchers_bp = Blueprint("watchers", __name__, url_prefix="/api/watchers")


def get_db_path():
    """Get database path from app config."""
    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


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

                service = get_api_key_service(get_db_path())
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


def get_current_user():
    """Get the current authenticated user."""
    return session.get("user", "anonymous")


# =============================================================================
# Watch/Unwatch Tasks
# =============================================================================


@watchers_bp.route("/watch", methods=["POST"])
@require_auth
def watch_task():
    """Subscribe to a task.

    Request body:
        task_id: ID of the task
        task_type: Type of task ('feature', 'bug', 'task_queue', 'milestone', etc.)
        watch_type: Optional - 'all', 'status', 'comments', 'assignment' (default 'all')
        notify_email: Optional - Send email notifications (default false)
        notify_dashboard: Optional - Send dashboard notifications (default true)

    Returns:
        Watcher details
    """
    from services.task_watchers import get_watcher_service

    data = request.get_json()

    if not data or not data.get("task_id") or not data.get("task_type"):
        return jsonify({"error": "task_id and task_type are required"}), 400

    try:
        service = get_watcher_service(get_db_path())
        result = service.watch_task(
            task_id=data["task_id"],
            task_type=data["task_type"],
            user_id=get_current_user(),
            watch_type=data.get("watch_type", "all"),
            notify_email=data.get("notify_email", False),
            notify_dashboard=data.get("notify_dashboard", True),
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Now watching {data['task_type']} {data['task_id']}",
                    "watcher": result,
                }
            ),
            201,
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to watch task: {e}")
        return jsonify({"error": str(e)}), 500


@watchers_bp.route("/unwatch", methods=["POST"])
@require_auth
def unwatch_task():
    """Unsubscribe from a task.

    Request body:
        task_id: ID of the task
        task_type: Type of task

    Returns:
        Success status
    """
    from services.task_watchers import get_watcher_service

    data = request.get_json()

    if not data or not data.get("task_id") or not data.get("task_type"):
        return jsonify({"error": "task_id and task_type are required"}), 400

    try:
        service = get_watcher_service(get_db_path())
        result = service.unwatch_task(
            task_id=data["task_id"], task_type=data["task_type"], user_id=get_current_user()
        )

        if result:
            return jsonify(
                {"success": True, "message": f"Unwatched {data['task_type']} {data['task_id']}"}
            )
        else:
            return jsonify({"error": "Not watching this task"}), 404

    except Exception as e:
        logger.error(f"Failed to unwatch task: {e}")
        return jsonify({"error": str(e)}), 500


@watchers_bp.route("/bulk", methods=["POST"])
@require_auth
def bulk_watch():
    """Watch or unwatch multiple tasks at once.

    Request body:
        action: 'watch' or 'unwatch'
        tasks: List of {task_id, task_type}
        watch_type: Optional - watch type for all tasks (default 'all')

    Returns:
        Results for each task
    """
    from services.task_watchers import get_watcher_service

    data = request.get_json()

    if not data or not data.get("action") or not data.get("tasks"):
        return jsonify({"error": "action and tasks are required"}), 400

    action = data["action"]
    tasks = data["tasks"]

    if action not in ["watch", "unwatch"]:
        return jsonify({"error": "action must be 'watch' or 'unwatch'"}), 400

    if not isinstance(tasks, list):
        return jsonify({"error": "tasks must be a list"}), 400

    try:
        service = get_watcher_service(get_db_path())

        if action == "watch":
            results = service.bulk_watch(
                user_id=get_current_user(), tasks=tasks, watch_type=data.get("watch_type", "all")
            )
            return jsonify(
                {
                    "success": True,
                    "action": "watch",
                    "results": results,
                    "count": len([r for r in results if "error" not in r]),
                }
            )
        else:
            count = service.bulk_unwatch(user_id=get_current_user(), tasks=tasks)
            return jsonify({"success": True, "action": "unwatch", "count": count})

    except Exception as e:
        logger.error(f"Bulk watch operation failed: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Query Watchers
# =============================================================================


@watchers_bp.route("/task/<task_type>/<int:task_id>", methods=["GET"])
@require_auth
def get_task_watchers(task_type, task_id):
    """Get all watchers for a specific task.

    Returns:
        List of watchers and current user's watch status
    """
    from services.task_watchers import get_watcher_service

    try:
        service = get_watcher_service(get_db_path())

        watchers = service.get_watchers(task_id, task_type)
        is_watching = service.is_watching(task_id, task_type, get_current_user())

        return jsonify(
            {
                "task_id": task_id,
                "task_type": task_type,
                "watchers": watchers,
                "watcher_count": len(watchers),
                "is_watching": is_watching,
            }
        )

    except Exception as e:
        logger.error(f"Failed to get watchers: {e}")
        return jsonify({"error": str(e)}), 500


@watchers_bp.route("/my-watches", methods=["GET"])
@require_auth
def get_my_watches():
    """Get all tasks the current user is watching.

    Query params:
        task_type: Optional - filter by task type

    Returns:
        List of watched tasks grouped by type
    """
    from services.task_watchers import get_watcher_service

    task_type = request.args.get("task_type")

    try:
        service = get_watcher_service(get_db_path())
        watches = service.get_user_watches(get_current_user(), task_type)

        # Group by task type
        grouped = {}
        for w in watches:
            tt = w["task_type"]
            if tt not in grouped:
                grouped[tt] = []
            grouped[tt].append(w)

        return jsonify({"watches": watches, "by_type": grouped, "total": len(watches)})

    except Exception as e:
        logger.error(f"Failed to get user watches: {e}")
        return jsonify({"error": str(e)}), 500


@watchers_bp.route("/check", methods=["GET"])
@require_auth
def check_watching():
    """Check if current user is watching a task.

    Query params:
        task_id: ID of the task
        task_type: Type of task

    Returns:
        Watch status
    """
    from services.task_watchers import get_watcher_service

    task_id = request.args.get("task_id", type=int)
    task_type = request.args.get("task_type")

    if not task_id or not task_type:
        return jsonify({"error": "task_id and task_type are required"}), 400

    try:
        service = get_watcher_service(get_db_path())
        is_watching = service.is_watching(task_id, task_type, get_current_user())

        return jsonify({"task_id": task_id, "task_type": task_type, "is_watching": is_watching})

    except Exception as e:
        logger.error(f"Failed to check watch status: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Watch Events/Notifications
# =============================================================================


@watchers_bp.route("/events", methods=["GET"])
@require_auth
def get_watch_events():
    """Get unread watch events for current user.

    Query params:
        limit: Max events to return (default 50)
        include_read: Include read events (default false)

    Returns:
        List of watch events
    """
    from services.task_watchers import get_watcher_service

    limit = request.args.get("limit", 50, type=int)

    try:
        service = get_watcher_service(get_db_path())
        events = service.get_unread_events(get_current_user(), limit)

        return jsonify({"events": events, "count": len(events)})

    except Exception as e:
        logger.error(f"Failed to get watch events: {e}")
        return jsonify({"error": str(e)}), 500


@watchers_bp.route("/events/read", methods=["POST"])
@require_auth
def mark_events_read():
    """Mark watch events as read.

    Request body:
        event_ids: Optional - list of specific event IDs (marks all if not provided)

    Returns:
        Number of events marked as read
    """
    from services.task_watchers import get_watcher_service

    data = request.get_json() or {}
    event_ids = data.get("event_ids")

    try:
        service = get_watcher_service(get_db_path())
        count = service.mark_events_read(get_current_user(), event_ids)

        return jsonify({"success": True, "marked_read": count})

    except Exception as e:
        logger.error(f"Failed to mark events read: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# User Preferences
# =============================================================================


@watchers_bp.route("/preferences", methods=["GET"])
@require_auth
def get_preferences():
    """Get current user's watch preferences."""
    from services.task_watchers import get_watcher_service

    try:
        service = get_watcher_service(get_db_path())
        prefs = service.get_watch_preferences(get_current_user())

        return jsonify(prefs)

    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        return jsonify({"error": str(e)}), 500


@watchers_bp.route("/preferences", methods=["PUT"])
@require_auth
def update_preferences():
    """Update current user's watch preferences.

    Request body (all optional):
        auto_watch_created: Auto-watch tasks you create
        auto_watch_assigned: Auto-watch tasks assigned to you
        auto_watch_commented: Auto-watch tasks you comment on
        quiet_hours_start: Start of quiet hours (e.g., '22:00')
        quiet_hours_end: End of quiet hours (e.g., '08:00')
        digest_frequency: 'instant', 'hourly', 'daily', 'weekly'

    Returns:
        Updated preferences
    """
    from services.task_watchers import get_watcher_service

    data = request.get_json()

    if not data:
        return jsonify({"error": "No preferences provided"}), 400

    try:
        service = get_watcher_service(get_db_path())
        prefs = service.set_watch_preferences(get_current_user(), **data)

        return jsonify({"success": True, "preferences": prefs})

    except Exception as e:
        logger.error(f"Failed to update preferences: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Statistics
# =============================================================================


@watchers_bp.route("/stats", methods=["GET"])
@require_auth
def get_watcher_stats():
    """Get watcher statistics.

    Query params:
        user: Optional - get stats for specific user (default: current user)
        global: Set to 'true' for global stats

    Returns:
        Watcher statistics
    """
    from services.task_watchers import get_watcher_service

    is_global = request.args.get("global", "").lower() == "true"
    user_id = request.args.get("user") or (None if is_global else get_current_user())

    try:
        service = get_watcher_service(get_db_path())
        stats = service.get_watcher_stats(user_id)

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Notify Watchers (Internal API)
# =============================================================================


@watchers_bp.route("/notify", methods=["POST"])
@require_auth
def send_notification():
    """Send notification to task watchers (for internal use).

    Request body:
        task_id: ID of the task
        task_type: Type of task
        event_type: Type of event ('status_change', 'comment_added', etc.)
        event_data: Optional - additional event details

    Returns:
        Number of watchers notified
    """
    from services.task_watchers import get_watcher_service

    data = request.get_json()

    required = ["task_id", "task_type", "event_type"]
    for field in required:
        if not data or not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    try:
        service = get_watcher_service(get_db_path())
        count = service.notify_watchers(
            task_id=data["task_id"],
            task_type=data["task_type"],
            event_type=data["event_type"],
            event_data=data.get("event_data"),
            actor=get_current_user(),
        )

        return jsonify({"success": True, "notified": count})

    except Exception as e:
        logger.error(f"Failed to notify watchers: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Watch Types Info
# =============================================================================


@watchers_bp.route("/types", methods=["GET"])
@require_auth
def get_watch_types():
    """Get available watch types and their event mappings."""
    from services.task_watchers import EVENT_TYPES, WATCH_TYPES, WATCHABLE_TASK_TYPES

    return jsonify(
        {"watch_types": WATCH_TYPES, "task_types": WATCHABLE_TASK_TYPES, "event_types": EVENT_TYPES}
    )
