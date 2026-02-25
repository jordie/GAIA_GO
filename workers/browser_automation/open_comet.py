#!/usr/bin/env python3
"""
Try to open Comet/Perplexity sidebar programmatically
"""

import asyncio
import json
import websockets


async def open_comet():
    """Try various methods to open Comet sidebar."""
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
    print("Opening fresh tab...")
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

    if not tab_id:
        print("❌ Failed to create tab")
        return

    # Wait for page load
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            print("✓ Page loaded\n")
            break

    await asyncio.sleep(2)
    print("=" * 70)

    # Try 1: Check if Comet is already open
    print("\n🔍 Try 1: Checking if Comet is already open...")
    cmd_id = "check-1"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "READ_COMET",
        "tabId": tab_id
    }))

    has_comet = False
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            result = data["data"]["result"]
            has_comet = result.get("hasComet", False)
            if has_comet:
                print("✓ Comet is already open!")
            else:
                print("⚠️  Comet not detected")
            break

    if not has_comet:
        # Try 2: Look for Perplexity button to click
        print("\n🔍 Try 2: Looking for Perplexity/Comet button...")
        cmd_id = "search-1"
        await ws.send(json.dumps({
            "command": True,
            "id": cmd_id,
            "action": "EXECUTE_SCRIPT",
            "tabId": tab_id,
            "params": {
                "code": """
                    const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
                    const perplexityBtn = buttons.find(btn =>
                        btn.innerText.toLowerCase().includes('perplexity') ||
                        btn.innerText.toLowerCase().includes('comet') ||
                        btn.getAttribute('aria-label')?.toLowerCase().includes('perplexity')
                    );
                    if (perplexityBtn) {
                        perplexityBtn.click();
                        return { found: true, text: perplexityBtn.innerText };
                    }
                    return { found: false };
                """
            }
        }))

        async for message in ws:
            data = json.loads(message)
            if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
                result = data["data"]
                if result["status"] == "success":
                    script_result = result["result"]
                    if script_result and script_result[0].get("result"):
                        btn_result = script_result[0]["result"]
                        if btn_result.get("found"):
                            print(f"✓ Found and clicked button: {btn_result.get('text')}")
                        else:
                            print("⚠️  No Perplexity button found")
                break

        await asyncio.sleep(2)

        # Try 3: Try common keyboard shortcuts
        print("\n🔍 Try 3: Trying keyboard shortcuts...")
        print("   (Ctrl+Shift+P, Cmd+K, Cmd+J)")

        shortcuts = [
            "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'p', ctrlKey: true, shiftKey: true}));",
            "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'k', metaKey: true}));",
            "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'j', metaKey: true}));",
        ]

        for i, shortcut_code in enumerate(shortcuts):
            cmd_id = f"shortcut-{i}"
            await ws.send(json.dumps({
                "command": True,
                "id": cmd_id,
                "action": "EXECUTE_SCRIPT",
                "tabId": tab_id,
                "params": {"code": shortcut_code}
            }))

            async for message in ws:
                data = json.loads(message)
                if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
                    break

            await asyncio.sleep(1)

        print("   ✓ Triggered keyboard shortcuts")

    # Final check
    print("\n🔍 Final check: Is Comet open now?")
    await asyncio.sleep(2)

    cmd_id = "check-final"
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
                print(f"\nComet state: {json.dumps(result, indent=2)}")
            else:
                print("❌ Comet still not detected")
                print("\n💡 Manual steps:")
                print("   1. Open Perplexity extension sidebar (check if it's installed)")
                print("   2. Or use Cmd+Shift+E / Ctrl+Shift+E if you have Arc browser")
                print("   3. Or click the Perplexity extension icon in Chrome toolbar")
            break

    print("\n" + "=" * 70)
    await ws.close()


if __name__ == "__main__":
    asyncio.run(open_comet())
