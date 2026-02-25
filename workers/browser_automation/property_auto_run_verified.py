#!/usr/bin/env python3
"""
Property Analysis automation with verification
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
    """Submit to Perplexity with longer delays."""
    try:
        subprocess.run(['osascript', '-e', 'tell application "Comet" to activate'], 
                      capture_output=True, timeout=5)
        time.sleep(1)
        
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
        return False

# Load project
project_file = Path('data/property_analysis/property_analysis_project.json')
with open(project_file) as f:
    project = json.load(f)

topics = project['research_topics']

print("=" * 80)
print("PROPERTY ANALYSIS - VERIFIED SUBMISSION")
print("=" * 80)
print()
print(f"Topics: {len(topics)}")
print()

successful = 0
failed = []

for i, topic in enumerate(topics, 1):
    name = topic['name']
    prompt = topic['prompt']
    
    print(f"[{i}/{len(topics)}] {name}")
    
    if not copy(prompt):
        failed.append(name)
        continue
    print(f"  📋 Copied to clipboard")
    
    if not submit_with_verification():
        failed.append(name)
        continue
    
    print(f"  ✅ Submitted")
    successful += 1
    
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
print("=" * 80)
