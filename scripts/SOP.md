# Standard Operating Procedures (SOP)
# Claude Session Management & Development Guidelines

## Core Principles

### 1. DRY - Don't Repeat Yourself
- Reuse existing functions, modules, and patterns
- Check for existing implementations before creating new ones
- Centralize shared logic in utility modules
- Use database models instead of duplicating schemas

### 2. KISS - Keep It Simple, Stupid
- Solve the immediate problem, not hypothetical future ones
- Avoid over-engineering and premature abstraction
- Prefer readable code over clever code
- Start with the simplest solution that works

### 3. Single Responsibility
- Each session works on ONE task at a time
- Each environment handles ONE feature branch
- Each scope has ONE owner (for exclusive scopes)

### 4. No Confirmations - Just Do It
- DO NOT ask "should I proceed?" or "would you like me to..."
- DO NOT wait for approval before making changes
- EXECUTE the task immediately and completely
- REPORT results when done, not questions before starting
- If something is unclear, make a reasonable decision and proceed
- Only stop if you encounter a blocking error

### 5. Command Prefixes (ALWAYS FOLLOW)
When the user uses these prefixes, ALWAYS follow the associated action:

| Prefix | Action | Example |
|--------|--------|---------|
| `sta:` | Send to Assigner - assign task to available session | `sta: fix the login bug` |
| `msto:` | Message to Orchestrator - status/coordination query | `msto: how many sessions active?` |

**Rules:**
- If prompt starts with `sta:` → Use session_assigner.py to assign the task
- If prompt starts with `msto:` → Respond with status/coordination info
- These prefixes are COMMANDS, not suggestions - always execute them

---

## Task Routing - Single Entry Points (Use This First)

When sending work to tmux/agents, use ONE of these entry points depending on the workflow:

### A) Standard session assignment (SOP-compliant, env/scopes enforced)
Use when you want environment isolation, scope locks, and SOP rules applied.

- Entry point: `scripts/session_assigner.py`
- Example: `python3 scripts/session_assigner.py assign <session> "<task>" --project architect`
- Output/state: `data/session_state.json`

### B) Assigner worker queue (generic tmux handoff)
Use when you want a single inbox that auto-assigns to any idle tmux AI session.

- Entry point: `workers/assigner_worker.py --send "<task>" [--provider claude|codex|ollama]`
- Interactive: `scripts/session_terminal.py` (use `os:` prefix)
- State DB: `data/assigner/assigner.db`

### C) Google Sheets task flow (DevTasks sheet)
Use when tasks are managed in the Google Sheet and tmux sessions should pull work.

- Entry point (session): `workers/sheet_task_cli.py pull <session_name>`
- Updates: `workers/sheets_sync.py` keeps DB <-> Sheets in sync
- Sheet: `DevTasks` in the configured spreadsheet

### D) Orchestrated research + implementation
Use for automated research (Perplexity) + implementation (tmux) pipelines.

- Entry point: `workers/project_orchestrator.py` (pulls from "Orchestrator" sheet)
- Research-only: `workers/perplexity_sheets.py` (Prompts/WebTests sheets)

If you are unsure, default to **A) session_assigner.py** for SOP compliance, or **B) assigner_worker.py** for a generic tmux inbox.

---

## System Integration Overview

Quick map of how the system works end-to-end:

1. **tmux AI Agents (Claude/Codex/Ollama)**
   - Work is delivered to tmux sessions and monitored for idle/busy state.
   - Provider detection is based on session name/output.

2. **Assigner + Session Coordination**
   - `scripts/session_assigner.py`: Env/scopes enforced, SOP-compliant assignment.
   - `workers/assigner_worker.py`: Generic prompt queue with auto-assignment.
   - `scripts/session_terminal.py`: Interactive os: queue entry point.

3. **Comet/Browser Research**
   - Research tasks run through Perplexity/Comet and feed implementation tasks.

4. **Google Sheets**
   - `workers/sheets_sync.py` syncs DevTasks/Tasks/Bugs/etc with the dashboard.
   - tmux sessions pull tasks from DevTasks and update status/results.

