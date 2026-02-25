#!/usr/bin/env python3
"""
App Health Manager
Starts, monitors, and manages health of all applications in the ecosystem.

Usage:
    python3 app_health_manager.py start            # Start all apps
    python3 app_health_manager.py stop             # Stop all apps
    python3 app_health_manager.py restart          # Restart all apps
    python3 app_health_manager.py status           # Check status of all apps
    python3 app_health_manager.py health           # Run health checks
    python3 app_health_manager.py --daemon         # Monitor and auto-restart
    python3 app_health_manager.py --report         # Send health report to dashboard
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

# App Configuration
APPS = {
    "architect": {
        "name": "Architect Dashboard",
        "path": "/Users/jgirmay/Desktop/gitrepo/pyWork/architect",
        "port": 8080,
        "health_endpoint": "/health",
        "start_command": ["python3", "app.py"],
        "priority": 1,  # Start first
    },
    "pharma": {
        "name": "Selam Pharmacy",
        "path": "/Users/jgirmay/Desktop/gitrepo/pyWork/selam_pharmacy",
        "port": 7085,
        "health_endpoint": "/health",
        "start_command": ["./deploy.sh", "--daemon"],
        "priority": 2,
    },
    "basic_edu": {
        "name": "Basic Edu Apps",
        "path": "/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final",
        "port": 5063,
        "health_endpoint": "/",
        "start_command": ["python3", "unified_app.py"],
        "env": {"PORT": "5063"},
        "priority": 3,
    },
}

# System Thresholds
MAX_CPU = 80  # %
MAX_MEMORY = 85  # %
MAX_DISK = 90  # %

LOG_FILE = Path("/tmp/app_health_manager.log")
PID_FILE = Path("/tmp/app_health_manager.pid")


def log(msg, level="INFO"):
    """Log message with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def get_system_health():
    """Get system resource usage."""
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    status = "healthy"
    issues = []

    if cpu > MAX_CPU:
        status = "warning"
        issues.append(f"High CPU: {cpu}%")

    if memory > MAX_MEMORY:
        status = "critical" if memory > 95 else "warning"
        issues.append(f"High Memory: {memory}%")

    if disk > MAX_DISK:
        status = "warning"
        issues.append(f"High Disk: {disk}%")

    return {"cpu": cpu, "memory": memory, "disk": disk, "status": status, "issues": issues}


def is_port_in_use(port):
    """Check if port is in use."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except:
        return False


def get_process_on_port(port):
    """Get process ID on port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) if result.stdout.strip() else None
    except:
        pass
    return None


def check_app_health(app_id, app_config):
    """Check health of an application."""
    port = app_config["port"]
    health_url = f"http://localhost:{port}{app_config.get('health_endpoint', '/')}"

    # Check if port is listening
    if not is_port_in_use(port):
        return {
            "app": app_id,
            "name": app_config["name"],
            "status": "down",
            "port": port,
            "message": "Port not listening",
        }

    # Check health endpoint
    try:
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            health_data = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            return {
                "app": app_id,
                "name": app_config["name"],
                "status": "healthy",
                "port": port,
                "health": health_data,
                "pid": get_process_on_port(port),
            }
        else:
            return {
                "app": app_id,
                "name": app_config["name"],
                "status": "unhealthy",
                "port": port,
                "message": f"Health check returned {response.status_code}",
            }
    except requests.exceptions.Timeout:
        return {
            "app": app_id,
            "name": app_config["name"],
            "status": "unhealthy",
            "port": port,
            "message": "Health check timeout",
        }
    except Exception as e:
        return {
            "app": app_id,
            "name": app_config["name"],
            "status": "unhealthy",
            "port": port,
            "message": str(e),
        }


