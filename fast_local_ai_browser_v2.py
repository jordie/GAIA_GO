#!/usr/bin/env python3
"""
Fast Local AI Browser v2 - WITH CONTEXT TRACKING
Adds action history and feedback to help models complete workflows
"""

import base64
import json
import os
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class FastLocalAIBrowserV2:
    """
    Improved AI browser with context tracking and action history.
    """

    def __init__(self, model="llama3.2-vision", headless=False):
        self.model = model
        self.headless = headless
        self.driver = None
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        # Action history for context
        self.action_history = []
        self.last_page_text = ""

        # Model-specific optimizations
        self.use_vision = "vision" in model or "llava" in model or "vl" in model or model in ["moondream", "phi3"]

        print("🚀 Fast Local AI Browser v2 (WITH CONTEXT)")
        print(f"   Model: {model}")
        print(f"   Vision: {'Yes' if self.use_vision else 'No (HTML-based)'}")

    def start_browser(self):
        """Start browser."""
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        print("✅ Browser started")

    def get_page_context(self):
        """Get page context with change detection."""
        if self.use_vision:
            screenshot_path = "/tmp/fast_browser_screen.png"
            self.driver.save_screenshot(screenshot_path)

            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            text = self.driver.find_element(By.TAG_NAME, "body").text[:500]

            # Detect what changed
            page_changed = text != self.last_page_text
            self.last_page_text = text

            return {
                "type": "vision",
                "image": image_data,
                "text_preview": text,
                "page_changed": page_changed
            }
        else:
            html = self.driver.page_source

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            for tag in soup(["script", "style", "meta", "link"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Detect what changed
            page_changed = text != self.last_page_text
            self.last_page_text = text

            elements = []
            for tag in soup.find_all(["a", "button", "input"]):
                elem_info = {
                    "tag": tag.name,
                    "text": tag.get_text(strip=True)[:50],
                    "type": tag.get("type", ""),
                    "href": tag.get("href", ""),
                }
                if any(elem_info.values()):
                    elements.append(elem_info)

            return {
                "type": "text",
                "text": text[:2000],
                "elements": elements[:20],
                "page_changed": page_changed
            }

    def ask_ai_with_context(self, goal, context, step_num, max_steps):
        """
        Ask AI with full context and history.
        """
        # Build history context
        history_text = ""
        if self.action_history:
            history_text = "\n\nPrevious actions:\n"
            for i, action in enumerate(self.action_history[-5:], 1):  # Last 5 actions
                status = "✓" if action.get("success") else "✗"
                history_text += f"{i}. {action['action']} [{status}]\n"

        # Page change feedback
        change_feedback = ""
        if context.get("page_changed"):
            change_feedback = "\n(Page content changed since last action)"
        else:
            change_feedback = "\n(Page content unchanged - might need different action)"

        # Build prompt with context
        prompt = f"""Task: {goal}

Step {step_num}/{max_steps}{history_text}{change_feedback}

What is the SINGLE next action to make progress?

Reply with EXACTLY ONE of these formats:
CLICK Login
CLICK Customer Portal
TYPE email jdoe@example.com
TYPE password mypass123
SUBMIT
SCROLL
DONE monthly payment is $150

DO NOT:
- Repeat previous actions
- Use placeholder text like "exact text" or "field"
- Give explanations
- Say the same action twice

Your response (one line only):"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 100,
                "num_ctx": 2048,
                "top_k": 10,
                "top_p": 0.9,
            },
        }

        if context["type"] == "vision":
            payload["images"] = [context["image"]]
            payload["prompt"] = f"{prompt}\n\nPage preview: {context['text_preview']}"
        else:
            payload["prompt"] = f"""{prompt}

Page text: {context['text'][:1000]}

Interactive elements:
{json.dumps(context['elements'], indent=2)}"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            return f"❌ Error: {e}"

    def navigate_with_context(self, url, goal, max_steps=8):
        """
        Navigate with context tracking.
        """
        print(f"\n🎯 Goal: {goal}")
        print(f"🌐 URL: {url}")
        print(f"🤖 Model: {self.model}")
        print("=" * 70)

        self.driver.get(url)
        time.sleep(2)
        self.last_page_text = self.driver.find_element(By.TAG_NAME, "body").text

        for step in range(1, max_steps + 1):
            print(f"\n📍 Step {step}/{max_steps}")

            start_time = time.time()

            # Get context
            context = self.get_page_context()

            # Ask AI with full context
            print("🤔 Analyzing (with context)...")
            decision = self.ask_ai_with_context(goal, context, step, max_steps)

            duration = time.time() - start_time
            print(f"💡 Decision ({duration:.1f}s): {decision[:80]}")

            # Track action
            action_record = {
                "step": step,
                "action": decision[:50],
                "success": False,
                "page_changed": False
            }

            # Execute
            if "DONE" in decision:
                answer = decision.replace("DONE", "").strip().strip('"')
                print("\n✅ Goal achieved!")
                print(f"📊 Answer: {answer}")
                action_record["success"] = True
                self.action_history.append(action_record)
                break

            elif "CLICK" in decision:
                try:
                    text = (
                        decision.split('"')[1]
                        if '"' in decision
                        else decision.replace("CLICK", "").strip()
                    )

                    # Try multiple strategies
                    element = None
                    try:
                        element = self.driver.find_element(By.PARTIAL_LINK_TEXT, text)
                    except:
                        try:
                            element = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{text}')]")
                        except:
                            pass

                    if element:
                        self.driver.execute_script("arguments[0].click();", element)
                        print(f"✅ Clicked: {text}")
                        action_record["success"] = True
                        time.sleep(2)

                        # Check if page changed
                        new_text = self.driver.find_element(By.TAG_NAME, "body").text
                        action_record["page_changed"] = new_text != self.last_page_text
                    else:
                        print(f"❌ Click failed: Element '{text}' not found")

                except Exception as e:
                    print(f"❌ Click failed: {e}")

            elif "TYPE" in decision:
                try:
                    parts = decision.replace("TYPE", "").strip().split()
                    if len(parts) >= 2:
                        field = parts[0]
                        value = " ".join(parts[1:])
                        print(f"✅ Type: {field} = {value}")
                        action_record["success"] = True
                except Exception as e:
                    print(f"❌ Type failed: {e}")

            elif "SCROLL" in decision:
                self.driver.execute_script("window.scrollBy(0, 600)")
                print("✅ Scrolled")
                action_record["success"] = True
                time.sleep(1)

            else:
                print("⚠️  Unknown action")

            self.action_history.append(action_record)

        print(f"\n{'='*70}")
        print("🏁 Navigation complete")
        print(f"\n📊 Action Success Rate: {sum(1 for a in self.action_history if a['success'])}/{len(self.action_history)}")

    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            print("✅ Browser closed")


def main():
    """Test improved AI browser."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 fast_local_ai_browser_v2.py <model> <goal> [url]")
        print("\nExample:")
        print('  python3 fast_local_ai_browser_v2.py llama3.2 "Login to customer portal" https://example.com')
        return

    model = sys.argv[1]
    goal = sys.argv[2]
    url = sys.argv[3] if len(sys.argv) > 3 else "https://www.aquatechswim.com"

    agent = FastLocalAIBrowserV2(model=model, headless=False)
    agent.start_browser()

    try:
        agent.navigate_with_context(url, goal)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
    finally:
        agent.close()


if __name__ == "__main__":
    main()
