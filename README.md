# GAIA Autonomous Development System

**Home Directory**: `/Users/jgirmay/Desktop/gitrepo/GAIA_HOME`

GAIA is Anthropic's autonomous development orchestration system that coordinates multiple Claude AI sessions to work on distributed development tasks without interfering with repository branches.

## Architecture

### Core Principle
GAIA orchestrates from its own **isolated home directory** and uses **distributed file-based locking** to prevent multiple workers from simultaneously modifying the same repository folder.

```
GAIA_HOME (Central Orchestration)
├── orchestration/          # Configuration & initialization
│   ├── gaia_init.py       # Initialization system
│   └── gaia_config.json   # Session group configuration
├── locks/                 # Distributed lock files (.gaia)
├── sessions/              # Session state tracking
├── metrics/               # Performance metrics
└── backups/              # Backup configurations
```

Repositories are left **untouched except via locks**:
```
Repository (pyWork/architect/etc)
├── .gitignore            # Added: .gaia* patterns
├── gaia_lock_manager.py  # Added: lock management
├── ... normal code ...
└── [NO GAIA METADATA IN .git]
```

## How It Works

### 1. GAIA Initialization (`gaia_init.py`)

When GAIA starts, it initializes three tiers of agents:

#### 🏛️ Architect Agent Groups (Strategic Layer)
Oversee system-wide decisions and architecture:

```json
{
  "Architect-Strategic": [
    "arch_lead",          // Leadership decisions
    "claude_architect",   // Architecture validation
    "gaia_orchestrator"   // GAIA control
  ],
  "Architect-Oversight": [
    "inspector",         // Code inspection
    "gaia_linter",       // Quality assurance
    "pr_review1-3"       // PR oversight
  ],
  "Architect-Coordination": [
    "foundation",        // Core integration
    "comparison",        // Comparative analysis
    "codex_worker"       // Code generation
  ]
}
```

#### 🎯 Manager Groups (Tactical Layer)
Per-module management and coordination:

```json
{
  "Manager-Reading": [manager_reading, dev_reading_1-2, tester_reading],
  "Manager-Math": [manager_math, dev_math_1-2, tester_math],
  "Manager-Piano": [manager_piano, dev_piano_1-2, tester_piano],
  "Manager-Typing": [manager_typing, dev_typing_1-2, tester_typing],
  "Manager-Dashboard": [manager_dashboard, dev_dashboard_1-2, tester_dashboard]
}
```

#### 🔧 Worker Pools (Execution Layer)
Generic worker sessions available for task assignment:

```json
{
  "Claude-Workers": 5 sessions (dev_worker_1-5),
  "Codex-Workers": 3 sessions (codex_worker_1-3),
  "PR-Implementation": 4 sessions (pr_impl_1-4),
  "PR-Integration": 3 sessions (pr_integ_1-3)
}
```

### 2. Task Assignment with Locking

When a task is assigned to a worker:

```
Task: "Implement User CRUD in architect repo"
      ↓
Assigner checks: Is /path/to/architect locked?
      ├─→ YES: Task waits (folder is busy)
      └─→ NO: Acquire lock
            ├─ Create: gaia_locks/.gaia_a1b2c3d4.lock
            ├─ Create: /path/to/architect/.gaia (marker)
            └─ Assign task to available worker
```

### 3. Distributed Lock System

**Lock Files** (stored in GAIA_HOME, not in repos):
```
/Users/jgirmay/Desktop/gitrepo/GAIA_HOME/locks/
├── .gaia_a1b2c3d4.lock  # Lock for architect repo
├── .gaia_e5f6g7h8.lock  # Lock for reading app repo
└── .gaia_i9j0k1l2.lock  # Lock for other repo
```

**Folder Markers** (in repo, in .gitignore):
```
/path/to/repo/
├── .gaia               # Temporary marker (git-ignored)
└── .gitignore          # Contains: .gaia*
```

**Lock Metadata**:
```json
{
  "folder_path": "/Users/jgirmay/Desktop/gitrepo/pyWork/architect",
  "session_id": "dev_worker_1",
  "task_id": 127,
  "created_at": "2026-02-21T10:30:45",
  "expires_at": "2026-02-21T12:30:45",
  "status": "active"
}
```

