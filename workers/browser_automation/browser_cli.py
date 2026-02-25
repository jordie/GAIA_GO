#!/usr/bin/env python3
"""
Interactive CLI for browser automation
Run in tmux and send prompts to browse websites and extract information
"""

import asyncio
import json
import subprocess
import sys
import time
import tempfile
import os
import readline  # For better input experience
from pathlib import Path

try:
    import pytesseract
    from PIL import Image, ImageChops
    import numpy as np
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# WebSocket connection
import websockets


from session_manager import SessionManager


class BrowserCLI:
    def __init__(self):
        self.ws = None
        self.current_tab_id = None
        self.current_url = None
        self.session_manager = SessionManager()
        self.current_session = None
        self.current_conversation_url = None

    async def connect(self):
        """Connect to browser extension WebSocket."""
        ws_url = "ws://localhost:8765"
        print("🔌 Connecting to browser extension...")

        try:
            self.ws = await websockets.connect(ws_url)

            # Wait for FULL_STATE
            async for message in self.ws:
                data = json.loads(message)
                if data.get("event") == "FULL_STATE":
                    print("✓ Connected to browser\n")
                    return True

        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    async def open_url(self, url):
        """Open URL in new tab."""
        print(f"🌐 Opening {url}...")

        await self.ws.send(json.dumps({
            "command": True,
            "id": f"open-{int(time.time())}",
            "action": "OPEN_TAB",
            "params": {"url": url}
        }))

        async for message in self.ws:
            data = json.loads(message)
            if data.get("event") == "COMMAND_RESULT":
                result = data["data"]
                if result.get("status") == "success":
                    self.current_tab_id = result["result"]["id"]
                    self.current_url = url
                    print(f"✓ Tab {self.current_tab_id}\n")
                    break

        # Wait for page load
        async for message in self.ws:
            data = json.loads(message)
            if data.get("event") == "PAGE_LOADED":
                if data["data"].get("tabId") == self.current_tab_id:
                    print("✓ Page loaded\n")
                    break

        # Activate tab
        await self.ws.send(json.dumps({
            "command": True,
            "id": f"activate-{int(time.time())}",
            "action": "ACTIVATE_TAB",
            "tabId": self.current_tab_id
        }))

        async for message in self.ws:
            data = json.loads(message)
            if data.get("event") == "COMMAND_RESULT":
                break

        await asyncio.sleep(2)

    def run_applescript(self, script):
        """Execute AppleScript."""
        try:
            subprocess.run(['osascript', '-e', script],
                         capture_output=True, timeout=10)
        except:
            pass

    def toggle_assistant(self):
        """Open Perplexity sidebar."""
        script = '''
        tell application "System Events"
            tell process "Comet"
                click menu item "Toggle Assistant" of menu "Assistant" of menu bar 1
            end tell
        end tell
        '''
        self.run_applescript(script)
        time.sleep(2)

    def type_text(self, text):
        """Type text via AppleScript."""
        text = text.replace('\\', '\\\\').replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{text}"'
        self.run_applescript(script)

    def press_enter(self):
        """Press Enter."""
        script = 'tell application "System Events" to keystroke return'
        self.run_applescript(script)

    def activate_comet(self):
        """Activate Comet browser."""
        script = 'tell application "Comet" to activate'
        self.run_applescript(script)
        time.sleep(0.5)

    def capture_screenshot(self):
        """Capture Comet window screenshot."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        screenshot_path = temp_file.name
        temp_file.close()

        # Try to get window ID
        get_window_script = '''
        tell application "System Events"
            tell process "Comet"
                return id of window 1
            end tell
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', get_window_script],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                window_id = result.stdout.strip()
                subprocess.run(
                    ['screencapture', '-o', '-l', window_id, screenshot_path],
                    timeout=5,
                    capture_output=True
                )

                if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                    return screenshot_path

        except:
            pass

        # Fallback: capture whole screen
        try:
            subprocess.run(
                ['screencapture', '-o', screenshot_path],
                timeout=5,
                capture_output=True
            )
            if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                return screenshot_path
        except:
            pass

        return None

    def compare_images(self, img1_path, img2_path):
        """Compare two images."""
        if not HAS_OCR:
            return 0

        try:
            img1 = Image.open(img1_path)
            img2 = Image.open(img2_path)

            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            diff = ImageChops.difference(img1, img2)
            diff_array = np.array(diff)
            total_pixels = diff_array.size
            different_pixels = np.count_nonzero(diff_array)

            similarity = 100 * (1 - different_pixels / total_pixels)
            return similarity

        except:
            return 0

    def extract_text_from_image(self, image_path):
        """Extract text from image using OCR."""
        if not HAS_OCR:
            return None

        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return '\n'.join(lines)
        except:
            return None

    async def wait_for_completion(self, max_wait=60):
        """Poll for response completion."""
        screenshots = []
        stable_count = 0
        start_time = time.time()

        sys.stdout.write("⏳ Waiting for response")
        sys.stdout.flush()

        while time.time() - start_time < max_wait:
            screenshot_path = self.capture_screenshot()

            if not screenshot_path:
                await asyncio.sleep(2)
                sys.stdout.write(".")
                sys.stdout.flush()
                continue

            screenshots.append(screenshot_path)

            if len(screenshots) >= 2:
                similarity = self.compare_images(screenshots[-2], screenshots[-1])

                if similarity > 98:
                    stable_count += 1
                    if stable_count >= 3:
                        sys.stdout.write(" ✓\n")
                        sys.stdout.flush()

                        # Clean up old screenshots
                        final_screenshot = screenshots[-1]
                        for path in screenshots[:-1]:
                            try:
                                os.unlink(path)
                            except:
                                pass

                        return final_screenshot
                else:
                    stable_count = 0

            sys.stdout.write(".")
            sys.stdout.flush()
            await asyncio.sleep(2)

        sys.stdout.write(" timeout\n")
        sys.stdout.flush()

        if screenshots:
            final_screenshot = screenshots[-1]
            for path in screenshots[:-1]:
                try:
                    os.unlink(path)
                except:
                    pass
            return final_screenshot

        return None

    async def ask_perplexity(self, question):
        """Ask Perplexity a question and return response."""
        print(f"\n💬 Asking: {question}\n")

        # Open sidebar
        self.toggle_assistant()

        # Type and submit
        self.type_text(question)
        await asyncio.sleep(0.5)
        self.press_enter()

        # Wait for response to start
        await asyncio.sleep(3)
        self.activate_comet()

        # Wait for completion
        screenshot = await self.wait_for_completion()

        if not screenshot:
            return None

        # Extract text
        text = self.extract_text_from_image(screenshot)

        # Clean up screenshot
        try:
            os.unlink(screenshot)
        except:
            pass

        return text

    async def interactive_mode(self):
        """Run interactive REPL."""
        print("=" * 70)
        print("BROWSER AUTOMATION CLI")
        print("=" * 70)
        print()
        print("Commands:")
        print("  open <url>              - Open URL in new tab")
        print("  ask <question>          - Ask Perplexity about current page")
        print("  library                 - Open Perplexity conversation library")
        print("  continue <perp_url>     - Open Perplexity conversation and continue")
        print("  save session <name>     - Save current session")
        print("  load session <name>     - Load session and restore tabs")
        print("  sessions                - List all sessions")
        print("  conversations           - List all conversations")
        print("  url                     - Show current URL")
        print("  quit                    - Exit")
        print()
        print("Tip: Perplexity conversation URLs automatically tracked!")
        print("=" * 70)
        print()

        while True:
            try:
                # Prompt
                if self.current_url:
                    prompt = f"\n[{self.current_url}] > "
                else:
                    prompt = "\n> "

                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Parse command
                if user_input.lower() == 'quit':
                    print("\n👋 Goodbye!")
                    break

                elif user_input.lower() == 'url':
                    if self.current_url:
                        print(f"📍 Current URL: {self.current_url}")
                    else:
                        print("No page loaded")

                elif user_input.lower() == 'library':
                    library_url = "https://www.perplexity.ai/library?source=comet"
                    print("📚 Opening Perplexity library...")
                    await self.open_url(library_url)
                    print("✓ Library loaded - you can select a conversation to continue")

                elif user_input.startswith('open '):
                    url = user_input[5:].strip()
                    if not url.startswith('http'):
                        url = 'https://' + url
                    await self.open_url(url)

                elif user_input.startswith('ask '):
                    question = user_input[4:].strip()
                    response = await self.ask_perplexity(question)

                    if response:
                        print("\n" + "=" * 70)
                        print("📝 RESPONSE:")
                        print("=" * 70)
                        print(response)
                        print("=" * 70)

                        # Track conversation if we detect perplexity URL
                        if self.current_conversation_url:
                            self.session_manager.save_conversation(
                                self.current_conversation_url,
                                topic=question[:50],
                                last_question=question,
                                last_response=response[:500] if response else "",
                                session_name=self.current_session
                            )
                    else:
                        print("✗ No response captured")

                elif user_input.startswith('continue '):
                    perp_url = user_input[9:].strip()
                    print(f"📂 Opening Perplexity conversation...")
                    await self.open_url(perp_url)
                    self.current_conversation_url = perp_url
                    print("✓ Conversation loaded - sidebar should open automatically")

                elif user_input.startswith('save session '):
                    session_name = user_input[13:].strip()
                    self.current_session = session_name
                    tabs = [{'url': self.current_url, 'title': 'Current', 'position': 0}]
                    self.session_manager.save_tabs(session_name, tabs)
                    print(f"💾 Saved session: {session_name}")

                elif user_input.startswith('load session '):
                    session_name = user_input[13:].strip()
                    tabs = self.session_manager.load_tabs(session_name)
                    if tabs:
                        self.current_session = session_name
                        print(f"📂 Loading session: {session_name}")
                        for tab in tabs:
                            await self.open_url(tab['url'])
                        print(f"✓ Loaded {len(tabs)} tab(s)")
                    else:
                        print(f"✗ Session not found: {session_name}")

                elif user_input == 'sessions':
                    sessions = self.session_manager.list_sessions()
                    if sessions:
                        print("\n📚 Sessions:")
                        print("-" * 70)
                        for s in sessions:
                            print(f"  {s['name']}")
                            if s['description']:
                                print(f"    {s['description']}")
                            print(f"    {s['tab_count']} tabs, {s['conversation_count']} conversations")
                            print(f"    Updated: {s['updated_at']}")
                            print()
                    else:
                        print("No sessions saved")

                elif user_input == 'conversations':
                    convs = self.session_manager.list_conversations()
                    if convs:
                        print("\n💬 Conversations:")
                        print("-" * 70)
                        for c in convs:
                            print(f"  {c['topic'] or 'Untitled'}")
                            print(f"    URL: {c['url']}")
                            if c['session']:
                                print(f"    Session: {c['session']}")
                            print(f"    Updated: {c['updated_at']}")
                            print()
                    else:
                        print("No conversations saved")

                else:
                    # Assume it's a question if no command
                    if self.current_url:
                        response = await self.ask_perplexity(user_input)

                        if response:
                            print("\n" + "=" * 70)
                            print("📝 RESPONSE:")
                            print("=" * 70)
                            print(response)
                            print("=" * 70)
                        else:
                            print("✗ No response captured")
                    else:
                        print("Please open a URL first with: open <url>")

            except KeyboardInterrupt:
                print("\n\n(Use 'quit' to exit)")
                continue
            except EOFError:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"✗ Error: {e}")
                continue

        # Clean up
        if self.ws:
            await self.ws.close()

    async def run(self):
        """Main entry point."""
        if not HAS_OCR:
            print("⚠️  Warning: OCR not available. Install with:")
            print("   pip install pytesseract pillow numpy")
            print("   brew install tesseract")
            print()

        # Connect to browser
        if not await self.connect():
            return

        # Run interactive mode
        await self.interactive_mode()


async def main():
    import sys

    cli = BrowserCLI()

    # Check for non-interactive mode (commands from args)
    if len(sys.argv) > 1 and sys.argv[1] == '--exec':
        # Non-interactive: execute commands from args
        if not HAS_OCR:
            print("⚠️  Warning: OCR not available. Install with:")
            print("   pip install pytesseract pillow numpy")
            print("   brew install tesseract")
            print()

        if not await cli.connect():
            return

        # Execute each command
        for i in range(2, len(sys.argv)):
            cmd = sys.argv[i]

            if cmd.startswith('open:'):
                url = cmd[5:]
                if not url.startswith('http'):
                    url = 'https://' + url
                await cli.open_url(url)

            elif cmd.startswith('ask:'):
                question = cmd[4:]
                response = await cli.ask_perplexity(question)

                if response:
                    print("\n" + "=" * 70)
                    print("📝 RESPONSE:")
                    print("=" * 70)
                    print(response)
                    print("=" * 70)
                else:
                    print("✗ No response captured")

        if cli.ws:
            await cli.ws.close()
    else:
        # Interactive mode
        await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
