#!/usr/bin/env python3
"""
Playwright Task Handler
Executes browser automation tasks received from the agent router.
"""

import json
import logging
import re
import sys
from pathlib import Path

from session_state_manager import SessionStateManager

logger = logging.getLogger(__name__)

# Session name for this handler
HANDLER_SESSION_NAME = "playwright_task_handler"
BROWSER_SESSION_NAME = "playwright_browser_agent"


def parse_task(task_description: str) -> dict:
    """Parse task description to extract credentials and instructions."""
    task_info = {
        "type": "generic",
        "url": None,
        "username": None,
        "password": None,
        "actions": [],
        "output_format": "json",
    }

    # Extract URL
    url_match = re.search(r"https?://[^\s]+", task_description)
    if url_match:
        task_info["url"] = url_match.group(0)

    # Extract username
    username_match = re.search(r"username[:\s]+([^\s]+)", task_description, re.IGNORECASE)
    if username_match:
        task_info["username"] = username_match.group(1)

    # Extract password
    password_match = re.search(r"password[:\s]+([^\s]+)", task_description, re.IGNORECASE)
    if password_match:
        task_info["password"] = password_match.group(1)

    # Determine task type
    if "login" in task_description.lower():
        task_info["type"] = "login_and_extract"
    elif "scrape" in task_description.lower():
        task_info["type"] = "scrape"
    elif "screenshot" in task_description.lower():
        task_info["type"] = "screenshot"

    # Parse actions
    if "navigate to" in task_description.lower():
        nav_match = re.search(r"navigate to ([^\s]+)", task_description, re.IGNORECASE)
        if nav_match:
            task_info["actions"].append(("navigate", nav_match.group(1)))

    if "click" in task_description.lower():
        task_info["actions"].append(("click", None))

    if "extract" in task_description.lower() or "find" in task_description.lower():
        task_info["actions"].append(("extract", None))

    return task_info


def execute_playwright_task(task_description: str, work_dir: str, output_file: str = "result.json"):
    """Execute a Playwright task based on description."""
    from browser_agent import BrowserAgent

    # Initialize handler-level state manager (parent)
    handler_state = SessionStateManager(HANDLER_SESSION_NAME)
    handler_state.set_tool_info("playwright_task_handler", "browser_automation")
    handler_state.set_task(f"Task: {task_description[:100]}")
    handler_state.set_status("working")

    print(f"📋 Task: {task_description}")
    print(f"📁 Work directory: {work_dir}")

    # Parse task
    task_info = parse_task(task_description)
    handler_state.set_metadata("task_type", task_info["type"])
    handler_state.set_metadata("task_parsed", True)
    print(f"🔍 Parsed task info: {json.dumps(task_info, indent=2)}")

    # Create output path
    output_path = Path(work_dir) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handler_state.set_metadata("output_path", str(output_path))

    # Initialize browser with separate state tracking (child)
    agent = BrowserAgent(headless=False)
    agent.configure_state_tracking(BROWSER_SESSION_NAME)

    try:
        if not agent.start():
            handler_state.increment_errors()
            handler_state.set_metadata("error", "Failed to start browser")
            handler_state.clear_task()
            handler_state.set_status("idle")
            result = {"error": "Failed to start browser"}
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            return result

        result = {"status": "success", "data": {}}

        # Execute based on task type
        if task_info["type"] == "login_and_extract":
            # Navigate to URL
            if task_info["url"]:
                agent.navigate(task_info["url"])

            # Attempt login if credentials provided
            if task_info["username"] and task_info["password"]:
                print("🔐 Attempting login...")
                success = agent.login(
                    url=agent.page.url,
                    username=task_info["username"],
                    password=task_info["password"],
                )
                result["login_success"] = success

                if success:
                    # Take screenshot
                    screenshot_path = str(output_path.parent / "logged_in.png")
                    agent.screenshot(screenshot_path)
                    result["screenshot"] = screenshot_path

                    # Extract page text
                    page_text = agent.get_page_text()
                    result["data"]["page_text"] = page_text[:2000]  # First 2000 chars

                    # Try to find pricing/financial info
                    import re

                    prices = re.findall(r"\$[\d,]+\.?\d*", page_text)
                    result["data"]["prices_found"] = prices

                    # Look for monthly/weekly patterns
                    monthly_matches = re.findall(
                        r"(monthly|per month|/month)[^\n]{0,50}", page_text, re.IGNORECASE
                    )
                    result["data"]["monthly_info"] = monthly_matches[:5]

                    weekly_matches = re.findall(
                        r"(weekly|per week|/week)[^\n]{0,50}", page_text, re.IGNORECASE
                    )
                    result["data"]["weekly_info"] = weekly_matches[:5]

        elif task_info["type"] == "scrape":
            if task_info["url"]:
                agent.navigate(task_info["url"])
                page_text = agent.get_page_text()
                result["data"]["content"] = page_text

                screenshot_path = str(output_path.parent / "scrape.png")
                agent.screenshot(screenshot_path)
                result["screenshot"] = screenshot_path

        elif task_info["type"] == "screenshot":
            if task_info["url"]:
                agent.navigate(task_info["url"])
                screenshot_path = str(output_path.parent / "screenshot.png")
                agent.screenshot(screenshot_path)
                result["screenshot"] = screenshot_path

        # Save result
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        handler_state.set_metadata("result_success", True)
        handler_state.set_metadata("output_written", str(output_path))
        handler_state.clear_task()
        handler_state.set_status("idle")

        print("\n✅ Task completed")
        print(f"📄 Results saved to: {output_path}")

        return result

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

        handler_state.increment_errors()
        handler_state.set_metadata("error", str(e))
        handler_state.clear_task()
        handler_state.set_status("idle")

        result = {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        return result

    finally:
        print("\n⏸  Closing browser in 5 seconds...")
        import time

        time.sleep(5)
        agent.stop()
        # Handler cleanup
        handler_state.cleanup()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: playwright_task_handler.py <task_description> <work_dir> [output_file]")
        sys.exit(1)

    task_desc = sys.argv[1]
    work_dir = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else "result.json"

    execute_playwright_task(task_desc, work_dir, output_file)
