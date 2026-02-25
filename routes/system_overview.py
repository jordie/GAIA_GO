"""
System Overview API - Comprehensive view of all systems, sessions, and environments.

Provides real-time data for the architect dashboard to enable informed decision-making.
"""

import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

import psutil
import requests
import urllib3
from flask import Blueprint, jsonify, request

# Disable SSL warnings for self-signed certs on internal services
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import centralized database module
import db as database

system_bp = Blueprint("system", __name__, url_prefix="/api/system")

# Paths
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
DATA_DIR = Path(__file__).parent.parent / "data"
EDU_APPS_DIR = Path("/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final")
KANBAN_DIR = Path("/Users/jgirmay/Desktop/gitrepo/pyWork/kanbanflow")
ARCHITECT_DIR = Path(__file__).parent.parent

# Remote host configuration
MACMINI_HOST = "100.112.58.92"  # Tailscale address for macmini

# Service definitions
SERVICES = {
    "edu_apps": {
        "dev": {"port": 5051, "protocol": "https", "host": MACMINI_HOST},
        "qa": {"port": 5052, "protocol": "https", "host": MACMINI_HOST},
        "prod": {"port": 5063, "protocol": "https", "host": MACMINI_HOST},
        "env_1": {"port": 5054, "protocol": "https", "host": MACMINI_HOST},
        "env_2": {"port": 5055, "protocol": "https", "host": MACMINI_HOST},
        "env_3": {"port": 5056, "protocol": "https", "host": MACMINI_HOST},
        "env_4": {"port": 5057, "protocol": "https", "host": MACMINI_HOST},
        "env_5": {"port": 5058, "protocol": "https", "host": MACMINI_HOST},
    },
    "kanbanflow": {
        "dev": {"port": 6051, "protocol": "https", "host": MACMINI_HOST},
        "feature1": {"port": 6052, "protocol": "https", "host": MACMINI_HOST},
        "feature2": {"port": 6053, "protocol": "https", "host": MACMINI_HOST},
        "prod": {"port": 6054, "protocol": "https", "host": MACMINI_HOST},
    },
    "architect": {
        "prod": {"port": 8080, "protocol": "http"},
        "qa": {"port": 8081, "protocol": "http"},
        "dev": {"port": 8082, "protocol": "http"},
        "https": {"port": 8085, "protocol": "https"},
        "main": {"port": 8086, "protocol": "http"},
    },
}


def check_port_listening(port):
    """Check if a port is listening locally."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True, timeout=2
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return False


def check_remote_health(host, port, protocol="https"):
    """Check if a remote service is healthy via HTTP health endpoint."""
    try:
        url = f"{protocol}://{host}:{port}/health"
        response = requests.get(url, timeout=3, verify=False)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def check_service_status(config):
    """Check if a service is running (local or remote)."""
    host = config.get("host")
    port = config["port"]
    protocol = config.get("protocol", "http")

    if host:
        # Remote service - check via HTTP health endpoint
        return check_remote_health(host, port, protocol)
    else:
        # Local service - check via lsof
        return check_port_listening(port)


def get_port_pid(port):
    """Get PID of process listening on port."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True, timeout=2
        )
        pids = result.stdout.strip().split("\n")
        return int(pids[0]) if pids and pids[0] else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, OSError):
        return None


