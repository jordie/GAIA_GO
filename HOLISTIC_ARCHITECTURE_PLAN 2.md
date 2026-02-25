# Holistic System Architecture Plan
## Integrating Go Wrapper + Assigner + Sessions + Context Management

**Date:** 2026-02-15
**Status:** Architecture Design
**Scope:** Complete system integration

---

## Current System Components

### 1. Go Wrapper (`go_wrapper/`)
**Purpose:** Real-time output extraction and streaming
**Components:**
- `wrapper` binary - Wraps Claude sessions, extracts structured data
- `apiserver` - REST API for extraction events (port 8151)
- `stream/extractor.go` - Pattern-based extraction from stdout
- `stream/process.go` - Process lifecycle management
- Dashboard - Real-time visualization of extractions

**Current State:**
- ✅ Works: Real-time extraction of errors, code blocks, metrics
- ✅ Works: SSE streaming to dashboard
- ❌ Missing: Integration with assigner task queue
- ❌ Missing: Context awareness (doesn't know what task is running)
- ❌ Missing: Feedback loop (extractions don't inform task routing)

### 2. Assigner Worker (`workers/assigner_worker.py`)
**Purpose:** Task queue and session assignment
**Components:**
- SQLite database (`data/assigner/assigner.db`)
- Session detection (tmux scanning)
- Priority-based queue
- Retry logic

**Current State:**
- ✅ Works: Priority queue, task assignment
- ✅ Works: Session targeting (claude/codex/ollama)
- ❌ Missing: Context management (working_dir, env vars)
- ❌ Missing: Integration with go_wrapper extractions
- ❌ Missing: Task success/failure detection from wrapper events

### 3. Sessions (Claude/Codex/Ollama in tmux)
**Purpose:** Execution environments for tasks
**Types:**
- `architect` - High-level coordination (this session)
- `foundation` - Foundation-level work
- `codex` - Code-focused tasks
- `dev_worker1`, `dev_worker2` - Development workers

**Current State:**
- ✅ Works: Multiple concurrent sessions
- ✅ Works: Auto-approve configured
- ❌ Missing: Context tracking (what directory? what branch?)
- ❌ Missing: State synchronization with assigner
- ❌ Missing: Extraction feedback (wrapper → assigner)

### 4. Context (Working directories, environments)
**Current State:**
- ❌ Tasks don't specify required directory
- ❌ Sessions don't track current directory
- ❌ No automatic `cd` before task execution
- ❌ No validation that session is in correct state

---

## The Integration Problem

**Current Flow (Disconnected):**
```
User → Assigner → tmux send-keys → Session
                                      ↓
                                   (works in wrong dir)
                                      ↓
                                   (no feedback)
                                      ✗
```

**What's Missing:**
1. Go wrapper sees extractions but doesn't tell assigner
2. Assigner sends tasks but doesn't know results
3. Sessions work but don't track context
4. No closed feedback loop

---

## Holistic Architecture Design

### Vision: Intelligent Task Orchestration System

```
┌─────────────────────────────────────────────────────────────┐
│                        USER / API                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   ASSIGNER (Brain)                           │
│  • Task queue with context                                   │
│  • Smart session selection                                   │
│  • Context preparation                                       │
│  • Result tracking                                           │
└──────┬──────────────────────────────────────────┬───────────┘
       │                                           │
       │ 1. Prepare Context                        │ 4. Report Result
       │    (cd, env vars, git checkout)           │    (success/fail)
       ▼                                           │
┌─────────────────────────────────────────┐       │
│         SESSION (Executor)               │       │
│  • Claude/Codex/Ollama in tmux          │       │
│  • Receives prepared task                │       │
│  • Executes in correct context          │       │
└─────────┬────────────────────────────────┘      │
          │                                        │
          │ 2. Wrap with Go Wrapper                │
          ▼                                        │
┌─────────────────────────────────────────┐       │
│      GO WRAPPER (Observer)               │       │
│  • Monitors session output               │       │
│  • Extracts structured events            │       │
│  • Detects success/failure               │───────┘
│  • Streams to dashboard                  │ 3. Events
└──────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│       DASHBOARD (Visibility)             │
│  • Real-time extraction view             │
│  • Task progress tracking                │
│  • Session health monitoring             │
└──────────────────────────────────────────┘
```

---

## Integration Points

### Integration 1: Assigner → Go Wrapper

**Before Task:**
```python
# Assigner prepares session context
def assign_task(task, session):
    # 1. Parse task context
    context = json.loads(task.metadata)
    working_dir = context.get('working_dir')

    # 2. Send context setup commands
    if working_dir:
        send_to_session(session, f"cd {working_dir}")

    # 3. Tell go_wrapper what task is starting
    requests.post('http://localhost:8151/api/tasks/start', json={
        'task_id': task.id,
        'session': session.name,
        'context': context
    })

    # 4. Send the actual task
    send_to_session(session, task.content)
```

**After Task:**
```python
# Go wrapper detects completion and notifies assigner
@app.post("/api/tasks/complete")
def task_complete(task_id: int, result: str, extractions: list):
    # Update assigner database
    assigner_db.update_prompt_status(
        task_id,
        'completed',
        response=result,
        metadata={'extractions': extractions}
    )
```

### Integration 2: Go Wrapper Event Detection

**Add to `go_wrapper/stream/extractor.go`:**
```go
// Task completion patterns
var taskCompletionPatterns = []Pattern{
    {
        Type:    "task_complete",
        Pattern: regexp.MustCompile(`✅.*complete|done|finished`),
    },
    {
        Type:    "task_failed",
        Pattern: regexp.MustCompile(`❌.*failed|error|exception`),
    },
}

// Notify assigner on task events
func (e *Extractor) notifyAssigner(event ExtractionEvent) {
    if event.Type == "task_complete" || event.Type == "task_failed" {
        http.Post(
            "http://localhost:8080/api/assigner/task-event",
            "application/json",
            marshal(event),
        )
    }
}
```

### Integration 3: Context Management

**Enhanced Sessions Table:**
```sql
-- Track full session context
ALTER TABLE sessions ADD COLUMN current_dir TEXT;
ALTER TABLE sessions ADD COLUMN git_branch TEXT;
ALTER TABLE sessions ADD COLUMN env_vars TEXT; -- JSON
ALTER TABLE sessions ADD COLUMN last_task_id INTEGER;
ALTER TABLE sessions ADD COLUMN context_hash TEXT; -- For change detection
```

**Context Sync:**
```python
def sync_session_context(session_name):
    """Poll session and update context"""

    # Get current state via tmux
    cwd = subprocess.check_output([
        'tmux', 'send-keys', '-t', session_name,
        'pwd', 'C-m', ';',
        'tmux', 'capture-pane', '-t', session_name, '-p'
    ]).decode().strip()

    git_branch = subprocess.check_output([
        'tmux', 'send-keys', '-t', session_name,
        'git branch --show-current', 'C-m', ';',
        'tmux', 'capture-pane', '-t', session_name, '-p'
    ]).decode().strip()

    # Update database
    db.execute("""
        UPDATE sessions
        SET current_dir = ?, git_branch = ?, updated_at = CURRENT_TIMESTAMP
        WHERE name = ?
    """, (cwd, git_branch, session_name))
```

### Integration 4: Smart Task Routing

**Context-Aware Assignment:**
```python
def select_best_session(task, available_sessions):
    """Score sessions by context match"""

    required_context = json.loads(task.metadata)
    required_dir = required_context.get('working_dir')

    scored = []
    for session in available_sessions:
        score = 0

        # Already in right directory = +20 (no context switch)
        if session.current_dir == required_dir:
            score += 20

        # Same git branch = +10
        if session.git_branch == required_context.get('git_branch'):
            score += 10

        # Recently active = +5
        if session.last_activity > (now() - timedelta(minutes=5)):
            score += 5

        # Idle = +3
        if session.status == 'idle':
            score += 3

        # Provider preference match = +2
        if session.provider == task.target_provider:
            score += 2

        scored.append((score, session))

    # Return highest scoring session
    scored.sort(reverse=True)
    return scored[0][1]
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Basic integration infrastructure

**Tasks:**
1. Add task lifecycle API to go_wrapper
   - `POST /api/tasks/start` - Task beginning
   - `POST /api/tasks/complete` - Task finished
   - `POST /api/tasks/event` - Task event (error, milestone)

2. Extend assigner database schema
   - Add context fields to prompts
   - Add current_dir/git_branch to sessions
   - Add task_events table

3. Implement context preparation
   - Auto `cd` before task
   - Set environment variables
   - Verify context before sending

**Success Criteria:**
- ✅ Tasks include working_dir in metadata
- ✅ Sessions change to correct directory before task
- ✅ Go wrapper tracks which task is running

### Phase 2: Feedback Loop (Week 2)
**Goal:** Close the loop - wrapper tells assigner results

**Tasks:**
1. Implement task event detection in go_wrapper
   - Pattern matching for success/failure
   - Extract completion status from output
   - Notify assigner via HTTP

2. Update assigner to consume events
   - Receive task completion events
   - Auto-mark prompts as completed/failed
   - Trigger retries on failure

3. Add session context sync
   - Poll sessions for current state
   - Track directory changes
   - Detect git branch switches

**Success Criteria:**
- ✅ Go wrapper detects task completion
- ✅ Assigner auto-marks tasks completed
- ✅ Failed tasks auto-retry

### Phase 3: Intelligence (Week 3)
**Goal:** Smart routing and optimization

**Tasks:**
1. Context-aware session selection
   - Score sessions by context match
   - Prefer sessions already in correct state
   - Minimize context switches

2. Session affinity
   - Keep related tasks on same session
   - Track "session expertise" (what it's good at)
   - Load balancing

3. Predictive context preparation
   - Pre-switch sessions to likely next context
   - Batch tasks by context
   - Optimize for throughput

**Success Criteria:**
- ✅ 80% of tasks assigned to sessions already in correct context
- ✅ Average context switches < 2 per hour per session
- ✅ Task throughput increases 30%

### Phase 4: Visibility (Week 4)
**Goal:** Complete observability

**Tasks:**
1. Enhanced dashboard
   - Show task queue with context
   - Session health with current context
   - Real-time task progress

2. Metrics and analytics
   - Task completion rates
   - Context switch frequency
   - Session utilization

3. Admin controls
   - Manually reassign tasks
   - Override session selection
   - Pause/resume workers

**Success Criteria:**
- ✅ Full visibility into task→session→result flow
- ✅ Metrics for optimization
- ✅ Manual intervention when needed

---

## Data Flow Examples

### Example 1: Simple Task

**Input:**
```python
assigner.send_prompt(
    content="Fix bug in app.py line 42",
    priority=5,
    metadata={
        'working_dir': '/Users/jgirmay/Desktop/gitrepo/pyWork/architect',
        'git_branch': 'main'
    }
)
```

**Flow:**
```
1. Assigner receives task (ID 123)
2. Scores sessions:
   - codex: score 23 (in /architect, on main, idle)
   - dev_worker1: score 8 (wrong dir, idle)
3. Selects codex (highest score)
4. Prepares context:
   → cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
   → (already on main branch)
5. Notifies wrapper:
   POST /api/tasks/start {task_id: 123, session: codex}
6. Sends task:
   → Fix bug in app.py line 42
7. Wrapper monitors output
8. Detects: "✅ Bug fixed" → task_complete event
9. Wrapper notifies assigner:
   POST /api/assigner/task-event {task_id: 123, status: complete}
10. Assigner marks task completed
```

### Example 2: Multi-Step Task with Context Switch

**Input:**
```python
assigner.send_prompt(
    content="Run tests in test environment",
    metadata={
        'working_dir': '/Users/jgirmay/Desktop/gitrepo/pyWork/basic-edu-apps',
        'git_branch': 'feature/new-tests',
        'prerequisites': [
            'source venv/bin/activate',
            'export TEST_ENV=staging'
        ]
    }
)
```

**Flow:**
```
1. Assigner finds best session (dev_worker1)
2. Current context: /architect, main branch
3. Context preparation:
   → cd /Users/jgirmay/Desktop/gitrepo/pyWork/basic-edu-apps
   → git checkout feature/new-tests
   → source venv/bin/activate
   → export TEST_ENV=staging
4. Verifies context:
   → Check pwd matches
   → Check git branch matches
5. Sends task
6. Wrapper monitors, extracts test results
7. Detects completion
8. Updates assigner with test results
```

---

## Benefits

### 1. Context Safety
- Tasks always run in correct directory
- No more "file not found" errors from wrong location
- Git branch verification prevents cross-contamination

### 2. Efficiency
- Smart session selection minimizes context switches
- Reuse sessions already in correct state
- Batch similar tasks together

### 3. Visibility
- Know what task each session is running
- Track task→result flow
- Dashboard shows full system state

### 4. Reliability
- Automatic retry on failure
- Context validation before execution
- Feedback loop catches errors early

### 5. Intelligence
- Learn which sessions are good at what
- Optimize task routing over time
- Predict and prepare contexts proactively

---

## Migration Strategy

### Step 1: Add Context to New Tasks (Day 1)
- Start including `working_dir` in task metadata
- Assigner uses it if present, ignores if missing
- **Backward compatible:** Old tasks still work

### Step 2: Implement Context Preparation (Day 2-3)
- Assigner sends `cd` before task
- Track session state in database
- **Backward compatible:** Only affects tasks with metadata

### Step 3: Add Go Wrapper Integration (Day 4-5)
- Wrapper exposes task lifecycle API
- Assigner starts notifying wrapper
- **Backward compatible:** Wrapper works with/without notifications

### Step 4: Close Feedback Loop (Day 6-7)
- Wrapper detects task completion
- Notifies assigner
- **Backward compatible:** Manual task completion still works

### Step 5: Enable Smart Routing (Week 2)
- Context-aware session selection
- Session affinity
- **Backward compatible:** Falls back to simple routing if needed

### Step 6: Full Integration (Week 3-4)
- Complete dashboard integration
- Metrics and analytics
- Admin controls

---

## Testing Strategy

### Unit Tests
```python
def test_context_preparation():
    """Test session context is prepared correctly"""
    task = create_task(working_dir='/tmp/test')
    session = create_session(name='test-session')

    prepare_context(session, task)

    assert get_session_pwd(session) == '/tmp/test'

def test_smart_routing():
    """Test session selection by context match"""
    task = create_task(working_dir='/architect')

    s1 = create_session(current_dir='/architect')  # Score: 20
    s2 = create_session(current_dir='/tmp')         # Score: 0

    selected = select_best_session(task, [s1, s2])
    assert selected == s1
```

### Integration Tests
```bash
#!/bin/bash
# Test full flow: task → context → execution → result

# 1. Send task with context
python3 workers/assigner_worker.py --send "ls -la" \
    --metadata '{"working_dir": "/tmp"}'

# 2. Wait for assignment
sleep 5

# 3. Check session changed directory
tmux capture-pane -t codex -p | grep "/tmp"

# 4. Check task completed
python3 workers/assigner_worker.py --prompts | grep "completed"
```

---

## Monitoring

### Metrics to Track
- **Context switches per hour** (minimize)
- **Task completion rate** (maximize)
- **Average task duration** (optimize)
- **Session utilization** (balance)
- **Context match rate** (% tasks assigned to sessions already in correct context)

### Alerts
- Session stuck (no activity > 30min)
- High failure rate (>20% in 1 hour)
- Context mismatch detected
- Worker down

### Dashboards
- Real-time task queue with context
- Session health and current state
- Task completion trends
- Context switch heatmap

---

## Success Metrics

### After Phase 1:
- ✅ 100% of new tasks include context
- ✅ 0 "file not found" errors from wrong directory
- ✅ Sessions tracked in database

### After Phase 2:
- ✅ 90% of tasks auto-complete (no manual marking)
- ✅ Failed tasks auto-retry within 5 min
- ✅ Full task→result visibility

### After Phase 3:
- ✅ 80% of tasks assigned to sessions already in correct context
- ✅ <2 context switches per hour per session
- ✅ 30% increase in task throughput

### After Phase 4:
- ✅ Complete observability (dashboard shows full state)
- ✅ Admin can intervene when needed
- ✅ Metrics guide optimization

---

## Next Steps

1. **Review this architecture** - Validate the approach
2. **Prioritize phases** - Which phase to start with?
3. **Assign implementation** - Which session builds what?
4. **Create tracking** - Tasks/milestones for each phase
5. **Begin Phase 1** - Start with foundation integration

**Question for you:** Does this holistic architecture address your concerns about context, efficiency, and integration?