### 4. Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  Task enters GAIA queue (e.g., "Implement feature X")      │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Architect group evaluates task feasibility and planning    │
│  • Strategic group: High-level approach                     │
│  • Oversight group: Validation                              │
│  • Coordination group: Integration concerns                 │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Manager group (e.g., Manager-Reading) receives task       │
│  • Plans implementation                                      │
│  • Determines working folder                                │
│  • Orchestrates worker assignment                           │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Assigner checks lock status                                │
│  • Is working folder locked?                                │
│  • If yes: Wait for lock release                            │
│  • If no: Acquire lock + assign to worker pool              │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Worker executes task on locked folder                      │
│  • Only one worker can modify folder at a time              │
│  • Safe git operations (no conflicts)                       │
│  • Worker runs tests, creates PRs, etc.                     │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Task completion                                             │
│  • Lock is released                                         │
│  • .gaia marker removed                                     │
│  • Oversight group validates quality                        │
│  • Next task in queue claims folder                         │
└─────────────────────────────────────────────────────────────┘
```

## Benefits

### ✅ No Repository Pollution
- GAIA metadata lives in `GAIA_HOME`, not in repos
- `.gaia` files are git-ignored
- Repository history stays clean
- No "GAIA system" commits

### ✅ Safe Parallel Development
- Multiple workers can work on different repos simultaneously
- Only one worker per repo folder at a time
- Git conflicts prevented by locking
- Automatic rollback if tasks fail

### ✅ Distributed Coordination
- Architect groups plan strategy
- Manager groups handle tactical execution
- Worker pools execute tasks
- Clear separation of concerns

### ✅ Visibility & Control
- Lock status always visible: `python3 gaia_lock_manager.py --status`
- Can inspect `.gaia` files in folders being worked on
- Full audit trail in `GAIA_HOME/orchestration/`
- Metrics tracked in `GAIA_HOME/metrics/`

## Directory Structure

```
GAIA_HOME/
├── orchestration/
│   ├── gaia_init.py                # Initialization system
│   ├── gaia_config.json           # Current configuration
│   └── README.md                   # This file
├── locks/
│   ├── .gaia_a1b2c3d4.lock        # Lock file 1
│   ├── .gaia_e5f6g7h8.lock        # Lock file 2
│   └── .gaia_*.lock               # Additional locks
├── sessions/
│   ├── session_state.json         # Current session states
│   └── session_assignments.json   # Who's assigned to what
├── metrics/
│   ├── performance.json           # Task execution metrics
│   ├── cost_tracking.json         # LLM provider costs
│   └── daily_reports.json         # Daily summaries
└── backups/
    ├── gaia_config_20260221.json  # Configuration backup
    └── state_backup_20260221.json # System state backup
```

## Usage

### Initialize GAIA

```bash
cd /Users/jgirmay/Desktop/gitrepo/GAIA_HOME
python3 orchestration/gaia_init.py
```

### Check Lock Status

```bash
# All locks
python3 /Users/jgirmay/Desktop/gitrepo/pyWork/architect/gaia_lock_manager.py --status

# By session
python3 ... --status --session dev_worker_1

# Cleanup expired locks
python3 ... --cleanup
```

### Send Task to GAIA

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Auto-assign to best available session
python3 workers/assigner_worker.py --send "Implement feature X" --priority 5

# Target specific manager group
python3 workers/assigner_worker.py --send "Fix reading bug" --target manager_reading
```

### Monitor GAIA Status

```bash
# Check all active prompts
python3 workers/assigner_worker.py --prompts

# Check session status
python3 workers/assigner_worker.py --sessions

# See metrics
curl http://localhost:8080/api/gaia/status
```

## Architecture Decisions

### Why File-Based Locks?
- No external dependencies (no Redis/etcd needed)
- Works across SSH sessions
- Survives process restarts
- Human-readable lock files
- Easy to debug

### Why Separate Home Directory?
- Keeps repos clean (no .gaia metadata)
- Central control point for orchestration
- Easy to backup/restore GAIA state
- Clear separation: GAIA ↔ Repos

### Why Architect Groups?
- Strategic decisions made by experienced agents
- Prevents unilateral bad decisions by workers
- Quality assurance built-in
- Oversight prevents mistakes

## Integration with Existing Systems

### Browser Agent
- GAIA can assign browser automation tasks
- Tab group management coordinated
- No lock needed (browser state ≠ git repos)

### Architect Dashboard
- Task queue shows GAIA status
- Architect can override priorities
- View lock status in UI
- Manually claim/release locks if needed

### Task Worker
- Picks up tasks from GAIA queue
- Respects lock system
- Reports completion back to GAIA
- Metrics tracked to GAIA_HOME/metrics/

## Examples

### Example 1: Implement Reading Module Feature

```
Task: "Add spaced repetition to reading module"

1. GAIA receives task
2. Architect-Strategic evaluates feasibility
3. Manager-Reading plans implementation
4. Assigner acquires lock on reading repo
5. dev_reading_1 implements feature
6. Oversight-Group reviews code
7. pr_impl_1 creates PR
8. pr_review_1 reviews PR
9. Lock released, next task claimed
```

### Example 2: Parallel Work on Multiple Modules

```
Time 0:00 - Task 1: "Fix bug in reading"
           Locks: /reading → dev_worker_1

Time 0:01 - Task 2: "Optimize math"
           Locks: /math → dev_worker_2
           (Different folder, no conflict!)

Time 0:05 - Task 3: "Add feature to piano"
           Locks: /piano → dev_worker_3
           (All running in parallel)

Time 0:30 - Task 1 completes
           Unlocks: /reading
           Task 4: "Implement reading tests"
           Locks: /reading → dev_worker_4
```

## Troubleshooting

### "Folder is locked but I need to work on it"
Check who's working on it:
```bash
python3 gaia_lock_manager.py --status | grep folder_path
```

Wait for completion or manually release (if it's orphaned):
```bash
python3 gaia_lock_manager.py --cleanup
```

### "Lock won't release"
Locks auto-expire after 2 hours. To clean up manually:
```bash
rm gaia_locks/.gaia_*.lock
```

### ".gaia file still in repo after task"
Should be auto-cleaned, but if not:
```bash
rm /path/to/repo/.gaia
```

## Future Enhancements

- [ ] Lock priority system (urgent tasks can preempt)
- [ ] Lock delegation (pass work to another session)
- [ ] Predictive locking (reserve folders for upcoming tasks)
- [ ] Lock analytics dashboard
- [ ] Cross-repo lock dependencies
- [ ] Lock-aware git merge conflict resolution

---

**GAIA Orchestration System v1.0**
Initialized: 2026-02-21
Home: `/Users/jgirmay/Desktop/gitrepo/GAIA_HOME`
