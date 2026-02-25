#!/usr/bin/env python3
"""
Migration Diagnosis Tool

Analyzes database schema vs migration state to detect issues:
- Migrations marked as applied but not actually executed
- Schema mismatches between expected and actual
- Column conflicts and missing columns
- Out-of-order execution problems
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class MigrationDiagnostics:
    """Diagnose migration issues"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.migrations_dir = Path(__file__).parent

    def get_applied_versions(self) -> Dict[str, dict]:
        """Get versions from schema_versions table with metadata"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT version, applied_at, description, checksum
                FROM schema_versions
                ORDER BY CAST(version AS INTEGER)
                """
            )
            return {
                row[0]: {
                    "applied_at": row[1],
                    "description": row[2],
                    "checksum": row[3],
                }
                for row in cursor.fetchall()
            }

    def get_table_schema(self, table_name: str) -> List[Dict]:
        """Get actual schema for a table"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for row in cursor.fetchall():
                columns.append(
                    {
                        "cid": row[0],
                        "name": row[1],
                        "type": row[2],
                        "notnull": row[3],
                        "default": row[4],
                        "pk": row[5],
                    }
                )
            return columns

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in database"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def check_milestones_schema(self) -> Dict[str, any]:
        """Specifically check the milestones table for known issues"""
        schema = self.get_table_schema("milestones")
        column_names = {col["name"] for col in schema}

        # Expected columns from migration 003 + 004
        expected_from_003 = {
            "id",
            "app_id",
            "run_id",
            "name",
            "description",
            "milestone_type",
            "status",
            "risk_score",
            "risk_factors",
            "blast_radius",
            "rollback_steps",
            "rollback_available",
            "reviewer_notes",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "ready_at",
        }

        # Columns from original baseline (001)
        original_columns = {
            "id",
            "project_id",
            "name",
            "description",
            "target_date",
            "status",
            "progress",
            "created_at",
            "updated_at",
            "deleted_at",
            "deleted_by",
        }

        missing_from_003 = expected_from_003 - column_names
        has_original = column_names & original_columns

        return {
            "current_columns": column_names,
            "missing_from_autopilot": list(missing_from_003),
            "has_original_schema": len(has_original) > 8,
            "has_project_id": "project_id" in column_names,
            "has_app_id": "app_id" in column_names,
            "needs_migration_004": "app_id" not in column_names,
        }

    def analyze_migration_003_004_conflict(self) -> Dict[str, any]:
        """Analyze the specific 003/004 conflict"""
        applied = self.get_applied_versions()

        migration_003_applied = "003" in applied
        migration_004_applied = "004" in applied

        if migration_003_applied:
            m003_time = applied["003"]["applied_at"]
        else:
            m003_time = None

        if migration_004_applied:
            m004_time = applied["004"]["applied_at"]
            m004_desc = applied["004"]["description"]
        else:
            m004_time = None
            m004_desc = None

        # Check if 004 was applied before 003 (wrong order)
        wrong_order = False
        if m003_time and m004_time:
            # Parse timestamps to compare
            # Format: 2026-02-10 19:45:37
            try:
                from datetime import datetime

                t003 = datetime.strptime(m003_time, "%Y-%m-%d %H:%M:%S")
                t004 = datetime.strptime(m004_time, "%Y-%m-%d %H:%M:%S")
                wrong_order = t004 < t003
            except:
                pass

        milestones_check = self.check_milestones_schema()

        return {
            "migration_003_applied": migration_003_applied,
            "migration_004_applied": migration_004_applied,
            "migration_003_time": m003_time,
            "migration_004_time": m004_time,
            "migration_004_desc": m004_desc,
            "wrong_order": wrong_order,
            "milestones_needs_fix": milestones_check["needs_migration_004"],
            "milestones_analysis": milestones_check,
        }

    def find_skipped_migrations(self) -> List[Dict]:
        """Find migrations marked as applied but likely not executed"""
        applied = self.get_applied_versions()
        skipped = []

        for version, info in applied.items():
            desc = info.get("description", "")
            if "skipped" in desc.lower() or "already applied" in desc.lower():
                skipped.append(
                    {"version": version, "description": desc, "applied_at": info["applied_at"]}
                )

        return skipped

    def generate_report(self) -> str:
        """Generate comprehensive diagnostic report"""
        lines = []
        lines.append("=" * 80)
        lines.append("MIGRATION DIAGNOSTICS REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Basic stats
        applied = self.get_applied_versions()
        lines.append(f"Database: {self.db_path}")
        lines.append(f"Applied migrations: {len(applied)}")
        lines.append("")

        # 003/004 conflict analysis
        lines.append("=" * 80)
        lines.append("MIGRATION 003/004 CONFLICT ANALYSIS")
        lines.append("=" * 80)
        conflict = self.analyze_migration_003_004_conflict()

        lines.append(f"Migration 003 applied: {conflict['migration_003_applied']}")
        if conflict["migration_003_time"]:
            lines.append(f"  Applied at: {conflict['migration_003_time']}")

        lines.append(f"Migration 004 applied: {conflict['migration_004_applied']}")
        if conflict["migration_004_time"]:
            lines.append(f"  Applied at: {conflict['migration_004_time']}")
            lines.append(f"  Description: {conflict['migration_004_desc']}")

        if conflict["wrong_order"]:
            lines.append("")
            lines.append("❌ ERROR: Migration 004 was marked as applied BEFORE 003!")
            lines.append("   This is wrong - 004 depends on 003 being applied first.")

        lines.append("")
        lines.append("Milestones table analysis:")
        m = conflict["milestones_analysis"]
        lines.append(f"  Has project_id (original schema): {m['has_project_id']}")
        lines.append(f"  Has app_id (autopilot schema): {m['has_app_id']}")
        lines.append(f"  Needs migration 004: {m['needs_migration_004']}")

        if m["missing_from_autopilot"]:
            lines.append(
                f"  Missing columns for autopilot: {', '.join(m['missing_from_autopilot'])}"
            )

        # Verdict
        lines.append("")
        if m["needs_migration_004"]:
            lines.append("🔴 VERDICT: Milestones table is missing autopilot columns")
            lines.append(
                "   Migration 004 was marked as applied but ALTER TABLE commands were never executed"
            )
            lines.append("   This is why app.py fails with 'no such column: app_id' errors")
        else:
            lines.append("✅ VERDICT: Milestones table has autopilot columns")

        # Skipped migrations
        lines.append("")
        lines.append("=" * 80)
        lines.append("SKIPPED MIGRATIONS")
        lines.append("=" * 80)
        skipped = self.find_skipped_migrations()
        if skipped:
            for s in skipped:
                lines.append(f"  {s['version']}: {s['description']}")
                lines.append(f"    (marked applied at {s['applied_at']})")
        else:
            lines.append("  None found")

        # Tables
        lines.append("")
        lines.append("=" * 80)
        lines.append("DATABASE TABLES")
        lines.append("=" * 80)
        tables = self.get_all_tables()
        for table in tables:
            columns = self.get_table_schema(table)
            lines.append(f"  {table} ({len(columns)} columns)")

        lines.append("")
        lines.append("=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)

        if m["needs_migration_004"]:
            lines.append("")
            lines.append("To fix the milestones table, you need to:")
            lines.append("1. Remove migration 004 from schema_versions")
            lines.append("2. Re-run migration 004 to actually execute the ALTER TABLE commands")
            lines.append("")
            lines.append("Run this command:")
            lines.append(f"  python3 migrations/diagnose.py --fix-004 --db {self.db_path}")
        else:
            lines.append("  Database schema appears correct for current migrations")

        skipped_count = len(skipped)
        if skipped_count > 0:
            lines.append("")
            lines.append(
                f"Found {skipped_count} migrations marked as 'skipped' - these may need review"
            )

        return "\n".join(lines)

    def fix_migration_004(self):
        """Fix migration 004 by removing it from schema_versions and re-running"""
        print("Fixing migration 004...")
        print("")

        # Check if 004 needs fixing
        conflict = self.analyze_migration_003_004_conflict()
        if not conflict["milestones_needs_fix"]:
            print("✅ Migration 004 doesn't need fixing - milestones table already has app_id")
            return

        with sqlite3.connect(str(self.db_path)) as conn:
            # Remove 004 from schema_versions
            print("1. Removing migration 004 from schema_versions...")
            conn.execute("DELETE FROM schema_versions WHERE version = '004'")
            conn.commit()
            print("   ✅ Removed")

            # Now manually apply the ALTER TABLE commands from 004
            print("")
            print("2. Applying ALTER TABLE commands from migration 004...")

            migration_004_path = self.migrations_dir / "004_fix_milestones_schema.sql"
            if not migration_004_path.exists():
                print(f"   ❌ ERROR: Migration file not found: {migration_004_path}")
                return

            sql_content = migration_004_path.read_text()

            # Execute each ALTER TABLE command
            for line in sql_content.split("\n"):
                line = line.strip()
                if line.startswith("ALTER TABLE") or line.startswith("CREATE INDEX"):
                    try:
                        print(f"   Executing: {line[:60]}...")
                        conn.execute(line)
                        print("   ✅ Success")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" in str(e):
                            print(f"   ⚠️  Column already exists (skipping)")
                        else:
                            print(f"   ❌ ERROR: {e}")
                            raise

            conn.commit()

            # Re-add 004 to schema_versions
            print("")
            print("3. Marking migration 004 as applied...")
            conn.execute(
                """
                INSERT INTO schema_versions (version, description, checksum)
                VALUES ('004', 'Fix milestones schema for autopilot', 'manual_fix')
                """
            )
            conn.commit()
            print("   ✅ Done")

        print("")
        print("✅ Migration 004 fix complete!")
        print("")
        print("Verify with:")
        print(f"  python3 migrations/diagnose.py --db {self.db_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Diagnose migration issues")
    parser.add_argument("--db", default="data/architect.db", help="Database path")
    parser.add_argument("--fix-004", action="store_true", help="Fix migration 004 issue")

    args = parser.parse_args()

    diag = MigrationDiagnostics(args.db)

    if args.fix_004:
        diag.fix_migration_004()
    else:
        report = diag.generate_report()
        print(report)


if __name__ == "__main__":
    main()
