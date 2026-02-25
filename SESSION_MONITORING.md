# Session Monitoring Integration

This document explains how the foundation session integrates with the orchestrator infrastructure for continuous work assignment and monitoring.

## Overview

The foundation session (this session) is monitored and coordinated with the main architect session to ensure:

1. **No conflicts**: Work is isolated in feature environment 1 (port 8081)
2. **Continuous progress**: Idle time is detected and new work is automatically assigned
3. **Strategic alignment**: Tasks come from the goal_engine based on strategic vision
4. **Progress tracking**: All work is logged and tracked
5. **Coordination**: Integration with the architect session monitoring system

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator Layer                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Goal Engine  │───▶│ Run Executor │───▶│  Review      │      │
│  │  (Strategy)  │    │   (Tactics)  │    │   Queue      │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Session Monitoring Layer                      │
│  ┌──────────────────┐           ┌──────────────────┐            │
│  │ Session Watchdog │           │ Session Keepalive│            │
│  │  (monitors idle) │           │  (prevents idle) │            │
│  └──────────────────┘           └──────────────────┘            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │      Foundation Session Monitor (NEW)                │       │
│  │  - Monitors "foundation" tmux session                │       │
│  │  - Pulls tasks from goal_engine when idle            │       │
│  │  - Tracks progress and reports back                  │       │
│  │  - Coordinates with architect session                │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Session Layer                              │
│  ┌──────────────┐           ┌──────────────┐                    │
│  │  architect   │           │  foundation  │                    │
│  │  (main work) │           │ (week2 work) │                    │
│  │  Port: 8080  │           │  Port: 8081  │                    │
│  └──────────────┘           └──────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Foundation Session Monitor (`scripts/foundation_session_monitor.py`)

**Purpose**: Monitor the foundation session and ensure continuous work

**Features**:
- Detects session idle/busy state by analyzing tmux output
- Pulls high-priority tasks from goal_engine database
- Sends tasks to the foundation session via tmux
- Tracks work sessions, completions, and failures
- Logs all activity to `logs/foundation_work.log`
- Persists state to `/tmp/foundation_session_state.json`

**Configuration**:
- `CHECK_INTERVAL`: 120 seconds (2 minutes)
- `IDLE_THRESHOLD`: 180 seconds (3 minutes)
- `SESSION_NAME`: "foundation"

**CLI Usage**:
```bash
# Show current status
python3 scripts/foundation_session_monitor.py --status

# Run one check cycle
python3 scripts/foundation_session_monitor.py --check-once

# Run as daemon (background)
python3 scripts/foundation_session_monitor.py --daemon

# Manually assign a task
python3 scripts/foundation_session_monitor.py --assign-task "Task description"
```

**State Tracking**:
```json
{
  "session_start": "2026-02-14T20:00:00",
  "tasks_completed": 15,
  "tasks_failed": 1,
  "last_activity": "2026-02-14T20:45:00",
  "current_task": {
    "id": "task-123",
    "content": "Implement quality scoring algorithm",
    "priority": 85
  },
  "idle_count": 0,
  "work_sessions": 16
}
```

### 2. Web Dashboard API Endpoints

New monitoring endpoints added to `web_dashboard.py`:

#### `GET /api/monitor/status`
Get current monitor status including session state, uptime, tasks completed, etc.

**Response**:
```json
{
  "session_name": "foundation",
  "session_running": true,
  "uptime_seconds": 3600,
  "uptime_formatted": "1:00:00",
  "tasks_completed": 15,
  "tasks_failed": 1,
  "work_sessions": 16,
  "current_task": {...},
  "is_idle": false,
  "is_busy": true,
  "last_activity": "2026-02-14T20:45:00",
  "feature_env": "env_1",
  "feature_port": 8081
}
```

#### `POST /api/monitor/assign-task`
Manually assign a task to the foundation session.

**Request**:
```json
{
  "task": "Implement new feature X",
  "priority": 100,
  "category": "feature"
}
```

**Response**:
```json
{
  "success": true,
  "task": {...},
  "message": "Task assigned successfully"
}
```

#### `GET /api/monitor/work-log?limit=50`
Get recent work log entries.

**Response**:
```json
{
  "entries": [
    "2026-02-14 20:00:00 - Assigned task 123: Implement quality scoring",
    "2026-02-14 20:15:00 - Completed task: Implement quality scoring"
  ],
  "count": 2,
  "total_lines": 150
}
```

#### `GET /api/monitor/check-and-assign`
Trigger an immediate check and assignment cycle.

**Response**:
```json
{
  "success": true,
  "message": "Check and assign cycle completed"
}
```

### 3. Management Scripts

#### Start Monitor
```bash
./scripts/start_foundation_monitor.sh
```

**What it does**:
- Checks if monitor is already running
- Starts monitor daemon in background
- Creates PID file at `/tmp/foundation_monitor.pid`
- Logs to `logs/foundation_monitor.log`

#### Stop Monitor
```bash
./scripts/stop_foundation_monitor.sh
```

**What it does**:
- Reads PID from `/tmp/foundation_monitor.pid`
- Sends SIGTERM to monitor process
- Force kills if necessary
- Removes PID file

## Integration with Orchestrator

### Goal Engine Integration

The monitor integrates with the goal_engine database (`orchestrator/goals.db`) to pull tasks:

```sql
SELECT * FROM tasks
WHERE status = 'pending'
AND (project LIKE '%week2%' OR project LIKE '%research%' OR project LIKE '%foundation%')
ORDER BY priority DESC, created_at ASC
LIMIT 1
```

