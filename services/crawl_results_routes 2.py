#!/usr/bin/env python3
"""
Crawl Results API Routes

Provides endpoints for storing and retrieving web crawler results.

Task: P06 - Add Crawl Results Storage
"""

import json
import logging
import sqlite3
from typing import Dict, List, Optional

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Create blueprint
crawl_results_bp = Blueprint("crawl_results", __name__, url_prefix="/api/crawl")

# Database path
DB_PATH = "data/architect.db"


def get_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


# =============================================================================
# API Endpoints
# =============================================================================


@crawl_results_bp.route("/results", methods=["POST"])
def save_result():
    """
    Save a crawl result.

    Body:
        {
            "task_id": 123,
            "prompt": "Find product prices",
            "start_url": "https://example.com",
            "final_url": "https://example.com/products",
            "success": true,
            "extracted_data": {"price": "$19.99"},
            "action_history": [...],
            "screenshots": ["path/to/screenshot.png"],
            "error_message": "",
            "duration_seconds": 12.5,
            "llm_provider": "claude"
        }

    Returns:
        {
            "success": true,
            "id": 1,
            "message": "Result saved"
        }
    """
    try:
        data = request.get_json()

        if not data or "task_id" not in data or "prompt" not in data:
            return (
                jsonify({"success": False, "error": "Missing required fields: task_id, prompt"}),
                400,
            )

        # Convert objects to JSON strings
        extracted_data_json = json.dumps(data.get("extracted_data", {}))
        action_history_json = json.dumps(data.get("action_history", []))
        screenshots_json = json.dumps(data.get("screenshots", []))

        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO crawl_results (
                    task_id, prompt, start_url, final_url, success,
                    extracted_data, action_history, screenshots,
                    error_message, duration_seconds, llm_provider
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["task_id"],
                    data["prompt"],
                    data.get("start_url", ""),
                    data.get("final_url", ""),
                    data.get("success", False),
                    extracted_data_json,
                    action_history_json,
                    screenshots_json,
                    data.get("error_message", ""),
                    data.get("duration_seconds", 0.0),
                    data.get("llm_provider", ""),
                ),
            )
            conn.commit()
            result_id = cursor.lastrowid

        logger.info(f"Saved crawl result {result_id} for task {data['task_id']}")
        return jsonify(
            {
                "success": True,
                "id": result_id,
                "message": f"Crawl result saved with ID {result_id}",
            }
        )

    except Exception as e:
        logger.error(f"Error saving crawl result: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@crawl_results_bp.route("/<int:task_id>/result", methods=["GET"])
def get_result(task_id: int):
    """
    Get crawl result for a specific task.

    Returns:
        {
            "success": true,
            "result": {
                "id": 1,
                "task_id": 123,
                "prompt": "...",
                "start_url": "...",
                "final_url": "...",
                "success": true,
                "extracted_data": {...},
                "action_history": [...],
                "screenshots": [...],
                "error_message": "",
                "duration_seconds": 12.5,
                "llm_provider": "claude",
                "created_at": "2026-02-10T08:00:00"
            }
        }
    """
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM crawl_results
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (task_id,),
            )
            row = cursor.fetchone()

        if not row:
            return jsonify({"success": False, "error": "Result not found"}), 404

        # Convert row to dict and parse JSON fields
        result = dict(row)
        result["extracted_data"] = json.loads(result["extracted_data"]) if result["extracted_data"] else {}
        result["action_history"] = json.loads(result["action_history"]) if result["action_history"] else []
        result["screenshots"] = json.loads(result["screenshots"]) if result["screenshots"] else []

        return jsonify({"success": True, "result": result})

    except Exception as e:
        logger.error(f"Error getting crawl result: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@crawl_results_bp.route("/history", methods=["GET"])
def get_history():
    """
    Get crawl result history.

    Query params:
        limit: Max results (default 50, max 500)
        offset: Pagination offset (default 0)
        success: Filter by success status (true/false)
        llm_provider: Filter by LLM provider

    Returns:
        {
            "success": true,
            "results": [...],
            "count": 10,
            "total": 100
        }
    """
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
        offset = int(request.args.get("offset", 0))
        success_filter = request.args.get("success")
        llm_provider = request.args.get("llm_provider")

        # Build query
        query = "SELECT * FROM crawl_results WHERE 1=1"
        params = []

        if success_filter is not None:
            query += " AND success = ?"
            params.append(success_filter.lower() == "true")

        if llm_provider:
            query += " AND llm_provider = ?"
            params.append(llm_provider)

        # Get total count
        with get_connection() as conn:
            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            total = conn.execute(count_query, params).fetchone()[0]

            # Get paginated results
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        # Convert to list of dicts and parse JSON
        results = []
        for row in rows:
            result = dict(row)
            result["extracted_data"] = json.loads(result["extracted_data"]) if result["extracted_data"] else {}
            result["action_history"] = json.loads(result["action_history"]) if result["action_history"] else []
            result["screenshots"] = json.loads(result["screenshots"]) if result["screenshots"] else []
            results.append(result)

        return jsonify(
            {
                "success": True,
                "results": results,
                "count": len(results),
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    except Exception as e:
        logger.error(f"Error getting crawl history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@crawl_results_bp.route("/stats", methods=["GET"])
def get_stats():
    """
    Get crawl results statistics.

    Returns:
        {
            "success": true,
            "stats": {
                "total_crawls": 100,
                "successful_crawls": 85,
                "failed_crawls": 15,
                "success_rate": 85.0,
                "avg_duration_seconds": 10.5,
                "by_provider": {
                    "claude": {"count": 60, "success_rate": 90.0},
                    "ollama": {"count": 40, "success_rate": 77.5}
                },
                "recent_crawls": [...]
            }
        }
    """
    try:
        with get_connection() as conn:
            # Overall stats
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    AVG(duration_seconds) as avg_duration
                FROM crawl_results
                """
            )
            row = cursor.fetchone()
            total = row[0]
            successful = row[1]
            avg_duration = row[2] or 0

            # Stats by provider
            cursor = conn.execute(
                """
                SELECT
                    llm_provider,
                    COUNT(*) as count,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM crawl_results
                WHERE llm_provider != ''
                GROUP BY llm_provider
                """
            )
            by_provider = {}
            for row in cursor.fetchall():
                provider = row[0]
                count = row[1]
                success_count = row[2]
                by_provider[provider] = {
                    "count": count,
                    "success_rate": round((success_count / count * 100) if count > 0 else 0, 1),
                }

            # Recent crawls
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, task_id, prompt, success, duration_seconds, llm_provider, created_at
                FROM crawl_results
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            recent_crawls = [dict(row) for row in cursor.fetchall()]

        stats = {
            "total_crawls": total,
            "successful_crawls": successful,
            "failed_crawls": total - successful,
            "success_rate": round((successful / total * 100) if total > 0 else 0, 1),
            "avg_duration_seconds": round(avg_duration, 2),
            "by_provider": by_provider,
            "recent_crawls": recent_crawls,
        }

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        logger.error(f"Error getting crawl stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@crawl_results_bp.route("/<int:result_id>", methods=["DELETE"])
def delete_result(result_id: int):
    """
    Delete a crawl result.

    Returns:
        {
            "success": true,
            "message": "Result deleted"
        }
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM crawl_results WHERE id = ?",
                (result_id,),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"success": False, "error": "Result not found"}), 404

        logger.info(f"Deleted crawl result {result_id}")
        return jsonify({"success": True, "message": "Result deleted"})

    except Exception as e:
        logger.error(f"Error deleting crawl result: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@crawl_results_bp.route("/cleanup", methods=["POST"])
def cleanup_old_results():
    """
    Clean up old crawl results.

    Body:
        {
            "days": 30  # Delete results older than this
        }

    Returns:
        {
            "success": true,
            "deleted_count": 10,
            "message": "Deleted 10 old results"
        }
    """
    try:
        data = request.get_json() or {}
        days = data.get("days", 30)

        with get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM crawl_results
                WHERE created_at < datetime('now', '-' || ? || ' days')
                """,
                (days,),
            )
            conn.commit()
            deleted_count = cursor.rowcount

        logger.info(f"Cleaned up {deleted_count} crawl results older than {days} days")
        return jsonify(
            {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Deleted {deleted_count} results older than {days} days",
            }
        )

    except Exception as e:
        logger.error(f"Error cleaning up crawl results: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
