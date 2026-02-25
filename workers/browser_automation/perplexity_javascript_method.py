#!/usr/bin/env python3
"""
Use JavaScript to directly interact with Perplexity page
"""
import subprocess
import json
import time
from pathlib import Path

def execute_javascript(js_code):
    """Execute JavaScript in active Comet tab."""
    script = f'''
    tell application "Comet"
        tell active tab of window 1
            execute javascript "{js_code}"
        end tell
    end tell
    '''
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)

# Load first prompt
prompts_file = Path('data/ethiopia/ethiopia_prompts.json')
with open(prompts_file) as f:
    data = json.load(f)

topic = data['tab_groups'][0]
prompt = topic['prompt'].replace('"', '\\"').replace('\n', '\\n')

print(f"Testing JavaScript method with: {topic['name']}")
print()

# Navigate to Perplexity
nav_script = '''
tell application "Comet"
    set URL of active tab of window 1 to "https://www.perplexity.ai/"
end tell
'''
subprocess.run(['osascript', '-e', nav_script])
time.sleep(4)

# Try to find and fill the textarea using JavaScript
js_fill = f'''
var textarea = document.querySelector('textarea');
if (textarea) {{
    textarea.value = "{prompt[:100]}...";
    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
    console.log('Filled textarea');
}}
'''

print("Attempting to fill search box with JavaScript...")
success, result = execute_javascript(js_fill)
print(f"Result: {success} - {result}")

# Try to click submit button
time.sleep(1)
js_submit = '''
var button = document.querySelector('button[type="submit"]') || document.querySelector('button');
if (button) {
    button.click();
    console.log('Clicked submit');
}
'''

print("Attempting to submit...")
success2, result2 = execute_javascript(js_submit)
print(f"Result: {success2} - {result2}")

# Check URL after submission
time.sleep(3)
check_url = '''
tell application "Comet"
    get URL of active tab of window 1
end tell
'''
result = subprocess.run(['osascript', '-e', check_url], capture_output=True, text=True)
final_url = result.stdout.strip()
print(f"\nFinal URL: {final_url}")

if '/search/' in final_url:
    print("🎯 SUCCESS! Conversation created!")
else:
    print("⚠️  Still on home page")
