# Component Types Classification

## Overview

This document clarifies the different types of components in the Architect system, their purposes, and relationships.

---

## LLM Providers

### Purpose: Generate Code, Content, and Decisions

| Provider | Type | Primary Use | Interface | Strengths |
|----------|------|-------------|-----------|-----------|
| **Claude (Anthropic)** | General AI | Code generation, refactoring, architecture | tmux session `architect` | Complex reasoning, following SOPs, context understanding |
| **Codex (OpenAI)** | Code specialist | Code completion, bug fixes | tmux session `codex` | Fast code generation, API integration |
| **Claude-Architect** | Specialized Claude | System architecture, design patterns | tmux session `claude_architect` | Large-scale design, multi-file changes |
| **Comet** | Claude variant | Task coordination, meta-programming | tmux session `claude_comet` | Managing other agents, orchestration |
| **AnythingLLM** | Multi-model | Document Q&A, RAG queries | API http://localhost:3001 | Document search, knowledge base |
| **Ollama** | Local models | Privacy-sensitive tasks, offline work | API http://localhost:11434 | No API costs, local execution |
| **Gemini (Google)** | Multimodal | Image understanding, mixed content | API (planned) | Visual analysis, multimedia |

### Classification by Purpose

**Coding LLMs** (Write/modify code):
- Claude → Complex implementations, refactoring
- Codex → Quick code generation, completions
- Claude-Architect → Large-scale architecture changes
- Ollama (code models) → Local code generation

**UI Testing LLMs** (Verify interfaces):
- Comet → Run Playwright tests, verify UI flows
- Claude → Generate test scripts, analyze screenshots
- Gemini → Visual regression testing (planned)

**Agent Management LLMs** (Coordinate others):
- Comet → Primary orchestrator, delegates to other agents
- Claude-Architect → Design workflows for other agents
- AnythingLLM → Query capabilities of other agents

**Decision-Making LLMs** (Planning, analysis):
- Claude → Architecture decisions, design patterns
- Claude-Architect → System-level planning
- AnythingLLM → Document-based recommendations

---

## Agents

### Purpose: Autonomous Workers

| Agent | Type | Purpose | Controlled By | Output |
|-------|------|---------|---------------|--------|
| **Assigner Worker** | Dispatcher | Route prompts to available LLM sessions | System | Database updates |
| **Task Worker** | Executor | Execute queued tasks (shell, Python, git) | System | Task results |
| **Milestone Worker** | Analyzer | Scan projects and generate milestone plans | System | JSON/MD reports |
| **Crawler Service** | Browser automation | Navigate websites, extract data | LLM/API | Screenshots, HTML |
| **Node Agent** | Monitor | Report system metrics (CPU, memory, disk) | System | Metrics to dashboard |
| **Test Runner** | Validator | Execute data-driven test suites | System/User | Test results |
| **LLM Orchestrator** | Coordinator | Run lifecycle tests across providers | System/User | Comprehensive test results |

### Classification by Purpose

**Coding Agents**:
- Task Worker (executes code commits, builds, deployments)

**UI Testing Agents**:
- Test Runner (runs Playwright tests)
- Crawler Service (browser automation for data extraction)

**Management Agents**:
- Assigner Worker (coordinates LLM sessions)
- LLM Orchestrator (manages test execution)
- Milestone Worker (project planning)

**Monitoring Agents**:
- Node Agent (system health)

---

## tmux Sessions

### Purpose: Interactive LLM Interfaces

| Session | LLM Provider | Purpose | Status Indicators | Control Method |
|---------|--------------|---------|-------------------|----------------|
| `architect` | Claude | Primary development tasks | `>`, `Claude>`, `How can I help` | Assigner Worker |
| `codex` | Codex/OpenAI | Code generation tasks | `>`, `>>>` | Assigner Worker |
| `claude_architect` | Claude | Architecture and design | `>`, `Claude>` | Assigner Worker |
| `claude_comet` | Comet/Claude | Meta-coordination | `>`, `Comet>` | Assigner Worker |
| `dev_claude` | Claude | Development environment | `>` | Manual |
| `test_claude` | Claude | Test environment | `>` | Manual |
| `staging_claude` | Claude | Staging environment | `>` | Manual |

### Idle Detection Patterns

Assigner Worker detects idle sessions by scanning for:
- **Prompt indicators**: `>`, `claude>`, `$`, `#`, `How can I help`
- **Non-busy**: No "Thinking...", "Running...", "Analyzing...", progress bars

### Busy Detection Patterns

Sessions are busy when output contains:
- Processing indicators: "Thinking...", "Analyzing...", "Processing..."
- Progress indicators: Loading bars, percentages
- Long-running commands: Still executing

