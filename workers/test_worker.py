#!/usr/bin/env python3
"""
Centralized Test Worker

Runs data-driven tests for ALL applications.
Test specifics come from test data files, NOT code.

Usage:
    python3 test_worker.py                    # Run worker
    python3 test_worker.py --daemon           # Run as daemon
    python3 test_worker.py --run-suite <id>   # Run specific suite
    python3 test_worker.py --list             # List available suites
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from testing import TestRunner, load_all_suites, load_test_suite
from testing.models import SuiteResult, TestStatus

# Configuration
TAILSCALE_IP = os.environ.get("TAILSCALE_IP", "100.112.58.92")
DASHBOARD_URL = os.environ.get("ARCHITECT_URL", f"http://{TAILSCALE_IP}:8080")
VAULT_URL = os.environ.get("VAULT_URL", f"http://{TAILSCALE_IP}:9000")
TEST_DATA_DIR = BASE_DIR / "test_data"
DB_PATH = BASE_DIR / "data" / "prod" / "architect.db"
DB_TIMEOUT = 30


def get_db_connection(db_path=None, timeout=DB_TIMEOUT):
    """Get database connection with WAL mode and proper timeout."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


PID_FILE = Path("/tmp/architect_test_worker.pid")
LOG_FILE = Path("/tmp/architect_test_worker.log")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("TestWorker")


