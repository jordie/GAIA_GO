# Migration System Documentation

## Overview

The Architect Dashboard uses a structured migration system to evolve the database schema across different environments (dev → qa → prod) in a controlled, traceable manner.

## Architecture

### Components

1. **Migration Manager** (`migrations/manager.py`)
   - Discovers and applies pending migrations
   - Tracks applied migrations in `schema_versions` table
   - Creates automatic backups before migrations
   - Supports both Python (.py) and SQL (.sql) migrations

2. **Migration Files** (`migrations/[0-9][0-9][0-9]_*.{py,sql}`)
   - Sequential numbering (001, 002, 003, ...)
   - Descriptive names (e.g., `002_add_testing.py`)
   - Self-contained and idempotent when possible

3. **Schema Versions Table** (in each database)
   - Tracks which migrations have been applied
   - Stores version, description, checksum, and timestamp
   - Prevents duplicate application of migrations

## Migration Flow Across Environments

```
┌─────────────────────────────────────────────────────────────┐
│                    Development (dev)                         │
│  - Developer creates new migration file                      │
│  - Tests locally on dev database                             │
│  - Commits migration to version control                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ git push
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Code Repository (GitHub)                  │
│  - Migration file stored in migrations/ directory            │
│  - Version controlled and code reviewed                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ deploy to QA
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    QA Environment (qa)                       │
│  - App startup runs auto_migrate()                           │
│  - Migration manager detects new migration                   │
│  - Creates backup: data/prod/backups/architect_YYYYMMDD.db   │
│  - Applies migration                                         │
│  - Records in schema_versions table                          │
│  - QA team validates changes                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ promote to prod
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Production (prod)                         │
│  - App startup runs auto_migrate()                           │
│  - Same migration applied automatically                      │
│  - Backup created before application                         │
│  - Migration tracked in schema_versions                      │
└─────────────────────────────────────────────────────────────┘
```

## Database Locations Per Environment

| Environment | Database Path | Notes |
|-------------|---------------|-------|
| **dev** | `data/architect.db` | Local development database |
| **qa** | `data/prod/architect.db` | Shared QA database (may use separate server) |
| **prod** | `data/prod/architect.db` | Production database (separate server) |

## How Auto-Migration Works

When the app starts (`app.py` initialization):

```python
from migrations.manager import auto_migrate

# Auto-migrate on startup
result = auto_migrate('data/prod/architect.db')
# result = {'status': 'migrated', 'applied': ['034', '035'], 'count': 2}
```

**Step-by-step:**

1. **Discover Pending Migrations**
   - Scans `migrations/` directory for `[0-9][0-9][0-9]_*.{py,sql}` files
   - Compares against `schema_versions` table in database
   - Identifies migrations not yet applied

2. **Create Backup**
   - Copies database to `data/prod/backups/architect_YYYYMMDD_HHMMSS.db`
   - Ensures rollback capability if migration fails

3. **Apply Migrations (Sequential)**
   - Migrations applied in version number order (001, 002, 003, ...)
   - SQL migrations: Execute via `executescript()`
   - Python migrations: Import module and call `upgrade(conn)` function

4. **Track Application**
   - Insert record into `schema_versions` table
   - Includes: version, description, checksum, timestamp

5. **Handle Errors**
   - If migration fails, process stops
   - Database remains in pre-migration state (backup available)
   - Error logged with details for manual intervention

## Migration File Types

### SQL Migrations

**Example:** `003_autopilot_orchestration.sql`

```sql
-- Migration description (first line comment becomes description)

CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    ...
);

CREATE INDEX IF NOT EXISTS idx_apps_status ON apps(status);
```

**Pros:**
- Simple and readable
- Direct SQL execution
- Fast for schema-only changes

**Cons:**
- Cannot rollback automatically
- Limited conditional logic
- No data transformation capabilities

### Python Migrations

**Example:** `002_add_testing.py`

```python
"""
Migration 002: Add Testing Framework
"""

DESCRIPTION = "Add testing framework and deployment tracking tables"

def upgrade(conn):
    """Apply the migration."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY,
            ...
        )
    """)
    conn.commit()

def downgrade(conn):
    """Rollback the migration (optional)."""
    conn.execute("DROP TABLE IF EXISTS test_runs")
    conn.commit()
```

**Pros:**
- Conditional logic (check if columns exist before adding)
- Data transformation and migration
- Rollback support via `downgrade()` function

**Cons:**
- More complex
- Requires Python knowledge
- Slightly slower execution

## Best Practices

### 1. Create Migrations for Schema Changes

**Always create a migration for:**
- New tables
- New columns
- Index changes
- Foreign key changes
- Column type changes
- Default value changes

**Never manually edit the database in production**

### 2. Test Migrations Locally First

```bash
# Check pending migrations
python3 -m migrations.manager pending --db data/architect.db

# Apply migrations manually
python3 -m migrations.manager migrate --db data/architect.db

# Check status
python3 -m migrations.manager status --db data/architect.db
```

### 3. Make Migrations Idempotent

Use `IF NOT EXISTS` and `IF EXISTS` clauses:

```sql
CREATE TABLE IF NOT EXISTS my_table (...);
CREATE INDEX IF NOT EXISTS idx_my_column ON my_table(my_column);
ALTER TABLE my_table ADD COLUMN my_col TEXT; -- Will fail if column exists
```

For Python migrations, check before altering:

```python
def upgrade(conn):
    cursor = conn.execute("PRAGMA table_info(my_table)")
    columns = {row[1] for row in cursor.fetchall()}

    if "new_column" not in columns:
        conn.execute("ALTER TABLE my_table ADD COLUMN new_column TEXT")
```

### 4. Sequential Numbering

