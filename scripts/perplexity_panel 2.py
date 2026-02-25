#!/usr/bin/env python3
"""
Perplexity Side Panel Automation

Interacts with the Perplexity AI Assistant side panel via Chrome DevTools Protocol.
Requires Chrome to be running with --remote-debugging-port=9222

Usage:
    # Start Chrome debug first
    ./start_chrome_debug.sh

    # Then use this script
    python3 perplexity_panel.py --ask "What is Python?"
    python3 perplexity_panel.py --interactive
"""

import argparse
import json
import re
import sys
import time
from typing import Optional

try:
    import requests
    import websocket
except ImportError:
    print("Required packages not installed. Run:")
    print("  pip install requests websocket-client")
    sys.exit(1)


class PerplexityPanel:
    """Interact with Perplexity AI side panel via Chrome DevTools Protocol."""

    def __init__(self, debug_port: int = 9222, verbose: bool = False):
        self.debug_port = debug_port
        self.debug_url = f"http://localhost:{debug_port}"
        self.verbose = verbose
        self.ws = None
        self.ws_url = None
        self.message_id = 0

    def log(self, msg: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[DEBUG] {msg}")

    def find_perplexity_target(self) -> Optional[dict]:
        """Find the Perplexity panel/tab in Chrome's debug targets."""
        try:
            response = requests.get(f"{self.debug_url}/json", timeout=5)
            targets = response.json()
        except requests.RequestException as e:
            print(f"Error connecting to Chrome debug: {e}")
            print("Make sure Chrome is running with --remote-debugging-port=9222")
            print("Run: ./start_chrome_debug.sh")
            return None

        # Look for Perplexity targets
        perplexity_targets = []
        for target in targets:
            url = target.get("url", "")
            title = target.get("title", "")
            target_type = target.get("type", "")

            # Match Perplexity URLs (main page, sidecar, extension)
            if "perplexity" in url.lower() or "perplexity" in title.lower():
                perplexity_targets.append(target)
                self.log(f"Found: {title} - {url} ({target_type})")

        if not perplexity_targets:
            # Try to find by looking for sidecar/sidepanel targets
            for target in targets:
                url = target.get("url", "")
                if "side_panel" in url or "sidecar" in url:
                    perplexity_targets.append(target)
                    self.log(f"Found sidepanel: {url}")

        if not perplexity_targets:
            print("No Perplexity panel found in Chrome.")
            print("Please open Perplexity in Chrome or enable the side panel.")
            print("\nAvailable targets:")
            for t in targets[:5]:
                print(f"  - {t.get('title', 'Untitled')[:50]}: {t.get('url', '')[:60]}")
            return None

        # Prefer sidecar with copilot=true (interactive panel), then search results
        for target in perplexity_targets:
            url = target.get("url", "")
            if "sidecar" in url and "copilot=true" in url:
                return target

        # Then try search results pages
        for target in perplexity_targets:
            url = target.get("url", "")
            if "/sidecar/search/" in url:
                return target

        # Then any sidecar
        for target in perplexity_targets:
            if "sidecar" in target.get("url", ""):
                return target

        for target in perplexity_targets:
            if target.get("type") == "page":
                return target

        return perplexity_targets[0]

    def connect(self) -> bool:
        """Connect to the Perplexity panel via WebSocket."""
        target = self.find_perplexity_target()
        if not target:
            return False

        self.ws_url = target.get("webSocketDebuggerUrl")
        if not self.ws_url:
            print("No WebSocket URL available for target")
            return False

        self.log(f"Connecting to: {self.ws_url}")

        try:
            self.ws = websocket.create_connection(self.ws_url, timeout=10)
            self.log("Connected successfully")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    def send_command(self, method: str, params: dict = None) -> dict:
        """Send a CDP command and wait for response."""
        self.message_id += 1
        message = {"id": self.message_id, "method": method, "params": params or {}}

        self.log(f"Sending: {method}")
        self.ws.send(json.dumps(message))

        # Wait for response with matching ID
        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") == self.message_id:
                if "error" in response:
                    self.log(f"Error: {response['error']}")
                return response
            # Store events for later processing if needed
            self.log(f"Event: {response.get('method', 'unknown')}")

    def execute_js(self, expression: str) -> Optional[str]:
        """Execute JavaScript in the page context."""
        result = self.send_command(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )

        if "result" in result and "result" in result["result"]:
            return result["result"]["result"].get("value")
        return None

    def inject_text(self, text: str) -> bool:
        """
        Inject text into the Perplexity input field.

        The input uses Lexical editor, so we need to:
        1. Focus the input
        2. Clear existing content
        3. Simulate typing via Lexical's internal state
        """
        # JavaScript to inject text into Lexical editor
        js_code = f"""
        (function() {{
            let input = document.getElementById('ask-input');
            if (!input) {{
                // Try finding by other selectors
                const inputs = document.querySelectorAll('[data-lexical-editor="true"]');
                if (inputs.length === 0) {{
                    return "ERROR: Input element not found";
                }}
                input = inputs[0];
            }}

            // Focus the input
            input.focus();

            // Clear existing content
            input.innerHTML = '';

            // Create a text node with our content
            const p = document.createElement('p');
            p.className = 'block';
            const span = document.createElement('span');
            span.setAttribute('data-lexical-text', 'true');
            span.textContent = {json.dumps(text)};
            p.appendChild(span);
            input.appendChild(p);

            // Trigger input event for Lexical to pick up the change
            input.dispatchEvent(new InputEvent('input', {{
                bubbles: true,
                cancelable: true,
                inputType: 'insertText',
                data: {json.dumps(text)}
            }}));

            // Also dispatch a beforeinput event
            input.dispatchEvent(new InputEvent('beforeinput', {{
                bubbles: true,
                cancelable: true,
                inputType: 'insertText',
                data: {json.dumps(text)}
            }}));

            return "OK";
        }})();
        """

        result = self.execute_js(js_code)
        if result == "OK":
            self.log("Text injected successfully")
            return True
        else:
            print(f"Failed to inject text: {result}")
            return False

    def inject_text_clipboard(self, text: str) -> bool:
        """
        Alternative method: Inject text using clipboard paste simulation.
        This often works better with complex editors like Lexical.
        """
        js_code = f"""
        (async function() {{
            const input = document.getElementById('ask-input') ||
                          document.querySelector('[data-lexical-editor="true"]');
            if (!input) return "ERROR: Input not found";

            // Focus
            input.focus();

            // Select all and delete
            document.execCommand('selectAll');
            document.execCommand('delete');

            // Use insertText command
            document.execCommand('insertText', false, {json.dumps(text)});

            return "OK";
        }})();
        """

        result = self.execute_js(js_code)
        return result == "OK"

    def submit_query(self) -> bool:
        """Submit the current query by pressing Enter or clicking submit."""
        js_code = """
        (function() {
            // Try to find and click the submit button
            const submitBtn = document.querySelector('button[aria-label="Submit"]') ||
                              document.querySelector('button[type="submit"]') ||
                              document.querySelector('[data-testid="submit-button"]');

            if (submitBtn) {
                submitBtn.click();
                return "CLICKED";
            }

            // Fallback: simulate Enter key on the input
            const input = document.getElementById('ask-input') ||
                          document.querySelector('[data-lexical-editor="true"]');
            if (input) {
                input.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    which: 13,
                    bubbles: true
                }));
                return "ENTER";
            }

            return "ERROR: No submit method found";
        })();
        """

        result = self.execute_js(js_code)
        self.log(f"Submit result: {result}")
        return result in ["CLICKED", "ENTER"]

    def get_search_page_urls(self) -> set:
        """Get all current search results page URLs."""
        urls = set()
        try:
            response = requests.get(f"{self.debug_url}/json", timeout=5)
            targets = response.json()
            for target in targets:
                url = target.get("url", "")
                if "/sidecar/search/" in url:
                    urls.add(url)
        except:
            pass
        return urls

    def find_new_search_page(self, old_urls: set) -> Optional[str]:
        """Find a search results page that wasn't in old_urls."""
        try:
            response = requests.get(f"{self.debug_url}/json", timeout=5)
            targets = response.json()
            for target in targets:
                url = target.get("url", "")
                if "/sidecar/search/" in url and url not in old_urls:
                    return target.get("webSocketDebuggerUrl")
        except:
            pass
        return None

    def wait_for_response(
        self, timeout: int = 60, old_response: str = "", old_search_urls: set = None
    ) -> Optional[str]:
        """
        Wait for and extract the response from Perplexity.

        Args:
            timeout: Maximum seconds to wait
            old_response: Previous response text to ignore (wait for new content)
            old_search_urls: Set of search page URLs that existed before submitting

        Returns the response text when available.
        """
        self.log(f"Waiting for response (timeout: {timeout}s)...")
        if old_search_urls is None:
            old_search_urls = set()

        start_time = time.time()
        last_response = ""
        stable_count = 0
        found_new = False
        connected_to_new_search = False

        while time.time() - start_time < timeout:
            # Check if there's a NEW search results page we should connect to
            if not connected_to_new_search and time.time() - start_time > 2:
                new_search_ws = self.find_new_search_page(old_search_urls)
                if new_search_ws:
                    self.log(f"Found NEW search results page, connecting...")
                    try:
                        self.ws.close()
                        self.ws = websocket.create_connection(new_search_ws, timeout=10)
                        self.ws_url = new_search_ws
                        connected_to_new_search = True
                        found_new = True  # New page means new response
                    except Exception as e:
                        self.log(f"Failed to connect to search page: {e}")

            # Extract the latest response
            js_code = """
            (function() {
                // Find response containers
                const responses = document.querySelectorAll('[class*="prose"]');

                if (responses.length === 0) {
                    // Try alternative selectors for Perplexity
                    const msgs = document.querySelectorAll('[class*="message"]');
                    if (msgs.length > 0) {
                        const last = msgs[msgs.length - 1];
                        return last.innerText || "";
                    }
                    return "";
                }

                // Get the last/most recent response
                const lastResponse = responses[responses.length - 1];
                return lastResponse.innerText || "";
            })();
            """

            response = self.execute_js(js_code)

            # Check if this is a new response (different from old_response)
            if response and response != old_response:
                found_new = True

            if not found_new:
                # Still showing old response, keep waiting
                time.sleep(0.5)
                continue

            if response and response != last_response:
                last_response = response
                stable_count = 0
                self.log(f"Response updating... ({len(response)} chars)")
            elif response == last_response and response:
                stable_count += 1
                # Consider response complete if stable for 3 checks
                if stable_count >= 3:
                    self.log("Response stable, returning")
                    return response

            time.sleep(1)

        if last_response and last_response != old_response:
            return last_response

        print("Timeout waiting for response")
        return None

    def get_current_response_text(self) -> str:
        """Get the current response text displayed on screen."""
        js_code = """
        (function() {
            const responses = document.querySelectorAll('[class*="prose"]');
            if (responses.length > 0) {
                return responses[responses.length - 1].innerText || "";
            }
            return "";
        })();
        """
        return self.execute_js(js_code) or ""

    def ask(self, query: str, wait_response: bool = True) -> Optional[str]:
        """
        Send a query to Perplexity and optionally wait for response.

        Args:
            query: The question to ask
            wait_response: Whether to wait for and return the response

        Returns:
            The response text if wait_response is True, else None
        """
        if not self.ws:
            if not self.connect():
                return None

        print(f"Asking: {query[:50]}...")

        # Capture current response and search pages before asking
        old_response = self.get_current_response_text()
        old_search_urls = self.get_search_page_urls()
        self.log(
            f"Old response length: {len(old_response)}, old search pages: {len(old_search_urls)}"
        )

        # Try clipboard method first (more reliable for Lexical)
        if not self.inject_text_clipboard(query):
            # Fallback to direct injection
            if not self.inject_text(query):
                print("Failed to inject query")
                return None

        time.sleep(0.5)  # Small delay before submitting

        if not self.submit_query():
            print("Failed to submit query")
            return None

        if wait_response:
            return self.wait_for_response(
                old_response=old_response, old_search_urls=old_search_urls
            )

        return None

    def get_response(self) -> Optional[str]:
        """Get the current response displayed in the panel."""
        if not self.ws:
            if not self.connect():
                return None

        js_code = """
        (function() {
            // Multiple selectors for Perplexity response content
            const selectors = [
                '[class*="prose"]',
                '[class*="markdown"]',
                '[class*="answer"]',
                '[class*="response"]',
                '.prose',
                'article'
            ];

            for (const selector of selectors) {
                const elements = document.querySelectorAll(selector);
                if (elements.length > 0) {
                    const last = elements[elements.length - 1];
                    const text = last.innerText;
                    if (text && text.length > 10) {
                        return text;
                    }
                }
            }

            return "";
        })();
        """

        return self.execute_js(js_code)

    def close(self):
        """Close the WebSocket connection."""
        if self.ws:
            self.ws.close()
            self.ws = None


def interactive_mode(panel: PerplexityPanel):
    """Run in interactive mode, accepting queries from stdin."""
    print("Perplexity Interactive Mode")
    print("Type your query and press Enter. Type 'quit' to exit.")
    print("-" * 50)

    while True:
        try:
            query = input("\nYou: ").strip()
            if not query:
                continue
            if query.lower() in ["quit", "exit", "q"]:
                break

            response = panel.ask(query)
            if response:
                print(f"\nPerplexity: {response[:500]}")
                if len(response) > 500:
                    print(f"... ({len(response)} chars total)")
            else:
                print("No response received")

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    print("\nGoodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="Interact with Perplexity AI side panel via Chrome DevTools"
    )
    parser.add_argument("--ask", "-a", type=str, help="Ask a single question")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument(
        "--get-response", "-g", action="store_true", help="Get the current response from the panel"
    )
    parser.add_argument(
        "--port", "-p", type=int, default=9222, help="Chrome debug port (default: 9222)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--list-targets", action="store_true", help="List all Chrome debug targets")

    args = parser.parse_args()

    panel = PerplexityPanel(debug_port=args.port, verbose=args.verbose)

    try:
        if args.list_targets:
            response = requests.get(f"http://localhost:{args.port}/json")
            targets = response.json()
            print(f"Found {len(targets)} targets:\n")
            for t in targets:
                print(f"  [{t.get('type')}] {t.get('title', 'Untitled')[:50]}")
                print(f"       {t.get('url', 'No URL')[:70]}")
                print()
            return

        if args.get_response:
            response = panel.get_response()
            if response:
                print(response)
            else:
                print("No response found")
            return

        if args.ask:
            response = panel.ask(args.ask)
            if response:
                print(f"\n{response}")
            return

        if args.interactive:
            if panel.connect():
                interactive_mode(panel)
            return

        # Default: show usage
        parser.print_help()

    finally:
        panel.close()


if __name__ == "__main__":
    main()