---

## Processes

### Purpose: Background Services

| Process | Type | Purpose | Started By | Monitored By |
|---------|------|---------|------------|--------------|
| `app.py` | Web server | Dashboard and API | `./deploy.sh` | systemd/manual |
| `task_worker.py` | Background worker | Process task queue | Manual/systemd | Worker heartbeat |
| `assigner_worker.py` | Dispatcher | Assign prompts to sessions | Manual/systemd | Worker heartbeat |
| `milestone_worker.py` | Analyzer | Generate project plans | Manual/systemd | Worker heartbeat |
| `node_agent.py` | Monitor | Report metrics | Manual/systemd | Dashboard |
| `crawler_service.py` | Browser service | Web automation | API request | Self-terminating |

### Process Lifecycles

**Long-running** (always active):
- app.py → Dashboard server
- task_worker.py → Task processor
- assigner_worker.py → Prompt dispatcher
- node_agent.py → Metrics reporter

**Periodic** (scheduled):
- milestone_worker.py → Runs on schedule or manual trigger

**On-demand** (triggered):
- crawler_service.py → Starts on API request, terminates after

---

## Environments

### Purpose: Isolated Execution Contexts

| Environment | Type | Purpose | Data Location | Port Range |
|-------------|------|---------|---------------|------------|
| **Development** | Local | Active development, debugging | `/tmp/dev_*` | 5000-5099 |
| **Test** | Isolated | Automated testing, CI/CD | `/tmp/test_*` | 5100-5199 |
| **Staging** | Pre-prod | Production simulation | `/tmp/staging_*` | 5200-5299 |
| **Production** | Live | Real users, real data | `/var/app/*` | 80, 443 |

### Data Isolation Rules

- **Development**: Shared data OK, no cleanup required
- **Test**: Isolated data per test run, automatic cleanup
- **Staging**: Production-like data (anonymized), manual cleanup
- **Production**: Real data, strict access control

---

## Tests

### Purpose: Validation and Quality Assurance

| Test Type | Scope | Technology | Target | Run By |
|-----------|-------|------------|--------|--------|
| **Unit Tests** | Function-level | pytest | Individual functions | Developer/CI |
| **Integration Tests** | Module-level | pytest | API endpoints, services | CI |
| **E2E Tests** | Full flow | Playwright | Complete user journeys | CI/manual |
| **UI Tests** | Interface | Playwright | Login, navigation, forms | Test Runner |
| **API Tests** | Backend | pytest/requests | REST endpoints | Test Runner |
| **Load Tests** | Performance | locust | System capacity | Manual |
| **Lifecycle Tests** | End-to-end | Custom framework | Full deployment cycle | LLM Orchestrator |

### Test Suite Classification

**For Coding Quality**:
- Unit tests → Verify logic correctness
- Integration tests → Verify module interaction
- API tests → Verify endpoint contracts

**For UI Quality**:
- E2E tests → Verify user flows work
- UI tests → Verify interface elements exist
- Visual regression → Verify UI appearance (planned)

**For Agent Coordination**:
- Lifecycle tests → Verify full workflow (generation → deploy → test → cleanup)
- Load tests → Verify system handles concurrent agents

---

## SOPs (Standard Operating Procedures)

### Purpose: Enforce Consistency and Quality

| SOP | Type | Enforced By | Checks |
|-----|------|-------------|--------|
| **Code Generation** | Development | LLM providers, reviewers | File structure, line limits, tests, docs |
| **Deployment** | Operations | CI/CD pipeline, manual gates | Health checks, smoke tests, rollback plan |
| **Testing** | Quality | Test frameworks, CI gates | Coverage thresholds, pass rates |
| **Code Review** | Quality | GitHub, manual review | Security, performance, maintainability |
| **Security** | Compliance | Automated scanners, manual review | Vulnerabilities, secrets, permissions |

### SOP Scoring System

**Code Generation SOP** (100 points):
- Required files present: 40 points
- Under line limit: 20 points
- Has automated tests: 10 points
- Has documentation: 10 points
- UI tests pass: 20 points
- **Passing threshold**: ≥80 points

**Deployment SOP** (checks):
- ✓ Health endpoint returns 200
- ✓ Database migrations applied
- ✓ Environment variables set
- ✓ Smoke tests pass
- ✓ Rollback plan documented

**Testing SOP** (requirements):
- ✓ ≥80% code coverage
- ✓ All critical paths tested
- ✓ Edge cases covered
- ✓ Performance benchmarks met

---

## Tools

### Purpose: Enable Specific Tasks

