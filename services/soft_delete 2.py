"""
Soft delete service for all entities.

Provides consistent soft delete functionality across the application.
Instead of permanently deleting records, marks them with a deleted_at timestamp.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Tables that support soft delete
SOFT_DELETE_TABLES = [
    "projects",
    "milestones",
    "features",
    "bugs",
    "devops_tasks",
    "nodes",
    "errors",
    "task_queue",
    "workers",
]


def soft_delete(
    conn: sqlite3.Connection, table: str, record_id: int, deleted_by: Optional[str] = None
) -> bool:
    """
    Soft delete a record by setting deleted_at timestamp.

    Args:
        conn: Database connection
        table: Table name
        record_id: ID of record to delete
        deleted_by: Optional user who performed the delete

    Returns:
        True if record was deleted, False if not found
    """
    if table not in SOFT_DELETE_TABLES:
        raise ValueError(f"Table '{table}' does not support soft delete")

    # Build update query
    if deleted_by:
        result = conn.execute(
            f"""
            UPDATE {table}
            SET deleted_at = CURRENT_TIMESTAMP,
                deleted_by = ?
            WHERE id = ? AND deleted_at IS NULL
        """,
            (deleted_by, record_id),
        )
    else:
        result = conn.execute(
            f"""
            UPDATE {table}
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """,
            (record_id,),
        )

    conn.commit()
    return result.rowcount > 0


def soft_delete_many(
    conn: sqlite3.Connection, table: str, record_ids: List[int], deleted_by: Optional[str] = None
) -> int:
    """
    Soft delete multiple records.

    Args:
        conn: Database connection
        table: Table name
        record_ids: List of IDs to delete
        deleted_by: Optional user who performed the delete

    Returns:
        Number of records deleted
    """
    if table not in SOFT_DELETE_TABLES:
        raise ValueError(f"Table '{table}' does not support soft delete")

    if not record_ids:
        return 0

    placeholders = ",".join("?" * len(record_ids))

    if deleted_by:
        result = conn.execute(
            f"""
            UPDATE {table}
            SET deleted_at = CURRENT_TIMESTAMP,
                deleted_by = ?
            WHERE id IN ({placeholders}) AND deleted_at IS NULL
        """,
            [deleted_by] + list(record_ids),
        )
    else:
        result = conn.execute(
            f"""
            UPDATE {table}
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders}) AND deleted_at IS NULL
        """,
            list(record_ids),
        )

    conn.commit()
    return result.rowcount


def restore(conn: sqlite3.Connection, table: str, record_id: int) -> bool:
    """
    Restore a soft-deleted record.

    Args:
        conn: Database connection
        table: Table name
        record_id: ID of record to restore

    Returns:
        True if record was restored, False if not found or not deleted
    """
    if table not in SOFT_DELETE_TABLES:
        raise ValueError(f"Table '{table}' does not support soft delete")

    result = conn.execute(
        f"""
        UPDATE {table}
        SET deleted_at = NULL,
            deleted_by = NULL
        WHERE id = ? AND deleted_at IS NOT NULL
    """,
        (record_id,),
    )

    conn.commit()
    return result.rowcount > 0


def restore_many(conn: sqlite3.Connection, table: str, record_ids: List[int]) -> int:
    """
    Restore multiple soft-deleted records.

    Args:
        conn: Database connection
        table: Table name
        record_ids: List of IDs to restore

    Returns:
        Number of records restored
    """
    if table not in SOFT_DELETE_TABLES:
        raise ValueError(f"Table '{table}' does not support soft delete")

    if not record_ids:
        return 0

    placeholders = ",".join("?" * len(record_ids))
    result = conn.execute(
        f"""
        UPDATE {table}
        SET deleted_at = NULL,
            deleted_by = NULL
        WHERE id IN ({placeholders}) AND deleted_at IS NOT NULL
    """,
        list(record_ids),
    )

    conn.commit()
    return result.rowcount


def hard_delete(conn: sqlite3.Connection, table: str, record_id: int) -> bool:
    """
    Permanently delete a record.

    Args:
        conn: Database connection
        table: Table name
        record_id: ID of record to permanently delete

    Returns:
        True if record was deleted, False if not found
    """
    result = conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
    conn.commit()
    return result.rowcount > 0


def purge_deleted(conn: sqlite3.Connection, table: str, older_than_days: int = 30) -> int:
    """
    Permanently delete records that have been soft-deleted for a period.

    Args:
        conn: Database connection
        table: Table name
        older_than_days: Delete records soft-deleted more than this many days ago

    Returns:
        Number of records permanently deleted
    """
    if table not in SOFT_DELETE_TABLES:
        raise ValueError(f"Table '{table}' does not support soft delete")

    result = conn.execute(
        f"""
        DELETE FROM {table}
        WHERE deleted_at IS NOT NULL
          AND deleted_at < datetime('now', '-{older_than_days} days')
    """
    )

    conn.commit()
    return result.rowcount


def get_deleted(
    conn: sqlite3.Connection, table: str, limit: int = 100, offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Get soft-deleted records from a table.

    Args:
        conn: Database connection
        table: Table name
        limit: Maximum records to return
        offset: Offset for pagination

    Returns:
        List of deleted records
    """
    if table not in SOFT_DELETE_TABLES:
        raise ValueError(f"Table '{table}' does not support soft delete")

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT * FROM {table}
        WHERE deleted_at IS NOT NULL
        ORDER BY deleted_at DESC
        LIMIT ? OFFSET ?
    """,
        (limit, offset),
    ).fetchall()

    return [dict(row) for row in rows]


def count_deleted(conn: sqlite3.Connection, table: str) -> int:
    """
    Count soft-deleted records in a table.

    Args:
        conn: Database connection
        table: Table name

    Returns:
        Count of deleted records
    """
    if table not in SOFT_DELETE_TABLES:
        raise ValueError(f"Table '{table}' does not support soft delete")

    result = conn.execute(
        f"""
        SELECT COUNT(*) FROM {table} WHERE deleted_at IS NOT NULL
    """
    ).fetchone()

    return result[0]


def get_deletion_stats(conn: sqlite3.Connection) -> Dict[str, Dict[str, int]]:
    """
    Get deletion statistics for all soft-delete enabled tables.

    Returns:
        Dict with table names as keys, containing counts of active/deleted records
    """
    stats = {}

    for table in SOFT_DELETE_TABLES:
        try:
            result = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END) as deleted
                FROM {table}
            """
            ).fetchone()

            stats[table] = {
                "total": result[0] or 0,
                "active": result[1] or 0,
                "deleted": result[2] or 0,
            }
        except sqlite3.OperationalError:
            # Table doesn't exist or doesn't have deleted_at column
            stats[table] = {"error": "Table not available or missing deleted_at column"}

    return stats


