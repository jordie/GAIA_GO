#!/usr/bin/env python3
"""
Simple Status Dashboard - See what's running at a glance

Run: python3 status_dashboard.py
Or serve as web: python3 status_dashboard.py --web
"""
import subprocess
import json
import psutil
from pathlib import Path
from datetime import datetime
import sys


class StatusDashboard:
    """System status overview."""
    
    def get_auto_confirm_status(self):
        """Check auto-confirm worker status."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if 'auto_confirm_worker' in ' '.join(proc.info['cmdline'] or []):
                    return {
                        'running': True,
                        'pid': proc.info['pid'],
                        'cpu_percent': proc.cpu_percent(interval=0.1),
                        'memory_mb': proc.memory_info().rss / 1024 / 1024
                    }
            return {'running': False}
        except:
            return {'running': False, 'error': 'Could not check'}
    
    def get_tmux_sessions(self):
        """Get tmux session count and names."""
        try:
            result = subprocess.run(
                ['tmux', 'list-sessions'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                sessions = result.stdout.strip().split('\n')
                return {
                    'count': len(sessions),
                    'sessions': [s.split(':')[0] for s in sessions[:5]],  # First 5
                    'total': len(sessions)
                }
            return {'count': 0, 'sessions': []}
        except:
            return {'count': 0, 'sessions': [], 'error': 'tmux not running'}
    
    def get_research_projects(self):
        """Get active research projects."""
        projects = []
        
        # Ethiopia project
        ethiopia_results = Path('data/ethiopia/research_results')
        if ethiopia_results.exists():
            count = len(list(ethiopia_results.glob('*.json')))
            projects.append({
                'name': 'Ethiopia Trip',
                'topics': count,
                'status': 'complete' if count == 7 else 'in progress',
                'path': str(ethiopia_results)
            })
        
        # Property project
        property_results = Path('data/property_analysis/research_results')
        if property_results.exists():
            count = len(list(property_results.glob('*.json')))
            projects.append({
                'name': 'Property Analysis',
                'topics': count,
                'status': 'complete' if count == 5 else 'in progress',
                'path': str(property_results)
            })
        
        return projects
    
    def get_messaging_stats(self):
        """Get messaging statistics."""
        stats_file = Path('data/messaging_stats.json')
        if stats_file.exists():
            with open(stats_file) as f:
                return json.load(f)
        return {'total_messages': 0, 'by_backend': {}}
    
    def get_verification_stats(self):
        """Get verification statistics."""
        log_file = Path('data/verification_log.json')
        if log_file.exists():
            with open(log_file) as f:
                data = json.load(f)
                if data['total_operations'] > 0:
                    success_rate = (data['verified'] / data['total_operations']) * 100
                else:
                    success_rate = 0
                return {
                    'total': data['total_operations'],
                    'verified': data['verified'],
                    'failed': data['failed'],
                    'success_rate': f"{success_rate:.1f}%"
                }
        return {'total': 0, 'verified': 0, 'failed': 0, 'success_rate': '0%'}
    
    def get_system_resources(self):
        """Get system resource usage."""
        return {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
    
    def get_status(self):
        """Get complete status."""
        return {
            'timestamp': datetime.now().isoformat(),
            'auto_confirm': self.get_auto_confirm_status(),
            'tmux': self.get_tmux_sessions(),
            'research_projects': self.get_research_projects(),
            'messaging': self.get_messaging_stats(),
            'verification': self.get_verification_stats(),
            'system': self.get_system_resources()
        }
    
    def print_status(self):
        """Print formatted status to console."""
        status = self.get_status()
        
        print("=" * 80)
        print(f"SYSTEM STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        
        # Auto-Confirm
        ac = status['auto_confirm']
        print("🤖 AUTO-CONFIRM:")
        if ac['running']:
            print(f"   ✅ Running (PID: {ac['pid']})")
            print(f"   CPU: {ac['cpu_percent']:.1f}%  Memory: {ac['memory_mb']:.1f}MB")
        else:
            print("   ❌ Not running")
        print()
        
        # Tmux Sessions
        tmux = status['tmux']
        print(f"💻 TMUX: {tmux['count']} sessions")
        if tmux['sessions']:
            for s in tmux['sessions']:
                print(f"   • {s}")
            if tmux['total'] > 5:
                print(f"   ... and {tmux['total'] - 5} more")
        print()
        
        # Research Projects
        print(f"🔍 RESEARCH PROJECTS: {len(status['research_projects'])}")
        for proj in status['research_projects']:
            status_icon = "✅" if proj['status'] == 'complete' else "⏳"
            print(f"   {status_icon} {proj['name']}: {proj['topics']} topics")
        print()
        
        # Messaging
        msg = status['messaging']
        print(f"📱 MESSAGING: {msg['total_messages']} messages sent")
        for backend, count in msg.get('by_backend', {}).items():
            print(f"   • {backend}: {count}")
        print()
        
        # Verification
        ver = status['verification']
        print(f"✓ VERIFICATION: {ver['success_rate']} success rate")
        print(f"   Total: {ver['total']}  Verified: {ver['verified']}  Failed: {ver['failed']}")
        print()
        
        # System Resources
        sys_res = status['system']
        print("💾 SYSTEM:")
        print(f"   CPU: {sys_res['cpu_percent']:.1f}%")
        print(f"   Memory: {sys_res['memory_percent']:.1f}%")
        print(f"   Disk: {sys_res['disk_percent']:.1f}%")
        print()
        
        print("=" * 80)


if __name__ == '__main__':
    dashboard = StatusDashboard()
    
    if '--json' in sys.argv:
        print(json.dumps(dashboard.get_status(), indent=2))
    else:
        dashboard.print_status()