| Tool | Category | Purpose | Used By | Output |
|------|----------|---------|---------|--------|
| **tmux** | Session management | Multiplex terminal sessions | Assigner, Manual | Virtual terminals |
| **Playwright** | Browser automation | Control browser, test UI | Test Runner, Crawler | Screenshots, HTML |
| **pytest** | Testing framework | Run Python tests | CI, Manual | Test results |
| **git** | Version control | Track code changes | All agents, Manual | Commits, branches |
| **curl** | HTTP client | Make API requests | Scripts, Tests | HTTP responses |
| **sqlite3** | Database | Store structured data | App, Workers | Query results |
| **Flask** | Web framework | Serve dashboard and API | app.py | HTTP responses |

### Tool Classification

**For Coding**:
- git → Version control
- pytest → Test execution
- Flask → Web development

**For UI Testing**:
- Playwright → Browser automation
- curl → API testing
- Screenshot tools → Visual verification

**For Agent Management**:
- tmux → Session multiplexing
- sqlite3 → State persistence
- Flask → API communication

---

## Relationships and Workflows

### Code Generation Flow

```
User Request
    ↓
Assigner Worker → Finds idle tmux session
    ↓
tmux session (Claude/Codex) → Generates code
    ↓
Code saved to filesystem
    ↓
Task Worker → Runs tests
    ↓
Test Runner (Playwright) → Validates UI
    ↓
Results → Dashboard
```

### UI Testing Flow

```
Test Configuration (JSON)
    ↓
LLM Orchestrator → Loads test suite
    ↓
Test Runner → Executes steps
    ↓
Playwright → Controls browser
    ↓
Screenshots + Results → Database
    ↓
Dashboard API → Displays results
```

### Agent Coordination Flow

```
Comet (Orchestrator)
    ↓
Assigner Worker → Routes tasks
    ├─> Claude (architect) → Complex coding
    ├─> Codex (codex) → Quick code gen
    ├─> Claude-Architect → Architecture
    └─> Ollama → Local tasks

Results collected → Database
```

### Full Lifecycle Flow

```
1. Code Generation
   LLM (Claude/Codex) → Generates files

2. Deployment
   Task Worker → Deploys to test environment

3. UI Testing
   Test Runner + Playwright → Verifies interface

4. API Testing
   Test Runner + curl → Verifies endpoints

5. Data Verification
   Test Runner → Checks data isolation

6. Cleanup
   Task Worker → Removes deployment

7. Verification
   Test Runner → Confirms clean state
```

---

## Quick Reference

### When to Use Each LLM

| Task | Best LLM | Why |
|------|----------|-----|
| Complex refactoring | Claude | Deep reasoning |
| Quick code gen | Codex | Speed |
| Multi-file changes | Claude-Architect | Architecture view |
| Coordinating agents | Comet | Meta-programming |
| Document search | AnythingLLM | RAG capabilities |
| Offline work | Ollama | Local execution |

### When to Use Each Agent

| Need | Agent | Why |
|------|-------|-----|
| Route tasks to LLMs | Assigner Worker | Session management |
| Execute shell commands | Task Worker | Sandboxed execution |
| Run UI tests | Test Runner | Data-driven testing |
| Extract web data | Crawler Service | Browser automation |
| Monitor systems | Node Agent | Metrics collection |

### When to Use Each Environment

| Purpose | Environment | Why |
|---------|-------------|-----|
| Experimenting | Development | No cleanup needed |
| Running tests | Test | Isolated + auto-cleanup |
| Pre-launch validation | Staging | Production-like |
| Serving users | Production | Real data |

---

## Summary Matrix

| Component | For Coding | For UI Testing | For Agent Management |
|-----------|------------|----------------|---------------------|
| **Claude** | ✅ Primary | ⚠️ Generate tests | ⚠️ Plan workflows |
| **Codex** | ✅ Quick gen | ❌ | ❌ |
| **Comet** | ⚠️ Meta-code | ✅ Run tests | ✅ Coordinate |
| **Playwright** | ❌ | ✅ Primary | ❌ |
| **Task Worker** | ✅ Execute | ⚠️ Run tests | ⚠️ Background |
| **Assigner Worker** | ⚠️ Route | ⚠️ Route | ✅ Primary |
| **Test Runner** | ⚠️ Run tests | ✅ Primary | ⚠️ Validate |
| **tmux** | ✅ Interface | ❌ | ✅ Multiplex |

Legend:
- ✅ Primary use case
- ⚠️ Secondary use case
- ❌ Not applicable

---

**Status**: ✅ Complete
**Version**: 1.0.0
**Last Updated**: 2026-02-05
