#!/usr/bin/env python3
"""
Verified Perplexity Automation
- Opens new tab for each topic
- Submits prompt
- Verifies conversation created
- Reports status
"""
import subprocess
import json
import time
import random
from pathlib import Path

def run_applescript(script):
    """Execute AppleScript and return output."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr
    except Exception as e:
        return False, str(e)

def open_new_perplexity_tab():
    """Open new tab and navigate to Perplexity."""
    script = '''
    tell application "Comet"
        activate
        tell application "System Events"
            keystroke "t" using {command down}
            delay 1
        end tell
        set URL of active tab of window 1 to "https://www.perplexity.ai/"
        delay 3
    end tell
    '''
    success, output = run_applescript(script)
    if success:
        print("  📂 New tab opened")
        return True
    else:
        print(f"  ❌ Failed to open tab: {output}")
        return False

def get_current_url():
    """Get URL of active tab."""
    script = '''
    tell application "Comet"
        get URL of active tab of window 1
    end tell
    '''
    success, url = run_applescript(script)
    return url if success else None

def copy_to_clipboard(text):
    """Copy text to clipboard."""
    try:
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
        process.communicate(text, timeout=5)
        return True
    except Exception as e:
        print(f"  ❌ Clipboard error: {e}")
        return False

def submit_to_perplexity():
    """Submit prompt using keyboard automation."""
    script = '''
    tell application "Comet"
        activate
        delay 0.5
    end tell
    tell application "System Events"
        keystroke "f" using {command down}
        delay 0.3
        key code 53
        delay 0.5
        keystroke tab
        delay 0.5
        keystroke "v" using {command down}
        delay 1
        keystroke return
        delay 3
    end tell
    '''
    success, output = run_applescript(script)
    if success:
        print("  ⌨️  Submitted")
        return True
    else:
        print(f"  ❌ Submit failed: {output}")
        return False

def verify_conversation_started():
    """Check if conversation URL contains /search/."""
    for attempt in range(6):  # Try for 6 seconds
        time.sleep(1)
        url = get_current_url()
        if url and "/search/" in url:
            print(f"  ✅ Verified: Conversation active")
            return True, url
        print(f"  ⏳ Waiting for conversation... ({attempt + 1}/6)")
    
    return False, None

def save_result(topic_id, topic_name, url, success):
    """Save research result."""
    results_dir = Path('data/ethiopia/research_results')
    results_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = results_dir / f"{topic_id}.json"
    data = {
        'id': topic_id,
        'name': topic_name,
        'url': url,
        'success': success,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open(result_file, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    # Load Ethiopia prompts
    prompts_file = Path('data/ethiopia/ethiopia_prompts.json')
    with open(prompts_file) as f:
        data = json.load(f)
    
    topics = data['tab_groups']
    
    print("=" * 80)
    print("VERIFIED PERPLEXITY AUTOMATION")
    print("=" * 80)
    print()
    print(f"Topics to research: {len(topics)}")
    print("Each topic will:")
    print("  1. Open new Perplexity tab")
    print("  2. Submit prompt")
    print("  3. Verify conversation started")
    print("  4. Save result")
    print()
    input("Press Enter to start (make sure Comet is open)...")
    print()
    
    results = {
        'successful': [],
        'failed': [],
        'total': len(topics)
    }
    
    for i, topic in enumerate(topics, 1):
        topic_id = topic['id']
        topic_name = topic['name']
        prompt = topic['prompt']
        
        print(f"[{i}/{len(topics)}] {topic_name}")
        print(f"  ID: {topic_id}")
        
        # Step 1: Open new tab
        if not open_new_perplexity_tab():
            results['failed'].append(topic_name)
            save_result(topic_id, topic_name, None, False)
            continue
        
        # Step 2: Copy prompt
        if not copy_to_clipboard(prompt):
            results['failed'].append(topic_name)
            save_result(topic_id, topic_name, None, False)
            continue
        print("  📋 Copied prompt")
        
        # Step 3: Submit
        if not submit_to_perplexity():
            results['failed'].append(topic_name)
            save_result(topic_id, topic_name, None, False)
            continue
        
        # Step 4: Verify
        success, url = verify_conversation_started()
        if success:
            results['successful'].append(topic_name)
            save_result(topic_id, topic_name, url, True)
            print(f"  🎯 URL: {url[:60]}...")
        else:
            results['failed'].append(topic_name)
            save_result(topic_id, topic_name, get_current_url(), False)
            print(f"  ⚠️  Could not verify conversation")
        
        print()
        
        # Wait before next topic
        if i < len(topics):
            delay = random.uniform(3, 6)
            print(f"  ⏱️  Waiting {delay:.1f}s before next topic...")
            time.sleep(delay)
            print()
    
    # Final summary
    print("=" * 80)
    print("AUTOMATION COMPLETE")
    print("=" * 80)
    print()
    print(f"✅ Successful: {len(results['successful'])}/{results['total']}")
    print(f"❌ Failed: {len(results['failed'])}/{results['total']}")
    print()
    
    if results['successful']:
        print("Successful topics:")
        for name in results['successful']:
            print(f"  ✓ {name}")
        print()
    
    if results['failed']:
        print("Failed topics (may need manual submission):")
        for name in results['failed']:
            print(f"  ✗ {name}")
        print()
    
    print("Results saved to: data/ethiopia/research_results/")
    print()

if __name__ == '__main__':
    main()