5. **Architect Dashboard**
   - Central UI for sessions, tasks, bugs, errors, and system status.
   - Assigners expose status endpoints for monitoring.

---

## Standardized Port Scheme

All apps follow a consistent port pattern for predictability:

```
Pattern: BASE + OFFSET
  x0 = PROD
  x1 = DEV
  x2 = QA
  x4-x8 = FEATURE environments
```

### Port Assignments

| App | PROD | DEV | QA | Features |
|-----|------|-----|-----|----------|
| **Edu Apps** | 5050 | 5051 | 5052 | 5054-5058 |
| **KanbanFlow** | 6050 | 6051 | 6052 | 6054-6058 |
| **Browser Auto** | 7050 | 7051 | 7052 | 7054-7058 |
| **Architect** | 8080 | 8081 | 8082 | 8084-8088 |

### Edu Apps Feature Environments

| Port | Env | Feature | Directory |
|------|-----|---------|-----------|
| 5054 | env_1 | journey-system | feature_environments/env_1 |
| 5055 | env_2 | gamification | feature_environments/env_2 |
| 5056 | env_3 | dark-mode | feature_environments/env_3 |
| 5057 | env_4 | accessibility | feature_environments/env_4 |
| 5058 | env_5 | error-handling | feature_environments/env_5 |

**Rules:**
- NEVER modify files in main `basic_edu_apps_final/` directory
- ALWAYS work in assigned `feature_environments/env_X/` directory
- COMMIT to your feature branch before switching tasks
- TEST on your assigned port only
- Databases are isolated - no locking conflicts

### KanbanFlow Environments

