#!/usr/bin/env python3
"""
Session Watchdog - Monitor and keepalive for Claude sessions

Monitors the main architect session and sends keepalive prompts
if it becomes idle for too long. Coordinates with orchestrator session.
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

CHECK_INTERVAL = 180  # 3 minutes
IDLE_THRESHOLD = 300  # 5 minutes of idle triggers action

MONITORED_SESSION = "architect"
ORCHESTRATOR_SESSION = "claude_orchestrator"


def get_session_status(session_name):
    """Get status of a tmux session"""
    try:
        cmd = f"tmux capture-pane -t {session_name} -p"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            return {"exists": False}

        output = result.stdout
        last_line = output.strip().split("\n")[-1] if output else ""

        # Check if idle
        idle_indicators = ["❯", ">", "$", "#", "How can I help"]
        is_idle = any(indicator in output for indicator in idle_indicators)

        # Check if busy
        busy_indicators = ["Thinking", "Analyzing", "Processing", "Running", "…"]
        is_busy = any(indicator in output for indicator in busy_indicators)

        return {
            "exists": True,
            "is_idle": is_idle and not is_busy,
            "is_busy": is_busy,
            "last_line": last_line[:100],
            "output_length": len(output),
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


def send_keepalive_prompt(session_name):
    """Send a status check prompt to the session"""
    prompt = "Quick status check - what are you currently working on? Provide a brief summary."

    try:
        # Send prompt
        cmd = f'tmux send-keys -t {session_name} "{prompt}"'
        subprocess.run(cmd, shell=True, timeout=5)

        # Send Enter
        cmd = f"tmux send-keys -t {session_name} Enter"
        subprocess.run(cmd, shell=True, timeout=5)

        return True
    except Exception as e:
        print(f"Failed to send keepalive: {e}")
        return False


def notify_orchestrator(message):
    """Send notification to orchestrator session"""
    try:
        cmd = f'tmux send-keys -t {ORCHESTRATOR_SESSION} "{message}"'
        subprocess.run(cmd, shell=True, timeout=5)
        cmd = f"tmux send-keys -t {ORCHESTRATOR_SESSION} Enter"
        subprocess.run(cmd, shell=True, timeout=5)
        return True
    except:
        return False


def main():
    print(f"Session Watchdog started")
    print(f"Monitoring: {MONITORED_SESSION}")
    print(f"Orchestrator: {ORCHESTRATOR_SESSION}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print()

    idle_count = 0
    last_check = datetime.now()

    while True:
        try:
            time.sleep(CHECK_INTERVAL)

            # Check monitored session
            status = get_session_status(MONITORED_SESSION)

            if not status["exists"]:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Session {MONITORED_SESSION} not found"
                )
                idle_count = 0
                continue

            # Check orchestrator session
            orch_status = get_session_status(ORCHESTRATOR_SESSION)

            timestamp = datetime.now().strftime("%H:%M:%S")

            if status["is_idle"]:
                idle_count += 1
                print(f"[{timestamp}] {MONITORED_SESSION} is IDLE ({idle_count * CHECK_INTERVAL}s)")

                # After 5 minutes of idle, notify orchestrator
                if idle_count * CHECK_INTERVAL >= IDLE_THRESHOLD:
                    print(f"[{timestamp}] Triggering keepalive...")

                    # Notify orchestrator
                    if orch_status["exists"]:
                        msg = f"Architect session idle for {idle_count * CHECK_INTERVAL}s. Check status and send prompts if needed."
                        notify_orchestrator(msg)
                        print(f"[{timestamp}] Notified orchestrator")

                    # Reset counter
                    idle_count = 0

            elif status["is_busy"]:
                if idle_count > 0:
                    print(
                        f"[{timestamp}] {MONITORED_SESSION} is BUSY (was idle for {idle_count * CHECK_INTERVAL}s)"
                    )
                idle_count = 0

            else:
                print(f"[{timestamp}] {MONITORED_SESSION} status unclear")
                idle_count = 0

        except KeyboardInterrupt:
            print("\nWatchdog stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
