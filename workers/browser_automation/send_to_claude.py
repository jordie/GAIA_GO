#!/usr/bin/env python3
"""
Send research topics to Claude via OpenClaw for better quality results
"""
import json
import subprocess
import time
from pathlib import Path

def send_to_claude_agent(topic_name, prompt):
    """Send research prompt to Claude via OpenClaw agent."""
    
    # Create a formatted prompt for Claude
    claude_prompt = f"""Research Request: {topic_name}

{prompt}

Please provide a comprehensive, detailed analysis with:
- Specific recommendations
- Concrete data and numbers where available
- Practical next steps
- Any important considerations or warnings
"""
    
    print(f"Sending to Claude: {topic_name}")
    
    # Use OpenClaw to send to Claude
    try:
        result = subprocess.run(
            ['openclaw', 'agent', '--deliver', '--message', claude_prompt],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"  ✅ Sent to Claude agent")
            return True
        else:
            print(f"  ❌ Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False

# Load Ethiopia prompts
prompts_file = Path('data/ethiopia/ethiopia_prompts.json')
with open(prompts_file) as f:
    data = json.load(f)

print("=" * 80)
print("SENDING RESEARCH TO CLAUDE (Better Quality)")
print("=" * 80)
print()

topics = data['tab_groups'][:2]  # Start with first 2 as test

for i, topic in enumerate(topics, 1):
    print(f"[{i}/{len(topics)}] {topic['name']}")
    send_to_claude_agent(topic['name'], topic['prompt'])
    print()
    time.sleep(2)

print("=" * 80)
print("Test complete. Claude will provide much better analysis than Perplexity.")
print("Would you like me to send all 12 topics to Claude instead?")
