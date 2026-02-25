"""
Tests for Alembic-style Migration Manager

Tests for the enhanced database migration system with Alembic-like features.
"""
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from migrations.alembic_manager import (
    AlembicMigrationManager,
    MigrationResult,
    MigrationState,
    SchemaDiff,
    TableInfo,
    auto_migrate,
    run_migrations,
)


class TestMigrationManagerInit:
    """Test migration manager initialization."""

    def test_init_creates_manager(self, tmp_path):
        """Manager initializes with valid path."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))

        assert manager.db_path == db_path
        assert manager.migrations_dir == migrations_dir

    def test_init_creates_migration_tables(self, tmp_path):
        """Manager creates tracking tables on first access."""
        db_path = tmp_path / "test.db"
        # Create empty database
        sqlite3.connect(str(db_path)).close()

        manager = AlembicMigrationManager(str(db_path))
        manager.init_migration_tables()

        # Check tables exist
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('schema_versions', 'migration_history')
            """
            )
            tables = {row[0] for row in cursor.fetchall()}

        assert "schema_versions" in tables
        assert "migration_history" in tables


class TestSchemaIntrospection:
    """Test schema introspection features."""

    @pytest.fixture
    def db_with_schema(self, tmp_path):
        """Create a database with test schema."""
        db_path = tmp_path / "test.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE posts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    title TEXT NOT NULL,
                    content TEXT
                );

                CREATE INDEX idx_posts_user ON posts(user_id);
            """
            )
        return db_path

    def test_get_schema_info(self, db_with_schema):
        """get_schema_info returns table information."""
        manager = AlembicMigrationManager(str(db_with_schema))
        schema = manager.get_schema_info()

        assert "users" in schema
        assert "posts" in schema

        users = schema["users"]
        assert users.name == "users"
        assert len(users.columns) == 4
        assert any(c["name"] == "email" for c in users.columns)

    def test_get_schema_includes_indexes(self, db_with_schema):
        """Schema info includes index information."""
        manager = AlembicMigrationManager(str(db_with_schema))
        schema = manager.get_schema_info()

        posts = schema["posts"]
        index_names = [i["name"] for i in posts.indexes]
        assert "idx_posts_user" in index_names

    def test_export_schema(self, db_with_schema, tmp_path):
        """export_schema generates valid SQL."""
        manager = AlembicMigrationManager(str(db_with_schema))
        schema_sql = manager.export_schema()

        assert "CREATE TABLE users" in schema_sql
        assert "CREATE TABLE posts" in schema_sql
        assert "CREATE INDEX idx_posts_user" in schema_sql


class TestSchemaDiff:
    """Test schema comparison."""

    def test_diff_detects_new_table(self):
        """SchemaDiff detects added tables."""
        schema1 = {"users": TableInfo(name="users")}
        schema2 = {"users": TableInfo(name="users"), "posts": TableInfo(name="posts")}

        manager = AlembicMigrationManager(":memory:")
        diff = manager.compare_schemas(schema1, schema2)

        assert "posts" in diff.tables_added
        assert diff.has_changes()

    def test_diff_detects_removed_table(self):
        """SchemaDiff detects removed tables."""
        schema1 = {"users": TableInfo(name="users"), "posts": TableInfo(name="posts")}
        schema2 = {"users": TableInfo(name="users")}

        manager = AlembicMigrationManager(":memory:")
        diff = manager.compare_schemas(schema1, schema2)

        assert "posts" in diff.tables_removed

    def test_diff_detects_new_column(self):
        """SchemaDiff detects added columns."""
        schema1 = {
            "users": TableInfo(
                name="users", columns=[{"name": "id", "type": "INTEGER", "notnull": False}]
            )
        }
        schema2 = {
            "users": TableInfo(
                name="users",
                columns=[
                    {"name": "id", "type": "INTEGER", "notnull": False},
                    {"name": "email", "type": "TEXT", "notnull": False},
                ],
            )
        }

        manager = AlembicMigrationManager(":memory:")
        diff = manager.compare_schemas(schema1, schema2)

        assert "users" in diff.columns_added
        assert "email" in diff.columns_added["users"]

    def test_diff_to_sql_generates_statements(self):
        """SchemaDiff.to_sql generates migration SQL."""
        diff = SchemaDiff(tables_removed=["old_table"], columns_added={"users": ["email", "phone"]})

        sql = diff.to_sql()

        assert any("DROP TABLE" in s and "old_table" in s for s in sql)
        assert any("ALTER TABLE users ADD COLUMN email" in s for s in sql)


class TestMigrationExecution:
    """Test migration execution."""

    @pytest.fixture
    def migration_setup(self, tmp_path):
        """Set up test database and migrations directory."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create test database
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")

        return db_path, migrations_dir

    def test_apply_sql_migration(self, migration_setup):
        """SQL migrations are applied correctly."""
        db_path, migrations_dir = migration_setup

        # Create a SQL migration
        migration_file = migrations_dir / "001_add_users.sql"
        migration_file.write_text(
            """-- Add users table
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
"""
        )

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        result = manager.apply_migration("001", str(migration_file), "sql")

        assert result.success
        assert result.version == "001"

        # Verify table was created
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master WHERE type='table' AND name='users'
            """
            )
            assert cursor.fetchone() is not None

    def test_apply_python_migration(self, migration_setup):
        """Python migrations are applied correctly."""
        db_path, migrations_dir = migration_setup

        # Create a Python migration
        migration_file = migrations_dir / "002_add_posts.py"
        migration_file.write_text(
            """
