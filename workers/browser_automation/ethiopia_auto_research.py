#!/usr/bin/env python3
"""
Automated Ethiopia project research using Perplexity
"""

import asyncio
import json
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from browser_cli import ask_and_capture_with_polling
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime


async def research_tab_group(tab_group, index, total):
    """Research a single tab group topic."""

    print(f"\n{'='*80}")
    print(f"[{index}/{total}] RESEARCHING: {tab_group['name']}")
    print(f"{'='*80}\n")

    # Use Perplexity to research the prompt
    try:
        # The ask_and_capture_with_polling function handles:
        # 1. Opening Perplexity
        # 2. Submitting the question
        # 3. Waiting for response
        # 4. Capturing the conversation URL

        result = await ask_and_capture_with_polling(
            url="https://www.perplexity.ai",
            question=tab_group['prompt'],
            wait_before_asking=5  # Give Perplexity time to load
        )

        if result and 'conversation_url' in result:
            print(f"\n✓ Research complete for {tab_group['name']}")
            print(f"  Conversation URL: {result['conversation_url']}")
            return result['conversation_url']
        else:
            print(f"\n⚠ Could not capture conversation URL for {tab_group['name']}")
            return None

    except Exception as e:
        print(f"\n✗ Error researching {tab_group['name']}: {e}")
        return None


async def update_sheet_with_url(tab_group_id, conversation_url, sheet_id):
    """Update Google Sheet with Perplexity conversation URL."""

    try:
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

        # Find the row for this tab group
        all_data = ws_tab_groups.get_all_values()

        for row_num, row in enumerate(all_data[1:], 2):  # Skip header
            if row[0] == tab_group_id:  # Column A is Group ID
                # Update Main Perplexity URL (column I, index 9)
                ws_tab_groups.update_cell(row_num, 9, conversation_url)

                # Update Last Updated (column N, index 14)
                ws_tab_groups.update_cell(row_num, 14, datetime.now().strftime('%Y-%m-%d %H:%M'))

                # Update Status to in-progress
                ws_tab_groups.update_cell(row_num, 5, "in-progress")

                print(f"  ✓ Updated Google Sheet for {tab_group_id}")
                return True

        print(f"  ⚠ Could not find {tab_group_id} in Google Sheet")
        return False

    except Exception as e:
        print(f"  ✗ Error updating sheet: {e}")
        return False


async def main():
    sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"

    # Load prompts
    prompts_file = Path("ethiopia_prompts.json")

    if not prompts_file.exists():
        print("Error: ethiopia_prompts.json not found")
        print("Run setup_ethiopia_project.py first")
        sys.exit(1)

    with open(prompts_file) as f:
        data = json.load(f)

    tab_groups = data["tab_groups"]

    print("="*80)
    print("ETHIOPIA PROJECT - AUTOMATED RESEARCH")
    print("="*80)
    print()
    print(f"Total research topics: {len(tab_groups)}")
    print()
    print("This will:")
    print("  1. Send each prompt to Perplexity")
    print("  2. Capture conversation URLs")
    print("  3. Update Google Sheet with results")
    print()

    # Process each tab group
    completed = 0
    failed = 0

    for i, group in enumerate(tab_groups, 1):
        print(f"\nProcessing {i}/{len(tab_groups)}: {group['name']}")

        # Research the topic
        conversation_url = await research_tab_group(group, i, len(tab_groups))

        if conversation_url:
            # Update Google Sheet
            success = await update_sheet_with_url(group['id'], conversation_url, sheet_id)

            if success:
                completed += 1
            else:
                failed += 1

            # Wait between requests to avoid overwhelming Perplexity
            if i < len(tab_groups):
                wait_time = 30  # 30 seconds between requests
                print(f"\nWaiting {wait_time} seconds before next research topic...")
                await asyncio.sleep(wait_time)
        else:
            failed += 1

    print("\n" + "="*80)
    print("RESEARCH COMPLETE")
    print("="*80)
    print()
    print(f"Completed: {completed}/{len(tab_groups)}")
    print(f"Failed: {failed}/{len(tab_groups)}")
    print()
    print("Next: Review results in Google Sheet and aggregate into Google Doc")
    print(f"Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    print()


if __name__ == "__main__":
    asyncio.run(main())
