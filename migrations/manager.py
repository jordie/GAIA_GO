"""
Migration Manager - Handles database schema migrations with data preservation

Supports both Python (.py) and SQL (.sql) migration files:
- Python migrations must have upgrade(conn) and optionally downgrade(conn) functions
- SQL migrations are executed directly and cannot be rolled back automatically

Usage:
    python3 -m migrations.manager status          # Check migration status
    python3 -m migrations.manager migrate         # Run pending migrations
    python3 -m migrations.manager pending         # List pending migrations
    python3 -m migrations.manager generate NAME   # Generate new migration file
    python3 -m migrations.manager rollback        # Rollback last migration (Python only)
"""
import hashlib
import importlib
import importlib.util
import logging
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations with backup and rollback support."""

    def __init__(self, db_path: str, migrations_dir: Optional[str] = None):
        self.db_path = Path(db_path)
        self.migrations_dir = Path(migrations_dir) if migrations_dir else Path(__file__).parent
        self.backup_dir = self.db_path.parent / "backups"

    def init_schema_table(self):
        """Create the schema_versions table if it doesn't exist."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_versions (
                    id INTEGER PRIMARY KEY,
                    version TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    checksum TEXT
                )
            """
            )
            conn.commit()

    def get_applied_versions(self) -> List[str]:
        """Get list of already applied migration versions."""
        self.init_schema_table()
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT version FROM schema_versions ORDER BY version")
            return [row[0] for row in cursor.fetchall()]

    def get_available_migrations(self) -> List[Tuple[str, str, str]]:
        """Get list of available migration files (version, filepath, type).

        Returns:
            List of tuples: (version, filepath, migration_type)
            where migration_type is 'python' or 'sql'
        """
        migrations = []

        # Find Python migrations
        for f in self.migrations_dir.glob("[0-9][0-9][0-9]_*.py"):
            if f.name.startswith("__"):
                continue
            version = f.stem.split("_")[0]
            migrations.append((version, str(f), "python"))

        # Find SQL migrations
        for f in self.migrations_dir.glob("[0-9][0-9][0-9]_*.sql"):
            version = f.stem.split("_")[0]
            migrations.append((version, str(f), "sql"))

        # Sort by version number
        return sorted(migrations, key=lambda x: x[0])

    def get_pending_migrations(self) -> List[Tuple[str, str, str]]:
        """Get migrations that haven't been applied yet.

        Returns:
            List of tuples: (version, filepath, migration_type)
        """
        applied = set(self.get_applied_versions())
        return [(v, p, t) for v, p, t in self.get_available_migrations() if v not in applied]

    def backup_database(self) -> str:
        """Create a backup of the database before migration."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"architect_{timestamp}.db"
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        return str(backup_path)

    def apply_migration(
        self, version: str, migration_path: str, migration_type: str = "python"
    ) -> bool:
        """Apply a single migration.

        Args:
            version: Migration version string (e.g., '001')
            migration_path: Path to the migration file
            migration_type: 'python' or 'sql'

        Returns:
            True if migration was applied successfully
        """
        path = Path(migration_path)

        try:
            if migration_type == "sql":
                return self._apply_sql_migration(version, path)
            else:
                return self._apply_python_migration(version, path)

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            raise

    def _apply_sql_migration(self, version: str, path: Path) -> bool:
        """Apply a SQL migration file."""
        sql_content = path.read_text()

        # Extract description from first comment line if present
        description = f"SQL Migration {version}"
        first_line = sql_content.strip().split("\n")[0]
        if first_line.startswith("--"):
            description = first_line[2:].strip()

        # Calculate checksum for tracking
        checksum = hashlib.md5(sql_content.encode()).hexdigest()

        with sqlite3.connect(str(self.db_path)) as conn:
            # Execute the SQL script
            conn.executescript(sql_content)

            # Record the migration
            conn.execute(
                """
                INSERT INTO schema_versions (version, description, checksum)
                VALUES (?, ?, ?)
            """,
                (version, description, checksum),
            )
            conn.commit()

        logger.info(f"Applied SQL migration {version}: {description}")
        return True

    def _apply_python_migration(self, version: str, path: Path) -> bool:
        """Apply a Python migration file."""
        # Load the migration module
        spec = importlib.util.spec_from_file_location(f"migration_{version}", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get migration info
        description = getattr(module, "DESCRIPTION", f"Python Migration {version}")

        # Check if migration has required functions
        if not hasattr(module, "upgrade"):
            raise ValueError(f"Migration {version} missing 'upgrade' function")

        # Calculate checksum
        checksum = hashlib.md5(path.read_bytes()).hexdigest()

        # Apply the migration
        with sqlite3.connect(str(self.db_path)) as conn:
            module.upgrade(conn)

            # Record the migration
            conn.execute(
                """
                INSERT INTO schema_versions (version, description, checksum)
                VALUES (?, ?, ?)
            """,
                (version, description, checksum),
            )
            conn.commit()

        logger.info(f"Applied Python migration {version}: {description}")
        return True

    def rollback_last(self) -> Optional[str]:
        """Rollback the last applied migration (Python migrations only).

        Returns:
            Version string of rolled back migration, or None if no rollback possible
        """
        applied = self.get_applied_versions()
        if not applied:
            logger.info("No migrations to rollback")
            return None

        last_version = applied[-1]

        # Find the migration file
        for v, p, t in self.get_available_migrations():
            if v == last_version:
                if t == "sql":
                    raise ValueError(
                        f"Cannot rollback SQL migration {v}. Manual intervention required."
                    )

                # Load and run downgrade
                spec = importlib.util.spec_from_file_location(f"migration_{v}", p)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if not hasattr(module, "downgrade"):
                    raise ValueError(f"Migration {v} has no downgrade function")

                with sqlite3.connect(str(self.db_path)) as conn:
                    module.downgrade(conn)
                    conn.execute("DELETE FROM schema_versions WHERE version = ?", (v,))
                    conn.commit()

                logger.info(f"Rolled back migration {v}")
                return v

        return None

    def run_pending_migrations(self, backup: bool = True) -> List[str]:
        """Run all pending migrations.

        Args:
            backup: Whether to backup database before migrations

        Returns:
            List of applied migration versions
        """
        pending = self.get_pending_migrations()
        if not pending:
            logger.info("No pending migrations")
            return []

        # Backup before migrations
        if backup and self.db_path.exists():
            self.backup_database()

        applied = []
        for version, path, migration_type in pending:
            try:
                self.apply_migration(version, path, migration_type)
                applied.append(version)
            except Exception as e:
                logger.error(f"Migration {version} failed: {e}")
                logger.error("Stopping migration process. Database may need manual recovery.")
                raise

        return applied

    def get_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        applied = self.get_applied_versions()
        pending = self.get_pending_migrations()

        return {
            "database": str(self.db_path),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied_versions": applied,
            "pending_versions": [v for v, _, _ in pending],
            "pending_details": [{"version": v, "path": p, "type": t} for v, p, t in pending],
            "last_applied": applied[-1] if applied else None,
            "is_current": len(pending) == 0,
        }

    def generate_migration(self, name: str, migration_type: str = "sql") -> str:
        """Generate a new migration file.

        Args:
            name: Descriptive name for the migration (e.g., 'add_users_table')
            migration_type: 'sql' or 'python'

        Returns:
            Path to the created migration file
        """
        # Get the next version number
        available = self.get_available_migrations()
        if available:
            last_version = max(int(v) for v, _, _ in available)
            next_version = f"{last_version + 1:03d}"
        else:
            next_version = "001"

        # Sanitize name
        safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())
        safe_name = re.sub(r"_+", "_", safe_name).strip("_")

        timestamp = datetime.now().strftime("%Y%m%d")

        if migration_type == "sql":
            filename = f"{next_version}_{safe_name}.sql"
            content = f"""-- {name.replace('_', ' ').title()}
-- Created: {datetime.now().isoformat()}

-- Add your SQL statements here
-- Example:
-- ALTER TABLE my_table ADD COLUMN new_column TEXT;
-- CREATE INDEX idx_my_table_new_column ON my_table(new_column);
"""
        else:
            filename = f"{next_version}_{safe_name}.py"
            content = f'''"""
Migration: {name.replace('_', ' ').title()}
Created: {datetime.now().isoformat()}
"""

DESCRIPTION = "{name.replace('_', ' ').title()}"


def upgrade(conn):
    """Apply the migration."""
    # Add your migration SQL here
    conn.execute("""
        -- Your SQL statements
    """)
    conn.commit()


def downgrade(conn):
    """Rollback the migration."""
    # Add rollback SQL here
    conn.execute("""
        -- Your rollback SQL statements
    """)
    conn.commit()
'''

        filepath = self.migrations_dir / filename
        filepath.write_text(content)
        logger.info(f"Created migration: {filepath}")
        return str(filepath)


