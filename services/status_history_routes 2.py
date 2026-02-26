"""
Status History Routes

Flask blueprint for status change history API endpoints.
"""

import logging

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

status_history_bp = Blueprint("status_history", __name__, url_prefix="/api/status-history")


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
# Entity History Endpoints
# =============================================================================


@status_history_bp.route("/<entity_type>/<int:entity_id>", methods=["GET"])
@require_auth
def get_entity_history(entity_type, entity_id):
    """Get status change history for a specific entity.

    Path params:
        entity_type: 'feature', 'bug', 'task', 'milestone', 'devops_task'
        entity_id: ID of the entity

    Query params:
        limit: Maximum records to return (default 50)

    Returns:
        List of status changes for the entity
    """
    from services.status_history import ENTITY_TYPES, get_status_history_service

    if entity_type not in ENTITY_TYPES:
        return (
            jsonify({"error": f"Invalid entity_type. Must be one of: {', '.join(ENTITY_TYPES)}"}),
            400,
        )

    limit = request.args.get("limit", 50, type=int)

    service = get_status_history_service(get_db_path())
    history = service.get_entity_history(entity_type, entity_id, limit)

    return jsonify(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "history": history,
            "count": len(history),
        }
    )


@status_history_bp.route("/<entity_type>/<int:entity_id>/duration", methods=["GET"])
@require_auth
def get_status_durations(entity_type, entity_id):
    """Get time spent in each status for an entity.

    Returns:
        List of status durations with timing info
    """
    from services.status_history import ENTITY_TYPES, get_status_history_service

    if entity_type not in ENTITY_TYPES:
        return jsonify({"error": "Invalid entity_type"}), 400

    service = get_status_history_service(get_db_path())
    durations = service.get_time_in_status(entity_type, entity_id)

    # Calculate totals
    total_hours = sum(d["duration_hours"] for d in durations)
    by_status = {}
    for d in durations:
        status = d["status"]
        if status not in by_status:
            by_status[status] = 0
        by_status[status] += d["duration_hours"]

    return jsonify(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "durations": durations,
            "total_hours": round(total_hours, 2),
            "by_status": {k: round(v, 2) for k, v in by_status.items()},
        }
    )


# =============================================================================
# Recent Changes Endpoint
# =============================================================================


@status_history_bp.route("/recent", methods=["GET"])
@require_auth
def get_recent_changes():
    """Get recent status changes across all entities.

    Query params:
        entity_type: Filter by entity type (optional)
        hours: Look back period in hours (default 24)
        limit: Maximum records to return (default 100)

    Returns:
        List of recent status changes
    """
    from services.status_history import get_status_history_service

    entity_type = request.args.get("entity_type")
    hours = request.args.get("hours", 24, type=int)
    limit = request.args.get("limit", 100, type=int)

    service = get_status_history_service(get_db_path())
    changes = service.get_recent_changes(entity_type, hours, limit)

    return jsonify({"changes": changes, "count": len(changes), "period_hours": hours})


# =============================================================================
# User Activity Endpoint
# =============================================================================


@status_history_bp.route("/user/<user_id>", methods=["GET"])
@require_auth
def get_user_changes(user_id):
    """Get status changes made by a specific user.

    Query params:
        limit: Maximum records to return (default 50)

    Returns:
        List of changes by the user
    """
    from services.status_history import get_status_history_service

    limit = request.args.get("limit", 50, type=int)

    service = get_status_history_service(get_db_path())
    changes = service.get_user_changes(user_id, limit)

    return jsonify({"user_id": user_id, "changes": changes, "count": len(changes)})


@status_history_bp.route("/my-changes", methods=["GET"])
@require_auth
def get_my_changes():
    """Get status changes made by the current user.

    Query params:
        limit: Maximum records to return (default 50)

    Returns:
        List of changes by current user
    """
    from services.status_history import get_status_history_service

    limit = request.args.get("limit", 50, type=int)
    user_id = get_current_user()

    service = get_status_history_service(get_db_path())
    changes = service.get_user_changes(user_id, limit)

    return jsonify({"user_id": user_id, "changes": changes, "count": len(changes)})


# =============================================================================
# Statistics Endpoint
# =============================================================================


