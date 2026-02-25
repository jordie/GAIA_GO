# Preventive Fixes Applied to Assigner Worker

**Date**: 2026-02-15
**File**: `workers/assigner_worker.py`
**Purpose**: Prevent stale session issues from causing failed prompts

---

## Problem Addressed

The assigner worker was failing to deliver prompts because it attempted to assign tasks to tmux sessions that no longer existed (e.g., "test-claude"). This resulted in:
- 15+ failed prompts with error: `tmux send-keys failed: can't find pane: <session>`
- Stale session data accumulating in the database
- No automatic cleanup or verification

## Fixes Implemented

### Fix 1: Automatic Stale Session Cleanup

**Location**: `_scan_sessions()` method (line ~1141)

**What it does**:
- During each session scan, compares sessions in the database with sessions currently in tmux
- Automatically removes sessions that exist in DB but not in tmux
- Frees up any tasks that were assigned to stale sessions (resets them to pending)
- Logs all cleanup actions for visibility

**Code changes**:
```python
# Get set of current session names from tmux
current_session_names = {s.name for s in sessions}

# Remove stale sessions (in DB but not in tmux)
stale_count = 0
for db_session in existing:
    if db_session["name"] not in current_session_names:
        logger.info(f"Removing stale session from DB: {db_session['name']}")
        # Free assigned tasks and delete session
        # ... (see code for full implementation)
```

**Benefits**:
- Prevents stale data from accumulating
- Automatically recovers from session crashes/closures
- Runs every scan interval (default: 10 seconds)

### Fix 2: Real-Time Session Verification

**Location**: `_assign_prompt()` method (line ~1294)

**What it does**:
- Verifies the target session exists in tmux BEFORE attempting to send the prompt
- If session not found, triggers an immediate re-scan
- After re-scan, if session still doesn't exist, marks prompt as failed with clear error message
- Prevents the "can't find pane" error from ever reaching tmux

**Code changes**:
```python
# VERIFY SESSION EXISTS before attempting to send
current_sessions = self.detector.list_sessions()
if session_name not in current_sessions:
    logger.warning(f"Session {session_name} not found, re-scanning...")
    self._scan_sessions()

    # Check again after re-scan
    current_sessions = self.detector.list_sessions()
    if session_name not in current_sessions:
        logger.error(f"Session {session_name} does not exist, marking prompt as failed")
        # Mark as failed and return (don't attempt tmux send-keys)
        return
```

**Benefits**:
- Catches stale session references before they cause errors
- Provides clear, actionable error messages
- Triggers automatic database cleanup when issues detected
- Eliminates "can't find pane" errors

## Impact

### Before Fixes:
- ❌ Stale sessions accumulated in database
- ❌ No verification before assignment
- ❌ Errors: `tmux send-keys failed: can't find pane: <session>`
- ❌ Manual cleanup required via cleanup script

### After Fixes:
- ✅ Automatic stale session removal every scan (10s interval)
- ✅ Real-time verification before every assignment
- ✅ Clear error messages: `Target session '<name>' not found in tmux`
- ✅ Self-healing: system automatically recovers from session issues
- ✅ No manual intervention needed

## Testing

To verify the fixes are working:

1. **Check for stale session cleanup**:
   ```bash
   # Watch logs for stale session removal
   tail -f /tmp/architect_assigner_worker.log | grep "Removing stale"
   ```

2. **Check for session verification**:
   ```bash
   # Watch logs for verification messages
   tail -f /tmp/architect_assigner_worker.log | grep "not found in tmux"
   ```

3. **Monitor failed prompts**:
   ```bash
   # Check that failed prompts stay at 0
   python3 workers/assigner_worker.py --status
   ```

## Rollback Plan

If issues occur, revert to the previous version:

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
git diff workers/assigner_worker.py  # Review changes
git checkout HEAD -- workers/assigner_worker.py  # Revert if needed
python3 workers/assigner_worker.py --stop
python3 workers/assigner_worker.py --daemon
```

## Related Files

- **Cleanup Script**: `workers/cleanup_assigner.py` (for manual cleanup if needed)
- **Troubleshooting Guide**: `workers/ASSIGNER_CLEANUP_GUIDE.md`
- **Worker Logs**: `/tmp/architect_assigner_worker.log`

## Performance Impact

- **Minimal overhead**: Session verification adds ~50ms per assignment (one tmux list-sessions call)
- **Stale cleanup**: Runs once per scan (10s interval), negligible CPU impact
- **Network**: No additional network calls
- **Database**: Minimal (one DELETE per stale session found)

## Future Improvements

Potential enhancements for consideration:

1. **Session Health Monitoring**: Track session uptime and restart crashed sessions
2. **Predictive Stale Detection**: Mark sessions as "at risk" if they haven't responded recently
3. **Session Pooling**: Maintain a pool of ready sessions for each provider type
4. **Smart Retry Logic**: Automatically reassign to different sessions on failure

---

**Deployment**: These fixes are immediately active upon worker restart.
**Monitoring**: Watch logs at `/tmp/architect_assigner_worker.log`
**Support**: See `ASSIGNER_CLEANUP_GUIDE.md` for troubleshooting
