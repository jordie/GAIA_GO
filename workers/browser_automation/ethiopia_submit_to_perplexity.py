#!/usr/bin/env python3
"""
Actually submit prompts to open Perplexity tabs using AppleScript
"""

import subprocess
import json
import time
from pathlib import Path
import random


def submit_prompt_to_perplexity(prompt, delay_before_submit=2):
    """Use AppleScript to submit a prompt to Perplexity."""

    # Clean prompt for AppleScript (escape quotes and newlines)
    clean_prompt = prompt.replace('"', '\\"').replace("'", "\\'").replace('\n', ' ')

    applescript = f'''
tell application "Comet"
    activate
    delay 1

    tell application "System Events"
        -- Click on the page to focus
        key code 48  -- Tab key to navigate
        delay {delay_before_submit}

        -- Type the prompt
        keystroke "{clean_prompt[:500]}"  -- Limit length for AppleScript
        delay 2

        -- Press Enter to submit
        keystroke return
        delay 1
    end tell
end tell
'''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return True
        else:
            print(f"AppleScript error: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def find_perplexity_tabs():
    """Find open Perplexity tabs in Comet."""

    applescript = '''
tell application "Comet"
    set tabList to {}
    set tabCount to count of tabs of window 1
    repeat with i from 1 to tabCount
        set tabURL to URL of tab i of window 1
        if tabURL contains "perplexity.ai" then
            set end of tabList to i
        end if
    end repeat
    return tabList
end tell
'''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            # Parse tab indices
            output = result.stdout.strip()
            if output:
                # Output is like "1, 2, 3"
                tabs = [int(x.strip()) for x in output.split(',') if x.strip()]
                return tabs
        return []

    except Exception as e:
        print(f"Error finding tabs: {e}")
        return []


def activate_tab(tab_index):
    """Activate a specific tab in Comet."""

    applescript = f'''
tell application "Comet"
    activate
    tell window 1
        set current tab to tab {tab_index}
    end tell
    delay 1
end tell
'''

    try:
        subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=10
        )
        return True
    except:
        return False


def submit_all_prompts():
    """Submit all Ethiopia prompts to open Perplexity tabs."""

    prompts_file = Path("ethiopia_prompts.json")

    if not prompts_file.exists():
        print("Error: ethiopia_prompts.json not found")
        return

    with open(prompts_file) as f:
        data = json.load(f)

    topics = data['tab_groups']

    print("="*80)
    print("SUBMITTING PROMPTS TO PERPLEXITY TABS")
    print("="*80)
    print()

    # Find Perplexity tabs
    print("Finding open Perplexity tabs...")
    perplexity_tabs = find_perplexity_tabs()

    if not perplexity_tabs:
        print("No Perplexity tabs found. Opening tabs first...")
        # Could open tabs here, but for now just error
        return

    print(f"Found {len(perplexity_tabs)} Perplexity tab(s)")
    print()

    submitted = 0

    for i, topic in enumerate(topics, 0):
        if i >= len(perplexity_tabs):
            print(f"Not enough tabs open. Need {len(topics)}, have {len(perplexity_tabs)}")
            break

        topic_name = topic['name']
        prompt = topic['prompt']
        tab_index = perplexity_tabs[i]

        print(f"[{i+1}/{len(topics)}] {topic_name}")
        print(f"  Tab index: {tab_index}")

        # Activate tab
        print(f"  Activating tab...")
        activate_tab(tab_index)
        time.sleep(2)

        # Submit prompt
        print(f"  Submitting prompt...")
        success = submit_prompt_to_perplexity(prompt, delay_before_submit=3)

        if success:
            submitted += 1
            print(f"  ✓ Submitted")
        else:
            print(f"  ✗ Failed")

        # Rate limiting
        if i < len(topics) - 1:
            delay = random.randint(180, 300)  # 3-5 minutes
            mins, secs = delay // 60, delay % 60

            print(f"\n  ⏱️  Rate limiting: {mins}m {secs}s")
            print(f"  Next: {topics[i+1]['name']}\n")

            time.sleep(delay)

    print("\n" + "="*80)
    print("SUBMISSION COMPLETE")
    print("="*80)
    print()
    print(f"Submitted: {submitted}/{len(topics)}")
    print()
    print("Perplexity is now processing your questions.")
    print("Check back in 30-60 minutes for responses.")
    print()


if __name__ == "__main__":
    submit_all_prompts()
