"""
Utility functions for Architect Dashboard.

This module provides common utility functions used across the application.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def get_version() -> str:
    """
    Return the current version of the Architect Dashboard.

    Returns:
        str: The version string in semantic versioning format.

    Examples:
        >>> get_version()
        '1.0.0'
    """
    return "1.0.0"


def ping() -> str:
    """
    Simple health check function.

    Returns:
        str: 'pong'

    Examples:
        >>> ping()
        'pong'
    """
    return "pong"


def validate_entity_data(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
    """
    Validate that required fields are present in entity data.

    This function checks if all required fields exist in the provided data
    dictionary and returns a result indicating success or failure with
    details about any missing fields.

    Args:
        data: Dictionary containing entity data to validate.
        required_fields: List of field names that must be present.

    Returns:
        Dictionary with validation result:
        - 'valid': Boolean indicating if validation passed
        - 'missing_fields': List of field names that were missing (if any)
        - 'message': Human-readable validation message

    Examples:
        >>> validate_entity_data({'name': 'Test', 'status': 'active'}, ['name'])
        {'valid': True, 'missing_fields': [], 'message': 'Validation passed'}

        >>> validate_entity_data({'name': 'Test'}, ['name', 'status'])
        {'valid': False, 'missing_fields': ['status'], 'message': 'Missing required fields: status'}
    """
    if not isinstance(data, dict):
        return {
            "valid": False,
            "missing_fields": required_fields,
            "message": "Data must be a dictionary",
        }

    missing = [field for field in required_fields if field not in data or data[field] is None]

    if missing:
        return {
            "valid": False,
            "missing_fields": missing,
            "message": f"Missing required fields: {', '.join(missing)}",
        }

    return {"valid": True, "missing_fields": [], "message": "Validation passed"}


def format_timestamp(dt: Optional[datetime] = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a datetime object as a string.

    Args:
        dt: Datetime object to format. Defaults to current time if None.
        format_str: strftime format string. Defaults to '%Y-%m-%d %H:%M:%S'.

    Returns:
        Formatted datetime string.

    Examples:
        >>> from datetime import datetime
        >>> format_timestamp(datetime(2024, 1, 15, 10, 30, 0))
        '2024-01-15 10:30:00'
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(format_str)


def sanitize_html(value: str) -> str:
    """
    Escape HTML special characters to prevent XSS attacks.

    Converts dangerous HTML characters to their entity equivalents:
    - & -> &amp;
    - < -> &lt;
    - > -> &gt;
    - " -> &quot;
    - ' -> &#x27;

    Args:
        value: String that may contain HTML.

    Returns:
        HTML-escaped string safe for rendering.

    Examples:
        >>> sanitize_html('<script>alert("xss")</script>')
        '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
        >>> sanitize_html("Hello <b>World</b>")
        'Hello &lt;b&gt;World&lt;/b&gt;'
        >>> sanitize_html("It's a test")
        "It&#x27;s a test"
    """
    import html

    if not isinstance(value, str):
        value = str(value)
    # Use html.escape which handles &, <, >, and optionally quotes
    escaped = html.escape(value, quote=True)
    # Also escape single quotes which html.escape doesn't do by default
    return escaped.replace("'", "&#x27;")


def sanitize_string(value: str, max_length: int = 255, escape_html: bool = True) -> str:
    """
    Sanitize a string by stripping whitespace, escaping HTML, and truncating.

    Args:
        value: String to sanitize.
        max_length: Maximum allowed length. Defaults to 255.
        escape_html: Whether to escape HTML characters. Defaults to True.

    Returns:
        Sanitized string safe for storage and display.

    Examples:
        >>> sanitize_string('  Hello World  ')
        'Hello World'
        >>> sanitize_string('A' * 300, max_length=10)
        'AAAAAAAAAA'
        >>> sanitize_string('<script>alert(1)</script>')
        '&lt;script&gt;alert(1)&lt;/script&gt;'
    """
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if escape_html:
        value = sanitize_html(value)
    return value[:max_length]


def sanitize_dict(
    data: Dict[str, Any], fields: List[str] = None, max_lengths: Dict[str, int] = None
) -> Dict[str, Any]:
    """
    Sanitize string fields in a dictionary to prevent XSS attacks.

    Applies HTML escaping and length limits to specified fields or all string fields.

    Args:
        data: Dictionary containing user input.
        fields: List of field names to sanitize. If None, sanitizes all string fields.
        max_lengths: Dict mapping field names to max lengths. Default is 255 for unlisted fields.

    Returns:
        New dictionary with sanitized values.

    Examples:
        >>> sanitize_dict({'name': '<b>Test</b>', 'count': 5})
        {'name': '&lt;b&gt;Test&lt;/b&gt;', 'count': 5}
        >>> sanitize_dict({'title': 'A' * 500}, max_lengths={'title': 100})
        {'title': 'AAAA...'}  # truncated to 100 chars
    """
    if not isinstance(data, dict):
        return data

    max_lengths = max_lengths or {}
    result = {}

    for key, value in data.items():
        if fields is not None and key not in fields:
            result[key] = value
        elif isinstance(value, str):
            max_len = max_lengths.get(key, 255)
            result[key] = sanitize_string(value, max_length=max_len)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, fields, max_lengths)
        elif isinstance(value, list):
            result[key] = [
                sanitize_string(item) if isinstance(item, str) else item for item in value
            ]
        else:
            result[key] = value

    return result


def format_bytes(size: int, precision: int = 2) -> str:
    """
    Format a byte size into a human-readable string (KB, MB, GB, etc.).

    Converts raw byte counts into appropriately scaled units for display.
    Uses binary units (1 KB = 1024 bytes).

    Args:
        size: Size in bytes to format.
        precision: Number of decimal places (default: 2).

    Returns:
        Formatted string with appropriate unit (e.g., "1.50 MB").

    Examples:
        >>> format_bytes(1024)
        '1.00 KB'
        >>> format_bytes(1536, precision=1)
        '1.5 KB'
        >>> format_bytes(1073741824)
        '1.00 GB'
        >>> format_bytes(500)
        '500 B'
        >>> format_bytes(0)
        '0 B'
    """
    if size < 0:
        return f"-{format_bytes(-size, precision)}"
    if size == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0

    size_float = float(size)
    while size_float >= 1024 and unit_index < len(units) - 1:
        size_float /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size_float)} B"
    return f"{size_float:.{precision}f} {units[unit_index]}"


def calculate_progress(completed: int, total: int) -> Dict[str, Any]:
    """
    Calculate progress percentage and status for task tracking.

    This function computes the completion percentage and provides a
    human-readable status based on the progress level. Useful for
    tracking milestones, features, and project completion.

    Args:
        completed: Number of completed items.
        total: Total number of items.

    Returns:
        Dictionary containing:
        - 'percentage': Integer percentage (0-100)
        - 'completed': Number of completed items
        - 'total': Total number of items
        - 'remaining': Number of remaining items
        - 'status': Human-readable status string

    Examples:
        >>> calculate_progress(5, 10)
        {'percentage': 50, 'completed': 5, 'total': 10, 'remaining': 5, 'status': 'in_progress'}

        >>> calculate_progress(10, 10)
        {'percentage': 100, 'completed': 10, 'total': 10, 'remaining': 0, 'status': 'complete'}

        >>> calculate_progress(0, 5)
        {'percentage': 0, 'completed': 0, 'total': 5, 'remaining': 5, 'status': 'not_started'}
    """
    if total <= 0:
        return {"percentage": 0, "completed": 0, "total": 0, "remaining": 0, "status": "empty"}

    completed = max(0, min(completed, total))  # Clamp to valid range
    percentage = int((completed / total) * 100)
    remaining = total - completed

    if percentage == 0:
        status = "not_started"
    elif percentage == 100:
        status = "complete"
    elif percentage >= 75:
        status = "almost_done"
    elif percentage >= 25:
        status = "in_progress"
    else:
        status = "just_started"

    return {
        "percentage": percentage,
        "completed": completed,
        "total": total,
        "remaining": remaining,
        "status": status,
    }


def format_api_response(
    success: bool,
    data: Optional[Any] = None,
    error: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Format a standardized API response structure.

    Claude Test Feature - This function provides consistent API response
    formatting for integration testing and production use.

    Args:
        success: Whether the operation was successful.
        data: The response payload (for successful responses).
        error: Error message (for failed responses).
        meta: Optional metadata (pagination, timestamps, etc.).

    Returns:
        Dictionary with standardized response structure:
        - 'success': Boolean indicating operation success
        - 'data': Response payload (None if error)
        - 'error': Error message (None if success)
        - 'meta': Optional metadata dictionary
        - 'timestamp': ISO format timestamp of response

    Examples:
        >>> format_api_response(True, data={'id': 1, 'name': 'Test'})
        {'success': True, 'data': {'id': 1, 'name': 'Test'}, 'error': None, 'meta': None, 'timestamp': '...'}

        >>> format_api_response(False, error='Not found')
        {'success': False, 'data': None, 'error': 'Not found', 'meta': None, 'timestamp': '...'}
    """
    return {
        "success": success,
        "data": data if success else None,
        "error": error if not success else None,
        "meta": meta,
        "timestamp": datetime.now().isoformat(),
    }


