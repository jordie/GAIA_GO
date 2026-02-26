#!/usr/bin/env python3
"""
Fast Local AI Browser - Optimized for Speed
Uses efficient local models and techniques for browser automation
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


class FastLocalAIBrowser:
    """
    Fast local AI browser using optimized models and techniques.

    Supported models (in order of speed):
    1. llama3.2-vision (fastest vision model)
    2. moondream (tiny 1.6B vision model)
    3. phi3-vision (Microsoft's efficient model)
    4. llava-phi3 (fast small vision model)
    5. llama3.2 (text-only, uses HTML instead of screenshots)
    """

    def __init__(self, model="llama3.2-vision", headless=False):
        """
        Initialize with fast local model.

        Args:
            model: Model to use:
                - "llama3.2-vision": Fast 11B vision model (recommended)
                - "moondream": Tiny 1.6B vision model (fastest)
                - "phi3-vision": Efficient 4.2B vision model
                - "llava-phi3": Fast 3.8B vision model
                - "llama3.2": Text-only, uses HTML (fastest, no vision)
            headless: Run browser headless
        """
        self.model = model
        self.headless = headless
        self.driver = None
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        # Model-specific optimizations
        self.use_vision = "vision" in model or "llava" in model or "vl" in model or model in ["moondream", "phi3"]

        print("🚀 Fast Local AI Browser")
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
        """
        Get page context optimized for the model type.
        Vision models get screenshots, text models get HTML.
        """
        if self.use_vision:
            # Take screenshot for vision models
            screenshot_path = "/tmp/fast_browser_screen.png"
            self.driver.save_screenshot(screenshot_path)

            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Get minimal text context
            text = self.driver.find_element(By.TAG_NAME, "body").text[:500]

            return {"type": "vision", "image": image_data, "text_preview": text}
        else:
            # Get HTML structure for text models (much faster)
            html = self.driver.page_source

            # Simplify HTML for LLM
            # Extract just the text content and basic structure
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove scripts, styles
            for tag in soup(["script", "style", "meta", "link"]):
                tag.decompose()

            # Get clean text with basic structure
            text = soup.get_text(separator="\n", strip=True)

            # Get interactive elements (links, buttons, inputs)
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
                "text": text[:2000],  # First 2000 chars
                "elements": elements[:20],  # Top 20 interactive elements
            }

    def ask_ai_fast(self, prompt, context):
        """
        Ask AI with optimized settings for speed.
        """
        # Optimized parameters for speed
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,  # Lower = faster, more deterministic
                "num_predict": 100,  # Shorter responses = faster
                "num_ctx": 2048,  # Smaller context = faster
                "top_k": 10,  # Smaller = faster
                "top_p": 0.9,
            },
        }

        if context["type"] == "vision":
            payload["images"] = [context["image"]]
            # Add text context
            payload["prompt"] = f"{prompt}\n\nPage preview: {context['text_preview']}"
        else:
            # Text-only with structured data
            payload[
                "prompt"
            ] = f"""{prompt}

Page text: {context['text'][:1000]}

Interactive elements:
{json.dumps(context['elements'], indent=2)}"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60,  # Shorter timeout for speed
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            return f"❌ Error: {e}"

    def navigate_fast(self, url, goal, max_steps=8):
        """
        Navigate with fast local AI.

        Args:
            url: Starting URL
            goal: What to accomplish
            max_steps: Maximum navigation steps (fewer = faster)
        """
        print(f"\n🎯 Goal: {goal}")
        print(f"🌐 URL: {url}")
        print(f"🤖 Model: {self.model}")
        print("=" * 70)

        self.driver.get(url)
        time.sleep(2)

        for step in range(1, max_steps + 1):
            print(f"\n📍 Step {step}/{max_steps}")

            start_time = time.time()

            # Get context
            context = self.get_page_context()

            # Ask AI what to do (optimized prompt for speed)
            prompt = f"""Task: {goal}

What's the SINGLE next action? Reply ONLY with one of:
- CLICK "exact text"
- TYPE "field" "value"
- SUBMIT
- DONE "answer"
- SCROLL

Be specific and brief."""

            print("🤔 Analyzing...")
            decision = self.ask_ai_fast(prompt, context)

            duration = time.time() - start_time
            print(f"💡 Decision ({duration:.1f}s): {decision[:80]}")

            # Execute
            if "DONE" in decision:
                answer = decision.replace("DONE", "").strip().strip('"')
                print("\n✅ Goal achieved!")
                print(f"📊 Answer: {answer}")
                break

            elif "CLICK" in decision:
                try:
                    # Extract text to click
                    text = (
                        decision.split('"')[1]
                        if '"' in decision
                        else decision.replace("CLICK", "").strip()
                    )
                    element = self.driver.find_element(By.PARTIAL_LINK_TEXT, text)
                    self.driver.execute_script("arguments[0].click();", element)
                    print(f"✅ Clicked: {text}")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Click failed: {e}")

            elif "SCROLL" in decision:
                self.driver.execute_script("window.scrollBy(0, 600)")
                print("✅ Scrolled")
                time.sleep(1)

            else:
                print("⚠️  Unknown action")

        print(f"\n{'='*70}")
        print("🏁 Navigation complete")

    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            print("✅ Browser closed")


def install_fast_models():
    """Helper to install recommended fast models."""
    print("📦 Installing fast local models for browser automation...")
    print()

    models = [
        ("llama3.2-vision", "11B vision model - best balance"),
        ("moondream", "1.6B tiny vision model - fastest vision"),
        ("phi3", "3.8B text model - fast text-only"),
    ]

    for model, desc in models:
        print(f"Installing {model} ({desc})...")
        os.system(f"ollama pull {model}")
        print()

    print("✅ Fast models installed!")


def main():
    """Test fast local AI browser."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        install_fast_models()
        return

    if len(sys.argv) < 3:
        print("Usage: python3 fast_local_ai_browser.py <model> <goal> [url]")
        print("\nModels (fastest to slowest):")
        print("  moondream        - Tiny 1.6B vision (fastest vision)")
        print("  llama3.2-vision  - Fast 11B vision (recommended)")
        print("  phi3-vision      - Efficient 4.2B vision")
        print("  llama3.2         - Text-only (fastest, no vision)")
        print("\nOr: python3 fast_local_ai_browser.py --install")
        return

    model = sys.argv[1]
    goal = sys.argv[2]
    url = sys.argv[3] if len(sys.argv) > 3 else "https://www.aquatechswim.com"

    agent = FastLocalAIBrowser(model=model, headless=False)
    agent.start_browser()

    try:
        agent.navigate_fast(url, goal)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
    finally:
        agent.close()


if __name__ == "__main__":
    main()
