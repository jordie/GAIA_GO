#!/usr/bin/env python3
"""
Session Health Monitor Daemon
Tracks sessions without needing AI - just output scraping and DB checks
"""
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data/assigner/assigner.db"
SESSIONS = ["claude_comet", "codex", "dev_worker1", "dev_worker2"]
CHECK_INTERVAL = 60  # seconds


def get_session_output(session_name):
    """Get last 50 lines from tmux session"""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-50"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout if result.returncode == 0 else ""
    except:
        return ""


def detect_session_state(output):
    """Detect if session is active, blocked, stuck, or idle"""
    if not output:
        return "no_output"

    # Check last 10 lines for activity indicators
    recent = "\n".join(output.split("\n")[-10:])

    if any(
        word in recent
        for word in ["Running", "Thinking", "Writing", "Reading", "...", "Processing"]
    ):
        return "active"
    elif any(word in recent for word in ["Do you want", "proceed?", "Yes/No", "allow"]):
        return "blocked_permission"
    elif any(word in recent for word in ["Error", "Failed", "Exception", "Traceback"]):
        return "error"
    elif len(set(output.split("\n")[-20:])) < 3:  # Same lines repeated
        return "stuck"
    else:
        return "idle"


def sync_database(session_name, state):
    """Update database based on actual session state"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    db_status = "idle" if state in ["idle", "no_output"] else "busy"

    c.execute("UPDATE sessions SET status = ? WHERE name = ?", (db_status, session_name))
    conn.commit()
    conn.close()


def monitor_loop():
    """Main monitoring loop"""
    print(f"🔍 Session Health Monitor Started - Checking every {CHECK_INTERVAL}s")

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Health Check")
        print("=" * 50)

        for session in SESSIONS:
            output = get_session_output(session)
            state = detect_session_state(output)

            # Sync database
            sync_database(session, state)

            # Display
            status_icon = {
                "active": "✅",
                "idle": "💤",
                "blocked_permission": "⚠️ ",
                "stuck": "🔴",
                "error": "❌",
                "no_output": "⚫",
            }.get(state, "❓")

            print(f"{status_icon} {session:<15} {state}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        monitor_loop()
    except KeyboardInterrupt:
        print("\n\n👋 Monitor stopped")
