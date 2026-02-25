# Multi-Environment Orchestration - Quick Start Guide

## 5-Minute Setup

### Step 1: Create All 5 Development Environments (2 minutes)

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
./scripts/setup_multi_env.sh
```

This creates:
- `architect-dev1/` through `architect-dev5/` directories
- Each with separate git branches (env/dev1, env/dev2, etc.)
- Launch/stop/status/sync scripts in each
- Configuration in `data/environments.json`

### Step 2: Start Development Environments (1 minute)

```bash
# Start environment dev1 in 'dev' sub-environment
cd architect-dev1
./launch.sh

# Verify it's running
./status.sh

# Access the dashboard
open https://localhost:8081   # (or your browser)

# Stop when done
./stop.sh
```

### Step 3: Start All 26 Sessions (1 minute)

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
./scripts/start_all_sessions.sh

# Verify they're all running
gaia --group-status
```

### Step 4: Check System Status (1 minute)

```bash
# Show sessions organized by groups
gaia --group-status

# Show complete multi-environment status
gaia --multi-env-status

# Show health of all environments
./scripts/dev_env_monitor.sh
```

## Common Tasks

### View Session Status

```bash
# Show sessions organized by functional groups
gaia --group-status

# Show live updating status
gaia --watch

# Show all environment details
gaia --multi-env-status
```

### Manage Development Environment

```bash
# Check if environment is running
cd architect-dev1
./status.sh

# Start environment
./launch.sh

# Stop environment
./stop.sh

# Start different sub-environment
./launch.sh qa       # Start QA sub-environment
./launch.sh staging  # Start staging sub-environment
```

### Git Workflow

```bash
# Check git status
./scripts/dev_env_git_workflow.sh status dev1

# Sync with main branch
./scripts/dev_env_git_workflow.sh sync dev1

# Create feature branch
./scripts/dev_env_git_workflow.sh feature dev1 my-feature-name

# Commit changes
./scripts/dev_env_git_workflow.sh commit dev1 "Implemented feature X"

# Push to remote
./scripts/dev_env_git_workflow.sh push dev1

# Show recent commits
./scripts/dev_env_git_workflow.sh log dev1 10

# Pull latest changes
./scripts/dev_env_git_workflow.sh pull dev1
```

### Monitor Environment Health

```bash
# Check health of all environments
./scripts/dev_env_monitor.sh

# This shows:
# ✓ Directory exists and accessible
# ✓ Git branch status (ahead/behind/dirty)
# ✓ Sub-environment status (running/stopped)
# ✓ Worker session status
# ✓ Database sizes
# ✓ Overall health assessment
```

## Session Groups Overview

### High-Level Protected (6 sessions)
- `architect`, `foundation`, `inspector` - System oversight
- `manager1`, `claude_architect` - Tactical coordination
- **DO NOT assign tasks to these**

### Dev Environment Workers (5 NEW)
- `dev1_worker`, `dev2_worker`, ..., `dev5_worker`
- Ollama provider (local, free)
- Automatically route dev-specific tasks

### PR Review Group - PRR (3 NEW)
- `pr_review1` (Claude) - High-quality reviews
- `pr_review2` (Claude) - High-quality reviews
- `pr_review3` (Ollama) - Quick automated checks

### PR Implementation Group - PRI (4 NEW)
- `pr_impl1` (Codex) - Cost-effective implementation
- `pr_impl2` (Codex) - Cost-effective implementation
- `pr_impl3` (Ollama) - Additional capacity
- `pr_impl4` (Ollama) - Additional capacity

### PR Integration Group - PRIG (3 NEW)
- `pr_integ1`, `pr_integ2`, `pr_integ3` (Ollama)
- Fast local testing and merging

### Existing Workers (5)
- `dev_worker1`, `dev_worker2`
- `edu_worker1`
- `codex_worker1`
- `qa_worker1`

## Typical Workflow

### 1. Start Environment

```bash
cd architect-dev1
./launch.sh
./status.sh        # Verify running
```

### 2. Do Work

