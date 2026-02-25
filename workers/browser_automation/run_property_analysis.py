#!/usr/bin/env python3
"""
Run Property Analysis Automation
Submit all 5 research topics to Perplexity
"""
import subprocess
import json
import time
import random
import sys
from pathlib import Path

def copy(text):
    """Copy text to clipboard."""
    try:
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
        process.communicate(text, timeout=5)
        return True
    except Exception as e:
        print(f"Error copying to clipboard: {e}")
        return False

def submit():
    """Submit to Perplexity."""
    try:
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
'''], capture_output=True, timeout=15)
        return True
    except Exception as e:
        print(f"Error submitting: {e}")
        return False

def next_tab():
    """Move to next tab."""
    try:
        subprocess.run(['osascript', '-e',
            'tell application "System Events" to keystroke "]" using {command down, shift down}'],
            capture_output=True, timeout=5)
        return True
    except Exception as e:
        print(f"Error moving tab: {e}")
        return False

# Load project data
project_file = Path('data/property_analysis/property_analysis_project.json')

if not project_file.exists():
    print("Error: property_analysis_project.json not found")
    print("Run: python3 create_property_analysis_project.py first")
    sys.exit(1)

with open(project_file) as f:
    project = json.load(f)

topics = project['research_topics']

print("="*80)
print("PROPERTY ANALYSIS AUTOMATION")
print("="*80)
print()
print(f"Project: {project['name']}")
print(f"Topics: {len(topics)}")
print()

# Get property details from user if provided
property_address = input("Property address (optional, press Enter to skip): ").strip()
print()

print("🚀 Starting automated research submission...")
print()

successful = 0
failed = []

for i, topic in enumerate(topics, 1):
    topic_id = topic['id']
    name = topic['name']
    prompt = topic['prompt']
    
    # Add property address context if provided
    if property_address:
        prompt = f"Property: {property_address}\n\n{prompt}"
    
    print(f"[{i}/{len(topics)}] {name}")
    
    if not copy(prompt):
        print(f"  ❌ Failed to copy")
        failed.append(name)
        continue
    
    if not submit():
        print(f"  ❌ Failed to submit")
        failed.append(name)
        continue
    
    print(f"  ✅ Submitted")
    successful += 1
    
    if i < len(topics):
        delay = random.uniform(5, 15)
        print(f"  ⏱️  {delay:.1f}s")
        time.sleep(delay)
        
        if not next_tab():
            print(f"  ⚠️  Could not move to next tab")
        
        time.sleep(0.5)

print()
print("="*80)
print(f"✅ Successfully submitted: {successful}/{len(topics)}")
if failed:
    print(f"❌ Failed: {len(failed)}")
    print("\nFailed topics:")
    for name in failed:
        print(f"  ✗ {name}")
print("="*80)
print()
print("📊 Perplexity is now analyzing the property...")
print("⏳ Estimated completion: 10-15 minutes")
print()
print("Results will include:")
print("  • Property value and comparables")
print("  • Rental income potential")
print("  • 100% loan feasibility")
print("  • Cash flow projections")
print("  • Risk assessment")
print()
