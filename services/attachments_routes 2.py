"""
Task Attachments Routes

Flask blueprint for file uploads, downloads, and previews.
"""

import logging
import os
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request, send_file, session

logger = logging.getLogger(__name__)

attachments_bp = Blueprint("attachments", __name__, url_prefix="/api/attachments")


def get_db_path():
    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


def get_upload_dir():
    return str(current_app.config.get("UPLOAD_DIR", "data/attachments"))


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


# =============================================================================
# Upload Endpoints
# =============================================================================


@attachments_bp.route("/upload", methods=["POST"])
@require_auth
def upload_attachment():
    """Upload a file attachment.

    Form data:
        file: The file to upload
        task_id: ID of the task
        task_type: Type of task ('feature', 'bug', 'task_queue', etc.)
        description: Optional description

    Returns:
        Attachment details
    """
    from services.attachments import get_attachment_service

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    task_id = request.form.get("task_id", type=int)
    task_type = request.form.get("task_type")
    description = request.form.get("description", "")

    if not task_id or not task_type:
        return jsonify({"error": "task_id and task_type are required"}), 400

    try:
        service = get_attachment_service(get_db_path(), get_upload_dir())

        # Read file content
        file_content = file.read()

        # Validate before upload
        validation = service.validate_file(file.filename, len(file_content))
        if not validation["valid"]:
            return jsonify({"error": validation["error"]}), 400

        # Upload
        attachment = service.upload_file(
            file_content=file_content,
            original_filename=file.filename,
            task_id=task_id,
            task_type=task_type,
            user_id=get_current_user(),
            description=description,
        )

        return jsonify({"success": True, "attachment": attachment}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return jsonify({"error": str(e)}), 500


@attachments_bp.route("/upload/validate", methods=["POST"])
@require_auth
def validate_upload():
    """Validate a file before upload.

    Request body:
        filename: Filename to validate
        size: File size in bytes

    Returns:
        Validation result
    """
    from services.attachments import get_attachment_service

    data = request.get_json()
    if not data or not data.get("filename"):
        return jsonify({"error": "filename is required"}), 400

    service = get_attachment_service(get_db_path(), get_upload_dir())
    result = service.validate_file(data["filename"], data.get("size", 0))

    return jsonify(result)


# =============================================================================
# Download/View Endpoints
# =============================================================================


@attachments_bp.route("/<int:attachment_id>/download", methods=["GET"])
@require_auth
def download_attachment(attachment_id):
    """Download an attachment file."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())
    attachment = service.get_attachment(attachment_id)

    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404

    file_path = Path(attachment["file_path"])
    if not file_path.exists():
        return jsonify({"error": "File not found on disk"}), 404

    return send_file(
        file_path,
        mimetype=attachment["mime_type"],
        as_attachment=True,
        download_name=attachment["original_filename"],
    )


@attachments_bp.route("/<int:attachment_id>/view", methods=["GET"])
@require_auth
def view_attachment(attachment_id):
    """View an attachment inline (for images, PDFs, etc.)."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())
    attachment = service.get_attachment(attachment_id)

    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404

    file_path = Path(attachment["file_path"])
    if not file_path.exists():
        return jsonify({"error": "File not found on disk"}), 404

    return send_file(file_path, mimetype=attachment["mime_type"], as_attachment=False)


@attachments_bp.route("/<int:attachment_id>/preview", methods=["GET"])
@require_auth
def get_preview(attachment_id):
    """Get preview image for an attachment."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())
    preview_path = service.get_preview_path(attachment_id)

    if not preview_path or not preview_path.exists():
        # Return original if no preview
        attachment = service.get_attachment(attachment_id)
        if attachment and Path(attachment["file_path"]).exists():
            return send_file(attachment["file_path"], mimetype=attachment["mime_type"])
        return jsonify({"error": "Preview not available"}), 404

    return send_file(preview_path, mimetype="image/jpeg")


@attachments_bp.route("/<int:attachment_id>/thumbnail", methods=["GET"])
@require_auth
def get_thumbnail(attachment_id):
    """Get thumbnail image for an attachment."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())
    thumbnail_path = service.get_thumbnail_path(attachment_id)

    if not thumbnail_path or not thumbnail_path.exists():
        return jsonify({"error": "Thumbnail not available"}), 404

    return send_file(thumbnail_path, mimetype="image/jpeg")


# =============================================================================
# Query Endpoints
# =============================================================================


@attachments_bp.route("/<int:attachment_id>", methods=["GET"])
@require_auth
def get_attachment(attachment_id):
    """Get attachment details."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())
    attachment = service.get_attachment(attachment_id)

    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404

    return jsonify(attachment)


@attachments_bp.route("/task/<task_type>/<int:task_id>", methods=["GET"])
@require_auth
def get_task_attachments(task_type, task_id):
    """Get all attachments for a task."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())
    attachments = service.get_task_attachments(task_id, task_type)

    return jsonify({"attachments": attachments, "count": len(attachments)})


@attachments_bp.route("/my-uploads", methods=["GET"])
@require_auth
def get_my_uploads():
    """Get attachments uploaded by current user."""
    from services.attachments import get_attachment_service

    limit = request.args.get("limit", 50, type=int)

    service = get_attachment_service(get_db_path(), get_upload_dir())
    attachments = service.get_user_attachments(get_current_user(), limit)

    return jsonify({"attachments": attachments, "count": len(attachments)})


@attachments_bp.route("/search", methods=["GET"])
@require_auth
def search_attachments():
    """Search attachments.

    Query params:
        q: Search query (filename or description)
        task_type: Filter by task type
        mime_type: Filter by MIME type prefix (e.g., 'image/')
        limit: Max results (default 50)
    """
    from services.attachments import get_attachment_service

    query = request.args.get("q")
    task_type = request.args.get("task_type")
    mime_type = request.args.get("mime_type")
    limit = request.args.get("limit", 50, type=int)

    service = get_attachment_service(get_db_path(), get_upload_dir())
    attachments = service.search_attachments(
        query=query, task_type=task_type, mime_type=mime_type, limit=limit
    )

    return jsonify({"attachments": attachments, "count": len(attachments)})


# =============================================================================
# Delete Endpoint
# =============================================================================


@attachments_bp.route("/<int:attachment_id>", methods=["DELETE"])
@require_auth
def delete_attachment(attachment_id):
    """Delete an attachment."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())

    try:
        result = service.delete_attachment(attachment_id, get_current_user())

        if result:
            return jsonify({"success": True, "message": "Attachment deleted"})
        return jsonify({"error": "Attachment not found"}), 404

    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Comments Endpoints
# =============================================================================


@attachments_bp.route("/<int:attachment_id>/comments", methods=["GET"])
@require_auth
def get_comments(attachment_id):
    """Get comments for an attachment."""
    from services.attachments import get_attachment_service

    service = get_attachment_service(get_db_path(), get_upload_dir())
    comments = service.get_comments(attachment_id)

    return jsonify({"comments": comments, "count": len(comments)})


@attachments_bp.route("/<int:attachment_id>/comments", methods=["POST"])
@require_auth
def add_comment(attachment_id):
    """Add a comment to an attachment."""
    from services.attachments import get_attachment_service

    data = request.get_json()
    if not data or not data.get("comment"):
        return jsonify({"error": "comment is required"}), 400

    service = get_attachment_service(get_db_path(), get_upload_dir())

    # Check attachment exists
    if not service.get_attachment(attachment_id):
        return jsonify({"error": "Attachment not found"}), 404

    comment = service.add_comment(
        attachment_id=attachment_id, user_id=get_current_user(), comment=data["comment"]
    )

    return jsonify(comment), 201


# =============================================================================
# Stats Endpoint
# =============================================================================


@attachments_bp.route("/stats", methods=["GET"])
@require_auth
def get_stats():
    """Get attachment statistics.

    Query params:
        task_id: Optional task ID
        task_type: Optional task type (required if task_id provided)
    """
    from services.attachments import get_attachment_service

    task_id = request.args.get("task_id", type=int)
    task_type = request.args.get("task_type")

    service = get_attachment_service(get_db_path(), get_upload_dir())
    stats = service.get_stats(task_id, task_type)

    return jsonify(stats)


# =============================================================================
# Allowed Types Info
# =============================================================================


@attachments_bp.route("/allowed-types", methods=["GET"])
@require_auth
def get_allowed_types():
    """Get list of allowed file types."""
    from services.attachments import ALLOWED_EXTENSIONS, MAX_FILE_SIZE

    # Group by category
    by_category = {}
    for ext, category in ALLOWED_EXTENSIONS.items():
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(ext)

    return jsonify(
        {
            "extensions": list(ALLOWED_EXTENSIONS.keys()),
            "by_category": by_category,
            "max_file_size": MAX_FILE_SIZE,
            "max_file_size_mb": MAX_FILE_SIZE / (1024 * 1024),
        }
    )
