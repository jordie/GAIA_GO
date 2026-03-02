#!/usr/bin/env python3
"""
Cooldown Manager

Manages persistent cooldowns for auto-confirm worker using SQLite.
Cooldowns survive worker restarts, preventing duplicate confirmations across sessions.
"""

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional


class CooldownManager:
    """Manages persistent cooldowns using SQLite."""

    def __init__(self, db_path: str = "/tmp/auto_confirm_cooldowns.db"):
        """Initialize cooldown manager."""
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Create cooldown table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cooldowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                prompt_key TEXT NOT NULL,
                cooldown_expires_at REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                operation_type TEXT,
                metadata JSON,
                UNIQUE(session_name, prompt_key)
            )
        """
        )

        # Create index for faster lookups
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_key ON cooldowns(session_name, prompt_key)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cooldowns(cooldown_expires_at)")

        conn.commit()
        conn.close()

    def set_cooldown(self, session_name: str, prompt_key: str, duration_seconds: int = 120):
        """
        Set a cooldown for a prompt.

        Args:
            session_name: Session identifier
            prompt_key: Unique prompt key
            duration_seconds: Cooldown duration (default 120s)
        """
        expires_at = time.time() + duration_seconds

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO cooldowns
            (session_name, prompt_key, cooldown_expires_at, operation_type)
            VALUES (?, ?, ?, ?)
        """,
            (session_name, prompt_key, expires_at, None),
        )
        conn.commit()
        conn.close()

    def is_in_cooldown(self, session_name: str, prompt_key: str) -> bool:
        """
        Check if a prompt is in cooldown.

        Args:
            session_name: Session identifier
            prompt_key: Unique prompt key

        Returns:
            True if in cooldown, False otherwise
        """
        conn = sqlite3.connect(self.db_path)

        cursor = conn.execute(
            """
            SELECT cooldown_expires_at FROM cooldowns
            WHERE session_name = ? AND prompt_key = ?
        """,
            (session_name, prompt_key),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return False

        # Check if cooldown has expired
        return time.time() < row[0]

    def clear_expired_cooldowns(self):
        """Remove expired cooldowns from database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM cooldowns WHERE cooldown_expires_at < ?", (time.time(),))
        deleted = conn.total_changes
        conn.commit()
        conn.close()

        return deleted

    def clear_session_cooldowns(self, session_name: str):
        """Clear all cooldowns for a session."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM cooldowns WHERE session_name = ?", (session_name,))
        deleted = conn.total_changes
        conn.commit()
        conn.close()

        return deleted

    def get_active_cooldowns(self, session_name: str = None) -> Dict:
        """
        Get active cooldowns.

        Args:
            session_name: Optional session filter

        Returns:
            Dict mapping (session, prompt_key) -> remaining_seconds
        """
        conn = sqlite3.connect(self.db_path)

        if session_name:
            cursor = conn.execute(
                """
                SELECT session_name, prompt_key, cooldown_expires_at
                FROM cooldowns
                WHERE session_name = ? AND cooldown_expires_at > ?
                ORDER BY cooldown_expires_at DESC
            """,
                (session_name, time.time()),
            )
        else:
            cursor = conn.execute(
                """
                SELECT session_name, prompt_key, cooldown_expires_at
                FROM cooldowns
                WHERE cooldown_expires_at > ?
                ORDER BY cooldown_expires_at DESC
            """,
                (time.time(),),
            )

        cooldowns = {}
        current_time = time.time()

        for row in cursor.fetchall():
            session, key, expires = row
            remaining = max(0, expires - current_time)
            cooldowns[(session, key)] = remaining

        conn.close()

        return cooldowns

    def get_cooldown_stats(self) -> Dict:
        """Get cooldown statistics."""
        conn = sqlite3.connect(self.db_path)

        # Total cooldowns
        cursor = conn.execute("SELECT COUNT(*) FROM cooldowns")
        total = cursor.fetchone()[0]

        # Active cooldowns
        cursor = conn.execute(
            "SELECT COUNT(*) FROM cooldowns WHERE cooldown_expires_at > ?",
            (time.time(),),
        )
        active = cursor.fetchone()[0]

        # Expired cooldowns
        expired = total - active

        # By session
        cursor = conn.execute(
            """
            SELECT session_name, COUNT(*) as count
            FROM cooldowns
            WHERE cooldown_expires_at > ?
            GROUP BY session_name
            ORDER BY count DESC
        """,
            (time.time(),),
        )

        by_session = dict(cursor.fetchall())

        conn.close()

        return {
            "total": total,
            "active": active,
            "expired": expired,
            "by_session": by_session,
        }

    def cleanup_old_records(self, days: int = 7):
        """Clean up old cooldown records."""
        cutoff_time = time.time() - (days * 86400)

        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM cooldowns WHERE cooldown_expires_at < ?", (cutoff_time,))
        deleted = conn.total_changes
        conn.commit()
        conn.close()

        return deleted


def main():
    """Test the cooldown manager."""
    print("Testing Cooldown Manager")
    print("=" * 80)

    manager = CooldownManager()

    # Test setting cooldowns
    print("\n1. Setting cooldowns:")
    manager.set_cooldown("basic_edu", "proceed_yes:abc123", 30)
    manager.set_cooldown("foundation", "accept_edits:def456", 60)
    manager.set_cooldown("inspector", "continue:ghi789", 120)
    print("   ✓ Set 3 cooldowns")

    # Test checking cooldowns
    print("\n2. Checking cooldowns:")
    in_cooldown = manager.is_in_cooldown("basic_edu", "proceed_yes:abc123")
    print(f"   basic_edu proceed_yes: {in_cooldown}")

    not_in_cooldown = manager.is_in_cooldown("rando", "unknown:xyz")
    print(f"   rando unknown: {not_in_cooldown}")

    # Test getting active cooldowns
    print("\n3. Active cooldowns:")
    active = manager.get_active_cooldowns()
    for (session, key), remaining in active.items():
        print(f"   {session}:{key[:20]}... -> {remaining:.0f}s")

    # Test stats
    print("\n4. Cooldown statistics:")
    stats = manager.get_cooldown_stats()
    print(f"   Total: {stats['total']}")
    print(f"   Active: {stats['active']}")
    print(f"   By session: {stats['by_session']}")

    # Wait and test expiration
    print("\n5. Testing expiration (waiting 35 seconds)...")
    print("   Setting 30s cooldown for rando...")
    manager.set_cooldown("rando", "test:quick", 2)  # 2 second cooldown

    print("   Waiting 3 seconds...")
    time.sleep(3)

    in_cooldown = manager.is_in_cooldown("rando", "test:quick")
    print(f"   rando test:quick (after 3s): {in_cooldown}")

    if not in_cooldown:
        print("   ✓ Cooldown expired correctly")

    print("\n✓ Cooldown Manager tests complete!")


if __name__ == "__main__":
    main()
