#!/usr/bin/env python3
"""
Fast submission to Perplexity - minimal delays
"""

import subprocess
import json
import time
from pathlib import Path


def copy_to_clipboard(text):
    """Copy text to clipboard."""
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
    process.communicate(text)


def submit_to_perplexity():
    """Submit current clipboard content to Perplexity."""

    applescript = '''
tell application "Comet"
    activate
end tell

delay 1

tell application "System Events"
    -- Click in textarea
    keystroke "f" using {command down}
    delay 0.3
    key code 53
    delay 0.3

    -- Tab to input
    keystroke tab
    delay 0.5

    -- Paste
    keystroke "v" using {command down}
    delay 1

    -- Submit
    keystroke return
end tell
'''

    subprocess.run(['osascript', '-e', applescript], capture_output=True)


def next_tab():
    """Move to next tab."""
    applescript = '''
tell application "System Events"
    keystroke "]" using {command down, shift down}
end tell
'''
    subprocess.run(['osascript', '-e', applescript], capture_output=True)


def main():
    prompts_file = Path("ethiopia_prompts.json")

    if not prompts_file.exists():
        print("Error: ethiopia_prompts.json not found")
        return

    with open(prompts_file) as f:
        data = json.load(f)

    topics = data['tab_groups']

    print("="*80)
    print("ETHIOPIA - FAST PERPLEXITY SUBMISSION")
    print("="*80)
    print()
    print(f"Topics: {len(topics)}")
    print("Delays: ~30 seconds between submissions")
    print("Total time: ~5-10 minutes for all")
    print()
    print("Make sure Perplexity tabs are open in Comet")
    print()

    input("Press Enter to start...")

    for i, topic in enumerate(topics, 1):
        name = topic['name']
        prompt = topic['prompt']

        print(f"\n[{i}/{len(topics)}] {name}")

        # Copy to clipboard
        copy_to_clipboard(prompt)
        print(f"  ✓ Copied to clipboard")

        # Submit
        submit_to_perplexity()
        print(f"  ✓ Submitted")

        # Brief wait for processing
        print(f"  ⏳ Waiting 30 seconds...")
        time.sleep(30)

        # Move to next tab
        if i < len(topics):
            next_tab()
            print(f"  → Next tab")
            time.sleep(2)

    print("\n" + "="*80)
    print("✅ ALL SUBMITTED")
    print("="*80)
    print()
    print("Check Perplexity tabs for responses")
    print()


if __name__ == "__main__":
    main()
