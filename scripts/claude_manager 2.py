#!/usr/bin/env python3
"""
Claude Session Manager - Interactive TUI for managing Claude sessions.

Provides a clean interface to:
- View all session statuses at a glance
- Assign tasks with proper environment isolation
- Monitor progress without streaming noise
- Coordinate work across sessions

Usage:
    python3 claude_manager.py          # Interactive mode
    python3 claude_manager.py --daemon # Background status monitor
"""

import curses
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Dict, List, Optional, Tuple

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
STATE_FILE = DATA_DIR / "claude_manager_state.json"

# Import session_assigner functions
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from session_assigner import (
        ARCHITECT_SCOPES,
        EDU_FEATURE_ENVS,
        KANBAN_ENVS,
        PROJECTS,
        assign_task,
        load_state,
        release_session,
        save_state,
    )
except ImportError:
    # Fallback definitions
    EDU_FEATURE_ENVS = {}
    KANBAN_ENVS = {}
    ARCHITECT_SCOPES = {}

# Status indicators
STATUS_ICONS = {
    "working": "⚙️ ",
    "thinking": "🧠",
    "idle": "💤",
    "error": "❌",
    "waiting": "⏳",
    "done": "✅",
    "unknown": "❓",
}

# ANSI colors for non-curses output
COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


class SessionMonitor:
    """Monitors tmux sessions and extracts status."""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.lock = Lock()
        self.running = False

    def get_tmux_sessions(self) -> List[str]:
        """Get list of active tmux sessions."""
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        return []

    def capture_session(self, session: str, lines: int = 30) -> str:
        """Capture recent output from a session."""
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
            capture_output=True,
            text=True,
        )
        return result.stdout if result.returncode == 0 else ""

    def parse_status(self, output: str) -> Dict:
        """Parse session output to determine status."""
        status = {
            "state": "unknown",
            "activity": "",
            "progress": "",
            "is_claude": False,
            "has_error": False,
        }

        if not output:
            return status

        # Check if Claude is running
        if "bypass permissions" in output or "accept edits" in output:
            status["is_claude"] = True

        # Detect current state
        if (
            "(thinking)" in output
            or "Thinking" in output
            or "Mustering" in output
            or "Elucidating" in output
        ):
            status["state"] = "thinking"
            # Extract thinking time
            match = re.search(r"(\d+m?\s*\d*s?)\s*·", output)
            if match:
                status["progress"] = match.group(1)
        elif "(running)" in output:
            status["state"] = "working"
            # Try to extract what's running
            match = re.search(r"·\s*([^·]+)\s*\(running\)", output)
            if match:
                status["activity"] = match.group(1).strip()[:40]
        elif "background task" in output:
            status["state"] = "working"
            match = re.search(r"(\d+)\s*background task", output)
            if match:
                status["activity"] = f"{match.group(1)} bg tasks"
        elif status["is_claude"]:
            status["state"] = "idle"

        # Check for errors
        if "Error" in output or "error:" in output.lower() or "failed" in output.lower():
            status["has_error"] = True

        # Extract last meaningful line
        lines = [l.strip() for l in output.split("\n") if l.strip() and not l.startswith("─")]
        for line in reversed(lines):
            if len(line) > 10 and not line.startswith(">") and not line.startswith("⏵"):
                status["activity"] = line[:50]
                break

        return status

    def update_session(self, session: str):
        """Update status for a single session."""
        output = self.capture_session(session)
        status = self.parse_status(output)

        with self.lock:
            self.sessions[session] = {
                "name": session,
                "status": status,
                "last_update": datetime.now().isoformat(),
                "output_preview": output[-200:] if output else "",
            }

    def update_all(self):
        """Update all session statuses."""
        sessions = self.get_tmux_sessions()
        for session in sessions:
            self.update_session(session)

        # Remove stale sessions
        with self.lock:
            current = set(sessions)
            stale = set(self.sessions.keys()) - current
            for s in stale:
                del self.sessions[s]

    def get_session(self, name: str) -> Optional[Dict]:
        """Get session info."""
        with self.lock:
            return self.sessions.get(name)

    def get_all_sessions(self) -> Dict[str, Dict]:
        """Get all session info."""
        with self.lock:
            return dict(self.sessions)


