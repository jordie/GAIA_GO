# Session Structure & Process SOP

**Last Updated**: 2026-02-08
**Purpose**: Define standard session structure and workflows for the Architect Dashboard multi-agent system

## Session Architecture

### Total Sessions: 9

```
┌─────────────────────────────────────────────────────────┐
│  HIGH-LEVEL: architect                                  │
│  - Strategic oversight                                  │
│  - User communication                                   │
│  - Delegate to managers (NOT workers)                   │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬──────────────┬─────────┐
        ▼            ▼            ▼              ▼         │
   ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐  │
   │orchestr │  │wrapper_ │  │efficiency│  │documenta │  │
   │ator     │  │claude   │  │_manager  │  │tion_mgr  │  │
   └────┬────┘  └────┬────┘  └─────┬────┘  └─────┬────┘  │
        │            │              │             │       │
        └────────────┴──────────────┴─────────────┴───────┘
                     │
        ┌────────────┼────────────┬──────────────┐
        ▼            ▼            ▼              ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
   │dev_     │  │dev_     │  │dev_     │  │fixer    │
   │worker1  │  │worker2  │  │worker3  │  │         │
   └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

## Session Roles & Responsibilities

### HIGH-LEVEL (architect)
- Monitor overall system health
- Make strategic decisions
- Delegate complex tasks to MANAGERS
- User communication and reporting
- **NEVER** delegate directly to workers

### MANAGER: claude_orchestrator
**Role**: Task Coordination & Deployment
**Responsibilities**:
- Break down complex tasks into subtasks
- Assign specific work to workers
- Coordinate task dependencies
- Review PRs for deployment readiness
- Test features in dev environment
- Approve dev → qa → prod promotions
- Monitor worker progress
- **Order workers to test deployments after completion**
- Verify deployment test results

**Key Tasks**:
```bash
- Receive task from high-level
- Analyze and break down
- Assign to appropriate workers
- Monitor completion
- Review and approve PRs
- Coordinate deployments
```

### MANAGER: wrapper_claude
**Role**: Quality Gate & SOP Compliance
**Responsibilities**:
- Monitor git flow compliance
- Review code quality in PRs (safety net)
- Ensure tests pass before merge
- Verify workers follow SOPs
- Approve qa → prod promotions
- **If nobody else reviews PRs, wrapper_claude reviews them**

**Key Tasks**:
```bash
- Monitor worker git activity
- Review uncommitted changes
- Check feature branch usage
- Ensure proper commits
- Review PRs when unreviewed
- Verify test coverage
```

### MANAGER: documentation_manager
**Role**: Automated Documentation & Knowledge Management
**Responsibilities**:
- Auto-update project documentation via Google Docs API
- Maintain development timeline
- Track milestones and completion status
- Update project roadmap
- Pull data from git commits, PRs, tasks
- Generate progress reports
- Keep documentation synchronized with actual progress

**Key Tasks**:
```bash
- Setup Google Docs API with EDIT permissions
  * Create Google Cloud project
  * Enable Google Docs API
  * Create service account with editor role
  * Download credentials JSON
  * Share doc with service account email
- Implement API calls to UPDATE/WRITE (not just read)
- Create/update timeline section
- Track milestone completion
- Update roadmap based on progress
- Pull commit history for timeline
- Sync task completions to doc
- Generate daily/weekly progress reports
```

### MANAGER: efficiency_manager
**Role**: Process Optimization & Metrics
**Responsibilities**:
- Identify repetitive tasks and patterns
- Find inefficiencies in workflows
- Recommend automation opportunities
- Track deployment metrics
- Analyze token usage waste
- Propose optimization strategies

**Key Tasks**:
```bash
- Analyze bash history for patterns
- Identify duplicate work
- Track grep/search patterns
- Calculate token waste
- Recommend script-based solutions
- Track deployment frequency
```

### WORKERS: dev_worker1, dev_worker2, dev_worker3, fixer
**Role**: Task Execution
**Responsibilities**:
- Execute specific assigned tasks
- Write code and fix bugs
- Follow git flow (feature branches)
- Commit work with proper messages
- Create PRs for completed work
- Report completion to manager
- Ask questions when blocked

**Key Tasks**:
```bash
- Receive task from manager
- Create feature branch
- Implement changes
- Write tests
- Commit with descriptive message
- Create PR
- Report to manager
```

## Git Flow Process

### Feature Branch Workflow
```
1. Worker receives task from manager
2. Create feature branch: feature/description-MMDD
3. Make changes
4. Run tests
5. Commit: "fix: Description" or "feat: Description"
6. Push branch
7. Create Pull Request
8. Manager reviews PR
9. Manager approves
10. Merge to dev
11. Auto-deploy to dev
12. Manager verifies
13. Promote to qa → prod
```

### Branch Naming Convention
- `feature/fix-piano-labels-0208` - New features
- `fix/bug-description-0208` - Bug fixes
- `refactor/description-0208` - Code refactoring

### Commit Message Format
```
type: Brief description

