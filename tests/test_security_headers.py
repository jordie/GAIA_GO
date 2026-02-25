#!/usr/bin/env python3
"""
Tests for Security Headers Middleware

Verifies:
- Default security headers are applied
- CSP header generation
- HSTS header for HTTPS
- Permissions-Policy header
- Path exemptions
- Configuration methods
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security_headers import (
    DEFAULT_CSP,
    DEFAULT_HEADERS,
    SecurityHeaders,
    SecurityLevel,
    add_security_headers,
)


class TestDefaultHeaders(unittest.TestCase):
    """Test default security headers."""

    def test_x_content_type_options(self):
        """Test X-Content-Type-Options header."""
        self.assertEqual(DEFAULT_HEADERS["X-Content-Type-Options"], "nosniff")

    def test_x_frame_options(self):
        """Test X-Frame-Options header."""
        self.assertEqual(DEFAULT_HEADERS["X-Frame-Options"], "SAMEORIGIN")

    def test_x_xss_protection(self):
        """Test X-XSS-Protection header."""
        self.assertEqual(DEFAULT_HEADERS["X-XSS-Protection"], "1; mode=block")

    def test_referrer_policy(self):
        """Test Referrer-Policy header."""
        self.assertEqual(DEFAULT_HEADERS["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_cache_control(self):
        """Test Cache-Control header."""
        self.assertIn("no-store", DEFAULT_HEADERS["Cache-Control"])


class TestDefaultCSP(unittest.TestCase):
    """Test default Content Security Policy."""

    def test_default_src(self):
        """Test default-src directive."""
        self.assertIn("'self'", DEFAULT_CSP["default-src"])

    def test_script_src(self):
        """Test script-src directive."""
        self.assertIn("'self'", DEFAULT_CSP["script-src"])
        self.assertIn("https://cdnjs.cloudflare.com", DEFAULT_CSP["script-src"])

    def test_style_src(self):
        """Test style-src directive."""
        self.assertIn("'self'", DEFAULT_CSP["style-src"])
        self.assertIn("https://fonts.googleapis.com", DEFAULT_CSP["style-src"])

    def test_font_src(self):
        """Test font-src directive."""
        self.assertIn("https://fonts.gstatic.com", DEFAULT_CSP["font-src"])

    def test_connect_src(self):
        """Test connect-src directive."""
        self.assertIn("'self'", DEFAULT_CSP["connect-src"])
        self.assertIn("wss:", DEFAULT_CSP["connect-src"])

    def test_object_src(self):
        """Test object-src directive blocks plugins."""
        self.assertIn("'none'", DEFAULT_CSP["object-src"])

    def test_frame_ancestors(self):
        """Test frame-ancestors directive."""
        self.assertIn("'self'", DEFAULT_CSP["frame-ancestors"])


class TestSecurityHeadersClass(unittest.TestCase):
    """Test SecurityHeaders class."""

    def setUp(self):
        """Set up test instance."""
        self.security = SecurityHeaders()

    def test_initialization(self):
        """Test SecurityHeaders initialization."""
        self.assertTrue(self.security.enabled)
        self.assertTrue(self.security.csp_enabled)
        self.assertTrue(self.security.hsts_enabled)

    def test_update_header(self):
        """Test updating a security header."""
        self.security.update_header("X-Frame-Options", "DENY")
        self.assertEqual(self.security.headers["X-Frame-Options"], "DENY")

    def test_remove_header(self):
        """Test removing a security header."""
        self.security.remove_header("X-XSS-Protection")
        self.assertNotIn("X-XSS-Protection", self.security.headers)

    def test_update_csp(self):
        """Test updating CSP directive."""
        self.security.update_csp("script-src", ["'self'", "https://example.com"])
        self.assertEqual(self.security.csp["script-src"], ["'self'", "https://example.com"])

    def test_add_csp_source(self):
        """Test adding CSP source."""
        self.security.add_csp_source("script-src", "https://new-source.com")
        self.assertIn("https://new-source.com", self.security.csp["script-src"])

    def test_add_csp_source_no_duplicates(self):
        """Test that adding duplicate CSP source is idempotent."""
        original_length = len(self.security.csp["script-src"])
        self.security.add_csp_source("script-src", "'self'")
        self.assertEqual(len(self.security.csp["script-src"]), original_length)

    def test_remove_csp_source(self):
        """Test removing CSP source."""
        self.security.add_csp_source("script-src", "https://remove-me.com")
        self.security.remove_csp_source("script-src", "https://remove-me.com")
        self.assertNotIn("https://remove-me.com", self.security.csp["script-src"])

    def test_add_cache_exempt_path(self):
        """Test adding cache exempt path."""
        self.security.add_cache_exempt_path("/api/data/")
        self.assertIn("/api/data/", self.security.cache_exempt_paths)

    def test_add_csp_exempt_path(self):
        """Test adding CSP exempt path."""
        self.security.add_csp_exempt_path("/webhook/")
        self.assertIn("/webhook/", self.security.csp_exempt_paths)

    def test_get_config(self):
        """Test getting configuration."""
        config = self.security.get_config()
        self.assertIn("enabled", config)
        self.assertIn("csp_enabled", config)
        self.assertIn("headers", config)
        self.assertIn("csp", config)


class TestCSPHeaderGeneration(unittest.TestCase):
    """Test CSP header generation."""

    def setUp(self):
        """Set up test instance."""
        self.security = SecurityHeaders()

    def test_build_csp_header(self):
        """Test building CSP header."""
        csp = self.security._build_csp_header()
        self.assertIn("default-src", csp)
        self.assertIn("script-src", csp)
        self.assertIn("'self'", csp)

    def test_csp_header_format(self):
        """Test CSP header format."""
        csp = self.security._build_csp_header()
        # Should have semicolon-separated directives
        self.assertIn(";", csp)


class TestPermissionsPolicyGeneration(unittest.TestCase):
    """Test Permissions-Policy header generation."""

    def setUp(self):
        """Set up test instance."""
        self.security = SecurityHeaders()

    def test_build_permissions_policy_header(self):
        """Test building Permissions-Policy header."""
        policy = self.security._build_permissions_policy_header()
        self.assertIn("camera=()", policy)
        self.assertIn("microphone=()", policy)
        self.assertIn("geolocation=()", policy)


class TestSecurityLevels(unittest.TestCase):
    """Test pre-configured security levels."""

    def test_strict_level(self):
        """Test strict security level."""
        config = SecurityLevel.strict()
        self.assertIn("csp", config)
        self.assertIn("headers", config)
        # Strict should have X-Frame-Options: DENY
        self.assertEqual(config["headers"]["X-Frame-Options"], "DENY")
        # Strict should not have unsafe-inline in script-src
        self.assertNotIn("'unsafe-inline'", config["csp"]["script-src"])

    def test_moderate_level(self):
        """Test moderate security level."""
        config = SecurityLevel.moderate()
        self.assertIn("csp", config)
        self.assertIn("headers", config)

    def test_relaxed_level(self):
        """Test relaxed security level."""
        config = SecurityLevel.relaxed()
        self.assertIn("csp", config)
        # Relaxed allows more sources
        self.assertIn("'unsafe-inline'", config["csp"]["script-src"])
        self.assertIn("'unsafe-eval'", config["csp"]["script-src"])


class TestPathExemptions(unittest.TestCase):
    """Test path exemption functionality."""

    def setUp(self):
        """Set up test instance."""
        self.security = SecurityHeaders()

    def test_is_path_exempt_static(self):
        """Test static path is exempt from cache control."""
        result = self.security._is_path_exempt(
            "/static/js/app.js", self.security.cache_exempt_paths
        )
        self.assertTrue(result)

    def test_is_path_exempt_api(self):
        """Test API path is exempt from CSP."""
        result = self.security._is_path_exempt("/api/users", self.security.csp_exempt_paths)
        self.assertTrue(result)

    def test_is_path_not_exempt(self):
        """Test non-exempt path."""
        result = self.security._is_path_exempt("/dashboard", self.security.cache_exempt_paths)
        self.assertFalse(result)


class MockHeaders(dict):
    """Mock headers class that behaves like Flask response headers."""

    def setdefault(self, key, value):
        if key not in self:
            self[key] = value
        return self[key]


class TestAddSecurityHeadersFunction(unittest.TestCase):
    """Test standalone add_security_headers function."""

    def test_adds_default_headers(self):
        """Test that function adds default headers."""
        mock_response = MagicMock()
        mock_response.headers = MockHeaders()

        result = add_security_headers(mock_response)

        self.assertIn("X-Content-Type-Options", result.headers)
        self.assertIn("X-Frame-Options", result.headers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