- Use 3-digit version numbers: 001, 002, ..., 099, 100
- Never reuse version numbers
- Never rename applied migrations
- Keep gaps for hotfixes if needed (e.g., use 005, 010, 015 instead of 001, 002, 003)

### 5. Descriptive Names

Good naming:
- `002_add_testing.py` - Clear purpose
- `015_task_watchers.sql` - Feature name
- `034_session_entity_tracking.sql` - Specific change

Bad naming:
- `002_update.sql` - Too vague
- `003_fix.py` - What fix?
- `004_new_stuff.sql` - Not descriptive

### 6. Document Complex Migrations

Add comments to migration files:

```python
"""
Migration 008: Add Multi-Region Support

Adds region-based routing and node assignment:
- Adds 'region' column to nodes table
- Creates region_config table
- Migrates existing nodes to 'default' region
"""
```

## Deployment Workflow

### Standard Deployment (dev → qa → prod)

1. **Development**
   ```bash
   # Create migration
   python3 -m migrations.manager generate add_feature_x

   # Edit migration file
   vim migrations/048_add_feature_x.sql

   # Test locally
   python3 -m migrations.manager migrate

   # Commit
   git add migrations/048_add_feature_x.sql
   git commit -m "feat: Add feature X (migration 048)"
   git push origin dev
   ```

2. **QA Deployment**
   ```bash
   # On QA server
   git pull origin dev
   ./deploy.sh  # Auto-migrates on startup

   # Verify
   curl http://localhost:8080/health | jq '.database'
   ```

3. **Production Deployment**
   ```bash
   # On prod server
   git pull origin main
   ./deploy.sh  # Auto-migrates on startup

   # Monitor
   tail -f /tmp/architect_dashboard.log
   ```

### Hotfix Workflow (emergency prod fix)

1. **Create Fix Migration on Prod**
   ```bash
   # On prod server
   python3 -m migrations.manager generate hotfix_issue_123

   # Edit and apply
   python3 -m migrations.manager migrate
   ```

2. **Backport to Dev**
   ```bash
   # Copy migration file back to dev
   scp prod:/path/to/migrations/049_hotfix.sql migrations/
   git add migrations/049_hotfix.sql
   git commit -m "hotfix: Apply prod hotfix (migration 049)"
   git push
   ```

## Rollback Procedures

### Python Migrations with downgrade()

```bash
python3 -m migrations.manager rollback --db data/prod/architect.db
```

### SQL Migrations (Manual Rollback)

SQL migrations cannot rollback automatically. Manual steps:

1. **Restore from Backup**
   ```bash
   cp data/prod/backups/architect_20260209_202525.db data/prod/architect.db
   ```

2. **Remove Migration from Tracking**
   ```bash
   sqlite3 data/prod/architect.db "DELETE FROM schema_versions WHERE version='048'"
   ```

3. **Restart App**
   ```bash
   ./deploy.sh
   ```

## Troubleshooting

### "Migration X failed: duplicate column name"

**Cause:** Column already exists (migration previously applied but not tracked)

**Fix:**
```bash
# Mark as applied
sqlite3 data/prod/architect.db \
  "INSERT INTO schema_versions (version, description, checksum)
   VALUES ('048', 'Manual skip', 'manual');"
```

### "No such table: schema_versions"

**Cause:** Database missing migration tracking table

**Fix:**
```bash
python3 -m migrations.manager migrate --db data/prod/architect.db
# This will create schema_versions and apply all migrations
```

### "Migration X modifies different files than expected"

**Cause:** Duplicate version numbers (multiple files with same version)

**Fix:** Renumber duplicate migrations (see RENUMBER_PLAN.md)

### "Database locked"

**Cause:** Another process has database open

**Fix:**
```bash
# Stop dashboard
./deploy.sh stop

# Apply migration
python3 -m migrations.manager migrate

# Restart
./deploy.sh
```

## Migration Checklist

Before creating a migration:

- [ ] Schema change is necessary and well-designed
- [ ] Migration file has unique version number
- [ ] Migration file has descriptive name
- [ ] SQL uses `IF NOT EXISTS` / `IF EXISTS` where possible
- [ ] Python migration checks for existing columns/tables
- [ ] Migration tested on local dev database
- [ ] Migration has clear comments/documentation
- [ ] Migration committed to version control
- [ ] Team notified of schema change

Before deploying to prod:

- [ ] Migration tested in dev environment
- [ ] Migration tested in qa environment
- [ ] Backup plan in place (restore procedure documented)
- [ ] Rollback plan documented (if not automatic)
- [ ] Team aware of deployment window
- [ ] Monitoring in place to detect issues

## Advanced Topics

### Custom Migration Functions

You can add helper functions to migrations:

```python
def table_exists(conn, table_name):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def upgrade(conn):
    if not table_exists(conn, 'my_new_table'):
        conn.execute("CREATE TABLE my_new_table (...)")
```

### Data Migrations

Migrate data along with schema:

```python
def upgrade(conn):
    # Add new column
    conn.execute("ALTER TABLE users ADD COLUMN region TEXT DEFAULT 'us-east-1'")

    # Migrate data based on business logic
    conn.execute("""
        UPDATE users
        SET region = 'eu-west-1'
        WHERE email LIKE '%@example.eu'
    """)

    conn.commit()
```

### Conditional Migrations

Apply different changes based on environment:

```python
import os

def upgrade(conn):
    env = os.environ.get('ENV', 'dev')

    if env == 'prod':
        # Production-specific migration
        conn.execute("CREATE INDEX idx_heavy ON large_table(column)")
    else:
        # Skip expensive index in dev/qa
        pass
```

## See Also

- `migrations/RENUMBER_PLAN.md` - Migration renumbering documentation
- `migrations/manager.py` - Migration manager source code
- `CLAUDE.md` - Project-wide development guidelines
