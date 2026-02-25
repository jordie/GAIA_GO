#!/usr/bin/env python3
"""
Browser Automation Agent
Real browser automation using Playwright for authenticated tasks.
"""

import json
import time
from typing import Any, Dict, Optional

from workers.session_state_manager import SessionStateManager


class BrowserAgent:
    """Browser automation agent using Playwright."""

    def __init__(self, headless: bool = False):
        """Initialize browser agent."""
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.session_name: Optional[str] = None
        self.state_manager: Optional[SessionStateManager] = None
        self.operations_count = 0

    def configure_state_tracking(self, session_name: str) -> None:
        """Enable state tracking for monitoring.

        Args:
            session_name: Unique session identifier for state tracking
        """
        self.session_name = session_name
        self.state_manager = SessionStateManager(session_name)
        self.state_manager.set_tool_info("browser_agent", "playwright")
        self.state_manager.set_status("idle")

    def start(self):
        """Start browser instance."""
        try:
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()

            # Launch with less bot-like settings
            self.browser = self.playwright.chromium.launch(
                headless=self.headless, args=["--disable-blink-features=AutomationControlled"]
            )

            # Use realistic viewport and user agent
            user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self.context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
            )

            # Increase default timeout
            self.context.set_default_timeout(60000)  # 60 seconds

            self.page = self.context.new_page()

            print("✅ Browser started")
            if self.state_manager:
                self.state_manager.set_status("idle")
            return True
        except ImportError:
            print("❌ Playwright not installed. Run: pip install playwright && playwright install")
            if self.state_manager:
                self.state_manager.increment_errors()
            return False
        except Exception as e:
            print(f"❌ Failed to start browser: {e}")
            if self.state_manager:
                self.state_manager.increment_errors()
            return False

    def stop(self):
        """Stop browser instance."""
        if self.state_manager:
            self.state_manager.set_status("stopped")
        if self.browser:
            self.browser.close()
        if hasattr(self, "playwright"):
            self.playwright.stop()
        if self.state_manager:
            self.state_manager.cleanup()
        print("✅ Browser stopped")

    def login(
        self,
        url: str,
        username: str,
        password: str,
        username_selector: str = 'input[type="email"], input[name="email"], input[name="username"]',
        password_selector: str = 'input[type="password"]',
        submit_selector: str = 'button[type="submit"], input[type="submit"]',
    ) -> bool:
        """
        Login to a website.

        Args:
            url: Login page URL
            username: Username/email
            password: Password
            username_selector: CSS selector for username field
            password_selector: CSS selector for password field
            submit_selector: CSS selector for submit button

        Returns:
            True if login successful
        """
        try:
            if self.state_manager:
                self.state_manager.set_task(f"Login to {url!r}")
                self.state_manager.set_status("working")

            print(f"🔐 Navigating to {url}")
            self.page.goto(url, wait_until="networkidle")

            print("📝 Entering credentials...")
            # Fill username
            self.page.fill(username_selector, username)
            time.sleep(0.5)

            # Fill password
            self.page.fill(password_selector, password)
            time.sleep(0.5)

            print("🚀 Submitting login form...")
            # Click submit and wait for navigation
            self.page.click(submit_selector)
            self.page.wait_for_load_state("networkidle")

            # Check if login was successful (page changed)
            current_url = self.page.url
            if current_url != url:
                print(f"✅ Login successful - redirected to {current_url}")
                if self.state_manager:
                    self.operations_count += 1
                    self.state_manager.set_metadata("operations", self.operations_count)
                    self.state_manager.set_metadata("last_operation", "login")
                    self.state_manager.clear_task()
                    self.state_manager.set_status("idle")
                return True
            else:
                print(f"⚠️  Still on login page - check credentials or selectors")
                if self.state_manager:
                    self.state_manager.clear_task()
                    self.state_manager.set_status("idle")
                return False

        except Exception as e:
            print(f"❌ Login failed: {e}")
            if self.state_manager:
                self.state_manager.increment_errors()
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
            self.page.screenshot(path="/tmp/login_error.png")
            print("📸 Screenshot saved to /tmp/login_error.png")
            return False

    def navigate(self, url: str):
        """Navigate to URL."""
        try:
            if self.state_manager:
                self.state_manager.set_task(f"Navigate to {url}")
                self.state_manager.set_status("working")
            print(f"🌐 Navigating to {url}")
            self.page.goto(url, wait_until="load")  # Less strict than networkidle
            print(f"✅ Loaded {self.page.title()}")
            if self.state_manager:
                self.operations_count += 1
                self.state_manager.set_metadata("operations", self.operations_count)
                self.state_manager.set_metadata("last_operation", "navigate")
                self.state_manager.set_metadata("current_url", self.page.url)
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            if self.state_manager:
                self.state_manager.increment_errors()
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")

    def extract_text(self, selector: str) -> Optional[str]:
        """Extract text from element."""
        try:
            if self.state_manager:
                self.state_manager.set_task(f"Extract text: {selector[:50]}")
                self.state_manager.set_status("working")
            element = self.page.locator(selector)
            if element.count() > 0:
                text = element.first.inner_text()
                if self.state_manager:
                    self.operations_count += 1
                    self.state_manager.set_metadata("operations", self.operations_count)
                    self.state_manager.set_metadata("last_operation", "extract_text")
                    self.state_manager.clear_task()
                    self.state_manager.set_status("idle")
                return text
            if self.state_manager:
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
            return None
        except Exception as e:
            print(f"⚠️  Could not extract text: {e}")
            if self.state_manager:
                self.state_manager.increment_errors()
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
            return None

    def extract_all_text(self, selector: str) -> list:
        """Extract text from all matching elements."""
        try:
            elements = self.page.locator(selector)
            return [elements.nth(i).inner_text() for i in range(elements.count())]
        except Exception as e:
            print(f"⚠️  Could not extract text: {e}")
            return []

    def click(self, selector: str):
        """Click an element."""
        try:
            self.page.click(selector)
            print(f"✅ Clicked {selector}")
        except Exception as e:
            print(f"❌ Click failed: {e}")

    def screenshot(self, path: str = "/tmp/screenshot.png"):
        """Take a screenshot."""
        try:
            if self.state_manager:
                self.state_manager.set_task(f"Screenshot: {path}")
                self.state_manager.set_status("working")
            self.page.screenshot(path=path)
            print(f"📸 Screenshot saved to {path}")
            if self.state_manager:
                self.operations_count += 1
                self.state_manager.set_metadata("operations", self.operations_count)
                self.state_manager.set_metadata("last_operation", "screenshot")
                self.state_manager.set_metadata("last_screenshot_path", path)
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
            return path
        except Exception as e:
            print(f"❌ Screenshot failed: {e}")
            if self.state_manager:
                self.state_manager.increment_errors()
                self.state_manager.clear_task()
                self.state_manager.set_status("idle")
            return None

    def get_page_text(self) -> str:
        """Get all text from current page."""
        return self.page.inner_text("body")

    def wait_for_selector(self, selector: str, timeout: int = 30000):
        """Wait for element to appear."""
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False


