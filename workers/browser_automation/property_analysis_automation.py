#!/usr/bin/env python3
"""
Property Analysis Automation - URL Method
"""
import subprocess
import json
import time
import urllib.parse
from pathlib import Path

def create_perplexity_search(topic_id, topic_name, query):
    """Create Perplexity search using URL parameters."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.perplexity.ai/search?q={encoded_query}"
    
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
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=15)
        final_url = result.stdout.strip()
        
        if '/search/' in final_url:
            results_dir = Path('data/property_analysis/research_results')
            results_dir.mkdir(parents=True, exist_ok=True)
            
            with open(results_dir / f"{topic_id}.json", 'w') as f:
                json.dump({
                    'id': topic_id,
                    'name': topic_name,
                    'url': final_url,
                    'success': True,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }, f, indent=2)
            
            return True, final_url
        return False, None
    except:
        return False, None

# Load property analysis project
project_file = Path('data/property_analysis/property_analysis_project.json')
with open(project_file) as f:
    project = json.load(f)

topics = project['research_topics']

print("=" * 80)
print("PROPERTY ANALYSIS AUTOMATION")
print("=" * 80)
print(f"\nTopics: {len(topics)}\n")

successful = []
for i, topic in enumerate(topics, 1):
    print(f"[{i}/{len(topics)}] {topic['name']}")
    success, url = create_perplexity_search(topic['id'], topic['name'], topic['prompt'])
    
    if success:
        successful.append(topic['name'])
        print(f"  ✅ {url[:70]}...")
    else:
        print(f"  ❌ Failed")
    print()
    if i < len(topics):
        time.sleep(2)

print("=" * 80)
print(f"✅ Complete: {len(successful)}/{len(topics)}")
print("=" * 80)
