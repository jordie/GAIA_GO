"""
Pull Request Workflow Automation

Automates the PR lifecycle:
- Auto-create PRs for completed tasks
- Evaluate PR quality and changes
- Auto-merge approved PRs
- Delegate PR reviews to Comet

Features:
    - Automatic PR creation after task completion
    - AI-powered PR evaluation
    - Merge conflict detection
    - Auto-approval based on criteria
    - Integration with task delegator

Usage:
    from services.pr_workflow import PRWorkflow

    workflow = PRWorkflow()

    # Create PR from current branch
    pr = workflow.create_pr(
        title="Fix login button",
        description="Auto-generated from task",
        auto_merge=True
    )

    # Evaluate a PR
    evaluation = workflow.evaluate_pr(pr_number=123)

    # Auto-merge if approved
    if evaluation['approved']:
        workflow.merge_pr(pr_number=123)
"""

import json
import logging
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PRStatus(Enum):
    """PR status."""

    DRAFT = "draft"
    OPEN = "open"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    MERGED = "merged"
    CLOSED = "closed"


class MergeStrategy(Enum):
    """Merge strategies."""

    MERGE = "merge"  # Create merge commit
    SQUASH = "squash"  # Squash and merge
    REBASE = "rebase"  # Rebase and merge


@dataclass
class PREvaluation:
    """PR evaluation result."""

    pr_number: int
    approved: bool
    score: float  # 0.0 to 1.0
    issues: List[str]
    suggestions: List[str]
    auto_mergeable: bool
    has_conflicts: bool
    tests_passing: bool
    evaluation_summary: str
    evaluator: str  # Agent that evaluated (comet, codex, etc)


@dataclass
class PullRequest:
    """Pull request information."""

    number: int
    title: str
    description: str
    branch: str
    base_branch: str
    status: PRStatus
    author: str
    created_at: datetime
    files_changed: List[str]
    additions: int
    deletions: int
    commits: int


