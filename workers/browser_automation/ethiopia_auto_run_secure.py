#!/usr/bin/env python3
"""
Ethiopia prompt submission with error handling and security improvements
"""
import subprocess
import json
import time
import random
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def copy(text):
    """Copy text to clipboard with error handling."""
    try:
        process = subprocess.Popen(
            ['pbcopy'],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(text, timeout=5)
        return True
    except subprocess.TimeoutExpired:
        logger.error("Timeout copying to clipboard")
        return False
    except Exception as e:
        logger.error(f"Error copying to clipboard: {e}")
        return False


def submit():
    """Submit prompt to Perplexity with error handling."""
    try:
        result = subprocess.run(
            ['osascript', '-e', '''
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
'''],
            capture_output=True,
            timeout=15
        )
        
        if result.returncode != 0:
            logger.error(f"AppleScript error: {result.stderr.decode()}")
            return False
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Timeout during submission")
        return False
    except Exception as e:
        logger.error(f"Error during submission: {e}")
        return False


def next_tab():
    """Move to next tab with error handling."""
    try:
        subprocess.run(
            ['osascript', '-e',
             'tell application "System Events" to keystroke "]" using {command down, shift down}'],
            capture_output=True,
            timeout=5
        )
        return True
    except subprocess.TimeoutExpired:
        logger.error("Timeout moving to next tab")
        return False
    except Exception as e:
        logger.error(f"Error moving to next tab: {e}")
        return False


def main():
    prompts_file = Path('ethiopia_prompts.json')
    
    # Validate file exists
    if not prompts_file.exists():
        logger.error(f"Prompts file not found: {prompts_file}")
        logger.error("Please run setup_ethiopia_project.py first")
        sys.exit(1)
    
    try:
        with open(prompts_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in prompts file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading prompts file: {e}")
        sys.exit(1)
    
    topics = data.get('tab_groups', [])
    
    if not topics:
        logger.error("No topics found in prompts file")
        sys.exit(1)
    
    print(f"🚀 Starting rapid submission of {len(topics)} topics...")
    print("Human-speed: 5-15 second delays")
    print()
    
    successful = 0
    failed = []
    
    for i, t in enumerate(topics, 1):
        name = t.get('name', f'Topic {i}')
        prompt = t.get('prompt', '')
        
        if not prompt:
            logger.warning(f"Skipping {name} - no prompt found")
            failed.append(name)
            continue
        
        print(f"[{i}/{len(topics)}] {name}")
        
        # Copy prompt
        if not copy(prompt):
            print(f"  ❌ Failed to copy")
            failed.append(name)
            continue
        
        # Submit
        if not submit():
            print(f"  ❌ Failed to submit")
            failed.append(name)
            continue
        
        print("  ✅ Submitted")
        successful += 1
        
        # Human-like delay between submissions
        if i < len(topics):
            delay = random.uniform(5, 15)
            print(f"  ⏱️  {delay:.1f}s")
            time.sleep(delay)
            
            if not next_tab():
                logger.warning("Failed to move to next tab")
            
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
    print("Check Perplexity tabs for responses")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
