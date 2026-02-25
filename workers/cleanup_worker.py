#!/usr/bin/env python3
"""
Storage Cleanup Worker

Manages storage cleanup for the architect dashboard:
- Database backup retention (keep last N backups per environment)
- Log file rotation (delete logs older than N days)
- Task queue cleanup (remove completed/cancelled tasks)
- Error cleanup (remove resolved errors)
- Temp file cleanup
- Assigner prompt cleanup

Usage:
    python3 cleanup_worker.py --dry-run              # Show what would be deleted
    python3 cleanup_worker.py --force                # Actually delete files
    python3 cleanup_worker.py --days 30              # Custom age threshold
    python3 cleanup_worker.py --keep 10              # Keep last N backups
    python3 cleanup_worker.py --daemon               # Run as daemon
    python3 cleanup_worker.py --status               # Check daemon status
    python3 cleanup_worker.py --stop                 # Stop daemon
"""

import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from db import get_connection, get_db_path

# Worker configuration
PID_FILE = Path("/tmp/architect_cleanup_worker.pid")
LOG_FILE = Path("/tmp/architect_cleanup_worker.log")
STATE_FILE = Path("/tmp/architect_cleanup_worker_state.json")

# Default cleanup settings
DEFAULT_BACKUP_RETENTION = {"prod": 10, "qa": 5, "dev": 5, "test": 3, "default": 5}
DEFAULT_LOG_AGE_DAYS = 30
DEFAULT_TASK_AGE_DAYS = 7
DEFAULT_ERROR_AGE_DAYS = 30
DEFAULT_PROMPT_AGE_DAYS = 14
CLEANUP_INTERVAL = 3600  # 1 hour in seconds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("cleanup_worker")


class CleanupStats:
    """Track cleanup statistics"""

    def __init__(self):
        self.backups_deleted = 0
        self.logs_deleted = 0
        self.tasks_deleted = 0
        self.errors_deleted = 0
        self.prompts_deleted = 0
        self.temp_files_deleted = 0
        self.space_freed = 0  # bytes

    def add_file(self, size: int):
        """Add file to space freed count"""
        self.space_freed += size

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "backups_deleted": self.backups_deleted,
            "logs_deleted": self.logs_deleted,
            "tasks_deleted": self.tasks_deleted,
            "errors_deleted": self.errors_deleted,
            "prompts_deleted": self.prompts_deleted,
            "temp_files_deleted": self.temp_files_deleted,
            "space_freed_mb": round(self.space_freed / (1024 * 1024), 2),
        }

    def __str__(self) -> str:
        """Human-readable summary"""
        return (
            f"Cleanup Summary:\n"
            f"  Backups deleted: {self.backups_deleted}\n"
            f"  Logs deleted: {self.logs_deleted}\n"
            f"  Tasks deleted: {self.tasks_deleted}\n"
            f"  Errors deleted: {self.errors_deleted}\n"
            f"  Prompts deleted: {self.prompts_deleted}\n"
            f"  Temp files deleted: {self.temp_files_deleted}\n"
            f"  Space freed: {round(self.space_freed / (1024 * 1024), 2)} MB"
        )


