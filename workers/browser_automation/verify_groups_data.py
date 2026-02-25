#!/usr/bin/env python3
"""
Verify what's in the groups worksheet
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

    # Check the 'groups' worksheet (gid=1900642570)
    ws_groups = spreadsheet.worksheet("groups")

    print("=" * 70)
    print("GROUPS WORKSHEET - ALL DATA")
    print("=" * 70)
    all_values = ws_groups.get_all_values()

    for i, row in enumerate(all_values, 1):
        print(f"Row {i}: {row}")

    print()
    print(f"Total rows: {len(all_values)}")
    print()

    if len(all_values) > 1:
        print("Column 3 should be 'Group Name'. Let me check:")
        for i, row in enumerate(all_values[1:], 2):  # Skip header
            group_name = row[2] if len(row) > 2 else "MISSING"
            print(f"  Row {i}: {group_name}")

if __name__ == "__main__":
    main()
