"""
Task Suggestions Routes

Flask blueprint for AI task suggestion API endpoints.
"""

import logging

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

suggestions_bp = Blueprint("suggestions", __name__, url_prefix="/api/tasks")


def get_db_path():
    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


def require_auth(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        # Check API key
        api_key = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        elif request.headers.get("X-API-Key"):
            api_key = request.headers.get("X-API-Key")

        if api_key:
            try:
                from services.api_keys import get_api_key_service

                service = get_api_key_service(get_db_path())
                if service.validate_key(api_key)["valid"]:
                    return f(*args, **kwargs)
            except Exception:
                pass

        # Check session
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


def get_current_user():
    return session.get("user", "anonymous")


# =============================================================================
# Main Suggestions Endpoint
# =============================================================================


@suggestions_bp.route("/suggested", methods=["GET"])
@require_auth
def get_suggested_tasks():
    """Get AI-powered task suggestions.

    Query params:
        project_id: Filter by project (optional)
        limit: Maximum suggestions (default 10, max 50)
        types: Comma-separated suggestion types to include (optional)
        personalized: Include personalized suggestions (default true)

    Suggestion types:
        - next_task: What to work on next
        - blocked: Items needing unblocking
        - overdue: Overdue milestones/tasks
        - dependency: Complete dependencies first
        - high_priority: Critical/high priority items
        - quick_win: Easy wins for momentum
        - stale: Items needing attention
        - review: Items ready for review
        - bottleneck: Pipeline bottlenecks

    Returns:
        Prioritized list of task suggestions with reasoning
    """
    from services.task_suggestions import get_suggestion_service

    project_id = request.args.get("project_id", type=int)
    limit = min(request.args.get("limit", 10, type=int), 50)
    types_param = request.args.get("types")
    include_personalized = request.args.get("personalized", "true").lower() == "true"

    include_types = None
    if types_param:
        include_types = [t.strip() for t in types_param.split(",")]

    user_id = get_current_user() if include_personalized else None

    service = get_suggestion_service(get_db_path())
    result = service.get_suggestions(
        project_id=project_id, user_id=user_id, limit=limit, include_types=include_types
    )

    # Add personalized suggestions if requested
    if include_personalized and user_id:
        personalized = service.get_personalized_suggestions(user_id, limit=3)
        if personalized:
            result["personalized"] = personalized

    return jsonify(result)


@suggestions_bp.route("/suggested/types", methods=["GET"])
@require_auth
def get_suggestion_types():
    """Get available suggestion types and their descriptions.

    Returns:
        List of suggestion types with descriptions
    """
    from services.task_suggestions import (
        SUGGESTION_BALANCE,
        SUGGESTION_BLOCKED,
        SUGGESTION_BOTTLENECK,
        SUGGESTION_DEPENDENCY,
        SUGGESTION_HIGH_PRIORITY,
        SUGGESTION_NEXT_TASK,
        SUGGESTION_OVERDUE,
        SUGGESTION_QUICK_WIN,
        SUGGESTION_REVIEW,
        SUGGESTION_STALE,
    )

    types = [
        {
            "id": SUGGESTION_NEXT_TASK,
            "name": "Next Task",
            "description": "Unassigned tasks ready to be claimed",
            "icon": "play",
        },
        {
            "id": SUGGESTION_HIGH_PRIORITY,
            "name": "High Priority",
            "description": "Critical and high priority items needing attention",
            "icon": "alert-triangle",
        },
        {
            "id": SUGGESTION_BLOCKED,
            "name": "Blocked Items",
            "description": "Items that are blocked and need unblocking",
            "icon": "lock",
        },
        {
            "id": SUGGESTION_OVERDUE,
            "name": "Overdue",
            "description": "Milestones and tasks past their due date",
            "icon": "clock",
        },
        {
            "id": SUGGESTION_DEPENDENCY,
            "name": "Dependencies",
            "description": "Tasks blocking other tasks",
            "icon": "git-branch",
        },
        {
            "id": SUGGESTION_QUICK_WIN,
            "name": "Quick Wins",
            "description": "Easy tasks to build momentum",
            "icon": "zap",
        },
        {
            "id": SUGGESTION_STALE,
            "name": "Stale Items",
            "description": "Items with no recent updates",
            "icon": "archive",
        },
        {
            "id": SUGGESTION_REVIEW,
            "name": "Ready for Review",
            "description": "Items waiting for review",
            "icon": "eye",
        },
        {
            "id": SUGGESTION_BOTTLENECK,
            "name": "Bottlenecks",
            "description": "Status with accumulated items",
            "icon": "alert-circle",
        },
    ]

    return jsonify({"types": types, "count": len(types)})


@suggestions_bp.route("/suggested/personalized", methods=["GET"])
@require_auth
def get_personalized_suggestions():
    """Get personalized suggestions based on user's work history.

    Query params:
        limit: Maximum suggestions (default 5)

    Returns:
        Personalized task suggestions
    """
    from services.task_suggestions import get_suggestion_service

    limit = min(request.args.get("limit", 5, type=int), 20)
    user_id = get_current_user()

    service = get_suggestion_service(get_db_path())
    suggestions = service.get_personalized_suggestions(user_id, limit)

    return jsonify({"user_id": user_id, "suggestions": suggestions, "count": len(suggestions)})


@suggestions_bp.route("/suggested/project/<int:project_id>", methods=["GET"])
@require_auth
def get_project_suggestions(project_id):
    """Get suggestions for a specific project.

    Query params:
        limit: Maximum suggestions (default 10)

    Returns:
        Task suggestions for the project
    """
    from services.task_suggestions import get_suggestion_service

    limit = min(request.args.get("limit", 10, type=int), 50)

    service = get_suggestion_service(get_db_path())
    result = service.get_suggestions(project_id=project_id, user_id=get_current_user(), limit=limit)

    result["project_id"] = project_id

    return jsonify(result)


@suggestions_bp.route("/suggested/quick-wins", methods=["GET"])
@require_auth
def get_quick_wins():
    """Get quick win suggestions only.

    Query params:
        project_id: Filter by project (optional)
        limit: Maximum suggestions (default 5)

    Returns:
        Quick win task suggestions
    """
    from services.task_suggestions import SUGGESTION_QUICK_WIN, get_suggestion_service

    project_id = request.args.get("project_id", type=int)
    limit = min(request.args.get("limit", 5, type=int), 20)

    service = get_suggestion_service(get_db_path())
    result = service.get_suggestions(
        project_id=project_id, limit=limit, include_types=[SUGGESTION_QUICK_WIN]
    )

    return jsonify({"quick_wins": result["suggestions"], "count": len(result["suggestions"])})


@suggestions_bp.route("/suggested/urgent", methods=["GET"])
@require_auth
def get_urgent_suggestions():
    """Get urgent suggestions (high priority, blocked, overdue).

    Query params:
        project_id: Filter by project (optional)
        limit: Maximum suggestions (default 10)

    Returns:
        Urgent task suggestions
    """
    from services.task_suggestions import (
        SUGGESTION_BLOCKED,
        SUGGESTION_HIGH_PRIORITY,
        SUGGESTION_OVERDUE,
        get_suggestion_service,
    )

    project_id = request.args.get("project_id", type=int)
    limit = min(request.args.get("limit", 10, type=int), 50)

    service = get_suggestion_service(get_db_path())
    result = service.get_suggestions(
        project_id=project_id,
        limit=limit,
        include_types=[SUGGESTION_HIGH_PRIORITY, SUGGESTION_BLOCKED, SUGGESTION_OVERDUE],
    )

    return jsonify(
        {
            "urgent": result["suggestions"],
            "count": len(result["suggestions"]),
            "summary": result["summary"],
        }
    )


@suggestions_bp.route("/suggested/next", methods=["GET"])
@require_auth
def get_next_task():
    """Get the single best next task suggestion.

    Query params:
        project_id: Filter by project (optional)

    Returns:
        The top suggested task
    """
    from services.task_suggestions import get_suggestion_service

    project_id = request.args.get("project_id", type=int)
    user_id = get_current_user()

    service = get_suggestion_service(get_db_path())
    result = service.get_suggestions(project_id=project_id, user_id=user_id, limit=1)

    if result["suggestions"]:
        return jsonify({"suggestion": result["suggestions"][0], "summary": result["summary"]})
    else:
        return jsonify(
            {
                "suggestion": None,
                "message": "No suggestions available",
                "summary": result["summary"],
            }
        )


@suggestions_bp.route("/suggested/summary", methods=["GET"])
@require_auth
def get_suggestions_summary():
    """Get summary of work items for suggestions context.

    Query params:
        project_id: Filter by project (optional)

    Returns:
        Summary statistics for features, bugs, and tasks
    """
    from services.task_suggestions import get_suggestion_service

    project_id = request.args.get("project_id", type=int)

    service = get_suggestion_service(get_db_path())
    result = service.get_suggestions(project_id=project_id, limit=0)  # Just get summary

    return jsonify({"summary": result["summary"], "project_id": project_id})
