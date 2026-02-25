#!/usr/bin/env python3
"""
Persistent Orchestrator - Never Stops

Keeps the autonomous development system running 24/7:
- Executes roadmap phases
- Detects idle time and keeps things moving
- Manages developer profiles
- Coordinates all workers
- Reports progress
- NEVER STOPS until explicitly killed

Usage:
    python3 persistent_orchestrator.py           # Run forever
    python3 persistent_orchestrator.py --daemon  # Run as daemon
    python3 persistent_orchestrator.py --stop    # Stop daemon
"""

import hashlib
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
DATA_DIR = BASE_DIR / "data"

# Worker configuration
PID_FILE = Path("/tmp/architect_persistent_orchestrator.pid")
STATE_FILE = Path("/tmp/architect_persistent_orchestrator_state.json")
LOG_FILE = Path("/tmp/architect_persistent_orchestrator.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("PersistentOrchestrator")


class PersistentOrchestrator:
    """Orchestrator that never stops - keeps the system moving 24/7."""

    def __init__(self):
        self.running = False
        self.started_at = datetime.now()
        self.cycle_interval = 60  # Check every minute
        self.idle_timeout = 300  # 5 minutes idle before taking action
        self.last_activity = datetime.now()

        # Roadmap state
        self.current_phase = 1
        self.phase_progress = {
            1: 65,  # Phase 1: 65% complete
            2: 15,  # Phase 2: 15% complete
            3: 5,  # Phase 3: 5% complete
            4: 0,
            5: 0,
            6: 0,
        }

        # Tasks completed today
        self.tasks_completed_today = 0

        # Dashboard API endpoint
        self.dashboard_url = "http://localhost:8080"

        # Track queued tasks to avoid duplicates
        self.queued_tasks = set()

        # Initialize database
        self.init_database()

    def init_database(self):
        """Initialize orchestrator database."""
        db_path = DATA_DIR / "orchestrator.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Roadmap progress table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS roadmap_progress (
                phase INTEGER PRIMARY KEY,
                title TEXT,
                progress INTEGER,
                status TEXT,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT
            )
        """
        )

        # Activity log
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                activity_type TEXT,
                description TEXT,
                phase INTEGER,
                metadata TEXT
            )
        """
        )

        # Initialize phases if not exist
        phases = [
            (1, "Autonomous Task Execution", 65, "in_progress"),
            (2, "Multi-Agent Development", 15, "in_progress"),
            (3, "Full Development Lifecycle", 5, "pending"),
            (4, "Multi-Project Management", 0, "pending"),
            (5, "Voice Integration & Communication", 0, "pending"),
            (6, "Advanced Automation & Learning", 0, "pending"),
        ]

        for phase_num, title, progress, status in phases:
            cursor.execute(
                """
                INSERT OR IGNORE INTO roadmap_progress (phase, title, progress, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (phase_num, title, progress, status, datetime.now().isoformat()),
            )

        conn.commit()
        conn.close()

    def log_activity(self, activity_type: str, description: str, phase: int = None):
        """Log activity to database."""
        try:
            db_path = DATA_DIR / "orchestrator.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO activity_log (timestamp, activity_type, description, phase)
                VALUES (?, ?, ?, ?)
            """,
                (datetime.now().isoformat(), activity_type, description, phase),
            )

            conn.commit()
            conn.close()

            logger.info(f"[{activity_type}] {description}")

        except Exception as e:
            logger.error(f"Error logging activity: {e}")

    def update_phase_progress(self, phase: int, progress: int):
        """Update roadmap phase progress."""
        try:
            db_path = DATA_DIR / "orchestrator.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            status = "completed" if progress >= 100 else "in_progress"

            cursor.execute(
                """
                UPDATE roadmap_progress
                SET progress = ?, status = ?, updated_at = ?
                WHERE phase = ?
            """,
                (progress, status, datetime.now().isoformat(), phase),
            )

            if progress >= 100:
                cursor.execute(
                    """
                    UPDATE roadmap_progress
                    SET completed_at = ?
                    WHERE phase = ? AND completed_at IS NULL
                """,
                    (datetime.now().isoformat(), phase),
                )

            conn.commit()
            conn.close()

            self.phase_progress[phase] = progress

            logger.info(f"Phase {phase} progress updated: {progress}%")

        except Exception as e:
            logger.error(f"Error updating phase progress: {e}")

    def check_idle_and_act(self):
        """Check if system is idle and take action to keep things moving."""
        idle_duration = (datetime.now() - self.last_activity).total_seconds()

        if idle_duration > self.idle_timeout:
            logger.warning(
                f"System idle for {idle_duration:.0f}s - Taking action to keep things moving"
            )

            # Take action based on current phase
            if self.current_phase == 1:
                self.execute_phase1_task()
            elif self.current_phase == 2:
                self.execute_phase2_task()

            self.last_activity = datetime.now()

    def queue_task_to_assigner(
        self, content: str, priority: int = 5, metadata: dict = None
    ) -> bool:
        """Queue a task to the assigner for Claude sessions."""
        try:
            # Check if already queued
            task_hash = hashlib.md5(content.encode()).hexdigest()
            if task_hash in self.queued_tasks:
                logger.debug(f"Task already queued: {content[:50]}...")
                return False

            # Queue via assigner API (no auth needed for internal calls)
            data = {"content": content, "priority": priority, "metadata": metadata or {}}

            # Try direct database insert (faster than API)
            try:
                assigner_db = Path("data/assigner/assigner.db")
                if assigner_db.exists():
                    conn = sqlite3.connect(str(assigner_db))
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO prompts (content, priority, status, created_at, metadata)
                        VALUES (?, ?, 'pending', ?, ?)
                    """,
                        (content, priority, datetime.now().isoformat(), json.dumps(metadata or {})),
                    )
                    conn.commit()
                    conn.close()

                    self.queued_tasks.add(task_hash)
                    logger.info(f"✅ Queued task: {content[:60]}...")
                    self.last_activity = datetime.now()
                    return True
            except Exception as e:
                logger.error(f"Failed to queue task directly: {e}")
                return False

        except Exception as e:
            logger.error(f"Error queuing task: {e}")
            return False

    def execute_phase1_task(self):
        """Execute a task from Phase 1 (Autonomous Task Execution)."""
        logger.info("Executing Phase 1 task to keep momentum")

        # Define Phase 1 work items with actual prompts
        phase1_tasks = [
            {
                "name": "google_voice_sms",
                "progress": 70,
                "prompt": "Continue implementing Google Voice SMS automation. Check scripts/send_voice_message.py and upgrade it to use OAuth2 for automated sending. Reference the strategic roadmap in data files.",
                "priority": 7,
            },
            {
                "name": "daily_scheduler",
                "progress": 0,
                "prompt": "Create a daily task scheduler worker that reads tasks from the database and schedules them for execution. It should support recurring tasks, one-time tasks, and cron-like scheduling. Save to workers/daily_scheduler.py.",
                "priority": 8,
            },
            {
                "name": "web_task_library",
                "progress": 25,
                "prompt": "Expand the web task automation library in data/automation/site_definitions.yaml. Add more common sites and workflows. Focus on sites that support the Basic EDU project.",
                "priority": 6,
            },
            {
                "name": "strategic_dashboard_integration",
                "progress": 50,
                "prompt": "Integrate the strategic dashboard (templates/strategic_dashboard.html) into the main dashboard. Add a new navigation item and panel. Make sure the API endpoints in app.py are wired up correctly.",
                "priority": 9,
            },
            {
                "name": "stripe_integration",
                "progress": 0,
                "prompt": "Research and plan Stripe API integration for Basic EDU payment processing. Create a design document outlining the implementation approach, required API keys, and integration points.",
                "priority": 5,
            },
        ]

        # Pick the next incomplete task with highest priority
        incomplete_tasks = [t for t in phase1_tasks if t["progress"] < 100]
        if not incomplete_tasks:
            logger.info("All Phase 1 tasks complete!")
            return

        # Sort by priority (highest first)
        incomplete_tasks.sort(key=lambda x: x["priority"], reverse=True)
        task = incomplete_tasks[0]

        # Queue the task
        queued = self.queue_task_to_assigner(
            content=task["prompt"],
            priority=task["priority"],
            metadata={
                "phase": 1,
                "task_name": task["name"],
                "orchestrator": "persistent",
                "roadmap_driven": True,
            },
        )

        if queued:
            logger.info(f"📋 Queued Phase 1 task: {task['name']}")
            self.log_activity("phase1_task_queued", f"Queued {task['name']}", 1)
            self.tasks_completed_today += 1

            # Update overall phase progress (small increment per task queued)
            avg_progress = sum(t["progress"] for t in phase1_tasks) / len(phase1_tasks)
            new_progress = min(int(avg_progress) + 2, 100)
            self.update_phase_progress(1, new_progress)

    def execute_phase2_task(self):
        """Execute a task from Phase 2 (Multi-Agent Development)."""
        logger.info("Executing Phase 2 task to keep momentum")

        # Define Phase 2 work items
        phase2_tasks = [
            {
                "name": "developer_profiles",
                "prompt": "Design the multi-agent developer profile system. Create 5 profiles (Backend Sr, Frontend Sr, DevOps, QA, Junior) with specialized roles and task routing logic.",
                "priority": 7,
            },
            {
                "name": "task_routing",
                "prompt": "Implement intelligent task routing based on developer profiles. Tasks should be assigned to the most appropriate Claude session based on expertise.",
                "priority": 6,
            },
            {
                "name": "session_coordination",
                "prompt": "Create a coordination layer for multiple Claude sessions to work on the same project without conflicts. Implement file locking and merge strategies.",
                "priority": 8,
            },
        ]

        # Pick a task and queue it
        task = phase2_tasks[0]  # Start with first task
        queued = self.queue_task_to_assigner(
            content=task["prompt"],
            priority=task["priority"],
            metadata={
                "phase": 2,
                "task_name": task["name"],
                "orchestrator": "persistent",
                "roadmap_driven": True,
            },
        )

        if queued:
            logger.info(f"📋 Queued Phase 2 task: {task['name']}")
            self.log_activity("phase2_task_queued", f"Queued {task['name']}", 2)
            self.tasks_completed_today += 1

            # Update phase 2 progress
            new_progress = min(self.phase_progress[2] + 3, 100)
            self.update_phase_progress(2, new_progress)

    def run_cycle(self):
        """Run one orchestration cycle."""
        logger.info("Running orchestration cycle")

        # Check idle and act
        self.check_idle_and_act()

        # Check if current phase is complete
        if self.phase_progress[self.current_phase] >= 100:
            logger.info(
                f"Phase {self.current_phase} complete! Moving to Phase {self.current_phase + 1}"
            )
            self.current_phase += 1
            self.log_activity(
                "phase_complete",
                f"Phase {self.current_phase - 1} completed",
                self.current_phase - 1,
            )

        # Save state
        self.save_state()

        logger.info(
            f"Cycle complete - Phase {self.current_phase} at {self.phase_progress[self.current_phase]}%"
        )

    def run(self):
        """Main loop - runs forever."""
        logger.info("=" * 70)
        logger.info("🚀 PERSISTENT ORCHESTRATOR STARTED")
        logger.info("=" * 70)
        logger.info("This orchestrator will run 24/7, keeping the system moving")
        logger.info(f"Cycle interval: {self.cycle_interval}s")
        logger.info(f"Idle timeout: {self.idle_timeout}s")
        logger.info(f"Current phase: {self.current_phase}")
        logger.info("=" * 70)

        self.running = True
        self.log_activity("orchestrator_start", "Persistent orchestrator started")

        while self.running:
            try:
                self.run_cycle()

                # Sleep until next cycle
                time.sleep(self.cycle_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in orchestration cycle: {e}")
                logger.info("Continuing despite error...")
                time.sleep(self.cycle_interval)

        logger.info("=" * 70)
        logger.info("🛑 PERSISTENT ORCHESTRATOR STOPPED")
        logger.info("=" * 70)

    def save_state(self):
        """Save orchestrator state."""
        try:
            uptime = (datetime.now() - self.started_at).total_seconds()
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)

            state = {
                "started_at": self.started_at.isoformat(),
                "last_cycle": datetime.now().isoformat(),
                "running": self.running,
                "current_phase": self.current_phase,
                "phase_progress": self.phase_progress,
                "tasks_completed_today": self.tasks_completed_today,
                "uptime": f"{hours}h {minutes}m",
            }

            STATE_FILE.write_text(json.dumps(state, indent=2))

        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def stop(self):
        """Stop the orchestrator."""
        logger.info("Stopping orchestrator")
        self.running = False
        self.log_activity("orchestrator_stop", "Persistent orchestrator stopped")


def start_daemon():
    """Start as daemon."""
    if PID_FILE.exists():
        print("❌ Orchestrator already running")
        return

    pid = os.fork()
    if pid > 0:
        PID_FILE.write_text(str(pid))
        print(f"✅ Started persistent orchestrator (PID: {pid})")
        print(f"📝 Logs: {LOG_FILE}")
        print("🔄 This will run 24/7 - keeping the roadmap moving")
        sys.exit(0)

    # Become session leader
    os.setsid()

    # Fork again
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect IO
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as f:
        os.dup2(f.fileno(), sys.stdin.fileno())

    # Run orchestrator
    orchestrator = PersistentOrchestrator()
    orchestrator.run()


def stop_daemon():
    """Stop daemon."""
    if not PID_FILE.exists():
        print("❌ Orchestrator not running")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        print(f"✅ Stopped orchestrator (PID: {pid})")
    except Exception as e:
        print(f"❌ Error stopping: {e}")
        if PID_FILE.exists():
            PID_FILE.unlink()


def check_status():
    """Check status."""
    if not PID_FILE.exists():
        print("⚪ Orchestrator not running")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)

        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
            print(f"🟢 Persistent Orchestrator Running (PID: {pid})")
            print(f"   Started: {state.get('started_at', 'Unknown')}")
            print(f"   Uptime: {state.get('uptime', 'Unknown')}")
            print(f"   Current Phase: {state.get('current_phase', 'Unknown')}")
            print(f"   Tasks Today: {state.get('tasks_completed_today', 0)}")
            print()
            print("   Phase Progress:")
            for phase, progress in state.get("phase_progress", {}).items():
                bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
                print(f"     Phase {phase}: [{bar}] {progress}%")
        else:
            print(f"🟡 Running (PID: {pid}) - no state file")

    except ProcessLookupError:
        print("🔴 Not running (stale PID file)")
        PID_FILE.unlink()
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Persistent Orchestrator")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Check status")

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        check_status()
    elif args.daemon:
        start_daemon()
    else:
        # Run in foreground
        orchestrator = PersistentOrchestrator()

        def signal_handler(sig, frame):
            orchestrator.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        orchestrator.run()


if __name__ == "__main__":
    main()
