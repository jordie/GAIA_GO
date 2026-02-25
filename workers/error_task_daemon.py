#!/usr/bin/env python3
"""
Error Task Daemon - Automatically sends unresolved errors to Claude wrapper session.

This daemon:
1. Monitors errors.md for unresolved errors (marked with [ ])
2. Sends error-fixing tasks to the wrapper_claude tmux session
3. Waits between tasks (default 60 seconds)
4. Runs continuously in the background

Usage:
    ./error_task_daemon.py start     # Start the daemon
    ./error_task_daemon.py stop      # Stop the daemon
    ./error_task_daemon.py status    # Check daemon status
    ./error_task_daemon.py run       # Run in foreground (for testing)
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
SCRIPT_DIR = Path(__file__).parent
ERRORS_FILE = SCRIPT_DIR / "errors.md"
PID_FILE = Path("/tmp/error_task_daemon.pid")
STATE_FILE = Path("/tmp/error_task_daemon_state.json")
LOG_FILE = SCRIPT_DIR / "error_task_daemon.log"

TMUX_SESSION = os.environ.get("ERROR_DAEMON_SESSION", "error_fixer")
TASK_INTERVAL = 60  # seconds between tasks
MAX_ERRORS_PER_RUN = 5  # Max errors to process before pausing


class ErrorTaskDaemon:
    def __init__(self):
        self.running = False
        self.current_error = None
        self.processed_errors = set()
        self.load_state()

    def load_state(self):
        """Load daemon state from file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    self.processed_errors = set(state.get("processed_errors", []))
            except Exception as e:
                self.log(f"Error loading state: {e}")

    def save_state(self):
        """Save daemon state to file."""
        try:
            state = {
                "processed_errors": list(self.processed_errors),
                "last_update": datetime.now().isoformat(),
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.log(f"Error saving state: {e}")

    def log(self, message: str):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        try:
            with open(LOG_FILE, "a") as f:
                f.write(log_msg + "\n")
        except:
            pass

    def parse_errors(self) -> List[Dict]:
        """Parse errors.md and return unresolved errors."""
        if not ERRORS_FILE.exists():
            return []

        errors = []
        try:
            with open(ERRORS_FILE, "r") as f:
                content = f.read()

            # Find unresolved errors (marked with [ ])
            # Format: ### [ ] Error Title
            pattern = r"### \[ \] (.+?)(?=\n### |\n## |\Z)"
            matches = re.findall(pattern, content, re.DOTALL)

            for i, match in enumerate(matches):
                lines = match.strip().split("\n")
                title = lines[0].strip() if lines else "Unknown Error"

                # Extract metadata
                error_data = {
                    "id": hash(title) & 0xFFFFFFFF,  # Simple hash for tracking
                    "title": title,
                    "full_text": match.strip(),
                    "type": "Unknown",
                    "priority": "MEDIUM",
                    "app": "unknown",
                }

                # Parse metadata lines
                for line in lines[1:10]:
                    if line.startswith("**Type:**"):
                        parts = line.split("|")
                        if parts:
                            error_data["type"] = parts[0].replace("**Type:**", "").strip()
                            for part in parts:
                                if "Priority:" in part:
                                    error_data["priority"] = (
                                        part.split(":")[1].strip().replace("**", "")
                                    )
                                if "App:" in part:
                                    error_data["app"] = part.split(":")[1].strip().replace("**", "")
                    elif line.startswith("**Source File:**"):
                        error_data["source_file"] = line.replace("**Source File:**", "").strip()
                    elif line.startswith("**Message:**"):
                        error_data["message"] = line.replace("**Message:**", "").strip()

                errors.append(error_data)

        except Exception as e:
            self.log(f"Error parsing errors.md: {e}")

        return errors

    def check_tmux_session(self) -> bool:
        """Check if the tmux session exists and is available."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", TMUX_SESSION], capture_output=True
            )
            return result.returncode == 0
        except:
            return False

    def send_task_to_claude(self, error: Dict) -> bool:
        """Send an error-fixing task to the Claude session."""
        if not self.check_tmux_session():
            self.log(f"Tmux session '{TMUX_SESSION}' not found")
            return False

        # Craft the task message
        task = f"""Fix this error from errors.md:

**Title:** {error['title']}
**Type:** {error['type']}
**Priority:** {error['priority']}
**App:** {error['app']}

{error['full_text'][:500]}

Please investigate and fix this error. When done, mark it as resolved in errors.md by changing [ ] to [X]."""

        # Escape special characters for tmux
        task_escaped = task.replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")

        try:
            # Send the task to tmux
            # First, clear any existing input
            subprocess.run(["tmux", "send-keys", "-t", TMUX_SESSION, "C-c"], capture_output=True)
            time.sleep(0.5)

            # Send the task text
            subprocess.run(
                ["tmux", "send-keys", "-t", TMUX_SESSION, task_escaped],
                capture_output=True,
                check=True,
            )
            time.sleep(0.2)

            # Press Enter to submit
            subprocess.run(
                ["tmux", "send-keys", "-t", TMUX_SESSION, "Enter"], capture_output=True, check=True
            )

            self.log(f"Sent task: {error['title'][:50]}...")
            return True

        except subprocess.CalledProcessError as e:
            self.log(f"Failed to send task: {e}")
            return False
        except Exception as e:
            self.log(f"Error sending task: {e}")
            return False

    def run_once(self) -> int:
        """Process one batch of errors. Returns number processed."""
        errors = self.parse_errors()

        # Filter out already processed errors
        new_errors = [e for e in errors if e["id"] not in self.processed_errors]

        if not new_errors:
            self.log("No new unresolved errors found")
            return 0

        # Sort by priority (HIGH first)
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        new_errors.sort(key=lambda e: priority_order.get(e["priority"], 1))

        processed = 0
        for error in new_errors[:MAX_ERRORS_PER_RUN]:
            self.log(f"Processing error: {error['title'][:60]}...")

            if self.send_task_to_claude(error):
                self.processed_errors.add(error["id"])
                self.save_state()
                processed += 1

                # Wait between tasks
                if processed < len(new_errors):
                    self.log(f"Waiting {TASK_INTERVAL} seconds before next task...")
                    time.sleep(TASK_INTERVAL)
            else:
                self.log(f"Failed to send task, will retry later")
                break

        return processed

    def run_daemon(self):
        """Run the daemon loop."""
        self.running = True
        self.log("Error Task Daemon started")

        # Handle signals
        def handle_signal(signum, frame):
            self.log("Received shutdown signal")
            self.running = False

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        while self.running:
            try:
                # Check if tmux session is available
                if not self.check_tmux_session():
                    self.log(f"Waiting for tmux session '{TMUX_SESSION}'...")
                    time.sleep(30)
                    continue

                # Process errors
                processed = self.run_once()

                if processed > 0:
                    self.log(f"Processed {processed} error(s)")

                # Wait before checking again
                # Longer wait if no errors, shorter if we processed some
                wait_time = TASK_INTERVAL if processed == 0 else TASK_INTERVAL * 2

                for _ in range(wait_time):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                self.log(f"Daemon error: {e}")
                time.sleep(30)

        self.log("Error Task Daemon stopped")
        self.save_state()


def start_daemon():
    """Start the daemon as a background process."""
    if PID_FILE.exists():
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            print(f"Daemon already running (PID {pid})")
            return 1
        except OSError:
            pass  # Process not running, clean up

    # Fork to background
    pid = os.fork()
    if pid > 0:
        # Parent process
        print(f"Started error task daemon (PID {pid})")
        return 0

    # Child process - become daemon
    os.setsid()

    # Fork again
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    # Daemon process
    os.chdir("/")
    os.umask(0)

    # Write PID file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    log_file = open(LOG_FILE, "a")
    os.dup2(log_file.fileno(), sys.stdout.fileno())
    os.dup2(log_file.fileno(), sys.stderr.fileno())

    # Run daemon
    daemon = ErrorTaskDaemon()
    daemon.run_daemon()

    # Cleanup
    if PID_FILE.exists():
        PID_FILE.unlink()

    return 0


def stop_daemon():
    """Stop the running daemon."""
    if not PID_FILE.exists():
        print("Daemon not running")
        return 1

    with open(PID_FILE, "r") as f:
        pid = int(f.read().strip())

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped daemon (PID {pid})")
        time.sleep(1)
    except OSError as e:
        print(f"Error stopping daemon: {e}")

    # Clean up PID file
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except:
        pass

    return 0


def daemon_status():
    """Check daemon status."""
    if not PID_FILE.exists():
        print("Daemon not running")
        return 1

    with open(PID_FILE, "r") as f:
        pid = int(f.read().strip())

    try:
        os.kill(pid, 0)
        print(f"Daemon running (PID {pid})")

        # Show state
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            print(f"Processed errors: {len(state.get('processed_errors', []))}")
            print(f"Last update: {state.get('last_update', 'Unknown')}")

        return 0
    except OSError:
        print("Daemon not running (stale PID file)")
        PID_FILE.unlink()
        return 1


def run_foreground():
    """Run daemon in foreground for testing."""
    print("Running in foreground (Ctrl+C to stop)")
    daemon = ErrorTaskDaemon()
    daemon.run_daemon()
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1].lower()

    if command == "start":
        return start_daemon()
    elif command == "stop":
        return stop_daemon()
    elif command == "status":
        return daemon_status()
    elif command == "run":
        return run_foreground()
    elif command == "reset":
        # Reset processed errors state
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            print("State reset")
        return 0
    else:
        print(f"Unknown command: {command}")
        print("Commands: start, stop, status, run, reset")
        return 1


if __name__ == "__main__":
    sys.exit(main())
