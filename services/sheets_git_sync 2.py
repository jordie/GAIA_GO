#!/usr/bin/env python3
"""
Google Sheets Git-Based Sync Service

Data flow:
1. Task completion → Write to CSV file in data/sheets_pending/
2. Git commit the file
3. Comet session pulls from git
4. Comet reads pending files and updates Google Sheets
5. Mark files as processed

This approach:
- Creates audit trail in git
- Works offline (queues updates)
- Allows manual review/editing before sheet update
- All updates go through comet browser session
"""

import csv
import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths
SERVICE_DIR = Path(__file__).parent
BASE_DIR = SERVICE_DIR.parent
SHEETS_PENDING_DIR = BASE_DIR / "data" / "sheets_pending"
SHEETS_PROCESSED_DIR = BASE_DIR / "data" / "sheets_processed"
ARCHITECT_DB = BASE_DIR / "data" / "prod" / "architect.db"

# Ensure directories exist
SHEETS_PENDING_DIR.mkdir(parents=True, exist_ok=True)
SHEETS_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class SheetsGitSync:
    """Manages git-based Google Sheets synchronization."""

    def __init__(self):
        self.pending_dir = SHEETS_PENDING_DIR
        self.processed_dir = SHEETS_PROCESSED_DIR
        self.architect_db = ARCHITECT_DB

    def get_task_details(self, task_id: int, task_type: str = "task") -> Optional[Dict[str, Any]]:
        """Get task details from database.

        Args:
            task_id: Task ID
            task_type: Task type (task, feature, bug)

        Returns:
            Dict with task details or None
        """
        try:
            with sqlite3.connect(str(self.architect_db), timeout=10) as conn:
                conn.row_factory = sqlite3.Row

                if task_type == "feature":
                    result = conn.execute(
                        """
                        SELECT f.id, f.name as title, f.description, f.status,
                               f.priority, f.project_id, p.name as project_name,
                               f.assigned_to, f.created_at, f.completed_at,
                               f.milestone_id, m.name as milestone_name
                        FROM features f
                        LEFT JOIN projects p ON f.project_id = p.id
                        LEFT JOIN milestones m ON f.milestone_id = m.id
                        WHERE f.id = ?
                    """,
                        (task_id,),
                    ).fetchone()

                elif task_type == "bug":
                    result = conn.execute(
                        """
                        SELECT b.id, b.title, b.description, b.status,
                               b.severity as priority, b.project_id, p.name as project_name,
                               b.assigned_to, b.created_at, b.resolved_at as completed_at,
                               b.milestone_id, m.name as milestone_name
                        FROM bugs b
                        LEFT JOIN projects p ON b.project_id = p.id
                        LEFT JOIN milestones m ON b.milestone_id = m.id
                        WHERE b.id = ?
                    """,
                        (task_id,),
                    ).fetchone()

                else:  # task
                    result = conn.execute(
                        """
                        SELECT t.id, t.task_type as title, t.content as description,
                               t.status, t.priority, t.project_id, p.name as project_name,
                               t.assigned_to, t.created_at, t.completed_at,
                               NULL as milestone_id, NULL as milestone_name
                        FROM task_queue t
                        LEFT JOIN projects p ON t.project_id = p.id
                        WHERE t.id = ?
                    """,
                        (task_id,),
                    ).fetchone()

                if result:
                    return dict(result)
                return None

        except Exception as e:
            logger.error(f"Failed to get task details: {e}")
            return None

    def write_pending_update(
        self, task_id: int, task_type: str, status: str, project_id: int = None
    ) -> Optional[Path]:
        """Write task update to pending CSV file.

        Args:
            task_id: Task ID
            task_type: Task type (task, feature, bug)
            status: New status
            project_id: Project ID (optional)

        Returns:
            Path to created file or None
        """
        try:
            # Get task details
            task = self.get_task_details(task_id, task_type)
            if not task:
                logger.warning(f"Task {task_id} not found")
                return None

            # Use project_id from task if not provided
            if project_id is None:
                project_id = task.get("project_id")

            if not project_id:
                logger.warning(f"Task {task_id} has no project_id")
                return None

            project_name = task.get("project_name", f"project_{project_id}")

            # Create filename: project_TIMESTAMP.csv
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{project_name}_{timestamp}_{task_type}_{task_id}.csv"
            filepath = self.pending_dir / filename

            # Write CSV
            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "task_id",
                        "task_type",
                        "title",
                        "description",
                        "status",
                        "priority",
                        "project_id",
                        "project_name",
                        "assigned_to",
                        "milestone_name",
                        "created_at",
                        "completed_at",
                        "updated_at",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "task_id": task["id"],
                        "task_type": task_type,
                        "title": task.get("title", ""),
                        "description": task.get("description", ""),
                        "status": status,
                        "priority": task.get("priority", ""),
                        "project_id": project_id,
                        "project_name": project_name,
                        "assigned_to": task.get("assigned_to", ""),
                        "milestone_name": task.get("milestone_name", ""),
                        "created_at": task.get("created_at", ""),
                        "completed_at": task.get("completed_at", ""),
                        "updated_at": datetime.now().isoformat(),
                    }
                )

            logger.info(f"Wrote pending update to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to write pending update: {e}")
            return None

    def git_commit_pending(self, filepath: Path, task_id: int, task_type: str) -> bool:
        """Commit the pending file to git.

        Args:
            filepath: Path to file to commit
            task_id: Task ID (for commit message)
            task_type: Task type

        Returns:
            True if committed successfully
        """
        try:
            # Add file
            subprocess.run(
                ["git", "add", str(filepath)], cwd=str(BASE_DIR), check=True, capture_output=True
            )

            # Commit with descriptive message
            commit_msg = f"sheets: Update {task_type} {task_id}\n\nAutomated Google Sheets sync"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=str(BASE_DIR),
                check=True,
                capture_output=True,
            )

            logger.info(f"Committed {filepath.name} to git")
            return True

        except subprocess.CalledProcessError as e:
            # Check if it's just "nothing to commit"
            if b"nothing to commit" in e.output:
                logger.debug("Nothing to commit")
                return True
            logger.error(f"Git commit failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to commit: {e}")
            return False

    def queue_comet_sync(self) -> bool:
        """Queue a sync request to comet session via assigner.

        Returns:
            True if queued successfully
        """
        try:
            import requests

            dashboard_url = os.environ.get("DASHBOARD_URL", "http://100.112.58.92:8080")

            # Build prompt for comet
            prompt = """Pull latest changes and sync Google Sheets:

**Instructions:**
1. Pull latest changes from git:
   ```bash
   cd /path/to/architect
   git pull
   ```

2. Run the sheets sync script:
   ```python
   python3 services/sheets_git_sync.py --sync-pending
   ```

3. The script will:
   - Read all CSV files in data/sheets_pending/
   - Update Google Sheets for each project
   - Move processed files to data/sheets_processed/

4. Report back with number of sheets updated.

**Expected output:**
"Synced N updates to Google Sheets"
"""

            # Send to assigner API
            response = requests.post(
                f"{dashboard_url}/api/assigner/send",
                json={
                    "content": prompt,
                    "priority": 3,
                    "target_session": "comet",
                    "timeout_minutes": 15,
                    "metadata": {"type": "sheet_sync", "automated": True},
                },
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Queued sync to comet: prompt_id={result.get('prompt_id')}")
                return True
            else:
                logger.error(f"Failed to queue to assigner: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to queue comet sync: {e}")
            return False


# =============================================================================
# Main Entry Point
# =============================================================================


def queue_sheet_update(
    task_id: int, task_type: str = "task", status: str = None, project_id: int = None
) -> bool:
    """Queue a Google Sheets update via git + comet.

    This is the main entry point for other modules.

    Args:
        task_id: Task ID
        task_type: Task type (task, feature, bug)
        status: New status
        project_id: Project ID (optional)

    Returns:
        True if queued successfully

    Example:
        >>> from services.sheets_git_sync import queue_sheet_update
        >>> queue_sheet_update(42, 'feature', 'completed')
        True
    """
    syncer = SheetsGitSync()

    # Write pending update
    filepath = syncer.write_pending_update(task_id, task_type, status, project_id)
    if not filepath:
        return False

    # Commit to git
    if not syncer.git_commit_pending(filepath, task_id, task_type):
        return False

    # Queue sync to comet (batched - comet will process all pending files)
    if not syncer.queue_comet_sync():
        logger.warning("Failed to queue comet sync, but file is committed")
        # Still return True because the file is safely committed
        return True

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Google Sheets Git Sync")
    parser.add_argument("--test", type=int, help="Test with task ID")
    parser.add_argument(
        "--type", default="task", choices=["task", "feature", "bug"], help="Task type"
    )
    parser.add_argument("--status", default="completed", help="Status")
    parser.add_argument(
        "--sync-pending",
        action="store_true",
        help="Sync all pending files to sheets (run by comet)",
    )

    args = parser.parse_args()

    if args.sync_pending:
        # This will be implemented in the comet sync script
        print("Sync pending files (to be run by comet)")
        # TODO: Implement reading pending files and updating sheets
    elif args.test:
        success = queue_sheet_update(args.test, args.type, args.status)
        print(f"Queued: {success}")
    else:
        parser.print_help()
