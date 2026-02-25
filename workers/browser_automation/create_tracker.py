#!/usr/bin/env python3
"""
Create Tab Groups Tracker sheet and import current Comet tab groups
"""

import asyncio
from project_orchestrator import ProjectOrchestrator


async def main():
    print("=" * 70)
    print("CREATING TAB GROUPS TRACKER")
    print("=" * 70)
    print()

    # Create orchestrator
    orch = ProjectOrchestrator()

    # Connect to browser
    print("🔌 Connecting to browser extension...")
    await orch.connect()
    print("✓ Connected\n")

    # Get current tab groups
    print("📚 Reading tab groups from Comet...")
    groups = await orch.get_tab_groups()
    print(f"✓ Found {len(groups)} tab groups\n")

    # Show tab groups
    print("Tab Groups:")
    print("-" * 70)
    for i, group in enumerate(groups):
        tabs = await orch.get_tabs_in_group(group['id'])
        title = group.get('title') or f'Untitled Group {i+1}'
        color = group.get('color', 'grey')
        print(f"{i+1}. {title} ({color}) - {len(tabs)} tabs")

    print()

    # Create project
    project_name = "tab-groups-tracker"
    print(f"📦 Creating project: {project_name}")
    project_id = await orch.import_tab_groups_to_project(project_name)
    print(f"✓ Project created (ID: {project_id})\n")

    # Sync to Google Sheets
    print("📊 Creating Google Sheet: 'Tab Groups Tracker'")

    if not orch.gs:
        print("✗ Google Sheets not available - check credentials")
        await orch.ws.close()
        return

    # Get project
    project = orch.pm.get_project(project_name)

    # Create custom sheet
    sheet_id = orch.gs.create_project_sheet(
        "Tab Groups Tracker",
        columns=["Group Name", "Color", "Tabs Count", "Status", "Notes", "Last Updated"]
    )

    print(f"✓ Sheet created: {sheet_id}\n")

    # Populate with tab groups
    spreadsheet = orch.gs.client.open_by_key(sheet_id)
    sheet = spreadsheet.sheet1

    rows = []
    for tg in project['tab_groups']:
        rows.append([
            tg['name'],
            tg.get('color', 'grey'),
            len(tg['tabs']),
            tg.get('status', 'active'),
            f"{len(tg['tabs'])} tabs",
            ""
        ])

    if rows:
        sheet.update('A2', rows)

    # Save sheet ID to project
    import sqlite3
    db = sqlite3.connect(orch.pm.db_path)
    cursor = db.cursor()
    cursor.execute(
        "UPDATE projects SET google_sheet_id = ? WHERE id = ?",
        (sheet_id, project_id)
    )
    db.commit()
    db.close()

    # Get sheet URL
    sheet_url = orch.gs.get_sheet_url(sheet_id)

    print("=" * 70)
    print("✅ SUCCESS!")
    print("=" * 70)
    print()
    print(f"📊 Google Sheet: {sheet_url}")
    print(f"📦 Project: {project_name}")
    print(f"📚 Tab Groups: {len(groups)}")
    print()
    print("You can now:")
    print("  - View/edit the sheet in Google Sheets")
    print("  - Add notes and status updates")
    print("  - Track progress on your tab groups")
    print("  - Share with collaborators")
    print()

    await orch.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
