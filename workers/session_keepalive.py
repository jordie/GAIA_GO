#!/usr/bin/env python3
"""
Session Keep-Alive Worker

Keeps tmux sessions alive by:
- Monitoring session idle time
- Sending periodic keep-alive signals
- Preventing session timeouts
- Detecting and reviving stuck sessions

Usage:
    python3 session_keepalive.py                # Run in foreground
    python3 session_keepalive.py --daemon       # Run as daemon
    python3 session_keepalive.py --stop         # Stop daemon
    python3 session_keepalive.py --status       # Check status
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent

# Worker configuration
PID_FILE = Path("/tmp/architect_session_keepalive.pid")
STATE_FILE = Path("/tmp/architect_session_keepalive_state.json")
LOG_FILE = Path("/tmp/architect_session_keepalive.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("SessionKeepAlive")


class SessionKeepAlive:
    """Session keep-alive manager."""

    def __init__(
        self,
        check_interval: int = 300,  # Check every 5 minutes
        idle_threshold: int = 1800,  # Send keep-alive after 30 min idle
        keepalive_method: str = "space",  # space, enter, or heartbeat
    ):
        self.running = False
        self.check_interval = check_interval
        self.idle_threshold = idle_threshold
        self.keepalive_method = keepalive_method
        self.session_state = {}

    def get_sessions(self) -> List[str]:
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
            logger.error(f"Error listing sessions: {e}")
            return []

    def get_session_activity(self, session: str) -> Optional[datetime]:
        """Get last activity time for a session."""
        try:
            # Get session activity time from tmux
            result = subprocess.run(
                ["tmux", "display-message", "-t", session, "-p", "#{session_activity}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                # session_activity is Unix timestamp
                timestamp = int(result.stdout.strip())
                return datetime.fromtimestamp(timestamp)
            return None
        except Exception as e:
            logger.debug(f"Error getting activity for {session}: {e}")
            return None

    def get_session_output(self, session: str, lines: int = 10) -> str:
        """Capture session output."""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                output_lines = result.stdout.strip().split("\n")
                return "\n".join(output_lines[-lines:])
            return ""
        except Exception as e:
            logger.debug(f"Error capturing output for {session}: {e}")
            return ""

    def is_session_idle(self, session: str) -> bool:
        """Check if session is idle."""
        last_activity = self.get_session_activity(session)
        if not last_activity:
            return False

        idle_time = (datetime.now() - last_activity).total_seconds()
        return idle_time > self.idle_threshold

    def send_keepalive(self, session: str):
        """Send keep-alive signal to session."""
        try:
            if self.keepalive_method == "space":
                # Send space then backspace (no visible effect)
                subprocess.run(
                    ["tmux", "send-keys", "-t", session, "Space", "BSpace"],
                    timeout=2,
                    capture_output=True,
                )
                logger.info(f"Sent space+backspace keep-alive to {session}")

            elif self.keepalive_method == "enter":
                # Just send Enter (might submit prompts)
                subprocess.run(
                    ["tmux", "send-keys", "-t", session, "Enter"], timeout=2, capture_output=True
                )
                logger.info(f"Sent Enter keep-alive to {session}")

            elif self.keepalive_method == "heartbeat":
                # Send invisible control character
                subprocess.run(
                    ["tmux", "send-keys", "-t", session, "C-["], timeout=2, capture_output=True
                )
                logger.info(f"Sent heartbeat to {session}")

            # Update state
            self.session_state[session] = {
                "last_keepalive": datetime.now().isoformat(),
                "keepalive_count": self.session_state.get(session, {}).get("keepalive_count", 0)
                + 1,
            }

        except Exception as e:
            logger.error(f"Error sending keep-alive to {session}: {e}")

    def check_session_health(self, session: str) -> Dict:
        """Check if session is healthy."""
        output = self.get_session_output(session, lines=5)

        health = {"session": session, "healthy": True, "issues": []}

        # Check for stuck indicators
        stuck_patterns = [
            "not responding",
            "timeout",
            "connection lost",
            "failed to connect",
            "error",
        ]

        for pattern in stuck_patterns:
            if pattern.lower() in output.lower():
                health["healthy"] = False
                health["issues"].append(f"Detected: {pattern}")

        # Check for idle prompt
        idle_patterns = ["> ", "$ ", "# ", "How can I help"]
        has_prompt = any(p in output for p in idle_patterns)

        if has_prompt:
            health["status"] = "idle"
        else:
            health["status"] = "active"

        return health

    def process_session(self, session: str):
        """Process a single session."""
        try:
            # Skip certain sessions
            skip_patterns = ["architect:", "comet:"]
            if any(pattern in session for pattern in skip_patterns):
                logger.debug(f"Skipping {session} (excluded pattern)")
                return

            # Check if session is idle
            if self.is_session_idle(session):
                logger.info(f"Session {session} is idle (>{self.idle_threshold}s)")

                # Check health
                health = self.check_session_health(session)

                if not health["healthy"]:
                    logger.warning(f"Session {session} has issues: {health['issues']}")
                    # Don't send keep-alive to unhealthy sessions
                    return

                # Send keep-alive
                self.send_keepalive(session)
            else:
                logger.debug(f"Session {session} is active")

        except Exception as e:
            logger.error(f"Error processing {session}: {e}")

    def run_cycle(self):
        """Run one keep-alive cycle."""
        logger.info("Starting keep-alive cycle")

        sessions = self.get_sessions()
        logger.info(f"Found {len(sessions)} sessions")

        for session in sessions:
            self.process_session(session)

        # Save state
        self.save_state()

        logger.info("Keep-alive cycle complete")

    def run(self):
        """Main worker loop."""
        logger.info("Session Keep-Alive Worker started")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Idle threshold: {self.idle_threshold}s")
        logger.info(f"Keep-alive method: {self.keepalive_method}")

        self.running = True

        while self.running:
            try:
                self.run_cycle()

                # Sleep until next check
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(60)  # Wait before retrying

        logger.info("Session Keep-Alive Worker stopped")

    def save_state(self):
        """Save worker state."""
        try:
            state = {
                "last_check": datetime.now().isoformat(),
                "running": self.running,
                "sessions": self.session_state,
            }
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def stop(self):
        """Stop the worker."""
        logger.info("Stopping worker")
        self.running = False


def start_daemon():
    """Start worker as daemon."""
    if PID_FILE.exists():
        print("❌ Worker already running")
        return

    pid = os.fork()
    if pid > 0:
        # Parent process
        PID_FILE.write_text(str(pid))
        print(f"✅ Started daemon (PID: {pid})")
        print(f"📝 Logs: {LOG_FILE}")
        sys.exit(0)

    # Child process - become session leader
    os.setsid()

    # Fork again to prevent zombie
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as f:
        os.dup2(f.fileno(), sys.stdin.fileno())

    # Run worker
    worker = SessionKeepAlive()
    worker.run()


def stop_daemon():
    """Stop daemon worker."""
    if not PID_FILE.exists():
        print("❌ Worker not running")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        print(f"✅ Stopped daemon (PID: {pid})")
    except Exception as e:
        print(f"❌ Error stopping daemon: {e}")
        if PID_FILE.exists():
            PID_FILE.unlink()


def check_status():
    """Check daemon status."""
    if not PID_FILE.exists():
        print("⚪ Worker not running")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Check if process exists

        # Read state
        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
            print(f"🟢 Worker running (PID: {pid})")
            print(f"   Last check: {state.get('last_check', 'Unknown')}")

            sessions = state.get("sessions", {})
            if sessions:
                print(f"   Sessions monitored: {len(sessions)}")
                total_keepalives = sum(s.get("keepalive_count", 0) for s in sessions.values())
                print(f"   Total keep-alives sent: {total_keepalives}")
        else:
            print(f"🟡 Worker running (PID: {pid}) - no state file")

    except ProcessLookupError:
        print(f"🔴 Worker not running (stale PID file)")
        PID_FILE.unlink()
    except Exception as e:
        print(f"❌ Error checking status: {e}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Session Keep-Alive Worker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Check status")
    parser.add_argument("--interval", type=int, default=300, help="Check interval (seconds)")
    parser.add_argument("--idle-threshold", type=int, default=1800, help="Idle threshold (seconds)")
    parser.add_argument(
        "--method",
        choices=["space", "enter", "heartbeat"],
        default="space",
        help="Keep-alive method",
    )

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        check_status()
    elif args.daemon:
        start_daemon()
    else:
        # Run in foreground
        worker = SessionKeepAlive(
            check_interval=args.interval,
            idle_threshold=args.idle_threshold,
            keepalive_method=args.method,
        )

        # Handle signals
        def signal_handler(sig, frame):
            worker.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        worker.run()


if __name__ == "__main__":
    main()
