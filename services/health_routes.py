"""
Deep Health Check Routes

Flask blueprint for comprehensive system health monitoring.
"""

import logging
import os
import time
from datetime import datetime

from flask import Blueprint, current_app, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__, url_prefix="/api/health")


def get_db_connection():
    """Get database connection from app."""
    import sqlite3

    from flask import g

    db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))

    if "db" not in g:
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row

    return g.db


def require_auth(f):
    """Decorator to require authentication."""
    from functools import wraps

    from flask import request, session

    @wraps(f)
    def decorated(*args, **kwargs):
        # Check API key first
        api_key = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        elif request.headers.get("X-API-Key"):
            api_key = request.headers.get("X-API-Key")
        elif request.args.get("api_key"):
            api_key = request.args.get("api_key")

        if api_key:
            try:
                from services.api_keys import get_api_key_service

                db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))
                service = get_api_key_service(db_path)
                result = service.validate_key(api_key)
                if result["valid"]:
                    return f(*args, **kwargs)
            except Exception:
                pass

        # Fall back to session auth
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


@health_bp.route("/deep", methods=["GET"])
@require_auth
def deep_health_check():
    """Comprehensive health check for all system components."""
    import psutil

    start_time = time.time()
    checks = {}
    overall_status = "healthy"

    def run_check(name, check_func):
        nonlocal overall_status
        check_start = time.time()
        try:
            result = check_func()
            result["duration_ms"] = round((time.time() - check_start) * 1000, 1)
            if result.get("status") == "unhealthy":
                overall_status = "unhealthy"
            elif result.get("status") == "degraded" and overall_status == "healthy":
                overall_status = "degraded"
            return result
        except Exception as e:
            overall_status = "unhealthy"
            return {
                "status": "unhealthy",
                "error": str(e),
                "duration_ms": round((time.time() - check_start) * 1000, 1),
            }

    # 1. Database connectivity and performance
    def check_database():
        conn = get_db_connection()
        # Basic connectivity
        conn.execute("SELECT 1")

        # Check table count
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

        # Check database size
        db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        return {
            "status": "healthy",
            "tables": len(tables),
            "size_mb": round(db_size / (1024 * 1024), 2),
        }

    checks["database"] = run_check("database", check_database)

    # 2. Table integrity check
    def check_tables():
        required_tables = [
            "projects",
            "milestones",
            "features",
            "bugs",
            "errors",
            "nodes",
            "task_queue",
            "workers",
        ]
        conn = get_db_connection()
        existing = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        missing = [t for t in required_tables if t not in existing]

        if missing:
            return {"status": "unhealthy", "missing_tables": missing}
        return {"status": "healthy", "tables_verified": len(required_tables)}

    checks["tables"] = run_check("tables", check_tables)

    # 3. Disk space check
    def check_disk():
        disk = psutil.disk_usage("/")
        status = "healthy"
        if disk.percent > 90:
            status = "unhealthy"
        elif disk.percent > 80:
            status = "degraded"

        return {
            "status": status,
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "percent_used": disk.percent,
        }

    checks["disk"] = run_check("disk", check_disk)

    # 4. Memory check
    def check_memory():
        mem = psutil.virtual_memory()
        status = "healthy"
        if mem.percent > 90:
            status = "unhealthy"
        elif mem.percent > 80:
            status = "degraded"

        return {
            "status": status,
            "total_gb": round(mem.total / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "percent_used": mem.percent,
        }

    checks["memory"] = run_check("memory", check_memory)

    # 5. CPU check
    def check_cpu():
        cpu_percent = psutil.cpu_percent(interval=0.1)
        status = "healthy"
        if cpu_percent > 90:
            status = "degraded"

        return {"status": status, "percent_used": cpu_percent, "cpu_count": psutil.cpu_count()}

    checks["cpu"] = run_check("cpu", check_cpu)

    # 6. Worker status
    def check_workers():
        conn = get_db_connection()
        workers = conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM workers
            WHERE last_heartbeat > datetime('now', '-5 minutes')
            GROUP BY status
        """
        ).fetchall()

        total_active = sum(w["count"] for w in workers)
        running = sum(w["count"] for w in workers if w["status"] == "running")

        status = "healthy" if total_active > 0 else "degraded"

        return {"status": status, "active_workers": total_active, "running": running}

    checks["workers"] = run_check("workers", check_workers)

    # 7. Task queue health
    def check_task_queue():
        conn = get_db_connection()
        stats = conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM task_queue
            WHERE created_at > datetime('now', '-24 hours')
            GROUP BY status
        """
        ).fetchall()

        stats_dict = {row["status"]: row["count"] for row in stats}
        pending = stats_dict.get("pending", 0)
        failed = stats_dict.get("failed", 0)

        status = "healthy"
        if failed > pending:
            status = "degraded"
        if pending > 100:
            status = "degraded"

        return {
            "status": status,
            "pending": pending,
            "running": stats_dict.get("running", 0),
            "completed": stats_dict.get("completed", 0),
            "failed": failed,
        }

    checks["task_queue"] = run_check("task_queue", check_task_queue)

    # 8. Scheduled tasks
    def check_scheduled_tasks():
        try:
            conn = get_db_connection()
            result = conn.execute(
                """
                SELECT COUNT(*) as count FROM scheduled_tasks WHERE enabled = 1
            """
            ).fetchone()
            active = result["count"] if result else 0

            overdue = conn.execute(
                """
                SELECT COUNT(*) as count FROM scheduled_tasks
                WHERE enabled = 1
                AND next_run_at < datetime('now', '-10 minutes')
            """
            ).fetchone()
            overdue_count = overdue["count"] if overdue else 0

            status = "healthy"
            if overdue_count > 0:
                status = "degraded"

            return {"status": status, "active_schedules": active, "overdue": overdue_count}
        except Exception:
            return {"status": "healthy", "active_schedules": 0, "note": "table not found"}

    checks["scheduled_tasks"] = run_check("scheduled_tasks", check_scheduled_tasks)

    # 9. Node connectivity
    def check_nodes():
        conn = get_db_connection()
        nodes = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN last_heartbeat > datetime('now', '-5 minutes') THEN 1 ELSE 0 END) as online
            FROM nodes
        """
        ).fetchone()

        total = nodes["total"] or 0
        online = nodes["online"] or 0

        status = "healthy"
        if total > 0 and online == 0:
            status = "unhealthy"
        elif total > 0 and online < total:
            status = "degraded"

        return {"status": status, "total_nodes": total, "online_nodes": online}

    checks["nodes"] = run_check("nodes", check_nodes)

    # 10. Integrations
    def check_integrations():
        try:
            conn = get_db_connection()
            result = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errored
                FROM integrations
            """
            ).fetchone()

            total = result["total"] or 0
            enabled = result["enabled"] or 0
            errored = result["errored"] or 0

            status = "healthy"
            if errored > 0:
                status = "degraded"

            return {"status": status, "total": total, "enabled": enabled, "errored": errored}
        except Exception:
            return {"status": "healthy", "total": 0, "note": "table not found"}

    checks["integrations"] = run_check("integrations", check_integrations)

    # 11. tmux sessions
    def check_tmux():
        import subprocess

        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            sessions = [s for s in result.stdout.strip().split("\n") if s]
            return {"status": "healthy", "active_sessions": len(sessions)}
        except subprocess.TimeoutExpired:
            return {"status": "degraded", "error": "timeout"}
        except FileNotFoundError:
            return {"status": "healthy", "note": "tmux not installed"}
        except Exception as e:
            if "no server running" in str(e):
                return {"status": "healthy", "active_sessions": 0}
            return {"status": "degraded", "error": str(e)}

    checks["tmux"] = run_check("tmux", check_tmux)

    # 12. Configuration validation
    def check_configuration():
        try:
            from config import Config

            errors = Config.validate()
            if errors:
                return {"status": "degraded", "errors": errors}
            return {"status": "healthy"}
        except ImportError:
            return {"status": "healthy", "note": "config module not available"}

    checks["configuration"] = run_check("configuration", check_configuration)

    # 13. Error rate (last hour)
    def check_error_rate():
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT COUNT(*) as count FROM errors
            WHERE last_seen > datetime('now', '-1 hour')
        """
        ).fetchone()

        recent_errors = result["count"] or 0

        status = "healthy"
        if recent_errors > 50:
            status = "degraded"
        if recent_errors > 100:
            status = "unhealthy"

        return {"status": status, "errors_last_hour": recent_errors}

    checks["error_rate"] = run_check("error_rate", check_error_rate)

    # Calculate summary
    total_checks = len(checks)
    healthy_checks = sum(1 for c in checks.values() if c.get("status") == "healthy")
    degraded_checks = sum(1 for c in checks.values() if c.get("status") == "degraded")
    unhealthy_checks = sum(1 for c in checks.values() if c.get("status") == "unhealthy")

    return jsonify(
        {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": round((time.time() - start_time) * 1000, 1),
            "summary": {
                "total": total_checks,
                "healthy": healthy_checks,
                "degraded": degraded_checks,
                "unhealthy": unhealthy_checks,
            },
            "checks": checks,
        }
    )


@health_bp.route("/components", methods=["GET"])
@require_auth
def health_components():
    """Get list of available health check components."""
    components = [
        {"name": "database", "description": "Database connectivity and performance"},
        {"name": "tables", "description": "Required database tables verification"},
        {"name": "disk", "description": "Disk space usage"},
        {"name": "memory", "description": "Memory usage"},
        {"name": "cpu", "description": "CPU utilization"},
        {"name": "workers", "description": "Background worker status"},
        {"name": "task_queue", "description": "Task queue health"},
        {"name": "scheduled_tasks", "description": "Scheduled task execution"},
        {"name": "nodes", "description": "Cluster node connectivity"},
        {"name": "integrations", "description": "Third-party integration status"},
        {"name": "tmux", "description": "tmux session availability"},
        {"name": "configuration", "description": "Configuration validation"},
        {"name": "error_rate", "description": "Recent error frequency"},
    ]
    return jsonify({"components": components})


@health_bp.route("/component/<component_name>", methods=["GET"])
@require_auth
def check_single_component(component_name):
    """Run a single health check component."""
    import psutil

    start_time = time.time()

    component_checks = {
        "database": lambda: check_database_component(),
        "tables": lambda: check_tables_component(),
        "disk": lambda: check_disk_component(),
        "memory": lambda: check_memory_component(),
        "cpu": lambda: check_cpu_component(),
        "workers": lambda: check_workers_component(),
        "task_queue": lambda: check_task_queue_component(),
        "scheduled_tasks": lambda: check_scheduled_tasks_component(),
        "nodes": lambda: check_nodes_component(),
        "integrations": lambda: check_integrations_component(),
        "tmux": lambda: check_tmux_component(),
        "configuration": lambda: check_configuration_component(),
        "error_rate": lambda: check_error_rate_component(),
    }

    if component_name not in component_checks:
        return jsonify({"error": f"Unknown component: {component_name}"}), 404

    try:
        result = component_checks[component_name]()
        result["duration_ms"] = round((time.time() - start_time) * 1000, 1)
        result["component"] = component_name
        return jsonify(result)
    except Exception as e:
        return (
            jsonify(
                {
                    "component": component_name,
                    "status": "unhealthy",
                    "error": str(e),
                    "duration_ms": round((time.time() - start_time) * 1000, 1),
                }
            ),
            500,
        )


# Individual component check functions
def check_database_component():
    conn = get_db_connection()
    conn.execute("SELECT 1")
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    db_path = str(current_app.config.get("DB_PATH", "data/prod/architect.db"))
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    return {
        "status": "healthy",
        "tables": len(tables),
        "size_mb": round(db_size / (1024 * 1024), 2),
    }


def check_tables_component():
    required_tables = [
        "projects",
        "milestones",
        "features",
        "bugs",
        "errors",
        "nodes",
        "task_queue",
        "workers",
    ]
    conn = get_db_connection()
    existing = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    missing = [t for t in required_tables if t not in existing]
    if missing:
        return {"status": "unhealthy", "missing_tables": missing}
    return {"status": "healthy", "tables_verified": len(required_tables)}


def check_disk_component():
    import psutil

    disk = psutil.disk_usage("/")
    status = "healthy"
    if disk.percent > 90:
        status = "unhealthy"
    elif disk.percent > 80:
        status = "degraded"
    return {
        "status": status,
        "total_gb": round(disk.total / (1024**3), 1),
        "used_gb": round(disk.used / (1024**3), 1),
        "free_gb": round(disk.free / (1024**3), 1),
        "percent_used": disk.percent,
    }


def check_memory_component():
    import psutil

    mem = psutil.virtual_memory()
    status = "healthy"
    if mem.percent > 90:
        status = "unhealthy"
    elif mem.percent > 80:
        status = "degraded"
    return {
        "status": status,
        "total_gb": round(mem.total / (1024**3), 1),
        "available_gb": round(mem.available / (1024**3), 1),
        "percent_used": mem.percent,
    }


def check_cpu_component():
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.1)
    status = "healthy"
    if cpu_percent > 90:
        status = "degraded"
    return {"status": status, "percent_used": cpu_percent, "cpu_count": psutil.cpu_count()}


def check_workers_component():
    conn = get_db_connection()
    workers = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM workers
        WHERE last_heartbeat > datetime('now', '-5 minutes')
        GROUP BY status
    """
    ).fetchall()
    total_active = sum(w["count"] for w in workers)
    running = sum(w["count"] for w in workers if w["status"] == "running")
    status = "healthy" if total_active > 0 else "degraded"
    return {"status": status, "active_workers": total_active, "running": running}


