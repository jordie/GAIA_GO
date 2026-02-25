#!/usr/bin/env python3
"""
Task Monitor - Proactively monitors tasks and detects blocked/stuck states

Monitors:
- Tasks marked complete but still running
- Tasks blocked on approval prompts
- Tasks asking questions
- Tasks that have been in same state too long
- Session health and availability

Alerts when intervention needed.
"""

import json
import logging
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("task_monitor")

DB_PATH = "/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/assigner/assigner.db"
MONITOR_INTERVAL = 30  # Check every 30 seconds
DASHBOARD_URL = "http://localhost:8080"

# Detection patterns
BLOCKED_PATTERNS = [
    "Do you want to",
    "want to proceed",
    "Behavior ask",
    "accept edits on",
    "shift+tab to cycle",
    "esc to interrupt",
    "[Pasted text",
    "Esc to cancel",
]

QUESTION_PATTERNS = [
    "?",
    "Which",
    "Should I",
    "How would you like",
    "What should",
    "Please confirm",
]

ACTIVE_PATTERNS = [
    "thinking",
    "Cooking",
    "Running",
    "Analyzing",
    "Processing",
    "Executing",
    "Working",
    "Building",
    "Testing",
    "Searching",
    "Reading",
    "Writing",
    "Architecting",
]


