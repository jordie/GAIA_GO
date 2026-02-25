#!/usr/bin/env python3
"""
Capture the response from Comet Assistant sidebar
"""

import asyncio
import json
import subprocess
import time
import websockets


def run_applescript(script):
    """Execute AppleScript."""
    try:
        subprocess.run(['osascript', '-e', script], capture_output=True, timeout=10)
    except:
        pass


def toggle_assistant():
    """Click Assistant -> Toggle Assistant menu."""
    script = '''
    tell application "System Events"
        tell process "Comet"
            click menu item "Toggle Assistant" of menu "Assistant" of menu bar 1
        end tell
    end tell
    '''
    print("📱 Opening Assistant sidebar...")
    run_applescript(script)
    time.sleep(2)


def type_text(text):
    """Type text via AppleScript."""
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'tell application "System Events" to keystroke "{text}"'
    run_applescript(script)


def press_enter():
    """Press Enter key."""
    script = 'tell application "System Events" to keystroke return'
    run_applescript(script)


async def ask_and_capture():
    """Ask question and try to capture response."""
    ws_url = "ws://localhost:8765"

    print("=" * 70)
    print("ASK & CAPTURE TEST")
    print("=" * 70)
    print()

    # Connect
    print("🔌 Connecting...")
    ws = await websockets.connect(ws_url)

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            print("✓ Connected\n")
            break

    # Open URL
    url = "https://www.aquatechswim.com"
    print(f"🌐 Opening {url}...")

    await ws.send(json.dumps({
        "command": True,
        "id": "cmd-1",
        "action": "OPEN_TAB",
        "params": {"url": url}
    }))

    tab_id = None
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == "cmd-1":
            tab_id = data["data"]["result"]["id"]
            print(f"✓ Tab {tab_id}\n")
            break

    # Wait for load
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            print("✓ Page loaded\n")
            break

    # Activate tab
    await ws.send(json.dumps({
        "command": True,
        "id": "cmd-2",
        "action": "ACTIVATE_TAB",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == "cmd-2":
            break

    await asyncio.sleep(1)

    # Open sidebar
    question = "What swimming classes are available for kids?"
    print(f"💬 Question: {question}\n")

    toggle_assistant()

    # Type and submit
    print("⌨️  Typing...")
    type_text(question)
    await asyncio.sleep(0.5)

    print("⌨️  Submitting...")
    press_enter()

    # Wait for response
    print("\n⏳ Waiting 10 seconds for response...")
    await asyncio.sleep(10)

    print("\n" + "=" * 70)
    print("ATTEMPTING TO CAPTURE RESPONSE")
    print("=" * 70)
    print()

    # Try 1: Check page DOM
    print("Try 1: Checking page DOM for response...")
    await ws.send(json.dumps({
        "command": True,
        "id": "cmd-3",
        "action": "DIAGNOSE_SIDEBAR",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == "cmd-3":
            result = data["data"].get("result", {})
            if result.get("sidebarElements", {}).get("bySidecar", 0) > 0:
                print(f"✓ Found {result['sidebarElements']['bySidecar']} sidebar elements")
            else:
                print("✗ No sidebar elements in page DOM")
            break

    # Try 2: Get all page text (might include sidebar if it's in DOM)
    print("\nTry 2: Getting all page text...")
    await ws.send(json.dumps({
        "command": True,
        "id": "cmd-4",
        "action": "GET_PAGE_TEXT",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == "cmd-4":
            text = data["data"]["result"].get("text", "")
            if "swimming" in text.lower() or "class" in text.lower():
                print(f"✓ Found {len(text)} chars")
                print(f"\nText preview:\n{text[:500]}\n")
            else:
                print("✗ Response not found in page text")
            break

    print("\n" + "=" * 70)
    print("📸 NEXT: Screenshot + OCR approach")
    print("=" * 70)
    print("\nThe sidebar is likely browser-level (not in DOM).")
    print("I'll create a screenshot + OCR version to capture the text.")

    await ws.close()


if __name__ == "__main__":
    asyncio.run(ask_and_capture())
