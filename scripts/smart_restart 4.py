#!/usr/bin/env python3
"""
Smart Session Restart - Auto-restart sessions at low context with state preservation
"""
import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data/assigner/assigner.db"
STATE_DIR = Path(__file__).parent.parent / "data/session_states"
STATE_DIR.mkdir(exist_ok=True)

CONTEXT_THRESHOLD = 10  # Restart at 10% context remaining
SESSIONS_TO_MONITOR = ["claude_comet", "codex", "dev_worker1", "dev_worker2"]


def get_session_output(session_name):
    """Get last 100 lines from tmux session"""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-100"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout if result.returncode == 0 else ""
    except:
        return ""


def detect_context_level(output):
    """Extract context percentage from session output"""
    # Look for patterns like "Context left: 4%" or "Context remaining: 10%"
    for line in output.split("\n")[-20:]:
        if "Context" in line and "%" in line:
            # Extract percentage
            parts = line.split("%")[0].split()
            try:
                percentage = int(parts[-1])
                return percentage
            except:
                continue
    return None


def save_session_state(session_name, output):
    """Save current session state before restart"""
    state = {
        "session": session_name,
        "timestamp": datetime.now().isoformat(),
        "last_output": output[-2000:],  # Last 2000 chars
        "restart_reason": "low_context",
    }

    state_file = STATE_DIR / f"{session_name}_state.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    print(f"💾 Saved state for {session_name}")
    return state_file


def restart_session(session_name):
    """Restart a tmux session"""
    print(f"🔄 Restarting {session_name}...")

    # Get current output
    output = get_session_output(session_name)

    # Save state
    state_file = save_session_state(session_name, output)

    # Send Ctrl+C to interrupt current task
    subprocess.run(["tmux", "send-keys", "-t", session_name, "C-c"])
    time.sleep(1)

    # Clear screen
    subprocess.run(["tmux", "send-keys", "-t", session_name, "clear", "Enter"])
    time.sleep(0.5)

    # Send a simple prompt to reset context
    timestamp = datetime.now().strftime("%H:%M:%S")
    subprocess.run(
        [
            "tmux",
            "send-keys",
            "-t",
            session_name,
            f'echo "Session restarted at {timestamp} - context refreshed"',
            "Enter",
        ]
    )

    # Update database
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("UPDATE sessions SET status = 'idle' WHERE name = ?", (session_name,))
    conn.commit()
    conn.close()

    print(f"✅ {session_name} restarted - state saved to {state_file}")


def check_and_restart_if_needed():
    """Check all sessions and restart if context is low"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking session context levels...")

    for session in SESSIONS_TO_MONITOR:
        output = get_session_output(session)
        context = detect_context_level(output)

        if context is not None:
            print(f"  {session}: {context}% context remaining")

            if context <= CONTEXT_THRESHOLD:
                print(f"  ⚠️  {session} at {context}% - triggering restart")
                restart_session(session)
            elif context <= 20:
                print(f"  ⚠️  {session} at {context}% - will restart at {CONTEXT_THRESHOLD}%")
        else:
            print(f"  {session}: Context level unknown")


def monitor_loop(interval=300):
    """Monitor sessions every N seconds (default 5 minutes)"""
    print(f"🔍 Smart Session Restart Monitor Started")
    print(f"   Monitoring: {', '.join(SESSIONS_TO_MONITOR)}")
    print(f"   Context threshold: {CONTEXT_THRESHOLD}%")
    print(f"   Check interval: {interval}s")
    print("   Press Ctrl+C to stop")
    print("")

    try:
        while True:
            check_and_restart_if_needed()
            print(f"\n⏰ Next check in {interval}s...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n👋 Monitor stopped")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            # One-time check
            check_and_restart_if_needed()
        elif sys.argv[1] == "--restart":
            # Manual restart of specific session
            if len(sys.argv) > 2:
                restart_session(sys.argv[2])
            else:
                print("Usage: smart_restart.py --restart <session_name>")
        elif sys.argv[1] == "--daemon":
            # Run as daemon
            monitor_loop()
        else:
            print("Usage:")
            print("  smart_restart.py --check           # One-time check")
            print("  smart_restart.py --daemon          # Run as daemon")
            print("  smart_restart.py --restart <name>  # Manual restart")
    else:
        # Default: one-time check
        check_and_restart_if_needed()
