# Claw Browser Automation Agent

The Claw agent is a specialized browser automation agent running on the pink laptop using OpenClaw.

## Overview

**Agent Name**: `claw`
**Tool**: OpenClaw (Browser Automation)
**Node**: Pink Laptop (192.168.1.172)
**Role**: Browser Automation Agent
**Focus**: Web scraping, browser automation, data extraction

## Architecture

```
┌─────────────────────────────────────────────────┐
│ Main System (100.112.58.92)                    │
│                                                 │
│  agent_task_router.py                          │
│  distributed_task_router.py                    │
│  └─> Routes browser automation tasks to claw   │
│                                                 │
└────────────────┬────────────────────────────────┘
                 │ SSH + tmux
                 ▼
┌─────────────────────────────────────────────────┐
│ Pink Laptop (192.168.1.172)                    │
│                                                 │
│  tmux session: "claw"                          │
│  └─> OpenClaw CLI running                      │
│                                                 │
│  Auto-Confirm Worker                           │
│  └─> Pattern-based confirmation                │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Capabilities

The Claw agent can handle:
- **Web Scraping**: Extract data from websites
- **Browser Automation**: Automate repetitive browser tasks
- **Form Filling**: Fill out web forms automatically
- **Screenshot Capture**: Take screenshots of pages
- **Data Extraction**: Parse and extract structured data
- **Navigation**: Navigate complex web applications
- **Element Interaction**: Click, type, hover, scroll

## Setup on Pink Laptop

### 1. Install OpenClaw

```bash
# Via pip
pip install openclaw

# Or from source
git clone https://github.com/openclaw/openclaw
cd openclaw
pip install -e .
```

### 2. Start the Claw Agent

From the pink laptop:
```bash
cd /path/to/architect
./start_claw_agent.sh
```

Or use the standard agent start script:
```bash
./start_agent.sh claw openclaw
```

### 3. Verify Agent is Running

```bash
# Check tmux session
tmux list-sessions | grep claw

# Check session state
python3 workers/session_state_manager.py list

# Attach to see what's happening
tmux attach -t claw
```

## Routing Tasks to Claw

### From Main System

```bash
# Route a browser automation task
python3 agent_task_router.py assign \
  "Scrape product prices from example.com" \
  /tmp/scraping_work \
  claw

# Route via distributed router (automatically detects remote agent)
python3 distributed_task_router.py assign \
  "Fill out the contact form on example.com" \
  /tmp/forms_work \
  --agent claw
```

### Task Examples

```bash
# Web scraping
python3 agent_task_router.py assign \
  "Scrape all blog post titles from techblog.com and save to titles.json" \
  /tmp/scraping \
  claw

# Screenshot capture
python3 agent_task_router.py assign \
  "Take screenshots of the homepage at mobile, tablet, and desktop widths" \
  /tmp/screenshots \
  claw

# Form automation
python3 agent_task_router.py assign \
  "Fill out the feedback form with test data and submit" \
  /tmp/testing \
  claw

# Data extraction
python3 agent_task_router.py assign \
  "Extract all pricing table data from pricing page and save as CSV" \
  /tmp/data \
  claw
```

## Auto-Confirmation

The Claw agent uses pattern-based auto-confirmation. The following patterns are pre-configured:

| Pattern | Description | Action |
|---------|-------------|--------|
| `openclaw_browser_launch` | Browser launch permission | Auto-allow |
| `openclaw_navigation` | Page navigation permission | Auto-allow |
| `openclaw_click` | Element click permission | Auto-allow |
| `openclaw_screenshot` | Screenshot permission | Auto-allow |

### View Patterns

```bash
python3 workers/pattern_tracker.py stats
```

### Add Custom Patterns

```python
from pattern_tracker import PatternTracker

tracker = PatternTracker()
tracker.add_pattern(
    pattern_type='permission',
    pattern_name='openclaw_custom_action',
    pattern_regex=r'Your custom pattern regex',
    tool_name='openclaw',
    description='Description of the pattern',
    action='send_key:1',
    confidence_threshold=0.9
)
```

## Session State Tracking

The Claw agent's state is tracked in real-time:

```bash
# View all agent states including Claw
python3 workers/session_state_manager.py list

