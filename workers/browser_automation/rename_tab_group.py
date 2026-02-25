#!/usr/bin/env python3
"""
Rename tab groups in Comet
"""

import asyncio
import json
import sys
import websockets


async def list_groups():
    """List all tab groups with their IDs."""
    ws = await websockets.connect('ws://localhost:8765')

    async for msg in ws:
        if json.loads(msg).get('event') == 'FULL_STATE':
            break

    await ws.send(json.dumps({
        'command': True,
        'id': 'get-groups',
        'action': 'GET_TAB_GROUPS',
        'params': {}
    }))

    async for msg in ws:
        data = json.loads(msg)
        if data.get('event') == 'COMMAND_RESULT':
            groups = data['data'].get('result', [])

            print("Tab Groups:")
            print("-" * 70)
            for i, g in enumerate(groups, 1):
                print(f"{i}. {g.get('title', 'Untitled')} (ID: {g['id']}, Color: {g.get('color', 'grey')})")

            await ws.close()
            return groups


async def rename_group(group_id, new_title):
    """Rename a tab group."""
    ws = await websockets.connect('ws://localhost:8765')

    async for msg in ws:
        if json.loads(msg).get('event') == 'FULL_STATE':
            break

    print(f"Renaming group {group_id} to '{new_title}'...")

    await ws.send(json.dumps({
        'command': True,
        'id': 'rename-group',
        'action': 'UPDATE_TAB_GROUP',
        'params': {
            'groupId': int(group_id),
            'props': {'title': new_title}
        }
    }))

    async for msg in ws:
        data = json.loads(msg)
        if data.get('event') == 'COMMAND_RESULT':
            result = data['data']
            if result.get('status') == 'success':
                print(f"✓ Renamed to '{new_title}'")
            else:
                print(f"✗ Failed: {result.get('error')}")

            await ws.close()
            return


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} list")
        print(f"  {sys.argv[0]} <group_id> <new_title>")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} list")
        print(f"  {sys.argv[0]} 1053275210 'Ethiopia Trip - Planning'")
        sys.exit(1)

    if sys.argv[1] == 'list':
        await list_groups()
    else:
        group_id = sys.argv[1]
        new_title = sys.argv[2] if len(sys.argv) > 2 else input("New title: ")
        await rename_group(group_id, new_title)


if __name__ == '__main__':
    asyncio.run(main())
