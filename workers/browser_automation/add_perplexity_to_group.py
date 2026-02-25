#!/usr/bin/env python3
"""
Add Perplexity conversation URL to a tab group
"""

import asyncio
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime
import sys

async def add_conversation_to_group(group_name, perplexity_url, conversation_title=""):
    """Add a Perplexity conversation URL to a tab group in Google Sheets."""

    sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"

    # Connect to Google Sheets
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

    # Get Tab Groups worksheet
    ws_groups = spreadsheet.worksheet("Tab Groups")
    groups_data = ws_groups.get_all_records()

    # Find the group
    target_row = None
    for i, group in enumerate(groups_data, 2):  # Start at row 2 (after header)
        if group.get('Group Name', '') == group_name:
            target_row = i
            break

    if not target_row:
        print(f"❌ Tab group '{group_name}' not found")
        return

    # Update the Main Perplexity URL column (column I, index 9)
    ws_groups.update_cell(target_row, 9, perplexity_url)

    # Update Last Updated column
    ws_groups.update_cell(target_row, 14, datetime.now().strftime('%Y-%m-%d %H:%M'))

    print(f"✅ Updated '{group_name}' with Perplexity conversation:")
    print(f"   {perplexity_url}")
    if conversation_title:
        print(f"   Title: {conversation_title}")


async def list_groups():
    """List all tab groups."""

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
    ws_groups = spreadsheet.worksheet("Tab Groups")
    groups_data = ws_groups.get_all_records()

    print("=" * 70)
    print("TAB GROUPS")
    print("=" * 70)

    for i, group in enumerate(groups_data, 1):
        group_name = group.get('Group Name', '')
        source = group.get('Source Computer', 'Unknown')
        perp_url = group.get('Main Perplexity URL', '')

        print(f"\n{i}. {group_name}")
        print(f"   Source: {source}")
        print(f"   Perplexity URL: {perp_url if perp_url else 'None'}")


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} list")
        print(f"  {sys.argv[0]} add '<group_name>' '<perplexity_url>' ['title']")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} list")
        print(f"  {sys.argv[0]} add 'DENTAL-MEDI' 'https://www.perplexity.ai/search/...' 'Best Medi-Cal dentists'")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'list':
        await list_groups()
    elif command == 'add':
        if len(sys.argv) < 4:
            print("Error: Need group name and Perplexity URL")
            sys.exit(1)

        group_name = sys.argv[2]
        perp_url = sys.argv[3]
        title = sys.argv[4] if len(sys.argv) > 4 else ""

        await add_conversation_to_group(group_name, perp_url, title)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
