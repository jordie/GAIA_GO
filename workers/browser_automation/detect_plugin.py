#!/usr/bin/env python3
"""
Detect and communicate with Perplexity/Comet plugin
"""

import asyncio
import json
import websockets


async def detect_plugin():
    """Detect the Perplexity plugin and try to communicate with it."""
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
            print(f"✓ Tab {tab_id}\n")
            break

    # Wait for load
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            break

    await asyncio.sleep(2)

    print("📝 Press Option+A to open Perplexity sidebar")
    input("Press Enter when sidebar is visible...\n")

    print("=" * 70)
    print("PLUGIN DETECTION")
    print("=" * 70)

    print("\n🔍 Detecting plugin/extension APIs...\n")

    cmd_id = "detect"
    await ws.send(json.dumps({
        "command": True,
        "id": cmd_id,
        "action": "DETECT_PLUGIN",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == cmd_id:
            cmd_result = data["data"]

            if cmd_result.get("status") != "success":
                print(f"❌ Command failed: {cmd_result.get('message')}")
                break

            result = cmd_result.get("result")
            if result:
                print("✓ Detection Results:\n")

                print("🌐 Window Global APIs:")
                globals = result.get('windowGlobals', {})
                for key, val in globals.items():
                    status = "✓" if val else "✗"
                    print(f"   {status} {key}")

                print(f"\n🔧 Custom Window Properties ({len(result.get('customWindowProps', []))}):")
                for prop in result.get('customWindowProps', [])[:15]:
                    print(f"   - {prop}")

                print(f"\n🎯 Chrome Extensions:")
                chrome_ext = result.get('chromeExtensions', {})
                print(f"   Has chrome.runtime: {chrome_ext.get('hasChromeRuntime')}")
                print(f"   Extension ID: {chrome_ext.get('extensionId', 'N/A')}")
                print(f"   Chrome keys: {', '.join(chrome_ext.get('chromeKeys', [])[:10])}")

                print(f"\n🔍 Suspect Global APIs ({len(result.get('suspectGlobals', []))}):")
                for suspect in result.get('suspectGlobals', [])[:5]:
                    print(f"   - {suspect['name']}: {', '.join(suspect['keys'][:5])}")

                if result.get('customDataAttributes'):
                    print(f"\n📝 Custom Data Attributes:")
                    for attr in result.get('customDataAttributes', [])[:10]:
                        print(f"   - {attr}")

                print("\n" + "=" * 70)
                print("\n💡 NEXT STEPS:")

                if chrome_ext.get('extensionId'):
                    print(f"   ✓ Found extension ID: {chrome_ext['extensionId']}")
                    print("   Can try: chrome.runtime.sendMessage(extensionId, message)")

                if any(globals.values()):
                    found_apis = [k for k, v in globals.items() if v]
                    print(f"   ✓ Found APIs: {', '.join(found_apis)}")
                    print("   Can try calling methods on these objects")

                if result.get('suspectGlobals'):
                    print(f"   ✓ Found {len(result['suspectGlobals'])} suspect global objects")
                    print("   Investigate these for potential API methods")

                if not any([chrome_ext.get('extensionId'), any(globals.values()), result.get('suspectGlobals')]):
                    print("   ⚠️  No obvious plugin APIs detected")
                    print("   The sidebar might be:")
                    print("      - A browser-level feature (not accessible via JS)")
                    print("      - In a separate process/window")
                    print("      - Using a non-standard communication method")
            break

    await ws.close()


if __name__ == "__main__":
    asyncio.run(detect_plugin())
