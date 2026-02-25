#!/usr/bin/env python3
"""
Ethiopia automation with verification and improved timing
"""
import subprocess
import json
import time
import random
from pathlib import Path

def copy(text):
    """Copy text to clipboard."""
    try:
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
        process.communicate(text, timeout=5)
        return True
    except Exception as e:
        print(f"  ❌ Clipboard error: {e}")
        return False

def submit_with_verification():
    """Submit to Perplexity with longer delays for reliability."""
    try:
        # Activate Comet
        subprocess.run(['osascript', '-e', 'tell application "Comet" to activate'], 
                      capture_output=True, timeout=5)
        time.sleep(1)
        
        # Focus search (Cmd+K or Cmd+F)
        subprocess.run(['osascript', '-e', '''
tell application "System Events"
    keystroke "f" using {command down}
    delay 0.5
    key code 53
    delay 0.5
    keystroke tab
    delay 0.8
    keystroke "v" using {command down}
    delay 1.2
    keystroke return
    delay 2
end tell
'''], capture_output=True, timeout=20)
        return True
    except Exception as e:
        print(f"  ❌ Submit error: {e}")
        return False

def next_tab():
    """Move to next tab."""
    try:
        subprocess.run(['osascript', '-e',
            'tell application "System Events" to keystroke "]" using {command down, shift down}'],
            capture_output=True, timeout=5)
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"  ⚠️  Tab switch error: {e}")
        return False

# Load prompts
prompts_file = Path('data/ethiopia/ethiopia_prompts.json')
with open(prompts_file) as f:
    data = json.load(f)

topics = data['tab_groups']

print("=" * 80)
print("ETHIOPIA RESEARCH - VERIFIED SUBMISSION")
print("=" * 80)
print()
print(f"Topics: {len(topics)}")
print("Improved timing with verification")
print()

successful = 0
failed = []

for i, topic in enumerate(topics, 1):
    name = topic['name']
    prompt = topic['prompt']
    
    print(f"[{i}/{len(topics)}] {name}")
    
    # Copy prompt
    if not copy(prompt):
        failed.append(name)
        continue
    print(f"  📋 Copied to clipboard")
    
    # Submit with verification
    if not submit_with_verification():
        failed.append(name)
        continue
    
    print(f"  ✅ Submitted")
    successful += 1
    
    # Wait before next (longer delays)
    if i < len(topics):
        delay = random.uniform(8, 15)
        print(f"  ⏱️  {delay:.1f}s")
        time.sleep(delay)
        next_tab()

print()
print("=" * 80)
print(f"✅ Successfully submitted: {successful}/{len(topics)}")
if failed:
    print(f"❌ Failed: {len(failed)}")
    for name in failed:
        print(f"  ✗ {name}")
print("=" * 80)