class CleanupWorker:
    """Manages storage cleanup operations"""

    def __init__(
        self,
        dry_run: bool = True,
        backup_retention: Optional[Dict] = None,
        log_age_days: int = DEFAULT_LOG_AGE_DAYS,
        task_age_days: int = DEFAULT_TASK_AGE_DAYS,
        error_age_days: int = DEFAULT_ERROR_AGE_DAYS,
        prompt_age_days: int = DEFAULT_PROMPT_AGE_DAYS,
    ):
        self.dry_run = dry_run
        self.backup_retention = backup_retention or DEFAULT_BACKUP_RETENTION
        self.log_age_days = log_age_days
        self.task_age_days = task_age_days
        self.error_age_days = error_age_days
        self.prompt_age_days = prompt_age_days
        self.stats = CleanupStats()
        self.data_dir = BASE_DIR / "data"

    def run_cleanup(self) -> CleanupStats:
        """Run all cleanup operations"""
        logger.info(f"Starting cleanup (dry_run={self.dry_run})")

        # Run cleanup operations
        self.cleanup_database_backups()
        self.cleanup_log_files()
        self.cleanup_task_queue()
        self.cleanup_errors()
        self.cleanup_assigner_prompts()
        self.cleanup_temp_files()

        logger.info(f"Cleanup complete:\n{self.stats}")
        return self.stats

    def cleanup_database_backups(self):
        """Clean up old database backups, keeping only the most recent N per environment"""
        logger.info("Cleaning up database backups...")

        # Find all backup directories
        backup_dirs = [
            self.data_dir / "prod" / "backups",
            self.data_dir / "qa" / "backups",
            self.data_dir / "dev" / "backups",
            self.data_dir / "test" / "backups",
            self.data_dir / "backups",  # Root level backups
        ]

        for backup_dir in backup_dirs:
            if not backup_dir.exists():
                continue

            # Determine environment from path
            env_name = "default"
            if backup_dir.parent.name in ["prod", "qa", "dev", "test"]:
                env_name = backup_dir.parent.name

            retention_count = self.backup_retention.get(env_name, self.backup_retention["default"])

            # Get all backup files sorted by modification time (newest first)
            backups = []
            for backup_file in backup_dir.glob("*.db"):
                if backup_file.is_file():
                    backups.append((backup_file, backup_file.stat().st_mtime))

            backups.sort(key=lambda x: x[1], reverse=True)

            # Keep only the most recent N backups
            if len(backups) > retention_count:
                to_delete = backups[retention_count:]
                logger.info(
                    f"Found {len(backups)} backups in {backup_dir}, "
                    f"keeping {retention_count}, deleting {len(to_delete)}"
                )

                for backup_file, mtime in to_delete:
                    file_size = backup_file.stat().st_size
                    if self.dry_run:
                        logger.info(
                            f"[DRY RUN] Would delete: {backup_file} "
                            f"({round(file_size / (1024 * 1024), 2)} MB)"
                        )
                        self.stats.backups_deleted += 1
                        self.stats.add_file(file_size)
                    else:
                        try:
                            backup_file.unlink()
                            logger.info(f"Deleted: {backup_file}")
                            self.stats.backups_deleted += 1
                            self.stats.add_file(file_size)
                        except Exception as e:
                            logger.error(f"Failed to delete {backup_file}: {e}")

    def cleanup_log_files(self):
        """Clean up log files older than N days"""
        logger.info(f"Cleaning up log files older than {self.log_age_days} days...")

        cutoff_date = datetime.now() - timedelta(days=self.log_age_days)
        cutoff_timestamp = cutoff_date.timestamp()

        # Find log files
        log_patterns = ["*.log", "*.log.*"]
        log_dirs = [
            self.data_dir,
            Path("/tmp"),
            BASE_DIR / "logs",
        ]

        for log_dir in log_dirs:
            if not log_dir.exists():
                continue

            for pattern in log_patterns:
                for log_file in log_dir.rglob(pattern):
                    if not log_file.is_file():
                        continue

                    # Skip active worker logs
                    if log_file.name in [
                        "architect_cleanup_worker.log",
                        "architect_worker.log",
                        "architect_assigner_worker.log",
                        "architect_milestone_worker.log",
                    ]:
                        continue

                    # Skip chrome profile logs (not ours)
                    if "chrome_profile" in str(log_file):
                        continue

                    mtime = log_file.stat().st_mtime
                    if mtime < cutoff_timestamp:
                        file_size = log_file.stat().st_size
                        if self.dry_run:
                            logger.info(
                                f"[DRY RUN] Would delete: {log_file} "
                                f"({round(file_size / 1024, 2)} KB)"
                            )
                        else:
                            try:
                                log_file.unlink()
                                logger.info(f"Deleted: {log_file}")
                                self.stats.logs_deleted += 1
                                self.stats.add_file(file_size)
                            except Exception as e:
                                logger.error(f"Failed to delete {log_file}: {e}")

    def cleanup_task_queue(self):
        """Clean up completed/cancelled tasks older than N days"""
        logger.info(f"Cleaning up task queue (tasks older than {self.task_age_days} days)...")

        cutoff_date = datetime.now() - timedelta(days=self.task_age_days)

        try:
            import sqlite3

            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if task_queue table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='task_queue'
            """
            )
            if not cursor.fetchone():
                logger.info("No task_queue table found, skipping")
                return

            # Check table structure
            cursor.execute("PRAGMA table_info(task_queue)")
            columns = [col[1] for col in cursor.fetchall()]
            has_type = "type" in columns
            has_description = "description" in columns

            # Build query based on available columns
            if has_type and has_description:
                cursor.execute(
                    """
                    SELECT id, status, created_at, type, description
                    FROM task_queue
                    WHERE status IN ('completed', 'cancelled', 'failed')
                    AND datetime(created_at) < datetime(?)
                """,
                    (cutoff_date.isoformat(),),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, status, created_at
                    FROM task_queue
                    WHERE status IN ('completed', 'cancelled', 'failed')
                    AND datetime(created_at) < datetime(?)
                """,
                    (cutoff_date.isoformat(),),
                )

            tasks_to_delete = cursor.fetchall()

            if tasks_to_delete:
                logger.info(f"Found {len(tasks_to_delete)} old tasks to delete")

                if self.dry_run:
                    for task in tasks_to_delete[:10]:  # Show first 10
                        task_desc = f"{task[0]}: {task[1]}"
                        if len(task) > 3:
                            task_desc += f" - {task[3]}"
                        if len(task) > 4:
                            task_desc += f" - {task[4][:50]}"
                        logger.info(f"[DRY RUN] Would delete task {task_desc}")
                    if len(tasks_to_delete) > 10:
                        logger.info(f"[DRY RUN] ... and {len(tasks_to_delete) - 10} more")
                else:
                    task_ids = [task[0] for task in tasks_to_delete]
                    placeholders = ",".join("?" * len(task_ids))
                    cursor.execute(f"DELETE FROM task_queue WHERE id IN ({placeholders})", task_ids)
                    conn.commit()
                    logger.info(f"Deleted {len(tasks_to_delete)} old tasks")
                    self.stats.tasks_deleted = len(tasks_to_delete)
            else:
                logger.info("No old tasks found to delete")

        except Exception as e:
            logger.error(f"Failed to cleanup task queue: {e}")
        finally:
            if conn:
                conn.close()

    def cleanup_errors(self):
        """Clean up resolved errors older than N days"""
        logger.info(f"Cleaning up resolved errors (older than {self.error_age_days} days)...")

        cutoff_date = datetime.now() - timedelta(days=self.error_age_days)

        try:
            import sqlite3

            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if errors table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='errors'
            """
            )
            if not cursor.fetchone():
                logger.info("No errors table found, skipping")
                return

            # Check table structure
            cursor.execute("PRAGMA table_info(errors)")
            columns = [col[1] for col in cursor.fetchall()]
            has_resolved = "resolved" in columns
            has_resolved_at = "resolved_at" in columns

            # Only proceed if table has resolved tracking
            if not has_resolved:
                logger.info("Errors table doesn't have resolved tracking, skipping")
                return

            # Find old resolved errors
            if has_resolved_at:
                cursor.execute(
                    """
                    SELECT id, error_type, message, resolved_at
                    FROM errors
                    WHERE resolved = 1
                    AND datetime(resolved_at) < datetime(?)
                """,
                    (cutoff_date.isoformat(),),
                )
            else:
                # If no resolved_at, use created_at or just skip old resolved errors
                logger.info("Errors table doesn't have resolved_at timestamp, skipping")
                return

            errors_to_delete = cursor.fetchall()

            if errors_to_delete:
                logger.info(f"Found {len(errors_to_delete)} old resolved errors to delete")

                if self.dry_run:
                    for error in errors_to_delete[:10]:  # Show first 10
                        logger.info(
                            f"[DRY RUN] Would delete error {error[0]}: "
                            f"{error[1]} - {error[2][:50]}"
                        )
                    if len(errors_to_delete) > 10:
                        logger.info(f"[DRY RUN] ... and {len(errors_to_delete) - 10} more")
                else:
                    error_ids = [error[0] for error in errors_to_delete]
                    placeholders = ",".join("?" * len(error_ids))
                    cursor.execute(f"DELETE FROM errors WHERE id IN ({placeholders})", error_ids)
                    conn.commit()
                    logger.info(f"Deleted {len(errors_to_delete)} old resolved errors")
                    self.stats.errors_deleted = len(errors_to_delete)
            else:
                logger.info("No old resolved errors found to delete")

        except Exception as e:
            logger.error(f"Failed to cleanup errors: {e}")
        finally:
            if conn:
                conn.close()

    def cleanup_assigner_prompts(self):
        """Clean up old assigner prompts (completed/cancelled/failed)"""
        logger.info(f"Cleaning up assigner prompts (older than {self.prompt_age_days} days)...")

        assigner_db = self.data_dir / "assigner" / "assigner.db"
        if not assigner_db.exists():
            logger.info("No assigner database found, skipping")
            return

        cutoff_date = datetime.now() - timedelta(days=self.prompt_age_days)

        try:
            conn = sqlite3.connect(str(assigner_db))
            cursor = conn.cursor()

            # Find old completed/cancelled/failed prompts that are not archived
            cursor.execute(
                """
                SELECT id, status, content, completed_at
                FROM prompts
                WHERE status IN ('completed', 'cancelled', 'failed')
                AND archived = 0
                AND datetime(COALESCE(completed_at, created_at)) < datetime(?)
            """,
                (cutoff_date.isoformat(),),
            )

            prompts_to_archive = cursor.fetchall()

            if prompts_to_archive:
                logger.info(f"Found {len(prompts_to_archive)} old prompts to archive")

                if self.dry_run:
                    for prompt in prompts_to_archive[:10]:  # Show first 10
                        logger.info(
                            f"[DRY RUN] Would archive prompt {prompt[0]}: "
                            f"{prompt[1]} - {prompt[2][:50]}"
                        )
                    if len(prompts_to_archive) > 10:
                        logger.info(f"[DRY RUN] ... and {len(prompts_to_archive) - 10} more")
                else:
                    # Archive instead of delete to preserve history
                    prompt_ids = [prompt[0] for prompt in prompts_to_archive]
                    placeholders = ",".join("?" * len(prompt_ids))
                    cursor.execute(
                        f"""
                        UPDATE prompts
                        SET archived = 1, archived_at = datetime('now')
                        WHERE id IN ({placeholders})
                    """,
                        prompt_ids,
                    )
                    conn.commit()
                    logger.info(f"Archived {len(prompts_to_archive)} old prompts")
                    self.stats.prompts_deleted = len(prompts_to_archive)
            else:
                logger.info("No old prompts found to archive")

        except Exception as e:
            logger.error(f"Failed to cleanup assigner prompts: {e}")
        finally:
            conn.close()

    def cleanup_temp_files(self):
        """Clean up temporary files and directories"""
        logger.info("Cleaning up temporary files...")

        temp_patterns = [
            "*.tmp",
            "*.temp",
            "*.cache",
            "__pycache__",
            ".pytest_cache",
            "*.pyc",
        ]

        # Only clean temp files in our data directory, not system-wide
        for pattern in temp_patterns:
            for temp_file in self.data_dir.rglob(pattern):
                # Skip chrome profiles
                if "chrome_profile" in str(temp_file):
                    continue

                try:
                    if temp_file.is_file():
                        file_size = temp_file.stat().st_size
                        if self.dry_run:
                            logger.info(f"[DRY RUN] Would delete: {temp_file}")
                            self.stats.temp_files_deleted += 1
                            self.stats.add_file(file_size)
                        else:
                            temp_file.unlink()
                            logger.info(f"Deleted: {temp_file}")
                            self.stats.temp_files_deleted += 1
                            self.stats.add_file(file_size)
                    elif temp_file.is_dir():
                        # Count files in directory
                        file_count = sum(1 for _ in temp_file.rglob("*") if _.is_file())
                        if self.dry_run:
                            logger.info(
                                f"[DRY RUN] Would delete directory: {temp_file} "
                                f"({file_count} files)"
                            )
                            self.stats.temp_files_deleted += file_count
                        else:
                            import shutil

                            shutil.rmtree(temp_file)
                            logger.info(f"Deleted directory: {temp_file}")
                            self.stats.temp_files_deleted += file_count
                except Exception as e:
                    logger.error(f"Failed to delete {temp_file}: {e}")


def save_state(stats: CleanupStats):
    """Save cleanup state to file"""
    state = {"last_run": datetime.now().isoformat(), "stats": stats.to_dict()}
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def load_state() -> Optional[Dict]:
    """Load cleanup state from file"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
    return None


