"""
API Keys Management Routes

Flask blueprint for API key CRUD operations.
"""

import logging

from flask import Blueprint, jsonify, request, session

logger = logging.getLogger(__name__)

api_keys_bp = Blueprint("api_keys", __name__, url_prefix="/api/keys")


def get_db_path():
    """Get database path from app config."""
    from flask import current_app

    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


def require_auth(f):
    """Decorator to require authentication (session only for key management)."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


@api_keys_bp.route("", methods=["GET"])
@require_auth
def list_api_keys():
    """List API keys for current user."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")
        include_disabled = request.args.get("include_disabled", "false").lower() == "true"

        keys = service.list_keys(user_id=user_id, include_disabled=include_disabled)

        return jsonify({"keys": keys, "count": len(keys)})
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("", methods=["POST"])
@require_auth
def create_api_key():
    """Create a new API key."""
    try:
        from services.api_keys import SCOPES, get_api_key_service

        data = request.get_json()

        if not data.get("name"):
            return jsonify({"error": "Name is required"}), 400

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")

        key_data = service.create_key(
            name=data["name"],
            user_id=user_id,
            description=data.get("description"),
            scopes=data.get("scopes", ["read"]),
            rate_limit=data.get("rate_limit", 1000),
            expires_days=data.get("expires_days"),
        )

        return (
            jsonify(
                {
                    "key": key_data,
                    "message": "API key created. Save the key now - it will not be shown again.",
                    "available_scopes": SCOPES,
                }
            ),
            201,
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/<key_id>", methods=["GET"])
@require_auth
def get_api_key(key_id):
    """Get API key details."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")

        key = service.get_key(key_id)

        if not key:
            return jsonify({"error": "API key not found"}), 404

        # Only allow viewing own keys (unless admin)
        if key["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403

        return jsonify(key)
    except Exception as e:
        logger.error(f"Failed to get API key: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/<key_id>", methods=["PUT"])
@require_auth
def update_api_key(key_id):
    """Update API key settings."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")
        data = request.get_json()

        # Check ownership
        key = service.get_key(key_id)
        if not key:
            return jsonify({"error": "API key not found"}), 404
        if key["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403

        updated = service.update_key(key_id, **data)

        return jsonify(updated)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update API key: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/<key_id>", methods=["DELETE"])
@require_auth
def delete_api_key(key_id):
    """Delete an API key."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")

        # Check ownership
        key = service.get_key(key_id)
        if not key:
            return jsonify({"error": "API key not found"}), 404
        if key["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403

        if service.delete_key(key_id):
            return jsonify({"success": True, "message": f"Deleted API key '{key['name']}'"})

        return jsonify({"error": "Failed to delete key"}), 500
    except Exception as e:
        logger.error(f"Failed to delete API key: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/<key_id>/revoke", methods=["POST"])
@require_auth
def revoke_api_key(key_id):
    """Revoke (disable) an API key."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")

        # Check ownership
        key = service.get_key(key_id)
        if not key:
            return jsonify({"error": "API key not found"}), 404
        if key["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403

        if service.revoke_key(key_id):
            return jsonify({"success": True, "message": f"Revoked API key '{key['name']}'"})

        return jsonify({"error": "Failed to revoke key"}), 500
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/<key_id>/regenerate", methods=["POST"])
@require_auth
def regenerate_api_key(key_id):
    """Regenerate the secret for an API key."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")

        # Check ownership
        key = service.get_key(key_id)
        if not key:
            return jsonify({"error": "API key not found"}), 404
        if key["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403

        result = service.regenerate_key(key_id)

        if result:
            return jsonify(
                {
                    "key": result,
                    "message": "Key regenerated. Save the new key - the old key is now invalid.",
                }
            )

        return jsonify({"error": "Failed to regenerate key"}), 500
    except Exception as e:
        logger.error(f"Failed to regenerate API key: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/<key_id>/usage", methods=["GET"])
@require_auth
def get_api_key_usage(key_id):
    """Get usage history for an API key."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")
        limit = request.args.get("limit", 100, type=int)

        # Check ownership
        key = service.get_key(key_id)
        if not key:
            return jsonify({"error": "API key not found"}), 404
        if key["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403

        usage = service.get_usage(key_id, limit=limit)

        return jsonify({"usage": usage, "count": len(usage)})
    except Exception as e:
        logger.error(f"Failed to get API key usage: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/<key_id>/stats", methods=["GET"])
@require_auth
def get_api_key_stats(key_id):
    """Get statistics for an API key."""
    try:
        from services.api_keys import get_api_key_service

        service = get_api_key_service(get_db_path())
        user_id = session.get("user")

        # Check ownership
        key = service.get_key(key_id)
        if not key:
            return jsonify({"error": "API key not found"}), 404
        if key["user_id"] != user_id:
            return jsonify({"error": "Access denied"}), 403

        stats = service.get_stats(key_id)

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get API key stats: {e}")
        return jsonify({"error": str(e)}), 500


@api_keys_bp.route("/scopes", methods=["GET"])
@require_auth
def get_available_scopes():
    """Get list of available permission scopes."""
    from services.api_keys import SCOPES

    return jsonify({"scopes": SCOPES})


@api_keys_bp.route("/validate", methods=["POST"])
@require_auth
def validate_key():
    """Validate an API key (for testing)."""
    try:
        from services.api_keys import get_api_key_service

        data = request.get_json()
        api_key = data.get("key")

        if not api_key:
            return jsonify({"error": "API key is required"}), 400

        service = get_api_key_service(get_db_path())
        result = service.validate_key(api_key, log_usage=False)  # Don't log validation tests

        # Don't expose full details in validation response
        return jsonify(
            {
                "valid": result["valid"],
                "error": result.get("error"),
                "scopes": result.get("scopes") if result["valid"] else None,
            }
        )
    except Exception as e:
        logger.error(f"Failed to validate API key: {e}")
        return jsonify({"error": str(e)}), 500
