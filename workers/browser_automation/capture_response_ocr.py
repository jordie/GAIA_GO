#!/usr/bin/env python3
"""
Capture Perplexity sidebar response using screenshot + OCR
"""

import asyncio
import json
import subprocess
import time
import tempfile
import os
import websockets

try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("⚠️  OCR libraries not installed. Install with:")
    print("   pip install pytesseract pillow")
    print("   brew install tesseract  # On macOS")


def run_applescript(script):
    """Execute AppleScript."""
    try:
        subprocess.run(['osascript', '-e', script], capture_output=True, timeout=10)
    except:
        pass


def toggle_assistant():
    """Click Assistant -> Toggle Assistant menu."""
    script = '''
    tell application "System Events"
        tell process "Comet"
            click menu item "Toggle Assistant" of menu "Assistant" of menu bar 1
        end tell
    end tell
    '''
    print("📱 Opening Assistant sidebar...")
    run_applescript(script)
    time.sleep(2)


def type_text(text):
    """Type text via AppleScript."""
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'tell application "System Events" to keystroke "{text}"'
    run_applescript(script)


def press_enter():
    """Press Enter key."""
    script = 'tell application "System Events" to keystroke return'
    run_applescript(script)


def activate_comet():
    """Activate Comet browser."""
    script = 'tell application "Comet" to activate'
    run_applescript(script)
    time.sleep(0.5)


def capture_screenshot():
    """Capture screenshot of Comet window and return file path."""
    # Create temp file for screenshot
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    screenshot_path = temp_file.name
    temp_file.close()

    # Use macOS screencapture to capture the frontmost window
    # -o = no window shadow
    # -l = window ID (we'll use AppleScript to get Comet's window ID)

    # Get Comet window ID
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
            print(f"📸 Capturing Comet window (ID: {window_id})...")

            # Capture specific window
            subprocess.run(
                ['screencapture', '-o', '-l', window_id, screenshot_path],
                timeout=5
            )
        else:
            # Fallback: interactive capture (user needs to click window)
            print("📸 Capturing screenshot (click Comet window)...")
            subprocess.run(
                ['screencapture', '-w', '-o', screenshot_path],
                timeout=10
            )

        if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
            print(f"✓ Screenshot saved: {screenshot_path}")
            return screenshot_path
        else:
            print("✗ Screenshot failed")
            return None

    except Exception as e:
        print(f"✗ Screenshot error: {e}")
        return None


def extract_text_from_image(image_path):
    """Extract text from image using OCR."""
    if not HAS_OCR:
        print("✗ OCR not available")
        return None

    try:
        print("🔍 Running OCR on screenshot...")
        image = Image.open(image_path)

        # Run OCR
        text = pytesseract.image_to_string(image)

        # Clean up
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        return '\n'.join(lines)

    except Exception as e:
        print(f"✗ OCR error: {e}")
        return None


async def ask_and_capture_with_ocr():
    """Ask question and capture response using OCR."""
    ws_url = "ws://localhost:8765"

    print("=" * 70)
    print("ASK & CAPTURE WITH OCR")
    print("=" * 70)
    print()

    # Connect
    print("🔌 Connecting...")
    ws = await websockets.connect(ws_url)

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "FULL_STATE":
            print("✓ Connected\n")
            break

    # Open URL
    url = "https://www.aquatechswim.com"
    print(f"🌐 Opening {url}...")

    await ws.send(json.dumps({
        "command": True,
        "id": "cmd-1",
        "action": "OPEN_TAB",
        "params": {"url": url}
    }))

    tab_id = None
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == "cmd-1":
            tab_id = data["data"]["result"]["id"]
            print(f"✓ Tab {tab_id}\n")
            break

    # Wait for load
    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "PAGE_LOADED" and data["data"].get("tabId") == tab_id:
            print("✓ Page loaded\n")
            break

    # Activate tab
    await ws.send(json.dumps({
        "command": True,
        "id": "cmd-2",
        "action": "ACTIVATE_TAB",
        "tabId": tab_id
    }))

    async for message in ws:
        data = json.loads(message)
        if data.get("event") == "COMMAND_RESULT" and data["data"].get("id") == "cmd-2":
            break

    await asyncio.sleep(1)

    # Open sidebar and ask question
    question = "What swimming classes are available for kids?"
    print(f"💬 Question: {question}\n")

    toggle_assistant()

    # Type and submit
    print("⌨️  Typing...")
    type_text(question)
    await asyncio.sleep(0.5)

    print("⌨️  Submitting...")
    press_enter()

    # Wait for response
    print("\n⏳ Waiting 15 seconds for Perplexity to respond...")
    await asyncio.sleep(15)

    # Activate Comet to ensure it's frontmost
    activate_comet()
    await asyncio.sleep(0.5)

    # Capture screenshot
    print("\n" + "=" * 70)
    print("📸 CAPTURING RESPONSE VIA SCREENSHOT + OCR")
    print("=" * 70)
    print()

    screenshot_path = capture_screenshot()

    if screenshot_path:
        if HAS_OCR:
            # Extract text using OCR
            text = extract_text_from_image(screenshot_path)

            if text:
                print("\n" + "=" * 70)
                print("📝 EXTRACTED TEXT")
                print("=" * 70)
                print()
                print(text)
                print()
                print("=" * 70)

                # Look for swimming-related content
                if any(keyword in text.lower() for keyword in ['swim', 'class', 'aqua', 'pool', 'kid']):
                    print("\n✓ Found swimming-related content in response!")
                else:
                    print("\n⚠️  No swimming keywords found - response may not be visible")
            else:
                print("\n✗ Could not extract text from screenshot")
        else:
            print(f"\n💡 Screenshot saved to: {screenshot_path}")
            print("   Install OCR libraries to extract text automatically")
            print("   Or open the image manually to read the response")
    else:
        print("\n✗ Failed to capture screenshot")

    print("\n" + "=" * 70)
    print("💡 NEXT STEPS")
    print("=" * 70)
    print()
    print("If OCR didn't work well, you can:")
    print("1. Open the screenshot manually and read the response")
    print("2. Adjust the wait time if response takes longer")
    print("3. Use macOS Accessibility API to read UI element text directly")
    print()

    await ws.close()


if __name__ == "__main__":
    asyncio.run(ask_and_capture_with_ocr())
