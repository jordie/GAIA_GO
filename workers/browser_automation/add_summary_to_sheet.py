#!/usr/bin/env python3
"""
Add Ethiopia project summary to Google Sheet as a new tab
"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime


def add_summary_tab():
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

    print("Creating 'Ethiopia Trip Summary' worksheet...")

    # Create or clear worksheet
    try:
        ws = spreadsheet.worksheet("Ethiopia Trip Summary")
        ws.clear()
    except:
        ws = spreadsheet.add_worksheet("Ethiopia Trip Summary", rows=100, cols=10)

    # Summary content
    summary_data = [
        ["ETHIOPIA FAMILY TRIP - AUTOMATION SUMMARY", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["PROJECT OVERVIEW", "", "", "", "", "", "", "", "", ""],
        ["Project ID:", "P002", "", "", "", "", "", "", "", ""],
        ["Project Name:", "Ethiopia Family Trip - June 2026", "", "", "", "", "", "", "", ""],
        ["Status:", "🤖 FULLY AUTOMATED - Running", "", "", "", "", "", "", "", ""],
        ["Created:", datetime.now().strftime('%Y-%m-%d'), "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["TRIP DETAILS", "", "", "", "", "", "", "", "", ""],
        ["Family Members:", "6 people", "", "", "", "", "", "", "", ""],
        ["", "• Yordanos Girmay (47)", "", "", "", "", "", "", "", ""],
        ["", "• Helen Atsibha (46)", "", "", "", "", "", "", "", ""],
        ["", "• Sara Girmay (13)", "", "", "", "", "", "", "", ""],
        ["", "• Ezana Girmay (12)", "", "", "", "", "", "", "", ""],
        ["", "• Eden Girmay (11)", "", "", "", "", "", "", "", ""],
        ["", "• Eden Girmay (6)", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Travel Dates:", "Mid-late June 2026 → Late July 2026", "", "", "", "", "", "", "", ""],
        ["Duration:", "1 month", "", "", "", "", "", "", "", ""],
        ["Special Trip:", "1 week to Tigray (Axum, Adigrat, Mekele)", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["RESEARCH TOPICS (7 Total)", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["#", "Topic", "Status", "AI System", "Description", "", "", "", "", ""],
        ["1", "Flights", "Automated", "Perplexity", "Best prices for family of 6, Bay Area to Addis Ababa", "", "", "", "", ""],
        ["2", "Hotels", "Automated", "Perplexity", "1-month family accommodation in Addis Ababa", "", "", "", "", ""],
        ["3", "Tigray Trip", "Automated", "Perplexity", "Week-long itinerary: Axum, Adigrat, Mekele", "", "", "", "", ""],
        ["4", "Activities", "Automated", "Perplexity", "Family-friendly experiences for ages 6-47", "", "", "", "", ""],
        ["5", "Documents", "Automated", "Perplexity", "Visas, passports, vaccinations, requirements", "", "", "", "", ""],
        ["6", "Budget", "Automated", "Perplexity", "Complete cost breakdown and tracking", "", "", "", "", ""],
        ["7", "Packing", "Automated", "Perplexity", "Comprehensive packing list for 1-month trip", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["AUTOMATION STATUS", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Main Automation:", "RUNNING (PID: 50474)", "", "", "", "", "", "", "", ""],
        ["Script:", "ethiopia_auto_submit.py", "", "", "", "", "", "", "", ""],
        ["Function:", "Opens Perplexity, submits prompts, captures URLs", "", "", "", "", "", "", "", ""],
        ["Rate Limiting:", "3-5 minutes between requests", "", "", "", "", "", "", "", ""],
        ["Estimated Time:", "2-3 hours for all 7 topics", "", "", "", "", "", "", "", ""],
        ["Log File:", "ethiopia_auto.log", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Progress Monitor:", "RUNNING (PID: 39035)", "", "", "", "", "", "", "", ""],
        ["Script:", "ethiopia_monitor.py", "", "", "", "", "", "", "", ""],
        ["Function:", "Checks progress every 5 minutes", "", "", "", "", "", "", "", ""],
        ["Target:", "3-4 topics (~20 min work equivalent)", "", "", "", "", "", "", "", ""],
        ["Log File:", "ethiopia_monitor.log", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["SAFETY FEATURES", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["✓", "Rate Limiting", "3-5 minute delays prevent API abuse", "", "", "", "", "", "", ""],
        ["✓", "Randomization", "Varies timing to appear human-like", "", "", "", "", "", "", ""],
        ["✓", "Error Handling", "Graceful failures, continues on error", "", "", "", "", "", "", ""],
        ["✓", "One at a Time", "No parallel request flooding", "", "", "", "", "", "", ""],
        ["✓", "Full Logging", "Complete audit trail of all actions", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["TIMELINE", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["T+0 min", "Automation started", "", "", "", "", "", "", "", ""],
        ["T+5 min", "First topic submitted to Perplexity", "", "", "", "", "", "", "", ""],
        ["T+20 min", "First topic complete + Sheet updated", "", "", "", "", "", "", "", ""],
        ["T+2-3 hours", "All 7 topics complete", "", "", "", "", "", "", "", ""],
        ["T+3 hours", "Results aggregated to document", "", "", "", "", "", "", "", ""],
        ["T+3 hours", "✅ Ready for human evaluation", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["WHAT YOU'LL GET", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["✓", "All 7 research topics completed via Perplexity", "", "", "", "", "", "", "", ""],
        ["✓", "Conversation URLs saved in Tab Groups worksheet", "", "", "", "", "", "", "", ""],
        ["✓", "Results compiled in ETHIOPIA_TRIP_RESEARCH.md", "", "", "", "", "", "", "", ""],
        ["✓", "Ready for your evaluation and decision-making", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["MONITORING", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Check Progress:", "python3 ethiopia_add_url.py list", "", "", "", "", "", "", "", ""],
        ["View Live Log:", "tail -f ethiopia_auto.log", "", "", "", "", "", "", "", ""],
        ["Check Processes:", "ps aux | grep ethiopia", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["NEXT STEPS (After Completion)", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["1.", "Review Tab Groups worksheet for all Perplexity URLs", "", "", "", "", "", "", "", ""],
        ["2.", "Read compiled document: ETHIOPIA_TRIP_RESEARCH.md", "", "", "", "", "", "", "", ""],
        ["3.", "Evaluate research quality and completeness", "", "", "", "", "", "", "", ""],
        ["4.", "Make decisions on flights, hotels, itinerary", "", "", "", "", "", "", "", ""],
        ["5.", "Create action items for bookings", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["🤖 SYSTEM IS FULLY AUTONOMOUS", "", "", "", "", "", "", "", "", ""],
        ["No intervention needed until completion (~2-3 hours)", "", "", "", "", "", "", "", "", ""],
    ]

    # Write data
    ws.update('A1', summary_data, value_input_option='USER_ENTERED')

    # Format header
    ws.format('A1:J1', {
        "backgroundColor": {"red": 0.2, "green": 0.5, "blue": 0.8},
        "textFormat": {"bold": True, "fontSize": 16, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "horizontalAlignment": "CENTER"
    })

    # Merge header
    ws.merge_cells('A1:J1')

    # Format section headers
    for row in [3, 9, 22, 33, 47, 57, 65, 70]:
        ws.format(f'A{row}:J{row}', {
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            "textFormat": {"bold": True, "fontSize": 12}
        })

    # Format checkmarks
    ws.format('A49:A53', {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0.7, "blue": 0}, "bold": True}
    })

    ws.format('A67:A70', {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0.7, "blue": 0}, "bold": True}
    })

    # Format topic table header
    ws.format('A24:E24', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    # Format final message
    ws.format('A81:J82', {
        "backgroundColor": {"red": 0.2, "green": 0.8, "blue": 0.2},
        "textFormat": {"bold": True, "fontSize": 14},
        "horizontalAlignment": "CENTER"
    })

    ws.merge_cells('A81:J81')
    ws.merge_cells('A82:J82')

    print(f"✓ Created 'Ethiopia Trip Summary' worksheet")
    print(f"  View: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")

    # Move to front
    try:
        worksheets = spreadsheet.worksheets()
        summary_ws = spreadsheet.worksheet("Ethiopia Trip Summary")
        index = next((i for i, w in enumerate(worksheets) if w.title == "Ethiopia Trip Summary"), None)

        if index and index > 0:
            # Move to position 2 (after Dashboard)
            new_order = [worksheets[0]] + [summary_ws] + worksheets[1:index] + worksheets[index+1:]
            spreadsheet.reorder_worksheets(new_order)
            print("✓ Moved to front (after Dashboard)")
    except Exception as e:
        print(f"Note: Could not reorder (not critical): {e}")


if __name__ == "__main__":
    add_summary_tab()