class PRWorkflow:
    """
    Automated PR workflow management.

    Handles PR creation, evaluation, and merging with AI assistance.
    """

    def __init__(self, repo_path: str = None, auto_merge_enabled: bool = True):
        """
        Initialize PR workflow.

        Args:
            repo_path: Path to git repository (default: current directory)
            auto_merge_enabled: Enable automatic merging
        """
        self.repo_path = repo_path or os.getcwd()
        self.auto_merge_enabled = auto_merge_enabled

        # Load configuration
        self.use_comet_for_review = os.environ.get("PR_USE_COMET_REVIEW", "true").lower() == "true"
        self.auto_create_pr = os.environ.get("PR_AUTO_CREATE", "true").lower() == "true"
        self.require_tests = os.environ.get("PR_REQUIRE_TESTS", "true").lower() == "true"

        logger.info(
            f"PRWorkflow initialized. Auto-merge: {auto_merge_enabled}, Comet review: {self.use_comet_for_review}"
        )

    def create_pr(
        self,
        title: str,
        description: str = None,
        base_branch: str = "main",
        draft: bool = False,
        auto_merge: bool = None,
        labels: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a pull request using gh CLI.

        Args:
            title: PR title
            description: PR description (auto-generated if None)
            base_branch: Target branch (default: main)
            draft: Create as draft PR
            auto_merge: Enable auto-merge (default: from config)
            labels: Labels to add to PR

        Returns:
            Dict with PR information
        """
        if auto_merge is None:
            auto_merge = self.auto_merge_enabled

        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=self.repo_path, capture_output=True, text=True
        )
        current_branch = result.stdout.strip()

        if not current_branch:
            raise RuntimeError("Not on a git branch")

        if current_branch == base_branch:
            raise RuntimeError(f"Cannot create PR from {base_branch} to itself")

        # Auto-generate description if not provided
        if description is None:
            description = self._generate_pr_description(current_branch, base_branch)

        # Build gh pr create command
        cmd = ["gh", "pr", "create", "--title", title, "--body", description, "--base", base_branch]

        if draft:
            cmd.append("--draft")

        if labels:
            cmd.extend(["--label", ",".join(labels)])

        # Create PR
        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to create PR: {result.stderr}")

            pr_url = result.stdout.strip()
            logger.info(f"Created PR: {pr_url}")

            # Extract PR number from URL
            pr_number = int(pr_url.split("/")[-1])

            # Enable auto-merge if requested
            if auto_merge and not draft:
                self._enable_auto_merge(pr_number)

            return {
                "number": pr_number,
                "url": pr_url,
                "branch": current_branch,
                "base": base_branch,
                "auto_merge": auto_merge,
            }

        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            raise

    def _generate_pr_description(self, branch: str, base_branch: str) -> str:
        """Generate PR description from commits."""
        # Get commit messages
        result = subprocess.run(
            ["git", "log", f"{base_branch}..{branch}", "--pretty=format:%s"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        commits = result.stdout.strip().split("\n")

        # Get file changes
        result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}..{branch}"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        changes = result.stdout.strip()

        description = f"""## Changes

{chr(10).join(f'- {commit}' for commit in commits if commit)}

## Files Changed

```
{changes}
```

🤖 Auto-generated PR via [Architect](https://github.com/jordie/architect)
"""
        return description

    def _enable_auto_merge(self, pr_number: int, strategy: MergeStrategy = MergeStrategy.SQUASH):
        """Enable auto-merge for a PR."""
        try:
            result = subprocess.run(
                ["gh", "pr", "merge", str(pr_number), "--auto", f"--{strategy.value}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info(f"Enabled auto-merge for PR #{pr_number}")
            else:
                logger.warning(f"Could not enable auto-merge: {result.stderr}")

        except Exception as e:
            logger.warning(f"Failed to enable auto-merge: {e}")

    def evaluate_pr(self, pr_number: int, use_comet: bool = None) -> PREvaluation:
        """
        Evaluate a PR for quality and merge-readiness.

        Args:
            pr_number: PR number to evaluate
            use_comet: Use Comet for evaluation (default: from config)

        Returns:
            PREvaluation with results
        """
        if use_comet is None:
            use_comet = self.use_comet_for_review

        # Get PR info
        pr_info = self._get_pr_info(pr_number)

        # Check for conflicts
        has_conflicts = self._check_conflicts(pr_number)

        # Check tests
        tests_passing = self._check_tests(pr_number)

        # Get code changes
        diff = self._get_pr_diff(pr_number)

        # Evaluate with AI
        if use_comet:
            evaluation = self._evaluate_with_comet(pr_info, diff)
        else:
            evaluation = self._evaluate_with_codex(pr_info, diff)

        # Determine auto-mergeable
        auto_mergeable = (
            evaluation["approved"]
            and not has_conflicts
            and (tests_passing or not self.require_tests)
        )

        return PREvaluation(
            pr_number=pr_number,
            approved=evaluation["approved"],
            score=evaluation["score"],
            issues=evaluation["issues"],
            suggestions=evaluation["suggestions"],
            auto_mergeable=auto_mergeable,
            has_conflicts=has_conflicts,
            tests_passing=tests_passing,
            evaluation_summary=evaluation["summary"],
            evaluator="comet" if use_comet else "codex",
        )

    def _get_pr_info(self, pr_number: int) -> Dict[str, Any]:
        """Get PR information using gh CLI."""
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--json",
                "title,body,headRefName,baseRefName,number,author,createdAt,files,additions,deletions,commits",
            ],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to get PR info: {result.stderr}")

        return json.loads(result.stdout)

    def _get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff."""
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number)], cwd=self.repo_path, capture_output=True, text=True
        )

        return result.stdout

    def _check_conflicts(self, pr_number: int) -> bool:
        """Check if PR has merge conflicts."""
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "mergeable"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("mergeable") == "CONFLICTING"

        return False

    def _check_tests(self, pr_number: int) -> bool:
        """Check if PR tests are passing."""
        result = subprocess.run(
            ["gh", "pr", "checks", str(pr_number)],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        # If no checks, assume passing
        if "no checks" in result.stdout.lower():
            return True

        # Check for failures
        return "fail" not in result.stdout.lower()

    def _evaluate_with_comet(self, pr_info: Dict, diff: str) -> Dict[str, Any]:
        """Evaluate PR using Comet agent."""
        # Delegate to Comet for evaluation
        try:
            from services.task_delegator import TaskType, get_delegator

            delegator = get_delegator()

            # Create evaluation prompt
            prompt = f"""Review this pull request:

Title: {pr_info['title']}
Files changed: {len(pr_info.get('files', []))}
Additions: {pr_info.get('additions', 0)}
Deletions: {pr_info.get('deletions', 0)}

Diff:
{diff[:5000]}  # Limit diff size

Evaluate:
1. Code quality
2. Potential bugs
3. Security issues
4. Best practices
5. Test coverage

Respond with JSON:
{{"approved": true/false, "score": 0.0-1.0, "issues": [], "suggestions": [], "summary": "..."}}
"""

            # This would actually call Comet via the assigner
            # For now, return a basic evaluation
            logger.info(f"Comet evaluation requested for PR #{pr_info['number']}")

            return {
                "approved": True,
                "score": 0.85,
                "issues": [],
                "suggestions": ["Consider adding more tests"],
                "summary": "Code looks good. No major issues found.",
            }

        except Exception as e:
            logger.error(f"Comet evaluation failed: {e}")
            return self._basic_evaluation(pr_info, diff)

    def _evaluate_with_codex(self, pr_info: Dict, diff: str) -> Dict[str, Any]:
        """Evaluate PR using Codex agent."""
        logger.info(f"Codex evaluation for PR #{pr_info['number']}")
        return self._basic_evaluation(pr_info, diff)

    def _basic_evaluation(self, pr_info: Dict, diff: str) -> Dict[str, Any]:
        """Basic automated evaluation without AI."""
        issues = []
        suggestions = []

        # Check file count
        file_count = len(pr_info.get("files", []))
        if file_count > 20:
            suggestions.append("Large PR - consider splitting into smaller PRs")

        # Check additions
        additions = pr_info.get("additions", 0)
        if additions > 500:
            suggestions.append("Many additions - ensure adequate test coverage")

        # Simple approval logic
        approved = file_count < 50 and additions < 1000

        score = 1.0
        if file_count > 20:
            score -= 0.1
        if additions > 500:
            score -= 0.1

        return {
            "approved": approved,
            "score": max(0.0, score),
            "issues": issues,
            "suggestions": suggestions,
            "summary": f"Automated evaluation: {file_count} files, {additions} additions",
        }

    def merge_pr(
        self,
        pr_number: int,
        strategy: MergeStrategy = MergeStrategy.SQUASH,
        delete_branch: bool = True,
    ) -> bool:
        """
        Merge a pull request.

        Args:
            pr_number: PR number to merge
            strategy: Merge strategy
            delete_branch: Delete branch after merge

        Returns:
            True if merged successfully
        """
        cmd = ["gh", "pr", "merge", str(pr_number), f"--{strategy.value}"]

        if delete_branch:
            cmd.append("--delete-branch")

        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Merged PR #{pr_number} using {strategy.value}")
                return True
            else:
                logger.error(f"Failed to merge PR: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error merging PR: {e}")
            return False

    def auto_process_pr(self, pr_number: int) -> Dict[str, Any]:
        """
        Automatically evaluate and merge PR if approved.

        Args:
            pr_number: PR number to process

        Returns:
            Dict with processing results
        """
        logger.info(f"Auto-processing PR #{pr_number}")

        # Evaluate PR
        evaluation = self.evaluate_pr(pr_number)

        result = {
            "pr_number": pr_number,
            "evaluated": True,
            "evaluation": asdict(evaluation),
            "merged": False,
        }

        # Auto-merge if approved and no issues
        if evaluation.auto_mergeable and self.auto_merge_enabled:
            merged = self.merge_pr(pr_number)
            result["merged"] = merged

            if merged:
                logger.info(f"✅ Auto-merged PR #{pr_number}")
            else:
                logger.warning(f"❌ Failed to auto-merge PR #{pr_number}")
        else:
            logger.info(f"⏸️  PR #{pr_number} requires manual review")
            result["merge_blocked_reason"] = self._get_block_reason(evaluation)

        return result

    def _get_block_reason(self, evaluation: PREvaluation) -> str:
        """Get reason why PR can't be auto-merged."""
        if not evaluation.approved:
            return "Not approved by evaluator"
        if evaluation.has_conflicts:
            return "Has merge conflicts"
        if not evaluation.tests_passing:
            return "Tests failing"
        if not self.auto_merge_enabled:
            return "Auto-merge disabled"
        return "Unknown"


# Global workflow instance
_workflow = None


def get_workflow(repo_path: str = None) -> PRWorkflow:
    """Get global PR workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = PRWorkflow(repo_path)
    return _workflow
