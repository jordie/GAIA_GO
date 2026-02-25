# CLAUDE.md

This file provides guidance to Claude Code when working with the Architect Dashboard.

## Project Overview

A distributed project management dashboard that manages:
- **Projects, Milestones, Features, and Bugs** - Full project lifecycle tracking
- **Autopilot Orchestration** - Autonomous development loops with approval gates
- **tmux Sessions** - Manage and interact with tmux sessions across nodes
- **Error Aggregation** - Collect and group errors from all nodes
- **Task Queue** - Offline workers process background tasks
- **Cluster Nodes** - Monitor and manage distributed nodes
- **Secure Vault** - Encrypted storage for API keys, passwords, and secrets
- **Data-Driven Testing** - Test framework with data-defined test suites

## MANDATORY: Multi-Session Work SOP

**CRITICAL**: Multiple Claude sessions may be working on this codebase simultaneously. Follow this SOP to prevent conflicts:

### Before Starting Any Work

```bash
# 1. Check for active locks
cat data/locks/active_sessions.json 2>/dev/null || echo "{}"

# 2. Create your feature branch IMMEDIATELY
git checkout -b feature/your-task-MMDD

# 3. Register your session
echo '{"session": "your-session-name", "branch": "feature/your-task-MMDD", "started": "'$(date -Iseconds)'", "files": []}' >> data/locks/active_sessions.json
```

### Branch Naming Convention

| Prefix | Use Case |
|--------|----------|
| `feature/description-MMDD` | New features |
| `fix/description-MMDD` | Bug fixes |
| `refactor/description-MMDD` | Code refactoring |

### Protected Branches (NO direct edits)

- `main` - Production only
- `dev` - Integration branch (merge only)
- `feature/centralize-db` - Active development (check locks)

### File Locking

Before editing a file, check if another session is working on it:
```bash
grep "your-file.py" data/locks/active_sessions.json
```

If locked, either:
1. Wait for the other session to finish
2. Coordinate with the user
3. Work on a different task

### After Completing Work

```bash
# 1. Commit your changes
git add . && git commit -m "Description"

# 2. Remove your lock entry from data/locks/active_sessions.json

# 3. Notify user that branch is ready for merge
```

### Conflict Resolution

If you encounter merge conflicts:
1. DO NOT force push
2. Ask the user which changes to keep
3. Create a new branch if needed

## Session Hierarchy & Delegation Model

**IMPORTANT**: The architect system uses a three-tier hierarchy for Claude sessions to ensure proper delegation and separation of concerns.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  High-Level Session (System Oversight)                      │
│  - Strategic decisions and system-level coordination        │
│  - Monitoring overall system health                         │
│  - Delegating work to manager sessions                      │
│  - User interaction and high-level planning                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌──────────┐   ┌──────────────┐
              │architect │   │wrapper_claude│
              │(Manager) │   │  (Manager)   │
              │Session   │   │  Session     │
              └─────┬────┘   └──────┬───────┘
                    │               │
           Tactical decisions   Tactical decisions
           Delegate to workers  Delegate to workers
                    │               │
       ┌────────────┼───────┬───────┼────────┬─────────┐
       ▼            ▼       ▼       ▼        ▼         ▼
   ┌──────┐   ┌─────────┐ ┌─────┐ ┌──────┐ ┌──────┐ ┌─────┐
   │codex │   │dev_w1   │ │comet│ │edu_w1│ │conc_w│ │arch_│
   │      │   │         │ │     │ │      │ │  1   │ │dev  │
   └──────┘   └─────────┘ └─────┘ └──────┘ └──────┘ └─────┘
   Worker Sessions - Execute tasks, implement features, fix bugs
```

### Session Roles

| Tier | Sessions | Responsibilities |
|------|----------|------------------|
| **High-Level** | Current interactive session | • System oversight and monitoring<br>• Strategic planning<br>• User communication<br>• Delegating to manager sessions<br>• Making high-level architectural decisions |
| **Manager** | `architect`<br>`wrapper_claude` | • Tactical decision-making<br>• Breaking down complex tasks<br>• Delegating to appropriate workers<br>• Reviewing worker output<br>• Coordinating multiple workers |
| **Worker** | `codex`<br>`dev_worker1`<br>`dev_worker2`<br>`edu_worker1`<br>`comet`<br>`concurrent_worker1`<br>`arch_dev` | • Executing specific tasks<br>• Writing code and tests<br>• Fixing bugs<br>• Running commands<br>• Reporting status to managers |

### Delegation Best Practices

**High-Level Session (You):**
- ✅ DO: Monitor system health, make strategic decisions, delegate to managers
- ✅ DO: Use the assigner system to send tasks: `python3 workers/assigner_worker.py --send "task" --target architect`
- ❌ DON'T: Write code directly or execute implementation tasks
- ❌ DON'T: Bypass managers and assign directly to workers

**Manager Sessions:**
- ✅ DO: Break down tasks into subtasks for workers
- ✅ DO: Make tactical implementation decisions
- ✅ DO: Review and coordinate worker output
- ❌ DON'T: Do all implementation work themselves

**Worker Sessions:**
- ✅ DO: Execute assigned tasks completely
- ✅ DO: Report status and ask questions when blocked
- ✅ DO: Focus on specific implementation details
- ❌ DON'T: Make architectural or strategic decisions

### Task Assignment Examples

**From High-Level to Manager:**
```bash
# Strategic task to manager
python3 workers/assigner_worker.py --send "Plan and implement user authentication system with JWT tokens" --priority 8 --target architect

