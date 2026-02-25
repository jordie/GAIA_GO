#!/usr/bin/env python3
"""
Service Health Checker Worker

A background worker that monitors all configured services from services.json
and reports their status to the dashboard.

Usage:
    python3 service_checker.py                # Run once
    python3 service_checker.py --daemon       # Run as daemon
    python3 service_checker.py --status       # Check worker status
    python3 service_checker.py --stop         # Stop daemon
    python3 service_checker.py --check        # Run single check and print results
"""

import argparse
import json
import logging
import os
import signal
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
DATA_DIR = BASE_DIR / "data"

# Configuration
PID_FILE = Path("/tmp/service_checker.pid")
LOG_FILE = Path("/tmp/service_checker.log")
STATE_FILE = Path("/tmp/service_checker_state.json")
SERVICES_FILE = DATA_DIR / "services.json"

CHECK_INTERVAL = 60  # seconds between checks
REQUEST_TIMEOUT = 5  # seconds for HTTP requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(str(LOG_FILE)), logging.StreamHandler()],
)
logger = logging.getLogger("ServiceChecker")


def load_services_config() -> Dict[str, Any]:
    """Load services configuration from services.json."""
    if not SERVICES_FILE.exists():
        logger.warning(f"Services config not found: {SERVICES_FILE}")
        return {"apps": {}, "services": {}, "hosts": {}}

    with open(SERVICES_FILE) as f:
        return json.load(f)


def check_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is open on the given host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_http_health(url: str, timeout: float = REQUEST_TIMEOUT) -> Dict[str, Any]:
    """Check HTTP health endpoint and return status."""
    result = {"reachable": False, "status_code": None, "response_time_ms": None, "error": None}

    try:
        start = time.time()
        response = requests.get(url, timeout=timeout, verify=False)
        elapsed = (time.time() - start) * 1000

        result["reachable"] = True
        result["status_code"] = response.status_code
        result["response_time_ms"] = round(elapsed, 2)

        # Try to get health data from response
        if response.status_code == 200:
            try:
                result["health_data"] = response.json()
            except Exception:
                result["health_data"] = None

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection_refused"
    except Exception as e:
        result["error"] = str(e)

    return result


def check_service(
    service_id: str, service_config: Dict, app_config: Dict, host: str = "localhost"
) -> Dict[str, Any]:
    """Check a single service and return its status."""
    port = service_config.get("port")
    protocol = service_config.get("protocol", "http")
    health_endpoint = app_config.get("health_endpoint", "/health")

    result = {
        "service_id": service_id,
        "app": service_config.get("app"),
        "env": service_config.get("env"),
        "port": port,
        "protocol": protocol,
        "host": host,
        "timestamp": datetime.now().isoformat(),
        "port_open": False,
        "http_check": None,
        "status": "unknown",
    }

    # Check if port is open
    result["port_open"] = check_port_open(host, port)

    if not result["port_open"]:
        result["status"] = "down"
        return result

    # Check HTTP health endpoint
    url = f"{protocol}://{host}:{port}{health_endpoint}"
    result["http_check"] = check_http_health(url)

    if result["http_check"]["reachable"]:
        if result["http_check"]["status_code"] == 200:
            result["status"] = "healthy"
        elif result["http_check"]["status_code"] in (401, 403):
            result["status"] = "auth_required"
        else:
            result["status"] = "unhealthy"
    else:
        result["status"] = "unreachable"

    return result


def check_all_services(host: str = "localhost") -> Dict[str, Any]:
    """Check all configured services in parallel."""
    config = load_services_config()
    apps = config.get("apps", {})
    services = config.get("services", {})

    results = {
        "timestamp": datetime.now().isoformat(),
        "host": host,
        "services": {},
        "summary": {"total": 0, "healthy": 0, "unhealthy": 0, "down": 0, "auth_required": 0},
    }

    # Check services in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for service_id, service_config in services.items():
            app_id = service_config.get("app")
            app_config = apps.get(app_id, {})
            future = executor.submit(check_service, service_id, service_config, app_config, host)
            futures[future] = service_id

        for future in as_completed(futures):
            service_id = futures[future]
            try:
                result = future.result()
                results["services"][service_id] = result
                results["summary"]["total"] += 1

                status = result.get("status", "unknown")
                if status == "healthy":
                    results["summary"]["healthy"] += 1
                elif status == "unhealthy":
                    results["summary"]["unhealthy"] += 1
                elif status == "down":
                    results["summary"]["down"] += 1
                elif status == "auth_required":
                    results["summary"]["auth_required"] += 1

            except Exception as e:
                logger.error(f"Error checking {service_id}: {e}")
                results["services"][service_id] = {
                    "service_id": service_id,
                    "status": "error",
                    "error": str(e),
                }

    return results


