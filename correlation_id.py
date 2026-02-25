#!/usr/bin/env python3
"""
Log Correlation ID Module

Provides request correlation IDs for distributed tracing and log correlation.

Features:
- Unique correlation ID per request
- Automatic injection into all log messages
- Header propagation for distributed tracing
- Response header inclusion for client correlation
- Context managers for background tasks
- Thread-safe correlation ID storage

Usage:
    from correlation_id import get_correlation_id, CorrelationIdMiddleware

    # In Flask app:
    app.before_request(generate_correlation_id)
    app.after_request(add_correlation_id_header)

    # In logs (automatic with CorrelationLogFilter):
    logger.info("Processing request")  # Includes [correlation_id] automatically

    # Access correlation ID:
    correlation_id = get_correlation_id()

    # For background tasks:
    with correlation_context("task-123"):
        do_background_work()
"""

import logging
import threading
import time
import uuid
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Optional

from flask import g, has_request_context, request

# Context variable for correlation ID (thread-safe)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Configuration
CORRELATION_ID_HEADER = "X-Correlation-ID"
CORRELATION_ID_HEADER_ALT = "X-Request-ID"  # Alternative header name
CORRELATION_ID_LOG_FORMAT = "[%(correlation_id)s] %(message)s"
CORRELATION_ID_PREFIX = ""  # Optional prefix for generated IDs

# Logger for this module
logger = logging.getLogger(__name__)


def generate_correlation_id() -> str:
    """
    Generate a new unique correlation ID.

    Format: timestamp_short-uuid (e.g., "1706745600-a1b2c3d4")
    This format provides:
    - Rough time ordering for debugging
    - Uniqueness across requests
    - Reasonable length for logging

    Returns:
        A unique correlation ID string
    """
    timestamp = int(time.time())
    short_uuid = uuid.uuid4().hex[:8]
    return f"{CORRELATION_ID_PREFIX}{timestamp}-{short_uuid}"


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID.

    Checks in order:
    1. Flask request context (g.correlation_id)
    2. Context variable (for background tasks)
    3. Returns None if no correlation ID is set

    Returns:
        The current correlation ID or None
    """
    # Try Flask request context first
    if has_request_context():
        return getattr(g, "correlation_id", None)

    # Fall back to context variable
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set
    """
    if has_request_context():
        g.correlation_id = correlation_id

    # Also set in context variable for thread safety
    _correlation_id.set(correlation_id)


class CorrelationLogFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to all log records.

    Usage:
        handler = logging.StreamHandler()
        handler.addFilter(CorrelationLogFilter())
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(correlation_id)s] %(name)s - %(levelname)s - %(message)s'
        ))
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record."""
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id or "-"
        return True


class CorrelationIdFormatter(logging.Formatter):
    """
    Custom formatter that includes correlation ID.

    Automatically adds correlation ID to log messages even if the
    format string doesn't include %(correlation_id)s.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with correlation ID."""
        # Ensure correlation_id is set
        if not hasattr(record, "correlation_id"):
            record.correlation_id = get_correlation_id() or "-"

        return super().format(record)


def init_correlation_logging(
    log_format: str = None, level: int = logging.INFO, include_correlation_id: bool = True
) -> None:
    """
    Initialize logging with correlation ID support.

    Args:
        log_format: Custom log format string (should include %(correlation_id)s)
        level: Logging level
        include_correlation_id: Whether to include correlation ID in format
    """
    if log_format is None:
        if include_correlation_id:
            log_format = "%(asctime)s [%(correlation_id)s] %(name)s - %(levelname)s - %(message)s"
        else:
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create formatter and filter
    formatter = CorrelationIdFormatter(log_format)
    correlation_filter = CorrelationLogFilter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Update all handlers
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(correlation_filter)

    # If no handlers, add a default one
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.addFilter(correlation_filter)
        root_logger.addHandler(handler)


def before_request_correlation() -> None:
    """
    Flask before_request handler to set up correlation ID.

    Extracts correlation ID from request headers if present,
    otherwise generates a new one.
    """
    # Try to get correlation ID from headers (for distributed tracing)
    correlation_id = request.headers.get(CORRELATION_ID_HEADER) or request.headers.get(
        CORRELATION_ID_HEADER_ALT
    )

    # Generate new ID if not provided
    if not correlation_id:
        correlation_id = generate_correlation_id()

    # Store in request context
    set_correlation_id(correlation_id)

    # Store request start time for duration logging
    g.request_start_time = time.time()