def run_daemon():
    """Run cleanup worker as daemon"""
    logger.info("Starting cleanup worker daemon")

    # Save PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while True:
            logger.info("Running cleanup cycle...")
            worker = CleanupWorker(dry_run=False)
            stats = worker.run_cleanup()
            save_state(stats)

            logger.info(f"Cleanup cycle complete, sleeping for {CLEANUP_INTERVAL}s")
            time.sleep(CLEANUP_INTERVAL)
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


def stop_daemon():
    """Stop the cleanup daemon"""
    if not PID_FILE.exists():
        print("Daemon is not running")
        return False

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        os.kill(pid, signal.SIGTERM)
        print(f"Stopped cleanup daemon (PID {pid})")

        # Wait for PID file to be removed
        for _ in range(10):
            if not PID_FILE.exists():
                break
            time.sleep(0.5)

        return True
    except ProcessLookupError:
        print("Daemon process not found, cleaning up PID file")
        PID_FILE.unlink()
        return False
    except Exception as e:
        print(f"Failed to stop daemon: {e}")
        return False


def show_status():
    """Show daemon status"""
    if PID_FILE.exists():
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)  # Check if process exists
            print(f"Cleanup daemon is running (PID {pid})")
        except ProcessLookupError:
            print(f"Cleanup daemon PID file exists but process {pid} is not running")
    else:
        print("Cleanup daemon is not running")

    # Show last run stats
    state = load_state()
    if state:
        print(f"\nLast cleanup: {state['last_run']}")
        print("\nStatistics:")
        for key, value in state["stats"].items():
            print(f"  {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description="Architect Dashboard Storage Cleanup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--force", action="store_true", help="Actually delete files (opposite of dry-run)"
    )
    parser.add_argument(
        "--days", type=int, help="Age threshold in days (applies to logs, tasks, errors)"
    )
    parser.add_argument("--keep", type=int, help="Number of backups to keep per environment")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Show daemon status")

    args = parser.parse_args()

    # Handle daemon commands
    if args.stop:
        stop_daemon()
        return

    if args.status:
        show_status()
        return

    if args.daemon:
        run_daemon()
        return

    # Determine dry-run mode
    dry_run = not args.force if args.force else True
    if args.dry_run:
        dry_run = True

    # Build cleanup configuration
    backup_retention = DEFAULT_BACKUP_RETENTION.copy()
    if args.keep:
        for env in backup_retention:
            backup_retention[env] = args.keep

    log_age = args.days if args.days else DEFAULT_LOG_AGE_DAYS
    task_age = args.days if args.days else DEFAULT_TASK_AGE_DAYS
    error_age = args.days if args.days else DEFAULT_ERROR_AGE_DAYS
    prompt_age = args.days if args.days else DEFAULT_PROMPT_AGE_DAYS

    # Run cleanup
    worker = CleanupWorker(
        dry_run=dry_run,
        backup_retention=backup_retention,
        log_age_days=log_age,
        task_age_days=task_age,
        error_age_days=error_age,
        prompt_age_days=prompt_age,
    )

    stats = worker.run_cleanup()
    print("\n" + str(stats))

    if dry_run:
        print("\nThis was a DRY RUN. Use --force to actually delete files.")
    else:
        save_state(stats)


if __name__ == "__main__":
    main()
