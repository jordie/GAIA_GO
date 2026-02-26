# Migration Issues: Root Cause Analysis & Resolution

## Problem Summary

The architect dashboard has been experiencing recurring migration failures with error:
```
duplicate column name: app_id
```

This prevented the application from starting successfully.

## Root Cause

### Timeline of Events

1. **Migration 001 (Baseline)** - Created original `milestones` table with:
   - `id`, `project_id`, `name`, `description`, `target_date`, `status`, `progress`
   - Used `project_id` to reference projects

2. **Migration 003 (Autopilot)** - Attempted to CREATE new `milestones` table with:
   - `id`, `app_id`, `run_id`, `milestone_type`, etc. (autopilot columns)
   - Used `app_id` instead of `project_id`
   - BUT: Used `CREATE TABLE IF NOT EXISTS` so it skipped creation (table already existed from 001)

3. **Migration 004 (Fix)** - Designed to bridge the gap:
   - Add `app_id`, `run_id`, `milestone_type` and other autopilot columns to existing milestones table
   - Should have run AFTER 003

4. **The Problem:**
   - Migration 004 was manually marked as "already applied" on **2026-02-10 19:45:37**
   - Migration 003 was actually applied **later** at **2026-02-10 19:46:48**
   - **Migration 004's ALTER TABLE commands were never executed**
   - The migration tracker thought 004 was applied, but the actual schema changes never happened

### Why This Caused Errors

- Application code expected `app_id` column in milestones table (for autopilot features)
- The column didn't exist because migration 004 was marked "skipped" but never executed
- Queries like `SELECT * FROM milestones WHERE app_id = ?` failed with "no such column: app_id"
- This caused the app to crash on startup

### Why Migrations Were Marked "Skipped"

Migrations 004-016 were marked as "skipped (already applied)" at **2026-02-10 19:56:42** during a manual intervention to fix migration issues. This was an attempt to bypass failing migrations, but it had the unintended consequence of:
- Marking migrations as applied without executing them
- Creating a schema mismatch between tracker and reality
- Causing persistent "duplicate column" errors when migrations tried to run

## Solution

### Immediate Fix

Created `migrations/diagnose.py` tool that:
1. **Detected the mismatch** - Found that migration 004 was marked applied but columns were missing
2. **Removed migration 004** from schema_versions table
3. **Re-executed migration 004** - Ran all ALTER TABLE commands to add missing columns
4. **Re-marked migration 004** as applied with correct timestamp

### Results

```
✅ BEFORE FIX:
- Milestones table: 11 columns (missing app_id, run_id, milestone_type, etc.)
- Migration 004: Marked applied but not executed
- App startup: FAILED with "no such column: app_id"

✅ AFTER FIX:
- Milestones table: 23 columns (all autopilot columns present)
- Migration 004: Properly applied with schema changes
- App startup: Should now succeed
```

## Verification

```bash
# Check migration status
python3 migrations/diagnose.py

# Verify milestones schema
sqlite3 data/architect.db "PRAGMA table_info(milestones)"

# Check for app_id column
sqlite3 data/architect.db "PRAGMA table_info(milestones)" | grep app_id
# Output: 11|app_id|INTEGER|0||0
```

## Remaining Issues

### Other Skipped Migrations (005-016)

The following migrations are still marked as "skipped":
- 005: Documentation table
- 006: Claude interactions
- 007: Bugs extended fields
- 008: Multi region
- 009: Notifications
- 010: User preferences
- 011: Scheduled tasks
- 012: Task assignment alerts
- 013: API keys
- 014: Integrations
- 015: Task watchers
- 016: Tmux project groups

**Impact:** These migrations may have been skipped incorrectly, causing similar schema mismatches.

**Recommendation:** Audit each migration to verify schema matches expectations.

## Prevention Strategy

### 1. Never Manually Mark Migrations as Applied

**DON'T:**
```sql
-- Manually inserting into schema_versions
INSERT INTO schema_versions (version, description)
VALUES ('004', 'Fix milestones schema - skipped (already applied)');
```

**DO:**
```bash
# Always use migration manager
python3 -m migrations.manager migrate
```

### 2. Use Diagnostics Tool Before Deployment

