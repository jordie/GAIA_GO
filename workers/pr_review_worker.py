#!/usr/bin/env python3
"""
PR Review Worker - Automated pull request reviews and merging

Responsibilities:
- Monitor for open pull requests
- Run automated code review
- Check tests pass
- Auto-merge if criteria met
- Request changes if issues found

Development sessions should NOT review/merge PRs - this worker does it.
"""

import json
import logging
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from workers.session_state_manager import SessionStateManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PRReviewWorker")

BASE_DIR = Path(__file__).parent.parent
STATE_FILE = Path("/tmp/pr_review_worker_state.json")


class PRReviewWorker:
    """Automated PR review and merge worker."""

    def __init__(self):
        self.state = self.load_state()
        self.session_name = "pr_review_worker"
        self.state_manager = SessionStateManager(self.session_name)
        self.state_manager.set_tool_info("pr_review_worker", "automated")
        self.state_manager.set_status("idle")

    def load_state(self) -> Dict:
        """Load persistent state."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

        return {"prs_reviewed": 0, "prs_merged": 0, "prs_rejected": 0, "last_check": None}

    def save_state(self):
        """Save state to file."""
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def _sync_counters(self) -> None:
        """Sync PR counters to state manager."""
        self.state_manager.set_metadata("prs_reviewed", self.state.get("prs_reviewed", 0))
        self.state_manager.set_metadata("prs_merged", self.state.get("prs_merged", 0))
        self.state_manager.set_metadata("prs_rejected", self.state.get("prs_rejected", 0))

    def get_open_prs(self) -> List[Dict]:
        """Get list of open pull requests using gh CLI."""
        self.state_manager.set_task("Fetching open pull requests")
        self.state_manager.set_status("working")
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--json", "number,title,headRefName,author,createdAt,isDraft"],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=30,
            )

            if result.returncode == 0:
                prs = json.loads(result.stdout)
                self.state_manager.set_metadata("open_pr_count", len(prs))
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
                return prs
            else:
                logger.error(f"Failed to get PRs: {result.stderr}")
                self.state_manager.increment_errors()
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
                return []

        except Exception as e:
            logger.error(f"Error getting PRs: {e}")
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return []

    def get_pr_details(self, pr_number: int) -> Optional[Dict]:
        """Get detailed info about a PR."""
        self.state_manager.set_task(f"Fetching PR #{pr_number} details")
        self.state_manager.set_status("working")
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "--json",
                    "number,title,body,headRefName,baseRefName,state,mergeable,reviews,commits",
                ],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=30,
            )

            if result.returncode == 0:
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
                return json.loads(result.stdout)
            else:
                self.state_manager.increment_errors()
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
                return None

        except Exception as e:
            logger.error(f"Error getting PR details: {e}")
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return None

    def check_pr_tests(self, pr_number: int) -> Dict:
        """Check if PR tests are passing."""
        try:
            # Get PR checks status
            result = subprocess.run(
                ["gh", "pr", "checks", str(pr_number), "--json", "state,conclusion"],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=30,
            )

            if result.returncode == 0:
                checks = json.loads(result.stdout)

                if not checks:
                    # No checks configured, run tests manually
                    return self.run_pr_tests(pr_number)

                all_passed = all(check.get("conclusion") == "success" for check in checks)

                return {"passing": all_passed, "checks": checks}
            else:
                # No CI configured, run tests manually
                return self.run_pr_tests(pr_number)

        except Exception as e:
            logger.error(f"Error checking PR tests: {e}")
            return {"passing": False, "error": str(e)}

    def run_pr_tests(self, pr_number: int) -> Dict:
        """Manually run tests for a PR."""
        try:
            # Checkout PR branch
            result = subprocess.run(
                ["gh", "pr", "checkout", str(pr_number)],
                capture_output=True,
                cwd=BASE_DIR,
                timeout=30,
            )

            if result.returncode != 0:
                return {"passing": False, "error": "Could not checkout PR"}

            # Run tests
            test_result = subprocess.run(
                ["python3", "-m", "pytest", "-q"],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=300,
            )

            # Return to dev
            subprocess.run(["git", "checkout", "dev"], cwd=BASE_DIR, capture_output=True)

            return {
                "passing": test_result.returncode == 0,
                "output": test_result.stdout,
                "errors": test_result.stderr,
            }

        except Exception as e:
            logger.error(f"Error running PR tests: {e}")
            return {"passing": False, "error": str(e)}

    def review_pr_code(self, pr_number: int) -> Dict:
        """Automated code review - check for common issues."""
        self.state_manager.set_task(f"Reviewing PR #{pr_number}")
        self.state_manager.set_status("working")
        try:
            # Get diff
            result = subprocess.run(
                ["gh", "pr", "diff", str(pr_number)],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=30,
            )

            diff = result.stdout

            issues = []

            # Check for common problems
            if "print(" in diff and "+" in diff:
                issues.append("Contains print statements (consider using logging)")

            if "TODO" in diff or "FIXME" in diff:
                issues.append("Contains TODO/FIXME comments")

            if re.search(r'\+.*password.*=.*["\']', diff, re.IGNORECASE):
                issues.append("⚠️  WARNING: Possible hardcoded password")

            if re.search(r'\+.*api[_-]?key.*=.*["\']', diff, re.IGNORECASE):
                issues.append("⚠️  WARNING: Possible hardcoded API key")

            # Check for large files
            lines_added = len([line for line in diff.split("\n") if line.startswith("+")])
            if lines_added > 1000:
                issues.append(f"Large PR: {lines_added} lines added (consider splitting)")

            self.state_manager.set_metadata("review_issues_found", len(issues))
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")

            return {
                "approved": len([i for i in issues if "WARNING" in i]) == 0,
                "issues": issues,
                "lines_changed": lines_added,
            }

        except Exception as e:
            logger.error(f"Error reviewing PR: {e}")
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return {"approved": False, "issues": [str(e)]}

    def auto_review_pr(self, pr_number: int) -> Dict:
        """Complete automated review of a PR."""
        logger.info(f"Reviewing PR #{pr_number}...")

        # Get PR details
        pr = self.get_pr_details(pr_number)
        if not pr:
            return {"approved": False, "reason": "Could not get PR details"}

        # Skip draft PRs
        if pr.get("isDraft"):
            return {"approved": False, "reason": "PR is draft"}

        # Check if mergeable
        if pr.get("mergeable") != "MERGEABLE":
            return {"approved": False, "reason": "PR has merge conflicts"}

        # Check tests
        tests = self.check_pr_tests(pr_number)
        if not tests.get("passing"):
            return {
                "approved": False,
                "reason": "Tests failing",
                "test_output": tests.get("errors", ""),
            }

        # Code review
        code_review = self.review_pr_code(pr_number)
        if not code_review.get("approved"):
            return {
                "approved": False,
                "reason": "Code review found issues",
                "issues": code_review.get("issues", []),
            }

        # All checks passed
        return {
            "approved": True,
            "tests_passing": True,
            "code_review_passed": True,
            "issues": code_review.get("issues", []),
        }

    def merge_pr(self, pr_number: int, method: str = "squash") -> Dict:
        """Merge an approved PR."""
        self.state_manager.set_task(f"Merging PR #{pr_number}")
        self.state_manager.set_status("working")
        logger.info(f"Merging PR #{pr_number}...")

        try:
            # Merge using gh CLI
            result = subprocess.run(
                ["gh", "pr", "merge", str(pr_number), f"--{method}", "--auto"],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=60,
            )

            success = result.returncode == 0
            if success:
                self.state.setdefault("prs_merged", 0)
                self.state["prs_merged"] += 1
                self.save_state()
                self._sync_counters()
            else:
                self.state_manager.increment_errors()

            self.state_manager.clear_task()
            self.state_manager.set_status("idle")

            return {"success": success, "output": result.stdout, "errors": result.stderr}

        except Exception as e:
            logger.error(f"Error merging PR: {e}")
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return {"success": False, "error": str(e)}

    def comment_on_pr(self, pr_number: int, comment: str):
        """Add a comment to the PR."""
        try:
            subprocess.run(
                ["gh", "pr", "comment", str(pr_number), "--body", comment], cwd=BASE_DIR, timeout=30
            )
        except Exception as e:
            logger.error(f"Error commenting on PR: {e}")

    def process_pr(self, pr_number: int) -> Dict:
        """Process a single PR - review and potentially merge."""
        logger.info(f"Processing PR #{pr_number}")

        # Review
        review = self.auto_review_pr(pr_number)

        self.state["prs_reviewed"] += 1
        self._sync_counters()

        if review["approved"]:
            logger.info(f"✅ PR #{pr_number} approved")

            # Merge
            merge_result = self.merge_pr(pr_number)

            if merge_result["success"]:
                logger.info(f"✅ PR #{pr_number} merged")
                self.state["prs_merged"] += 1
                self.save_state()
                self._sync_counters()

                # Comment
                self.comment_on_pr(
                    pr_number,
                    "✅ Automated review passed. PR merged automatically.\n\n"
                    "- Tests: ✅ Passing\n"
                    "- Code review: ✅ Approved\n"
                    "- Merge conflicts: ✅ None",
                )

                return {"status": "merged", "pr": pr_number}
            else:
                logger.error(f"❌ Failed to merge PR #{pr_number}")
                return {
                    "status": "merge_failed",
                    "pr": pr_number,
                    "error": merge_result.get("errors"),
                }
        else:
            logger.warning(f"⚠️  PR #{pr_number} not approved: {review.get('reason')}")
            self.state["prs_rejected"] += 1
            self.save_state()
            self._sync_counters()

            # Comment with issues
            issues_text = "\n".join(f"- {issue}" for issue in review.get("issues", []))
            self.comment_on_pr(
                pr_number,
                f"⚠️ Automated review found issues:\n\n"
                f"**Reason**: {review.get('reason')}\n\n"
                f"**Issues found**:\n{issues_text}\n\n"
                f"Please address these issues before merging.",
            )

            return {"status": "rejected", "pr": pr_number, "reason": review.get("reason")}

        self.save_state()

    def auto_review_cycle(self):
        """Main review cycle - check and process PRs."""
        logger.info("Starting PR review cycle...")

        # Get open PRs
        prs = self.get_open_prs()

        if not prs:
            logger.info("No open PRs to review")
            return

        logger.info(f"Found {len(prs)} open PRs")

        # Process each PR
        for pr in prs:
            if not pr.get("isDraft"):
                self.process_pr(pr["number"])

        self.state["last_check"] = datetime.now().isoformat()
        self.save_state()

    def run_daemon(self, check_interval: int = 300):
        """Run as background daemon."""
        logger.info(f"PR Review worker starting (check interval: {check_interval}s)")

        try:
            while True:
                self.auto_review_cycle()
                time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("PR Review worker shutting down...")
            self.save_state()

    def get_status(self) -> Dict:
        """Get worker status."""
        return {
            "worker": "pr_review_worker",
            "prs_reviewed": self.state.get("prs_reviewed", 0),
            "prs_merged": self.state.get("prs_merged", 0),
            "prs_rejected": self.state.get("prs_rejected", 0),
            "last_check": self.state.get("last_check"),
            "approval_rate": self._calculate_approval_rate(),
        }

    def _calculate_approval_rate(self) -> float:
        """Calculate PR approval rate."""
        total = self.state.get("prs_reviewed", 0)
        if total == 0:
            return 0.0

        merged = self.state.get("prs_merged", 0)
        return round(merged / total * 100, 2)


def main():
    """CLI interface."""
    import sys

    worker = PRReviewWorker()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--daemon":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            worker.run_daemon(check_interval=interval)

        elif command == "--run-once":
            worker.auto_review_cycle()

        elif command == "--status":
            status = worker.get_status()
            print(json.dumps(status, indent=2))

        elif command == "--review":
            if len(sys.argv) < 3:
                print("Usage: --review <pr_number>")
                sys.exit(1)
            pr_number = int(sys.argv[2])
            result = worker.process_pr(pr_number)
            print(json.dumps(result, indent=2))

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("PR Review Worker")
        print("\nUsage:")
        print("  python3 pr_review_worker.py --daemon [interval_seconds]")
        print("  python3 pr_review_worker.py --run-once")
        print("  python3 pr_review_worker.py --status")
        print("  python3 pr_review_worker.py --review <pr_number>")


if __name__ == "__main__":
    main()
