#!/usr/bin/env python3
"""
Continuous Improvement Worker

A persistent worker that:
- Monitors system health (workers, services, database)
- Uses local LLM (Ollama) for decision making
- Suggests improvements and optimizations
- Tracks goals and progress
- Automatically tests improvements
- Ensures session continuity

Usage:
    python3 continuous_improvement_worker.py                # Run in foreground
    python3 continuous_improvement_worker.py --daemon       # Run as daemon
    python3 continuous_improvement_worker.py --stop         # Stop daemon
    python3 continuous_improvement_worker.py --status       # Check status

    # Goals
    python3 continuous_improvement_worker.py --add-goal "Improve LLM response time"
    python3 continuous_improvement_worker.py --list-goals

    # Suggestions
    python3 continuous_improvement_worker.py --list-suggestions
    python3 continuous_improvement_worker.py --approve <suggestion_id>
"""

import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
DATA_DIR = BASE_DIR / "data"
CI_DIR = DATA_DIR / "continuous_improvement"

# Add parent directory to Python path
sys.path.insert(0, str(BASE_DIR))

# Worker configuration
PID_FILE = Path("/tmp/architect_ci_worker.pid")
STATE_FILE = Path("/tmp/architect_ci_worker_state.json")
LOG_FILE = Path("/tmp/architect_ci_worker.log")

# Create CI data directory
CI_DIR.mkdir(parents=True, exist_ok=True)

# CI database
CI_DB = CI_DIR / "ci.db"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("ContinuousImprovement")


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    DEPLOYED = "deployed"


@dataclass
class Goal:
    id: Optional[int]
    title: str
    description: str
    status: GoalStatus
    priority: int  # 1-10, higher is more urgent
    progress: int  # 0-100%
    target_date: Optional[str]
    dependencies: Optional[str]  # JSON list of goal IDs
    created_at: str
    updated_at: str
    completed_at: Optional[str]


@dataclass
class Suggestion:
    id: Optional[int]
    goal_id: Optional[int]
    title: str
    description: str
    rationale: str  # LLM's reasoning
    implementation_plan: str
    status: SuggestionStatus
    priority: int
    estimated_impact: str  # low, medium, high
    risk_level: str  # low, medium, high
    created_at: str
    updated_at: str
    approved_at: Optional[str]
    implemented_at: Optional[str]


@dataclass
class SystemHealth:
    timestamp: str
    workers_running: int
    workers_total: int
    database_size_mb: float
    disk_usage_percent: float
    memory_usage_percent: float
    cpu_usage_percent: float
    session_count: int
    error_count_24h: int
    issues: List[str]


