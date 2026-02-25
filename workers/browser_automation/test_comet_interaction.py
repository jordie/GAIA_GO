#!/usr/bin/env python3
"""
Test Comet interaction (assumes Comet is already open via Option+A)
"""

import asyncio
import json
import websockets


async def test_comet_interaction():
    """Test full Comet interaction workflow."""
    ws_url = "ws://localhost:8765"

    print("=" * 70)
    print("COMET INTERACTION TEST")
    print("=" * 70)
    print("\n📝 INSTRUCTIONS:")
    print("   1. This will open a fresh tab")
    print("   2. Press Option+A to open the Perplexity sidebar")
    print("   3. The test will interact with it\n")
    input("Press Enter to start...")
    print()

    print("Connecting to browser extension...")
    ws = await websockets.connect(ws_url)
    print("✓ Connected\n")

    # Wait for FULL_STATE
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            print(f"✓ Got browser state\n")
            break

    # Open a fresh tab so content script is loaded
    print("Opening fresh tab with Google...")
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
            print("✓ Page loaded\n")
            break

    # Wait for content script to be ready
    await asyncio.sleep(2)

    print("📝 Now press Option+A in the browser to open Perplexity sidebar...")
    input("Press Enter when sidebar is open...")
    print()

    print(f"Using tab {tab_id}")
    print("=" * 70)

    # Step 1: Verify Comet is open
    print("\n📖 Step 1: Verifying Comet is open...")
    cmd_id = "cmd-1"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "READ_COMET",
        "tabId": tab_id
    }))

    comet_state = None
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                comet_state = result["result"]
                if comet_state.get("hasComet"):
                    print("✅ Comet is open!")
                    print(f"   Current input: '{comet_state.get('inputValue', '(empty)')}'")
                    print(f"   Can submit: {comet_state.get('canSubmit')}")
                    print(f"   Previous queries: {len(comet_state.get('queries', []))}")
                    print(f"   Previous responses: {len(comet_state.get('responses', []))}")
                else:
                    print("❌ Comet not detected!")
                    print("   Make sure you pressed Option+A to open it")
                    return
            break

    # Step 2: Write a question to Comet
    test_question = "What are the best swimming techniques for beginners?"
    print(f"\n✍️  Step 2: Writing question to Comet...")
    print(f"   Question: {test_question}")

    cmd_id = "cmd-2"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "WRITE_COMET",
        "tabId": tab_id,
        "params": {"text": test_question}
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                print("✓ Text written to Comet input!")
            else:
                print(f"❌ Failed: {result.get('message')}")
                return
            break

    # Step 3: Submit the question
    print("\n📤 Step 3: Submitting question...")

    cmd_id = "cmd-3"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "SUBMIT_COMET",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                print("✓ Question submitted!")
            else:
                print(f"❌ Failed: {result.get('message')}")
                return
            break

    # Step 4: Monitor for Comet responses
    print("\n👂 Step 4: Monitoring for Comet response...")
    print("   (waiting up to 20 seconds...)")

    start_time = asyncio.get_event_loop().time()
    response_detected = False

    while asyncio.get_event_loop().time() - start_time < 20:
        try:
            message = await asyncio.wait_for(ws.recv(), timeout=1.0)
            data = json.loads(message)

            if data.get("event") == "COMET_RESPONSE":
                response_detected = True
                event_data = data["data"]
                print(f"\n   📨 Got Comet response!")
                print(f"      Response ID: {event_data.get('responseId')}")
                print(f"      Type: {event_data.get('type')}")
                text_preview = event_data.get('text', '')[:400]
                print(f"      Text preview:\n      {text_preview}...")
                break

        except asyncio.TimeoutError:
            continue

    if not response_detected:
        print("   ⏱️  No response event captured (sidebar might update without events)")

    # Step 5: Read final state
    print("\n📖 Step 5: Reading final Comet state...")
    await asyncio.sleep(2)

    cmd_id = "cmd-5"
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
            print("✓ Final state:")
            print(f"   Total queries: {len(result.get('queries', []))}")
            print(f"   Total responses: {len(result.get('responses', []))}")

            if result.get('responses'):
                latest = result['responses'][-1]
                print(f"\n   Latest response preview:")
                print(f"   {latest['text'][:300]}...")
            break

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE!")
    print("=" * 70)
    await ws.close()


if __name__ == "__main__":
    asyncio.run(test_comet_interaction())