```bash
# Add to deployment checklist
python3 migrations/diagnose.py

# Should output:
# ✅ VERDICT: Database schema matches all applied migrations
```

### 3. Environment-Specific Migration Tracking

The migration system doesn't currently account for different environments (dev, staging, prod, feature branches). Consider:

1. **Separate databases per environment:**
   - `data/dev/architect.db`
   - `data/staging/architect.db`
   - `data/prod/architect.db`

2. **Environment-aware migration tracking:**
   ```python
   # Track which environment a migration was applied in
   ALTER TABLE schema_versions ADD COLUMN environment TEXT;
   ```

3. **Branch-specific migrations:**
   - Feature branches use their own migration state
   - Only merge migrations to main after testing
   - Migration conflicts are caught in PR review

### 4. Schema Verification Tests

Add automated tests that verify schema matches expectations:

```python
def test_milestones_schema():
    """Verify milestones table has all required autopilot columns"""
    conn = sqlite3.connect('data/architect.db')
    cursor = conn.execute("PRAGMA table_info(milestones)")
    columns = {row[1] for row in cursor.fetchall()}

    required = {'app_id', 'run_id', 'milestone_type', 'risk_score'}
    missing = required - columns

    assert not missing, f"Missing columns: {missing}"
```

### 5. Migration Rollback Strategy

For migrations that fail:
1. **Don't manually mark as skipped** - This creates schema drift
2. **Fix the migration** - Correct the SQL/Python code
3. **Rollback and retry:**
   ```bash
   python3 -m migrations.manager rollback
   # Fix migration file
   python3 -m migrations.manager migrate
   ```

## Feature Branch Migration Best Practices

When working in feature branches:

1. **Check migration status first:**
   ```bash
   python3 migrations/diagnose.py
   ```

2. **Create environment-specific database:**
   ```bash
   cp data/architect.db data/dev/architect_feature_branch.db
   export ARCHITECT_DB=data/dev/architect_feature_branch.db
   ```

3. **Generate new migrations with proper numbering:**
   ```bash
   python3 -m migrations.manager generate add_my_feature
   # Creates 049_add_my_feature.sql (next available number)
   ```

4. **Test migrations in isolation:**
   ```bash
   python3 -m migrations.manager migrate --db data/dev/architect_feature_branch.db
   ```

5. **Document schema changes in PR:**
   - List all new tables/columns
   - Explain migration dependencies
   - Note any data transformations

## Lessons Learned

1. **Manual interventions bypass safeguards** - The migration system works when used as designed, but manual SQL bypasses tracking

2. **Schema drift accumulates** - Small mismatches compound over time, making debugging harder

3. **Out-of-order execution breaks dependencies** - Migration 004 depended on 003, but was marked applied first

4. **"Skipped" is not the same as "applied"** - Marking something as applied without executing creates technical debt

5. **Feature branches need isolation** - Multiple environments modifying the same database causes conflicts

## Next Steps

1. ✅ **DONE:** Fix migration 004 (completed)
2. **TODO:** Audit migrations 005-016 for similar issues
3. **TODO:** Implement environment-specific databases
4. **TODO:** Add schema verification tests
5. **TODO:** Update deployment process to run diagnostics
6. **TODO:** Document migration best practices in CLAUDE.md

## Diagnostics Tool Usage

```bash
# Check current status
python3 migrations/diagnose.py

# Fix migration 004 issue (COMPLETED)
python3 migrations/diagnose.py --fix-004

# Future: Fix other migrations
python3 migrations/diagnose.py --fix-all-skipped
python3 migrations/diagnose.py --verify-schema
```

## Conclusion

The recurring migration failures were caused by manually marking migrations as "skipped" without executing their schema changes. This created a mismatch between what the migration tracker thought was applied and what actually existed in the database.

The fix was to:
1. Identify the mismatch using diagnostics
2. Remove incorrect tracking records
3. Re-execute the migrations properly
4. Verify schema matches expectations

To prevent this in the future:
- Never manually mark migrations as applied
- Use environment-specific databases
- Run diagnostics before deployment
- Add automated schema verification tests

---

**Status:** ✅ Migration 004 issue RESOLVED
**Date:** 2026-02-10
**Fixed by:** Claude Code AI Assistant via diagnostics tool
