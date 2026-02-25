#!/usr/bin/env python3
"""
Auto-Confirm Monitor - Real-time monitoring of auto-confirm activity

Monitors auto-confirm worker and tracks:
- What prompts are being detected
- Which ones are auto-approved vs rejected
- Risk levels and reasoning
- Real-time activity feed
- Statistics (approval rate, common prompts)

Usage:
    monitor = AutoConfirmMonitor()
    activity = monitor.get_recent_activity()
    stats = monitor.get_stats()
"""
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict


class AutoConfirmMonitor:
    """Monitor auto-confirm worker activity."""

    def __init__(self):
        self.log_file = Path('data/auto_confirm_activity.json')
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_activity()

        # Risk level classifications
        self.risk_levels = {
            'safe': ['read', 'glob', 'grep', 'task', 'websearch', 'webfetch'],
            'low': ['bash (ls/pwd/echo)', 'bash (read-only)'],
            'medium': ['bash (file operations)', 'edit', 'write'],
            'high': ['bash (git)', 'bash (rm)', 'bash (system commands)'],
            'critical': ['bash (dangerous)']
        }

    def load_activity(self):
        """Load activity log."""
        if self.log_file.exists():
            with open(self.log_file) as f:
                self.activity = json.load(f)
        else:
            self.activity = {
                'prompts': [],
                'stats': {
                    'total_prompts': 0,
                    'auto_approved': 0,
                    'manually_confirmed': 0,
                    'rejected': 0,
                    'by_tool': {},
                    'by_risk_level': {}
                }
            }

    def save_activity(self):
        """Save activity log."""
        with open(self.log_file, 'w') as f:
            json.dump(self.activity, f, indent=2)

    def classify_prompt(self, prompt_text: str) -> Dict:
        """
        Classify a prompt by tool and risk level.

        Returns:
            Classification details
        """
        prompt_lower = prompt_text.lower()

        # Detect tool
        tool = 'unknown'
        if 'read' in prompt_lower or 'reading' in prompt_lower:
            tool = 'read'
        elif 'write' in prompt_lower or 'writing' in prompt_lower:
            tool = 'write'
        elif 'edit' in prompt_lower or 'editing' in prompt_lower:
            tool = 'edit'
        elif 'bash' in prompt_lower or 'command' in prompt_lower:
            tool = 'bash'
        elif 'glob' in prompt_lower:
            tool = 'glob'
        elif 'grep' in prompt_lower:
            tool = 'grep'
        elif 'task' in prompt_lower:
            tool = 'task'
        elif 'websearch' in prompt_lower or 'web search' in prompt_lower:
            tool = 'websearch'
        elif 'webfetch' in prompt_lower or 'web fetch' in prompt_lower:
            tool = 'webfetch'

        # Determine risk level
        risk_level = 'low'
        for level, tools in self.risk_levels.items():
            if any(t in tool.lower() for t in tools):
                risk_level = level
                break

        # Extract command if bash
        command = None
        if tool == 'bash':
            # Try to extract command
            match = re.search(r'command[:\s]+([^\n]+)', prompt_lower)
            if match:
                command = match.group(1).strip()

        return {
            'tool': tool,
            'risk_level': risk_level,
            'command': command
        }

    def log_prompt(self, prompt_text: str, action: str, reasoning: str = ''):
        """
        Log a prompt detection.

        Args:
            prompt_text: The prompt text detected
            action: auto_approved, manually_confirmed, rejected
            reasoning: Why this action was taken
        """
        classification = self.classify_prompt(prompt_text)

        prompt_entry = {
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt_text[:200],  # Limit length
            'action': action,
            'reasoning': reasoning,
            'tool': classification['tool'],
            'risk_level': classification['risk_level'],
            'command': classification.get('command')
        }

        self.activity['prompts'].append(prompt_entry)

        # Update stats
        self.activity['stats']['total_prompts'] += 1
        self.activity['stats'][action] = self.activity['stats'].get(action, 0) + 1

        # By tool
        tool = classification['tool']
        if tool not in self.activity['stats']['by_tool']:
            self.activity['stats']['by_tool'][tool] = 0
        self.activity['stats']['by_tool'][tool] += 1

        # By risk level
        risk_level = classification['risk_level']
        if risk_level not in self.activity['stats']['by_risk_level']:
            self.activity['stats']['by_risk_level'][risk_level] = 0
        self.activity['stats']['by_risk_level'][risk_level] += 1

        # Keep only last 1000 prompts
        if len(self.activity['prompts']) > 1000:
            self.activity['prompts'] = self.activity['prompts'][-1000:]

        self.save_activity()

    def get_recent_activity(self, limit: int = 20, minutes: int = None) -> List[Dict]:
        """
        Get recent activity.

        Args:
            limit: Max number of entries
            minutes: Only show activity from last N minutes

        Returns:
            List of recent prompts
        """
        prompts = self.activity['prompts'][-limit:]

        if minutes:
            cutoff = datetime.now() - timedelta(minutes=minutes)
            prompts = [
                p for p in prompts
                if datetime.fromisoformat(p['timestamp']) > cutoff
            ]

        return list(reversed(prompts))

    def get_stats(self) -> Dict:
        """Get activity statistics."""
        stats = self.activity['stats'].copy()

        # Calculate rates
        total = stats['total_prompts']
        if total > 0:
            stats['approval_rate'] = f"{(stats.get('auto_approved', 0) / total) * 100:.1f}%"
            stats['manual_rate'] = f"{(stats.get('manually_confirmed', 0) / total) * 100:.1f}%"
            stats['rejection_rate'] = f"{(stats.get('rejected', 0) / total) * 100:.1f}%"
        else:
            stats['approval_rate'] = '0%'
            stats['manual_rate'] = '0%'
            stats['rejection_rate'] = '0%'

        # Most common tool
        if stats['by_tool']:
            most_common_tool = max(stats['by_tool'], key=stats['by_tool'].get)
            stats['most_common_tool'] = most_common_tool
        else:
            stats['most_common_tool'] = None

        # Most common risk level
        if stats['by_risk_level']:
            most_common_risk = max(stats['by_risk_level'], key=stats['by_risk_level'].get)
            stats['most_common_risk'] = most_common_risk
        else:
            stats['most_common_risk'] = None

        return stats

    def get_activity_by_tool(self, tool: str, limit: int = 10) -> List[Dict]:
        """Get recent activity for a specific tool."""
        return [
            p for p in self.activity['prompts']
            if p['tool'] == tool
        ][-limit:]

    def get_activity_by_risk(self, risk_level: str, limit: int = 10) -> List[Dict]:
        """Get recent activity for a specific risk level."""
        return [
            p for p in self.activity['prompts']
            if p['risk_level'] == risk_level
        ][-limit:]

    def simulate_activity(self):
        """Simulate some activity for testing."""
        sample_prompts = [
            ("Read file: data/ethiopia/ethiopia_prompts.json", "auto_approved", "Safe read operation"),
            ("Bash command: ls -la", "auto_approved", "Safe listing command"),
            ("Write file: test.txt", "manually_confirmed", "File write requires confirmation"),
            ("Bash command: rm -rf /", "rejected", "Dangerous command blocked"),
            ("Glob pattern: **/*.py", "auto_approved", "Safe file pattern search"),
            ("Edit file: config.py", "manually_confirmed", "Code edit needs review"),
            ("WebSearch: Ethiopia travel tips", "auto_approved", "Safe web search"),
            ("Task: Deploy to production", "manually_confirmed", "Deployment needs approval"),
        ]

        for prompt, action, reasoning in sample_prompts:
            self.log_prompt(prompt, action, reasoning)

        print(f"Simulated {len(sample_prompts)} activity entries")