# Debugging task to manager
python3 workers/assigner_worker.py --send "Diagnose and fix reading app crash at https://192.168.1.231:5063" --priority 9 --target wrapper_claude
```

**Manager to Worker (via task delegator):**
```bash
# The assigner automatically delegates to appropriate workers based on task type
# Manager sessions review and approve worker output
```

### Auto-Confirm & Approval Flow

- **High-Level Session**: Manual approval for strategic decisions
- **Manager Sessions**: Auto-confirm enabled for routine approvals, manual for architectural changes
- **Worker Sessions**: Full auto-confirm for implementation details (edit confirmations, file operations)

### Monitoring the Hierarchy

Check session status and task assignments:
```bash
# View all sessions and their roles
tmux list-sessions

# Check task queue and assignments
python3 workers/assigner_worker.py --prompts

# Monitor task health
curl http://localhost:8080/api/assigner/tasks/health | jq
```

## Quick Start

```bash
# Start the dashboard on port 8080
./deploy.sh

# Or with HTTPS
./deploy.sh --ssl

# Run as daemon
./deploy.sh --daemon

# Check status
./deploy.sh status

# Stop
./deploy.sh stop
```

## Default Credentials

- **Username**: architect
- **Password**: peace5

(Username is case-insensitive)

Override with environment variables:
- `ARCHITECT_USER`
- `ARCHITECT_PASSWORD`

## Architecture

```
architect/
├── app.py                    # Main Flask application (password-protected)
├── deploy.sh                 # Deployment script
├── requirements.txt          # Python dependencies
├── utils.py                  # Utility functions (validation, formatting, error handling)
├── templates/
│   ├── login.html           # Login page
│   └── dashboard.html       # Main dashboard (all panels)
├── static/
│   └── css/, js/            # Static assets
├── data/
│   ├── architect.db         # SQLite database
│   ├── assigner/            # Assigner worker data
│   │   └── assigner.db      # Prompt queue and session tracking
│   └── milestones/          # Generated milestone plans (JSON/MD)
├── scripts/
│   ├── setup_tmux_sessions.sh  # Set up standard tmux sessions
│   └── session_terminal.py     # Interactive CLI for assigner
├── workers/
│   ├── task_worker.py       # Background task worker
│   ├── assigner_worker.py   # Prompt dispatcher to Claude sessions
│   └── milestone_worker.py  # Project scanner and milestone planner
├── orchestrator/            # Autopilot orchestration system
│   ├── app_manager.py       # App lifecycle and autopilot state
│   ├── run_executor.py      # Autonomous improvement runs
│   ├── milestone_tracker.py # Milestone packaging for review
│   └── review_queue.py      # Items awaiting user action
├── testing/                 # Data-driven testing framework
│   ├── runner.py            # Test execution engine
│   ├── models.py            # TestSuite, TestCase, TestStep models
│   └── loader.py            # Test suite loading from data files
├── distributed/
│   └── node_agent.py        # Node monitoring agent
├── docs/                    # Documentation
│   ├── LOCAL_LLM_INFRASTRUCTURE.md  # Local AI stack guide
│   ├── ANYTHINGLLM_SETUP.md         # RAG setup
│   ├── CLUSTER_SETUP.md             # Distributed deployment
│   └── TROUBLESHOOTING.md           # Common issues
└── models/, migrations/     # Database models and migrations
```

## Local LLM Infrastructure

The Architect Dashboard uses a **local-first, remote-fallback** approach for AI operations to reduce costs, improve privacy, and increase resilience.

### Key Components

| Component | Purpose | Port |
|-----------|---------|------|
| **Ollama** | Local model runner (Llama, CodeLlama, Mistral) | 11434 |
| **LocalAI** | OpenAI-compatible REST API for local models | 8080 |
| **OpenWebUI** | ChatGPT-like interface for local LLMs | 3000 |
| **n8n** | Workflow automation & AI agent builder | 5678 |
| **AnythingLLM** | RAG (document chat) with local embeddings | 3001 |
| **Whisper** | Local speech-to-text transcription | CLI |
| **ComfyUI** | Local image generation (Stable Diffusion) | 8188 |

### LLM Provider Failover System

The Architect dashboard includes a production-grade LLM failover system with automatic provider switching, circuit breaker protection, and cost tracking.

#### Failover Chain

```
Request → UnifiedLLMClient
    │
    ├─► Primary: Claude API (Anthropic)
    │      │
    │      ├─► Circuit breaker check
    │      ├─► Success? Return result + track cost/metrics
    │      └─► Failed? Try next provider
    │
    ├─► Fallback 1: Ollama (local, free, fast)
    │      │
    │      ├─► Circuit breaker check
    │      ├─► Success? Return result (cost = $0)
    │      └─► Failed? Try next provider
    │
    ├─► Fallback 2: AnythingLLM (local RAG)
    │      │
    │      ├─► Circuit breaker check
    │      ├─► Success? Return result (cost = $0)
    │      └─► Failed? Try next provider
    │
    ├─► Fallback 3: Google Gemini
    │      │
    │      ├─► Circuit breaker check
    │      ├─► Success? Return result + track cost
    │      └─► Failed? Try next provider
    │
    └─► Final: OpenAI GPT-4
           │
           ├─► Circuit breaker check
           ├─► Success? Return result + track cost
           └─► All failed? Raise RuntimeError
