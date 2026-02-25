# Worker Automation System

## Overview

Development sessions now focus **ONLY on development**. All non-development work (PR reviews, merging, deployments, testing) is handled automatically by specialized worker sessions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Development Sessions                     │
│   (architect, foundation, dev_worker1-3)                   │
│                                                              │
│   Responsibilities: ONLY CODE                               │
│   - Implement features                                      │
│   - Fix bugs                                                │
│   - Refactor code                                           │
│   - Write documentation                                     │
│                                                              │
│   NOT responsible for:                                      │
│   ❌ Testing                                                │
│   ❌ PR reviews                                             │
│   ❌ Merging                                                │
│   ❌ Deployments                                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Task Router
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Specialized Workers                        │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐                 │
│  │ PR Review Worker│  │Deployment Worker │                 │
│  │                 │  │                  │                 │
│  │ - Auto review   │  │ - Run tests      │                 │
│  │ - Check tests   │  │ - Tag releases   │                 │
│  │ - Auto merge    │  │ - Deploy to QA   │                 │
│  │ - Comment       │  │ - Deploy to prod │                 │
│  └─────────────────┘  └──────────────────┘                 │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐                 │
│  │ Testing Worker  │  │ Task Router      │                 │
│  │                 │  │                  │                 │
│  │ - Run tests     │  │ - Route tasks    │                 │
│  │ - Report errors │  │ - Classify work  │                 │
│  │ - Track coverage│  │ - Send to sessions│                │
│  └─────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Workers

### 1. PR Review Worker (`pr_review_worker.py`)

**Responsibilities**:
- Monitor for open pull requests
- Run automated code review
- Check tests pass
- Auto-merge if criteria met
- Comment on PRs with issues

**Auto-merge Criteria**:
- ✅ Not a draft PR
- ✅ No merge conflicts
- ✅ All tests passing
- ✅ Code review passes
- ✅ No security issues (hardcoded secrets)

**Usage**:
```bash
# Run as daemon (checks every 5 minutes)
python3 workers/pr_review_worker.py --daemon 300

# Review specific PR
python3 workers/pr_review_worker.py --review 123

# Run once and exit
python3 workers/pr_review_worker.py --run-once

# Get status
python3 workers/pr_review_worker.py --status
```

**Output Example**:
```
Processing PR #45
✅ PR #45 approved
✅ PR #45 merged

Comment added:
  ✅ Automated review passed. PR merged automatically.
  - Tests: ✅ Passing
  - Code review: ✅ Approved
  - Merge conflicts: ✅ None
```

---

### 2. Deployment Worker (`deployment_worker.py`)

**Responsibilities**:
- Monitor dev branch for new commits
- Run tests automatically
- Tag releases
- Deploy to QA
- Send notifications

**Deployment Flow**:
1. Check dev branch for new commits
2. Run full test suite
3. If tests pass → create tag
4. Deploy to QA automatically
5. Notify team
6. Update deployment state

**Usage**:
```bash
# Run as daemon (checks every 5 minutes)
python3 workers/deployment_worker.py --daemon 300

# Deploy once and exit
python3 workers/deployment_worker.py --run-once

# Get status
python3 workers/deployment_worker.py --status

# Test only (no deploy)
python3 workers/deployment_worker.py --test
```

**Output Example**:
```
Starting deployment cycle...
Found 3 new commits
Running tests...
✅ Tests passed
Created tag: v2.1.0
Deploying v2.1.0 to QA...
✅ Deployment successful
```

---

### 3. Task Router (`task_router.py`)

**Responsibilities**:
- Classify incoming tasks
- Route to appropriate session type
- Track routing statistics
- Ensure separation of concerns

**Task Classification**:

| Task Pattern | Routed To | Priority |
|--------------|-----------|----------|
| deploy*, release* | deployment_worker | 100 |
| merge*, review pr* | pr_review_worker | 90 |
| test*, qa* | testing_worker | 70 |
| fix*, bugfix* | development | 70 |
| implement*, feature* | development | 60 |
| refactor* | development | 50 |
| monitor* | monitoring | 50 |

**Usage**:
```bash
# Classify a task (shows routing decision)
python3 workers/task_router.py --classify "Deploy v2.0 to production"

# Route task (logs routing)
python3 workers/task_router.py --route "Fix login bug"

# Route and send to session immediately
python3 workers/task_router.py --send "Review PR #123"

# Get routing statistics
python3 workers/task_router.py --stats
```

**Output Example**:
```json
{
  "success": true,
  "task_type": "deployment",
  "session": "deployment_worker",
  "priority": 100,
  "classification": {
    "matched_pattern": "deploy%"
  }
}
```

---

## Session Types

### Development Sessions

**Sessions**: `architect`, `foundation`, `dev_worker1`, `dev_worker2`, `dev_worker3`

**Task Types**:
- Feature implementation
- Bug fixes
- Code refactoring
- Documentation
- Code reviews (manual, not auto)

**What they DON'T do**:
- ❌ Deploy to QA/Production
- ❌ Merge pull requests
- ❌ Run automated tests (workers do this)
- ❌ Tag releases

### Deployment Sessions

**Sessions**: `deployment_worker`

**Task Types**:
- Automated deployments
- Release tagging
- Test execution
- Environment management

### PR Review Sessions

**Sessions**: `pr_review_worker`

**Task Types**:
- PR code review
- Test verification
- Auto-merging
- PR comments

### Testing Sessions

**Sessions**: `qa_tester1`, `qa_tester2`, `qa_tester3`, `testing_worker`

**Task Types**:
- Test execution
- Coverage reports
- Error tracking
- Verification

---

