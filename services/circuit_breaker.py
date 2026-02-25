"""
Circuit Breaker Pattern Implementation

Provides fault tolerance for external API calls by preventing cascading failures.

Features:
    - Multiple named circuits for different services
    - Configurable failure thresholds and timeouts
    - Three states: CLOSED (normal), OPEN (blocking), HALF_OPEN (testing)
    - Automatic recovery with exponential backoff
    - Metrics and monitoring
    - Thread-safe operation

Usage:
    from services.circuit_breaker import circuit_breaker, CircuitBreaker

    # Using decorator
    @circuit_breaker("github-api")
    def call_github_api():
        response = requests.get("https://api.github.com/...")
        return response.json()

    # Using context manager
    with CircuitBreaker.get("slack-api") as cb:
        if cb.allow_request():
            try:
                result = call_slack()
                cb.record_success()
            except Exception as e:
                cb.record_failure(e)
                raise

    # Manual usage
    cb = CircuitBreaker.get("external-service")
    if cb.allow_request():
        try:
            result = make_call()
            cb.record_success()
        except Exception as e:
            cb.record_failure(e)
            raise CircuitOpenError(cb.name)
"""

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"  # Failures exceeded threshold, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is blocked."""

    def __init__(self, circuit_name: str, retry_after: float = None):
        self.circuit_name = circuit_name
        self.retry_after = retry_after
        message = f"Circuit '{circuit_name}' is open"
        if retry_after:
            message += f", retry after {retry_after:.1f}s"
        super().__init__(message)


@dataclass
class CircuitConfig:
    """Configuration for a circuit breaker."""

    # Failure threshold to open circuit
    failure_threshold: int = 5

    # Time window to count failures (seconds)
    failure_window: float = 60.0

    # Time to wait before testing recovery (seconds)
    recovery_timeout: float = 30.0

    # Number of successful calls to close circuit
    success_threshold: int = 3

    # Maximum recovery timeout with exponential backoff
    max_recovery_timeout: float = 300.0

    # Backoff multiplier for recovery timeout
    backoff_multiplier: float = 2.0

    # Exceptions to count as failures (None = all exceptions)
    failure_exceptions: tuple = None

    # Exceptions to ignore (don't count as failure)
    exclude_exceptions: tuple = ()

    # Timeout for individual calls (seconds, None = no timeout)
    call_timeout: float = None

    @classmethod
    def for_service(cls, service_type: str) -> "CircuitConfig":
        """Get recommended config for service type."""
        configs = {
            "fast": cls(
                failure_threshold=3,
                failure_window=30.0,
                recovery_timeout=10.0,
                success_threshold=2,
            ),
            "slow": cls(
                failure_threshold=5,
                failure_window=120.0,
                recovery_timeout=60.0,
                success_threshold=3,
            ),
            "critical": cls(
                failure_threshold=10,
                failure_window=300.0,
                recovery_timeout=30.0,
                success_threshold=5,
            ),
            "default": cls(),
        }
        return configs.get(service_type, configs["default"])


@dataclass
class CircuitMetrics:
    """Metrics for a circuit breaker."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    timeouts: int = 0

    state_changes: List[Dict] = field(default_factory=list)
    recent_failures: List[Dict] = field(default_factory=list)

    last_failure_time: float = None
    last_success_time: float = None
    last_state_change: float = None

    circuit_opened_count: int = 0
    circuit_closed_count: int = 0

    def record_call(self, success: bool, error: Exception = None):
        """Record a call result."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
            self.last_success_time = time.time()
        else:
            self.failed_calls += 1
            self.last_failure_time = time.time()
            self.recent_failures.append(
                {
                    "time": time.time(),
                    "error": str(error) if error else "Unknown",
                    "type": type(error).__name__ if error else "Unknown",
                }
            )
            # Keep only last 20 failures
            self.recent_failures = self.recent_failures[-20:]

    def record_rejection(self):
        """Record a rejected call (circuit open)."""
        self.rejected_calls += 1

    def record_timeout(self):
        """Record a timeout."""
        self.timeouts += 1

    def record_state_change(self, from_state: CircuitState, to_state: CircuitState):
        """Record a state change."""
        now = time.time()
        self.state_changes.append(
            {
                "time": now,
                "from": from_state.value,
                "to": to_state.value,
            }
        )
        self.last_state_change = now

        if to_state == CircuitState.OPEN:
            self.circuit_opened_count += 1
        elif to_state == CircuitState.CLOSED:
            self.circuit_closed_count += 1

        # Keep only last 50 state changes
        self.state_changes = self.state_changes[-50:]

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "timeouts": self.timeouts,
            "success_rate": round(self.success_rate * 100, 2),
            "failure_rate": round(self.failure_rate * 100, 2),
            "circuit_opened_count": self.circuit_opened_count,
            "circuit_closed_count": self.circuit_closed_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "last_state_change": self.last_state_change,
            "recent_failures": self.recent_failures[-5:],
        }


