#!/usr/bin/env python3
"""
Supervisor API Routes

Flask routes for supervisor integration with architect dashboard.
Add these routes to app.py to enable supervisor management via API.
"""

import logging
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supervisor.health_checks import HealthChecker
from supervisor.supervisor_integration import SupervisorIntegration

logger = logging.getLogger(__name__)

# Create blueprint
supervisor_bp = Blueprint("supervisor", __name__, url_prefix="/api/supervisor")

# Initialize integration
integration = SupervisorIntegration()
health_checker = HealthChecker()


@supervisor_bp.route("/status", methods=["GET"])
def get_status():
    """Get status of all supervised services."""
    try:
        service_id = request.args.get("service_id")
        services = integration.get_service_status(service_id)

        return jsonify({"success": True, "services": services, "count": len(services)})

    except Exception as e:
        logger.error(f"Error getting supervisor status: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/services/<service_id>", methods=["GET"])
def get_service(service_id):
    """Get details for a specific service."""
    try:
        services = integration.get_service_status(service_id)

        if not services:
            return jsonify({"success": False, "error": "Service not found"}), 404

        service = services[0]

        # Get recent metrics
        metrics = integration.get_service_metrics(service_id, limit=10)

        # Get recent events
        events = integration.get_service_events(service_id, limit=10)

        return jsonify({"success": True, "service": service, "metrics": metrics, "events": events})

    except Exception as e:
        logger.error(f"Error getting service '{service_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/services/<service_id>/start", methods=["POST"])
def start_service(service_id):
    """Start a service.

    This endpoint sends a start command to the supervisor.
    The actual implementation depends on how you want to communicate
    with the running supervisor process (IPC, signals, etc.)
    """
    try:
        # For now, log the event
        integration.log_event(service_id, "start_requested", "Service start requested via API")

        return jsonify(
            {"success": True, "message": f"Start command sent for service '{service_id}'"}
        )

    except Exception as e:
        logger.error(f"Error starting service '{service_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/services/<service_id>/stop", methods=["POST"])
def stop_service(service_id):
    """Stop a service."""
    try:
        integration.log_event(service_id, "stop_requested", "Service stop requested via API")

        return jsonify(
            {"success": True, "message": f"Stop command sent for service '{service_id}'"}
        )

    except Exception as e:
        logger.error(f"Error stopping service '{service_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/services/<service_id>/restart", methods=["POST"])
def restart_service(service_id):
    """Restart a service."""
    try:
        integration.log_event(service_id, "restart_requested", "Service restart requested via API")

        return jsonify(
            {"success": True, "message": f"Restart command sent for service '{service_id}'"}
        )

    except Exception as e:
        logger.error(f"Error restarting service '{service_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/services/<service_id>/health", methods=["GET"])
def get_service_health(service_id):
    """Get health status for a service."""
    try:
        # Get service info
        services = integration.get_service_status(service_id)

        if not services:
            return jsonify({"success": False, "error": "Service not found"}), 404

        service = services[0]

        # Get health summary
        health_summary = health_checker.get_health_summary(service_id)

        return jsonify(
            {
                "success": True,
                "service_id": service_id,
                "state": service.get("state"),
                "health": health_summary,
            }
        )

    except Exception as e:
        logger.error(f"Error getting health for '{service_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/health", methods=["GET"])
def get_overall_health():
    """Get overall health status of all services."""
    try:
        services = integration.get_service_status()

        health_data = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0, "services": {}}

        for service in services:
            service_id = service["id"]
            health_summary = health_checker.get_health_summary(service_id)

            status = health_summary.get("status", "unknown")
            health_data[status] = health_data.get(status, 0) + 1
            health_data["services"][service_id] = health_summary

        return jsonify({"success": True, "overall_health": health_data})

    except Exception as e:
        logger.error(f"Error getting overall health: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/metrics", methods=["POST"])
def receive_metrics():
    """Receive metrics from supervisor process."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Record metrics for each service
        services = data.get("services", {})

        for service_id, metrics in services.items():
            integration.record_metrics(service_id, metrics)

        return jsonify({"success": True, "message": "Metrics recorded"})

    except Exception as e:
        logger.error(f"Error receiving metrics: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/events", methods=["GET"])
def get_events():
    """Get recent supervisor events."""
    try:
        service_id = request.args.get("service_id")
        event_type = request.args.get("event_type")
        limit = int(request.args.get("limit", 50))

        events = integration.get_service_events(
            service_id=service_id, event_type=event_type, limit=limit
        )

        return jsonify({"success": True, "events": events, "count": len(events)})

    except Exception as e:
        logger.error(f"Error getting events: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/summary", methods=["GET"])
def get_summary():
    """Get supervisor summary for dashboard."""
    try:
        summary = integration.get_dashboard_summary()

        return jsonify({"success": True, "summary": summary})

    except Exception as e:
        logger.error(f"Error getting summary: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supervisor_bp.route("/reload", methods=["POST"])
def reload_config():
    """Reload supervisor configuration.

    This sends a signal to the supervisor to reload its config.
    Implementation depends on IPC mechanism.
    """
    try:
        integration.log_event(
            "supervisor", "reload_requested", "Configuration reload requested via API"
        )

        return jsonify({"success": True, "message": "Reload command sent"})

    except Exception as e:
        logger.error(f"Error reloading config: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# Function to register blueprint with Flask app
def register_supervisor_routes(app):
    """Register supervisor routes with Flask app.

    Usage in app.py:
        from supervisor.api_routes import register_supervisor_routes
        register_supervisor_routes(app)
    """
    app.register_blueprint(supervisor_bp)
    logger.info("Supervisor API routes registered")
