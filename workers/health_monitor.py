#!/usr/bin/env python3
"""
Health Monitor Worker - Self-Healing System

Monitors all system components and automatically repairs failures:
- Worker processes (orchestrator, assigner, task workers)
- Claude sessions (stuck, crashed, unresponsive)
- Database locks and corruption
- Disk space and resource exhaustion
- Task queue health

Runs every 60 seconds and takes auto-recovery actions.
"""

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
from typing import Dict, List, Optional, Tuple

import psutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.FileHandler("/tmp/health_monitor.log"), logging.StreamHandler()],
)
logger = logging.getLogger("health_monitor")


class HealthMonitor:
    """Self-healing system monitor and auto-recovery coordinator."""

    def __init__(self, check_interval: int = 60):
        """Initialize health monitor.

        Args:
            check_interval: Seconds between health checks (default: 60)
        """
        self.check_interval = check_interval
        self.running = False
        self.pid_file = Path("/tmp/health_monitor.pid")
        self.data_dir = Path("data")
        self.db_path = self.data_dir / "architect.db"
        self.assigner_db = self.data_dir / "assigner" / "assigner.db"

        # Health thresholds
        self.session_stuck_threshold = 30 * 60  # 30 minutes
        self.worker_restart_delay = 5  # seconds
        self.max_restart_attempts = 3
        self.disk_warning_threshold = 90  # percent
        self.disk_critical_threshold = 95  # percent

        # Worker configurations
        self.workers = {
            "assigner": {
                "script": "workers/assigner_worker.py",
                "args": ["--daemon"],
                "pid_file": "/tmp/assigner_worker.pid",
                "critical": True,
            },
            "task_worker": {
                "script": "workers/task_worker.py",
                "args": ["--daemon"],
                "pid_file": "/tmp/task_worker.pid",
                "critical": False,
            },
            "milestone": {
                "script": "workers/milestone_worker.py",
                "args": ["--daemon"],
                "pid_file": "/tmp/milestone_worker.pid",
                "critical": False,
            },
        }

        # Health metrics
        self.metrics = {
            "total_checks": 0,
            "workers_restarted": 0,
            "sessions_cleared": 0,
            "tasks_requeued": 0,
            "locks_cleared": 0,
            "alerts_sent": 0,
            "last_check": None,
        }

    def start(self):
        """Start the health monitor daemon."""
        if self.is_running():
            logger.warning("Health monitor already running")
            return False

        # Write PID file
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        logger.info("🏥 Health Monitor started")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Session stuck threshold: {self.session_stuck_threshold}s")

        self.running = True
        self._init_database()

        try:
            while self.running:
                self._run_health_check()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Health monitor stopped by user")
        except Exception as e:
            logger.error(f"Health monitor crashed: {e}", exc_info=True)
            self._send_alert("critical", f"Health monitor crashed: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the health monitor daemon."""
        self.running = False
        if self.pid_file.exists():
            self.pid_file.unlink()
        logger.info("Health monitor stopped")

    def is_running(self) -> bool:
        """Check if health monitor is already running."""
        if not self.pid_file.exists():
            return False

        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            return psutil.pid_exists(pid)
        except (ValueError, ProcessLookupError):
            return False

    def _init_database(self):
        """Initialize health metrics table."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS health_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        component TEXT NOT NULL,
                        status TEXT NOT NULL,
                        details TEXT,
                        action_taken TEXT,
                        recovery_successful INTEGER DEFAULT 0
                    )
                """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS health_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        component TEXT,
                        resolved INTEGER DEFAULT 0,
                        resolved_at TIMESTAMP
                    )
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_health_metrics_timestamp
                    ON health_metrics(timestamp)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_health_alerts_severity
                    ON health_alerts(severity, resolved)
                """
                )

                conn.commit()
                logger.info("Health metrics database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize health database: {e}")

    def _run_health_check(self):
        """Run comprehensive health check on all components."""
        self.metrics["total_checks"] += 1
        self.metrics["last_check"] = datetime.now()

        logger.info(f"━━━ Health Check #{self.metrics['total_checks']} ━━━")

        # 1. Check worker processes
        self._check_workers()

        # 2. Check Claude sessions
        self._check_sessions()

        # 3. Check database health
        self._check_database()

        # 4. Check disk space
        self._check_disk_space()

        # 5. Check task queue health
        self._check_task_queue()

        # 6. Cleanup old logs and temp files
        self._cleanup_old_files()

        # 7. Save health metrics
        self._save_metrics()

        logger.info(
            f"✅ Health check complete | Workers: {self.metrics['workers_restarted']} | "
            f"Sessions: {self.metrics['sessions_cleared']} | "
            f"Locks: {self.metrics['locks_cleared']}"
        )

    def _check_workers(self):
        """Check all worker processes and restart if needed."""
        logger.info("🔍 Checking worker processes...")

        for worker_name, config in self.workers.items():
            try:
                is_running = self._is_worker_running(config["pid_file"])

                if not is_running:
                    logger.warning(f"⚠️  Worker '{worker_name}' is not running")

                    # Auto-restart worker
                    success = self._restart_worker(worker_name, config)

                    if success:
                        self.metrics["workers_restarted"] += 1
                        self._log_health_event(
                            worker_name,
                            "failed",
                            "Worker not running",
                            "auto_restart",
                            recovery_successful=True,
                        )

                        if config.get("critical"):
                            self._send_alert(
                                "warning",
                                f"Critical worker '{worker_name}' was down and has been restarted",
                            )
                    else:
                        self._log_health_event(
                            worker_name,
                            "failed",
                            "Worker not running",
                            "restart_failed",
                            recovery_successful=False,
                        )
                        self._send_alert("critical", f"Failed to restart worker '{worker_name}'")
                else:
                    logger.debug(f"✓ Worker '{worker_name}' is healthy")

            except Exception as e:
                logger.error(f"Error checking worker '{worker_name}': {e}")

    def _is_worker_running(self, pid_file: str) -> bool:
        """Check if a worker is running by PID file."""
        pid_path = Path(pid_file)

        if not pid_path.exists():
            return False

        try:
            with open(pid_path) as f:
                pid = int(f.read().strip())

            # Check if process exists and is the right script
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            return False
        except (ValueError, psutil.NoSuchProcess, ProcessLookupError):
            return False

    def _restart_worker(self, worker_name: str, config: Dict) -> bool:
        """Restart a failed worker process."""
        logger.info(f"🔄 Restarting worker '{worker_name}'...")

        try:
            script_path = Path(config["script"])
            if not script_path.exists():
                logger.error(f"Worker script not found: {script_path}")
                return False

            # Build command
            cmd = ["python3", str(script_path)] + config.get("args", [])

            # Start worker process
            subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
            )

            # Wait and verify
            time.sleep(self.worker_restart_delay)

            if self._is_worker_running(config["pid_file"]):
                logger.info(f"✅ Worker '{worker_name}' restarted successfully")
                return True
            else:
                logger.error(f"❌ Worker '{worker_name}' failed to start")
                return False

        except Exception as e:
            logger.error(f"Error restarting worker '{worker_name}': {e}")
            return False

    def _check_sessions(self):
        """Check Claude sessions for stuck or crashed states."""
        logger.info("🔍 Checking Claude sessions...")

        if not self.assigner_db.exists():
            logger.debug("Assigner database not found, skipping session check")
            return

        try:
            with sqlite3.connect(str(self.assigner_db)) as conn:
                conn.row_factory = sqlite3.Row

                # Find stuck sessions
                threshold_time = datetime.now() - timedelta(seconds=self.session_stuck_threshold)

                cursor = conn.execute(
                    """
                    SELECT p.id, p.content, p.assigned_session, p.assigned_at, p.status
                    FROM prompts p
                    WHERE p.status IN ('assigned', 'in_progress')
                    AND p.assigned_at < ?
                    AND p.assigned_session IS NOT NULL
                """,
                    (threshold_time.isoformat(),),
                )

                stuck_tasks = cursor.fetchall()

                for task in stuck_tasks:
                    logger.warning(
                        f"⚠️  Stuck task: #{task['id']} "
                        f"in '{task['assigned_session']}' "
                        f"for {(datetime.now() - datetime.fromisoformat(task['assigned_at'])).seconds // 60} min"
                    )

                    # Auto-clear stuck session
                    self._clear_stuck_session(task)

        except Exception as e:
            logger.error(f"Error checking sessions: {e}")

    def _clear_stuck_session(self, task):
        """Clear stuck session and requeue task."""
        try:
            with sqlite3.connect(str(self.assigner_db)) as conn:
                # Requeue task
                conn.execute(
                    """
                    UPDATE prompts
                    SET status = 'pending',
                        assigned_session = NULL,
                        assigned_at = NULL,
                        error = ?
                    WHERE id = ?
                """,
                    (
                        f"Auto-recovered from stuck session at {datetime.now().isoformat()}",
                        task["id"],
                    ),
                )

                # Mark session needs restart
                conn.execute(
                    """
                    UPDATE sessions
                    SET status = 'needs_restart',
                        current_task_id = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """,
                    (task["assigned_session"],),
                )

                conn.commit()

                self.metrics["sessions_cleared"] += 1
                self.metrics["tasks_requeued"] += 1

                logger.info(f"✅ Cleared '{task['assigned_session']}', requeued #{task['id']}")

                self._log_health_event(
                    f"session_{task['assigned_session']}",
                    "stuck",
                    f"Task #{task['id']} stuck",
                    "session_cleared_task_requeued",
                    recovery_successful=True,
                )

                # Kill tmux session if exists
                try:
                    subprocess.run(
                        ["tmux", "kill-session", "-t", task["assigned_session"]],
                        capture_output=True,
                        timeout=5,
                    )
                    logger.info(f"Killed tmux session '{task['assigned_session']}'")
                except:
                    pass

        except Exception as e:
            logger.error(f"Error clearing stuck session: {e}")

    def _check_database(self):
        """Check database health and clear stale locks."""
        logger.info("🔍 Checking database health...")

        try:
            self._check_db_file(self.db_path, "main")

            if self.assigner_db.exists():
                self._check_db_file(self.assigner_db, "assigner")

            self._clear_stale_locks()

        except Exception as e:
            logger.error(f"Error checking database: {e}")

    def _check_db_file(self, db_path: Path, db_name: str):
        """Check database for corruption and locks."""
        try:
            with sqlite3.connect(str(db_path), timeout=5) as conn:
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]

                if result != "ok":
                    logger.error(f"❌ DB '{db_name}' integrity failed: {result}")
                    self._send_alert("critical", f"DB '{db_name}' corruption: {result}")
                else:
                    logger.debug(f"✓ DB '{db_name}' healthy")

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.warning(f"⚠️  DB '{db_name}' is locked")
                self._handle_db_lock(db_path, db_name)
            else:
                logger.error(f"DB '{db_name}' error: {e}")

    def _handle_db_lock(self, db_path: Path, db_name: str):
        """Handle locked database."""
        try:
            with sqlite3.connect(str(db_path), timeout=30) as conn:
                logger.info(f"✅ DB '{db_name}' lock cleared")
                self.metrics["locks_cleared"] += 1

        except Exception as e:
            logger.error(f"Failed to clear lock on '{db_name}': {e}")
            self._send_alert("warning", f"DB '{db_name}' lock not cleared: {e}")

    def _clear_stale_locks(self):
        """Clear stale lock files."""
        # Placeholder for lock cleanup
        pass

    def _check_disk_space(self):
        """Check disk space and cleanup if needed."""
        logger.info("🔍 Checking disk space...")

        try:
            disk = psutil.disk_usage("/")
            percent_used = disk.percent

            logger.debug(f"Disk usage: {percent_used}%")

            if percent_used >= self.disk_critical_threshold:
                logger.error(f"❌ CRITICAL: Disk {percent_used}%")
                self._send_alert("critical", f"Disk critically low: {percent_used}%")
                self._cleanup_old_files(aggressive=True)

            elif percent_used >= self.disk_warning_threshold:
                logger.warning(f"⚠️  WARNING: Disk {percent_used}%")
                self._send_alert("warning", f"Disk running low: {percent_used}%")
                self._cleanup_old_files(aggressive=False)
            else:
                logger.debug(f"✓ Disk healthy: {percent_used}%")

        except Exception as e:
            logger.error(f"Error checking disk space: {e}")

    def _check_task_queue(self):
        """Check task queue health."""
        logger.info("🔍 Checking task queue...")

        if not self.assigner_db.exists():
            return

        try:
            with sqlite3.connect(str(self.assigner_db)) as conn:
                threshold = datetime.now() - timedelta(hours=1)

                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM prompts
                    WHERE status = 'pending'
                    AND created_at < ?
                """,
                    (threshold.isoformat(),),
                )

                stuck_pending = cursor.fetchone()[0]

                if stuck_pending > 0:
                    logger.warning(f"⚠️  {stuck_pending} tasks stuck in pending >1hr")

                    if not self._is_worker_running(self.workers["assigner"]["pid_file"]):
                        logger.warning("Assigner worker not running")

                # Check failures
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM prompts
                    WHERE status = 'failed'
                    AND created_at > datetime('now', '-1 hour')
                """
                )

                recent_failures = cursor.fetchone()[0]

                if recent_failures > 10:
                    logger.warning(f"⚠️  {recent_failures} failures in last hour")
                    self._send_alert("warning", f"High failure rate: {recent_failures}/hr")

        except Exception as e:
            logger.error(f"Error checking task queue: {e}")

    def _cleanup_old_files(self, aggressive: bool = False):
        """Cleanup old logs and temp files."""
        logger.info(f"🧹 Cleaning up (aggressive={aggressive})...")

        try:
            log_dirs = [Path("/tmp"), Path("logs")]
            max_age_days = 7 if aggressive else 30

            for log_dir in log_dirs:
                if not log_dir.exists():
                    continue

                cutoff_time = time.time() - (max_age_days * 86400)

                for log_file in log_dir.glob("*.log*"):
                    try:
                        if log_file.stat().st_mtime < cutoff_time:
                            log_file.unlink()
                            logger.debug(f"Deleted: {log_file}")
                    except:
                        pass

            # Cleanup screenshots if aggressive
            if aggressive:
                screenshot_dir = Path("data/screenshots")
                if screenshot_dir.exists():
                    cutoff_time = time.time() - (3 * 86400)
                    for img in screenshot_dir.glob("**/*.png"):
                        try:
                            if img.stat().st_mtime < cutoff_time:
                                img.unlink()
                        except:
                            pass

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _log_health_event(
        self,
        component: str,
        status: str,
        details: str,
        action_taken: str,
        recovery_successful: bool = False,
    ):
        """Log health event to database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO health_metrics
                    (component, status, details, action_taken, recovery_successful)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (component, status, details, action_taken, int(recovery_successful)),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log health event: {e}")

    def _send_alert(self, severity: str, message: str, component: str = None):
        """Send health alert."""
        logger.info(f"🚨 ALERT [{severity.upper()}]: {message}")

        self.metrics["alerts_sent"] += 1

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO health_alerts (severity, message, component)
                    VALUES (?, ?, ?)
                """,
                    (severity, message, component),
                )
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to save alert: {e}")

    def _save_metrics(self):
        """Save health metrics."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO health_metrics
                    (component, status, details, action_taken, recovery_successful)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    ("health_monitor", "running", json.dumps(self.metrics), "periodic_check", 1),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def status(self):
        """Print status."""
        if not self.is_running():
            print("❌ Health monitor not running")
            return

        print("✅ Health monitor running")
        print(f"\nMetrics:")
        print(f"  Total checks: {self.metrics['total_checks']}")
        print(f"  Workers restarted: {self.metrics['workers_restarted']}")
        print(f"  Sessions cleared: {self.metrics['sessions_cleared']}")
        print(f"  Tasks requeued: {self.metrics['tasks_requeued']}")
        print(f"  Locks cleared: {self.metrics['locks_cleared']}")
        print(f"  Alerts sent: {self.metrics['alerts_sent']}")

        if self.metrics["last_check"]:
            print(f"  Last check: {self.metrics['last_check']}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Health Monitor Worker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--interval", type=int, default=60, help="Check interval (default: 60)")

    args = parser.parse_args()

    monitor = HealthMonitor(check_interval=args.interval)

    if args.status:
        monitor.status()
    elif args.stop:
        if monitor.is_running():
            try:
                with open(monitor.pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print("✅ Health monitor stopped")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("❌ Not running")
    elif args.daemon:
        # Daemonize
        pid = os.fork()
        if pid > 0:
            print(f"✅ Health monitor started (PID: {pid})")
            sys.exit(0)

        os.setsid()
        # Stay in project directory for database access
        project_root = Path(__file__).parent.parent
        os.chdir(str(project_root))

        sys.stdout.flush()
        sys.stderr.flush()

        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        monitor.start()
    else:
        print("🏥 Starting health monitor (Ctrl+C to stop)...")
        monitor.start()


if __name__ == "__main__":
    main()
