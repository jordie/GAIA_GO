#!/usr/bin/env python3
"""
Task Progress Monitor

Monitors active tasks in tmux sessions and updates the dashboard.
Runs continuously, checking every 10 seconds.
NO AI - pure script-based monitoring to conserve tokens.

Usage:
    python3 scripts/task_monitor.py --daemon
    python3 scripts/task_monitor.py --status
    python3 scripts/task_monitor.py --stop
"""

import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Setup paths
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DB_PATH = BASE_DIR / "data" / "prod" / "architect.db"
PID_FILE = Path("/tmp/task_monitor.pid")
LOG_FILE = Path("/tmp/task_monitor.log")

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://100.112.58.92:8080")
CHECK_INTERVAL = 10  # seconds

# Sessions to monitor for Basic Edu Apps
MONITORED_SESSIONS = {
    "codex_edu": {"task_id": 2, "type": "codex"},
    "codex": {"task_id": 1, "type": "codex"},
    "concurrent_worker1": {"task_id": 4, "type": "claude"},
    "concurrent_worker2": {"task_id": 5, "type": "claude"},
    "comet": {"task_id": 9, "type": "comet"},
    "concurrent_worker3": {"task_id": 10, "type": "comet"},
}


def log(message):
    """Log message to file and stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_line + "\n")
    except:
        pass


def is_running():
    """Check if monitor is already running."""
    if not PID_FILE.exists():
        return False

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # Check if process exists
        return True
    except (ProcessLookupError, ValueError):
        PID_FILE.unlink()
        return False


def write_pid():
    """Write current PID to file."""
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def get_session_output(session_name: str, lines: int = 30) -> str:
    """Capture output from tmux session.

    Args:
        session_name: Name of tmux session
        lines: Number of lines to capture

    Returns:
        Session output as string
    """
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", f"-{lines}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout
        return ""
    except Exception as e:
        log(f"Error capturing {session_name}: {e}")
        return ""


def detect_progress(output: str, session_type: str) -> Dict:
    """Detect progress indicators in session output.

    Args:
        output: Session output text
        session_type: Type of session (codex, claude, comet)

    Returns:
        Dict with status, progress, and message
    """
    status = {
        "is_working": False,
        "progress": 0,
        "current_step": "",
        "status": "idle",
        "last_activity": datetime.now().isoformat(),
    }

    output_lower = output.lower()

    # Check if waiting for input (idle)
    if any(indicator in output for indicator in [">", "How can I help", "?", "Esc to cancel"]):
        status["status"] = "idle"
        status["current_step"] = "Waiting for input"
        return status

    # Check for active work indicators
    working_indicators = [
        "analyzing",
        "fixing",
        "updating",
        "creating",
        "implementing",
        "debugging",
        "testing",
        "reviewing",
        "processing",
        "building",
        "reading",
        "writing",
        "checking",
        "git",
        "commit",
    ]

    if any(indicator in output_lower for indicator in working_indicators):
        status["is_working"] = True
        status["status"] = "working"

        # Extract current step from output
        lines = output.split("\n")
        for line in reversed(lines[-10:]):  # Check last 10 lines
            line_stripped = line.strip()
            if line_stripped and len(line_stripped) > 10:
                status["current_step"] = line_stripped[:100]
                break

    # Check for completion indicators
    if any(indicator in output_lower for indicator in ["completed", "done", "finished", "success"]):
        status["status"] = "completed"
        status["progress"] = 100
        status["current_step"] = "Task completed"

    # Check for error indicators
    elif any(indicator in output_lower for indicator in ["error", "failed", "exception"]):
        status["status"] = "error"
        status["current_step"] = "Error encountered"

    # Estimate progress based on keywords
    elif status["is_working"]:
        if "analyzing" in output_lower or "reading" in output_lower:
            status["progress"] = 20
        elif "implementing" in output_lower or "fixing" in output_lower:
            status["progress"] = 50
        elif "testing" in output_lower:
            status["progress"] = 75
        elif "commit" in output_lower:
            status["progress"] = 90
        else:
            status["progress"] = 30

    return status


def update_task_status(task_id: int, status: Dict):
    """Update task status in database.

    Args:
        task_id: Task ID
        status: Status dict from detect_progress
    """
    try:
        with sqlite3.connect(str(DB_PATH), timeout=10) as conn:
            # Update task_queue with current status
            task_data_update = json.dumps(
                {
                    "live_status": status["status"],
                    "live_progress": status["progress"],
                    "live_step": status["current_step"],
                    "live_updated": status["last_activity"],
                }
            )

            conn.execute(
                """
                UPDATE task_queue
                SET task_data = json_patch(task_data, ?)
                WHERE id = ?
            """,
                (task_data_update, task_id),
            )

            # If completed, mark task as completed
            if status["status"] == "completed" and status["progress"] == 100:
                conn.execute(
                    """
                    UPDATE task_queue
                    SET status = 'completed',
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status != 'completed'
                """,
                    (task_id,),
                )

            conn.commit()

    except Exception as e:
        log(f"Error updating task {task_id}: {e}")


def send_websocket_update(task_updates: List[Dict]):
    """Send updates via WebSocket for live dashboard refresh.

    Args:
        task_updates: List of task update dicts
    """
    try:
        # Use the dashboard's WebSocket broadcast endpoint
        requests.post(
            f"{DASHBOARD_URL}/api/tasks/broadcast-status", json={"updates": task_updates}, timeout=5
        )
    except Exception as e:
        log(f"Error sending WebSocket update: {e}")


def monitor_cycle():
    """Run one monitoring cycle - check all sessions and update status."""
    log("Running monitor cycle...")

    task_updates = []

    for session_name, config in MONITORED_SESSIONS.items():
        task_id = config["task_id"]
        session_type = config["type"]

        # Capture session output
        output = get_session_output(session_name)

        if not output:
            log(f"  {session_name}: No output (session may not exist)")
            continue

        # Detect progress
        status = detect_progress(output, session_type)

        log(
            f"  {session_name} (Task #{task_id}): {status['status']} - {status['current_step'][:50]}"
        )

        # Update database
        update_task_status(task_id, status)

        # Add to WebSocket update
        task_updates.append(
            {"task_id": task_id, "session": session_name, "type": session_type, **status}
        )

    # Send WebSocket update
    if task_updates:
        send_websocket_update(task_updates)

    log(f"Monitored {len(task_updates)} sessions")


def run_daemon():
    """Run monitor as daemon."""
    if is_running():
        log("Monitor already running")
        return

    write_pid()
    log("Starting task monitor daemon...")
    log(f"Monitoring {len(MONITORED_SESSIONS)} sessions")
    log(f"Check interval: {CHECK_INTERVAL} seconds")

    try:
        while True:
            monitor_cycle()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        log("Stopped by user")
    except Exception as e:
        log(f"Error: {e}")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


def stop_daemon():
    """Stop running daemon."""
    if not PID_FILE.exists():
        log("Monitor not running")
        return

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        log(f"Stopped monitor (PID {pid})")
    except Exception as e:
        log(f"Error stopping: {e}")


def show_status():
    """Show monitor status."""
    if not is_running():
        print("Monitor: NOT RUNNING")
        return

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        print(f"Monitor: RUNNING (PID {pid})")
        print(f"Sessions monitored: {len(MONITORED_SESSIONS)}")
        print(f"Check interval: {CHECK_INTERVAL}s")
        print(f"\nMonitored sessions:")
        for session, config in MONITORED_SESSIONS.items():
            print(f"  - {session}: Task #{config['task_id']} ({config['type']})")
    except Exception as e:
        print(f"Error: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Task Progress Monitor")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--once", action="store_true", help="Run one cycle")

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        show_status()
    elif args.once:
        monitor_cycle()
    elif args.daemon:
        run_daemon()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