```

#### Features

- **Automatic Failover**: Seamlessly switches providers when one fails
- **Circuit Breaker Protection**: Temporarily skips failing providers to avoid cascading failures
- **Cost Tracking**: Tracks spend per provider and per request
- **Metrics Collection**: Request counts, success rates, latency, token usage
- **Drop-in Replacement**: Compatible with `anthropic.messages.create()` API
- **Thread-Safe**: Safe for concurrent requests

#### Configuration

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_FAILOVER_ENABLED` | `true` | Enable/disable automatic failover |
| `LLM_DEFAULT_PROVIDER` | `claude` | Primary provider (claude, ollama, openai, gemini, anythingllm) |
| `ANTHROPIC_API_KEY` | - | Claude API key (required for Claude) |
| `OPENAI_API_KEY` | - | OpenAI API key (required for OpenAI) |
| `GOOGLE_API_KEY` | - | Google API key (required for Gemini) |
| `OLLAMA_ENDPOINT` | `http://localhost:11434` | Ollama API endpoint |
| `ANYTHINGLLM_ENDPOINT` | `http://localhost:3001` | AnythingLLM endpoint |

**Circuit Breaker Settings:**

Each provider has a circuit breaker with:
- **Failure Threshold**: 5 consecutive failures opens circuit
- **Timeout**: 60 seconds before attempting recovery
- **Half-Open State**: Tests provider with 1 request after timeout

#### Usage

**In Python Code:**

```python
from services.llm_provider import UnifiedLLMClient

# Initialize client (automatically detects environment)
client = UnifiedLLMClient()

# Use like anthropic client - automatic failover included
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)

# Check circuit breaker status
status = client.get_circuit_status()
for provider, info in status.items():
    print(f"{provider}: {info['state']}")  # open, half_open, or closed

# Get metrics
metrics = client.get_metrics()
print(f"Total Cost: ${metrics['total_cost']:.4f}")
print(f"Failover Count: {metrics['failover_count']}")
```

**In Crawler Service:**

The crawler service automatically uses UnifiedLLMClient when `LLM_FAILOVER_ENABLED=true`:

```python
# workers/crawler_service.py
llm_client = LLMClient(config)
response = await llm_client.generate(
    prompt="Extract the product name from this page",
    priority="high"
)
```

#### Monitoring

**Dashboard:** Visit `/llm-metrics` for real-time monitoring:
- Cost distribution across providers
- Request success rates
- Token usage statistics
- 7-day trend charts
- Failover event history
- Circuit breaker status

