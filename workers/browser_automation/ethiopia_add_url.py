#!/usr/bin/env python3
"""
Quick script to add Perplexity conversation URLs to Ethiopia tab groups
"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime
import sys


def add_url_to_group(group_name_partial, conversation_url):
    """Add Perplexity URL to a tab group."""

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
    ws_tab_groups = spreadsheet.worksheet("Tab Groups")

    # Find the tab group
    all_data = ws_tab_groups.get_all_records()
    ethiopia_groups = [g for g in all_data if g.get('Project ID') == 'P002']

    for group in ethiopia_groups:
        group_name = group.get('Group Name', '')

        if group_name_partial.lower() in group_name.lower():
            # Find row number
            all_values = ws_tab_groups.get_all_values()

            for row_num, row in enumerate(all_values[1:], 2):  # Skip header
                if row[0] == group.get('Group ID'):
                    # Update Main Perplexity URL (column I)
                    ws_tab_groups.update_cell(row_num, 9, conversation_url)

                    # Update Status
                    ws_tab_groups.update_cell(row_num, 5, "in-progress")

                    # Update Last Updated
                    ws_tab_groups.update_cell(row_num, 14, datetime.now().strftime('%Y-%m-%d %H:%M'))

                    print(f"✓ Added URL to '{group_name}'")
                    return True

    print(f"✗ Could not find tab group matching '{group_name_partial}'")
    return False


def list_pending():
    """List pending Ethiopia tab groups."""

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
    ws_tab_groups = spreadsheet.worksheet("Tab Groups")

    all_data = ws_tab_groups.get_all_records()
    ethiopia_groups = [g for g in all_data if g.get('Project ID') == 'P002']

    print("="*80)
    print("ETHIOPIA PROJECT - PENDING RESEARCH")
    print("="*80)
    print()

    for i, group in enumerate(ethiopia_groups, 1):
        group_name = group.get('Group Name')
        status = group.get('Status')
        has_url = bool(group.get('Main Perplexity URL'))

        status_icon = "✓" if has_url else "○"
        print(f"{status_icon} [{i}] {group_name}")
        if has_url:
            print(f"      URL: {group.get('Main Perplexity URL')}")
        print()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} list")
        print(f"  {sys.argv[0]} add '<group_name_part>' '<perplexity_url>'")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} list")
        print(f"  {sys.argv[0]} add 'Flights' 'https://www.perplexity.ai/search/...'")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'list':
        list_pending()
    elif command == 'add':
        if len(sys.argv) < 4:
            print("Error: Need group name and URL")
            sys.exit(1)

        group_name = sys.argv[2]
        url = sys.argv[3]
        add_url_to_group(group_name, url)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
