#!/usr/bin/env python3
import subprocess, json, time, random
from pathlib import Path

def copy(t): subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True).communicate(t)

def submit():
    subprocess.run(['osascript', '-e', '''
tell application "Comet" to activate
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
'''], capture_output=True)

def next_tab():
    subprocess.run(['osascript', '-e', 'tell application "System Events" to keystroke "]" using {command down, shift down}'], capture_output=True)

data = json.load(open('ethiopia_prompts.json'))
topics = data['tab_groups']

print(f"🚀 Starting rapid submission of {len(topics)} topics...")
print("Human-speed: 5-15 second delays")
print()

for i, t in enumerate(topics, 1):
    print(f"[{i}/{len(topics)}] {t['name']}")
    copy(t['prompt'])
    print("  ✅ Submitted")
    submit()

    if i < len(topics):
        delay = random.uniform(5, 15)
        print(f"  ⏱️  {delay:.1f}s")
        time.sleep(delay)
        next_tab()
        time.sleep(0.5)

print(f"\n✅ All {len(topics)} submitted! Check Perplexity tabs.")