# CLI interface
if __name__ == '__main__':
    import sys

    monitor = AutoConfirmMonitor()

    if '--simulate' in sys.argv:
        # Simulate activity for testing
        monitor.simulate_activity()
        print("\n✅ Simulated activity logged\n")

    elif '--stats' in sys.argv:
        # Show statistics
        stats = monitor.get_stats()
        print("\n" + "="*80)
        print("AUTO-CONFIRM STATISTICS")
        print("="*80 + "\n")
        print(f"Total Prompts: {stats['total_prompts']}")
        print(f"\nActions:")
        print(f"  Auto-Approved:        {stats.get('auto_approved', 0):4} ({stats['approval_rate']})")
        print(f"  Manually Confirmed:   {stats.get('manually_confirmed', 0):4} ({stats['manual_rate']})")
        print(f"  Rejected:             {stats.get('rejected', 0):4} ({stats['rejection_rate']})")

        if stats['by_tool']:
            print(f"\nBy Tool:")
            for tool, count in sorted(stats['by_tool'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {tool:15} {count:4}")

        if stats['by_risk_level']:
            print(f"\nBy Risk Level:")
            for risk, count in sorted(stats['by_risk_level'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {risk:10} {count:4}")

        if stats['most_common_tool']:
            print(f"\nMost Common Tool: {stats['most_common_tool']}")
        if stats['most_common_risk']:
            print(f"Most Common Risk: {stats['most_common_risk']}")

        print("\n" + "="*80)

    elif '--recent' in sys.argv:
        # Show recent activity
        activity = monitor.get_recent_activity(limit=20)
        print("\n" + "="*80)
        print("RECENT AUTO-CONFIRM ACTIVITY")
        print("="*80 + "\n")

        if not activity:
            print("No activity yet. Run with --simulate to generate test data.\n")
        else:
            for entry in activity:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M:%S')
                action_icon = {
                    'auto_approved': '✅',
                    'manually_confirmed': '⚠️',
                    'rejected': '❌'
                }.get(entry['action'], '?')

                print(f"[{timestamp}] {action_icon} {entry['action'].upper()}")
                print(f"  Tool: {entry['tool']:10} Risk: {entry['risk_level']}")
                print(f"  Prompt: {entry['prompt'][:80]}...")
                if entry['reasoning']:
                    print(f"  Reason: {entry['reasoning']}")
                print()

    else:
        print("""
Auto-Confirm Monitor - Track auto-confirm activity

Usage:
    python3 auto_confirm_monitor.py --stats       # Show statistics
    python3 auto_confirm_monitor.py --recent      # Show recent activity
    python3 auto_confirm_monitor.py --simulate    # Generate test data

Statistics:
    - Total prompts detected
    - Auto-approved vs manually confirmed vs rejected
    - By tool (read, bash, edit, etc.)
    - By risk level (safe, low, medium, high, critical)

Activity Log:
    - Real-time feed of detected prompts
    - Action taken (approved/confirmed/rejected)
    - Risk level and reasoning
    - Tool type and command details
""")
