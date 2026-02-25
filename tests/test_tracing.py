#!/usr/bin/env python3
"""
Tests for Distributed Tracing Module

Verifies:
- Tracing initialization
- Span creation and attributes
- Fallback span implementation
- Context propagation
- Function decorators
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tracing import (
    TRACING_ENABLED,
    FallbackSpan,
    TracingConfig,
    get_trace_context,
    trace_function,
    trace_span,
)


class TestFallbackSpan(unittest.TestCase):
    """Test FallbackSpan implementation."""

    def test_span_creation(self):
        """Test creating a fallback span."""
        span = FallbackSpan("test_span")
        self.assertEqual(span.name, "test_span")
        self.assertIsNotNone(span.span_id)
        self.assertIsNotNone(span.start_time)
        self.assertIsNone(span.end_time)

    def test_span_attributes(self):
        """Test setting span attributes."""
        span = FallbackSpan("test_span")
        span.set_attribute("key1", "value1")
        span.set_attribute("key2", 123)

        self.assertEqual(span.attributes["key1"], "value1")
        self.assertEqual(span.attributes["key2"], 123)

    def test_span_set_attributes(self):
        """Test setting multiple attributes at once."""
        span = FallbackSpan("test_span")
        span.set_attributes({"a": 1, "b": 2, "c": 3})

        self.assertEqual(span.attributes["a"], 1)
        self.assertEqual(span.attributes["b"], 2)
        self.assertEqual(span.attributes["c"], 3)

    def test_span_events(self):
        """Test adding events to span."""
        span = FallbackSpan("test_span")
        span.add_event("event1", {"data": "test"})

        self.assertEqual(len(span.events), 1)
        self.assertEqual(span.events[0]["name"], "event1")
        self.assertEqual(span.events[0]["attributes"]["data"], "test")

    def test_span_status(self):
        """Test setting span status."""
        span = FallbackSpan("test_span")
        span.set_status("ERROR", "Something went wrong")

        self.assertEqual(span.status, "ERROR")
        self.assertEqual(span.status_description, "Something went wrong")

    def test_span_exception(self):
        """Test recording exception."""
        span = FallbackSpan("test_span")
        try:
            raise ValueError("Test error")
        except Exception as e:
            span.record_exception(e)

        self.assertEqual(span.status, "ERROR")
        self.assertEqual(len(span.events), 1)
        self.assertEqual(span.events[0]["name"], "exception")

    def test_span_end(self):
        """Test ending a span."""
        span = FallbackSpan("test_span")
        time.sleep(0.01)
        span.end()

        self.assertIsNotNone(span.end_time)
        self.assertGreater(span.end_time, span.start_time)

    def test_span_context_manager(self):
        """Test span as context manager."""
        with FallbackSpan("test_span") as span:
            span.set_attribute("test", True)

        self.assertIsNotNone(span.end_time)

    def test_span_context_manager_exception(self):
        """Test span context manager with exception."""
        try:
            with FallbackSpan("test_span") as span:
                raise ValueError("Test error")
        except ValueError:
            pass

        self.assertEqual(span.status, "ERROR")

    def test_span_to_dict(self):
        """Test converting span to dictionary."""
        span = FallbackSpan("test_span")
        span.set_attribute("key", "value")
        span.end()

        result = span.to_dict()

        self.assertEqual(result["name"], "test_span")
        self.assertIn("span_id", result)
        self.assertIn("duration_ms", result)
        self.assertEqual(result["attributes"]["key"], "value")


class TestTraceSpan(unittest.TestCase):
    """Test trace_span context manager."""

    def test_trace_span_basic(self):
        """Test basic trace_span usage."""
        with trace_span("test_operation") as span:
            span.set_attribute("test", True)

    def test_trace_span_with_attributes(self):
        """Test trace_span with initial attributes."""
        with trace_span("test_operation", {"key": "value"}) as span:
            self.assertIn("key", span.attributes)


class TestTraceFunction(unittest.TestCase):
    """Test trace_function decorator."""

    def test_decorator_basic(self):
        """Test basic function decoration."""

        @trace_function()
        def test_func():
            return "result"

        result = test_func()
        self.assertEqual(result, "result")

    def test_decorator_with_args(self):
        """Test decorator with function arguments."""

        @trace_function(record_args=True)
        def test_func(x, y):
            return x + y

        result = test_func(1, 2)
        self.assertEqual(result, 3)

    def test_decorator_with_result(self):
        """Test decorator recording result."""

        @trace_function(record_result=True)
        def test_func():
            return {"data": "test"}

        result = test_func()
        self.assertEqual(result["data"], "test")

    def test_decorator_with_custom_name(self):
        """Test decorator with custom span name."""

        @trace_function(name="custom_operation")
        def test_func():
            pass

        test_func()  # Should not raise

    def test_decorator_exception_handling(self):
        """Test decorator handles exceptions."""

        @trace_function()
        def test_func():
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            test_func()


class TestTracingConfig(unittest.TestCase):
    """Test TracingConfig helper."""

    def test_get_config(self):
        """Test getting tracing configuration."""
        config = TracingConfig.get_config()

        self.assertIn("enabled", config)
        self.assertIn("service_name", config)
        self.assertIn("exporter", config)
        self.assertIn("sample_rate", config)
        self.assertIn("exporters_available", config)

    def test_is_enabled(self):
        """Test checking if tracing is enabled."""
        result = TracingConfig.is_enabled()
        self.assertIsInstance(result, bool)


class TestTraceContext(unittest.TestCase):
    """Test trace context functions."""

    def test_get_trace_context(self):
        """Test getting trace context."""
        context = get_trace_context()
        self.assertIsInstance(context, dict)


class TestTracingConfiguration(unittest.TestCase):
    """Test tracing configuration constants."""

    def test_tracing_enabled_default(self):
        """Test TRACING_ENABLED has a default value."""
        self.assertIsInstance(TRACING_ENABLED, bool)


if __name__ == "__main__":
    unittest.main(verbosity=2)
