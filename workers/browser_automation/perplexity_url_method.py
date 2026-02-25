#!/usr/bin/env python3
"""
Use Perplexity URL parameters to create searches directly
"""
import subprocess
import json
import time
import urllib.parse
from pathlib import Path

def open_perplexity_search(query):
    """Open Perplexity search using URL parameters."""
    encoded_query = urllib.parse.quote(query)
    
    # Try different URL formats
    urls_to_try = [
        f"https://www.perplexity.ai/search?q={encoded_query}",
        f"https://www.perplexity.ai/?q={encoded_query}",
        f"https://www.perplexity.ai/search/{encoded_query}",
    ]
    
    for url in urls_to_try:
        print(f"Trying: {url[:80]}...")
        
        script = f'''
        tell application "Comet"
            tell application "System Events"
                keystroke "t" using {{command down}}
            end tell
            delay 1
            set URL of active tab of window 1 to "{url}"
            delay 5
            get URL of active tab of window 1
        end tell
        '''
        
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            final_url = result.stdout.strip()
            print(f"Final URL: {final_url[:80]}...")
            
            if '/search/' in final_url:
                print("✅ Conversation created!")
                return True, final_url
            else:
                print("❌ No conversation")
        
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(2)
    
    return False, None

# Test with first prompt
prompts_file = Path('data/ethiopia/ethiopia_prompts.json')
with open(prompts_file) as f:
    data = json.load(f)

topic = data['tab_groups'][0]
print(f"Testing URL method with: {topic['name']}")
print()

success, url = open_perplexity_search(topic['prompt'])

if success:
    print(f"\n🎯 SUCCESS! URL: {url}")
else:
    print("\n❌ URL method failed")
