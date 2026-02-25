#!/usr/bin/env python3
"""
Test if content script can access basic page properties
"""

import asyncio
import json
import websockets


async def test_basic():
    """Test basic content script functionality."""
    ws_url = "ws://localhost:8765"

    print("Testing basic content script access...\n")
    ws = await websockets.connect(ws_url)

    # Wait for state
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            break

    # Open tab
    cmd_id = "cmd-0"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "OPEN_TAB",
        "params": {"url": "https://www.google.com"}
    }))

    tab_id = None
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            tab_id = data["data"]["result"]["id"]
            break

    # Wait for load
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            break

    await asyncio.sleep(2)

    # Test 1: Get page text (should work)
    print("Test 1: GET_PAGE_TEXT")
    cmd_id = "test-1"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "GET_PAGE_TEXT",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result.get("status") == "success":
                text = result.get("result", {}).get("text", "")
                print(f"✓ Got {len(text)} chars of page text")
                print(f"  Preview: {text[:100]}...\n")
            else:
                print(f"✗ Failed: {result.get('message')}\n")
            break

    # Test 2: Extract elements (should work)
    print("Test 2: EXTRACT_ELEMENTS")
    cmd_id = "test-2"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "EXTRACT_ELEMENTS",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result.get("status") == "success":
                elements = result.get("result", {})
                print(f"✓ Found {len(elements.get('links', []))} links, {len(elements.get('buttons', []))} buttons\n")
            else:
                print(f"✗ Failed: {result.get('message')}\n")
            break

    # Test 3: Detect plugin (might fail)
    print("Test 3: DETECT_PLUGIN")
    cmd_id = "test-3"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "DETECT_PLUGIN",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            print(f"Status: {result.get('status')}")
            if result.get("status") == "success":
                plugin_data = result.get("result", {})
                print(f"Result keys: {list(plugin_data.keys())}")
                print(f"Full result: {json.dumps(plugin_data, indent=2)}")
            else:
                print(f"Error: {result.get('message')}")
                print(f"Stack: {result.get('stack')}")
            break

    await ws.close()


if __name__ == "__main__":
    asyncio.run(test_basic())
