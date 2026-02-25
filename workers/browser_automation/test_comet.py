#!/usr/bin/env python3
"""
Test Comet AI sidebar interaction
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
            tabs = data["data"]["tabs"]
            print(f"✓ Got state: {len(tabs)} tabs\n")
            break

    # Find a tab (or use the active one)
    active_tab_id = tabs[0]["id"] if tabs else None
    if not active_tab_id:
        print("❌ No tabs found")
        return

    print(f"Using tab {active_tab_id}")
    print("=" * 70)

    # Test 1: Read current Comet state
    print("\n📖 Test 1: Reading Comet sidebar state...")
    cmd_id = "cmd-1"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "READ_COMET",
        "tabId": active_tab_id
    }))

    # Wait for result
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                print(f"✓ Comet state: {json.dumps(result['result'], indent=2)}")
            else:
                print(f"❌ Failed: {result.get('message')}")
            break

    # Test 2: Write text to Comet input
    test_question = "What is the capital of France?"
    print(f"\n✍️  Test 2: Writing to Comet input...")
    print(f"   Question: {test_question}")

    cmd_id = "cmd-2"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "WRITE_COMET",
        "tabId": active_tab_id,
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
    print("   (waiting 10 seconds for response events...)")

    timeout = asyncio.create_task(asyncio.sleep(10))
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
                    text_preview = event_data.get('text', '')[:200]
                    print(f"      Text: {text_preview}{'...' if len(event_data.get('text', '')) > 200 else ''}")

            except asyncio.TimeoutError:
                continue
    except Exception as e:
        print(f"   Error: {e}")

    timeout.cancel()

    if response_count == 0:
        print("   ⚠️  No Comet responses detected")
        print("   (Make sure Comet/Perplexity sidebar is open in the browser)")

    # Test 4: Read Comet state again
    print("\n📖 Test 4: Reading Comet state after interaction...")
    cmd_id = "cmd-3"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "READ_COMET",
        "tabId": active_tab_id
    }))

    # Wait for result
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                print(f"✓ Updated state: {json.dumps(result['result'], indent=2)}")
            else:
                print(f"❌ Failed: {result.get('message')}")
            break

    print("\n" + "=" * 70)
    print("✓ Test complete")

    await ws.close()


if __name__ == "__main__":
    asyncio.run(test_comet())
