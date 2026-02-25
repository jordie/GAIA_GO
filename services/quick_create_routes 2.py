"""
Quick Create Routes

Flask blueprint for quick task creation API endpoints.
"""

import logging

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

quick_create_bp = Blueprint("quick_create", __name__, url_prefix="/api/quick-create")


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
# Quick Create Endpoints
# =============================================================================


@quick_create_bp.route("/", methods=["POST"])
@require_auth
def quick_create():
    """Quickly create a task/feature/bug with minimal fields.

    Request body:
        entity_type: 'feature', 'bug', 'task', 'milestone', 'devops_task'
        ... entity-specific fields

    Required fields by type:
        feature: name, project_id
        bug: title, project_id
        task: task_type
        milestone: name, project_id
        devops_task: name

    Returns:
        Created entity with ID
    """
    from services.quick_create import get_quick_create_service

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    entity_type = data.pop("entity_type", None)
    if not entity_type:
        return jsonify({"error": "entity_type is required"}), 400

    service = get_quick_create_service(get_db_path())

    try:
        result = service.quick_create(
            entity_type=entity_type, data=data, created_by=get_current_user()
        )
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Quick create failed: {e}")
        return jsonify({"error": str(e)}), 500


@quick_create_bp.route("/feature", methods=["POST"])
@require_auth
def quick_create_feature():
    """Quickly create a feature.

    Request body:
        name: Feature name (required)
        project_id: Project ID (required)
        description: Optional description
        priority: 'critical', 'high', 'medium', 'low'
        milestone_id: Optional milestone
        assigned_to: Optional assignee

    Returns:
        Created feature
    """
    from services.quick_create import get_quick_create_service

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    service = get_quick_create_service(get_db_path())

    try:
        result = service.quick_create(
            entity_type="feature", data=data, created_by=get_current_user()
        )
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@quick_create_bp.route("/bug", methods=["POST"])
@require_auth
def quick_create_bug():
    """Quickly create a bug.

    Request body:
        title: Bug title (required)
        project_id: Project ID (required)
        description: Optional description
        severity: 'critical', 'high', 'medium', 'low'
        milestone_id: Optional milestone
        assigned_to: Optional assignee

    Returns:
        Created bug
    """
    from services.quick_create import get_quick_create_service

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    service = get_quick_create_service(get_db_path())

    try:
        result = service.quick_create(entity_type="bug", data=data, created_by=get_current_user())
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@quick_create_bp.route("/task", methods=["POST"])
@require_auth
def quick_create_task():
    """Quickly create a task queue item.

    Request body:
        task_type: Type of task (required)
        name: Task name/description
        priority: Numeric priority (default 0)
        task_data: Additional task data (JSON)

    Returns:
        Created task
    """
    from services.quick_create import get_quick_create_service

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    service = get_quick_create_service(get_db_path())

    try:
        result = service.quick_create(entity_type="task", data=data, created_by=get_current_user())
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@quick_create_bp.route("/milestone", methods=["POST"])
@require_auth
def quick_create_milestone():
    """Quickly create a milestone.

    Request body:
        name: Milestone name (required)
        project_id: Project ID (required)
        description: Optional description
        target_date: Target date (YYYY-MM-DD)

    Returns:
        Created milestone
    """
    from services.quick_create import get_quick_create_service

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    service = get_quick_create_service(get_db_path())

    try:
        result = service.quick_create(
            entity_type="milestone", data=data, created_by=get_current_user()
        )
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@quick_create_bp.route("/parse", methods=["POST"])
@require_auth
def parse_quick_input():
    """Parse a quick input string into structured data.

    Supports natural language-like input:
    - "feature: Add login page @project:1 #high"
    - "bug: Button broken @2 !critical +john"
    - "task: Run tests"

    Syntax:
    - @project:N or @N - Set project ID
    - %milestone:N or %N - Set milestone ID
    - #priority - Set priority (critical, high, medium, low)
    - !severity - Set severity for bugs
    - +username - Assign to user

    Request body:
        text: Quick input text

    Returns:
        Parsed entity type and data
    """
    from services.quick_create import get_quick_create_service

    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "text is required"}), 400

    service = get_quick_create_service(get_db_path())
    result = service.parse_quick_input(data["text"])

    return jsonify(result)


