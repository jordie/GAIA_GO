#!/usr/bin/env python3
"""
Test LLM Metrics API Endpoints

Tests the new LLM provider metrics, costs, and health endpoints.
"""

import sys
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import json

from services.llm_metrics import LLMMetricsService


def test_providers():
    """Test get_all_providers."""
    print("\n" + "=" * 60)
    print("TEST: Get All Providers")
    print("=" * 60)

    providers = LLMMetricsService.get_all_providers()

    print(f"Found {len(providers)} providers:\n")
    for p in providers:
        print(f"  {p['display_name']}")
        print(f"    Type: {p['provider_type']}")
        print(f"    Priority: {p['priority']}")
        print(f"    Enabled: {p['is_enabled']}")
        print(f"    Available: {p.get('is_available', 'N/A')}")
        print(f"    Circuit State: {p.get('circuit_state', 'N/A')}")
        print(f"    Requests: {p.get('total_requests', 0)}")
        print()

    return len(providers) > 0


def test_metrics():
    """Test get_provider_metrics."""
    print("\n" + "=" * 60)
    print("TEST: Get Provider Metrics (7 days)")
    print("=" * 60)

    metrics = LLMMetricsService.get_provider_metrics(days=7)

    print(f"Metrics for {len(metrics)} providers:\n")
    for m in metrics:
        print(f"  {m['display_name']}")
        print(f"    Total Requests: {m['total_requests']}")
        print(f"    Successful: {m['successful_requests']}")
        print(f"    Failed: {m['failed_requests']}")
        print(f"    Success Rate: {m['success_rate']}%")
        print(f"    Total Tokens: {m['total_tokens']}")
        print(f"    Avg Duration: {m['avg_duration_seconds']}")
        print()

    return True


def test_costs():
    """Test get_cost_summary."""
    print("\n" + "=" * 60)
    print("TEST: Get Cost Summary (30 days)")
    print("=" * 60)

    costs = LLMMetricsService.get_cost_summary(days=30)

    print(f"Cost Summary:")
    print(f"  Total Cost: ${costs['total_cost_usd']}")
    print(f"  Total Tokens: {costs['total_tokens']:,}")
    print(f"  Total Requests: {costs['total_requests']}")
    print(f"  Local Requests: {costs['local_requests']}")
    print(f"  Remote Requests: {costs['remote_requests']}")
    print(f"\n  Hypothetical Claude Cost: ${costs['hypothetical_claude_cost_usd']}")
    print(
        f"  Estimated Savings: ${costs['estimated_savings_usd']} ({costs['savings_percentage']}%)"
    )

    print(f"\n  Breakdown by Provider:")
    for p in costs["providers"]:
        print(f"    {p['display_name']}")
        print(f"      Requests: {p['request_count']}")
        print(f"      Tokens: {p['total_tokens']:,}")
        print(f"      Cost: ${p['actual_cost_usd']}")

    return True


def test_record_request():
    """Test recording a request."""
    print("\n" + "=" * 60)
    print("TEST: Record Sample Request")
    print("=" * 60)

    # Record a sample Ollama request
    success = LLMMetricsService.record_request(
        provider_name="ollama",
        model="llama3.2",
        status="success",
        prompt_tokens=150,
        completion_tokens=300,
        duration_seconds=0.52,
        session_id="test-session",
        endpoint="/api/generate",
    )

    print(f"  Record Ollama request: {'✓ Success' if success else '✗ Failed'}")

    # Record a sample Claude request
    success2 = LLMMetricsService.record_request(
        provider_name="claude",
        model="claude-sonnet-4-5",
        status="success",
        prompt_tokens=200,
        completion_tokens=500,
        duration_seconds=1.23,
        session_id="test-session",
        endpoint="/v1/messages",
    )

    print(f"  Record Claude request: {'✓ Success' if success2 else '✗ Failed'}")

    # Record a failed request with fallback
    success3 = LLMMetricsService.record_request(
        provider_name="ollama",
        model="llama3.2",
        status="success",
        prompt_tokens=100,
        completion_tokens=200,
        duration_seconds=0.45,
        is_fallback=True,
        original_provider_name="localai",
        session_id="test-session",
    )

    print(f"  Record fallback request: {'✓ Success' if success3 else '✗ Failed'}")

    return success and success2 and success3


def test_trends():
    """Test get_daily_trends."""
    print("\n" + "=" * 60)
    print("TEST: Get Daily Trends (7 days)")
    print("=" * 60)

    trends = LLMMetricsService.get_daily_trends(days=7)

    print(f"Found {len(trends)} daily records:\n")

    # Group by date
    by_date = {}
    for trend in trends:
        date = trend["date"]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(trend)

    for date in sorted(by_date.keys(), reverse=True):
        print(f"  {date}:")
        for trend in by_date[date]:
            print(
                f"    {trend['display_name']}: {trend['total_requests']} requests, {trend['total_tokens']} tokens"
            )

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Metrics Service Tests")
    print("=" * 60)

    tests = [
        ("Providers", test_providers),
        ("Metrics", test_metrics),
        ("Costs", test_costs),
        ("Record Request", test_record_request),
        ("Trends", test_trends),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' failed with error: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\n  {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