| Port | Env | Branch | Purpose |
|------|-----|--------|---------|
| 6050 | PROD | main | Production - NO DIRECT COMMITS |
| 6051 | DEV | dev | Integration testing |
| 6052 | QA | qa | QA testing |
| 6054 | FEAT | feature/* | Feature work |

**Rules:**
- `git checkout <branch>` before any work
- NEVER commit directly to main or prod
- Merge to dev only when feature complete
- Run tests before merging

### Architect Dashboard Scopes
Coordinated access to prevent conflicts:

| Scope | Files | Exclusive | Rules |
|-------|-------|-----------|-------|
| database | app.py, db.py, models/ | YES | Only one session modifies DB code |
| api | routes/, api/ | YES | Only one session modifies API routes |
| frontend | static/, templates/ | NO | Multiple can work (different files) |
| workers | workers/ | NO | Multiple can work (different files) |
| readonly | - | NO | Read/research only, no modifications |

**Rules:**
- Check scope assignment before modifying files
- Database scope MUST enable WAL mode
- API scope MUST maintain backward compatibility
- Frontend scope should not break existing JS/CSS

---

## Development Workflow

### 1. Before Starting Work
```
1. Check your environment assignment
2. Navigate to correct directory/branch
3. Pull latest changes (if applicable)
4. Verify no one else is working on same files
```

### 2. During Development
```
1. Make small, focused commits
2. Test after each significant change
3. Check for errors before moving on
4. Don't modify files outside your scope
```

### 3. After Completing Task
```
1. Run relevant tests
2. Commit with descriptive message
3. Update task status
4. Report completion to manager
```

---

## Git Branching Rules

### Branch Hierarchy

```
main (production)
  ↑ merge only from qa
  │
qa (QA testing)
  ↑ merge only from dev
  │
dev (integration)
  ↑ merge only from feature/*
  │
feature/* (development)
  ↑ created from dev
  └── work in feature_environments/env_X/
```

### STRICT RULES - NO EXCEPTIONS

| Action | Allowed | Prohibited |
|--------|---------|------------|
| Merge to `main` | From `qa` only | From `dev`, `feature/*`, direct commits |
| Merge to `qa` | From `dev` only | From `feature/*`, direct commits |
| Merge to `dev` | From `feature/*` only | From `main`, `qa`, direct commits |
| Create feature branch | From `dev` | From `main`, `qa` |
| Direct commits/pushes | `feature/*` only | `main`, `qa`, `dev` |
| Force push | `feature/*` (own branch) | `main`, `qa`, `dev` |
| Development work | `feature_environments/env_X/` | Root app files directly |

### Workflow

1. **Start New Feature**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-feature
   ```

2. **During Development** (work in feature environment!)
   ```bash
   # Work ONLY in feature_environments/env_X/
   # DO NOT modify root app files (unified_app.py, typing/, math/, etc.)
   cd feature_environments/env_2/  # Your assigned environment
   # Make changes here
   git add .
   git commit -m "feat: description"
   git push origin feature/my-feature
   ```

3. **Ready for Integration**
   ```bash
   # Create PR: feature/my-feature → dev
   gh pr create --base dev --title "Feature: description"
   ```

4. **After PR Merged to Dev**
   ```bash
   # Delete feature branch
   git branch -d feature/my-feature
   git push origin --delete feature/my-feature
   ```

5. **QA Testing**
   ```bash
   # Create PR: dev → qa (for QA testing)
   gh pr create --base qa --head dev --title "QA: features for testing"
   # QA team tests on qa branch/environment
   ```

6. **Release to Production**
   ```bash
   # After QA approval, create PR: qa → main
   gh pr create --base main --head qa --title "Release: version X.Y"
   ```

### Feature Environments

Each feature branch works in an isolated environment:

| Environment | Port | Feature Branch | Purpose |
|-------------|------|----------------|---------|
| env_1 | 5054 | feature/journey-system | Journey/learning path |
| env_2 | 5055 | feature/gamification | XP, badges, streaks |
| env_3 | 5056 | feature/dark-mode | Theme support |
| env_4 | 5057 | feature/accessibility | A11y improvements |
| env_5 | 5058 | feature/error-handling | Error boundaries |

**Rules:**
- Work ONLY in your assigned `feature_environments/env_X/`
- Pre-commit hook blocks changes to root app files
- Each environment has its own database (no conflicts)
- Test on your assigned port before creating PR

### PR Requirements

| Target Branch | Requirements |
|---------------|--------------|
| `dev` | Tests pass, feature environment tested |
| `qa` | All dev tests pass, integration tested |
| `main` | QA approved, code review REQUIRED |

### Enforcement

These rules are enforced by:
1. **Pre-commit hooks** - Blocks root file changes in feature branches
2. **Pre-push hooks** - Blocks pushes to `main`, `qa`, and `dev`
3. **GitHub Branch Protection** (if available)
4. **CI/CD checks** (PR validation)
5. **Code review** (human verification)

**Protected branches:** `main`, `master`, `qa`, `dev` - No direct pushes allowed

### Violations

If you accidentally commit to wrong branch:
```bash
# Undo last commit, keep changes
git reset --soft HEAD~1

# Switch to correct branch
git checkout -b feature/my-fix

# Commit there instead
git add . && git commit -m "fix: description"
```

---

## Testing Guidelines

### Online Apps (Web Servers)
1. **ALWAYS use SSL/HTTPS** - Start with `./deploy.sh --ssl`
2. Start server on assigned port
3. Test in browser with correct URL (https://)
4. Check health endpoint: `/health`
5. Verify no console errors
6. Test API endpoints if applicable

**SSL Rules:**
- NEVER run production or shared servers on HTTP
- Use `./deploy.sh --ssl --port XXXX` for all deployments
- Certificates are auto-generated in `certs/` directory
- External access MUST use HTTPS

### Offline Workers
1. Run worker in foreground first (see output)
2. Check log file for errors
3. Verify task processing
4. Run as daemon only when stable

### Database Changes
1. Create migration file for schema changes
2. Test migration on dev environment first
3. Backup before applying to shared DBs
4. Use WAL mode for concurrent access

---

## Code Quality Standards

### Python
```python
# Good: Simple, focused function
def get_user_stats(user_id):
    """Get stats for a single user."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM stats WHERE user_id = ?",
            (user_id,)
        ).fetchone()

# Bad: Doing too much
def get_user_data_and_update_and_notify(user_id, data, notify=True):
    # Too many responsibilities
    pass
```

### JavaScript
```javascript
// Good: Clear, simple
async function fetchData(endpoint) {
    const response = await fetch(endpoint);
    if (!response.ok) throw new Error('Fetch failed');
    return response.json();
}

// Bad: Overly clever
const fetchData = e => fetch(e).then(r => r.ok ? r.json() : (() => { throw 1 })());
```

### CSS
```css
/* Good: Semantic, maintainable */
.card-header {
    padding: 1rem;
    border-bottom: 1px solid var(--border-color);
}