class ClaudeManager:
    """Interactive Claude session manager."""

    def __init__(self):
        self.monitor = SessionMonitor()
        self.assigner_state = load_state()
        self.selected_idx = 0
        self.mode = "list"  # list, assign, detail
        self.message = ""
        self.input_buffer = ""

    def refresh_data(self):
        """Refresh all data."""
        self.monitor.update_all()
        self.assigner_state = load_state()

    def get_session_list(self) -> List[Tuple[str, Dict, Dict]]:
        """Get combined session list with status and assignment."""
        sessions = self.monitor.get_all_sessions()
        assignments = self.assigner_state.get("sessions", {})

        result = []
        for name in sorted(sessions.keys()):
            session_info = sessions[name]
            assignment = assignments.get(name, {})
            result.append((name, session_info, assignment))

        return result

    def send_task(self, session: str, task: str) -> bool:
        """Send a task to a session via the assigner."""
        success, msg = assign_task(session, task)
        self.message = msg
        return success

    def format_status_line(self, name: str, info: Dict, assignment: Dict, width: int = 80) -> str:
        """Format a single session status line."""
        status = info.get("status", {})
        state = status.get("state", "unknown")

        # Icon
        icon = STATUS_ICONS.get(state, "❓")

        # State color
        if state == "working" or state == "thinking":
            color = COLORS["green"]
        elif state == "idle":
            color = COLORS["yellow"]
        elif state == "error" or status.get("has_error"):
            color = COLORS["red"]
        else:
            color = COLORS["reset"]

        # Assignment info
        project = assignment.get("project", "")
        env_info = assignment.get("env_info", {})
        if project == "edu_apps":
            env_str = env_info.get("path", "").split("/")[-1] if env_info.get("path") else ""
        elif project == "kanbanflow":
            env_str = env_info.get("branch", "").split("/")[-1] if env_info.get("branch") else ""
        elif project == "architect":
            env_str = env_info.get("scope", "")
        else:
            env_str = ""

        # Activity
        activity = status.get("activity", "")[:30]
        progress = status.get("progress", "")

        # Format line
        name_part = f"{name[:15]:<15}"
        state_part = f"{state[:8]:<8}"
        env_part = f"[{project[:5]}/{env_str[:10]}]" if project else "[unassigned]"
        env_part = f"{env_part:<20}"
        activity_part = activity if activity else ""
        if progress:
            activity_part = f"{progress} {activity_part}"

        line = f"{icon} {color}{name_part}{COLORS['reset']} {state_part} {env_part} {activity_part}"
        return line[:width]

    def run_simple(self):
        """Run simple non-curses interface."""
        print(f"\n{COLORS['bold']}Claude Session Manager{COLORS['reset']}")
        print("=" * 70)
        print("Commands: [r]efresh [a]ssign [d]etail [q]uit")
        print("=" * 70)

        while True:
            self.refresh_data()
            sessions = self.get_session_list()

            # Clear and print status
            print("\033[2J\033[H")  # Clear screen
            print(
                f"{COLORS['bold']}Claude Session Manager{COLORS['reset']} - {datetime.now().strftime('%H:%M:%S')}"
            )
            print("=" * 70)

            if self.message:
                print(f"{COLORS['cyan']}{self.message}{COLORS['reset']}")
                print("-" * 70)

            # Group by project
            by_project = {"architect": [], "edu_apps": [], "kanbanflow": [], "other": []}
            for name, info, assignment in sessions:
                project = assignment.get("project", "other")
                if project not in by_project:
                    project = "other"
                by_project[project].append((name, info, assignment))

            for project, items in by_project.items():
                if not items:
                    continue
                print(f"\n{COLORS['bold']}{project.upper()}{COLORS['reset']}")
                for name, info, assignment in items:
                    print(self.format_status_line(name, info, assignment))

            print("\n" + "=" * 70)
            print("[r]efresh [a]ssign <session> <task> [d]etail <session> [q]uit")

            # Simple input handling
            try:
                cmd = input("> ").strip()
                if cmd == "q" or cmd == "quit":
                    break
                elif cmd == "r" or cmd == "refresh":
                    continue
                elif cmd.startswith("a ") or cmd.startswith("assign "):
                    parts = cmd.split(" ", 2)
                    if len(parts) >= 3:
                        session = parts[1]
                        task = parts[2]
                        success, msg = assign_task(session, task)
                        self.message = msg
                    else:
                        self.message = "Usage: assign <session> <task>"
                elif cmd.startswith("d ") or cmd.startswith("detail "):
                    parts = cmd.split(" ", 1)
                    if len(parts) >= 2:
                        session = parts[1]
                        info = self.monitor.get_session(session)
                        if info:
                            print(f"\n--- {session} ---")
                            print(info.get("output_preview", "No output"))
                            print("---")
                            input("Press Enter to continue...")
                        else:
                            self.message = f"Session '{session}' not found"
                elif cmd.startswith("release "):
                    parts = cmd.split(" ", 1)
                    if len(parts) >= 2:
                        session = parts[1]
                        state = load_state()
                        release_session(session, state)
                        save_state(state)
                        self.message = f"Released {session}"
                elif cmd:
                    self.message = f"Unknown command: {cmd}"
            except EOFError:
                break
            except KeyboardInterrupt:
                break

    def run_curses(self, stdscr):
        """Run curses-based interface."""
        curses.curs_set(0)
        curses.use_default_colors()

        # Initialize colors
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)

        stdscr.timeout(2000)  # Refresh every 2 seconds

        while True:
            self.refresh_data()
            sessions = self.get_session_list()

            stdscr.clear()
            height, width = stdscr.getmaxyx()

            # Header
            header = " Claude Session Manager "
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(0, 0, "=" * width)
            stdscr.addstr(0, (width - len(header)) // 2, header)
            stdscr.attroff(curses.A_BOLD)

            # Time
            time_str = datetime.now().strftime("%H:%M:%S")
            stdscr.addstr(0, width - len(time_str) - 2, time_str)

            # Message line
            if self.message:
                stdscr.attron(curses.color_pair(4))
                stdscr.addstr(1, 0, self.message[: width - 1])
                stdscr.attroff(curses.color_pair(4))

            # Session list
            row = 3
            for idx, (name, info, assignment) in enumerate(sessions):
                if row >= height - 2:
                    break

                status = info.get("status", {})
                state = status.get("state", "unknown")

                # Highlight selected
                if idx == self.selected_idx:
                    stdscr.attron(curses.color_pair(5))

                # Color by state
                if state in ("working", "thinking"):
                    stdscr.attron(curses.color_pair(1))
                elif state == "idle":
                    stdscr.attron(curses.color_pair(2))
                elif state == "error" or status.get("has_error"):
                    stdscr.attron(curses.color_pair(3))

                # Format line
                icon = ">" if idx == self.selected_idx else " "
                project = assignment.get("project", "")[:5]
                env_info = assignment.get("env_info", {})
                env_str = ""
                if project == "edu_a":
                    env_str = (
                        env_info.get("path", "").split("/")[-1][:6] if env_info.get("path") else ""
                    )
                elif project == "kanba":
                    env_str = (
                        env_info.get("branch", "").split("/")[-1][:6]
                        if env_info.get("branch")
                        else ""
                    )
                elif project == "archi":
                    env_str = env_info.get("scope", "")[:6]

                activity = status.get("activity", "")[:25]
                line = f"{icon} {name[:12]:<12} {state[:7]:<7} [{project}/{env_str}]".ljust(45)
                line += activity

                try:
                    stdscr.addstr(row, 0, line[: width - 1])
                except:
                    pass

                # Reset colors
                stdscr.attroff(curses.color_pair(1))
                stdscr.attroff(curses.color_pair(2))
                stdscr.attroff(curses.color_pair(3))
                stdscr.attroff(curses.color_pair(5))

                row += 1

            # Footer
            footer = " [↑↓]Navigate [a]Assign [d]Detail [r]Refresh [q]Quit "
            stdscr.addstr(height - 1, 0, "=" * width)
            stdscr.addstr(height - 1, (width - len(footer)) // 2, footer)

            stdscr.refresh()

            # Handle input
            try:
                key = stdscr.getch()
                if key == ord("q"):
                    break
                elif key == ord("r"):
                    self.message = "Refreshing..."
                elif key == curses.KEY_UP:
                    self.selected_idx = max(0, self.selected_idx - 1)
                elif key == curses.KEY_DOWN:
                    self.selected_idx = min(len(sessions) - 1, self.selected_idx + 1)
                elif key == ord("a"):
                    # Assign mode - drop to simple input
                    curses.endwin()
                    if sessions:
                        session = sessions[self.selected_idx][0]
                        task = input(f"Task for {session}: ").strip()
                        if task:
                            success, msg = assign_task(session, task)
                            self.message = msg
                    stdscr = curses.initscr()
                    curses.curs_set(0)
                elif key == ord("d"):
                    # Detail view
                    if sessions:
                        session = sessions[self.selected_idx][0]
                        info = self.monitor.get_session(session)
                        if info:
                            curses.endwin()
                            print(f"\n--- {session} ---")
                            print(info.get("output_preview", "No output"))
                            print("---")
                            input("Press Enter...")
                            stdscr = curses.initscr()
                            curses.curs_set(0)
            except:
                pass

    def run(self, use_curses: bool = True):
        """Run the manager."""
        if use_curses and sys.stdout.isatty():
            try:
                curses.wrapper(self.run_curses)
            except:
                self.run_simple()
        else:
            self.run_simple()


def daemon_mode():
    """Run as background status monitor."""
    monitor = SessionMonitor()

    print("Claude Manager Daemon started")
    print("Monitoring sessions...")

    while True:
        monitor.update_all()
        sessions = monitor.get_all_sessions()

        # Log status
        timestamp = datetime.now().strftime("%H:%M:%S")
        working = sum(
            1
            for s in sessions.values()
            if s.get("status", {}).get("state") in ("working", "thinking")
        )
        idle = sum(1 for s in sessions.values() if s.get("status", {}).get("state") == "idle")

        print(f"[{timestamp}] Sessions: {len(sessions)} total, {working} working, {idle} idle")

        time.sleep(30)


def main():
    if "--daemon" in sys.argv:
        daemon_mode()
    elif "--simple" in sys.argv:
        manager = ClaudeManager()
        manager.run(use_curses=False)
    else:
        manager = ClaudeManager()
        manager.run(use_curses=True)


if __name__ == "__main__":
    main()