def after_request_correlation(response):
    """
    Flask after_request handler to add correlation ID to response.

    Also logs request completion with duration.
    """
    correlation_id = get_correlation_id()

    if correlation_id:
        # Add correlation ID to response headers
        response.headers[CORRELATION_ID_HEADER] = correlation_id

    # Log request completion with duration
    if hasattr(g, "request_start_time"):
        duration_ms = (time.time() - g.request_start_time) * 1000
        # Only log for non-static, non-health check requests
        if not request.path.startswith("/static") and request.path != "/health":
            logger.info(
                f"Request completed: {request.method} {request.path} "
                f"-> {response.status_code} ({duration_ms:.2f}ms)"
            )

    return response


class correlation_context:
    """
    Context manager for setting correlation ID in background tasks.

    Usage:
        # In background task:
        with correlation_context("task-123"):
            do_work()
            logger.info("Work done")  # Logs with [task-123]

        # Or generate a new ID:
        with correlation_context() as cid:
            print(f"Working with correlation ID: {cid}")
    """

    def __init__(self, correlation_id: str = None):
        """
        Initialize context manager.

        Args:
            correlation_id: Optional correlation ID. If not provided, generates one.
        """
        self.correlation_id = correlation_id or generate_correlation_id()
        self.previous_id = None

    def __enter__(self) -> str:
        """Set the correlation ID and return it."""
        self.previous_id = _correlation_id.get()
        _correlation_id.set(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Restore the previous correlation ID."""
        _correlation_id.set(self.previous_id)


def with_correlation_id(func: Callable = None, *, inherit: bool = True) -> Callable:
    """
    Decorator to ensure a function has a correlation ID.

    Args:
        func: The function to decorate
        inherit: Whether to inherit the current correlation ID or generate new

    Usage:
        @with_correlation_id
        def background_task():
            logger.info("Processing...")

        @with_correlation_id(inherit=False)
        def independent_task():
            logger.info("New correlation ID for this task")
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs) -> Any:
            current_id = get_correlation_id() if inherit else None
            with correlation_context(current_id):
                return f(*args, **kwargs)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def propagate_correlation_id(headers: dict = None) -> dict:
    """
    Get headers with correlation ID for outgoing requests.

    Use when making requests to other services to propagate tracing.

    Args:
        headers: Existing headers dict to extend (optional)

    Returns:
        Headers dict with correlation ID

    Usage:
        import requests
        headers = propagate_correlation_id({'Authorization': 'Bearer token'})
        requests.get('http://other-service/api', headers=headers)
    """
    if headers is None:
        headers = {}

    correlation_id = get_correlation_id()
    if correlation_id:
        headers[CORRELATION_ID_HEADER] = correlation_id

    return headers


def get_request_context() -> dict:
    """
    Get a dictionary of request context for logging/debugging.

    Returns:
        Dict with correlation_id, method, path, user, etc.
    """
    context = {
        "correlation_id": get_correlation_id(),
    }

    if has_request_context():
        context.update(
            {
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", "")[:100],
            }
        )

        # Add user info from session if available
        from flask import session

        if session.get("authenticated"):
            context["user_id"] = session.get("user_id")
            context["username"] = session.get("username")

    return context


class CorrelationIdMiddleware:
    """
    WSGI middleware for correlation ID handling.

    Alternative to Flask before_request/after_request handlers.
    Useful for handling correlation IDs at the WSGI level.

    Usage:
        app.wsgi_app = CorrelationIdMiddleware(app.wsgi_app)
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Extract or generate correlation ID
        correlation_id = (
            environ.get(f'HTTP_{CORRELATION_ID_HEADER.upper().replace("-", "_")}')
            or environ.get(f'HTTP_{CORRELATION_ID_HEADER_ALT.upper().replace("-", "_")}')
            or generate_correlation_id()
        )

        # Store in environment for Flask to pick up
        environ["correlation_id"] = correlation_id
        _correlation_id.set(correlation_id)

        def custom_start_response(status, headers, exc_info=None):
            # Add correlation ID to response headers
            headers.append((CORRELATION_ID_HEADER, correlation_id))
            return start_response(status, headers, exc_info)

        try:
            return self.app(environ, custom_start_response)
        finally:
            _correlation_id.set(None)


# Convenience function to set up Flask app
def init_app(app) -> None:
    """
    Initialize correlation ID support for a Flask app.

    Args:
        app: Flask application instance

    Usage:
        from correlation_id import init_app
        init_app(app)
    """
    # Register before/after request handlers
    app.before_request(before_request_correlation)
    app.after_request(after_request_correlation)

    # Initialize logging with correlation ID support
    init_correlation_logging()

    logger.info("Correlation ID support initialized")
