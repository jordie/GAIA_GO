#!/usr/bin/env python3
"""
Direct Perplexity submission - clicks in search box, pastes, submits
"""
import subprocess
import json
import time
from pathlib import Path

def copy_to_clipboard(text):
    """Copy text to clipboard."""
    try:
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
        process.communicate(text, timeout=5)
        return True
    except:
        return False

def submit_to_perplexity_direct():
    """Submit to Perplexity by clicking search box and pasting."""
    script = '''
    tell application "Comet"
        activate
        delay 0.5
        set URL of active tab of window 1 to "https://www.perplexity.ai/"
        delay 3
    end tell
    
    tell application "System Events"
        tell process "Comet"
            -- Click in the page to focus
            keystroke tab
            delay 0.5
            keystroke tab
            delay 0.5
            
            -- Paste the prompt
            keystroke "v" using {command down}
            delay 1
            
            -- Submit with Enter
            keystroke return
            delay 4
        end tell
    end tell
    
    tell application "Comet"
        get URL of active tab of window 1
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=20
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            return True, url
        return False, result.stderr
    except Exception as e:
        return False, str(e)

# Test with first prompt
prompts_file = Path('data/ethiopia/ethiopia_prompts.json')
with open(prompts_file) as f:
    data = json.load(f)

topic = data['tab_groups'][0]
print(f"Testing with: {topic['name']}")
print()

# Copy prompt
if copy_to_clipboard(topic['prompt']):
    print("✅ Copied to clipboard")
else:
    print("❌ Failed to copy")
    exit(1)

# Submit
print("Submitting to Perplexity...")
success, result = submit_to_perplexity_direct()

if success:
    print(f"✅ Success!")
    print(f"URL: {result}")
    
    if '/search/' in result:
        print("🎯 Conversation created!")
    else:
        print("⚠️  No conversation URL yet, might still be loading")
else:
    print(f"❌ Failed: {result}")
