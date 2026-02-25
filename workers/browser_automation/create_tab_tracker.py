#!/usr/bin/env python3
"""Create Tab Groups Tracker sheet using existing gspread setup"""

import asyncio
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import json


async def main():
    print("=" * 70)
    print("CREATING TAB GROUPS TRACKER SHEET")
    print("=" * 70)
    print()

    # Use existing credentials
    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"

    print(f"📄 Using credentials: {creds_path}")

    # Connect to Google Sheets
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    gc = gspread.authorize(creds)
    print("✓ Connected to Google Sheets\n")

    # Create the sheet
    print("📊 Creating 'Tab Groups Tracker' sheet...")

    try:
        spreadsheet = gc.create("Tab Groups Tracker")
        sheet_id = spreadsheet.id
        print(f"✓ Sheet created: {sheet_id}\n")

        # Get first worksheet
        ws = spreadsheet.sheet1
        ws.update_title("Tab Groups")

        # Set up headers
        headers = ["Group Name", "Color", "Tab Count", "Status", "Notes", "Last Updated"]
        ws.update('A1', [headers])

        # Format header row
        ws.format('A1:F1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1}
            }
        })

        # Get sheet URL
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

        print("=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        print()
        print(f"📊 Sheet URL: {sheet_url}")
        print(f"📋 Sheet ID: {sheet_id}")
        print()
        print("Next steps:")
        print("1. Open the sheet in your browser")
        print("2. Import your Comet tab groups data")
        print()

        # Save sheet ID for later use
        config = {"sheet_id": sheet_id, "sheet_url": sheet_url}
        with open("tab_tracker_config.json", "w") as f:
            json.dump(config, f, indent=2)

        print("💾 Sheet ID saved to: tab_tracker_config.json")

    except Exception as e:
        if "quota" in str(e).lower():
            print(f"❌ Storage quota exceeded: {e}")
            print("\nOptions:")
            print("1. Free up Google Drive storage")
            print("2. Use a different Google account")
            print("3. Delete old sheets")
        else:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
