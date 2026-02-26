#!/usr/bin/env python3
"""
Auto Router & Executor - Route and execute tasks automatically

Combines smart routing with actual execution:
1. Analyzes task → Routes to best AI/tool
2. Executes via appropriate method (tmux, Perplexity URL, browser automation)
3. Tracks results and learns from feedback

Usage:
    executor = AutoRouterExecutor()
    result = executor.execute("Research Ethiopia hotels for families")
"""
import subprocess
import json
import time
import urllib.parse
from pathlib import Path
from datetime import datetime
from smart_task_router import SmartTaskRouter
from perplexity_scraper import PerplexityScraper


class AutoRouterExecutor:
    """Automatically route and execute tasks."""

    def __init__(self):
        self.router = SmartTaskRouter()
        self.scraper = PerplexityScraper()
        self.results_dir = Path('data/auto_execution')
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def execute_via_claude(self, task: str) -> dict:
        """
        Execute task via Claude (tmux session).

        For now, returns instructions for manual execution.
        Future: Integrate with tmux Claude sessions.
        """
        return {
            'status': 'manual_required',
            'method': 'claude_tmux',
            'instructions': f'Send to Claude tmux session: {task}',
            'suggested_session': 'claude-research'
        }

    def execute_via_perplexity(self, task: str) -> dict:
        """
        Execute task via Perplexity (URL method).

        Opens Perplexity search in browser via Comet.
        """
        try:
            # Encode query for URL
            encoded_query = urllib.parse.quote(task)
            url = f"https://www.perplexity.ai/search?q={encoded_query}"

            # Open in Comet browser
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

            # Verify /search/ in URL
            if '/search/' in final_url:
                # Auto-scrape the result
                scraped_result = self.scraper.scrape_url(final_url, method='simple')
                self.scraper.scrape_and_save(final_url, method='simple')

                return {
                    'status': 'success',
                    'method': 'perplexity_url',
                    'url': final_url,
                    'verified': True,
                    'scraped': True,
                    'search_id': scraped_result.get('search_id'),
                    'query': scraped_result.get('query', task)
                }
            else:
                return {
                    'status': 'failed',
                    'method': 'perplexity_url',
                    'url': final_url,
                    'verified': False,
                    'scraped': False,
                    'error': 'URL missing /search/ pattern'
                }

        except Exception as e:
            return {
                'status': 'error',
                'method': 'perplexity_url',
                'error': str(e)
            }

    def execute_via_comet(self, task: str) -> dict:
        """
        Execute task via Comet browser automation.

        For now, returns instructions for manual execution.
        Future: Implement AppleScript automation.
        """
        return {
            'status': 'manual_required',
            'method': 'comet_automation',
            'instructions': f'Automate in Comet browser: {task}',
            'suggested_action': 'Use AppleScript or Playwright'
        }

    def execute(self, task: str, auto_execute: bool = True) -> dict:
        """
        Route and execute a task automatically.

        Args:
            task: Task to execute
            auto_execute: If False, only route without executing

        Returns:
            Execution result
        """
        # Route the task
        target, confidence, reasoning = self.router.route(task)

        result = {
            'timestamp': datetime.now().isoformat(),
            'task': task,
            'routing': {
                'target': target,
                'confidence': confidence,
                'reasoning': reasoning
            }
        }

        # Execute if auto_execute enabled
        if auto_execute:
            if target == 'claude':
                exec_result = self.execute_via_claude(task)
            elif target == 'perplexity':
                exec_result = self.execute_via_perplexity(task)
            elif target == 'comet':
                exec_result = self.execute_via_comet(task)
            else:
                exec_result = {'status': 'unknown_target', 'error': f'Unknown target: {target}'}

            result['execution'] = exec_result

            # Save result
            result_file = self.results_dir / f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)

        return result

    def batch_execute(self, tasks: list, auto_execute: bool = True) -> list:
        """
        Execute multiple tasks in batch.

        Args:
            tasks: List of task descriptions
            auto_execute: If False, only route without executing

        Returns:
            List of execution results
        """
        results = []
        for task in tasks:
            result = self.execute(task, auto_execute=auto_execute)
            results.append(result)

            # Small delay between tasks
            if auto_execute:
                time.sleep(2)

        return results

    def get_recent_executions(self, limit: int = 10) -> list:
        """Get recent execution results."""
        result_files = sorted(self.results_dir.glob('exec_*.json'), reverse=True)[:limit]

        results = []
        for result_file in result_files:
            with open(result_file) as f:
                results.append(json.load(f))

        return results


# CLI interface
if __name__ == '__main__':
    import sys

    executor = AutoRouterExecutor()

    if '--recent' in sys.argv:
        # Show recent executions
        results = executor.get_recent_executions()
        print("\n" + "="*80)
        print("RECENT EXECUTIONS")
        print("="*80 + "\n")

        for result in results:
            print(f"Task: {result['task']}")
            print(f"→ Routed to: {result['routing']['target'].upper()} ({result['routing']['confidence']:.2f})")
            if 'execution' in result:
                exec_status = result['execution']['status']
                print(f"  Execution: {exec_status}")
                if exec_status == 'success':
                    print(f"  ✅ URL: {result['execution'].get('url', 'N/A')}")
            print()

    elif '--dry-run' in sys.argv:
        # Dry run (route only, don't execute)
        task = ' '.join([arg for arg in sys.argv[1:] if arg != '--dry-run'])
        if task:
            result = executor.execute(task, auto_execute=False)
            print(f"\nTask: {task}")
            print(f"→ Would route to: {result['routing']['target'].upper()}")
            print(f"  Confidence: {result['routing']['confidence']:.2f}")
            print(f"  Reasoning: {result['routing']['reasoning']}\n")

    elif len(sys.argv) > 1:
        # Execute a task
        task = ' '.join(sys.argv[1:])
        result = executor.execute(task, auto_execute=True)

        print(f"\nTask: {task}")
        print(f"→ Routed to: {result['routing']['target'].upper()} ({result['routing']['confidence']:.2f})")
        print(f"  Reasoning: {result['routing']['reasoning']}")

        if 'execution' in result:
            print(f"\nExecution:")
            exec_result = result['execution']
            print(f"  Status: {exec_result['status']}")

            if exec_result['status'] == 'success':
                print(f"  ✅ URL: {exec_result['url']}")
                print(f"  ✅ Verified: {exec_result['verified']}")
            elif exec_result['status'] == 'manual_required':
                print(f"  📝 {exec_result['instructions']}")
            elif exec_result['status'] == 'error':
                print(f"  ❌ Error: {exec_result['error']}")

        print()

    else:
        print("""
Auto Router & Executor - Intelligent task execution

Usage:
    python3 auto_router_executor.py "your task"     # Route and execute
    python3 auto_router_executor.py --dry-run "task"  # Route only
    python3 auto_router_executor.py --recent         # Show recent executions

Examples:
    # Execute Perplexity search
    python3 auto_router_executor.py "What is the capital of Ethiopia?"

    # Dry run (route only)
    python3 auto_router_executor.py --dry-run "Research Ethiopia hotels"

Supported targets:
    - Claude (tmux): Deep research, analysis, coding
    - Perplexity: Quick facts, current events
    - Comet: Web automation

Note: Claude and Comet execution require manual steps for now.
      Only Perplexity executes automatically via URL method.
""")
