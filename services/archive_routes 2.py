"""
Project Archive Routes

Flask blueprint for archiving, restoring, and managing archived projects.
"""

import logging
import sqlite3
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

archive_bp = Blueprint("archive", __name__, url_prefix="/api/projects")


def get_db_connection():
    """Get database connection."""
    from flask import g

    db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))
    if "db" not in g:
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db


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

                db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))
                service = get_api_key_service(db_path)
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


def log_activity(action, entity_type, entity_id, details=None):
    """Log an activity to the activity log."""
    try:
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO activity_log (action, entity_type, entity_id, details, user, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (action, entity_type, entity_id, details, session.get("user", "system")),
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"Failed to log activity: {e}")


@archive_bp.route("/archive", methods=["GET"])
@require_auth
def list_archived_projects():
    """List all archived projects.

    Query params:
        page: Page number (default 1)
        per_page: Items per page (default 20)
        search: Search term for name/description
        sort_by: Sort field - 'name', 'archived_at', 'created_at' (default 'updated_at')
        sort_order: 'asc' or 'desc' (default 'desc')

    Returns:
        List of archived projects with counts
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    search = request.args.get("search", "")
    sort_by = request.args.get("sort_by", "updated_at")
    sort_order = request.args.get("sort_order", "desc").upper()

    conn = get_db_connection()

    # Validate sort parameters
    allowed_sorts = ["name", "updated_at", "created_at", "priority"]
    if sort_by not in allowed_sorts:
        sort_by = "updated_at"
    if sort_order not in ["ASC", "DESC"]:
        sort_order = "DESC"

    # Build query
    conditions = ["p.status = 'archived'"]
    params = []

    if search:
        conditions.append("(p.name LIKE ? OR p.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_clause = " AND ".join(conditions)

    # Get total count
    count_result = conn.execute(
        f"""
        SELECT COUNT(*) as total FROM projects p WHERE {where_clause}
    """,
        params,
    ).fetchone()
    total = count_result["total"]

    # Get paginated results
    offset = (page - 1) * per_page
    projects = conn.execute(
        f"""
        SELECT p.*,
               COALESCE(fc.cnt, 0) as feature_count,
               COALESCE(bc.cnt, 0) as bug_count,
               COALESCE(mc.cnt, 0) as milestone_count
        FROM projects p
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM features GROUP BY project_id) fc ON p.id = fc.project_id
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM bugs GROUP BY project_id) bc ON p.id = bc.project_id
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM milestones GROUP BY project_id) mc ON p.id = mc.project_id
        WHERE {where_clause}
        ORDER BY p.{sort_by} {sort_order}
        LIMIT ? OFFSET ?
    """,
        params + [per_page, offset],
    ).fetchall()

    project_list = []
    for p in projects:
        p_dict = dict(p)
        # Calculate days since archived
        if p_dict.get("updated_at"):
            try:
                updated = datetime.fromisoformat(p_dict["updated_at"].replace("Z", "+00:00"))
                p_dict["days_archived"] = (datetime.now() - updated.replace(tzinfo=None)).days
            except (ValueError, TypeError):
                p_dict["days_archived"] = None
        project_list.append(p_dict)

    return jsonify(
        {
            "projects": project_list,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        }
    )


@archive_bp.route("/archive", methods=["POST"])
@require_auth
def archive_project():
    """Archive a project.

    Request body:
        project_id: ID of project to archive
        reason: Optional reason for archiving

    Returns:
        Success status and archived project details
    """
    data = request.get_json()

    if not data or not data.get("project_id"):
        return jsonify({"error": "project_id is required"}), 400

    project_id = data["project_id"]
    reason = data.get("reason", "")

    conn = get_db_connection()

    # Check if project exists and is not already archived
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

    if not project:
        return jsonify({"error": "Project not found"}), 404

    if project["status"] == "archived":
        return jsonify({"error": "Project is already archived"}), 400

    # Archive the project
    conn.execute(
        """
        UPDATE projects
        SET status = 'archived', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (project_id,),
    )
    conn.commit()

    log_activity("archive_project", "project", project_id, reason)

    return jsonify(
        {
            "success": True,
            "message": f"Project '{project['name']}' has been archived",
            "project_id": project_id,
        }
    )


