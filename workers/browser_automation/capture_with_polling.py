#!/usr/bin/env python3
"""
Capture Perplexity sidebar response with completion detection
Uses screenshot comparison to detect when response is complete
"""

import asyncio
import json
import subprocess
import sys
import time
import tempfile
import os
import websockets
from pathlib import Path

try:
    import pytesseract
    from PIL import Image, ImageChops
    import numpy as np
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("⚠️  OCR libraries not installed. Install with:")
    print("   pip install pytesseract pillow numpy")
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
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    screenshot_path = temp_file.name
    temp_file.close()

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

            # Capture specific window
            subprocess.run(
                ['screencapture', '-o', '-l', window_id, screenshot_path],
                timeout=5,
                capture_output=True
            )

            if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                return screenshot_path

    except Exception as e:
        print(f"✗ Screenshot error: {e}")

    return None


def compare_images(img1_path, img2_path):
    """Compare two images and return similarity percentage."""
    try:
        img1 = Image.open(img1_path)
        img2 = Image.open(img2_path)

        # Resize if needed
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)

        # Calculate difference
        diff = ImageChops.difference(img1, img2)

        # Convert to numpy array and calculate similarity
        diff_array = np.array(diff)
        total_pixels = diff_array.size
        different_pixels = np.count_nonzero(diff_array)

        similarity = 100 * (1 - different_pixels / total_pixels)
        return similarity

    except Exception as e:
        print(f"⚠️  Image comparison error: {e}")
        return 0


def extract_text_from_image(image_path):
    """Extract text from image using OCR."""
    if not HAS_OCR:
        return None

    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    except Exception as e:
        print(f"✗ OCR error: {e}")
        return None


async def wait_for_completion(max_wait=60, poll_interval=2, stability_threshold=3):
    """
    Poll screenshots until response appears stable (completed).

    Args:
        max_wait: Maximum seconds to wait
        poll_interval: Seconds between polls
        stability_threshold: Number of stable comparisons needed

    Returns:
        Path to final screenshot, or None
    """
    print(f"\n⏳ Polling for completion (max {max_wait}s, every {poll_interval}s)...")
    print(f"   Looking for {stability_threshold} consecutive stable screenshots\n")

    screenshots = []
    stable_count = 0
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # Capture screenshot
        screenshot_path = capture_screenshot()

        if not screenshot_path:
            await asyncio.sleep(poll_interval)
            continue

        screenshots.append(screenshot_path)
        elapsed = int(time.time() - start_time)

        # Compare with previous screenshot if available
        if len(screenshots) >= 2:
            prev_path = screenshots[-2]
            curr_path = screenshots[-1]

            similarity = compare_images(prev_path, curr_path)

            # If images are very similar (>98%), response might be stable
            if similarity > 98:
                stable_count += 1
                print(f"   [{elapsed}s] Stable screenshot #{stable_count} (similarity: {similarity:.1f}%)")

                if stable_count >= stability_threshold:
                    print(f"\n✓ Response appears complete (stable for {stable_count} checks)")

                    # Clean up old screenshots, keep final one
                    final_screenshot = screenshots[-1]
                    for path in screenshots[:-1]:
                        try:
                            os.unlink(path)
                        except:
                            pass

                    return final_screenshot
            else:
                if stable_count > 0:
                    print(f"   [{elapsed}s] Content changed (similarity: {similarity:.1f}%), resetting stability counter")
                else:
                    print(f"   [{elapsed}s] Content changing (similarity: {similarity:.1f}%)...")
                stable_count = 0
        else:
            print(f"   [{elapsed}s] Initial screenshot captured")

        await asyncio.sleep(poll_interval)

    # Timeout reached
    print(f"\n⚠️  Timeout reached ({max_wait}s)")

    if screenshots:
        # Return most recent screenshot
        final_screenshot = screenshots[-1]
        for path in screenshots[:-1]:
            try:
                os.unlink(path)
            except:
                pass
        return final_screenshot

    return None


async def ask_and_capture_with_polling(url=None, question=None, wait_before_asking=3):
    """Ask question and capture response using polling."""
    ws_url = "ws://localhost:8765"

    # Default values
    if not url:
        url = "https://www.aquatechswim.com"
    if not question:
        question = "What swimming classes are available for kids?"

    print("=" * 70)
    print("ASK & CAPTURE WITH POLLING")
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

    # Wait for page to be ready
    if wait_before_asking > 0:
        print(f"⏳ Waiting {wait_before_asking}s for page to be ready...")
        await asyncio.sleep(wait_before_asking)

    # Open sidebar and ask question
    print(f"💬 Question: {question}\n")

    toggle_assistant()

    # Type and submit
    print("⌨️  Typing...")
    type_text(question)
    await asyncio.sleep(0.5)

    print("⌨️  Submitting...")
    press_enter()

    # Wait a moment for response to start
    await asyncio.sleep(3)

    # Activate Comet to ensure it's frontmost
    activate_comet()
    await asyncio.sleep(0.5)

    # Poll for completion
    print("\n" + "=" * 70)
    print("📸 POLLING FOR COMPLETION")
    print("=" * 70)

    final_screenshot = await wait_for_completion(
        max_wait=60,
        poll_interval=2,
        stability_threshold=3
    )

    if final_screenshot:
        if HAS_OCR:
            # Extract text using OCR
            print("\n" + "=" * 70)
            print("🔍 EXTRACTING TEXT")
            print("=" * 70)
            print()

            text = extract_text_from_image(final_screenshot)

            if text:
                print("📝 EXTRACTED TEXT:")
                print("-" * 70)
                print(text)
                print("-" * 70)
                print()

                # Look for swimming-related content
                if any(keyword in text.lower() for keyword in ['swim', 'class', 'aqua', 'pool', 'kid', 'child']):
                    print("✓ Found swimming-related content in response!")
                else:
                    print("⚠️  No swimming keywords found")

                # Save text to file
                text_file = final_screenshot.replace('.png', '.txt')
                with open(text_file, 'w') as f:
                    f.write(text)
                print(f"\n💾 Text saved to: {text_file}")
            else:
                print("✗ Could not extract text from screenshot")
        else:
            print(f"\n💾 Screenshot saved to: {final_screenshot}")
            print("   Install OCR libraries to extract text automatically")

        print(f"\n📸 Final screenshot: {final_screenshot}")
    else:
        print("\n✗ Failed to capture response")

    print("\n" + "=" * 70)
    print("✅ DONE")
    print("=" * 70)
    print()

    await ws.close()


if __name__ == "__main__":
    # Parse command line arguments
    url = None
    question = None
    wait_before_asking = 3

    if len(sys.argv) > 1:
        url = sys.argv[1]
    if len(sys.argv) > 2:
        question = sys.argv[2]
    if len(sys.argv) > 3:
        wait_before_asking = int(sys.argv[3])

    asyncio.run(ask_and_capture_with_polling(url, question, wait_before_asking))
