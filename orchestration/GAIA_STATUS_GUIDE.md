# GAIA Status Command Guide

## Overview

The GAIA Status command provides comprehensive visibility into all tmux sessions in the GAIA distributed system, displaying:

- **Session names** organized by type (architect, manager, developer)
- **Working directories** for each session
- **Git branches** currently checked out
- **Agent providers** (claude, codex, ollama, comet, etc.)
- **Work duration** (how long session has been on current task)
- **Pane counts** (number of windows in each session)

## Setup

### 1. Automatic Setup (Recommended)

```bash
cd /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration
bash setup_gaia_command.sh
```

This adds the `gaia_status` and `GAIA` aliases to your shell configuration.

### 2. Manual Setup

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias gaia_status='python3 /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration/gaia_status.py'
alias GAIA='python3 /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration/gaia_status.py'
```

Then reload your shell:

```bash
source ~/.bashrc    # or source ~/.zshrc
```

## Usage

### Full Status Tree

Shows complete details for all sessions including working directory, git branch, and work duration:

```bash
gaia_status
```

Output structure:
```
🏛️  ARCHITECT TIER (N sessions)
├─ 🤖 session_name (provider)
│  ├─ Duration: Xh Ym
│  ├─ Branch: branch-name
│  ├─ Work Dir: /path/to/directory
│  └─ Panes: N

🏛️  MANAGER TIER (N sessions)
...

🏛️  DEVELOPER TIER (N sessions)
...
```

### Brief View (Condensed)

Shows only session names and providers, no details:

```bash
gaia_status --brief
```

### Watch Mode (Real-time Updates)

Continuously updates session status every 5 seconds:

```bash
gaia_status --watch

# Custom refresh interval (every N seconds)
gaia_status --watch --interval 3
```

Press `Ctrl+C` to exit watch mode.

### JSON Output

Export all session data as JSON for programmatic use:

```bash
gaia_status --json
```

Output format:
```json
{
  "timestamp": "2026-02-21T12:34:56.123456",
  "total_sessions": 54,
  "sessions": [
    {
      "name": "arch_lead",
      "type": "architect",
      "provider": "claude",
      "cwd": "/path/to/work",
      "git_branch": "feature/xyz-0221",
      "git_repo": "/path/to/repo",
      "pane_count": 1,
      "work_duration": "2h 15m"
    },
    ...
  ]
}
```

## Session Types

Sessions are automatically classified into three tiers:

### 🏛️  Architect Tier

Strategic oversight and architectural guidance:
- `arch_lead` - System leadership
- `claude_architect` - Architecture decisions
- `inspector` - Code inspection
- `gaia_linter` - Code quality checks
- `pr_review1/2/3` - Pull request reviews
- `foundation`, `comparison` - Cross-cutting concerns
- Module-specific architects (e.g., `reading_architect`)

**Provider**: Primarily Claude or curator agents

### 🏛️  Manager Tier

Tactical execution and module management:
- `manager_*` - Module managers (reading, math, piano, typing, dashboard)
- `dev_*_1/2` - Module developers
- `tester_*` - Module testers
- Generic worker managers

**Provider**: Mix of claude, codex, and unknown providers

### 🏛️  Developer Tier

Execution and task implementation:
- `dev_worker_1-5` - Generic Claude workers
- `codex_worker_1-3` - Codex code generation workers
- `pr_impl_1-4` - PR implementation workers
- `pr_integ_1-3` - PR integration workers
- `ollama_worker` - Local LLM workers
- `comet_*` - Browser automation workers

**Provider**: claude, codex, ollama, comet

## Agent Providers

The status display identifies the LLM provider for each session:

| Provider | Emoji | Description |
|----------|-------|-------------|
| claude | 🤖 | Anthropic Claude API |
| codex | 💻 | OpenAI Codex |
| ollama | 🦙 | Local Ollama models |
| comet | 🌐 | Comet browser automation |
| curator | 🎨 | Specialized curator agents |
| unknown | ❓ | Provider not identified |

## Work Duration

Shows how long the session has been working on the current task:

- **0m** - Recently started or no task assigned
- **15m** - 15 minutes
- **2h 30m** - 2 hours 30 minutes
- **1d 3h** - 1 day 3 hours
- **—** - Unknown (no state tracked)

Work duration is tracked in:
```
/Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration/.session_state.json
```

You can manually update the `work_start` timestamp for a session to adjust tracking.

## Examples

### Check system health at a glance

```bash
gaia_status --brief
```

### Monitor active work in real-time

```bash
gaia_status --watch
```

In another terminal, you'll see updates every 5 seconds showing current session status.

### Export session data for analysis

```bash
gaia_status --json > sessions.json
jq '.sessions | map(select(.type == "architect"))' sessions.json
```

### Filter sessions by type (using jq)

```bash
# Show only architect tier sessions
gaia_status --json | jq '.sessions[] | select(.type == "architect")'

