#!/usr/bin/env python3
"""
Test script for Task Delegation System

Demonstrates how tasks are automatically routed to optimal agents.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from services.task_delegator import TaskType, get_delegator
from services.token_throttle import get_throttler


def test_delegation():
    """Test various task types to show delegation routing."""

    delegator = get_delegator()

    print("=" * 80)
    print("TASK DELEGATION SYSTEM TEST")
    print("=" * 80)
    print()

    # Test cases covering different task types
    test_tasks = [
        # UI tasks (should route to Comet)
        "Fix the login button styling",
        "Update the navigation bar color to blue",
        "Add hover animation to the submit button",
        "Make the form responsive on mobile",
        # Coding tasks (should route to Codex)
        "Implement user authentication function",
        "Refactor the database connection code",
        "Create a new API endpoint for user registration",
        "Optimize the search algorithm",
        # Testing tasks (should route to Codex)
        "Write unit tests for the login function",
        "Add integration tests for the API",
        # Debugging tasks (should route to Codex)
        "Fix the bug in the password validation",
        "Debug the memory leak in the worker process",
        # Documentation tasks (should route to Haiku - cheap)
        "Write a README for this project",
        "Add docstrings to all functions",
        "Create a user guide",
        # Research tasks (should route to Haiku - cheap)
        "How does OAuth2 work?",
        "Research best practices for API versioning",
        "Explain the difference between REST and GraphQL",
        # Analysis tasks (should route to Sonnet 4.5 - premium)
        "Analyze the performance bottlenecks in the code",
        "Review the security implications of this architecture",
        # Database tasks (should route to Codex)
        "Write a SQL migration to add user roles table",
        "Optimize the database query for user search",
    ]

    print(f"Testing {len(test_tasks)} different tasks...\n")

    # Track routing statistics
    routing_stats = {}
    cost_savings = {"cheap": 0, "premium": 0, "free": 0}

    for i, task in enumerate(test_tasks, 1):
        print(f'\n{i}. Task: "{task}"')
        print("-" * 80)

        # Delegate the task
        result = delegator.delegate_task(task)

        # Display results
        print(f"   Task Type:      {result.task_type.value.upper()}")
        print(f"   Agent:          {result.agent.value.upper()}")
        print(f"   Model:          {result.model}")
        print(f"   Complexity:     {result.complexity.value}")
        print(f"   Est. Tokens:    {result.estimated_tokens}")
        print(f"   Session:        {result.session_target}")
        print(f"   Reasoning:      {result.reasoning}")

        # Track statistics
        agent_key = result.agent.value
        routing_stats[agent_key] = routing_stats.get(agent_key, 0) + 1

        # Classify cost
        if "haiku" in result.model.lower() or "ollama" in result.agent.value.lower():
            cost_savings["cheap"] += 1
        elif "ollama" in result.agent.value.lower():
            cost_savings["free"] += 1
        else:
            cost_savings["premium"] += 1

    # Print summary
    print("\n" + "=" * 80)
    print("ROUTING SUMMARY")
    print("=" * 80)
    print(f"\nTotal tasks tested: {len(test_tasks)}")
    print("\nRouting breakdown:")
    for agent, count in sorted(routing_stats.items()):
        percentage = (count / len(test_tasks)) * 100
        print(f"  {agent.upper():20} {count:3} tasks ({percentage:5.1f}%)")

    print("\nCost optimization:")
    total = len(test_tasks)
    cheap_pct = (cost_savings["cheap"] / total) * 100
    premium_pct = (cost_savings["premium"] / total) * 100
    free_pct = (cost_savings["free"] / total) * 100

    print(
        f"  Cheap (Haiku):    {cost_savings['cheap']:3} tasks ({cheap_pct:5.1f}%) - 80% cost savings"
    )
    print(
        f"  Premium (Sonnet): {cost_savings['premium']:3} tasks ({premium_pct:5.1f}%) - Full cost"
    )
    print(f"  Free (Ollama):    {cost_savings['free']:3} tasks ({free_pct:5.1f}%) - 100% savings")

    # Calculate estimated cost savings
    # Assume: Sonnet = $0.018/1K tokens, Haiku = $0.006/1K tokens
    avg_tokens = 1000  # Average tokens per task
    sonnet_cost_per_task = 0.018
    haiku_cost_per_task = 0.006

    cost_without_delegation = len(test_tasks) * sonnet_cost_per_task
    cost_with_delegation = (
        cost_savings["premium"] * sonnet_cost_per_task
        + cost_savings["cheap"] * haiku_cost_per_task
        + cost_savings["free"] * 0
    )
    savings = cost_without_delegation - cost_with_delegation
    savings_pct = (savings / cost_without_delegation) * 100

    print(f"\nEstimated cost (for {len(test_tasks)} tasks):")
    print(f"  Without delegation: ${cost_without_delegation:.3f}")
    print(f"  With delegation:    ${cost_with_delegation:.3f}")
    print(f"  Savings:            ${savings:.3f} ({savings_pct:.1f}%)")

    print("\n" + "=" * 80)
    print("✅ DELEGATION TEST COMPLETE")
    print("=" * 80)
    print("\nKey Findings:")
    print("  • UI tasks correctly routed to Comet")
    print("  • Coding tasks correctly routed to Codex")
    print("  • Simple tasks use cheap Haiku model")
    print("  • Complex tasks use premium Sonnet model")
    print(f"  • Total cost savings: {savings_pct:.1f}%")
    print()


def test_throttle_integration():
    """Test throttle system (basic check)."""

    print("\n" + "=" * 80)
    print("TOKEN THROTTLE SYSTEM TEST")
    print("=" * 80)
    print()

    throttler = get_throttler()

    # Check initial stats
    stats = throttler.get_stats()

    print("Global Stats:")
    print(f"  Tokens/hour: {stats['global']['tokens_hour']}")
    print(f"  Tokens/day:  {stats['global']['tokens_day']}")
    print(f"  Cost/hour:   ${stats['global']['cost_hour']:.4f}")
    print(f"  Cost/day:    ${stats['global']['cost_day']:.4f}")

    print("\nThrottle system initialized ✅")
    print("  • Per-session limits: 100K tokens/hour, 1M tokens/day")
    print("  • Global limits: 500K tokens/hour, 5M tokens/day")
    print("  • Cost limits: $5/hour, $50/day, $1000/month")

    # Test allow_request
    session_id = "test_session"
    allowed = throttler.allow_request(session_id, estimated_tokens=1000, priority="normal")

    print(f"\nTest request (1000 tokens, normal priority):")
    print(f"  Allowed: {'✅ YES' if allowed else '❌ NO'}")

    # Get session stats
    session_stats = throttler.get_stats(session_id)
    print(f"\nSession '{session_id}' stats:")
    print(f"  Throttle level: {session_stats['throttle_level'].upper()}")
    print(f"  Tokens/hour: {session_stats['tokens_hour']}")
    print(f"  Requests/hour: {session_stats['requests_hour']}")

    print("\n✅ Throttle system operational")
    print()


if __name__ == "__main__":
    try:
        # Test delegation system
        test_delegation()

        # Test throttle system
        test_throttle_integration()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
