"""
Session Groups Routes

Flask blueprint for managing tmux session grouping by project.
"""

import logging

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

session_groups_bp = Blueprint("session_groups", __name__, url_prefix="/api/tmux/groups")


def get_db_path():
    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


def require_auth(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
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

        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


def get_current_user():
    return session.get("user", "anonymous")


@session_groups_bp.route("", methods=["GET"])
@require_auth
def get_grouped_sessions():
    """Get all sessions grouped by project.

    Returns:
        Groups with their sessions, collapsed states, and counts
    """
    from services.session_groups import get_session_group_service

    try:
        service = get_session_group_service(get_db_path())
        result = service.get_sessions_grouped(get_current_user())
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get grouped sessions: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/assign", methods=["POST"])
@require_auth
def assign_session_to_project():
    """Assign a session to a project.

    Request body:
        session_id: ID of the session (or use session_name)
        session_name: Name of the session (or use session_id)
        project_id: ID of the project (null to unassign)

    Returns:
        Success status
    """
    from services.session_groups import get_session_group_service

    data = request.get_json()

    if not data or (not data.get("session_id") and not data.get("session_name")):
        return jsonify({"error": "session_id or session_name required"}), 400

    try:
        service = get_session_group_service(get_db_path())
        result = service.assign_session_to_project(
            session_id=data.get("session_id"),
            session_name=data.get("session_name"),
            project_id=data.get("project_id"),
        )

        if result:
            return jsonify({"success": True})
        return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        logger.error(f"Failed to assign session: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/environment", methods=["POST"])
@require_auth
def set_session_environment():
    """Set environment for a session.

    Request body:
        session_id or session_name: Session identifier
        environment: Environment name (e.g., 'dev', 'staging', 'prod')

    Returns:
        Success status
    """
    from services.session_groups import get_session_group_service

    data = request.get_json()

    if not data or (not data.get("session_id") and not data.get("session_name")):
        return jsonify({"error": "session_id or session_name required"}), 400

    try:
        service = get_session_group_service(get_db_path())
        result = service.set_session_environment(
            session_id=data.get("session_id"),
            session_name=data.get("session_name"),
            environment=data.get("environment"),
        )

        if result:
            return jsonify({"success": True})
        return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        logger.error(f"Failed to set environment: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/worker", methods=["POST"])
@require_auth
def set_session_worker():
    """Mark/unmark a session as a worker.

    Request body:
        session_id or session_name: Session identifier
        is_worker: Boolean

    Returns:
        Success status
    """
    from services.session_groups import get_session_group_service

    data = request.get_json()

    if not data or (not data.get("session_id") and not data.get("session_name")):
        return jsonify({"error": "session_id or session_name required"}), 400

    try:
        service = get_session_group_service(get_db_path())
        result = service.set_session_worker(
            session_id=data.get("session_id"),
            session_name=data.get("session_name"),
            is_worker=data.get("is_worker", True),
        )

        if result:
            return jsonify({"success": True})
        return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        logger.error(f"Failed to set worker status: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/toggle/<group_id>", methods=["POST"])
@require_auth
def toggle_group(group_id):
    """Toggle collapsed state of a group.

    Returns:
        New collapsed state
    """
    from services.session_groups import get_session_group_service

    try:
        service = get_session_group_service(get_db_path())
        new_state = service.toggle_group_collapsed(get_current_user(), group_id)
        return jsonify({"collapsed": new_state})
    except Exception as e:
        logger.error(f"Failed to toggle group: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/collapse-all", methods=["POST"])
@require_auth
def collapse_all_groups():
    """Collapse all groups."""
    from services.session_groups import get_session_group_service

    try:
        service = get_session_group_service(get_db_path())
        count = service.collapse_all_groups(get_current_user())
        return jsonify({"success": True, "collapsed": count})
    except Exception as e:
        logger.error(f"Failed to collapse all: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/expand-all", methods=["POST"])
@require_auth
def expand_all_groups():
    """Expand all groups."""
    from services.session_groups import get_session_group_service

    try:
        service = get_session_group_service(get_db_path())
        count = service.expand_all_groups(get_current_user())
        return jsonify({"success": True, "expanded": count})
    except Exception as e:
        logger.error(f"Failed to expand all: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/collapsed", methods=["GET"])
@require_auth
def get_collapsed_groups():
    """Get list of collapsed group IDs."""
    from services.session_groups import get_session_group_service

    try:
        service = get_session_group_service(get_db_path())
        collapsed = service.get_collapsed_groups(get_current_user())
        return jsonify({"collapsed": collapsed})
    except Exception as e:
        logger.error(f"Failed to get collapsed groups: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/auto-assign", methods=["POST"])
@require_auth
def auto_assign_sessions():
    """Auto-assign sessions to projects based on naming patterns."""
    from services.session_groups import get_session_group_service

    try:
        service = get_session_group_service(get_db_path())
        result = service.auto_assign_sessions()
        return jsonify(
            {
                "success": True,
                "assigned": result["assigned"],
                "total_sessions": result["total_sessions"],
            }
        )
    except Exception as e:
        logger.error(f"Failed to auto-assign sessions: {e}")
        return jsonify({"error": str(e)}), 500


@session_groups_bp.route("/projects", methods=["GET"])
@require_auth
def get_available_projects():
    """Get list of projects available for session assignment."""
    from services.session_groups import get_session_group_service

    try:
        service = get_session_group_service(get_db_path())
        projects = service.get_available_projects()
        return jsonify({"projects": projects})
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        return jsonify({"error": str(e)}), 500
