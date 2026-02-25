#!/usr/bin/env python3
"""
Track PR Provider Attribution

This script demonstrates how to record which provider (Claude, Codex, Ollama)
worked on each stage of a pull request throughout the review, implementation,
and integration workflow.

Usage:
    # Record a new PR workflow
    python3 scripts/track_pr_attribution.py --pr 42 --title "Add health endpoint" \\
        --branch "feature/health-endpoint" --review-provider claude --review-session pr_review1

    # Update PR with implementation provider
    python3 scripts/track_pr_attribution.py --pr 42 --impl-provider codex --impl-session pr_impl1

    # View all PR attributions
    python3 scripts/track_pr_attribution.py --view-all

    # View specific PR
    python3 scripts/track_pr_attribution.py --pr 42 --view
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.multi_env_status import MultiEnvStatusManager  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Track PR provider attribution across workflow stages"
    )

    parser.add_argument("--pr", type=int, help="PR number/ID")
    parser.add_argument("--title", help="PR title/subject")
    parser.add_argument("--branch", help="Source branch name")
    parser.add_argument("--created-by", help="Original creator")

    parser.add_argument("--review-provider", help="Provider for code review (claude/codex/ollama)")
    parser.add_argument("--review-session", help="Session name for review (e.g., pr_review1)")

    parser.add_argument("--impl-provider", help="Provider for implementation (claude/codex/ollama)")
    parser.add_argument("--impl-session", help="Session name for implementation (e.g., pr_impl1)")

    parser.add_argument(
        "--integ-provider", help="Provider for integration/testing (claude/codex/ollama)"
    )
    parser.add_argument("--integ-session", help="Session name for integration (e.g., pr_integ1)")

    parser.add_argument("--view", action="store_true", help="View attribution for specific PR")
    parser.add_argument("--view-all", action="store_true", help="View all PR attributions")

    args = parser.parse_args()

    try:
        manager = MultiEnvStatusManager()
    except Exception as e:
        print(f"Error: Failed to initialize status manager: {e}")
        return 1

    # View all attributions
    if args.view_all:
        print(manager.format_pr_attribution_report())
        return 0

    # View specific PR
    if args.view and args.pr:
        attr = manager.get_pr_attribution(args.pr)
        if attr:
            print(f"\nPR #{attr['pr_id']}: {attr['pr_title']}")
            print(f"Branch: {attr['pr_branch']}")
            print(f"Created by: {attr['created_by']}")
            print(f"Status: {attr['status']}")
            print("\nProvider Attribution:")

            if attr["review_provider"]:
                review_info = f"{attr['review_provider']} ({attr['review_session']})"
                print(f"  Review: {review_info}")
            if attr["implementation_provider"]:
                impl_info = f"{attr['implementation_provider']} ({attr['implementation_session']})"
                print(f"  Implementation: {impl_info}")
            if attr["integration_provider"]:
                integ_info = f"{attr['integration_provider']} ({attr['integration_session']})"
                print(f"  Integration: {integ_info}")

            print(f"Last updated: {attr['last_updated']}")
        else:
            print(f"PR #{args.pr} not found")
        return 0

    # Record or update PR attribution
    if args.pr:
        try:
            manager.record_pr_attribution(
                pr_id=args.pr,
                pr_title=args.title or f"PR #{args.pr}",
                pr_branch=args.branch or "unknown",
                created_by=args.created_by,
                review_provider=args.review_provider,
                implementation_provider=args.impl_provider,
                integration_provider=args.integ_provider,
                review_session=args.review_session,
                implementation_session=args.impl_session,
                integration_session=args.integ_session,
            )

            print(f"✓ PR #{args.pr} attribution recorded/updated")

            # Show what was recorded
            attr = manager.get_pr_attribution(args.pr)
            print(f"\nPR #{attr['pr_id']}: {attr['pr_title']}")
            print(f"Branch: {attr['pr_branch']}")

            if attr["review_provider"]:
                print(f"📝 Review: {attr['review_provider']} ({attr['review_session']})")
            if attr["implementation_provider"]:
                impl_provider = attr["implementation_provider"]
                impl_session = attr["implementation_session"]
                print(f"⚙️  Implementation: {impl_provider} ({impl_session})")
            if attr["integration_provider"]:
                integ_provider = attr["integration_provider"]
                integ_session = attr["integration_session"]
                print(f"🧪 Integration: {integ_provider} ({integ_session})")

            return 0
        except Exception as e:
            print(f"Error recording PR attribution: {e}")
            return 1

    # If no action specified, show usage
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
