#!/usr/bin/env python3
"""
Simple Session Restart Script

Restart tmux sessions by re-running the original command.
Much simpler than keep-alive - just restart when needed.

Usage:
    python3 session_restart.py --list              # List sessions
    python3 session_restart.py --restart claude_architect  # Restart specific session
    python3 session_restart.py --restart-all       # Restart all Claude sessions
    python3 session_restart.py --kill <session>    # Kill a session
"""

import argparse
import subprocess
import sys
from typing import List, Optional


def get_sessions() -> List[str]:
    """Get list of tmux sessions."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")
        return []
    except Exception as e:
        print(f"❌ Error listing sessions: {e}")
        return []


def kill_session(session: str) -> bool:
    """Kill a tmux session."""
    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", session], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error killing session {session}: {e}")
        return False


def create_session(session: str, command: Optional[str] = None) -> bool:
    """Create a new tmux session."""
    try:
        if command:
            # Create session with specific command
            result = subprocess.run(
                ["tmux", "new-session", "-d", "-s", session, command],
                capture_output=True,
                text=True,
                timeout=5,
            )
        else:
            # Create session with shell
            result = subprocess.run(
                ["tmux", "new-session", "-d", "-s", session],
                capture_output=True,
                text=True,
                timeout=5,
            )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error creating session {session}: {e}")
        return False


def restart_session(session: str, command: Optional[str] = None) -> bool:
    """Restart a session (kill and recreate)."""
    print(f"🔄 Restarting session: {session}")

    # Kill existing session
    if session in get_sessions():
        print(f"   Killing existing session...")
        if not kill_session(session):
            print(f"   ❌ Failed to kill session")
            return False

    # Create new session
    print(f"   Creating new session...")
    if create_session(session, command):
        print(f"   ✅ Session restarted successfully")
        return True
    else:
        print(f"   ❌ Failed to create session")
        return False


def restart_claude_session(session: str) -> bool:
    """Restart a Claude session with the claude command."""
    # Get the base session name without 'claude_' prefix
    base_name = session.replace("claude_", "")

    # Claude sessions typically run: claude code
    command = "claude code"

    return restart_session(session, command)


def list_sessions():
    """List all sessions."""
    sessions = get_sessions()

    print("=" * 70)
    print("📺 TMUX SESSIONS")
    print("=" * 70)

    if not sessions:
        print("No sessions found")
        return

    claude_sessions = []
    other_sessions = []

    for session in sessions:
        if "claude" in session.lower():
            claude_sessions.append(session)
        else:
            other_sessions.append(session)

    if claude_sessions:
        print("\n🤖 Claude Sessions:")
        for i, session in enumerate(claude_sessions, 1):
            print(f"   {i}. {session}")

    if other_sessions:
        print("\n💻 Other Sessions:")
        for i, session in enumerate(other_sessions, 1):
            print(f"   {i}. {session}")

    print(f"\nTotal: {len(sessions)} sessions")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Simple Session Restart")
    parser.add_argument("--list", action="store_true", help="List all sessions")
    parser.add_argument("--restart", type=str, help="Restart specific session")
    parser.add_argument("--restart-all", action="store_true", help="Restart all Claude sessions")
    parser.add_argument("--kill", type=str, help="Kill specific session")
    parser.add_argument("--command", type=str, help="Command to run in session")

    args = parser.parse_args()

    if args.list:
        list_sessions()

    elif args.restart:
        session = args.restart
        if "claude" in session.lower():
            restart_claude_session(session)
        else:
            restart_session(session, args.command)

    elif args.restart_all:
        sessions = get_sessions()
        claude_sessions = [s for s in sessions if "claude" in s.lower()]

        print(f"🔄 Restarting {len(claude_sessions)} Claude sessions...")

        success_count = 0
        for session in claude_sessions:
            if restart_claude_session(session):
                success_count += 1

        print(f"\n✅ Restarted {success_count}/{len(claude_sessions)} sessions")

    elif args.kill:
        session = args.kill
        if kill_session(session):
            print(f"✅ Killed session: {session}")
        else:
            print(f"❌ Failed to kill session: {session}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
