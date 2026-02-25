#!/usr/bin/env python3
"""
Clean up redundant worksheets in Google Sheet
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
    print("CLEANING UP GOOGLE SHEET")
    print("=" * 70)
    print()

    # Delete redundant worksheets
    worksheets_to_delete = ['groups', 'Sheet1']

    for ws_name in worksheets_to_delete:
        try:
            ws = spreadsheet.worksheet(ws_name)
            spreadsheet.del_worksheet(ws)
            print(f"✓ Deleted '{ws_name}' worksheet")
        except Exception as e:
            print(f"  '{ws_name}' - {e}")

    print()
    print("Remaining worksheets:")
    for ws in spreadsheet.worksheets():
        print(f"  • {ws.title}")

    print()
    print("=" * 70)
    print("✅ Sheet cleaned up!")
    print("=" * 70)
    print()
    print("Main worksheets to use:")
    print("  1. Tab Groups - All your tab groups with status tracking")
    print("  2. Tabs - Individual tabs with full URLs")
    print("  3. Conversations - Perplexity conversation URLs")
    print("  4. Projects - Top-level project organization")
    print()

if __name__ == "__main__":
    main()
