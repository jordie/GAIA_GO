# Migration System Diagnosis Report

**Date:** 2026-02-10
**Status:** Multiple migration issues identified and partially resolved

## Executive Summary

The architect dashboard has recurring migration failures across multiple environment databases. Root cause analysis reveals:

1. **Multiple environment databases** with different migration states
2. **Inconsistent migration APIs** (some use `migrate()`, should use `upgrade()`)
3. **Out-of-order migration tracking** causing "already applied" vs actual schema mismatches
4. **Schema reference issues** in SQL migrations

## Issues Found & Resolutions

### Issue #1: Migration 004 - Duplicate Column Error

**Error:** `duplicate column name: app_id`

**Root Cause:**
- Migration 003 creates `milestones` table with `app_id` (via CREATE TABLE IF NOT EXISTS)
- Migration 004 tries to ALTER TABLE to ADD `app_id` column
- Migration 004 was manually marked as "applied" before actually executing
- When auto-migration runs, it tries to re-apply 004 → duplicate column error

**Affected Databases:**
- ✅ data/architect.db - FIXED
- ✅ data/dev/architect.db - FIXED
- ✅ data/prod/architect.db - Already OK
- ✅ data/env3/architect.db - Already OK
- ✅ data/qa/architect.db - Already OK
- ✅ data/test_suite/architect.db - FIXED

**Resolution:**
- Created `migrations/diagnose.py` tool to detect schema mismatches
- Created `migrations/fix_all_environments.py` to fix all databases
- Fixed by:
  1. Removing migration 004 from schema_versions
  2. Re-executing ALTER TABLE commands
  3. Re-marking as applied with correct timestamp

**Tools Created:**
- `migrations/diagnose.py` - Detect migration mismatches
- `migrations/fix_all_environments.py` - Fix across all environments

### Issue #2: Migration 008 - Missing upgrade Function

**Error:** `Migration 008 missing 'upgrade' function`

**Root Cause:**
- Migration 008 uses `migrate()` and `rollback()` functions
- Migration manager expects `upgrade()` and `downgrade()` functions
- API inconsistency between migration file and migration manager

**Resolution:**
- Renamed `migrate()` → `upgrade()`
- Renamed `rollback()` → `downgrade()`
- Migration now loads successfully

**Status:** ✅ RESOLVED

### Issue #3: Migration 009 - Schema Reference Error

**Error:** `no such column: notification_type`

**Root Cause:**
- Migration 009 (notifications.sql) tries to INSERT data
- References column `notification_type` that may not exist yet
- Likely a table doesn't exist yet or column definition is missing

**Status:** 🔴 IN PROGRESS - requires investigation

### Issue #4: Skipped Migrations (005-016)

**Problem:**
Migrations 005-016 were manually marked as "skipped (already applied)" on 2026-02-10 19:56:42 without actually executing their schema changes.

**Affected Migrations:**
- 005: Documentation table
- 006: Claude interactions
- 007: Bugs extended fields
- 008: Multi region (fixed)
- 009: Notifications (current failure)
- 010: User preferences
- 011: Scheduled tasks
- 012: Task assignment alerts
- 013: API keys
- 014: Integrations
- 015: Task watchers
- 016: Tmux project groups

**Impact:**
These migrations' schema changes may not exist in some databases, causing similar "no such column" or "no such table" errors.

**Status:** ⚠️  NEEDS AUDIT - each migration should be checked for schema mismatches

## Environment-Specific Migration State

### Primary Databases

| Environment | Location | Migration 004 | Status |
|-------------|----------|---------------|--------|
| **Main** | data/architect.db | ✅ Fixed | OK |
| **Dev** | data/dev/architect.db | ✅ Fixed | OK (current failures at 009) |
| **Prod** | data/prod/architect.db | ✅ Already OK | OK |
| **QA** | data/qa/architect.db | ✅ Already OK | OK |
| **Env3** | data/env3/architect.db | ✅ Already OK | OK |
| **Test Suite** | data/test_suite/architect.db | ✅ Fixed | OK |

### Uninitialized Databases (No schema_versions table)

- data/test/architect.db
- data/env1/architect.db
- data/env2/architect.db
- data/feature1/architect.db
- data/feature2/architect.db
- data/feature3/architect.db

**These can be safely ignored** - they're empty test/feature databases that were never fully initialized.

## Root Cause Analysis

### Why Migrations Keep Failing

1. **Manual Intervention Bypass:**
   - Someone manually marked migrations 004-016 as "applied" without executing them
   - This creates permanent schema drift between tracker and reality
   - Each migration failure leads to more manual interventions → more drift

2. **Multiple Environment Databases:**
   - 12+ different database files (main, dev, prod, qa, env1-3, feature1-3, test, test_suite)
   - Each environment can have different migration states
   - Changes in one environment don't propagate to others
   - No centralized migration state tracking

3. **No Environment Isolation:**
   - All environments share the same migration files
   - No way to have environment-specific migrations
   - Feature branches modify shared database causing conflicts

4. **Migration API Inconsistency:**
   - Some migrations use `migrate()` function
   - Migration manager expects `upgrade()` function
   - No validation at migration creation time

