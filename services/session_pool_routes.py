#!/usr/bin/env python3
"""
Session Pool Management API Routes

Provides endpoints for monitoring and managing Claude agent sessions.

Task: P04 - Add Session Pool Management
"""

import logging
from typing import Dict

from flask import Blueprint, jsonify, request

from .session_pool_service import get_service

logger = logging.getLogger(__name__)

# Create blueprint
session_pool_bp = Blueprint("session_pool", __name__, url_prefix="/api/session-pool")


# =============================================================================
# API Endpoints
# =============================================================================


@session_pool_bp.route("/members", methods=["GET"])
def get_members():
    """
    Get all pool members.

    Query params:
        role: Filter by role (worker, coordinator, etc.)
        status: Filter by status (stopped, running, failed, etc.)

    Returns:
        {
            "success": true,
            "members": [...],
            "count": 10
        }
    """
    try:
        service = get_service()
        role = request.args.get("role")
        status = request.args.get("status")

        members = service.get_pool_members(role=role, status=status)

        return jsonify({"success": True, "members": members, "count": len(members)})

    except Exception as e:
        logger.error(f"Error getting pool members: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/members/<name>", methods=["GET"])
def get_member(name: str):
    """
    Get specific pool member.

    Returns:
        {
            "success": true,
            "member": {...}
        }
    """
    try:
        service = get_service()
        member = service.get_pool_member(name)

        if not member:
            return jsonify({"success": False, "error": "Member not found"}), 404

        return jsonify({"success": True, "member": member})

    except Exception as e:
        logger.error(f"Error getting pool member: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/members", methods=["POST"])
def add_member():
    """
    Add or update a pool member.

    Body:
        {
            "name": "session-1",
            "tmux_name": "claude-session-1",
            "role": "worker",
            "status": "stopped",
            "health": "unknown",
            "metadata": {}
        }

    Returns:
        {
            "success": true,
            "id": 1,
            "message": "Member saved"
        }
    """
    try:
        data = request.get_json()

        if not data or "name" not in data or "tmux_name" not in data:
            return (
                jsonify({"success": False, "error": "Missing required fields: name, tmux_name"}),
                400,
            )

        service = get_service()
        session_id = service.save_pool_member(
            name=data["name"],
            tmux_name=data["tmux_name"],
            role=data.get("role", "worker"),
            status=data.get("status", "stopped"),
            health=data.get("health", "unknown"),
            metadata=data.get("metadata"),
        )

        # Log the event
        service.log_pool_event(data["name"], "registered", "Member added to pool")

        return jsonify(
            {
                "success": True,
                "id": session_id,
                "message": f"Member '{data['name']}' saved successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error adding pool member: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/members/<name>/heartbeat", methods=["POST"])
def update_heartbeat(name: str):
    """
    Update heartbeat for a session.

    Body (optional):
        {
            "health": "healthy"
        }

    Returns:
        {
            "success": true,
            "message": "Heartbeat updated"
        }
    """
    try:
        service = get_service()
        data = request.get_json() or {}

        health = data.get("health")
        success = service.update_heartbeat(name, health=health)

        if not success:
            return jsonify({"success": False, "error": "Member not found"}), 404

        return jsonify({"success": True, "message": "Heartbeat updated"})

    except Exception as e:
        logger.error(f"Error updating heartbeat: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/members/<name>/status", methods=["PUT"])
def update_status(name: str):
    """
    Update session status.

    Body:
        {
            "status": "running",
            "health": "healthy"
        }

    Returns:
        {
            "success": true,
            "message": "Status updated"
        }
    """
    try:
        data = request.get_json()

        if not data or "status" not in data:
            return jsonify({"success": False, "error": "Missing required field: status"}), 400

        service = get_service()
        success = service.update_status(name, data["status"], health=data.get("health"))

        if not success:
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Log the status change
        service.log_pool_event(name, "status_changed", f"Status: {data['status']}")

        return jsonify({"success": True, "message": "Status updated"})

    except Exception as e:
        logger.error(f"Error updating status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/members/<name>/health", methods=["GET"])
def check_health(name: str):
    """
    Perform health check on a session.

    Returns:
        {
            "success": true,
            "health": {
                "healthy": true,
                "status": "healthy",
                "tmux_running": true,
                "issues": [],
                "recommendations": [],
                "last_heartbeat": "2026-02-10T10:00:00",
                "restart_count": 0
            }
        }
    """
    try:
        service = get_service()
        health = service.health_check_session(name)

        # Log the health check
        service.log_pool_event(name, "health_check", f"Status: {health['status']}")

        return jsonify({"success": True, "health": health})

    except Exception as e:
        logger.error(f"Error checking health: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/members/<name>/restart", methods=["POST"])
def restart_session(name: str):
    """
    Attempt to restart a session.

    Returns:
        {
            "success": true,
            "message": "Session restarted successfully",
            "restart_count": 3
        }
    """
    try:
        service = get_service()
        result = service.auto_restart_session(name)

        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error restarting session: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/events", methods=["GET"])
def get_events():
    """
    Get pool events.

    Query params:
        session_name: Filter by session name
        event_type: Filter by event type
        limit: Max events (default 100)

    Returns:
        {
            "success": true,
            "events": [...],
            "count": 50
        }
    """
    try:
        service = get_service()

        session_name = request.args.get("session_name")
        event_type = request.args.get("event_type")
        limit = int(request.args.get("limit", 100))

        events = service.get_pool_events(
            session_name=session_name, event_type=event_type, limit=limit
        )

        return jsonify({"success": True, "events": events, "count": len(events)})

    except Exception as e:
        logger.error(f"Error getting pool events: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/health-summary", methods=["GET"])
def health_summary():
    """
    Get health summary for all pool members.

    Returns:
        {
            "success": true,
            "summary": {
                "total": 10,
                "healthy": 7,
                "degraded": 2,
                "unhealthy": 1,
                "members": [...]
            }
        }
    """
    try:
        service = get_service()
        members = service.get_pool_members()

        healthy = 0
        degraded = 0
        unhealthy = 0

        member_health = []
        for member in members:
            health = service.health_check_session(member["name"])
            member_health.append(
                {
                    "name": member["name"],
                    "role": member["role"],
                    "status": member["status"],
                    "health": health,
                }
            )

            if health["status"] == "healthy":
                healthy += 1
            elif health["status"] == "degraded":
                degraded += 1
            else:
                unhealthy += 1

        summary = {
            "total": len(members),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "members": member_health,
        }

        return jsonify({"success": True, "summary": summary})

    except Exception as e:
        logger.error(f"Error getting health summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@session_pool_bp.route("/auto-restart-all", methods=["POST"])
def auto_restart_all():
    """
    Auto-restart all unhealthy sessions.

    Returns:
        {
            "success": true,
            "restarted": ["session-1", "session-3"],
            "failed": ["session-5"],
            "summary": "Restarted 2/3 unhealthy sessions"
        }
    """
    try:
        service = get_service()
        members = service.get_pool_members()

        restarted = []
        failed = []

        for member in members:
            health = service.health_check_session(member["name"])
            if not health["healthy"]:
                result = service.auto_restart_session(member["name"])
                if result["success"]:
                    restarted.append(member["name"])
                else:
                    failed.append(member["name"])

        return jsonify(
            {
                "success": True,
                "restarted": restarted,
                "failed": failed,
                "summary": f"Restarted {len(restarted)}/{len(restarted) + len(failed)} unhealthy sessions",
            }
        )

    except Exception as e:
        logger.error(f"Error auto-restarting sessions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
