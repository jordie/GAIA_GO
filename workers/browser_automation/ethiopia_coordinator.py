#!/usr/bin/env python3
"""
Coordinate Ethiopia project research across Perplexity/Comet
"""

import asyncio
import json
import websockets
from pathlib import Path
import sys

async def send_to_perplexity(prompt, tab_group_name):
    """Send a prompt to Perplexity via Comet extension."""

    # Connect to localhost WebSocket (Comet extension)
    ws_url = "ws://localhost:8765"

    try:
        ws = await websockets.connect(ws_url)

        # Wait for FULL_STATE
        async for message in ws:
            data = json.loads(message)
            if data.get("event") == "FULL_STATE":
                break

        print(f"\n{'='*80}")
        print(f"STARTING: {tab_group_name}")
        print(f"{'='*80}")
        print(f"\nPrompt:\n{prompt}\n")

        # Open Perplexity in a new tab
        perplexity_url = "https://www.perplexity.ai"

        await ws.send(json.dumps({
            "command": True,
            "id": f"open-perplexity-{tab_group_name}",
            "action": "OPEN_TAB",
            "params": {"url": perplexity_url}
        }))

        # Wait a bit for tab to load
        await asyncio.sleep(3)

        print(f"✓ Opened Perplexity tab for {tab_group_name}")
        print(f"\nNext: Paste this prompt into Perplexity:\n{'-'*80}\n{prompt}\n{'-'*80}\n")
        print("After getting results, save the conversation URL to the Google Sheet")
        print()

        await ws.close()
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


async def main():
    # Load prompts
    prompts_file = Path("ethiopia_prompts.json")

    if not prompts_file.exists():
        print("Error: ethiopia_prompts.json not found")
        print("Run setup_ethiopia_project.py first")
        sys.exit(1)

    with open(prompts_file) as f:
        data = json.load(f)

    tab_groups = data["tab_groups"]

    print("="*80)
    print("ETHIOPIA PROJECT RESEARCH COORDINATOR")
    print("="*80)
    print()
    print(f"Total tab groups: {len(tab_groups)}")
    print()

    # Process each tab group
    for i, group in enumerate(tab_groups, 1):
        print(f"\n[{i}/{len(tab_groups)}] Processing: {group['name']}")

        # Send to Perplexity
        success = await send_to_perplexity(group['prompt'], group['name'])

        if success:
            # Wait before next one
            if i < len(tab_groups):
                print(f"\nWaiting 10 seconds before next prompt...")
                await asyncio.sleep(10)
        else:
            print(f"Failed to process {group['name']}")
            break

    print("\n" + "="*80)
    print("RESEARCH COORDINATION COMPLETE")
    print("="*80)
    print()
    print("Next steps:")
    print("1. Review Perplexity responses for each topic")
    print("2. Save conversation URLs to Google Sheet")
    print("3. Run aggregator to compile results into Google Doc")
    print()


if __name__ == "__main__":
    asyncio.run(main())
