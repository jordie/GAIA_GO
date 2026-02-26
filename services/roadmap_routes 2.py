#!/usr/bin/env python3
"""
Flask Routes for Roadmap API

Provides HTTP endpoints for agents to interact with the roadmap.
"""

import logging

from flask import Blueprint, jsonify, request

from services.roadmap_api import RoadmapAPI

logger = logging.getLogger(__name__)

# Create blueprint
roadmap_bp = Blueprint("roadmap", __name__, url_prefix="/api/roadmap")

# Initialize API
roadmap_api = RoadmapAPI()


# =============================================================================
# Routes
# =============================================================================


@roadmap_bp.route("/sync", methods=["POST"])
def sync_roadmap():
    """Sync tasks from roadmap files to database."""
    try:
        count = roadmap_api.sync_from_roadmap()
        return jsonify({"success": True, "synced_tasks": count})
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roadmap_bp.route("/tasks/available", methods=["GET"])
def get_available_tasks():
    """Get available tasks for assignment."""
    agent_id = request.args.get("agent_id")
    if not agent_id:
        return jsonify({"success": False, "error": "agent_id required"}), 400

    project = request.args.get("project")
    priority = request.args.get("priority")
    limit = int(request.args.get("limit", 10))

    try:
        tasks = roadmap_api.get_available_tasks(
            agent_id=agent_id, project=project, priority=priority, limit=limit
        )

        return jsonify(
            {
                "success": True,
                "count": len(tasks),
                "tasks": [task.to_dict() for task in tasks],
            }
        )
    except Exception as e:
        logger.error(f"Get available tasks failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roadmap_bp.route("/tasks/<task_id>/claim", methods=["POST"])
def claim_task(task_id):
    """Claim a task for an agent."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id")

    if not agent_id:
        return jsonify({"success": False, "error": "agent_id required"}), 400

    try:
        task = roadmap_api.claim_task(task_id=task_id, agent_id=agent_id)

        if task:
            return jsonify({"success": True, "task": task.to_dict()})
        else:
            return jsonify({"success": False, "error": "Task not available"}), 409

    except Exception as e:
        logger.error(f"Claim task failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roadmap_bp.route("/tasks/<task_id>/progress", methods=["POST"])
def update_task_progress(task_id):
    """Update task progress."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id")
    progress = data.get("progress")
    message = data.get("message")

    if not agent_id or progress is None:
        return jsonify({"success": False, "error": "agent_id and progress required"}), 400

    try:
        success = roadmap_api.update_task_progress(
            task_id=task_id, agent_id=agent_id, progress=int(progress), message=message
        )

        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Update progress failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roadmap_bp.route("/tasks/<task_id>/complete", methods=["POST"])
def complete_task(task_id):
    """Mark task as complete."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id")
    notes = data.get("notes")

    if not agent_id:
        return jsonify({"success": False, "error": "agent_id required"}), 400

    try:
        success = roadmap_api.complete_task(task_id=task_id, agent_id=agent_id, notes=notes)

        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Complete task failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roadmap_bp.route("/tasks/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """Get detailed task status."""
    try:
        status = roadmap_api.get_task_status(task_id=task_id)

        if status:
            return jsonify({"success": True, "task": status})
        else:
            return jsonify({"success": False, "error": "Task not found"}), 404

    except Exception as e:
        logger.error(f"Get task status failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roadmap_bp.route("/agents/<agent_id>/tasks", methods=["GET"])
def get_agent_tasks(agent_id):
    """Get all tasks assigned to an agent."""
    try:
        tasks = roadmap_api.get_agent_tasks(agent_id=agent_id)

        return jsonify(
            {
                "success": True,
                "agent_id": agent_id,
                "count": len(tasks),
                "tasks": [task.to_dict() for task in tasks],
            }
        )
    except Exception as e:
        logger.error(f"Get agent tasks failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roadmap_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get roadmap statistics."""
    try:
        stats = roadmap_api.get_stats()
        return jsonify({"success": True, **stats})
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Health Check
# =============================================================================


@roadmap_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"success": True, "service": "roadmap_api", "status": "healthy"})
