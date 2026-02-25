#!/usr/bin/env python3
"""
TickTick Cache Database Initialization

Initializes the SQLite cache database with proper schema, indexes, and views.
Supports schema versioning and migrations.
"""

import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TickTickCacheDB:
    """Manages TickTick cache database initialization and migrations."""

    def __init__(self, db_path: str = "data/ticktick_cache.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrations_dir = Path(__file__).parent.parent / "migrations"

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with pragmas."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Performance pragmas
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
        conn.execute("PRAGMA foreign_keys = ON")

        return conn

    def get_current_version(self, conn: sqlite3.Connection) -> int:
        """Get current schema version."""
        try:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result[0] else 0
        except sqlite3.OperationalError:
            return 0

    def initialize(self) -> bool:
        """Initialize database schema from migration files."""
        try:
            conn = self.get_connection()
            current_version = self.get_current_version(conn)

            # Load and apply migrations
            migration_file = self.migrations_dir / "ticktick_001_initial_schema.sql"

            if not migration_file.exists():
                logger.error(f"Migration file not found: {migration_file}")
                return False

            logger.info(f"Applying migration: {migration_file}")

            with open(migration_file, "r") as f:
                sql = f.read()

            conn.executescript(sql)
            conn.commit()

            new_version = self.get_current_version(conn)
            logger.info(f"Schema version: {current_version} → {new_version}")

            # Verify tables exist
            self._verify_schema(conn)

            conn.close()
            logger.info(f"Database initialized: {self.db_path}")
            return True

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

    def _verify_schema(self, conn: sqlite3.Connection) -> bool:
        """Verify that all required tables exist."""
        required_tables = [
            "schema_version",
            "folders",
            "tasks",
            "tags",
            "sync_state",
        ]

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        missing_tables = set(required_tables) - existing_tables

        if missing_tables:
            logger.error(f"Missing tables: {missing_tables}")
            return False

        # Check for indexes
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        logger.info(f"Created {len(indexes)} indexes")

        # Check for views
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {row[0] for row in cursor.fetchall()}
        logger.info(f"Created {len(views)} views")

        # Get database size
        size_mb = self.db_path.stat().st_size / (1024 * 1024)
        logger.info(f"Database size: {size_mb:.2f} MB")

        return True

    def reset(self, confirm: bool = False) -> bool:
        """Reset database (delete and reinitialize)."""
        if not confirm:
            logger.warning("Reset requires confirmation. Use confirm=True")
            return False

        try:
            if self.db_path.exists():
                self.db_path.unlink()
                logger.info(f"Deleted {self.db_path}")

            return self.initialize()
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return False

    def get_stats(self) -> dict:
        """Get database statistics."""
        try:
            conn = self.get_connection()

            stats = {
                "path": str(self.db_path),
                "size_mb": self.db_path.stat().st_size / (1024 * 1024),
                "schema_version": self.get_current_version(conn),
                "folders_count": conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0],
                "tasks_count": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                "open_tasks": conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE status = 0"
                ).fetchone()[0],
                "completed_tasks": conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE status = 1"
                ).fetchone()[0],
                "tags_count": conn.execute("SELECT COUNT(DISTINCT tag) FROM tags").fetchone()[0],
            }

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TickTick Cache Database Manager")
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize database schema",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (delete and reinitialize)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics",
    )
    parser.add_argument(
        "--db-path",
        default="data/ticktick_cache.db",
        help="Database path",
    )

    args = parser.parse_args()

    db = TickTickCacheDB(args.db_path)

    if args.init:
        success = db.initialize()
        if success:
            print("✓ Database initialized successfully")
        else:
            print("✗ Database initialization failed")
            exit(1)

    elif args.reset:
        print("Warning: This will delete all cached data!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            success = db.reset(confirm=True)
            if success:
                print("✓ Database reset successfully")
            else:
                print("✗ Database reset failed")
                exit(1)
        else:
            print("Reset cancelled")

    elif args.stats:
        stats = db.get_stats()
        print("\nDatabase Statistics:")
        print("-" * 50)
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"{key:20s}: {value:>10.2f}")
            else:
                print(f"{key:20s}: {value:>10}")
        print("-" * 50)

    else:
        # Default: initialize if needed
        stats = db.get_stats()
        if stats.get("tasks_count", 0) == 0:
            print("Initializing empty database...")
            db.initialize()
        else:
            db.get_stats()


if __name__ == "__main__":
    main()