@quick_create_bp.route("/parse-and-create", methods=["POST"])
@require_auth
def parse_and_create():
    """Parse quick input and create the entity.

    Request body:
        text: Quick input text
        project_id: Default project if not specified in text

    Returns:
        Created entity
    """
    from services.quick_create import get_quick_create_service

    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "text is required"}), 400

    service = get_quick_create_service(get_db_path())

    # Parse the input
    parsed = service.parse_quick_input(data["text"])

    # Apply defaults
    if data.get("project_id") and "project_id" not in parsed["data"]:
        parsed["data"]["project_id"] = data["project_id"]

    if data.get("milestone_id") and "milestone_id" not in parsed["data"]:
        parsed["data"]["milestone_id"] = data["milestone_id"]

    # Validate required fields
    entity_type = parsed["entity_type"]
    entity_data = parsed["data"]

    try:
        result = service.quick_create(
            entity_type=entity_type, data=entity_data, created_by=get_current_user()
        )
        result["parsed"] = parsed
        return jsonify(result), 201

    except ValueError as e:
        return (
            jsonify(
                {
                    "error": str(e),
                    "parsed": parsed,
                    "hint": "Use @N to set project, #priority for priority",
                }
            ),
            400,
        )


@quick_create_bp.route("/options", methods=["GET"])
@require_auth
def get_options():
    """Get options for quick create dropdowns.

    Returns:
        Available projects, milestones, task types, etc.
    """
    from services.quick_create import get_quick_create_service

    service = get_quick_create_service(get_db_path())
    options = service.get_quick_create_options()

    return jsonify(options)


@quick_create_bp.route("/templates", methods=["GET"])
@require_auth
def get_templates():
    """Get quick create templates.

    Returns:
        Common templates for quick creation
    """
    templates = [
        {
            "id": "feature_basic",
            "name": "Basic Feature",
            "entity_type": "feature",
            "template": {"name": "", "priority": "medium", "status": "planned"},
            "description": "A simple feature with default settings",
        },
        {
            "id": "feature_urgent",
            "name": "Urgent Feature",
            "entity_type": "feature",
            "template": {"name": "", "priority": "high", "status": "planned"},
            "description": "High priority feature",
        },
        {
            "id": "bug_critical",
            "name": "Critical Bug",
            "entity_type": "bug",
            "template": {"title": "", "severity": "critical", "status": "open"},
            "description": "Critical severity bug",
        },
        {
            "id": "bug_minor",
            "name": "Minor Bug",
            "entity_type": "bug",
            "template": {"title": "", "severity": "low", "status": "open"},
            "description": "Low severity bug",
        },
        {
            "id": "task_shell",
            "name": "Shell Task",
            "entity_type": "task",
            "template": {"task_type": "shell", "priority": 0},
            "description": "Shell command task",
        },
        {
            "id": "task_deploy",
            "name": "Deploy Task",
            "entity_type": "task",
            "template": {"task_type": "deploy", "priority": 5},
            "description": "Deployment task",
        },
        {
            "id": "milestone_sprint",
            "name": "Sprint Milestone",
            "entity_type": "milestone",
            "template": {"name": "", "status": "open"},
            "description": "Sprint milestone",
        },
    ]

    return jsonify({"templates": templates, "count": len(templates)})


@quick_create_bp.route("/recent", methods=["GET"])
@require_auth
def get_recent_creates():
    """Get recently created items by the current user.

    Query params:
        limit: Maximum items (default 10)

    Returns:
        Recently created items
    """
    import sqlite3

    limit = min(request.args.get("limit", 10, type=int), 50)
    user = get_current_user()

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row

    # Get recent features
    features = conn.execute(
        """
        SELECT 'feature' as entity_type, id, name as title, created_at
        FROM features
        WHERE assigned_to = ? OR assigned_to IS NULL
        ORDER BY created_at DESC
        LIMIT ?
    """,
        (user, limit),
    ).fetchall()

    # Get recent bugs
    bugs = conn.execute(
        """
        SELECT 'bug' as entity_type, id, title, created_at
        FROM bugs
        WHERE assigned_to = ? OR assigned_to IS NULL
        ORDER BY created_at DESC
        LIMIT ?
    """,
        (user, limit),
    ).fetchall()

    # Get recent tasks
    tasks = conn.execute(
        """
        SELECT 'task' as entity_type, id, task_type as title, created_at
        FROM task_queue
        ORDER BY created_at DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()

    conn.close()

    # Combine and sort
    all_items = [dict(f) for f in features] + [dict(b) for b in bugs] + [dict(t) for t in tasks]
    all_items.sort(key=lambda x: x["created_at"] or "", reverse=True)

    return jsonify({"recent": all_items[:limit], "count": len(all_items[:limit])})
