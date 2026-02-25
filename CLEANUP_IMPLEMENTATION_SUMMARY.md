# Storage Cleanup System - Implementation Summary

## Overview

Implemented a comprehensive storage cleanup system for the Architect Dashboard to manage growing data directory size (reduced from ~693MB to 417MB, freeing 276MB).

## Components Created

### 1. Cleanup Worker (`workers/cleanup_worker.py`)

A standalone Python worker that performs automated storage cleanup operations.

**Features:**
- Database backup retention (configurable per environment)
- Log file rotation and cleanup
- Task queue cleanup (old completed/cancelled tasks)
- Error cleanup (old resolved errors)
- Assigner prompt archival
- Temporary file cleanup
- Dry-run mode for safe testing
- Daemon mode for automated recurring cleanup
- Comprehensive statistics tracking

**Key Classes:**
- `CleanupStats`: Tracks cleanup statistics (files deleted, space freed)
- `CleanupWorker`: Main cleanup orchestrator

**Safety Features:**
- Schema-aware queries (adapts to database structure)
- Protected files (never deletes active worker logs)
- Chrome profile exclusion
- Dry-run default mode
- Detailed logging

### 2. API Endpoints

Added two new REST endpoints to `app.py`:

#### POST /api/system/cleanup
Execute cleanup operations with configurable parameters.

**Request Body:**
```json
{
  "dry_run": true,
  "backup_retention": 10,
  "log_age_days": 30,
  "task_age_days": 7,
  "error_age_days": 30,
  "prompt_age_days": 14
}
```

**Response:**
```json
{
  "success": true,
  "dry_run": true,
  "stats": {
    "backups_deleted": 84,
    "logs_deleted": 0,
    "tasks_deleted": 0,
    "errors_deleted": 0,
    "prompts_deleted": 0,
    "temp_files_deleted": 0,
    "space_freed_mb": 271.93
  },
  "message": "Cleanup completed"
}
```

#### GET /api/system/cleanup/status
Get cleanup daemon status and last run statistics.

**Response:**
```json
{
  "success": true,
  "daemon_running": false,
  "daemon_pid": null,
  "last_run": "2026-02-07T19:07:36",
  "last_stats": {
    "backups_deleted": 84,
    "space_freed_mb": 271.93
  }
}
```

### 3. Documentation

Created comprehensive documentation:
- `workers/CLEANUP_README.md` - Full usage guide
- `test_cleanup_api.py` - API testing script
- This summary document

## Cleanup Operations

### Database Backups

**Location:** `data/{env}/backups/`

**Retention Policy:**
- prod: Keep last 10 backups
- qa: Keep last 5 backups
- dev: Keep last 5 backups
- test: Keep last 3 backups

**How it works:**
1. Scans backup directories per environment
2. Sorts backups by modification time (newest first)
3. Keeps N most recent, deletes the rest
4. Tracks space freed

**Example cleanup:**
- Before: 93 backups in prod (346 MB)
- After: 10 backups in prod (68 MB)
- **Freed: 278 MB**

### Log Files

**Age Threshold:** 30 days (default)

**Cleaned Locations:**
- `data/` directory
- `/tmp/` (architect logs only)
- `logs/` directory

**Protected Logs:**
- Active worker logs (architect_*_worker.log)
- Chrome profile logs (not ours)

### Task Queue

**Age Threshold:** 7 days (default)

**What's Cleaned:**
- Completed tasks older than threshold
- Cancelled tasks older than threshold
- Failed tasks older than threshold

**Schema-Aware:**
- Auto-detects table structure
- Adapts queries to available columns

### Errors

**Age Threshold:** 30 days (default)

**What's Cleaned:**
- Resolved errors older than threshold

**Safety:**
- Only deletes if table has `resolved` and `resolved_at` columns
- Preserves unresolved errors indefinitely

### Assigner Prompts

**Age Threshold:** 14 days (default)

**What's Cleaned:**
- Archives (not deletes) old prompts
- Sets `archived = 1` and `archived_at` timestamp
- Preserves history for auditing

### Temporary Files

**Patterns Cleaned:**
- `*.tmp`
- `*.temp`
- `*.cache`
- `__pycache__`
- `.pytest_cache`
- `*.pyc`

**Exclusions:**
- Chrome profiles (not our data)

## Usage Examples

### CLI Usage

```bash
# Safe dry-run to see what would be deleted
python3 workers/cleanup_worker.py --dry-run

# Actually delete files
python3 workers/cleanup_worker.py --force

# Keep more backups (15 per environment)
python3 workers/cleanup_worker.py --force --keep 15

# Longer retention for logs/tasks (60 days)
python3 workers/cleanup_worker.py --force --days 60

# Run as daemon (every hour)
python3 workers/cleanup_worker.py --daemon

# Check status
python3 workers/cleanup_worker.py --status

# Stop daemon
python3 workers/cleanup_worker.py --stop
```

### API Usage

```bash
# Dry run
curl -X POST http://localhost:8080/api/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Actual cleanup with custom settings
curl -X POST http://localhost:8080/api/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": false,
    "backup_retention": 15,
    "log_age_days": 60,
    "task_age_days": 14
  }'

# Check status
curl http://localhost:8080/api/system/cleanup/status
```

### Python Usage

