"""
Migration 003: Add Task Risk Assessment

This migration adds risk assessment fields to tasks:
- risk_level: Overall risk classification (low, medium, high, critical)
- risk_score: Numeric risk score (0-100)
- risk_factors: JSON array of identified risk factors
- risk_assessed_at: Timestamp of last risk assessment
"""

DESCRIPTION = "Add task risk assessment indicators"


def upgrade(conn):
    """Apply the migration."""

    # Add risk assessment columns to task_queue
    # Using ALTER TABLE with IF NOT EXISTS pattern for SQLite compatibility

    # Check existing columns
    cursor = conn.execute("PRAGMA table_info(task_queue)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "risk_level" not in existing_columns:
        conn.execute(
            """
            ALTER TABLE task_queue ADD COLUMN risk_level TEXT DEFAULT 'low'
        """
        )

    if "risk_score" not in existing_columns:
        conn.execute(
            """
            ALTER TABLE task_queue ADD COLUMN risk_score INTEGER DEFAULT 0
        """
        )

    if "risk_factors" not in existing_columns:
        conn.execute(
            """
            ALTER TABLE task_queue ADD COLUMN risk_factors TEXT DEFAULT '[]'
        """
        )

    if "risk_assessed_at" not in existing_columns:
        conn.execute(
            """
            ALTER TABLE task_queue ADD COLUMN risk_assessed_at TIMESTAMP
        """
        )

    # Create index for risk-based queries
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_task_queue_risk_level
        ON task_queue(risk_level)
    """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_task_queue_risk_score
        ON task_queue(risk_score DESC)
    """
    )

    conn.commit()
