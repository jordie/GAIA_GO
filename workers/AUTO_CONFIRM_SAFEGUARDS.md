# Auto-Confirm Worker - Safety Features

## Overview

The auto-confirm worker now includes intelligent safeguards to prevent interference with active sessions while still providing reliable automation.

## New Safety Features

### 1. Session Idle Detection
**Problem**: Auto-confirm was interfering with user typing
**Solution**: Only confirms if session idle >30 seconds

```python
IDLE_THRESHOLD = 30  # Seconds - only confirm if no input for 30s
```

The worker checks `#{pane_activity}` from tmux to determine when the last input occurred.

### 2. Operation Whitelist
**Problem**: Confirming destructive operations automatically was risky
**Solution**: Only auto-confirm safe, read-only operations

```python
SAFE_OPERATIONS = {
    'read',           # Reading files is safe
    'grep',           # Searching is safe
    'glob',           # File pattern matching is safe
    'accept_edits',   # Accepting edits (after review)
}

REQUIRES_APPROVAL = {
    'bash',           # Shell commands can be destructive
    'write',          # Writing files needs care
    'edit',           # Editing files needs care
}
```

Operations in `REQUIRES_APPROVAL` are logged but skipped.

### 3. Dry-Run Mode
**Problem**: Testing changes was risky
**Solution**: Dry-run mode logs what would be confirmed without actually confirming

```python
DRY_RUN = False  # Set to True for testing
```

When enabled, logs show:
```
🔍 DRY RUN - Would confirm: claude_agent1 - read
```

### 4. Kill Switch API
**Problem**: No way to stop auto-confirm remotely
**Solution**: API endpoint to enable/disable auto-confirm

```bash
# Check status
curl http://localhost:8080/api/workers/autoconfirm/kill-switch

# Stop auto-confirm
curl -X POST http://localhost:8080/api/workers/autoconfirm/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Resume auto-confirm
curl -X POST http://localhost:8080/api/workers/autoconfirm/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

The worker checks `/tmp/auto_confirm_kill_switch` every cycle and stops if active.

## Usage

### Start Worker (Safe Mode)
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/workers
./auto_confirm_worker.py
```

### Enable Dry-Run Mode
Edit `auto_confirm_worker.py`:
```python
DRY_RUN = True
```

Then start the worker to see what would be confirmed without actually confirming.

### Customize Safety Settings

#### Adjust Idle Threshold
```python
IDLE_THRESHOLD = 60  # More conservative - 60 seconds idle required
```

#### Add Safe Operations
```python
SAFE_OPERATIONS = {
    'read',
    'grep',
    'glob',
    'accept_edits',
    'plan_confirm',  # Add plan mode confirmations
}
```

#### Exclude Specific Sessions
```python
EXCLUDED_SESSIONS = {
    'autoconfirm',
    'my_active_session',  # Add your active sessions
}
```

## Monitoring

### View Logs
```bash
tail -f /tmp/auto_confirm.log
```

### Sample Log Output
```
[14:23:15] ▶️  Starting monitor cycle (10m 0s)
[14:23:15]    Excluding sessions: autoconfirm
[14:23:15]    ✅ Safe operations: read, grep, glob, accept_edits
[14:23:15]    ⚠️  Requires approval: bash, write, edit
[14:23:20] 📋 claude_agent1: read - read utils.py
[14:23:20]    ⏱️  Confirming in 1.3s
[14:23:21] ✅ Confirmed #1: claude_agent1 (sent '1 (Yes)')
[14:23:45] 📋 claude_agent2: bash - run command
[14:23:45] ⚠️  claude_agent2: Skipping - requires manual approval: bash
[14:23:45]    Command: run command
[14:24:10] 📋 claude_agent3: read - read main.py
[14:24:10] ⏭️  claude_agent3: Skipping - session active (idle: 5s < 30s)
[14:33:15] ⏹️  Cycle complete: 1 confirmations, 1 skipped (active), 1 skipped (unsafe)
```

### Statistics
Query the database:
```bash
sqlite3 /tmp/auto_confirm.db "
SELECT
  session_name,
  total_confirmations,
  datetime(last_confirmation) as last_confirmed
FROM session_stats
ORDER BY total_confirmations DESC
LIMIT 10"
```

## Safety Guarantees

1. ✅ **Never confirms while user is typing** (30s idle threshold)
2. ✅ **Never confirms destructive operations** (whitelist only)
3. ✅ **Can be stopped remotely** (kill switch API)
4. ✅ **Testable without risk** (dry-run mode)
5. ✅ **Full audit trail** (all confirmations logged to DB)

## Troubleshooting

### Worker Not Confirming
1. Check if kill switch is active:
   ```bash
   cat /tmp/auto_confirm_kill_switch
   ```

2. Check if session is idle:
   ```bash
   tmux display-message -t claude_agent1 -p '#{pane_activity}'
   ```

3. Check logs for skip reasons:
   ```bash
   grep "Skipping" /tmp/auto_confirm.log | tail -10
   ```

### False Positives (Confirming Too Much)
1. Increase idle threshold:
   ```python
   IDLE_THRESHOLD = 60  # Require 60s idle
   ```

2. Remove operations from safe list:
   ```python
   SAFE_OPERATIONS = {
       'read',  # Only confirm reads
       'grep',
   }
   ```

### False Negatives (Not Confirming Enough)
1. Add operations to safe list:
   ```python
   SAFE_OPERATIONS = {
       'read', 'grep', 'glob',
       'accept_edits',
       'plan_confirm',  # Add this
   }
   ```

2. Decrease idle threshold:
   ```python
   IDLE_THRESHOLD = 10  # Confirm after 10s idle
   ```

## Migration from Old Version

The new version is backward compatible. No configuration changes required for basic operation.

To enable safety features:
1. Leave defaults (safe operations only)
2. Monitor logs for skipped confirmations
3. Adjust whitelist based on your workflow

## Testing Checklist

Before deploying:
- [ ] Enable dry-run mode
- [ ] Run for 10 minutes
- [ ] Check logs for expected behavior
- [ ] Test kill switch API
- [ ] Verify idle detection works
- [ ] Disable dry-run and deploy

## Version History

**v2.0 (2025-02-04)** - Safety Features
- Added session idle detection
- Added operation whitelist
- Added dry-run mode
- Added kill switch API
- Improved logging

**v1.0** - Original
- Basic auto-confirmation
- Pattern matching
- Database logging
