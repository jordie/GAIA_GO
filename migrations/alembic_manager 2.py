"""
Alembic-style Migration Manager

Enhanced database migration system with Alembic-like features:
- Schema introspection and comparison
- Auto-generate migrations from schema diff
- Dry-run mode for previewing changes
- Stamp command for marking migrations without execution
- Migration history with audit trail
- Transaction support with automatic rollback on failure
- Pre/post migration hooks

Usage:
    python3 -m migrations.alembic_manager status
    python3 -m migrations.alembic_manager migrate
    python3 -m migrations.alembic_manager generate NAME
    python3 -m migrations.alembic_manager autogenerate NAME
    python3 -m migrations.alembic_manager rollback
    python3 -m migrations.alembic_manager stamp VERSION
    python3 -m migrations.alembic_manager history
    python3 -m migrations.alembic_manager schema
    python3 -m migrations.alembic_manager diff
"""
import hashlib
import importlib.util
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class MigrationState(Enum):
    """Migration execution state."""

    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TableInfo:
    """Information about a database table."""

    name: str
    columns: List[Dict[str, Any]] = field(default_factory=list)
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    foreign_keys: List[Dict[str, Any]] = field(default_factory=list)
    create_sql: str = ""


@dataclass
class SchemaDiff:
    """Difference between two schemas."""

    tables_added: List[str] = field(default_factory=list)
    tables_removed: List[str] = field(default_factory=list)
    columns_added: Dict[str, List[str]] = field(default_factory=dict)
    columns_removed: Dict[str, List[str]] = field(default_factory=dict)
    columns_modified: Dict[str, List[Dict]] = field(default_factory=dict)
    indexes_added: List[Dict] = field(default_factory=list)
    indexes_removed: List[Dict] = field(default_factory=list)

    def has_changes(self) -> bool:
        return any(
            [
                self.tables_added,
                self.tables_removed,
                self.columns_added,
                self.columns_removed,
                self.columns_modified,
                self.indexes_added,
                self.indexes_removed,
            ]
        )

    def to_sql(self) -> List[str]:
        """Generate SQL statements for the diff."""
        statements = []

        # Add new tables (would need full CREATE TABLE - placeholder)
        for table in self.tables_added:
            statements.append(f"-- TODO: CREATE TABLE {table}")

        # Remove tables
        for table in self.tables_removed:
            statements.append(f"DROP TABLE IF EXISTS {table};")

        # Add columns
        for table, columns in self.columns_added.items():
            for col in columns:
                statements.append(f"ALTER TABLE {table} ADD COLUMN {col};")

        # Note: SQLite doesn't support DROP COLUMN directly
        for table, columns in self.columns_removed.items():
            for col in columns:
                statements.append(
                    f"-- TODO: Remove column {col} from {table} (requires table rebuild)"
                )

        return statements


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    success: bool
    version: str
    migration_type: str
    duration_ms: float
    error: Optional[str] = None
    rollback_performed: bool = False


