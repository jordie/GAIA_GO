# 🚀 Multi-Project Development Workflow

## 5 Isolated Development Environments

You now have **5 completely isolated development environments** running in parallel:

### Environment Overview

```
Main Project (architect)                  Port 8080
├─ Production Dashboard

Parallel Dev Projects (architect-dev1-5)  Ports 8081-8085
├─ architect-dev1 (DEV, QA, STAGING)     Port 8081/8091/8101
├─ architect-dev2 (DEV, QA, STAGING)     Port 8082/8092/8102
├─ architect-dev3 (DEV, QA, STAGING)     Port 8083/8093/8103
├─ architect-dev4 (DEV, QA, STAGING)     Port 8084/8094/8104
└─ architect-dev5 (DEV, QA, STAGING)     Port 8085/8095/8105
```

---

## 🎯 Quick Start by Project

### Project 1: architect-dev1
```bash
# Enter environment
cd ~/Desktop/gitrepo/pyWork/architect-dev1

# Start services
./launch.sh                    # Start DEV environment
./launch.sh qa                 # Start QA environment
./launch.sh staging            # Start STAGING environment

# Check status
./status.sh

# Git operations
./git sync                     # Sync with main
./git feature my-feature       # Create feature branch
./git commit -m "message"      # Commit changes
./git push                     # Push to origin

# Stop when done
./stop.sh
```

### Projects 2-5: Same Pattern
Replace `architect-dev1` with `architect-dev2`, `architect-dev3`, `architect-dev4`, or `architect-dev5`

---

## 👥 Session Routing

### Dev Workers (1 per project)
- `dev1_worker` → architect-dev1 (Ollama provider)
- `dev2_worker` → architect-dev2 (Ollama provider)
- `dev3_worker` → architect-dev3 (Ollama provider)
- `dev4_worker` → architect-dev4 (Ollama provider)
- `dev5_worker` → architect-dev5 (Ollama provider)

**Usage**: Assign development tasks to specific workers
```bash
python3 workers/assigner_worker.py --send "Implement auth feature" --target dev1_worker
```

### PR Agent Groups (Shared Across All Projects)
- **PR Review Group (3 sessions)**: `pr_review1`, `pr_review2`, `pr_review3`
  - Claude-powered code review
  - Shared infrastructure analysis
  
- **PR Implementation Group (4 sessions)**: `pr_impl1-4`
  - Codex + Ollama providers
  - Implementation task execution
  
- **PR Integration Group (3 sessions)**: `pr_integ1-3`
  - Testing & integration
  - Validation workflows

---

## 🔄 Typical Workflows

### Workflow 1: Parallel Development
```
Time 0:00
  ✓ Start dev1 on Feature A
  ✓ Start dev2 on Feature B
  ✓ Start dev3 on Bug Fix C

Time 1:00
  ✓ Complete Feature A - PR created
  ✓ dev1_worker → feature/feature-a (dev1)

Time 1:30
  ✓ PR Review: pr_review1 reviews Feature A PR
  ✓ dev1_worker starts Feature D (next task)

Time 2:00
  ✓ Complete Feature B - PR created
  ✓ PR Review: pr_review2 reviews Feature B PR

Time 2:30
  ✓ Implement PR feedback using pr_impl sessions
  ✓ dev1_worker & dev2_worker collaborate on implementation
```

### Workflow 2: Testing Pipeline
```
dev1 (implementation)
  → pr_impl1 (code review & implement feedback)
  → pr_integ1 (run tests)
  → If PASS → Merge to main
  → If FAIL → dev1_worker fixes issues
```

### Workflow 3: Cross-Project Collaboration
```
Project A (dev1):  Feature X depends on Library Y
Project B (dev2):  Building Library Y
Project C (dev3):  Independent work

Timeline:
  - dev2_worker builds Library Y on archer-dev2
  - dev1_worker waits for notification
  - dev2_worker tags and releases
  - dev1_worker pulls latest Library Y
  - dev1_worker completes Feature X
```

---

## 📋 Assign Work to Sessions

### Send Task to Specific Dev Worker
```bash
# Feature development
python3 workers/assigner_worker.py \
  --send "Implement OAuth2 authentication" \
  --target dev1_worker \
  --priority 8

# Bug fix
python3 workers/assigner_worker.py \
  --send "Fix login timeout issue in reading app" \
  --target dev2_worker \
  --priority 9

# Refactoring
python3 workers/assigner_worker.py \
  --send "Refactor database connection pooling" \
  --target dev3_worker \
  --priority 5
```

### Send PR to Review Group
```bash
python3 workers/assigner_worker.py \
  --send "Review PR #47 for code quality and security" \
  --target pr_review1 \
  --priority 7
```

### Send to Implementation Group
```bash
python3 workers/assigner_worker.py \
  --send "Implement the feedback from code review on PR #47" \
  --target pr_impl1 \
  --priority 6
```

---

## 🔍 Monitor Progress

### Check All Environments Status
```bash
# Show all 5 environments
python3 gaia.py --multi-env-status

# Show all sessions grouped by type
python3 gaia.py --group-status

# Show all sessions (including hidden)
python3 gaia.py --sessions
```

