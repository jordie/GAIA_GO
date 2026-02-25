#!/usr/bin/env python3
"""
Live status monitor for Ethiopia project
"""

import time
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime


def get_progress():
    """Get current progress from Google Sheet."""

    sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"

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
    ws = spreadsheet.worksheet("Tab Groups")

    all_data = ws.get_all_records()
    ethiopia_groups = [g for g in all_data if g.get('Project ID') == 'P002']

    completed = []
    in_progress = []
    pending = []

    for group in ethiopia_groups:
        name = group.get('Group Name')
        url = group.get('Main Perplexity URL', '')
        status = group.get('Status', 'pending')

        if url and url.strip():
            completed.append(name)
        elif status == 'in-progress':
            in_progress.append(name)
        else:
            pending.append(name)

    return {
        'total': len(ethiopia_groups),
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'progress_pct': (len(completed) / len(ethiopia_groups) * 100) if ethiopia_groups else 0
    }


def print_status(progress):
    """Print formatted status."""

    print("\n" + "="*80)
    print("ETHIOPIA PROJECT - LIVE STATUS")
    print("="*80)
    print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n📊 Progress: {len(progress['completed'])}/{progress['total']} topics ({progress['progress_pct']:.0f}%)")

    if progress['completed']:
        print(f"\n✅ Completed ({len(progress['completed'])}):")
        for topic in progress['completed']:
            print(f"   • {topic}")

    if progress['in_progress']:
        print(f"\n⏳ In Progress ({len(progress['in_progress'])}):")
        for topic in progress['in_progress']:
            print(f"   • {topic}")

    if progress['pending']:
        print(f"\n○ Pending ({len(progress['pending'])}):")
        for topic in progress['pending'][:3]:  # Show first 3
            print(f"   • {topic}")
        if len(progress['pending']) > 3:
            print(f"   ... and {len(progress['pending']) - 3} more")

    # Estimate remaining time
    if progress['completed']:
        avg_time_per_topic = 15  # ~15 minutes per topic with delays
        remaining = progress['total'] - len(progress['completed'])
        est_minutes = remaining * avg_time_per_topic

        print(f"\n⏱️  Estimated: ~{est_minutes} minutes remaining")

    print("\n" + "="*80)


def monitor_continuously(interval=60):
    """Monitor progress continuously."""

    print("Starting live monitoring...")
    print(f"Checking every {interval} seconds")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            progress = get_progress()
            print_status(progress)

            # Check if complete
            if len(progress['completed']) == progress['total']:
                print("\n🎉 ALL TOPICS COMPLETE!")
                print("\nNext steps:")
                print("1. Review Google Sheet for all conversation URLs")
                print("2. Read compiled results in Google Doc")
                print("3. Evaluate research quality")
                print("\nExiting monitor...")
                break

            print(f"\nNext check in {interval} seconds...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--continuous':
        monitor_continuously()
    else:
        # Single check
        progress = get_progress()
        print_status(progress)