This query prioritizes:
1. Pending tasks (not started yet)
2. Related to week2/research/foundation work
3. Highest priority first
4. Oldest created first (FIFO)

### Coordination with Architect Session

The foundation session monitor coordinates with the main architect session by:

1. **Environment Isolation**: Using separate port (8081 vs 8080) and data directory
2. **Work Filtering**: Only pulling tasks relevant to week2/research work
3. **Activity Detection**: Monitoring for idle/busy state to avoid interrupting active work
4. **State Persistence**: Tracking progress separately in `/tmp/foundation_session_state.json`

This ensures no race conditions or conflicts between sessions.

## Workflow

### Normal Operation

1. **Monitor starts** (every 2 minutes):
   - Check if foundation session is running
   - Capture session output (last 50 lines)
   - Analyze for idle/busy indicators

2. **If session is busy**:
   - Reset idle counter
   - Update last_activity timestamp
   - Continue monitoring

3. **If session is idle**:
   - Increment idle counter
   - If idle threshold exceeded (3 min):
     - Query goal_engine for next task
     - If task found: send to session
     - If no task: send general work prompt
     - Reset idle counter

4. **Work completion detected**:
   - Increment tasks_completed counter
   - Log completion
   - Clear current_task
   - Ready for next assignment

### Manual Intervention

You can manually intervene at any time via:

1. **CLI**: `python3 scripts/foundation_session_monitor.py --assign-task "Task"`
2. **API**: `POST /api/monitor/assign-task`
3. **Direct tmux**: Send commands directly to the foundation session

## Monitoring

### Check Monitor Status

```bash
# Via CLI
python3 scripts/foundation_session_monitor.py --status

# Via API (if web dashboard is running)
curl http://localhost:8081/api/monitor/status | jq

# Via logs
tail -f logs/foundation_monitor.log
tail -f logs/foundation_work.log
```

### Verify Integration

```bash
# Check if foundation session exists
tmux has-session -t foundation

# Check if monitor is running
ps aux | grep foundation_session_monitor

# Check state file
cat /tmp/foundation_session_state.json | jq

# Check recent work
curl http://localhost:8081/api/monitor/work-log?limit=10 | jq
```

## Troubleshooting

### Monitor Not Starting

**Check**:
```bash
# Is tmux session running?
tmux list-sessions | grep foundation

# Is port 8081 available?
lsof -i :8081

# Check logs
tail -100 logs/foundation_monitor.log
```

**Fix**:
```bash
# Start foundation session if needed
tmux new-session -d -s foundation

# Kill process using port 8081
kill $(lsof -t -i :8081)

# Restart monitor
./scripts/stop_foundation_monitor.sh
./scripts/start_foundation_monitor.sh
```

### No Tasks Being Assigned

**Check**:
```bash
# Is goal_engine database initialized?
ls -la orchestrator/goals.db

# Are there pending tasks?
sqlite3 orchestrator/goals.db "SELECT * FROM tasks WHERE status='pending'"

# Check monitor status
python3 scripts/foundation_session_monitor.py --status
```

**Fix**:
```bash
# Initialize goal engine if needed
python3 orchestrator/goal_engine.py --init

# Add a vision/goal
python3 orchestrator/goal_engine.py --add-vision "Strategic vision here"
python3 orchestrator/goal_engine.py --add-goal "Specific goal here"

# Generate tasks
python3 orchestrator/goal_engine.py --generate
```

### Session Detection Issues

If the monitor can't detect session activity correctly:

**Check tmux capture**:
```bash
tmux capture-pane -t foundation -p -S -50
```

**Adjust idle indicators** in `foundation_session_monitor.py`:
```python
idle_indicators = ['❯', '>', '$', '#', 'How can I help', 'Continue']
busy_indicators = ['Thinking', 'Analyzing', 'Processing', 'Running', '…', 'Task']
```

## Future Enhancements

Potential improvements:

1. **Machine Learning**: Learn optimal assignment patterns based on task completion times
2. **Priority Adjustment**: Dynamically adjust priority based on dependencies and deadlines
3. **Multi-Session Support**: Monitor and coordinate multiple feature sessions
4. **Slack/Email Notifications**: Alert when tasks complete or issues occur
5. **Web UI Dashboard**: Real-time visualization of session activity
6. **Task Splitting**: Break large tasks into smaller chunks automatically
7. **Performance Metrics**: Track throughput, velocity, cycle time

## References

Related files and documentation:

- **Session Watchdog**: `scripts/session_watchdog.py` - Monitors architect session
- **Session Keepalive**: `workers/session_keepalive.py` - Keeps sessions alive
- **Goal Engine**: `orchestrator/goal_engine.py` - Strategic task generation
- **Run Executor**: `orchestrator/run_executor.py` - Task execution
- **Status Dashboard**: `status_dashboard.py` - System status monitoring
- **Web Dashboard**: `web_dashboard.py` - Real-time web interface

## Quick Start

To get the full monitoring system running:

```bash
# 1. Start the web dashboard on port 8081
cd feature_environments/env_1
./start_dashboard.sh

# 2. Start the foundation session monitor
cd ../..
./scripts/start_foundation_monitor.sh

# 3. Verify everything is running
python3 scripts/foundation_session_monitor.py --status
curl http://localhost:8081/api/monitor/status | jq

# 4. Watch the logs
tail -f logs/foundation_monitor.log logs/foundation_work.log

# 5. Access web dashboard
open http://localhost:8081
```

That's it! The foundation session will now automatically receive work from the orchestrator and stay productive.
