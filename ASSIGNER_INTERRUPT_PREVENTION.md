# Assigner Worker: Interrupt Prevention Rules

**Created**: 2026-02-21
**Priority**: HIGH
**Status**: ACTIVE - IMPLEMENT IMMEDIATELY

## User Requirement

> "Don't interrupt user typing into 'inspector', 'architect', and 'foundation' sessions, especially if '##' is in the string"

**Translation**: The assigner worker must detect active user input and avoid sending prompts to sessions with live editing in progress.

## Protected Sessions

These sessions have special interrupt prevention:
- `inspector` - User may be inspecting/debugging
- `architect` - User may be editing architecture/plans
- `foundation` - User may be building foundations/scaffolding

## Detection Rules

### Rule 1: Markdown Header Detection (##)
If session output contains `##` (markdown headers), assume user is **actively editing** a markdown file or document.

```python
def has_active_markdown_editing(session_output: str) -> bool:
    """Detect if session has active markdown editing"""
    return "##" in session_output
```

### Rule 2: Protected Session Detection
```python
PROTECTED_SESSIONS = {'inspector', 'architect', 'foundation'}

def is_protected_session(session_name: str) -> bool:
    """Check if session is protected from interruption"""
    return any(protected in session_name.lower() for protected in PROTECTED_SESSIONS)
```

### Rule 3: Active Typing Detection
Look for these patterns indicating user is actively typing:
```python
ACTIVE_TYPING_INDICATORS = [
    "Type a message",          # Claude Code prompt
    "claude>",                 # Waiting for input
    ">",                       # Shell/CLI prompt
    "? ",                      # Interactive prompt
    "│",                       # Vertical bar (split view)
    "Thinking",               # Processing
    "Analyzing",              # Processing
    "Checking",               # Processing
    "[EDITOR]",               # Editor mode
]

def has_active_typing_indicator(session_output: str) -> bool:
    """Detect if session has active input prompt"""
    return any(indicator in session_output for indicator in ACTIVE_TYPING_INDICATORS)
```

### Rule 4: Session State Detection
```python
def detect_session_state(session_name: str) -> str:
    """Detect current session state via tmux"""

    output = subprocess.check_output(
        ['tmux', 'capture-pane', '-p', '-t', session_name]
    ).decode('utf-8')

    # Check for active editing
    if "##" in output and is_protected_session(session_name):
        return "EDITING_PROTECTED"

    if has_active_markdown_editing(output):
        return "EDITING_MARKDOWN"

    if has_active_typing_indicator(output):
        return "WAITING_INPUT"

    if "error" in output.lower():
        return "ERROR"

    if "busy" in output.lower() or len(output.strip()) < 20:
        return "BUSY"

    return "IDLE"
```

## Assignment Logic

### Enhanced Session Selection

```python
def should_assign_to_session(session_name: str, prompt: Dict) -> bool:
    """Determine if safe to assign prompt to session"""

    state = detect_session_state(session_name)

    # Never assign to these states
    BLOCKED_STATES = {
        'EDITING_PROTECTED',      # User editing in protected session
        'EDITING_MARKDOWN',       # User editing markdown (## detected)
        'WAITING_INPUT',          # Session waiting for user input
        'ERROR',                  # Session in error state
    }

    if state in BLOCKED_STATES:
        return False

    # Can assign to these states
    SAFE_STATES = {'IDLE', 'BUSY'}
    return state in SAFE_STATES
```

### Assignment Flow with Interrupt Prevention

```
Prompt needs assignment
    ↓
Get available sessions
    ↓
For each session:
    ├─ Check session state
    ├─ Is protected session? → Check for ## or typing
    │   ├─ YES → Skip (don't assign)
    │   └─ NO → Proceed to next check
    ├─ Has active typing? → Skip
    ├─ Has active markdown (##)? → Skip
    ├─ Is idle/busy (safe)? → Can assign
    └─ Is error/stuck? → Skip
    ↓
Select best non-blocked session
    ↓
Assign prompt
```

## Implementation in AssignerDatabase

```python
class AssignerDatabase:
    # ... existing methods ...

    def get_available_sessions_safe(
        self,
        provider: Optional[str] = None,
        exclude_protected: bool = True
    ) -> List[Dict]:
        """
        Get available sessions, excluding those with active user input.

        Args:
            provider: Filter by provider (optional)
            exclude_protected: Skip protected sessions if user is typing (default: True)

        Returns:
            List of safe session objects
        """

        all_sessions = self.get_available_sessions(provider)
        safe_sessions = []

        for session in all_sessions:
            name = session['name']

            # Detect current session state
            state = self._detect_session_state(name)

            # Exclude protected sessions if in editing/typing state
            if exclude_protected and self._is_protected_session(name):
                if self._is_active_state(state):
                    logger.info(f"Skipping protected session {name} (state: {state})")
                    continue

            # Exclude any session with active typing
            if self._is_active_state(state):
                logger.info(f"Skipping {name} - active user input (state: {state})")
                continue

            safe_sessions.append(session)

        return safe_sessions

    def _detect_session_state(self, session_name: str) -> str:
        """Detect session state via tmux capture-pane"""
        try:
            output = subprocess.check_output(
                ['tmux', 'capture-pane', '-p', '-t', session_name],
                stderr=subprocess.DEVNULL
            ).decode('utf-8', errors='ignore')

            # Check for protected session + active editing
            if self._is_protected_session(session_name):
                if "##" in output or any(ind in output for ind in ACTIVE_TYPING_INDICATORS):
                    return "EDITING_PROTECTED"

            # Check for markdown editing
            if "##" in output:
                return "EDITING_MARKDOWN"

            # Check for active input prompts
            if any(ind in output for ind in ACTIVE_TYPING_INDICATORS):
                return "WAITING_INPUT"

            # Check for errors
            if "error" in output.lower() or "failed" in output.lower():
                return "ERROR"

            # Check if busy (output suggests activity)
            if len(output.strip()) > 50 and ("Thinking" in output or "Analyzing" in output):
                return "BUSY"

            return "IDLE"

        except Exception as e:
            logger.warning(f"Could not detect state of {session_name}: {e}")
            return "UNKNOWN"

    def _is_protected_session(self, session_name: str) -> bool:
        """Check if session is protected from interruption"""
        protected = {'inspector', 'architect', 'foundation'}
        return any(p in session_name.lower() for p in protected)

    def _is_active_state(self, state: str) -> bool:
        """Check if state indicates active user interaction"""
        return state in {'EDITING_PROTECTED', 'EDITING_MARKDOWN', 'WAITING_INPUT'}
```

