#!/usr/bin/env python3
"""
Check the 'groups' worksheet and sync data to it
"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path

def main():
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

    # Check the 'groups' worksheet
    ws_groups_old = spreadsheet.worksheet("groups")
    print("=" * 70)
    print("GROUPS WORKSHEET (old)")
    print("=" * 70)
    all_values = ws_groups_old.get_all_values()
    print(f"Total rows: {len(all_values)}")
    for i, row in enumerate(all_values[:5], 1):
        print(f"Row {i}: {row}")
    print()

    # Get data from Tab Groups worksheet
    ws_tab_groups = spreadsheet.worksheet("Tab Groups")
    tab_groups_data = ws_tab_groups.get_all_values()

    print("=" * 70)
    print("COPYING DATA FROM 'Tab Groups' TO 'groups'")
    print("=" * 70)

    # Clear and update the 'groups' worksheet
    ws_groups_old.clear()

    # Copy all data
    ws_groups_old.update('A1', tab_groups_data)

    # Format header
    ws_groups_old.format('A1:O1', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    print(f"✅ Copied {len(tab_groups_data)} rows to 'groups' worksheet")
    print()
    print("You can now view the data at:")
    print("https://docs.google.com/spreadsheets/d/1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q/edit?gid=1900642570")

if __name__ == "__main__":
    main()
