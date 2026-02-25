#!/usr/bin/env python3
"""
Security Headers Middleware

Provides HTTP security headers to protect against common web vulnerabilities.

Headers implemented:
- Content-Security-Policy (CSP): Controls resource loading to prevent XSS
- X-Content-Type-Options: Prevents MIME type sniffing
- X-Frame-Options: Prevents clickjacking
- X-XSS-Protection: Legacy XSS filter (for older browsers)
- Strict-Transport-Security (HSTS): Enforces HTTPS
- Referrer-Policy: Controls referrer information
- Permissions-Policy: Controls browser features
- Cache-Control: Prevents caching of sensitive data
- X-Permitted-Cross-Domain-Policies: Controls Flash/PDF cross-domain access

Usage:
    from security_headers import SecurityHeaders

    # Initialize with Flask app
    security = SecurityHeaders(app)

    # Or use init_app pattern
    security = SecurityHeaders()
    security.init_app(app)

    # Access configuration
    security.update_csp('script-src', "'self' https://cdn.example.com")
"""

import logging
import os
import secrets
from functools import wraps
from typing import Callable, Dict, List, Optional, Set

from flask import Flask, Response, g, request

logger = logging.getLogger(__name__)

# Default security header values
DEFAULT_HEADERS = {
    # Prevent MIME type sniffing
    "X-Content-Type-Options": "nosniff",
    # Prevent clickjacking - page cannot be embedded in frames
    "X-Frame-Options": "SAMEORIGIN",
    # Legacy XSS protection for older browsers
    "X-XSS-Protection": "1; mode=block",
    # Control referrer information sent with requests
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Prevent Adobe Flash/PDF cross-domain access
    "X-Permitted-Cross-Domain-Policies": "none",
    # Prevent caching of sensitive responses
    "Cache-Control": "no-store, max-age=0",
    # Indicate this is a download, not inline content (for API responses)
    "X-Download-Options": "noopen",
}

# HSTS configuration (only for HTTPS)
HSTS_HEADER = {"Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"}

# Default Content Security Policy
DEFAULT_CSP = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'",
        "'unsafe-inline'",  # Required for inline scripts (minimize in production)
        "'unsafe-eval'",  # Required for some JS frameworks (minimize in production)
        "https://cdnjs.cloudflare.com",  # Socket.IO CDN
        "https://cdn.jsdelivr.net",  # xterm and other CDN libraries
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",  # Required for inline styles
        "https://fonts.googleapis.com",
        "https://cdn.jsdelivr.net",  # xterm CSS
    ],
    "font-src": [
        "'self'",
        "https://fonts.gstatic.com",
        "https://r2cdn.perplexity.ai",  # FKGroteskNeue font
    ],
    "img-src": [
        "'self'",
        "data:",  # Allow data URIs for images
        "blob:",  # Allow blob URIs
    ],
    "connect-src": [
        "'self'",
        "wss:",  # WebSocket connections
        "ws:",  # WebSocket connections (dev)
        "wss://*",  # WebSocket wildcard
        "ws://*",  # WebSocket wildcard (dev)
        "https://cdnjs.cloudflare.com",  # CDN source maps
        "https://cdn.jsdelivr.net",  # CDN libraries and source maps
    ],
    "frame-ancestors": ["'self'"],  # Only allow framing from same origin
    "form-action": ["'self'"],  # Only allow form submissions to same origin
    "base-uri": ["'self'"],  # Restrict <base> tag
    "object-src": ["'none'"],  # Disable plugins (Flash, etc.)
    "upgrade-insecure-requests": [],  # Upgrade HTTP to HTTPS
}

# Default Permissions Policy
DEFAULT_PERMISSIONS_POLICY = {
    "accelerometer": [],
    "camera": [],
    "geolocation": [],
    "gyroscope": [],
    "magnetometer": [],
    "microphone": [],
    "payment": [],
    "usb": [],
    "interest-cohort": [],  # Disable FLoC
}

