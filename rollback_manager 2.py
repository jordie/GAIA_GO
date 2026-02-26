#!/usr/bin/env python3
"""
Automated Rollback Manager for Architect Dashboard

Provides automated rollback functionality when health checks fail after deployment.
Features:
- Pre-deployment snapshots (git commit + database backup)
- Post-deployment health monitoring
- Automatic rollback on consecutive health failures
- Manual rollback capability
- Rollback history tracking

Usage:
    from rollback_manager import RollbackManager

    manager = RollbackManager()

    # Before deployment
    snapshot_id = manager.create_snapshot("Deploying feature X")

    # After deployment, monitor health
    manager.start_health_monitoring(snapshot_id)

    # Or manually trigger rollback
    manager.rollback(snapshot_id)
"""

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "rollback_snapshots"
HISTORY_FILE = DATA_DIR / "rollback_history.json"
STATE_FILE = DATA_DIR / "rollback_state.json"
DB_FILE = DATA_DIR / "architect.db"

# Health check configuration
DEFAULT_HEALTH_URL = "http://localhost:8080/health"
HEALTH_CHECK_INTERVAL = 10  # seconds
CONSECUTIVE_FAILURES_THRESHOLD = 3
POST_DEPLOY_MONITORING_DURATION = 300  # 5 minutes
ROLLBACK_COOLDOWN = 600  # 10 minutes between rollbacks

# Setup logging
logger = logging.getLogger("rollback_manager")


