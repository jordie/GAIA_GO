#!/usr/bin/env python3
"""
Pattern Tracker - Monitors and learns from prompt patterns across LLM tools.
Tracks when patterns appear, detects trends, and enables quick adaptation.
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PatternTracker:
    """Tracks and analyzes patterns in LLM tool outputs."""

    def __init__(self, db_path: str = "/tmp/pattern_tracker.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize pattern tracking database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Pattern definitions table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_name TEXT NOT NULL,
                pattern_regex TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                description TEXT,
                action TEXT,
                confidence_threshold REAL DEFAULT 0.8,
                active BOOLEAN DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(pattern_name, tool_name)
            )
        """
        )

        # Pattern occurrences table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id INTEGER NOT NULL,
                session_name TEXT NOT NULL,
                matched_text TEXT NOT NULL,
                context TEXT,
                timestamp REAL NOT NULL,
                response_action TEXT,
                response_success BOOLEAN,
                FOREIGN KEY (pattern_id) REFERENCES patterns(id)
            )
        """
        )

        # Pattern trends table (hourly aggregates)
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id INTEGER NOT NULL,
                hour_bucket TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_response_time REAL,
                UNIQUE(pattern_id, hour_bucket),
                FOREIGN KEY (pattern_id) REFERENCES patterns(id)
            )
        """
        )

        # Pattern changes/alerts table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS pattern_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_type TEXT NOT NULL,
                pattern_id INTEGER,
                description TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                detected_at REAL NOT NULL,
                acknowledged BOOLEAN DEFAULT 0
            )
        """
        )

        # Create indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_occurrences_pattern ON occurrences(pattern_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_occurrences_timestamp ON occurrences(timestamp)")
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_trends_pattern_hour ON trends(pattern_id, hour_bucket)"
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_changes_detected ON pattern_changes(detected_at)")

        conn.commit()
        conn.close()

    def add_pattern(
        self,
        pattern_type: str,
        pattern_name: str,
        pattern_regex: str,
        tool_name: str,
        description: str = "",
        action: str = "",
        confidence_threshold: float = 0.8,
    ) -> int:
        """Add a new pattern to track."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        now = time.time()

        try:
            c.execute(
                """
                INSERT INTO patterns
                (pattern_type, pattern_name, pattern_regex, tool_name, description,
                 action, confidence_threshold, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    pattern_type,
                    pattern_name,
                    pattern_regex,
                    tool_name,
                    description,
                    action,
                    confidence_threshold,
                    now,
                    now,
                ),
            )

            pattern_id = c.lastrowid
            conn.commit()
            return pattern_id
        except sqlite3.IntegrityError:
            # Pattern already exists, get its ID
            c.execute(
                """
                SELECT id FROM patterns
                WHERE pattern_name = ? AND tool_name = ?
            """,
                (pattern_name, tool_name),
            )
            result = c.fetchone()
            return result[0] if result else None
        finally:
            conn.close()

    def record_occurrence(
        self,
        pattern_id: int,
        session_name: str,
        matched_text: str,
        context: str = "",
        response_action: str = "",
        response_success: bool = True,
    ):
        """Record when a pattern is detected."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        now = time.time()

        # Record occurrence
        c.execute(
            """
            INSERT INTO occurrences
            (pattern_id, session_name, matched_text, context, timestamp,
             response_action, response_success)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                pattern_id,
                session_name,
                matched_text,
                context,
                now,
                response_action,
                response_success,
            ),
        )

        # Update trend aggregate
        hour_bucket = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:00:00")

        c.execute(
            """
            INSERT INTO trends (pattern_id, hour_bucket, occurrence_count, success_count, failure_count)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(pattern_id, hour_bucket) DO UPDATE SET
                occurrence_count = occurrence_count + 1,
                success_count = success_count + ?,
                failure_count = failure_count + ?
        """,
            (
                pattern_id,
                hour_bucket,
                1 if response_success else 0,
                0 if response_success else 1,
                1 if response_success else 0,
                0 if response_success else 1,
            ),
        )

        conn.commit()
        conn.close()

    def get_pattern_trends(self, pattern_id: int, hours: int = 24) -> List[Dict]:
        """Get trend data for a pattern."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        cutoff_time = datetime.now() - timedelta(hours=hours)
        hour_bucket = cutoff_time.strftime("%Y-%m-%d %H:00:00")

        c.execute(
            """
            SELECT hour_bucket, occurrence_count, success_count, failure_count
            FROM trends
            WHERE pattern_id = ? AND hour_bucket >= ?
            ORDER BY hour_bucket DESC
        """,
            (pattern_id, hour_bucket),
        )

        trends = []
        for row in c.fetchall():
            trends.append(
                {
                    "hour": row[0],
                    "occurrences": row[1],
                    "successes": row[2],
                    "failures": row[3],
                    "success_rate": row[2] / row[1] if row[1] > 0 else 0,
                }
            )

        conn.close()
        return trends

    def detect_pattern_changes(self) -> List[Dict]:
        """Detect changes in pattern behavior (new patterns, disappeared patterns, etc.)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        changes = []
        now = time.time()

        # Check for patterns that haven't appeared recently (24h)
        c.execute(
            """
            SELECT p.id, p.pattern_name, p.tool_name, MAX(o.timestamp) as last_seen
            FROM patterns p
            LEFT JOIN occurrences o ON p.id = o.pattern_id
            WHERE p.active = 1
            GROUP BY p.id
            HAVING last_seen IS NULL OR last_seen < ?
        """,
            (now - 86400,),
        )  # 24 hours ago

        for row in c.fetchall():
            pattern_id, pattern_name, tool_name, last_seen = row

            if last_seen:
                hours_ago = (now - last_seen) / 3600
                changes.append(
                    {
                        "type": "pattern_disappeared",
                        "pattern_id": pattern_id,
                        "pattern_name": pattern_name,
                        "tool_name": tool_name,
                        "description": f"Pattern hasn't appeared in {hours_ago:.1f} hours",
                        "last_seen": last_seen,
                    }
                )

        # Check for patterns with declining success rates
        c.execute(
            """
            SELECT p.id, p.pattern_name, p.tool_name, t.hour_bucket,
                   t.occurrence_count, t.success_count, t.failure_count
            FROM patterns p
            JOIN trends t ON p.id = t.pattern_id
            WHERE t.hour_bucket >= datetime('now', '-24 hours')
              AND t.failure_count > t.success_count
              AND t.occurrence_count >= 5
        """
        )

        for row in c.fetchall():
            pattern_id, pattern_name, tool_name, hour, count, success, failure = row
            success_rate = success / count if count > 0 else 0

            changes.append(
                {
                    "type": "low_success_rate",
                    "pattern_id": pattern_id,
                    "pattern_name": pattern_name,
                    "tool_name": tool_name,
                    "description": f"Success rate dropped to {success_rate*100:.1f}% ({success}/{count})",
                    "hour": hour,
                    "success_rate": success_rate,
                }
            )

        # Check for new patterns (first seen in last hour)
        c.execute(
            """
            SELECT p.id, p.pattern_name, p.tool_name, MIN(o.timestamp) as first_seen
            FROM patterns p
            JOIN occurrences o ON p.id = o.pattern_id
            GROUP BY p.id
            HAVING first_seen >= ?
        """,
            (now - 3600,),
        )  # Last hour

        for row in c.fetchall():
            pattern_id, pattern_name, tool_name, first_seen = row

            changes.append(
                {
                    "type": "new_pattern_detected",
                    "pattern_id": pattern_id,
                    "pattern_name": pattern_name,
                    "tool_name": tool_name,
                    "description": f"New pattern first seen",
                    "first_seen": first_seen,
                }
            )

        # Record changes
        for change in changes:
            c.execute(
                """
                INSERT INTO pattern_changes
                (change_type, pattern_id, description, detected_at)
                VALUES (?, ?, ?, ?)
            """,
                (change["type"], change.get("pattern_id"), change["description"], now),
            )

        conn.commit()
        conn.close()

        return changes

    def get_pattern_stats(self, hours: int = 24) -> Dict:
        """Get overall pattern statistics."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        cutoff_time = time.time() - (hours * 3600)

        # Total patterns
        c.execute("SELECT COUNT(*) FROM patterns WHERE active = 1")
        total_patterns = c.fetchone()[0]

        # Patterns by tool
        c.execute(
            """
            SELECT tool_name, COUNT(*) as count
            FROM patterns
            WHERE active = 1
            GROUP BY tool_name
        """
        )
        by_tool = {row[0]: row[1] for row in c.fetchall()}

        # Recent occurrences
        c.execute(
            """
            SELECT COUNT(*) FROM occurrences
            WHERE timestamp >= ?
        """,
            (cutoff_time,),
        )
        recent_occurrences = c.fetchone()[0]

        # Success rate
        c.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN response_success = 1 THEN 1 ELSE 0 END) as successes
            FROM occurrences
            WHERE timestamp >= ?
        """,
            (cutoff_time,),
        )
        row = c.fetchone()
        total, successes = row
        success_rate = (successes / total * 100) if total > 0 else 0

        # Active patterns (seen in last 24h)
        c.execute(
            """
            SELECT COUNT(DISTINCT pattern_id)
            FROM occurrences
            WHERE timestamp >= ?
        """,
            (cutoff_time,),
        )
        active_count = c.fetchone()[0]

        # Unacknowledged changes
        c.execute(
            """
            SELECT COUNT(*) FROM pattern_changes
            WHERE acknowledged = 0
        """
        )
        pending_changes = c.fetchone()[0]

        conn.close()

        return {
            "total_patterns": total_patterns,
            "active_patterns": active_count,
            "by_tool": by_tool,
            "recent_occurrences": recent_occurrences,
            "success_rate": success_rate,
            "pending_changes": pending_changes,
            "period_hours": hours,
        }

    def export_patterns(self, output_file: str = "patterns_export.json"):
        """Export all patterns and their stats for backup/analysis."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT p.*,
                   COUNT(o.id) as total_occurrences,
                   SUM(CASE WHEN o.response_success = 1 THEN 1 ELSE 0 END) as successes,
                   MAX(o.timestamp) as last_seen
            FROM patterns p
            LEFT JOIN occurrences o ON p.id = o.pattern_id
            GROUP BY p.id
        """
        )

        patterns = []
        for row in c.fetchall():
            patterns.append(
                {
                    "id": row[0],
                    "pattern_type": row[1],
                    "pattern_name": row[2],
                    "pattern_regex": row[3],
                    "tool_name": row[4],
                    "description": row[5],
                    "action": row[6],
                    "confidence_threshold": row[7],
                    "active": bool(row[8]),
                    "created_at": row[9],
                    "updated_at": row[10],
                    "stats": {
                        "total_occurrences": row[11] or 0,
                        "successes": row[12] or 0,
                        "last_seen": row[13],
                    },
                }
            )

        conn.close()

        with open(output_file, "w") as f:
            json.dump(patterns, f, indent=2)

        return patterns


def init_default_patterns():
    """Initialize default patterns for known LLM tools."""
    tracker = PatternTracker()

    # Claude Code patterns
    tracker.add_pattern(
        pattern_type="permission_prompt",
        pattern_name="claude_allow_once",
        pattern_regex=r"(?:●|•)\s*1\.\s*Allow once",
        tool_name="claude",
        description="Claude Code standard permission prompt",
        action="send_key:1",
    )

    tracker.add_pattern(
        pattern_type="permission_prompt",
        pattern_name="claude_allow_session",
        pattern_regex=r"(?:●|•)?\s*2\.\s*Allow for this session",
        tool_name="claude",
        description="Claude Code session-wide permission",
        action="send_key:2",
    )

    # Gemini CLI patterns
    tracker.add_pattern(
        pattern_type="permission_prompt",
        pattern_name="gemini_allow_once",
        pattern_regex=r"●\s*1\.\s*Allow once",
        tool_name="gemini",
        description="Gemini CLI permission prompt - allow once",
        action="send_key:1",
    )

    tracker.add_pattern(
        pattern_type="permission_prompt",
        pattern_name="gemini_allow_session",
        pattern_regex=r"2\.\s*Allow for this session",
        tool_name="gemini",
        description="Gemini CLI permission prompt - allow session",
        action="send_key:2",
    )

    tracker.add_pattern(
        pattern_type="permission_prompt",
        pattern_name="gemini_action_required",
        pattern_regex=r"Action Required",
        tool_name="gemini",
        description="Gemini CLI action required header",
        action="wait_for_options",
    )

    # Error patterns
    tracker.add_pattern(
        pattern_type="error",
        pattern_name="gemini_api_error",
        pattern_regex=r"\[API Error:.*models/([\w\-\.]+)\s+is not found",
        tool_name="gemini",
        description="Gemini API model not found error",
        action="alert:model_deprecated",
    )

    tracker.add_pattern(
        pattern_type="status",
        pattern_name="claude_accept_edits",
        pattern_regex=r"accept edits on",
        tool_name="claude",
        description="Claude Code accept edits status line (not a prompt)",
        action="skip",
    )

    print("✅ Default patterns initialized")


def main():
    """CLI for pattern tracker."""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python pattern_tracker.py init          # Initialize default patterns")
        print("  python pattern_tracker.py stats         # Show statistics")
        print("  python pattern_tracker.py changes       # Detect pattern changes")
        print("  python pattern_tracker.py trends <id>   # Show trends for pattern")
        print("  python pattern_tracker.py export        # Export patterns")
        sys.exit(0)

    command = sys.argv[1]

    if command == "init":
        init_default_patterns()

    elif command == "stats":
        tracker = PatternTracker()
        stats = tracker.get_pattern_stats()

        print("\n" + "=" * 60)
        print("PATTERN TRACKER STATISTICS")
        print("=" * 60)
        print(f"\nTotal Patterns: {stats['total_patterns']}")
        print(f"Active Patterns (last {stats['period_hours']}h): {stats['active_patterns']}")
        print(f"\nPatterns by Tool:")
        for tool, count in stats["by_tool"].items():
            print(f"  {tool}: {count}")
        print(f"\nRecent Occurrences: {stats['recent_occurrences']}")
        print(f"Success Rate: {stats['success_rate']:.1f}%")
        print(f"Pending Changes: {stats['pending_changes']}")

    elif command == "changes":
        tracker = PatternTracker()
        changes = tracker.detect_pattern_changes()

        print("\n" + "=" * 60)
        print("PATTERN CHANGES DETECTED")
        print("=" * 60)

        if not changes:
            print("\n✅ No significant changes detected")
        else:
            for change in changes:
                print(f"\n⚠️  {change['type'].upper()}")
                print(f"   Pattern: {change.get('pattern_name', 'N/A')}")
                print(f"   Tool: {change.get('tool_name', 'N/A')}")
                print(f"   {change['description']}")

    elif command == "trends":
        if len(sys.argv) < 3:
            print("Error: Usage: pattern_tracker.py trends <pattern_id>")
            sys.exit(1)

        pattern_id = int(sys.argv[2])
        tracker = PatternTracker()
        trends = tracker.get_pattern_trends(pattern_id)

        print("\n" + "=" * 60)
        print(f"PATTERN TRENDS (ID: {pattern_id})")
        print("=" * 60)

        for trend in trends:
            print(f"\n{trend['hour']}")
            print(f"  Occurrences: {trend['occurrences']}")
            print(f"  Successes: {trend['successes']}")
            print(f"  Failures: {trend['failures']}")
            print(f"  Success Rate: {trend['success_rate']*100:.1f}%")

    elif command == "export":
        tracker = PatternTracker()
        patterns = tracker.export_patterns()
        print(f"✅ Exported {len(patterns)} patterns to patterns_export.json")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
