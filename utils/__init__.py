"""
Utility functions for Architect Dashboard.

This module provides common utility functions used across the application.
"""

import html


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


__all__ = [
    "sanitize_html",
    "sanitize_string",
]