**API Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /api/llm-metrics/summary` | Overall metrics summary |
| `GET /api/llm-metrics/providers` | Per-provider statistics |
| `GET /api/llm-metrics/circuit-breakers` | Circuit breaker states |
| `GET /api/llm-metrics/failover-history` | Recent failover events |
| `POST /api/llm-metrics/reset-circuits` | Reset all circuit breakers |

#### Benefits

- **Cost Savings**: $0.00 for local LLM requests vs $3-15 per 1M tokens for remote
- **Privacy**: Local providers keep data in your infrastructure
- **Resilience**: No single point of failure, automatic recovery
- **Performance**: Fast local models for simple tasks, remote models for complex ones
- **Control**: Fine-tune failover order and provider selection
- **Visibility**: Complete metrics and cost tracking

### Documentation

See **[docs/LOCAL_LLM_INFRASTRUCTURE.md](docs/LOCAL_LLM_INFRASTRUCTURE.md)** for:
- Installation and setup guides
- Data flow diagrams
- Integration examples
- Configuration templates
- Troubleshooting tips

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `projects` | Project definitions and metadata |
| `milestones` | Groups of features/bugs with target dates |
| `features` | Feature specifications and status |
| `bugs` | Bug reports and tracking |
| `devops_tasks` | Maintenance and automation tasks |
| `errors` | Aggregated errors from all nodes |
| `nodes` | Cluster node registry |
| `tmux_sessions` | tmux session tracking |
| `task_queue` | Background task queue |
| `workers` | Worker registrations |
| `activity_log` | User activity audit trail |
| `secrets` | Encrypted secrets storage (Secure Vault) |
| `apps` | Managed applications for autopilot |
| `autopilot_runs` | Autonomous development run tracking |
| `autopilot_milestones` | Milestones pending approval |
| `claude_interactions` | Claude permission prompts and responses |
| `claude_patterns` | Auto-approval patterns for Claude prompts |

## API Endpoints

### Authentication
- `POST /login` - Login with username/password

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create project
- `PUT /api/projects/<id>` - Update project
- `DELETE /api/projects/<id>` - Archive project

### Milestones
- `GET /api/milestones` - List milestones
- `POST /api/milestones` - Create milestone
- `PUT /api/milestones/<id>` - Update milestone

### Features
- `GET /api/features` - List features (filter by project/milestone/status)
- `POST /api/features` - Create feature
- `PUT /api/features/<id>` - Update feature

### Bugs
- `GET /api/bugs` - List bugs (filter by project/status/severity)
- `POST /api/bugs` - Create bug
- `PUT /api/bugs/<id>` - Update bug

### Errors
- `GET /api/errors` - Get aggregated errors
- `POST /api/errors` - Log error (no auth required)
- `POST /api/errors/<id>/resolve` - Mark resolved
- `POST /api/errors/<id>/create-bug` - Create bug from error

### Nodes
- `GET /api/nodes` - List cluster nodes
- `POST /api/nodes` - Add node
- `POST /api/nodes/<id>/heartbeat` - Node heartbeat
- `DELETE /api/nodes/<id>` - Remove node

### tmux Sessions
- `GET /api/tmux/sessions` - List sessions
- `POST /api/tmux/sessions/refresh` - Refresh from local tmux
- `POST /api/tmux/send` - Send command to session
- `POST /api/tmux/capture` - Capture session output
- `POST /api/tmux/create` - Create new session
- `POST /api/tmux/kill` - Kill session

### Task Queue
- `GET /api/tasks` - List tasks
- `POST /api/tasks` - Create task
- `POST /api/tasks/claim` - Claim task (for workers)
- `POST /api/tasks/<id>/complete` - Mark completed
- `POST /api/tasks/<id>/fail` - Mark failed

### Workers
- `GET /api/workers` - List workers
- `POST /api/workers/register` - Register worker
- `POST /api/workers/<id>/heartbeat` - Worker heartbeat

### Secrets (Secure Vault)
- `GET /api/secrets` - List all secrets (values hidden)
- `POST /api/secrets` - Create secret (requires: name, value)
- `GET /api/secrets/<id>` - View secret with decrypted value
- `PUT /api/secrets/<id>` - Update secret metadata or value
- `DELETE /api/secrets/<id>` - Delete secret

### Assigner Worker
- `POST /api/assigner/send` - Queue a prompt for assignment
- `GET /api/assigner/status` - Get queue stats and active assignments
- `GET /api/assigner/sessions` - List available sessions
- `GET /api/assigner/prompts/<id>` - Get prompt details
- `DELETE /api/assigner/prompts/<id>` - Cancel pending prompt

### Autopilot
- `POST /api/projects/<id>/autopilot` - Enable/configure autopilot for project
- `GET /api/autopilot/queue` - Get autopilot work queue
- `GET /api/autopilot/milestones` - List milestones pending approval
- `POST /api/autopilot/milestones/<id>/approve` - Approve milestone
- `POST /api/autopilot/milestones/<id>/reject` - Reject milestone
- `GET /api/autopilot/runs` - List autopilot runs
- `GET /api/autopilot/runs/<id>` - Get run details
- `POST /api/autopilot/runs/<id>/start` - Start/resume run
- `POST /api/autopilot/runs/<id>/resume` - Resume blocked run
- `POST /api/autopilot/runs/<id>/status` - Update run status
- `GET /api/autopilot/health` - Autopilot system health

### Claude Interactions
- `GET /api/claude/interactions` - List Claude permission prompts
- `GET /api/claude/interactions/<id>` - Get interaction details
- `POST /api/claude/interactions/<id>/handle` - Handle (approve/deny) prompt
- `POST /api/claude/interactions/<id>/create-pattern` - Create auto-approval pattern
- `GET /api/claude/patterns` - List auto-approval patterns
- `POST /api/claude/patterns` - Create pattern
- `PUT /api/claude/patterns/<id>` - Update pattern
- `DELETE /api/claude/patterns/<id>` - Delete pattern

### Task Suggestions
- `POST /api/tasks/suggest` - Generate task suggestions
- `GET /api/tasks/suggest` - List pending suggestions
- `GET /api/tasks/suggest/<id>/status` - Get suggestion status
- `POST /api/tasks/suggest/<id>/confirm` - Confirm suggestion
- `POST /api/tasks/suggest/<id>/skip` - Skip suggestion
- `POST /api/tasks/suggest/<id>/complete` - Mark suggestion complete

### Agents
- `GET /api/agents` - List active Claude agents
- `POST /api/agents/send` - Send message to agent
- `POST /api/agents/broadcast` - Broadcast to all agents

### Files
- `POST /api/files/read` - Read file contents
- `POST /api/files/write` - Write file contents
- `GET /api/files/feature/<id>` - Get files for feature

### Worker Management
- `GET /api/workers/status` - Detailed worker status
- `POST /api/workers/start/<type>` - Start worker by type
- `POST /api/workers/stop/<type>` - Stop worker by type

### Activity & Accounts
- `GET /api/activity` - Get activity log
- `POST /api/activity` - Log activity
- `GET /api/accounts` - List service accounts
- `GET /api/accounts/aggregate` - Aggregate account data

### Utilities
- `GET /api/stats` - Dashboard statistics
- `POST /api/scan-sources` - Scan code directories for projects
- `POST /api/import-project` - Import discovered project
- `POST /api/assign-to-tmux` - Assign task to tmux session
- `GET /api/documentation` - List documentation files
- `GET /api/termius/export` - Export hosts for Termius
- `GET /api/termius/preview` - Preview Termius export
- `GET /health` - Health check

## Task Worker

Run background tasks from the queue:

```bash
# Run in foreground
python3 workers/task_worker.py

