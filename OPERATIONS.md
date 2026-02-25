# Architect Operations Manual (SOP)

> Standard Operating Procedures for the Architect Dashboard and Multi-Agent Development Environment

**Last Updated**: December 2024
**Version**: 1.0

---

## Table of Contents

1. [Core Rules](#core-rules)
2. [Development Workflow](#development-workflow)
3. [Worker Sessions & Roles](#worker-sessions--roles)
4. [Environment Management](#environment-management)
5. [Testing Requirements](#testing-requirements)
6. [Deployment Process](#deployment-process)
7. [Task Delegation](#task-delegation)
8. [Application Overview](#application-overview)
9. [Troubleshooting](#troubleshooting)

---

## Core Rules

### CRITICAL: These Rules Must NEVER Be Violated

| # | Rule | Consequence of Violation |
|---|------|--------------------------|
| 1 | **No two agents work the same directory simultaneously** | Merge conflicts, data corruption, lost work |
| 2 | **No direct work on dev/main/qa/prod branches** | Broken CI/CD, untested code in production |
| 3 | **Deployments are milestone-based** | Batch fixes and emergency patches only |
| 4 | **command_runner is for delegation ONLY** | Session used for managing, NOT executing tasks |

### Branch Protection Matrix

| Branch | Direct Commits | Who Can Merge | Purpose |
|--------|----------------|---------------|---------|
| `main` | NEVER | Release manager only | Production releases |
| `dev` | NEVER | After PR approval | Integration branch |
| `qa` | NEVER | Deployment script only | Testing via deploy |
| `prod` | NEVER | Automated only | Production mirror |
| `feature/*` | YES | Developer | Active work |
| `fix/*` | YES | Developer | Bug fixes |
| `agent/*` | YES | Assigned agent | Agent work |

---

## Development Workflow

### Feature Branch Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Create    │────▶│   Develop   │────▶│   Review    │────▶│   Merge     │
│   Branch    │     │   & Test    │     │   & QA      │     │   to Dev    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  feature/name-MMDD   Local testing      Deploy to QA       PR to dev
```

### Step-by-Step Process

#### 1. Start New Work
```bash
# ALWAYS create a feature branch first
git checkout dev
git pull origin dev
git checkout -b feature/description-MMDD

# Or use the agent manager
python3 agent_manager.py create <agent-name>

# Or use branch enforcer
python3 branch_enforcer.py assign <session-name> "task description"
```

#### 2. Development Cycle
```bash
# Make changes
# ... edit files ...

# Test locally
python3 -m pytest tests/ -q

# Commit frequently
git add .
git commit -m "Descriptive message"
```

#### 3. Ready for Review
```bash
# Push feature branch
git push origin feature/description-MMDD

# Create tag for deployment
git tag v1.0.X -m "Description of changes"
git push origin v1.0.X

# Deploy to QA for testing
./deploy.sh qa v1.0.X
```

#### 4. Merge to Dev
```bash
# After QA approval
git checkout dev
git pull origin dev
git merge feature/description-MMDD
git push origin dev
```

### Environment Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                         PRODUCTION                               │
│                    Port: 8080 / 5063                            │
│                  Tagged releases only                            │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Deploy after QA approval
                              │
┌─────────────────────────────────────────────────────────────────┐
│                             QA                                   │
│                    Port: 8081 / 5052                            │
│              Deployed versions only - NO direct edits            │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ ./deploy.sh qa v1.0.X
                              │
┌─────────────────────────────────────────────────────────────────┐
│                            DEV                                   │
│                    Port: 8082 / 5051                            │
│               Integration branch - merge only                    │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Merge approved PRs
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      FEATURE BRANCHES                            │
│                    Port: 8085+ / env3+                          │
│                   Active development here                        │
└─────────────────────────────────────────────────────────────────┘
```

### Code Review Process

1. **Self-Review**: Developer reviews own changes before PR
2. **Automated Tests**: All tests must pass
3. **Peer Review**: Another developer/agent reviews code
4. **QA Testing**: Deploy to QA and verify functionality
5. **Approval**: Reviewer approves PR
6. **Merge**: Merge to dev branch

---

## Worker Sessions & Roles

### Session Overview

| Session Name | Role | Allowed Actions | Forbidden Actions |
|--------------|------|-----------------|-------------------|
| `command_runner` | Management/Delegation | Assign tasks, monitor progress, coordinate | Execute tasks, write code, modify files |
| `task_worker1-5` | General task execution | Any assigned development task | Work on same dir as another worker |
| `arch_worker1` | Architecture/Dashboard | Architecture routes, dashboard features | Education app work |
| `edu_worker1` | Education apps | Typing, Math, Reading, Piano apps | Architecture/dashboard work |
| `queue_manager` | Task queue management | Manage task queue, prioritize work | Direct development |
| `audit_manager` | Auditing and SOP | Review code, enforce standards, documentation | Direct development |

### Session Management Commands

```bash
# List all tmux sessions
tmux list-sessions

# Create a new worker session
tmux new-session -d -s task_worker1

# Attach to a session
tmux attach -t task_worker1

# Send command to session
tmux send-keys -t task_worker1 "command here" Enter

# Kill a session
tmux kill-session -t task_worker1
```

### Worker Assignment Rules

1. **One directory per worker**: Never assign two workers to the same directory
2. **Check before assigning**: Verify no other worker is active in target directory
3. **Clear handoffs**: When passing work, ensure previous worker has committed/pushed
4. **Monitor progress**: Use dashboard to track worker activity

### Directory Ownership Matrix

| Directory | Primary Worker | Backup Worker |
|-----------|----------------|---------------|
| `/architect/` | arch_worker1 | task_worker1 |
| `/basic_edu_apps_final/environments/` | edu_worker1 | task_worker2 |
| `/basic_edu_apps_final/environments/architecture/` | arch_worker1 | edu_worker1 |
| `/basic_edu_apps_final/environments/typing/` | edu_worker1 | task_worker3 |
| `/basic_edu_apps_final/environments/math/` | edu_worker1 | task_worker4 |
| `/basic_edu_apps_final/environments/reading/` | edu_worker1 | task_worker5 |

---

## Environment Management

### Port Assignments

| Environment | Architect Port | Edu Apps Port | Purpose |
|-------------|----------------|---------------|---------|
| Production | 8080 | 5063 | Live users |
| QA | 8081 | 5052 | Testing deployed versions |
| Development | 8082 | 5051 | Integration testing |
| Env3 (Feature) | 8085 | 5053 | Feature development |
| Env4 (Feature) | 8086 | 5054 | Feature development |
| Env5 (Feature) | 8087 | 5055 | Feature development |

### Database Isolation

Each environment has its own database to prevent cross-contamination:

```
Production:    data/architect.db           education_central.db
QA:            qa_data/architect.db        qa_data/education_central.db
Development:   dev_data/architect.db       (uses main, isolated by port)
Feature Envs:  env_X_data/architect.db     feature_environments/env_X/
```

### Environment Variables

```bash
# Architect Dashboard
export PORT=8080
export ARCHITECT_USER=architect
export ARCHITECT_PASSWORD=peace5

# Education Apps
export APP_ENV=dev|qa|prod
export PORT=5051|5052|5063
export USE_HTTPS=true
```

### Starting Environments

```bash
# Architect Dashboard
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
./deploy.sh                    # Production on 8080
./deploy.sh --port 8081        # QA on 8081

# Education Apps
cd /Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final/environments
USE_HTTPS=true APP_ENV=dev PORT=5051 python3 unified_app.py    # DEV
USE_HTTPS=true APP_ENV=qa PORT=5052 python3 unified_app.py     # QA
USE_HTTPS=true APP_ENV=prod PORT=5063 python3 unified_app.py   # PROD
```

### Cross-Environment Rules

| Action | Allowed? | Notes |
|--------|----------|-------|
| Read prod data from dev | NO | Use test data |
| Write to QA directly | NO | Deploy only |
| Copy prod DB to dev | YES | For debugging (sanitize first) |
| Share feature env | NO | One developer per env |
| Run tests against prod | NO | Never |

---

## Testing Requirements

### Pre-Merge Checklist

- [ ] All pytest tests pass
- [ ] No new linting errors
- [ ] Client-side error handling verified
- [ ] Server-side error handling verified
- [ ] Manual testing in DEV environment
- [ ] Code reviewed by peer/agent

### Test Commands

```bash
# Run all tests
python3 -m pytest -q

# Run specific test file
python3 -m pytest tests/test_app.py -v

# Run with coverage
python3 -m pytest --cov=. --cov-report=html

# Run architecture dashboard tests
python3 -m pytest tests/test_architecture_dashboard.py -v

# Run smoke tests
python3 smoke_test.py
```

### Error Catching Requirements

#### Client-Side (JavaScript)
```javascript
// All API calls must have error handling
try {
    const response = await fetch('/api/endpoint');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
} catch (error) {
    console.error('API Error:', error);
    showUserError('Operation failed. Please try again.');
    // Log to server
    fetch('/api/log_error', {
        method: 'POST',
        body: JSON.stringify({ error: error.message, source: 'client' })
    });
}
```

#### Server-Side (Python)
```python
@app.route('/api/endpoint')
def endpoint():
    try:
        # Business logic
        return jsonify({'success': True, 'data': result})
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except NotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        log_error(e)  # Log to errors.md or database
        return jsonify({'error': 'Internal server error'}), 500
```

### Test Coverage Requirements

| Component | Minimum Coverage | Critical Paths |
|-----------|------------------|----------------|
| API Routes | 80% | All CRUD operations |
| Authentication | 100% | Login, logout, session |
| Database Operations | 90% | Migrations, queries |
| Error Handling | 100% | All error types |

---

## Deployment Process

### Deployment Types

| Type | When | Process |
|------|------|---------|
| Milestone Release | Batch of features complete | Full testing cycle |
| Emergency Patch | Critical bug in production | Expedited review |
| Hotfix | Urgent security issue | Immediate deploy |

### Tag-Based Deployment

```bash
# 1. Ensure all tests pass
python3 -m pytest -q

# 2. Create annotated tag
git tag -a v1.0.X -m "Release description"

# 3. Push tag
git push origin v1.0.X

# 4. Deploy to QA
./deploy.sh qa v1.0.X

# 5. Test in QA environment
# ... manual and automated testing ...

# 6. Deploy to Production (after approval)
./deploy.sh prod v1.0.X
```

### Milestone/Batch Approach

```
Week 1: Feature development in branches
Week 2: Integration testing in dev
Week 3: QA testing (v1.0.X-rc1)
Week 4: Production release (v1.0.X)
```

### Emergency Patch Procedure

```bash
# 1. Create hotfix branch from production tag
git checkout -b hotfix/critical-issue v1.0.X

# 2. Apply fix
# ... minimal changes only ...

# 3. Test locally
python3 -m pytest tests/test_affected_area.py -v

# 4. Create patch tag
git tag -a v1.0.X-patch1 -m "Emergency fix: description"
git push origin v1.0.X-patch1

# 5. Deploy directly to QA
./deploy.sh qa v1.0.X-patch1

# 6. Quick verification (15 min max)

# 7. Deploy to production
./deploy.sh prod v1.0.X-patch1

# 8. Merge fix back to dev
git checkout dev
git merge hotfix/critical-issue
git push origin dev
```

### Rollback Procedure

```bash
# Identify last good version
git tag -l 'v1.0.*'

# Deploy previous version
./deploy.sh prod v1.0.PREVIOUS

# Notify team
# ... send alert ...
```

---

## Task Delegation

### How to Assign Tasks to Workers

#### Via Dashboard UI
1. Navigate to **Features**, **Bugs**, or **Errors** panel
2. Select the item to assign
3. Click **"Assign"** button
4. Choose target tmux session from dropdown
5. Customize message if needed
6. Click **"Send"**

#### Via API
```bash
curl -X POST http://localhost:8080/api/assign-to-tmux \
  -H "Content-Type: application/json" \
  -d '{
    "session": "task_worker1",
    "task_type": "feature",
    "task_id": 123,
    "message": "Implement user authentication"
  }'
```

#### Via tmux Direct
```bash
# Send task description to worker
tmux send-keys -t task_worker1 "
# TASK: Implement user authentication
# Priority: High
# Branch: feature/auth-MMDD
# Files: auth.py, templates/login.html
# Requirements:
# - Add login/logout endpoints
# - Session management
# - Password hashing
" Enter
```

### Monitoring Progress

#### Dashboard Panels
- **tmux Sessions**: View active sessions and recent output
- **Task Queue**: Track pending/active/completed tasks
- **Activity Log**: Audit trail of all actions

#### Command Line
```bash
# Capture worker output
tmux capture-pane -t task_worker1 -p | tail -50

# Check git status in worker's directory
tmux send-keys -t task_worker1 "git status" Enter

# List worker's recent commits
tmux send-keys -t task_worker1 "git log --oneline -5" Enter
```

### Auto-Approval Patterns

Configure patterns in `wrapper_core/config.py` or worker settings:

```python
# Commands that can be auto-approved
AUTO_APPROVE_PATTERNS = [
    r'^git (status|log|diff|branch)',      # Read-only git
    r'^python3 -m pytest',                  # Running tests
    r'^ls|^cat|^head|^tail',               # Read-only file ops
    r'^curl .* --head',                     # HEAD requests only
]

# Commands requiring manual approval
REQUIRE_APPROVAL_PATTERNS = [
    r'^rm ',                                # Delete operations
    r'^git push.*--force',                  # Force push
    r'^git reset --hard',                   # Hard reset
    r'^DROP|^DELETE|^TRUNCATE',            # Destructive SQL
]
```

### Task Priority Levels

| Priority | Response Time | Examples |
|----------|---------------|----------|
| Critical | Immediate | Security issue, data loss |
| High | Within 1 hour | Blocking bug, broken feature |
| Medium | Within 4 hours | Non-blocking bug, enhancement |
| Low | Within 24 hours | Documentation, cleanup |

---

## Application Overview

### Architect Dashboard Purpose

The Architect Dashboard is a **centralized command center** for:

1. **Project Management**: Track projects, milestones, features, and bugs
2. **Multi-Agent Coordination**: Manage Claude Code sessions via tmux
3. **Error Aggregation**: Collect and triage errors from all environments
4. **Deployment Control**: Manage releases across environments
5. **Cluster Monitoring**: Track node health and metrics

### Key Features

#### Projects Panel
- Create and manage projects
- Link to source code directories
- Track project health metrics
- Archive completed projects

#### Milestones Panel
- Group features into releases
- Set target dates
- Track completion percentage
- Generate release notes

#### Features Panel
- Track feature specifications
- Link to branches and PRs
- Monitor development progress
- Assign to workers

#### Bugs Panel
- Log and track bugs
- Set severity and priority
- Link to related features
- Track resolution time

#### Errors Panel
- Aggregate errors from all nodes
- Deduplicate by type/message
- Convert to bugs
- Track resolution

#### tmux Panel
- List all active sessions
- Send commands to sessions
- Capture session output
- Create/kill sessions

#### Nodes Panel
- Monitor cluster health
- CPU/memory/disk metrics
- Node uptime tracking
- Alert on issues

#### Deployments Panel
- View deployment history
- Trigger new deployments
- Rollback capability
- Environment status

### Education Apps Overview

| App | Purpose | Key Features |
|-----|---------|--------------|
| Typing | Typing practice | Speed tests, lessons, journey mode |
| Math | Math practice | Problem generation, mastery tracking |
| Reading | Reading practice | Comprehension, word recognition |
| Piano | Piano practice | Lessons, performance tracking |

### API Quick Reference

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| Projects | `/api/projects` | GET/POST | List/create projects |
| Features | `/api/features` | GET/POST | List/create features |
| Bugs | `/api/bugs` | GET/POST | List/create bugs |
| Errors | `/api/errors` | GET/POST | List/log errors |
| tmux | `/api/tmux/sessions` | GET | List sessions |
| tmux | `/api/tmux/send` | POST | Send command |
| Tasks | `/api/tasks` | GET/POST | Task queue |
| Stats | `/api/stats` | GET | Dashboard stats |

---

## Troubleshooting

### Common Issues

#### Server Won't Start
```bash
# Check if port is in use
lsof -i :8080
lsof -i :5051

# Kill blocking process
kill -9 <PID>

# Check logs
tail -f /tmp/architect_dashboard.log
tail -f /tmp/unified_app.log
```

#### tmux Sessions Not Showing
```bash
# Verify tmux is running
tmux list-sessions

# Refresh from dashboard
curl -X POST http://localhost:8080/api/tmux/sessions/refresh

# Check permissions
ls -la /tmp/tmux-*
```

#### Database Issues
```bash
# Backup database
cp data/architect.db data/architect.db.backup

# Check integrity
sqlite3 data/architect.db "PRAGMA integrity_check;"

# Reset (last resort)
rm data/architect.db
python3 -c "from app import init_db; init_db()"
```

#### Git Conflicts
```bash
# Check status
git status

# Stash local changes
git stash

# Pull latest
git pull origin dev

# Apply stash
git stash pop

# Resolve conflicts manually if needed
```

### Health Checks

```bash
# Architect Dashboard
curl http://localhost:8080/health

# Education Apps
curl -k https://localhost:5051/api/deployment/status

# Worker status
python3 workers/task_worker.py --status

# Node agent status
python3 distributed/node_agent.py --status
```

### Emergency Contacts

| Issue Type | Escalation Path |
|------------|-----------------|
| Production down | command_runner -> manual intervention |
| Security breach | Immediate shutdown, audit |
| Data corruption | Restore from backup |
| Performance issue | Monitor, scale if needed |

---

## Appendix

### Quick Reference Commands

```bash
# Start everything
./deploy.sh                                    # Architect
USE_HTTPS=true APP_ENV=dev PORT=5051 python3 unified_app.py  # Edu Apps

# Check status
./deploy.sh status
ps aux | grep unified_app

# View logs
tail -f /tmp/architect_dashboard.log
tail -f /tmp/unified_app.log

# Run tests
python3 -m pytest -q
python3 smoke_test.py

# Deploy
./deploy.sh qa v1.0.X
./deploy.sh prod v1.0.X

# Git workflow
git checkout -b feature/name-MMDD
git add . && git commit -m "message"
git tag -a v1.0.X -m "description"
git push origin v1.0.X
```

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2024 | Initial SOP document |

---

*This document is maintained by the audit_manager session. Updates require review and approval.*
