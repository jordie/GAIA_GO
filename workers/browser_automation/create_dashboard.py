#!/usr/bin/env python3
"""
Create a useful Dashboard worksheet with actionable views
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

    # Create Dashboard worksheet
    try:
        ws_dashboard = spreadsheet.worksheet("Dashboard")
        ws_dashboard.clear()
    except:
        ws_dashboard = spreadsheet.add_worksheet("Dashboard", rows=100, cols=10)

    print("Creating Dashboard...")

    # Dashboard header
    dashboard_data = [
        ["TAB GROUPS DASHBOARD", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["SUMMARY", "", "", "", "QUICK ACTIONS", "", "", "", "", ""],
        ["Total Tab Groups:", "=COUNTA('Tab Groups'!C2:C100)", "", "", "🔗 Open Tab Groups worksheet", "", "", "", "", ""],
        ["Total Tabs:", "=COUNTA(Tabs!D2:D1000)", "", "", "🔗 Open Tabs worksheet", "", "", "", "", ""],
        ["Mac Mini Groups:", "=COUNTIF('Tab Groups'!O2:O100,\"Mac Mini (Gezabase)\")", "", "", "🔗 Open Conversations worksheet", "", "", "", "", ""],
        ["Pink Laptop Groups:", "=COUNTIF('Tab Groups'!O2:O100,\"jgirmay@Helus-Air.attlocal.net\")", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["BY TOPIC", "", "", "", "STATUS", "", "", "", "", ""],
        ["Group Name", "Computer", "Tab Count", "Perplexity URL", "Status", "Progress %", "Last Updated", "", "", ""],
    ]

    # Add current tab groups data
    ws_groups = spreadsheet.worksheet("Tab Groups")
    groups_data = ws_groups.get_all_records()

    for group in groups_data:
        group_name = group.get('Group Name', '')
        source = group.get('Source Computer', '')
        tab_count = group.get('Tab Count', 0)
        perp_url = group.get('Main Perplexity URL', '')
        status = group.get('Status', 'pending')
        progress = group.get('Progress %', 0)
        updated = group.get('Last Updated', '')

        # Shorten computer name for display
        source_short = "Mac Mini" if "Mac Mini" in source else "Pink Laptop" if "jgirmay" in source else source

        dashboard_data.append([
            group_name,
            source_short,
            tab_count,
            perp_url if perp_url else "No conversation yet",
            status,
            progress,
            updated,
            "", "", ""
        ])

    # Write to Dashboard
    ws_dashboard.update('A1', dashboard_data)

    # Format header
    ws_dashboard.format('A1:J1', {
        "backgroundColor": {"red": 0.2, "green": 0.5, "blue": 0.8},
        "textFormat": {"bold": True, "fontSize": 16, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "horizontalAlignment": "CENTER"
    })

    # Format section headers
    ws_dashboard.format('A3:A3', {
        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
        "textFormat": {"bold": True, "fontSize": 12}
    })

    ws_dashboard.format('A9:J9', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    # Format data columns
    ws_dashboard.format('A10:J100', {
        "textFormat": {"fontSize": 10}
    })

    # Merge header cell
    ws_dashboard.merge_cells('A1:J1')

    # Set column widths
    ws_dashboard.update('A1', [["TAB GROUPS DASHBOARD 📊"]])

    print("✓ Dashboard created")
    print()

    # Move Dashboard to be first worksheet
    try:
        ws_list = spreadsheet.worksheets()
        dashboard_index = next((i for i, ws in enumerate(ws_list) if ws.title == "Dashboard"), None)
        if dashboard_index is not None and dashboard_index > 0:
            ws_dashboard = ws_list[dashboard_index]
            spreadsheet.reorder_worksheets([ws_dashboard] + ws_list[:dashboard_index] + ws_list[dashboard_index+1:])
            print("✓ Moved Dashboard to first position")
    except Exception as e:
        print(f"Note: Could not reorder (not critical): {e}")

    print()
    print("=" * 70)
    print("✅ DASHBOARD CREATED!")
    print("=" * 70)
    print()
    print("Open the sheet and click the 'Dashboard' tab for:")
    print("  • Summary statistics")
    print("  • All tab groups organized by topic")
    print("  • Quick links to Perplexity conversations")
    print("  • Status tracking at a glance")
    print()
    print(f"📊 View Dashboard: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    print()

if __name__ == "__main__":
    main()
