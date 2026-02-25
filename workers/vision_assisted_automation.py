#!/usr/bin/env python3
"""
Vision-Assisted Browser Automation
Uses local LLM with vision (Ollama llava) to navigate pages and extract information
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import websocket

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.vault_service import get_login_credentials


class VisionAssistedAutomation:
    """Browser automation guided by vision LLM."""

    def __init__(self, site_key: str, search_term: str, goal: str):
        self.site_key = site_key
        self.search_term = search_term
        self.goal = goal
        self.ws = None
        self.msg_id = 1
        self.credentials = None
        self.screenshots = []
        self.steps_taken = []

        # LLM configuration
        self.ollama_url = "http://localhost:11434/api/generate"
        self.llava_model = "llava:7b"

    def _execute_js(self, expression: str) -> Any:
        """Execute JavaScript and return result."""
        self.msg_id += 1
        current_id = self.msg_id

        self.ws.send(
            json.dumps(
                {
                    "id": current_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                }
            )
        )

        for _ in range(30):
            try:
                response = json.loads(self.ws.recv())
                if response.get("id") == current_id:
                    if "result" in response and "result" in response["result"]:
                        return response["result"]["result"].get("value")
                    return None
            except:
                return None

        return None

    def _take_screenshot(self) -> Optional[str]:
        """Take screenshot of current page and return base64 encoded."""
        self.msg_id += 1

        self.ws.send(
            json.dumps(
                {"id": self.msg_id, "method": "Page.captureScreenshot", "params": {"format": "png"}}
            )
        )

        for _ in range(30):
            try:
                response = json.loads(self.ws.recv())
                if response.get("id") == self.msg_id:
                    if "result" in response and "data" in response["result"]:
                        return response["result"]["data"]
                    return None
            except:
                return None

        return None

    def _ask_llm_vision(self, screenshot_b64: str, question: str) -> str:
        """Ask Ollama llava to analyze screenshot."""
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.llava_model,
                    "prompt": question,
                    "images": [screenshot_b64],
                    "stream": False,
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")

        except requests.exceptions.Timeout:
            print("   ⚠️ LLM timeout (model may be slow)")
        except Exception as e:
            print(f"   ⚠️ LLM error: {e}")

        return ""

    def _get_page_info(self) -> Dict[str, Any]:
        """Get current page information."""
        info = self._execute_js(
            """
        JSON.stringify({
            url: window.location.href,
            title: document.title,
            bodyText: document.body.innerText.substring(0, 2000),
            hasPassword: !!document.querySelector('input[type="password"]'),
            hasSearch: !!document.querySelector('input[type="search"], input[name="search"]'),
            links: Array.from(document.querySelectorAll('a, button')).slice(0, 20).map(el => ({
                text: (el.innerText || el.textContent || '').trim().substring(0, 50),
                type: el.tagName.toLowerCase()
            }))
        })
        """
        )

        return json.loads(info) if info else {}

    def _click_element(self, text: str) -> bool:
        """Click element by text content."""
        js = f"""
        (function() {{
            const elements = Array.from(document.querySelectorAll('a, button, div[role="button"], input[type="submit"]'));
            for (const el of elements) {{
                const elText = (el.innerText || el.textContent || el.value || '').toLowerCase().trim();
                if (elText.includes('{text.lower()}')) {{
                    el.click();
                    return 'clicked:' + elText.substring(0, 30);
                }}
            }}
            return 'not_found';
        }})()
        """

        result = self._execute_js(js)
        return result and result.startswith("clicked")

    def _fill_credentials(self) -> Dict[str, bool]:
        """Fill login credentials."""
        js = f"""
        (function() {{
            const inputs = Array.from(document.querySelectorAll('input'));
            let emailField = inputs.find(el => el.type === 'email' || el.type === 'text');
            let passField = inputs.find(el => el.type === 'password');

            const results = {{email: false, password: false}};

            if (emailField) {{
                emailField.value = '{self.credentials["username"]}';
                emailField.dispatchEvent(new Event('input', {{bubbles: true}}));
                results.email = true;
            }}

            if (passField) {{
                passField.value = '{self.credentials["password"]}';
                passField.dispatchEvent(new Event('input', {{bubbles: true}}));
                results.password = true;
            }}

            return results;
        }})()
        """

        return self._execute_js(js) or {"email": False, "password": False}

    def run(self):
        """Execute vision-assisted automation."""
        print("\n" + "=" * 70)
        print("Vision-Assisted Browser Automation")
        print(f"Goal: {self.goal}")
        print("=" * 70)

        # Get credentials
        print(f"\n🔐 Loading credentials for {self.site_key}...")
        self.credentials = get_login_credentials(self.site_key)
        print(f"✅ Username: {self.credentials['username']}")

        # Connect to browser
        print("\n🌐 Connecting to browser...")
        tabs = requests.get("http://localhost:9222/json").json()

        # Find matching tab or use first available
        tab = None
        for t in tabs:
            if t["type"] == "page":
                url = t.get("url", "").lower()
                if self.site_key.replace("_", "") in url or "login" in url or "signin" in url:
                    tab = t
                    break

        if not tab:
            tab = next((t for t in tabs if t["type"] == "page"), None)

        if not tab:
            print("❌ No browser tab found")
            return False

        print(f"✅ Tab: {tab.get('title', 'Unknown')[:60]}")

        # Connect CDP
        self.ws = websocket.create_connection(f"ws://localhost:9222/devtools/page/{tab['id']}")
        self.ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        self.ws.recv()
        self.ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
        self.ws.recv()

        print("✅ Connected")

        # Main automation loop
        max_steps = 10
        for step in range(max_steps):
            print(f"\n{'='*70}")
            print(f"STEP {step + 1}/{max_steps}")
            print(f"{'='*70}")

            # Get page info
            page_info = self._get_page_info()
            print(f"\n📄 Page: {page_info.get('title', 'Unknown')}")
            print(f"🔗 URL: {page_info.get('url', 'Unknown')[:80]}")

            # Check if goal achieved
            if (
                self.search_term
                and self.search_term.lower() in page_info.get("bodyText", "").lower()
            ):
                print(f"\n✅ Found '{self.search_term}' on page!")

                # Take screenshot
                print("\n📸 Taking screenshot...")
                screenshot = self._take_screenshot()

                if screenshot:
                    self.screenshots.append(
                        {"step": step + 1, "title": page_info.get("title"), "data": screenshot}
                    )

                    # Ask LLM to extract information
                    print("\n🤖 Asking vision LLM to extract information...")

                    extraction_prompt = f"""
                    This is a screenshot of a website showing information about {self.search_term}.

                    Goal: {self.goal}

                    Please extract and provide:
                    1. All relevant information about {self.search_term}
                    2. Specifically answer: {self.goal}
                    3. List all classes, times, dates, and payment information visible

                    Be thorough and extract all visible details.
                    """

                    result = self._ask_llm_vision(screenshot, extraction_prompt)

                    print("\n" + "=" * 70)
                    print("EXTRACTED INFORMATION")
                    print("=" * 70)
                    print(result)

                    self.ws.close()
                    return True

            # Take screenshot for navigation
            print("\n📸 Taking screenshot for navigation analysis...")
            screenshot = self._take_screenshot()

            if not screenshot:
                print("❌ Could not capture screenshot")
                continue

            self.screenshots.append(
                {"step": step + 1, "title": page_info.get("title"), "data": screenshot}
            )

            # Check if login page
            if page_info.get("hasPassword"):
                print("\n🔐 Login page detected - filling credentials...")

                fill_result = self._fill_credentials()
                print(f"   Email: {'✅' if fill_result.get('email') else '❌'}")
                print(f"   Password: {'✅' if fill_result.get('password') else '❌'}")

                # Click submit
                time.sleep(1)
                if self._click_element("sign") or self._click_element("log"):
                    print("   ✅ Clicked login button")
                    time.sleep(5)
                    continue
                else:
                    print("   ⚠️ Could not find login button")

            # Ask vision LLM what to do next
            print("\n🤖 Asking vision LLM for navigation guidance...")

            navigation_prompt = f"""
            This is a screenshot of a website. I need to find information about "{self.search_term}".

            Goal: {self.goal}

            Current page: {page_info.get('title')}

            What should I click next to find {self.search_term}? Look at the page carefully and tell me:
            1. What link or button text should I click?
            2. Why is this the right next step?

            Respond with ONLY the text of the link/button to click (10 words or less).
            If {self.search_term} is already visible, respond with: "FOUND"
            """

            llm_response = self._ask_llm_vision(screenshot, navigation_prompt)

            print(f"\n   LLM suggests: {llm_response[:100]}")

            if "found" in llm_response.lower():
                print(f"\n✅ LLM says {self.search_term} is visible!")
                continue

            # Extract clickable text from LLM response
            # Try clicking what LLM suggested
            click_terms = llm_response.lower().split()[:5]

            for term in click_terms:
                if len(term) > 3 and term.isalpha():
                    if self._click_element(term):
                        print(f"   ✅ Clicked: {term}")
                        self.steps_taken.append(f"Clicked: {term}")
                        time.sleep(3)
                        break

        print("\n⚠️ Reached maximum steps without finding complete information")
        print(f"\nSteps taken: {len(self.steps_taken)}")
        for i, step in enumerate(self.steps_taken, 1):
            print(f"   {i}. {step}")

        self.ws.close()
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Vision-assisted browser automation")
    parser.add_argument("site", help="Site key (iclasspro, hoh_gymnastics)")
    parser.add_argument("--search", required=True, help="Search term (Saba, Eden)")
    parser.add_argument("--goal", required=True, help="What information to extract")

    args = parser.parse_args()

    automation = VisionAssistedAutomation(args.site, args.search, args.goal)
    success = automation.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
