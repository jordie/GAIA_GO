#!/usr/bin/env python3
"""
Run LLM Metrics Migration
Applies the 013_llm_metrics.sql migration to the database
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
MIGRATION_FILE = BASE_DIR / "migrations" / "013_llm_metrics.sql"
DB_FILE = BASE_DIR / "data" / "architect.db"


def run_migration():
    """Run the LLM metrics migration."""
    try:
        # Read migration SQL
        with open(MIGRATION_FILE, "r") as f:
            migration_sql = f.read()

        # Connect to database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Execute migration
        cursor.executescript(migration_sql)
        conn.commit()
        conn.close()

        print(f"✓ Migration applied successfully")
        print(f"  Database: {DB_FILE}")
        print(f"  Migration: {MIGRATION_FILE}")

        # Verify tables were created
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        tables = cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE 'llm_%'
            ORDER BY name
        """
        ).fetchall()

        print(f"\n✓ Created {len(tables)} tables:")
        for table in tables:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
            print(f"  - {table[0]} ({count} rows)")

        conn.close()

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False

    return True


if __name__ == "__main__":
    run_migration()
