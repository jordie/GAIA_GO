# Storage Cleanup Worker

Automated storage cleanup system for the Architect Dashboard.

## Overview

The cleanup worker manages storage by:
- **Database Backups**: Keeps only the N most recent backups per environment
- **Log Files**: Removes logs older than specified days
- **Task Queue**: Cleans up completed/cancelled tasks
- **Errors**: Removes resolved errors after aging period
- **Assigner Prompts**: Archives old prompts
- **Temp Files**: Removes temporary files and caches

## Quick Start

```bash
# Dry run (safe - shows what would be deleted)
python3 workers/cleanup_worker.py --dry-run

# Actually delete files
python3 workers/cleanup_worker.py --force

# Custom retention (keep 15 backups per environment)
python3 workers/cleanup_worker.py --force --keep 15

# Custom age threshold (delete logs/tasks older than 60 days)
python3 workers/cleanup_worker.py --force --days 60

# Run as background daemon (runs every hour)
python3 workers/cleanup_worker.py --daemon

# Check daemon status
python3 workers/cleanup_worker.py --status

# Stop daemon
python3 workers/cleanup_worker.py --stop
```

## Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Backup Retention** | | |
| - prod | 10 | Keep last 10 backups |
| - qa | 5 | Keep last 5 backups |
| - dev | 5 | Keep last 5 backups |
| - test | 3 | Keep last 3 backups |
| **Log Age** | 30 days | Delete logs older than this |
| **Task Age** | 7 days | Delete completed tasks older than this |
| **Error Age** | 30 days | Delete resolved errors older than this |
| **Prompt Age** | 14 days | Archive prompts older than this |

## API Usage

### Run Cleanup

```bash
# Dry run via API
curl -X POST http://localhost:8080/api/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Actual cleanup
curl -X POST http://localhost:8080/api/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": false,
    "backup_retention": 10,
    "log_age_days": 30,
    "task_age_days": 7,
    "error_age_days": 30,
    "prompt_age_days": 14
  }'
```

### Check Status

```bash
curl http://localhost:8080/api/system/cleanup/status
```

Response:
```json
{
  "success": true,
  "daemon_running": false,
  "daemon_pid": null,
  "last_run": "2026-02-07T19:07:36",
  "last_stats": {
    "backups_deleted": 84,
    "logs_deleted": 0,
    "tasks_deleted": 0,
    "errors_deleted": 0,
    "prompts_deleted": 0,
    "temp_files_deleted": 0,
    "space_freed_mb": 271.93
  }
}
```

## Safety Features

1. **Dry Run Default**: API calls default to dry_run=true to prevent accidental deletion
2. **Recent Backups Protected**: Always keeps the N most recent backups per environment
3. **Active Files Protected**: Never deletes current worker logs or active session files
4. **Chrome Profiles Skipped**: Ignores chrome_profile directories (not our data)
5. **Detailed Logging**: All operations logged to `/tmp/architect_cleanup_worker.log`

## CLI Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would be deleted (safe mode) |
| `--force` | Actually delete files |
| `--days N` | Age threshold for logs/tasks/errors |
| `--keep N` | Number of backups to keep per environment |
| `--daemon` | Run as background daemon (every hour) |
| `--status` | Show daemon status and last run stats |
| `--stop` | Stop the daemon |

## Examples

### Clean up everything older than 90 days

```bash
python3 workers/cleanup_worker.py --force --days 90
```

### Keep only last 20 backups in prod, 10 in dev/qa

Edit `DEFAULT_BACKUP_RETENTION` in the script or use API:

```json
{
  "dry_run": false,
  "backup_retention": {
    "prod": 20,
    "qa": 10,
    "dev": 10,
    "test": 5
  }
}
```

### Schedule with cron

```cron
# Run cleanup every day at 2 AM
0 2 * * * cd /path/to/architect && python3 workers/cleanup_worker.py --force --days 30
```

## Output Example

```
Cleanup Summary:
  Backups deleted: 84
  Logs deleted: 0
  Tasks deleted: 0
  Errors deleted: 0
  Prompts deleted: 0
  Temp files deleted: 0
  Space freed: 271.93 MB
```

## Files

- **Script**: `workers/cleanup_worker.py`
- **PID File**: `/tmp/architect_cleanup_worker.pid`
- **Log File**: `/tmp/architect_cleanup_worker.log`
- **State File**: `/tmp/architect_cleanup_worker_state.json`

## Troubleshooting

### Daemon won't start

```bash
# Check if already running
python3 workers/cleanup_worker.py --status

# Stop stale daemon
python3 workers/cleanup_worker.py --stop

# Check logs
tail -f /tmp/architect_cleanup_worker.log
```

### No files being deleted

- Check that files meet age criteria
- Verify backup counts exceed retention limits
- Use `--dry-run` to see what would be deleted

### Schema errors

The cleanup worker auto-detects table schemas and adapts queries. If you see errors, the table structure may have changed. Check the logs for details.

## Integration with Dashboard

The cleanup system is integrated into the architect dashboard:

1. **System Status**: View cleanup status in system-status endpoint
2. **Manual Trigger**: Trigger cleanup via dashboard UI or API
3. **Activity Logging**: All cleanup operations logged to activity log
4. **Statistics**: Track space freed over time

## Future Enhancements

- [ ] Archive old backups to S3/cloud storage instead of deleting
- [ ] Compress old backups before archiving
- [ ] More granular retention policies (e.g., keep daily for 7 days, weekly for 30 days)
- [ ] Email notifications on cleanup runs
- [ ] Webhooks for cleanup events
- [ ] Dashboard UI panel for cleanup configuration