## Workflow Examples

### Example 1: Developer Creates Feature

**Old Way** (before workers):
```
1. Developer codes feature
2. Developer runs tests manually
3. Developer creates PR
4. Developer reviews own PR
5. Developer merges PR
6. Developer tags release
7. Developer deploys to QA
8. Developer monitors deployment
```

**New Way** (with workers):
```
1. Developer codes feature
2. Developer commits to feature branch
3. Developer creates PR

   → PR Review Worker automatically:
     - Reviews code
     - Runs tests
     - Merges if approved
     - Comments with status

   → Deployment Worker automatically:
     - Detects merge to dev
     - Runs tests
     - Tags release
     - Deploys to QA
     - Notifies team

Developer moves on to next task immediately!
```

### Example 2: Task Routing in Action

**Developer gets task**: "Implement user authentication"

```bash
# Task router classifies it
$ python3 workers/task_router.py --classify "Implement user authentication"
{
  "task_type": "development",
  "priority": 60,
  "matched_pattern": "implement%"
}

# Routes to development session
$ python3 workers/task_router.py --send "Implement user authentication"
{
  "success": true,
  "session": "foundation",
  "sent": true
}

# Task appears in foundation session
# Developer works on it
# When done, commits and creates PR
# PR Review Worker takes over from there
```

**Different task**: "Deploy v2.1.0 to production"

```bash
# Task router classifies it
$ python3 workers/task_router.py --classify "Deploy v2.1.0 to production"
{
  "task_type": "deployment",
  "priority": 100,
  "matched_pattern": "deploy%"
}

# Routes to deployment worker (NOT developer)
$ python3 workers/task_router.py --send "Deploy v2.1.0 to production"
{
  "success": true,
  "session": "deployment_worker",
  "sent": true
}

# Deployment worker handles it automatically
# Developer never interrupted
```

---

## Starting Workers

### Start All Workers

```bash
# Start deployment worker
python3 workers/deployment_worker.py --daemon 300 &

# Start PR review worker
python3 workers/pr_review_worker.py --daemon 300 &

# Check status
python3 workers/deployment_worker.py --status
python3 workers/pr_review_worker.py --status
```

### Or Use Tmux Sessions

```bash
# Create dedicated worker sessions
tmux new-session -d -s deployment_worker "python3 workers/deployment_worker.py --daemon 300"
tmux new-session -d -s pr_review_worker "python3 workers/pr_review_worker.py --daemon 300"

# Check they're running
tmux list-sessions | grep worker
```

---

## Benefits

### For Developers

1. **Focus**: Only code, no context switching to deployments
2. **Speed**: Move from feature to feature without waiting
3. **No interruptions**: Workers handle everything asynchronously
4. **Less responsibility**: Don't need to remember deployment steps

### For Project

1. **Consistency**: Automated processes never forget steps
2. **Reliability**: Workers run same checks every time
3. **Speed**: Parallel processing (dev codes while workers deploy)
4. **Audit trail**: All actions logged in databases

### For CI/CD

1. **Continuous deployment**: Automatic on every merge
2. **Continuous testing**: Automatic on every PR
3. **Continuous review**: No PRs sit unreviewed
4. **Continuous improvement**: Workers collect metrics

---

## Configuration

### Routing Rules

Add custom routing rules to `data/task_routing.db`:

```sql
INSERT INTO routing_rules (task_pattern, session_type, priority)
VALUES ('hotfix%', 'development', 100);
```

### Worker Check Intervals

- **Deployment Worker**: Default 300s (5 min) - can adjust
- **PR Review Worker**: Default 300s (5 min) - can adjust

Change via command line:
```bash
# Check every 1 minute
python3 workers/deployment_worker.py --daemon 60
```

---

## Monitoring

### Check Worker Status

```bash
# Deployment worker
python3 workers/deployment_worker.py --status

# PR review worker
python3 workers/pr_review_worker.py --status

# Task router stats
python3 workers/task_router.py --stats
```

### Status Output

**Deployment Worker**:
```json
{
  "worker": "deployment_worker",
  "last_checked": "2026-02-15T05:30:00",
  "last_deployed_commit": "791cc58",
  "total_deployments": 15,
  "failed_deployments": 1,
  "success_rate": 93.33,
  "recent_deployments": [...]
}
```

**PR Review Worker**:
```json
{
  "worker": "pr_review_worker",
  "prs_reviewed": 25,
  "prs_merged": 20,
  "prs_rejected": 5,
  "approval_rate": 80.0
}
```

**Task Router**:
```json
{
  "total_routes": 150,
  "by_type": {
    "development": 100,
    "deployment": 30,
    "pr_review": 15,
    "testing": 5
  },
  "by_status": {
    "sent": 145,
    "pending": 5
  }
}
```

---

## Troubleshooting

### Worker Not Processing

**Check if running**:
```bash
ps aux | grep deployment_worker
ps aux | grep pr_review_worker
```

**Check logs**:
```bash
tail -f logs/deployment_worker.log
```

**Restart worker**:
```bash
pkill -f deployment_worker
python3 workers/deployment_worker.py --daemon 300 &
```

### Task Not Routed

**Check classification**:
```bash
python3 workers/task_router.py --classify "your task here"
```

**Check session running**:
```bash
tmux list-sessions | grep <session_name>
```

**Manual route**:
```bash
python3 workers/task_router.py --send "your task here"
```

---

## Summary

**Development sessions**: Only code
**PR Review Worker**: Automatic reviews and merging
**Deployment Worker**: Automatic testing and deployment
**Task Router**: Routes work to right place

**Result**: Developers stay in flow, everything else is automated!