def check_task_queue_component():
    conn = get_db_connection()
    stats = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM task_queue
        WHERE created_at > datetime('now', '-24 hours')
        GROUP BY status
    """
    ).fetchall()
    stats_dict = {row["status"]: row["count"] for row in stats}
    pending = stats_dict.get("pending", 0)
    failed = stats_dict.get("failed", 0)
    status = "healthy"
    if failed > pending:
        status = "degraded"
    if pending > 100:
        status = "degraded"
    return {
        "status": status,
        "pending": pending,
        "running": stats_dict.get("running", 0),
        "completed": stats_dict.get("completed", 0),
        "failed": failed,
    }


def check_scheduled_tasks_component():
    try:
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT COUNT(*) as count FROM scheduled_tasks WHERE enabled = 1
        """
        ).fetchone()
        active = result["count"] if result else 0
        overdue = conn.execute(
            """
            SELECT COUNT(*) as count FROM scheduled_tasks
            WHERE enabled = 1 AND next_run_at < datetime('now', '-10 minutes')
        """
        ).fetchone()
        overdue_count = overdue["count"] if overdue else 0
        status = "healthy"
        if overdue_count > 0:
            status = "degraded"
        return {"status": status, "active_schedules": active, "overdue": overdue_count}
    except Exception:
        return {"status": "healthy", "active_schedules": 0, "note": "table not found"}