@status_history_bp.route("/stats", methods=["GET"])
@require_auth
def get_transition_stats():
    """Get statistics about status transitions.

    Query params:
        entity_type: Filter by entity type (optional)
        days: Look back period in days (default 30)

    Returns:
        Transition statistics
    """
    from services.status_history import get_status_history_service

    entity_type = request.args.get("entity_type")
    days = request.args.get("days", 30, type=int)

    service = get_status_history_service(get_db_path())
    stats = service.get_transition_stats(entity_type, days)

    return jsonify(stats)


# =============================================================================
# Transition Rules Endpoints
# =============================================================================


@status_history_bp.route("/transitions/<entity_type>/<status>", methods=["GET"])
@require_auth
def get_allowed_transitions(entity_type, status):
    """Get allowed transitions from a status.

    Returns:
        List of allowed next statuses
    """
    from services.status_history import get_status_history_service

    service = get_status_history_service(get_db_path())
    allowed = service.get_allowed_transitions(entity_type, status)

    return jsonify(
        {"entity_type": entity_type, "current_status": status, "allowed_transitions": allowed}
    )


@status_history_bp.route("/transitions/check", methods=["POST"])
@require_auth
def check_transition():
    """Check if a status transition is allowed.

    Request body:
        entity_type: Type of entity
        from_status: Current status
        to_status: Target status

    Returns:
        Whether the transition is allowed
    """
    from services.status_history import get_status_history_service

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["entity_type", "from_status", "to_status"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    service = get_status_history_service(get_db_path())
    result = service.is_transition_allowed(
        data["entity_type"], data["from_status"], data["to_status"]
    )

    return jsonify(
        {
            "entity_type": data["entity_type"],
            "from_status": data["from_status"],
            "to_status": data["to_status"],
            **result,
        }
    )


# =============================================================================
# Record Change Endpoint
# =============================================================================


@status_history_bp.route("/", methods=["POST"])
@require_auth
def record_change():
    """Record a status change.

    Request body:
        entity_type: Type of entity
        entity_id: ID of the entity
        old_status: Previous status (optional for new entities)
        new_status: New status
        change_reason: Optional reason for the change
        metadata: Optional additional context

    Returns:
        The created history record
    """
    from services.status_history import ENTITY_TYPES, get_status_history_service

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["entity_type", "entity_id", "new_status"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    if data["entity_type"] not in ENTITY_TYPES:
        return jsonify({"error": "Invalid entity_type"}), 400

    service = get_status_history_service(get_db_path())

    try:
        record = service.record_change(
            entity_type=data["entity_type"],
            entity_id=data["entity_id"],
            old_status=data.get("old_status"),
            new_status=data["new_status"],
            changed_by=get_current_user(),
            change_reason=data.get("change_reason"),
            change_source=data.get("change_source", "api"),
            metadata=data.get("metadata"),
        )

        if record:
            return jsonify({"success": True, "record": record}), 201
        else:
            return jsonify({"success": False, "message": "No change recorded (status unchanged)"})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# =============================================================================
# Search Endpoint
# =============================================================================


@status_history_bp.route("/search", methods=["GET"])
@require_auth
def search_history():
    """Search status history with various filters.

    Query params:
        entity_type: Filter by entity type
        status: Filter by new_status
        direction: 'to' or 'from' (with status)
        user: Filter by changed_by
        start_date: Filter by date range start
        end_date: Filter by date range end
        limit: Maximum records (default 100)

    Returns:
        Matching history records
    """
    import sqlite3

    from services.status_history import get_status_history_service

    entity_type = request.args.get("entity_type")
    status = request.args.get("status")
    direction = request.args.get("direction", "to")
    user = request.args.get("user")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    limit = request.args.get("limit", 100, type=int)

    conditions = []
    params = []

    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)

    if status:
        if direction == "to":
            conditions.append("new_status = ?")
        else:
            conditions.append("old_status = ?")
        params.append(status)

    if user:
        conditions.append("changed_by = ?")
        params.append(user)

    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row

    records = conn.execute(
        f"""
        SELECT * FROM status_history
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
    """,
        params + [limit],
    ).fetchall()

    conn.close()

    return jsonify(
        {
            "results": [dict(r) for r in records],
            "count": len(records),
            "filters": {
                "entity_type": entity_type,
                "status": status,
                "direction": direction,
                "user": user,
                "start_date": start_date,
                "end_date": end_date,
            },
        }
    )
