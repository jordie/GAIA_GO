#!/usr/bin/env python3
"""
Health Monitor - Continuously monitors system health and service ports.
Reads port configuration from config/ports.json for dynamic updates.
Supports auto-restart of down services using start_cmd from config.
Logs to /tmp/health_monitor.log
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yaml

LOG_FILE = "/tmp/health_monitor.log"
PID_FILE = "/tmp/health_monitor.pid"
STATE_FILE = "/tmp/health_monitor_state.json"
CHECK_INTERVAL = 120  # 2 minutes in seconds

# Path to config files
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR.parent / "config" / "ports.json"
THRESHOLDS_FILE = SCRIPT_DIR.parent / "config" / "thresholds.yaml"

# Fallback ports if config file not found
DEFAULT_PORTS = [8080, 8085, 5051, 5063, 6085]

# Default thresholds (overridden by config/thresholds.yaml)
DEFAULT_THRESHOLDS = {
    "restart": {"max_per_hour": 3, "cooldown_minutes": 30, "warning_at": 2},
    "resources": {"cpu_alert_percent": 90, "memory_alert_percent": 85, "disk_alert_percent": 80},
    "health": {"consecutive_failures": 3},
}

# Legacy constants - use thresholds from config instead
CPU_THRESHOLD = 90
MEMORY_THRESHOLD = 90
DISK_THRESHOLD = 90

# Cache for configs
_ports_config = None
_config_mtime = 0
_thresholds = None
_thresholds_mtime = 0

# State tracking for threshold enforcement
_restart_history = defaultdict(list)  # port -> [timestamps]
_failure_counts = defaultdict(int)  # port -> consecutive failures
_escalated_errors = set()  # Already escalated error keys


def load_thresholds(force_reload=False):
    """Load threshold configuration from thresholds.yaml."""
    global _thresholds, _thresholds_mtime

    if not THRESHOLDS_FILE.exists():
        return DEFAULT_THRESHOLDS

    try:
        current_mtime = THRESHOLDS_FILE.stat().st_mtime
        if not force_reload and _thresholds and current_mtime == _thresholds_mtime:
            return _thresholds

        with open(THRESHOLDS_FILE) as f:
            config = yaml.safe_load(f)
        _thresholds = config.get("thresholds", DEFAULT_THRESHOLDS)
        _thresholds_mtime = current_mtime
        return _thresholds
    except Exception as e:
        log(f"Error loading thresholds.yaml: {e}", "ERROR")
        return DEFAULT_THRESHOLDS


def load_state():
    """Load persistent state from file."""
    global _restart_history, _failure_counts, _escalated_errors
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            # Convert timestamps back to datetime
            for port, times in state.get("restart_history", {}).items():
                _restart_history[int(port)] = [datetime.fromisoformat(t) for t in times]
            _failure_counts = defaultdict(
                int, {int(k): v for k, v in state.get("failure_counts", {}).items()}
            )
            _escalated_errors = set(state.get("escalated_errors", []))
        except Exception as e:
            log(f"Error loading state: {e}", "WARN")


def save_state():
    """Save persistent state to file."""
    try:
        state = {
            "restart_history": {
                str(k): [t.isoformat() for t in v] for k, v in _restart_history.items()
            },
            "failure_counts": dict(_failure_counts),
            "escalated_errors": list(_escalated_errors),
            "last_saved": datetime.now().isoformat(),
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"Error saving state: {e}", "WARN")


def get_restart_count(port, hours=1):
    """Get number of restarts for a port within the last N hours."""
    cutoff = datetime.now() - timedelta(hours=hours)
    _restart_history[port] = [t for t in _restart_history[port] if t > cutoff]
    return len(_restart_history[port])


def record_restart(port):
    """Record a restart event for a port."""
    _restart_history[port].append(datetime.now())
    save_state()


def should_restart_service(port):
    """Check if service should be auto-restarted based on thresholds."""
    thresholds = load_thresholds()
    restart_config = thresholds.get("restart", {})
    max_per_hour = restart_config.get("max_per_hour", 3)
    warning_at = restart_config.get("warning_at", 2)

    restarts = get_restart_count(port, hours=1)
    info = get_service_info(port)
    name = info.get("name", f"Port {port}") if info else f"Port {port}"

    if restarts >= max_per_hour:
        # Too many restarts - something is fundamentally wrong
        error_key = f"restart_threshold_{port}"
        if error_key not in _escalated_errors:
            _escalated_errors.add(error_key)
            create_error_ticket(
                title=f"{name} requires {restarts}+ restarts/hour",
                message=f"Auto-restart disabled for port {port}. Root cause investigation needed. "
                f"Service has been restarted {restarts} times in the last hour.",
                priority="high",
                source="health_monitor",
            )
            save_state()
        log(
            f"  THRESHOLD EXCEEDED: {name} restarted {restarts}x in 1 hour - NOT restarting",
            "ALERT",
        )
        return False

    if restarts >= warning_at:
        log(f"  WARNING: {name} restart count: {restarts}/{max_per_hour}", "WARN")

    return True


def create_error_ticket(title, message, priority="medium", source="health_monitor"):
    """Create an error ticket via the dashboard API."""
    try:
        response = requests.post(
            "http://127.0.0.1:8080/api/errors",
            json={
                "node_id": "health_monitor",
                "error_type": "threshold_exceeded",
                "message": f"{title}: {message}",
                "source": source,
                "priority": priority,
            },
            timeout=5,
        )
        if response.status_code in [200, 201]:
            log(f"  Created error ticket: {title}", "INFO")
            return True
    except Exception as e:
        log(f"  Failed to create error ticket: {e}", "WARN")
    return False


def load_ports_config(force_reload=False):
    """Load port configuration from ports.json with caching."""
    global _ports_config, _config_mtime

    if not CONFIG_FILE.exists():
        return None

    try:
        current_mtime = CONFIG_FILE.stat().st_mtime
        if not force_reload and _ports_config and current_mtime == _config_mtime:
            return _ports_config

        with open(CONFIG_FILE) as f:
            config = json.load(f)
        _ports_config = config.get("services", {})
        _config_mtime = current_mtime
        return _ports_config
    except Exception as e:
        log(f"Error loading ports.json: {e}", "ERROR")
        return None


def get_monitored_ports():
    """Get list of ports to monitor from config or defaults."""
    config = load_ports_config()
    if config:
        return [int(port) for port in config.keys()]
    return DEFAULT_PORTS


def get_service_info(port):
    """Get service info from ports.json for a given port."""
    config = load_ports_config()
    if config and str(port) in config:
        return config[str(port)]
    return None


def restart_service(port):
    """Attempt to restart a service using its start_cmd from config."""
    info = get_service_info(port)
    if not info:
        log(f"  No config found for port {port}, cannot restart", "WARN")
        return False

    if not info.get("auto_restart", False):
        log(f"  Auto-restart disabled for port {port}", "INFO")
        return False

    # Check threshold before restarting
    if not should_restart_service(port):
        return False

    start_cmd = info.get("start_cmd")
    if not start_cmd or start_cmd == "unknown":
        log(f"  No start_cmd for port {port}, cannot restart", "WARN")
        return False

    name = info.get("name", f"Port {port}")
    log(f"  Attempting to restart {name} on port {port}...")

    try:
        # Run start command in background
        subprocess.Popen(
            start_cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(3)

        # Verify it started
        if check_port(port):
            record_restart(port)  # Track the restart
            log(f"  Successfully restarted {name} on port {port}", "INFO")
            _failure_counts[port] = 0  # Reset failure count on success
            return True
        else:
            log(f"  Failed to restart {name} on port {port}", "ERROR")
            return False
    except Exception as e:
        log(f"  Error restarting {name}: {e}", "ERROR")
        return False


def log(message, level="INFO"):
    """Write log entry to file and stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def get_cpu_usage():
    """Get current CPU usage percentage."""
    try:
        result = subprocess.run(["ps", "-A", "-o", "%cpu"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")[1:]
        total = sum(float(line.strip()) for line in lines if line.strip())
        return min(total, 100.0)
    except Exception as e:
        log(f"Error getting CPU usage: {e}", "ERROR")
        return -1


def get_memory_usage():
    """Get current memory usage percentage."""
    try:
        result = subprocess.run(["vm_stat"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        stats = {}
        for line in lines[1:]:
            if ":" in line:
                key, val = line.split(":")
                stats[key.strip()] = int(val.strip().rstrip("."))

        page_size = 16384  # macOS default
        free = stats.get("Pages free", 0)
        active = stats.get("Pages active", 0)
        inactive = stats.get("Pages inactive", 0)
        speculative = stats.get("Pages speculative", 0)
        wired = stats.get("Pages wired down", 0)

        total = free + active + inactive + speculative + wired
        used = active + wired

        if total > 0:
            return (used / total) * 100
        return 0
    except Exception as e:
        log(f"Error getting memory usage: {e}", "ERROR")
        return -1


def get_disk_usage():
    """Get disk usage percentage for root filesystem."""
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            capacity = parts[4].rstrip("%")
            return float(capacity)
        return 0
    except Exception as e:
        log(f"Error getting disk usage: {e}", "ERROR")
        return -1


def check_port(port):
    """Check if a port is listening using netstat (works for all users)."""
    try:
        result = subprocess.run(["netstat", "-an"], capture_output=True, text=True)
        # Look for LISTEN on this port
        for line in result.stdout.split("\n"):
            if f".{port}" in line and "LISTEN" in line:
                return True
            if f":{port}" in line and "LISTEN" in line:
                return True
        return False
    except Exception as e:
        log(f"Error checking port {port}: {e}", "ERROR")
        return False


def check_port_health(port):
    """Check port health via HTTP endpoint."""
    info = get_service_info(port)
    if not info:
        return check_port(port)

    protocol = info.get("protocol", "http")
    health_endpoint = info.get("health_endpoint", "/health")
    url = f"{protocol}://127.0.0.1:{port}{health_endpoint}"

    try:
        result = subprocess.run(
            ["curl", "-sk", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() in ["200", "201", "204"]
    except:
        return check_port(port)


def get_port_service(port):
    """Get the service name running on a port."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"], capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip().split("\n")[0]
            ps_result = subprocess.run(
                ["ps", "-p", pid, "-o", "comm="], capture_output=True, text=True
            )
            return ps_result.stdout.strip()
    except:
        pass
    return "unknown"


def run_health_check():
    """Run a complete health check."""
    log("=" * 60)
    log("Starting health check")

    # Reload configs to pick up any changes
    load_ports_config(force_reload=True)
    thresholds = load_thresholds(force_reload=True)
    monitored_ports = get_monitored_ports()

    # Get resource thresholds from config
    resource_config = thresholds.get("resources", {})
    cpu_threshold = resource_config.get("cpu_alert_percent", 90)
    memory_threshold = resource_config.get("memory_alert_percent", 85)
    disk_threshold = resource_config.get("disk_alert_percent", 80)

    alerts = []

    # CPU check
    cpu = get_cpu_usage()
    if cpu >= 0:
        status = "OK" if cpu < cpu_threshold else "ALERT"
        log(f"CPU Usage: {cpu:.1f}% [{status}]")
        if cpu >= cpu_threshold:
            alerts.append(f"HIGH CPU: {cpu:.1f}%")

    # Memory check
    memory = get_memory_usage()
    if memory >= 0:
        status = "OK" if memory < memory_threshold else "ALERT"
        log(f"Memory Usage: {memory:.1f}% [{status}]")
        if memory >= memory_threshold:
            alerts.append(f"HIGH MEMORY: {memory:.1f}%")

    # Disk check
    disk = get_disk_usage()
    if disk >= 0:
        status = "OK" if disk < disk_threshold else "ALERT"
        log(f"Disk Usage: {disk:.1f}% [{status}]")
        if disk >= disk_threshold:
            alerts.append(f"HIGH DISK: {disk:.1f}%")

    # Port checks
    log("-" * 40)
    log(f"Port Status (from {'ports.json' if CONFIG_FILE.exists() else 'defaults'}):")
    for port in monitored_ports:
        info = get_service_info(port)
        name = info.get("name", "unknown") if info else "unknown"
        # Use health endpoint check if available, fallback to port check
        is_up = check_port_health(port)
        if is_up:
            service = get_port_service(port)
            if service == "unknown":
                service = info.get("app", "service") if info else "service"
            log(f"  Port {port} ({name}): UP ({service})")
        else:
            log(f"  Port {port} ({name}): DOWN", "WARN")
            # Attempt auto-restart
            if restart_service(port):
                log(f"  Port {port}: RECOVERED", "INFO")
            else:
                alerts.append(f"PORT DOWN: {port} ({name})")

    # Summary
    log("-" * 40)
    if alerts:
        log(f"ALERTS ({len(alerts)}):", "ALERT")
        for alert in alerts:
            log(f"  ! {alert}", "ALERT")
    else:
        log("All systems healthy")

    log(f"Next check in {CHECK_INTERVAL // 60} minutes")
    log("=" * 60)

    return len(alerts) == 0


def write_pid():
    """Write PID file."""
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def cleanup(signum=None, frame=None):
    """Clean up on exit."""
    log("Health monitor stopping...")
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    sys.exit(0)


def is_running():
    """Check if monitor is already running."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return pid
        except (ProcessLookupError, ValueError):
            os.remove(PID_FILE)
    return None


def start_daemon():
    """Start as background daemon."""
    pid = is_running()
    if pid:
        print(f"Health monitor already running (PID: {pid})")
        return

    # Fork to background
    if os.fork() > 0:
        print(f"Health monitor started in background")
        print(f"Log file: {LOG_FILE}")
        return

    os.setsid()

    if os.fork() > 0:
        os._exit(0)

    # Redirect stdout/stderr
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    run_monitor()


def stop_daemon():
    """Stop the background daemon."""
    pid = is_running()
    if pid:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped health monitor (PID: {pid})")
    else:
        print("Health monitor is not running")


def status():
    """Show current status."""
    pid = is_running()
    if pid:
        print(f"Health monitor is running (PID: {pid})")
    else:
        print("Health monitor is not running")

    if os.path.exists(LOG_FILE):
        print(f"\nLast 20 log entries from {LOG_FILE}:")
        print("-" * 60)
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())


def run_monitor():
    """Main monitoring loop."""
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    write_pid()
    load_state()  # Load persistent state on startup
    thresholds = load_thresholds()

    log("Health monitor started")
    log(f"Config file: {CONFIG_FILE}")
    log(f"Thresholds file: {THRESHOLDS_FILE}")
    monitored_ports = get_monitored_ports()
    log(f"Monitoring ports: {monitored_ports}")
    log(f"Check interval: {CHECK_INTERVAL // 60} minutes")
    log(f"Restart threshold: {thresholds.get('restart', {}).get('max_per_hour', 3)}/hour")

    while True:
        try:
            run_health_check()
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            log(f"Error in health check: {e}", "ERROR")
            time.sleep(60)


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--daemon":
            start_daemon()
        elif cmd == "--stop":
            stop_daemon()
        elif cmd == "--status":
            status()
        elif cmd == "--once":
            run_health_check()
        else:
            print("Usage: health_monitor.py [--daemon|--stop|--status|--once]")
            print("  --daemon  Run in background")
            print("  --stop    Stop background monitor")
            print("  --status  Show status and recent logs")
            print("  --once    Run single check and exit")
    else:
        run_monitor()


if __name__ == "__main__":
    main()
