# wrapper-cli - Command-Line Interface

**Powerful CLI for managing Go Agent Wrapper from the terminal**

## Installation

### Build from Source

```bash
# Build the CLI
go build -o wrapper-cli cmd/cli/main.go

# Install to ~/bin (optional)
cp wrapper-cli ~/bin/
chmod +x ~/bin/wrapper-cli

# Or install system-wide
sudo cp wrapper-cli /usr/local/bin/
```

### Quick Install Script

```bash
# Install latest version
./scripts/install-cli.sh

# Verify installation
wrapper-cli version
```

---

## Quick Start

```bash
# Check server health
wrapper-cli health

# List all running agents
wrapper-cli agents list

# Start a new agent
wrapper-cli agents start --name worker-1 --command codex

# Tail agent logs
wrapper-cli logs tail worker-1

# Get metrics
wrapper-cli metrics

# Stop agent
wrapper-cli agents stop worker-1
```

---

## Global Options

All commands support these global options:

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | localhost | API server host |
| `--port` | 8151 | API server port |
| `--format` | table | Output format (table, json, csv) |
| `--no-color` | false | Disable colored output |

---

## Commands

### agents - Manage Agents

Manage agent lifecycle (start, stop, pause, resume, kill).

#### list / ls - List All Agents

```bash
# List all agents (table format)
wrapper-cli agents list

# JSON format
wrapper-cli agents list --format json

# CSV format
wrapper-cli agents list --format csv
```

**Output:**
```
NAME       COMMAND  PID     STATUS   STARTED               ENV
worker-1   codex    12345   running  2026-02-10 09:30:00   production
worker-2   comet    12346   running  2026-02-10 09:31:00   development

Total: 2 agent(s)
```

#### start - Start New Agent

```bash
# Basic start
wrapper-cli agents start --name worker-1 --command codex

# With environment
wrapper-cli agents start --name prod-agent --command codex --env production

# With arguments
wrapper-cli agents start --name test-agent --command bash --args "-c 'echo hello'"
```

**Flags:**
- `--name` (required) - Agent name
- `--command` (required) - Command to execute
- `--args` - Command arguments
- `--env` - Environment name

#### stop - Stop Agent Gracefully

```bash
# Stop agent with SIGTERM
wrapper-cli agents stop worker-1
```

#### kill - Force Kill Agent

```bash
# Force kill with SIGKILL
wrapper-cli agents kill worker-1
```

#### status / info - Get Agent Details

```bash
# Get agent status
wrapper-cli agents status worker-1

# JSON format
wrapper-cli agents status worker-1 --format json
```

**Output:**
```
Agent Information
=================
Name:    worker-1
Command: codex
PID:     12345
Status:  running
Started: 2026-02-10 09:30:00
```

#### pause - Pause Agent Execution

```bash
# Send SIGSTOP to pause agent
wrapper-cli agents pause worker-1
```

#### resume - Resume Agent Execution

```bash
# Send SIGCONT to resume agent
wrapper-cli agents resume worker-1
```

---

### logs - View and Search Logs

View, tail, and search agent logs.

#### tail / follow - Stream Live Logs

```bash
# Tail agent logs (SSE stream)
wrapper-cli logs tail worker-1

# With options
wrapper-cli logs tail worker-1 --lines 100 --stream stdout
```

**Flags:**
- `--lines` - Number of lines to show (default: 50)
- `--stream` - Stream type: stdout, stderr, both (default: both)

#### view / cat - View Recent Logs

```bash
# View last 100 lines
wrapper-cli logs view worker-1 --lines 100

# View only stderr
wrapper-cli logs view worker-1 --stream stderr
```

#### search / grep - Search Logs

```bash
# Search for pattern
wrapper-cli logs search worker-1 "ERROR"

# Case-insensitive search
wrapper-cli logs search worker-1 "error" -i

# Count matches
wrapper-cli logs search worker-1 "warning" --count
```

**Flags:**
- `-i` - Case-insensitive search
- `--count` - Show only match count
- `--stream` - Stream to search: stdout, stderr, both

#### list - List Log Files

```bash
# List all log files for agent
wrapper-cli logs list worker-1
```

**Output:**
```
FILE                           SIZE     MODIFIED
2026-02-10-09-30-00-stdout.log 1.2 MB   2026-02-10 10:45:00
2026-02-10-09-30-00-stderr.log 45.3 KB  2026-02-10 10:45:00

Total: 2 log file(s)
```

---

### metrics - View Metrics

View agent metrics and statistics.

#### get / show - Get Current Metrics

```bash
# Get all agent metrics
wrapper-cli metrics

# Specific agent
wrapper-cli metrics get worker-1

# JSON format
wrapper-cli metrics --format json
```

**Output:**
```
AGENT      LINES   EVENTS  UPTIME   STATUS
worker-1   12450   345     2h5m30s  running
worker-2   8920    198     1h45m0s  running
```

#### export - Export Metrics

```bash
# Export in Prometheus format
wrapper-cli metrics export --format prometheus

# Export in InfluxDB line protocol
wrapper-cli metrics export --format influxdb
```

---

### health - Check Server Health

```bash
# Get server health status
wrapper-cli health

# JSON format
wrapper-cli health --format json
```

**Output:**
```
Server Health Status
====================
Status:        healthy
Uptime:        5h30m15s
Active Agents: 3
Version:       1.0.0
```

---

### query - Query Database (Coming Soon)

