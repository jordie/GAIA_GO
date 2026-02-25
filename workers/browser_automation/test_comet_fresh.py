#!/usr/bin/env python3
"""
Test Comet AI sidebar interaction with a fresh tab
"""

import asyncio
import json
import websockets


async def test_comet():
    """Test writing to Comet sidebar and reading responses."""
    ws_url = "ws://localhost:8765"

    print("Connecting to browser extension...")
    ws = await websockets.connect(ws_url)
    print("✓ Connected\n")

    # Wait for FULL_STATE
    print("Waiting for browser state...")
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            print(f"✓ Got state\n")
            break

    # Open a fresh tab
    print("Opening fresh tab with aquatechswim.com...")
    cmd_id = "cmd-0"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "OPEN_TAB",
        "params": {"url": "https://www.aquatechswim.com"}
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

    if not tab_id:
        print("❌ Failed to create tab")
        return

    # Wait for page load
    print("Waiting for page to load...")
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            print(f"✓ Page loaded\n")
            break

    # Small delay to ensure content script is ready
    await asyncio.sleep(2)

    print("=" * 70)

    # Test 1: Read current Comet state
    print("\n📖 Test 1: Reading Comet sidebar state...")
    cmd_id = "cmd-1"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "READ_COMET",
        "tabId": tab_id
    }))

    # Wait for result
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                print(f"✓ Comet state: {json.dumps(result['result'], indent=2)}")
            else:
                print(f"⚠️  Failed: {result.get('message')}")
                print(f"   (Make sure Comet/Perplexity sidebar is open on this tab)")
            break

    # Test 2: Write text to Comet input
    test_question = "What are the swimming class options at AquaTech?"
    print(f"\n✍️  Test 2: Writing to Comet input...")
    print(f"   Question: {test_question}")

    cmd_id = "cmd-2"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "WRITE_COMET",
        "tabId": tab_id,
        "params": {"text": test_question}
    }))

    # Wait for result
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                print(f"✓ Text written to Comet input")
            else:
                print(f"❌ Failed: {result.get('message')}")
            break

    # Test 3: Monitor for Comet response events
    print("\n👂 Test 3: Monitoring for Comet responses...")
    print("   (waiting 15 seconds for response events...)")

    timeout = asyncio.create_task(asyncio.sleep(15))
    response_count = 0

    try:
        while not timeout.done():
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(message)

                if data.get("event") == "COMET_RESPONSE":
                    response_count += 1
                    event_data = data["data"]
                    print(f"\n   📨 Response #{response_count}:")
                    print(f"      ID: {event_data.get('responseId')}")
                    print(f"      Type: {event_data.get('type')}")
                    text_preview = event_data.get('text', '')[:300]
                    print(f"      Text: {text_preview}{'...' if len(event_data.get('text', '')) > 300 else ''}")

            except asyncio.TimeoutError:
                continue
    except Exception as e:
        print(f"   Error: {e}")

    timeout.cancel()

    if response_count == 0:
        print("   ⚠️  No Comet responses detected")
        print("   (This is normal if Comet sidebar isn't open or doesn't respond)")

    # Test 4: Read Comet state again
    print("\n📖 Test 4: Reading Comet state after interaction...")
    cmd_id = "cmd-3"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "READ_COMET",
        "tabId": tab_id
    }))

    # Wait for result
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                print(f"✓ Updated state: {json.dumps(result['result'], indent=2)}")
            else:
                print(f"⚠️  Failed: {result.get('message')}")
            break

    print("\n" + "=" * 70)
    print("✓ Test complete")

    await ws.close()


if __name__ == "__main__":
    asyncio.run(test_comet())
