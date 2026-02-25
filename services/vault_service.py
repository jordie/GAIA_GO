"""
Vault Service - Secure credential retrieval for automation

Integration with Comet automation and other services that need
secure access to login credentials.
"""

import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet

DB_PATH = Path(__file__).parent.parent / "data" / "architect.db"
KEY_FILE = Path.home() / ".architect" / "vault.key"


def get_encryption_key():
    """Get the encryption key."""
    if not KEY_FILE.exists():
        raise FileNotFoundError(
            f"Vault key not found at {KEY_FILE}. "
            "Run: python3 scripts/vault_cli.py list to initialize."
        )
    return KEY_FILE.read_bytes()


def decrypt_secret(encrypted: bytes) -> str:
    """Decrypt a secret value."""
    key = get_encryption_key()
    f = Fernet(key)
    return f.decrypt(encrypted).decode()


def get_login_credentials(service: str) -> dict:
    """
    Get login credentials for a service.

    Args:
        service: Service name (gmail, chatgpt, grok, claude, etc.)

    Returns:
        dict with keys: username, password, url, service
        Returns None if not found or not set

    Example:
        >>> creds = get_login_credentials('gmail')
        >>> print(creds['username'])  # jgirmay@gmail.com
        >>> print(creds['password'])  # decrypted password
        >>> print(creds['url'])  # https://mail.google.com
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    try:
        secret = conn.execute(
            """
            SELECT id, name, encrypted_value, service, username, url, description
            FROM secrets
            WHERE service = ? AND category = 'login'
        """,
            (service,),
        ).fetchone()

        if not secret:
            return None

        if not secret["encrypted_value"]:
            # Credential exists but password not set
            return {
                "service": secret["service"],
                "username": secret["username"],
                "url": secret["url"],
                "password": None,
                "status": "not_set",
            }

        try:
            password = decrypt_secret(secret["encrypted_value"])

            # Update access tracking
            conn.execute(
                """
                UPDATE secrets
                SET last_accessed = CURRENT_TIMESTAMP,
                    access_count = access_count + 1
                WHERE id = ?
            """,
                (secret["id"],),
            )

            # Log access
            import os

            conn.execute(
                """
                INSERT INTO secret_access_log (secret_id, accessed_by, action)
                VALUES (?, ?, 'api_access')
            """,
                (secret["id"], os.getenv("USER", "automation")),
            )

            conn.commit()

            return {
                "service": secret["service"],
                "username": secret["username"],
                "url": secret["url"],
                "password": password,
                "status": "active",
            }

        except Exception as e:
            return {
                "service": secret["service"],
                "username": secret["username"],
                "url": secret["url"],
                "password": None,
                "status": "decrypt_failed",
                "error": str(e),
            }

    finally:
        conn.close()


def list_available_services() -> list:
    """Get list of all services with login credentials configured."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    try:
        services = conn.execute(
            """
            SELECT service, username, url,
                   CASE WHEN encrypted_value = '' THEN 'not_set' ELSE 'active' END as status
            FROM secrets
            WHERE category = 'login'
            ORDER BY service
        """
        ).fetchall()

        return [dict(s) for s in services]

    finally:
        conn.close()


def is_credential_available(service: str) -> bool:
    """Check if a credential is available and has a password set."""
    creds = get_login_credentials(service)
    return creds is not None and creds.get("password") is not None


# Example usage for Comet automation
def get_comet_credentials():
    """Get all credentials needed for Comet automation."""
    services = ["gmail", "chatgpt", "grok", "claude"]
    credentials = {}

    for service in services:
        creds = get_login_credentials(service)
        credentials[service] = creds

    return credentials
