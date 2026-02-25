#!/usr/bin/env python3
"""
Fix Migration 004 Across All Environments

Applies the migration 004 fix to all environment-specific databases
"""

import sys
from pathlib import Path

from diagnose import MigrationDiagnostics


def find_architect_databases():
    """Find all architect.db files in data subdirectories"""
    base = Path("data")
    if not base.exists():
        return []

    databases = []

    # Main database
    if (base / "architect.db").exists():
        databases.append(("main", base / "architect.db"))

    # Environment databases
    for env_dir in base.iterdir():
        if env_dir.is_dir():
            db_path = env_dir / "architect.db"
            if db_path.exists():
                databases.append((env_dir.name, db_path))

    return databases


def main():
    databases = find_architect_databases()

    if not databases:
        print("❌ No architect databases found in data/ directory")
        return

    print(f"Found {len(databases)} architect databases:")
    print()

    for env_name, db_path in databases:
        print(f"{'='*80}")
        print(f"Environment: {env_name}")
        print(f"Database: {db_path}")
        print(f"{'='*80}")

        diag = MigrationDiagnostics(str(db_path))

        # Check if migration 004 needs fixing
        try:
            conflict = diag.analyze_migration_003_004_conflict()
        except Exception as e:
            if "no such table: schema_versions" in str(e):
                print("⚠️  Database not initialized (no schema_versions table)")
                print("   Skipping...")
                print()
                continue
            else:
                print(f"❌ Error analyzing database: {e}")
                print()
                continue

        if conflict["milestones_needs_fix"]:
            print("🔴 Migration 004 needs fixing")
            print(
                f"   Missing columns: {conflict['milestones_analysis']['missing_from_autopilot']}"
            )
            print()
            print("Applying fix...")
            try:
                diag.fix_migration_004()
                print("✅ Fixed successfully")
            except Exception as e:
                print(f"❌ Failed to fix: {e}")
        else:
            print("✅ Migration 004 OK - milestones table has autopilot columns")

        print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Re-check all databases
    fixed_count = 0
    ok_count = 0
    failed_count = 0

    for env_name, db_path in databases:
        diag = MigrationDiagnostics(str(db_path))
        try:
            conflict = diag.analyze_migration_003_004_conflict()

            if conflict["milestones_needs_fix"]:
                print(f"❌ {env_name}: Still needs fixing")
                failed_count += 1
            else:
                print(f"✅ {env_name}: OK")
                ok_count += 1
        except Exception as e:
            if "no such table" in str(e):
                print(f"⚠️  {env_name}: Not initialized (skipped)")
            else:
                print(f"❌ {env_name}: Error - {e}")
                failed_count += 1

    print()
    print(f"Total: {len(databases)} databases")
    print(f"  ✅ OK: {ok_count}")
    print(f"  ❌ Failed: {failed_count}")


if __name__ == "__main__":
    main()
