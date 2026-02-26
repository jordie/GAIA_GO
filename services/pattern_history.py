#!/usr/bin/env python3
"""
Pattern History Tracker

Tracks prompt patterns and confirmation behaviors over time.
Provides historical analysis for learning and optimization.
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class PatternHistoryTracker:
    """Tracks and analyzes prompt patterns over time."""

    def __init__(self, db_path: str = "/tmp/pattern_history.db"):
        """Initialize tracker."""
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Create pattern history tables."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        # Pattern occurrences
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pattern_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                operation_type TEXT,
                prompt_text TEXT,
                occurrence_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmation_key TEXT,
                success BOOLEAN,
                duration_seconds REAL,
                metadata JSON
            )
        """
        )

        # Pattern statistics
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pattern_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT UNIQUE,
                operation_type TEXT,
                total_occurrences INTEGER DEFAULT 0,
                successful_confirmations INTEGER DEFAULT 0,
                failed_confirmations INTEGER DEFAULT 0,
                average_duration REAL,
                first_seen TIMESTAMP,
                last_seen TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Confirmation trends
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS confirmation_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                operation_type TEXT NOT NULL,
                total_confirmations INTEGER DEFAULT 0,
                successful INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                average_duration REAL,
                UNIQUE(date, operation_type)
            )
        """
        )

        # Create indices
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fingerprint ON pattern_occurrences(fingerprint)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON pattern_occurrences(session_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON pattern_occurrences(occurrence_time)")

        conn.commit()
        conn.close()

    def record_occurrence(
        self,
        session_name: str,
        fingerprint: str,
        operation_type: str,
        prompt_text: str,
        confirmation_key: str = None,
        success: bool = True,
        duration_seconds: float = None,
    ):
        """Record a prompt confirmation occurrence."""
        conn = sqlite3.connect(self.db_path)

        # Record occurrence
        conn.execute(
            """
            INSERT INTO pattern_occurrences
            (session_name, fingerprint, operation_type, prompt_text,
             confirmation_key, success, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_name,
                fingerprint,
                operation_type,
                prompt_text[:500],  # Limit text length
                confirmation_key,
                success,
                duration_seconds,
            ),
        )

        # Update statistics
        current_time = datetime.now()

        cursor = conn.execute(
            """
            SELECT total_occurrences, successful_confirmations,
                   failed_confirmations, average_duration
            FROM pattern_statistics
            WHERE fingerprint = ?
        """,
            (fingerprint,),
        )

        row = cursor.fetchone()

        if row:
            total, successful, failed, avg_duration = row
            new_total = total + 1
            new_successful = successful + (1 if success else 0)
            new_failed = failed + (0 if success else 1)

            # Calculate new average
            if avg_duration and duration_seconds:
                new_avg = (avg_duration * total + duration_seconds) / new_total
            else:
                new_avg = duration_seconds

            conn.execute(
                """
                UPDATE pattern_statistics
                SET total_occurrences = ?,
                    successful_confirmations = ?,
                    failed_confirmations = ?,
                    average_duration = ?,
                    last_seen = CURRENT_TIMESTAMP,
                    last_updated = CURRENT_TIMESTAMP
                WHERE fingerprint = ?
            """,
                (new_total, new_successful, new_failed, new_avg, fingerprint),
            )
        else:
            # Insert new pattern
            conn.execute(
                """
                INSERT INTO pattern_statistics
                (fingerprint, operation_type, total_occurrences,
                 successful_confirmations, failed_confirmations,
                 average_duration, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    fingerprint,
                    operation_type,
                    1,
                    1 if success else 0,
                    0 if success else 1,
                    duration_seconds,
                ),
            )

        conn.commit()
        conn.close()

    def get_pattern_statistics(self, fingerprint: str = None) -> Dict:
        """Get pattern statistics."""
        conn = sqlite3.connect(self.db_path)

        if fingerprint:
            cursor = conn.execute(
                """
                SELECT fingerprint, operation_type, total_occurrences,
                       successful_confirmations, failed_confirmations,
                       average_duration, first_seen, last_seen
                FROM pattern_statistics
                WHERE fingerprint = ?
            """,
                (fingerprint,),
            )
        else:
            cursor = conn.execute(
                """
                SELECT fingerprint, operation_type, total_occurrences,
                       successful_confirmations, failed_confirmations,
                       average_duration, first_seen, last_seen
                FROM pattern_statistics
                ORDER BY total_occurrences DESC
                LIMIT 20
            """
            )

        stats = []
        for row in cursor.fetchall():
            fp, op, total, successful, failed, avg_dur, first, last = row
            success_rate = (successful / total * 100) if total > 0 else 0

            stats.append(
                {
                    "fingerprint": fp,
                    "operation": op,
                    "total": total,
                    "successful": successful,
                    "failed": failed,
                    "success_rate": success_rate,
                    "average_duration": avg_dur,
                    "first_seen": first,
                    "last_seen": last,
                }
            )

        conn.close()
        return stats

    def get_daily_trends(self, days: int = 7) -> List[Dict]:
        """Get confirmation trends for the last N days."""
        conn = sqlite3.connect(self.db_path)

        start_date = (datetime.now() - timedelta(days=days)).date()

        cursor = conn.execute(
            """
            SELECT date, operation_type, total_confirmations,
                   successful, failed, average_duration
            FROM confirmation_trends
            WHERE date >= ?
            ORDER BY date, operation_type
        """,
            (start_date,),
        )

        trends = []
        for row in cursor.fetchall():
            date, op, total, successful, failed, avg_dur = row
            success_rate = (successful / total * 100) if total > 0 else 0

            trends.append(
                {
                    "date": date,
                    "operation": op,
                    "total": total,
                    "successful": successful,
                    "failed": failed,
                    "success_rate": success_rate,
                    "average_duration": avg_dur,
                }
            )

        conn.close()
        return trends

    def get_session_statistics(self, session_name: str) -> Dict:
        """Get statistics for a specific session."""
        conn = sqlite3.connect(self.db_path)

        cursor = conn.execute(
            """
            SELECT operation_type, COUNT(*) as count,
                   SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                   AVG(duration_seconds) as avg_duration
            FROM pattern_occurrences
            WHERE session_name = ?
            GROUP BY operation_type
        """,
            (session_name,),
        )

        stats = {
            "session_name": session_name,
            "total_confirmations": 0,
            "by_operation": {},
        }

        for op, count, successful, avg_dur in cursor.fetchall():
            success_rate = (successful / count * 100) if count > 0 else 0
            stats["by_operation"][op] = {
                "count": count,
                "successful": successful,
                "failed": count - successful,
                "success_rate": success_rate,
                "average_duration": avg_dur,
            }
            stats["total_confirmations"] += count

        conn.close()
        return stats

    def cleanup_old_records(self, days: int = 30):
        """Remove records older than N days."""
        conn = sqlite3.connect(self.db_path)

        cutoff_date = datetime.now() - timedelta(days=days)

        conn.execute(
            "DELETE FROM pattern_occurrences WHERE occurrence_time < ?",
            (cutoff_date,),
        )

        deleted = conn.total_changes
        conn.commit()
        conn.close()

        return deleted


def main():
    """Test the pattern history tracker."""
    print("Testing Pattern History Tracker")
    print("=" * 80)

    tracker = PatternHistoryTracker()

    # Record some test patterns
    print("\n1. Recording test patterns:")
    test_data = [
        ("basic_edu", "fp001", "proceed_yes", "Do you want to proceed?", "1", True, 0.5),
        ("basic_edu", "fp001", "proceed_yes", "Do you want to proceed?", "1", True, 0.48),
        ("foundation", "fp002", "accept_edits", "Accept edits?", "Enter", True, 0.2),
        ("foundation", "fp002", "accept_edits", "Accept edits?", "Enter", True, 0.25),
        ("inspector", "fp003", "continue", "What should Claude do?", "continue", True, 1.5),
    ]

    for session, fp, op, prompt, key, success, duration in test_data:
        tracker.record_occurrence(session, fp, op, prompt, key, success, duration)
        print(f"   ✓ {session}: {op}")

    # Get statistics
    print("\n2. Pattern statistics:")
    stats = tracker.get_pattern_statistics()
    for stat in stats:
        print(f"   {stat['operation']}: {stat['total']} total, {stat['success_rate']:.0f}% success")

    # Get session statistics
    print("\n3. Session statistics:")
    for session in ["basic_edu", "foundation", "inspector"]:
        session_stats = tracker.get_session_statistics(session)
        print(f"   {session}: {session_stats['total_confirmations']} confirmations")
        for op, op_stats in session_stats["by_operation"].items():
            print(f"     - {op}: {op_stats['count']} ({op_stats['success_rate']:.0f}% success)")

    # Get trends
    print("\n4. Trends (last 7 days):")
    trends = tracker.get_daily_trends(7)
    print(f"   Found {len(trends)} trend records")

    print("\n✓ Pattern History Tracker tests complete!")


if __name__ == "__main__":
    main()
