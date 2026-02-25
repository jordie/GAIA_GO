# Go Wrapper Usage Guide

## Overview

The Go Wrapper (`main.go`) wraps command execution with logging, monitoring, and project management capabilities. It's designed to run from any directory and automatically manage project context.

## Key Features

1. **Current Directory Based** - Uses the directory where it's run, not the binary location
2. **Project Management** - Automatically detects or prompts for project selection
3. **Organized Logs** - Saves logs in `./logs/agents/<project>/` by default
4. **Signal Handling** - Graceful shutdown on SIGINT/SIGTERM

## Usage

### Basic Usage

```bash
# Run with defaults (will prompt for project if not set)
./wrapper <agent-name>

# Specify command and args
./wrapper <agent-name> <command> [args...]
```

### Examples

```bash
# Run codex agent (default command)
./wrapper codex-1

# Run with custom command
./wrapper test-agent yes hello

# Run from any directory
cd /path/to/my/project
/path/to/wrapper my-agent
# Logs will be saved in /path/to/my/project/logs/agents/<project>/
```

## Project Selection

The wrapper determines the project name using this priority:

1. **Environment Variable** - `PROJECT_NAME=myproject ./wrapper agent-1`
2. **.project File** - Checks for `.project` file in current directory
3. **Interactive Prompt** - Asks user to enter project name (saves to `.project` for future runs)

### Setting Project Name

**Option 1: Create .project file**
```bash
echo "architect" > .project
./wrapper my-agent
```

**Option 2: Use environment variable**
```bash
export PROJECT_NAME=architect
./wrapper my-agent
```

**Option 3: Enter when prompted**
```bash
./wrapper my-agent
# Will prompt: "Enter project name: "
# Automatically saves to .project file
```

## Logs Directory

Logs are saved in a structured hierarchy:

```
./logs/
└── agents/
    └── <project-name>/
        ├── <agent-name>_stdout_<timestamp>.log
        └── <agent-name>_stderr_<timestamp>.log
```

### Custom Logs Directory

Override with `WRAPPER_LOGS_DIR` environment variable:

```bash
WRAPPER_LOGS_DIR=/custom/path ./wrapper agent-1
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECT_NAME` | Set project name | (prompt or .project file) |
| `WRAPPER_LOGS_DIR` | Override logs directory | `./logs/agents/<project>` |

## Working Directory

The wrapper uses the **current working directory** (where you run it from), not the directory containing the wrapper binary. This allows you to:

- Run from project directories
- Keep logs organized per project
- Use relative paths in wrapped commands

### Example Workflow

```bash
# Terminal 1: Work in Project A
cd ~/projects/projectA
echo "projectA" > .project
/opt/go_wrapper/wrapper agent-1
# Logs: ~/projects/projectA/logs/agents/projectA/

# Terminal 2: Work in Project B
cd ~/projects/projectB
echo "projectB" > .project
/opt/go_wrapper/wrapper agent-2
# Logs: ~/projects/projectB/logs/agents/projectB/
```

## Output

When the wrapper starts, it displays:

```
[Wrapper] Project: architect
[Wrapper] Agent: codex-1
[Wrapper] Command: codex []
[Wrapper] Working directory: /Users/jgirmay/Desktop/gitrepo/pyWork/architect
[Wrapper] Logs directory: /Users/jgirmay/Desktop/gitrepo/pyWork/architect/logs/agents/architect
```

When it completes:

```
[Wrapper] Process exited with code: 0
[Wrapper] Logs saved:
  stdout: /path/to/logs/codex-1_stdout_20260209_203000.log
  stderr: /path/to/logs/codex-1_stderr_20260209_203000.log
```

## Signal Handling

The wrapper handles interrupt signals gracefully:

```bash
# Press Ctrl+C
^C
[Wrapper] Received signal: interrupt
# Graceful shutdown, exit code 130
```

## Integration with Architect Dashboard

The wrapper integrates with the Architect Dashboard's agent management:

1. **Agent Registration** - Agents can register with the dashboard
2. **Log Collection** - Logs are collected and indexed
3. **Task Assignment** - Agents receive tasks from the assigner
4. **Training Data** - Execution patterns collected for ML

## Troubleshooting

### "Could not get working directory"

**Cause:** Process doesn't have permission to read current directory

**Fix:**
```bash
cd /path/to/accessible/directory
./wrapper agent-1
```

### "Could not create logs directory"

**Cause:** No write permission in current directory

**Fix:**
```bash
# Use custom logs directory
WRAPPER_LOGS_DIR=/tmp/logs ./wrapper agent-1

# Or run from directory with write permission
cd ~/writable/path
./wrapper agent-1
```

### "Project name cannot be empty"

**Cause:** Entered empty project name at prompt

**Fix:** Enter a valid project name or set via environment variable

## Advanced Usage

### Multiple Agents Per Project

```bash
cd ~/myproject
echo "myproject" > .project

# Run multiple agents
./wrapper agent-1 codex &
./wrapper agent-2 gemini &
./wrapper agent-3 claude &

# All logs go to: ~/myproject/logs/agents/myproject/
```

### CI/CD Integration

```bash
#!/bin/bash
# deploy.sh

cd /app/production
export PROJECT_NAME=production
export WRAPPER_LOGS_DIR=/var/log/agents

/opt/wrapper/main deploy-agent deployment-script
```

### Development vs Production

```bash
# Development
cd ~/dev/myapp
echo "myapp-dev" > .project
./wrapper dev-agent

# Production
cd /opt/myapp
echo "myapp-prod" > .project
./wrapper prod-agent
```

## Comparison: Before vs After

### Before (Binary Directory Based)

```bash
cd /home/user/projectA
/opt/wrapper/main agent-1
# Logs: /opt/wrapper/logs/agents/  (wrong location!)
```

### After (Working Directory Based)

```bash
cd /home/user/projectA
/opt/wrapper/main agent-1
# Logs: /home/user/projectA/logs/agents/projectA/  (correct!)
```

## See Also

- `go_wrapper/cmd/manager/main.go` - Manager for multi-agent coordination
- `CLAUDE.md` - Architect Dashboard project instructions
- `docs/MIGRATION_SYSTEM.md` - Database migration documentation
