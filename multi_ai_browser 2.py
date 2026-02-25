#!/usr/bin/env python3
"""
Multi-AI Browser Agent
Supports Ollama, Claude (Codex), Grok, and Gemini for intelligent web automation
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class MultiAIBrowser:
    """Browser automation with multiple AI backends for decision making."""

    def __init__(self, ai_backend="ollama", headless=False):
        """
        Initialize browser with AI backend.

        Args:
            ai_backend: "ollama", "claude", "grok", or "gemini"
            headless: Run browser in headless mode
        """
        self.ai_backend = ai_backend
        self.headless = headless
        self.driver = None

        # AI API endpoints and keys
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.xai_key = os.getenv("XAI_API_KEY")  # For Grok
        self.google_key = os.getenv("GOOGLE_API_KEY")  # For Gemini

        # Model names
        self.ollama_model = "llava"
        self.claude_model = "claude-3-5-sonnet-20241022"
        self.grok_model = "grok-code-fast-1"
        self.gemini_model = "gemini-1.5-flash"

    def start_browser(self):
        """Start Chrome browser."""
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        print(f"✅ Browser started (AI: {self.ai_backend})")

    def take_screenshot(self, path="/tmp/browser_screenshot.png"):
        """Take screenshot and return path."""
        self.driver.save_screenshot(path)
        return path

    def get_page_text(self):
        """Get visible page text."""
        return self.driver.find_element(By.TAG_NAME, "body").text

    def ask_ai(self, prompt, screenshot_path=None):
        """
        Ask AI for navigation decision.

        Args:
            prompt: Question about what to do next
            screenshot_path: Optional screenshot for vision models

        Returns:
            AI response with action recommendation
        """
        if self.ai_backend == "ollama":
            return self._ask_ollama(prompt, screenshot_path)
        elif self.ai_backend == "claude":
            return self._ask_claude(prompt, screenshot_path)
        elif self.ai_backend == "grok":
            return self._ask_grok(prompt, screenshot_path)
        elif self.ai_backend == "gemini":
            return self._ask_gemini(prompt, screenshot_path)
        else:
            raise ValueError(f"Unknown AI backend: {self.ai_backend}")

    def _ask_ollama(self, prompt, screenshot_path):
        """Ask Ollama llava model."""
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
        }

        if screenshot_path:
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            payload["images"] = [image_data]

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate", json=payload, timeout=120
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            return f"❌ Ollama error: {e}"

    def _ask_claude(self, prompt, screenshot_path):
        """Ask Claude API (Anthropic)."""
        if not self.anthropic_key:
            return "❌ ANTHROPIC_API_KEY not set"

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.anthropic_key)

            content = [{"type": "text", "text": prompt}]

            if screenshot_path:
                with open(screenshot_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
                content.insert(
                    0,
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                )

            message = client.messages.create(
                model=self.claude_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )

            return message.content[0].text
        except Exception as e:
            return f"❌ Claude error: {e}"

    def _ask_grok(self, prompt, screenshot_path):
        """Ask xAI Grok model."""
        if not self.xai_key:
            return "❌ XAI_API_KEY not set"

        try:
            headers = {
                "Authorization": f"Bearer {self.xai_key}",
                "Content-Type": "application/json",
            }

            messages = [{"role": "user", "content": prompt}]

            # Grok vision API format (hypothetical - adjust based on actual API)
            if screenshot_path:
                with open(screenshot_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
                messages[0]["content"] = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{image_data}"},
                ]

            payload = {"model": self.grok_model, "messages": messages, "max_tokens": 1024}

            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"❌ Grok error: {e}"

    def _ask_gemini(self, prompt, screenshot_path):
        """Ask Google Gemini model."""
        if not self.google_key:
            return "❌ GOOGLE_API_KEY not set"

        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{self.gemini_model}:generateContent?key={self.google_key}"

            parts = [{"text": prompt}]

            if screenshot_path:
                with open(screenshot_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
                parts.insert(0, {"inline_data": {"mime_type": "image/png", "data": image_data}})

            payload = {"contents": [{"parts": parts}]}

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"❌ Gemini error: {e}"

    def navigate_with_ai(self, url, goal):
        """
        Navigate to URL and use AI to achieve goal.

        Args:
            url: Starting URL
            goal: What to accomplish (e.g., "Find pricing information")
        """
        print(f"\n🎯 Goal: {goal}")
        print(f"🌐 URL: {url}")
        print(f"🤖 AI: {self.ai_backend}")
        print("=" * 70)

        self.driver.get(url)
        time.sleep(3)

        max_steps = 10
        for step in range(1, max_steps + 1):
            print(f"\n📍 Step {step}")

            # Take screenshot
            screenshot = self.take_screenshot(f"/tmp/step_{step}.png")
            page_text = self.get_page_text()[:1000]  # First 1000 chars

            # Ask AI what to do next
            prompt = f"""You are helping automate a web browser.

Goal: {goal}
Current page text preview: {page_text}

Based on the screenshot and page text, what should we do next?
Respond with one of:
1. CLICK "link text" - Click a link or button
2. FILL "field_name" "value" - Fill a form field
3. SUBMIT - Submit current form
4. DONE "answer" - Goal achieved, provide the answer
5. SCROLL - Scroll down to see more content

Be specific with element text you want to click."""

            print(f"🤔 Asking {self.ai_backend}...")
            decision = self.ask_ai(prompt, screenshot)
            print(f"💡 AI says: {decision}")

            # Parse and execute decision
            if decision.startswith("DONE"):
                answer = decision.replace("DONE", "").strip().strip('"')
                print(f"\n✅ Goal achieved!")
                print(f"📊 Answer: {answer}")
                self.driver.save_screenshot(f"/tmp/final_{step}.png")
                break

            elif decision.startswith("CLICK"):
                target = decision.replace("CLICK", "").strip().strip('"')
                try:
                    element = self.driver.find_element(By.PARTIAL_LINK_TEXT, target)
                    self.driver.execute_script("arguments[0].click();", element)
                    print(f"✅ Clicked: {target}")
                    time.sleep(3)
                except Exception as e:
                    print(f"❌ Click failed: {e}")

            elif decision.startswith("SCROLL"):
                self.driver.execute_script("window.scrollBy(0, 800)")
                print("✅ Scrolled")
                time.sleep(2)

            else:
                print("❌ Unknown action, stopping")
                break

        print(f"\n{'='*70}")
        print("🏁 Navigation complete")

    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            print("✅ Browser closed")


def main():
    """Test multi-AI browser with different backends."""
    if len(sys.argv) < 3:
        print("Usage: python3 multi_ai_browser.py <ai_backend> <goal> [url]")
        print("\nAI backends: ollama, claude, grok, gemini")
        print("\nExample:")
        print('  python3 multi_ai_browser.py claude "Find pricing" https://example.com')
        sys.exit(1)

    ai_backend = sys.argv[1]
    goal = sys.argv[2]
    url = sys.argv[3] if len(sys.argv) > 3 else "https://www.aquatechswim.com"

    agent = MultiAIBrowser(ai_backend=ai_backend, headless=False)
    agent.start_browser()

    try:
        agent.navigate_with_ai(url, goal)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        agent.close()


if __name__ == "__main__":
    main()