class WidgetDataHandler:
    """
    Widget data handler for dashboard components.

    Workflow Test Feature - This class provides a robust widget data handling
    system that:
    - Displays data correctly with proper formatting
    - Updates in real-time with change tracking
    - Handles errors gracefully without crashing

    Examples:
        >>> widget = WidgetDataHandler('stats', {'count': 0})
        >>> widget.get_display_data()
        {'widget_id': 'stats', 'data': {'count': 0}, 'status': 'ready', ...}

        >>> widget.update({'count': 5})
        >>> widget.data
        {'count': 5}
    """

    def __init__(self, widget_id: str, initial_data: Optional[Dict[str, Any]] = None):
        """
        Initialize widget with ID and optional initial data.

        Args:
            widget_id: Unique identifier for the widget.
            initial_data: Initial data dictionary. Defaults to empty dict.
        """
        self.widget_id = widget_id
        self.data = initial_data or {}
        self.last_updated = datetime.now()
        self.update_count = 0
        self.error_state = None
        self.status = "ready"

    def update(self, new_data: Dict[str, Any]) -> bool:
        """
        Update widget data with real-time tracking.

        Args:
            new_data: New data to merge with existing data.

        Returns:
            True if update succeeded, False if error occurred.
        """
        try:
            if not isinstance(new_data, dict):
                self.error_state = "Invalid data type: expected dictionary"
                self.status = "error"
                return False

            self.data.update(new_data)
            self.last_updated = datetime.now()
            self.update_count += 1
            self.error_state = None
            self.status = "ready"
            return True
        except Exception as e:
            self.error_state = str(e)
            self.status = "error"
            return False

    def get_display_data(self) -> Dict[str, Any]:
        """
        Get formatted data for widget display.

        Returns:
            Dictionary with widget state for rendering:
            - widget_id: The widget identifier
            - data: Current widget data
            - status: Current status (ready/error/loading)
            - last_updated: ISO timestamp of last update
            - update_count: Number of updates performed
            - error: Error message if in error state
        """
        return {
            "widget_id": self.widget_id,
            "data": self.data,
            "status": self.status,
            "last_updated": self.last_updated.isoformat(),
            "update_count": self.update_count,
            "error": self.error_state,
        }

    def reset(self) -> None:
        """Reset widget to initial state."""
        self.data = {}
        self.last_updated = datetime.now()
        self.update_count = 0
        self.error_state = None
        self.status = "ready"

    def set_loading(self) -> None:
        """Set widget to loading state."""
        self.status = "loading"

    def set_error(self, message: str) -> None:
        """
        Set widget to error state with message.

        Args:
            message: Error message to display.
        """
        self.error_state = message
        self.status = "error"

    def clear_error(self) -> None:
        """Clear error state and return to ready."""
        self.error_state = None
        self.status = "ready"


