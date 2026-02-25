#!/usr/bin/env python3
"""
Fully automated: Opens URL, clicks Assistant → Toggle Assistant, types question
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


def type_text(text):
    """Type text via AppleScript."""
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'tell application "System Events" to keystroke "{text}"'
    run_applescript(script)


def press_enter():
    """Press Enter key."""
    script = 'tell application "System Events" to keystroke return'
    run_applescript(script)


def toggle_assistant():
    """Click Assistant -> Toggle Assistant menu."""
    script = '''
    tell application "System Events"
        tell process "Comet"
            click menu item "Toggle Assistant" of menu "Assistant" of menu bar 1
        end tell
    end tell
    '''
    print("📱 Clicking Assistant → Toggle Assistant...")
    run_applescript(script)
    time.sleep(2)  # Wait for sidebar to open


async def test_semi_manual():
    """Open URL, countdown, user opens sidebar, then auto-type."""
    ws_url = "ws://localhost:8765"

    print("=" * 70)
    print("SEMI-MANUAL PERPLEXITY TEST")
    print("=" * 70)
    print()

    # Connect to extension
    print("🔌 Connecting to browser extension...")
    ws = await websockets.connect(ws_url)
    print("✓ Connected\n")

    # Wait for state
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            print("✓ Got browser state\n")
            break

    # Open URL
    url = "https://www.aquatechswim.com"
    print(f"🌐 Opening {url}...")

    cmd_id = "cmd-1"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "OPEN_TAB",
        "params": {"url": url}
    }))

    tab_id = None
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]
            if result["status"] == "success":
                tab_id = result["result"]["id"]
                print(f"✓ Opened tab {tab_id}\n")
            break

    # Wait for page load
    print("⏳ Waiting for page to load...")
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            print("✓ Page loaded\n")
            break

    # Activate tab
    print("🎯 Activating the tab...")
    cmd_id = "cmd-2"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "ACTIVATE_TAB",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            print("✓ Tab activated\n")
            break

    # Open Assistant sidebar via menu
    question = "What swimming classes are available for kids?"

    print("=" * 70)
    print("🤖 OPENING ASSISTANT SIDEBAR")
    print("=" * 70)
    print()
    print(f"📝 Question: {question}")
    print()

    # Small countdown
    print("⏱️  Starting in 3 seconds...")
    await asyncio.sleep(3)

    # Click menu item
    toggle_assistant()
    print("✓ Assistant sidebar should be open\n")

    # Wait for input to be ready
    print("⏳ Waiting for input to be ready...")
    await asyncio.sleep(2)

    print()
    print("⌨️  Typing question...")
    type_text(question)

    await asyncio.sleep(0.5)

    print("⌨️  Pressing Enter...")
    press_enter()

    print()
    print("⏳ Waiting 10 seconds for response...")
    await asyncio.sleep(10)

    print()
    print("=" * 70)
    print("✅ DONE!")
    print("=" * 70)
    print()
    print("💡 Check the Perplexity sidebar in Comet for the response!")
    print()

    await ws.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_semi_manual())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
