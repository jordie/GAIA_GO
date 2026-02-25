"""
LLM Provider Test API Routes
API endpoints for managing and viewing LLM provider test results
"""

import sqlite3
from functools import wraps

from flask import Blueprint, jsonify, request

from db import get_connection

llm_test_bp = Blueprint("llm_tests", __name__)


def require_auth_decorator(f):
    """Decorator for authentication - placeholder"""

    @wraps(f)
    def decorated(*args, **kwargs):
        # Authentication handled by main app
        return f(*args, **kwargs)

    return decorated


@llm_test_bp.route("/api/llm-tests/runs", methods=["GET"])
def get_test_runs():
    """Get all test runs"""
    try:
        with get_connection("main") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            runs = cursor.execute(
                """
                SELECT id, test_name, description, max_lines, created_at
                FROM llm_test_runs
                ORDER BY created_at DESC
            """
            ).fetchall()

            return jsonify({"success": True, "runs": [dict(row) for row in runs]})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_test_bp.route("/api/llm-tests/runs/<int:run_id>/results", methods=["GET"])
def get_test_results(run_id):
    """Get results for a specific test run"""
    try:
        with get_connection("main") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            results = cursor.execute(
                """
                SELECT
                    id, provider_name, session_name, status,
                    started_at, completed_at, duration_seconds,
                    files_created, total_lines, total_bytes,
                    test_passed, error_message, metadata
                FROM llm_test_results
                WHERE test_run_id = ?
                ORDER BY created_at DESC
            """,
                (run_id,),
            ).fetchall()

            return jsonify({"success": True, "results": [dict(row) for row in results]})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_test_bp.route("/api/llm-tests/latest", methods=["GET"])
def get_latest_results():
    """Get latest test results across all providers"""
    try:
        limit = request.args.get("limit", 10, type=int)

        with get_connection("main") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            results = cursor.execute(
                """
                SELECT
                    r.id, r.provider_name, r.status,
                    r.duration_seconds, r.files_created, r.total_lines,
                    r.test_passed, r.completed_at,
                    t.test_name
                FROM llm_test_results r
                JOIN llm_test_runs t ON r.test_run_id = t.id
                WHERE r.status IN ('completed', 'failed', 'timeout')
                ORDER BY r.created_at DESC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

            return jsonify({"success": True, "results": [dict(row) for row in results]})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_test_bp.route("/api/llm-tests/stats", methods=["GET"])
def get_test_stats():
    """Get aggregate statistics across all tests"""
    try:
        with get_connection("main") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Overall stats
            overall = cursor.execute(
                """
                SELECT
                    COUNT(*) as total_tests,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeout,
                    SUM(CASE WHEN test_passed = 1 THEN 1 ELSE 0 END) as passed,
                    AVG(CASE WHEN duration_seconds > 0 THEN duration_seconds ELSE NULL END) as avg_duration,
                    AVG(CASE WHEN total_lines > 0 THEN total_lines ELSE NULL END) as avg_lines
                FROM llm_test_results
                WHERE status IN ('completed', 'failed', 'timeout')
            """
            ).fetchone()

            # Per-provider stats
            by_provider = cursor.execute(
                """
                SELECT
                    provider_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN test_passed = 1 THEN 1 ELSE 0 END) as passed,
                    AVG(CASE WHEN duration_seconds > 0 THEN duration_seconds ELSE NULL END) as avg_duration,
                    AVG(CASE WHEN total_lines > 0 THEN total_lines ELSE NULL END) as avg_lines
                FROM llm_test_results
                WHERE status IN ('completed', 'failed', 'timeout')
                GROUP BY provider_name
                ORDER BY passed DESC, avg_duration ASC
            """
            ).fetchall()

            return jsonify(
                {
                    "success": True,
                    "overall": dict(overall) if overall else {},
                    "by_provider": [dict(row) for row in by_provider],
                }
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_test_bp.route("/api/llm-tests/comparison", methods=["GET"])
def get_provider_comparison():
    """Get side-by-side comparison of providers"""
    try:
        test_name = request.args.get("test_name", "Calculator Web App")

        with get_connection("main") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get the most recent run for this test
            latest_run = cursor.execute(
                """
                SELECT id FROM llm_test_runs
                WHERE test_name = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (test_name,),
            ).fetchone()

            if not latest_run:
                return jsonify({"success": True, "comparison": []})

            # Get results for all providers in this run
            results = cursor.execute(
                """
                SELECT
                    provider_name, status, duration_seconds,
                    files_created, total_lines, total_bytes,
                    test_passed, error_message
                FROM llm_test_results
                WHERE test_run_id = ?
                ORDER BY
                    CASE
                        WHEN status = 'completed' THEN 1
                        WHEN status = 'timeout' THEN 2
                        WHEN status = 'failed' THEN 3
                        ELSE 4
                    END,
                    duration_seconds ASC
            """,
                (latest_run["id"],),
            ).fetchall()

            return jsonify(
                {
                    "success": True,
                    "test_name": test_name,
                    "comparison": [dict(row) for row in results],
                }
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
