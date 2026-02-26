#!/usr/bin/env python3
"""
Secure Vault CLI
Manage encrypted login credentials for automation

Usage:
    python3 vault_cli.py add gmail        # Add Gmail password
    python3 vault_cli.py add chatgpt      # Add ChatGPT password
    python3 vault_cli.py list             # List all secrets (values hidden)
    python3 vault_cli.py view gmail       # View decrypted Gmail password
    python3 vault_cli.py delete gmail     # Delete a secret
    python3 vault_cli.py rotate gmail     # Rotate/update a password
"""

import getpass
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

# Paths
DB_PATH = Path(__file__).parent.parent / "data" / "architect.db"
KEY_FILE = Path.home() / ".architect" / "vault.key"


def get_or_create_key():
    """Get or create encryption key."""
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    else:
        # Generate new key
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        KEY_FILE.chmod(0o600)  # Owner read/write only
        print(f"✅ Created new encryption key at {KEY_FILE}")
        return key


def encrypt_value(value: str) -> bytes:
    """Encrypt a secret value using Fernet."""
    key = get_or_create_key()
    f = Fernet(key)
    return f.encrypt(value.encode())


def decrypt_value(encrypted: bytes) -> str:
    """Decrypt a secret value using Fernet."""
    key = get_or_create_key()
    f = Fernet(key)
    return f.decrypt(encrypted).decode()


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def list_secrets(category=None):
    """List all secrets (without values)."""
    with get_db() as conn:
        if category:
            secrets = conn.execute(
                """
                SELECT id, name, category, service, username, url, description,
                       last_accessed, access_count, created_at
                FROM secrets
                WHERE category = ?
                ORDER BY service, name
            """,
                (category,),
            ).fetchall()
        else:
            secrets = conn.execute(
                """
                SELECT id, name, category, service, username, url, description,
                       last_accessed, access_count, created_at
                FROM secrets
                ORDER BY category, service, name
            """
            ).fetchall()

        if not secrets:
            print("No secrets found.")
            return

        print(
            f"\n{'ID':<4} {'Name':<20} {'Category':<10} {'Service':<12} {'Username':<25} {'Access Count':<12}"
        )
        print("=" * 100)

        for s in secrets:
            print(
                f"{s['id']:<4} {s['name']:<20} {s['category']:<10} {s['service'] or '-':<12} "
                f"{s['username'] or '-':<25} {s['access_count']:<12}"
            )


def view_secret(name_or_service):
    """View a decrypted secret value."""
    with get_db() as conn:
        # Try by name first
        secret = conn.execute(
            """
            SELECT id, name, encrypted_value, category, service, username, url
            FROM secrets
            WHERE name = ? OR service = ?
        """,
            (name_or_service, name_or_service),
        ).fetchone()

        if not secret:
            print(f"❌ Secret '{name_or_service}' not found.")
            return

        if not secret["encrypted_value"]:
            print(f"⚠️  Secret '{secret['name']}' exists but has no password set.")
            print(f"   Service: {secret['service']}")
            print(f"   Username: {secret['username']}")
            print(f"   URL: {secret['url']}")
            print(f"\n   Use: python3 vault_cli.py add {secret['service']} --password")
            return

        try:
            decrypted = decrypt_value(secret["encrypted_value"])

            print(f"\n🔐 Secret: {secret['name']}")
            print(f"   Category: {secret['category']}")
            print(f"   Service: {secret['service']}")
            print(f"   Username: {secret['username']}")
            print(f"   URL: {secret['url']}")
            print(f"   Password: {decrypted}")
            print()

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
            conn.execute(
                """
                INSERT INTO secret_access_log (secret_id, accessed_by, action)
                VALUES (?, ?, 'view')
            """,
                (secret["id"], os.getenv("USER", "unknown")),
            )

            conn.commit()

        except Exception as e:
            print(f"❌ Failed to decrypt: {e}")


def add_or_update_secret(service, password=None, username=None):
    """Add or update a secret."""
    with get_db() as conn:
        # Check if secret exists
        secret = conn.execute(
            """
            SELECT id, name, encrypted_value, username as old_username
            FROM secrets
            WHERE service = ?
        """,
            (service,),
        ).fetchone()

        # Get password if not provided
        if password is None:
            password = getpass.getpass(f"Enter password for {service}: ")
            password_confirm = getpass.getpass(f"Confirm password: ")

            if password != password_confirm:
                print("❌ Passwords don't match.")
                return

        # Get username if not provided and not in DB
        if username is None and (not secret or not secret["old_username"]):
            username = input(f"Enter username/email for {service} (optional): ").strip()
            if not username:
                username = None
        elif username is None and secret:
            username = secret["old_username"]

        encrypted = encrypt_value(password)

        if secret:
            # Update existing
            conn.execute(
                """
                UPDATE secrets
                SET encrypted_value = ?,
                    username = COALESCE(?, username),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (encrypted, username, secret["id"]),
            )

            action = "update"
            print(f"✅ Updated password for {service}")
        else:
            # Create new
            name = f"{service}_login"
            url = {
                "gmail": "https://mail.google.com",
                "chatgpt": "https://chat.openai.com",
                "grok": "https://grok.x.ai",
                "claude": "https://claude.ai",
            }.get(service, "")

            conn.execute(
                """
                INSERT INTO secrets (name, encrypted_value, category, service, username, url, description)
                VALUES (?, ?, 'login', ?, ?, ?, ?)
            """,
                (name, encrypted, service, username, url, f"{service.title()} login credentials"),
            )

            action = "create"
            print(f"✅ Added new credential for {service}")

        # Log action
        conn.execute(
            """
            INSERT INTO secret_access_log (secret_id, accessed_by, action)
            VALUES (
                (SELECT id FROM secrets WHERE service = ?),
                ?, ?
            )
        """,
            (service, os.getenv("USER", "unknown"), action),
        )

        conn.commit()


def delete_secret(name_or_service):
    """Delete a secret."""
    confirm = input(f"⚠️  Delete secret '{name_or_service}'? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return

    with get_db() as conn:
        result = conn.execute(
            """
            DELETE FROM secrets
            WHERE name = ? OR service = ?
        """,
            (name_or_service, name_or_service),
        )

        if result.rowcount > 0:
            conn.commit()
            print(f"✅ Deleted secret '{name_or_service}'")
        else:
            print(f"❌ Secret '{name_or_service}' not found.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        category = sys.argv[2] if len(sys.argv) > 2 else None
        list_secrets(category)

    elif command == "view":
        if len(sys.argv) < 3:
            print("Usage: vault_cli.py view <name_or_service>")
            sys.exit(1)
        view_secret(sys.argv[2])

    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: vault_cli.py add <service> [--password PASSWORD] [--username USERNAME]")
            sys.exit(1)

        service = sys.argv[2]
        password = None
        username = None

        # Parse optional flags
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--password" and i + 1 < len(sys.argv):
                password = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--username" and i + 1 < len(sys.argv):
                username = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        add_or_update_secret(service, password, username)

    elif command == "rotate":
        if len(sys.argv) < 3:
            print("Usage: vault_cli.py rotate <service>")
            sys.exit(1)
        print(f"🔄 Rotating password for {sys.argv[2]}...")
        add_or_update_secret(sys.argv[2])

    elif command == "delete":
        if len(sys.argv) < 3:
            print("Usage: vault_cli.py delete <name_or_service>")
            sys.exit(1)
        delete_secret(sys.argv[2])

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