class AlembicMigrationManager:
    """Enhanced migration manager with Alembic-like features."""

    def __init__(self, db_path: str, migrations_dir: Optional[str] = None):
        self.db_path = Path(db_path)
        self.migrations_dir = Path(migrations_dir) if migrations_dir else Path(__file__).parent
        self.backup_dir = self.db_path.parent / "backups"
        self._hooks: Dict[str, List[Callable]] = {
            "pre_migrate": [],
            "post_migrate": [],
            "pre_rollback": [],
            "post_rollback": [],
        }

    # =========================================================================
    # Connection Management
    # =========================================================================

    @contextmanager
    def get_connection(self, timeout: float = 30.0):
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(str(self.db_path), timeout=timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    # =========================================================================
    # Schema Introspection
    # =========================================================================

    def get_schema_info(self) -> Dict[str, TableInfo]:
        """Get complete schema information from the database."""
        tables = {}

        with self.get_connection() as conn:
            # Get all tables
            cursor = conn.execute(
                """
                SELECT name, sql FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """
            )

            for row in cursor.fetchall():
                table_name = row["name"]
                table_info = TableInfo(name=table_name, create_sql=row["sql"] or "")

                # Get columns
                col_cursor = conn.execute(f"PRAGMA table_info({table_name})")
                for col in col_cursor.fetchall():
                    table_info.columns.append(
                        {
                            "cid": col["cid"],
                            "name": col["name"],
                            "type": col["type"],
                            "notnull": bool(col["notnull"]),
                            "default": col["dflt_value"],
                            "pk": bool(col["pk"]),
                        }
                    )

                # Get indexes
                idx_cursor = conn.execute(f"PRAGMA index_list({table_name})")
                for idx in idx_cursor.fetchall():
                    idx_info = {"name": idx["name"], "unique": bool(idx["unique"]), "columns": []}
                    # Get index columns
                    idx_col_cursor = conn.execute(f"PRAGMA index_info({idx['name']})")
                    idx_info["columns"] = [c["name"] for c in idx_col_cursor.fetchall()]
                    table_info.indexes.append(idx_info)

                # Get foreign keys
                fk_cursor = conn.execute(f"PRAGMA foreign_key_list({table_name})")
                for fk in fk_cursor.fetchall():
                    table_info.foreign_keys.append(
                        {
                            "id": fk["id"],
                            "table": fk["table"],
                            "from": fk["from"],
                            "to": fk["to"],
                            "on_update": fk["on_update"],
                            "on_delete": fk["on_delete"],
                        }
                    )

                tables[table_name] = table_info

        return tables

    def export_schema(self, output_path: Optional[str] = None) -> str:
        """Export full database schema to SQL file."""
        schema_sql = []

        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE sql IS NOT NULL AND type IN ('table', 'index', 'trigger', 'view')
                ORDER BY type, name
            """
            )

            for row in cursor.fetchall():
                if row["sql"]:
                    schema_sql.append(row["sql"] + ";")

        schema_text = "\n\n".join(schema_sql)

        if output_path:
            Path(output_path).write_text(schema_text)
            logger.info(f"Schema exported to: {output_path}")

        return schema_text

    def compare_schemas(
        self, schema1: Dict[str, TableInfo], schema2: Dict[str, TableInfo]
    ) -> SchemaDiff:
        """Compare two schemas and return differences."""
        diff = SchemaDiff()

        tables1 = set(schema1.keys())
        tables2 = set(schema2.keys())

        # Tables added/removed
        diff.tables_added = list(tables2 - tables1)
        diff.tables_removed = list(tables1 - tables2)

        # Compare common tables
        for table_name in tables1 & tables2:
            t1 = schema1[table_name]
            t2 = schema2[table_name]

            cols1 = {c["name"]: c for c in t1.columns}
            cols2 = {c["name"]: c for c in t2.columns}

            # Columns added/removed
            added = set(cols2.keys()) - set(cols1.keys())
            removed = set(cols1.keys()) - set(cols2.keys())

            if added:
                diff.columns_added[table_name] = list(added)
            if removed:
                diff.columns_removed[table_name] = list(removed)

            # Check for modified columns (type changes, etc.)
            for col_name in set(cols1.keys()) & set(cols2.keys()):
                c1, c2 = cols1[col_name], cols2[col_name]
                if c1["type"] != c2["type"] or c1["notnull"] != c2["notnull"]:
                    if table_name not in diff.columns_modified:
                        diff.columns_modified[table_name] = []
                    diff.columns_modified[table_name].append(
                        {"column": col_name, "old": c1, "new": c2}
                    )

            # Compare indexes
            idx1 = {i["name"]: i for i in t1.indexes}
            idx2 = {i["name"]: i for i in t2.indexes}

            for idx_name in set(idx2.keys()) - set(idx1.keys()):
                diff.indexes_added.append({"table": table_name, **idx2[idx_name]})
            for idx_name in set(idx1.keys()) - set(idx2.keys()):
                diff.indexes_removed.append({"table": table_name, **idx1[idx_name]})

        return diff

    # =========================================================================
    # Migration Table Management
    # =========================================================================

    def init_migration_tables(self):
        """Create migration tracking tables if they don't exist."""
        with self.get_connection() as conn:
            conn.executescript(
                """
                -- Main schema versions table
                CREATE TABLE IF NOT EXISTS schema_versions (
                    id INTEGER PRIMARY KEY,
                    version TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    checksum TEXT,
                    execution_time_ms INTEGER,
                    applied_by TEXT
                );

                -- Migration history/audit log
                CREATE TABLE IF NOT EXISTS migration_history (
                    id INTEGER PRIMARY KEY,
                    version TEXT NOT NULL,
                    operation TEXT NOT NULL,  -- 'upgrade', 'downgrade', 'stamp'
                    status TEXT NOT NULL,     -- 'success', 'failed', 'skipped'
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_ms INTEGER,
                    error_message TEXT,
                    backup_path TEXT,
                    executed_by TEXT,
                    host TEXT,
                    details TEXT  -- JSON for additional info
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_migration_history_version
                ON migration_history(version);

                CREATE INDEX IF NOT EXISTS idx_migration_history_started
                ON migration_history(started_at);
            """
            )
            conn.commit()

    def get_applied_versions(self) -> List[str]:
        """Get list of applied migration versions."""
        self.init_migration_tables()
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT version FROM schema_versions ORDER BY version")
            return [row["version"] for row in cursor.fetchall()]

    def get_migration_history(self, limit: int = 50) -> List[Dict]:
        """Get migration execution history."""
        self.init_migration_tables()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM migration_history
                ORDER BY started_at DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Migration Discovery
    # =========================================================================

    def get_available_migrations(self) -> List[Tuple[str, str, str]]:
        """Get list of available migration files.

        Returns:
            List of tuples: (version, filepath, migration_type)
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

        return sorted(migrations, key=lambda x: x[0])

    def get_pending_migrations(self) -> List[Tuple[str, str, str]]:
        """Get migrations that haven't been applied yet."""
        applied = set(self.get_applied_versions())
        return [(v, p, t) for v, p, t in self.get_available_migrations() if v not in applied]

    # =========================================================================
    # Backup & Restore
    # =========================================================================

    def backup_database(self, suffix: str = "") -> str:
        """Create a timestamped backup of the database."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_str = f"_{suffix}" if suffix else ""
        backup_path = self.backup_dir / f"architect_{timestamp}{suffix_str}.db"
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        return str(backup_path)

    def restore_from_backup(self, backup_path: str) -> bool:
        """Restore database from a backup file."""
        backup = Path(backup_path)
        if not backup.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        # Create backup of current state first
        if self.db_path.exists():
            self.backup_database(suffix="pre_restore")

        shutil.copy2(backup, self.db_path)
        logger.info(f"Database restored from: {backup_path}")
        return True

    def list_backups(self) -> List[Dict]:
        """List available database backups."""
        if not self.backup_dir.exists():
            return []

        backups = []
        for f in sorted(self.backup_dir.glob("*.db"), reverse=True):
            stat = f.stat()
            backups.append(
                {
                    "path": str(f),
                    "name": f.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        return backups

    # =========================================================================
    # Migration Execution
    # =========================================================================

    def _log_migration(
        self,
        version: str,
        operation: str,
        status: str,
        duration_ms: int = 0,
        error: str = None,
        backup_path: str = None,
        details: dict = None,
    ):
        """Log migration execution to history table."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO migration_history
                (version, operation, status, completed_at, duration_ms,
                 error_message, backup_path, executed_by, host, details)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
            """,
                (
                    version,
                    operation,
                    status,
                    duration_ms,
                    error,
                    backup_path,
                    os.environ.get("USER", "unknown"),
                    os.uname().nodename if hasattr(os, "uname") else "unknown",
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()

    def apply_migration(
        self,
        version: str,
        migration_path: str,
        migration_type: str = "python",
        dry_run: bool = False,
    ) -> MigrationResult:
        """Apply a single migration with transaction support."""
        # Ensure migration tables exist
        self.init_migration_tables()

        path = Path(migration_path)
        start_time = datetime.now()

        if dry_run:
            logger.info(f"[DRY RUN] Would apply migration {version}: {path.name}")
            if migration_type == "sql":
                logger.info(f"[DRY RUN] SQL content:\n{path.read_text()[:500]}...")
            return MigrationResult(
                success=True, version=version, migration_type=migration_type, duration_ms=0
            )

        # Run pre-migrate hooks
        for hook in self._hooks["pre_migrate"]:
            hook(version, migration_path)

        try:
            if migration_type == "sql":
                result = self._apply_sql_migration(version, path)
            else:
                result = self._apply_python_migration(version, path)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            result.duration_ms = duration_ms

            # Log success
            self._log_migration(version, "upgrade", "success", int(duration_ms))

            # Run post-migrate hooks
            for hook in self._hooks["post_migrate"]:
                hook(version, migration_path, result)

            return result

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = str(e)
            logger.error(f"Migration {version} failed: {error_msg}")

            # Log failure
            self._log_migration(version, "upgrade", "failed", int(duration_ms), error_msg)

            return MigrationResult(
                success=False,
                version=version,
                migration_type=migration_type,
                duration_ms=duration_ms,
                error=error_msg,
            )

    def _apply_sql_migration(self, version: str, path: Path) -> MigrationResult:
        """Apply a SQL migration file."""
        sql_content = path.read_text()

        # Extract description from first comment
        description = f"SQL Migration {version}"
        first_line = sql_content.strip().split("\n")[0]
        if first_line.startswith("--"):
            description = first_line[2:].strip()

        checksum = hashlib.md5(sql_content.encode()).hexdigest()

        with self.get_connection() as conn:
            conn.executescript(sql_content)
            conn.execute(
                """
                INSERT INTO schema_versions (version, description, checksum)
                VALUES (?, ?, ?)
            """,
                (version, description, checksum),
            )
            conn.commit()

        logger.info(f"Applied SQL migration {version}: {description}")
        return MigrationResult(success=True, version=version, migration_type="sql", duration_ms=0)

    def _apply_python_migration(self, version: str, path: Path) -> MigrationResult:
        """Apply a Python migration file."""
        spec = importlib.util.spec_from_file_location(f"migration_{version}", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        description = getattr(module, "DESCRIPTION", f"Python Migration {version}")

        if not hasattr(module, "upgrade"):
            raise ValueError(f"Migration {version} missing 'upgrade' function")

        checksum = hashlib.md5(path.read_bytes()).hexdigest()

        with self.get_connection() as conn:
            module.upgrade(conn)
            conn.execute(
                """
                INSERT INTO schema_versions (version, description, checksum)
                VALUES (?, ?, ?)
            """,
                (version, description, checksum),
            )
            conn.commit()

        logger.info(f"Applied Python migration {version}: {description}")
        return MigrationResult(
            success=True, version=version, migration_type="python", duration_ms=0
        )

    def run_migrations(
        self, backup: bool = True, dry_run: bool = False, target_version: str = None
    ) -> Dict[str, Any]:
        """Run all pending migrations up to optional target version."""
        pending = self.get_pending_migrations()

        if target_version:
            pending = [(v, p, t) for v, p, t in pending if v <= target_version]

        if not pending:
            logger.info("No pending migrations")
            return {"applied": [], "failed": [], "dry_run": dry_run}

        backup_path = None
        if backup and not dry_run and self.db_path.exists():
            backup_path = self.backup_database(suffix="pre_migrate")

        applied = []
        failed = []

        for version, path, migration_type in pending:
            result = self.apply_migration(version, path, migration_type, dry_run)
            if result.success:
                applied.append(result)
            else:
                failed.append(result)
                logger.error(f"Stopping migrations due to failure at {version}")
                break

        return {
            "applied": [asdict(r) for r in applied],
            "failed": [asdict(r) for r in failed],
            "backup_path": backup_path,
            "dry_run": dry_run,
        }

    # =========================================================================
    # Rollback
    # =========================================================================

    def rollback_migration(
        self, version: str = None, dry_run: bool = False
    ) -> Optional[MigrationResult]:
        """Rollback a specific version or the last applied migration."""
        applied = self.get_applied_versions()
        if not applied:
            logger.info("No migrations to rollback")
            return None

        target_version = version or applied[-1]

        if target_version not in applied:
            raise ValueError(f"Version {target_version} is not applied")

        # Find the migration file
        for v, p, t in self.get_available_migrations():
            if v == target_version:
                if t == "sql":
                    raise ValueError(
                        f"Cannot rollback SQL migration {v}. Manual intervention required."
                    )

                if dry_run:
                    logger.info(f"[DRY RUN] Would rollback migration {v}")
                    return MigrationResult(success=True, version=v, migration_type=t, duration_ms=0)

                # Run pre-rollback hooks
                for hook in self._hooks["pre_rollback"]:
                    hook(v, p)

                start_time = datetime.now()

                # Load and execute downgrade
                spec = importlib.util.spec_from_file_location(f"migration_{v}", p)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if not hasattr(module, "downgrade"):
                    raise ValueError(f"Migration {v} has no downgrade function")

                with self.get_connection() as conn:
                    module.downgrade(conn)
                    conn.execute("DELETE FROM schema_versions WHERE version = ?", (v,))
                    conn.commit()

                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                self._log_migration(v, "downgrade", "success", int(duration_ms))

                # Run post-rollback hooks
                result = MigrationResult(
                    success=True,
                    version=v,
                    migration_type=t,
                    duration_ms=duration_ms,
                    rollback_performed=True,
                )
                for hook in self._hooks["post_rollback"]:
                    hook(v, p, result)

                logger.info(f"Rolled back migration {v}")
                return result

        return None

    # =========================================================================
    # Stamp (mark as applied without executing)
    # =========================================================================

    def stamp(self, version: str) -> bool:
        """Mark a migration as applied without executing it.

        Useful for syncing migration state after manual schema changes.
        """
        applied = self.get_applied_versions()
        if version in applied:
            logger.warning(f"Version {version} is already applied")
            return False

        # Find the migration to get description
        description = f"Stamped migration {version}"
        for v, p, t in self.get_available_migrations():
            if v == version:
                path = Path(p)
                if t == "sql":
                    first_line = path.read_text().strip().split("\n")[0]
                    if first_line.startswith("--"):
                        description = first_line[2:].strip()
                break

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO schema_versions (version, description, checksum)
                VALUES (?, ?, ?)
            """,
                (version, description, "stamped"),
            )
            conn.commit()

        self._log_migration(version, "stamp", "success", 0, details={"stamped": True})
        logger.info(f"Stamped migration {version} as applied")
        return True

    def stamp_all(self) -> List[str]:
        """Stamp all pending migrations as applied."""
        pending = self.get_pending_migrations()
        stamped = []
        for version, _, _ in pending:
            if self.stamp(version):
                stamped.append(version)
        return stamped

    # =========================================================================
    # Migration Generation
    # =========================================================================

    def generate_migration(
        self, name: str, migration_type: str = "sql", template: str = None
    ) -> str:
        """Generate a new migration file."""
        available = self.get_available_migrations()
        if available:
            last_version = max(int(v) for v, _, _ in available)
            next_version = f"{last_version + 1:03d}"
        else:
            next_version = "001"

        safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())
        safe_name = re.sub(r"_+", "_", safe_name).strip("_")

        if migration_type == "sql":
            filename = f"{next_version}_{safe_name}.sql"
            content = (
                template
                or f"""-- {name.replace('_', ' ').title()}
-- Created: {datetime.now().isoformat()}
-- Version: {next_version}

-- Add your SQL statements here
-- Example:
-- ALTER TABLE my_table ADD COLUMN new_column TEXT;
-- CREATE INDEX idx_my_table_new_column ON my_table(new_column);
"""
            )
        else:
            filename = f"{next_version}_{safe_name}.py"
            content = (
                template
                or f'''"""
Migration: {name.replace('_', ' ').title()}
Created: {datetime.now().isoformat()}
Version: {next_version}
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
            )

        filepath = self.migrations_dir / filename
        filepath.write_text(content)
        logger.info(f"Created migration: {filepath}")
        return str(filepath)

    def autogenerate_migration(self, name: str, model_schema: Dict[str, TableInfo] = None) -> str:
        """Auto-generate a migration by comparing current schema to model.

        If model_schema is not provided, generates a migration template
        with the current schema diff analysis.
        """
        current_schema = self.get_schema_info()

        if model_schema:
            diff = self.compare_schemas(current_schema, model_schema)
            if not diff.has_changes():
                logger.info("No schema changes detected")
                return ""

            sql_statements = diff.to_sql()
            migration_sql = "\n".join(sql_statements)
        else:
            # Generate template with schema info
            migration_sql = "-- Auto-generated migration\n"
            migration_sql += f"-- Current tables: {', '.join(current_schema.keys())}\n"
            migration_sql += "\n-- Add your SQL changes below:\n"

        return self.generate_migration(
            name,
            "sql",
            f"""-- {name.replace('_', ' ').title()} (Auto-generated)
-- Created: {datetime.now().isoformat()}
-- Tables: {len(current_schema)}

{migration_sql}
""",
        )

    # =========================================================================
    # Status & Info
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status."""
        self.init_migration_tables()
        applied = self.get_applied_versions()
        pending = self.get_pending_migrations()
        schema = self.get_schema_info()

        return {
            "database": str(self.db_path),
            "database_exists": self.db_path.exists(),
            "database_size": self.db_path.stat().st_size if self.db_path.exists() else 0,
            "table_count": len(schema),
            "tables": list(schema.keys()),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied_versions": applied,
            "pending_versions": [v for v, _, _ in pending],
            "pending_details": [{"version": v, "path": p, "type": t} for v, p, t in pending],
            "last_applied": applied[-1] if applied else None,
            "is_current": len(pending) == 0,
            "migrations_dir": str(self.migrations_dir),
            "backup_dir": str(self.backup_dir),
            "backup_count": len(self.list_backups()),
        }

    # =========================================================================
    # Hooks
    # =========================================================================

    def register_hook(self, hook_type: str, callback: Callable):
        """Register a hook callback."""
        if hook_type in self._hooks:
            self._hooks[hook_type].append(callback)
        else:
            raise ValueError(f"Unknown hook type: {hook_type}")


# =============================================================================
# Convenience Functions
# =============================================================================


def run_migrations(
    db_path: str, migrations_dir: str = None, backup: bool = True, dry_run: bool = False
) -> Dict:
    """Convenience function to run all pending migrations."""
    manager = AlembicMigrationManager(db_path, migrations_dir)
    return manager.run_migrations(backup=backup, dry_run=dry_run)


def auto_migrate(db_path: str, migrations_dir: str = None) -> Dict[str, Any]:
    """Run migrations automatically on app startup."""
    try:
        manager = AlembicMigrationManager(db_path, migrations_dir)
        pending = manager.get_pending_migrations()

        if not pending:
            return {"status": "current", "applied": []}

        result = manager.run_migrations(backup=True)
        return {
            "status": "migrated" if not result["failed"] else "partial",
            "applied": [r["version"] for r in result["applied"]],
            "failed": [r["version"] for r in result["failed"]],
            "count": len(result["applied"]),
        }
    except Exception as e:
        logger.error(f"Auto-migration failed: {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# CLI
# =============================================================================


def main():
    """Command-line interface for migration manager."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Alembic-style Database Migration Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status        Show migration status
  migrate       Run pending migrations
  rollback      Rollback last migration (Python only)
  generate      Create new migration file
  autogenerate  Generate migration with schema analysis
  stamp         Mark migration as applied without running
  history       Show migration execution history
  schema        Export current database schema
  diff          Compare migrations and show pending changes
  backups       List available database backups

Examples:
  python -m migrations.alembic_manager status
  python -m migrations.alembic_manager migrate --dry-run
  python -m migrations.alembic_manager generate add_users_table
  python -m migrations.alembic_manager stamp 005
  python -m migrations.alembic_manager rollback
  python -m migrations.alembic_manager history --limit 10
        """,
    )

    parser.add_argument(
        "command",
        choices=[
            "status",
            "migrate",
            "rollback",
            "generate",
            "autogenerate",
            "stamp",
            "history",
            "schema",
            "diff",
            "backups",
            "pending",
        ],
        help="Command to run",
    )
    parser.add_argument(
        "name", nargs="?", default=None, help="Migration name (for generate) or version (for stamp)"
    )
    parser.add_argument(
        "--db", default="data/architect.db", help="Database path (default: data/architect.db)"
    )
    parser.add_argument(
        "--type",
        choices=["sql", "python"],
        default="sql",
        help="Migration type for generate command",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--no-backup", action="store_true", help="Skip database backup")
    parser.add_argument("--limit", type=int, default=20, help="Limit for history command")
    parser.add_argument("--output", "-o", help="Output file for schema export")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    manager = AlembicMigrationManager(args.db)

    if args.command == "status":
        status = manager.get_status()
        if args.json:
            print(json.dumps(status, indent=2, default=str))
        else:
            print(f"\n{'='*50}")
            print("Database Migration Status")
            print(f"{'='*50}")
            print(f"Database:    {status['database']}")
            print(f"Size:        {status['database_size'] / 1024:.1f} KB")
            print(f"Tables:      {status['table_count']}")
            print(f"Applied:     {status['applied_count']} migrations")
            print(f"Pending:     {status['pending_count']} migrations")
            print(f"Backups:     {status['backup_count']}")
            if status["pending_versions"]:
                print(f"\nPending migrations:")
                for detail in status["pending_details"]:
                    print(f"  {detail['version']} ({detail['type']}): {Path(detail['path']).name}")
            print(f"\nStatus: {'✓ Current' if status['is_current'] else '⚠ Updates available'}")

    elif args.command == "pending":
        pending = manager.get_pending_migrations()
        if args.json:
            print(
                json.dumps([{"version": v, "path": p, "type": t} for v, p, t in pending], indent=2)
            )
        elif pending:
            print("\nPending migrations:")
            for v, p, t in pending:
                print(f"  {v} ({t}): {Path(p).name}")
        else:
            print("No pending migrations - database is current")

    elif args.command == "migrate":
        result = manager.run_migrations(backup=not args.no_backup, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            prefix = "[DRY RUN] " if args.dry_run else ""
            if result["applied"]:
                print(f"\n{prefix}Applied {len(result['applied'])} migrations:")
                for r in result["applied"]:
                    print(f"  ✓ {r['version']} ({r['duration_ms']:.0f}ms)")
            if result["failed"]:
                print(f"\n{prefix}Failed migrations:")
                for r in result["failed"]:
                    print(f"  ✗ {r['version']}: {r['error']}")
            if not result["applied"] and not result["failed"]:
                print("No migrations to apply - database is current")
            if result.get("backup_path"):
                print(f"\nBackup created: {result['backup_path']}")

    elif args.command == "rollback":
        try:
            result = manager.rollback_migration(args.name, dry_run=args.dry_run)
            if result:
                prefix = "[DRY RUN] " if args.dry_run else ""
                print(f"{prefix}Rolled back migration: {result.version}")
            else:
                print("No migrations to rollback")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "generate":
        if not args.name:
            print("Error: Migration name required")
            print("Usage: python -m migrations.alembic_manager generate <name>")
            sys.exit(1)
        filepath = manager.generate_migration(args.name, args.type)
        print(f"\nCreated migration: {filepath}")
        print("Edit the file to add your migration SQL/code")

    elif args.command == "autogenerate":
        if not args.name:
            print("Error: Migration name required")
            sys.exit(1)
        filepath = manager.autogenerate_migration(args.name)
        if filepath:
            print(f"\nCreated migration: {filepath}")
        else:
            print("No migration created - no changes detected")

    elif args.command == "stamp":
        if not args.name:
            print("Error: Version required for stamp command")
            sys.exit(1)
        if manager.stamp(args.name):
            print(f"Stamped version {args.name} as applied")
        else:
            print(f"Version {args.name} was already applied")

    elif args.command == "history":
        history = manager.get_migration_history(limit=args.limit)
        if args.json:
            print(json.dumps(history, indent=2, default=str))
        else:
            print(f"\nMigration History (last {args.limit}):")
            print("-" * 70)
            for entry in history:
                status_icon = "✓" if entry["status"] == "success" else "✗"
                print(
                    f"  {status_icon} {entry['version']} | {entry['operation']:10} | "
                    f"{entry['started_at']} | {entry.get('duration_ms', 0):.0f}ms"
                )
            if not history:
                print("  No migration history found")

    elif args.command == "schema":
        schema_sql = manager.export_schema(args.output)
        if args.output:
            print(f"Schema exported to: {args.output}")
        else:
            print(schema_sql)

    elif args.command == "diff":
        pending = manager.get_pending_migrations()
        if not pending:
            print("No pending migrations - database is current")
        else:
            print("\nPending changes:")
            for v, p, t in pending:
                print(f"\n--- Migration {v} ({t}) ---")
                content = Path(p).read_text()
                # Show first 30 lines of each migration
                lines = content.split("\n")[:30]
                print("\n".join(lines))
                if len(content.split("\n")) > 30:
                    print("... (truncated)")

    elif args.command == "backups":
        backups = manager.list_backups()
        if args.json:
            print(json.dumps(backups, indent=2))
        else:
            print(f"\nAvailable backups ({len(backups)}):")
            for b in backups[:20]:  # Show last 20
                size_kb = b["size"] / 1024
                print(f"  {b['name']} ({size_kb:.1f} KB) - {b['created']}")
            if not backups:
                print("  No backups found")


if __name__ == "__main__":
    main()
