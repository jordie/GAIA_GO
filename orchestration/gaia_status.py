#!/usr/bin/env python3
"""
GAIA Status Command
===================

Display a hierarchical tree of all tmux sessions with details:
- Session names, directories, git branches
- Session types (architect, manager, developer)
- Agent providers (claude, codex, ollama, comet)
- Work duration (how long on current task)

Usage:
  python3 gaia_status.py              # Full status tree
  python3 gaia_status.py --brief      # Condensed view
  python3 gaia_status.py --json       # JSON output
  python3 gaia_status.py --watch      # Real-time updates (5s refresh)
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

GAIA_HOME = Path("/Users/jgirmay/Desktop/gitrepo/GAIA_HOME")
SESSION_STATE_FILE = GAIA_HOME / "orchestration" / ".session_state.json"


class SessionInfo:
    """Information about a tmux session"""

    def __init__(self, name: str):
        self.name = name
        self.pane_count = 0
        self.created_at = None
        self.cwd = None
        self.git_branch = None
        self.git_repo = None
        self.session_type = self._classify_type()
        self.agent_provider = self._infer_provider()
        self.work_start = self._get_work_start()
        self.work_duration = None
        self.status = "idle"
        self._fetch_details()

    def _classify_type(self) -> str:
        """Classify session type based on name"""
        name = self.name.lower()
        if any(x in name for x in ["arch", "claude_architect", "inspector", "linter", "comparison", "foundation", "pr_review"]):
            return "architect"
        elif any(x in name for x in ["manager", "dev_", "tester_"]):
            return "manager"
        else:
            return "developer"

    def _infer_provider(self) -> str:
        """Infer LLM provider from session name"""
        name = self.name.lower()
        if "claude" in name or "arch" in name or "dev_worker" in name or "pr_integ" in name:
            return "claude"
        elif "codex" in name or "pr_impl" in name:
            return "codex"
        elif "comet" in name:
            return "comet"
        elif "comparison" in name or "foundation" in name:
            return "curator"
        else:
            return "unknown"

    def _get_work_start(self) -> Optional[datetime]:
        """Get when session started working on current task"""
        state = self._load_state()
        if self.name in state and "work_start" in state[self.name]:
            try:
                return datetime.fromisoformat(state[self.name]["work_start"])
            except:
                return None
        return None

    def _load_state(self) -> Dict:
        """Load session state from file"""
        if SESSION_STATE_FILE.exists():
            try:
                with open(SESSION_STATE_FILE) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _fetch_details(self):
        """Fetch session details from tmux"""
        try:
            # Get pane count
            result = subprocess.run(
                ["tmux", "list-panes", "-t", self.name, "-F", "#{pane_id}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                self.pane_count = len(result.stdout.strip().split("\n"))

            # Get working directory from first pane
            result = subprocess.run(
                ["tmux", "send-keys", "-t", f"{self.name}:0", "pwd", "Enter"],
                capture_output=True,
                timeout=1,
            )

            # Capture output to get cwd
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", f"{self.name}:0", "-p"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in reversed(lines):
                    line = line.strip()
                    if line and not line.startswith(">"):
                        self.cwd = line
                        break

            # Get git branch if in repo
            if self.cwd:
                try:
                    result = subprocess.run(
                        ["git", "-C", self.cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    if result.returncode == 0:
                        self.git_branch = result.stdout.strip()

                    result = subprocess.run(
                        ["git", "-C", self.cwd, "rev-parse", "--show-toplevel"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    if result.returncode == 0:
                        self.git_repo = result.stdout.strip()
                except:
                    pass

        except Exception as e:
            pass

    def get_work_duration(self) -> str:
        """Get formatted work duration"""
        if not self.work_start:
            return "—"

        elapsed = datetime.now() - self.work_start
        hours = elapsed.seconds // 3600
        minutes = (elapsed.seconds % 3600) // 60

        if elapsed.days > 0:
            return f"{elapsed.days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.session_type,
            "provider": self.agent_provider,
            "cwd": self.cwd,
            "git_branch": self.git_branch,
            "git_repo": self.git_repo,
            "pane_count": self.pane_count,
            "work_duration": self.get_work_duration(),
        }


def get_all_sessions() -> List[SessionInfo]:
    """Get all tmux sessions"""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            sessions = []
            for name in result.stdout.strip().split("\n"):
                if name:
                    sessions.append(SessionInfo(name))
            return sorted(sessions, key=lambda s: (s.session_type != "architect", s.name))
        return []
    except Exception as e:
        print(f"Error getting sessions: {e}", file=sys.stderr)
        return []


def print_tree(sessions: List[SessionInfo], brief: bool = False):
    """Print session tree"""
    if not sessions:
        print("No tmux sessions found")
        return

    # Group by type
    by_type = {}
    for session in sessions:
        if session.session_type not in by_type:
            by_type[session.session_type] = []
        by_type[session.session_type].append(session)

    # Print header
    print("\n" + "=" * 100)
    print("GAIA SESSION STATUS".center(100))
    print("=" * 100 + "\n")

    # Print each group
    type_order = ["architect", "manager", "developer"]
    for session_type in type_order:
        if session_type not in by_type:
            continue

        sessions_in_type = by_type[session_type]
        print(f"🏛️  {session_type.upper()} TIER ({len(sessions_in_type)} sessions)")
        print("-" * 100)

        for i, session in enumerate(sessions_in_type):
            is_last = i == len(sessions_in_type) - 1
            prefix = "└─ " if is_last else "├─ "

            # Session name and provider
            provider_emoji = {
                "claude": "🤖",
                "codex": "💻",
                "ollama": "🦙",
                "comet": "🌐",
                "curator": "🎨",
                "unknown": "❓",
            }.get(session.agent_provider, "?")

            print(f"{prefix}{provider_emoji} {session.name:<25} ({session.agent_provider})")

            if not brief:
                # Work duration
                duration_prefix = "   " if is_last else "│  "
                print(f"{duration_prefix}├─ Duration: {session.get_work_duration()}")

                # Git branch
                if session.git_branch:
                    print(f"{duration_prefix}├─ Branch: {session.git_branch}")

                # Working directory
                if session.cwd:
                    cwd_short = session.cwd.replace(
                        str(Path.home()), "~"
                    )
                    print(f"{duration_prefix}├─ Work Dir: {cwd_short}")

                # Panes
                if session.pane_count > 1:
                    print(f"{duration_prefix}└─ Panes: {session.pane_count}")
                print()

    print("=" * 100)
    print(f"Total Sessions: {len(sessions)}")
    print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100 + "\n")


def print_json(sessions: List[SessionInfo]):
    """Print as JSON"""
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_sessions": len(sessions),
        "sessions": [s.to_dict() for s in sessions],
    }
    print(json.dumps(data, indent=2))


def watch_mode(interval: int = 5):
    """Watch mode with real-time updates"""
    try:
        while True:
            os.system("clear" if os.name != "nt" else "cls")
            sessions = get_all_sessions()
            print_tree(sessions, brief=True)
            print(f"Refreshing every {interval}s... (Press Ctrl+C to exit)")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nWatch mode stopped")
        sys.exit(0)


def save_session_state(sessions: List[SessionInfo]):
    """Save session state for future reference"""
    state = {}
    for session in sessions:
        state[session.name] = {
            "type": session.session_type,
            "provider": session.agent_provider,
            "work_start": (session.work_start or datetime.now()).isoformat(),
            "last_updated": datetime.now().isoformat(),
        }

    SESSION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Display GAIA session status tree",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 gaia_status.py              # Full status tree
  python3 gaia_status.py --brief      # Condensed view
  python3 gaia_status.py --json       # JSON output
  python3 gaia_status.py --watch      # Real-time updates
        """,
    )
    parser.add_argument(
        "--brief", action="store_true", help="Show condensed view"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode with real-time updates",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Refresh interval in seconds for watch mode",
    )

    args = parser.parse_args()

    if args.watch:
        watch_mode(args.interval)
    else:
        sessions = get_all_sessions()
        save_session_state(sessions)

        if args.json:
            print_json(sessions)
        else:
            print_tree(sessions, brief=args.brief)


if __name__ == "__main__":
    main()
