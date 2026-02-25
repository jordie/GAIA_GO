#!/usr/bin/env python3
"""
Submit prompts to already-open Perplexity tabs using AppleScript
"""

import subprocess
import json
import time
from pathlib import Path


def submit_to_perplexity_via_applescript(prompt, tab_index=1, delay_after=3):
    """Use AppleScript to paste prompt into Perplexity tab and submit."""

    # AppleScript to:
    # 1. Activate Comet browser
    # 2. Go to specific tab
    # 3. Click in textarea
    # 4. Paste prompt
    # 5. Submit

    applescript = f'''
tell application "Comet"
    activate
    delay 0.5

    -- Go to tab {tab_index}
    tell window 1
        set current tab to tab {tab_index}
    end tell

    delay 1

    -- Click on the textarea (Perplexity input)
    tell application "System Events"
        keystroke "f" using {{command down}}
        delay 0.5
        key code 53  -- Escape to close find
        delay 0.5

        -- Tab to get to input area
        keystroke tab
        delay 0.5

        -- Paste the prompt
        set the clipboard to "{prompt.replace('"', '\\"').replace('\n', ' ')}"
        keystroke "v" using {{command down}}
        delay 1

        -- Submit (Enter key)
        keystroke return
    end tell

    delay {delay_after}
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
    print("SUBMITTING PROMPTS TO OPEN PERPLEXITY TABS")
    print("="*80)
    print()
    print(f"Total prompts: {len(topics)}")
    print()
    print("NOTE: This assumes Perplexity tabs are already open")
    print("      Each prompt will be submitted with 3-5 minute delay")
    print()

    input("Press Enter when Perplexity tabs are ready in Comet browser...")

    submitted = 0

    for i, topic in enumerate(topics, 1):
        topic_name = topic['name']
        prompt = topic['prompt']

        print(f"\n[{i}/{len(topics)}] Submitting: {topic_name}")

        # Submit to tab i (tabs are 1-indexed)
        success = submit_to_perplexity_via_applescript(
            prompt=prompt,
            tab_index=i,
            delay_after=3
        )

        if success:
            submitted += 1
            print(f"  ✓ Submitted to tab {i}")
        else:
            print(f"  ✗ Failed to submit")

        # Wait 3-5 minutes between submissions (rate limiting)
        if i < len(topics):
            import random
            delay = random.randint(180, 300)  # 3-5 minutes

            print(f"\n  ⏱️  Waiting {delay//60}m {delay%60}s before next submission...")
            time.sleep(delay)

    print("\n" + "="*80)
    print("SUBMISSION COMPLETE")
    print("="*80)
    print()
    print(f"Submitted: {submitted}/{len(topics)}")
    print()
    print("Perplexity is now processing your questions.")
    print("Wait 30-60 minutes for all responses to complete.")
    print("Then collect conversation URLs and update Google Sheet.")
    print()


if __name__ == "__main__":
    submit_all_prompts()