class CircuitBreaker:
    """
    Circuit breaker implementation.

    States:
        CLOSED: Normal operation. Requests flow through. Failures are tracked.
        OPEN: Too many failures. Requests are blocked. Waits for recovery timeout.
        HALF_OPEN: Testing recovery. Limited requests allowed. Success closes circuit.
    """

    # Global registry of circuit breakers
    _circuits: Dict[str, "CircuitBreaker"] = {}
    _registry_lock = threading.Lock()

    def __init__(self, name: str, config: CircuitConfig = None):
        self.name = name
        self.config = config or CircuitConfig()

        self._state = CircuitState.CLOSED
        self._lock = threading.RLock()

        # Failure tracking
        self._failures: List[float] = []  # Timestamps of failures
        self._consecutive_successes = 0
        self._current_recovery_timeout = self.config.recovery_timeout

        # Timing
        self._opened_at: float = None
        self._last_failure_at: float = None

        # Metrics
        self.metrics = CircuitMetrics()

        # Callbacks
        self._on_open: List[Callable] = []
        self._on_close: List[Callable] = []
        self._on_half_open: List[Callable] = []

    @classmethod
    def get(cls, name: str, config: CircuitConfig = None) -> "CircuitBreaker":
        """Get or create a circuit breaker by name."""
        with cls._registry_lock:
            if name not in cls._circuits:
                cls._circuits[name] = cls(name, config)
            return cls._circuits[name]

    @classmethod
    def get_all(cls) -> Dict[str, "CircuitBreaker"]:
        """Get all registered circuit breakers."""
        with cls._registry_lock:
            return dict(cls._circuits)

    @classmethod
    def reset_all(cls):
        """Reset all circuit breakers."""
        with cls._registry_lock:
            for cb in cls._circuits.values():
                cb.reset()

    @classmethod
    def remove(cls, name: str):
        """Remove a circuit breaker."""
        with cls._registry_lock:
            cls._circuits.pop(name, None)

    @property
    def state(self) -> CircuitState:
        """Get current state (may trigger state transition)."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        with self._lock:
            self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                self.metrics.record_rejection()
                return False

            # HALF_OPEN: allow request for testing
            return True

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            self.metrics.record_call(success=True)

            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.config.success_threshold:
                    self._close_circuit()

            elif self._state == CircuitState.CLOSED:
                # Clear old failures outside window
                self._cleanup_failures()

    def record_failure(self, error: Exception = None):
        """Record a failed call."""
        with self._lock:
            # Check if this exception should be counted
            if not self._should_count_failure(error):
                return

            now = time.time()
            self._failures.append(now)
            self._last_failure_at = now
            self.metrics.record_call(success=False, error=error)

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open state opens the circuit
                self._open_circuit()

            elif self._state == CircuitState.CLOSED:
                # Check if we exceeded threshold
                self._cleanup_failures()
                if len(self._failures) >= self.config.failure_threshold:
                    self._open_circuit()

    def record_timeout(self):
        """Record a timeout (counts as failure)."""
        self.metrics.record_timeout()
        self.record_failure(TimeoutError("Request timed out"))

    def _should_count_failure(self, error: Exception) -> bool:
        """Check if error should count as failure."""
        if error is None:
            return True

        # Check excluded exceptions
        if self.config.exclude_exceptions:
            if isinstance(error, self.config.exclude_exceptions):
                return False

        # Check failure exceptions
        if self.config.failure_exceptions:
            return isinstance(error, self.config.failure_exceptions)

        return True

    def _cleanup_failures(self):
        """Remove failures outside the time window."""
        cutoff = time.time() - self.config.failure_window
        self._failures = [t for t in self._failures if t > cutoff]

    def _check_state_transition(self):
        """Check if state should change."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._opened_at:
                elapsed = time.time() - self._opened_at
                if elapsed >= self._current_recovery_timeout:
                    self._half_open_circuit()

    def _open_circuit(self):
        """Open the circuit."""
        if self._state != CircuitState.OPEN:
            old_state = self._state
            self._state = CircuitState.OPEN
            self._opened_at = time.time()
            self._consecutive_successes = 0

            # Apply exponential backoff
            self._current_recovery_timeout = min(
                self._current_recovery_timeout * self.config.backoff_multiplier,
                self.config.max_recovery_timeout,
            )

            self.metrics.record_state_change(old_state, CircuitState.OPEN)
            logger.warning(
                f"Circuit '{self.name}' opened. "
                f"Recovery in {self._current_recovery_timeout:.1f}s"
            )

            for callback in self._on_open:
                try:
                    callback(self)
                except Exception as e:
                    logger.error(f"Error in on_open callback: {e}")

    def _half_open_circuit(self):
        """Transition to half-open state."""
        if self._state != CircuitState.HALF_OPEN:
            old_state = self._state
            self._state = CircuitState.HALF_OPEN
            self._consecutive_successes = 0

            self.metrics.record_state_change(old_state, CircuitState.HALF_OPEN)
            logger.info(f"Circuit '{self.name}' half-open. Testing recovery...")

            for callback in self._on_half_open:
                try:
                    callback(self)
                except Exception as e:
                    logger.error(f"Error in on_half_open callback: {e}")

    def _close_circuit(self):
        """Close the circuit (return to normal)."""
        if self._state != CircuitState.CLOSED:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failures.clear()
            self._consecutive_successes = 0
            self._current_recovery_timeout = self.config.recovery_timeout

            self.metrics.record_state_change(old_state, CircuitState.CLOSED)
            logger.info(f"Circuit '{self.name}' closed. Normal operation resumed.")

            for callback in self._on_close:
                try:
                    callback(self)
                except Exception as e:
                    logger.error(f"Error in on_close callback: {e}")

    def reset(self):
        """Reset circuit to closed state."""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failures.clear()
            self._consecutive_successes = 0
            self._current_recovery_timeout = self.config.recovery_timeout
            self._opened_at = None

            if old_state != CircuitState.CLOSED:
                self.metrics.record_state_change(old_state, CircuitState.CLOSED)

            logger.info(f"Circuit '{self.name}' reset to closed state.")

    def force_open(self, duration: float = None):
        """Force circuit open (for testing or maintenance)."""
        with self._lock:
            self._open_circuit()
            if duration:
                self._current_recovery_timeout = duration

    def get_status(self) -> Dict[str, Any]:
        """Get circuit status."""
        with self._lock:
            self._check_state_transition()

            status = {
                "name": self.name,
                "state": self._state.value,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "failure_window": self.config.failure_window,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold,
                },
                "current_failures": len(self._failures),
                "consecutive_successes": self._consecutive_successes,
                "current_recovery_timeout": self._current_recovery_timeout,
                "metrics": self.metrics.to_dict(),
            }

            if self._state == CircuitState.OPEN and self._opened_at:
                elapsed = time.time() - self._opened_at
                remaining = self._current_recovery_timeout - elapsed
                status["retry_after"] = max(0, remaining)

            return status

    def on_open(self, callback: Callable):
        """Register callback for when circuit opens."""
        self._on_open.append(callback)

    def on_close(self, callback: Callable):
        """Register callback for when circuit closes."""
        self._on_close.append(callback)

    def on_half_open(self, callback: Callable):
        """Register callback for when circuit becomes half-open."""
        self._on_half_open.append(callback)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure(exc_val)
        return False


