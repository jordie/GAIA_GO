#!/usr/bin/env python3
"""Add 'groups' worksheet with tab group details"""

import asyncio
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import json
import websockets
from datetime import datetime


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

        # Get tab groups
        cmd_id = "get-groups"
        await ws.send(json.dumps({
            "command": True,
            "id": cmd_id,
            "action": "GET_TAB_GROUPS",
            "params": {}
        }))

        async for message in ws:
            data = json.loads(message)
            if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
                groups = data["data"].get("result", [])
                break

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

    except Exception as e:
        print(f"Error getting tab groups: {e}")
        return []


async def main():
    print("=" * 70)
    print("ADDING 'groups' WORKSHEET")
    print("=" * 70)
    print()

    # Sheet ID
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
    print("✓ Connected to Google Sheets\n")

    # Open spreadsheet
    spreadsheet = gc.open_by_key(sheet_id)
    print(f"✓ Opened: {spreadsheet.title}\n")

    # Check if 'groups' worksheet exists
    try:
        ws = spreadsheet.worksheet("groups")
        print("📋 Found existing 'groups' worksheet")
        print("   Clearing and updating...\n")
        ws.clear()
    except:
        print("📋 Creating new 'groups' worksheet...\n")
        ws = spreadsheet.add_worksheet("groups", rows=100, cols=10)

    # Set up headers
    headers = ["Group Name", "Color", "Number of Tabs", "URLs (comma-delimited)", "Last Updated"]
    ws.update(range_name='A1', values=[headers])

    # Format header
    ws.format('A1:E1', {
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
        print("⚠️  No tab groups found")
        return

    print(f"✓ Found {len(groups)} tab groups\n")

    # Populate data
    rows = []
    for group in groups:
        tabs = group.get('tabs', [])
        tab_count = len(tabs)

        # Create comma-delimited URLs
        urls = ", ".join([tab.get('url', '') for tab in tabs])

        rows.append([
            group.get('title') or 'Untitled',
            group.get('color', 'grey'),
            tab_count,
            urls,
            datetime.now().strftime('%Y-%m-%d %H:%M')
        ])

    if rows:
        ws.update(range_name='A2', values=rows)
        print(f"✓ Added {len(rows)} tab groups\n")

    # Auto-resize columns
    ws.columns_auto_resize(0, 4)

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={ws.id}"

    print("=" * 70)
    print("✅ SUCCESS!")
    print("=" * 70)
    print()
    print(f"📊 Worksheet: groups")
    print(f"📋 URL: {sheet_url}")
    print(f"📚 Tab Groups: {len(groups)}")
    print()

    # Show summary
    print("Tab Groups Added:")
    print("-" * 70)
    for i, group in enumerate(groups, 1):
        title = group.get('title', 'Untitled')
        color = group.get('color', 'grey')
        count = len(group.get('tabs', []))
        print(f"{i}. {title} ({color}) - {count} tabs")

    print()
    print("✓ Tab group details with comma-delimited URLs added!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
