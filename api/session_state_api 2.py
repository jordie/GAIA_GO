#!/usr/bin/env python3
"""
Session State API
Real-time API endpoints for monitoring agent session state without tmux.
"""

import sys
from pathlib import Path

from flask import Flask, jsonify, request

# Add workers to path
sys.path.insert(0, str(Path(__file__).parent.parent / "workers"))
from session_state_manager import SessionStateManager

app = Flask(__name__)


@app.route("/api/sessions", methods=["GET"])
def get_all_sessions():
    """Get all active session states."""
    try:
        sessions = SessionStateManager.get_all_sessions()

        # Enrich with status categorization
        result = {
            "sessions": sessions,
            "summary": {
                "total": len(sessions),
                "working": sum(1 for s in sessions.values() if s.get("status") == "working"),
                "idle": sum(1 for s in sessions.values() if s.get("status") == "idle"),
                "error": sum(1 for s in sessions.values() if s.get("status") == "error"),
            },
        }

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_name>", methods=["GET"])
def get_session(session_name):
    """Get specific session state."""
    try:
        state = SessionStateManager.get_session_state(session_name)

        if not state:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(state)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/working", methods=["GET"])
def get_working_sessions():
    """Get all sessions currently working on tasks."""
    try:
        all_sessions = SessionStateManager.get_all_sessions()
        working = {
            name: state
            for name, state in all_sessions.items()
            if state.get("status") == "working" and state.get("current_task")
        }

        return jsonify({"sessions": working, "count": len(working)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/idle", methods=["GET"])
def get_idle_sessions():
    """Get all idle sessions."""
    try:
        all_sessions = SessionStateManager.get_all_sessions()
        idle = {
            name: state for name, state in all_sessions.items() if state.get("status") == "idle"
        }

        return jsonify({"sessions": idle, "count": len(idle)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/summary", methods=["GET"])
def get_summary():
    """Get summary of all sessions."""
    try:
        sessions = SessionStateManager.get_all_sessions()

        summary = {
            "total_sessions": len(sessions),
            "by_status": {},
            "by_tool": {},
            "total_prompts_handled": 0,
            "total_errors": 0,
            "active_tasks": [],
        }

        for name, state in sessions.items():
            # Count by status
            status = state.get("status", "unknown")
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

            # Count by tool
            tool = state.get("tool", "unknown")
            summary["by_tool"][tool] = summary["by_tool"].get(tool, 0) + 1

            # Aggregate metrics
            summary["total_prompts_handled"] += state.get("prompts_handled", 0)
            summary["total_errors"] += state.get("errors", 0)

            # Collect active tasks
            if state.get("current_task"):
                summary["active_tasks"].append(
                    {
                        "session": name,
                        "task": state["current_task"],
                        "work_dir": state.get("working_directory"),
                    }
                )

        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/cleanup", methods=["POST"])
def cleanup_stale():
    """Cleanup stale session states."""
    try:
        max_age = request.json.get("max_age_seconds", 3600) if request.json else 3600
        removed = SessionStateManager.cleanup_stale_states(max_age_seconds=max_age)

        return jsonify({"removed": removed, "message": f"Removed {removed} stale session states"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/stream", methods=["GET"])
def stream_sessions():
    """Server-sent events stream for real-time updates."""
    import time

    def generate():
        """Generate SSE stream."""
        while True:
            try:
                sessions = SessionStateManager.get_all_sessions()
                data = {"timestamp": time.time(), "sessions": sessions}
                yield f"data: {jsonify(data).get_data(as_text=True)}\n\n"
                time.sleep(1)  # Update every second
            except GeneratorExit:
                break
            except Exception as e:
                yield f'data: {{"error": "{str(e)}"}}\n\n'
                break

    return app.response_class(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Session State API Server")
    parser.add_argument("--port", type=int, default=5555, help="Port to run on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    print(f"🚀 Session State API starting on http://{args.host}:{args.port}")
    print(f"   GET  /api/sessions          - All sessions")
    print(f"   GET  /api/sessions/summary  - Summary stats")
    print(f"   GET  /api/sessions/working  - Working sessions")
    print(f"   GET  /api/sessions/stream   - SSE real-time stream")
    print()

    app.run(host=args.host, port=args.port, debug=False)