5. **Schema Validation Missing:**
   - No automated tests verify schema matches migrations
   - No pre-deployment schema checks
   - Errors only discovered at runtime

## Migration History Timeline

**2026-02-10 Timeline:**
- 15:38:01 - Migrations 001-002 applied to main database
- 19:45:37 - Migration 004 manually marked "skipped (already applied)" - **WRONG**
- 19:46:48 - Migration 003 actually applied (after 004!) - **OUT OF ORDER**
- 19:56:42 - Migrations 005-016 manually marked "skipped" in batch - **SCHEMA DRIFT BEGINS**
- 22:56:33 - Migration 004 properly fixed and re-applied (main DB)
- 15:27:10 - Migration 008 fixed (API issue resolved)
- **Current:** Migration 009 failing on dev database

## Recommendations

### Immediate Actions

1. **Continue with non-fatal migrations:**
   - Don't block app startup on migration failures
   - Log migration errors but continue
   - Alert user/admin about pending migrations

2. **Audit migrations 009-017:**
   - Check each SQL file for schema references
   - Verify tables/columns exist before INSERT/UPDATE
   - Test in isolated database first

3. **Fix migration 009:**
   - Investigate the notifications table schema
   - Check if notification_type column exists
   - Add IF NOT EXISTS checks or reorder statements

### Short-term Fixes

1. **Add migration bypass flag:**
   ```bash
   python3 app.py --skip-migrations
   # Or environment variable
   export ARCHITECT_SKIP_MIGRATIONS=true
   ```

2. **Run migrations manually:**
   ```bash
   python3 -m migrations.manager status
   python3 -m migrations.manager migrate
   ```

3. **Use diagnostics before deployment:**
   ```bash
   python3 migrations/diagnose.py
   python3 migrations/fix_all_environments.py
   ```

### Long-term Solutions

1. **Environment-Specific Databases:**
   ```
   data/
     dev/architect.db
     staging/architect.db
     prod/architect.db
   ```

2. **Migration Validation:**
   - Add `--validate` flag to generate command
   - Check for required functions (upgrade/downgrade)
   - Verify SQL syntax before committing

3. **Schema Verification Tests:**
   ```python
   def test_schema_matches_migrations():
       """Verify database schema matches all applied migrations"""
       conn = get_db()
       expected_tables = get_expected_tables_from_migrations()
       actual_tables = get_actual_tables(conn)
       assert expected_tables == actual_tables
   ```

4. **Migration Locking:**
   - Prevent concurrent migrations
   - Lock database during migration
   - Atomic transaction for all migration steps

5. **Rollback Strategy:**
   - Test downgrade functions
   - Keep backups before migrations
   - Document rollback procedures

## Next Steps

**Priority 1 - Critical (App won't start):**
- [ ] Fix migration 009 schema reference issue
- [ ] Add --skip-migrations flag to app.py
- [ ] Test app startup with migrations disabled

**Priority 2 - High (Recurring issues):**
- [ ] Audit migrations 010-017 for similar issues
- [ ] Create migration validation tool
- [ ] Document migration best practices in CLAUDE.md

**Priority 3 - Medium (Prevention):**
- [ ] Implement environment-specific databases
- [ ] Add schema verification tests
- [ ] Create migration API validator

**Priority 4 - Low (Nice to have):**
- [ ] Migration rollback testing
- [ ] Automated schema documentation
- [ ] Migration performance profiling

## Tools & Commands

### Check Migration Status
```bash
# Main database
python3 migrations/diagnose.py

# Specific environment
python3 migrations/diagnose.py --db data/dev/architect.db

# All environments
python3 migrations/fix_all_environments.py
```

### Manual Migration Management
```bash
# Check status
python3 -m migrations.manager status

# Run pending migrations
python3 -m migrations.manager migrate

# Generate new migration
python3 -m migrations.manager generate my_feature

# Rollback last migration
python3 -m migrations.manager rollback
```

### Fix Specific Issues
```bash
# Fix migration 004
python3 migrations/diagnose.py --fix-004

# Fix all environments
python3 migrations/fix_all_environments.py
```

## Lessons Learned

1. **Never manually mark migrations as applied** - Always use migration manager
2. **Test migrations in isolation** - Use separate test database
3. **Verify schema after each migration** - Automated tests catch issues early
4. **Document environment strategy** - Clear separation prevents conflicts
5. **API consistency matters** - Standardize on upgrade/downgrade naming
6. **Schema drift accumulates** - Small issues compound over time
7. **Manual interventions create debt** - Bypass protections = future problems

## Current Status

**✅ Fixed:**
- Migration 004: Duplicate column error across all initialized databases
- Migration 008: Missing upgrade function API issue

**🔴 Failing:**
- Migration 009: Schema reference error (notification_type column)

**⚠️  Needs Audit:**
- Migrations 010-048: Unknown state, may have similar issues

**📊 Database Status:**
- 6 databases fully functional (migration 004+ fixed)
- 6 databases uninitialized (can be ignored)
- 1 database (dev) currently failing at migration 009

**🎯 Goal:**
Get app starting successfully with option to skip failing migrations, then fix migrations incrementally.

---

**Next Update:** After fixing migration 009 or implementing migration bypass