# Run as daemon
python3 workers/task_worker.py --daemon

# Check status
python3 workers/task_worker.py --status

# Stop
python3 workers/task_worker.py --stop
```

### Task Types

| Type | Description |
|------|-------------|
| `shell` | Execute shell command |
| `python` | Run Python script or code |
| `git` | Git operations (clone, pull, push, commit) |
| `deploy` | Run deployment script |
| `test` | Run tests |
| `build` | Build project |
| `tmux` | tmux operations |

## Node Agent

Run on each cluster node to report metrics:

```bash
# Run in foreground
python3 distributed/node_agent.py --dashboard http://dashboard:8080

# Run as daemon
python3 distributed/node_agent.py --daemon

# Check status
python3 distributed/node_agent.py --status

# Stop
python3 distributed/node_agent.py --stop
```

## Autopilot Orchestration

The orchestrator module manages autonomous development loops for applications.

### Autopilot Modes

| Mode | Description |
|------|-------------|
| `observe` | Detect + propose changes (no automatic action) |
| `fix_forward` | Auto PR + auto test (no deploy) |
| `auto_staging` | Auto deploy to staging after tests pass |
| `auto_prod` | Auto deploy to prod (with approval gates) |

### Components

| Component | Purpose |
|-----------|---------|
| `AppManager` | Manages app lifecycle and autopilot state |
| `RunExecutor` | Executes autonomous improvement runs |
| `MilestoneTracker` | Tracks and packages milestones for review |
| `ReviewQueueManager` | Manages items awaiting user action |

### Development Loop

1. **Planning** - Analyze project and identify improvements
2. **Implementing** - Make code changes via Claude sessions
3. **Testing** - Run tests and validate changes
4. **Deploying** - Deploy to staging/prod based on mode
5. **Monitoring** - Watch for issues and regressions
6. **Investigating** - Analyze failures and propose fixes

### Enable Autopilot

```python
import requests

