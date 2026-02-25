#!/usr/bin/env python3
"""List all Comet tab groups with details"""

import asyncio
import json
import websockets


async def main():
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

        # Display results
        print("=" * 70)
        print(f"COMET TAB GROUPS ({len(groups)} total)")
        print("=" * 70)
        print()

        if not groups:
            print("No tab groups found")
            return

        for i, group in enumerate(groups, 1):
            title = group.get('title') or 'Untitled'
            color = group.get('color', 'grey')
            group_id = group.get('id')
            tabs = group.get('tabs', [])

            print(f"{i}. {title}")
            print(f"   Color: {color}")
            print(f"   ID: {group_id}")
            print(f"   Tabs: {len(tabs)}")
            print()

            for j, tab in enumerate(tabs, 1):
                tab_title = tab.get('title', 'Untitled')[:60]
                url = tab.get('url', '')
                print(f"   {j}. {tab_title}")
                print(f"      {url}")
                print()

            print("-" * 70)
            print()

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. Comet browser is running")
        print("2. Extension is active")
        print("3. WebSocket server is running on localhost:8765")


if __name__ == "__main__":
    asyncio.run(main())