class ContinuousImprovementWorker:
    """Continuous improvement worker with LLM integration."""

    def __init__(self):
        self.running = False
        self.check_interval = 300  # Check every 5 minutes
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.init_database()

    def init_database(self):
        """Initialize CI database."""
        conn = sqlite3.connect(str(CI_DB))
        cursor = conn.cursor()

        # Goals table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                priority INTEGER DEFAULT 5,
                progress INTEGER DEFAULT 0,
                target_date TEXT,
                dependencies TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
        """
        )

        # Suggestions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                rationale TEXT,
                implementation_plan TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                estimated_impact TEXT DEFAULT 'medium',
                risk_level TEXT DEFAULT 'medium',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved_at TEXT,
                implemented_at TEXT,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            )
        """
        )

        # Health metrics table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS health_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                workers_running INTEGER,
                workers_total INTEGER,
                database_size_mb REAL,
                disk_usage_percent REAL,
                memory_usage_percent REAL,
                cpu_usage_percent REAL,
                session_count INTEGER,
                error_count_24h INTEGER,
                issues TEXT
            )
        """
        )

        # Improvement log table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS improvement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (suggestion_id) REFERENCES suggestions(id)
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def check_system_health(self) -> SystemHealth:
        """Check overall system health."""
        try:
            # Worker status
            workers_running = 0
            workers_total = 0
            worker_files = list(WORKER_DIR.glob("*_worker.py"))
            workers_total = len(worker_files)

            for worker_file in worker_files:
                worker_name = worker_file.stem
                pid_file = Path(f"/tmp/architect_{worker_name}.pid")
                if pid_file.exists():
                    try:
                        pid = int(pid_file.read_text().strip())
                        # Check if process is running
                        os.kill(pid, 0)
                        workers_running += 1
                    except:
                        pass

            # Database size
            main_db = DATA_DIR / "architect.db"
            db_size_mb = main_db.stat().st_size / (1024 * 1024) if main_db.exists() else 0

            # Disk usage
            disk_usage = subprocess.run(["df", "-h", str(BASE_DIR)], capture_output=True, text=True)
            disk_percent = 0
            if disk_usage.returncode == 0:
                lines = disk_usage.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        disk_percent = float(parts[4].rstrip("%"))

            # Memory usage (macOS)
            memory_percent = 0
            try:
                vm_stat = subprocess.run(["vm_stat"], capture_output=True, text=True)
                if vm_stat.returncode == 0:
                    # Parse vm_stat output (simplified)
                    memory_percent = 50.0  # Placeholder - would need proper parsing
            except:
                pass

            # CPU usage
            cpu_percent = 0
            try:
                top_output = subprocess.run(
                    ["top", "-l", "1", "-n", "0"], capture_output=True, text=True, timeout=2
                )
                if top_output.returncode == 0:
                    # Parse CPU usage from top output
                    for line in top_output.stdout.split("\n"):
                        if "CPU usage" in line:
                            # Extract percentage
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if "user" in part and i > 0:
                                    cpu_percent = float(parts[i - 1].rstrip("%"))
                                    break
                            break
            except:
                pass

            # Session count
            session_count = 0
            try:
                tmux_output = subprocess.run(
                    ["tmux", "list-sessions"], capture_output=True, text=True
                )
                if tmux_output.returncode == 0:
                    session_count = len(tmux_output.stdout.strip().split("\n"))
            except:
                pass

            # Error count (last 24 hours)
            error_count = 0
            try:
                conn = sqlite3.connect(str(DATA_DIR / "architect.db"))
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM errors
                    WHERE created_at >= datetime('now', '-1 day')
                """
                )
                error_count = cursor.fetchone()[0]
                conn.close()
            except:
                pass

            # Issues
            issues = []
            if workers_running < workers_total:
                issues.append(f"{workers_total - workers_running} workers not running")
            if disk_percent > 90:
                issues.append(f"Disk usage high: {disk_percent}%")
            if error_count > 100:
                issues.append(f"High error count: {error_count} in last 24h")
            if session_count == 0:
                issues.append("No tmux sessions running")

            health = SystemHealth(
                timestamp=datetime.now().isoformat(),
                workers_running=workers_running,
                workers_total=workers_total,
                database_size_mb=round(db_size_mb, 2),
                disk_usage_percent=disk_percent,
                memory_usage_percent=memory_percent,
                cpu_usage_percent=cpu_percent,
                session_count=session_count,
                error_count_24h=error_count,
                issues=issues,
            )

            # Log health metrics
            self.log_health_metrics(health)

            return health

        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return SystemHealth(
                timestamp=datetime.now().isoformat(),
                workers_running=0,
                workers_total=0,
                database_size_mb=0,
                disk_usage_percent=0,
                memory_usage_percent=0,
                cpu_usage_percent=0,
                session_count=0,
                error_count_24h=0,
                issues=[f"Health check failed: {str(e)}"],
            )

    def log_health_metrics(self, health: SystemHealth):
        """Log health metrics to database."""
        try:
            conn = sqlite3.connect(str(CI_DB))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO health_metrics
                (timestamp, workers_running, workers_total, database_size_mb,
                 disk_usage_percent, memory_usage_percent, cpu_usage_percent,
                 session_count, error_count_24h, issues)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    health.timestamp,
                    health.workers_running,
                    health.workers_total,
                    health.database_size_mb,
                    health.disk_usage_percent,
                    health.memory_usage_percent,
                    health.cpu_usage_percent,
                    health.session_count,
                    health.error_count_24h,
                    json.dumps(health.issues),
                ),
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging health metrics: {e}")

    def ask_llm(self, prompt: str, context: Optional[str] = None) -> Optional[str]:
        """Ask local LLM for suggestions."""
        try:
            full_prompt = prompt
            if context:
                full_prompt = f"Context:\n{context}\n\nQuestion:\n{prompt}"

            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={"model": self.ollama_model, "prompt": full_prompt, "stream": False},
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.error(f"LLM request failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error asking LLM: {e}")
            return None

    def generate_suggestions(self, health: SystemHealth) -> List[Suggestion]:
        """Generate improvement suggestions based on system health."""
        suggestions = []
        now = datetime.now().isoformat()

        # Get active goals
        goals = self.get_goals(status=GoalStatus.ACTIVE)

        # Generate context for LLM
        context = f"""
System Health Report:
- Workers: {health.workers_running}/{health.workers_total} running
- Database Size: {health.database_size_mb} MB
- Disk Usage: {health.disk_usage_percent}%
- Memory Usage: {health.memory_usage_percent}%
- CPU Usage: {health.cpu_usage_percent}%
- tmux Sessions: {health.session_count}
- Errors (24h): {health.error_count_24h}
- Issues: {', '.join(health.issues) if health.issues else 'None'}

Active Goals:
"""
        for goal in goals[:5]:  # Top 5 goals
            context += f"- [{goal.priority}] {goal.title} ({goal.progress}% complete)\n"

        # Ask LLM for suggestions
        prompt = """Based on this system health report and active goals, suggest 1-3 specific improvements.
For each suggestion, provide:
1. Title (brief, actionable)
2. Description (what to do)
3. Rationale (why it matters)
4. Implementation plan (how to do it)
5. Impact (low/medium/high)
6. Risk (low/medium/high)

Format your response as JSON array:
[
  {
    "title": "...",
    "description": "...",
    "rationale": "...",
    "implementation_plan": "...",
    "impact": "medium",
    "risk": "low"
  }
]
"""

        llm_response = self.ask_llm(prompt, context)

        if llm_response:
            try:
                # Try to parse JSON response
                # First, find JSON array in response
                start_idx = llm_response.find("[")
                end_idx = llm_response.rfind("]") + 1

                if start_idx >= 0 and end_idx > start_idx:
                    json_str = llm_response[start_idx:end_idx]
                    llm_suggestions = json.loads(json_str)

                    for llm_sug in llm_suggestions:
                        # Convert all fields to strings to handle lists
                        def to_string(val):
                            if isinstance(val, list):
                                return "\n".join(str(item) for item in val)
                            return str(val) if val else ""

                        suggestion = Suggestion(
                            id=None,
                            goal_id=goals[0].id if goals else None,
                            title=to_string(llm_sug.get("title", "Untitled")),
                            description=to_string(llm_sug.get("description", "")),
                            rationale=to_string(llm_sug.get("rationale", "")),
                            implementation_plan=to_string(llm_sug.get("implementation_plan", "")),
                            status=SuggestionStatus.PENDING,
                            priority=5,
                            estimated_impact=to_string(llm_sug.get("impact", "medium")),
                            risk_level=to_string(llm_sug.get("risk", "medium")),
                            created_at=now,
                            updated_at=now,
                            approved_at=None,
                            implemented_at=None,
                        )
                        suggestions.append(suggestion)
                        logger.info(f"Generated suggestion: {suggestion.title}")

            except Exception as e:
                logger.error(f"Error parsing LLM response: {e}")
                logger.debug(f"LLM response: {llm_response}")

        # Fallback: rule-based suggestions if LLM fails
        if not suggestions:
            if health.issues:
                for issue in health.issues[:2]:
                    suggestion = Suggestion(
                        id=None,
                        goal_id=None,
                        title=f"Fix: {issue}",
                        description=f"Address the issue: {issue}",
                        rationale="System health check identified this issue",
                        implementation_plan="Investigate and resolve the root cause",
                        status=SuggestionStatus.PENDING,
                        priority=7,
                        estimated_impact="medium",
                        risk_level="low",
                        created_at=now,
                        updated_at=now,
                        approved_at=None,
                        implemented_at=None,
                    )
                    suggestions.append(suggestion)

        # Save suggestions to database
        for suggestion in suggestions:
            self.save_suggestion(suggestion)

        return suggestions

    def save_suggestion(self, suggestion: Suggestion) -> int:
        """Save suggestion to database."""
        try:
            conn = sqlite3.connect(str(CI_DB))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO suggestions
                (goal_id, title, description, rationale, implementation_plan,
                 status, priority, estimated_impact, risk_level, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    suggestion.goal_id,
                    suggestion.title,
                    suggestion.description,
                    suggestion.rationale,
                    suggestion.implementation_plan,
                    suggestion.status,
                    suggestion.priority,
                    suggestion.estimated_impact,
                    suggestion.risk_level,
                    suggestion.created_at,
                    suggestion.updated_at,
                ),
            )

            suggestion_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return suggestion_id

        except Exception as e:
            logger.error(f"Error saving suggestion: {e}")
            return 0

    def get_goals(self, status: Optional[GoalStatus] = None) -> List[Goal]:
        """Get goals from database."""
        try:
            conn = sqlite3.connect(str(CI_DB))
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    """
                    SELECT * FROM goals
                    WHERE status = ?
                    ORDER BY priority DESC, created_at DESC
                """,
                    (status,),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM goals
                    ORDER BY priority DESC, created_at DESC
                """
                )

            rows = cursor.fetchall()
            conn.close()

            goals = []
            for row in rows:
                goal = Goal(
                    id=row[0],
                    title=row[1],
                    description=row[2],
                    status=GoalStatus(row[3]),
                    priority=row[4],
                    progress=row[5],
                    target_date=row[6],
                    dependencies=row[7],
                    created_at=row[8],
                    updated_at=row[9],
                    completed_at=row[10],
                )
                goals.append(goal)

            return goals

        except Exception as e:
            logger.error(f"Error getting goals: {e}")
            return []

    def add_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 5,
        target_date: Optional[str] = None,
    ) -> int:
        """Add a new goal."""
        try:
            conn = sqlite3.connect(str(CI_DB))
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            cursor.execute(
                """
                INSERT INTO goals
                (title, description, status, priority, progress, target_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (title, description, GoalStatus.ACTIVE, priority, 0, target_date, now, now),
            )

            goal_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Added goal #{goal_id}: {title}")
            return goal_id

        except Exception as e:
            logger.error(f"Error adding goal: {e}")
            return 0

    def run_cycle(self):
        """Run one improvement cycle."""
        logger.info("Starting improvement cycle")

        # 1. Check system health
        health = self.check_system_health()
        logger.info(
            f"System health: {health.workers_running}/{health.workers_total} workers, "
            f"{len(health.issues)} issues"
        )

        # 2. Generate suggestions if there are issues or active goals
        if health.issues or self.get_goals(status=GoalStatus.ACTIVE):
            suggestions = self.generate_suggestions(health)
            if suggestions:
                logger.info(f"Generated {len(suggestions)} improvement suggestions")

        # 3. Check for approved suggestions to implement
        # (This would be handled separately - implementation logic)

        logger.info("Improvement cycle complete")

    def run(self):
        """Main worker loop."""
        logger.info("Continuous Improvement Worker started")
        self.running = True

        # Add initial goals if none exist
        if not self.get_goals():
            logger.info("No goals found, adding initial goals")
            self.add_goal(
                "Improve local LLM response time",
                "Optimize Ollama configuration and model selection for faster responses",
                priority=8,
            )
            self.add_goal(
                "Achieve 90% worker uptime",
                "Ensure all critical workers are running consistently",
                priority=7,
            )
            self.add_goal(
                "Reduce error rate by 50%",
                "Identify and fix common errors in the system",
                priority=6,
            )

        while self.running:
            try:
                self.run_cycle()

                # Save state
                self.save_state()

                # Sleep until next check
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(60)  # Wait before retrying

        logger.info("Continuous Improvement Worker stopped")

    def save_state(self):
        """Save worker state."""
        try:
            state = {"last_check": datetime.now().isoformat(), "running": self.running}
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
    worker = ContinuousImprovementWorker()
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

    parser = argparse.ArgumentParser(description="Continuous Improvement Worker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Check status")
    parser.add_argument("--add-goal", type=str, help="Add a goal")
    parser.add_argument("--list-goals", action="store_true", help="List goals")
    parser.add_argument("--list-suggestions", action="store_true", help="List suggestions")
    parser.add_argument("--approve", type=int, help="Approve suggestion by ID")

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        check_status()
    elif args.daemon:
        start_daemon()
    elif args.add_goal:
        worker = ContinuousImprovementWorker()
        goal_id = worker.add_goal(args.add_goal)
        print(f"✅ Added goal #{goal_id}")
    elif args.list_goals:
        worker = ContinuousImprovementWorker()
        goals = worker.get_goals()
        print(f"\n📋 Goals ({len(goals)} total):\n")
        for goal in goals:
            status_emoji = "🟢" if goal.status == GoalStatus.ACTIVE else "⚪"
            print(f"{status_emoji} [{goal.priority}] {goal.title}")
            print(f"   Progress: {goal.progress}%")
            print(f"   Status: {goal.status}")
            if goal.description:
                print(f"   {goal.description}")
            print()
    elif args.list_suggestions:
        worker = ContinuousImprovementWorker()
        conn = sqlite3.connect(str(CI_DB))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM suggestions ORDER BY created_at DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()

        print(f"\n💡 Recent Suggestions ({len(rows)}):\n")
        for row in rows:
            print(f"#{row[0]} - {row[2]}")
            print(f"   Status: {row[6]} | Impact: {row[8]} | Risk: {row[9]}")
            print(f"   {row[3][:100]}...")
            print()
    else:
        # Run in foreground
        worker = ContinuousImprovementWorker()

        # Handle signals
        def signal_handler(sig, frame):
            worker.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        worker.run()


if __name__ == "__main__":
    main()
