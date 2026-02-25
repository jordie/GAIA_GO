"""
API Key Authentication Service

Provides API key-based authentication as an alternative to session login.
Supports:
- Key generation with secure random tokens
- Scoped permissions (read, write, admin)
- Rate limiting per key
- Key expiration
- Usage tracking and auditing

Usage:
    from services.api_keys import APIKeyService, validate_api_key

    # Create a new API key
    service = APIKeyService(db_path)
    key_data = service.create_key(
        name='CI/CD Pipeline',
        user_id='admin',
        scopes=['read', 'write'],
        expires_days=90
    )
    # key_data['key'] contains the full API key (only shown once)

    # Validate an API key
    result = validate_api_key(api_key, db_path)
    if result['valid']:
        print(f"Key belongs to {result['user_id']}")

API Key Format:
    arch_<key_id>_<secret>
    Example: arch_k7x9m2p4_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# API key prefix for easy identification
KEY_PREFIX = "arch"

# Available scopes
SCOPES = {
    "read": "Read-only access to resources",
    "write": "Create and modify resources",
    "delete": "Delete resources",
    "admin": "Full administrative access",
    "tasks": "Task queue operations",
    "nodes": "Node management",
    "tmux": "tmux session operations",
}

# Default rate limit (requests per hour)
DEFAULT_RATE_LIMIT = 1000


def generate_key_id(length: int = 8) -> str:
    """Generate a short, readable key ID."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # No confusing chars
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_secret(length: int = 32) -> str:
    """Generate a secure random secret."""
    return secrets.token_hex(length)


def hash_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def create_full_key(key_id: str, secret: str) -> str:
    """Create the full API key string."""
    return f"{KEY_PREFIX}_{key_id}_{secret}"


