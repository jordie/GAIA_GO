# Session Status Update System - Complete Guide

**Version**: 1.0
**Status**: Production Ready

## Overview

Push-based real-time status monitoring for all 39+ Claude sessions. Sessions proactively write progress updates to files, eliminating the need for constant stdout polling.

## Quick Start

### For Sessions (Push Updates)

```python
from utils.session_status import SessionStatus

# Initialize
status = SessionStatus("your_session_name")

# Push updates as you work
status.working("Starting task", progress=0.1, task_id="160")
status.working("Processing data", progress=0.5, task_id="160")
status.completed("Task finished", task_id="160")
```

### For Monitoring (Pull Updates)

```bash
# Watch sessions in real-time
python3 workers/session_monitor.py

# Check once and exit
python3 workers/session_monitor.py --once
```

### Via API

```bash
# Get summary
curl http://localhost:8080/api/session-status/summary

# Get all sessions
curl http://localhost:8080/api/session-status/sessions

# Get specific session
curl http://localhost:8080/api/session-status/session/manager1

# Get working sessions
curl http://localhost:8080/api/session-status/working
```

## Architecture

```
Sessions (39+)
    │
    │ Write updates
    ▼
data/session_status/*.json
    │
    │ Read periodically
    ▼
SessionMonitor
    │
    ├─► CLI Dashboard
    └─► REST API
```

## Status Values

| Status | Meaning | Use When |
|--------|---------|----------|
| `idle` | Waiting for tasks | No active work |
| `working` | Actively processing | Doing work |
| `blocked` | Waiting on dependency | Can't proceed |
| `completed` | Task finished | Work done |
| `error` | Encountered error | Something failed |

## Update Format

```json
{
  "timestamp": "2026-02-14T20:35:00Z",
  "session": "manager1",
  "status": "working",
  "progress": 0.45,
  "message": "Querying database for statistics",
  "task_id": "160",
  "metadata": {
    "phase": "data_collection",
    "items_processed": 15
  }
}
```

## Python API

### SessionStatus Class

```python
from utils.session_status import SessionStatus

# Initialize
status = SessionStatus("session_name")

# Convenience methods
status.idle("Waiting for tasks")
status.working("Processing", progress=0.5, task_id="123")
status.blocked("Waiting for API", task_id="123")
status.completed("Done", task_id="123")
status.error("Failed: timeout", task_id="123")

# Full control
status.push(
    status="working",
    message="Custom message",
    progress=0.75,
    task_id="123",
    metadata={"custom": "data"}
)
```

### Command Line

```bash
# Direct Python call
python3 utils/session_status.py manager1 working "Querying DB" 0.5 160

# From bash script
python3 -c "from utils.session_status import SessionStatus; \
SessionStatus('manager1').working('Task complete', progress=1.0)"
```

## Monitoring

### CLI Monitor

```bash
# Run as daemon (updates every 10s)
python3 workers/session_monitor.py

# Custom interval
python3 workers/session_monitor.py --interval 5

# Check once
python3 workers/session_monitor.py --once
```

**Output Example:**
```
============================================================
SESSION STATUS SUMMARY
============================================================
Total Sessions: 6

By Status:
  working: 4
  idle: 2

Working (4):
  • architect1: Checking roadmap alignment (50%)
  • manager1: Compiling status report (75%)
  • qa_tester1: Running integration tests (60%)
  • worker2: Implementing feature (40%)

⚠️  Stale (1):
  • worker3: No update for 6.2 minutes
============================================================
```

### API Endpoints

#### GET /api/session-status/summary
Summary statistics across all sessions.

**Response:**
```json
{
  "total_sessions": 6,
  "by_status": {
    "working": 4,
    "idle": 2
  },
  "working_sessions": ["manager1", "architect1"],
  "error_sessions": [],
  "stale_sessions": ["worker3"]
}
```

#### GET /api/session-status/sessions
Detailed status for all sessions.

