# Development Team Setup with Go Wrapper

This document describes the automated development team setup using the Go Wrapper infrastructure.

## Team Structure

### Total: 10 Agents

#### Developers (3)
1. **dev-backend-1** (Codex)
   - Role: Backend Developer
   - Focus: API development

2. **dev-frontend-1** (Codex)
   - Role: Frontend Developer
   - Focus: UI/UX implementation

3. **dev-fullstack-1** (Gemini)
   - Role: Full Stack Developer
   - Focus: Feature development

#### QA Engineers (2)
1. **qa-tester-1** (Codex)
   - Role: QA Engineer
   - Focus: Test automation

2. **qa-tester-2** (Codex)
   - Role: QA Engineer
   - Focus: Manual testing

#### Managers (2)
1. **manager-product** (Claude)
   - Role: Product Manager
   - Focus: Requirements and planning

2. **manager-tech** (Claude)
   - Role: Technical Manager
   - Focus: Architecture decisions

#### Operations (2)
1. **architect** (Claude)
   - Role: Solutions Architect
   - Focus: System design

2. **devops** (Gemini)
   - Role: DevOps Engineer
   - Focus: CI/CD and infrastructure

## Prerequisites

### 1. Go Wrapper Binaries

The go_wrapper system must be built:

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper

# Build wrapper binary
go build -o wrapper main.go

# Build API server
go build -o apiserver cmd/apiserver/main.go
```

### 2. Gemini API Key (Required for Gemini agents)

Set the Gemini API key:

```bash
# Option 1: Export in current shell
export GEMINI_API_KEY='your-gemini-api-key-here'

# Option 2: Add to .env.local
echo "GEMINI_API_KEY=your-gemini-api-key-here" >> .env.local

# Option 3: Add to shell profile (~/.zshrc or ~/.bashrc)
echo 'export GEMINI_API_KEY="your-gemini-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### 3. tmux

All agents run in dedicated tmux sessions:

```bash
# Install tmux (if not already installed)
brew install tmux  # macOS
# or
apt-get install tmux  # Linux
```

## Quick Start

### 1. Run the Setup Script

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
python3 setup_dev_team.py
```

The script will:
1. Check for required binaries
2. Start the Go Wrapper API server (if not running)
3. Spawn all 10 team members in individual tmux sessions
4. Save team configuration to `team_config.json`
5. Display dashboard URLs

### 2. Expected Output

```
======================================================================
🏗️  DEVELOPMENT TEAM SETUP
======================================================================

📋 DEVELOPERS (3 members)
----------------------------------------------------------------------

👤 Spawning Backend Developer: dev-backend-1
   Tool: codex
   Focus: API development
   ✅ Agent spawned in tmux session: dev-backend-1

[... spawning continues for all agents ...]

======================================================================
✅ Team Setup Complete: 10/10 agents spawned
======================================================================

📊 TEAM ROSTER
======================================================================

DEVELOPERS:
  🟢 dev-backend-1         | Backend Developer          | codex
  🟢 dev-frontend-1        | Frontend Developer         | codex
  🟢 dev-fullstack-1       | Full Stack Developer       | gemini

QA:
  🟢 qa-tester-1           | QA Engineer                | codex
  🟢 qa-tester-2           | QA Engineer                | codex

MANAGERS:
  🟢 manager-product       | Product Manager            | claude
  🟢 manager-tech          | Technical Manager          | claude

OPERATIONS:
  🟢 architect             | Solutions Architect        | claude
  🟢 devops                | DevOps Engineer            | gemini

🖥️  TMUX SESSIONS
======================================================================
  dev-backend-1: 1 windows (created ...)
  dev-frontend-1: 1 windows (created ...)
  [... all sessions ...]

💾 Team configuration saved to team_config.json

🎯 DASHBOARDS
======================================================================
📊 Main Dashboard:      http://100.112.58.92:8151
🎮 Interactive Control: http://100.112.58.92:8151/interactive
📈 Performance:         http://100.112.58.92:8151/performance
🗄️  Database Queries:    http://100.112.58.92:8151/database
▶️  Session Replay:      http://100.112.58.92:8151/replay
🔍 Query Builder:       http://100.112.58.92:8151/query

