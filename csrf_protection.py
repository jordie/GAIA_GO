#!/usr/bin/env python3
"""
CSRF Protection Module

Provides Cross-Site Request Forgery (CSRF) protection for the Architect Dashboard.

Features:
- Cryptographically secure token generation
- Token validation with timing-safe comparison
- Token rotation on sensitive operations
- Configurable exemptions for API key authentication
- Double-submit cookie pattern support

Usage:
    from csrf_protection import generate_csrf_token, validate_csrf_token, csrf_protect

    # In route:
    @app.route('/api/resource', methods=['POST'])
    @csrf_protect
    def create_resource():
        ...

    # In template:
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
"""

import hashlib
import hmac
import logging
import os
import secrets
import time
from functools import wraps
from typing import List, Optional, Tuple

from flask import current_app, g, jsonify, request, session

logger = logging.getLogger(__name__)

# Configuration
CSRF_TOKEN_LENGTH = 32  # 256 bits of entropy
CSRF_TOKEN_LIFETIME = 3600  # 1 hour (tokens rotate but old ones valid for this period)
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_COOKIE_NAME = "csrf_double_submit"

# Methods that require CSRF protection
CSRF_PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Endpoints exempt from CSRF (login, public APIs, etc.)
CSRF_EXEMPT_ENDPOINTS = {
    "/login",
    "/api/errors",  # Error logging from nodes (uses API key)
    "/api/nodes",  # Node registration (uses API key)
    "/health",
    "/api/health",
}

# Prefixes exempt from CSRF (typically external API integrations)
CSRF_EXEMPT_PREFIXES = [
    "/api/webhooks/",  # Incoming webhooks
    "/api/external/",  # External integrations
    "/api/tasks/monitor/",  # Monitor archive operations (public, no auth required)
    "/api/todos",  # Todo REST API (stateless, non-browser clients)
]


def generate_csrf_token(force_new: bool = False) -> str:
    """
    Generate a CSRF token and store it in the session.

    Args:
        force_new: If True, always generate a new token (for rotation)

    Returns:
        The CSRF token string
    """
    # Check for existing valid token
    if not force_new:
        existing_token = session.get("csrf_token")
        token_time = session.get("csrf_token_time", 0)

        # Reuse token if it's still valid (within lifetime)
        if existing_token and (time.time() - token_time) < CSRF_TOKEN_LIFETIME:
            return existing_token

    # Generate new cryptographically secure token
    token = secrets.token_hex(CSRF_TOKEN_LENGTH)

    # Store in session with timestamp
    session["csrf_token"] = token
    session["csrf_token_time"] = time.time()

    # Also store previous token for grace period during rotation
    if session.get("csrf_token") and session.get("csrf_token") != token:
        session["csrf_token_prev"] = session.get("csrf_token")
        session["csrf_token_prev_time"] = session.get("csrf_token_time", 0)

    logger.debug(f"Generated new CSRF token for session")
    return token


def validate_csrf_token(token: Optional[str]) -> Tuple[bool, str]:
    """
    Validate a CSRF token against the session token.

    Args:
        token: The token to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not token:
        return False, "CSRF token missing"

    # Get current token from session
    session_token = session.get("csrf_token")
    if not session_token:
        return False, "No CSRF token in session"

    # Use timing-safe comparison to prevent timing attacks
    if hmac.compare_digest(token, session_token):
        return True, ""

    # Check previous token (grace period during rotation)
    prev_token = session.get("csrf_token_prev")
    prev_time = session.get("csrf_token_prev_time", 0)

    if prev_token and (time.time() - prev_time) < 300:  # 5-minute grace period
        if hmac.compare_digest(token, prev_token):
            return True, ""

    return False, "CSRF token invalid"


def get_csrf_token_from_request() -> Optional[str]:
    """
    Extract CSRF token from request (header or form field).

    Checks in order:
    1. X-CSRF-Token header
    2. csrf_token form field
    3. csrf_token in JSON body

    Returns:
        The token string or None
    """
    # Check header first (preferred for AJAX)
    token = request.headers.get(CSRF_HEADER_NAME)
    if token:
        return token

    # Check form field
    token = request.form.get(CSRF_FORM_FIELD)
    if token:
        return token

    # Check JSON body
    if request.is_json:
        try:
            data = request.get_json(silent=True)
            if data and isinstance(data, dict):
                token = data.get(CSRF_FORM_FIELD)
                if token:
                    return token
        except Exception:
            pass

    return None


def is_csrf_exempt() -> bool:
    """
    Check if the current request is exempt from CSRF protection.

    Returns:
        True if exempt, False otherwise
    """
    # Check exact endpoint matches
    if request.path in CSRF_EXEMPT_ENDPOINTS:
        return True

    # Check prefix matches
    for prefix in CSRF_EXEMPT_PREFIXES:
        if request.path.startswith(prefix):
            return True

    # API key authenticated requests are exempt (they have their own auth)
    if hasattr(g, "api_key_auth") and g.api_key_auth:
        return True

    return False


def csrf_protect(f):
    """
    Decorator to enforce CSRF protection on a route.

    Usage:
        @app.route('/api/resource', methods=['POST'])
        @require_auth
        @csrf_protect
        def create_resource():
            ...
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip for safe methods
        if request.method not in CSRF_PROTECTED_METHODS:
            return f(*args, **kwargs)

        # Skip for exempt endpoints
        if is_csrf_exempt():
            return f(*args, **kwargs)

        # Validate token
        token = get_csrf_token_from_request()
        is_valid, error = validate_csrf_token(token)

        if not is_valid:
            logger.warning(f"CSRF validation failed for {request.path}: {error}")
            return (
                jsonify(
                    {"error": "CSRF validation failed", "code": "CSRF_INVALID", "message": error}
                ),
                403,
            )

        return f(*args, **kwargs)

    return decorated