# Show sessions working for more than 1 hour
gaia_status --json | jq '.sessions[] | select(.work_duration | startswith("1d") or startswith("2") or startswith("3"))'

# Count sessions by provider
gaia_status --json | jq '[.sessions[] | .provider] | group_by(.) | map({(.[0]): length}) | add'
```

### Monitor a specific module

```bash
gaia_status --json | jq '.sessions[] | select(.name | startswith("dev_reading"))'
```

## Integration Points

### With Assigner Worker

The GAIA status command integrates with the task assignment system:

```python
# In assigner_worker.py
from orchestration.gaia_status import get_all_sessions

sessions = get_all_sessions()
for session in sessions:
    if session.status == "idle":
        # Assign task to this session
        assign_task(session.name)
```

### With Monitoring

Use watch mode to monitor system load:

```bash
# Monitor in one terminal
gaia_status --watch --interval 2

# In another terminal, send tasks
python3 workers/assigner_worker.py --send "Task description"
```

### With Automation

Schedule periodic status checks:

```bash
# Add to crontab to log status every hour
0 * * * * /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration/gaia_status.sh --json >> /tmp/gaia_status_log.json
```

## Troubleshooting

### Sessions not showing up

1. Verify tmux sessions exist:
   ```bash
   tmux list-sessions
   ```

2. Check if `gaia_status.py` has execute permissions:
   ```bash
   ls -l /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration/gaia_status.py
   # Should show 'x' in permissions (rwxr-xr-x)
   ```

3. Run with verbose output:
   ```bash
   python3 -u /Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration/gaia_status.py 2>&1
   ```

### Working directory shows garbled text

This happens when a tmux pane is showing output from a running command. The script attempts to extract the working directory but may capture partial output instead.

**Solution**: The git branch is more reliable. Use that to determine the actual working directory.

### Work duration shows "—" or "0m" for all sessions

Work duration tracking requires the `.session_state.json` file to be populated. This happens automatically but can be manual set:

```bash
# Force update state file
python3 gaia_status.py  # Saves state automatically
```

### Alias not working after setup

1. Verify setup completed:
   ```bash
   grep "gaia_status" ~/.bashrc  # or ~/.zshrc
   ```

2. Reload your shell:
   ```bash
   source ~/.bashrc  # or source ~/.zshrc
   ```

3. Test the alias:
   ```bash
   gaia_status --brief
   ```

## Architecture

### Data Flow

```
tmux sessions
     │
     ▼
gaia_status.py
     │
     ├─► tmux list-sessions (get session list)
     ├─► tmux capture-pane (get working directory)
     ├─► git rev-parse (get current branch)
     │
     ▼
SessionInfo objects
     │
     ├─► Classify type (architect/manager/developer)
     ├─► Infer provider (claude/codex/ollama/comet)
     ├─► Calculate work duration
     │
     ▼
Output format
     ├─► Tree (human-readable)
     ├─► Brief (condensed)
     ├─► JSON (programmatic)
     │
     └─► Display or export
```

### Session State File

Location: `/Users/jgirmay/Desktop/gitrepo/GAIA_HOME/orchestration/.session_state.json`

Structure:
```json
{
  "session_name": {
    "type": "architect|manager|developer",
    "provider": "claude|codex|ollama|comet|unknown",
    "work_start": "2026-02-21T12:00:00.000000",
    "last_updated": "2026-02-21T12:15:00.000000"
  }
}
```

## Performance

- **Full status**: ~2-3 seconds (queries all sessions and git)
- **Brief status**: ~1 second (no git queries)
- **Watch mode**: Updates every 5 seconds (configurable)
- **JSON export**: ~2-3 seconds

## Related Commands

```bash
# List tmux sessions directly
tmux list-sessions

# Show details for specific session
tmux list-panes -t session_name -F "#{pane_id} #{pane_current_path}"

# Send command to session
tmux send-keys -t session_name "command" Enter

# Monitor all sessions in real-time
watch -n 5 'gaia_status --brief'
```

## See Also

- [GAIA Lock System](GAIA_LOCK_SYSTEM.md)
- [GAIA Initialization](gaia_init.py)
- [Assigner Worker](../workers/assigner_worker.py)
