#!/usr/bin/env python3
"""
Collect Perplexity conversation URLs from open tabs and update Google Sheet
"""

import subprocess
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime
import json
import re


def get_current_tab_url():
    """Get URL of current tab in Comet."""

    applescript = '''
tell application "Comet"
    get URL of active tab of window 1
end tell
'''

    result = subprocess.run(
        ['osascript', '-e', applescript],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return result.stdout.strip()
    return None


def next_tab():
    """Move to next tab."""
    subprocess.run(['osascript', '-e', '''
tell application "System Events"
    keystroke "]" using {command down, shift down}
end tell
'''], capture_output=True)


def update_sheet_with_url(topic_id, url):
    """Update Google Sheet with Perplexity URL."""

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

    all_data = ws.get_all_values()

    for row_num, row in enumerate(all_data[1:], 2):
        if row[0] == topic_id:
            # Update Perplexity URL (column 9)
            ws.update_cell(row_num, 9, url)

            # Update status
            ws.update_cell(row_num, 5, "completed")

            # Update timestamp
            ws.update_cell(row_num, 14, datetime.now().strftime('%Y-%m-%d %H:%M'))

            return True

    return False


def main():
    prompts_file = Path("ethiopia_prompts.json")

    with open(prompts_file) as f:
        data = json.load(f)

    topics = data['tab_groups']

    print("="*80)
    print("COLLECTING PERPLEXITY CONVERSATION URLs")
    print("="*80)
    print()
    print(f"Topics: {len(topics)}")
    print()
    print("Position browser on first Perplexity tab with responses")
    print()

    input("Press Enter to start collecting URLs...")

    collected = []

    for i, topic in enumerate(topics, 1):
        name = topic['name']
        topic_id = topic['id']

        print(f"\n[{i}/{len(topics)}] {name}")

        # Get current tab URL
        url = get_current_tab_url()

        if url and 'perplexity.ai/search/' in url:
            print(f"  ✅ URL: {url}")

            # Update Google Sheet
            success = update_sheet_with_url(topic_id, url)

            if success:
                print(f"  ✓ Updated Google Sheet")
                collected.append({'name': name, 'url': url})
            else:
                print(f"  ⚠️  Failed to update sheet")

        else:
            print(f"  ⚠️  Not a Perplexity conversation URL: {url}")

        # Move to next tab
        if i < len(topics):
            next_tab()
            import time
            time.sleep(1)

    print("\n" + "="*80)
    print(f"✅ COLLECTED {len(collected)}/{len(topics)} URLs")
    print("="*80)
    print()

    if collected:
        print("Updated in Google Sheet:")
        for item in collected:
            print(f"  • {item['name']}")
        print()

    print("View results:")
    print("  Google Sheet: https://docs.google.com/spreadsheets/d/1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q/edit")
    print()


if __name__ == "__main__":
    main()
