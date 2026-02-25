# Self-Healing System Documentation

## Overview

The Self-Healing Health Monitor (`health_monitor_v2.py`) automatically detects and repairs common system issues without human intervention.

## Features

### 1. **Worker Auto-Restart**
Monitors critical workers and automatically restarts them if they crash:
- `assigner_worker` - Prompt distribution
- `task_worker` - Background task processing
- `milestone_worker` - Project planning

**Recovery Action:**
```
Worker crashed → Detect → Wait 5s → Restart with original config → Verify
```

### 2. **Stuck Session Detection**
Detects tmux sessions that have been inactive for >30 minutes with assigned tasks:
- Monitors all in-progress tasks
- Checks session activity
- Auto-clears stuck sessions
- Requeues failed tasks

**Recovery Action:**
```
Session stuck >30 min → Detect → Send Ctrl+C → Mark task failed → Alert user
```

### 3. **Database Lock Management**
Detects and clears stale database locks:
- Checks main architect.db
- Checks assigner.db
- Identifies locking processes
- Cleans up WAL/SHM files

**Recovery Action:**
```
DB locked → Detect PIDs → Kill zombies → Remove WAL files → Alert
```

### 4. **Disk Space Cleanup**
Monitors disk usage and auto-cleans when needed:
- Warning at 85% full
- Critical at 95% full
- Cleans logs >7 days old
- Removes temp files >24 hours old

**Recovery Action:**
```
Disk >95% → Detect → Clean old logs → Clean temp files → Report count
```

## Usage

### Run Once (Test Mode)
```bash
python3 workers/health_monitor_v2.py --once
```

### Start as Daemon
```bash
python3 workers/health_monitor_v2.py --daemon
```

### Check Status
```bash
python3 workers/health_monitor_v2.py --status
```

### Stop Daemon
```bash
python3 workers/health_monitor_v2.py --stop
```

## Configuration

Edit these constants in `health_monitor_v2.py`:

```python
CHECK_INTERVAL = 60              # Check every 60 seconds
STUCK_SESSION_TIMEOUT = 1800     # 30 minutes
DISK_CRITICAL_THRESHOLD = 95     # percent
DISK_WARNING_THRESHOLD = 85      # percent
LOG_RETENTION_DAYS = 7
TEMP_FILE_AGE_HOURS = 24
```

## Worker Configuration

Add workers to auto-restart by editing `WORKER_CONFIGS`:

```python
WORKER_CONFIGS = {
    'your_worker': {
        'script': 'workers/your_worker.py',
        'args': ['--daemon'],
        'critical': True,        # Send alerts if down
        'restart_delay': 5       # Wait 5s before restart
    }
}
```

## Monitoring

### Health Metrics Database

All checks and actions are logged to `health_metrics` table:

```sql
SELECT timestamp, component, metric_type, status, action_taken
FROM health_metrics
ORDER BY timestamp DESC
LIMIT 20;
```

### Health Alerts

Critical issues are logged to `health_alerts` table:

```sql
SELECT timestamp, severity, component, message
FROM health_alerts
WHERE resolved = 0
ORDER BY timestamp DESC;
```

## Alert Levels

| Level | Icon | Meaning |
|-------|------|---------|
| **CRITICAL** | 🚨 | Service down, immediate action needed |
| **WARNING** | ⚠️ | Degraded performance, monitor closely |
| **INFO** | ℹ️ | Informational, auto-recovered |

## Recovery Actions Logged

Each recovery action is logged with:
- **Component:** What was affected
- **Metric Type:** What was detected
- **Status:** healthy/unhealthy/error/recovered
- **Action Taken:** What fix was applied
- **Details:** Additional context

## Example Output

```
======================================================================
Health Check #1
======================================================================
🔍 Checking workers...
   Workers: 3/3 healthy

🔍 Checking sessions...
   ⚠️  Found 1 stuck session(s)
      - claude_architect: 45.2 min
   [INFO] Clearing stuck session: claude_architect (task 77)
   ✅ Cleared stuck session claude_architect

🔍 Checking database locks...
   ✅ No database locks

🔍 Checking disk space...
   ⚠️ Disk: 86.9% used (121.0 GB free)

📊 Session Stats:
   Checks run: 1
   Workers restarted: 0
   Sessions cleared: 1
   Locks cleared: 0
   Disk cleanups: 0
   Alerts sent: 1
======================================================================
```

## Integration with Dashboard

View health status on the Architect Dashboard:

```
http://localhost:8080/#health
```

See:
- Real-time health metrics
- Recent alerts
- Recovery history
- System status

## Best Practices

1. **Run as Daemon:** Always run in production
   ```bash
   python3 workers/health_monitor_v2.py --daemon &
   ```

2. **Monitor Logs:** Check logs regularly
   ```bash
   tail -f /tmp/health_monitor_v2.log
   ```

3. **Review Alerts:** Check dashboard for unresolved alerts

4. **Tune Thresholds:** Adjust based on your environment

5. **Test Recovery:** Periodically test with `--once` mode

## Troubleshooting

### Health Monitor Won't Start

```bash
# Check if already running
python3 workers/health_monitor_v2.py --status

# Remove stale PID file
rm /tmp/health_monitor_v2.pid

# Try again
python3 workers/health_monitor_v2.py --daemon
```

### Worker Keeps Crashing

Check the health_metrics table:
```sql
SELECT * FROM health_metrics
WHERE component = 'worker_name'
ORDER BY timestamp DESC
LIMIT 10;
```

### False Positive Stuck Sessions

Increase timeout in configuration:
```python
STUCK_SESSION_TIMEOUT = 3600  # 60 minutes instead of 30
```

## Performance Impact

- **CPU:** <1% average
- **Memory:** ~50-100 MB
- **Disk I/O:** Minimal (checks every 60s)
- **Network:** None

## Limitations

1. **Worker Detection:** Requires unique process names
2. **Session Detection:** Requires assigner database
3. **Lock Clearing:** May not work for all lock types
4. **Disk Cleanup:** Only cleans known patterns

## Future Enhancements

- [ ] Email/Slack notifications
- [ ] Grafana/Prometheus integration
- [ ] ML-based anomaly detection
- [ ] Predictive failure analysis
- [ ] Auto-scaling worker pools
- [ ] Cloud backup before cleanup

## Security Considerations

- **Process Killing:** Only kills zombie processes
- **File Deletion:** Only deletes old logs/temp files
- **Database Access:** Read/write to health tables only
- **Session Interrupts:** Non-destructive (Ctrl+C only)

## Support

For issues or questions:
1. Check logs: `/tmp/health_monitor_v2.log`
2. Review metrics: `health_metrics` table
3. Check alerts: `health_alerts` table
4. Run status: `--status` flag

---

**Version:** 2.0
**Last Updated:** 2026-02-06
**Maintainer:** Architect Dashboard Team