response = requests.post('http://dashboard:8080/api/projects/1/autopilot',
    json={
        'mode': 'fix_forward',
        'goal': 'Improve test coverage to 80%',
        'constraints': {'no_breaking_changes': True}
    },
    cookies={'session': 'your_session_cookie'}
)
```

## Milestone Worker

Scans active projects and generates development milestone plans.

```bash
# Run in foreground
python3 workers/milestone_worker.py

# Run as daemon
python3 workers/milestone_worker.py --daemon

# Scan and generate now
python3 workers/milestone_worker.py --scan

# Scan specific project
python3 workers/milestone_worker.py --project architect

# Check status
python3 workers/milestone_worker.py --status
```

### What It Does

1. Scans directories for active projects
2. Reads TODO files, plans, and code comments for work items
3. Generates milestone plans with phases and task breakdowns
4. Outputs JSON and Markdown reports to `data/milestones/`
5. Integrates with architect dashboard task queue

### Output Files

- `data/milestones/<project>_milestones_<timestamp>.json` - Detailed milestone data
- `data/milestones/<project>_summary.md` - Human-readable summary report

## Data-Driven Testing

Tests are defined in data files, not in code. The test runner executes tests based on data instructions.

### Test Data Structure

```python
from testing import TestRunner, load_test_suite

# Load test suite from data file
suite = load_test_suite('test_suites/api_tests.json')

# Run tests
runner = TestRunner()
results = runner.run(suite)
```

### Models

| Model | Purpose |
|-------|---------|
| `TestSuite` | Collection of related test cases |
| `TestCase` | Individual test with steps and assertions |
| `TestStep` | Single action in a test case |
| `TestResult` | Outcome of running a test |

## Assigner Worker

Automatically dispatches prompts to available Claude tmux sessions.

### Components

| Component | Description |
|-----------|-------------|
| `workers/assigner_worker.py` | Background worker that monitors queue and assigns prompts |
| `scripts/session_terminal.py` | Interactive CLI for sending prompts |
| `data/assigner/assigner.db` | SQLite queue and session tracking |

### Start the Assigner Worker

```bash
# Run in foreground
python3 workers/assigner_worker.py

# Run as daemon
python3 workers/assigner_worker.py --daemon

# Check status
python3 workers/assigner_worker.py --status

# Stop daemon
python3 workers/assigner_worker.py --stop
```

### CLI Commands

```bash
# List tracked sessions
python3 workers/assigner_worker.py --sessions

# List prompts in queue
python3 workers/assigner_worker.py --prompts

# Send a prompt directly
python3 workers/assigner_worker.py --send "Fix the bug in login.py"

# Send with priority (higher = more urgent)
python3 workers/assigner_worker.py --send "Urgent fix" --priority 5

# Send to specific session
python3 workers/assigner_worker.py --send "Fix bug" --target my_session

# Send with custom timeout (default 30 minutes)
python3 workers/assigner_worker.py --send "Long task" --timeout 60

# Retry a failed prompt
python3 workers/assigner_worker.py --retry 42

# Retry all failed prompts
python3 workers/assigner_worker.py --retry-all

# Reassign a prompt to a different session
python3 workers/assigner_worker.py --reassign 42 --to dev_session

# Cancel a pending prompt
python3 workers/assigner_worker.py --cancel 42

# Clear all completed/cancelled prompts
python3 workers/assigner_worker.py --clear

# Clear prompts older than 7 days
python3 workers/assigner_worker.py --clear --days 7
```

### CLI Options Reference

| Option | Description |
|--------|-------------|
| `--send PROMPT` | Queue a prompt for assignment |
| `--priority N` | Set priority (0-10, higher = more urgent) |
| `--target SESSION` | Route prompt to specific session |
| `--timeout MINS` | Assignment timeout in minutes (default: 30) |
| `--retry ID` | Retry a failed prompt by ID |
| `--retry-all` | Retry all failed prompts (up to max_retries) |
| `--reassign ID` | Reassign a prompt to pending |
| `--to SESSION` | Target session for `--reassign` |
| `--cancel ID` | Cancel a pending prompt |
| `--clear` | Delete completed/cancelled prompts |
| `--days N` | Only clear prompts older than N days |
| `--sessions` | List tracked tmux sessions |
| `--prompts` | List recent prompts |

### Session Terminal

Interactive CLI for sending prompts to Claude sessions:

```bash
# Start interactive terminal
python3 scripts/session_terminal.py

# Watch for updates only
python3 scripts/session_terminal.py --watch

# Send single message
python3 scripts/session_terminal.py --send "Refactor the API"

