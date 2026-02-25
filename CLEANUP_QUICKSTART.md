# Storage Cleanup - Quick Reference

## Quick Commands

```bash
# See what would be deleted (SAFE)
python3 workers/cleanup_worker.py --dry-run

# Actually delete files
python3 workers/cleanup_worker.py --force

# Keep more backups (20 per environment)
python3 workers/cleanup_worker.py --force --keep 20

# Longer retention (90 days for logs/tasks)
python3 workers/cleanup_worker.py --force --days 90

# Run every hour in background
python3 workers/cleanup_worker.py --daemon

# Check daemon status
python3 workers/cleanup_worker.py --status

# Stop daemon
python3 workers/cleanup_worker.py --stop
```

## What Gets Cleaned

| Type | Default Retention | Location |
|------|-------------------|----------|
| **Prod Backups** | Last 10 | `data/prod/backups/` |
| **QA Backups** | Last 5 | `data/qa/backups/` |
| **Dev Backups** | Last 5 | `data/dev/backups/` |
| **Logs** | >30 days | `data/`, `/tmp/` |
| **Completed Tasks** | >7 days | Database |
| **Resolved Errors** | >30 days | Database |
| **Old Prompts** | >14 days | Archived in DB |
| **Temp Files** | All | `*.tmp`, `*.cache`, etc. |

## API Endpoints

```bash
# Dry run
curl -X POST http://localhost:8080/api/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Full cleanup
curl -X POST http://localhost:8080/api/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'

# Status
curl http://localhost:8080/api/system/cleanup/status
```

## Results from Initial Run

```
Before:  693 MB
After:   417 MB
Freed:   276 MB (39.8% reduction)

- Deleted 84 old backup files
- Freed 271.93 MB
- Kept 10 most recent backups in prod
```

## Safety

✓ Dry-run mode by default (CLI and API)
✓ Never deletes active worker logs
✓ Schema-aware (won't break on DB changes)
✓ Protected files list (chrome_profile, etc.)
✓ Detailed logging to `/tmp/architect_cleanup_worker.log`

## Schedule with Cron

```cron
# Every day at 2 AM
0 2 * * * cd /path/to/architect && python3 workers/cleanup_worker.py --force --days 30

# Every week on Sunday
0 3 * * 0 cd /path/to/architect && python3 workers/cleanup_worker.py --force --keep 10
```

## Files

- **Worker**: `workers/cleanup_worker.py`
- **Docs**: `workers/CLEANUP_README.md`
- **Tests**: `test_cleanup_api.py`
- **Logs**: `/tmp/architect_cleanup_worker.log`
- **State**: `/tmp/architect_cleanup_worker_state.json`

## Troubleshooting

```bash
# Check what would be deleted
python3 workers/cleanup_worker.py --dry-run

# View logs
tail -f /tmp/architect_cleanup_worker.log

# Check daemon
ps aux | grep cleanup_worker

# Kill stale daemon
python3 workers/cleanup_worker.py --stop
```
