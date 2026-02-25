#!/usr/bin/env python3
"""
Setup complete project tracking system with:
- Projects
- Tab Groups
- Tabs
- Perplexity Conversations
- Dependencies
"""

import asyncio
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import json
import websockets
from datetime import datetime


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
    print("=" * 70)
    print("SETTING UP COMPLETE PROJECT TRACKING SYSTEM")
    print("=" * 70)
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
    print(f"✓ Opened: {spreadsheet.title}\n")

    # =================================================================
    # 1. PROJECTS TAB
    # =================================================================
    print("📋 Creating 'Projects' worksheet...")
    try:
        ws_projects = spreadsheet.worksheet("Projects")
        ws_projects.clear()
    except:
        ws_projects = spreadsheet.add_worksheet("Projects", rows=100, cols=12)

    projects_headers = [
        "Project ID",
        "Project Name",
        "Description",
        "Status",
        "Progress %",
        "Tab Groups Count",
        "Total Tabs",
        "Completed Tabs",
        "Perplexity Conversations",
        "Created Date",
        "Last Updated",
        "Notes"
    ]

    ws_projects.update(range_name='A1', values=[projects_headers])
    ws_projects.format('A1:L1', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    print("✓ Projects worksheet created\n")

    # =================================================================
    # 2. TAB GROUPS TAB
    # =================================================================
    print("📋 Creating 'Tab Groups' worksheet...")
    try:
        ws_groups = spreadsheet.worksheet("Tab Groups")
        ws_groups.clear()
    except:
        ws_groups = spreadsheet.add_worksheet("Tab Groups", rows=100, cols=14)

    groups_headers = [
        "Group ID",
        "Project ID",
        "Group Name",
        "Color",
        "Status",
        "Progress %",
        "Tab Count",
        "Completed Tabs",
        "Main Perplexity URL",
        "Dependencies",
        "Blocked By",
        "Notes",
        "Created Date",
        "Last Updated"
    ]

    ws_groups.update(range_name='A1', values=[groups_headers])
    ws_groups.format('A1:N1', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    print("✓ Tab Groups worksheet created\n")

    # =================================================================
    # 3. TABS TAB
    # =================================================================
    print("📋 Creating 'Tabs' worksheet...")
    try:
        ws_tabs = spreadsheet.worksheet("Tabs")
        ws_tabs.clear()
    except:
        ws_tabs = spreadsheet.add_worksheet("Tabs", rows=500, cols=12)

    tabs_headers = [
        "Tab ID",
        "Group ID",
        "Project ID",
        "Tab Title",
        "URL",
        "Status",
        "Perplexity Conversation URL",
        "Data Extracted",
        "Continue From Here",
        "Notes",
        "Created Date",
        "Last Updated"
    ]

    ws_tabs.update(range_name='A1', values=[tabs_headers])
    ws_tabs.format('A1:L1', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    print("✓ Tabs worksheet created\n")

    # =================================================================
    # 4. CONVERSATIONS TAB
    # =================================================================
    print("📋 Creating 'Conversations' worksheet...")
    try:
        ws_convs = spreadsheet.worksheet("Conversations")
        ws_convs.clear()
    except:
        ws_convs = spreadsheet.add_worksheet("Conversations", rows=500, cols=11)

    convs_headers = [
        "Conversation ID",
        "Perplexity URL",
        "Project",
        "Tab Group",
        "Related Tab",
        "Topic/Question",
        "Status",
        "Last Response Summary",
        "Created Date",
        "Last Updated",
        "Continue URL"
    ]

    ws_convs.update(range_name='A1', values=[convs_headers])
    ws_convs.format('A1:K1', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    print("✓ Conversations worksheet created\n")

    # =================================================================
    # 5. POPULATE WITH CURRENT DATA
    # =================================================================
    print("📚 Reading current tab groups from Comet...")
    groups = await get_tab_groups_with_details()

    if groups:
        print(f"✓ Found {len(groups)} tab groups\n")

        # Create default project for ungrouped tabs
        project_id = "P001"
        project_name = "General Research"

        # Add to Projects
        ws_projects.update(range_name='A2', values=[[
            project_id,
            project_name,
            "Default project for current tab groups",
            "active",
            0,
            len(groups),
            sum(len(g.get('tabs', [])) for g in groups),
            0,
            sum(1 for g in groups if extract_perplexity_url(g.get('tabs', []))),
            datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d %H:%M'),
            "Auto-imported from Comet"
        ]])

        # Add tab groups
        group_rows = []
        tab_rows = []
        conv_rows = []

        for i, group in enumerate(groups, 1):
            group_id = f"G{i:03d}"
            tabs = group.get('tabs', [])
            perp_url = extract_perplexity_url(tabs)

            group_rows.append([
                group_id,
                project_id,
                group.get('title') or 'Untitled',
                group.get('color', 'grey'),
                "in-progress",
                0,
                len(tabs),
                0,
                perp_url,
                "",  # Dependencies
                "",  # Blocked by
                "",  # Notes
                datetime.now().strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d %H:%M')
            ])

            # Add tabs
            for j, tab in enumerate(tabs, 1):
                tab_id = f"T{i:03d}-{j:02d}"
                tab_url = tab.get('url', '')
                is_perp = 'perplexity.ai/search/' in tab_url

                tab_rows.append([
                    tab_id,
                    group_id,
                    project_id,
                    tab.get('title', 'Untitled')[:60],
                    tab_url,
                    "pending",
                    tab_url if is_perp else "",
                    "",  # Data extracted
                    "📍 Click to continue" if is_perp else "",
                    "",  # Notes
                    datetime.now().strftime('%Y-%m-%d'),
                    datetime.now().strftime('%Y-%m-%d %H:%M')
                ])

                # Add conversation if it's a Perplexity URL
                if is_perp:
                    conv_id = f"C{len(conv_rows) + 1:03d}"
                    conv_rows.append([
                        conv_id,
                        tab_url,
                        project_name,
                        group.get('title') or 'Untitled',
                        tab_id,
                        tab.get('title', 'Untitled')[:60],
                        "active",
                        "",  # Summary
                        datetime.now().strftime('%Y-%m-%d'),
                        datetime.now().strftime('%Y-%m-%d %H:%M'),
                        tab_url  # Continue URL
                    ])

        if group_rows:
            ws_groups.update(range_name='A2', values=group_rows)
            print(f"✓ Added {len(group_rows)} tab groups\n")

        if tab_rows:
            ws_tabs.update(range_name='A2', values=tab_rows)
            print(f"✓ Added {len(tab_rows)} tabs\n")

        if conv_rows:
            ws_convs.update(range_name='A2', values=conv_rows)
            print(f"✓ Added {len(conv_rows)} conversations\n")

    # =================================================================
    # 6. ADD INSTRUCTIONS TAB
    # =================================================================
    print("📋 Creating 'Instructions' worksheet...")
    try:
        ws_instructions = spreadsheet.worksheet("Instructions")
        ws_instructions.clear()
    except:
        ws_instructions = spreadsheet.add_worksheet("Instructions", rows=50, cols=2)

    instructions = [
        ["HOW TO USE THIS TRACKER", ""],
        ["", ""],
        ["1. PROJECTS", "Top-level organization (e.g., 'Ethiopia Trip')"],
        ["", "- Create projects for major initiatives"],
        ["", "- Link tab groups to projects"],
        ["", "- Track overall progress"],
        ["", ""],
        ["2. TAB GROUPS", "Organize related tabs (e.g., 'Flight Search', 'Hotels')"],
        ["", "- Each group represents a sub-task"],
        ["", "- Mark status: pending/in-progress/completed"],
        ["", "- Track dependencies between groups"],
        ["", "- Store main Perplexity conversation URL"],
        ["", ""],
        ["3. TABS", "Individual browser tabs with URLs"],
        ["", "- Each tab has a purpose"],
        ["", "- Link to Perplexity conversation if applicable"],
        ["", "- Extract data and store in 'Data Extracted' column"],
        ["", "- Mark completed when done"],
        ["", ""],
        ["4. CONVERSATIONS", "All Perplexity conversations"],
        ["", "- Click Perplexity URL to continue conversation"],
        ["", "- Works from any computer - just open the URL!"],
        ["", "- Track status and last response"],
        ["", "- Link back to project/tab group/tab"],
        ["", ""],
        ["5. WORKFLOW", ""],
        ["", "a) Create project (or use 'General Research')"],
        ["", "b) Add tab groups for different workstreams"],
        ["", "c) Open tabs, ask Perplexity questions"],
        ["", "d) Copy Perplexity conversation URL to sheet"],
        ["", "e) Mark progress as you go"],
        ["", "f) Switch computers? Open sheet → click Perplexity URL → continue!"],
        ["", ""],
        ["6. CONTINUING WORK", ""],
        ["", "- Open this sheet from any computer"],
        ["", "- Find your project/tab group"],
        ["", "- Click the Perplexity URL in 'Continue From Here'"],
        ["", "- Conversation loads with full history"],
        ["", "- Keep working where you left off"],
        ["", ""],
        ["7. MARKING COMPLETE", ""],
        ["", "- Tab Groups: Change Status to 'completed'"],
        ["", "- Tabs: Mark Status as 'completed'"],
        ["", "- Projects: Progress % updates automatically"],
    ]

    ws_instructions.update(range_name='A1', values=instructions)
    ws_instructions.format('A1', {
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
        "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })

    print("✓ Instructions worksheet created\n")

    print("=" * 70)
    print("✅ COMPLETE PROJECT TRACKING SYSTEM READY!")
    print("=" * 70)
    print()
    print(f"📊 Sheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    print()
    print("Worksheets created:")
    print("  1. Projects - Top-level project tracking")
    print("  2. Tab Groups - Organize tabs into groups")
    print("  3. Tabs - Individual tabs with Perplexity URLs")
    print("  4. Conversations - All Perplexity conversations")
    print("  5. Instructions - How to use this system")
    print()
    print("🎯 Key Feature: Perplexity conversation URLs let you")
    print("   continue work from ANY computer!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
