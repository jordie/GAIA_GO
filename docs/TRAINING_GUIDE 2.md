# Architect Dashboard Training Guide

Comprehensive training materials for new team members and operators.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Core Workflows](#core-workflows)
4. [Advanced Features](#advanced-features)
5. [Best Practices](#best-practices)
6. [Common Tasks](#common-tasks)
7. [Training Exercises](#training-exercises)

---

## Getting Started

### Prerequisites

Before beginning training, ensure you have:
- Access to the Architect Dashboard (https://your-dashboard-url)
- Login credentials (default: architect/peace5)
- Basic understanding of:
  - Git and version control
  - Command-line interfaces
  - Database concepts (SQLite)
  - tmux (optional but helpful)

### First Login

1. Navigate to the dashboard URL
2. Log in with provided credentials
3. Familiarize yourself with the main navigation
4. Check the **Overview** panel for system status

### Navigation Structure

```
┌─ Overview ─────────────┐
├─ Projects             │  Manage projects and milestones
├─ Features             │  Track feature development
├─ Tasks                │  Task queue and assignments
├─ Bugs                 │  Bug tracking and triage
├─ Nodes                │  Cluster node management
├─ Workers              │  Background worker status
├─ Sessions             │  tmux session monitoring
├─ Testing              │  Test campaigns and results
├─ Errors               │  Error aggregation across nodes
└─ Settings             │  System configuration
```

---

## Dashboard Overview

### Main Panels

#### 1. Overview Dashboard
**Purpose**: Real-time system health and activity monitoring

**Key Metrics**:
- Active projects and features
- Task queue depth
- Worker status (idle/busy/offline)
- Recent errors and alerts
- Node cluster health

**When to Use**: Daily standup, system health checks

#### 2. Projects Panel
**Purpose**: Project portfolio management

**Features**:
- Create/edit projects
- Set milestones and deadlines
- Track completion status
- View project hierarchy

**When to Use**: Sprint planning, roadmap reviews

#### 3. Tasks Panel
**Purpose**: Task queue management and assignment

**Features**:
- View pending/in-progress/completed tasks
- Assign tasks to workers or agents
- Set priorities (high/medium/low)
- Filter and search
- Kanban board view

**When to Use**: Daily task assignment, workload balancing

#### 4. Sessions Panel
**Purpose**: tmux session monitoring and control

**Features**:
- View all active tmux sessions
- Send commands to sessions
- Capture output (scrollback)
- Health monitoring
- Auto-restart failed sessions

**When to Use**: Worker monitoring, debugging, command execution

---

## Core Workflows

### Workflow 1: Creating a New Project

1. Navigate to **Projects** panel
2. Click **+ New Project**
3. Fill in details:
   - Name: Descriptive project name
   - Description: Project goals and scope
   - Priority: high/medium/low
   - Deadline: Target completion date
4. Click **Create**
5. Add milestones and features

**Best Practice**: Use consistent naming (e.g., "2026-Q1-feature-name")

### Workflow 2: Assigning Tasks

1. Navigate to **Tasks** panel
2. Click on a pending task
3. Review task details:
   - Description
   - Estimated effort
   - Required skills
4. Click **Assign**
5. Select agent/worker from dropdown
6. Set priority if needed
7. Click **Confirm**

**Best Practice**: Balance workload across workers

### Workflow 3: Monitoring Worker Sessions

1. Navigate to **Sessions** panel
2. View session list with status indicators:
   - 🟢 Green: Healthy and active
   - 🟡 Yellow: Degraded (warnings)
   - 🔴 Red: Unhealthy (errors)
3. Click session to view details:
   - Current task
   - Last heartbeat
   - Restart count
   - Event history
4. Use controls:
   - **Restart**: Manually restart session
   - **Send Command**: Execute command in session
   - **View Output**: Capture scrollback

**Best Practice**: Check session health every 30 minutes

### Workflow 4: Handling Errors

1. Navigate to **Errors** panel
2. Filter by:
   - Severity (critical/high/medium/low)
   - Node
   - Time range
3. Click error to view details:
   - Stack trace
   - Context
   - Frequency
4. Take action:
   - **Resolve**: Mark as fixed
   - **Assign**: Route to developer
   - **Suppress**: Ignore known issues
5. Add notes for tracking

**Best Practice**: Triage errors within 15 minutes of detection

### Workflow 5: Deploying Changes

1. Navigate to **Deployments** panel
2. Select environment (dev/qa/prod)
3. Choose deployment strategy:
   - **Blue-Green**: Zero-downtime deployment
   - **Rolling**: Gradual rollout
   - **Direct**: Immediate replacement
4. Select version/tag to deploy
5. Review health checks
6. Click **Deploy**
7. Monitor deployment progress
8. Verify health after deployment

**Best Practice**: Always test in QA before prod

---

## Advanced Features

### LLM Provider Failover

The system automatically switches between LLM providers when one fails:

**Failover Chain**:
```
Claude (primary) → Ollama (local) → AnythingLLM → Gemini → OpenAI
```

**Monitor Failover**:
1. Navigate to `/llm-metrics` dashboard
2. View:
   - Success rates per provider
   - Cost distribution
   - Failover event history
   - Circuit breaker status

**Manual Circuit Breaker Reset**:
```bash
POST /api/llm-metrics/reset-circuits
```

### Session Pool Management

Automatic health monitoring and recovery for worker sessions.

**Check Pool Health**:
```bash
GET /api/session-pool/health-summary
```

**Manual Session Restart**:
1. Navigate to **Sessions** panel
2. Find unhealthy session
3. Click **Restart**
4. Verify recovery in events log

**Auto-Restart Configuration**:
- Max restart attempts: 10
- Heartbeat timeout: 15 minutes
- Health check interval: 30 seconds

### Crawl Results Storage

Store and analyze web crawler task results.

**View Crawl History**:
```bash
GET /api/crawl/history?limit=50&success=true
```

**Analyze Stats**:
```bash
GET /api/crawl/stats
```

**Response includes**:
- Success rate by provider
- Average duration
- Recent crawls

### Go Wrapper Monitoring

Real-time monitoring for autonomous agent tasks.

**Access Dashboard**: Navigate to `/go-wrapper-monitor`

**Features**:
- Agent status (idle/busy/error)
- Task completion tracking
- Health alerts
- Performance charts

---

## Best Practices

### Daily Operations

**Morning Checklist** (5 minutes):
1. Check **Overview** for alerts
2. Review **Tasks** queue depth
3. Verify **Workers** all healthy
4. Check **Errors** for critical issues
5. Review **Deployments** status

**Afternoon Check** (3 minutes):
1. Monitor **Sessions** health
2. Review task completion progress
3. Check for stuck tasks

**End of Day** (5 minutes):
1. Review completed tasks
2. Check error resolution rate
3. Plan next day's priorities

### Task Management

**Prioritization Guidelines**:
- **Critical**: System down, data loss, security
- **High**: Feature blocking, performance degradation
- **Medium**: Feature work, enhancements
- **Low**: Documentation, cleanup, optimization

**Assignment Strategy**:
- Balance load across workers
- Match tasks to worker skills
- Consider time zones for distributed teams
- Leave capacity for urgent issues (20% buffer)

### Error Handling

**Triage Process**:
1. **Assess Severity** (1 min)
   - Critical: Drop everything
   - High: Address within 1 hour
   - Medium: Address within 1 day
   - Low: Address within 1 week

2. **Gather Context** (2-5 min)
   - Check error frequency
   - Review stack trace
   - Check related logs
   - Identify affected users/services

3. **Assign Owner** (1 min)
   - Route to appropriate developer
   - Set deadline based on severity
   - Add to task queue

4. **Track Progress** (ongoing)
   - Check status every 30 min (critical)
   - Daily check (high/medium)
   - Weekly check (low)

### Documentation

**When to Document**:
- New features implemented
- Configuration changes made
- Troubleshooting solutions found
- Process improvements discovered

**Where to Document**:
- `docs/` directory for guides
- `CLAUDE.md` for AI agent instructions
- `TASKS.md` for task tracking
- Inline code comments for complex logic

---

## Common Tasks

### Add a New Worker

```bash
# Register worker
POST /api/session-pool/members
{
  "name": "worker-6",
  "tmux_name": "claude-worker-6",
  "role": "worker",
  "status": "stopped"
}

# Start worker session
tmux new-session -d -s claude-worker-6

# Verify
GET /api/session-pool/health-summary
```

### Create a Custom Dashboard View

1. Navigate to **Settings** > **Dashboard Layouts**
2. Click **+ New Layout**
3. Drag components to canvas
4. Configure widget settings
5. Save layout
6. Set as default (optional)

### Set Up Health Alerts

```bash
# Configure alert thresholds
POST /api/health/thresholds
{
  "cpu_warning": 70,
  "cpu_critical": 90,
  "memory_warning": 80,
  "memory_critical": 95,
  "disk_warning": 85,
  "disk_critical": 95
}

# Configure notifications
POST /api/notifications/rules
{
  "type": "health_alert",
  "channels": ["email", "slack"],
  "severity": ["critical", "high"]
}
```

### Bulk Task Assignment

```bash
# Auto-assign tasks based on workload
POST /api/tasks/auto-assign/batch
{
  "task_ids": ["A01", "A02", "A03"],
  "strategy": "balanced"
}
```

### Generate Reports

```bash
# Sprint velocity report
GET /api/reports/sprint-velocity?num_sprints=6

# Burndown chart
GET /api/reports/burndown?start_date=2026-02-01&end_date=2026-02-14

# Export progress data
GET /api/admin/progress/export?format=csv
```

---

## Training Exercises

### Exercise 1: Create and Assign a Task (15 minutes)

**Objective**: Learn the complete task lifecycle

**Steps**:
1. Create a new task:
   - Title: "Update welcome message"
   - Description: "Change homepage welcome text"
   - Priority: Low
2. Assign to yourself
3. Mark in-progress
4. Add a comment with progress update
5. Mark as completed
6. Verify it appears in completion metrics

**Success Criteria**: Task shows in completed tasks with correct timestamps

### Exercise 2: Monitor and Restart a Session (10 minutes)

**Objective**: Practice session health monitoring

**Steps**:
1. Navigate to Sessions panel
2. Find a healthy session
3. View session details and event log
4. Manually trigger restart
5. Monitor restart process
6. Verify session returns to healthy state
7. Check event log for restart entry

**Success Criteria**: Session restarts successfully within 30 seconds

### Exercise 3: Triage and Resolve an Error (20 minutes)

**Objective**: Practice error handling workflow

**Steps**:
1. Navigate to Errors panel
2. Find an unresolved error
3. Assess severity
4. Gather context:
   - Check frequency
   - Review stack trace
   - Check related logs
5. Create a task to fix the error
6. Assign to appropriate worker
7. Add notes to error record
8. Mark as "Under Investigation"
9. (Optional) Resolve if trivial

**Success Criteria**: Error is properly categorized and assigned

### Exercise 4: Deploy a Change (30 minutes)

**Objective**: Learn deployment process

**Steps**:
1. Make a small code change (e.g., comment)
2. Commit and tag: `git tag v1.0.test`
3. Deploy to QA environment
4. Verify deployment success
5. Check health metrics
6. Review deployment logs
7. Rollback if issues detected
8. Document the process

**Success Criteria**: Successful deployment or rollback

### Exercise 5: Configure LLM Failover (15 minutes)

**Objective**: Understand LLM provider management

**Steps**:
1. Check current provider status:
   ```bash
   GET /api/llm-metrics/circuit-breakers
   ```
2. Review failover history:
   ```bash
   GET /api/llm-metrics/failover-history
   ```
3. Simulate failure (in test environment):
   - Manually open circuit for Claude
   - Trigger LLM request
   - Verify failover to Ollama
4. Reset circuit breakers:
   ```bash
   POST /api/llm-metrics/reset-circuits
   ```
5. Monitor recovery

**Success Criteria**: Understand failover chain and circuit breaker behavior

---

## Certification Checklist

Complete these tasks to demonstrate proficiency:

- [ ] **Dashboard Navigation**: Navigate all panels without assistance
- [ ] **Task Management**: Create, assign, and complete 5 tasks
- [ ] **Error Handling**: Triage and resolve 3 errors of varying severity
- [ ] **Session Monitoring**: Monitor sessions for 1 hour, identify issues
- [ ] **Deployment**: Successfully deploy to QA and prod environments
- [ ] **Health Monitoring**: Configure alerts and respond to test alert
- [ ] **Documentation**: Document a new process or troubleshooting solution
- [ ] **LLM Management**: Understand and monitor LLM failover system
- [ ] **Reporting**: Generate and interpret 2 reports
- [ ] **Recovery**: Practice rollback procedure in test environment

---

## Getting Help

### Internal Resources

- **Troubleshooting Guide**: `docs/TROUBLESHOOTING.md`
- **LLM Provider Guide**: `docs/LLM_PROVIDER_SELECTION_GUIDE.md`
- **Architecture Docs**: `docs/ARCHITECT_SYSTEM_DOCUMENTATION.md`
- **API Reference**: `CLAUDE.md` (comprehensive API list)

### Support Channels

- **Slack**: #architect-support
- **Email**: architect-team@example.com
- **GitHub Issues**: https://github.com/your-org/architect/issues

### Escalation Path

1. **Self-serve**: Check documentation and troubleshooting guide
2. **Team chat**: Ask in #architect-support
3. **On-call**: Page on-call engineer for critical issues
4. **Management**: Escalate if issue impacts multiple teams

---

## Appendix

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus search |
| `t` | Go to Tasks |
| `s` | Go to Sessions |
| `e` | Go to Errors |
| `?` | Show keyboard shortcuts |
| `Esc` | Close modal/dialog |

### CLI Commands Reference

```bash
# Check status
./deploy.sh status

# View logs
tail -f /tmp/architect_dashboard.log

# Run migrations
python3 -m migrations.manager migrate --db data/architect.db

# Start specific worker
python3 workers/crawler_service.py --daemon

# Health check
curl http://localhost:8080/health
```

### Configuration Files

| File | Purpose |
|------|---------|
| `app.py` | Main application |
| `config/session_assigner.yaml` | Task routing rules |
| `data/architect.db` | Main database |
| `.env` | Environment variables |

---

**Last Updated**: 2026-02-10
**Version**: 1.0
**Maintainer**: Architect Team
