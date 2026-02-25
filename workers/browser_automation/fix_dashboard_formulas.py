#!/usr/bin/env python3
"""
Fix the formulas in Dashboard to work properly
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

    ws_dashboard = spreadsheet.worksheet("Dashboard")

    print("Fixing formulas in Dashboard...")

    # Fix formulas using USER_ENTERED value input option
    formulas = [
        ("B4", "=COUNTA('Tab Groups'!C2:C100)"),
        ("B5", "=COUNTA(Tabs!D2:D1000)"),
        ("B6", '=COUNTIF(\'Tab Groups\'!O2:O100,"Mac Mini (Gezabase)")'),
        ("B7", '=COUNTIF(\'Tab Groups\'!O2:O100,"jgirmay@Helus-Air.attlocal.net")')
    ]

    for cell, formula in formulas:
        ws_dashboard.update(cell, [[formula]], value_input_option='USER_ENTERED')
        print(f"  ✓ Updated {cell}")

    print()
    print("✅ Formulas fixed! The Dashboard now shows live counts.")
    print()

if __name__ == "__main__":
    main()
