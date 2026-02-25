#!/usr/bin/env python3
"""
Tests for Log Correlation ID Module

Verifies:
- Correlation ID generation
- ID storage and retrieval
- Context manager for background tasks
- Logging filter integration
"""

import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from correlation_id import (
    CORRELATION_ID_HEADER,
    CorrelationLogFilter,
    correlation_context,
    generate_correlation_id,
    get_correlation_id,
    propagate_correlation_id,
    set_correlation_id,
)


class TestCorrelationIdGeneration(unittest.TestCase):
    """Test correlation ID generation."""

    def test_generate_id_format(self):
        """Test that generated IDs have correct format."""
        cid = generate_correlation_id()
        self.assertIsNotNone(cid)
        # Format: timestamp-shortuuid
        parts = cid.split("-")
        self.assertEqual(len(parts), 2)
        # First part should be numeric (timestamp)
        self.assertTrue(parts[0].isdigit())
        # Second part should be 8 hex chars
        self.assertEqual(len(parts[1]), 8)

    def test_generate_id_uniqueness(self):
        """Test that generated IDs are unique."""
        ids = [generate_correlation_id() for _ in range(100)]
        self.assertEqual(len(ids), len(set(ids)))


class TestCorrelationIdStorage(unittest.TestCase):
    """Test correlation ID storage and retrieval."""

    def setUp(self):
        """Set up mock context."""
        from correlation_id import _correlation_id

        self.token = _correlation_id.set(None)

    def tearDown(self):
        """Clean up."""
        from correlation_id import _correlation_id

        _correlation_id.set(None)

    @patch("correlation_id.has_request_context", return_value=False)
    def test_set_and_get_id(self, mock_has_context):
        """Test setting and getting correlation ID."""
        test_id = "test-12345678"
        set_correlation_id(test_id)
        self.assertEqual(get_correlation_id(), test_id)

    @patch("correlation_id.has_request_context", return_value=False)
    def test_get_id_when_not_set(self, mock_has_context):
        """Test getting ID when not set."""
        self.assertIsNone(get_correlation_id())


class TestCorrelationContext(unittest.TestCase):
    """Test correlation context manager."""

    def setUp(self):
        """Set up clean context."""
        from correlation_id import _correlation_id

        _correlation_id.set(None)

    def tearDown(self):
        """Clean up."""
        from correlation_id import _correlation_id

        _correlation_id.set(None)

    @patch("correlation_id.has_request_context", return_value=False)
    def test_context_sets_id(self, mock_has_context):
        """Test that context manager sets correlation ID."""
        with correlation_context("ctx-12345678") as cid:
            self.assertEqual(cid, "ctx-12345678")
            self.assertEqual(get_correlation_id(), "ctx-12345678")

    @patch("correlation_id.has_request_context", return_value=False)
    def test_context_restores_previous_id(self, mock_has_context):
        """Test that context manager restores previous ID."""
        from correlation_id import _correlation_id

        _correlation_id.set("original-id")

        with correlation_context("temp-id"):
            self.assertEqual(get_correlation_id(), "temp-id")

        self.assertEqual(get_correlation_id(), "original-id")

    @patch("correlation_id.has_request_context", return_value=False)
    def test_context_generates_id_if_not_provided(self, mock_has_context):
        """Test that context manager generates ID if not provided."""
        with correlation_context() as cid:
            self.assertIsNotNone(cid)
            self.assertEqual(get_correlation_id(), cid)


class TestCorrelationLogFilter(unittest.TestCase):
    """Test correlation ID logging filter."""

    def test_filter_adds_correlation_id(self):
        """Test that filter adds correlation_id to log record."""
        log_filter = CorrelationLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = log_filter.filter(record)

        self.assertTrue(result)
        self.assertTrue(hasattr(record, "correlation_id"))

    @patch("correlation_id.get_correlation_id", return_value="test-id")
    def test_filter_uses_current_id(self, mock_get_id):
        """Test that filter uses current correlation ID."""
        log_filter = CorrelationLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        log_filter.filter(record)

        self.assertEqual(record.correlation_id, "test-id")

    @patch("correlation_id.get_correlation_id", return_value=None)
    def test_filter_uses_placeholder_when_no_id(self, mock_get_id):
        """Test that filter uses '-' when no correlation ID."""
        log_filter = CorrelationLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        log_filter.filter(record)

        self.assertEqual(record.correlation_id, "-")


class TestCorrelationIdPropagation(unittest.TestCase):
    """Test correlation ID propagation for outgoing requests."""

    @patch("correlation_id.get_correlation_id", return_value="prop-id")
    def test_propagate_adds_header(self, mock_get_id):
        """Test that propagate adds correlation ID header."""
        headers = propagate_correlation_id()
        self.assertEqual(headers[CORRELATION_ID_HEADER], "prop-id")

    @patch("correlation_id.get_correlation_id", return_value="prop-id")
    def test_propagate_extends_existing_headers(self, mock_get_id):
        """Test that propagate extends existing headers."""
        existing = {"Authorization": "Bearer token"}
        headers = propagate_correlation_id(existing)
        self.assertEqual(headers["Authorization"], "Bearer token")
        self.assertEqual(headers[CORRELATION_ID_HEADER], "prop-id")

    @patch("correlation_id.get_correlation_id", return_value=None)
    def test_propagate_empty_when_no_id(self, mock_get_id):
        """Test that propagate returns empty dict when no ID."""
        headers = propagate_correlation_id()
        self.assertNotIn(CORRELATION_ID_HEADER, headers)


class TestCorrelationIdConfiguration(unittest.TestCase):
    """Test correlation ID configuration."""

    def test_header_name(self):
        """Test correlation ID header name."""
        self.assertEqual(CORRELATION_ID_HEADER, "X-Correlation-ID")


if __name__ == "__main__":
    unittest.main(verbosity=2)