class TestWorker:
    """
    Centralized test worker that runs data-driven tests.

    The worker:
    1. Claims 'test' tasks from the architect task queue
    2. Loads test suite from test_data directory
    3. Runs tests using the TestRunner
    4. Reports results back to architect
    """

    def __init__(self, worker_id: str = None, poll_interval: int = 10, headless: bool = True):
        import uuid

        self.worker_id = worker_id or f"test-worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self.headless = headless
        self.vault_token = None

        self._running = False
        self._current_task = None

    def start(self):
        """Start the worker."""
        self._running = True
        logger.info(f"Starting Test Worker: {self.worker_id}")
        logger.info(f"Dashboard: {DASHBOARD_URL}")
        logger.info(f"Vault: {VAULT_URL}")
        logger.info(f"Test Data: {TEST_DATA_DIR}")

        # Get vault token
        self._get_vault_token()

        # Register with dashboard
        self._register()

        # Main loop
        while self._running:
            try:
                # Heartbeat
                self._heartbeat()

                # Claim task
                task = self._claim_task()

                if task:
                    self._current_task = task
                    logger.info(f"Processing test task: {task.get('id')}")

                    try:
                        result = asyncio.run(self._run_test_task(task))
                        self._complete_task(task["id"], result)
                    except Exception as e:
                        logger.error(f"Test task failed: {e}")
                        self._fail_task(task["id"], str(e))
                    finally:
                        self._current_task = None
                else:
                    time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                self._running = False
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(5)

        logger.info("Test Worker stopped")

    def stop(self):
        """Stop the worker."""
        self._running = False

    def _get_vault_token(self):
        """Get vault authentication token."""
        try:
            import requests

            resp = requests.post(
                f"{VAULT_URL}/api/tokens",
                json={"environment": os.environ.get("APP_ENV", "dev")},
                timeout=5,
            )
            if resp.status_code == 200:
                self.vault_token = resp.json()["token"]
                logger.info("Authenticated with vault")
        except Exception as e:
            logger.warning(f"Could not get vault token: {e}")

    def _register(self):
        """Register with architect dashboard."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/workers/register",
                json={
                    "id": self.worker_id,
                    "worker_type": "test",
                    "capabilities": ["test", "browser_test", "api_test"],
                },
                timeout=5,
            )
            logger.info("Registered with dashboard")
        except Exception as e:
            logger.warning(f"Could not register: {e}")

    def _heartbeat(self):
        """Send heartbeat."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/workers/{self.worker_id}/heartbeat",
                json={
                    "status": "busy" if self._current_task else "idle",
                    "current_task_id": self._current_task.get("id") if self._current_task else None,
                },
                timeout=5,
            )
        except Exception:
            pass

    def _claim_task(self) -> Optional[Dict]:
        """Claim a test task from the queue."""
        try:
            import requests

            resp = requests.post(
                f"{DASHBOARD_URL}/api/tasks/claim",
                json={
                    "worker_id": self.worker_id,
                    "task_types": ["test", "browser_test", "api_test"],
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("task")
            return None
        except Exception:
            return None

    def _complete_task(self, task_id: int, result: Dict):
        """Mark task completed."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/tasks/{task_id}/complete",
                json={"worker_id": self.worker_id, "result": result},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Could not complete task: {e}")

    def _fail_task(self, task_id: int, error: str):
        """Mark task failed."""
        try:
            import requests

            requests.post(
                f"{DASHBOARD_URL}/api/tasks/{task_id}/fail",
                json={"worker_id": self.worker_id, "error": error},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Could not fail task: {e}")

    async def _run_test_task(self, task: Dict) -> Dict:
        """Run a test task."""
        task_data = task.get("task_data", {})

        # What kind of test?
        suite_id = task_data.get("suite_id")
        test_id = task_data.get("test_id")
        suite_file = task_data.get("suite_file")
        service_id = task_data.get("service_id")
        tags = task_data.get("tags", [])

        # Load test suite
        suite = None
        if suite_file:
            suite = load_test_suite(str(TEST_DATA_DIR / suite_file))
        elif suite_id:
            for s in load_all_suites(str(TEST_DATA_DIR)):
                if s.id == suite_id:
                    suite = s
                    break
        elif service_id:
            for s in load_all_suites(str(TEST_DATA_DIR)):
                if s.target_service == service_id:
                    suite = s
                    break

        if not suite:
            return {"success": False, "error": "Test suite not found"}

        # Filter by test_id or tags if specified
        if test_id:
            suite.test_cases = [tc for tc in suite.test_cases if tc.id == test_id]
        elif tags:
            suite.test_cases = [tc for tc in suite.test_cases if any(t in tc.tags for t in tags)]

        # Run tests
        runner = TestRunner(
            vault_url=VAULT_URL, vault_token=self.vault_token, headless=self.headless
        )

        result = await runner.execute_suite(suite)

        # Store results in database
        self._store_results(result)

        return result.to_dict()

    def _store_results(self, result: SuiteResult):
        """Store test results in database."""
        try:
            with get_db_connection() as conn:
                # Store suite result
                conn.execute(
                    """
                    INSERT INTO test_runs
                    (run_id, environment, triggered_by, status, total_tests,
                     passed, failed, skipped, duration_seconds, started_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        os.environ.get("APP_ENV", "dev"),
                        self.worker_id,
                        result.status.value,
                        result.total,
                        result.passed,
                        result.failed,
                        result.skipped,
                        result.duration,
                        result.started_at,
                        result.completed_at,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Could not store results: {e}")


def list_suites():
    """List available test suites."""
    print("\n=== Available Test Suites ===\n")
    suites = load_all_suites(str(TEST_DATA_DIR))
    for suite in suites:
        print(f"  {suite.id}")
        print(f"    Name: {suite.name}")
        print(f"    Service: {suite.target_service}")
        print(f"    Tests: {len(suite.test_cases)}")
        print(f"    Tags: {', '.join(suite.tags)}")
        print()


async def run_suite(suite_id: str, headless: bool = True):
    """Run a specific test suite."""
    print(f"\n=== Running Suite: {suite_id} ===\n")

    # Get vault token
    vault_token = None
    try:
        import requests

        resp = requests.post(f"{VAULT_URL}/api/tokens", json={"environment": "dev"}, timeout=5)
        if resp.status_code == 200:
            vault_token = resp.json()["token"]
    except Exception:
        pass

    # Find suite
    suite = None
    for s in load_all_suites(str(TEST_DATA_DIR)):
        if s.id == suite_id:
            suite = s
            break

    if not suite:
        print(f"Suite not found: {suite_id}")
        return

    # Run
    runner = TestRunner(vault_url=VAULT_URL, vault_token=vault_token, headless=headless)

    result = await runner.execute_suite(suite)

    # Print results
    print(f"\n=== Results ===\n")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration:.2f}s")
    print(f"Passed: {result.passed}/{result.total}")
    print(f"Failed: {result.failed}")
    print()

    for tr in result.test_results:
        status_icon = "✓" if tr.status == TestStatus.PASSED else "✗"
        print(f"  {status_icon} {tr.test_case.name}: {tr.status.value}")
        if tr.error:
            print(f"      Error: {tr.error}")


def main():
    parser = argparse.ArgumentParser(description="Centralized Test Worker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--list", action="store_true", help="List test suites")
    parser.add_argument("--run-suite", type=str, help="Run specific suite")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--visible", action="store_true", help="Show browser")
    args = parser.parse_args()

    if args.list:
        list_suites()
        return

    if args.run_suite:
        asyncio.run(run_suite(args.run_suite, headless=not args.visible))
        return

    if args.daemon:
        # Daemonize
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        PID_FILE.write_text(str(os.getpid()))

    worker = TestWorker(headless=not args.visible)

    def signal_handler(sig, frame):
        worker.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    worker.start()


if __name__ == "__main__":
    main()
