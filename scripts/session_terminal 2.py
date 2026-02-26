#!/usr/bin/env python3
"""
Session Terminal - Interactive CLI for the Architect Assigner System

Provides an interactive prompt where:
- Messages starting with 'os:' get routed to the assigner worker
- Shows real-time updates from assigned sessions
- Displays which session is handling which task

Usage:
    python3 session_terminal.py               # Interactive mode
    python3 session_terminal.py --watch       # Watch mode (status updates only)
    python3 session_terminal.py --send "msg"  # Send a single message
"""

import argparse
import json
import os
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Setup paths
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from workers.assigner_worker import (
    SUPPORTED_PROVIDERS,
    AssignerDatabase,
    PromptStatus,
    SessionDetector,
)


# ANSI Colors
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def colored(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{Colors.RESET}"


def clear_line():
    """Clear current line."""
    print("\r\033[K", end="")


def move_cursor_up(n: int = 1):
    """Move cursor up n lines."""
    print(f"\033[{n}A", end="")


class SessionTerminal:
    """Interactive terminal for the assigner system."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.running = False
        self.db = AssignerDatabase()
        self.detector = SessionDetector()

        self._last_prompts: Dict[int, Dict] = {}
        self._watch_thread: Optional[threading.Thread] = None

    def print_header(self):
        """Print the terminal header."""
        print(colored("\n" + "=" * 60, Colors.BLUE))
        print(colored("  Architect Session Terminal", Colors.BOLD + Colors.CYAN))
        print(colored("  Type 'os: <message>' to send to available sessions", Colors.DIM))
        print(colored("  Type 'help' for more commands", Colors.DIM))
        print(colored("=" * 60 + "\n", Colors.BLUE))

    def print_help(self):
        """Print help information."""
        help_text = """
Commands:
  os: <message>               Send message to next available session
  os:<n>: <message>           Send message with priority n (higher = more urgent)
  os:<provider>: <message>    Target a provider (claude, codex, ollama)
  os:<provider>:<n>: <message> Target provider + priority

  status            Show queue and session status
  sessions          List all tmux sessions with their status
  prompts           Show recent prompts
  watch             Watch for updates (Ctrl+C to stop)

  clear             Clear the screen
  help              Show this help
  quit/exit         Exit the terminal

Examples:
  os: Fix the bug in app.py line 42
  os:5: URGENT - Server is down, investigate immediately
  os: Refactor the login function to use async/await
"""
        print(colored(help_text, Colors.WHITE))

    def print_status(self):
        """Print current status."""
        stats = self.db.get_stats()

        print(colored("\n--- Queue Status ---", Colors.BOLD + Colors.CYAN))
        print(f"  Pending:    {colored(str(stats['pending_prompts']), Colors.YELLOW)}")
        print(f"  Active:     {colored(str(stats['active_assignments']), Colors.BLUE)}")
        print(f"  Completed:  {colored(str(stats['completed_prompts']), Colors.GREEN)}")
        print(f"  Failed:     {colored(str(stats['failed_prompts']), Colors.RED)}")

        print(colored("\n--- Sessions ---", Colors.BOLD + Colors.CYAN))
        print(f"  Available:  {colored(str(stats['available_sessions']), Colors.GREEN)}")
        print(f"  Busy:       {colored(str(stats['busy_sessions']), Colors.YELLOW)}")
        print(f"  Total:      {stats['total_sessions']}")

        # Show active assignments
        active = self.db.get_active_assignments()
        if active:
            print(colored("\n--- Active Assignments ---", Colors.BOLD + Colors.CYAN))
            for a in active:
                session = a.get("assigned_session", "N/A")
                content = a["content"][:50] + "..." if len(a["content"]) > 50 else a["content"]
                content = content.replace("\n", " ")
                status_color = Colors.BLUE if a["status"] == "assigned" else Colors.YELLOW
                print(
                    f"  [{colored(a['status'], status_color)}] {colored(session, Colors.CYAN)}: {content}"
                )

        print()

    def print_sessions(self):
        """Print all tracked sessions."""
        sessions = self.db.get_all_sessions()

        if not sessions:
            # Scan for sessions if none tracked
            print(colored("Scanning sessions...", Colors.DIM))
            detected = self.detector.scan_all_sessions()
            for s in detected:
                self.db.update_session(
                    name=s.name,
                    status=s.status,
                    is_claude=s.is_claude,
                    working_dir=s.working_dir,
                    provider=s.provider,
                )
            sessions = self.db.get_all_sessions()

        print(colored("\n--- tmux Sessions ---", Colors.BOLD + Colors.CYAN))
        print(
            f"{'Session':<20} {'Status':<12} {'Provider':<10} {'Claude':<8} {'Task':<8} {'Working Dir'}"
        )
        print("-" * 95)

        for s in sessions:
            status = s["status"]
            if status == "idle" or status == "waiting_input":
                status_color = Colors.GREEN
            elif status == "busy":
                status_color = Colors.YELLOW
            else:
                status_color = Colors.DIM

            provider = s.get("provider") or ("claude" if s.get("is_claude") else "unknown")
            is_claude = (
                colored("Yes", Colors.GREEN) if s["is_claude"] else colored("No", Colors.DIM)
            )
            task = s.get("current_task_id") or "-"
            working_dir = s.get("working_dir", "-")
            if working_dir and len(working_dir) > 30:
                working_dir = "..." + working_dir[-27:]

            print(
                f"{s['name']:<20} {colored(status, status_color):<21} {provider:<10} {is_claude:<17} {str(task):<8} {working_dir}"
            )

        print()

    def print_prompts(self, limit: int = 10):
        """Print recent prompts."""
        with self.db._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompts ORDER BY created_at DESC LIMIT ?
            """,
                (limit,),
            ).fetchall()

        print(colored("\n--- Recent Prompts ---", Colors.BOLD + Colors.CYAN))
        print(f"{'ID':<6} {'Status':<12} {'Session':<15} {'Time':<12} {'Content'}")
        print("-" * 90)

        for r in rows:
            status = r["status"]
            if status == "completed":
                status_color = Colors.GREEN
            elif status == "failed":
                status_color = Colors.RED
            elif status in ("assigned", "in_progress"):
                status_color = Colors.YELLOW
            else:
                status_color = Colors.DIM

            content = r["content"][:35] + "..." if len(r["content"]) > 35 else r["content"]
            content = content.replace("\n", " ")
            session = r["assigned_session"] or "-"
            time_str = r["created_at"][11:19] if r["created_at"] else "-"

            print(
                f"{r['id']:<6} {colored(status, status_color):<21} {session:<15} {time_str:<12} {content}"
            )

        print()

    def send_prompt(self, message: str, priority: int = 0, provider: Optional[str] = None) -> int:
        """Send a prompt to the queue."""
        if provider and provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        prompt_id = self.db.add_prompt(
            content=message, source="terminal", priority=priority, target_provider=provider
        )
        return prompt_id

    def watch_updates(self):
        """Watch for updates in real-time."""
        print(colored("\nWatching for updates (Ctrl+C to stop)...\n", Colors.DIM))

        last_prompt_count = 0
        last_check = {}

        try:
            while self.running:
                # Check for new prompts
                with self.db._get_conn() as conn:
                    rows = conn.execute(
                        """
                        SELECT * FROM prompts
                        WHERE status IN ('assigned', 'in_progress', 'completed', 'failed')
                        ORDER BY id DESC LIMIT 10
                    """
                    ).fetchall()

                for r in rows:
                    prompt_id = r["id"]
                    status = r["status"]

                    # Check if status changed
                    if prompt_id in last_check and last_check[prompt_id] == status:
                        continue

                    last_check[prompt_id] = status

                    # Print update
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    content = r["content"][:40] + "..." if len(r["content"]) > 40 else r["content"]
                    content = content.replace("\n", " ")

                    if status == "assigned":
                        color = Colors.BLUE
                        msg = f"Assigned to {r['assigned_session']}"
                    elif status == "in_progress":
                        color = Colors.YELLOW
                        msg = f"In progress on {r['assigned_session']}"
                    elif status == "completed":
                        color = Colors.GREEN
                        msg = f"Completed on {r['assigned_session']}"
                    elif status == "failed":
                        color = Colors.RED
                        msg = f"Failed: {r.get('error', 'Unknown error')[:30]}"
                    else:
                        continue

                    print(
                        f"[{timestamp}] {colored(f'Prompt #{prompt_id}', Colors.BOLD)}: {colored(msg, color)}"
                    )
                    print(f"           {colored(content, Colors.DIM)}")

                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            print(colored("\n\nStopped watching.", Colors.DIM))

    def parse_command(self, line: str) -> tuple[str, Optional[str], int, Optional[str]]:
        """
        Parse a command line.

        Returns: (command, argument, priority, provider)
        """
        line = line.strip()

        if not line:
            return ("", None, 0, None)

        # Check for os: prefix
        if line.lower().startswith("os:"):
            rest = line[3:].strip()
            provider = None

            for candidate in SUPPORTED_PROVIDERS:
                prefix = f"{candidate}:"
                if rest.lower().startswith(prefix):
                    provider = candidate
                    rest = rest[len(prefix) :].strip()
                    break

            # Check for priority: os:5: message
            if rest and rest[0].isdigit():
                parts = rest.split(":", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    priority = int(parts[0])
                    message = parts[1].strip()
                    return ("send", message, priority, provider)

            # Normal os: message
            return ("send", rest, 0, provider)

        # Other commands
        parts = line.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        return (cmd, arg, 0, None)

    def run_interactive(self):
        """Run in interactive mode."""
        self.running = True
        self.print_header()

        # Start background watcher thread
        self._watch_thread = threading.Thread(target=self._background_watcher, daemon=True)
        self._watch_thread.start()

        try:
            while self.running:
                try:
                    line = input(colored("> ", Colors.GREEN + Colors.BOLD))
                except EOFError:
                    break

                cmd, arg, priority, provider = self.parse_command(line)

                if cmd == "":
                    continue
                elif cmd == "send":
                    if not arg:
                        print(colored("Error: No message provided", Colors.RED))
                        continue

                    try:
                        prompt_id = self.send_prompt(arg, priority, provider=provider)
                    except ValueError as e:
                        print(colored(f"Error: {e}", Colors.RED))
                        continue

                    if priority > 0:
                        print(
                            colored(
                                f"Queued prompt #{prompt_id} with priority {priority}", Colors.GREEN
                            )
                        )
                    else:
                        print(colored(f"Queued prompt #{prompt_id}", Colors.GREEN))

                elif cmd == "status":
                    self.print_status()
                elif cmd == "sessions":
                    self.print_sessions()
                elif cmd == "prompts":
                    self.print_prompts()
                elif cmd == "watch":
                    self.watch_updates()
                elif cmd == "clear":
                    os.system("clear" if os.name == "posix" else "cls")
                    self.print_header()
                elif cmd == "help":
                    self.print_help()
                elif cmd in ("quit", "exit", "q"):
                    break
                else:
                    print(
                        colored(f"Unknown command: {cmd}. Type 'help' for commands.", Colors.YELLOW)
                    )

        except KeyboardInterrupt:
            print()

        self.running = False
        print(colored("\nGoodbye!", Colors.CYAN))

    def _background_watcher(self):
        """Background thread to check for prompt completions."""
        notified = set()

        while self.running:
            try:
                # Check for recently completed prompts
                with self.db._get_conn() as conn:
                    rows = conn.execute(
                        """
                        SELECT * FROM prompts
                        WHERE status = 'completed'
                          AND completed_at > datetime('now', '-5 minutes')
                        ORDER BY completed_at DESC
                    """
                    ).fetchall()

                for r in rows:
                    if r["id"] not in notified:
                        notified.add(r["id"])
                        # Print notification (might interrupt user input, but that's OK)
                        content = (
                            r["content"][:30] + "..." if len(r["content"]) > 30 else r["content"]
                        )
                        content = content.replace("\n", " ")
                        print(
                            f"\n{colored('[Completed]', Colors.GREEN + Colors.BOLD)} "
                            f"Prompt #{r['id']} on {r['assigned_session']}: {content}"
                        )
                        print(colored("> ", Colors.GREEN + Colors.BOLD), end="", flush=True)

            except Exception:
                pass

            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Session Terminal")
    parser.add_argument("--watch", action="store_true", help="Watch mode only")
    parser.add_argument("--send", metavar="MESSAGE", help="Send a single message and exit")
    parser.add_argument("--priority", "-p", type=int, default=0, help="Priority for --send")
    parser.add_argument(
        "--provider", metavar="PROVIDER", help="Target provider (claude, codex, ollama)"
    )
    parser.add_argument("--status", "-s", action="store_true", help="Show status and exit")
    parser.add_argument("--sessions", action="store_true", help="List sessions and exit")
    parser.add_argument(
        "--poll-interval", type=float, default=2.0, help="Poll interval for watch mode"
    )

    args = parser.parse_args()

    terminal = SessionTerminal(poll_interval=args.poll_interval)

    if args.send:
        try:
            prompt_id = terminal.send_prompt(args.send, args.priority, provider=args.provider)
        except ValueError as e:
            print(f"Error: {e}")
            return
        print(f"Queued prompt #{prompt_id}")
    elif args.status:
        terminal.print_status()
    elif args.sessions:
        terminal.print_sessions()
    elif args.watch:
        terminal.running = True
        terminal.watch_updates()
    else:
        terminal.run_interactive()


if __name__ == "__main__":
    main()