- Detail 1
- Detail 2

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

## Deployment Workflow

### PR Review Process
```
Worker creates PR
    ↓
Manager reviews (orchestrator or wrapper_claude)
    ↓
If nobody reviewed → wrapper_claude reviews (safety net)
    ↓
Manager approves
    ↓
Merge to dev
    ↓
**Auto-deploy triggered on commit to dev branch**
    ↓
Deploy to dev environment
    ↓
Manager tests in dev
    ↓
Manager approves → Merge to qa
    ↓
Auto-deploy to qa
    ↓
Manager final review
    ↓
Manager approves → Merge to prod
    ↓
Deploy to production
    ↓
Manager orders worker to test deployment
    ↓
Worker verifies deployment works
    ↓
Worker reports test results to manager
```

### Deployment Rules
1. ✅ All deployments MUST go through PR
2. ✅ Manager review required before merge
3. ✅ No direct commits to dev/qa/prod branches
4. ✅ Automated tests must pass
5. ✅ At least 1 manager approval required
6. ✅ If unreviewed, wrapper_claude steps in
7. ✅ **Manager orders worker to test deployment after completing deployment**
8. ✅ **Auto-deploy on commit**:
   - main branch → production environment
   - dev branch → dev environment
   - qa branch → qa environment
   - Triggered automatically when commits merge to respective branch

## Auto-Confirm Configuration

### Purpose
Automatically confirm permission prompts to prevent sessions from blocking.

### Setup
```bash
# Start auto-confirm worker
python3 workers/auto_confirm_worker.py --daemon

# Verify running
ps aux | grep auto_confirm
```

### Configuration
- **Check interval**: 0.3 seconds
- **Excluded sessions**: autoconfirm (itself)
- **Safe operations**: read, grep, glob, edit, write, bash, accept_edits
- **Handles wrapped text**: Detects "2.Yes" and "2. Yes"

### Known Issues
- Sessions generate prompts faster than auto-confirm can process
- May require manual unsticking during heavy parallel work
- Consider implementing confirmation queue for better throughput

## Task Assignment Flow

### High-Level → Manager
```bash
# User request to architect
User: "Fix all reading app issues"

# Architect delegates to manager
tmux send-keys -t claude_orchestrator "Analyze reading app, create task breakdown and assign to workers" Enter
```

### Manager → Worker
```bash
# Manager assigns via assigner system
python3 workers/assigner_worker.py --send "Fix mastered words recording in reading app" --target dev_worker1 --priority 8
```

### Worker → Manager
```bash
# Worker reports completion
# (Manager monitors tmux sessions and git activity)
```

## Startup Process

### 1. Create Sessions
```bash
# High-level
tmux new-session -d -s architect 'claude'

# Managers
tmux new-session -d -s claude_orchestrator 'claude'
tmux new-session -d -s wrapper_claude 'claude'
tmux new-session -d -s efficiency_manager 'claude'
tmux new-session -d -s documentation_manager 'claude'

# Workers
tmux new-session -d -s dev_worker1 'claude'
tmux new-session -d -s dev_worker2 'claude'
tmux new-session -d -s dev_worker3 'claude'
tmux new-session -d -s fixer 'claude'
```

### 2. Initialize Manager Roles
```bash
# Task Coordinator
tmux send-keys -t claude_orchestrator "ROLE: Task Coordination Manager. Break down tasks, assign to workers, review PRs, coordinate deployments." Enter

# Quality Gate
tmux send-keys -t wrapper_claude "ROLE: Quality & SOP Manager. Monitor git flow, review PRs if unreviewed, ensure compliance." Enter

# Efficiency Analyst
tmux send-keys -t efficiency_manager "ROLE: Process Optimization Manager. Identify inefficiencies, recommend automation, track metrics." Enter

# Documentation Manager
tmux send-keys -t documentation_manager "ROLE: Documentation & Knowledge Manager. Auto-update Google Doc with timeline, milestones, roadmap using API." Enter
```

### 3. Start Auto-Confirm
```bash
python3 workers/auto_confirm_worker.py --daemon
```

