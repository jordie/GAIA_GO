#!/usr/bin/env python3
"""
Generic Browser Automation Runner
Executes data-driven workflows from site_definitions.yaml
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import websocket
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vault_service import get_login_credentials


class BrowserAutomationRunner:
    """Data-driven browser automation runner."""

    def __init__(self, site_key: str, search_term: Optional[str] = None):
        self.site_key = site_key
        self.search_term = search_term
        self.ws = None
        self.msg_id = 1
        self.site_def = None
        self.credentials = None
        self.results = {}

        # Load site definition
        self._load_site_definition()

        # Get credentials
        self._load_credentials()

    def _load_site_definition(self):
        """Load site definition from YAML."""
        yaml_path = Path(__file__).parent.parent / "data" / "automation" / "site_definitions.yaml"

        if not yaml_path.exists():
            raise FileNotFoundError(f"Site definitions not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        if self.site_key not in data.get("sites", {}):
            raise ValueError(f"Site '{self.site_key}' not found in definitions")

        self.site_def = data["sites"][self.site_key]
        print(f"✅ Loaded definition for: {self.site_def['name']}")

    def _load_credentials(self):
        """Load credentials from vault."""
        vault_key = self.site_def.get("vault_key", self.site_key)
        self.credentials = get_login_credentials(vault_key)
        print(f"✅ Retrieved credentials: {self.credentials['username']}")

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

        # Read responses until we get ours
        max_attempts = 30
        for _ in range(max_attempts):
            try:
                response = json.loads(self.ws.recv())

                if response.get("id") == current_id:
                    if "result" in response and "result" in response["result"]:
                        return response["result"]["result"].get("value")
                    elif "error" in response:
                        print(f"   ⚠️ JS Error: {response['error']}")
                        return None
                    return None

            except Exception as e:
                print(f"   ⚠️ Recv error: {e}")
                return None

        return None

    def _find_element(self, selectors: List[str]) -> Optional[str]:
        """Find element using selector list."""
        for selector in selectors:
            # Handle pattern: type selectors
            if selector.startswith("pattern:"):
                continue  # Patterns handled differently

            js = f"""
            (function() {{
                const el = document.querySelector('{selector}');
                return el ? 'found' : null;
            }})()
            """

            result = self._execute_js(js)
            if result == "found":
                return selector

        return None

    def _fill_field(self, selectors: List[str], value: str) -> bool:
        """Fill form field."""
        selector = self._find_element(selectors)

        if not selector:
            print(f"   ⚠️ Field not found with selectors: {selectors}")
            return False

        js = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (el) {{
                el.value = '{value}';
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                return 'filled';
            }}
            return null;
        }})()
        """

        result = self._execute_js(js)
        return result == "filled"

    def _click_element(self, selectors: List[str]) -> bool:
        """Click element."""
        selector = self._find_element(selectors)

        if not selector:
            print(f"   ⚠️ Element not found with selectors: {selectors}")
            return False

        js = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (el) {{
                el.click();
                return 'clicked';
            }}
            return null;
        }})()
        """

        result = self._execute_js(js)
        return result == "clicked"

    def _execute_step(self, step: Dict) -> bool:
        """Execute a single workflow step."""
        step_type = step.get("type")
        print(f"   📍 Step: {step_type}")

        if step_type == "navigate":
            # Already handled by opening URL
            time.sleep(step.get("wait", 2))
            return True

        elif step_type == "check_condition":
            condition = step.get("condition")
            value = step.get("value")

            if condition == "url_contains":
                current_url = self._execute_js("window.location.href")
                if current_url and value in current_url:
                    print(f"      ✅ Condition met: URL contains '{value}'")

                    # Execute if_true steps
                    if "if_true" in step:
                        for sub_step in step["if_true"]:
                            self._execute_step(sub_step)

                    return True

            return False

        elif step_type == "fill_field":
            field = step.get("field")
            value = step.get("value", "")

            # Replace placeholders
            value = value.replace("{username}", self.credentials["username"])
            value = value.replace("{password}", self.credentials["password"])
            value = value.replace("{search_term}", self.search_term or "")

            result = self._fill_field(step["selectors"], value)

            if result:
                print(f"      ✅ Filled: {field}")
            else:
                print(f"      ❌ Failed to fill: {field}")

            return result

        elif step_type == "click":
            result = self._click_element(step["selectors"])

            if result:
                print(f"      ✅ Clicked")
                time.sleep(step.get("wait", 2))
            else:
                print(f"      ❌ Failed to click")

            return result

        elif step_type == "navigate_menu":
            menu_items = step.get("menu_items", [])

            for item in menu_items:
                js = f"""
                (function() {{
                    const elements = Array.from(document.querySelectorAll('a, button, [role="menuitem"]'));
                    const target = elements.find(el => {{
                        const text = (el.innerText || el.textContent || '').trim();
                        return text === '{item}' || text.includes('{item}');
                    }});

                    if (target) {{
                        target.click();
                        return 'clicked:{item}';
                    }}
                    return null;
                }})()
                """

                result = self._execute_js(js)

                if result and result.startswith("clicked"):
                    print(f"      ✅ Navigated to: {item}")
                    time.sleep(step.get("wait", 2))
                    return True

            print(f"      ⚠️ Menu items not found: {menu_items}")
            return False

        elif step_type == "verify":
            condition = step.get("condition")
            value = step.get("value", "").replace("{search_term}", self.search_term or "")

            if condition == "page_contains":
                js = f"document.body.innerText.toLowerCase().includes('{value.lower()}')"
                result = self._execute_js(js)

                if result:
                    print(f"      ✅ Verified: Page contains '{value}'")
                else:
                    print(f"      ⚠️ Not found on page: '{value}'")

                return result

        elif step_type == "search":
            value = step.get("value", "").replace("{search_term}", self.search_term or "")
            result = self._fill_field(step["selectors"], value)

            if result and step.get("submit_after"):
                time.sleep(1)
                # Press Enter or click search button
                self._execute_js(
                    """
                (function() {
                    const searchField = document.querySelector('input[type="search"], input[name="search"]');
                    if (searchField) {
                        searchField.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
                    }
                })()
                """
                )

            time.sleep(step.get("wait", 2))
            return result

        return False

    def _extract_data(self) -> Dict[str, Any]:
        """Extract data based on site definition."""
        print("\n📊 Extracting data...")
        extraction_defs = self.site_def.get("extract", [])
        results = {}

        for extract_def in extraction_defs:
            name = extract_def["name"]
            description = extract_def["description"]
            selectors = extract_def["selectors"]

            print(f"\n   🔍 Extracting: {name} ({description})")

            # Try pattern matching first
            for selector in selectors:
                if selector.startswith("pattern:"):
                    pattern = selector.replace("pattern:", "").strip()

                    js = f"""
                    (function() {{
                        const bodyText = document.body.innerText;
                        const pattern = {pattern};
                        const matches = bodyText.match(pattern);
                        return matches ? [...new Set(matches)].slice(0, 10) : null;
                    }})()
                    """

                    result = self._execute_js(js)

                    if result:
                        results[name] = result
                        print(f"      ✅ Found via pattern: {result}")
                        break

            # Try label-based extraction
            if name not in results:
                for selector in selectors:
                    if selector.startswith("label:"):
                        label = selector.replace("label:", "").strip().strip("'\"")

                        js = f"""
                        (function() {{
                            const labels = Array.from(document.querySelectorAll('label, th, td, div, span'));
                            const matches = [];

                            for (const el of labels) {{
                                const text = el.innerText || el.textContent || '';
                                if (text.toLowerCase().includes('{label.lower()}')) {{
                                    // Get next sibling or parent context
                                    const next = el.nextElementSibling;
                                    if (next) {{
                                        matches.push(next.innerText || next.textContent);
                                    }} else {{
                                        const parent = el.closest('tr, div.row, div.card');
                                        if (parent) {{
                                            matches.push(parent.innerText || parent.textContent);
                                        }}
                                    }}
                                }}
                            }}

                            return matches.length > 0 ? [...new Set(matches)].slice(0, 5) : null;
                        }})()
                        """

                        result = self._execute_js(js)

                        if result:
                            results[name] = result
                            print(f"      ✅ Found via label: {result}")
                            break

        return results

    def run(self):
        """Execute complete automation workflow."""
        print("\n" + "=" * 70)
        print(f"{self.site_def['name']}")
        print("=" * 70)

        # Open browser
        print(f"\n🌐 Opening URL...")
        base_url = self.site_def["base_url"]

        import subprocess

        subprocess.run(["open", "-a", "Comet", base_url], check=False)
        time.sleep(5)

        # Find tab
        print("\n📑 Connecting to browser...")
        response = requests.get("http://localhost:9222/json")
        tabs = response.json()

        # Find matching tab
        tab = None
        url_parts = base_url.split("/")[2].split(".")[:2]

        for t in tabs:
            if t["type"] == "page":
                tab_url = t.get("url", "").lower()
                if any(part in tab_url for part in url_parts):
                    tab = t
                    break

        if not tab:
            # Use most recent
            for t in tabs:
                if t["type"] == "page" and not t.get("url", "").startswith(
                    ("chrome://", "devtools://")
                ):
                    tab = t
                    break

        if not tab:
            print("❌ No suitable tab found")
            return False

        print(f"✅ Tab: {tab.get('title', 'Unknown')[:60]}")

        # Connect CDP
        self.ws = websocket.create_connection(f"ws://localhost:9222/devtools/page/{tab['id']}")

        # Enable domains
        self.ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        self.ws.recv()
        self.ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
        self.ws.recv()
        time.sleep(1)

        print("✅ Connected")

        # Execute login workflow
        print("\n🔐 Executing login workflow...")
        login_steps = self.site_def["login"]["steps"]

        for step in login_steps:
            self._execute_step(step)

        # Execute search workflow
        if self.search_term:
            print(f"\n🔍 Searching for: {self.search_term}")
            search_steps = self.site_def["search"]["steps"]

            for step in search_steps:
                self._execute_step(step)

        # Extract data
        self.results = self._extract_data()

        # Display results
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)

        if self.results:
            for key, value in self.results.items():
                print(f"\n📋 {key}:")
                if isinstance(value, list):
                    for item in value:
                        print(f"   - {item}")
                else:
                    print(f"   {value}")
        else:
            print("\n⚠️ No data extracted")

        self.ws.close()

        return bool(self.results)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Data-driven browser automation")
    parser.add_argument("site", help="Site key (iclasspro, hoh_gymnastics, etc.)")
    parser.add_argument("--search", help="Search term (participant name)")

    args = parser.parse_args()

    runner = BrowserAutomationRunner(args.site, args.search)
    success = runner.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