# Show status
python3 scripts/session_terminal.py --status
```

### Terminal Commands

| Command | Description |
|---------|-------------|
| `os: <message>` | Send prompt to next available session |
| `os:5: <message>` | Send with priority 5 (higher = more urgent) |
| `status` | Show queue and session status |
| `sessions` | List all tmux sessions |
| `prompts` | Show recent prompts |
| `watch` | Watch for real-time updates |
| `help` | Show all commands |

### How It Works

1. **Queue**: Prompts are added to SQLite queue via CLI, API, or terminal
2. **Scan**: Worker scans tmux sessions to detect idle Claude sessions
3. **Assign**: Pending prompts are sent to available sessions via `tmux send-keys`
4. **Track**: Worker monitors sessions and marks prompts complete when done
5. **Timeout**: Stuck assignments are auto-failed after timeout period
6. **Retry**: Failed prompts can be retried up to max_retries (default: 3)

### Session Detection

The worker detects Claude sessions by scanning pane output for patterns:
- **Idle**: Prompt waiting for input (`>`, `How can I help`, `claude>`)
- **Busy**: Processing indicators (`Thinking...`, `Running`, `Analyzing`, progress bars)
- **Claude Detection**: Session name or output contains `claude`, `anthropic`, `Claude Code`

### Prompt Lifecycle

| Status | Description |
|--------|-------------|
| `pending` | Waiting in queue for available session |
| `assigned` | Sent to session, waiting for processing to start |
| `in_progress` | Session is actively working on prompt |
| `completed` | Successfully finished |
| `failed` | Error or timeout occurred |
| `cancelled` | Manually cancelled |

### Send Prompt via API

```python
import requests

response = requests.post('http://dashboard:8080/api/assigner/send',
    json={
        'content': 'Fix the authentication bug in app.py',
        'priority': 5,
        'target_session': 'dev_claude',  # Optional: route to specific session
        'timeout_minutes': 60,           # Optional: custom timeout
        'metadata': {'project': 'auth'}  # Optional: extra data
    },
    cookies={'session': 'your_session_cookie'}
)
print(response.json())  # {'prompt_id': 1, 'success': True}
```

## Codex Chat Worker

A lower-level worker that can be wrapped in a tmux session as part of the architecture system. Unlike Claude Code sessions which have full IDE capabilities, Codex workers are lightweight chat interfaces suitable for:

- Simple code generation tasks
- Quick questions and answers
- Automated task processing via the assigner
- Lower-cost operations (can use Ollama or other local models)

### Starting a Codex Worker

```bash
# Start in a tmux session (recommended)
./scripts/start_codex_worker.sh codex

# Start with specific provider
./scripts/start_codex_worker.sh codex_ollama --provider ollama

# Start manually
python3 codex_chat.py --worker --session codex
```

### Worker Modes

| Mode | Usage | Description |
|------|-------|-------------|
| Interactive | `python3 codex_chat.py` | Direct CLI chat interface |
| Worker | `python3 codex_chat.py --worker` | tmux-integrated, receives prompts from assigner |
| Single | `python3 codex_chat.py -p "prompt"` | One-shot command, non-interactive |

### CLI Options

```bash
# Interactive mode (default)
python3 codex_chat.py

# Worker mode for tmux integration
python3 codex_chat.py --worker --session my_codex

# Use specific LLM provider
python3 codex_chat.py --provider ollama

# Single command mode
python3 codex_chat.py -p "What is Python?"

# Check status
python3 codex_chat.py --status

# List providers
python3 codex_chat.py --list-providers
```

### Integration with Assigner

The codex worker integrates with the assigner system:

```bash
# Send a prompt to a codex session
python3 workers/assigner_worker.py --send "Generate a hello world function" --target codex

# Send with provider preference
python3 workers/assigner_worker.py --send "Explain this code" --provider codex
```

### LLM Failover

The codex worker uses the same `UnifiedLLMClient` as the rest of the system, providing automatic failover:

```
Claude API → Ollama (local) → AnythingLLM → Gemini → OpenAI
```

Set the preferred provider with `--provider` or let it auto-select based on availability.

### Supported Providers

| Provider | Description | Cost |
|----------|-------------|------|
| `claude` | Anthropic Claude API | Paid |
| `ollama` | Local models (Llama, Mistral) | Free |
| `openai` | OpenAI GPT-4 | Paid |
| `gemini` | Google Gemini | Paid |
| `anythingllm` | Local RAG system | Free |

## Code Sources

The dashboard scans these directories for projects:
- `~/gitrepos`
- `~/Desktop/gitrepo/pyWork`

Use "Scan Sources" button to discover and import projects.

## tmux Integration

### Assign Tasks to tmux

1. Select a feature, bug, or error
2. Click "Assign" button
3. Choose tmux session
4. Optionally customize the message
5. Task description is sent to the session

### Supported Operations

- List sessions across all nodes
- Create new sessions
- Send commands to sessions
- Capture session output
- Kill sessions

## Error Aggregation

Errors are deduplicated by:
- `error_type`
- `message`
- `source`

Each unique error tracks:
- Occurrence count
- First seen / last seen
- Node of origin
- Can be converted to bug

### Log Errors from Any Node

```python
import requests