def get_process_info(pid):
    """Get process info from PID."""
    try:
        proc = psutil.Process(pid)
        return {
            "pid": pid,
            "cpu_percent": proc.cpu_percent(),
            "memory_mb": proc.memory_info().rss / 1024 / 1024,
            "uptime_seconds": (
                datetime.now() - datetime.fromtimestamp(proc.create_time())
            ).total_seconds(),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def get_tmux_sessions():
    """Get all tmux sessions with status."""
    try:
        result = subprocess.run(
            [
                "tmux",
                "list-sessions",
                "-F",
                "#{session_name}:#{session_created}:#{session_attached}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        sessions = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":")
                    name = parts[0]
                    created = int(parts[1]) if len(parts) > 1 else 0
                    attached = parts[2] == "1" if len(parts) > 2 else False

                    # Capture recent output to determine status
                    capture_result = subprocess.run(
                        ["tmux", "capture-pane", "-t", name, "-p", "-S", "-10"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    output = capture_result.stdout if capture_result.returncode == 0 else ""

                    # Determine session state
                    state = "unknown"
                    if "bypass permissions" in output or "accept edits" in output:
                        if "(thinking)" in output or "Thinking" in output:
                            state = "thinking"
                        elif "(running)" in output:
                            state = "working"
                        else:
                            state = "idle"

                    sessions.append(
                        {
                            "name": name,
                            "created": datetime.fromtimestamp(created).isoformat()
                            if created
                            else None,
                            "attached": attached,
                            "state": state,
                            "is_claude": "bypass permissions" in output or "accept edits" in output,
                        }
                    )
        return sessions
    except Exception as e:
        return []


def get_session_assignments():
    """Get session assignments from the session assigner."""
    state_file = DATA_DIR / "session_state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return {"sessions": {}, "env_assignments": {}, "scope_locks": {}}


def get_git_status(repo_path):
    """Get git status for a repository."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = result.stdout.strip() if result.returncode == 0 else "unknown"

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        changes = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

        return {"branch": branch, "uncommitted_changes": changes}
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return {"branch": "unknown", "uncommitted_changes": 0}


def get_database_status(db_path):
    """Get database status."""
    size_mb = 0
    try:
        if not Path(db_path).exists():
            return {"status": "missing", "size_mb": 0}

        size_mb = Path(db_path).stat().st_size / 1024 / 1024

        # Try to connect with proper timeout and WAL mode
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("SELECT 1")
        conn.close()

        return {"status": "ok", "size_mb": round(size_mb, 2)}
    except sqlite3.OperationalError as e:
        if "locked" in str(e):
            return {"status": "locked", "size_mb": round(size_mb, 2)}
        return {"status": "error", "size_mb": round(size_mb, 2), "error": str(e)}
    except Exception as e:
        return {"status": "error", "size_mb": round(size_mb, 2), "error": str(e)}


@system_bp.route("/overview", methods=["GET"])
def get_system_overview():
    """Get comprehensive system overview."""
    try:
        overview = {
            "timestamp": datetime.now().isoformat(),
            "system": {},
            "services": {},
            "sessions": {},
            "environments": {},
            "databases": {},
            "summary": {},
        }

        # System resources
        overview["system"] = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_available_gb": round(psutil.virtual_memory().available / 1024 / 1024 / 1024, 2),
            "disk_percent": psutil.disk_usage("/").percent,
        }

        # Check all services
        total_running = 0
        total_stopped = 0

        for project, envs in SERVICES.items():
            overview["services"][project] = {}
            for env_name, config in envs.items():
                port = config["port"]
                host = config.get("host")
                is_running = check_service_status(config)

                # Only get local process info for local services
                pid = None
                proc_info = None
                if not host and is_running:
                    pid = get_port_pid(port)
                    proc_info = get_process_info(pid) if pid else None

                overview["services"][project][env_name] = {
                    "port": port,
                    "protocol": config["protocol"],
                    "running": is_running,
                    "pid": pid,
                    "process": proc_info,
                    "host": host or "localhost",
                }

                if is_running:
                    total_running += 1
                else:
                    total_stopped += 1

        # tmux sessions and assignments
        tmux_sessions = get_tmux_sessions()
        assignments = get_session_assignments()

        working_count = 0
        idle_count = 0

        for session in tmux_sessions:
            name = session["name"]
            assignment = assignments.get("sessions", {}).get(name, {})

            session_info = {
                **session,
                "project": assignment.get("project"),
                "task": assignment.get("task"),
                "env_info": assignment.get("env_info"),
                "assigned_at": assignment.get("assigned_at"),
            }
            overview["sessions"][name] = session_info

            if session["state"] in ("working", "thinking"):
                working_count += 1
            elif session["state"] == "idle":
                idle_count += 1

        # Environment details
        overview["environments"]["edu_apps"] = {
            "main": get_git_status(EDU_APPS_DIR),
            "feature_envs": {},
        }
        for i in range(1, 6):
            env_path = EDU_APPS_DIR / "feature_environments" / f"env_{i}"
            if env_path.exists():
                overview["environments"]["edu_apps"]["feature_envs"][f"env_{i}"] = get_git_status(
                    env_path
                )

        overview["environments"]["kanbanflow"] = get_git_status(KANBAN_DIR)
        overview["environments"]["architect"] = get_git_status(ARCHITECT_DIR)

        # Database status
        overview["databases"]["architect"] = get_database_status(DATA_DIR / "architect.db")
        overview["databases"]["edu_central"] = get_database_status(
            EDU_APPS_DIR / "education_central.db"
        )

        # Summary for quick decisions
        overview["summary"] = {
            "services_running": total_running,
            "services_stopped": total_stopped,
            "sessions_total": len(tmux_sessions),
            "sessions_working": working_count,
            "sessions_idle": idle_count,
            "sessions_assigned": len(assignments.get("sessions", {})),
            "cpu_percent": overview["system"]["cpu_percent"],
            "memory_percent": overview["system"]["memory_percent"],
        }

        return jsonify(overview)
    except Exception as e:
        return jsonify({"error": str(e), "timestamp": datetime.now().isoformat()}), 500


@system_bp.route("/health-matrix", methods=["GET"])
def get_health_matrix():
    """Get health status of all services in matrix format."""
    try:
        matrix = []

        for project, envs in SERVICES.items():
            for env_name, config in envs.items():
                port = config["port"]
                host = config.get("host")
                is_running = check_service_status(config)

                matrix.append(
                    {
                        "project": project,
                        "environment": env_name,
                        "port": port,
                        "status": "online" if is_running else "offline",
                        "protocol": config["protocol"],
                        "host": host or "localhost",
                    }
                )

        return jsonify(matrix)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@system_bp.route("/sessions/summary", methods=["GET"])
def get_sessions_summary():
    """Get summary of all Claude sessions."""
    try:
        sessions = get_tmux_sessions()
        assignments = get_session_assignments()

        summary = {
            "total": len(sessions),
            "by_state": {},
            "by_project": {},
            "unassigned": [],
            "details": [],
        }

        for session in sessions:
            name = session["name"]
            state = session["state"]
            assignment = assignments.get("sessions", {}).get(name, {})
            project = assignment.get("project", "unassigned")

            # Count by state
            summary["by_state"][state] = summary["by_state"].get(state, 0) + 1

            # Count by project
            summary["by_project"][project] = summary["by_project"].get(project, 0) + 1

            # Track unassigned
            if not assignment:
                summary["unassigned"].append(name)

            # Add details
            summary["details"].append(
                {
                    "name": name,
                    "state": state,
                    "project": project,
                    "task": assignment.get("task", "")[:50] if assignment.get("task") else None,
                    "is_claude": session.get("is_claude", False),
                }
            )

        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@system_bp.route("/decision-data", methods=["GET"])
def get_decision_data():
    """Get data needed for making decisions about system management."""
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "recommendations": [],
            "alerts": [],
            "capacity": {},
        }

        # Check system resources
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent

        if cpu > 80:
            data["alerts"].append(
                {
                    "level": "warning",
                    "message": f"High CPU usage: {cpu}%",
                    "action": "Consider stopping idle sessions or services",
                }
            )

        if mem > 85:
            data["alerts"].append(
                {
                    "level": "critical",
                    "message": f"High memory usage: {mem}%",
                    "action": "Stop some services or restart memory-heavy processes",
                }
            )

        # Check service capacity
        running_services = 0
        for project, envs in SERVICES.items():
            for env_name, config in envs.items():
                if check_service_status(config):
                    running_services += 1

        data["capacity"]["services_running"] = running_services
        data["capacity"]["services_total"] = sum(len(envs) for envs in SERVICES.values())

        # Check session capacity
        sessions = get_tmux_sessions()
        assignments = get_session_assignments()

        working = sum(1 for s in sessions if s["state"] in ("working", "thinking"))
        idle = sum(1 for s in sessions if s["state"] == "idle")
        assigned = len(assignments.get("sessions", {}))

        data["capacity"]["sessions_total"] = len(sessions)
        data["capacity"]["sessions_working"] = working
        data["capacity"]["sessions_idle"] = idle
        data["capacity"]["sessions_assigned"] = assigned

        # Generate recommendations
        if idle > 3:
            data["recommendations"].append(
                {
                    "type": "optimization",
                    "message": f"{idle} idle sessions available",
                    "action": "Assign new tasks to idle sessions",
                }
            )

        if working > 10:
            data["recommendations"].append(
                {
                    "type": "monitoring",
                    "message": f"{working} sessions actively working",
                    "action": "Monitor for completion and potential conflicts",
                }
            )

        # Check for unassigned sessions
        unassigned = [
            s["name"] for s in sessions if s["name"] not in assignments.get("sessions", {})
        ]
        if unassigned:
            data["recommendations"].append(
                {
                    "type": "assignment",
                    "message": f"{len(unassigned)} unassigned sessions",
                    "action": f"Assign tasks to: {', '.join(unassigned[:5])}",
                }
            )

        # Check database health
        db_status = get_database_status(DATA_DIR / "architect.db")
        if db_status["status"] == "locked":
            data["alerts"].append(
                {
                    "level": "critical",
                    "message": "Architect database is locked",
                    "action": "Check for stuck processes, consider restart",
                }
            )

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e), "timestamp": datetime.now().isoformat()}), 500