DESCRIPTION = "Add posts table"

def upgrade(conn):
    conn.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT)")
    conn.commit()

def downgrade(conn):
    conn.execute("DROP TABLE posts")
    conn.commit()
"""
        )

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        result = manager.apply_migration("002", str(migration_file), "python")

        assert result.success

        # Verify table was created
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master WHERE type='table' AND name='posts'
            """
            )
            assert cursor.fetchone() is not None

    def test_dry_run_does_not_apply(self, migration_setup):
        """Dry run mode does not modify database."""
        db_path, migrations_dir = migration_setup

        migration_file = migrations_dir / "001_add_users.sql"
        migration_file.write_text("CREATE TABLE users (id INTEGER);")

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        result = manager.apply_migration("001", str(migration_file), "sql", dry_run=True)

        assert result.success

        # Verify table was NOT created
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master WHERE type='table' AND name='users'
            """
            )
            assert cursor.fetchone() is None

    def test_run_pending_migrations(self, migration_setup):
        """run_migrations applies all pending migrations."""
        db_path, migrations_dir = migration_setup

        # Create multiple migrations
        (migrations_dir / "001_users.sql").write_text("CREATE TABLE users (id INTEGER);")
        (migrations_dir / "002_posts.sql").write_text("CREATE TABLE posts (id INTEGER);")

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        result = manager.run_migrations(backup=False)

        assert len(result["applied"]) == 2
        assert not result["failed"]


class TestRollback:
    """Test migration rollback."""

    @pytest.fixture
    def rollback_setup(self, tmp_path):
        """Set up for rollback tests."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create Python migration with downgrade
        migration_file = migrations_dir / "001_add_users.py"
        migration_file.write_text(
            """
DESCRIPTION = "Add users table"

def upgrade(conn):
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    conn.commit()

def downgrade(conn):
    conn.execute("DROP TABLE users")
    conn.commit()
"""
        )

        sqlite3.connect(str(db_path)).close()
        return db_path, migrations_dir

    def test_rollback_python_migration(self, rollback_setup):
        """Python migrations can be rolled back."""
        db_path, migrations_dir = rollback_setup

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))

        # Apply migration first
        manager.run_migrations(backup=False)

        # Verify applied
        assert "001" in manager.get_applied_versions()

        # Rollback
        result = manager.rollback_migration()

        assert result.success
        assert result.rollback_performed
        assert "001" not in manager.get_applied_versions()

    def test_cannot_rollback_sql_migration(self, tmp_path):
        """SQL migrations cannot be rolled back."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_users.sql").write_text("CREATE TABLE users (id INTEGER);")
        sqlite3.connect(str(db_path)).close()

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        manager.run_migrations(backup=False)

        with pytest.raises(ValueError, match="Cannot rollback SQL migration"):
            manager.rollback_migration()


class TestStamp:
    """Test stamp functionality."""

    def test_stamp_marks_as_applied(self, tmp_path):
        """Stamp marks a migration as applied without executing."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_users.sql").write_text("CREATE TABLE users (id INTEGER);")
        sqlite3.connect(str(db_path)).close()

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))

        # Stamp without executing
        assert manager.stamp("001")
        assert "001" in manager.get_applied_versions()

        # Table should NOT exist
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master WHERE type='table' AND name='users'
            """
            )
            assert cursor.fetchone() is None

    def test_stamp_all(self, tmp_path):
        """stamp_all marks all pending migrations."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_users.sql").write_text("CREATE TABLE users (id INTEGER);")
        (migrations_dir / "002_posts.sql").write_text("CREATE TABLE posts (id INTEGER);")
        sqlite3.connect(str(db_path)).close()

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        stamped = manager.stamp_all()

        assert "001" in stamped
        assert "002" in stamped
        assert len(manager.get_pending_migrations()) == 0