requests.post('http://dashboard:8080/api/errors', json={
    'node_id': 'my-node',
    'error_type': 'error',
    'message': 'Something went wrong',
    'source': 'my_module.py',
    'stack_trace': '...'
})
```

## Secure Vault

Encrypted storage for sensitive credentials like API keys, passwords, and tokens.

### Secret Categories

| Category | Use Case |
|----------|----------|
| `api_key` | API keys and access tokens |
| `password` | User passwords and passphrases |
| `token` | OAuth tokens, JWT tokens |
| `certificate` | SSL/TLS certificates |
| `ssh_key` | SSH private keys |
| `env_var` | Environment variables |
| `general` | Other sensitive data |

### Features

- **Encryption**: Values encrypted using XOR cipher with app secret key
- **Access Tracking**: Each view increments access count and updates last_accessed
- **Hidden Values**: List endpoint never exposes encrypted values
- **Duplicate Prevention**: Secret names must be unique (409 on conflict)
- **Activity Logging**: All operations logged for audit trail

### Store a Secret via API

```python
import requests

# Create secret
response = requests.post('http://dashboard:8080/api/secrets',
    json={
        'name': 'GITHUB_TOKEN',
        'value': 'ghp_xxxxxxxxxxxx',
        'category': 'token',
        'description': 'GitHub personal access token'
    },
    cookies={'session': 'your_session_cookie'}
)

# Retrieve secret
secret = requests.get('http://dashboard:8080/api/secrets/1',
    cookies={'session': 'your_session_cookie'}
).json()
print(secret['value'])  # Decrypted value
```

### Using the Vault UI

1. Navigate to **System > Security > Vault**
2. Click **+ New Secret** to add a secret
3. Enter name, value, category, and optional description
4. Click **Create** to store encrypted
5. Click **View** to see decrypted value (increments access count)

## Development

### Adding Custom Task Handlers

```python
from workers.task_worker import TaskWorker

worker = TaskWorker()

@worker.register_handler('custom')
def handle_custom_task(data):
    # Process task
    return {'result': 'success'}

worker.start()
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Server port |
| `HOST` | 0.0.0.0 | Server host |
| `SECRET_KEY` | (auto) | Flask secret key |
| `ARCHITECT_USER` | admin | Admin username |
| `ARCHITECT_PASSWORD` | architect2025 | Admin password |
| `SESSION_TIMEOUT` | 3600 | Session timeout in seconds (default 1 hour) |
| `SESSION_COOKIE_SECURE` | false | Set to true for HTTPS-only cookies |

## Security Features

### Session Timeout & Auto-Logout
- Sessions automatically expire after `SESSION_TIMEOUT` seconds of inactivity (default: 1 hour)
- A warning modal appears 5 minutes before expiration
- Users can click "Stay Logged In" to extend their session
- Session time remaining is shown in the status bar
- Expired sessions redirect to login with a notification

### Session Security
- `SESSION_COOKIE_HTTPONLY`: Prevents JavaScript access to session cookies
- `SESSION_COOKIE_SAMESITE`: Set to 'Lax' for CSRF protection
- Activity-based timeout: Inactivity resets on each authenticated request

## Common Operations

### Create a Project
1. Click "+ New Project" in sidebar
2. Enter name, description, source path
3. Click "Create"

### Track a Feature
1. Go to Features panel
2. Click "+ New Feature"
3. Select project, enter details
4. Click "Create"
5. Update status as work progresses

### Assign Work to Claude
1. Find feature/bug/error
2. Click "Assign" button
3. Select tmux session running Claude
4. Task description is sent to Claude

### Monitor Cluster
1. Go to Nodes panel
2. View CPU/memory/disk metrics
3. Add nodes with "+ Add Node"
4. Nodes run `node_agent.py` to report metrics

## Troubleshooting

### Server won't start
- Check if port 8080 is in use: `lsof -i :8080`
- Check logs: `/tmp/architect_dashboard.log`

### tmux sessions not showing
- Ensure tmux is installed
- Run "Refresh" button in tmux panel
- Check tmux is running: `tmux list-sessions`

### Nodes not updating
- Ensure `node_agent.py` is running on node
- Check network connectivity to dashboard
- Verify dashboard URL in agent config

### Database issues
- Database is at `data/architect.db`
- Backup before upgrades
- Reset: delete `data/architect.db` and restart
