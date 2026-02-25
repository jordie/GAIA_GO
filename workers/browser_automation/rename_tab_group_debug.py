#!/usr/bin/env python3
"""
Rename tab groups in Comet - Debug version
"""

import asyncio
import json
import sys
import websockets


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
        print(f"DEBUG: Received message: {json.dumps(data, indent=2)}")

        if data.get('event') == 'COMMAND_RESULT':
            result = data.get('data', {})
            print(f"DEBUG: Result data: {json.dumps(result, indent=2)}")

            if result.get('status') == 'success':
                print(f"✓ Renamed to '{new_title}'")
            else:
                print(f"✗ Failed")
                print(f"   Full result: {result}")

            await ws.close()
            return


async def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print(f"  {sys.argv[0]} <group_id> <new_title>")
        sys.exit(1)

    group_id = sys.argv[1]
    new_title = sys.argv[2]
    await rename_group(group_id, new_title)


if __name__ == '__main__':
    asyncio.run(main())
