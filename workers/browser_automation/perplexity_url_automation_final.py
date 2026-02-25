#!/usr/bin/env python3
"""
WORKING Perplexity Automation - Uses URL Parameters
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
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        final_url = result.stdout.strip()
        
        if '/search/' in final_url:
            # Save result
            results_dir = Path('data/ethiopia/research_results')
            results_dir.mkdir(parents=True, exist_ok=True)
            
            result_data = {
                'id': topic_id,
                'name': topic_name,
                'url': final_url,
                'query': query[:200],
                'success': True,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(results_dir / f"{topic_id}.json", 'w') as f:
                json.dump(result_data, f, indent=2)
            
            return True, final_url
        
        return False, None
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False, None

def main():
    prompts_file = Path('data/ethiopia/ethiopia_prompts.json')
    with open(prompts_file) as f:
        data = json.load(f)
    
    topics = data['tab_groups']
    
    print("=" * 80)
    print("PERPLEXITY AUTOMATION - URL METHOD")
    print("=" * 80)
    print()
    print(f"Topics: {len(topics)}")
    print("Method: Direct URL parameters (VERIFIED WORKING)")
    print()
    
    results = {'successful': [], 'failed': []}
    
    for i, topic in enumerate(topics, 1):
        topic_id = topic['id']
        topic_name = topic['name']
        prompt = topic['prompt']
        
        print(f"[{i}/{len(topics)}] {topic_name}")
        print(f"  ID: {topic_id}")
        
        success, url = create_perplexity_search(topic_id, topic_name, prompt)
        
        if success:
            results['successful'].append(topic_name)
            print(f"  ✅ Created: {url[:70]}...")
        else:
            results['failed'].append(topic_name)
            print(f"  ❌ Failed")
        
        print()
        
        if i < len(topics):
            time.sleep(2)
    
    print("=" * 80)
    print("COMPLETE!")
    print("=" * 80)
    print()
    print(f"✅ Successful: {len(results['successful'])}/{len(topics)}")
    print(f"❌ Failed: {len(results['failed'])}/{len(topics)}")
    print()
    
    if results['successful']:
        print("Research running for:")
        for name in results['successful']:
            print(f"  ✓ {name}")
    
    print()
    print("URLs saved to: data/ethiopia/research_results/")

if __name__ == '__main__':
    main()
