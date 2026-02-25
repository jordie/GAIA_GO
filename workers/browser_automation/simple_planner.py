#!/usr/bin/env python3
"""
Simple Browser Automation Planner
Proof-of-concept for autonomous browser task execution
"""

import asyncio
import json
import sys
import time
from typing import Dict, List, Optional

import websockets


class SimplePlanner:
    """Simple autonomous browser agent planner."""

    def __init__(self, ws_url="ws://localhost:8765"):
        self.ws_url = ws_url
        self.ws = None
        self.command_counter = 0
        self.browser_state = {"tabs": {}, "groups": {}}
        self.pending_commands = {}
        self.current_tab_id = None

    async def connect(self):
        """Connect to the browser extension."""
        print(f"Connecting to {self.ws_url}...")
        self.ws = await websockets.connect(self.ws_url)
        print("✓ Connected to browser extension")

        # Wait for CONNECTED and FULL_STATE events
        await self.wait_for_connection()

    async def wait_for_connection(self):
        """Wait for extension to send initial state."""
        print("Waiting for browser state...")

        async for message in self.ws:
            data = json.loads(message)

            if data.get("event") == "FULL_STATE":
                # Update browser state
                event_data = data["data"]
                self.browser_state["tabs"] = {
                    tab["id"]: tab for tab in event_data.get("tabs", [])
                }
                self.browser_state["groups"] = {
                    group["id"]: group for group in event_data.get("groups", [])
                }

                print(f"✓ Browser state received: {len(self.browser_state['tabs'])} tabs")
                break

    async def send_command(self, action: str, params: Dict = None, target: str = None, tab_id: int = None) -> str:
        """Send command to extension and return command ID."""
        self.command_counter += 1
        cmd_id = f"cmd-{self.command_counter}"

        command = {
            "command": True,
            "id": cmd_id,
            "action": action
        }

        if params:
            command["params"] = params
        if target:
            command["target"] = target
        if tab_id:
            command["tabId"] = tab_id

        await self.ws.send(json.dumps(command))
        print(f"→ Sent: {action} (id: {cmd_id})")

        self.pending_commands[cmd_id] = {
            "action": action,
            "sent_at": time.time(),
            "result": None
        }

        return cmd_id

    async def wait_for_result(self, cmd_id: str, timeout: float = 30.0) -> Optional[Dict]:
        """Wait for command result."""
        start = time.time()

        while time.time() - start < timeout:
            # Check if we already have the result
            if self.pending_commands[cmd_id]["result"] is not None:
                result = self.pending_commands[cmd_id]["result"]
                del self.pending_commands[cmd_id]
                return result

            # Wait for messages
            try:
                message = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                data = json.loads(message)

                # Handle events
                if data.get("event") == "COMMAND_RESULT":
                    result_data = data["data"]
                    result_cmd_id = result_data["id"]

                    if result_cmd_id in self.pending_commands:
                        self.pending_commands[result_cmd_id]["result"] = result_data

                    if result_cmd_id == cmd_id:
                        del self.pending_commands[cmd_id]
                        return result_data

                # Handle other events
                elif data.get("event"):
                    await self.handle_event(data)

            except asyncio.TimeoutError:
                continue

        print(f"⚠ Timeout waiting for result: {cmd_id}")
        return None

    async def handle_event(self, data: Dict):
        """Handle events from extension."""
        event_type = data.get("event")
        event_data = data.get("data", {})

        if event_type == "PAGE_LOADED":
            tab_id = event_data.get("tabId")
            url = event_data.get("url")
            print(f"← Event: PAGE_LOADED - Tab {tab_id}: {url}")

        elif event_type == "TAB_CREATED":
            tab_id = event_data.get("id")
            self.browser_state["tabs"][tab_id] = event_data
            print(f"← Event: TAB_CREATED - Tab {tab_id}")

    async def open_url(self, url: str) -> int:
        """Open URL in new tab and return tab ID."""
        cmd_id = await self.send_command("OPEN_TAB", {"url": url})
        result = await self.wait_for_result(cmd_id)

        if result and result["status"] == "success":
            tab_id = result["result"][0]["result"]["id"]
            self.current_tab_id = tab_id
            print(f"✓ Opened tab {tab_id}: {url}")
            return tab_id
        else:
            raise Exception(f"Failed to open URL: {result}")

    async def wait_for_page_load(self, tab_id: int, timeout: float = 10.0):
        """Wait for page to finish loading."""
        print(f"Waiting for page to load (tab {tab_id})...")
        start = time.time()

        while time.time() - start < timeout:
            try:
                message = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                data = json.loads(message)

                if data.get("event") == "PAGE_LOADED":
                    if data["data"]["tabId"] == tab_id:
                        print("✓ Page loaded")
                        return

                # Handle command results
                if data.get("event") == "COMMAND_RESULT":
                    result_data = data["data"]
                    cmd_id = result_data["id"]
                    if cmd_id in self.pending_commands:
                        self.pending_commands[cmd_id]["result"] = result_data

            except asyncio.TimeoutError:
                continue

        print("⚠ Timeout waiting for page load")

    async def extract_elements(self, tab_id: int) -> Dict:
        """Extract actionable elements from page."""
        cmd_id = await self.send_command(
            "EXTRACT_ELEMENTS",
            target="content",
            tab_id=tab_id
        )

        result = await self.wait_for_result(cmd_id)

        if result and result["status"] == "success":
            elements = result["result"]
            print(f"✓ Extracted: {len(elements.get('links', []))} links, "
                  f"{len(elements.get('buttons', []))} buttons, "
                  f"{len(elements.get('forms', []))} forms")
            return elements
        else:
            raise Exception(f"Failed to extract elements: {result}")

    async def click_element(self, tab_id: int, selector: str) -> bool:
        """Click element by selector."""
        cmd_id = await self.send_command(
            "CLICK",
            params={"selector": selector},
            target="content",
            tab_id=tab_id
        )

        result = await self.wait_for_result(cmd_id)

        if result and result["status"] == "success":
            print(f"✓ Clicked: {selector}")
            return True
        else:
            print(f"✗ Click failed: {selector}")
            return False

    async def get_page_text(self, tab_id: int) -> str:
        """Get full page text."""
        cmd_id = await self.send_command(
            "GET_PAGE_TEXT",
            target="content",
            tab_id=tab_id
        )

        result = await self.wait_for_result(cmd_id)

        if result and result["status"] == "success":
            text = result["result"]["text"]
            print(f"✓ Got page text: {len(text)} chars")
            return text
        else:
            raise Exception(f"Failed to get page text: {result}")

    def decide_next_action(self, goal: str, elements: Dict, page_text: str = "") -> Optional[str]:
        """
        Simple rule-based decision making.
        TODO: Replace with LLM call (Ollama, Claude Code, etc.)
        """
        links = elements.get("links", [])
        buttons = elements.get("buttons", [])

        # For AquaTech schedule search
        if "schedule" in goal.lower() or "classes" in goal.lower():
            # Look for schedule-related links
            for link in links:
                text_lower = link["text"].lower()
                if any(word in text_lower for word in ["schedule", "classes", "calendar", "my account", "account"]):
                    return link["selector"]

            # Look for schedule-related buttons
            for button in buttons:
                text_lower = button["text"].lower()
                if any(word in text_lower for word in ["schedule", "view", "classes"]):
                    return button["selector"]

        return None

    async def execute_task(self, goal: str, start_url: str, max_steps: int = 10):
        """Execute a browser automation task."""
        print(f"\n{'='*70}")
        print(f"🎯 Goal: {goal}")
        print(f"🌐 Starting URL: {start_url}")
        print(f"{'='*70}\n")

        # Step 1: Open URL
        tab_id = await self.open_url(start_url)
        await self.wait_for_page_load(tab_id)

        # Step 2: Execute navigation loop
        for step in range(1, max_steps + 1):
            print(f"\n📍 Step {step}/{max_steps}")

            # Extract elements
            elements = await self.extract_elements(tab_id)

            # Check if we found what we're looking for
            page_text = await self.get_page_text(tab_id)

            # Simple check: if page mentions Wednesday classes for Saba
            if "wednesday" in page_text.lower() and "saba" in page_text.lower():
                print("\n✅ Found relevant information!")
                print("\nExtracting schedule information...")

                # Look for schedule-related text
                lines = page_text.split('\n')
                relevant_lines = []

                for line in lines:
                    line_lower = line.lower()
                    if any(word in line_lower for word in ["wednesday", "saba", "class", "lesson", "swim"]):
                        if line.strip():
                            relevant_lines.append(line.strip())

                print("\n📅 Schedule Information:")
                for line in relevant_lines[:20]:  # Show first 20 relevant lines
                    print(f"  {line}")

                return True

            # Decide next action
            next_selector = self.decide_next_action(goal, elements, page_text)

            if not next_selector:
                print("⚠ No clear next action found")
                print("\nAvailable links:")
                for link in elements.get("links", [])[:10]:
                    print(f"  - {link['text']}")
                break

            # Execute action
            print(f"💡 Decision: Click '{next_selector}'")
            await self.click_element(tab_id, next_selector)
            await asyncio.sleep(2)  # Wait for navigation

        print("\n⚠ Did not complete goal within max steps")
        return False

    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            print("\n✓ Disconnected from extension")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 simple_planner.py '<goal>' [url]")
        print("\nExample:")
        print("  python3 simple_planner.py 'Find Wednesday classes for Saba' https://www.aquatechswim.com")
        sys.exit(1)

    goal = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else "https://www.aquatechswim.com"

    planner = SimplePlanner()

    try:
        await planner.connect()
        await planner.execute_task(goal, url)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await planner.close()


if __name__ == "__main__":
    asyncio.run(main())
