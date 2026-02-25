"""
LLM Metrics API Routes
API endpoints for managing and viewing LLM provider metrics, costs, and health
"""

import sqlite3
from functools import wraps

from flask import Blueprint, jsonify, request

from db import get_connection
from services.llm_metrics import LLMMetricsService

llm_metrics_bp = Blueprint("llm_metrics", __name__)


def require_auth_decorator(f):
    """Decorator for authentication - placeholder"""

    @wraps(f)
    def decorated(*args, **kwargs):
        # Authentication handled by main app
        return f(*args, **kwargs)

    return decorated


@llm_metrics_bp.route("/api/llm/providers", methods=["GET"])
@require_auth_decorator
def get_llm_providers():
    """
    Get all LLM providers with their current status.

    Returns:
        200: List of providers with health status
            {
                "success": true,
                "providers": [
                    {
                        "id": 1,
                        "name": "ollama",
                        "display_name": "Ollama (Local)",
                        "provider_type": "local",
                        "base_url": "http://localhost:11434",
                        "is_enabled": 1,
                        "priority": 1,
                        "is_available": 1,
                        "circuit_state": "closed",
                        "failure_count": 0,
                        "total_requests": 150,
                        "successful_requests": 148,
                        "failed_requests": 2,
                        "avg_response_time_ms": 523.4,
                        "last_success_at": "2026-02-07 19:00:00"
                    },
                    ...
                ]
            }

    Example:
        GET /api/llm/providers
    """
    try:
        providers = LLMMetricsService.get_all_providers()

        # Add status indicator based on health
        for provider in providers:
            if provider["circuit_state"] == "open":
                provider["status"] = "unavailable"
            elif provider["circuit_state"] == "half_open":
                provider["status"] = "recovering"
            elif provider["is_available"]:
                provider["status"] = "healthy"
            else:
                provider["status"] = "unknown"

        return jsonify({"success": True, "providers": providers})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_metrics_bp.route("/api/llm/metrics", methods=["GET"])
@require_auth_decorator
def get_llm_metrics():
    """
    Get usage metrics per provider.

    Query Parameters:
        provider: Optional provider name to filter by
        days: Number of days to look back (default: 7)

    Returns:
        200: Metrics for each provider
            {
                "success": true,
                "metrics": [
                    {
                        "provider_id": 1,
                        "provider_name": "ollama",
                        "display_name": "Ollama (Local)",
                        "provider_type": "local",
                        "total_requests": 150,
                        "successful_requests": 148,
                        "failed_requests": 2,
                        "timeout_requests": 0,
                        "total_tokens": 1500000,
                        "prompt_tokens": 500000,
                        "completion_tokens": 1000000,
                        "total_cost_usd": 0.0,
                        "avg_duration_seconds": 0.52,
                        "fallback_count": 5,
                        "success_rate": 98.67,
                        "first_request_at": "2026-02-01 10:00:00",
                        "last_request_at": "2026-02-07 19:00:00"
                    },
                    ...
                ],
                "days": 7
            }

    Examples:
        GET /api/llm/metrics
        GET /api/llm/metrics?days=30
        GET /api/llm/metrics?provider=ollama&days=7
    """
    try:
        days = request.args.get("days", 7, type=int)
        provider_name = request.args.get("provider")

        provider_id = None
        if provider_name:
            provider = LLMMetricsService.get_provider_by_name(provider_name)
            if provider:
                provider_id = provider["id"]

        metrics = LLMMetricsService.get_provider_metrics(provider_id=provider_id, days=days)

        return jsonify({"success": True, "metrics": metrics, "days": days})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_metrics_bp.route("/api/llm/costs", methods=["GET"])
@require_auth_decorator
def get_llm_costs():
    """
    Get cost tracking per provider with estimated savings.

    Query Parameters:
        days: Number of days to look back (default: 30)

    Returns:
        200: Cost summary with savings calculation
            {
                "success": true,
                "costs": {
                    "total_cost_usd": 45.23,
                    "total_tokens": 15000000,
                    "total_requests": 500,
                    "local_requests": 450,
                    "remote_requests": 50,
                    "estimated_savings_usd": 180.50,
                    "hypothetical_claude_cost_usd": 225.73,
                    "savings_percentage": 79.97,
                    "providers": [
                        {
                            "id": 1,
                            "name": "ollama",
                            "display_name": "Ollama (Local)",
                            "provider_type": "local",
                            "request_count": 450,
                            "prompt_tokens": 4500000,
                            "completion_tokens": 9000000,
                            "total_tokens": 13500000,
                            "actual_cost_usd": 0.0
                        },
                        {
                            "id": 3,
                            "name": "claude",
                            "display_name": "Claude (Anthropic)",
                            "provider_type": "remote",
                            "request_count": 50,
                            "prompt_tokens": 500000,
                            "completion_tokens": 1000000,
                            "total_tokens": 1500000,
                            "actual_cost_usd": 45.23
                        }
                    ],
                    "days": 30
                }
            }

    Example:
        GET /api/llm/costs
        GET /api/llm/costs?days=90
    """
    try:
        days = request.args.get("days", 30, type=int)
        costs = LLMMetricsService.get_cost_summary(days=days)

        return jsonify({"success": True, "costs": costs})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_metrics_bp.route("/api/llm/trends", methods=["GET"])