def run_migrations(db_path: str, migrations_dir: Optional[str] = None, backup: bool = True) -> dict:
    """Convenience function to run all pending migrations."""
    manager = MigrationManager(db_path, migrations_dir)

    status_before = manager.get_status()
    applied = manager.run_pending_migrations(backup=backup)
    status_after = manager.get_status()

    return {
        "applied": applied,
        "status": status_after,
        "backup_created": backup and len(applied) > 0,
    }


def auto_migrate(db_path: str, migrations_dir: Optional[str] = None) -> Dict[str, Any]:
    """Run migrations automatically on app startup.

    This function is safe to call on every app startup - it will only apply
    pending migrations and skip if database is already current.

    Args:
        db_path: Path to the database file
        migrations_dir: Optional path to migrations directory

    Returns:
        Dict with migration results
    """
    try:
        manager = MigrationManager(db_path, migrations_dir)
        pending = manager.get_pending_migrations()

        if not pending:
            return {"status": "current", "applied": []}

        # Run with backup
        applied = manager.run_pending_migrations(backup=True)
        return {"status": "migrated", "applied": applied, "count": len(applied)}
    except Exception as e:
        logger.error(f"Auto-migration failed: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Database Migration Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m migrations.manager status              # Check migration status
  python -m migrations.manager migrate             # Run pending migrations
  python -m migrations.manager pending             # List pending migrations
  python -m migrations.manager generate add_users  # Generate SQL migration
  python -m migrations.manager generate add_users --type python  # Generate Python migration
  python -m migrations.manager rollback            # Rollback last migration
        """,
    )
    parser.add_argument(
        "command",
        choices=["status", "migrate", "pending", "generate", "rollback"],
        help="Command to run",
    )
    parser.add_argument(
        "name", nargs="?", default=None, help="Migration name (for generate command)"
    )
    parser.add_argument("--db", default="data/architect.db", help="Database path")
    parser.add_argument(
        "--type",
        choices=["sql", "python"],
        default="sql",
        help="Migration type for generate command",
    )
    parser.add_argument("--no-backup", action="store_true", help="Skip database backup")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    manager = MigrationManager(args.db)

    if args.command == "status":
        status = manager.get_status()
        print(f"\nDatabase: {status['database']}")
        print(f"Applied:  {status['applied_count']} migrations")
        print(f"Pending:  {status['pending_count']} migrations")
        if status["pending_versions"]:
            print(f"\nPending migrations:")
            for detail in status["pending_details"]:
                print(f"  {detail['version']} ({detail['type']}): {Path(detail['path']).name}")
        print(f"\nDatabase is {'current' if status['is_current'] else 'OUT OF DATE'}")

    elif args.command == "pending":
        pending = manager.get_pending_migrations()
        if pending:
            print("\nPending migrations:")
            for v, p, t in pending:
                print(f"  {v} ({t}): {Path(p).name}")
        else:
            print("No pending migrations - database is current")

    elif args.command == "generate":
        if not args.name:
            print("Error: Migration name required for generate command")
            print("Usage: python -m migrations.manager generate <name>")
            sys.exit(1)
        filepath = manager.generate_migration(args.name, args.type)
        print(f"\nCreated migration: {filepath}")
        print(f"Edit the file to add your migration SQL/code")

    elif args.command == "rollback":
        try:
            version = manager.rollback_last()
            if version:
                print(f"Rolled back migration: {version}")
            else:
                print("No migrations to rollback")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "migrate":
        result = run_migrations(args.db, backup=not args.no_backup)
        if result["applied"]:
            print(f"\nApplied {len(result['applied'])} migrations:")
            for v in result["applied"]:
                print(f"  - {v}")
        else:
            print("No migrations to apply")
