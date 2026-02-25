#!/usr/bin/env python3
"""
Sheet Task CLI - Interface for tmux sessions to interact with Google Sheets tasks.

Usage:
    sheet_task_cli.py pull <session_name>       # Pull next available task
    sheet_task_cli.py complete <task_id> [note] # Mark task as completed
    sheet_task_cli.py fail <task_id> [reason]   # Mark task as failed
    sheet_task_cli.py list <session_name>       # List tasks for session
    sheet_task_cli.py status                    # Show task summary

Examples:
    ./sheet_task_cli.py pull task_worker1
    ./sheet_task_cli.py complete 42 "Fixed the bug"
    ./sheet_task_cli.py fail 42 "Missing dependency"
    ./sheet_task_cli.py list task_worker1
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sheets_sync import (
    SPREADSHEET_ID,
    assign_task_to_session,
    get_next_task_for_session,
    get_session_tasks,
    get_sheets_client,
    log,
    update_task_status,
)


def pull_task(session_name):
    """Pull next available task for a session."""
    task = get_next_task_for_session(session_name)
    if task:
        print(f"Task pulled successfully!")
        print(f"=" * 60)
        print(f"Task ID:     {task['id']}")
        print(f"Type:        {task['type']}")
        print(f"Priority:    {task['priority']}")
        print(f"Description: {task['description']}")
        print(f"=" * 60)
        print(f"\nTo complete: ./sheet_task_cli.py complete {task['id']} \"<notes>\"")
        print(f"To fail:     ./sheet_task_cli.py fail {task['id']} \"<reason>\"")
        return task
    else:
        print("No pending tasks available.")
        return None


def complete_task(task_id, note=None):
    """Mark a task as completed."""
    session = "cli"
    success = update_task_status(task_id, "completed", note, session)
    if success:
        print(f"Task {task_id} marked as COMPLETED")
        if note:
            print(f"Note: {note}")
    else:
        print(f"Failed to update task {task_id}")
    return success


def fail_task(task_id, reason=None):
    """Mark a task as failed."""
    session = "cli"
    success = update_task_status(task_id, "failed", reason, session)
    if success:
        print(f"Task {task_id} marked as FAILED")
        if reason:
            print(f"Reason: {reason}")
    else:
        print(f"Failed to update task {task_id}")
    return success


def list_tasks(session_name):
    """List all tasks for a session."""
    tasks = get_session_tasks(session_name)
    if tasks:
        print(f"Tasks for session: {session_name}")
        print(f"=" * 60)
        for t in tasks:
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "assigned": "📋",
            }.get(t["status"].lower(), "❓")
            print(f"{status_icon} [{t['id']}] {t['type']}: {t['description'][:50]}...")
            print(f"   Priority: {t['priority']} | Status: {t['status']}")
        print(f"=" * 60)
        print(f"Total: {len(tasks)} tasks")
    else:
        print(f"No tasks assigned to {session_name}")
    return tasks


def show_status():
    """Show overall task summary from sheet."""
    try:
        client = get_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        ws = spreadsheet.worksheet("DevTasks")
        rows = ws.get_all_values()

        if len(rows) < 2:
            print("No tasks in sheet")
            return

        statuses = {}
        types = {}
        for row in rows[1:]:
            if len(row) > 4:
                status = row[4].lower() if row[4] else "unknown"
                task_type = row[2] if len(row) > 2 else "unknown"
                statuses[status] = statuses.get(status, 0) + 1
                types[task_type] = types.get(task_type, 0) + 1

        print("DevTasks Summary")
        print("=" * 40)
        print("\nBy Status:")
        for status, count in sorted(statuses.items()):
            icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}.get(
                status, "❓"
            )
            print(f"  {icon} {status}: {count}")

        print("\nBy Type:")
        for t, count in sorted(types.items()):
            print(f"  - {t}: {count}")

        print(f"\nTotal: {len(rows) - 1} tasks")
        print("=" * 40)

    except Exception as e:
        print(f"Error getting status: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "pull":
        if len(sys.argv) < 3:
            print("Usage: sheet_task_cli.py pull <session_name>")
            sys.exit(1)
        pull_task(sys.argv[2])

    elif command == "complete":
        if len(sys.argv) < 3:
            print("Usage: sheet_task_cli.py complete <task_id> [note]")
            sys.exit(1)
        note = sys.argv[3] if len(sys.argv) > 3 else None
        complete_task(sys.argv[2], note)

    elif command == "fail":
        if len(sys.argv) < 3:
            print("Usage: sheet_task_cli.py fail <task_id> [reason]")
            sys.exit(1)
        reason = sys.argv[3] if len(sys.argv) > 3 else None
        fail_task(sys.argv[2], reason)

    elif command == "list":
        if len(sys.argv) < 3:
            print("Usage: sheet_task_cli.py list <session_name>")
            sys.exit(1)
        list_tasks(sys.argv[2])

    elif command == "status":
        show_status()

    elif command == "assign":
        if len(sys.argv) < 4:
            print("Usage: sheet_task_cli.py assign <task_id> <session_name>")
            sys.exit(1)
        assign_task_to_session(sys.argv[2], sys.argv[3])
        print(f"Task {sys.argv[2]} assigned to {sys.argv[3]}")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
