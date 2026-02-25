# Session Status Update Protocol

**Version**: 1.0
**Date**: February 14, 2026

## Overview

Push-based status update system where sessions proactively write progress updates to files. The system monitors these files without needing stdout access or tmux polling.

## Architecture

```
┌─────────────────────────────────────────┐
│  Claude Sessions (39+)                  │
│  • Write status updates to files        │
│  • No need to be polled                 │
└──────────────┬──────────────────────────┘
               │ (Write updates)
               ▼
┌─────────────────────────────────────────┐
│  Status Update Files                    │
│  data/session_status/                   │
│  • {session_name}_status.json           │
│  • Append-only, timestamped             │
└──────────────┬──────────────────────────┘
               │ (Read periodically)
               ▼
┌─────────────────────────────────────────┐
│  Status Monitor (session_monitor.py)    │
│  • Reads update files every 5-10s       │
│  • Aggregates status                    │
│  • Detects stalled sessions             │
└──────────────┬──────────────────────────┘
               │ (Store/Expose)
               ▼
┌─────────────────────────────────────────┐
│  Dashboard / API                        │
│  • Real-time status view                │
│  • Alert on issues                      │
│  • Historical progress                  │
└─────────────────────────────────────────┘
```

## Update File Format

### Location
`data/session_status/{session_name}_status.json`

### Format (JSON Lines - one update per line)
```json
{
  "timestamp": "2026-02-14T20:35:00Z",
  "session": "manager1",
  "status": "working",
  "task_id": "160",
  "progress": 0.45,
  "message": "Querying database for project statistics",
  "metadata": {
    "phase": "data_collection",
    "items_processed": 15,
    "items_total": 33
  }
}
```

### Status Values
- `idle` - Waiting for tasks
- `working` - Actively processing
- `blocked` - Waiting on dependency
- `completed` - Task finished
- `error` - Encountered error

## Session Instructions

### Update Command (Bash)
```bash
echo '{"timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'","session":"session_name","status":"working","progress":0.5,"message":"Current activity"}' >> data/session_status/session_name_status.json
```

### Update Command (Python)
```python
import json
from datetime import datetime
from pathlib import Path

def push_status(session, status, message, progress=None, task_id=None, metadata=None):
    status_file = Path(f"data/session_status/{session}_status.json")
    status_file.parent.mkdir(parents=True, exist_ok=True)

    update = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session": session,
        "status": status,
        "message": message
    }
    if progress is not None:
        update["progress"] = progress
    if task_id is not None:
        update["task_id"] = task_id
    if metadata is not None:
        update["metadata"] = metadata

    with open(status_file, "a") as f:
        f.write(json.dumps(update) + "\n")

# Usage
push_status("manager1", "working", "Querying database", progress=0.3, task_id="160")
```

## Benefits

### 1. No Polling Required
- Sessions push updates when they have something to report
- No need to constantly read tmux stdout
- Reduces system overhead

### 2. Reliable
- File-based, always available
- No dependency on tmux session state
- Persists across session restarts

### 3. Scalable
- Works with 10 or 1000 sessions
- Monitoring script only reads files that changed
- Low resource usage

### 4. Flexible
- Update collection method can change without affecting sessions
- Can switch from files to HTTP POST, database, etc.
- Sessions just write to the agreed interface

### 5. Historical
- All updates preserved in append-only files
- Can replay session progress
- Useful for debugging and analysis

## Fallback: stdout Reading

- Still available for debugging
- Used when status file hasn't updated in 5+ minutes
- Helps detect stuck sessions

## Implementation

### Phase 1: File-based (Current)
- Sessions write to `data/session_status/*.json`
- Monitor reads files every 10 seconds
- Dashboard shows aggregated status

### Phase 2: Optional HTTP Endpoint
- Sessions can POST to `/api/session-status`
- Useful for remote sessions
- Falls back to file if endpoint unavailable

### Phase 3: Database Integration
- Status updates written to `session_status` table
- Real-time queries via MCP
- Historical analysis

## Security

- Status files in `data/session_status/` (gitignored)
- Read-only access for monitoring
- Write-only for sessions
- No sensitive data in status messages

## Monitoring

### Stalled Detection
- If no update in 5+ minutes: mark as potentially stalled
- If no update in 15+ minutes: alert
- Check tmux stdout as fallback

### Progress Tracking
- Latest progress value shown in dashboard
- Estimated completion time calculated
- Visual progress bars

### Error Detection
- Status "error" triggers immediate alert
- Error messages shown prominently
- Can trigger auto-retry or escalation

---

This protocol provides reliable, scalable session monitoring without constant polling or stdout reading.