def circuit_breaker(
    name: str, config: CircuitConfig = None, fallback: Callable = None, raise_on_open: bool = True
):
    """
    Decorator to wrap a function with circuit breaker protection.

    Args:
        name: Circuit breaker name
        config: Circuit configuration
        fallback: Function to call when circuit is open
        raise_on_open: Whether to raise CircuitOpenError when open

    Example:
        @circuit_breaker("github-api")
        def fetch_github_data():
            return requests.get("https://api.github.com/...").json()

        @circuit_breaker("slack", fallback=lambda: {"ok": False})
        def send_slack_message(msg):
            return slack_client.chat_postMessage(text=msg)
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cb = CircuitBreaker.get(name, config)

            if not cb.allow_request():
                if fallback:
                    return fallback(*args, **kwargs)
                if raise_on_open:
                    status = cb.get_status()
                    raise CircuitOpenError(name, retry_after=status.get("retry_after"))
                return None

            try:
                result = func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure(e)
                raise

        return wrapper

    return decorator


@contextmanager
def circuit_context(name: str, config: CircuitConfig = None):
    """
    Context manager for circuit breaker.

    Example:
        with circuit_context("external-api") as cb:
            if cb.allow_request():
                result = make_api_call()
    """
    cb = CircuitBreaker.get(name, config)
    try:
        yield cb
    except Exception as e:
        cb.record_failure(e)
        raise


# =============================================================================
# HTTP Client with Circuit Breaker
# =============================================================================


class ProtectedHTTPClient:
    """
    HTTP client with built-in circuit breaker protection.

    Example:
        client = ProtectedHTTPClient("github-api", base_url="https://api.github.com")
        response = client.get("/repos/owner/repo")
    """

    def __init__(
        self,
        circuit_name: str,
        base_url: str = "",
        config: CircuitConfig = None,
        timeout: float = 30.0,
        headers: Dict[str, str] = None,
    ):
        self.circuit_name = circuit_name
        self.base_url = base_url.rstrip("/")
        self.circuit = CircuitBreaker.get(circuit_name, config)
        self.timeout = timeout
        self.default_headers = headers or {}

        # Import requests lazily
        self._requests = None

    @property
    def requests(self):
        if self._requests is None:
            import requests

            self._requests = requests
        return self._requests

    def _make_request(self, method: str, path: str, **kwargs):
        """Make HTTP request with circuit breaker protection."""
        if not self.circuit.allow_request():
            status = self.circuit.get_status()
            raise CircuitOpenError(self.circuit_name, retry_after=status.get("retry_after"))

        url = f"{self.base_url}{path}" if self.base_url else path

        # Merge headers
        headers = {**self.default_headers, **kwargs.pop("headers", {})}

        # Set timeout
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = getattr(self.requests, method)(url, headers=headers, **kwargs)
            response.raise_for_status()
            self.circuit.record_success()
            return response
        except self.requests.exceptions.Timeout as e:
            self.circuit.record_timeout()
            raise
        except Exception as e:
            self.circuit.record_failure(e)
            raise

    def get(self, path: str, **kwargs):
        return self._make_request("get", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._make_request("post", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self._make_request("put", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self._make_request("patch", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self._make_request("delete", path, **kwargs)

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return self.circuit.get_status()


# =============================================================================
# Convenience Functions
# =============================================================================


def get_all_circuit_status() -> Dict[str, Dict]:
    """Get status of all circuit breakers."""
    circuits = CircuitBreaker.get_all()
    return {name: cb.get_status() for name, cb in circuits.items()}


def reset_circuit(name: str):
    """Reset a specific circuit breaker."""
    circuits = CircuitBreaker.get_all()
    if name in circuits:
        circuits[name].reset()
        return True
    return False


def force_open_circuit(name: str, duration: float = 60.0):
    """Force a circuit breaker open."""
    circuits = CircuitBreaker.get_all()
    if name in circuits:
        circuits[name].force_open(duration)
        return True
    return False