# API endpoint
curl http://localhost:5555/api/sessions/claw
```

State includes:
- Current task description
- Working directory
- Status (idle, working, error)
- Last activity timestamp
- Prompts handled count

## Monitoring

### Real-Time Dashboard

Access the session state API:
```bash
# Start API server
python3 api/session_state_api.py --port 5555

# View all sessions
curl http://localhost:5555/api/sessions

# View only Claw
curl http://localhost:5555/api/sessions/claw

# SSE stream for real-time updates
curl -N http://localhost:5555/api/sessions/stream
```

### Pattern Tracking Stats

```bash
# View pattern statistics
python3 workers/pattern_tracker.py stats

# Export pattern data
python3 workers/pattern_tracker.py export patterns.json
```

## Troubleshooting

### Agent Not Starting

```bash
# Check if OpenClaw is installed
which openclaw
which claw

# Install if missing
pip install openclaw

# Check tmux session
tmux has-session -t claw && echo "Running" || echo "Not running"
```

### Tasks Not Being Received

```bash
# Check agent is in team config
python3 -c "import json; print([a['name'] for a in json.load(open('team_config.json'))['agents']])"

# Check node connectivity
ping -c 1 192.168.1.172

# Check SSH access
ssh user@192.168.1.172 'tmux list-sessions'
```

### Auto-Confirm Not Working

```bash
# Check auto-confirm worker is running
ps aux | grep auto_confirm_worker

# Check pattern detection
python3 workers/pattern_integration.py

# View recent pattern occurrences
python3 workers/pattern_tracker.py stats
```

## Integration with Other Systems

### With Architecture Dashboard

The Claw agent appears in:
- Architecture Dashboard > Agents panel
- Session state display
- Pattern tracking statistics

### With Task Router

```python
from agent_task_router import AgentTaskRouter

router = AgentTaskRouter()
router.assign_task(
    task_description="Scrape data from website",
    work_directory="/tmp/work",
    agent_name="claw",
    priority="high"
)
```

### With Distributed Router

```python
from distributed_task_router import DistributedTaskRouter

router = DistributedTaskRouter()
router.assign_task_to_node(
    task_description="Browser automation task",
    work_directory="/tmp/work",
    node_id="pink-laptop",
    agent_name="claw"
)
```

## Best Practices

1. **Use Specific Task Descriptions**: Be clear about what should be scraped/automated
2. **Specify Output Format**: Tell Claw how to save results (JSON, CSV, etc.)
3. **Include URLs**: Provide exact URLs for navigation
4. **Set Timeouts**: For long-running scraping, specify timeout expectations
5. **Handle Errors**: Tasks may fail if sites change - include retry logic
6. **Respect robots.txt**: Only scrape sites that allow it
7. **Rate Limiting**: Don't overwhelm target sites

## Configuration

### Team Config

The Claw agent is configured in `team_config.json`:

```json
{
  "name": "claw",
  "tool": "openclaw",
  "role": "Browser Automation Agent",
  "focus": "Web scraping and browser automation",
  "node": "pink-laptop",
  "node_ip": "192.168.1.172",
  "status": "running"
}
```

### Environment Variables

```bash
# Optional: Configure OpenClaw
export OPENCLAW_HEADLESS=true
export OPENCLAW_BROWSER=chromium
export OPENCLAW_TIMEOUT=30000
```

## Security Considerations

- Claw runs on remote pink laptop - ensure SSH keys are set up
- Browser automation can access sensitive data - use with care
- Scraping tasks should respect site terms of service
- Auto-confirm is enabled - monitor for unexpected behavior
- Session state is stored in `/tmp` - clean up regularly

## Future Enhancements

- [ ] Proxy support for scraping
- [ ] Parallel browser sessions
- [ ] Screenshot comparison/diffing
- [ ] Cookie management for authenticated scraping
- [ ] Headless vs headed mode toggle
- [ ] Browser extension loading
- [ ] Custom user agent rotation
- [ ] CAPTCHA handling integration

## Related Documentation

- [Pattern Tracking System](PATTERN_TRACKING.md)
- [Session State Management](../workers/session_state_manager.py)
- [Agent Task Router](../agent_task_router.py)
- [Distributed Task Router](../distributed_task_router.py)