/* Bad: Magic numbers, duplicated values */
.card-header {
    padding: 16.5px 17px 15px 16px;
    border-bottom: 1px solid #e5e5e5;
}
```

---

## Error Handling

### Logging Errors
```python
# Log to architect dashboard
import requests

def log_error(error_type, message, source):
    requests.post('http://localhost:8086/api/errors', json={
        'node_id': os.environ.get('AGENT_NAME', 'unknown'),
        'error_type': error_type,
        'message': message,
        'source': source,
    })
```

### Handling Database Errors
```python
# Always use WAL mode and timeouts
conn = sqlite3.connect(db_path, timeout=30)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA busy_timeout=30000')
```

### Handling API Errors
```javascript
// Always check response before using
const response = await fetch(url);
if (!response) {
    console.error('No response');
    return null;
}
if (!response.ok) {
    console.error(`API error: ${response.status}`);
    return null;
}
return response.json();
```

---

## Commit Message Format

```
<type>: <short description>

[optional body with details]

Types:
- feat: New feature
- fix: Bug fix
- refactor: Code restructure (no behavior change)
- test: Adding tests
- docs: Documentation
- style: Formatting (no code change)
```

Examples:
```
feat: Add board templates API endpoint

fix: Handle null response in dataStore.js

refactor: Extract database connection to helper function
```

---

## Session Assignment Priorities

### High Priority (assign immediately)
1. Database locking issues
2. Server crashes
3. API errors affecting users
4. Security issues

### Medium Priority
1. Feature development
2. Bug fixes (non-critical)
3. Performance improvements
4. UI/UX enhancements

### Low Priority
1. Refactoring
2. Documentation
3. Code cleanup
4. Test coverage improvement

---

## Prohibited Actions

### NEVER Do:
1. **Commit directly to main or dev branches** - ALWAYS use feature branches
2. **Merge feature branches to main** - Feature branches go to dev ONLY
3. **Force push to main or dev** - Only force push your own feature branches
4. Modify files outside your assigned scope
5. Work on same database from multiple sessions
6. Push untested code
7. Delete data without backup
8. Hardcode credentials or secrets
9. Ignore failing tests
10. Skip error handling
11. **Run servers without SSL/HTTPS** - Always use `--ssl` or `USE_HTTPS=true`

### ALWAYS Do:
1. **Use HTTPS/SSL for all web servers** - Never HTTP for shared/production
2. **Create feature branches from dev** - `git checkout dev && git checkout -b feature/name`
3. **PR to dev first** - Feature branches → dev → main
4. Check your scope/environment first
5. Pull before starting work
6. Test before committing
7. Handle errors gracefully
8. Log significant operations
9. Clean up temporary files
10. Report completion status

---

## Threshold-Based Automation

The system uses thresholds to detect patterns, prevent repeated errors, and trigger automatic actions. This makes the system smarter by learning from behavior patterns.

### Core Threshold Concepts

| Metric | Threshold | Action |
|--------|-----------|--------|
| Server restarts | 3 in 1 hour | Log as recurring error, assign to session |
| Same error repeated | 5 in 24 hours | Escalate priority, create bug ticket |
| Health check failures | 3 consecutive | Auto-restart service |
| Deployment failures | 2 consecutive | Block auto-deploy, require manual review |
| CPU > 90% | 5 minutes sustained | Alert and log for investigation |
| Memory > 85% | 10 minutes sustained | Trigger cleanup or restart |

### Error Frequency Tracking

Workers MUST track error patterns, not just individual errors:

```python
# Error tracking with frequency detection
class ErrorTracker:
    THRESHOLDS = {
        'restart_per_hour': 3,      # Max restarts before flagging
        'same_error_per_day': 5,    # Same error repeats
        'health_failures': 3,        # Consecutive health check fails
    }

    def record_error(self, error_type, source):
        # Count occurrences in time window
        count = self.count_recent(error_type, source, hours=1)
        if count >= self.THRESHOLDS.get(error_type, 5):
            self.escalate_to_bug(error_type, source, count)
