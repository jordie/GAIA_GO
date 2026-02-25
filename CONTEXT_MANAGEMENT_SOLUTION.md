# Context Management Solution for Assigner Queue

## Problem Statement

When tasks are sent to the assigner queue:
1. **Queue collisions**: Two tasks sent → need proper queuing
2. **Missing context**: Tasks don't know what directory they need
3. **Session state**: Sessions might be in wrong directory
4. **Efficiency**: Context switching is expensive

## Current State Analysis

### ✅ What Works:
- Priority queue (higher priority processed first)
- Status tracking (pending → assigned → in_progress → completed)
- Sessions table tracks `working_dir`
- Metadata field available (JSON)

### ❌ What's Missing:
- Tasks don't specify required `working_dir`
- No automatic `cd` before task execution
- No context validation before assignment
- No session state verification

## Solution Design

### 1. Enhanced Task Context

Add to prompt metadata:
```json
{
  "working_dir": "/Users/jgirmay/Desktop/gitrepo/pyWork/architect",
  "env_vars": {
    "PYTHON_ENV": "production",
    "PORT": "8080"
  },
  "prerequisites": [
    "cd ~/Desktop/gitrepo/pyWork/architect",
    "source venv/bin/activate"
  ],
  "session_state": {
    "expected_cwd": "/Users/jgirmay/Desktop/gitrepo/pyWork/architect",
    "git_branch": "feature/context-mgmt"
  }
}
```

### 2. Pre-Task Context Setup

Before sending task to session:
```python
def prepare_session_context(session_name, task_context):
    """Ensure session is in correct context before task"""

    # 1. Change to required directory
    if task_context.get("working_dir"):
        send_to_session(session_name, f"cd {task_context['working_dir']}")
        time.sleep(0.5)

    # 2. Set environment variables
    for key, value in task_context.get("env_vars", {}).items():
        send_to_session(session_name, f"export {key}={value}")
        time.sleep(0.3)

    # 3. Run prerequisites
    for cmd in task_context.get("prerequisites", []):
        send_to_session(session_name, cmd)
        time.sleep(0.5)

    # 4. Verify context
    verify_session_context(session_name, task_context)
```

### 3. Session State Tracking

Update sessions table to track:
```sql
ALTER TABLE sessions ADD COLUMN current_dir TEXT;
ALTER TABLE sessions ADD COLUMN env_vars TEXT; -- JSON
ALTER TABLE sessions ADD COLUMN git_branch TEXT;
ALTER TABLE sessions ADD COLUMN last_context_update TIMESTAMP;
```

Track session state changes:
```python
def update_session_state(session_name):
    """Poll session and update state"""

    # Capture current state
    state = {
        "cwd": get_session_pwd(session_name),
        "git_branch": get_session_git_branch(session_name),
        "idle": is_session_idle(session_name)
    }

    # Update database
    db.execute("""
        UPDATE sessions
        SET current_dir = ?,
            git_branch = ?,
            last_context_update = CURRENT_TIMESTAMP
        WHERE name = ?
    """, (state['cwd'], state['git_branch'], session_name))
```

### 4. Smart Task Assignment

Consider context when assigning:
```python
def assign_task_to_session(task, sessions):
    """Assign task to best matching session"""

    required_dir = task.metadata.get("working_dir")
    required_env = task.metadata.get("env_vars", {})

    # Score sessions by context match
    scored_sessions = []
    for session in sessions:
        score = 0

        # Already in right directory = +10
        if session.current_dir == required_dir:
            score += 10

        # Already has env vars = +5
        if matches_env_vars(session.env_vars, required_env):
            score += 5

        # Is idle = +3
        if session.status == "idle":
            score += 3

        # Recent activity = +1
        if session.last_activity > (now() - timedelta(minutes=5)):
            score += 1

        scored_sessions.append((score, session))

    # Sort by score, assign to highest
    scored_sessions.sort(reverse=True)
    return scored_sessions[0][1]  # Return best session
```

### 5. Queue Visualization