class RollbackManager:
    """Manages automated rollback on health check failures."""

    def __init__(self, health_url: str = None, db_path: str = None):
        """Initialize the rollback manager.

        Args:
            health_url: URL for health check endpoint
            db_path: Path to the database file
        """
        self.health_url = health_url or DEFAULT_HEALTH_URL
        self.db_path = Path(db_path) if db_path else DB_FILE
        self.snapshots_dir = SNAPSHOTS_DIR
        self.history_file = HISTORY_FILE
        self.state_file = STATE_FILE

        # Monitoring state
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        self._current_snapshot_id = None
        self._failure_count = 0

        # Ensure directories exist
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load state
        self._load_state()

    def _load_state(self):
        """Load persistent state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    state = json.load(f)
                self._current_snapshot_id = state.get("current_snapshot_id")
                self._failure_count = state.get("failure_count", 0)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")

    def _save_state(self):
        """Save persistent state to file."""
        try:
            state = {
                "current_snapshot_id": self._current_snapshot_id,
                "failure_count": self._failure_count,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    def _get_git_info(self) -> Dict[str, str]:
        """Get current git commit information."""
        info = {}
        try:
            # Get current commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=BASE_DIR
            )
            if result.returncode == 0:
                info["commit_sha"] = result.stdout.strip()

            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
            )
            if result.returncode == 0:
                info["branch"] = result.stdout.strip()

            # Get commit message
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"], capture_output=True, text=True, cwd=BASE_DIR
            )
            if result.returncode == 0:
                info["commit_message"] = result.stdout.strip()[:200]

            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=BASE_DIR
            )
            info["has_uncommitted_changes"] = bool(result.stdout.strip())

        except Exception as e:
            logger.warning(f"Failed to get git info: {e}")

        return info

    def _backup_database(self, snapshot_id: str) -> Optional[str]:
        """Create a database backup for the snapshot.

        Returns:
            Path to backup file or None if failed
        """
        if not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}")
            return None

        backup_path = self.snapshots_dir / f"{snapshot_id}.db"

        try:
            # Use SQLite backup API for consistency
            src = sqlite3.connect(str(self.db_path))
            dst = sqlite3.connect(str(backup_path))
            src.backup(dst)
            src.close()
            dst.close()

            logger.info(f"Database backed up to: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            # Fallback to file copy
            try:
                shutil.copy2(self.db_path, backup_path)
                return str(backup_path)
            except Exception as e2:
                logger.error(f"Fallback backup also failed: {e2}")
                return None

    def _restore_database(self, backup_path: str) -> bool:
        """Restore database from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if successful, False otherwise
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        try:
            # Create pre-restore backup
            pre_restore = self.db_path.with_suffix(
                f".pre_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
            if self.db_path.exists():
                shutil.copy2(self.db_path, pre_restore)
                logger.info(f"Pre-rollback backup created: {pre_restore}")

            # Restore using SQLite backup API
            src = sqlite3.connect(str(backup_path))
            dst = sqlite3.connect(str(self.db_path))
            src.backup(dst)
            src.close()
            dst.close()

            logger.info(f"Database restored from: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    def _git_rollback(self, commit_sha: str) -> bool:
        """Rollback git to a specific commit.

        Args:
            commit_sha: Git commit SHA to rollback to

        Returns:
            True if successful, False otherwise
        """
        try:
            # First, stash any uncommitted changes
            subprocess.run(
                ["git", "stash", "push", "-m", "Auto-stash before rollback"],
                cwd=BASE_DIR,
                capture_output=True,
            )

            # Checkout the specific commit
            result = subprocess.run(
                ["git", "checkout", commit_sha], cwd=BASE_DIR, capture_output=True, text=True
            )

            if result.returncode != 0:
                logger.error(f"Git checkout failed: {result.stderr}")
                return False

            logger.info(f"Git rolled back to: {commit_sha}")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback git: {e}")
            return False

    def _check_health(self) -> Dict[str, Any]:
        """Perform a health check.

        Returns:
            Dict with health check results
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "healthy": False,
            "status": None,
            "response_time_ms": None,
            "error": None,
        }

        try:
            start = time.time()
            response = requests.get(self.health_url, timeout=10)
            result["response_time_ms"] = round((time.time() - start) * 1000, 2)
            result["status_code"] = response.status_code

            if response.status_code == 200:
                data = response.json()
                result["status"] = data.get("status", "unknown")
                result["healthy"] = data.get("status") in ["healthy", "ok"]
                result["details"] = data
            else:
                result["error"] = f"HTTP {response.status_code}"

        except requests.Timeout:
            result["error"] = "Health check timed out"
        except requests.ConnectionError:
            result["error"] = "Connection refused"
        except Exception as e:
            result["error"] = str(e)

        return result

    def _restart_service(self) -> bool:
        """Attempt to restart the service.

        Returns:
            True if restart command was issued successfully
        """
        try:
            deploy_script = BASE_DIR / "deploy.sh"
            if deploy_script.exists():
                # Stop then start
                subprocess.run([str(deploy_script), "stop"], cwd=BASE_DIR, capture_output=True)
                time.sleep(2)
                result = subprocess.run(
                    [str(deploy_script), "--daemon"], cwd=BASE_DIR, capture_output=True
                )
                return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
        return False

    def create_snapshot(self, description: str = None) -> str:
        """Create a pre-deployment snapshot.

        Args:
            description: Optional description for the snapshot

        Returns:
            Snapshot ID
        """
        snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        snapshot = {
            "id": snapshot_id,
            "created_at": datetime.now().isoformat(),
            "description": description,
            "git": self._get_git_info(),
            "database_backup": None,
            "status": "created",
        }

        # Backup database
        db_backup = self._backup_database(snapshot_id)
        snapshot["database_backup"] = db_backup

        # Save snapshot metadata
        metadata_path = self.snapshots_dir / f"{snapshot_id}.json"
        with open(metadata_path, "w") as f:
            json.dump(snapshot, f, indent=2)

        # Add to history
        self._add_to_history(
            {
                "type": "snapshot_created",
                "snapshot_id": snapshot_id,
                "timestamp": snapshot["created_at"],
                "description": description,
                "git_commit": snapshot["git"].get("commit_sha"),
            }
        )

        logger.info(f"Snapshot created: {snapshot_id}")
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """Get snapshot metadata.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Snapshot metadata or None if not found
        """
        metadata_path = self.snapshots_dir / f"{snapshot_id}.json"
        if not metadata_path.exists():
            return None

        with open(metadata_path) as f:
            return json.load(f)

    def list_snapshots(self, limit: int = 20) -> List[Dict]:
        """List available snapshots.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of snapshot metadata
        """
        snapshots = []
        for path in sorted(self.snapshots_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(path) as f:
                    snapshots.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to read snapshot {path}: {e}")
        return snapshots

    def rollback(self, snapshot_id: str, restart_service: bool = True) -> Dict[str, Any]:
        """Execute rollback to a specific snapshot.

        Args:
            snapshot_id: Snapshot ID to rollback to
            restart_service: Whether to restart the service after rollback

        Returns:
            Dict with rollback results
        """
        result = {
            "success": False,
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now().isoformat(),
            "operations": [],
        }

        # Get snapshot
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            result["error"] = f"Snapshot not found: {snapshot_id}"
            return result

        # Check cooldown
        last_rollback = self._get_last_rollback_time()
        if last_rollback:
            elapsed = (datetime.now() - last_rollback).total_seconds()
            if elapsed < ROLLBACK_COOLDOWN:
                result[
                    "error"
                ] = f"Rollback cooldown active. Wait {int(ROLLBACK_COOLDOWN - elapsed)}s"
                return result

        logger.info(f"Starting rollback to snapshot: {snapshot_id}")

        # 1. Restore database
        if snapshot.get("database_backup"):
            db_result = self._restore_database(snapshot["database_backup"])
            result["operations"].append({"operation": "database_restore", "success": db_result})

        # 2. Rollback git (optional - only if commit SHA available)
        git_sha = snapshot.get("git", {}).get("commit_sha")
        if git_sha:
            git_result = self._git_rollback(git_sha)
            result["operations"].append(
                {"operation": "git_rollback", "commit": git_sha, "success": git_result}
            )

        # 3. Restart service
        if restart_service:
            restart_result = self._restart_service()
            result["operations"].append({"operation": "service_restart", "success": restart_result})

            # Wait for service to start and verify health
            time.sleep(5)
            health = self._check_health()
            result["operations"].append({"operation": "health_check", "result": health})

        # Determine overall success
        result["success"] = all(
            op.get("success", True)
            for op in result["operations"]
            if op.get("operation") != "health_check"
        )

        # Update snapshot status
        snapshot["status"] = "rolled_back" if result["success"] else "rollback_failed"
        snapshot["rollback_at"] = result["timestamp"]
        metadata_path = self.snapshots_dir / f"{snapshot_id}.json"
        with open(metadata_path, "w") as f:
            json.dump(snapshot, f, indent=2)

        # Add to history
        self._add_to_history(
            {
                "type": "rollback_executed",
                "snapshot_id": snapshot_id,
                "timestamp": result["timestamp"],
                "success": result["success"],
                "operations": result["operations"],
                "triggered_by": "manual",
            }
        )

        logger.info(f"Rollback {'completed' if result['success'] else 'failed'}: {snapshot_id}")
        return result

    def start_health_monitoring(
        self,
        snapshot_id: str,
        duration: int = POST_DEPLOY_MONITORING_DURATION,
        check_interval: int = HEALTH_CHECK_INTERVAL,
        failure_threshold: int = CONSECUTIVE_FAILURES_THRESHOLD,
    ):
        """Start health monitoring after deployment.

        Args:
            snapshot_id: Snapshot ID to rollback to if health fails
            duration: How long to monitor (seconds)
            check_interval: Interval between health checks (seconds)
            failure_threshold: Consecutive failures before rollback
        """
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.warning("Health monitoring already running")
            return

        self._current_snapshot_id = snapshot_id
        self._failure_count = 0
        self._stop_monitoring.clear()
        self._save_state()

        def monitor():
            end_time = datetime.now() + timedelta(seconds=duration)
            consecutive_failures = 0

            logger.info(
                f"Starting health monitoring for {duration}s (rollback snapshot: {snapshot_id})"
            )

            while datetime.now() < end_time and not self._stop_monitoring.is_set():
                health = self._check_health()

                if health["healthy"]:
                    consecutive_failures = 0
                    logger.debug(f"Health OK: {health.get('response_time_ms')}ms")
                else:
                    consecutive_failures += 1
                    logger.warning(
                        f"Health FAILED ({consecutive_failures}/{failure_threshold}): {health.get('error')}"
                    )

                    if consecutive_failures >= failure_threshold:
                        logger.error(f"Health threshold exceeded! Triggering automatic rollback...")

                        # Record the failure in history
                        self._add_to_history(
                            {
                                "type": "auto_rollback_triggered",
                                "snapshot_id": snapshot_id,
                                "timestamp": datetime.now().isoformat(),
                                "consecutive_failures": consecutive_failures,
                                "last_health_check": health,
                            }
                        )

                        # Execute rollback
                        rollback_result = self.rollback(snapshot_id)
                        rollback_result["triggered_by"] = "automatic"

                        # Update history entry
                        self._add_to_history(
                            {
                                "type": "auto_rollback_completed",
                                "snapshot_id": snapshot_id,
                                "timestamp": datetime.now().isoformat(),
                                "success": rollback_result["success"],
                                "operations": rollback_result.get("operations", []),
                            }
                        )

                        break

                self._failure_count = consecutive_failures
                self._save_state()

                # Wait for next check
                self._stop_monitoring.wait(check_interval)

            logger.info("Health monitoring ended")
            self._current_snapshot_id = None
            self._failure_count = 0
            self._save_state()

        self._monitoring_thread = threading.Thread(target=monitor, daemon=True)
        self._monitoring_thread.start()

    def stop_health_monitoring(self):
        """Stop health monitoring."""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        self._current_snapshot_id = None
        self._failure_count = 0
        self._save_state()
        logger.info("Health monitoring stopped")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status.

        Returns:
            Dict with monitoring status
        """
        is_active = self._monitoring_thread and self._monitoring_thread.is_alive()

        return {
            "active": is_active,
            "current_snapshot_id": self._current_snapshot_id if is_active else None,
            "failure_count": self._failure_count if is_active else 0,
            "failure_threshold": CONSECUTIVE_FAILURES_THRESHOLD,
            "health_url": self.health_url,
        }

    def _add_to_history(self, entry: Dict):
        """Add entry to rollback history."""
        history = self.get_history()
        history.insert(0, entry)

        # Keep last 100 entries
        history = history[:100]

        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get rollback history.

        Args:
            limit: Maximum entries to return

        Returns:
            List of history entries
        """
        try:
            if self.history_file.exists():
                with open(self.history_file) as f:
                    history = json.load(f)
                return history[:limit]
        except Exception as e:
            logger.warning(f"Failed to read history: {e}")
        return []

    def _get_last_rollback_time(self) -> Optional[datetime]:
        """Get timestamp of last rollback."""
        for entry in self.get_history():
            if entry.get("type") in ["rollback_executed", "auto_rollback_completed"]:
                try:
                    return datetime.fromisoformat(entry["timestamp"])
                except:
                    pass
        return None

    def cleanup_old_snapshots(self, keep_count: int = 10):
        """Remove old snapshots, keeping the most recent ones.

        Args:
            keep_count: Number of snapshots to keep
        """
        snapshots = sorted(self.snapshots_dir.glob("*.json"), reverse=True)

        for path in snapshots[keep_count:]:
            snapshot_id = path.stem
            try:
                # Remove metadata
                path.unlink()
                # Remove database backup
                db_backup = self.snapshots_dir / f"{snapshot_id}.db"
                if db_backup.exists():
                    db_backup.unlink()
                logger.info(f"Removed old snapshot: {snapshot_id}")
            except Exception as e:
                logger.warning(f"Failed to remove snapshot {snapshot_id}: {e}")


# Singleton instance
_manager_instance = None


def get_rollback_manager() -> RollbackManager:
    """Get the singleton rollback manager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = RollbackManager()
    return _manager_instance


# CLI interface
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Rollback Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Snapshot command
    snap_parser = subparsers.add_parser("snapshot", help="Create a snapshot")
    snap_parser.add_argument("-m", "--message", help="Snapshot description")

    # Rollback command
    rb_parser = subparsers.add_parser("rollback", help="Rollback to snapshot")
    rb_parser.add_argument("snapshot_id", help="Snapshot ID to rollback to")
    rb_parser.add_argument("--no-restart", action="store_true", help="Don't restart service")

    # List command
    list_parser = subparsers.add_parser("list", help="List snapshots")
    list_parser.add_argument("-n", "--count", type=int, default=10, help="Number to show")

    # History command
    hist_parser = subparsers.add_parser("history", help="Show rollback history")
    hist_parser.add_argument("-n", "--count", type=int, default=20, help="Number to show")

    # Monitor command
    mon_parser = subparsers.add_parser("monitor", help="Start health monitoring")
    mon_parser.add_argument("snapshot_id", help="Snapshot ID for rollback")
    mon_parser.add_argument("-d", "--duration", type=int, default=300, help="Duration in seconds")

    # Status command
    subparsers.add_parser("status", help="Show monitoring status")

    # Cleanup command
    clean_parser = subparsers.add_parser("cleanup", help="Clean up old snapshots")
    clean_parser.add_argument("-k", "--keep", type=int, default=10, help="Snapshots to keep")

    args = parser.parse_args()
    manager = RollbackManager()

    if args.command == "snapshot":
        snapshot_id = manager.create_snapshot(args.message)
        print(f"Created snapshot: {snapshot_id}")

    elif args.command == "rollback":
        result = manager.rollback(args.snapshot_id, not args.no_restart)
        print(json.dumps(result, indent=2))

    elif args.command == "list":
        for snap in manager.list_snapshots(args.count):
            print(f"{snap['id']} - {snap.get('description', 'No description')} ({snap['status']})")

    elif args.command == "history":
        for entry in manager.get_history(args.count):
            print(f"{entry['timestamp']} - {entry['type']}: {entry.get('snapshot_id', 'N/A')}")

    elif args.command == "monitor":
        manager.start_health_monitoring(args.snapshot_id, args.duration)
        print(f"Monitoring started (Ctrl+C to stop)")
        try:
            while manager._monitoring_thread and manager._monitoring_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop_health_monitoring()

    elif args.command == "status":
        status = manager.get_monitoring_status()
        print(json.dumps(status, indent=2))

    elif args.command == "cleanup":
        manager.cleanup_old_snapshots(args.keep)
        print(f"Cleanup complete, kept {args.keep} most recent snapshots")

    else:
        parser.print_help()