### 4. Start Assigner Worker
```bash
python3 workers/assigner_worker.py --daemon
```

### 5. Verify All Running
```bash
tmux list-sessions
# Should show: architect, claude_orchestrator, wrapper_claude,
#              efficiency_manager, dev_worker1, dev_worker2,
#              dev_worker3, fixer

ps aux | grep "auto_confirm\|assigner"
# Should show both workers running
```

## Communication Patterns

### User → High-Level (architect)
- Natural language requests
- Strategic questions
- Status checks

### High-Level → Managers
- Complex task delegation
- Strategic directives
- Coordination requests

### Managers → Workers
- Specific task assignments via assigner
- Direct prompts via tmux send-keys
- Task queue system

### Workers → Managers
- Completion reports (via git commits/PRs)
- Blocked status (via prompts)
- Questions (via session output)

### Managers → Managers
- Coordination (mentioned in prompts)
- Handoffs (deployment flow)
- Conflict resolution

## Workflow Example

### Complete Task Flow
```
1. User: "Add dark mode to reading app"
   → architect session

2. architect: Analyzes, delegates to manager
   → tmux send-keys -t claude_orchestrator "Implement dark mode..."

3. claude_orchestrator: Breaks down task
   - Subtask 1: CSS variables
   - Subtask 2: Toggle button
   - Subtask 3: Persistence

4. claude_orchestrator: Assigns to worker
   → python3 workers/assigner_worker.py --send "Task 1..." --target dev_worker1

5. dev_worker1: Executes
   - Creates feature/dark-mode-0208
   - Implements changes
   - Commits with proper message
   - Creates PR

6. wrapper_claude: Reviews PR (safety net)
   - Checks code quality
   - Verifies tests
   - Approves

7. claude_orchestrator: Deployment
   - Merges to dev
   - Tests in dev environment
   - Approves promotion to qa
   - Final review
   - Deploys to prod

8. efficiency_manager: Analyzes
   - Notes dark mode pattern
   - Recommends: "Create reusable theme system"
   - Identifies token savings opportunity
```

## Maintenance

### Daily
- Check auto-confirm is running
- Verify all sessions active
- Review open PRs
- Monitor worker git status

### Weekly
- Review efficiency_manager reports
- Implement recommended automations
- Update this SOP based on learnings
- Clean up old branches

### As Needed
- Restart stuck sessions
- Manually unstick prompts
- Adjust worker count
- Refine manager responsibilities

## Troubleshooting

### Sessions Keep Getting Stuck
- Check auto-confirm is running: `ps aux | grep auto_confirm`
- Restart auto-confirm: `pkill -f auto_confirm && python3 workers/auto_confirm_worker.py --daemon`
- Manually unstick: `tmux send-keys -t SESSION_NAME "1" Enter`

### Workers Not Following Git Flow
- wrapper_claude reviews and corrects
- Remind workers of feature branch requirement
- Check CLAUDE.md is up to date

### PRs Not Being Reviewed
- wrapper_claude acts as safety net
- Check manager sessions are active
- Verify PR review tasks assigned

### Too Much Token Usage
- efficiency_manager analyzes patterns
- Implement recommended scripts
- Cache common searches
- Use non-AI tools for repetitive tasks

## Success Metrics

### Good Signs
- ✅ Workers on feature branches
- ✅ Regular commits with good messages
- ✅ PRs reviewed before merge
- ✅ Auto-confirm handling most prompts
- ✅ Managers coordinating effectively
- ✅ No duplicate work

### Red Flags
- ❌ Workers on env/ or main branch
- ❌ 50+ uncommitted files
- ❌ PRs merged without review
- ❌ Sessions constantly stuck
- ❌ Managers doing worker tasks
- ❌ Same work done multiple times

## Future Improvements

### Planned
- [ ] Confirmation queue system (async)
- [ ] Automated PR review bot
- [ ] Session health monitoring
- [ ] Auto-restart stuck sessions
- [ ] Metrics dashboard
- [ ] Token usage tracking

### Under Consideration
- [ ] Add 4th manager (deployment specialist)
- [ ] Worker specialization (frontend/backend)
- [ ] Automated test runner
- [ ] CI/CD pipeline integration
- [ ] Slack notifications for PR reviews

---

**Document Owner**: architect (high-level session)
**Review Frequency**: Weekly or after major changes
**Related Docs**: CLAUDE.md, MULTI_ENVIRONMENT_GUIDE.md, ASSIGNER_ENV_SOP.md
