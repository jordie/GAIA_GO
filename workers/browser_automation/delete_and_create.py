#!/usr/bin/env python3
"""Delete an old sheet and create Tab Groups Tracker"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 delete_and_create.py <sheet_number_to_delete>")
        print()
        print("Your sheets:")
        print("1. Pharma - Day to Day Operation")
        print("2. Peralta Services - Property Mangement")
        print("3. Selam Pharmacy Prospect Lists")
        print("4. Architect Dashboard Testing System")
        print("5. BasisEdu App Management")
        print("6. Total Properties: Peralta Services Source Documents")
        print("7. Real Estate Income and Expenses")
        print("8. 1321 Perlata Rent Roll")
        print("9. P&L Perlata.xlsx")
        print("10. Collections Calculations")
        print("11. All properties Calculations")
        print("12. Selam_Pharmacy_Prospect_Tracker")
        print()
        print("Example: python3 delete_and_create.py 12")
        sys.exit(1)

    sheet_num = int(sys.argv[1])

    sheet_ids = [
        "1ccQiLwbpKCKYTjPFjpq-ZS-bgNm4yOWN3-Z6ibDMWGQ",  # 1
        "1anX4P87uB0l5efatfu3SofVM9zHtOCWWxn395HozBP0",  # 2
        "1nEodmfnsjml8vT1NKOYRrEiYxzWGFmqVQJQOQlH8t1M",  # 3
        "12i2uO6-41uZdHl_a9BbhBHhR1qbNlAqOgH-CWQBz7rA",  # 4
        "1wvgaIsF7gyq5Z-Ld9sgjtvuBNMlwI0O05tfjX7BKOW4",  # 5
        "17lGq_rXxHXeXOxazbDILDCwmp8i6DdUpevmaOdWjRqo",  # 6
        "1GgeHe_vStHThqWzUtzz4yB8lB5YzcTO9PNVjzPOlvaA",  # 7
        "139QdbDOkZwUKXpCIk4GXYe26Pev5k2LCoBppC62EIr0",  # 8
        "13JdCVi2fHWpFz8QJIez0C79Ui2NlP8WiOur9HDXR7R4",  # 9
        "1bmEPKJSFS7uhHJT3ECySVJbWwj8VbCoJnY_W8P-tNJA",  # 10
        "1_Qri6jaYDzKCyscAqjPyDu4VDbpoK8GaEZNZYlVzzGo",  # 11
        "1Za2M2c7RiA8xnGY_KiTffB9qTIPLkGUNCqI-hlakxxs",  # 12
    ]

    sheet_names = [
        "Pharma - Day to Day Operation",
        "Peralta Services - Property Mangement",
        "Selam Pharmacy Prospect Lists",
        "Architect Dashboard Testing System",
        "BasisEdu App Management",
        "Total Properties: Peralta Services Source Documents",
        "Real Estate Income and Expenses",
        "1321 Perlata Rent Roll",
        "P&L Perlata.xlsx",
        "Collections Calculations",
        "All properties Calculations",
        "Selam_Pharmacy_Prospect_Tracker",
    ]

    if sheet_num < 1 or sheet_num > len(sheet_ids):
        print(f"Invalid sheet number. Choose 1-{len(sheet_ids)}")
        sys.exit(1)

    # Connect
    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    gc = gspread.authorize(creds)

    # Delete old sheet
    sheet_id_to_delete = sheet_ids[sheet_num - 1]
    sheet_name_to_delete = sheet_names[sheet_num - 1]

    print(f"Deleting: {sheet_name_to_delete}")
    print(f"ID: {sheet_id_to_delete}")
    print()

    confirm = input("Are you sure? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Cancelled")
        sys.exit(0)

    try:
        spreadsheet = gc.open_by_key(sheet_id_to_delete)
        gc.del_spreadsheet(sheet_id_to_delete)
        print(f"✓ Deleted: {sheet_name_to_delete}\n")
    except Exception as e:
        print(f"Error deleting: {e}\n")

    # Create new sheet
    print("Creating 'Tab Groups Tracker'...")

    try:
        spreadsheet = gc.create("Tab Groups Tracker")
        sheet_id = spreadsheet.id

        # Setup
        ws = spreadsheet.sheet1
        ws.update_title("Tab Groups")

        headers = ["Group Name", "Color", "Tab Count", "Status", "Notes", "Last Updated"]
        ws.update('A1', [headers])

        ws.format('A1:F1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1}
            }
        })

        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

        print(f"✓ Created: Tab Groups Tracker")
        print(f"📊 URL: {sheet_url}")
        print(f"📋 ID: {sheet_id}")

    except Exception as e:
        print(f"Error creating: {e}")


if __name__ == "__main__":
    main()
