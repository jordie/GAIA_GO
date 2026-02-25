#!/usr/bin/env python3
"""
Health Daemon for Architect Dashboard (Port 8085)
Monitors https://100.112.58.92:8085/health and auto-restarts if down

Usage:
    python3 health_daemon.py          # Run in foreground
    python3 health_daemon.py --daemon # Run in background
    python3 health_daemon.py --stop   # Stop daemon
    python3 health_daemon.py --status # Show status
"""

import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Configuration
PORT = 8085
HEALTH_URL = "http://100.112.58.92:8085/health"  # Changed to HTTP
CHECK_INTERVAL = 30  # seconds
MAX_FAILURES = 3  # consecutive failures before restart
STARTUP_WAIT = 5  # seconds to wait after restart

SCRIPT_DIR = Path(__file__).parent
APP_DIR = SCRIPT_DIR.parent
PID_FILE = Path("/tmp/health_daemon_8085.pid")
LOG_FILE = Path("/tmp/health_daemon_8085.log")

START_CMD = f"cd {APP_DIR} && nohup python3 app.py --port {PORT} > /tmp/architect_{PORT}.log 2>&1 &"  # No --ssl


def log(level, msg):
    """Write log entry."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {msg}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def check_health():
    """Check if health endpoint responds with 200."""
    try:
        result = subprocess.run(
            [
                "curl",
                "-sk",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--connect-timeout",
                "5",
                "--max-time",
                "10",
                HEALTH_URL,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip() == "200"
    except:
        return False


def restart_service():
    """Restart the service."""
    log("WARN", f"Restarting service on port {PORT}...")

    # Kill existing process
    try:
        result = subprocess.run(["lsof", "-ti", f":{PORT}"], capture_output=True, text=True)
        if result.stdout.strip():
            pid = result.stdout.strip().split("\n")[0]
            log("INFO", f"Killing existing process (PID: {pid})")
            subprocess.run(["kill", "-9", pid], capture_output=True)
            time.sleep(2)
    except:
        pass

    # Start service
    log("INFO", f"Starting service...")
    subprocess.Popen(START_CMD, shell=True, cwd=APP_DIR)

    # Wait for startup
    time.sleep(STARTUP_WAIT)

    # Verify
    if check_health():
        log("INFO", f"Service restarted successfully on port {PORT}")
        return True
    else:
        log("ERROR", f"Service failed to start on port {PORT}")
        return False


def run_daemon():
    """Main daemon loop."""
    failure_count = 0

    log("INFO", "=" * 50)
    log("INFO", f"Health Daemon started for port {PORT}")
    log("INFO", f"Monitoring: {HEALTH_URL}")
    log("INFO", f"Check interval: {CHECK_INTERVAL}s")
    log("INFO", f"Max failures before restart: {MAX_FAILURES}")
    log("INFO", "=" * 50)

    while True:
        if check_health():
            if failure_count > 0:
                log("INFO", f"Service recovered (was at {failure_count} failures)")
            failure_count = 0
        else:
            failure_count += 1
            log("WARN", f"Health check failed ({failure_count}/{MAX_FAILURES})")

            if failure_count >= MAX_FAILURES:
                log("ERROR", "Max failures reached, triggering restart")
                if restart_service():
                    failure_count = 0
                else:
                    failure_count = MAX_FAILURES - 1

        time.sleep(CHECK_INTERVAL)


def is_running():
    """Check if daemon is running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return pid
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    return None


def start_daemon():
    """Start as background daemon."""
    pid = is_running()
    if pid:
        print(f"Health daemon already running (PID: {pid})")
        return

    # Fork to background
    if os.fork() > 0:
        print(f"Health daemon started in background")
        print(f"Log file: {LOG_FILE}")
        return

    os.setsid()
    if os.fork() > 0:
        os._exit(0)

    PID_FILE.write_text(str(os.getpid()))

    def cleanup(signum, frame):
        log("INFO", "Health daemon stopping...")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    run_daemon()


def stop_daemon():
    """Stop the daemon."""
    pid = is_running()
    if pid:
        os.kill(pid, signal.SIGTERM)
        print(f"Health daemon stopped (PID: {pid})")
    else:
        print("Health daemon is not running")


def show_status():
    """Show daemon status."""
    print("=" * 50)
    print(f"Health Daemon Status (Port {PORT})")
    print("=" * 50)

    pid = is_running()
    if pid:
        print(f"Daemon: RUNNING (PID: {pid})")
    else:
        print("Daemon: NOT RUNNING")

    print(f"\nService Status:")
    if check_health():
        print(f"  Port {PORT}: HEALTHY")
    else:
        print(f"  Port {PORT}: DOWN or UNHEALTHY")

    print(f"\nLast 10 log entries:")
    print("-" * 50)
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text().strip().split("\n")
        for line in lines[-10:]:
            print(line)


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--daemon":
            start_daemon()
        elif cmd == "--stop":
            stop_daemon()
        elif cmd == "--status":
            show_status()
        elif cmd == "--check":
            if check_health():
                print("HEALTHY")
            else:
                print("DOWN - restarting...")
                restart_service()
        elif cmd == "--foreground":
            # For launchd
            PID_FILE.write_text(str(os.getpid()))
            signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
            signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
            run_daemon()
        else:
            print("Usage: health_daemon.py [--daemon|--stop|--status|--check|--foreground]")
    else:
        # Default: run in foreground for launchd
        PID_FILE.write_text(str(os.getpid()))
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
        run_daemon()


if __name__ == "__main__":
    main()
