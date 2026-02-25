#!/usr/bin/env python3
"""
Comet Google Sheets Sync Script

Run by comet session to process pending sheet updates.

Workflow:
1. Pull latest changes from git
2. Read all CSV files in data/sheets_pending/
3. For each file:
   - Parse CSV
   - Update corresponding Google Sheet
   - Move file to data/sheets_processed/
4. Report summary

Usage:
    python3 scripts/comet_sheets_sync.py
    python3 scripts/comet_sheets_sync.py --dry-run  # Preview only
"""

import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
SHEETS_PENDING_DIR = BASE_DIR / "data" / "sheets_pending"
SHEETS_PROCESSED_DIR = BASE_DIR / "data" / "sheets_processed"

sys.path.insert(0, str(BASE_DIR))


class CometSheetsSync:
    """Syncs pending updates to Google Sheets."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.pending_dir = SHEETS_PENDING_DIR
        self.processed_dir = SHEETS_PROCESSED_DIR
        self.sheets_client = None

    def git_pull(self) -> bool:
        """Pull latest changes from git.

        Returns:
            True if pull successful
        """
        try:
            print("📥 Pulling latest changes from git...")
            result = subprocess.run(
                ["git", "pull"], cwd=str(BASE_DIR), capture_output=True, text=True, check=True
            )
            print(f"   {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Git pull failed: {e.stderr}")
            return False

    def get_sheets_client(self):
        """Get authenticated Google Sheets client."""
        if self.sheets_client:
            return self.sheets_client

        try:
            import gspread
            from google.oauth2.service_account import Credentials

            creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
            if not creds_path.exists():
                print(f"❌ Credentials not found: {creds_path}")
                return None

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
            self.sheets_client = gspread.authorize(creds)
            return self.sheets_client

        except ImportError:
            print("❌ gspread not installed: pip install gspread google-auth")
            return None
        except Exception as e:
            print(f"❌ Failed to authenticate: {e}")
            return None

    def get_project_sheet_id(self, project_name: str) -> Optional[str]:
        """Get or create sheet ID for project.

        For now, uses a mapping file. In production, would query from database.

        Returns:
            Spreadsheet ID or None
        """
        # TODO: Get from project metadata in database
        # For now, use environment variable or config file
        mapping_file = BASE_DIR / "config" / "project_sheets.json"

        if mapping_file.exists():
            try:
                with open(mapping_file) as f:
                    mapping = json.load(f)
                    return mapping.get(project_name)
            except Exception as e:
                print(f"⚠️  Failed to read sheet mapping: {e}")

        # Fallback to environment variable
        return os.environ.get(f'SHEET_ID_{project_name.upper().replace("-", "_")}')

    def read_pending_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Read and parse a pending CSV file.

        Returns:
            Dict with task data or None
        """
        try:
            with open(filepath, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    return rows[0]  # Each file has one task
            return None
        except Exception as e:
            print(f"❌ Failed to read {filepath.name}: {e}")
            return None

    def update_sheet(self, task_data: Dict[str, Any]) -> bool:
        """Update Google Sheet with task data.

        Args:
            task_data: Task data from CSV

        Returns:
            True if updated successfully
        """
        try:
            project_name = task_data.get("project_name", "").replace(" ", "_")
            sheet_id = self.get_project_sheet_id(project_name)

            if not sheet_id:
                print(f"⚠️  No sheet ID for project: {project_name}")
                return False

            if self.dry_run:
                print(f"   [DRY RUN] Would update sheet {sheet_id}")
                print(f"             Task {task_data['task_id']}: {task_data['status']}")
                return True

            # Get sheets client
            gc = self.get_sheets_client()
            if not gc:
                return False

            # Open spreadsheet and worksheet
            sheet = gc.open_by_key(sheet_id)
            worksheet_name = task_data.get("project_name", "Tasks")

            try:
                worksheet = sheet.worksheet(worksheet_name)
            except:
                # Create worksheet if doesn't exist
                worksheet = sheet.add_worksheet(worksheet_name, rows=1000, cols=15)
                # Add header row
                worksheet.append_row(
                    [
                        "Task ID",
                        "Type",
                        "Title",
                        "Status",
                        "Priority",
                        "Assigned To",
                        "Milestone",
                        "Created",
                        "Completed",
                        "Updated",
                    ]
                )

            # Find existing row by task_id
            task_id = str(task_data["task_id"])
            task_id_col = worksheet.col_values(1)  # Column A = Task ID
            row_num = None

            for i, val in enumerate(task_id_col, start=1):
                if str(val) == task_id:
                    row_num = i
                    break

            # Prepare row data
            row_data = [
                task_data["task_id"],
                task_data["task_type"],
                task_data["title"],
                task_data["status"],
                task_data["priority"],
                task_data.get("assigned_to", ""),
                task_data.get("milestone_name", ""),
                task_data.get("created_at", ""),
                task_data.get("completed_at", ""),
                task_data.get("updated_at", ""),
            ]

            if row_num:
                # Update existing row
                for col, value in enumerate(row_data, start=1):
                    worksheet.update_cell(row_num, col, value)
                print(f"   ✅ Updated row {row_num} for task {task_id}")
            else:
                # Append new row
                worksheet.append_row(row_data)
                print(f"   ✅ Added new row for task {task_id}")

            return True

        except Exception as e:
            print(f"❌ Failed to update sheet: {e}")
            import traceback

            traceback.print_exc()
            return False

    def process_pending_files(self) -> Dict[str, int]:
        """Process all pending CSV files.

        Returns:
            Dict with stats (processed, failed, skipped)
        """
        stats = {"processed": 0, "failed": 0, "skipped": 0}

        # Get all pending CSV files
        pending_files = sorted(self.pending_dir.glob("*.csv"))

        if not pending_files:
            print("ℹ️  No pending files to process")
            return stats

        print(f"\n📋 Found {len(pending_files)} pending file(s)")

        for filepath in pending_files:
            print(f"\n📝 Processing: {filepath.name}")

            # Read file
            task_data = self.read_pending_file(filepath)
            if not task_data:
                stats["failed"] += 1
                continue

            # Update sheet
            success = self.update_sheet(task_data)

            if success:
                stats["processed"] += 1

                if not self.dry_run:
                    # Move to processed directory
                    dest = self.processed_dir / filepath.name
                    shutil.move(str(filepath), str(dest))
                    print(f"   📦 Moved to processed/")
            else:
                stats["failed"] += 1

        return stats

    def sync(self) -> Dict[str, int]:
        """Main sync process.

        Returns:
            Dict with stats
        """
        # Pull from git
        if not self.git_pull():
            print("⚠️  Continuing without git pull...")

        # Process pending files
        return self.process_pending_files()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Comet Google Sheets Sync")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without updating sheets"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🤖 Comet Google Sheets Sync")
    print("=" * 60)

    if args.dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made")

    syncer = CometSheetsSync(dry_run=args.dry_run)
    stats = syncer.sync()

    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"   ✅ Processed: {stats['processed']}")
    print(f"   ❌ Failed: {stats['failed']}")
    print(f"   ⏭️  Skipped: {stats['skipped']}")
    print("=" * 60)

    if stats["processed"] > 0:
        print(f"\n✨ Synced {stats['processed']} update(s) to Google Sheets")
    elif stats["failed"] > 0:
        print("\n❌ Sync completed with errors")
        sys.exit(1)
    else:
        print("\n✅ No updates needed")


if __name__ == "__main__":
    main()