# Paths exempt from certain headers
CACHE_EXEMPT_PATHS = [
    "/static/",  # Static files should be cacheable
]

CSP_EXEMPT_PATHS = [
    "/api/",  # API responses don't need CSP
]

# Paths that should completely bypass security headers (WebSocket, etc.)
SECURITY_HEADERS_EXEMPT_PATHS = [
    "/socket.io/",  # WebSocket connections must not have security headers applied
    "/ws/",  # WebSocket endpoints
]


class SecurityHeaders:
    """
    Flask extension for adding security headers to responses.

    Configurable via environment variables:
    - SECURITY_HEADERS_ENABLED: Enable/disable all security headers (default: true)
    - SECURITY_CSP_ENABLED: Enable/disable CSP (default: true)
    - SECURITY_HSTS_ENABLED: Enable/disable HSTS (default: true for HTTPS)
    - SECURITY_CSP_REPORT_ONLY: Use CSP in report-only mode (default: false)
    - SECURITY_CSP_REPORT_URI: URI for CSP violation reports
    """

    def __init__(self, app: Flask = None, **kwargs):
        self.app = app
        self.headers = DEFAULT_HEADERS.copy()
        self.csp = {k: list(v) for k, v in DEFAULT_CSP.items()}
        self.permissions_policy = DEFAULT_PERMISSIONS_POLICY.copy()
        self.hsts = HSTS_HEADER.copy()

        # Configuration options
        self.enabled = kwargs.get("enabled", True)
        self.csp_enabled = kwargs.get("csp_enabled", True)
        self.hsts_enabled = kwargs.get("hsts_enabled", True)
        self.csp_report_only = kwargs.get("csp_report_only", False)
        self.csp_report_uri = kwargs.get("csp_report_uri", None)
        self.csp_nonce_enabled = kwargs.get("csp_nonce_enabled", False)

        # Exempt paths
        self.cache_exempt_paths = list(CACHE_EXEMPT_PATHS)
        self.csp_exempt_paths = list(CSP_EXEMPT_PATHS)
        self.security_headers_exempt_paths = list(SECURITY_HEADERS_EXEMPT_PATHS)

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize security headers for a Flask application."""
        self.app = app

        # Load configuration from environment
        self.enabled = os.environ.get("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
        self.csp_enabled = os.environ.get("SECURITY_CSP_ENABLED", "true").lower() == "true"
        self.hsts_enabled = os.environ.get("SECURITY_HSTS_ENABLED", "true").lower() == "true"
        self.csp_report_only = os.environ.get("SECURITY_CSP_REPORT_ONLY", "false").lower() == "true"
        self.csp_report_uri = os.environ.get("SECURITY_CSP_REPORT_URI")

        # Register after_request handler
        app.after_request(self._add_security_headers)

        # Register before_request handler for CSP nonce
        if self.csp_nonce_enabled:
            app.before_request(self._generate_csp_nonce)

        # Store reference on app
        app.security_headers = self

        # Add context processor for CSP nonce
        @app.context_processor
        def inject_csp_nonce():
            return {"csp_nonce": getattr(g, "csp_nonce", "")}

        logger.info(
            f"Security headers initialized (enabled={self.enabled}, csp={self.csp_enabled}, hsts={self.hsts_enabled})"
        )

    def _generate_csp_nonce(self) -> None:
        """Generate a CSP nonce for the current request."""
        g.csp_nonce = secrets.token_urlsafe(16)

    def _add_security_headers(self, response: Response) -> Response:
        """
        Add security headers to the response.

        IMPORTANT: WebSocket connections must be completely exempt from security headers
        to avoid WSGI protocol violations (AssertionError: write() before start_response).
        WebSocket upgrade requests use HTTP GET with 'Upgrade: websocket' header, then
        switch to 101 status code. Adding headers during this process causes errors.
        """
        if not self.enabled:
            return response

        # Skip for WebSocket and other exempt paths (e.g., /socket.io/)
        if self._is_path_exempt(request.path, self.security_headers_exempt_paths):
            return response

        # Skip for WebSocket upgrade requests (check Upgrade header)
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return response

        # Skip for certain response types
        if response.status_code == 304:  # Not Modified
            return response

        # Skip for WebSocket protocol switching response
        if response.status_code == 101:  # Switching Protocols
            return response

        # Add basic security headers
        for header, value in self.headers.items():
            # Skip Cache-Control for exempt paths
            if header == "Cache-Control" and self._is_path_exempt(
                request.path, self.cache_exempt_paths
            ):
                continue
            response.headers.setdefault(header, value)

        # Add HSTS for HTTPS connections
        if self.hsts_enabled and (
            request.is_secure or request.headers.get("X-Forwarded-Proto") == "https"
        ):
            for header, value in self.hsts.items():
                response.headers.setdefault(header, value)

        # Add Content-Security-Policy
        if self.csp_enabled and not self._is_path_exempt(request.path, self.csp_exempt_paths):
            csp_header = self._build_csp_header()
            if csp_header:
                header_name = (
                    "Content-Security-Policy-Report-Only"
                    if self.csp_report_only
                    else "Content-Security-Policy"
                )
                response.headers.setdefault(header_name, csp_header)

        # Add Permissions-Policy
        permissions_header = self._build_permissions_policy_header()
        if permissions_header:
            response.headers.setdefault("Permissions-Policy", permissions_header)

        return response

    def _is_path_exempt(self, path: str, exempt_paths: List[str]) -> bool:
        """Check if a path is exempt from certain headers."""
        for exempt in exempt_paths:
            if path.startswith(exempt):
                return True
        return False

    def _build_csp_header(self) -> str:
        """Build the Content-Security-Policy header value."""
        directives = []

        for directive, sources in self.csp.items():
            if directive == "upgrade-insecure-requests":
                # Only include upgrade-insecure-requests when running HTTPS
                # to avoid breaking HTTP-only deployments
                if sources is not None and request.is_secure:
                    directives.append(directive)
            elif sources:
                # Add nonce if enabled
                if self.csp_nonce_enabled and directive in ("script-src", "style-src"):
                    nonce = getattr(g, "csp_nonce", None)
                    if nonce:
                        sources = list(sources) + [f"'nonce-{nonce}'"]
                directives.append(f"{directive} {' '.join(sources)}")

        # Add report-uri if configured
        if self.csp_report_uri:
            directives.append(f"report-uri {self.csp_report_uri}")

        return "; ".join(directives)

    def _build_permissions_policy_header(self) -> str:
        """Build the Permissions-Policy header value."""
        policies = []
        for feature, allowlist in self.permissions_policy.items():
            if not allowlist:
                policies.append(f"{feature}=()")
            else:
                origins = " ".join(f'"{o}"' if o != "self" else o for o in allowlist)
                policies.append(f"{feature}=({origins})")
        return ", ".join(policies)

    # Configuration methods
    def update_header(self, header: str, value: str) -> None:
        """Update a security header value."""
        self.headers[header] = value

    def remove_header(self, header: str) -> None:
        """Remove a security header."""
        self.headers.pop(header, None)

    def update_csp(self, directive: str, sources: List[str]) -> None:
        """Update a CSP directive."""
        self.csp[directive] = sources

    def add_csp_source(self, directive: str, source: str) -> None:
        """Add a source to a CSP directive."""
        if directive not in self.csp:
            self.csp[directive] = []
        if source not in self.csp[directive]:
            self.csp[directive].append(source)

    def remove_csp_source(self, directive: str, source: str) -> None:
        """Remove a source from a CSP directive."""
        if directive in self.csp and source in self.csp[directive]:
            self.csp[directive].remove(source)

    def update_permissions(self, feature: str, allowlist: List[str]) -> None:
        """Update a Permissions-Policy feature."""
        self.permissions_policy[feature] = allowlist

    def add_cache_exempt_path(self, path: str) -> None:
        """Add a path exempt from cache control headers."""
        if path not in self.cache_exempt_paths:
            self.cache_exempt_paths.append(path)

    def add_csp_exempt_path(self, path: str) -> None:
        """Add a path exempt from CSP headers."""
        if path not in self.csp_exempt_paths:
            self.csp_exempt_paths.append(path)

    def get_config(self) -> Dict:
        """Get the current security headers configuration."""
        return {
            "enabled": self.enabled,
            "csp_enabled": self.csp_enabled,
            "hsts_enabled": self.hsts_enabled,
            "csp_report_only": self.csp_report_only,
            "csp_report_uri": self.csp_report_uri,
            "headers": self.headers.copy(),
            "csp": {k: list(v) for k, v in self.csp.items()},
            "permissions_policy": self.permissions_policy.copy(),
            "cache_exempt_paths": self.cache_exempt_paths.copy(),
            "csp_exempt_paths": self.csp_exempt_paths.copy(),
        }


def add_security_headers(response: Response) -> Response:
    """
    Standalone function to add security headers to a response.

    Use this for manual header addition outside the middleware.
    """
    for header, value in DEFAULT_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


def csp_nonce_required(f: Callable) -> Callable:
    """
    Decorator to ensure a CSP nonce is generated for a route.

    Usage:
        @app.route('/page')
        @csp_nonce_required
        def page():
            return render_template('page.html')
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, "csp_nonce"):
            g.csp_nonce = secrets.token_urlsafe(16)
        return f(*args, **kwargs)

    return decorated