======================================================================
🎉 Development Team is Ready!
======================================================================
```

## Managing the Team

### View All Agents

```bash
# List tmux sessions
tmux list-sessions

# Query via API
curl http://100.112.58.92:8151/api/agents | jq

# Open web dashboard
open http://100.112.58.92:8151
```

### Interact with Individual Agents

```bash
# Attach to agent's tmux session
tmux attach -t dev-backend-1

# Detach from session (while attached)
Press Ctrl+B, then D

# Send command to agent
curl -X POST http://100.112.58.92:8151/api/agents/dev-backend-1 \
  -H "Content-Type: application/json" \
  -d '{"command": "your command here"}'

# View agent logs
curl -N http://100.112.58.92:8151/api/agents/dev-backend-1/stream
```

### Monitor Team Activity

#### Web Dashboards

1. **Main Dashboard** (`http://100.112.58.92:8151`)
   - Overview of all agents
   - Real-time status
   - Log streaming

2. **Interactive Control** (`http://100.112.58.92:8151/interactive`)
   - Pause/resume agents
   - Send commands
   - View real-time logs

3. **Performance Dashboard** (`http://100.112.58.92:8151/performance`)
   - CPU/memory usage
   - Goroutine counts
   - GC metrics

4. **Database Dashboard** (`http://100.112.58.92:8151/database`)
   - Query agent activity
   - View extraction events
   - Export data

#### API Queries

```bash
# Get all agent statuses
curl http://100.112.58.92:8151/api/agents | jq '.[] | {name, status}'

# Get specific agent details
curl http://100.112.58.92:8151/api/agents/architect | jq

# Get agent metrics
curl http://100.112.58.92:8151/api/metrics | jq

# Get cluster health
curl http://100.112.58.92:8151/api/health | jq
```

### Stop Individual Agents

```bash
# Via API
curl -X DELETE http://100.112.58.92:8151/api/agents/dev-backend-1

# Via tmux
tmux kill-session -t dev-backend-1
```

### Stop All Agents

```bash
# Kill all tmux sessions
tmux kill-server

# Or stop via API (all agents)
for agent in dev-backend-1 dev-frontend-1 dev-fullstack-1 \
             qa-tester-1 qa-tester-2 \
             manager-product manager-tech \
             architect devops; do
  curl -X DELETE http://100.112.58.92:8151/api/agents/$agent
done
```

## Team Workflows

### Example: Assign Task to Developer

```bash
# Using tmux
tmux send-keys -t dev-backend-1 "Implement user authentication API" Enter

# Using API (if interactive control enabled)
curl -X POST http://100.112.58.92:8151/api/agents/dev-backend-1 \
  -H "Content-Type: application/json" \
  -d '{"command": "Implement user authentication API"}'
```

### Example: Code Review Flow

1. **Developer** (dev-backend-1) implements feature
2. **Manager** (manager-tech) reviews architecture
3. **QA** (qa-tester-1) creates test plan
4. **Architect** assigns code review to another dev

### Example: Deployment Flow

1. **Developer** completes feature
2. **QA** validates testing
3. **Manager** approves release
4. **DevOps** (devops) handles deployment
5. **Operations** (architect) monitors production

## Configuration

### Team Configuration File

The team structure is defined in `setup_dev_team.py`:

```python
TEAM_CONFIG = {
    "developers": [
        {"name": "dev-backend-1", "tool": "codex", "role": "Backend Developer", ...},
        ...
    ],
    "qa": [...],
    "managers": [...],
    "operations": [...]
}
```

### Customization

#### Add More Developers

```python
"developers": [
    # Existing...
    {"name": "dev-mobile-1", "tool": "gemini", "role": "Mobile Developer", "focus": "iOS/Android"},
]
```

#### Change Tools

```python
# Use Claude for all developers
"developers": [
    {"name": "dev-backend-1", "tool": "claude", ...},
    ...
]
```

#### Add New Roles

```python
"security": [
    {"name": "security-analyst", "tool": "claude", "role": "Security Analyst", "focus": "Vulnerability assessment"},
]
```

## Monitoring & Logs

### Log Files

