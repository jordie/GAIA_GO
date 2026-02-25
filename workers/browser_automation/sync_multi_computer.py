#!/usr/bin/env python3
"""
Multi-computer sync for tab groups
Adds 'Source Computer' column and merges data from different machines
"""

import asyncio
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import json
import websockets
from datetime import datetime
import socket
import os


def get_computer_name():
    """Get a friendly name for this computer."""
    # Try to get hostname
    hostname = socket.gethostname()

    # Check for known machines
    if 'mac-mini' in hostname.lower() or 'gezabase' in hostname.lower():
        return "Mac Mini (Gezabase)"
    elif 'macbook' in hostname.lower():
        # Check if it's the pink laptop
        return "Pink MacBook"
    else:
        # Use hostname or username@hostname
        user = os.environ.get('USER', 'unknown')
        return f"{user}@{hostname}"


async def get_tab_groups_with_details():
    """Get all tab groups with full tab details from Comet."""
    ws_url = "ws://localhost:8765"

    try:
        ws = await websockets.connect(ws_url)

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
        print(f"Error: {e}")
        return []


def extract_perplexity_url(tabs):
    """Extract Perplexity conversation URL from tabs."""
    for tab in tabs:
        url = tab.get('url', '')
        if 'perplexity.ai/search/' in url:
            return url
    return ""


async def main():
    # Get computer name
    computer_name = get_computer_name()

    print("=" * 70)
    print("MULTI-COMPUTER TAB GROUP SYNC")
    print("=" * 70)
    print()
    print(f"💻 Computer: {computer_name}")
    print()

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

    spreadsheet = gc.open_by_key(sheet_id)

    # Get worksheets
    try:
        ws_groups = spreadsheet.worksheet("Tab Groups")
        ws_tabs = spreadsheet.worksheet("Tabs")
    except:
        print("❌ Error: Run setup_complete_tracker.py first!")
        return

    # Check if 'Source Computer' column exists, add if not
    groups_headers = ws_groups.row_values(1)
    if "Source Computer" not in groups_headers:
        print("📋 Adding 'Source Computer' column to Tab Groups...")
        col_index = len(groups_headers) + 1
        ws_groups.update_cell(1, col_index, "Source Computer")
        ws_groups.format(f'{chr(64 + col_index)}1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
        })

    tabs_headers = ws_tabs.row_values(1)
    if "Source Computer" not in tabs_headers:
        print("📋 Adding 'Source Computer' column to Tabs...")
        col_index = len(tabs_headers) + 1
        ws_tabs.update_cell(1, col_index, "Source Computer")
        ws_tabs.format(f'{chr(64 + col_index)}1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
        })

    print()

    # Get current data from Comet
    print("📚 Reading tab groups from Comet...")
    groups = await get_tab_groups_with_details()

    if not groups:
        print("⚠️  No tab groups found")
        return

    print(f"✓ Found {len(groups)} tab groups\n")

    # Get existing data from sheet to avoid duplicates
    existing_groups = ws_groups.get_all_records()
    existing_tabs = ws_tabs.get_all_records()

    # Track what's new vs updated
    new_groups = 0
    updated_groups = 0
    new_tabs = 0
    updated_tabs = 0

    # Sync tab groups
    for i, group in enumerate(groups, 1):
        group_name = group.get('title') or 'Untitled'
        group_id = f"{computer_name[:3].upper()}-G{i:03d}"

        # Check if group exists (by name and computer)
        existing = None
        for eg in existing_groups:
            if (eg.get('Group Name') == group_name and
                eg.get('Source Computer') == computer_name):
                existing = eg
                break

        tabs = group.get('tabs', [])
        perp_url = extract_perplexity_url(tabs)

        row_data = [
            group_id if not existing else existing.get('Group ID'),
            "P001",  # Default project
            group_name,
            group.get('color', 'grey'),
            existing.get('Status', 'in-progress') if existing else 'in-progress',
            existing.get('Progress %', 0) if existing else 0,
            len(tabs),
            existing.get('Completed Tabs', 0) if existing else 0,
            perp_url,
            "",  # Dependencies
            "",  # Blocked by
            "",  # Notes
            existing.get('Created Date') if existing else datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d %H:%M'),
            computer_name  # Source Computer
        ]

        if existing:
            # Update existing row
            row_num = existing_groups.index(existing) + 2
            ws_groups.update(range_name=f'A{row_num}', values=[row_data])
            updated_groups += 1
        else:
            # Append new row
            ws_groups.append_row(row_data)
            new_groups += 1

        # Sync tabs
        for j, tab in enumerate(tabs, 1):
            tab_url = tab.get('url', '')
            tab_title = tab.get('title', 'Untitled')[:60]

            # Check if tab exists
            existing_tab = None
            for et in existing_tabs:
                if (et.get('URL') == tab_url and
                    et.get('Source Computer') == computer_name):
                    existing_tab = et
                    break

            is_perp = 'perplexity.ai/search/' in tab_url

            tab_row_data = [
                f"{group_id}-T{j:02d}" if not existing_tab else existing_tab.get('Tab ID'),
                group_id if not existing else existing.get('Group ID'),
                "P001",
                tab_title,
                tab_url,
                existing_tab.get('Status', 'pending') if existing_tab else 'pending',
                tab_url if is_perp else "",
                existing_tab.get('Data Extracted', '') if existing_tab else '',
                "📍 Click to continue" if is_perp else "",
                existing_tab.get('Notes', '') if existing_tab else '',
                existing_tab.get('Created Date') if existing_tab else datetime.now().strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d %H:%M'),
                computer_name  # Source Computer
            ]

            if existing_tab:
                row_num = existing_tabs.index(existing_tab) + 2
                ws_tabs.update(range_name=f'A{row_num}', values=[tab_row_data])
                updated_tabs += 1
            else:
                ws_tabs.append_row(tab_row_data)
                new_tabs += 1

    print("=" * 70)
    print("✅ SYNC COMPLETE!")
    print("=" * 70)
    print()
    print(f"💻 Computer: {computer_name}")
    print(f"📚 Tab Groups: {new_groups} new, {updated_groups} updated")
    print(f"📑 Tabs: {new_tabs} new, {updated_tabs} updated")
    print()
    print(f"📊 Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    print()
    print("✓ You can now sync from other computers!")
    print("  Each computer's tabs will be tracked separately")
    print("  Filter by 'Source Computer' column to see tabs from specific machines")
    print()


if __name__ == "__main__":
    asyncio.run(main())