class TestBackup:
    """Test backup functionality."""

    def test_backup_creates_copy(self, tmp_path):
        """Backup creates a copy of the database."""
        db_path = tmp_path / "test.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

        manager = AlembicMigrationManager(str(db_path))
        backup_path = manager.backup_database()

        assert Path(backup_path).exists()

        # Verify backup has same content
        with sqlite3.connect(backup_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM test").fetchone()[0]
            assert count == 1

    def test_list_backups(self, tmp_path):
        """list_backups returns available backups."""
        db_path = tmp_path / "test.db"
        sqlite3.connect(str(db_path)).close()

        manager = AlembicMigrationManager(str(db_path))

        # Create some backups
        manager.backup_database(suffix="test1")
        manager.backup_database(suffix="test2")

        backups = manager.list_backups()

        assert len(backups) >= 2
        assert all("path" in b and "name" in b for b in backups)


class TestMigrationHistory:
    """Test migration history/audit."""

    def test_history_records_migrations(self, tmp_path):
        """Migration history records applied migrations."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_users.sql").write_text("CREATE TABLE users (id INTEGER);")
        sqlite3.connect(str(db_path)).close()

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        manager.run_migrations(backup=False)

        history = manager.get_migration_history()

        assert len(history) >= 1
        assert history[0]["version"] == "001"
        assert history[0]["operation"] == "upgrade"
        assert history[0]["status"] == "success"


class TestGenerateMigration:
    """Test migration file generation."""

    def test_generate_sql_migration(self, tmp_path):
        """generate_migration creates SQL file."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        sqlite3.connect(str(db_path)).close()
        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))

        filepath = manager.generate_migration("add_users_table", "sql")

        assert Path(filepath).exists()
        assert filepath.endswith(".sql")
        content = Path(filepath).read_text()
        assert "Add Users Table" in content

    def test_generate_python_migration(self, tmp_path):
        """generate_migration creates Python file."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        sqlite3.connect(str(db_path)).close()
        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))

        filepath = manager.generate_migration("add_posts", "python")

        assert filepath.endswith(".py")
        content = Path(filepath).read_text()
        assert "def upgrade(conn):" in content
        assert "def downgrade(conn):" in content

    def test_version_numbers_increment(self, tmp_path):
        """Generated migrations have incrementing version numbers."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create existing migration
        (migrations_dir / "005_existing.sql").write_text("-- existing")

        sqlite3.connect(str(db_path)).close()
        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))

        filepath = manager.generate_migration("new_migration", "sql")

        assert "006_" in filepath


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_run_migrations_function(self, tmp_path):
        """run_migrations convenience function works."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_test.sql").write_text("CREATE TABLE test (id INTEGER);")
        sqlite3.connect(str(db_path)).close()

        result = run_migrations(str(db_path), str(migrations_dir), backup=False)

        assert "applied" in result
        assert len(result["applied"]) == 1

    def test_auto_migrate_function(self, tmp_path):
        """auto_migrate function works for startup."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_test.sql").write_text("CREATE TABLE test (id INTEGER);")
        sqlite3.connect(str(db_path)).close()

        result = auto_migrate(str(db_path), str(migrations_dir))

        assert result["status"] == "migrated"
        assert "001" in result["applied"]


class TestHooks:
    """Test migration hooks."""

    def test_pre_migrate_hook(self, tmp_path):
        """Pre-migrate hook is called."""
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_test.sql").write_text("CREATE TABLE test (id INTEGER);")
        sqlite3.connect(str(db_path)).close()

        hook_called = []

        def pre_hook(version, path):
            hook_called.append(version)

        manager = AlembicMigrationManager(str(db_path), str(migrations_dir))
        manager.register_hook("pre_migrate", pre_hook)
        manager.run_migrations(backup=False)

        assert "001" in hook_called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
