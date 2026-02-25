# Assigner Worker Cleanup Guide

## Problem Summary

The assigner worker has 15 failed prompts because it's trying to assign tasks to tmux sessions that no longer exist (primarily "test-claude"). This causes errors like:

```
Failed to assign prompt X: tmux send-keys failed: can't find pane: test-claude
```

## Root Causes

1. **Stale Session Data**: The database contains references to tmux sessions that no longer exist
2. **No Real-Time Verification**: The assigner doesn't verify a session exists before trying to send to it
3. **Failed Prompt Accumulation**: Failed prompts aren't automatically reset when the target session is invalid

## Cleanup Process

### Step 1: Analyze the Database (Dry Run)

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
python3 workers/cleanup_assigner.py
```

This will show you:
- Active tmux sessions
- Stale sessions in the database
- Failed prompts and what they were targeting
- What would be cleaned (without actually changing anything)

### Step 2: Apply Cleanup

```bash
python3 workers/cleanup_assigner.py --apply
```

This will:
- Remove stale sessions from the database
- Free up any tasks assigned to those sessions
- Reset failed prompts that targeted non-existent sessions

### Step 3: Retry Failed Prompts

```bash
python3 workers/cleanup_assigner.py --retry-failed --apply
```

This will:
- Queue all failed prompts for retry (that haven't exceeded max retries)
- Clear the error messages
- Reset them to pending status

### Step 4: Verify and Monitor

```bash
# Check status
python3 workers/assigner_worker.py --status

# Monitor logs
tail -f /tmp/architect_assigner_worker.log

# List current sessions
python3 workers/assigner_worker.py --sessions

# List current prompts
python3 workers/assigner_worker.py --prompts
```

## Prevention (Future Improvements)

### Recommended Code Changes

**File**: `workers/assigner_worker.py`

**Change 1**: Add real-time session verification in `_assign_prompt()` (line ~1253)

```python
def _assign_prompt(self, prompt: Dict, session_name: str):
    prompt_id = prompt["id"]
    content = prompt["content"]

    # VERIFY SESSION EXISTS BEFORE ASSIGNMENT
    current_sessions = self.detector.list_sessions()
    if session_name not in current_sessions:
        logger.warning(f"Session {session_name} not found, re-scanning...")
        self._scan_sessions()

        # Check again after re-scan
        current_sessions = self.detector.list_sessions()
        if session_name not in current_sessions:
            logger.error(f"Session {session_name} does not exist, marking prompt as failed")
            self.db.update_prompt_status(
                prompt_id,
                PromptStatus.FAILED,
                error=f"Target session '{session_name}' not found in tmux"
            )
            return

    # ... rest of existing code ...
```

**Change 2**: Auto-cleanup stale sessions during scan (line ~1141)

```python
def _scan_sessions(self):
    """Scan all tmux sessions and update database."""
    logger.debug("Scanning sessions...")
    sessions = self.detector.scan_all_sessions()
    current_session_names = {s.name for s in sessions}

    # Get existing sessions from DB
    existing = self.db.get_all_sessions()

    # Remove stale sessions (in DB but not in tmux)
    for db_session in existing:
        if db_session["name"] not in current_session_names:
            logger.info(f"Removing stale session: {db_session['name']}")
            with self.db._get_conn() as conn:
                # Free any assigned tasks
                if db_session.get("current_task_id"):
                    conn.execute(
                        "UPDATE prompts SET status = 'pending', assigned_session = NULL "
                        "WHERE id = ? AND status IN ('assigned', 'in_progress')",
                        (db_session["current_task_id"],)
                    )
                # Delete stale session
                conn.execute("DELETE FROM sessions WHERE name = ?", (db_session["name"],))

    # ... rest of existing code ...
```

## Quick Reference

### Cleanup Commands

```bash
# Analysis only (dry run)
python3 workers/cleanup_assigner.py

# Apply cleanup
python3 workers/cleanup_assigner.py --apply

# Retry failed prompts
python3 workers/cleanup_assigner.py --retry-failed --apply

# Just verify database integrity
python3 workers/cleanup_assigner.py --verify-only
```

### Monitoring Commands

```bash
# Check worker status
python3 workers/assigner_worker.py --status

# List sessions
python3 workers/assigner_worker.py --sessions

# List prompts
python3 workers/assigner_worker.py --prompts

# Watch logs
tail -f /tmp/architect_assigner_worker.log

# Restart worker
python3 workers/assigner_worker.py --stop
python3 workers/assigner_worker.py --daemon
```

### Manual Prompt Management

```bash
# Retry specific prompt
python3 workers/assigner_worker.py --retry 159

# Retry all failed
python3 workers/assigner_worker.py --retry-all

# Cancel a prompt
python3 workers/assigner_worker.py --cancel 170

# Clear old completed prompts
python3 workers/assigner_worker.py --clear --days 7
```

## Expected Results

After cleanup:
- **Pending prompts**: ~15 (the failed ones will be reset to pending)
- **Active assignments**: 0 or 1 (depending on current work)
- **Failed prompts**: 0
- **Available sessions**: Only sessions that actually exist in tmux
- **Database**: Consistent with tmux reality

## Troubleshooting

### If prompts still fail after cleanup:

1. **Check which session they're targeting**:
   ```bash
   sqlite3 data/assigner/assigner.db "SELECT id, target_session, assigned_session FROM prompts WHERE status='failed';"
   ```

2. **Verify those sessions exist**:
   ```bash
   tmux list-sessions
   ```

3. **Check the logs for the actual error**:
   ```bash
   grep "Failed to assign" /tmp/architect_assigner_worker.log | tail -20
   ```

### If the database is corrupted:

```bash
# Backup first
cp data/assigner/assigner.db data/assigner/assigner.db.backup

# Try to recover
sqlite3 data/assigner/assigner.db "PRAGMA integrity_check;"

# If corruption is severe, you may need to rebuild:
# (This will lose historical data but preserve schema)
mv data/assigner/assigner.db data/assigner/assigner.db.corrupt
python3 workers/assigner_worker.py --daemon  # Will recreate DB
```
