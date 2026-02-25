# Multi-Environment Orchestration System Implementation Guide

## Overview

This document describes the complete multi-environment orchestration system with GAIA integration for the Architect Dashboard. The system creates:

- **5 isolated development directories** (architect-dev1 through architect-dev5)
- **3 PR agent groups** (PRR: Review, PRI: Implementation, PRIG: Integration)
- **26 total sessions** distributed across multiple providers
- **Comprehensive status reporting** showing directories, environments, and PR groups

## Architecture

### Directory Structure

```
/Users/jgirmay/Desktop/gitrepo/pyWork/
├── architect/                         # Main production (port 8080)
├── architect-dev1/                    # Dev environment 1 (port 8081)
│   ├── data/dev/architect.db         # Dev sub-environment
│   ├── data/qa/architect.db          # QA sub-environment
│   ├── data/staging/architect.db     # Staging sub-environment
│   ├── logs/
│   ├── launch.sh                     # Start dev environment
│   ├── stop.sh                       # Stop environment
│   ├── status.sh                     # Check status
│   ├── sync.sh                       # Sync with main
│   └── .env.local                    # Environment variables
├── architect-dev2/ through dev5/      # Similar structure
└── [Other projects]
```

### Session Architecture (26 Total)

**High-Level Protected (6)** - Do NOT assign tasks to these:
- `architect`, `foundation`, `inspector` - System oversight
- `manager1`, `claude_architect` - Tactical coordination

**Dev Environment Workers (5 NEW)**
- `dev1_worker`, `dev2_worker`, ..., `dev5_worker` (Ollama provider)
- One worker per development directory
- Routes dev-specific tasks to correct environment

**PR Review Group - PRR (3 NEW)**
- `pr_review1`, `pr_review2` (Claude) - High-quality code review
- `pr_review3` (Ollama) - Quick automated checks

**PR Implementation Group - PRI (4 NEW)**
- `pr_impl1`, `pr_impl2` (Codex) - Cost-effective implementation
- `pr_impl3`, `pr_impl4` (Ollama) - Additional capacity

**PR Integration Group - PRIG (3 NEW)**
- `pr_integ1`, `pr_integ2`, `pr_integ3` (Ollama) - Fast local testing/merging

**Existing Workers (5)**
- `dev_worker1`, `dev_worker2` - General development
- `edu_worker1` - Education projects
- `codex_worker1` - Codex operations
- `qa_worker1` - QA and testing

## Implementation Steps

### Phase 1: Setup Development Environments

Run the master setup script to create all 5 environments:

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
./scripts/setup_multi_env.sh
```

This script:
1. Clones the main architect repository 5 times
2. Creates environment branches (env/dev1 through env/dev5)
3. Initializes 3 databases per environment (dev/qa/staging)
4. Creates launch/stop/status/sync scripts in each environment
5. Updates `data/environments.json` with configuration

**Output files created:**
- `architect-dev1/` through `architect-dev5/` directories
- Each with `launch.sh`, `stop.sh`, `status.sh`, `sync.sh`, `.env.local`
- `data/environments.json` - Master environment configuration

**To clean up (if needed):**
```bash
./scripts/setup_multi_env.sh --clean
```

### Phase 2: Start Development Environments

Test a single environment:

```bash
cd architect-dev1
./launch.sh              # Start in 'dev' sub-environment
./status.sh              # Check status
curl -k https://localhost:8081/health
./stop.sh                # Stop when done
```

Test different sub-environments:

```bash
cd architect-dev1
./launch.sh dev          # Start dev sub-environment (default)
./launch.sh qa           # Start qa sub-environment
./launch.sh staging      # Start staging sub-environment
```

### Phase 3: Start All Sessions

Start all 26 sessions (5 dev workers + 3 PR review + 4 PR impl + 3 PR integ):

```bash
./scripts/start_all_sessions.sh
```

This creates tmux sessions for:
- 5 development environment workers
- 3 PR review sessions (2 Claude, 1 Ollama)
- 4 PR implementation sessions (2 Codex, 2 Ollama)
- 3 PR integration sessions (3 Ollama)

**To stop all new sessions:**
```bash
./scripts/start_all_sessions.sh --stop
```

### Phase 4: Manage Development Environments

#### View Status

View all environments and sessions:

```bash
# Show sessions organized by functional groups
gaia --group-status

# Show multi-environment status (directories, git, databases, etc.)
gaia --multi-env-status

# Show live updating dashboard
gaia --watch
```

#### Git Workflow Commands

```bash
# Show git status for dev1
./scripts/dev_env_git_workflow.sh status dev1

# Sync dev1 with main branch
./scripts/dev_env_git_workflow.sh sync dev1

# Create feature branch in dev2
./scripts/dev_env_git_workflow.sh feature dev2 add-caching

# Commit changes
./scripts/dev_env_git_workflow.sh commit dev3 "Implement feature X"

