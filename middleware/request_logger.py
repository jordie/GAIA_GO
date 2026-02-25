"""
Request Logging Middleware for Flask

Provides comprehensive request/response logging for debugging with:
- Configurable log levels (debug, info, minimal)
- In-memory log buffer for API access
- File logging for persistent debugging
- Request timing and performance metrics
- Automatic sensitive data masking

Configuration via environment variables:
    REQUEST_LOG_ENABLED: Enable/disable logging (default: true)
    REQUEST_LOG_LEVEL: Log level - debug, info, minimal (default: info)
    REQUEST_LOG_FILE: Log file path (default: /tmp/architect_requests.log)
    REQUEST_LOG_MAX_BODY: Max body size to log (default: 1000)
    REQUEST_LOG_EXCLUDE: Comma-separated paths to exclude (default: /health,/socket.io)

Usage:
    from middleware import init_request_logging, get_request_logs

    # Initialize with Flask app
    init_request_logging(app)

    # Get recent logs
    logs = get_request_logs(limit=100)
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, g, request

logger = logging.getLogger(__name__)

# Configuration
REQUEST_LOG_ENABLED = os.environ.get("REQUEST_LOG_ENABLED", "true").lower() == "true"
REQUEST_LOG_LEVEL = os.environ.get("REQUEST_LOG_LEVEL", "info").lower()
REQUEST_LOG_FILE = Path(os.environ.get("REQUEST_LOG_FILE", "/tmp/architect_requests.log"))
REQUEST_LOG_MAX_BODY = int(os.environ.get("REQUEST_LOG_MAX_BODY", 1000))
REQUEST_LOG_EXCLUDE = set(
    filter(
        None, os.environ.get("REQUEST_LOG_EXCLUDE", "/health,/api/metrics,/socket.io").split(",")
    )
)

# In-memory circular buffer for recent logs
_log_buffer: List[Dict] = []
_log_buffer_size = 500
_log_lock = threading.Lock()

# Statistics
_stats = {
    "total_requests": 0,
    "total_errors": 0,
    "avg_duration_ms": 0,
    "status_counts": {},
    "slowest_requests": [],
}
_stats_lock = threading.Lock()


def _should_log(path: str) -> bool:
    """Check if request path should be logged."""
    for exclude in REQUEST_LOG_EXCLUDE:
        if path.startswith(exclude):
            return False
    return True


def _mask_sensitive(headers: dict) -> dict:
    """Mask sensitive header values."""
    masked = dict(headers)
    sensitive_keys = ["Authorization", "Cookie", "X-Api-Key", "X-Auth-Token"]
    for key in sensitive_keys:
        if key in masked:
            masked[key] = "***masked***"
    return masked


def _add_to_buffer(entry: dict):
    """Add log entry to circular buffer."""
    with _log_lock:
        _log_buffer.append(entry)
        while len(_log_buffer) > _log_buffer_size:
            _log_buffer.pop(0)


def _update_stats(entry: dict):
    """Update request statistics."""
    with _stats_lock:
        _stats["total_requests"] += 1

        if entry["status"] >= 400:
            _stats["total_errors"] += 1

        # Update status counts
        status = str(entry["status"])
        _stats["status_counts"][status] = _stats["status_counts"].get(status, 0) + 1

        # Update average duration (rolling average)
        n = _stats["total_requests"]
        old_avg = _stats["avg_duration_ms"]
        _stats["avg_duration_ms"] = old_avg + (entry["duration_ms"] - old_avg) / n

        # Track slowest requests
        if entry["duration_ms"] > 100:  # Only track requests > 100ms
            slow_entry = {
                "path": entry["path"],
                "method": entry["method"],
                "duration_ms": entry["duration_ms"],
                "timestamp": entry["timestamp"],
            }
            _stats["slowest_requests"].append(slow_entry)
            _stats["slowest_requests"].sort(key=lambda x: x["duration_ms"], reverse=True)
            _stats["slowest_requests"] = _stats["slowest_requests"][:20]


def _write_to_file(entry: dict):
    """Write log entry to file."""
    if not REQUEST_LOG_FILE:
        return
    try:
        with open(REQUEST_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write request log: {e}")


def init_request_logging(app: Flask):
    """
    Initialize request logging middleware for Flask app.

    Args:
        app: Flask application instance
    """
    if not REQUEST_LOG_ENABLED:
        logger.info("Request logging disabled")
        return

    logger.info(f"Request logging enabled (level={REQUEST_LOG_LEVEL}, file={REQUEST_LOG_FILE})")

    @app.before_request
    def before_request():
        """Start request timing."""
        if not _should_log(request.path):
            return

        g.request_start_time = time.time()
        g.request_id = str(uuid.uuid4())[:8]

        if REQUEST_LOG_LEVEL == "debug":
            headers = _mask_sensitive(dict(request.headers))
            logger.debug(
                f"[{g.request_id}] --> {request.method} {request.path} "
                f"| IP: {request.remote_addr} | Headers: {len(headers)}"
            )

    @app.after_request
    def after_request(response):
        """Log completed request."""
        if not _should_log(request.path):
            return response

        # Calculate duration
        start_time = getattr(g, "request_start_time", time.time())
        duration_ms = round((time.time() - start_time) * 1000, 2)
        request_id = getattr(g, "request_id", str(uuid.uuid4())[:8])

        status = response.status_code

        # Build log entry
        entry = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.path,
            "query": request.query_string.decode() if request.query_string else None,
            "status": status,
            "duration_ms": duration_ms,
            "ip": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", "")[:100],
            "content_type": request.content_type,
            "content_length": request.content_length,
            "response_size": response.content_length,
            "referrer": request.referrer,
        }

        # Determine log level
        if status >= 500:
            log_func = logger.error
        elif status >= 400:
            log_func = logger.warning
        else:
            log_func = logger.info if REQUEST_LOG_LEVEL != "minimal" else logger.debug

        # Log message
        log_msg = f"[{request_id}] {request.method} {request.path} | {status} | {duration_ms}ms"
        if REQUEST_LOG_LEVEL == "debug":
            log_msg += f" | Size: {response.content_length or 0}B"
        log_func(log_msg)

        # Store in buffer and update stats
        _add_to_buffer(entry)
        _update_stats(entry)

        # Write to file
        if REQUEST_LOG_LEVEL in ["debug", "info"]:
            _write_to_file(entry)

        # Add request ID header for tracing
        response.headers["X-Request-ID"] = request_id

        return response

    # Register API endpoints for log access
    _register_log_endpoints(app)


def _register_log_endpoints(app: Flask):
    """Register API endpoints for accessing request logs."""

    @app.route("/api/debug/requests", methods=["GET"])
    def get_request_log_api():
        """Get recent request logs."""
        # Check for admin/debug access
        from flask import session

        if not session.get("user"):
            return {"error": "Authentication required"}, 401

        limit = request.args.get("limit", 100, type=int)
        status_filter = request.args.get("status", type=int)
        method_filter = request.args.get("method")
        path_filter = request.args.get("path")
        min_duration = request.args.get("min_duration", type=float)

        logs = get_request_logs(
            limit=limit,
            status=status_filter,
            method=method_filter,
            path_contains=path_filter,
            min_duration_ms=min_duration,
        )

        return {"logs": logs, "count": len(logs)}

    @app.route("/api/debug/requests/stats", methods=["GET"])
    def get_request_stats_api():
        """Get request statistics."""
        from flask import session

        if not session.get("user"):
            return {"error": "Authentication required"}, 401

        return get_request_stats()

    @app.route("/api/debug/requests/clear", methods=["POST"])
    def clear_request_logs_api():
        """Clear request log buffer."""
        from flask import session

        if not session.get("user"):
            return {"error": "Authentication required"}, 401

        clear_request_logs()
        return {"success": True, "message": "Request logs cleared"}


def get_request_logs(
    limit: int = 100,
    status: Optional[int] = None,
    method: Optional[str] = None,
    path_contains: Optional[str] = None,
    min_duration_ms: Optional[float] = None,
) -> List[Dict]:
    """
    Get recent request logs from buffer.

    Args:
        limit: Maximum number of logs to return
        status: Filter by HTTP status code
        method: Filter by HTTP method
        path_contains: Filter by path substring
        min_duration_ms: Filter by minimum duration

    Returns:
        List of log entries (newest first)
    """
    with _log_lock:
        logs = list(reversed(_log_buffer))

    # Apply filters
    if status is not None:
        logs = [l for l in logs if l["status"] == status]
    if method:
        logs = [l for l in logs if l["method"] == method.upper()]
    if path_contains:
        logs = [l for l in logs if path_contains in l["path"]]
    if min_duration_ms is not None:
        logs = [l for l in logs if l["duration_ms"] >= min_duration_ms]

    return logs[:limit]


def get_request_stats() -> Dict:
    """Get request statistics."""
    with _stats_lock:
        return {
            "total_requests": _stats["total_requests"],
            "total_errors": _stats["total_errors"],
            "error_rate": round(_stats["total_errors"] / max(_stats["total_requests"], 1) * 100, 2),
            "avg_duration_ms": round(_stats["avg_duration_ms"], 2),
            "status_counts": dict(_stats["status_counts"]),
            "slowest_requests": list(_stats["slowest_requests"][:10]),
        }


def clear_request_logs():
    """Clear the request log buffer and reset stats."""
    global _log_buffer, _stats
    with _log_lock:
        _log_buffer = []
    with _stats_lock:
        _stats = {
            "total_requests": 0,
            "total_errors": 0,
            "avg_duration_ms": 0,
            "status_counts": {},
            "slowest_requests": [],
        }