def csrf_protect_all():
    """
    Before-request handler to enforce CSRF protection globally.

    Add to app:
        app.before_request(csrf_protect_all)
    """
    # Skip for safe methods
    if request.method not in CSRF_PROTECTED_METHODS:
        return None

    # Skip for unauthenticated requests (they'll fail auth anyway)
    if not session.get("authenticated"):
        return None

    # Skip for exempt endpoints
    if is_csrf_exempt():
        return None

    # Validate token
    token = get_csrf_token_from_request()
    is_valid, error = validate_csrf_token(token)

    if not is_valid:
        logger.warning(f"CSRF validation failed for {request.path}: {error}")
        if request.is_json or request.path.startswith("/api/"):
            return (
                jsonify(
                    {"error": "CSRF validation failed", "code": "CSRF_INVALID", "message": error}
                ),
                403,
            )
        # For non-API requests, redirect to login with error
        from flask import flash, redirect, url_for

        flash("Your session has expired. Please log in again.", "error")
        return redirect(url_for("login"))

    return None


def rotate_csrf_token():
    """
    Rotate the CSRF token after a sensitive operation.

    Call after operations like:
    - Password change
    - Email change
    - Permission changes
    """
    generate_csrf_token(force_new=True)
    logger.debug("CSRF token rotated after sensitive operation")


def get_csrf_context() -> dict:
    """
    Get CSRF context for template rendering.

    Returns:
        Dictionary with csrf_token and csrf_header_name
    """
    return {
        "csrf_token": generate_csrf_token(),
        "csrf_header_name": CSRF_HEADER_NAME,
        "csrf_form_field": CSRF_FORM_FIELD,
    }


class CSRFProtection:
    """
    Flask extension-style CSRF protection.

    Usage:
        csrf = CSRFProtection()
        csrf.init_app(app)
    """

    def __init__(self, app=None, exempt_endpoints: List[str] = None):
        self.exempt_endpoints = set(exempt_endpoints or [])
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize CSRF protection for the Flask app."""
        # Add exempt endpoints from config
        if "CSRF_EXEMPT_ENDPOINTS" in app.config:
            self.exempt_endpoints.update(app.config["CSRF_EXEMPT_ENDPOINTS"])

        # Register before_request handler
        app.before_request(self._check_csrf)

        # Add CSRF token to template context
        @app.context_processor
        def inject_csrf():
            return get_csrf_context()

        # Store reference on app
        app.csrf_protection = self

        logger.info("CSRF protection initialized")

    def _check_csrf(self):
        """Before-request CSRF check."""
        return csrf_protect_all()

    def exempt(self, view_or_endpoint):
        """
        Decorator to exempt a view from CSRF protection.

        Usage:
            @csrf.exempt
            @app.route('/webhook', methods=['POST'])
            def webhook():
                ...
        """
        if callable(view_or_endpoint):
            # It's a view function
            endpoint = view_or_endpoint.__name__
            self.exempt_endpoints.add(endpoint)
            return view_or_endpoint
        else:
            # It's an endpoint string
            self.exempt_endpoints.add(view_or_endpoint)
            return lambda f: f


# Convenience function to add CSRF to existing forms
def csrf_field() -> str:
    """
    Generate an HTML hidden input field with the CSRF token.

    Returns:
        HTML string for the hidden input
    """
    token = generate_csrf_token()
    return f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">'


# Double-submit cookie pattern support
def set_csrf_cookie(response):
    """
    Set CSRF token as a cookie for double-submit pattern.

    This allows JavaScript to read the token and include it in requests.
    The token is also stored in session for server-side validation.
    """
    token = session.get("csrf_token")
    if token:
        response.set_cookie(
            CSRF_COOKIE_NAME,
            token,
            httponly=False,  # Must be readable by JavaScript
            secure=True,  # HTTPS only
            samesite="Strict",
            max_age=CSRF_TOKEN_LIFETIME,
        )
    return response