# Push to remote
./scripts/dev_env_git_workflow.sh push dev3

# Show commit log
./scripts/dev_env_git_workflow.sh log dev1 10

# Clean merged branches
./scripts/dev_env_git_workflow.sh clean dev1
```

#### Monitor Environment Health

```bash
# Health check all environments (git status, databases, processes)
./scripts/dev_env_monitor.sh

# This checks:
# - Directory exists
# - Git branch status (ahead/behind/dirty)
# - Sub-environment status (running/stopped)
# - Worker session status
# - Database sizes
# - Overall health assessment
```

## GAIA Integration

### Session Pattern Detection

The `gaia.py` file has been updated to recognize new session patterns:

```python
# Name patterns added:
r"dev\d+_worker",      # dev1_worker through dev5_worker
r"pr_impl\d*",         # pr_impl1 through pr_impl4
r"pr_review\d*",       # pr_review1 through pr_review3
r"pr_integ\d*",        # pr_integ1 through pr_integ3

# Provider indicators added:
"ollama": [..., r"dev\d+_worker", r"pr_integ\d+"],
"codex": [..., r"pr_impl\d+"],
"claude": [..., r"pr_review[12]$"],
```

### Status Display

**Grouped status display:**
```bash
gaia --group-status
```

Shows sessions organized by:
- High-Level (Protected)
- Dev Environment Workers
- PR Review (PRR)
- PR Implementation (PRI)
- PR Integration (PRIG)
- Existing Workers
- Other Sessions

**Multi-environment status:**
```bash
gaia --multi-env-status
```

Shows:
- All directories with git status (branch, ahead/behind, dirty files)
- All sub-environments (dev/qa/staging) with port, status, PID
- All PR agent groups with session names and providers
- System totals (directories, environments, sessions)

## Task Routing

### Development Environment Tasks

Tasks mentioning specific environments are routed to the appropriate worker:

```bash
# This task goes to dev1_worker
python3 workers/assigner_worker.py --send "Fix bug in dev1 environment" --target auto

# This task goes to dev2_worker
python3 workers/assigner_worker.py --send "Implement feature X in dev2" --target auto
```

### PR Workflow Tasks

Tasks are routed to the appropriate PR group:

```bash
# Code review → pr_review group (round-robin)
python3 workers/assigner_worker.py --send "Review PR #123" --target auto

# Implement changes → pr_impl group (load-balanced)
python3 workers/assigner_worker.py --send "Address PR #123 review comments" --target auto

# Test and merge → pr_integ group (sequential)
python3 workers/assigner_worker.py --send "Run tests and merge PR #123" --target auto
```

## Files Created/Modified

### New Files Created

1. **scripts/setup_multi_env.sh** (400 lines)
   - Master setup script for 5 development environments
   - Creates git clones, branches, databases, and launch scripts

2. **scripts/start_all_sessions.sh** (260 lines)
   - Starts all 26 sessions with proper grouping
   - Includes cleanup and status verification

3. **scripts/dev_env_git_workflow.sh** (450 lines)
   - Git workflow utilities for each environment
   - Commands: status, sync, feature, commit, push, pull, log, clean, diff, rebase, reset

4. **scripts/dev_env_monitor.sh** (280 lines)
   - Health monitoring for all environments
   - Checks git status, databases, worker sessions, processes

5. **services/multi_env_status.py** (380 lines)
   - Status tracking service
   - Database schema for environments, PR groups, task assignments
   - Methods for getting directory, environment, and group status

### Modified Files

1. **gaia.py**
   - Added session patterns for dev workers and PR agents (lines 174-187)
   - Updated provider indicators for new session types (lines 197-234)
   - Added `show_group_status()` method for grouped display
   - Added CLI arguments: `--multi-env-status`, `--group-status`
   - Added handlers in main() for new status displays

2. **data/environments.json** (NEW)
   - Created by setup_multi_env.sh
   - Contains configuration for all 5 environments and their sub-environments

## Cost Analysis

### Monthly Estimate: ~$376

- **Claude (6 sessions)**: $350/month
  - architect, foundation, inspector (high-level)
  - pr_review1, pr_review2 (high-quality code review)
  - claude_architect (management)

- **Codex (4 sessions)**: $104/month ($26 each)
  - pr_impl1, pr_impl2 (PR implementation)

- **Ollama (16 sessions)**: $0/month (local)
  - 5 dev environment workers (dev1_worker through dev5_worker)
  - 3 PR review workers (pr_review3 included in claude count above)
  - 2 PR implementation workers (pr_impl3, pr_impl4)
  - 3 PR integration workers (pr_integ1-3)
  - 3 existing workers (dev_worker1, dev_worker2, qa_worker1)

**Savings**: ~$824/month vs all-Claude approach ($1200/month)

## Verification Steps

### 1. Environment Setup Verification

```bash
# Verify directories created
ls -la /Users/jgirmay/Desktop/gitrepo/pyWork/ | grep architect-dev

