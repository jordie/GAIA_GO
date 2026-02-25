#!/usr/bin/env python3
"""List all Google Sheets and help clean up space"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime


def main():
    # Use existing credentials
    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"

    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    gc = gspread.authorize(creds)

    print("=" * 70)
    print("YOUR GOOGLE SHEETS")
    print("=" * 70)
    print()

    try:
        # List all spreadsheets
        sheets = gc.openall()

        print(f"Found {len(sheets)} sheets:\n")

        for i, sheet in enumerate(sheets, 1):
            print(f"{i}. {sheet.title}")
            print(f"   ID: {sheet.id}")
            print(f"   URL: https://docs.google.com/spreadsheets/d/{sheet.id}/edit")
            print()

        if sheets:
            print("\nTo use an existing sheet:")
            print("1. Pick a sheet from above")
            print("2. I can populate it with your tab groups data")
            print()
            print("Or to free up space:")
            print("1. Delete sheets you don't need at drive.google.com")
            print("2. Run this script again to create new sheet")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
