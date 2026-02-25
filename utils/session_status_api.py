#!/usr/bin/env python3
"""
Session Status API Routes

Flask routes for exposing session status via REST API.
Add to app.py with: from utils.session_status_api import register_session_status_routes
"""

from flask import jsonify, request
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.session_monitor import SessionMonitor


def register_session_status_routes(app, status_dir="data/session_status"):
    """
    Register session status API routes.

    Args:
        app: Flask app instance
        status_dir: Directory containing status files
    """

    # Initialize monitor (shared instance)
    monitor = SessionMonitor(Path(status_dir))

    @app.route('/api/session-status/summary', methods=['GET'])
    def get_session_status_summary():
        """Get summary of all session statuses."""
        try:
            summary = monitor.get_summary()
            return jsonify(summary), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/session-status/sessions', methods=['GET'])
    def get_all_session_statuses():
        """Get detailed status for all sessions."""
        try:
            statuses = monitor.scan_sessions()
            return jsonify(statuses), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/session-status/session/<session_name>', methods=['GET'])
    def get_session_status(session_name):
        """Get status for a specific session."""
        try:
            statuses = monitor.scan_sessions()
            if session_name not in statuses:
                return jsonify({"error": f"Session '{session_name}' not found"}), 404

            return jsonify(statuses[session_name]), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/session-status/session/<session_name>/history', methods=['GET'])
    def get_session_history(session_name):
        """Get update history for a session."""
        try:
            status_file = Path(status_dir) / f"{session_name}_status.json"
            if not status_file.exists():
                return jsonify({"error": f"Session '{session_name}' not found"}), 404

            # Get recent updates (last N or since timestamp)
            limit = request.args.get('limit', 50, type=int)
            updates = monitor.get_all_updates(status_file)

            # Return most recent N updates
            recent = updates[-limit:] if len(updates) > limit else updates

            return jsonify({
                "session": session_name,
                "total_updates": len(updates),
                "updates": recent
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/session-status/working', methods=['GET'])
    def get_working_sessions():
        """Get all sessions currently working."""
        try:
            summary = monitor.get_summary()
            working = []

            for session_name in summary['working_sessions']:
                status = monitor.current_status.get(session_name)
                if status:
                    working.append(status)

            return jsonify({
                "count": len(working),
                "sessions": working
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/session-status/errors', methods=['GET'])
    def get_error_sessions():
        """Get all sessions with errors."""
        try:
            summary = monitor.get_summary()
            errors = []

            for session_name in summary['error_sessions']:
                status = monitor.current_status.get(session_name)
                if status:
                    errors.append(status)

            return jsonify({
                "count": len(errors),
                "sessions": errors
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/session-status/stale', methods=['GET'])
    def get_stale_sessions():
        """Get sessions that haven't updated recently."""
        try:
            summary = monitor.get_summary()
            stale = []

            for session_name in summary['stale_sessions']:
                status = monitor.current_status.get(session_name)
                if status:
                    stale.append(status)

            return jsonify({
                "count": len(stale),
                "sessions": stale
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


# Example integration with app.py
"""
Add to app.py:

from utils.session_status_api import register_session_status_routes

# After creating app
app = Flask(__name__)

# Register routes
register_session_status_routes(app)
"""
