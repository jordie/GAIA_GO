#!/usr/bin/env python3
"""
Go Wrapper Monitoring API Routes

Provides endpoints for monitoring Go Wrapper agents, tasks, and events with SSE support.

Task: P09 - Implement Go Wrapper Monitoring
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List

import requests
from flask import Blueprint, Response, jsonify, request, stream_with_context

logger = logging.getLogger(__name__)

# Create blueprint
go_monitor_bp = Blueprint("go_monitor", __name__, url_prefix="/api/go-wrapper")

# Configuration
GO_WRAPPER_API = os.getenv("GO_WRAPPER_API", "http://100.112.58.92:8151")
REQUEST_TIMEOUT = 5


# =============================================================================
# Helper Functions
# =============================================================================


def fetch_go_wrapper_data(endpoint: str) -> Dict:
    """Fetch data from Go Wrapper API."""
    try:
        url = f"{GO_WRAPPER_API}{endpoint}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {endpoint}")
        return {"error": "Go Wrapper API timeout"}
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error fetching {endpoint}")
        return {"error": "Go Wrapper API unavailable"}
    except Exception as e:
        logger.error(f"Error fetching {endpoint}: {e}")
        return {"error": str(e)}


def calculate_agent_health(agent: Dict) -> str:
    """
    Calculate agent health based on status and last activity.

    Returns: "healthy", "degraded", or "unhealthy"
    """
    status = agent.get("status", "unknown").lower()
    last_active = agent.get("last_active_at")

    if status == "error" or status == "failed":
        return "unhealthy"

    if status == "busy":
        return "healthy"

    # Check if agent has been idle too long (>5 minutes = degraded, >15 minutes = unhealthy)
    if last_active:
        try:
            # Parse last_active timestamp
            last_time = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            idle_seconds = (datetime.now() - last_time).total_seconds()

            if idle_seconds > 900:  # 15 minutes
                return "unhealthy"
            elif idle_seconds > 300:  # 5 minutes
                return "degraded"
        except Exception:
            pass

    return "healthy"


# =============================================================================
# API Endpoints
# =============================================================================


@go_monitor_bp.route("/agents", methods=["GET"])
def get_agents():
    """
    Get all agents from Go Wrapper.

    Returns:
        {
            "success": true,
            "agents": [
                {
                    "id": "agent-1",
                    "name": "ws-test",
                    "status": "idle",
                    "current_task": null,
                    "tasks_completed": 2,
                    "last_active_at": "2026-02-10T10:00:00Z",
                    "health": "healthy"
                },
                ...
            ],
            "count": 5
        }
    """
    try:
        data = fetch_go_wrapper_data("/api/manager/agents")

        if "error" in data:
            return jsonify({"success": False, "error": data["error"]}), 503

        agents = data.get("agents", [])

        # Enhance agents with health status
        for agent in agents:
            agent["health"] = calculate_agent_health(agent)

        return jsonify({"success": True, "agents": agents, "count": len(agents)})

    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@go_monitor_bp.route("/tasks", methods=["GET"])
def get_tasks():
    """
    Get all tasks from Go Wrapper.

    Query params:
        status: Filter by status (pending, assigned, in_progress, completed, failed)
        agent: Filter by agent name

    Returns:
        {
            "success": true,
            "tasks": [...],
            "count": 10
        }
    """
    try:
        data = fetch_go_wrapper_data("/api/manager/tasks")

        if "error" in data:
            return jsonify({"success": False, "error": data["error"]}), 503

        tasks = data.get("tasks", [])

        # Apply filters
        status_filter = request.args.get("status")
        agent_filter = request.args.get("agent")

        if status_filter:
            tasks = [t for t in tasks if t.get("status") == status_filter]

        if agent_filter:
            tasks = [t for t in tasks if t.get("assigned_agent") == agent_filter]

        return jsonify({"success": True, "tasks": tasks, "count": len(tasks)})

    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@go_monitor_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get Go Wrapper system status.

    Returns:
        {
            "success": true,
            "status": {
                "total_agents": 5,
                "active_agents": 3,
                "idle_agents": 2,
                "total_tasks": 15,
                "pending_tasks": 3,
                "in_progress_tasks": 2,
                "completed_tasks": 10
            }
        }
    """
    try:
        agents_data = fetch_go_wrapper_data("/api/manager/agents")
        tasks_data = fetch_go_wrapper_data("/api/manager/tasks")

        if "error" in agents_data or "error" in tasks_data:
            return jsonify({"success": False, "error": "Go Wrapper API unavailable"}), 503

        agents = agents_data.get("agents", [])
        tasks = tasks_data.get("tasks", [])

        # Calculate statistics
        active_agents = sum(1 for a in agents if a.get("status") in ["busy", "in_progress"])
        idle_agents = sum(1 for a in agents if a.get("status") == "idle")

        pending_tasks = sum(1 for t in tasks if t.get("status") == "pending")
        in_progress_tasks = sum(1 for t in tasks if t.get("status") == "in_progress")
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")

        status = {
            "total_agents": len(agents),
            "active_agents": active_agents,
            "idle_agents": idle_agents,
            "total_tasks": len(tasks),
            "pending_tasks": pending_tasks,
            "in_progress_tasks": in_progress_tasks,
            "completed_tasks": completed_tasks,
        }

        return jsonify({"success": True, "status": status})

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@go_monitor_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """
    Get aggregated metrics for charts.

    Returns:
        {
            "success": true,
            "metrics": {
                "agents_by_status": {"idle": 2, "busy": 3},
                "tasks_by_status": {"pending": 5, "completed": 10},
                "agent_performance": [...]
            }
        }
    """
    try:
        agents_data = fetch_go_wrapper_data("/api/manager/agents")
        tasks_data = fetch_go_wrapper_data("/api/manager/tasks")

        if "error" in agents_data or "error" in tasks_data:
            return jsonify({"success": False, "error": "Go Wrapper API unavailable"}), 503

        agents = agents_data.get("agents", [])
        tasks = tasks_data.get("tasks", [])

        # Agents by status
        agents_by_status = {}
        for agent in agents:
            status = agent.get("status", "unknown")
            agents_by_status[status] = agents_by_status.get(status, 0) + 1

        # Tasks by status
        tasks_by_status = {}
        for task in tasks:
            status = task.get("status", "unknown")
            tasks_by_status[status] = tasks_by_status.get(status, 0) + 1

        # Agent performance (tasks completed)
        agent_performance = []
        for agent in agents:
            agent_performance.append(
                {
                    "name": agent.get("name", "unknown"),
                    "tasks_completed": agent.get("tasks_completed", 0),
                    "health": calculate_agent_health(agent),
                }
            )

        metrics = {
            "agents_by_status": agents_by_status,
            "tasks_by_status": tasks_by_status,
            "agent_performance": agent_performance,
        }

        return jsonify({"success": True, "metrics": metrics})

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@go_monitor_bp.route("/stream", methods=["GET"])
def stream_events():
    """
    SSE endpoint for real-time updates.

    Usage:
        const eventSource = new EventSource('/api/go-wrapper/stream');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Update:', data);
        };
    """

    def generate():
        """Generate SSE events."""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"

            while True:
                try:
                    # Fetch current data
                    agents_data = fetch_go_wrapper_data("/api/manager/agents")
                    tasks_data = fetch_go_wrapper_data("/api/manager/tasks")

                    if "error" not in agents_data and "error" not in tasks_data:
                        agents = agents_data.get("agents", [])
                        tasks = tasks_data.get("tasks", [])

                        # Add health status to agents
                        for agent in agents:
                            agent["health"] = calculate_agent_health(agent)

                        # Calculate status counts
                        active_agents = sum(
                            1 for a in agents if a.get("status") in ["busy", "in_progress"]
                        )
                        pending_tasks = sum(1 for t in tasks if t.get("status") == "pending")

                        event_data = {
                            "type": "update",
                            "timestamp": datetime.now().isoformat(),
                            "agents": agents,
                            "tasks": tasks,
                            "summary": {
                                "total_agents": len(agents),
                                "active_agents": active_agents,
                                "total_tasks": len(tasks),
                                "pending_tasks": pending_tasks,
                            },
                        }

                        yield f"data: {json.dumps(event_data)}\n\n"

                    # Wait 5 seconds before next update
                    time.sleep(5)

                except GeneratorExit:
                    break
                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    error_data = {"type": "error", "error": str(e)}
                    yield f"data: {json.dumps(error_data)}\n\n"
                    time.sleep(5)

        except Exception as e:
            logger.error(f"Fatal error in SSE stream: {e}")

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@go_monitor_bp.route("/health", methods=["GET"])
def check_health():
    """
    Check if Go Wrapper API is accessible.

    Returns:
        {"success": true, "healthy": true, "api_url": "..."}
    """
    try:
        data = fetch_go_wrapper_data("/api/manager/status")
        healthy = "error" not in data

        return jsonify({"success": True, "healthy": healthy, "api_url": GO_WRAPPER_API})

    except Exception as e:
        return jsonify({"success": False, "healthy": False, "error": str(e)}), 503