Agent logs are stored in:
```
/Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/logs/agents/<agent-name>/
```

### API Server Logs

```
/Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/logs/apiserver.log
```

### Database

Team activity is stored in:
```
/Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/data/dev_team.db
```

Query examples:

```bash
# Using API
curl "http://100.112.58.92:8151/api/query/sessions?limit=10" | jq

# Direct SQLite query
sqlite3 /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/data/dev_team.db \
  "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 10;"
```

## Troubleshooting

### API Server Not Starting

```bash
# Check if port 8151 is already in use
lsof -i :8151

# Kill existing process
kill -9 <PID>

# Restart server manually
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper
./apiserver --host 100.112.58.92 --port 8151 --db data/dev_team.db --cluster dev-team-node
```

### Agent Not Spawning

```bash
# Check tmux sessions
tmux list-sessions

# Check if wrapper binary exists
ls -la /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/wrapper

# Check logs
tail -f /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/logs/agents/<agent-name>/*.log
```

### Gemini API Key Not Working

```bash
# Verify key is set
echo $GEMINI_API_KEY

# Test Gemini CLI
gemini "hello" --model gemini-2.0-flash-exp

# Check if key is valid (should not show error about missing key)
```

### Agent Not Responding

```bash
# Check agent status via API
curl http://100.112.58.92:8151/api/agents/<agent-name> | jq

# Check tmux session
tmux attach -t <agent-name>

# Restart agent
tmux kill-session -t <agent-name>
python3 setup_dev_team.py  # Will respawn missing agents
```

## Integration with Auto-Confirm

The auto-confirm worker will automatically confirm prompts for all team agents:

```bash
# Auto-confirm should be monitoring all tmux sessions including team agents
tail -f /tmp/autoconfirm_restart.log
```

If auto-confirm is not working for team agents, restart it:

```bash
pkill -f auto_confirm_worker_v2
nohup python3 workers/auto_confirm_worker_v2.py > /tmp/autoconfirm.log 2>&1 &
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Go Wrapper API Server                      │
│                    (Port 8151)                               │
│  ┌────────────────────────────────────────────────────┐    │
│  │  REST API │ WebSocket │ SSE │ Database │ Cluster  │    │
│  └────────────────────────────────────────────────────┘    │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┬───────────┬────────────┐
        │           │           │           │            │
┌───────▼──┐  ┌─────▼────┐  ┌──▼─────┐  ┌─▼──────┐  ┌──▼──────┐
│   Dev    │  │    QA    │  │Manager │  │Architect│  │ DevOps  │
│ Backend  │  │ Tester 1 │  │Product │  │         │  │         │
│  (Codex) │  │ (Codex)  │  │(Claude)│  │(Claude) │  │(Gemini) │
└──────────┘  └──────────┘  └────────┘  └─────────┘  └─────────┘

┌──────────┐  ┌──────────┐  ┌────────┐
│   Dev    │  │    QA    │  │Manager │
│Frontend  │  │ Tester 2 │  │  Tech  │
│ (Codex)  │  │ (Codex)  │  │(Claude)│
└──────────┘  └──────────┘  └────────┘

┌──────────┐
│   Dev    │
│FullStack │
│ (Gemini) │
└──────────┘
```

## Best Practices

1. **Regular Monitoring**: Check dashboard frequently for agent health
2. **Log Review**: Review agent logs daily for errors or issues
3. **Load Balancing**: Distribute tasks evenly across developers
4. **Clear Communication**: Use descriptive task assignments
5. **Documentation**: Keep track of agent assignments in team_config.json
6. **Backup**: Regularly backup the database (data/dev_team.db)
7. **Resource Management**: Monitor system resources with performance dashboard

## Next Steps

After team is running:
1. Integrate with task management system (TASKS.md)
2. Set up automated task routing
3. Configure notification webhooks
4. Implement team metrics and reporting
5. Create automated workflows for common operations

## Support

- **Go Wrapper Docs**: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper/README.md`
- **API Reference**: Go Wrapper API documentation
- **Dashboard Help**: Available at each dashboard URL
- **Logs**: Check agent and API server logs for debugging

---

**Created**: 2026-02-10
**Version**: 1.0.0
**Maintainer**: Development Team