# Pre-configured security levels
class SecurityLevel:
    """Pre-configured security header settings for different use cases."""

    @staticmethod
    def strict() -> Dict:
        """
        Strict security settings for production.
        Disables unsafe-inline and unsafe-eval.
        """
        return {
            "csp": {
                "default-src": ["'self'"],
                "script-src": ["'self'"],
                "style-src": ["'self'"],
                "font-src": ["'self'"],
                "img-src": ["'self'", "data:"],
                "connect-src": ["'self'", "wss:"],
                "frame-ancestors": ["'none'"],
                "form-action": ["'self'"],
                "base-uri": ["'self'"],
                "object-src": ["'none'"],
                "upgrade-insecure-requests": [],
            },
            "headers": {
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store, max-age=0, must-revalidate",
            },
        }

    @staticmethod
    def moderate() -> Dict:
        """
        Moderate security settings (default).
        Allows some inline scripts/styles for compatibility.
        """
        return {
            "csp": DEFAULT_CSP.copy(),
            "headers": DEFAULT_HEADERS.copy(),
        }

    @staticmethod
    def relaxed() -> Dict:
        """
        Relaxed security settings for development.
        More permissive but still provides basic protection.
        """
        return {
            "csp": {
                "default-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
                "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", "*"],
                "style-src": ["'self'", "'unsafe-inline'", "*"],
                "font-src": ["'self'", "*"],
                "img-src": ["'self'", "data:", "blob:", "*"],
                "connect-src": ["'self'", "wss:", "ws:", "*"],
                "frame-ancestors": ["'self'"],
                "form-action": ["'self'"],
                "base-uri": ["'self'"],
                "object-src": ["'none'"],
            },
            "headers": {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "SAMEORIGIN",
                "Referrer-Policy": "no-referrer-when-downgrade",
            },
        }


def init_app(app: Flask, level: str = "moderate") -> SecurityHeaders:
    """
    Convenience function to initialize security headers with a preset level.

    Args:
        app: Flask application
        level: Security level ('strict', 'moderate', 'relaxed')

    Returns:
        SecurityHeaders instance
    """
    security = SecurityHeaders()

    # Apply security level
    if level == "strict":
        config = SecurityLevel.strict()
    elif level == "relaxed":
        config = SecurityLevel.relaxed()
    else:
        config = SecurityLevel.moderate()

    security.headers.update(config.get("headers", {}))
    security.csp = config.get("csp", DEFAULT_CSP.copy())

    security.init_app(app)
    return security