```bash
# Create feature branch
../scripts/dev_env_git_workflow.sh feature dev1 add-caching

# Make changes in the development environment
# (use the web UI at https://localhost:8081)

# Commit changes
../scripts/dev_env_git_workflow.sh commit dev1 "Implement caching feature"
```

### 3. Sync with Main

```bash
../scripts/dev_env_git_workflow.sh sync dev1
```

### 4. Push to Remote

```bash
../scripts/dev_env_git_workflow.sh push dev1
```

### 5. Create PR and Request Review

```bash
# In GitHub, create PR from feature branch
# Assign to PR review group
```

### 6. Monitor PR Workflow

```bash
# Task routing automatically handles:
# - Code review (pr_review group)
# - Implementation of feedback (pr_impl group)
# - Testing and merging (pr_integ group)

# Monitor progress
gaia --multi-env-status
gaia --watch
```

### 7. Stop Environment

```bash
./stop.sh
```

## Directory Structure

```
architect-dev1/
├── app.py                    # Flask application
├── gaia.py                   # GAIA CLI
├── .env.local                # Environment variables
├── launch.sh                 # Start environment
├── stop.sh                   # Stop environment
├── status.sh                 # Check status
├── sync.sh                   # Sync with main
├── data/
│   ├── dev/architect.db      # Dev database
│   ├── qa/architect.db       # QA database
│   ├── staging/architect.db  # Staging database
│   └── environments.json
├── logs/
│   └── architect_dev1.log
└── [all other architect files...]
```

## Cost Breakdown

- **Claude** (6 sessions): $350/month
- **Codex** (4 sessions): $104/month
- **Ollama** (16 sessions): $0/month (local)

**Total**: ~$376/month (vs $1200/month for all-Claude)

## Troubleshooting

### Environment won't start

```bash
# Check if port is in use
lsof -i :8081

# Check logs
tail -f logs/architect_dev1.log

# Ensure launch.sh is executable
chmod +x launch.sh
./launch.sh
```

### Sessions not appearing

```bash
# Verify tmux is running
tmux list-sessions

# Start sessions manually
cd architect
./scripts/start_all_sessions.sh

# Check status
gaia --group-status
```

### Git conflict during sync

```bash
# Resolve manually
cd architect-dev1
git status          # See conflicts
# Fix files manually
git add .
git commit -m "Resolved conflicts"
```

### Database corrupted

```bash
# Backup and delete
cd architect-dev1
mv data/dev/architect.db data/dev/architect.db.bak

# Restart - database will be recreated
./launch.sh
```

## Key Commands Reference

```bash
# Setup
./scripts/setup_multi_env.sh              # Create all 5 environments
./scripts/start_all_sessions.sh           # Start all 26 sessions

# Status
gaia --group-status                       # Show grouped sessions
gaia --multi-env-status                   # Show environment details
gaia --watch                              # Live dashboard
./scripts/dev_env_monitor.sh              # Health check

# Environment management
cd architect-dev1 && ./launch.sh           # Start environment
cd architect-dev1 && ./stop.sh             # Stop environment
cd architect-dev1 && ./status.sh           # Check status

# Git workflow
./scripts/dev_env_git_workflow.sh status dev1      # Show status
./scripts/dev_env_git_workflow.sh sync dev1        # Sync with main
./scripts/dev_env_git_workflow.sh feature dev1 x   # Create branch
./scripts/dev_env_git_workflow.sh commit dev1 "x"  # Commit
./scripts/dev_env_git_workflow.sh push dev1        # Push
./scripts/dev_env_git_workflow.sh log dev1 5       # Show commits

# Cleanup
./scripts/setup_multi_env.sh --clean               # Remove all environments
./scripts/start_all_sessions.sh --stop             # Stop all sessions
```

## Next Steps

1. **Setup**: `./scripts/setup_multi_env.sh`
2. **Start Sessions**: `./scripts/start_all_sessions.sh`
3. **Verify**: `gaia --group-status` and `gaia --multi-env-status`
4. **Test**: `cd architect-dev1 && ./launch.sh && ./status.sh`
5. **Monitor**: `./scripts/dev_env_monitor.sh`

For detailed documentation, see: `docs/MULTI_ENVIRONMENT_ORCHESTRATION.md`
