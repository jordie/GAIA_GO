#!/usr/bin/env python3
"""
Check what data is actually in the Google Sheet
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

    print("=" * 70)
    print("WORKSHEETS IN SPREADSHEET")
    print("=" * 70)
    for ws in spreadsheet.worksheets():
        print(f"- {ws.title} (ID: {ws.id}, Rows: {ws.row_count}, Cols: {ws.col_count})")
    print()

    # Check Tab Groups worksheet
    try:
        ws_groups = spreadsheet.worksheet("Tab Groups")
        print("=" * 70)
        print("TAB GROUPS WORKSHEET HEADERS")
        print("=" * 70)
        headers = ws_groups.row_values(1)
        for i, header in enumerate(headers, 1):
            print(f"Column {i}: {header}")
        print()

        print("=" * 70)
        print("TAB GROUPS DATA (First 10 rows)")
        print("=" * 70)
        all_values = ws_groups.get_all_values()
        for i, row in enumerate(all_values[:11], 1):  # Header + first 10 data rows
            if i == 1:
                print(f"Row {i} (HEADER): {row}")
            else:
                print(f"Row {i}: {row}")
        print()

        print(f"Total rows with data: {len(all_values)}")

    except Exception as e:
        print(f"Error reading Tab Groups worksheet: {e}")
        print()

    # Check Tabs worksheet
    try:
        ws_tabs = spreadsheet.worksheet("Tabs")
        print("=" * 70)
        print("TABS WORKSHEET")
        print("=" * 70)
        headers = ws_tabs.row_values(1)
        print(f"Headers: {headers}")
        all_values = ws_tabs.get_all_values()
        print(f"Total rows: {len(all_values)}")
        print()

    except Exception as e:
        print(f"Error reading Tabs worksheet: {e}")

if __name__ == "__main__":
    main()
