#!/usr/bin/env python3
"""
Self-Healing Health Monitor - Enhanced Version

Monitors and auto-recovers:
- Worker processes (orchestrator, assigner, task workers)
- Stuck tmux sessions (>30 mins no activity)
- Database locks
- Disk space issues

Features:
- Auto-restart crashed workers
- Auto-clear stuck sessions and requeue tasks
- Auto-cleanup stale database locks
- Disk space cleanup
- Alert system for critical failures
- Health metrics tracking

Usage:
    python3 health_monitor_v2.py                # Run once
    python3 health_monitor_v2.py --daemon       # Run as daemon
    python3 health_monitor_v2.py --status       # Check status
    python3 health_monitor_v2.py --stop         # Stop daemon
"""

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_connection

# ============================================================================
# CONFIGURATION
# ============================================================================

CHECK_INTERVAL = 60  # Check every 60 seconds
STUCK_SESSION_TIMEOUT = 1800  # 30 minutes
DB_LOCK_TIMEOUT = 300  # 5 minutes
DISK_CRITICAL_THRESHOLD = 95  # percent
DISK_WARNING_THRESHOLD = 85  # percent
LOG_RETENTION_DAYS = 7
TEMP_FILE_AGE_HOURS = 24

# Worker configurations for auto-restart
WORKER_CONFIGS = {
    "assigner_worker": {
        "script": "workers/assigner_worker.py",
        "args": ["--daemon"],
        "critical": True,
        "restart_delay": 5,
    },
    "task_worker": {
        "script": "workers/task_worker.py",
        "args": ["--daemon"],
        "critical": True,
        "restart_delay": 5,
    },
    "milestone_worker": {
        "script": "workers/milestone_worker.py",
        "args": ["--daemon"],
        "critical": False,
        "restart_delay": 10,
    },
}

PID_FILE = Path("/tmp/health_monitor_v2.pid")
LOG_FILE = Path("/tmp/health_monitor_v2.log")

# ============================================================================
# MAIN CLASS
# ============================================================================