**Response:**
```json
{
  "manager1": {
    "timestamp": "2026-02-14T20:35:00Z",
    "session": "manager1",
    "status": "working",
    "progress": 0.75,
    "message": "Compiling status report",
    "task_id": "160",
    "age_seconds": 12.5,
    "is_stale": false
  },
  ...
}
```

#### GET /api/session-status/session/{name}
Status for specific session.

#### GET /api/session-status/session/{name}/history?limit=50
Update history for session.

#### GET /api/session-status/working
All sessions currently working.

#### GET /api/session-status/errors
All sessions with errors.

#### GET /api/session-status/stale
Sessions that haven't updated recently.

## Integration with Dashboard

Add to `app.py`:

```python
from utils.session_status_api import register_session_status_routes

# After creating Flask app
app = Flask(__name__)

# Register session status routes
register_session_status_routes(app)
```

## Session Instructions

Each session type (manager, architect, QA) should push updates at key points:

### Managers
```python
status = SessionStatus("manager1")
status.working("Received task", progress=0.1, task_id="160")
status.working("Analyzing requirements", progress=0.2, task_id="160")
status.working("Delegating to workers", progress=0.5, task_id="160")
status.working("Reviewing results", progress=0.8, task_id="160")
status.completed("Report ready", task_id="160")
```

### Architects
```python
status = SessionStatus("architect1")
status.working("Loading roadmap", progress=0.1, task_id="161")
status.working("Checking milestone alignment", progress=0.4, task_id="161")
status.working("Flagging deviations", progress=0.7, task_id="161")
status.completed("Analysis complete", task_id="161")
```

### QA Testers
```python
status = SessionStatus("qa_tester1")
status.working("Running unit tests", progress=0.2, task_id="162")
status.working("Running integration tests", progress=0.5, task_id="162")
status.working("Running e2e tests", progress=0.8, task_id="162")
status.completed("All tests passed", task_id="162")
```

## Staleness Detection

- **5 minutes**: Marked as potentially stale
- **15 minutes**: Marked as very stale, alert triggered
- **Fallback**: Check tmux stdout for debugging

## File Structure

```
data/session_status/
├── manager1_status.json
├── manager2_status.json
├── architect1_status.json
├── qa_tester1_status.json
└── ... (one file per session)
```

Each file contains JSON Lines format (one update per line):
```json
{"timestamp":"...","session":"manager1","status":"working","progress":0.1,"message":"Starting"}
{"timestamp":"...","session":"manager1","status":"working","progress":0.5,"message":"Halfway"}
{"timestamp":"...","session":"manager1","status":"completed","progress":1.0,"message":"Done"}
```

## Benefits

1. **No Polling**: Sessions push when they have updates
2. **Scalable**: Works with 10 or 1000 sessions
3. **Reliable**: File-based, always available
4. **Historical**: All updates preserved
5. **Flexible**: Can switch to HTTP/database without changing sessions

## Troubleshooting

### Session not showing up
- Check if `data/session_status/{session}_status.json` exists
- Verify session is pushing updates
- Check file permissions

### Stale sessions
- Session may be stuck or crashed
- Check tmux stdout as fallback
- Verify session is still running

### Missing updates
- Ensure `utils/session_status.py` is importable
- Check `data/session_status/` directory exists
- Verify session has write permissions

## Future Enhancements

### Phase 2: HTTP Push
Sessions can POST to `/api/session-status/push`:
```bash
curl -X POST http://localhost:8080/api/session-status/push \
  -H "Content-Type: application/json" \
  -d '{"session":"manager1","status":"working","message":"Processing"}'
```

### Phase 3: Database Integration
Store updates in `session_status` table for advanced queries and analytics.

### Phase 4: WebSocket
Real-time push to dashboard clients via WebSocket.

---

**Status**: ✅ Production ready
**Files**: 5 (protocol, helper, monitor, API, guide)
**Lines**: ~800
**Sessions**: All 39+ sessions can use this system