### Monitor Task Queue
```bash
# Show active tasks
python3 workers/assigner_worker.py --prompts

# Show sessions
python3 workers/assigner_worker.py --sessions

# Show completed tasks (last 10)
sqlite3 data/assigner/assigner.db \
  "SELECT id, status, target_session, created_at FROM prompts \
   WHERE status='completed' ORDER BY created_at DESC LIMIT 10"
```

### View Environment Git Status
```bash
# From any dev environment
cd ~/Desktop/gitrepo/pyWork/architect-dev1
./git status      # Current branch and changes
./git log --oneline -10  # Recent commits
./git branch -a   # All branches
```

---

## 💾 Database Management

Each environment has independent databases:
- `architect-dev1/data/architect.db`
- `architect-dev2/data/architect.db`
- ... (separate for each)

**Query specific environment**:
```bash
cd ~/Desktop/gitrepo/pyWork/architect-dev1
sqlite3 data/architect.db "SELECT * FROM features LIMIT 5"
```

---

## 🚀 Cost Breakdown

| Component | Cost/Month | Usage |
|-----------|----------|-------|
| Claude (dev workers) | $0 | Using Ollama locally |
| Codex (PR impl) | $104 | pr_impl1-4 |
| Gemini (fallback) | $0 | Not used, fallback only |
| Ollama (local) | $0 | All workers |
| **Total** | **~$100** | All 5 projects |

**Savings**: ~$1,000/month vs all-Claude ✅

---

## ⚡ Performance Tips

1. **Stagger Starts**: Don't launch all 5 environments at once
   ```bash
   # Do this instead:
   ./architect-dev1/launch.sh &
   sleep 10
   ./architect-dev2/launch.sh &
   sleep 10
   # ... continue
   ```

2. **Monitor System Resources**
   ```bash
   ./scripts/dev_env_monitor.sh  # Health check
   ```

3. **Use Context Matching** - Assigner automatically routes tasks to workers with matching context
   ```bash
   python3 workers/assigner_worker.py \
     --send "Fix issue in auth module" \
     --working-dir /architect-dev1 \
     --env-var CONTEXT=authentication
   ```

4. **Batch Similar Tasks** - Run related tasks on same worker
   ```bash
   # All auth work on dev1_worker
   python3 workers/assigner_worker.py --send "Task 1" --target dev1_worker
   python3 workers/assigner_worker.py --send "Task 2" --target dev1_worker
   python3 workers/assigner_worker.py --send "Task 3" --target dev1_worker
   ```

---

## 🔧 Git Workflow Per Project

### Create Feature Branch
```bash
cd ~/Desktop/gitrepo/pyWork/architect-dev1
./git feature my-new-feature    # Creates env/dev1/feature/my-new-feature
```

### Push Changes
```bash
./git push          # Pushes to origin/env/dev1
```

### Sync with Main
```bash
./git sync          # Pulls latest from main branch
```

### Create PR
```bash
# Changes are on env/dev1 branch
# Create PR from env/dev1 → main via GitHub
gh pr create --base main --head env/dev1 --title "My feature" --body "Description"
```

---

## 📊 Example: Working on 5 Projects in Parallel

**Time 09:00** - Start day
```bash
# Project 1: New authentication feature
cd architect-dev1 && ./launch.sh

# Project 2: Database optimization
cd architect-dev2 && ./launch.sh

# Project 3: API endpoint refactoring
cd architect-dev3 && ./launch.sh

# Project 4: UI improvements
cd architect-dev4 && ./launch.sh

# Project 5: Deployment automation
cd architect-dev5 && ./launch.sh
```

**Time 09:15** - Assign work
```bash
# Send to workers - each gets their project
python3 workers/assigner_worker.py --send "Implement OAuth2" --target dev1_worker
python3 workers/assigner_worker.py --send "Optimize queries" --target dev2_worker
python3 workers/assigner_worker.py --send "Refactor API" --target dev3_worker
python3 workers/assigner_worker.py --send "Update UI components" --target dev4_worker
python3 workers/assigner_worker.py --send "Setup CI/CD" --target dev5_worker
```

**Time 12:00** - Monitor progress
```bash
python3 gaia.py --multi-env-status  # See all projects
python3 workers/assigner_worker.py --prompts  # See task status
```

**Time 15:00** - First PR ready
```bash
# dev1_worker finished, PR created
python3 workers/assigner_worker.py --send "Review PR #48" --target pr_review1

# dev1_worker starts next task
python3 workers/assigner_worker.py --send "Fix remaining issues" --target dev1_worker
```

**Time 17:00** - Merge and continue
```bash
# PR #48 approved and merged
gh pr merge 48 --merge

# All 5 projects moving forward in parallel
```

---

## 🎉 You're Ready!

You now have:
- ✅ 5 completely isolated development environments
- ✅ 26 specialized sessions for different tasks
- ✅ Intelligent routing and task assignment
- ✅ 68% cost savings vs all-Claude
- ✅ Parallel development capability

**Start working on your 5 projects!**