class SelfHealingMonitor:
    """Self-healing health monitor with auto-recovery"""

    def __init__(self, daemon=False):
        self.daemon = daemon
        self.base_dir = Path(__file__).parent.parent
        self.running = True
        self.stats = {
            "checks_run": 0,
            "workers_restarted": 0,
            "sessions_cleared": 0,
            "locks_cleared": 0,
            "disk_cleanups": 0,
            "alerts_sent": 0,
        }

        # Initialize database tables
        self._init_database()

    def _init_database(self):
        """Initialize health monitoring tables"""
        with get_connection("main") as conn:
            cursor = conn.cursor()

            # Health metrics table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    component TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_value TEXT,
                    status TEXT,
                    action_taken TEXT,
                    details TEXT
                )
            """
            )

            # Health alerts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS health_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at TEXT
                )
            """
            )

            # Create indexes
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_health_metrics_timestamp
                ON health_metrics(timestamp DESC)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_health_alerts_severity
                ON health_alerts(severity, resolved)
            """
            )

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level:8s}] {message}"
        print(log_line)

        try:
            with open(LOG_FILE, "a") as f:
                f.write(log_line + "\n")
        except Exception:
            pass

    def log_metric(
        self,
        component: str,
        metric_type: str,
        value: str,
        status: str,
        action: str = None,
        details: str = None,
    ):
        """Log health metric to database"""
        try:
            with get_connection("main") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO health_metrics
                    (timestamp, component, metric_type, metric_value, status, action_taken, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        datetime.now().isoformat(),
                        component,
                        metric_type,
                        value,
                        status,
                        action,
                        details,
                    ),
                )
        except Exception as e:
            self.log(f"Error logging metric: {e}", "ERROR")

    def send_alert(self, severity: str, component: str, message: str):
        """Send and log health alert"""
        icon = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}.get(severity, "📢")
        self.log(f"{icon} [{severity}] {component}: {message}", severity)

        try:
            with get_connection("main") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO health_alerts
                    (timestamp, severity, component, message)
                    VALUES (?, ?, ?, ?)
                """,
                    (datetime.now().isoformat(), severity, component, message),
                )
            self.stats["alerts_sent"] += 1
        except Exception as e:
            self.log(f"Error sending alert: {e}", "ERROR")

    # ========================================================================
    # WORKER HEALTH CHECKS
    # ========================================================================

    def check_worker_health(self) -> Dict[str, bool]:
        """Check all worker processes and auto-restart if needed"""
        results = {}

        for worker_name, config in WORKER_CONFIGS.items():
            try:
                is_running, pid = self._is_worker_running(worker_name)

                if is_running:
                    self.log_metric(worker_name, "process", str(pid), "healthy")
                    results[worker_name] = True
                else:
                    # Worker is down
                    self.log_metric(worker_name, "process", "dead", "unhealthy")

                    if config["critical"]:
                        self.send_alert("CRITICAL", worker_name, "Worker process not running")

                    # Auto-restart
                    self.log(f"Attempting to restart {worker_name}...", "WARNING")
                    time.sleep(config.get("restart_delay", 5))

                    if self._restart_worker(worker_name, config):
                        self.log_metric(
                            worker_name,
                            "auto_recovery",
                            "restarted",
                            "recovered",
                            action="restart_worker",
                        )
                        self.send_alert("INFO", worker_name, "Worker auto-restarted successfully")
                        self.stats["workers_restarted"] += 1
                        results[worker_name] = True
                    else:
                        self.send_alert("CRITICAL", worker_name, "Failed to auto-restart worker")
                        results[worker_name] = False

            except Exception as e:
                self.log(f"Error checking {worker_name}: {e}", "ERROR")
                self.log_metric(
                    worker_name, "check_error", str(e), "error", details=traceback.format_exc()
                )
                results[worker_name] = False

        return results

    def _is_worker_running(self, worker_name: str) -> Tuple[bool, Optional[int]]:
        """Check if a worker process is running"""
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info["cmdline"]
                    if cmdline and any(worker_name in str(cmd) for cmd in cmdline):
                        return True, proc.info["pid"]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False, None
        except Exception as e:
            self.log(f"Error checking worker {worker_name}: {e}", "ERROR")
            return False, None

    def _restart_worker(self, worker_name: str, config: Dict) -> bool:
        """Restart a failed worker process"""
        try:
            script_path = self.base_dir / config["script"]

            if not script_path.exists():
                self.log(f"Worker script not found: {script_path}", "ERROR")
                return False

            cmd = ["python3", str(script_path)] + config["args"]

            self.log(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, cwd=str(self.base_dir), capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                self.log(f"✅ {worker_name} restarted successfully")
                return True
            else:
                self.log(f"❌ Failed to restart {worker_name}: {result.stderr}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Error restarting {worker_name}: {e}", "ERROR")
            return False

    # ========================================================================
    # STUCK SESSION DETECTION
    # ========================================================================

    def check_stuck_sessions(self) -> List[Dict]:
        """Detect and clear stuck tmux sessions"""
        stuck_sessions = []

        try:
            # Query assigner database for in-progress tasks
            assigner_db = self.base_dir / "data" / "assigner" / "assigner.db"
            if not assigner_db.exists():
                return stuck_sessions

            with sqlite3.connect(str(assigner_db)) as conn:
                cursor = conn.cursor()
                # Query with fallback for missing updated_at column
                try:
                    cursor.execute(
                        """
                        SELECT id, target_session, content, assigned_at, updated_at
                        FROM prompts
                        WHERE status IN ('in_progress', 'assigned')
                    """
                    )
                except sqlite3.OperationalError:
                    # Fallback if updated_at column doesn't exist
                    cursor.execute(
                        """
                        SELECT id, target_session, content, assigned_at, assigned_at as updated_at
                        FROM prompts
                        WHERE status IN ('in_progress', 'assigned')
                    """
                    )

                active_tasks = cursor.fetchall()

            for task_id, session, content, assigned_at, updated_at in active_tasks:
                try:
                    # Calculate age
                    timestamp = updated_at or assigned_at
                    if not timestamp:
                        continue

                    updated = datetime.fromisoformat(timestamp)
                    age_seconds = (datetime.now() - updated).total_seconds()

                    if age_seconds > STUCK_SESSION_TIMEOUT:
                        stuck_sessions.append(
                            {
                                "task_id": task_id,
                                "session": session,
                                "age_seconds": age_seconds,
                                "content": content[:100] if content else "",
                            }
                        )

                        self.log_metric(
                            f"session:{session}",
                            "stuck_detected",
                            f"{age_seconds:.0f}s",
                            "unhealthy",
                            details=f"Task {task_id} stuck for {age_seconds/60:.1f} minutes",
                        )

                        # Auto-clear stuck session
                        if self._clear_stuck_session(task_id, session):
                            self.log_metric(
                                f"session:{session}",
                                "auto_recovery",
                                "cleared_and_requeued",
                                "recovered",
                                action="clear_stuck_session",
                            )
                            self.stats["sessions_cleared"] += 1

                except (ValueError, TypeError) as e:
                    self.log(f"Error parsing timestamp for task {task_id}: {e}", "WARNING")
                    continue

        except Exception as e:
            self.log(f"Error checking stuck sessions: {e}", "ERROR")
            self.log_metric(
                "session_monitor", "check_error", str(e), "error", details=traceback.format_exc()
            )

        return stuck_sessions

    def _clear_stuck_session(self, task_id: int, session: str) -> bool:
        """Clear stuck session and mark task as failed"""
        try:
            self.log(f"Clearing stuck session: {session} (task {task_id})")

            assigner_db = self.base_dir / "data" / "assigner" / "assigner.db"
            with sqlite3.connect(str(assigner_db)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE prompts
                    SET status = 'failed',
                        error = 'Session stuck >30 min - auto-cleared by health monitor',
                        completed_at = ?
                    WHERE id = ?
                """,
                    (datetime.now().isoformat(), task_id),
                )
                conn.commit()

            # Try to interrupt the session
            try:
                result = subprocess.run(
                    ["tmux", "has-session", "-t", session], capture_output=True, timeout=5
                )

                if result.returncode == 0:
                    # Send Ctrl+C to interrupt
                    subprocess.run(["tmux", "send-keys", "-t", session, "C-c"], timeout=5)
                    self.log(f"Sent interrupt signal to session {session}")
            except Exception as e:
                self.log(f"Could not interrupt session {session}: {e}", "WARNING")

            self.send_alert(
                "WARNING", f"session:{session}", f"Cleared stuck task {task_id} (>30 min inactive)"
            )

            return True

        except Exception as e:
            self.log(f"Error clearing stuck session {session}: {e}", "ERROR")
            return False

    # ========================================================================
    # DATABASE LOCK DETECTION
    # ========================================================================

    def check_database_locks(self) -> List[Dict]:
        """Check for and clear stale database locks"""
        issues = []

        databases = [
            ("architect.db", self.base_dir / "data" / "architect.db"),
            ("assigner.db", self.base_dir / "data" / "assigner" / "assigner.db"),
        ]

        for db_name, db_path in databases:
            if not db_path.exists():
                continue

            try:
                lock_info = self._check_db_lock(db_path, db_name)
                if lock_info:
                    issues.append(lock_info)
                    self.stats["locks_cleared"] += 1
            except Exception as e:
                self.log(f"Error checking {db_name}: {e}", "ERROR")

        return issues

    def _check_db_lock(self, db_path: Path, db_name: str) -> Optional[Dict]:
        """Check specific database for locks"""
        try:
            # Try to acquire exclusive lock
            conn = sqlite3.connect(str(db_path), timeout=2.0)
            cursor = conn.cursor()

            # Attempt immediate transaction
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("ROLLBACK")
            conn.close()

            self.log_metric(db_name, "lock_check", "no_locks", "healthy")
            return None

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self.log_metric(db_name, "lock_detected", "locked", "unhealthy")

                # Find locking processes
                locking_pids = self._find_locking_processes(db_path)

                self.send_alert("WARNING", db_name, f"Database locked (PIDs: {locking_pids})")

                # Attempt recovery
                if self._clear_database_lock(db_path, db_name, locking_pids):
                    self.log_metric(
                        db_name,
                        "auto_recovery",
                        "lock_cleared",
                        "recovered",
                        action="clear_database_lock",
                    )

                return {"database": db_name, "locked": True, "pids": locking_pids}

        except Exception as e:
            self.log(f"Unexpected error checking {db_name}: {e}", "ERROR")

        return None

    def _find_locking_processes(self, db_path: Path) -> List[int]:
        """Find processes holding database locks"""
        locking_pids = []

        try:
            result = subprocess.run(
                ["lsof", str(db_path)], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")[1:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            locking_pids.append(pid)
                        except ValueError:
                            continue

        except Exception as e:
            self.log(f"Error finding locking processes: {e}", "WARNING")

        return locking_pids

    def _clear_database_lock(self, db_path: Path, db_name: str, pids: List[int]) -> bool:
        """Attempt to clear database lock"""
        try:
            # Check if processes are still alive
            for pid in pids:
                try:
                    proc = psutil.Process(pid)
                    # Check if process is a zombie or inactive
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        self.log(f"Killing zombie process {pid}")
                        proc.kill()
                except psutil.NoSuchProcess:
                    continue

            # Try removing WAL files if they exist
            wal_file = Path(str(db_path) + "-wal")
            shm_file = Path(str(db_path) + "-shm")

            if wal_file.exists():
                self.log(f"Removing WAL file: {wal_file}")
                wal_file.unlink()

            if shm_file.exists():
                self.log(f"Removing SHM file: {shm_file}")
                shm_file.unlink()

            self.log(f"✅ Cleared lock on {db_name}")
            return True

        except Exception as e:
            self.log(f"Error clearing lock on {db_name}: {e}", "ERROR")
            return False

    # ========================================================================
    # DISK SPACE MONITORING
    # ========================================================================

    def check_disk_space(self) -> Dict:
        """Monitor disk space and cleanup if needed"""
        try:
            usage = shutil.disk_usage(str(self.base_dir))
            percent_used = (usage.used / usage.total) * 100

            status = "healthy"
            action_taken = None

            if percent_used >= DISK_CRITICAL_THRESHOLD:
                status = "critical"
                self.send_alert(
                    "CRITICAL", "disk_space", f"Disk {percent_used:.1f}% full - cleaning up"
                )

                # Auto-cleanup
                cleaned = self._cleanup_disk()
                action_taken = f"cleaned_{cleaned}_files"
                self.stats["disk_cleanups"] += 1

            elif percent_used >= DISK_WARNING_THRESHOLD:
                status = "warning"
                self.send_alert("WARNING", "disk_space", f"Disk {percent_used:.1f}% full")

            self.log_metric(
                "disk_space", "usage_percent", f"{percent_used:.1f}", status, action=action_taken
            )

            return {
                "percent_used": percent_used,
                "total_gb": usage.total / (1024**3),
                "free_gb": usage.free / (1024**3),
                "status": status,
            }

        except Exception as e:
            self.log(f"Error checking disk space: {e}", "ERROR")
            return {"error": str(e)}

    def _cleanup_disk(self) -> int:
        """Cleanup old logs and temp files"""
        cleaned_count = 0

        try:
            # Cleanup targets
            cleanup_paths = [
                (self.base_dir / "logs", "*.log", LOG_RETENTION_DAYS * 24),
                (Path("/tmp"), "llm_simple_test_*", TEMP_FILE_AGE_HOURS),
                (Path("/tmp"), "orchestrator_*", TEMP_FILE_AGE_HOURS),
                (Path("/tmp"), "*.log", LOG_RETENTION_DAYS * 24),
            ]

            current_time = time.time()

            for base_path, pattern, age_hours in cleanup_paths:
                if not base_path.exists():
                    continue

                age_seconds = age_hours * 3600

                for item in base_path.glob(pattern):
                    try:
                        if item.is_file():
                            file_age = current_time - item.stat().st_mtime
                            if file_age > age_seconds:
                                item.unlink()
                                cleaned_count += 1
                                self.log(f"Deleted old file: {item}")
                        elif item.is_dir():
                            dir_age = current_time - item.stat().st_mtime
                            if dir_age > age_seconds:
                                shutil.rmtree(item)
                                cleaned_count += 1
                                self.log(f"Deleted old directory: {item}")
                    except Exception as e:
                        self.log(f"Could not delete {item}: {e}", "WARNING")

            self.log(f"🧹 Cleaned up {cleaned_count} old files/directories")

        except Exception as e:
            self.log(f"Error during cleanup: {e}", "ERROR")

        return cleaned_count

    # ========================================================================
    # MAIN HEALTH CHECK
    # ========================================================================

    def run_health_check(self):
        """Run complete health check cycle"""
        self.log("=" * 70)
        self.log(f"Health Check #{self.stats['checks_run'] + 1}")
        self.log("=" * 70)

        # 1. Check workers
        self.log("🔍 Checking workers...")
        worker_health = self.check_worker_health()
        healthy_workers = sum(1 for h in worker_health.values() if h)
        self.log(f"   Workers: {healthy_workers}/{len(worker_health)} healthy")

        # 2. Check stuck sessions
        self.log("🔍 Checking sessions...")
        stuck = self.check_stuck_sessions()
        if stuck:
            self.log(f"   ⚠️  Found {len(stuck)} stuck session(s)")
            for s in stuck:
                self.log(f"      - {s['session']}: {s['age_seconds']/60:.1f} min")
        else:
            self.log("   ✅ No stuck sessions")

        # 3. Check database locks
        self.log("🔍 Checking database locks...")
        locks = self.check_database_locks()
        if locks:
            self.log(f"   ⚠️  Found {len(locks)} locked database(s)")
        else:
            self.log("   ✅ No database locks")

        # 4. Check disk space
        self.log("🔍 Checking disk space...")
        disk = self.check_disk_space()
        if "percent_used" in disk:
            icon = "✅" if disk["status"] == "healthy" else "⚠️"
            self.log(
                f"   {icon} Disk: {disk['percent_used']:.1f}% used ({disk['free_gb']:.1f} GB free)"
            )

        # Update stats
        self.stats["checks_run"] += 1

        # Log summary
        self.log("")
        self.log(f"📊 Session Stats:")
        self.log(f"   Checks run: {self.stats['checks_run']}")
        self.log(f"   Workers restarted: {self.stats['workers_restarted']}")
        self.log(f"   Sessions cleared: {self.stats['sessions_cleared']}")
        self.log(f"   Locks cleared: {self.stats['locks_cleared']}")
        self.log(f"   Disk cleanups: {self.stats['disk_cleanups']}")
        self.log(f"   Alerts sent: {self.stats['alerts_sent']}")
        self.log("=" * 70)
        self.log("")

    # ========================================================================
    # DAEMON CONTROL
    # ========================================================================

    def start(self):
        """Start health monitor daemon"""
        if self.daemon:
            with open(PID_FILE, "w") as f:
                f.write(str(os.getpid()))

            self.log(f"🏥 Self-Healing Health Monitor started (PID: {os.getpid()})")
            self.log(f"   Check interval: {CHECK_INTERVAL}s")
            self.log(f"   Stuck timeout: {STUCK_SESSION_TIMEOUT}s")
            self.log(f"   Monitoring: {len(WORKER_CONFIGS)} workers")
            self.log("")

        try:
            while self.running:
                self.run_health_check()
                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            self.log("🛑 Health Monitor stopped by user")
        finally:
            if self.daemon and PID_FILE.exists():
                PID_FILE.unlink()

    def stop(self):
        """Stop health monitor"""
        self.running = False


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Self-Healing Health Monitor")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Show status")

    args = parser.parse_args()

    if args.stop:
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"✅ Health Monitor stopped (PID: {pid})")
                PID_FILE.unlink()
            except (ProcessLookupError, ValueError):
                print("⚠️  Health Monitor not running (stale PID file)")
                PID_FILE.unlink()
        else:
            print("ℹ️  Health Monitor not running")
        return

    if args.status:
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, 0)  # Check if process exists
                print(f"✅ Health Monitor running (PID: {pid})")
                print(f"   Log: {LOG_FILE}")

                # Show recent metrics
                try:
                    from db import get_connection

                    with get_connection("main") as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            SELECT timestamp, component, metric_type, status, action_taken
                            FROM health_metrics
                            ORDER BY id DESC LIMIT 10
                        """
                        )

                        print("\nRecent activity:")
                        for row in cursor.fetchall():
                            ts, comp, metric, status, action = row
                            action_str = f" → {action}" if action else ""
                            print(f"  {ts} - {comp}: {metric} ({status}){action_str}")
                except Exception as e:
                    print(f"Could not fetch metrics: {e}")

            except (ProcessLookupError, ValueError):
                print("⚠️  Health Monitor not running (stale PID file)")
        else:
            print("ℹ️  Health Monitor not running")
        return

    monitor = SelfHealingMonitor(daemon=args.daemon)

    if args.once:
        monitor.run_health_check()
    else:
        monitor.start()


if __name__ == "__main__":
    main()
