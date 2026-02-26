"""API routes for Reputation System management.

Endpoints for:
- Viewing user reputation and details
- Recording events
- Managing VIP tiers
- Leaderboards and statistics
- Admin operations
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import logging
from services.reputation_system import get_reputation_system

logger = logging.getLogger(__name__)

# Create blueprint
reputation_bp = Blueprint("reputation", __name__, url_prefix="/api/reputation")


def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        # This assumes Flask-Login is being used
        from flask_login import current_user
        if not current_user or not current_user.is_authenticated:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        if not current_user or not current_user.is_authenticated:
            return jsonify({"error": "Unauthorized"}), 401
        # Check if user has admin role (adjust based on your user model)
        if not getattr(current_user, "is_admin", False):
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Public User Endpoints
# ============================================================================

@reputation_bp.route("/users/<int:user_id>", methods=["GET"])
@require_auth
def get_user_reputation(user_id):
    """Get reputation details for a user.

    Args:
        user_id: User ID

    Returns:
        JSON with reputation details
    """
    try:
        reputation_system = get_reputation_system()
        details = reputation_system.get_reputation_details(user_id)

        if not details:
            return jsonify({"error": "User not found"}), 404

        return jsonify(details), 200
    except Exception as e:
        logger.error(f"Error getting reputation for user {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@reputation_bp.route("/users/<int:user_id>/history", methods=["GET"])
@require_auth
def get_user_event_history(user_id):
    """Get reputation event history for a user.

    Query Parameters:
        limit: Maximum number of events (default: 50)

    Returns:
        JSON with event history
    """
    try:
        limit = request.args.get("limit", 50, type=int)
        limit = min(limit, 100)  # Cap at 100

        reputation_system = get_reputation_system()
        events = reputation_system.get_event_history(user_id, limit=limit)

        return jsonify({"events": events, "count": len(events)}), 200
    except Exception as e:
        logger.error(f"Error getting history for user {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# Admin Endpoints
# ============================================================================

@reputation_bp.route("/users/<int:user_id>/vip", methods=["POST"])
@require_admin
def set_vip_tier(user_id):
    """Set VIP tier for a user.

    Request Body:
        {
            "tier": "premium",
            "limit_multiplier": 2.0,
            "notes": "API partner"
        }

    Returns:
        JSON with success status
    """
    try:
        data = request.get_json()

        if not data or "tier" not in data:
            return jsonify({"error": "Missing required field: tier"}), 400

        tier = data["tier"]
        limit_multiplier = data.get("limit_multiplier", 2.0)
        notes = data.get("notes", "")

        reputation_system = get_reputation_system()
        from flask_login import current_user

        success = reputation_system.set_vip_tier(
            user_id,
            tier=tier,
            limit_multiplier=limit_multiplier,
            notes=notes,
            approved_by=current_user.id if hasattr(current_user, "id") else None,
        )

        if not success:
            return jsonify({"error": "Failed to set VIP tier"}), 500

        return jsonify({
            "success": True,
            "user_id": user_id,
            "tier": tier,
            "limit_multiplier": limit_multiplier,
        }), 201
    except Exception as e:
        logger.error(f"Error setting VIP tier for user {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@reputation_bp.route("/users/<int:user_id>/vip", methods=["DELETE"])
@require_admin
def remove_vip_tier(user_id):
    """Remove VIP tier for a user.

    Returns:
        JSON with success status
    """
    try:
        reputation_system = get_reputation_system()
        success = reputation_system.remove_vip_tier(user_id)

        if not success:
            return jsonify({"error": "Failed to remove VIP tier"}), 500

        return jsonify({
            "success": True,
            "user_id": user_id,
            "message": "VIP tier removed, user reverts to reputation-based limits",
        }), 200
    except Exception as e:
        logger.error(f"Error removing VIP tier for user {user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# Leaderboards and Statistics
# ============================================================================

@reputation_bp.route("/leaderboard", methods=["GET"])
@require_auth
def get_leaderboard():
    """Get top users by reputation score.

    Query Parameters:
        limit: Number of users (default: 10, max: 100)
        metric: Sort metric (score, violations, clean)

    Returns:
        JSON with top users
    """
    try:
        limit = request.args.get("limit", 10, type=int)
        metric = request.args.get("metric", "score")

        limit = min(limit, 100)  # Cap at 100

        reputation_system = get_reputation_system()
        users = reputation_system.get_top_users(limit=limit, metric=metric)

        return jsonify({
            "leaderboard": users,
            "count": len(users),
            "metric": metric,
        }), 200
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({"error": "Internal server error"}), 500


@reputation_bp.route("/statistics", methods=["GET"])
@require_auth
def get_statistics():
    """Get system-wide reputation statistics.

    Returns:
        JSON with statistics
    """
    try:
        reputation_system = get_reputation_system()
        stats = reputation_system.get_statistics()

        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# Event Recording (Admin/System)
# ============================================================================

@reputation_bp.route("/events", methods=["POST"])
@require_admin
def record_event():
    """Record a reputation event for a user.

    Request Body:
        {
            "user_id": 123,
            "event_type": "rate_limit_violation",
            "severity": 5,
            "description": "Exceeded API limit"
        }

    Returns:
        JSON with success status
    """
    try:
        data = request.get_json()

        if not data or "user_id" not in data or "event_type" not in data:
            return jsonify({"error": "Missing required fields"}), 400

        user_id = data["user_id"]
        event_type = data["event_type"]
        severity = data.get("severity", 1)
        description = data.get("description", "")

        reputation_system = get_reputation_system()
        success = reputation_system.record_event(
            user_id,
            event_type=event_type,
            severity=severity,
            description=description,
        )

        if not success:
            return jsonify({"error": "Failed to record event"}), 500

        # Get updated reputation
        updated_score = reputation_system.get_reputation(user_id)
        tier = reputation_system.get_tier_for_score(updated_score)

        return jsonify({
            "success": True,
            "user_id": user_id,
            "event_type": event_type,
            "reputation_score": updated_score,
            "tier": tier,
        }), 201
    except Exception as e:
        logger.error(f"Error recording event: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# Configuration and Status
# ============================================================================

@reputation_bp.route("/config", methods=["GET"])
@require_admin
def get_config():
    """Get reputation system configuration.

    Returns:
        JSON with configuration
    """
    try:
        reputation_system = get_reputation_system()
        config = reputation_system._load_config(force_reload=True)

        # Also include tier definitions
        tiers = {}
        for tier_name, tier in reputation_system.TIERS.items():
            tiers[tier_name] = {
                "min_score": tier.min_score,
                "max_score": tier.max_score,
                "limit_multiplier": tier.limit_multiplier,
                "description": tier.description,
                "color_code": tier.color_code,
            }

        return jsonify({
            "config": config,
            "tiers": tiers,
        }), 200
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": "Internal server error"}), 500


@reputation_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint (no auth required).

    Returns:
        JSON with health status
    """
    try:
        reputation_system = get_reputation_system()
        # Try a simple operation
        stats = reputation_system.get_statistics()

        return jsonify({
            "status": "healthy",
            "timestamp": None,
        }), 200
    except Exception as e:
        logger.error(f"Reputation system health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
        }), 500


# ============================================================================
# Helper function to register blueprint
# ============================================================================

def register_reputation_routes(app):
    """Register reputation routes with Flask app.

    Args:
        app: Flask application instance
    """
    app.register_blueprint(reputation_bp)
    logger.info("Reputation system routes registered")
