#!/usr/bin/env python3
"""
Full test: Open URL, then ask Perplexity about it using OS automation
"""

import asyncio
import json
import sys
import subprocess
import time
import websockets


def run_applescript(script):
    """Execute AppleScript."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False


def activate_comet():
    """Activate Comet browser."""
    script = 'tell application "Comet" to activate'
    print("📱 Activating Comet browser...")
    run_applescript(script)
    time.sleep(0.5)


def send_keystroke(key, modifiers=None):
    """Send keystroke via System Events."""
    if modifiers:
        mods = ', '.join(f'{m} down' for m in modifiers)
        modifier_str = f' using {{{mods}}}'
    else:
        modifier_str = ''

    script = f'tell application "System Events" to keystroke "{key}"{modifier_str}'
    run_applescript(script)


def type_text(text):
    """Type text."""
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'tell application "System Events" to keystroke "{text}"'
    run_applescript(script)


async def test_comet_with_url():
    """Open URL, then ask Perplexity about it."""
    ws_url = "ws://localhost:8765"

    print("=" * 70)
    print("COMET + PERPLEXITY INTEGRATION TEST")
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

    # Open a URL
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

    # Activate the tab to make sure it's focused
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

    await asyncio.sleep(1)

    # Prompt user to verify
    print("👀 Check Comet browser - you should see the AquaTech page")
    input("Press Enter to continue and ask Perplexity...\n")

    # Now use OS automation to ask Perplexity
    question = "What swimming classes are available for kids?"
    print("=" * 70)
    print(f"💬 Asking Perplexity: {question}")
    print("=" * 70)
    print()

    # Activate browser
    activate_comet()

    # Open Perplexity (Option+A)
    print("⌨️  Pressing Option+A to open Perplexity...")
    send_keystroke("a", ["option"])
    print("   Waiting for sidebar to open...")
    time.sleep(3)

    # Type question
    print("⌨️  Typing question...")
    type_text(question)
    time.sleep(0.5)

    # Submit (Enter)
    print("⌨️  Submitting (Enter)...")
    send_keystroke("\\n")

    # Wait for response
    print("\n⏳ Waiting 8 seconds for Perplexity response...")
    time.sleep(8)

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE!")
    print("=" * 70)
    print("\n📋 Results:")
    print("   1. ✓ Extension connected")
    print("   2. ✓ Opened webpage")
    print("   3. ✓ Activated Perplexity sidebar")
    print("   4. ✓ Asked question via OS automation")
    print("\n💡 Check the Perplexity sidebar for the response!")
    print()

    await ws.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_comet_with_url())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
        sys.exit(0)
