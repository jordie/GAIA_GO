#!/usr/bin/env python3
"""
Open Comet sidebar with Option+A (Alt+A) shortcut
"""

import asyncio
import json
import websockets


async def open_comet():
    """Open Comet with Option+A shortcut."""
    ws_url = "ws://localhost:8765"

    print("Connecting to browser extension...")
    ws = await websockets.connect(ws_url)
    print("✓ Connected\n")

    # Wait for FULL_STATE
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            print("✓ Got browser state\n")
            break

    # Open a fresh tab
    print("Opening fresh tab with Google...")
    cmd_id = "cmd-0"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "OPEN_TAB",
        "params": {"url": "https://www.google.com"}
    }))

    # Wait for tab creation
    tab_id = None
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                tab_id = result["result"]["id"]
                print(f"✓ Created tab {tab_id}\n")
            break

    # Wait for page load
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            print("✓ Page loaded\n")
            break

    await asyncio.sleep(2)
    print("=" * 70)

    # Try Option+A (Alt+A) to open Comet
    print("\n⌨️  Pressing Option+A to open Comet...")

    cmd_id = "open-comet"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "EXECUTE_SCRIPT",
        "tabId": tab_id,
        "params": {
            "code": """
                // Trigger Option+A (Alt+A) keyboard event
                document.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'a',
                    code: 'KeyA',
                    altKey: true,
                    bubbles: true,
                    cancelable: true
                }));
                document.dispatchEvent(new KeyboardEvent('keyup', {
                    key: 'a',
                    code: 'KeyA',
                    altKey: true,
                    bubbles: true,
                    cancelable: true
                }));
                return { triggered: true };
            """
        }
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            print("✓ Triggered Option+A\n")
            break

    # Wait a bit for Comet to open
    print("Waiting for Comet to open...")
    await asyncio.sleep(3)

    # Check if Comet is now open
    print("\n🔍 Checking if Comet opened...")
    cmd_id = "check"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "READ_COMET",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]["result"]
            has_comet = result.get("hasComet", False)

            if has_comet:
                print("✅ SUCCESS! Comet is now open!")
                print(f"\nComet state:")
                print(f"  - Input value: {result.get('inputValue', '(empty)')}")
                print(f"  - Can submit: {result.get('canSubmit')}")
                print(f"  - Queries: {len(result.get('queries', []))}")
                print(f"  - Responses: {len(result.get('responses', []))}")
            else:
                print("❌ Comet still not detected")
                print("\n💡 The keyboard shortcut might be caught by the browser/OS before reaching the page")
                print("   Try manually pressing Option+A in the browser to verify it works")
            break

    print("\n" + "=" * 70)
    await ws.close()


if __name__ == "__main__":
    asyncio.run(open_comet())
