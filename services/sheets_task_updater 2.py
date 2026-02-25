#!/usr/bin/env python3
"""
Google Sheets Task Update Service

Automatically updates Google Sheets when tasks are completed in the architect system.
Routes update requests through the comet session for UI/integration tasks.

Features:
- Hooks into task completion events
- Routes sheet updates through comet session via assigner
- Project-aware: Each project can have its own sheet configuration
- Tracks sync status and errors
- Batches multiple updates to reduce API calls

Usage:
    from services.sheets_task_updater import queue_sheet_update

    # After task completion
    queue_sheet_update(task_id, project_id, status='completed')
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Setup paths
SERVICE_DIR = Path(__file__).parent
BASE_DIR = SERVICE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

# Configuration
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://100.112.58.92:8080")
ASSIGNER_DB = BASE_DIR / "data" / "assigner" / "assigner.db"
ARCHITECT_DB = BASE_DIR / "data" / "prod" / "architect.db"

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class SheetsTaskUpdater:
    """Manages Google Sheets updates for task completions."""

    def __init__(self, dashboard_url: str = None):
        self.dashboard_url = dashboard_url or DASHBOARD_URL
        self.assigner_db = ASSIGNER_DB
        self.architect_db = ARCHITECT_DB

    def get_project_sheet_config(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get Google Sheets configuration for a project.

        Args:
            project_id: Project ID

        Returns:
            Dict with sheet_id, worksheet_name, enabled status, or None
        """
        try:
            with sqlite3.connect(str(self.architect_db), timeout=10) as conn:
                conn.row_factory = sqlite3.Row

                # Check if project has sheets config in metadata or separate table
                result = conn.execute(
                    """
                    SELECT id, name, metadata
                    FROM projects
                    WHERE id = ?
                """,
                    (project_id,),
                ).fetchone()

                if not result:
                    return None

                # Parse metadata for sheets config
                metadata = json.loads(result["metadata"]) if result["metadata"] else {}
                sheets_config = metadata.get("google_sheets", {})

                if not sheets_config.get("enabled"):
                    logger.debug(f"Google Sheets not enabled for project {project_id}")
                    return None

                return {
                    "project_id": project_id,
                    "project_name": result["name"],
                    "sheet_id": sheets_config.get("spreadsheet_id"),
                    "worksheet_name": sheets_config.get("worksheet_name", result["name"]),
                    "enabled": True,
                    "columns": sheets_config.get(
                        "columns",
                        {
                            "task_id": "A",
                            "title": "B",
                            "status": "C",
                            "priority": "D",
                            "assigned_to": "E",
                            "completed_at": "F",
                            "notes": "G",
                        },
                    ),
                }
        except Exception as e:
            logger.error(f"Failed to get project sheet config: {e}")
            return None

    def get_task_details(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get task details from database.

        Args:
            task_id: Task ID

        Returns:
            Dict with task details or None
        """
        try:
            with sqlite3.connect(str(self.architect_db), timeout=10) as conn:
                conn.row_factory = sqlite3.Row

                # Try task_queue first
                result = conn.execute(
                    """
                    SELECT id, task_type, content, status, priority,
                           assigned_to, project_id, created_at, completed_at,
                           metadata
                    FROM task_queue
                    WHERE id = ?
                """,
                    (task_id,),
                ).fetchone()

                if result:
                    task = dict(result)
                    task["type"] = "task"
                    return task

                # Try features table
                result = conn.execute(
                    """
                    SELECT id, name as content, status, priority,
                           project_id, created_at, updated_at as completed_at,
                           description, metadata
                    FROM features
                    WHERE id = ?
                """,
                    (task_id,),
                ).fetchone()

                if result:
                    task = dict(result)
                    task["type"] = "feature"
                    task["task_type"] = "feature"
                    return task

                # Try bugs table
                result = conn.execute(
                    """
                    SELECT id, title as content, status, severity as priority,
                           project_id, created_at, resolved_at as completed_at,
                           description, metadata
                    FROM bugs
                    WHERE id = ?
                """,
                    (task_id,),
                ).fetchone()

                if result:
                    task = dict(result)
                    task["type"] = "bug"
                    task["task_type"] = "bug"
                    return task

                logger.warning(f"Task {task_id} not found")
                return None

        except Exception as e:
            logger.error(f"Failed to get task details: {e}")
            return None

    def build_sheet_update_prompt(self, task: Dict[str, Any], sheet_config: Dict[str, Any]) -> str:
        """Build a prompt for comet to update the Google Sheet.

        Args:
            task: Task details
            sheet_config: Sheet configuration

        Returns:
            Formatted prompt for comet
        """
        sheet_id = sheet_config["sheet_id"]
        worksheet = sheet_config["worksheet_name"]
        columns = sheet_config["columns"]

        # Format task data
        task_id = task["id"]
        title = task.get("content") or task.get("title", "Untitled")
        status = task["status"]
        priority = task.get("priority", "medium")
        assigned_to = task.get("assigned_to", "")
        completed_at = task.get("completed_at", datetime.now().isoformat())
        notes = task.get("description", "")

        # Build prompt
        prompt = f"""Update Google Sheet for task completion:

**Sheet Information:**
- Spreadsheet ID: {sheet_id}
- Worksheet: "{worksheet}"
- Project: {sheet_config['project_name']}

**Task Details:**
- Task ID: {task_id}
- Title: {title}
- Status: {status}
- Priority: {priority}
- Assigned To: {assigned_to}
- Completed At: {completed_at}
- Type: {task.get('type', 'task')}

**Instructions:**
1. Open the Google Sheet using gspread
2. Find the worksheet "{worksheet}" (create if doesn't exist)
3. Look for row with Task ID {task_id} in column {columns['task_id']}
4. If found: Update the existing row
5. If not found: Append a new row
6. Update columns:
   - {columns['task_id']}: {task_id}
   - {columns['title']}: {title}
   - {columns['status']}: {status}
   - {columns['priority']}: {priority}
   - {columns['assigned_to']}: {assigned_to}
   - {columns['completed_at']}: {completed_at}
   - {columns['notes']}: {notes[:100]}

**Code Template:**
```python
import gspread
from google.oauth2.service_account import Credentials

creds_path = "{Path.home()}/.config/gspread/service_account.json"
creds = Credentials.from_service_account_file(creds_path,
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)

sheet = gc.open_by_key('{sheet_id}')
ws = sheet.worksheet('{worksheet}')

# Find or append row
task_id_col = ws.col_values({columns['task_id'].replace('A', '1').replace('B', '2').replace('C', '3')})
row_num = None
for i, val in enumerate(task_id_col, start=1):
    if str(val) == str({task_id}):
        row_num = i
        break

if row_num:
    # Update existing
    ws.update_cell(row_num, 2, "{title}")
    ws.update_cell(row_num, 3, "{status}")
else:
    # Append new
    ws.append_row([{task_id}, "{title}", "{status}", "{priority}",
                   "{assigned_to}", "{completed_at}", "{notes[:100]}"])
```

Respond with "Sheet updated successfully" when done.
"""
        return prompt

    def queue_to_comet(self, prompt: str, priority: int = 3) -> Optional[int]:
        """Queue the sheet update request to comet session via assigner.

        Args:
            prompt: Update prompt for comet
            priority: Priority level (default: 3 for normal)

        Returns:
            Prompt ID if queued successfully, None otherwise
        """
        try:
            # Send to assigner API
            response = requests.post(
                f"{self.dashboard_url}/api/assigner/send",
                json={
                    "content": prompt,
                    "priority": priority,
                    "target_session": "comet",
                    "timeout_minutes": 10,
                    "metadata": {"type": "sheet_update", "automated": True},
                },
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                prompt_id = result.get("prompt_id")
                logger.info(f"Queued sheet update to comet: prompt_id={prompt_id}")
                return prompt_id
            else:
                logger.error(f"Failed to queue to assigner: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Failed to queue to comet: {e}")
            return None

    def queue_sheet_update(self, task_id: int, project_id: int = None, status: str = None) -> bool:
        """Main entry point: Queue a sheet update for a completed task.

        Args:
            task_id: Task ID to update
            project_id: Project ID (optional, will be fetched from task)
            status: New status (optional, will be fetched from task)

        Returns:
            True if queued successfully, False otherwise
        """
        try:
            # Get task details
            task = self.get_task_details(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return False

            # Get project_id from task if not provided
            if project_id is None:
                project_id = task.get("project_id")

            if not project_id:
                logger.warning(f"Task {task_id} has no project_id, skipping sheet update")
                return False

            # Get project sheet config
            sheet_config = self.get_project_sheet_config(project_id)
            if not sheet_config:
                logger.debug(f"No sheet config for project {project_id}, skipping")
                return False

            # Update status if provided
            if status:
                task["status"] = status

            # Build prompt
            prompt = self.build_sheet_update_prompt(task, sheet_config)

            # Queue to comet
            prompt_id = self.queue_to_comet(prompt, priority=3)

            if prompt_id:
                logger.info(f"Sheet update queued for task {task_id}: prompt_id={prompt_id}")
                return True
            else:
                logger.error(f"Failed to queue sheet update for task {task_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to queue sheet update: {e}")
            return False


# =============================================================================
# Convenience Functions
# =============================================================================

_updater = None


def get_updater() -> SheetsTaskUpdater:
    """Get singleton updater instance."""
    global _updater
    if _updater is None:
        _updater = SheetsTaskUpdater()
    return _updater


def queue_sheet_update(task_id: int, project_id: int = None, status: str = None) -> bool:
    """Queue a Google Sheets update for a completed task.

    This is the main entry point for other modules to trigger sheet updates.

    Args:
        task_id: Task ID to update
        project_id: Project ID (optional)
        status: New status (optional)

    Returns:
        True if queued successfully, False otherwise

    Example:
        >>> from services.sheets_task_updater import queue_sheet_update
        >>> queue_sheet_update(task_id=42, status='completed')
        True
    """
    updater = get_updater()
    return updater.queue_sheet_update(task_id, project_id, status)


def enable_sheets_for_project(
    project_id: int, spreadsheet_id: str, worksheet_name: str = None
) -> bool:
    """Enable Google Sheets sync for a project.

    Args:
        project_id: Project ID
        spreadsheet_id: Google Sheets spreadsheet ID
        worksheet_name: Worksheet name (defaults to project name)

    Returns:
        True if enabled successfully
    """
    try:
        with sqlite3.connect(str(ARCHITECT_DB), timeout=10) as conn:
            # Get current metadata
            result = conn.execute(
                "SELECT metadata, name FROM projects WHERE id = ?", (project_id,)
            ).fetchone()

            if not result:
                logger.error(f"Project {project_id} not found")
                return False

            metadata = json.loads(result[0]) if result[0] else {}
            project_name = result[1]

            # Update sheets config
            metadata["google_sheets"] = {
                "enabled": True,
                "spreadsheet_id": spreadsheet_id,
                "worksheet_name": worksheet_name or project_name,
                "enabled_at": datetime.now().isoformat(),
            }

            # Save
            conn.execute(
                "UPDATE projects SET metadata = ? WHERE id = ?", (json.dumps(metadata), project_id)
            )
            conn.commit()

            logger.info(f"Enabled Google Sheets for project {project_id}")
            return True

    except Exception as e:
        logger.error(f"Failed to enable sheets for project: {e}")
        return False


if __name__ == "__main__":
    # Test/demo
    import argparse

    parser = argparse.ArgumentParser(description="Google Sheets Task Updater")
    parser.add_argument("--test", type=int, help="Test with task ID")
    parser.add_argument("--enable", type=int, help="Enable for project ID")
    parser.add_argument("--sheet-id", help="Spreadsheet ID for --enable")
    parser.add_argument("--worksheet", help="Worksheet name for --enable")

    args = parser.parse_args()

    if args.enable:
        if not args.sheet_id:
            print("Error: --sheet-id required with --enable")
            sys.exit(1)
        success = enable_sheets_for_project(args.enable, args.sheet_id, args.worksheet)
        print(f"{'Success' if success else 'Failed'}")

    elif args.test:
        success = queue_sheet_update(args.test, status="completed")
        print(f"Queued: {success}")

    else:
        parser.print_help()
