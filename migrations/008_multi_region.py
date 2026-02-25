#!/usr/bin/env python3
"""
Migration 008: Multi-Region Deployment Support

Adds support for multi-region deployments:
- regions table for region metadata
- region field on nodes table
- region-based metrics and health tracking
- cross-region replication configuration
"""

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_db_path():
    """Get the database path based on environment."""
    data_dir = Path(__file__).parent.parent / "data"
    env = os.environ.get("ARCHITECT_ENV", "default")

    if env != "default":
        env_db = data_dir / env / "architect.db"
        if env_db.exists():
            return env_db

    return data_dir / "architect.db"


def upgrade(conn=None):
    """Run the migration (upgrade function expected by migration manager)."""
    close_conn = False
    if conn is None:
        db_path = get_db_path()
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        close_conn = True

    cursor = conn.cursor()

    try:
        # Create regions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS regions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                description TEXT,
                provider TEXT DEFAULT 'on-premise',
                location TEXT,
                latitude REAL,
                longitude REAL,
                timezone TEXT,
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'maintenance', 'draining')),
                is_primary INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 100,
                max_nodes INTEGER DEFAULT 100,
                current_nodes INTEGER DEFAULT 0,
                replication_targets TEXT DEFAULT '[]',
                config TEXT DEFAULT '{}',
                health_status TEXT DEFAULT 'unknown' CHECK(health_status IN ('unknown', 'healthy', 'warning', 'critical', 'offline')),
                last_health_check TIMESTAMP,
                avg_latency_ms REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                deleted_at TIMESTAMP,
                deleted_by TEXT
            )
        """
        )

        # Create region_metrics table for historical tracking
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS region_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                node_count INTEGER DEFAULT 0,
                online_nodes INTEGER DEFAULT 0,
                total_cpu_usage REAL DEFAULT 0,
                total_memory_usage REAL DEFAULT 0,
                total_disk_usage REAL DEFAULT 0,
                avg_latency_ms REAL,
                request_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                FOREIGN KEY (region_id) REFERENCES regions(id)
            )
        """
        )

        # Create region_connections table for cross-region connectivity
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS region_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_region TEXT NOT NULL,
                target_region TEXT NOT NULL,
                latency_ms REAL,
                bandwidth_mbps REAL,
                status TEXT DEFAULT 'unknown' CHECK(status IN ('unknown', 'connected', 'degraded', 'disconnected')),
                last_checked TIMESTAMP,
                config TEXT DEFAULT '{}',
                UNIQUE(source_region, target_region),
                FOREIGN KEY (source_region) REFERENCES regions(id),
                FOREIGN KEY (target_region) REFERENCES regions(id)
            )
        """
        )

        # Add region column to nodes table if not exists
        cursor.execute("PRAGMA table_info(nodes)")
        columns = [col[1] for col in cursor.fetchall()]

        if "region_id" not in columns:
            cursor.execute("ALTER TABLE nodes ADD COLUMN region_id TEXT REFERENCES regions(id)")

        if "datacenter" not in columns:
            cursor.execute("ALTER TABLE nodes ADD COLUMN datacenter TEXT")

        if "availability_zone" not in columns:
            cursor.execute("ALTER TABLE nodes ADD COLUMN availability_zone TEXT")

        # Add region to errors table if not exists
        cursor.execute("PRAGMA table_info(errors)")
        error_columns = [col[1] for col in cursor.fetchall()]

        if "region_id" not in error_columns:
            cursor.execute("ALTER TABLE errors ADD COLUMN region_id TEXT")

        # Add region to task_queue table if not exists
        cursor.execute("PRAGMA table_info(task_queue)")
        task_columns = [col[1] for col in cursor.fetchall()]

        if "region_id" not in task_columns:
            cursor.execute("ALTER TABLE task_queue ADD COLUMN region_id TEXT")

        if "region_affinity" not in task_columns:
            cursor.execute("ALTER TABLE task_queue ADD COLUMN region_affinity TEXT")

        # Create indexes for efficient queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_regions_status ON regions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_regions_code ON regions(code)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_region_metrics_region ON region_metrics(region_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_region_metrics_timestamp ON region_metrics(timestamp)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_region ON nodes(region_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_region ON errors(region_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_region ON task_queue(region_id)")

        # Insert default region if no regions exist
        cursor.execute("SELECT COUNT(*) FROM regions")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                INSERT INTO regions (id, name, code, description, provider, is_primary, priority, status, health_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "default",
                    "Default Region",
                    "default",
                    "Default local region for single-region deployments",
                    "on-premise",
                    1,
                    1,
                    "active",
                    "healthy",
                ),
            )

        conn.commit()
        print("Migration 008: Multi-region support added successfully")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Migration 008 failed: {e}")
        raise
    finally:
        if close_conn:
            conn.close()


def downgrade(conn=None):
    """Rollback the migration."""
    close_conn = False
    if conn is None:
        db_path = get_db_path()
        conn = sqlite3.connect(str(db_path), timeout=30)
        close_conn = True

    cursor = conn.cursor()

    try:
        # Note: SQLite doesn't support DROP COLUMN, so we can only drop tables
        cursor.execute("DROP TABLE IF EXISTS region_connections")
        cursor.execute("DROP TABLE IF EXISTS region_metrics")
        cursor.execute("DROP TABLE IF EXISTS regions")

        conn.commit()
        print("Migration 008: Rollback completed")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Migration 008 rollback failed: {e}")
        raise
    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-region migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")
    args = parser.parse_args()

    if args.rollback:
        downgrade()
    else:
        upgrade()
