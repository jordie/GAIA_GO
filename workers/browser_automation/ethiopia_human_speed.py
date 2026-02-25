#!/usr/bin/env python3
"""
Human-speed Perplexity submission - like someone quickly browsing
"""

import subprocess
import json
import time
from pathlib import Path
import random


def copy_to_clipboard(text):
    """Copy text to clipboard."""
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
    process.communicate(text)


def submit_to_perplexity():
    """Submit to Perplexity with human-like timing."""

    applescript = '''
tell application "Comet"
    activate
end tell

delay 0.5

tell application "System Events"
    keystroke "f" using {command down}
    delay 0.2
    key code 53
    delay 0.3
    keystroke tab
    delay 0.4
    keystroke "v" using {command down}
    delay 0.8
    keystroke return
end tell
'''

    subprocess.run(['osascript', '-e', applescript], capture_output=True)


def next_tab():
    """Move to next tab."""
    subprocess.run(['osascript', '-e', '''
tell application "System Events"
    keystroke "]" using {command down, shift down}
end tell
'''], capture_output=True)


def human_delay(min_sec=5, max_sec=15):
    """Random delay simulating human reading/waiting."""
    delay = random.uniform(min_sec, max_sec)
    return delay


def main():
    prompts_file = Path("ethiopia_prompts.json")

    if not prompts_file.exists():
        print("Error: ethiopia_prompts.json not found")
        return

    with open(prompts_file) as f:
        data = json.load(f)

    topics = data['tab_groups']

    print("="*80)
    print("🚀 ETHIOPIA - HUMAN-SPEED SUBMISSION")
    print("="*80)
    print()
    print(f"Topics: {len(topics)}")
    print("Speed: Like a human quickly browsing")
    print("Delays: 5-15 seconds (varied, human-like)")
    print(f"Total time: ~{len(topics) * 10 / 60:.0f} minutes")
    print()
    print("Position browser on first Perplexity tab")
    print()

    input("Press Enter to start rapid submission...")

    start_time = time.time()

    for i, topic in enumerate(topics, 1):
        name = topic['name']
        prompt = topic['prompt']

        print(f"\n[{i}/{len(topics)}] {name}")

        # Copy
        copy_to_clipboard(prompt)
        print(f"  📋 Copied")

        # Submit
        submit_to_perplexity()
        print(f"  ✅ Submitted")

        # Human-like wait (reading, checking response)
        if i < len(topics):
            delay = human_delay(5, 15)
            print(f"  ⏱️  {delay:.1f}s → next")

            time.sleep(delay)

            # Move to next tab
            next_tab()
            time.sleep(0.5)

    elapsed = time.time() - start_time

    print("\n" + "="*80)
    print("✅ ALL SUBMITTED")
    print("="*80)
    print()
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Speed: {elapsed/len(topics):.1f} seconds per topic")
    print()
    print("Perplexity is processing all questions")
    print("Responses should be ready in 10-15 minutes")
    print()


if __name__ == "__main__":
    main()
