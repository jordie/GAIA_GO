#!/usr/bin/env python3
"""
Update tab group names in Google Sheet to more descriptive names
"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime

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

    # Mapping of old names to new names
    name_mappings = {
        'this is...': 'School - Ezana Assignments',
        'find out...': 'Phone Plans - AT&T Research',
        'pull out...': 'Healthcare - Stanford',
        'try to...': 'Real Estate - Alameda Property',
        'my Name:...': 'Water Damage - Unit 8 Repairs',
        'get all...': 'Task Tracking - Javier',
        'find health...': 'Health Insurance - Covered CA'
    }

    # Update both worksheets
    for ws_name in ['Tab Groups', 'groups']:
        try:
            ws = spreadsheet.worksheet(ws_name)
            all_data = ws.get_all_values()

            print(f"Updating {ws_name}...")

            for row_num, row in enumerate(all_data[1:], 2):  # Skip header
                if len(row) > 2:
                    old_name = row[2]  # Column C (Group Name)

                    if old_name in name_mappings:
                        new_name = name_mappings[old_name]

                        # Update Group Name (column 3)
                        ws.update_cell(row_num, 3, new_name)

                        # Update Last Updated (column 14)
                        ws.update_cell(row_num, 14, datetime.now().strftime('%Y-%m-%d %H:%M'))

                        print(f"  ✓ Row {row_num}: '{old_name}' → '{new_name}'")

        except Exception as e:
            print(f"Error updating {ws_name}: {e}")

    print()
    print("✅ Done! Updated tab group names in Google Sheet")
    print()
    print("New names:")
    for old, new in name_mappings.items():
        print(f"  • {new}")

if __name__ == "__main__":
    main()
