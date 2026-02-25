#!/usr/bin/env python3
"""
Deployment Worker - Handles deployments automatically

Responsibilities:
- Monitor for completed features on dev branch
- Run tests automatically
- Tag releases
- Deploy to QA
- Deploy to production (with approval)
- Report deployment status

Development sessions should NOT handle deployment - this worker does it all.
"""

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from workers.session_state_manager import SessionStateManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DeploymentWorker")

BASE_DIR = Path(__file__).parent.parent
STATE_FILE = Path("/tmp/deployment_worker_state.json")
LOG_FILE = BASE_DIR / "logs" / "deployment_worker.log"


class DeploymentWorker:
    """Automated deployment worker."""

    def __init__(self):
        self.state = self.load_state()
        self.session_name = "deployment_worker"
        self.state_manager = SessionStateManager(self.session_name)
        self.state_manager.set_tool_info("deployment_worker", "automated")
        self.state_manager.set_status("idle")
        self.ensure_log_dir()

    def ensure_log_dir(self):
        """Ensure log directory exists."""
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _track_operation(self, operation: str, details: Dict = None) -> None:
        """Track deployment operation in state manager.

        Args:
            operation: Operation name (e.g., "check_commits", "run_tests")
            details: Optional dict of metadata to set
        """
        self.state_manager.set_task(f"Deployment: {operation}")
        self.state_manager.set_status("working")
        if details:
            for key, value in details.items():
                self.state_manager.set_metadata(key, value)

    def load_state(self) -> Dict:
        """Load persistent state."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

        return {
            "last_checked": None,
            "last_deployed_commit": None,
            "deployments": [],
            "total_deployments": 0,
            "failed_deployments": 0,
        }

    def save_state(self):
        """Save state to file."""
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def check_for_new_commits(self) -> List[Dict]:
        """Check dev branch for new commits since last deployment."""
        self._track_operation("check_commits")
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
            )
            current_branch = result.stdout.strip()

            # Switch to dev if needed
            if current_branch != "dev":
                subprocess.run(["git", "checkout", "dev"], cwd=BASE_DIR, capture_output=True)

            # Pull latest
            subprocess.run(["git", "pull"], cwd=BASE_DIR, capture_output=True)

            # Get commits since last deployment
            last_commit = self.state.get("last_deployed_commit")

            if last_commit:
                cmd = ["git", "log", f"{last_commit}..HEAD", "--oneline"]
            else:
                cmd = ["git", "log", "-5", "--oneline"]

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)

            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(" ", 1)
                    commits.append(
                        {"hash": parts[0], "message": parts[1] if len(parts) > 1 else ""}
                    )

            self.state_manager.set_metadata("commits_checked", len(commits))
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return commits

        except Exception as e:
            logger.error(f"Error checking commits: {e}")
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return []

    def run_tests(self) -> Dict:
        """Run automated tests."""
        self._track_operation("run_tests")
        logger.info("Running tests...")

        try:
            # Run pytest
            result = subprocess.run(
                ["python3", "-m", "pytest", "-q"],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=300,
            )

            success = result.returncode == 0
            self.state_manager.set_metadata("tests_passed", success)
            self.state_manager.set_metadata("test_exit_code", result.returncode)
            if not success:
                self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")

            return {
                "success": success,
                "output": result.stdout,
                "errors": result.stderr,
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            self.state_manager.increment_errors()
            self.state_manager.set_metadata("tests_passed", False)
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return {
                "success": False,
                "output": "",
                "errors": "Tests timed out after 5 minutes",
                "exit_code": -1,
            }
        except Exception as e:
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return {"success": False, "output": "", "errors": str(e), "exit_code": -1}

    def tag_release(self, version: Optional[str] = None) -> str:
        """Create a git tag for the release."""
        self._track_operation("tag_release")
        try:
            if not version:
                # Auto-generate version from last tag
                result = subprocess.run(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    capture_output=True,
                    text=True,
                    cwd=BASE_DIR,
                )

                last_tag = result.stdout.strip()
                if last_tag:
                    # Increment patch version
                    parts = last_tag.lstrip("v").split(".")
                    parts[-1] = str(int(parts[-1]) + 1)
                    version = "v" + ".".join(parts)
                else:
                    version = "v1.0.0"

            # Create tag
            subprocess.run(
                ["git", "tag", "-a", version, "-m", f"Release {version}"], cwd=BASE_DIR, check=True
            )

            logger.info(f"Created tag: {version}")
            self.state_manager.set_metadata("last_release_version", version)
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return version

        except Exception as e:
            logger.error(f"Error creating tag: {e}")
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return None

    def deploy_to_qa(self, version: str) -> Dict:
        """Deploy to QA environment."""
        self._track_operation("deploy_qa", {"version": version, "environment": "qa"})
        logger.info(f"Deploying {version} to QA...")

        try:
            # Use deploy script
            deploy_script = BASE_DIR / "deploy.sh"

            if deploy_script.exists():
                result = subprocess.run(
                    [str(deploy_script), "qa", version],
                    capture_output=True,
                    text=True,
                    cwd=BASE_DIR,
                    timeout=600,
                )

                success = result.returncode == 0
                if success:
                    self.state_manager.set_metadata("qa_deployment_success", True)
                else:
                    self.state_manager.increment_errors()
                    self.state_manager.set_metadata("qa_deployment_success", False)

                self.state_manager.clear_task()
                self.state_manager.set_status("idle")

                return {
                    "success": success,
                    "version": version,
                    "environment": "qa",
                    "output": result.stdout,
                    "errors": result.stderr,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                logger.warning("deploy.sh not found, skipping QA deployment")
                self.state_manager.increment_errors()
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
                return {
                    "success": False,
                    "version": version,
                    "environment": "qa",
                    "output": "",
                    "errors": "deploy.sh not found",
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Error deploying to QA: {e}")
            self.state_manager.increment_errors()
            self.state_manager.clear_task()
            self.state_manager.set_status("idle")
            return {
                "success": False,
                "version": version,
                "environment": "qa",
                "output": "",
                "errors": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def notify_deployment(self, deployment: Dict):
        """Send deployment notification (Slack, email, etc)."""
        # Placeholder for notifications
        status = "✅ SUCCESS" if deployment["success"] else "❌ FAILED"

        message = f"""
        {status} Deployment to {deployment['environment'].upper()}
        Version: {deployment.get('version', 'unknown')}
        Timestamp: {deployment['timestamp']}
        """

        logger.info(message)

        # TODO: Add Slack notification
        # TODO: Add email notification

    def auto_deploy_cycle(self):
        """Main deployment cycle - check, test, deploy."""
        logger.info("Starting deployment cycle...")

        # 1. Check for new commits
        new_commits = self.check_for_new_commits()

        if not new_commits:
            logger.info("No new commits to deploy")
            return

        logger.info(f"Found {len(new_commits)} new commits")

        # 2. Run tests
        test_results = self.run_tests()

        if not test_results["success"]:
            logger.error("Tests failed, aborting deployment")
            logger.error(f"Test errors: {test_results['errors']}")
            self.state["failed_deployments"] += 1
            self.save_state()
            return

        logger.info("✅ Tests passed")

        # 3. Tag release
        version = self.tag_release()

        if not version:
            logger.error("Failed to create tag, aborting deployment")
            return

        # 4. Deploy to QA
        qa_deployment = self.deploy_to_qa(version)

        # 5. Update state
        self.state["last_checked"] = datetime.now().isoformat()
        self.state["last_deployed_commit"] = new_commits[0]["hash"]
        self.state["deployments"].append(qa_deployment)
        self.state["total_deployments"] += 1

        if not qa_deployment["success"]:
            self.state["failed_deployments"] += 1

        self.save_state()

        # 6. Notify
        self.notify_deployment(qa_deployment)

        logger.info(f"Deployment cycle complete: {version}")

    def run_daemon(self, check_interval: int = 300):
        """Run as background daemon - check every N seconds."""
        logger.info(f"Deployment worker starting (check interval: {check_interval}s)")

        try:
            while True:
                self.auto_deploy_cycle()
                time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Deployment worker shutting down...")
            self.save_state()

    def get_status(self) -> Dict:
        """Get deployment worker status."""
        return {
            "worker": "deployment_worker",
            "last_checked": self.state.get("last_checked"),
            "last_deployed_commit": self.state.get("last_deployed_commit"),
            "total_deployments": self.state.get("total_deployments", 0),
            "failed_deployments": self.state.get("failed_deployments", 0),
            "success_rate": self._calculate_success_rate(),
            "recent_deployments": self.state.get("deployments", [])[-5:],
        }

    def _calculate_success_rate(self) -> float:
        """Calculate deployment success rate."""
        total = self.state.get("total_deployments", 0)
        if total == 0:
            return 0.0

        failed = self.state.get("failed_deployments", 0)
        return round((total - failed) / total * 100, 2)


def main():
    """CLI interface."""
    import sys

    worker = DeploymentWorker()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--daemon":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            worker.run_daemon(check_interval=interval)

        elif command == "--run-once":
            worker.auto_deploy_cycle()

        elif command == "--status":
            status = worker.get_status()
            print(json.dumps(status, indent=2))

        elif command == "--test":
            results = worker.run_tests()
            print(json.dumps(results, indent=2))

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("Deployment Worker")
        print("\nUsage:")
        print("  python3 deployment_worker.py --daemon [interval_seconds]")
        print("  python3 deployment_worker.py --run-once")
        print("  python3 deployment_worker.py --status")
        print("  python3 deployment_worker.py --test")


if __name__ == "__main__":
    main()
