#!/usr/bin/env python3
"""
LLM Metrics Service

Tracks usage, metrics, and costs for LLM providers (Ollama, LocalAI, Claude, OpenAI).
Provides aggregated statistics and cost analysis.
"""

import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
SERVICE_DIR = Path(__file__).parent
BASE_DIR = SERVICE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import get_connection


class LLMMetricsService:
    """Service for tracking and analyzing LLM provider metrics."""

    # Pricing per 1M tokens (USD)
    PRICING = {
        "ollama": {"input": 0.0, "output": 0.0},  # Local = free
        "localai": {"input": 0.0, "output": 0.0},  # Local = free
        "claude": {"input": 3.0, "output": 15.0},  # Claude Sonnet 4.5
        "openai": {"input": 5.0, "output": 15.0},  # GPT-4 Turbo
    }

    @staticmethod
    def get_provider_by_name(name: str) -> Optional[Dict]:
        """Get provider details by name."""
        try:
            with get_connection("main") as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                provider = cursor.execute(
                    """
                    SELECT * FROM llm_providers
                    WHERE name = ? OR display_name = ?
                """,
                    (name, name),
                ).fetchone()

                return dict(provider) if provider else None
        except Exception as e:
            print(f"Error getting provider: {e}")
            return None

    @staticmethod
    def get_all_providers() -> List[Dict]:
        """Get all LLM providers with their current status."""
        try:
            with get_connection("main") as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                providers = cursor.execute(
                    """
                    SELECT
                        p.*,
                        h.is_available,
                        h.circuit_state,
                        h.failure_count,
                        h.total_requests,
                        h.successful_requests,
                        h.failed_requests,
                        h.avg_response_time_ms,
                        h.last_success_at,
                        h.last_failure_at
                    FROM llm_providers p
                    LEFT JOIN llm_provider_health h ON p.id = h.provider_id
                    ORDER BY p.priority ASC
                """
                ).fetchall()

                return [dict(row) for row in providers]
        except Exception as e:
            print(f"Error getting providers: {e}")
            return []

    @staticmethod
    def get_provider_metrics(provider_id: Optional[int] = None, days: int = 7) -> List[Dict]:
        """
        Get aggregated metrics for providers.

        Args:
            provider_id: Optional provider ID to filter by
            days: Number of days to look back

        Returns:
            List of metric records
        """
        try:
            with get_connection("main") as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                where_clause = ""
                params = []

                if provider_id:
                    where_clause = "WHERE r.provider_id = ?"
                    params.append(provider_id)

                metrics = cursor.execute(
                    f"""
                    SELECT
                        p.id as provider_id,
                        p.name as provider_name,
                        p.display_name,
                        p.provider_type,
                        COUNT(r.id) as total_requests,
                        SUM(CASE WHEN r.status = 'success' THEN 1 ELSE 0 END) as successful_requests,
                        SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failed_requests,
                        SUM(CASE WHEN r.status = 'timeout' THEN 1 ELSE 0 END) as timeout_requests,
                        SUM(r.total_tokens) as total_tokens,
                        SUM(r.prompt_tokens) as prompt_tokens,
                        SUM(r.completion_tokens) as completion_tokens,
                        SUM(r.cost_usd) as total_cost_usd,
                        AVG(r.duration_seconds) as avg_duration_seconds,
                        SUM(CASE WHEN r.is_fallback = 1 THEN 1 ELSE 0 END) as fallback_count,
                        MIN(r.created_at) as first_request_at,
                        MAX(r.created_at) as last_request_at
                    FROM llm_providers p
                    LEFT JOIN llm_requests r ON p.id = r.provider_id
                        AND r.created_at >= datetime('now', '-{days} days')
                    {where_clause}
                    GROUP BY p.id
                    ORDER BY p.priority ASC
                """,
                    params,
                ).fetchall()

                result = []
                for row in metrics:
                    metric = dict(row)

                    # Calculate success rate
                    if metric["total_requests"] and metric["total_requests"] > 0:
                        metric["success_rate"] = round(
                            (metric["successful_requests"] / metric["total_requests"]) * 100, 2
                        )
                    else:
                        metric["success_rate"] = 0.0

                    result.append(metric)

                return result
        except Exception as e:
            print(f"Error getting provider metrics: {e}")
            return []

    @staticmethod
    def get_cost_summary(days: int = 30) -> Dict:
        """
        Get cost summary with savings calculation.

        Args:
            days: Number of days to look back

        Returns:
            Cost summary with total, by provider, and estimated savings
        """
        try:
            with get_connection("main") as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get actual costs
                costs = cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.name,
                        p.display_name,
                        p.provider_type,
                        COUNT(r.id) as request_count,
                        SUM(r.prompt_tokens) as prompt_tokens,
                        SUM(r.completion_tokens) as completion_tokens,
                        SUM(r.total_tokens) as total_tokens,
                        SUM(r.cost_usd) as actual_cost_usd
                    FROM llm_providers p
                    LEFT JOIN llm_requests r ON p.id = r.provider_id
                        AND r.created_at >= datetime('now', '-? days')
                        AND r.status = 'success'
                    GROUP BY p.id
                """,
                    (days,),
                ).fetchall()

                total_cost = 0.0
                total_tokens = 0
                total_requests = 0
                local_requests = 0
                remote_requests = 0
                providers_detail = []

                # Calculate what it would have cost with Claude
                hypothetical_claude_cost = 0.0

                for row in costs:
                    cost_data = dict(row)
                    total_cost += cost_data["actual_cost_usd"] or 0.0
                    total_tokens += cost_data["total_tokens"] or 0
                    total_requests += cost_data["request_count"] or 0

                    if cost_data["provider_type"] == "local":
                        local_requests += cost_data["request_count"] or 0
                    else:
                        remote_requests += cost_data["request_count"] or 0

                    # Calculate hypothetical Claude cost for all requests
                    if cost_data["prompt_tokens"] and cost_data["completion_tokens"]:
                        hypothetical_claude_cost += (
                            cost_data["prompt_tokens"] / 1_000_000
                        ) * LLMMetricsService.PRICING["claude"]["input"] + (
                            cost_data["completion_tokens"] / 1_000_000
                        ) * LLMMetricsService.PRICING[
                            "claude"
                        ][
                            "output"
                        ]

                    providers_detail.append(cost_data)

                # Estimated savings = what we would have paid with Claude - what we actually paid
                estimated_savings = hypothetical_claude_cost - total_cost

                return {
                    "total_cost_usd": round(total_cost, 2),
                    "total_tokens": total_tokens,
                    "total_requests": total_requests,
                    "local_requests": local_requests,
                    "remote_requests": remote_requests,
                    "estimated_savings_usd": round(estimated_savings, 2),
                    "hypothetical_claude_cost_usd": round(hypothetical_claude_cost, 2),
                    "savings_percentage": round(
                        (estimated_savings / hypothetical_claude_cost * 100), 2
                    )
                    if hypothetical_claude_cost > 0
                    else 0.0,
                    "providers": providers_detail,
                    "days": days,
                }
        except Exception as e:
            print(f"Error getting cost summary: {e}")
            return {
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "total_requests": 0,
                "local_requests": 0,
                "remote_requests": 0,
                "estimated_savings_usd": 0.0,
                "hypothetical_claude_cost_usd": 0.0,
                "savings_percentage": 0.0,
                "providers": [],
                "days": days,
            }

    @staticmethod
    def record_request(
        provider_name: str,
        model: str,
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        duration_seconds: float = 0.0,
        error_message: Optional[str] = None,
        is_fallback: bool = False,
        original_provider_name: Optional[str] = None,
        session_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        request_metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Record an LLM request for metrics tracking.

        Args:
            provider_name: Name of the provider (ollama, claude, etc.)
            model: Model used (llama3.2, claude-sonnet-4-5, etc.)
            status: success, failed, timeout
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            duration_seconds: Request duration
            error_message: Optional error message if failed
            is_fallback: Whether this was a fallback attempt
            original_provider_name: If fallback, which provider failed
            session_id: Optional session/workflow ID
            endpoint: Optional API endpoint
            user_id: Optional user ID
            request_metadata: Optional additional metadata

        Returns:
            True if recorded successfully
        """
        try:
            with get_connection("main") as conn:
                cursor = conn.cursor()

                # Get provider ID
                provider = cursor.execute(
                    "SELECT id FROM llm_providers WHERE name = ?", (provider_name,)
                ).fetchone()

                if not provider:
                    print(f"Provider {provider_name} not found")
                    return False

                provider_id = provider[0]

                # Get original provider ID if fallback
                original_provider_id = None
                if is_fallback and original_provider_name:
                    orig = cursor.execute(
                        "SELECT id FROM llm_providers WHERE name = ?", (original_provider_name,)
                    ).fetchone()
                    if orig:
                        original_provider_id = orig[0]

                # Calculate cost
                total_tokens = prompt_tokens + completion_tokens
                cost_usd = 0.0

                if provider_name in LLMMetricsService.PRICING:
                    pricing = LLMMetricsService.PRICING[provider_name]
                    cost_usd = (prompt_tokens / 1_000_000) * pricing["input"] + (
                        completion_tokens / 1_000_000
                    ) * pricing["output"]

                # Insert request record
                cursor.execute(
                    """
                    INSERT INTO llm_requests (
                        provider_id, session_id, model, endpoint,
                        prompt_tokens, completion_tokens, total_tokens,
                        duration_seconds, status, error_message, cost_usd,
                        is_fallback, original_provider_id, user_id, request_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        provider_id,
                        session_id,
                        model,
                        endpoint,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        duration_seconds,
                        status,
                        error_message,
                        cost_usd,
                        1 if is_fallback else 0,
                        original_provider_id,
                        user_id,
                        json.dumps(request_metadata) if request_metadata else None,
                    ),
                )

                # Update provider health
                LLMMetricsService._update_provider_health(
                    cursor, provider_id, status, duration_seconds
                )

                # Update daily costs
                LLMMetricsService._update_daily_costs(
                    cursor,
                    provider_id,
                    total_tokens,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    status,
                )

                conn.commit()
                return True

        except Exception as e:
            print(f"Error recording request: {e}")
            return False

    @staticmethod
    def _update_provider_health(cursor, provider_id: int, status: str, duration_seconds: float):
        """Update provider health statistics."""
        # Get current health record
        health = cursor.execute(
            "SELECT * FROM llm_provider_health WHERE provider_id = ?", (provider_id,)
        ).fetchone()

        if not health:
            # Create initial health record
            cursor.execute(
                """
                INSERT INTO llm_provider_health (provider_id, is_available, circuit_state)
                VALUES (?, 1, 'closed')
            """,
                (provider_id,),
            )
            health = cursor.execute(
                "SELECT * FROM llm_provider_health WHERE provider_id = ?", (provider_id,)
            ).fetchone()

        # Update counters
        total_requests = (health[7] or 0) + 1
        successful_requests = health[8] or 0
        failed_requests = health[9] or 0

        if status == "success":
            successful_requests += 1
            cursor.execute(
                """
                UPDATE llm_provider_health
                SET failure_count = 0,
                    last_success_at = CURRENT_TIMESTAMP,
                    circuit_state = 'closed',
                    is_available = 1
                WHERE provider_id = ?
            """,
                (provider_id,),
            )
        else:
            failed_requests += 1
            failure_count = (health[3] or 0) + 1
            cursor.execute(
                """
                UPDATE llm_provider_health
                SET failure_count = ?,
                    last_failure_at = CURRENT_TIMESTAMP
                WHERE provider_id = ?
            """,
                (failure_count, provider_id),
            )

        # Update request stats and avg response time
        avg_response_time = health[10] or 0.0
        new_avg = (
            (avg_response_time * (total_requests - 1)) + (duration_seconds * 1000)
        ) / total_requests

        cursor.execute(
            """
            UPDATE llm_provider_health
            SET total_requests = ?,
                successful_requests = ?,
                failed_requests = ?,
                avg_response_time_ms = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE provider_id = ?
        """,
            (total_requests, successful_requests, failed_requests, new_avg, provider_id),
        )

    @staticmethod
    def _update_daily_costs(
        cursor,
        provider_id: int,
        total_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        status: str,
    ):
        """Update daily cost aggregations."""
        today = date.today().isoformat()

        # Check if record exists
        existing = cursor.execute(
            """
            SELECT * FROM llm_costs_daily
            WHERE provider_id = ? AND date = ?
        """,
            (provider_id, today),
        ).fetchone()

        if existing:
            # Update existing record
            cursor.execute(
                """
                UPDATE llm_costs_daily
                SET total_requests = total_requests + 1,
                    successful_requests = successful_requests + ?,
                    failed_requests = failed_requests + ?,
                    total_tokens = total_tokens + ?,
                    prompt_tokens = prompt_tokens + ?,
                    completion_tokens = completion_tokens + ?,
                    total_cost_usd = total_cost_usd + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE provider_id = ? AND date = ?
            """,
                (
                    1 if status == "success" else 0,
                    1 if status != "success" else 0,
                    total_tokens,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    provider_id,
                    today,
                ),
            )
        else:
            # Insert new record
            cursor.execute(
                """
                INSERT INTO llm_costs_daily (
                    provider_id, date, total_requests, successful_requests, failed_requests,
                    total_tokens, prompt_tokens, completion_tokens, total_cost_usd
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
                (
                    provider_id,
                    today,
                    1 if status == "success" else 0,
                    1 if status != "success" else 0,
                    total_tokens,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                ),
            )

    @staticmethod
    def get_daily_trends(days: int = 30) -> List[Dict]:
        """Get daily cost and usage trends."""
        try:
            with get_connection("main") as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                trends = cursor.execute(
                    """
                    SELECT
                        c.date,
                        p.name as provider_name,
                        p.display_name,
                        c.total_requests,
                        c.successful_requests,
                        c.total_tokens,
                        c.total_cost_usd
                    FROM llm_costs_daily c
                    JOIN llm_providers p ON c.provider_id = p.id
                    WHERE c.date >= date('now', '-? days')
                    ORDER BY c.date DESC, p.priority ASC
                """,
                    (days,),
                ).fetchall()

                return [dict(row) for row in trends]
        except Exception as e:
            print(f"Error getting daily trends: {e}")
            return []


if __name__ == "__main__":
    # Test the service
    service = LLMMetricsService()

    print("Testing LLM Metrics Service...")
    print("\nAll Providers:")
    providers = service.get_all_providers()
    for p in providers:
        print(f"  - {p['display_name']} ({p['name']}): {p['provider_type']}")

    print("\nProvider Metrics (last 7 days):")
    metrics = service.get_provider_metrics(days=7)
    for m in metrics:
        print(
            f"  - {m['display_name']}: {m['total_requests']} requests, {m['success_rate']}% success"
        )

    print("\nCost Summary (last 30 days):")
    costs = service.get_cost_summary(days=30)
    print(f"  Total Cost: ${costs['total_cost_usd']}")
    print(
        f"  Estimated Savings: ${costs['estimated_savings_usd']} ({costs['savings_percentage']}%)"
    )
    print(f"  Local Requests: {costs['local_requests']}")
    print(f"  Remote Requests: {costs['remote_requests']}")