class TaskMonitor:
    def __init__(self):
        self.db_path = DB_PATH
        self.alerts = []

    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_tasks(self) -> List[Dict]:
        """Get all active tasks"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                content,
                status,
                assigned_session,
                assigned_at,
                completed_at,
                priority,
                metadata
            FROM prompts
            WHERE status IN ('assigned', 'in_progress', 'pending')
            ORDER BY priority DESC, created_at ASC
        """
        )

        tasks = []
        for row in cursor.fetchall():
            tasks.append(
                {
                    "id": row["id"],
                    "content": row["content"],
                    "status": row["status"],
                    "session": row["assigned_session"],
                    "assigned_at": row["assigned_at"],
                    "completed_at": row["completed_at"],
                    "priority": row["priority"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                }
            )

        conn.close()
        return tasks

    def capture_session_output(self, session: str) -> Optional[str]:
        """Capture tmux session output"""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception as e:
            logger.error(f"Failed to capture {session}: {e}")
            return None

    def detect_blocked_state(self, output: str) -> Optional[str]:
        """Detect if session is blocked on approval/question"""
        if not output:
            return None

        # Check for blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if pattern.lower() in output.lower():
                return f"Blocked on: {pattern}"

        # Check for questions (last 10 lines)
        lines = output.strip().split("\n")[-10:]
        for line in lines:
            for pattern in QUESTION_PATTERNS:
                if pattern in line and "?" in line:
                    return f"Asking: {line.strip()[:100]}"

        return None

    def is_actively_working(self, output: str) -> bool:
        """Check if session is actively working"""
        if not output:
            return False

        # Check last 20 lines for active indicators
        recent = "\n".join(output.strip().split("\n")[-20:])
        return any(pattern in recent for pattern in ACTIVE_PATTERNS)

    def check_task_health(self, task: Dict) -> Optional[Dict]:
        """Check if task needs attention"""
        task_id = task["id"]
        status = task["status"]
        session = task["session"]
        assigned_at = task["assigned_at"]

        alerts = []

        # Skip if no session assigned
        if not session:
            return None

        # Capture session output
        output = self.capture_session_output(session)
        if output is None:
            alerts.append({"severity": "warning", "message": f"Cannot capture session '{session}'"})
            return (
                {"task_id": task_id, "session": session, "status": status, "alerts": alerts}
                if alerts
                else None
            )

        # Check for blocked state
        blocked = self.detect_blocked_state(output)
        if blocked:
            alerts.append(
                {
                    "severity": "high",
                    "message": blocked,
                    "action": "needs_response",
                    "output_preview": "\n".join(output.strip().split("\n")[-15:]),
                }
            )

        # Check if marked complete but still working
        if status == "completed":
            if self.is_actively_working(output) or blocked:
                alerts.append(
                    {
                        "severity": "critical",
                        "message": "Marked complete but still running/blocked",
                        "action": "update_status",
                    }
                )

        # Check for stale tasks (in progress > 1 hour)
        if status == "in_progress" and assigned_at:
            try:
                assigned_time = datetime.fromisoformat(assigned_at)
                elapsed = (datetime.now() - assigned_time).total_seconds() / 60

                if elapsed > 60:  # 1 hour
                    alerts.append(
                        {
                            "severity": "medium",
                            "message": f"In progress for {elapsed:.0f} minutes",
                            "action": "check_progress",
                        }
                    )
            except:
                pass

        return (
            {
                "task_id": task_id,
                "session": session,
                "status": status,
                "content_preview": task["content"][:100],
                "alerts": alerts,
            }
            if alerts
            else None
        )

    def send_notification(self, alert: Dict):
        """Send notification about task issue"""
        # Log alert
        severity = alert.get("severity", "info")
        task_id = alert.get("task_id")
        session = alert.get("session")
        message = alert.get("alerts", [{}])[0].get("message", "")

        logger.warning(f"🚨 Task #{task_id} in {session}: {message}")

        # Could integrate with:
        # - Dashboard notifications
        # - Slack/Discord webhooks
        # - Email alerts
        # For now, just log and store
        self.alerts.append(
            {
                "timestamp": datetime.now().isoformat(),
                "task_id": task_id,
                "session": session,
                "severity": severity,
                "message": message,
            }
        )

    def auto_handle_common_prompts(self, task: Dict, blocked_info: Dict):
        """Auto-handle common approval prompts"""
        message = blocked_info.get("message", "").lower()
        session = task["session"]

        # Auto-accept edit confirmations (if configured)
        if "accept edits" in message:
            logger.info(f"Auto-accepting edits in {session} for task #{task['id']}")
            try:
                subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], timeout=5)
                return True
            except Exception as e:
                logger.error(f"Failed to auto-accept: {e}")

        return False

    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("🔍 Task monitor started")
        logger.info(f"Monitoring interval: {MONITOR_INTERVAL}s")

        while True:
            try:
                # Get all active tasks
                tasks = self.get_all_tasks()
                logger.debug(f"Checking {len(tasks)} active tasks")

                issues_found = 0

                for task in tasks:
                    health = self.check_task_health(task)

                    if health and health.get("alerts"):
                        issues_found += 1
                        self.send_notification(health)

                        # Try auto-handling
                        for alert in health["alerts"]:
                            if alert.get("action") == "needs_response":
                                self.auto_handle_common_prompts(task, alert)

                if issues_found > 0:
                    logger.info(f"⚠️  Found {issues_found} tasks needing attention")

                # Sleep until next check
                time.sleep(MONITOR_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(MONITOR_INTERVAL)

    def get_status_report(self) -> Dict:
        """Get current status report"""
        tasks = self.get_all_tasks()

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(tasks),
            "by_status": {},
            "issues": [],
            "recent_alerts": self.alerts[-20:],  # Last 20 alerts
        }

        for task in tasks:
            status = task["status"]
            report["by_status"][status] = report["by_status"].get(status, 0) + 1

            health = self.check_task_health(task)
            if health and health.get("alerts"):
                report["issues"].append(health)

        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Monitor tasks for issues")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--status", action="store_true", help="Get status report")
    parser.add_argument("--check-task", type=int, help="Check specific task ID")

    args = parser.parse_args()

    monitor = TaskMonitor()

    if args.status:
        report = monitor.get_status_report()
        print(json.dumps(report, indent=2))

    elif args.check_task:
        tasks = monitor.get_all_tasks()
        task = next((t for t in tasks if t["id"] == args.check_task), None)

        if task:
            health = monitor.check_task_health(task)
            print(json.dumps(health or {"status": "healthy"}, indent=2))
        else:
            print(f"Task {args.check_task} not found or not active")

    else:
        # Run monitoring loop
        monitor.monitor_loop()


if __name__ == "__main__":
    main()