## Configuration

```yaml
# ~/.gaia/config.json
assigner:
  # ... existing config ...

  interrupt_prevention:
    enabled: true
    protected_sessions:
      - inspector
      - architect
      - foundation

    active_state_indicators:
      - "##"                    # Markdown headers
      - "Type a message"        # Claude prompt
      - "claude>"               # Waiting for input
      - "Thinking"             # Processing
      - "Analyzing"            # Processing

    check_interval_seconds: 2   # How often to check session state
    timeout_seconds: 30         # Max wait before forcing assignment
```

## Monitoring & Logging

```python
def assign_with_interrupt_prevention(self, prompt: Dict, timeout_seconds: int = 30):
    """
    Assign prompt while avoiding user interruption.

    1. Try to find safe session (non-protected/non-active)
    2. If none available, wait up to timeout_seconds
    3. On timeout, auto-assign to least-active session
    """

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        # Get safe sessions only
        safe_sessions = self.get_available_sessions_safe(exclude_protected=True)

        if safe_sessions:
            # Pick best safe session
            best_session = self._select_best_session(safe_sessions)
            logger.info(
                f"Assigning prompt {prompt['id']} to {best_session['name']} "
                f"(interrupt-safe)"
            )
            return self._do_assignment(prompt, best_session)

        # No safe sessions, wait a bit and retry
        wait_time = 2
        logger.debug(
            f"No safe sessions available for prompt {prompt['id']}, "
            f"retrying in {wait_time}s"
        )
        time.sleep(wait_time)

    # Timeout - forced assignment to least-active session
    logger.warning(
        f"Interrupt prevention timeout for prompt {prompt['id']}, "
        f"forcing assignment to least-active session"
    )
    fallback_sessions = self.get_available_sessions()
    if fallback_sessions:
        least_active = min(
            fallback_sessions,
            key=lambda s: self._activity_score(s)
        )
        return self._do_assignment(prompt, least_active)

    # Give up - queue will retry later
    logger.error(f"Could not assign prompt {prompt['id']} - all sessions unavailable")
    return False
```

## Metrics & Observability

```python
def get_interrupt_prevention_metrics(self) -> Dict:
    """Get metrics on interrupt prevention effectiveness"""

    return {
        'total_prompts_queued': self._count_prompts('all'),
        'prompts_assigned_safe': self._count_prompts('assigned_safe'),
        'prompts_waiting_safe_slot': self._count_prompts('pending_safe'),
        'prompts_forced_assignment': self._count_prompts('forced_assigned'),

        'protected_sessions_protected': self._count_protected_sessions_active(),
        'interrupt_prevention_timeouts': self._count_timeout_events(),

        'average_wait_for_safe_slot_ms': self._calculate_avg_wait(),
        'user_interruptions_prevented': self._count_prevented_interruptions(),
    }
```

## Testing the Feature

```python
def test_interrupt_prevention():
    """Test that protected sessions with ## are never interrupted"""

    # Setup: Create protected session with markdown editing
    os.system('tmux new-session -d -s test_architect -c /tmp')
    os.system('tmux send-keys -t test_architect "# Architecture Plan" Enter')
    os.system('tmux send-keys -t test_architect "## Phase 1" Enter')

    time.sleep(1)

    # Verify session is detected as protected + editing
    state = db._detect_session_state('test_architect')
    assert state == "EDITING_PROTECTED", f"Expected EDITING_PROTECTED, got {state}"

    # Verify session is not in safe list
    safe = db.get_available_sessions_safe()
    session_names = [s['name'] for s in safe]
    assert 'test_architect' not in session_names, "Protected editing session should not be in safe list"

    # Verify assignment is rejected
    prompt = {'id': 1, 'content': 'test'}
    can_assign = db.should_assign_to_session('test_architect', prompt)
    assert not can_assign, "Should not assign to protected editing session"

    print("✅ Interrupt prevention working correctly")
```

## Summary

| Scenario | Action | Behavior |
|----------|--------|----------|
| `inspector` session with `##` | Skip | Never assign |
| `architect` session typing | Skip | Never assign |
| `foundation` session idle | Check | Can assign if safe |
| Any session with active prompt (`>`) | Skip | Wait or reassign |
| Protected session EDITING_MARKDOWN | Skip | Wait for completion |
| Regular session idle | Assign | Normal operation |

---

**Status**: Ready for implementation
**Priority**: HIGH
**Implementation Effort**: 4-6 hours
**Complexity**: Medium (tmux integration + state detection)
