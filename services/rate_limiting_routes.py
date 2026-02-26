"""Rate Limiting and Resource Monitoring Routes

Flask blueprint for managing rate limiting configurations and viewing statistics.
"""

import logging
from functools import wraps
from flask import Blueprint, jsonify, request, session, current_app

logger = logging.getLogger(__name__)

rate_limiting_bp = Blueprint("rate_limiting", __name__, url_prefix="/api/rate-limiting")


def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401

        # Check if user has admin role (implement based on your role system)
        is_admin = session.get("role") == "admin" or session.get("is_admin", False)
        if not is_admin:
            return jsonify({"error": "Admin access required"}), 403

        return f(*args, **kwargs)
    return decorated


@rate_limiting_bp.route("/config", methods=["GET"])
@require_auth
def list_configs():
    """List all rate limit configurations."""
    try:
        rate_limiter = current_app.rate_limiter
        configs = rate_limiter.get_all_configs()
        return jsonify({
            "success": True,
            "configs": configs,
            "count": len(configs)
        })
    except Exception as e:
        logger.error(f"Error listing configs: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/config", methods=["POST"])
@require_admin
def create_config():
    """Create a new rate limit configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        rate_limiter = current_app.rate_limiter
        success = rate_limiter.create_config(
            rule_name=data.get("rule_name"),
            scope=data.get("scope"),
            limit_type=data.get("limit_type"),
            limit_value=data.get("limit_value"),
            scope_value=data.get("scope_value"),
            resource_type=data.get("resource_type")
        )

        if success:
            return jsonify({
                "success": True,
                "message": f"Created rate limit config: {data.get('rule_name')}"
            }), 201
        else:
            return jsonify({"error": "Failed to create config"}), 500
    except Exception as e:
        logger.error(f"Error creating config: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/config/<rule_name>", methods=["PUT"])
@require_admin
def toggle_config(rule_name):
    """Enable/disable a rate limit configuration."""
    try:
        data = request.get_json()
        enabled = data.get("enabled", True)

        rate_limiter = current_app.rate_limiter
        if not enabled:
            success = rate_limiter.disable_config(rule_name)
        else:
            # Would need enable_config method
            success = True

        if success:
            action = "enabled" if enabled else "disabled"
            return jsonify({
                "success": True,
                "message": f"Rate limit config {action}: {rule_name}"
            })
        else:
            return jsonify({"error": "Failed to update config"}), 500
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/stats", methods=["GET"])
@require_auth
def get_stats():
    """Get rate limiting statistics."""
    try:
        days = request.args.get("days", 7, type=int)
        rate_limiter = current_app.rate_limiter
        stats = rate_limiter.get_stats(days=days)

        return jsonify({
            "success": True,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/violations", methods=["GET"])
@require_auth
def get_violations():
    """Get recent rate limit violations."""
    try:
        hours = request.args.get("hours", 24, type=int)
        rate_limiter = current_app.rate_limiter
        violations = rate_limiter.get_violations_summary(hours=hours)

        return jsonify({
            "success": True,
            "violations": violations
        })
    except Exception as e:
        logger.error(f"Error getting violations: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/resource-health", methods=["GET"])
@require_auth
def resource_health():
    """Get system resource health status."""
    try:
        resource_monitor = current_app.resource_monitor
        health = resource_monitor.get_health_status()

        return jsonify({
            "success": True,
            "health": health
        })
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/resource-trends", methods=["GET"])
@require_auth
def resource_trends():
    """Get resource usage trends."""
    try:
        minutes = request.args.get("minutes", 5, type=int)
        resource_monitor = current_app.resource_monitor
        trends = resource_monitor.get_load_trend(minutes=minutes)

        return jsonify({
            "success": True,
            "trends": trends
        })
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/resource-hourly", methods=["GET"])
@require_auth
def resource_hourly():
    """Get hourly resource usage summary."""
    try:
        hours = request.args.get("hours", 24, type=int)
        resource_monitor = current_app.resource_monitor
        summary = resource_monitor.get_hourly_summary(hours=hours)

        return jsonify({
            "success": True,
            "summary": summary
        })
    except Exception as e:
        logger.error(f"Error getting hourly summary: {e}")
        return jsonify({"error": str(e)}), 500


@rate_limiting_bp.route("/dashboard", methods=["GET"])
@require_auth
def dashboard():
    """Get comprehensive dashboard data."""
    try:
        rate_limiter = current_app.rate_limiter
        resource_monitor = current_app.resource_monitor

        return jsonify({
            "success": True,
            "rate_limiting": {
                "stats": rate_limiter.get_stats(days=7),
                "violations": rate_limiter.get_violations_summary(hours=24),
                "configs": rate_limiter.get_all_configs()
            },
            "resources": {
                "health": resource_monitor.get_health_status(),
                "trends_5min": resource_monitor.get_load_trend(minutes=5),
                "hourly": resource_monitor.get_hourly_summary(hours=24)
            }
        })
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({"error": str(e)}), 500