def aquatech_get_pricing(username: str, password: str, output_file: str) -> Dict[str, Any]:
    """
    Specific task: Get AquaTech pricing from customer portal.

    Args:
        username: AquaTech account username
        password: AquaTech account password
        output_file: Path to save results

    Returns:
        Dictionary with pricing info
    """
    agent = BrowserAgent(headless=False)  # Show browser for debugging

    try:
        if not agent.start():
            return {"error": "Failed to start browser"}

        # Navigate to AquaTech
        print("\n🏊 Accessing AquaTech Swim School...")
        agent.navigate("https://www.aquatechswim.com")
        time.sleep(2)

        # Look for login link
        print("🔍 Looking for login/account link...")
        agent.screenshot("/tmp/aquatech_home.png")

        # Try common login selectors
        login_selectors = [
            'a[href*="login"]',
            'a[href*="account"]',
            'a[href*="portal"]',
            'a:has-text("Login")',
            'a:has-text("Sign In")',
            'a:has-text("My Account")',
        ]

        login_found = False
        for selector in login_selectors:
            try:
                if agent.page.locator(selector).count() > 0:
                    print(f"✅ Found login link: {selector}")
                    agent.click(selector)
                    login_found = True
                    time.sleep(2)
                    break
            except:
                continue

        if not login_found:
            print("⚠️  Could not find login link automatically")
            print("📄 Page text preview:")
            page_text = agent.get_page_text()[:500]
            print(page_text)

            result = {
                "status": "login_link_not_found",
                "page_url": agent.page.url,
                "page_title": agent.page.title(),
                "screenshot": "/tmp/aquatech_home.png",
                "note": "Could not locate login link. Manual intervention may be needed.",
            }

            # Save result
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)

            return result

        # Try to login
        print("🔐 Attempting login...")
        agent.screenshot("/tmp/aquatech_login.png")

        success = agent.login(url=agent.page.url, username=username, password=password)

        if not success:
            result = {
                "status": "login_failed",
                "screenshot": "/tmp/login_error.png",
                "note": "Login failed. Check credentials or page structure.",
            }

            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)

            return result

        # Login successful - navigate to billing/account info
        print("💰 Looking for billing/pricing information...")
        time.sleep(3)

        # Take screenshot of logged-in dashboard
        agent.screenshot("/tmp/aquatech_dashboard.png")

        # Try to find billing/pricing info
        billing_selectors = [
            'a[href*="billing"]',
            'a[href*="payment"]',
            'a[href*="invoice"]',
            'a:has-text("Billing")',
            'a:has-text("Payment")',
            'a:has-text("Account")',
        ]

        for selector in billing_selectors:
            try:
                if agent.page.locator(selector).count() > 0:
                    print(f"✅ Found billing link: {selector}")
                    agent.click(selector)
                    time.sleep(2)
                    break
            except:
                continue

        # Extract all text from current page
        page_text = agent.get_page_text()

        # Take final screenshot
        agent.screenshot("/tmp/aquatech_final.png")

        # Parse for pricing information
        import re

        # Look for dollar amounts
        prices = re.findall(r"\$[\d,]+\.?\d*", page_text)

        # Look for student names
        students = []
        if "student" in page_text.lower() or "child" in page_text.lower():
            # Extract context around these words
            lines = page_text.split("\n")
            for line in lines:
                if "student" in line.lower() or "child" in line.lower():
                    students.append(line.strip())

        result = {
            "status": "success",
            "current_url": agent.page.url,
            "page_title": agent.page.title(),
            "prices_found": prices,
            "student_info": students[:5],  # First 5 matches
            "screenshots": {
                "home": "/tmp/aquatech_home.png",
                "login": "/tmp/aquatech_login.png",
                "dashboard": "/tmp/aquatech_dashboard.png",
                "final": "/tmp/aquatech_final.png",
            },
            "page_excerpt": page_text[:1000],  # First 1000 chars
        }

        # Save result
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\n✅ Results saved to {output_file}")
        print(f"💵 Prices found: {prices}")

        return result

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

        result = {"status": "error", "error": str(e)}

        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        return result

    finally:
        input("\n⏸  Press Enter to close browser...")
        agent.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Browser Automation Agent")
    parser.add_argument("task", choices=["aquatech-pricing"], help="Task to perform")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument("--output", default="/tmp/browser_agent_output.json", help="Output file")

    args = parser.parse_args()

    if args.task == "aquatech-pricing":
        result = aquatech_get_pricing(args.username, args.password, args.output)
        print("\n" + "=" * 60)
        print("RESULT:")
        print(json.dumps(result, indent=2))