```

### Restart Threshold Rules

When a service requires restart:
1. **First restart**: Normal operation, log it
2. **Second restart (within 1 hour)**: Warning, increase monitoring
3. **Third restart (within 1 hour)**: STOP auto-restarting, create error ticket
   - Something is fundamentally broken
   - Assign to a session to investigate root cause
   - Do NOT keep restarting - this masks the real problem

### Auto-Deployment Thresholds

Deployments are automated ONLY when thresholds are met:

| Condition | Threshold | Deploy? |
|-----------|-----------|---------|
| Tests passing | 100% | Required |
| Health check | 3 consecutive passes | Required |
| Error rate | < 1% for 5 minutes | Required |
| Previous deploy | > 10 minutes ago | Required |
| Failed deploys today | < 2 | Required |

If ANY threshold is not met, deployment is blocked and requires manual approval.

### Pattern Recognition

Workers should detect these patterns and escalate:

1. **Cyclical Failures**: Error → Fix → Same Error
   - If same fix is applied 3+ times, the fix is wrong
   - Escalate for architectural review

2. **Cascading Errors**: Error A causes Error B causes Error C
   - Track error chains, fix root cause (A), not symptoms

3. **Time-Based Patterns**: Errors at specific times
   - Track error timestamps
   - Identify cron jobs, scheduled tasks, or load patterns

4. **Resource Exhaustion**: Gradual degradation
   - Memory leaks, connection pool exhaustion
   - Track trends, not just current values

### Threshold Configuration

Thresholds are configured in `config/thresholds.yaml`:

```yaml
thresholds:
  restart:
    max_per_hour: 3
    cooldown_minutes: 30
    escalate_after: 3

  errors:
    duplicate_window_hours: 24
    duplicate_count_escalate: 5
    priority_boost_after: 3

  deployment:
    min_interval_minutes: 10
    max_failures_per_day: 2
    required_health_checks: 3

  resources:
    cpu_alert_percent: 90
    cpu_alert_duration_minutes: 5
    memory_alert_percent: 85
    memory_alert_duration_minutes: 10
```

### Worker Implementation Requirements

All monitoring workers MUST:

1. **Track frequency, not just occurrence**
   - Use sliding time windows (1 hour, 24 hours)
   - Count occurrences per window

2. **Check thresholds before acting**
   - Don't auto-restart past threshold
   - Don't auto-deploy past threshold

3. **Escalate when thresholds exceeded**
   - Create bug/error ticket
   - Assign to available session
   - Include frequency data in report

4. **Log all threshold events**
   - When threshold approached (80%)
   - When threshold exceeded
   - When threshold reset (after cooldown)

### Example: Smart Restart Logic

```python
def should_restart_service(service_name):
    """Check if service should be auto-restarted."""
    restarts = get_restart_count(service_name, hours=1)

    if restarts >= THRESHOLDS['restart']['max_per_hour']:
        # Too many restarts - something is fundamentally wrong
        create_error_ticket(
            title=f"{service_name} requires {restarts} restarts/hour",
            priority="high",
            message="Auto-restart disabled. Root cause investigation needed."
        )
        return False  # Do NOT restart

    if restarts >= THRESHOLDS['restart']['max_per_hour'] - 1:
        # Approaching threshold - warn
        log_warning(f"{service_name} restart count: {restarts}")

    return True  # Safe to restart
```

---

## Quick Reference

### Check Your Assignment
```bash
python3 session_assigner.py status
```

### Assign a Task
```bash
python3 session_assigner.py assign <session> "<task>" --project <project> --env <env>
```

### Start Claude Manager
```bash
python3 claude_manager.py
```

### Release Assignment
```bash
python3 session_assigner.py release <session>
```

### View Session Detail
```bash
tmux capture-pane -t <session> -p | tail -50
```
