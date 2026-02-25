# wrapper-cli Quick Reference

## Installation
```bash
go build -o wrapper-cli cmd/cli/main.go
# Or use install script
./scripts/install-cli.sh
```

## Common Commands

### Agents
```bash
wrapper-cli agents list                              # List all agents
wrapper-cli agents start --name w1 --command codex   # Start agent
wrapper-cli agents status w1                         # Get agent status
wrapper-cli agents pause w1                          # Pause agent
wrapper-cli agents resume w1                         # Resume agent
wrapper-cli agents stop w1                           # Stop agent
wrapper-cli agents kill w1                           # Force kill agent
```

### Logs
```bash
wrapper-cli logs tail w1                    # Tail live logs (SSE)
wrapper-cli logs view w1 --lines 100        # View last 100 lines
wrapper-cli logs search w1 "ERROR"          # Search for pattern
wrapper-cli logs list w1                    # List log files
```

### Monitoring
```bash
wrapper-cli health                          # Server health
wrapper-cli metrics                         # All agent metrics
wrapper-cli metrics --format json           # JSON format
```

### Output Formats
```bash
--format table      # Human-readable (default)
--format json       # Machine-readable
--format csv        # Spreadsheet-friendly
```

### Global Options
```bash
--host localhost    # API server host
--port 8151         # API server port
--no-color          # Disable colors
```

## Examples

### Monitor agents every 30s
```bash
watch -n 30 wrapper-cli agents list
```

### Export metrics
```bash
wrapper-cli metrics --format csv > metrics.csv
```

### Remote server
```bash
wrapper-cli --host 192.168.1.10 agents list
```

### Scripting
```bash
# Get agent count
wrapper-cli agents list --format json | jq '.count'

# Check if agent is running
if wrapper-cli agents status worker-1 &>/dev/null; then
    echo "Agent is running"
fi
```

## Tips

### Shell Aliases
```bash
alias wl='wrapper-cli agents list'
alias wt='wrapper-cli logs tail'
alias wh='wrapper-cli health'
```

### Environment Variables
```bash
export WRAPPER_HOST=localhost
export WRAPPER_PORT=8151
```

### Quick Status Check
```bash
wrapper-cli health && wrapper-cli agents list
```

## Troubleshooting

### Connection Refused
```bash
# Check if server is running
curl http://localhost:8151/api/health
```

### Command Not Found
```bash
# Use full path
./wrapper-cli agents list

# Or add to PATH
export PATH=$PATH:$(pwd)
```

## Help

```bash
wrapper-cli help                # Main help
wrapper-cli agents help         # Command-specific help
wrapper-cli version             # Show version
```
