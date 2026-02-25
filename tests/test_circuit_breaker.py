"""
Circuit Breaker Tests

Tests for the circuit breaker pattern implementation.
"""
import threading
import time
from unittest.mock import Mock, patch

import pytest

from services.circuit_breaker import (
    CircuitBreaker,
    CircuitConfig,
    CircuitOpenError,
    CircuitState,
    ProtectedHTTPClient,
    circuit_breaker,
    circuit_context,
    force_open_circuit,
    get_all_circuit_status,
    reset_circuit,
)


class TestCircuitBreakerBasics:
    """Test basic circuit breaker functionality."""

    def setup_method(self):
        """Reset circuits before each test."""
        CircuitBreaker.reset_all()
        # Clear registry
        CircuitBreaker._circuits.clear()

    def test_initial_state_is_closed(self):
        """Circuit starts in closed state."""
        cb = CircuitBreaker.get("test-basic")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed

    def test_success_keeps_circuit_closed(self):
        """Successful calls keep circuit closed."""
        cb = CircuitBreaker.get("test-success")

        for _ in range(10):
            cb.record_success()

        assert cb.is_closed
        assert cb.metrics.successful_calls == 10
        assert cb.metrics.failed_calls == 0

    def test_failures_open_circuit(self):
        """Failures above threshold open circuit."""
        config = CircuitConfig(failure_threshold=3)
        cb = CircuitBreaker.get("test-failures", config)

        # First 2 failures - still closed
        cb.record_failure(Exception("Error 1"))
        cb.record_failure(Exception("Error 2"))
        assert cb.is_closed

        # Third failure - opens circuit
        cb.record_failure(Exception("Error 3"))
        assert cb.is_open

    def test_open_circuit_blocks_requests(self):
        """Open circuit blocks requests."""
        config = CircuitConfig(failure_threshold=2)
        cb = CircuitBreaker.get("test-blocking", config)

        # Open the circuit
        cb.record_failure(Exception())
        cb.record_failure(Exception())
        assert cb.is_open

        # Request should be blocked
        assert not cb.allow_request()
        assert cb.metrics.rejected_calls == 1

    def test_reset_closes_circuit(self):
        """Reset returns circuit to closed state."""
        config = CircuitConfig(failure_threshold=2)
        cb = CircuitBreaker.get("test-reset", config)

        # Open circuit
        cb.record_failure(Exception())
        cb.record_failure(Exception())
        assert cb.is_open

        # Reset
        cb.reset()
        assert cb.is_closed
        assert cb.allow_request()


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery behavior."""

    def setup_method(self):
        CircuitBreaker._circuits.clear()

    def test_half_open_after_timeout(self):
        """Circuit becomes half-open after recovery timeout."""
        config = CircuitConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms for testing
            backoff_multiplier=1.0,  # No backoff for testing
        )
        cb = CircuitBreaker.get("test-halfopen", config)

        # Open circuit
        cb.record_failure(Exception())
        cb.record_failure(Exception())
        assert cb.is_open

        # Wait for recovery timeout
        time.sleep(0.15)

        # Should be half-open now
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(self):
        """Success in half-open state closes circuit."""
        config = CircuitConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
            backoff_multiplier=1.0,  # No backoff for testing
        )
        cb = CircuitBreaker.get("test-recovery", config)

        # Open circuit
        cb.record_failure(Exception())
        cb.record_failure(Exception())

        # Wait for recovery
        time.sleep(0.15)
        assert cb.is_half_open

        # Successful calls close circuit
        cb.record_success()
        assert cb.is_half_open  # Need 2 successes
        cb.record_success()
        assert cb.is_closed

    def test_failure_in_half_open_reopens_circuit(self):
        """Failure in half-open state reopens circuit."""
        config = CircuitConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            backoff_multiplier=1.0,  # No backoff for testing
        )
        cb = CircuitBreaker.get("test-reopen", config)

        # Open circuit
        cb.record_failure(Exception())
        cb.record_failure(Exception())

        # Wait for recovery
        time.sleep(0.15)
        assert cb.is_half_open

        # Failure reopens circuit
        cb.record_failure(Exception())
        assert cb.is_open


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator."""

    def setup_method(self):
        CircuitBreaker._circuits.clear()

    def test_decorator_success(self):
        """Decorator records success."""

        @circuit_breaker("test-decorator")
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

        cb = CircuitBreaker.get("test-decorator")
        assert cb.metrics.successful_calls == 1

    def test_decorator_failure(self):
        """Decorator records failure."""

        @circuit_breaker("test-decorator-fail")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        cb = CircuitBreaker.get("test-decorator-fail")
        assert cb.metrics.failed_calls == 1

    def test_decorator_open_circuit_raises(self):
        """Decorator raises when circuit is open."""
        config = CircuitConfig(failure_threshold=1)

        @circuit_breaker("test-decorator-open", config)
        def my_function():
            raise Exception("Fail")

        # First call fails and opens circuit
        with pytest.raises(Exception):
            my_function()

        # Second call should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            my_function()

    def test_decorator_with_fallback(self):
        """Decorator uses fallback when circuit is open."""
        config = CircuitConfig(failure_threshold=1)

        @circuit_breaker("test-fallback", config, fallback=lambda: "fallback")
        def my_function():
            raise Exception("Fail")

        # First call fails
        with pytest.raises(Exception):
            my_function()

        # Second call returns fallback
        result = my_function()
        assert result == "fallback"


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics."""

    def setup_method(self):
        CircuitBreaker._circuits.clear()

    def test_metrics_tracking(self):
        """Metrics are tracked correctly."""
        cb = CircuitBreaker.get("test-metrics")

        for _ in range(5):
            cb.record_success()
        for _ in range(3):
            cb.record_failure(Exception())

        assert cb.metrics.total_calls == 8
        assert cb.metrics.successful_calls == 5
        assert cb.metrics.failed_calls == 3
        assert cb.metrics.success_rate == 5 / 8

    def test_status_contains_metrics(self):
        """Status includes metrics."""
        cb = CircuitBreaker.get("test-status")
        cb.record_success()
        cb.record_failure(Exception())

        status = cb.get_status()

        assert "name" in status
        assert "state" in status
        assert "metrics" in status
        assert status["metrics"]["total_calls"] == 2


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""

    def setup_method(self):
        CircuitBreaker._circuits.clear()

    def test_custom_config(self):
        """Custom configuration is applied."""
        config = CircuitConfig(failure_threshold=10, recovery_timeout=120.0, success_threshold=5)
        cb = CircuitBreaker.get("test-config", config)

        assert cb.config.failure_threshold == 10
        assert cb.config.recovery_timeout == 120.0
        assert cb.config.success_threshold == 5

    def test_failure_window(self):
        """Failures outside window are not counted."""
        config = CircuitConfig(failure_threshold=3, failure_window=0.1)  # 100ms
        cb = CircuitBreaker.get("test-window", config)

        # Record 2 failures
        cb.record_failure(Exception())
        cb.record_failure(Exception())

        # Wait for window to expire
        time.sleep(0.15)

        # Third failure should not open circuit (old failures expired)
        cb.record_failure(Exception())
        assert cb.is_closed


class TestCircuitBreakerThreadSafety:
    """Test circuit breaker thread safety."""

    def setup_method(self):
        CircuitBreaker._circuits.clear()

    def test_concurrent_access(self):
        """Circuit breaker handles concurrent access."""
        cb = CircuitBreaker.get("test-concurrent")
        errors = []

        def make_calls():
            try:
                for _ in range(100):
                    if cb.allow_request():
                        cb.record_success()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_calls) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cb.metrics.total_calls == 1000


class TestProtectedHTTPClient:
    """Test protected HTTP client."""

    def setup_method(self):
        CircuitBreaker._circuits.clear()

    @patch("requests.get")
    def test_successful_request(self, mock_get):
        """Successful request is recorded."""
        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.raise_for_status = Mock()

        client = ProtectedHTTPClient("test-http", base_url="https://api.example.com")
        response = client.get("/endpoint")

        assert mock_get.called
        assert client.circuit.metrics.successful_calls == 1

    @patch("requests.get")
    def test_failed_request(self, mock_get):
        """Failed request opens circuit."""
        import requests

        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")

        config = CircuitConfig(failure_threshold=1)
        client = ProtectedHTTPClient("test-http-fail", config=config)

        with pytest.raises(requests.exceptions.RequestException):
            client.get("https://api.example.com/endpoint")

        assert client.circuit.is_open


class TestConvenienceFunctions:
    """Test convenience functions."""

    def setup_method(self):
        CircuitBreaker._circuits.clear()

    def test_get_all_circuit_status(self):
        """Get status of all circuits."""
        CircuitBreaker.get("circuit-1")
        CircuitBreaker.get("circuit-2")

        status = get_all_circuit_status()

        assert "circuit-1" in status
        assert "circuit-2" in status

    def test_reset_circuit(self):
        """Reset specific circuit."""
        config = CircuitConfig(failure_threshold=1)
        cb = CircuitBreaker.get("circuit-reset", config)
        cb.record_failure(Exception())
        assert cb.is_open

        reset_circuit("circuit-reset")
        assert cb.is_closed

    def test_force_open_circuit(self):
        """Force circuit open."""
        cb = CircuitBreaker.get("circuit-force")
        assert cb.is_closed

        force_open_circuit("circuit-force", duration=60)
        assert cb.is_open
