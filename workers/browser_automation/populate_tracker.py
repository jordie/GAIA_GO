#!/usr/bin/env python3
"""Add Tab Groups Tracker worksheet and populate with Comet data"""

import asyncio
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import json
import sys
import websockets


async def get_tab_groups():
    """Get tab groups from Comet browser."""
    ws_url = "ws://localhost:8765"

    try:
        ws = await websockets.connect(ws_url)

        # Wait for FULL_STATE
        async for message in ws:
            data = json.loads(message)
            if data.get("event") == "FULL_STATE":
                break

        # Send GET_TAB_GROUPS command
        cmd_id = "get-groups"
        await ws.send(json.dumps({
            "command": True,
            "id": cmd_id,
            "action": "GET_TAB_GROUPS",
            "params": {}
        }))

        # Wait for result
        async for message in ws:
            data = json.loads(message)
            if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
                groups = data["data"].get("result", [])

                # Get tabs for each group
                for group in groups:
                    cmd_id = f"get-tabs-{group['id']}"
                    await ws.send(json.dumps({
                        "command": True,
                        "id": cmd_id,
                        "action": "GET_TABS",
                        "params": {"groupId": group['id']}
                    }))

                    async for msg in ws:
                        d = json.loads(msg)
                        if d.get("event") == "COMMAND_RESULT" and d["data"].get("id") == cmd_id:
                            group['tabs'] = d["data"].get("result", [])
                            break

                await ws.close()
                return groups

        await ws.close()
        return []

    except Exception as e:
        print(f"Error getting tab groups: {e}")
        return []


async def main():
    print("=" * 70)
    print("ADDING TAB GROUPS TRACKER WORKSHEET")
    print("=" * 70)
    print()

    # Sheet ID for Architect Dashboard Testing System
    sheet_id = "12i2uO6-41uZdHl_a9BbhBHhR1qbNlAqOgH-CWQBz7rA"

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
    print("✓ Connected to Google Sheets\n")

    # Open spreadsheet
    spreadsheet = gc.open_by_key(sheet_id)
    print(f"✓ Opened: {spreadsheet.title}\n")

    # Check if Tab Groups Tracker worksheet exists
    try:
        ws = spreadsheet.worksheet("Tab Groups Tracker")
        print("📋 Found existing 'Tab Groups Tracker' worksheet")
        print("   Clearing and updating...\n")
        ws.clear()
    except:
        print("📋 Creating new 'Tab Groups Tracker' worksheet...\n")
        ws = spreadsheet.add_worksheet("Tab Groups Tracker", rows=100, cols=10)

    # Set up headers
    headers = ["Group Name", "Color", "Tab Count", "Status", "Tabs (URLs)", "Last Updated"]
    ws.update('A1', [headers])

    # Format header
    ws.format('A1:F1', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {
            "bold": True,
            "foregroundColor": {"red": 1, "green": 1, "blue": 1}
        }
    })

    print("✓ Headers created\n")

    # Get tab groups from Comet
    print("📚 Reading tab groups from Comet...")
    groups = await get_tab_groups()

    if not groups:
        print("⚠️  No tab groups found or browser not connected")
        print("\nMake sure:")
        print("1. Comet browser is running")
        print("2. Browser extension is active")
        print("3. WebSocket server is running on localhost:8765")
        return

    print(f"✓ Found {len(groups)} tab groups\n")

    # Populate data
    rows = []
    for group in groups:
        tab_count = len(group.get('tabs', []))
        tabs_urls = ", ".join([tab.get('url', '') for tab in group.get('tabs', [])[:3]])
        if tab_count > 3:
            tabs_urls += f" ... (+{tab_count - 3} more)"

        rows.append([
            group.get('title') or 'Untitled',
            group.get('color', 'grey'),
            tab_count,
            'active',
            tabs_urls,
            ''
        ])

    if rows:
        ws.update('A2', rows)
        print(f"✓ Added {len(rows)} tab groups\n")

    # Get URL
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={ws.id}"

    print("=" * 70)
    print("✅ SUCCESS!")
    print("=" * 70)
    print()
    print(f"📊 Worksheet: Tab Groups Tracker")
    print(f"📋 Sheet URL: {sheet_url}")
    print(f"📚 Tab Groups: {len(groups)}")
    print()

    # Show summary
    print("Tab Groups Summary:")
    print("-" * 70)
    for i, group in enumerate(groups, 1):
        print(f"{i}. {group.get('title', 'Untitled')} ({group.get('color', 'grey')}) - {len(group.get('tabs', []))} tabs")

    print()
    print("✓ All tab groups are now tracked in Google Sheets!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
