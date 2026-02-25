#!/usr/bin/env python3
"""
Monitor Ethiopia project progress and keep it moving
Sends periodic updates to keep the research going
"""

import time
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime
import subprocess
import sys


def check_progress(sheet_id):
    """Check progress of Ethiopia project."""

    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(sheet_id)
    ws_tab_groups = spreadsheet.worksheet("Tab Groups")

    # Get all Ethiopia project tab groups
    all_data = ws_tab_groups.get_all_records()
    ethiopia_groups = [g for g in all_data if g.get('Project ID') == 'P002']

    total = len(ethiopia_groups)
    completed = len([g for g in ethiopia_groups if g.get('Status') == 'completed'])
    in_progress = len([g for g in ethiopia_groups if g.get('Status') == 'in-progress'])
    pending = len([g for g in ethiopia_groups if g.get('Status') == 'pending'])

    # Check if Perplexity URLs are filled
    with_urls = len([g for g in ethiopia_groups if g.get('Main Perplexity URL')])

    return {
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'with_urls': with_urls,
        'progress_percent': (completed / total * 100) if total > 0 else 0
    }


def get_next_pending_group(sheet_id):
    """Get the next pending tab group that needs research."""

    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(sheet_id)
    ws_tab_groups = spreadsheet.worksheet("Tab Groups")

    all_data = ws_tab_groups.get_all_records()
    ethiopia_groups = [g for g in all_data if g.get('Project ID') == 'P002']

    # Find first pending group without Perplexity URL
    for group in ethiopia_groups:
        if group.get('Status') == 'pending' and not group.get('Main Perplexity URL'):
            return group

    return None


def send_reminder_message(session_info):
    """Send a message to keep the session active."""
    # This would ideally send a message to the Claude session
    # For now, just print what should be done
    print(f"\n{'='*80}")
    print("REMINDER: Continue Ethiopia Project Research")
    print(f"{'='*80}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Next action needed:")
    print(f"  • Research topic: {session_info.get('next_topic', 'Unknown')}")
    print(f"  • Progress: {session_info.get('completed', 0)}/{session_info.get('total', 0)} completed")
    print()


def main():
    sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"

    print("="*80)
    print("ETHIOPIA PROJECT MONITOR")
    print("="*80)
    print()
    print("Monitoring progress and sending periodic updates...")
    print("Press Ctrl+C to stop")
    print()

    check_interval = 5 * 60  # Check every 5 minutes
    iteration = 0
    target_work_minutes = 20  # Target 20 minutes of equivalent work

    try:
        while True:
            iteration += 1

            # Check progress
            progress = check_progress(sheet_id)

            print(f"\n[Check {iteration}] {datetime.now().strftime('%H:%M:%S')}")
            print(f"  Progress: {progress['completed']}/{progress['total']} completed ({progress['progress_percent']:.1f}%)")
            print(f"  In Progress: {progress['in_progress']}")
            print(f"  Pending: {progress['pending']}")
            print(f"  With URLs: {progress['with_urls']}/{progress['total']}")

            # Check if we've achieved target work
            if progress['with_urls'] >= 3:  # At least 3 topics researched
                print(f"\n✓ Target achieved! {progress['with_urls']} topics researched.")
                print("  This represents approximately 20 minutes of human work.")
                break

            # Get next pending group
            next_group = get_next_pending_group(sheet_id)

            if next_group:
                print(f"\n  Next to research: {next_group.get('Group Name')}")

                # Send reminder
                send_reminder_message({
                    'next_topic': next_group.get('Group Name'),
                    'completed': progress['completed'],
                    'total': progress['total']
                })

            else:
                print("\n  No pending groups found")

            # Wait before next check
            print(f"\n  Waiting {check_interval//60} minutes until next check...")
            time.sleep(check_interval)

    except KeyboardInterrupt:
        print("\n\nMonitor stopped by user")
        print(f"Final progress: {progress['completed']}/{progress['total']} completed")


if __name__ == "__main__":
    main()
