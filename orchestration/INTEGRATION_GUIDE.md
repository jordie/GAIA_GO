# GAIA Lock System Integration Guide

## Integration Points

### 1. Task Assignment (assigner_worker.py)

**Before assigning a task, check if folder is locked:**

```python
from gaia_lock_manager import GaiaLockManager

manager = GaiaLockManager(gaia_locks_dir="/Users/jgirmay/Desktop/gitrepo/GAIA_HOME/locks")

def _assign_prompt(self, prompt: Dict, session_name: str):
    """Assign prompt to session (respects locks)"""

    working_dir = prompt.get('working_dir')
    task_id = prompt.get('id')

    # Skip if working_dir is None
    if not working_dir:
        logger.warning(f"Task {task_id} has no working directory, assigning anyway")
        self._send_to_session(prompt, session_name)
        return True

    # Check if folder is locked
    is_locked, lock_info = manager.is_locked(working_dir)
    if is_locked:
        logger.warning(
            f"Cannot assign task {task_id}: folder {working_dir} is locked by "
            f"{lock_info['session_id']}:{lock_info['task_id']}"
        )
        # Don't assign - task will be retried later
        return False

    # Try to acquire lock
    if not manager.acquire_lock(working_dir, session_name, task_id):
        logger.error(f"Failed to acquire lock for {working_dir}")
        return False

    # Lock acquired, now assign the task
    self._send_to_session(prompt, session_name)
    self.log_assignment(task_id, session_name, working_dir)

    return True
```

### 2. Task Completion (assigner_worker.py)

**When task completes, release the lock:**

```python
def _check_assignments(self):
    """Check active assignments and release locks for completed tasks"""

    completed = []

    for assignment in self.get_active_assignments():
        # Poll task status
        task_status = self.poll_task_status(assignment['task_id'])

        if task_status == 'completed':
            task_id = assignment['task_id']
            session_name = assignment['session']
            working_dir = assignment.get('working_dir')

            # Release lock if task had one
            if working_dir:
                if manager.release_lock(working_dir, session_name):
                    logger.info(f"Released lock for task {task_id}")
                else:
                    logger.warning(f"Failed to release lock for task {task_id}")

            # Mark assignment as complete
            self.mark_assignment_complete(assignment['id'])
            completed.append(assignment)

        elif task_status == 'failed':
            # Task failed - still release the lock
            task_id = assignment['task_id']
            session_name = assignment['session']
            working_dir = assignment.get('working_dir')

            if working_dir:
                manager.release_lock(working_dir, session_name)
                logger.info(f"Released lock for failed task {task_id}")

            # Mark as failed
            self.mark_assignment_failed(assignment['id'])
            completed.append(assignment)

    return completed
```

### 3. Task Timeout Handling

**If a task times out, release its lock:**

```python
def timeout_stuck_assignments(self) -> int:
    """Timeout assignments that are stuck (release locks)"""

    timed_out = 0
    timeout_seconds = 60 * 60  # 1 hour

    for assignment in self.get_active_assignments():
        elapsed = time.time() - assignment['assigned_at_timestamp']

        if elapsed > timeout_seconds:
            task_id = assignment['task_id']
            session_name = assignment['session']
            working_dir = assignment.get('working_dir')

            logger.warning(f"Task {task_id} timed out after {elapsed}s")

            # Release lock
            if working_dir:
                manager.release_lock(working_dir, session_name)
                logger.info(f"Released lock from timed-out task {task_id}")

            # Mark as failed
            self.mark_assignment_failed(assignment['id'])
            timed_out += 1

    return timed_out
```

### 4. Session Cleanup

**When restarting assigner, clean up orphaned locks:**

```python
def __init__(self):
    # ... existing init ...

    # Clean up expired locks on startup
    cleaned = manager.cleanup_expired_locks()
    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} expired locks on startup")
```

## Database Schema

Add these columns to `assigner.db` to track locks:

```sql
-- Extend prompts table to track locks
ALTER TABLE prompts ADD COLUMN working_dir TEXT;
ALTER TABLE prompts ADD COLUMN lock_status TEXT;  -- active, released, expired
ALTER TABLE prompts ADD COLUMN lock_acquired_at TIMESTAMP;
ALTER TABLE prompts ADD COLUMN lock_released_at TIMESTAMP;

-- New table to track lock history
CREATE TABLE lock_history (
    id INTEGER PRIMARY KEY,
    folder_path TEXT NOT NULL,
    session_id TEXT NOT NULL,
    task_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    released_at TIMESTAMP,
    expired_at TIMESTAMP,
    status TEXT DEFAULT 'active'  -- active, released, expired
);

-- Index for performance
CREATE INDEX idx_lock_history_folder ON lock_history(folder_path);
CREATE INDEX idx_lock_history_session ON lock_history(session_id);
CREATE INDEX idx_lock_history_task ON lock_history(task_id);
```

## Environment Configuration

Add to `.env` or `.env.example`:

```bash
# GAIA Lock System
GAIA_HOME=/Users/jgirmay/Desktop/gitrepo/GAIA_HOME
GAIA_LOCKS_DIR=${GAIA_HOME}/locks
GAIA_LOCK_TIMEOUT_HOURS=2
GAIA_AUTO_CLEANUP_LOCKS=true
GAIA_LOCK_CLEANUP_INTERVAL=3600  # seconds (1 hour)
```

Load in assigner_worker.py:

```python
import os
from pathlib import Path

GAIA_HOME = Path(os.getenv('GAIA_HOME', '/Users/jgirmay/Desktop/gitrepo/GAIA_HOME'))
GAIA_LOCKS_DIR = Path(os.getenv('GAIA_LOCKS_DIR', str(GAIA_HOME / 'locks')))
GAIA_LOCK_TIMEOUT = int(os.getenv('GAIA_LOCK_TIMEOUT_HOURS', 2))
GAIA_AUTO_CLEANUP = os.getenv('GAIA_AUTO_CLEANUP_LOCKS', 'true').lower() == 'true'
GAIA_CLEANUP_INTERVAL = int(os.getenv('GAIA_LOCK_CLEANUP_INTERVAL', 3600))

manager = GaiaLockManager(gaia_locks_dir=str(GAIA_LOCKS_DIR))
```

## API Endpoints (for Architect Dashboard)

Add to dashboard `app.py`:

```python
@app.route('/api/gaia/locks', methods=['GET'])
@login_required
def get_gaia_locks():
    """Get all active GAIA locks"""
    manager = GaiaLockManager()
    status = manager.get_lock_status()
    return jsonify(status)

@app.route('/api/gaia/locks/<folder_path>', methods=['GET'])
@login_required
def get_lock_status(folder_path):
    """Get lock status for specific folder"""
    manager = GaiaLockManager()
    is_locked, lock_info = manager.is_locked(folder_path)
    return jsonify({
        'folder_path': folder_path,
        'is_locked': is_locked,
        'lock_info': lock_info
    })

@app.route('/api/gaia/locks/<int:lock_id>/release', methods=['POST'])
@login_required
@admin_required  # Only admins can force-release
def force_release_lock(lock_id):
    """Force release a stuck lock (admin only)"""
    manager = GaiaLockManager()
    # Implementation depends on how you track lock IDs
    # This would need the lock_history table
    return jsonify({'success': True, 'message': 'Lock released'})
```

## Dashboard UI Widget

Add to `templates/dashboard.html`:

```html
<!-- GAIA Lock Status Widget -->
<div class="panel panel-danger" id="gaia-locks">
    <div class="panel-heading">
        <h3 class="panel-title">
            🔒 GAIA Lock Status
            <span class="badge" id="lock-count">0</span>
        </h3>
    </div>
    <div class="panel-body">
        <table class="table table-sm" id="locks-table">
            <thead>
                <tr>
                    <th>Folder</th>
                    <th>Session</th>
                    <th>Task</th>
                    <th>Created</th>
                    <th>Expires</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody id="locks-tbody">
            </tbody>
        </table>
        <div id="no-locks" class="alert alert-success">
            No active locks - all folders are available
        </div>
    </div>
</div>

<script>
function refreshLocks() {
    fetch('/api/gaia/locks')
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById('locks-tbody');
            const table = document.getElementById('locks-table').parentElement;

            if (data.locks.length === 0) {
                table.style.display = 'none';
                document.getElementById('no-locks').style.display = 'block';
                document.getElementById('lock-count').textContent = '0';
                return;
            }

            table.style.display = 'table';
            document.getElementById('no-locks').style.display = 'none';
            document.getElementById('lock-count').textContent = data.locks.length;

            tbody.innerHTML = data.locks.map(lock => `
                <tr>
                    <td><code>${lock.folder_path}</code></td>
                    <td><strong>${lock.session_id}</strong></td>
                    <td>Task ${lock.task_id}</td>
                    <td>${new Date(lock.created_at).toLocaleString()}</td>
                    <td>${new Date(lock.expires_at).toLocaleString()}</td>
                    <td>
                        <button class="btn btn-xs btn-danger"
                                onclick="releaseLock(${lock.id})">
                            Force Release
                        </button>
                    </td>
                </tr>
            `).join('');
        });
}

function releaseLock(lockId) {
    if (!confirm('Force release this lock?')) return;

    fetch(`/api/gaia/locks/${lockId}/release`, {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            alert(data.message);
            refreshLocks();
        });
}

// Refresh every 10 seconds
setInterval(refreshLocks, 10000);
refreshLocks();  // Initial load
</script>
```

## Monitoring & Logging

```python
# In assigner_worker.py main loop
while True:
    try:
        # Assign pending tasks
        self._assign_pending_tasks()

        # Check active assignments
        self._check_assignments()

        # Timeout stuck tasks (releases locks)
        self.timeout_stuck_assignments()

        # Periodic cleanup
        if self._should_cleanup():
            cleaned = manager.cleanup_expired_locks()
            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} expired locks")

        time.sleep(1)  # Check every second

    except Exception as e:
        logger.error(f"Error in assigner loop: {e}")
```

## Testing

```python
# test_gaia_locking.py
import pytest
from gaia_lock_manager import GaiaLockManager

@pytest.fixture
def manager():
    return GaiaLockManager()

def test_acquire_lock(manager):
    """Test lock acquisition"""
    assert manager.acquire_lock("/test/folder", "session1", 123)
    is_locked, info = manager.is_locked("/test/folder")
    assert is_locked
    assert info['session_id'] == 'session1'

def test_prevent_double_lock(manager):
    """Test that locks prevent double assignment"""
    manager.acquire_lock("/test/folder", "session1", 123)
    # Second session can't get lock
    assert not manager.acquire_lock("/test/folder", "session2", 124)

def test_release_lock(manager):
    """Test lock release"""
    manager.acquire_lock("/test/folder", "session1", 123)
    assert manager.release_lock("/test/folder", "session1")
    is_locked, info = manager.is_locked("/test/folder")
    assert not is_locked

def test_prevent_cross_session_release(manager):
    """Test that wrong session can't release lock"""
    manager.acquire_lock("/test/folder", "session1", 123)
    # session2 can't release session1's lock
    assert not manager.release_lock("/test/folder", "session2")
```

## Troubleshooting Checklist

- [ ] GAIA_HOME directory exists: `/Users/jgirmay/Desktop/gitrepo/GAIA_HOME`
- [ ] Locks directory exists: `GAIA_HOME/locks`
- [ ] `.gaia*` is in repository `.gitignore`
- [ ] `gaia_lock_manager.py` is in repository root
- [ ] Assigner worker imports `GaiaLockManager`
- [ ] Lock acquisition checked in `_assign_prompt()`
- [ ] Lock release happens in `_check_assignments()`
- [ ] Lock release happens in timeout handlers
- [ ] Periodic cleanup runs hourly or on-demand

## Integration Checklist

- [ ] Copy `gaia_lock_manager.py` to repository
- [ ] Update `.gitignore` with `.gaia*` patterns
- [ ] Integrate `GaiaLockManager` into `assigner_worker.py`
- [ ] Add working_dir to task schema
- [ ] Add lock tracking to database
- [ ] Add API endpoints to dashboard
- [ ] Add UI widget to dashboard
- [ ] Add monitoring/logging
- [ ] Add unit tests
- [ ] Test with multiple concurrent tasks
- [ ] Document in README and GAIA_HOME

---

**Ready for integration!**
