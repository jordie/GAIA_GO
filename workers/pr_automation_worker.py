#!/usr/bin/env python3
"""
PR Automation Worker

Monitors completed tasks and automatically:
- Creates pull requests
- Evaluates PRs with Comet
- Auto-merges approved PRs

Usage:
    python3 pr_automation_worker.py                    # Run worker
    python3 pr_automation_worker.py --daemon           # Run as daemon
    python3 pr_automation_worker.py --create-pr "title" # Manual PR creation
    python3 pr_automation_worker.py --evaluate 123     # Evaluate PR #123
    python3 pr_automation_worker.py --merge 123        # Merge PR #123
    python3 pr_automation_worker.py --auto-process 123 # Evaluate and merge PR #123
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from services.pr_workflow import PREvaluation, PRWorkflow, get_workflow

# Worker configuration
PID_FILE = Path("/tmp/architect_pr_automation.pid")
LOG_FILE = Path("/tmp/architect_pr_automation.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("PRAutomation")


class PRAutomationWorker:
    """Worker that automates PR creation and merging."""

    def __init__(self, poll_interval: int = 60):
        self.poll_interval = poll_interval
        self.running = False
        self.workflow = get_workflow()

    def start(self):
        """Start the worker."""
        self.running = True
        logger.info("Starting PR Automation Worker")

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        try:
            while self.running:
                self._process_open_prs()
                time.sleep(self.poll_interval)

        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            logger.info("PR Automation Worker stopped")

    def stop(self):
        """Stop the worker."""
        self.running = False

    def _handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop()

    def _process_open_prs(self):
        """Process all open PRs."""
        logger.debug("Checking for open PRs...")

        try:
            import json
            import subprocess

            # Get open PRs
            result = subprocess.run(
                ["gh", "pr", "list", "--json", "number,title,headRefName"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning("Could not fetch PRs")
                return

            prs = json.loads(result.stdout)

            for pr in prs:
                pr_number = pr["number"]
                logger.info(f"Processing PR #{pr_number}: {pr['title']}")

                # Auto-evaluate and merge if ready
                result = self.workflow.auto_process_pr(pr_number)

                if result["merged"]:
                    logger.info(f"✅ Auto-merged PR #{pr_number}")
                else:
                    reason = result.get("merge_blocked_reason", "Unknown")
                    logger.info(f"⏸️  PR #{pr_number} not merged: {reason}")

        except Exception as e:
            logger.error(f"Error processing PRs: {e}")


def create_pr_cli(args):
    """CLI: Create a PR."""
    workflow = get_workflow()

    try:
        pr = workflow.create_pr(
            title=args.title,
            description=args.description,
            base_branch=args.base,
            draft=args.draft,
            auto_merge=not args.no_auto_merge,
        )

        print(f"✅ Created PR #{pr['number']}: {pr['url']}")

        if not args.draft and not args.no_auto_merge:
            print("   Auto-merge enabled - will merge when checks pass")

    except Exception as e:
        print(f"❌ Failed to create PR: {e}")
        sys.exit(1)


def evaluate_pr_cli(args):
    """CLI: Evaluate a PR."""
    workflow = get_workflow()

    try:
        print(f"Evaluating PR #{args.pr_number}...")

        evaluation = workflow.evaluate_pr(args.pr_number, use_comet=args.use_comet)

        print(f"\n{'='*60}")
        print(f"PR #{evaluation.pr_number} Evaluation")
        print(f"{'='*60}")
        print(f"Evaluator:       {evaluation.evaluator}")
        print(f"Approved:        {'✅ YES' if evaluation.approved else '❌ NO'}")
        print(f"Score:           {evaluation.score:.2%}")
        print(f"Auto-mergeable:  {'✅ YES' if evaluation.auto_mergeable else '❌ NO'}")
        print(f"Has conflicts:   {'❌ YES' if evaluation.has_conflicts else '✅ NO'}")
        print(f"Tests passing:   {'✅ YES' if evaluation.tests_passing else '❌ NO'}")

        if evaluation.issues:
            print(f"\n🔴 Issues:")
            for issue in evaluation.issues:
                print(f"   - {issue}")

        if evaluation.suggestions:
            print(f"\n💡 Suggestions:")
            for suggestion in evaluation.suggestions:
                print(f"   - {suggestion}")

        print(f"\n📝 Summary:")
        print(f"   {evaluation.evaluation_summary}")
        print()

    except Exception as e:
        print(f"❌ Failed to evaluate PR: {e}")
        sys.exit(1)


def merge_pr_cli(args):
    """CLI: Merge a PR."""
    workflow = get_workflow()

    try:
        print(f"Merging PR #{args.pr_number}...")

        from services.pr_workflow import MergeStrategy

        strategy = MergeStrategy(args.strategy)

        success = workflow.merge_pr(
            args.pr_number, strategy=strategy, delete_branch=not args.keep_branch
        )

        if success:
            print(f"✅ Successfully merged PR #{args.pr_number}")
        else:
            print(f"❌ Failed to merge PR #{args.pr_number}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error merging PR: {e}")
        sys.exit(1)


def auto_process_pr_cli(args):
    """CLI: Auto-evaluate and merge PR."""
    workflow = get_workflow()

    try:
        print(f"Auto-processing PR #{args.pr_number}...")

        result = workflow.auto_process_pr(args.pr_number)

        print(f"\n{'='*60}")
        print(f"PR #{result['pr_number']} Auto-Processing Results")
        print(f"{'='*60}")

        eval_data = result["evaluation"]
        print(f"Evaluated:       ✅ YES")
        print(f"Approved:        {'✅ YES' if eval_data['approved'] else '❌ NO'}")
        print(f"Merged:          {'✅ YES' if result['merged'] else '❌ NO'}")

        if not result["merged"]:
            reason = result.get("merge_blocked_reason", "Unknown")
            print(f"Block reason:    {reason}")

        print()

    except Exception as e:
        print(f"❌ Error processing PR: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="PR Automation Worker")

    # Worker mode
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")

    # PR operations
    parser.add_argument("--create-pr", metavar="TITLE", help="Create a new PR")
    parser.add_argument("--description", help="PR description")
    parser.add_argument("--base", default="main", help="Base branch (default: main)")
    parser.add_argument("--draft", action="store_true", help="Create as draft PR")
    parser.add_argument("--no-auto-merge", action="store_true", help="Disable auto-merge")

    parser.add_argument("--evaluate", type=int, metavar="PR#", help="Evaluate a PR")
    parser.add_argument("--use-comet", action="store_true", help="Use Comet for evaluation")

    parser.add_argument("--merge", type=int, metavar="PR#", help="Merge a PR")
    parser.add_argument(
        "--strategy",
        choices=["merge", "squash", "rebase"],
        default="squash",
        help="Merge strategy (default: squash)",
    )
    parser.add_argument("--keep-branch", action="store_true", help="Keep branch after merge")

    parser.add_argument(
        "--auto-process", type=int, metavar="PR#", help="Auto-evaluate and merge PR"
    )

    args = parser.parse_args()

    # Execute based on arguments
    if args.create_pr:
        args.title = args.create_pr
        create_pr_cli(args)

    elif args.evaluate:
        args.pr_number = args.evaluate
        evaluate_pr_cli(args)

    elif args.merge:
        args.pr_number = args.merge
        merge_pr_cli(args)

    elif args.auto_process:
        args.pr_number = args.auto_process
        auto_process_pr_cli(args)

    else:
        # Run worker
        worker = PRAutomationWorker()

        if args.daemon:
            # TODO: Implement daemon mode
            logger.error("Daemon mode not yet implemented")
            sys.exit(1)
        else:
            worker.start()


if __name__ == "__main__":
    main()