def parse_api_key(api_key: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse an API key into key_id and secret."""
    if not api_key:
        return None, None

    parts = api_key.split("_")
    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        return None, None

    return parts[1], parts[2]


class APIKeyService:
    """Service for managing API keys."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_key(
        self,
        name: str,
        user_id: str,
        description: str = None,
        scopes: List[str] = None,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        expires_days: int = None,
    ) -> Dict[str, Any]:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key
            user_id: User who owns this key
            description: Optional description
            scopes: List of permission scopes (default: ['read'])
            rate_limit: Requests per hour limit
            expires_days: Days until expiration (None = never)

        Returns:
            Dict with key details including the full key (shown only once)
        """
        # Generate key components
        key_id = generate_key_id()
        secret = generate_secret()
        full_key = create_full_key(key_id, secret)
        key_hash = hash_key(full_key)

        # Validate scopes
        if scopes is None:
            scopes = ["read"]
        invalid_scopes = [s for s in scopes if s not in SCOPES]
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {invalid_scopes}")

        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()

        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO api_keys
                    (key_id, key_hash, name, description, user_id, scopes, rate_limit, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        key_id,
                        key_hash,
                        name,
                        description,
                        user_id,
                        json.dumps(scopes),
                        rate_limit,
                        expires_at,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"Key with ID '{key_id}' already exists")

        logger.info(f"Created API key '{name}' for user {user_id}")

        return {
            "key": full_key,  # Only returned on creation
            "key_id": key_id,
            "name": name,
            "description": description,
            "user_id": user_id,
            "scopes": scopes,
            "rate_limit": rate_limit,
            "expires_at": expires_at,
            "created_at": datetime.now().isoformat(),
        }

    def validate_key(
        self,
        api_key: str,
        required_scope: str = None,
        log_usage: bool = True,
        endpoint: str = None,
        method: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ) -> Dict[str, Any]:
        """
        Validate an API key.

        Args:
            api_key: The full API key string
            required_scope: Scope that must be present
            log_usage: Whether to log this usage
            endpoint: API endpoint being accessed
            method: HTTP method
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Dict with validation result
        """
        result = {
            "valid": False,
            "error": None,
            "key_id": None,
            "user_id": None,
            "scopes": [],
            "name": None,
        }

        # Parse the key
        key_id, secret = parse_api_key(api_key)
        if not key_id or not secret:
            result["error"] = "Invalid API key format"
            return result

        result["key_id"] = key_id
        key_hash = hash_key(api_key)

        with self._get_connection() as conn:
            # Find the key
            row = conn.execute(
                """
                SELECT * FROM api_keys WHERE key_id = ?
            """,
                (key_id,),
            ).fetchone()

            if not row:
                result["error"] = "API key not found"
                return result

            # Verify hash
            if not hmac.compare_digest(row["key_hash"], key_hash):
                result["error"] = "Invalid API key"
                return result

            # Check if enabled
            if not row["enabled"]:
                result["error"] = "API key is disabled"
                return result

            # Check expiration
            if row["expires_at"]:
                expires = datetime.fromisoformat(row["expires_at"])
                if datetime.now() > expires:
                    result["error"] = "API key has expired"
                    return result

            # Parse scopes
            try:
                scopes = json.loads(row["scopes"])
            except json.JSONDecodeError:
                scopes = ["read"]

            # Check required scope
            if required_scope and required_scope not in scopes and "admin" not in scopes:
                result["error"] = f"Missing required scope: {required_scope}"
                return result

            # Check rate limit
            if not self._check_rate_limit(key_id, row["rate_limit"], conn):
                result["error"] = "Rate limit exceeded"
                return result

            # Update last used
            conn.execute(
                """
                UPDATE api_keys
                SET last_used_at = CURRENT_TIMESTAMP,
                    last_used_ip = ?,
                    use_count = use_count + 1
                WHERE key_id = ?
            """,
                (ip_address, key_id),
            )
            conn.commit()

            # Log usage
            if log_usage and endpoint:
                self._log_usage(key_id, endpoint, method, ip_address, user_agent, conn)

            result["valid"] = True
            result["user_id"] = row["user_id"]
            result["scopes"] = scopes
            result["name"] = row["name"]

        return result

    def _check_rate_limit(self, key_id: str, limit: int, conn: sqlite3.Connection) -> bool:
        """Check if key is within rate limit."""
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

        row = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM api_key_usage
            WHERE key_id = ? AND created_at > ?
        """,
            (key_id, one_hour_ago),
        ).fetchone()

        return row["count"] < limit

    def _log_usage(
        self,
        key_id: str,
        endpoint: str,
        method: str,
        ip_address: str,
        user_agent: str,
        conn: sqlite3.Connection,
    ):
        """Log API key usage."""
        try:
            conn.execute(
                """
                INSERT INTO api_key_usage
                (key_id, endpoint, method, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            """,
                (key_id, endpoint, method, ip_address, user_agent),
            )
            conn.commit()
        except Exception as e:
            logger.debug(f"Failed to log API usage: {e}")

    def get_key(self, key_id: str) -> Optional[Dict]:
        """Get API key details (without the secret)."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT key_id, name, description, user_id, scopes, rate_limit,
                       expires_at, last_used_at, last_used_ip, use_count,
                       enabled, created_at, updated_at
                FROM api_keys WHERE key_id = ?
            """,
                (key_id,),
            ).fetchone()

            if row:
                data = dict(row)
                try:
                    data["scopes"] = json.loads(data["scopes"])
                except json.JSONDecodeError:
                    data["scopes"] = ["read"]
                return data
            return None

    def list_keys(self, user_id: str = None, include_disabled: bool = False) -> List[Dict]:
        """List API keys."""
        query = "SELECT * FROM api_keys WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if not include_disabled:
            query += " AND enabled = 1"

        query += " ORDER BY created_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

            keys = []
            for row in rows:
                data = dict(row)
                # Never return the hash
                del data["key_hash"]
                try:
                    data["scopes"] = json.loads(data["scopes"])
                except json.JSONDecodeError:
                    data["scopes"] = ["read"]
                keys.append(data)

            return keys

    def update_key(self, key_id: str, **kwargs) -> Optional[Dict]:
        """Update API key settings."""
        allowed = {"name", "description", "scopes", "rate_limit", "enabled"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}

        if not updates:
            return self.get_key(key_id)

        if "scopes" in updates:
            updates["scopes"] = json.dumps(updates["scopes"])

        updates["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [key_id]

        with self._get_connection() as conn:
            result = conn.execute(f"UPDATE api_keys SET {set_clause} WHERE key_id = ?", values)
            conn.commit()

            if result.rowcount == 0:
                return None

        logger.info(f"Updated API key {key_id}")
        return self.get_key(key_id)

    def revoke_key(self, key_id: str) -> bool:
        """Revoke (disable) an API key."""
        with self._get_connection() as conn:
            result = conn.execute(
                """
                UPDATE api_keys SET enabled = 0, updated_at = CURRENT_TIMESTAMP
                WHERE key_id = ?
            """,
                (key_id,),
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Revoked API key {key_id}")
                return True
            return False

    def delete_key(self, key_id: str) -> bool:
        """Permanently delete an API key."""
        with self._get_connection() as conn:
            result = conn.execute("DELETE FROM api_keys WHERE key_id = ?", (key_id,))
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted API key {key_id}")
                return True
            return False

    def regenerate_key(self, key_id: str) -> Optional[Dict]:
        """Regenerate the secret for an existing key."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()

            if not row:
                return None

            # Generate new secret
            secret = generate_secret()
            full_key = create_full_key(key_id, secret)
            key_hash = hash_key(full_key)

            conn.execute(
                """
                UPDATE api_keys
                SET key_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE key_id = ?
            """,
                (key_hash, key_id),
            )
            conn.commit()

        logger.info(f"Regenerated API key {key_id}")

        return {
            "key": full_key,
            "key_id": key_id,
            "message": "Key regenerated. Old key is no longer valid.",
        }

    def get_usage(self, key_id: str, limit: int = 100) -> List[Dict]:
        """Get usage history for a key."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM api_key_usage
                WHERE key_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (key_id, limit),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_stats(self, key_id: str = None) -> Dict:
        """Get API key statistics."""
        with self._get_connection() as conn:
            if key_id:
                # Stats for a specific key
                key = self.get_key(key_id)
                if not key:
                    return {"error": "Key not found"}

                # Usage in last 24 hours
                yesterday = (datetime.now() - timedelta(days=1)).isoformat()
                usage_24h = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM api_key_usage
                    WHERE key_id = ? AND created_at > ?
                """,
                    (key_id, yesterday),
                ).fetchone()["count"]

                # Usage by endpoint
                by_endpoint = conn.execute(
                    """
                    SELECT endpoint, COUNT(*) as count
                    FROM api_key_usage
                    WHERE key_id = ?
                    GROUP BY endpoint
                    ORDER BY count DESC
                    LIMIT 10
                """,
                    (key_id,),
                ).fetchall()

                return {
                    "key_id": key_id,
                    "total_uses": key["use_count"],
                    "uses_24h": usage_24h,
                    "by_endpoint": {row["endpoint"]: row["count"] for row in by_endpoint},
                    "last_used": key["last_used_at"],
                    "rate_limit": key["rate_limit"],
                }
            else:
                # Global stats
                total_keys = conn.execute("SELECT COUNT(*) as count FROM api_keys").fetchone()[
                    "count"
                ]

                active_keys = conn.execute(
                    "SELECT COUNT(*) as count FROM api_keys WHERE enabled = 1"
                ).fetchone()["count"]

                yesterday = (datetime.now() - timedelta(days=1)).isoformat()
                total_usage_24h = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM api_key_usage
                    WHERE created_at > ?
                """,
                    (yesterday,),
                ).fetchone()["count"]

                return {
                    "total_keys": total_keys,
                    "active_keys": active_keys,
                    "disabled_keys": total_keys - active_keys,
                    "total_usage_24h": total_usage_24h,
                }


# Singleton instance
_api_key_service: Optional[APIKeyService] = None


def get_api_key_service(db_path: str = None) -> APIKeyService:
    """Get or create the API key service singleton."""
    global _api_key_service
    if _api_key_service is None:
        if db_path is None:
            raise ValueError("db_path required for first initialization")
        _api_key_service = APIKeyService(db_path)
    elif db_path:
        _api_key_service.db_path = db_path
    return _api_key_service


def validate_api_key(
    api_key: str,
    db_path: str = None,
    required_scope: str = None,
    endpoint: str = None,
    method: str = None,
    ip_address: str = None,
    user_agent: str = None,
) -> Dict[str, Any]:
    """
    Convenience function to validate an API key.

    Args:
        api_key: The API key to validate
        db_path: Database path
        required_scope: Required permission scope
        endpoint: API endpoint (for logging)
        method: HTTP method (for logging)
        ip_address: Client IP (for logging)
        user_agent: Client user agent (for logging)

    Returns:
        Validation result dict
    """
    service = get_api_key_service(db_path)
    return service.validate_key(
        api_key,
        required_scope=required_scope,
        endpoint=endpoint,
        method=method,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def extract_api_key(request) -> Optional[str]:
    """
    Extract API key from request headers or query params.

    Checks in order:
    1. Authorization: Bearer <key>
    2. X-API-Key: <key>
    3. ?api_key=<key> query parameter
    """
    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Check X-API-Key header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        return api_key_header

    # Check query parameter (less secure, but useful for testing)
    api_key_param = request.args.get("api_key")
    if api_key_param:
        return api_key_param

    return None