```bash
# Query extraction events
wrapper-cli query extractions --agent worker-1 --type error

# Get statistics
wrapper-cli query stats --agent worker-1

# Export results
wrapper-cli query extractions --agent worker-1 --format csv > data.csv
```

---

### sessions - Manage Sessions (Coming Soon)

```bash
# List all sessions
wrapper-cli sessions list

# Show session details
wrapper-cli sessions show sess_abc123

# View session history
wrapper-cli sessions history worker-1
```

---

### replay - Session Replay (Coming Soon)

```bash
# List available sessions
wrapper-cli replay list

# Start session replay
wrapper-cli replay start sess_abc123 --speed 2.0

# Export to HAR
wrapper-cli replay export sess_abc123 --format har
```

---

### cluster - Cluster Management (Coming Soon)

```bash
# List cluster nodes
wrapper-cli cluster nodes

# Get cluster status
wrapper-cli cluster status

# Change load balancing strategy
wrapper-cli cluster balance --strategy least_loaded
```

---

### profile - Performance Profiling (Coming Soon)

```bash
# Show memory usage
wrapper-cli profile memory

# Download CPU profile
wrapper-cli profile cpu --duration 30 > cpu.prof

# Show goroutine stats
wrapper-cli profile goroutines

# Show GC statistics
wrapper-cli profile gc
```

---

## Output Formats

The CLI supports multiple output formats:

### Table (Default)

Human-readable tabular output with colors.

```bash
wrapper-cli agents list
```

### JSON

Machine-readable JSON output for scripting.

```bash
wrapper-cli agents list --format json | jq '.agents[0].name'
```

### CSV

Comma-separated values for spreadsheet import.

```bash
wrapper-cli agents list --format csv > agents.csv
```

---

## Colors and Formatting

The CLI uses colors to enhance readability:

- **Green** ✓ - Success, running status
- **Red** ✗ - Error, failed status
- **Yellow** ⚠ - Warning, degraded status
- **Blue** ℹ - Information
- **Cyan** - Headers, labels
- **Bold** - Important fields

Disable colors with `--no-color`:

```bash
wrapper-cli agents list --no-color
```

---

## Remote Server

Connect to a remote API server:

```bash
# Connect to remote host
wrapper-cli --host 192.168.1.10 --port 8151 agents list

# Set environment variables
export WRAPPER_HOST=192.168.1.10
export WRAPPER_PORT=8151
wrapper-cli agents list
```

---

## Scripting Examples

### Bash Script - Monitor Agent Status

```bash
#!/bin/bash
# monitor.sh - Monitor agent status every 30 seconds

while true; do
    clear
    echo "=== Agent Status @ $(date) ==="
    wrapper-cli agents list
    sleep 30
done
```

### Python Script - Parse JSON Output

```python
import json
import subprocess

# Get agents as JSON
result = subprocess.run(
    ['wrapper-cli', 'agents', 'list', '--format', 'json'],
    capture_output=True, text=True
)

data = json.loads(result.stdout)
for agent in data['agents']:
    if agent['status'] != 'running':
        print(f"Alert: Agent {agent['name']} is {agent['status']}")
```

### Shell Alias - Quick Commands

```bash
# Add to ~/.bashrc or ~/.zshrc
alias wl='wrapper-cli agents list'
alias wt='wrapper-cli logs tail'
alias wh='wrapper-cli health'
alias ws='wrapper-cli agents status'
```

---

## Error Handling

The CLI provides clear error messages:

```bash
$ wrapper-cli agents stop nonexistent
Error: API error (status 404): agent not found

$ wrapper-cli agents start --name test
Error: command is required (--command)

$ wrapper-cli --host invalid-host agents list
Error: GET request failed: dial tcp: lookup invalid-host: no such host
```

Exit codes:
- `0` - Success
- `1` - Error (with message to stderr)

---

## Performance

The CLI is optimized for speed:

- **Fast startup**: < 10ms
- **Low memory**: ~5MB
- **Efficient streaming**: No buffering for logs
- **Concurrent requests**: Parallel API calls when possible

---

## Completion (Future)

Bash/Zsh completion support planned:

```bash
# Will be available in future version
wrapper-cli completion bash > /etc/bash_completion.d/wrapper-cli
wrapper-cli completion zsh > /usr/local/share/zsh/site-functions/_wrapper-cli
```

---

## Troubleshooting

### Cannot connect to server

```bash
# Check if server is running
curl http://localhost:8151/api/health

# Check host and port
wrapper-cli --host localhost --port 8151 health
```

### Permission denied

```bash
# Make CLI executable
chmod +x wrapper-cli

# Or use go run
go run cmd/cli/main.go agents list
```

### Command not found

```bash
# Add to PATH
export PATH=$PATH:$(pwd)

# Or use full path
./wrapper-cli agents list
```

---

## Contributing

The CLI is designed to be extensible:

1. Add new command in `cmd/cli/commands/`
2. Register in `cmd/cli/main.go`
3. Add tests in `cmd/cli/commands/*_test.go`
4. Update documentation

See [DEVELOPMENT.md](./DEVELOPMENT.md) for details.

---

## Roadmap

- [x] Agent management commands
- [x] Log viewing and searching
- [x] Metrics and health checks
- [ ] Database query commands
- [ ] Session replay commands
- [ ] Cluster management commands
- [ ] Performance profiling commands
- [ ] Bash/Zsh completion
- [ ] Interactive mode
- [ ] Configuration file support

---

**Built with ❤️ for the Claude agent ecosystem**
