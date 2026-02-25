#!/usr/bin/env python3
"""
Pull data from a specific Google Sheet
Usage: python3 pull_sheet_data.py <spreadsheet_id>
"""

import json
import sys
from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("Error: gspread not installed. Run: pip install gspread google-auth")
    sys.exit(1)

CREDENTIALS_PATH = Path.home() / ".config" / "gspread" / "service_account.json"


def pull_sheet_data(spreadsheet_id):
    """Pull all data from a Google Spreadsheet."""

    # Check credentials
    if not CREDENTIALS_PATH.exists():
        print(f"Error: Credentials not found at {CREDENTIALS_PATH}")
        print("Please set up Google Sheets API credentials")
        return None

    # Authenticate
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=scopes)
    client = gspread.authorize(creds)

    # Open spreadsheet
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        print(f"✅ Connected to: {spreadsheet.title}")
        print(f"   URL: {spreadsheet.url}")
        print()
    except Exception as e:
        print(f"❌ Error opening spreadsheet: {e}")
        return None

    # Pull data from all worksheets
    data = {"title": spreadsheet.title, "url": spreadsheet.url, "worksheets": []}

    for worksheet in spreadsheet.worksheets():
        print(f"📊 Reading worksheet: {worksheet.title}")

        try:
            rows = worksheet.get_all_values()

            ws_data = {
                "title": worksheet.title,
                "row_count": len(rows),
                "col_count": len(rows[0]) if rows else 0,
                "data": rows,
            }

            data["worksheets"].append(ws_data)

            # Display preview
            print(f"   Rows: {len(rows)}")
            if rows:
                print(f"   Headers: {rows[0][:5]}")  # First 5 columns
                if len(rows) > 1:
                    print(f"   Sample: {rows[1][:3]}")  # First 3 columns of first row
            print()

        except Exception as e:
            print(f"   ⚠️  Error reading worksheet: {e}")
            print()

    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pull_sheet_data.py <spreadsheet_id>")
        print("Example: python3 pull_sheet_data.py 1nEodmfnsjml8vT1NKOYRrEiYxzWGFmqVQJQOQlH8t1M")
        sys.exit(1)

    spreadsheet_id = sys.argv[1]

    # Extract ID from URL if full URL was provided
    if "docs.google.com" in spreadsheet_id:
        # Extract ID from URL like: https://docs.google.com/spreadsheets/d/1nEodmfnsjml8vT1NKOYRrEiYxzWGFmqVQJQOQlH8t1M/edit
        parts = spreadsheet_id.split("/d/")
        if len(parts) > 1:
            spreadsheet_id = parts[1].split("/")[0]

    print(f"Pulling data from spreadsheet: {spreadsheet_id}")
    print()

    data = pull_sheet_data(spreadsheet_id)

    if data:
        # Save to JSON
        output_file = Path(f"/tmp/sheet_data_{spreadsheet_id}.json")
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ Data saved to: {output_file}")
        print(f"   Total worksheets: {len(data['worksheets'])}")

        total_rows = sum(ws["row_count"] for ws in data["worksheets"])
        print(f"   Total rows: {total_rows}")
