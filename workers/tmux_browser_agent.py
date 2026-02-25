#!/usr/bin/env python3
"""
Tmux Browser Agent
Runs in tmux, takes screenshots, Claude Code analyzes them and provides actions
"""

import sys
import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class TmuxBrowserAgent:
    """Browser agent that works with Claude Code via screenshots."""

    def __init__(self):
        self.driver = None
        self.step = 0

    def start_browser(self):
        """Start browser."""
        options = Options()
        options.add_argument('--start-maximized')

        print("🚀 Starting browser...")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        print("✅ Browser ready")

    def take_screenshot_and_get_info(self):
        """Take screenshot and return page info."""
        self.step += 1
        screenshot_path = f"/tmp/browser_step_{self.step}.png"
        self.driver.save_screenshot(screenshot_path)

        page_text = self.driver.find_element(By.TAG_NAME, 'body').text

        info = {
            'step': self.step,
            'url': self.driver.current_url,
            'title': self.driver.title,
            'screenshot': screenshot_path,
            'page_text_preview': page_text[:1000]
        }

        return info

    def execute_action(self, action, target=None, username=None, password=None):
        """Execute an action based on Claude Code's instruction."""
        print(f"\n🎬 Executing: {action}")

        try:
            if action == "CLICK":
                element = self.driver.find_element(By.PARTIAL_LINK_TEXT, target)
                element.click()
                print(f"✅ Clicked: {target}")
                time.sleep(3)
                return True

            elif action == "FILL_LOGIN":
                # Find email field
                for selector in ['input[type="email"]', 'input[name="email"]', 'input[name="username"]']:
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, selector).send_keys(username)
                        print(f"✅ Filled username")
                        break
                    except:
                        continue

                # Fill password
                self.driver.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(password)
                print(f"✅ Filled password")
                time.sleep(1)
                return True

            elif action == "SUBMIT":
                self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]').click()
                print(f"✅ Submitted form")
                time.sleep(5)
                return True

            elif action == "SCROLL":
                self.driver.execute_script("window.scrollBy(0, 800)")
                print(f"✅ Scrolled")
                time.sleep(2)
                return True

        except Exception as e:
            print(f"❌ Action failed: {e}")
            return False

    def close(self):
        """Close browser."""
        if self.driver:
            print("\n⏸  Keeping browser open for 10 seconds...")
            time.sleep(10)
            self.driver.quit()
            print("✅ Browser closed")


def main():
    """Main function - navigate to AquaTech and wait for Claude Code instructions."""

    goal = sys.argv[1] if len(sys.argv) > 1 else "Find pricing information"
    url = sys.argv[2] if len(sys.argv) > 2 else "https://www.aquatechswim.com"
    username = sys.argv[3] if len(sys.argv) > 3 else None
    password = sys.argv[4] if len(sys.argv) > 4 else None

    agent = TmuxBrowserAgent()
    agent.start_browser()

    try:
        print(f"\n🎯 Goal: {goal}")
        print(f"🌐 URL: {url}")
        print("="*70)

        # Navigate to start URL
        agent.driver.get(url)
        time.sleep(3)

        # Take initial screenshot
        info = agent.take_screenshot_and_get_info()

        print(f"\n📍 STEP {info['step']}")
        print(f"📄 Page: {info['title']}")
        print(f"🔗 URL: {info['url']}")
        print(f"📸 Screenshot: {info['screenshot']}")
        print(f"\n📝 Page preview:")
        print(info['page_text_preview'][:500])
        print("\n" + "="*70)

        # Save info for Claude Code to read
        with open('/tmp/browser_current_state.json', 'w') as f:
            json.dump(info, f, indent=2)

        print(f"\n💡 CLAUDE CODE: Please read {info['screenshot']}")
        print(f"💡 Then provide next action by running:")
        print(f"   python3 workers/tmux_browser_agent.py action <ACTION> <TARGET>")
        print(f"\n   Available actions:")
        print(f"   - CLICK 'link text'")
        print(f"   - FILL_LOGIN")
        print(f"   - SUBMIT")
        print(f"   - SCROLL")
        print(f"   - DONE 'answer'")

        # Wait for next command
        print(f"\n⏸  Waiting for next action...")
        print(f"   (Browser will stay open)")

        # Keep browser alive
        time.sleep(300)  # 5 minutes

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
    finally:
        agent.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'action':
        # Execute action on existing browser
        # This would need browser handle - for now just print
        print(f"Action mode: {sys.argv[2:]}")
    else:
        main()
