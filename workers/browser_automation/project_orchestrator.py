#!/usr/bin/env python3
"""
Project orchestrator - manages data flow between tab groups, database, and Google Sheets
"""

import asyncio
import json
import websockets
from project_manager import ProjectManager
from google_sheets_sync import GoogleSheetsSync, HAS_GSPREAD


class ProjectOrchestrator:
    def __init__(self, ws_url="ws://localhost:8765"):
        self.ws_url = ws_url
        self.ws = None
        self.pm = ProjectManager()
        self.gs = None

        if HAS_GSPREAD:
            try:
                self.gs = GoogleSheetsSync()
                print("✓ Google Sheets connected")
            except Exception as e:
                print(f"⚠️  Google Sheets not available: {e}")

    async def connect(self):
        """Connect to browser extension."""
        self.ws = await websockets.connect(self.ws_url)

        # Wait for FULL_STATE
        async for message in self.ws:
            data = json.loads(message)
            if data.get("event") == "FULL_STATE":
                return True

    async def send_command(self, action, params=None):
        """Send command to extension and wait for result."""
        cmd_id = f"cmd-{int(asyncio.get_event_loop().time() * 1000)}"

        await self.ws.send(json.dumps({
            "command": True,
            "id": cmd_id,
            "action": action,
            "params": params or {}
        }))

        async for message in self.ws:
            data = json.loads(message)
            if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
                return data["data"].get("result")

    async def get_tab_groups(self):
        """Get all tab groups from browser."""
        result = await self.send_command("GET_TAB_GROUPS", {})
        return result

    async def get_tabs_in_group(self, group_id):
        """Get all tabs in a tab group."""
        result = await self.send_command("GET_TABS", {"groupId": group_id})
        return result

    async def import_tab_groups_to_project(self, project_name):
        """
        Import current browser tab groups into a project.
        Creates project if it doesn't exist.
        """
        # Get tab groups from browser
        chrome_groups = await self.get_tab_groups()

        if not chrome_groups:
            print("No tab groups found in browser")
            return None

        # Get or create project
        project = self.pm.get_project(project_name)

        if not project:
            project_id = self.pm.create_project(project_name, "Imported from browser")
            print(f"Created new project: {project_name}")
        else:
            project_id = project['id']
            print(f"Using existing project: {project_name}")

        # Import each tab group
        for i, chrome_group in enumerate(chrome_groups):
            # Get tabs in this group
            tabs = await self.get_tabs_in_group(chrome_group['id'])

            # Create tab group in database
            tg_id = self.pm.create_tab_group(
                project_id,
                chrome_group.get('title', f'Group {i+1}'),
                description="",
                color=chrome_group.get('color'),
                position=i
            )

            print(f"  Imported tab group: {chrome_group.get('title', f'Group {i+1}')} ({len(tabs)} tabs)")

            # Add tabs to group
            for tab in tabs:
                self.pm.add_tab_to_group(
                    tg_id,
                    tab['url'],
                    tab.get('title', ''),
                    tab['id']
                )

        return project_id

    async def sync_project_to_sheets(self, project_name):
        """Sync project to Google Sheets."""
        if not self.gs:
            print("Google Sheets not available")
            return None

        project = self.pm.get_project(project_name)

        if not project:
            print(f"Project not found: {project_name}")
            return None

        # Create or update Google Sheet
        sheet_id = project.get('google_sheet_id')

        print(f"Syncing project '{project_name}' to Google Sheets...")

        sheet_id = self.gs.sync_project_to_sheet(project, sheet_id)

        # Save sheet ID to project
        conn = self.pm.db_path
        import sqlite3
        db = sqlite3.connect(conn)
        cursor = db.cursor()
        cursor.execute(
            "UPDATE projects SET google_sheet_id = ? WHERE id = ?",
            (sheet_id, project['id'])
        )
        db.commit()
        db.close()

        sheet_url = self.gs.get_sheet_url(sheet_id)
        print(f"✓ Synced to: {sheet_url}")

        return sheet_url

    async def cleanup_tab_groups(self):
        """
        Interactive cleanup of tab groups.
        Shows all groups and lets you archive/merge/delete them.
        """
        chrome_groups = await self.get_tab_groups()

        print("\n" + "=" * 70)
        print("TAB GROUP CLEANUP")
        print("=" * 70)
        print()

        for i, group in enumerate(chrome_groups):
            tabs = await self.get_tabs_in_group(group['id'])
            print(f"{i+1}. {group.get('title', 'Untitled')} ({len(tabs)} tabs)")
            print(f"   Color: {group.get('color', 'none')}")
            if len(tabs) <= 5:
                for tab in tabs:
                    print(f"   - {tab.get('title', 'Untitled')[:60]}")
            print()

        print("Actions:")
        print("  1. Import all groups to a project")
        print("  2. Show detailed view")
        print("  3. Exit")

        return chrome_groups

    async def monitor_project_progress(self, project_name, interval=60):
        """
        Monitor project progress and auto-sync to Google Sheets.

        interval: seconds between syncs
        """
        print(f"Monitoring project: {project_name}")
        print(f"Auto-sync interval: {interval}s")
        print("Press Ctrl+C to stop")

        while True:
            try:
                # Get current tab groups from browser
                chrome_groups = await self.get_tab_groups()

                # Update project with current state
                # TODO: Track changes, update progress

                # Sync to Google Sheets
                await self.sync_project_to_sheets(project_name)

                print(f"✓ Synced at {datetime.now().strftime('%H:%M:%S')}")

                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                print("\nStopped monitoring")
                break


async def main():
    """Demo usage."""
    orchestrator = ProjectOrchestrator()

    print("Connecting to browser...")
    await orchestrator.connect()
    print("✓ Connected\n")

    # Show tab groups
    groups = await orchestrator.cleanup_tab_groups()

    # Import to project
    if groups:
        choice = input("\nImport tab groups to project? (y/n): ")
        if choice.lower() == 'y':
            project_name = input("Project name: ")
            await orchestrator.import_tab_groups_to_project(project_name)

            # Sync to Google Sheets
            if HAS_GSPREAD:
                sync = input("Sync to Google Sheets? (y/n): ")
                if sync.lower() == 'y':
                    await orchestrator.sync_project_to_sheets(project_name)

    await orchestrator.ws.close()


if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