def save_state(results: Dict[str, Any]):
    """Save check results to state file."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def load_state() -> Optional[Dict[str, Any]]:
    """Load last check results from state file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def report_to_dashboard(results: Dict[str, Any], dashboard_url: str = None):
    """Report service status to the dashboard API."""
    if dashboard_url is None:
        dashboard_url = os.environ.get("DASHBOARD_URL", "http://100.112.58.92:8080")
    try:
        # Post to dashboard API if available
        response = requests.post(
            f"{dashboard_url}/api/services/health-report", json=results, timeout=5
        )
        if response.status_code == 200:
            logger.debug("Reported to dashboard successfully")
    except Exception as e:
        logger.debug(f"Could not report to dashboard: {e}")


class ServiceCheckerDaemon:
    """Daemon that continuously checks services."""

    def __init__(self, check_interval: int = CHECK_INTERVAL):
        self.check_interval = check_interval
        self.running = False

    def start(self):
        """Start the daemon loop."""
        self.running = True
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info(f"Service checker started (interval: {self.check_interval}s)")

        while self.running:
            try:
                results = check_all_services()
                save_state(results)

                summary = results["summary"]
                logger.info(
                    f"Check complete: {summary['healthy']}/{summary['total']} healthy, "
                    f"{summary['down']} down, {summary['unhealthy']} unhealthy"
                )

                # Report to dashboard
                report_to_dashboard(results)

                # Alert on down services
                for service_id, status in results["services"].items():
                    if status.get("status") == "down":
                        logger.warning(f"Service DOWN: {service_id} (port {status.get('port')})")

            except Exception as e:
                logger.error(f"Check failed: {e}")

            # Sleep in small increments to respond to signals
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Service checker stopped")

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False


def daemonize():
    """Fork into background daemon."""
    if os.fork() > 0:
        sys.exit(0)

    os.setsid()

    if os.fork() > 0:
        sys.exit(0)

    # Write PID file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    log_fd = open(LOG_FILE, "a")
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())


def get_daemon_status() -> Dict[str, Any]:
    """Get daemon status."""
    status = {"running": False, "pid": None, "last_check": None}

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process is running
            os.kill(pid, 0)
            status["running"] = True
            status["pid"] = pid
        except (OSError, ValueError):
            pass

    # Get last check results
    state = load_state()
    if state:
        status["last_check"] = state.get("timestamp")
        status["summary"] = state.get("summary")

    return status


def stop_daemon():
    """Stop the daemon if running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            PID_FILE.unlink()
            logger.info(f"Stopped daemon (PID {pid})")
            return True
        except (OSError, ValueError) as e:
            logger.error(f"Failed to stop daemon: {e}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Service Health Checker")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    parser.add_argument("--status", "-s", action="store_true", help="Show daemon status")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--check", "-c", action="store_true", help="Run single check")
    parser.add_argument("--host", default="localhost", help="Host to check (default: localhost)")
    parser.add_argument(
        "--interval", type=int, default=CHECK_INTERVAL, help="Check interval in seconds"
    )

    args = parser.parse_args()

    if args.status:
        status = get_daemon_status()
        print(json.dumps(status, indent=2))
        return

    if args.stop:
        if stop_daemon():
            print("Daemon stopped")
        else:
            print("Daemon not running")
        return

    if args.check:
        # Run single check and print results
        results = check_all_services(args.host)
        print(json.dumps(results, indent=2))
        return

    if args.daemon:
        # Check if already running
        status = get_daemon_status()
        if status["running"]:
            print(f"Daemon already running (PID {status['pid']})")
            return

        print("Starting service checker daemon...")
        daemonize()

    # Run the checker
    daemon = ServiceCheckerDaemon(check_interval=args.interval)
    daemon.start()


if __name__ == "__main__":
    main()