Show queue with context:
```python
def show_queue():
    """Display queue with context information"""

    prompts = db.execute("""
        SELECT id, content, priority, status, metadata, target_session
        FROM prompts
        WHERE status IN ('pending', 'assigned', 'in_progress')
        ORDER BY priority DESC, created_at ASC
    """).fetchall()

    print("\n📋 Task Queue:")
    print("=" * 80)

    for p in prompts:
        metadata = json.loads(p['metadata'] or '{}')
        working_dir = metadata.get('working_dir', 'N/A')
        target = p['target_session'] or 'auto'

        print(f"[{p['id']}] {p['status'].upper():12} Pri:{p['priority']} → {target}")
        print(f"    Dir: {working_dir}")
        print(f"    Task: {p['content'][:60]}...")
        print()
```

### 6. Context Validation

Before sending task:
```python
def validate_context(session_name, required_context):
    """Verify session is in correct context"""

    current_dir = get_session_pwd(session_name)
    required_dir = required_context.get("working_dir")

    if required_dir and current_dir != required_dir:
        logger.warning(f"Session {session_name} in wrong dir: {current_dir} != {required_dir}")
        return False

    # Check git branch if required
    if "git_branch" in required_context:
        current_branch = get_session_git_branch(session_name)
        if current_branch != required_context["git_branch"]:
            logger.warning(f"Wrong git branch: {current_branch} != {required_context['git_branch']}")
            return False

    return True
```

## Implementation Plan

### Phase 1: Basic Context (Week 1)
- [ ] Add `working_dir` to task metadata
- [ ] Implement `cd` before task send
- [ ] Update sessions table schema
- [ ] Track session `current_dir`

### Phase 2: Environment Variables (Week 1)
- [ ] Add `env_vars` to metadata
- [ ] Set env vars before task
- [ ] Track session env state

### Phase 3: Validation (Week 2)
- [ ] Implement context validation
- [ ] Smart session selection by context match
- [ ] Context mismatch warnings

### Phase 4: Queue Management (Week 2)
- [ ] Queue visualization with context
- [ ] Priority + context-based assignment
- [ ] Session readiness scoring

## Usage Examples

### Send Task with Context
```python
# New way - with full context
assigner.send_prompt(
    content="Fix the bug in login.py",
    priority=5,
    metadata={
        "working_dir": "/Users/jgirmay/Desktop/gitrepo/pyWork/architect",
        "env_vars": {"DEBUG": "1"},
        "prerequisites": ["git checkout feature/login-fix"],
        "session_state": {
            "git_branch": "feature/login-fix"
        }
    }
)
```

### Check Queue Status
```bash
python3 workers/assigner_worker.py --queue

# Output:
# 📋 Task Queue:
# [1] PENDING     Pri:5 → codex
#     Dir: ~/architect
#     Task: Fix the bug in login.py...
#
# [2] ASSIGNED    Pri:3 → dev_worker1
#     Dir: ~/basic-edu-apps
#     Task: Add new feature to dashboard...
```

### Verify Session Context
```python
# Check if session is ready for task
session_state = assigner.get_session_state("codex")
print(f"Directory: {session_state['current_dir']}")
print(f"Git branch: {session_state['git_branch']}")
print(f"Ready: {session_state['idle']}")
```

## Benefits

1. **No More Context Confusion**: Sessions always in right directory
2. **Efficient Assignment**: Match tasks to sessions already in correct context
3. **Better Visibility**: See queue with full context info
4. **Automatic Setup**: Prerequisites run before task
5. **Validation**: Catch context mismatches early

## Migration Path

1. **Backward Compatible**: Old tasks without context still work
2. **Gradual Adoption**: Add context to new tasks incrementally
3. **No Breaking Changes**: Existing queue continues working
4. **Optional Features**: Context validation can be toggled

## Testing Strategy

```bash
# Test 1: Send task with context
python3 workers/assigner_worker.py --send "Test task" \
    --metadata '{"working_dir": "/tmp/test"}'

# Test 2: Verify session changes dir
tmux capture-pane -t codex -p | grep "/tmp/test"

# Test 3: Multiple tasks, different contexts
# Verify each session goes to correct directory

# Test 4: Context validation
# Send task requiring dir that doesn't exist → should fail gracefully
```

## Monitoring

```python
# Add logging for context operations
logger.info(f"Changing session {name} dir: {old_dir} → {new_dir}")
logger.info(f"Setting env vars: {env_vars}")
logger.warning(f"Context mismatch detected: {details}")
logger.error(f"Failed to prepare context: {error}")
```

## Next Steps

1. Review this proposal
2. Implement Phase 1 (basic context)
3. Test with architect/foundation sessions
4. Roll out to all sessions
5. Add context to existing task senders