def check_nodes_component():
    conn = get_db_connection()
    nodes = conn.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN last_heartbeat > datetime('now', '-5 minutes') THEN 1 ELSE 0 END) as online
        FROM nodes
    """
    ).fetchone()
    total = nodes["total"] or 0
    online = nodes["online"] or 0
    status = "healthy"
    if total > 0 and online == 0:
        status = "unhealthy"
    elif total > 0 and online < total:
        status = "degraded"
    return {"status": status, "total_nodes": total, "online_nodes": online}


def check_integrations_component():
    try:
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errored
            FROM integrations
        """
        ).fetchone()
        total = result["total"] or 0
        enabled = result["enabled"] or 0
        errored = result["errored"] or 0
        status = "healthy"
        if errored > 0:
            status = "degraded"
        return {"status": status, "total": total, "enabled": enabled, "errored": errored}
    except Exception:
        return {"status": "healthy", "total": 0, "note": "table not found"}


def check_tmux_component():
    import subprocess

    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        sessions = [s for s in result.stdout.strip().split("\n") if s]
        return {"status": "healthy", "active_sessions": len(sessions)}
    except subprocess.TimeoutExpired:
        return {"status": "degraded", "error": "timeout"}
    except FileNotFoundError:
        return {"status": "healthy", "note": "tmux not installed"}
    except Exception as e:
        if "no server running" in str(e):
            return {"status": "healthy", "active_sessions": 0}
        return {"status": "degraded", "error": str(e)}


def check_configuration_component():
    try:
        from config import Config

        errors = Config.validate()
        if errors:
            return {"status": "degraded", "errors": errors}
        return {"status": "healthy"}
    except ImportError:
        return {"status": "healthy", "note": "config module not available"}


def check_error_rate_component():
    conn = get_db_connection()
    result = conn.execute(
        """
        SELECT COUNT(*) as count FROM errors
        WHERE last_seen > datetime('now', '-1 hour')
    """
    ).fetchone()
    recent_errors = result["count"] or 0
    status = "healthy"
    if recent_errors > 50:
        status = "degraded"
    if recent_errors > 100:
        status = "unhealthy"
    return {"status": status, "errors_last_hour": recent_errors}
