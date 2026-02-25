#!/usr/bin/env python3
"""
Test if we can send keystrokes to Comet browser
"""

import subprocess
import time


def run_applescript(script):
    """Execute AppleScript."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Error: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"Exception: {e}")
        return False


print("=" * 70)
print("KEYSTROKE TEST")
print("=" * 70)
print()

# Test 1: Activate Comet
print("Test 1: Activating Comet browser...")
script1 = '''
tell application "Comet"
    activate
end tell
'''
if run_applescript(script1):
    print("✓ Comet activated\n")
else:
    print("✗ Failed to activate Comet\n")

time.sleep(1)

# Test 2: Type some visible text (to verify keystrokes work)
print("Test 2: Typing 'hello' to test keystrokes...")
print("(You should see 'hello' typed wherever the cursor is)")
input("Press Enter to send keystroke...")

script2 = '''
tell application "System Events"
    keystroke "hello"
end tell
'''
if run_applescript(script2):
    print("✓ Keystroke sent\n")
else:
    print("✗ Failed to send keystroke\n")

time.sleep(2)

# Test 3: Try Option+A
print("Test 3: Sending Option+A...")
input("Press Enter to send Option+A...")

script3 = '''
tell application "System Events"
    keystroke "a" using {option down}
end tell
'''
if run_applescript(script3):
    print("✓ Option+A sent")
    print("   Did the Perplexity sidebar open?")
else:
    print("✗ Failed to send Option+A")

print()
print("=" * 70)
print("RESULTS:")
print("   If 'hello' appeared: ✓ Keystrokes work")
print("   If sidebar opened: ✓ Option+A works")
print("   If nothing happened: Check Accessibility permissions")
print()
print("Accessibility permissions:")
print("   System Settings > Privacy & Security > Accessibility")
print("   Make sure Terminal (or your terminal app) is allowed")
print("=" * 70)