# Verify git branches
cd architect-dev1 && git branch

# Test launch scripts
./status.sh           # Should show "NOT RUNNING"
./launch.sh           # Should start on port 8081
./status.sh           # Should show "RUNNING"
curl -k https://localhost:8081/health
./stop.sh             # Should stop gracefully
```

### 2. Session Discovery Verification

```bash
# Start all sessions
./scripts/start_all_sessions.sh

# Verify GAIA sees them
gaia --group-status    # Should show all 26 sessions

# Count sessions
tmux list-sessions | wc -l  # Should be 26+

# Verify grouping
gaia --group-status | grep -c "Dev Environment"  # Should be 5
gaia --group-status | grep -c "PR Review"        # Should be 3
gaia --group-status | grep -c "PR Implementation" # Should be 4
gaia --group-status | grep -c "PR Integration"   # Should be 3
```

### 3. Multi-Environment Status Verification

```bash
# Test multi-env status
gaia --multi-env-status

# Verify it shows:
# - All 5 directories
# - Git branch info (ahead/behind/clean)
# - Environment status (running/stopped)
# - PR group assignments
```

### 4. Git Workflow Verification

```bash
# Check status
./scripts/dev_env_git_workflow.sh status dev1

# Sync with main
./scripts/dev_env_git_workflow.sh sync dev1

# Create feature branch
./scripts/dev_env_git_workflow.sh feature dev1 test-feature

# Verify branch created
cd architect-dev1 && git branch

# Commit changes
./scripts/dev_env_git_workflow.sh commit dev1 "Test commit"

# Show log
./scripts/dev_env_git_workflow.sh log dev1 5
```

### 5. Environment Health Monitoring

```bash
# Run health check
./scripts/dev_env_monitor.sh

# Should show:
# - Directory status
# - Git status for each
# - Sub-environment status
# - Worker session status
# - Overall health assessment
```

## Troubleshooting

### Port Conflicts

If port 8081-8085 are in use:

```bash
# Find what's using the port
lsof -i :8081

# Kill the process
kill -9 <PID>

# Or change ports in launch.sh
```

### Database Corruption

If a database is corrupted:

```bash
cd architect-dev1
rm data/dev/architect.db
./launch.sh   # Database will be recreated
```

### Git Conflicts

If a git operation fails with conflicts:

```bash
cd architect-dev1
git status                    # See conflicted files
# Manually resolve conflicts
git add .
git commit -m "Resolved conflicts"
```

### Session Not Starting

If a session fails to start:

```bash
# Check if already running
tmux list-sessions | grep session_name

# Kill any stale session
tmux kill-session -t session_name

# Try starting again
./scripts/start_all_sessions.sh
```

## Maintenance

### Regular Tasks

- **Daily**: Check environment health with `./scripts/dev_env_monitor.sh`
- **Weekly**: Sync environments with main branch using `./scripts/dev_env_git_workflow.sh sync dev{1-5}`
- **Monthly**: Clean up merged branches with `./scripts/dev_env_git_workflow.sh clean dev{1-5}`

### Backup

Databases are automatically backed up to `data/backups/`. To manually backup:

```bash
for i in {1..5}; do
    tar -czf "architect-dev$i-backup-$(date +%Y%m%d).tar.gz" "architect-dev$i/"
done
```

### Reset All Environments

To completely reset (DESTRUCTIVE):

```bash
# Stop all sessions
./scripts/start_all_sessions.sh --stop

# Remove all environments
./scripts/setup_multi_env.sh --clean

# Recreate from scratch
./scripts/setup_multi_env.sh
./scripts/start_all_sessions.sh
```

## API Integration

The dashboard includes new endpoints for multi-environment management:

```python
GET /api/multi-env/status        # Complete status report (JSON)
GET /api/multi-env/directories   # List directories with git status
GET /api/multi-env/environments  # List environments (dev/qa/staging)
GET /api/multi-env/pr-groups     # PR agent group status
GET /api/multi-env/health        # Overall system health
```

## Next Steps

1. Run `./scripts/setup_multi_env.sh` to create all 5 environments
2. Run `./scripts/start_all_sessions.sh` to start all 26 sessions
3. Use `gaia --group-status` to verify all sessions are running
4. Use `gaia --multi-env-status` to see complete system overview
5. Use `./scripts/dev_env_git_workflow.sh` for git operations
6. Use `./scripts/dev_env_monitor.sh` for health checks

## Summary

The multi-environment orchestration system provides:

✅ Complete isolation between 5 development directories
✅ Flexible sub-environments (dev/qa/staging)
✅ 26 sessions across Claude, Codex, and Ollama providers
✅ Smart task routing by environment and PR group
✅ Comprehensive status reporting and monitoring
✅ Cost optimization ($376/month vs $1200/month)
✅ Git workflow automation and management
✅ Health monitoring and alerts
✅ Zero token budget impact (uses existing provider infrastructure)