def start_app(app_id, app_config):
    """Start an application."""
    log(f"Starting {app_config['name']}...")

    # Check if already running
    if is_port_in_use(app_config["port"]):
        log(f"{app_config['name']} already running on port {app_config['port']}", "WARN")
        return True

    # Change to app directory
    app_path = Path(app_config["path"])
    if not app_path.exists():
        log(f"App path does not exist: {app_path}", "ERROR")
        return False

    try:
        # Start app
        subprocess.Popen(
            app_config["start_command"],
            cwd=str(app_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for startup
        time.sleep(5)

        # Verify it started
        if is_port_in_use(app_config["port"]):
            log(f"✓ {app_config['name']} started successfully on port {app_config['port']}")
            return True
        else:
            log(f"✗ {app_config['name']} failed to start", "ERROR")
            return False

    except Exception as e:
        log(f"Error starting {app_config['name']}: {e}", "ERROR")
        return False


def stop_app(app_id, app_config):
    """Stop an application."""
    log(f"Stopping {app_config['name']}...")

    pid = get_process_on_port(app_config["port"])
    if not pid:
        log(f"{app_config['name']} not running")
        return True

    try:
        subprocess.run(["kill", "-9", str(pid)], timeout=5)
        time.sleep(2)

        if not is_port_in_use(app_config["port"]):
            log(f"✓ {app_config['name']} stopped")
            return True
        else:
            log(f"✗ Failed to stop {app_config['name']}", "ERROR")
            return False
    except Exception as e:
        log(f"Error stopping {app_config['name']}: {e}", "ERROR")
        return False


def start_all():
    """Start all applications in priority order."""
    log("Starting all applications...")

    # Sort by priority
    sorted_apps = sorted(APPS.items(), key=lambda x: x[1].get("priority", 999))

    results = {}
    for app_id, app_config in sorted_apps:
        results[app_id] = start_app(app_id, app_config)

    return results


def stop_all():
    """Stop all applications."""
    log("Stopping all applications...")

    # Reverse priority order for stopping
    sorted_apps = sorted(APPS.items(), key=lambda x: x[1].get("priority", 999), reverse=True)

    results = {}
    for app_id, app_config in sorted_apps:
        results[app_id] = stop_app(app_id, app_config)

    return results


def restart_all():
    """Restart all applications."""
    log("Restarting all applications...")
    stop_all()
    time.sleep(3)
    return start_all()


def check_all_health():
    """Check health of all applications."""
    log("Checking health of all applications...")

    system = get_system_health()
    apps = {}

    for app_id, app_config in APPS.items():
        apps[app_id] = check_app_health(app_id, app_config)

    return {"timestamp": datetime.now().isoformat(), "system": system, "apps": apps}


def send_health_report():
    """Send health report to Architect Dashboard."""
    health = check_all_health()

    try:
        response = requests.post("http://localhost:8080/api/system/health", json=health, timeout=5)

        if response.ok:
            log("Health report sent to dashboard")
        else:
            log(f"Failed to send health report: {response.status_code}", "WARN")

    except Exception as e:
        log(f"Error sending health report: {e}", "WARN")

    return health


def monitor_daemon():
    """Monitor apps and auto-restart if needed."""
    log("Starting health monitoring daemon...")

    # Write PID
    PID_FILE.write_text(str(os.getpid()))

    try:
        while True:
            health = check_all_health()

            # Check system health
            if health["system"]["status"] in ["warning", "critical"]:
                log(
                    f"System health {health['system']['status']}: {', '.join(health['system']['issues'])}",
                    "WARN",
                )
                send_health_report()

            # Check app health
            for app_id, app_health in health["apps"].items():
                if app_health["status"] != "healthy":
                    log(
                        f"{app_health['name']} is {app_health['status']}: {app_health.get('message', 'Unknown')}",
                        "WARN",
                    )

                    # Auto-restart if down
                    if app_health["status"] == "down":
                        log(f"Attempting to restart {app_health['name']}...")
                        start_app(app_id, APPS[app_id])

            # Sleep for 60 seconds
            time.sleep(60)

    except KeyboardInterrupt:
        log("Monitoring daemon stopped")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


def print_status():
    """Print status of all apps."""
    health = check_all_health()

    print("\n" + "=" * 60)
    print("APPLICATION HEALTH STATUS")
    print("=" * 60)

    # System Health
    sys_health = health["system"]
    status_icon = {"healthy": "✓", "warning": "⚠", "critical": "✗"}.get(sys_health["status"], "?")

    print(f"\nSystem: {status_icon} {sys_health['status'].upper()}")
    print(f"  CPU: {sys_health['cpu']}%")
    print(f"  Memory: {sys_health['memory']}%")
    print(f"  Disk: {sys_health['disk']}%")

    if sys_health["issues"]:
        print(f"  Issues: {', '.join(sys_health['issues'])}")

    # App Health
    print(f"\nApplications:")
    for app_id, app_health in health["apps"].items():
        status_icon = {"healthy": "✓", "unhealthy": "⚠", "down": "✗"}.get(app_health["status"], "?")

        print(f"  {status_icon} {app_health['name']}")
        print(f"     Port: {app_health['port']}")
        print(f"     Status: {app_health['status']}")
        if app_health.get("pid"):
            print(f"     PID: {app_health['pid']}")
        if app_health.get("message"):
            print(f"     Message: {app_health['message']}")

    print("\n" + "=" * 60 + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == "start":
        start_all()
    elif command == "stop":
        stop_all()
    elif command == "restart":
        restart_all()
    elif command == "status":
        print_status()
    elif command == "health":
        health = check_all_health()
        print(json.dumps(health, indent=2))
    elif command == "--daemon":
        monitor_daemon()
    elif command == "--report":
        health = send_health_report()
        print(json.dumps(health, indent=2))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