```python
from cleanup_worker import CleanupWorker

# Create worker
worker = CleanupWorker(
    dry_run=True,
    backup_retention={'prod': 15, 'qa': 10, 'dev': 10},
    log_age_days=60,
    task_age_days=14
)

# Run cleanup
stats = worker.run_cleanup()

print(f"Freed {stats.space_freed / (1024*1024)} MB")
print(f"Deleted {stats.backups_deleted} backups")
```

## Results

### Initial Cleanup Run

```
Storage Before:  693 MB
Storage After:   417 MB
Space Freed:     276 MB (39.8% reduction)

Breakdown:
- Backups deleted: 84 files
- Space freed:     271.93 MB
- Prod backups:    346 MB → 68 MB
- Retention:       93 backups → 10 backups
```

### Maintenance

Running cleanup again shows proper retention:
```
Cleanup Summary:
  Backups deleted: 0
  Logs deleted: 0
  Tasks deleted: 0
  Errors deleted: 0
  Prompts deleted: 0
  Temp files deleted: 0
  Space freed: 0.0 MB
```

This confirms the system maintains the retention policy correctly.

## Files

### Created
- `workers/cleanup_worker.py` - Main cleanup worker (665 lines)
- `workers/CLEANUP_README.md` - Usage documentation
- `test_cleanup_api.py` - API test script
- `CLEANUP_IMPLEMENTATION_SUMMARY.md` - This file

### Modified
- `app.py` - Added cleanup API endpoints (~100 lines)

### State Files
- `/tmp/architect_cleanup_worker.pid` - Daemon PID
- `/tmp/architect_cleanup_worker.log` - Worker logs
- `/tmp/architect_cleanup_worker_state.json` - Last run state

## Integration Points

1. **System Status**: Cleanup status visible in `/api/system-status` endpoint
2. **Activity Log**: All cleanup operations logged to activity_log table
3. **Dashboard UI**: Can trigger cleanup via API (future: add UI panel)
4. **Cron/Scheduled**: Can schedule with cron or run as daemon

## Future Enhancements

- [ ] Archive old backups to S3/cloud before deleting
- [ ] Compress backups before archiving
- [ ] Granular retention (daily for 7 days, weekly for 30 days, etc.)
- [ ] Email notifications on cleanup runs
- [ ] Webhooks for cleanup events
- [ ] Dashboard UI panel for cleanup configuration
- [ ] More cleanup targets (session logs, orphaned files, etc.)
- [ ] Cleanup reports/analytics

## Testing

### Test Script
```bash
python3 test_cleanup_api.py
```

Tests:
1. ✓ Cleanup status endpoint
2. ✓ Cleanup dry-run
3. ✓ Cleanup with custom settings

### Manual Testing
```bash
# Test dry-run
python3 workers/cleanup_worker.py --dry-run

# Test actual cleanup
python3 workers/cleanup_worker.py --force

# Test daemon
python3 workers/cleanup_worker.py --daemon &
python3 workers/cleanup_worker.py --status
python3 workers/cleanup_worker.py --stop
```

## Configuration

Default settings in `cleanup_worker.py`:

```python
DEFAULT_BACKUP_RETENTION = {
    'prod': 10,
    'qa': 5,
    'dev': 5,
    'test': 3,
    'default': 5
}

DEFAULT_LOG_AGE_DAYS = 30
DEFAULT_TASK_AGE_DAYS = 7
DEFAULT_ERROR_AGE_DAYS = 30
DEFAULT_PROMPT_AGE_DAYS = 14
CLEANUP_INTERVAL = 3600  # 1 hour for daemon mode
```

These can be overridden via:
- CLI arguments (`--keep`, `--days`)
- API request body
- Editing the worker file

## Troubleshooting

### Schema Errors
The worker auto-detects table schemas and adapts. If errors occur:
1. Check logs: `/tmp/architect_cleanup_worker.log`
2. Verify database schema matches expected structure
3. Worker will skip operations on missing tables/columns

### No Files Deleted
Common causes:
- Files don't meet age criteria (check thresholds)
- Backup counts below retention limits
- Files are protected (active logs, etc.)

Use `--dry-run` to see what would be deleted.

### Daemon Issues
```bash
# Check status
python3 workers/cleanup_worker.py --status

# Check logs
tail -f /tmp/architect_cleanup_worker.log

# Kill stale daemon
python3 workers/cleanup_worker.py --stop
```

## Security

- **Authentication Required**: API endpoints require login
- **Activity Logging**: All operations logged with user context
- **Dry-run Default**: API defaults to dry_run=true
- **Protected Files**: Never deletes active system files
- **Validation**: Input sanitization and validation

## Performance

- **Fast Scanning**: Uses glob patterns for efficient file discovery
- **Minimal DB Load**: Schema detection cached, efficient queries
- **Low Resource**: Runs independently, doesn't block main app
- **Progress Tracking**: Real-time logging of operations

## Conclusion

The storage cleanup system successfully:
- ✓ Reduced storage from 693MB to 417MB (39.8% reduction)
- ✓ Automated backup retention management
- ✓ Provided safe dry-run testing
- ✓ Integrated with dashboard API
- ✓ Maintained data integrity and safety
- ✓ Documented comprehensively

The system is production-ready and can be scheduled for recurring cleanup or run on-demand via API.
