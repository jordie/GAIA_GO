#!/usr/bin/env python3
"""
Foundation Session Monitor - Ensures continuous work for the foundation session

Integrates with the orchestrator's goal_engine to:
1. Monitor the foundation session's activity
2. Pull tasks from the goal engine when idle
3. Track progress and report back
4. Coordinate with the architect session to avoid conflicts

This ensures the foundation session always has work and stays productive.
"""

import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("FoundationMonitor")

# Configuration
SESSION_NAME = "foundation"
CHECK_INTERVAL = 120  # Check every 2 minutes
IDLE_THRESHOLD = 180  # Consider idle after 3 minutes
STATE_FILE = "/tmp/foundation_session_state.json"
WORK_LOG = BASE_DIR / "logs" / "foundation_work.log"

# Feature environment configuration
FEATURE_ENV = "env_1"
FEATURE_PORT = 8081
FEATURE_DATA_DIR = BASE_DIR / "feature_environments" / FEATURE_ENV / "data"


class FoundationSessionMonitor:
    """Monitor and coordinate work for the foundation session."""

    def __init__(self):
        self.session_name = SESSION_NAME
        self.state = self.load_state()
        self.ensure_log_directory()

    def ensure_log_directory(self):
        """Ensure log directory exists."""
        WORK_LOG.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> Dict:
        """Load persistent state from file."""
        if Path(STATE_FILE).exists():
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

        return {
            "session_start": datetime.now().isoformat(),
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_activity": datetime.now().isoformat(),
            "current_task": None,
            "idle_count": 0,
            "work_sessions": 0,
        }

    def save_state(self):
        """Save state to file."""
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def is_session_running(self) -> bool:
        """Check if the foundation session exists and is running."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self.session_name], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking session: {e}")
            return False

    def get_session_activity(self) -> Dict:
        """Get current activity status of the session."""
        try:
            # Capture last 50 lines of session output
            cmd = f"tmux capture-pane -t {self.session_name} -p -S -50"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                return {"status": "error", "message": "Could not capture pane"}

            output = result.stdout
            lines = output.strip().split("\n")
            last_line = lines[-1] if lines else ""

            # Detect idle indicators
            idle_indicators = ["❯", ">", "$", "#", "How can I help", "Continue"]
            is_idle = any(ind in last_line for ind in idle_indicators)

            # Detect busy indicators
            busy_indicators = ["Thinking", "Analyzing", "Processing", "Running", "…", "Task"]
            is_busy = any(ind in output for ind in busy_indicators)

            # Detect work completion
            completion_indicators = ["✓ Completed", "Success", "Done", "Finished"]
            completed_work = any(ind in output for ind in completion_indicators)

            return {
                "status": "ok",
                "is_idle": is_idle and not is_busy,
                "is_busy": is_busy,
                "completed_work": completed_work,
                "last_line": last_line[:200],
                "output_length": len(output),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting session activity: {e}")
            return {"status": "error", "message": str(e)}

    def get_next_task_from_orchestrator(self) -> Optional[Dict]:
        """Get next high-priority task from the goal engine."""
        try:
            # Check if goal engine database exists
            goal_db = BASE_DIR / "orchestrator" / "goals.db"
            if not goal_db.exists():
                logger.info("Goal engine database not initialized yet")
                return None

            conn = sqlite3.connect(str(goal_db))
            conn.row_factory = sqlite3.Row

            # Get highest priority task that's not yet started
            # Prefer tasks for the foundation/research/week2 work
            cursor = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'pending'
                AND (project LIKE '%week2%' OR project LIKE '%research%' OR project LIKE '%foundation%')
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """
            )

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "id": row["id"],
                    "content": row["content"],
                    "priority": row["priority"],
                    "category": row["category"],
                    "project": row["project"],
                }

            return None

        except Exception as e:
            logger.error(f"Error getting task from orchestrator: {e}")
            return None

    def send_task_to_session(self, task: Dict):
        """Send a task to the foundation session via tmux."""
        try:
            task_text = task["content"]
            priority = task.get("priority", 50)
            category = task.get("category", "general")

            # Format the task with context
            prompt = f"""
New Task from Orchestrator:
Priority: {priority}
Category: {category}
Task: {task_text}

Please work on this task now.
"""

            # Send to tmux session
            subprocess.run(
                ["tmux", "send-keys", "-t", self.session_name, prompt, "Enter"], timeout=5
            )

            # Update state
            self.state["current_task"] = task
            self.state["last_activity"] = datetime.now().isoformat()
            self.state["work_sessions"] += 1
            self.save_state()

            # Log work assignment
            self.log_work(f"Assigned task {task['id']}: {task_text[:100]}")

            logger.info(f"Sent task to {self.session_name}: {task_text[:100]}")
            return True

        except Exception as e:
            logger.error(f"Error sending task to session: {e}")
            return False

    def log_work(self, message: str):
        """Log work activity to file."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(WORK_LOG, "a") as f:
                f.write(f"{timestamp} - {message}\n")
        except Exception as e:
            logger.error(f"Error writing to work log: {e}")

    def check_and_assign_work(self):
        """Main monitoring loop - check if idle and assign work."""
        if not self.is_session_running():
            logger.warning(f"Session {self.session_name} is not running")
            return

        # Get activity status
        activity = self.get_session_activity()

        if activity["status"] != "ok":
            logger.error(f"Could not get session activity: {activity.get('message')}")
            return

        # Update state based on activity
        if activity["completed_work"]:
            if self.state["current_task"]:
                self.state["tasks_completed"] += 1
                self.log_work(f"Completed task: {self.state['current_task']['content'][:100]}")
                self.state["current_task"] = None

        # Check if idle and needs work
        if activity["is_idle"]:
            self.state["idle_count"] += 1
            logger.info(f"Session is idle (count: {self.state['idle_count']})")

            # If idle for threshold, assign new work
            if self.state["idle_count"] >= (IDLE_THRESHOLD / CHECK_INTERVAL):
                logger.info("Session idle for threshold, getting new task...")

                # Get next task from orchestrator
                task = self.get_next_task_from_orchestrator()

                if task:
                    logger.info(f"Found task from orchestrator: {task['content'][:100]}")
                    self.send_task_to_session(task)
                    self.state["idle_count"] = 0
                else:
                    logger.info("No tasks available from orchestrator")
                    # Could send a general "continue working on Week 2" prompt
                    self.send_general_work_prompt()
                    self.state["idle_count"] = 0
        else:
            # Session is busy
            self.state["idle_count"] = 0
            self.state["last_activity"] = datetime.now().isoformat()

        self.save_state()

    def send_general_work_prompt(self):
        """Send a general work prompt when no specific tasks are queued."""
        prompts = [
            "Continue working on Week 2 advanced features (Perplexity scraping, quality scoring, multi-project coordination)",
            "Check if there are any integration improvements needed for the web dashboard",
            "Review and enhance the quality scoring algorithm if needed",
            "Test the perplexity scraper with different result types",
            "Add any missing API endpoints to the web dashboard",
        ]

        import random

        prompt = random.choice(prompts)

        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", self.session_name, prompt, "Enter"], timeout=5
            )
            self.log_work(f"Sent general work prompt: {prompt}")
            logger.info(f"Sent general work prompt")
        except Exception as e:
            logger.error(f"Error sending work prompt: {e}")

    def get_status_summary(self) -> Dict:
        """Get a summary of the monitor status."""
        session_running = self.is_session_running()
        activity = self.get_session_activity() if session_running else {}

        uptime_seconds = 0
        if self.state.get("session_start"):
            start = datetime.fromisoformat(self.state["session_start"])
            uptime_seconds = (datetime.now() - start).total_seconds()

        return {
            "session_name": self.session_name,
            "session_running": session_running,
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": str(timedelta(seconds=int(uptime_seconds))),
            "tasks_completed": self.state.get("tasks_completed", 0),
            "tasks_failed": self.state.get("tasks_failed", 0),
            "work_sessions": self.state.get("work_sessions", 0),
            "current_task": self.state.get("current_task"),
            "is_idle": activity.get("is_idle", False) if activity else False,
            "is_busy": activity.get("is_busy", False) if activity else False,
            "last_activity": self.state.get("last_activity"),
            "feature_env": FEATURE_ENV,
            "feature_port": FEATURE_PORT,
            "timestamp": datetime.now().isoformat(),
        }

    def run_daemon(self):
        """Run as a background daemon."""
        logger.info(f"Starting Foundation Session Monitor for {self.session_name}")
        logger.info(f"Check interval: {CHECK_INTERVAL}s, Idle threshold: {IDLE_THRESHOLD}s")

        try:
            while True:
                self.check_and_assign_work()
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Shutting down monitor...")
            self.save_state()
        except Exception as e:
            logger.error(f"Fatal error in monitor loop: {e}")
            self.save_state()
            raise


def main():
    """Main entry point."""
    monitor = FoundationSessionMonitor()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--daemon":
            # Run as background daemon
            monitor.run_daemon()

        elif command == "--status":
            # Show current status
            status = monitor.get_status_summary()
            print(json.dumps(status, indent=2))

        elif command == "--check-once":
            # Run one check cycle
            monitor.check_and_assign_work()
            print("Check complete")

        elif command == "--assign-task":
            # Manually assign a task
            if len(sys.argv) < 3:
                print("Usage: --assign-task '<task description>'")
                sys.exit(1)

            task = {"id": "manual", "content": sys.argv[2], "priority": 100, "category": "manual"}
            monitor.send_task_to_session(task)
            print("Task assigned")

        else:
            print(f"Unknown command: {command}")
            print(
                "Usage: foundation_session_monitor.py [--daemon|--status|--check-once|--assign-task '<task>']"
            )
            sys.exit(1)
    else:
        # Default: show status
        status = monitor.get_status_summary()
        print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