@require_auth_decorator
def get_llm_trends():
    """
    Get daily usage and cost trends.

    Query Parameters:
        days: Number of days to look back (default: 30)

    Returns:
        200: Daily trend data
            {
                "success": true,
                "trends": [
                    {
                        "date": "2026-02-07",
                        "provider_name": "ollama",
                        "display_name": "Ollama (Local)",
                        "total_requests": 25,
                        "successful_requests": 24,
                        "total_tokens": 250000,
                        "total_cost_usd": 0.0
                    },
                    ...
                ],
                "days": 30
            }

    Example:
        GET /api/llm/trends
        GET /api/llm/trends?days=7
    """
    try:
        days = request.args.get("days", 30, type=int)
        trends = LLMMetricsService.get_daily_trends(days=days)

        return jsonify({"success": True, "trends": trends, "days": days})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_metrics_bp.route("/api/llm/record", methods=["POST"])
@require_auth_decorator
def record_llm_request():
    """
    Record an LLM request for metrics tracking.

    Request Body:
        {
            "provider": "ollama",
            "model": "llama3.2",
            "status": "success",
            "prompt_tokens": 150,
            "completion_tokens": 300,
            "duration_seconds": 0.52,
            "error_message": null,
            "is_fallback": false,
            "original_provider": null,
            "session_id": "session-123",
            "endpoint": "/api/generate",
            "user_id": "user-1",
            "metadata": {}
        }

    Returns:
        200: Request recorded successfully
            {"success": true, "message": "Request recorded"}
        400: Invalid request
            {"success": false, "error": "Provider name required"}

    Example:
        POST /api/llm/record
        {
            "provider": "ollama",
            "model": "llama3.2",
            "status": "success",
            "prompt_tokens": 100,
            "completion_tokens": 200
        }
    """
    try:
        data = request.get_json()

        if not data.get("provider"):
            return jsonify({"success": False, "error": "Provider name required"}), 400

        if not data.get("model"):
            return jsonify({"success": False, "error": "Model name required"}), 400

        if not data.get("status"):
            return (
                jsonify({"success": False, "error": "Status required (success, failed, timeout)"}),
                400,
            )

        success = LLMMetricsService.record_request(
            provider_name=data["provider"],
            model=data["model"],
            status=data["status"],
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            duration_seconds=data.get("duration_seconds", 0.0),
            error_message=data.get("error_message"),
            is_fallback=data.get("is_fallback", False),
            original_provider_name=data.get("original_provider"),
            session_id=data.get("session_id"),
            endpoint=data.get("endpoint"),
            user_id=data.get("user_id"),
            request_metadata=data.get("metadata"),
        )

        if success:
            return jsonify({"success": True, "message": "Request recorded"})
        else:
            return jsonify({"success": False, "error": "Failed to record request"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_metrics_bp.route("/api/llm/providers/<int:provider_id>/enable", methods=["POST"])
@require_auth_decorator
def enable_provider(provider_id):
    """
    Enable or disable a provider.

    Request Body:
        {"enabled": true}

    Returns:
        200: Provider updated
        404: Provider not found
    """
    try:
        data = request.get_json()
        enabled = data.get("enabled", True)

        with get_connection("main") as conn:
            cursor = conn.cursor()

            # Check if provider exists
            provider = cursor.execute(
                "SELECT id FROM llm_providers WHERE id = ?", (provider_id,)
            ).fetchone()

            if not provider:
                return jsonify({"success": False, "error": "Provider not found"}), 404

            # Update enabled status
            cursor.execute(
                """
                UPDATE llm_providers
                SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (1 if enabled else 0, provider_id),
            )

            conn.commit()

            return jsonify(
                {"success": True, "message": f"Provider {'enabled' if enabled else 'disabled'}"}
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@llm_metrics_bp.route("/api/llm/health", methods=["GET"])
@require_auth_decorator
def get_llm_health():
    """
    Get overall LLM system health.

    Returns:
        200: System health summary
            {
                "success": true,
                "health": {
                    "total_providers": 4,
                    "healthy_providers": 3,
                    "degraded_providers": 1,
                    "unavailable_providers": 0,
                    "local_providers_available": 2,
                    "remote_providers_available": 1,
                    "has_fallback": true
                }
            }
    """
    try:
        providers = LLMMetricsService.get_all_providers()

        total = len(providers)
        healthy = sum(1 for p in providers if p["circuit_state"] == "closed" and p["is_available"])
        degraded = sum(1 for p in providers if p["circuit_state"] == "half_open")
        unavailable = sum(
            1 for p in providers if p["circuit_state"] == "open" or not p["is_available"]
        )

        local_available = sum(
            1 for p in providers if p["provider_type"] == "local" and p["is_available"]
        )
        remote_available = sum(
            1 for p in providers if p["provider_type"] == "remote" and p["is_available"]
        )

        has_fallback = (local_available + remote_available) > 1

        return jsonify(
            {
                "success": True,
                "health": {
                    "total_providers": total,
                    "healthy_providers": healthy,
                    "degraded_providers": degraded,
                    "unavailable_providers": unavailable,
                    "local_providers_available": local_available,
                    "remote_providers_available": remote_available,
                    "has_fallback": has_fallback,
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
