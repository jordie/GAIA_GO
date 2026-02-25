#!/usr/bin/env python3
"""
Submit prompts to Perplexity using clipboard and keyboard automation
Simpler approach that works with any browser
"""

import subprocess
import json
import time
from pathlib import Path
import random


def copy_to_clipboard(text):
    """Copy text to macOS clipboard."""
    process = subprocess.Popen(
        ['pbcopy'],
        stdin=subprocess.PIPE,
        text=True
    )
    process.communicate(text)


def send_keys(keys):
    """Send keyboard keys using AppleScript."""

    applescript = f'''
tell application "System Events"
    {keys}
end tell
'''

    subprocess.run(['osascript', '-e', applescript], capture_output=True)


def activate_browser():
    """Activate Comet browser."""

    applescript = '''
tell application "Comet"
    activate
end tell
'''

    subprocess.run(['osascript', '-e', applescript], capture_output=True)


def submit_prompt_to_current_tab(prompt):
    """Submit prompt to currently active Perplexity tab."""

    print(f"  Prompt length: {len(prompt)} chars")

    # Copy prompt to clipboard
    copy_to_clipboard(prompt)
    print(f"  ✓ Copied to clipboard")

    time.sleep(1)

    # Activate browser
    activate_browser()
    time.sleep(1)

    # Click in page and paste
    applescript = '''
tell application "System Events"
    keystroke "f" using {command down}
    delay 0.5
    key code 53
    delay 0.5
    keystroke tab
    delay 1
    keystroke "v" using {command down}
    delay 2
    keystroke return
end tell
'''

    subprocess.run(['osascript', '-e', applescript], capture_output=True)
    print(f"  ✓ Pasted and submitted")

    return True


def next_tab():
    """Switch to next tab."""

    applescript = '''
tell application "System Events"
    keystroke "]" using {command down, shift down}
end tell
'''

    subprocess.run(['osascript', '-e', applescript], capture_output=True)


def submit_all_prompts_interactive():
    """Submit all prompts with user confirmation for each."""

    prompts_file = Path("ethiopia_prompts.json")

    if not prompts_file.exists():
        print("Error: ethiopia_prompts.json not found")
        return

    with open(prompts_file) as f:
        data = json.load(f)

    topics = data['tab_groups']

    print("="*80)
    print("ETHIOPIA - INTERACTIVE PERPLEXITY SUBMISSION")
    print("="*80)
    print()
    print(f"Total prompts: {len(topics)}")
    print()
    print("Instructions:")
    print("1. Make sure you have Perplexity tabs open in Comet")
    print("2. Position yourself on the first Perplexity tab")
    print("3. This script will:")
    print("   - Copy prompt to clipboard")
    print("   - Activate Comet")
    print("   - Paste and submit")
    print("   - Wait 3-5 minutes (rate limiting)")
    print("   - Move to next tab")
    print()

    input("Press Enter when ready to start...")

    for i, topic in enumerate(topics, 1):
        topic_name = topic['name']
        prompt = topic['prompt']

        print(f"\n{'='*80}")
        print(f"[{i}/{len(topics)}] {topic_name}")
        print(f"{'='*80}")

        # Submit prompt
        success = submit_prompt_to_current_tab(prompt)

        if success:
            print(f"  ✓ Submitted successfully")

            # Wait for Perplexity to process
            print(f"  ⏳ Waiting for Perplexity to respond (30 seconds)...")
            time.sleep(30)

            # Move to next tab for next iteration
            if i < len(topics):
                print(f"  → Moving to next tab")
                next_tab()
                time.sleep(2)

                # Rate limiting
                delay = random.randint(180, 300)
                mins, secs = delay // 60, delay % 60

                print(f"\n  ⏱️  Rate limiting: {mins}m {secs}s before next submission")
                print(f"  Next topic: {topics[i]['name']}")

                time.sleep(delay)

    print("\n" + "="*80)
    print("✅ ALL PROMPTS SUBMITTED")
    print("="*80)
    print()
    print("Perplexity is processing all questions.")
    print("Check back in 30-60 minutes for complete responses.")
    print()
    print("Next steps:")
    print("1. Review each Perplexity tab for responses")
    print("2. Copy conversation URLs")
    print("3. Update Google Sheet:")
    print("   python3 ethiopia_add_url.py add 'Flights' 'URL'")
    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        # Fully automated mode (risky)
        print("Auto mode not recommended due to rate limiting")
        print("Use interactive mode instead")
    else:
        submit_all_prompts_interactive()
