#!/usr/bin/env python3
"""
Goal Engine API Wrapper

Provides a simple API for integrating the goal engine with other services.
Can be used as a standalone Flask API or imported as a module.

Usage as module:
    from scripts.goal_engine_api import GoalEngineAPI

    api = GoalEngineAPI()

    # Generate tasks
    results = api.generate_tasks(max_tasks=5)

    # Get vision
    vision = api.get_vision()

    # Update vision
    api.update_vision(primary_goal="New goal")

Usage as API:
    python3 scripts/goal_engine_api.py

    curl http://localhost:5555/api/goal-engine/generate
    curl http://localhost:5555/api/goal-engine/vision
    curl http://localhost:5555/api/goal-engine/state
"""

import sys
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import logging

from flask import Flask, jsonify, request

from orchestrator.goal_engine import GoalEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoalEngineAPI")


class GoalEngineAPI:
    """Wrapper for goal engine with simplified API."""

    def __init__(self):
        self.engine = GoalEngine()

    def generate_tasks(self, max_tasks=None, dry_run=False):
        """
        Generate tasks from vision and optionally queue them.

        Args:
            max_tasks: Maximum number of tasks to generate
            dry_run: If True, don't queue tasks

        Returns:
            Dict with generation results
        """
        try:
            results = self.engine.generate_and_queue_tasks(dry_run=dry_run, max_tasks=max_tasks)
            return {"success": True, "results": results}
        except Exception as e:
            logger.error(f"Failed to generate tasks: {e}")
            return {"success": False, "error": str(e)}

    def get_vision(self):
        """Get strategic vision."""
        try:
            vision = self.engine.get_strategic_vision()
            return {"success": True, "vision": vision}
        except Exception as e:
            logger.error(f"Failed to get vision: {e}")
            return {"success": False, "error": str(e)}

    def get_state(self):
        """Get current state analysis."""
        try:
            state = self.engine.analyze_current_state()
            return {"success": True, "state": state}
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return {"success": False, "error": str(e)}

    def get_revenue_metrics(self):
        """Get revenue metrics."""
        try:
            metrics = self.engine.analyze_revenue_metrics()
            return {"success": True, "metrics": metrics}
        except Exception as e:
            logger.error(f"Failed to get revenue metrics: {e}")
            return {"success": False, "error": str(e)}

    def learn_patterns(self):
        """Analyze task execution patterns and update learning database."""
        try:
            results = self.engine.learn_from_patterns()
            return {"success": True, "results": results}
        except Exception as e:
            logger.error(f"Failed to learn patterns: {e}")
            return {"success": False, "error": str(e)}

    def update_vision(self, **updates):
        """
        Update strategic vision.

        Args:
            **updates: Fields to update (statement, primary_goal, focus_areas, etc.)

        Returns:
            Dict with success status
        """
        try:
            success = self.engine.update_vision(**updates)
            return {
                "success": success,
                "message": "Vision updated" if success else "Failed to update vision",
            }
        except Exception as e:
            logger.error(f"Failed to update vision: {e}")
            return {"success": False, "error": str(e)}


# Flask API
app = Flask(__name__)
api = GoalEngineAPI()


@app.route("/api/goal-engine/generate", methods=["POST"])
def generate_tasks():
    """
    Generate and queue tasks from strategic vision.

    Request body (JSON):
        {
            "max_tasks": 5,       // Optional: limit number of tasks
            "dry_run": false      // Optional: preview without queuing
        }

    Response:
        {
            "success": true,
            "results": {
                "generated": 10,
                "unique": 8,
                "queued": 5,
                "skipped": 3,
                "total_revenue_impact": 2850.0,
                "tasks": [...]
            }
        }
    """
    data = request.get_json() or {}
    max_tasks = data.get("max_tasks")
    dry_run = data.get("dry_run", False)

    result = api.generate_tasks(max_tasks=max_tasks, dry_run=dry_run)
    return jsonify(result)


@app.route("/api/goal-engine/vision", methods=["GET"])
def get_vision():
    """
    Get strategic vision.

    Response:
        {
            "success": true,
            "vision": {
                "statement": "...",
                "primary_goal": "...",
                "focus_areas": [...],
                "revenue_targets": {...},
                "success_metrics": {...}
            }
        }
    """
    result = api.get_vision()
    return jsonify(result)


@app.route("/api/goal-engine/vision", methods=["PUT"])
def update_vision():
    """
    Update strategic vision.

    Request body (JSON):
        {
            "primary_goal": "New goal",
            "focus_areas": ["area1", "area2"]
        }

    Response:
        {
            "success": true,
            "message": "Vision updated"
        }
    """
    data = request.get_json() or {}
    result = api.update_vision(**data)
    return jsonify(result)


@app.route("/api/goal-engine/state", methods=["GET"])
def get_state():
    """
    Get current state analysis.

    Response:
        {
            "success": true,
            "state": {
                "projects": {...},
                "blockers": [...],
                "opportunities": [...],
                "revenue": {...}
            }
        }
    """
    result = api.get_state()
    return jsonify(result)


@app.route("/api/goal-engine/revenue", methods=["GET"])
def get_revenue():
    """
    Get revenue metrics.

    Response:
        {
            "success": true,
            "metrics": {
                "current_revenue": 0,
                "target_revenue": 999,
                "revenue_gap": 999,
                "on_track": false,
                ...
            }
        }
    """
    result = api.get_revenue_metrics()
    return jsonify(result)


@app.route("/api/goal-engine/learn", methods=["POST"])
def learn_patterns():
    """
    Analyze task execution patterns and update learning database.

    Response:
        {
            "success": true,
            "results": {
                "patterns_analyzed": 15,
                "patterns_updated": 10,
                "tasks_processed": 50
            }
        }
    """
    result = api.learn_patterns()
    return jsonify(result)


@app.route("/api/goal-engine/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "goal-engine-api"})


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Goal Engine API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5555, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    logger.info(f"Starting Goal Engine API on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
