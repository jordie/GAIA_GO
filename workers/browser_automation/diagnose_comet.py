#!/usr/bin/env python3
"""
Diagnose what Perplexity sidebar elements exist
"""

import asyncio
import json
import websockets


async def diagnose():
    """Find out what sidebar elements exist."""
    ws_url = "ws://localhost:8765"

    print("Connecting...")
    ws = await websockets.connect(ws_url)
    print("✓ Connected\n")

    # Wait for state
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            break

    # Open fresh tab
    print("Opening fresh tab...")
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
            print(f"✓ Tab {tab_id}")
            break

    # Wait for load
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            break

    await asyncio.sleep(2)

    print("\n📝 NOW: Press Option+A to open Perplexity sidebar")
    input("Press Enter when sidebar is visible...\n")

    print("=" * 70)
    print("DIAGNOSTIC SCAN")
    print("=" * 70)

    # Scan for various sidebar patterns
    print("\n🔍 Scanning for sidebar elements...\n")

    cmd_id = "diagnose"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "DIAGNOSE_SIDEBAR",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            cmd_result = data["data"]

            if cmd_result.get("status") != "success":
                print(f"❌ Command failed: {cmd_result.get('message')}")
                print(f"Full response: {json.dumps(cmd_result, indent=2)}")
                break

            scan = cmd_result.get("result")
            if scan:

                print("✓ Diagnostic Results:\n")
                print(f"📌 Expected selectors:")
                print(f"   [data-erpsidecar]: {scan['dataErpsidecar']}")
                print(f"   #ask-input: {scan['askInput']}")

                print(f"\n🌐 Page structure:")
                print(f"   iframes: {scan['iframes']}")
                print(f"   shadow roots: {scan['shadowRoots']}")

                if scan.get('iframeInfo'):
                    print(f"\n🖼️  Iframe details:")
                    for iframe in scan['iframeInfo']:
                        print(f"   [{iframe['index']}] {iframe.get('src', 'no src')[:80]}")
                        print(f"       ID: {iframe.get('id', 'none')}, Class: {iframe.get('className', 'none')[:50]}")
                        print(f"       Can access: {iframe.get('canAccess', False)}")
                        if iframe.get('canAccess'):
                            print(f"       Has ask-input: {iframe.get('hasAskInput', False)}")
                            print(f"       Has data-erpsidecar: {iframe.get('hasDataErpsidecar', False)}")
                            print(f"       Looks like Perplexity: {iframe.get('hasPerplexity', False)}")
                        elif iframe.get('error'):
                            print(f"       Error: {iframe['error']}")
                        print()

                print(f"\n🔎 Perplexity elements:")
                print(f"   By class: {scan['perplexityElements']['byClass']}")
                print(f"   By ID: {scan['perplexityElements']['byId']}")
                print(f"   By data-attr: {scan['perplexityElements']['byDataAttr']}")

                print(f"\n📂 Sidebar elements:")
                print(f"   By class: {scan['sidebarElements']['byClass']}")
                print(f"   By ID: {scan['sidebarElements']['byId']}")
                print(f"   By data-attr: {scan['sidebarElements']['byDataAttr']}")

                print(f"\n🤖 AI interface elements:")
                print(f"   Chat inputs: {scan['aiElements']['chatInput']}")
                print(f"   Textareas: {scan['aiElements']['textareas']}")
                print(f"   Submit buttons: {scan['aiElements']['submitButtons']}")

                print(f"\n🎯 Specific checks:")
                for key, val in scan['specificChecks'].items():
                    print(f"   {key}: {val}")

                if scan.get('sampleElements'):
                    print(f"\n📋 Sample sidebar-related elements:")
                    for el in scan['sampleElements']:
                        print(f"   <{el['tag']} id='{el['id']}' class='{el['classes'][:50]}' visible={el.get('visible', '?')}>")

                if scan.get('allIds'):
                    print(f"\n🆔 All element IDs on page (first 50):")
                    for elem_id in scan['allIds'][:20]:
                        print(f"   - {elem_id}")

                print("\n" + "=" * 70)
                print("\n💡 Next steps:")
                print("   Based on the results above, I can update the content script")
                print("   to use the correct selectors for Comet browser's Perplexity sidebar")
            else:
                print("❌ Unexpected result structure:")
                print(json.dumps(cmd_result, indent=2))
            break

    await ws.close()


if __name__ == "__main__":
    asyncio.run(diagnose())