@archive_bp.route("/archive/bulk", methods=["POST"])
@require_auth
def bulk_archive_projects():
    """Bulk archive old inactive projects.

    Request body:
        inactive_days: Archive projects with no updates in this many days (default 180)
        dry_run: If true, return list of projects that would be archived without archiving (default false)
        exclude_ids: List of project IDs to exclude from archiving

    Returns:
        List of archived (or would-be-archived) projects
    """
    data = request.get_json() or {}

    inactive_days = data.get("inactive_days", 180)
    dry_run = data.get("dry_run", False)
    exclude_ids = data.get("exclude_ids", [])

    conn = get_db_connection()

    cutoff_date = datetime.now() - timedelta(days=inactive_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

    # Find inactive projects
    query = """
        SELECT p.id, p.name, p.updated_at,
               COALESCE(fc.cnt, 0) as feature_count,
               COALESCE(bc.cnt, 0) as bug_count
        FROM projects p
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM features GROUP BY project_id) fc ON p.id = fc.project_id
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM bugs GROUP BY project_id) bc ON p.id = bc.project_id
        WHERE p.status != 'archived'
        AND p.updated_at < ?
    """
    params = [cutoff_str]

    if exclude_ids:
        placeholders = ",".join("?" * len(exclude_ids))
        query += f" AND p.id NOT IN ({placeholders})"
        params.extend(exclude_ids)

    query += " ORDER BY p.updated_at ASC"

    candidates = conn.execute(query, params).fetchall()

    project_list = []
    for p in candidates:
        p_dict = dict(p)
        try:
            updated = datetime.fromisoformat(p_dict["updated_at"].replace("Z", "+00:00"))
            p_dict["days_inactive"] = (datetime.now() - updated.replace(tzinfo=None)).days
        except (ValueError, TypeError):
            p_dict["days_inactive"] = inactive_days
        project_list.append(p_dict)

    if dry_run:
        return jsonify(
            {
                "dry_run": True,
                "projects_to_archive": project_list,
                "count": len(project_list),
                "criteria": {"inactive_days": inactive_days, "cutoff_date": cutoff_str},
            }
        )

    # Archive the projects
    if project_list:
        project_ids = [p["id"] for p in project_list]
        placeholders = ",".join("?" * len(project_ids))
        conn.execute(
            f"""
            UPDATE projects
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """,
            project_ids,
        )
        conn.commit()

        log_activity(
            "bulk_archive",
            "project",
            None,
            f"Archived {len(project_list)} projects inactive for {inactive_days}+ days",
        )

    return jsonify(
        {
            "success": True,
            "archived_projects": project_list,
            "count": len(project_list),
            "criteria": {"inactive_days": inactive_days, "cutoff_date": cutoff_str},
        }
    )


@archive_bp.route("/<int:project_id>/restore", methods=["POST"])
@require_auth
def restore_project(project_id):
    """Restore an archived project.

    Returns:
        Success status and restored project details
    """
    conn = get_db_connection()

    # Check if project exists and is archived
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

    if not project:
        return jsonify({"error": "Project not found"}), 404

    if project["status"] != "archived":
        return jsonify({"error": "Project is not archived"}), 400

    # Restore the project
    conn.execute(
        """
        UPDATE projects
        SET status = 'active', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (project_id,),
    )
    conn.commit()

    log_activity("restore_project", "project", project_id)

    return jsonify(
        {
            "success": True,
            "message": f"Project '{project['name']}' has been restored",
            "project_id": project_id,
        }
    )


@archive_bp.route("/archive/<int:project_id>", methods=["DELETE"])
@require_auth
def permanently_delete_project(project_id):
    """Permanently delete an archived project and all its data.

    Query params:
        confirm: Must be 'true' to confirm permanent deletion

    Returns:
        Success status with deletion summary
    """
    confirm = request.args.get("confirm", "").lower() == "true"

    if not confirm:
        return (
            jsonify(
                {
                    "error": "Permanent deletion requires confirmation. Add ?confirm=true to proceed.",
                    "warning": "This action cannot be undone. All project data will be permanently deleted.",
                }
            ),
            400,
        )

    conn = get_db_connection()

    # Check if project exists and is archived
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

    if not project:
        return jsonify({"error": "Project not found"}), 404

    if project["status"] != "archived":
        return (
            jsonify(
                {
                    "error": "Only archived projects can be permanently deleted",
                    "hint": "Archive the project first, then delete it permanently",
                }
            ),
            400,
        )

    # Count related data before deletion
    counts = {}
    for table in ["features", "bugs", "milestones", "errors"]:
        result = conn.execute(
            f"""
            SELECT COUNT(*) as cnt FROM {table} WHERE project_id = ?
        """,
            (project_id,),
        ).fetchone()
        counts[table] = result["cnt"]

    # Delete related data (cascading)
    for table in ["features", "bugs", "milestones", "errors"]:
        conn.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))

    # Delete the project
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()

    log_activity(
        "permanent_delete_project",
        "project",
        project_id,
        f"Deleted with {sum(counts.values())} related items",
    )

    return jsonify(
        {
            "success": True,
            "message": f"Project '{project['name']}' has been permanently deleted",
            "deleted_items": counts,
        }
    )


@archive_bp.route("/archive/stats", methods=["GET"])
@require_auth
def get_archive_stats():
    """Get archive statistics.

    Returns:
        Statistics about archived projects and related data
    """
    conn = get_db_connection()

    # Get overall counts
    stats = conn.execute(
        """
        SELECT
            COUNT(*) as total_projects,
            SUM(CASE WHEN status = 'archived' THEN 1 ELSE 0 END) as archived_projects,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_projects
        FROM projects
    """
    ).fetchone()

    # Get archived project details
    archived_details = conn.execute(
        """
        SELECT p.id, p.name, p.updated_at,
               COALESCE(fc.cnt, 0) as feature_count,
               COALESCE(bc.cnt, 0) as bug_count,
               COALESCE(mc.cnt, 0) as milestone_count
        FROM projects p
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM features GROUP BY project_id) fc ON p.id = fc.project_id
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM bugs GROUP BY project_id) bc ON p.id = bc.project_id
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM milestones GROUP BY project_id) mc ON p.id = mc.project_id
        WHERE p.status = 'archived'
    """
    ).fetchall()

    # Calculate storage used by archived projects
    total_features = 0
    total_bugs = 0
    total_milestones = 0
    oldest_archive = None
    newest_archive = None

    for p in archived_details:
        p_dict = dict(p)
        total_features += p_dict["feature_count"]
        total_bugs += p_dict["bug_count"]
        total_milestones += p_dict["milestone_count"]

        if p_dict.get("updated_at"):
            if oldest_archive is None or p_dict["updated_at"] < oldest_archive:
                oldest_archive = p_dict["updated_at"]
            if newest_archive is None or p_dict["updated_at"] > newest_archive:
                newest_archive = p_dict["updated_at"]

    # Find candidates for archiving (inactive 90+ days)
    cutoff_90 = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
    archive_candidates = conn.execute(
        """
        SELECT COUNT(*) as cnt FROM projects
        WHERE status != 'archived' AND updated_at < ?
    """,
        (cutoff_90,),
    ).fetchone()

    return jsonify(
        {
            "summary": {
                "total_projects": stats["total_projects"],
                "active_projects": stats["active_projects"],
                "archived_projects": stats["archived_projects"],
                "archive_percentage": round(
                    (stats["archived_projects"] / stats["total_projects"] * 100)
                    if stats["total_projects"] > 0
                    else 0,
                    1,
                ),
            },
            "archived_data": {
                "total_features": total_features,
                "total_bugs": total_bugs,
                "total_milestones": total_milestones,
                "total_items": total_features + total_bugs + total_milestones,
            },
            "timeline": {"oldest_archived": oldest_archive, "newest_archived": newest_archive},
            "recommendations": {
                "archive_candidates_90_days": archive_candidates["cnt"],
                "suggestion": f"{archive_candidates['cnt']} projects have been inactive for 90+ days and could be archived"
                if archive_candidates["cnt"] > 0
                else "No projects recommended for archiving",
            },
        }
    )


@archive_bp.route("/archive/cleanup", methods=["POST"])
@require_auth
def cleanup_old_archives():
    """Clean up (permanently delete) very old archived projects.

    Request body:
        older_than_days: Delete archives older than this many days (minimum 365, default 730)
        dry_run: If true, return list without deleting (default true for safety)

    Returns:
        List of deleted (or would-be-deleted) projects
    """
    data = request.get_json() or {}

    older_than_days = max(data.get("older_than_days", 730), 365)  # Minimum 1 year
    dry_run = data.get("dry_run", True)  # Default to dry run for safety

    conn = get_db_connection()

    cutoff_date = datetime.now() - timedelta(days=older_than_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

    # Find old archived projects
    old_archives = conn.execute(
        """
        SELECT p.id, p.name, p.updated_at,
               COALESCE(fc.cnt, 0) as feature_count,
               COALESCE(bc.cnt, 0) as bug_count
        FROM projects p
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM features GROUP BY project_id) fc ON p.id = fc.project_id
        LEFT JOIN (SELECT project_id, COUNT(*) as cnt FROM bugs GROUP BY project_id) bc ON p.id = bc.project_id
        WHERE p.status = 'archived'
        AND p.updated_at < ?
        ORDER BY p.updated_at ASC
    """,
        (cutoff_str,),
    ).fetchall()

    project_list = [dict(p) for p in old_archives]

    if dry_run:
        return jsonify(
            {
                "dry_run": True,
                "projects_to_delete": project_list,
                "count": len(project_list),
                "criteria": {"older_than_days": older_than_days, "cutoff_date": cutoff_str},
                "warning": "Set dry_run to false to actually delete these projects",
            }
        )

    # Delete old archives and their related data
    deleted_counts = {"features": 0, "bugs": 0, "milestones": 0, "errors": 0}

    for p in project_list:
        for table in ["features", "bugs", "milestones", "errors"]:
            result = conn.execute(
                f"""
                DELETE FROM {table} WHERE project_id = ?
            """,
                (p["id"],),
            )
            deleted_counts[table] += result.rowcount

        conn.execute("DELETE FROM projects WHERE id = ?", (p["id"],))

    conn.commit()

    log_activity(
        "cleanup_archives",
        "project",
        None,
        f"Permanently deleted {len(project_list)} projects archived for {older_than_days}+ days",
    )

    return jsonify(
        {
            "success": True,
            "deleted_projects": project_list,
            "count": len(project_list),
            "deleted_items": deleted_counts,
            "criteria": {"older_than_days": older_than_days, "cutoff_date": cutoff_str},
        }
    )
