#!/usr/bin/env python3
"""
Milestone Summaries API
Tracks progress, achievements, and plan changes
"""

import json
from datetime import datetime

from flask import jsonify, request

import db as database


def register_milestone_summaries_routes(app, requires_auth):
    """Register milestone summaries API routes"""

    @app.route("/api/milestone-summaries", methods=["GET"])
    @requires_auth
    def get_milestone_summaries():
        """Get all milestone summaries with optional filtering"""
        phase = request.args.get("phase")
        status = request.args.get("status")
        limit = request.args.get("limit", 50, type=int)

        with database.get_connection("main") as conn:
            cursor = conn.cursor()

            query = """
                SELECT id, milestone_name, phase, status, summary, details,
                       metrics, blockers, next_steps, session_id, created_at, updated_at
                FROM milestone_summaries
                WHERE 1=1
            """
            params = []

            if phase:
                query += " AND phase = ?"
                params.append(phase)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            summaries = []
            for row in cursor.fetchall():
                summary = {
                    "id": row[0],
                    "milestone_name": row[1],
                    "phase": row[2],
                    "status": row[3],
                    "summary": row[4],
                    "details": row[5],
                    "metrics": json.loads(row[6]) if row[6] else {},
                    "blockers": json.loads(row[7]) if row[7] else [],
                    "next_steps": row[8],
                    "session_id": row[9],
                    "created_at": row[10],
                    "updated_at": row[11],
                }
                summaries.append(summary)

            return jsonify(summaries)

    @app.route("/api/milestone-summaries", methods=["POST"])
    @requires_auth
    def create_milestone_summary():
        """Create a new milestone summary"""
        data = request.json

        required_fields = ["milestone_name", "phase", "status", "summary"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400

        with database.get_connection("main") as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO milestone_summaries
                (milestone_name, phase, status, summary, details, metrics, blockers, next_steps, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["milestone_name"],
                    data["phase"],
                    data["status"],
                    data["summary"],
                    data.get("details"),
                    json.dumps(data.get("metrics", {})),
                    json.dumps(data.get("blockers", [])),
                    data.get("next_steps"),
                    data.get("session_id"),
                ),
            )

            summary_id = cursor.lastrowid

            return (
                jsonify(
                    {"id": summary_id, "success": True, "message": "Milestone summary created"}
                ),
                201,
            )

    @app.route("/api/milestone-summaries/<int:summary_id>", methods=["GET"])
    @requires_auth
    def get_milestone_summary(summary_id):
        """Get a specific milestone summary"""
        with database.get_connection("main") as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, milestone_name, phase, status, summary, details,
                       metrics, blockers, next_steps, session_id, created_at, updated_at
                FROM milestone_summaries
                WHERE id = ?
            """,
                (summary_id,),
            )

            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Milestone summary not found"}), 404

            summary = {
                "id": row[0],
                "milestone_name": row[1],
                "phase": row[2],
                "status": row[3],
                "summary": row[4],
                "details": row[5],
                "metrics": json.loads(row[6]) if row[6] else {},
                "blockers": json.loads(row[7]) if row[7] else [],
                "next_steps": row[8],
                "session_id": row[9],
                "created_at": row[10],
                "updated_at": row[11],
            }

            return jsonify(summary)

    @app.route("/api/milestone-summaries/<int:summary_id>", methods=["PUT"])
    @requires_auth
    def update_milestone_summary(summary_id):
        """Update a milestone summary"""
        data = request.json

        with database.get_connection("main") as conn:
            cursor = conn.cursor()

            # Build update query dynamically
            updates = []
            params = []

            if "status" in data:
                updates.append("status = ?")
                params.append(data["status"])

            if "summary" in data:
                updates.append("summary = ?")
                params.append(data["summary"])

            if "details" in data:
                updates.append("details = ?")
                params.append(data["details"])

            if "metrics" in data:
                updates.append("metrics = ?")
                params.append(json.dumps(data["metrics"]))

            if "blockers" in data:
                updates.append("blockers = ?")
                params.append(json.dumps(data["blockers"]))

            if "next_steps" in data:
                updates.append("next_steps = ?")
                params.append(data["next_steps"])

            if not updates:
                return jsonify({"error": "No fields to update"}), 400

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(summary_id)

            query = f'UPDATE milestone_summaries SET {", ".join(updates)} WHERE id = ?'
            cursor.execute(query, params)

            return jsonify({"success": True, "message": "Milestone summary updated"})

    @app.route("/api/milestone-summaries/stats", methods=["GET"])
    @requires_auth
    def get_milestone_stats():
        """Get statistics about milestone summaries"""
        with database.get_connection("main") as conn:
            cursor = conn.cursor()

            # Get counts by status
            cursor.execute(
                """
                SELECT status, COUNT(*) as count
                FROM milestone_summaries
                GROUP BY status
            """
            )
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Get counts by phase
            cursor.execute(
                """
                SELECT phase, COUNT(*) as count
                FROM milestone_summaries
                GROUP BY phase
            """
            )
            phase_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Get recent activity
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM milestone_summaries
                WHERE created_at > datetime('now', '-24 hours')
            """
            )
            recent_24h = cursor.fetchone()[0]

            return jsonify(
                {
                    "total": sum(status_counts.values()),
                    "by_status": status_counts,
                    "by_phase": phase_counts,
                    "recent_24h": recent_24h,
                }
            )
