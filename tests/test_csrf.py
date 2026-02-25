#!/usr/bin/env python3
"""
Tests for CSRF Protection Module

Verifies:
- Token generation and validation
- Token expiration and rotation
- Exempt endpoint handling
- Error responses for invalid tokens
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csrf_protection import (
    CSRF_EXEMPT_ENDPOINTS,
    CSRF_FORM_FIELD,
    CSRF_HEADER_NAME,
    CSRF_PROTECTED_METHODS,
    generate_csrf_token,
    get_csrf_token_from_request,
    is_csrf_exempt,
    validate_csrf_token,
)


class TestCSRFTokenGeneration(unittest.TestCase):
    """Test CSRF token generation."""

    def setUp(self):
        """Set up mock session."""
        self.mock_session = {}
        self.session_patcher = patch("csrf_protection.session", self.mock_session)
        self.session_patcher.start()

    def tearDown(self):
        """Clean up."""
        self.session_patcher.stop()

    def test_generate_token_creates_token(self):
        """Test that generate_csrf_token creates a token."""
        token = generate_csrf_token()
        self.assertIsNotNone(token)
        self.assertEqual(len(token), 64)  # 32 bytes = 64 hex chars

    def test_generate_token_stores_in_session(self):
        """Test that token is stored in session."""
        token = generate_csrf_token()
        self.assertEqual(self.mock_session.get("csrf_token"), token)
        self.assertIn("csrf_token_time", self.mock_session)

    def test_generate_token_reuses_valid_token(self):
        """Test that valid tokens are reused."""
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        self.assertEqual(token1, token2)

    def test_generate_token_force_new(self):
        """Test that force_new creates a new token."""
        token1 = generate_csrf_token()
        token2 = generate_csrf_token(force_new=True)
        self.assertNotEqual(token1, token2)


class TestCSRFTokenValidation(unittest.TestCase):
    """Test CSRF token validation."""

    def setUp(self):
        """Set up mock session."""
        self.mock_session = {}
        self.session_patcher = patch("csrf_protection.session", self.mock_session)
        self.session_patcher.start()

    def tearDown(self):
        """Clean up."""
        self.session_patcher.stop()

    def test_validate_valid_token(self):
        """Test validation of correct token."""
        token = generate_csrf_token()
        is_valid, error = validate_csrf_token(token)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_validate_missing_token(self):
        """Test validation with missing token."""
        generate_csrf_token()
        is_valid, error = validate_csrf_token(None)
        self.assertFalse(is_valid)
        self.assertIn("missing", error.lower())

    def test_validate_wrong_token(self):
        """Test validation with wrong token."""
        generate_csrf_token()
        is_valid, error = validate_csrf_token("wrong_token")
        self.assertFalse(is_valid)
        self.assertIn("invalid", error.lower())

    def test_validate_no_session_token(self):
        """Test validation with no session token."""
        is_valid, error = validate_csrf_token("some_token")
        self.assertFalse(is_valid)
        self.assertIn("session", error.lower())


class TestCSRFExemptions(unittest.TestCase):
    """Test CSRF exemption handling."""

    def test_exempt_endpoints_defined(self):
        """Test that exempt endpoints are defined."""
        self.assertIn("/login", CSRF_EXEMPT_ENDPOINTS)
        self.assertIn("/health", CSRF_EXEMPT_ENDPOINTS)

    def test_protected_methods_defined(self):
        """Test that protected methods are defined."""
        self.assertIn("POST", CSRF_PROTECTED_METHODS)
        self.assertIn("PUT", CSRF_PROTECTED_METHODS)
        self.assertIn("DELETE", CSRF_PROTECTED_METHODS)
        self.assertIn("PATCH", CSRF_PROTECTED_METHODS)
        self.assertNotIn("GET", CSRF_PROTECTED_METHODS)


class TestCSRFConfiguration(unittest.TestCase):
    """Test CSRF configuration."""

    def test_header_name(self):
        """Test CSRF header name is configured."""
        self.assertEqual(CSRF_HEADER_NAME, "X-CSRF-Token")

    def test_form_field_name(self):
        """Test CSRF form field name is configured."""
        self.assertEqual(CSRF_FORM_FIELD, "csrf_token")


if __name__ == "__main__":
    unittest.main(verbosity=2)