def normalize_status(status: str, valid_statuses: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Normalize a status string to a standard format.

    E2E Test Feature 1766597951 - This function provides status normalization
    for consistent status handling across the dashboard.

    Args:
        status: The status string to normalize.
        valid_statuses: Optional list of valid status values. Defaults to
                       ['pending', 'in_progress', 'completed', 'failed', 'cancelled'].

    Returns:
        Dictionary containing:
        - 'original': The original input status
        - 'normalized': The normalized status string (lowercase, trimmed)
        - 'valid': Boolean indicating if status is in valid_statuses
        - 'suggested': Suggested valid status if invalid (or None)

    Examples:
        >>> normalize_status('  In Progress  ')
        {'original': '  In Progress  ', 'normalized': 'in_progress', 'valid': True, 'suggested': None}

        >>> normalize_status('DONE')
        {'original': 'DONE', 'normalized': 'done', 'valid': False, 'suggested': 'completed'}

        >>> normalize_status('pending', ['pending', 'done'])
        {'original': 'pending', 'normalized': 'pending', 'valid': True, 'suggested': None}
    """
    if valid_statuses is None:
        valid_statuses = ["pending", "in_progress", "completed", "failed", "cancelled"]

    # Normalize: lowercase, strip whitespace, replace spaces with underscores
    normalized = status.strip().lower().replace(" ", "_").replace("-", "_")

    # Check if valid
    is_valid = normalized in valid_statuses

    # Suggest closest match if invalid
    suggested = None
    if not is_valid:
        # Common mappings
        mappings = {
            "done": "completed",
            "complete": "completed",
            "finished": "completed",
            "active": "in_progress",
            "working": "in_progress",
            "started": "in_progress",
            "waiting": "pending",
            "queued": "pending",
            "error": "failed",
            "stopped": "cancelled",
            "aborted": "cancelled",
        }
        suggested = mappings.get(normalized)

    return {"original": status, "normalized": normalized, "valid": is_valid, "suggested": suggested}


def validate_lifecycle_state(current_state: str, target_state: str) -> Dict[str, Any]:
    """
    Validate if a lifecycle state transition is allowed.

    E2E Full Lifecycle 1766629424 - This function validates state transitions
    for features, bugs, and tasks following a defined lifecycle.

    Args:
        current_state: The current state of the entity.
        target_state: The desired target state.

    Returns:
        Dictionary containing:
        - 'allowed': Boolean indicating if transition is valid
        - 'current': The current state (normalized)
        - 'target': The target state (normalized)
        - 'message': Human-readable message about the transition

    Examples:
        >>> validate_lifecycle_state('pending', 'in_progress')
        {'allowed': True, 'current': 'pending', 'target': 'in_progress', 'message': 'Transition allowed'}

        >>> validate_lifecycle_state('completed', 'pending')
        {'allowed': False, 'current': 'completed', 'target': 'pending', 'message': 'Cannot transition from completed to pending'}
    """
    # Define valid transitions for each state
    valid_transitions = {
        "pending": ["in_progress", "cancelled"],
        "in_progress": ["completed", "failed", "pending", "cancelled"],
        "completed": ["in_progress"],  # Allow reopening
        "failed": ["pending", "in_progress"],  # Allow retry
        "cancelled": ["pending"],  # Allow reactivation
    }

    # Normalize states
    current = current_state.strip().lower().replace(" ", "_").replace("-", "_")
    target = target_state.strip().lower().replace(" ", "_").replace("-", "_")

    # Same state is always allowed
    if current == target:
        return {
            "allowed": True,
            "current": current,
            "target": target,
            "message": "No state change required",
        }

    # Check if transition is valid
    allowed_targets = valid_transitions.get(current, [])
    is_allowed = target in allowed_targets

    if is_allowed:
        message = "Transition allowed"
    else:
        message = f"Cannot transition from {current} to {target}"

    return {"allowed": is_allowed, "current": current, "target": target, "message": message}


def parse_priority(value: Any, default: str = "medium") -> Dict[str, Any]:
    """
    Parse and validate priority values for tasks, features, and bugs.

    Claude Test Feature - This function provides priority parsing and
    validation for consistent priority handling across the dashboard.

    Args:
        value: The priority value to parse (string, int, or None).
        default: Default priority if value is invalid. Defaults to 'medium'.

    Returns:
        Dictionary containing:
        - 'priority': The validated priority string
        - 'level': Numeric level (1-4) for sorting
        - 'valid': Boolean indicating if input was valid
        - 'color': Suggested color for UI display

    Examples:
        >>> parse_priority('high')
        {'priority': 'high', 'level': 3, 'valid': True, 'color': 'orange'}

        >>> parse_priority(4)
        {'priority': 'critical', 'level': 4, 'valid': True, 'color': 'red'}

        >>> parse_priority('invalid')
        {'priority': 'medium', 'level': 2, 'valid': False, 'color': 'blue'}
    """
    priority_map = {
        "low": {"level": 1, "color": "gray"},
        "medium": {"level": 2, "color": "blue"},
        "high": {"level": 3, "color": "orange"},
        "critical": {"level": 4, "color": "red"},
    }

    level_to_priority = {1: "low", 2: "medium", 3: "high", 4: "critical"}

    # Handle None
    if value is None:
        info = priority_map[default]
        return {"priority": default, "level": info["level"], "valid": False, "color": info["color"]}

    # Handle integer levels
    if isinstance(value, int):
        if 1 <= value <= 4:
            priority = level_to_priority[value]
            info = priority_map[priority]
            return {"priority": priority, "level": value, "valid": True, "color": info["color"]}

    # Handle string values
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in priority_map:
            info = priority_map[normalized]
            return {
                "priority": normalized,
                "level": info["level"],
                "valid": True,
                "color": info["color"],
            }

    # Invalid value - use default
    info = priority_map[default]
    return {"priority": default, "level": info["level"], "valid": False, "color": info["color"]}


class ErrorContext:
    """
    Context manager for structured error handling.

    Feature #2: error-handling - Provides consistent error handling with
    context tracking, automatic cleanup, and detailed error information.

    Examples:
        >>> with ErrorContext('database_operation', {'table': 'users'}) as ctx:
        ...     # perform operation
        ...     ctx.add_detail('rows_affected', 5)
        >>> ctx.success
        True

        >>> with ErrorContext('api_call') as ctx:
        ...     raise ValueError("Invalid input")
        >>> ctx.success
        False
        >>> ctx.error_type
        'ValueError'
    """

    def __init__(self, operation: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize error context.

        Args:
            operation: Name of the operation being performed.
            context: Optional context data for the operation.
        """
        self.operation = operation
        self.context = context or {}
        self.details: Dict[str, Any] = {}
        self.success = False
        self.error: Optional[Exception] = None
        self.error_type: Optional[str] = None
        self.error_message: Optional[str] = None
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None

    def __enter__(self) -> "ErrorContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.end_time = datetime.now()

        if exc_type is None:
            self.success = True
        else:
            self.success = False
            self.error = exc_val
            self.error_type = exc_type.__name__
            self.error_message = str(exc_val)

        # Don't suppress the exception
        return False

    def add_detail(self, key: str, value: Any) -> None:
        """Add a detail to the context."""
        self.details[key] = value

    def get_duration_ms(self) -> int:
        """Get operation duration in milliseconds."""
        end = self.end_time or datetime.now()
        delta = end - self.start_time
        return int(delta.total_seconds() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging/storage."""
        return {
            "operation": self.operation,
            "success": self.success,
            "context": self.context,
            "details": self.details,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "duration_ms": self.get_duration_ms(),
            "timestamp": self.start_time.isoformat(),
        }


def classify_error(error: Exception) -> Dict[str, Any]:
    """
    Classify an error by type and severity.

    Feature #2: error-handling - Provides error classification for
    consistent error handling and reporting.

    Args:
        error: The exception to classify.

    Returns:
        Dictionary containing:
        - 'category': Error category (validation, database, network, etc.)
        - 'severity': Error severity (low, medium, high, critical)
        - 'recoverable': Whether the error is potentially recoverable
        - 'user_message': Safe message to show to users
        - 'log_level': Suggested logging level

    Examples:
        >>> classify_error(ValueError("invalid input"))
        {'category': 'validation', 'severity': 'low', 'recoverable': True, ...}

        >>> classify_error(ConnectionError("timeout"))
        {'category': 'network', 'severity': 'medium', 'recoverable': True, ...}
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # Classification rules
    if error_type in ("ValueError", "TypeError", "KeyError", "AttributeError"):
        return {
            "category": "validation",
            "severity": "low",
            "recoverable": True,
            "user_message": "Invalid input provided",
            "log_level": "warning",
        }

    if error_type in ("ConnectionError", "TimeoutError", "ConnectionRefusedError"):
        return {
            "category": "network",
            "severity": "medium",
            "recoverable": True,
            "user_message": "Connection error, please try again",
            "log_level": "error",
        }

    if "database" in error_msg or "sqlite" in error_msg or error_type == "OperationalError":
        return {
            "category": "database",
            "severity": "high",
            "recoverable": True,
            "user_message": "Database error occurred",
            "log_level": "error",
        }

    if "permission" in error_msg or "access denied" in error_msg:
        return {
            "category": "permission",
            "severity": "medium",
            "recoverable": False,
            "user_message": "Permission denied",
            "log_level": "warning",
        }

    if "memory" in error_msg or error_type == "MemoryError":
        return {
            "category": "resource",
            "severity": "critical",
            "recoverable": False,
            "user_message": "System resource error",
            "log_level": "critical",
        }

    if error_type in ("FileNotFoundError", "IOError", "OSError"):
        return {
            "category": "filesystem",
            "severity": "medium",
            "recoverable": True,
            "user_message": "File operation failed",
            "log_level": "error",
        }

    # Default classification
    return {
        "category": "unknown",
        "severity": "medium",
        "recoverable": False,
        "user_message": "An unexpected error occurred",
        "log_level": "error",
    }


def format_error_response(
    error: Exception, include_trace: bool = False, request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format an error into a standardized API response.

    Feature #2: error-handling - Provides consistent error response
    formatting for API endpoints.

    Args:
        error: The exception to format.
        include_trace: Whether to include stack trace (dev only).
        request_id: Optional request ID for tracking.

    Returns:
        Dictionary with standardized error response structure.

    Examples:
        >>> format_error_response(ValueError("bad input"))
        {'success': False, 'error': {...}, 'timestamp': '...'}
    """
    import traceback

    classification = classify_error(error)

    response = {
        "success": False,
        "error": {
            "type": type(error).__name__,
            "message": classification["user_message"],
            "category": classification["category"],
            "recoverable": classification["recoverable"],
        },
        "timestamp": datetime.now().isoformat(),
    }

    if request_id:
        response["request_id"] = request_id

    if include_trace:
        response["error"]["detail"] = str(error)
        response["error"]["trace"] = traceback.format_exc()

    return response


def safe_execute(
    func, *args, default: Any = None, on_error: Optional[callable] = None, **kwargs
) -> Any:
    """
    Execute a function safely with error handling.

    Feature #2: error-handling - Wraps function execution with
    automatic error handling and fallback values.

    Args:
        func: Function to execute.
        *args: Positional arguments for the function.
        default: Default value to return on error.
        on_error: Optional callback for error handling.
        **kwargs: Keyword arguments for the function.

    Returns:
        Function result or default value on error.

    Examples:
        >>> safe_execute(int, "123")
        123

        >>> safe_execute(int, "invalid", default=0)
        0

        >>> safe_execute(lambda x: x / 0, 1, default=-1)
        -1
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if on_error:
            on_error(e)
        return default


def estimate_completion(completed: int, total: int, elapsed_seconds: float) -> Dict[str, Any]:
    """
    Estimate time to completion based on current progress.

    E2E Test Feature 1766695304 - This function calculates estimated
    completion time for tasks based on current progress rate.

    Args:
        completed: Number of items completed so far.
        total: Total number of items to complete.
        elapsed_seconds: Time elapsed so far in seconds.

    Returns:
        Dictionary containing:
        - 'percentage': Current completion percentage
        - 'remaining': Number of items remaining
        - 'rate': Items per second
        - 'eta_seconds': Estimated seconds until completion
        - 'eta_formatted': Human-readable ETA string

    Examples:
        >>> estimate_completion(50, 100, 60.0)
        {'percentage': 50, 'remaining': 50, 'rate': 0.83, 'eta_seconds': 60.0, 'eta_formatted': '1m 0s'}

        >>> estimate_completion(0, 100, 0)
        {'percentage': 0, 'remaining': 100, 'rate': 0, 'eta_seconds': None, 'eta_formatted': 'Unknown'}
    """
    if total <= 0:
        return {
            "percentage": 0,
            "remaining": 0,
            "rate": 0,
            "eta_seconds": None,
            "eta_formatted": "N/A",
        }

    completed = max(0, min(completed, total))
    remaining = total - completed
    percentage = int((completed / total) * 100)

    # Calculate rate
    if elapsed_seconds > 0 and completed > 0:
        rate = round(completed / elapsed_seconds, 2)
        eta_seconds = remaining / rate if rate > 0 else None
    else:
        rate = 0
        eta_seconds = None

    # Format ETA
    if eta_seconds is None:
        eta_formatted = "Unknown"
    elif eta_seconds < 60:
        eta_formatted = f"{int(eta_seconds)}s"
    elif eta_seconds < 3600:
        minutes = int(eta_seconds // 60)
        seconds = int(eta_seconds % 60)
        eta_formatted = f"{minutes}m {seconds}s"
    else:
        hours = int(eta_seconds // 3600)
        minutes = int((eta_seconds % 3600) // 60)
        eta_formatted = f"{hours}h {minutes}m"

    return {
        "percentage": percentage,
        "remaining": remaining,
        "rate": rate,
        "eta_seconds": eta_seconds,
        "eta_formatted": eta_formatted,
    }


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length with a suffix.

    E2E Test Feature 1766695630 - This function provides safe string
    truncation for display purposes in the dashboard.

    Args:
        text: The string to truncate.
        max_length: Maximum length including suffix. Defaults to 100.
        suffix: String to append when truncated. Defaults to '...'.

    Returns:
        Truncated string with suffix if it exceeded max_length,
        otherwise the original string.

    Examples:
        >>> truncate_string('Hello World', max_length=8)
        'Hello...'

        >>> truncate_string('Short', max_length=10)
        'Short'

        >>> truncate_string('Long text here', max_length=10, suffix='>')
        'Long text>'
    """
    if not isinstance(text, str):
        text = str(text)

    if len(text) <= max_length:
        return text

    # Calculate how much of the original text we can keep
    truncate_at = max_length - len(suffix)
    if truncate_at <= 0:
        return suffix[:max_length]

    return text[:truncate_at] + suffix


def merge_dicts(
    base: Dict[str, Any], override: Dict[str, Any], deep: bool = False
) -> Dict[str, Any]:
    """
    Merge two dictionaries with override taking precedence.

    E2E Test Feature 1766695896 - This function provides dictionary
    merging with optional deep merge for nested dictionaries.

    Args:
        base: The base dictionary.
        override: Dictionary with values to override.
        deep: If True, recursively merge nested dictionaries.

    Returns:
        New dictionary with merged values.

    Examples:
        >>> merge_dicts({'a': 1, 'b': 2}, {'b': 3, 'c': 4})
        {'a': 1, 'b': 3, 'c': 4}

        >>> merge_dicts({'a': {'x': 1}}, {'a': {'y': 2}}, deep=True)
        {'a': {'x': 1, 'y': 2}}
    """
    result = base.copy()

    for key, value in override.items():
        if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, deep=True)
        else:
            result[key] = value

    return result


def chunk_list(items: list, chunk_size: int) -> list:
    """
    Split a list into chunks of specified size.

    E2E Test Feature 1766696767 - This function provides list chunking
    for batch processing and pagination use cases.

    Args:
        items: List to split into chunks.
        chunk_size: Maximum size of each chunk (must be positive).

    Returns:
        List of chunks (sublists).

    Raises:
        ValueError: If chunk_size is not positive.

    Examples:
        >>> chunk_list([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]

        >>> chunk_list(['a', 'b', 'c'], 3)
        [['a', 'b', 'c']]
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if not items:
        return []

    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def dedupe_list(items: list, key=None) -> list:
    """
    Remove duplicates from a list while preserving order.

    E2E Test Feature 1766714906/1766714907 - This function provides
    deduplication with optional key function for complex objects.

    Args:
        items: List to deduplicate.
        key: Optional function to extract comparison key from items.

    Returns:
        New list with duplicates removed, order preserved.

    Examples:
        >>> dedupe_list([1, 2, 2, 3, 1, 4])
        [1, 2, 3, 4]

        >>> dedupe_list([{'id': 1}, {'id': 2}, {'id': 1}], key=lambda x: x['id'])
        [{'id': 1}, {'id': 2}]
    """
    if not items:
        return []

    seen = set()
    result = []

    for item in items:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)

    return result


def clamp_value(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value to a specified range.

    Feature #4: Claude Test Feature - This function provides value
    clamping for ensuring values stay within bounds.

    Args:
        value: The value to clamp.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        The clamped value.

    Raises:
        ValueError: If min_val > max_val.

    Examples:
        >>> clamp_value(5, 0, 10)
        5
        >>> clamp_value(-5, 0, 10)
        0
        >>> clamp_value(15, 0, 10)
        10
    """
    if min_val > max_val:
        raise ValueError("min_val cannot be greater than max_val")

    return max(min_val, min(value, max_val))


# Alias for clamp_value
clamp_number = clamp_value


def group_by(items: list, key) -> dict:
    """
    Group items by a key function.

    Feature #5: Workflow Test Feature - This function provides data
    grouping for widget displays and real-time updates.

    Args:
        items: List of items to group.
        key: Function to extract grouping key from each item.

    Returns:
        Dictionary mapping keys to lists of items.

    Examples:
        >>> group_by([{'type': 'a', 'val': 1}, {'type': 'b', 'val': 2}, {'type': 'a', 'val': 3}], lambda x: x['type'])
        {'a': [{'type': 'a', 'val': 1}, {'type': 'a', 'val': 3}], 'b': [{'type': 'b', 'val': 2}]}
    """
    result = {}
    for item in items:
        k = key(item)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return result


def flatten_list(nested: list, depth: int = 1) -> list:
    """
    Flatten a nested list to a specified depth.

    Feature #4: E2E Full Lifecycle 1766729999 - This function provides
    list flattening for data processing pipelines.

    Args:
        nested: The nested list to flatten.
        depth: How many levels to flatten (default 1, -1 for unlimited).

    Returns:
        Flattened list.

    Examples:
        >>> flatten_list([[1, 2], [3, 4]])
        [1, 2, 3, 4]

        >>> flatten_list([[[1, 2]], [[3, 4]]], depth=2)
        [1, 2, 3, 4]
    """
    if depth == 0:
        return nested

    result = []
    for item in nested:
        if isinstance(item, list):
            if depth == 1:
                result.extend(item)
            else:
                result.extend(flatten_list(item, depth - 1 if depth > 0 else -1))
        else:
            result.append(item)
    return result


def hello_world() -> str:
    """
    Simple test function that returns hello world.

    This function is used for testing the autonomous orchestrator system.

    Returns:
        str: The string "hello world"

    Examples:
        >>> hello_world()
        'hello world'
    """
    return "hello world"


def safe_get(data: dict, *keys, default=None):
    """
    Safely get a nested value from a dictionary.

    Feature #6: Claude Test Feature - This function provides safe
    access to nested dictionary values without raising KeyError.

    Args:
        data: The dictionary to access.
        *keys: Variable number of keys for nested access.
        default: Value to return if key path doesn't exist.

    Returns:
        The value at the key path, or default if not found.

    Examples:
        >>> safe_get({'a': {'b': 1}}, 'a', 'b')
        1

        >>> safe_get({'a': 1}, 'b', 'c', default='missing')
        'missing'
    """
    result = data
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    return result


def is_valid_email(email: str) -> bool:
    """
    Validate an email address format.

    This function checks if the provided string is a valid email address
    using a regex pattern that covers common email formats. It validates:
    - Local part (before @): alphanumeric, dots, hyphens, underscores, plus signs
    - Domain part (after @): valid domain with at least one dot
    - TLD: 2-10 characters (covers standard TLDs like .com, .org, .museum)

    Args:
        email: The email address string to validate.

    Returns:
        True if the email format is valid, False otherwise.

    Examples:
        >>> is_valid_email('user@example.com')
        True

        >>> is_valid_email('user.name+tag@sub.domain.org')
        True

        >>> is_valid_email('invalid-email')
        False

        >>> is_valid_email('@nodomain.com')
        False

        >>> is_valid_email('user@')
        False

        >>> is_valid_email('')
        False
    """
    import re

    if not email or not isinstance(email, str):
        return False

    # Strip whitespace
    email = email.strip()

    if not email:
        return False

    # Email regex pattern
    # - Local part: alphanumeric, dots, hyphens, underscores, plus signs
    # - @ symbol
    # - Domain: alphanumeric and hyphens, with dots separating subdomains
    # - TLD: 2-10 alphabetic characters
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,10}$"

    # Additional checks
    if ".." in email:  # No consecutive dots
        return False

    if email.startswith(".") or email.startswith("-"):
        return False

    # Split and validate parts
    if email.count("@") != 1:
        return False

    local, domain = email.split("@")

    if not local or not domain:
        return False

    if local.startswith(".") or local.endswith("."):
        return False

    if domain.startswith(".") or domain.startswith("-"):
        return False

    if domain.endswith("-"):
        return False

    return bool(re.match(pattern, email))


def generate_id(length: int = 8) -> str:
    """
    Generate a random alphanumeric ID.

    This function creates a random string of uppercase letters and digits,
    useful for generating unique identifiers for tasks, sessions, or entities.

    Args:
        length: Length of the ID to generate. Defaults to 8.

    Returns:
        A random alphanumeric string of the specified length.

    Examples:
        >>> len(generate_id())
        8

        >>> generate_id(12)  # doctest: +SKIP
        'A1B2C3D4E5F6'

        >>> generate_id().isalnum()
        True
    """
    import random
    import string

    if length <= 0:
        return ""

    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: callable = None,
):
    """
    Decorator that retries a function with exponential backoff on failure.

    This decorator wraps a function and automatically retries it when specified
    exceptions occur. The delay between retries increases exponentially, with
    optional jitter to prevent thundering herd problems.

    Args:
        max_retries: Maximum number of retry attempts. Defaults to 3.
        base_delay: Initial delay in seconds before first retry. Defaults to 1.0.
        max_delay: Maximum delay in seconds between retries. Defaults to 60.0.
        exponential_base: Base for exponential backoff calculation. Defaults to 2.0.
        exceptions: Tuple of exception types to catch and retry. Defaults to (Exception,).
        on_retry: Optional callback function called on each retry with
                  (exception, attempt, delay) arguments.

    Returns:
        Decorated function that implements retry logic.

    Examples:
        >>> @retry_with_backoff(max_retries=3, base_delay=0.1)
        ... def flaky_function():
        ...     # This function might fail sometimes
        ...     pass

        >>> @retry_with_backoff(max_retries=5, exceptions=(ConnectionError, TimeoutError))
        ... def fetch_data():
        ...     # Retry only on connection/timeout errors
        ...     pass

        >>> def log_retry(exc, attempt, delay):
        ...     print(f"Retry {attempt}, waiting {delay}s: {exc}")
        >>> @retry_with_backoff(max_retries=3, on_retry=log_retry)
        ... def operation():
        ...     pass
    """
    import random as rand
    import time
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Final attempt failed, raise the exception
                        raise

                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (exponential_base**attempt), max_delay)
                    # Add jitter (±25%) to prevent thundering herd
                    jitter = delay * 0.25 * (rand.random() * 2 - 1)
                    actual_delay = max(0, delay + jitter)

                    # Call on_retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1, actual_delay)
                        except Exception:
                            pass  # Don't let callback errors affect retry logic

                    time.sleep(actual_delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def rate_limiter(
    calls_per_second: float = 1.0, burst: int = 1, block: bool = True, on_limited: callable = None
):
    """
    Decorator that limits the rate at which a function can be called.

    Implements a token bucket algorithm for rate limiting. Allows burst
    capacity for handling spikes while maintaining average rate limits.

    Args:
        calls_per_second: Maximum average calls per second. Defaults to 1.0.
        burst: Maximum burst size (tokens in bucket). Defaults to 1.
            Higher values allow more calls in quick succession.
        block: If True, blocks until rate limit allows. If False, raises
            RateLimitExceeded immediately. Defaults to True.
        on_limited: Optional callback called when rate limited with
            (wait_time,) argument.

    Returns:
        Decorated function with rate limiting.

    Raises:
        RateLimitExceeded: When block=False and rate limit is exceeded.

    Examples:
        >>> @rate_limiter(calls_per_second=2)
        ... def api_call():
        ...     return 'response'

        >>> @rate_limiter(calls_per_second=10, burst=5)
        ... def batch_operation():
        ...     # Allow bursts of up to 5 calls
        ...     pass

        >>> @rate_limiter(calls_per_second=1, block=False)
        ... def non_blocking_call():
        ...     # Raises RateLimitExceeded if called too fast
        ...     pass
    """
    import threading
    import time
    from functools import wraps

    class RateLimitExceeded(Exception):
        """Raised when rate limit is exceeded and block=False."""

        def __init__(self, wait_time: float):
            self.wait_time = wait_time
            super().__init__(f"Rate limit exceeded. Retry after {wait_time:.2f}s")

    def decorator(func):
        # Token bucket state
        tokens = burst
        last_update = time.monotonic()
        lock = threading.Lock()

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal tokens, last_update

            with lock:
                now = time.monotonic()
                elapsed = now - last_update
                last_update = now

                # Add tokens based on elapsed time
                tokens = min(burst, tokens + elapsed * calls_per_second)

                if tokens >= 1:
                    # Consume a token and proceed
                    tokens -= 1
                else:
                    # Calculate wait time
                    wait_time = (1 - tokens) / calls_per_second

                    if not block:
                        raise RateLimitExceeded(wait_time)

                    # Call on_limited callback if provided
                    if on_limited:
                        try:
                            on_limited(wait_time)
                        except Exception:
                            pass

                    # Wait and then consume token
                    time.sleep(wait_time)
                    tokens = 0
                    last_update = time.monotonic()

            return func(*args, **kwargs)

        # Attach RateLimitExceeded to wrapper for easy access
        wrapper.RateLimitExceeded = RateLimitExceeded

        # Add method to check current token count
        def get_tokens():
            with lock:
                now = time.monotonic()
                elapsed = now - last_update
                return min(burst, tokens + elapsed * calls_per_second)

        wrapper.get_tokens = get_tokens

        return wrapper

    return decorator


def parse_duration(duration_str: str) -> int:
    """
    Parse a duration string into seconds.

    Supports formats like '1h30m', '2h', '45m', '30s', '1h30m45s', '90m', etc.

    Args:
        duration_str: Duration string with units (h=hours, m=minutes, s=seconds).
                     Can also be just a number (interpreted as seconds).

    Returns:
        Total duration in seconds as an integer.

    Raises:
        ValueError: If the duration string format is invalid.

    Examples:
        >>> parse_duration('1h30m')
        5400

        >>> parse_duration('2h')
        7200

        >>> parse_duration('45m')
        2700

        >>> parse_duration('30s')
        30

        >>> parse_duration('1h30m45s')
        5445

        >>> parse_duration('90')
        90
    """
    import re

    if not duration_str or not isinstance(duration_str, str):
        raise ValueError("Duration must be a non-empty string")

    duration_str = duration_str.strip().lower()

    if not duration_str:
        raise ValueError("Duration must be a non-empty string")

    # If it's just a number, treat as seconds
    if duration_str.isdigit():
        return int(duration_str)

    # Pattern to match duration components
    pattern = r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$"
    match = re.match(pattern, duration_str)

    if not match or not any(match.groups()):
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. Use format like '1h30m', '2h', '45m', '30s'"
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    total_seconds = hours * 3600 + minutes * 60 + seconds

    return total_seconds


def hash_string(s: str) -> str:
    """
    Return the SHA256 hex digest of a string.

    This function computes a SHA256 hash of the input string and returns
    it as a lowercase hexadecimal string. Useful for generating unique
    identifiers, checksums, or secure tokens.

    Args:
        s: The string to hash.

    Returns:
        A 64-character lowercase hexadecimal string representing the SHA256 hash.

    Examples:
        >>> hash_string('hello')
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'

        >>> hash_string('')
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

        >>> len(hash_string('any string'))
        64
    """
    import hashlib

    if not isinstance(s, str):
        s = str(s)

    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sanitize_input(fields: List[str] = None, max_lengths: Dict[str, int] = None):
    """
    Decorator to automatically sanitize JSON input for Flask routes.

    XSS Prevention - This decorator automatically applies sanitization to
    incoming JSON request data before the route handler processes it.

    Args:
        fields: List of field names to sanitize. If None, sanitizes all string fields.
        max_lengths: Dict mapping field names to max lengths.

    Returns:
        Decorated function with sanitized request data.

    Examples:
        >>> @app.route('/api/projects', methods=['POST'])
        >>> @sanitize_input(fields=['name', 'description'])
        >>> def create_project():
        ...     data = request.get_json()  # Already sanitized
        ...     return jsonify({'success': True})

        >>> @app.route('/api/comments', methods=['POST'])
        >>> @sanitize_input(max_lengths={'content': 1000})
        >>> def create_comment():
        ...     pass
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import g, request

            if request.is_json and request.data:
                try:
                    original_data = request.get_json(silent=True)
                    if original_data and isinstance(original_data, dict):
                        # Store sanitized data in g for access
                        g.sanitized_json = sanitize_dict(original_data, fields, max_lengths)
                except Exception:
                    pass

            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_sanitized_json(fallback_to_original: bool = True):
    """
    Get sanitized JSON data from request.

    XSS Prevention - Helper function to retrieve sanitized JSON data
    that was processed by the @sanitize_input decorator.

    Args:
        fallback_to_original: If True, falls back to original request.get_json()
                             if sanitized data is not available.

    Returns:
        Sanitized JSON data or None if not available.

    Examples:
        >>> @app.route('/api/data', methods=['POST'])
        >>> @sanitize_input()
        >>> def process_data():
        ...     data = get_sanitized_json()
        ...     return jsonify(data)
    """
    from flask import g, request

    sanitized = getattr(g, "sanitized_json", None)
    if sanitized is not None:
        return sanitized

    if fallback_to_original:
        return request.get_json(silent=True)

    return None


def escape_js_string(value: str) -> str:
    """
    Escape a string for safe inclusion in JavaScript.

    XSS Prevention - Escapes special characters that could break out of
    JavaScript string literals or execute code.

    Args:
        value: String to escape for JavaScript context.

    Returns:
        Escaped string safe for JavaScript string literals.

    Examples:
        >>> escape_js_string('Hello "World"')
        'Hello \\\\"World\\\\"'
        >>> escape_js_string("It's a test")
        "It\\\\'s a test"
        >>> escape_js_string('<script>alert(1)</script>')
        '\\\\x3cscript\\\\x3ealert(1)\\\\x3c/script\\\\x3e'
    """
    if not isinstance(value, str):
        value = str(value)

    # Escape backslashes first
    value = value.replace("\\", "\\\\")
    # Escape quotes
    value = value.replace('"', '\\"')
    value = value.replace("'", "\\'")
    # Escape newlines
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    # Escape HTML special chars to prevent breaking out of JS into HTML
    value = value.replace("<", "\\x3c")
    value = value.replace(">", "\\x3e")
    value = value.replace("&", "\\x26")
    # Escape Unicode line/paragraph separators
    value = value.replace("\u2028", "\\u2028")
    value = value.replace("\u2029", "\\u2029")

    return value


def sanitize_for_attribute(value: str) -> str:
    """
    Sanitize a string for safe use in HTML attributes.

    XSS Prevention - Escapes characters that could break out of
    HTML attribute values.

    Args:
        value: String to sanitize for HTML attribute context.

    Returns:
        Sanitized string safe for HTML attributes.

    Examples:
        >>> sanitize_for_attribute('onclick="alert(1)"')
        'onclick=&quot;alert(1)&quot;'
        >>> sanitize_for_attribute("test' onload='alert(1)")
        "test&#x27; onload=&#x27;alert(1)"
    """
    if not isinstance(value, str):
        value = str(value)

    # Escape HTML entities
    import html

    value = html.escape(value, quote=True)
    # Also escape single quotes
    value = value.replace("'", "&#x27;")
    # Escape backticks (template literals)
    value = value.replace("`", "&#x60;")

    return value


def sanitize_url(url: str, allowed_schemes: List[str] = None) -> str:
    """
    Sanitize a URL to prevent javascript: and data: XSS attacks.

    XSS Prevention - Validates URL scheme and removes dangerous protocols.

    Args:
        url: URL string to sanitize.
        allowed_schemes: List of allowed URL schemes. Defaults to ['http', 'https', 'mailto'].

    Returns:
        Sanitized URL or empty string if URL is invalid/dangerous.

    Examples:
        >>> sanitize_url('https://example.com')
        'https://example.com'
        >>> sanitize_url('javascript:alert(1)')
        ''
        >>> sanitize_url('data:text/html,<script>alert(1)</script>')
        ''
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()

    if not url:
        return ""

    if allowed_schemes is None:
        allowed_schemes = ["http", "https", "mailto", "tel", "ftp"]

    # Normalize and check scheme
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)

        # Check for dangerous schemes
        scheme = parsed.scheme.lower()

        if scheme and scheme not in allowed_schemes:
            return ""

        # Check for javascript: or data: in various encodings
        url_lower = url.lower().replace(" ", "").replace("\t", "").replace("\n", "")
        dangerous_patterns = ["javascript:", "data:", "vbscript:", "file:"]

        for pattern in dangerous_patterns:
            if pattern in url_lower:
                return ""

        return url

    except Exception:
        return ""


def create_csp_nonce() -> str:
    """
    Generate a random nonce for Content Security Policy.

    XSS Prevention - Creates a cryptographically random nonce for use
    in CSP script-src and style-src directives.

    Returns:
        Base64-encoded random nonce string.

    Examples:
        >>> nonce = create_csp_nonce()
        >>> len(nonce) > 0
        True
    """
    import base64
    import os

    # Generate 16 random bytes and base64 encode
    random_bytes = os.urandom(16)
    return base64.b64encode(random_bytes).decode("ascii")


def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two nested dictionaries.

    Values from dict2 override values from dict1. When both values are
    dictionaries, they are merged recursively. Lists and other types
    are replaced, not merged.

    Args:
        dict1: Base dictionary.
        dict2: Dictionary with values to merge/override.

    Returns:
        New dictionary with deeply merged values.

    Examples:
        >>> deep_merge({'a': 1}, {'b': 2})
        {'a': 1, 'b': 2}

        >>> deep_merge({'a': {'x': 1}}, {'a': {'y': 2}})
        {'a': {'x': 1, 'y': 2}}

        >>> deep_merge({'a': {'b': {'c': 1}}}, {'a': {'b': {'d': 2}}})
        {'a': {'b': {'c': 1, 'd': 2}}}

        >>> deep_merge({'a': [1, 2]}, {'a': [3, 4]})
        {'a': [3, 4]}

        >>> deep_merge({'a': 1}, {'a': 2})
        {'a': 2}
    """
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        return dict2

    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result
