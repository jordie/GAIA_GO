#!/usr/bin/env python3
"""
Improved Automation System - With verification and messaging

Combines:
- Unified messaging (Email → File → Console)
- Verification layer (always verify success)
- Better error handling and logging
"""
import subprocess
import json
import time
import urllib.parse
from pathlib import Path
from datetime import datetime

# Import our new modules
from unified_messaging import UnifiedMessenger
from automation_verification import AutomationVerifier


class ImprovedPerplexityAutomation:
    """Perplexity automation with built-in verification and notifications."""
    
    def __init__(self, notify_recipient=None):
        self.verifier = AutomationVerifier()
        self.messenger = UnifiedMessenger() if notify_recipient else None
        self.recipient = notify_recipient
    
    def create_search(self, topic_id, topic_name, prompt):
        """
        Create Perplexity search with verification.
        
        Returns:
            (success, url, error_message)
        """
        try:
            # Create URL
            encoded_query = urllib.parse.quote(prompt)
            url = f"https://www.perplexity.ai/search?q={encoded_query}"
            
            # Open in browser
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
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            final_url = result.stdout.strip()
            
            # VERIFY - This is the key improvement
            try:
                self.verifier.verify_perplexity_submission(final_url)
                return True, final_url, None
            
            except Exception as verify_error:
                # Verification failed - return error
                return False, final_url, str(verify_error)
        
        except Exception as e:
            return False, None, str(e)
    
    def run_research(self, prompts_file, project_name):
        """
        Run complete research project with verification and notifications.
        
        Args:
            prompts_file: Path to JSON with research topics
            project_name: Name of project (e.g., 'Ethiopia Trip')
        
        Returns:
            Summary of results
        """
        with open(prompts_file) as f:
            data = json.load(f)
        
        topics = data.get('tab_groups') or data.get('research_topics')
        
        results = {
            'project': project_name,
            'total': len(topics),
            'successful': [],
            'failed': [],
            'urls': {}
        }
        
        print(f"\n{'='*80}")
        print(f"IMPROVED AUTOMATION: {project_name}")
        print(f"{'='*80}\n")
        
        for i, topic in enumerate(topics, 1):
            topic_id = topic['id']
            topic_name = topic['name']
            prompt = topic['prompt']
            
            print(f"[{i}/{len(topics)}] {topic_name}")
            
            success, url, error = self.create_search(topic_id, topic_name, prompt)
            
            if success:
                results['successful'].append(topic_name)
                results['urls'][topic_id] = url
                print(f"  ✅ Verified: {url[:60]}...")
            else:
                results['failed'].append(topic_name)
                print(f"  ❌ Failed: {error}")
            
            print()
            
            if i < len(topics):
                time.sleep(2)
        
        # Send notification if configured
        if self.messenger and self.recipient:
            self._send_completion_notification(results)
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _send_completion_notification(self, results):
        """Send completion notification."""
        message = f"""
🎯 Research Complete: {results['project']}

✅ Successful: {len(results['successful'])}/{results['total']}
❌ Failed: {len(results['failed'])}/{results['total']}

Successful topics:
"""
        for topic in results['successful']:
            message += f"  • {topic}\n"
        
        if results['failed']:
            message += f"\nFailed topics:\n"
            for topic in results['failed']:
                message += f"  • {topic}\n"
        
        message += f"\nTimestamp: {datetime.now().isoformat()}"
        
        self.messenger.send(message, self.recipient)
    
    def _print_summary(self, results):
        """Print results summary."""
        print(f"{'='*80}")
        print("RESULTS SUMMARY")
        print(f"{'='*80}\n")
        print(f"Project: {results['project']}")
        print(f"Success Rate: {len(results['successful'])}/{results['total']} ({len(results['successful'])/results['total']*100:.1f}%)")
        print()
        
        if results['successful']:
            print("✅ Successful:")
            for topic in results['successful']:
                print(f"   • {topic}")
            print()
        
        if results['failed']:
            print("❌ Failed:")
            for topic in results['failed']:
                print(f"   • {topic}")
            print()


# Example usage
if __name__ == '__main__':
    automation = ImprovedPerplexityAutomation(
        notify_recipient='jgirmay@gmail.com'
    )
    
    # Run Ethiopia research with improvements
    results = automation.run_research(
        'data/ethiopia/ethiopia_prompts.json',
        'Ethiopia Trip (Improved)'
    )
