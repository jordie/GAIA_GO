#!/usr/bin/env python3
"""
Confirmation Learner - Learn from auto_confirm successes

Tracks confirmation patterns and builds a knowledge base of:
- What prompts appear frequently
- Which operations succeed most reliably
- What responses work best for each pattern
- Timing and context of confirmations

This data can be used to improve auto_confirm_worker detection and response.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class ConfirmationLearner:
    """Learn from confirmation patterns and successes."""

    def __init__(self, db_file="/tmp/auto_confirm_learner.db"):
        self.db_file = Path(db_file)
        self.init_db()

    def init_db(self):
        """Initialize learning database."""
        conn = sqlite3.connect(str(self.db_file))
        c = conn.cursor()

        # Track confirmation patterns
        c.execute(
            """CREATE TABLE IF NOT EXISTS confirmation_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            prompt_text TEXT,
            response_key TEXT,
            success INTEGER DEFAULT 1,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )

        # Track operation statistics
        c.execute(
            """CREATE TABLE IF NOT EXISTS operation_stats (
            operation_type TEXT PRIMARY KEY,
            total_confirmations INTEGER DEFAULT 0,
            successful INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            best_response TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )

        # Track prompt variations
        c.execute(
            """CREATE TABLE IF NOT EXISTS prompt_variations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT,
            pattern TEXT UNIQUE,
            occurrences INTEGER DEFAULT 1,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )

        conn.commit()
        conn.close()

    def record_confirmation(self, session, operation, prompt_text, response_key, success=True):
        """Record a confirmation attempt and its outcome."""
        try:
            conn = sqlite3.connect(str(self.db_file))
            c = conn.cursor()

            # Record the confirmation
            c.execute(
                """INSERT INTO confirmation_patterns
                (session_name, operation_type, prompt_text, response_key, success)
                VALUES (?, ?, ?, ?, ?)""",
                (session, operation, prompt_text[:500], response_key, int(success)),
            )

            # Update operation stats
            c.execute(
                """INSERT INTO operation_stats
                (operation_type, total_confirmations, successful)
                VALUES (?, 1, ?)
                ON CONFLICT(operation_type) DO UPDATE SET
                    total_confirmations = total_confirmations + 1,
                    successful = successful + ?,
                    last_updated = CURRENT_TIMESTAMP""",
                (operation, int(success), int(success)),
            )

            # Track prompt variations
            pattern_key = self._extract_pattern(prompt_text)
            if pattern_key:
                c.execute(
                    """INSERT INTO prompt_variations (operation_type, pattern)
                    VALUES (?, ?)
                    ON CONFLICT(pattern) DO UPDATE SET
                        occurrences = occurrences + 1,
                        last_seen = CURRENT_TIMESTAMP""",
                    (operation, pattern_key),
                )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error recording confirmation: {e}")
            return False

    def _extract_pattern(self, prompt_text):
        """Extract a pattern key from prompt text."""
        if not prompt_text:
            return None

        # Look for key phrases
        text_lower = prompt_text.lower()
        if "do you want to" in text_lower:
            return "do_you_want_to"
        elif "would you like" in text_lower:
            return "would_you_like"
        elif "accept edits" in text_lower:
            return "accept_edits"
        elif "bash" in text_lower or "command" in text_lower:
            return "bash_command"
        elif "edit" in text_lower:
            return "edit_file"
        else:
            return "generic_prompt"

    def get_stats(self):
        """Get operation statistics from learning database."""
        try:
            conn = sqlite3.connect(str(self.db_file))
            c = conn.cursor()

            # Get operation success rates
            c.execute(
                """SELECT operation_type, total_confirmations, successful,
                ROUND(100.0 * successful / total_confirmations, 1) as success_rate
                FROM operation_stats
                ORDER BY success_rate DESC"""
            )
            stats = c.fetchall()
            conn.close()

            return {
                "operations": [
                    {
                        "type": row[0],
                        "total": row[1],
                        "successful": row[2],
                        "success_rate": f"{row[3]}%",
                    }
                    for row in stats
                ]
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}

    def get_best_response(self, operation_type):
        """Get the best response for an operation type based on history."""
        try:
            conn = sqlite3.connect(str(self.db_file))
            c = conn.cursor()

            # Find most common successful response
            c.execute(
                """SELECT response_key, COUNT(*) as count
                FROM confirmation_patterns
                WHERE operation_type = ? AND success = 1
                GROUP BY response_key
                ORDER BY count DESC
                LIMIT 1""",
                (operation_type,),
            )
            result = c.fetchone()
            conn.close()

            return result[0] if result else None
        except Exception as e:
            print(f"Error getting best response: {e}")
            return None

    def get_top_patterns(self, limit=10):
        """Get most common confirmation patterns."""
        try:
            conn = sqlite3.connect(str(self.db_file))
            c = conn.cursor()

            c.execute(
                """SELECT pattern, operation_type, occurrences, last_seen
                FROM prompt_variations
                ORDER BY occurrences DESC
                LIMIT ?""",
                (limit,),
            )
            patterns = c.fetchall()
            conn.close()

            return [
                {"pattern": p[0], "operation": p[1], "occurrences": p[2], "last_seen": p[3]}
                for p in patterns
            ]
        except Exception as e:
            print(f"Error getting patterns: {e}")
            return []

    def export_learnings(self, output_file="/tmp/confirmation_learnings.json"):
        """Export learnings to JSON for analysis."""
        try:
            learnings = {
                "exported_at": datetime.now().isoformat(),
                "stats": self.get_stats(),
                "top_patterns": self.get_top_patterns(20),
                "database": str(self.db_file),
            }

            with open(output_file, "w") as f:
                json.dump(learnings, f, indent=2)

            print(f"Learnings exported to {output_file}")
            return True
        except Exception as e:
            print(f"Error exporting learnings: {e}")
            return False


def main():
    """Interactive learner CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Confirmation learning analyzer")
    parser.add_argument("--stats", action="store_true", help="Show operation statistics")
    parser.add_argument("--patterns", action="store_true", help="Show top patterns")
    parser.add_argument("--export", action="store_true", help="Export learnings to JSON")
    parser.add_argument("--best", metavar="OPERATION", help="Get best response for operation")

    args = parser.parse_args()

    learner = ConfirmationLearner()

    if args.stats:
        stats = learner.get_stats()
        print("\n=== OPERATION STATISTICS ===\n")
        for op in stats.get("operations", []):
            print(
                f"{op['type']:20} | Total: {op['total']:3} | "
                f"Success: {op['successful']:3} | Rate: {op['success_rate']}"
            )

    if args.patterns:
        patterns = learner.get_top_patterns()
        print("\n=== TOP PATTERNS ===\n")
        for p in patterns:
            print(f"{p['pattern']:20} ({p['operation']:15}) | {p['occurrences']:3}x")

    if args.export:
        learner.export_learnings()

    if args.best:
        best = learner.get_best_response(args.best)
        print(f"\nBest response for '{args.best}': {best}")

    if not any([args.stats, args.patterns, args.export, args.best]):
        print("Use --help to see options")
        print(f"\nDatabase: {learner.db_file}")


if __name__ == "__main__":
    main()