def build_active_filter(table_alias: str = "") -> str:
    """
    Build a SQL WHERE clause fragment to filter out deleted records.

    Args:
        table_alias: Optional table alias (e.g., 'p' for 'p.deleted_at')

    Returns:
        SQL fragment like 'deleted_at IS NULL' or 'p.deleted_at IS NULL'
    """
    prefix = f"{table_alias}." if table_alias else ""
    return f"{prefix}deleted_at IS NULL"


def add_soft_delete_columns(conn: sqlite3.Connection, table: str) -> bool:
    """
    Add soft delete columns to an existing table.

    Args:
        conn: Database connection
        table: Table name

    Returns:
        True if columns were added, False if they already exist
    """
    added = False

    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMP")
        added = True
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN deleted_by TEXT")
        added = True
    except sqlite3.OperationalError:
        pass  # Column already exists

    if added:
        # Create index for faster queries on non-deleted records
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_deleted ON {table}(deleted_at)")
        except sqlite3.OperationalError:
            pass

        conn.commit()

    return added


def cascade_soft_delete(
    conn: sqlite3.Connection,
    parent_table: str,
    parent_id: int,
    child_tables: List[Tuple[str, str]],
    deleted_by: Optional[str] = None,
) -> Dict[str, int]:
    """
    Soft delete a parent record and cascade to child records.

    Args:
        conn: Database connection
        parent_table: Parent table name
        parent_id: Parent record ID
        child_tables: List of (child_table, foreign_key_column) tuples
        deleted_by: Optional user who performed the delete

    Returns:
        Dict with table names and count of deleted records
    """
    result = {parent_table: 0}

    # Delete parent
    if soft_delete(conn, parent_table, parent_id, deleted_by):
        result[parent_table] = 1

    # Cascade to children
    for child_table, fk_column in child_tables:
        if child_table in SOFT_DELETE_TABLES:
            if deleted_by:
                count = conn.execute(
                    f"""
                    UPDATE {child_table}
                    SET deleted_at = CURRENT_TIMESTAMP,
                        deleted_by = ?
                    WHERE {fk_column} = ? AND deleted_at IS NULL
                """,
                    (deleted_by, parent_id),
                ).rowcount
            else:
                count = conn.execute(
                    f"""
                    UPDATE {child_table}
                    SET deleted_at = CURRENT_TIMESTAMP
                    WHERE {fk_column} = ? AND deleted_at IS NULL
                """,
                    (parent_id,),
                ).rowcount

            result[child_table] = count

    conn.commit()
    return result


# Export commonly used functions
__all__ = [
    "SOFT_DELETE_TABLES",
    "soft_delete",
    "soft_delete_many",
    "restore",
    "restore_many",
    "hard_delete",
    "purge_deleted",
    "get_deleted",
    "count_deleted",
    "get_deletion_stats",
    "build_active_filter",
    "add_soft_delete_columns",
    "cascade_soft_delete",
]
