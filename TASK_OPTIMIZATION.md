# Task Optimization & Token Throttling Guide

## Overview

The Architect Dashboard now includes intelligent task delegation and token throttling to:
- **Prevent excessive token usage** and budget overruns
- **Route tasks to optimal agents** (Comet for UI, Codex for coding)
- **Automatically use cheaper models** for simple tasks
- **Throttle requests** when approaching limits

## Task Delegation Strategy

### Routing Rules

| Task Type | First Choice | Model | Cost | Use Case |
|-----------|-------------|-------|------|----------|
| **UI Tasks** | Comet | Haiku | Cheap | Frontend, styling, buttons, forms |
| **Coding** | Codex | Sonnet 4.5 | Premium | Functions, classes, refactoring |
| **Testing** | Codex | Sonnet 4.5 | Premium | Unit tests, integration tests |
| **Debugging** | Codex | Sonnet 4.5 | Premium | Bug fixes, error analysis |
| **Documentation** | Haiku | Haiku | Cheap | READMEs, comments, guides |
| **Research** | Haiku | Haiku | Cheap | Investigation, exploration |
| **Analysis** | Sonnet 4.5 | Sonnet 4.5 | Premium | Code review, performance |
| **Automation** | Codex | Sonnet 4.5 | Premium | Scripts, workflows |

### Automatic Task Detection

The system automatically detects task type from natural language:

```python
from services.task_delegator import get_delegator

delegator = get_delegator()

# Automatically routes to Comet (UI agent)
result = delegator.delegate_task("Fix the login button styling")
# -> agent: COMET, model: haiku, session: comet

# Automatically routes to Codex (code agent)
result = delegator.delegate_task("Implement user authentication function")
# -> agent: CODEX, model: sonnet-4-5, session: codex

# Automatically uses Haiku (cheap)
result = delegator.delegate_task("Write a README for this project")
# -> agent: CLAUDE_HAIKU, model: haiku, cost: 80% savings
```

### Detection Patterns

**UI Task Indicators:**
- Keywords: `ui`, `frontend`, `style`, `css`, `html`, `button`, `form`, `modal`
- Keywords: `click`, `hover`, `animation`, `element`, `component`
- Keywords: `browser`, `chrome`, `selenium`, `playwright`, `comet`

**Coding Task Indicators:**
- Keywords: `code`, `implement`, `function`, `class`, `method`, `refactor`
- Keywords: `python`, `javascript`, `typescript`, `algorithm`, `logic`

**Simple Task Indicators:**
- Keywords: `comment`, `rename`, `typo`, `log`, `simple`, `quick`
- Short descriptions (< 10 words)

## Token Throttling System

### Limits (Default)

**Per-Session Limits:**
- 100,000 tokens/hour
- 1,000,000 tokens/day

**Global Limits:**
- 500,000 tokens/hour (all sessions)
- 5,000,000 tokens/day (all sessions)

**Cost Limits:**
- $5/hour per session
- $50/day per session
- $1,000/month globally

### Throttle Levels

| Level | Threshold | Action | Description |
|-------|-----------|--------|-------------|
| **NONE** | < 70% | Allow all | Normal operation |
| **WARNING** | 70-80% | Warn | Log warning, allow |
| **SOFT** | 80-90% | Queue low priority | Delay non-urgent requests |
| **HARD** | 90-95% | Block normal | Only allow high/critical |
| **CRITICAL** | > 95% | Block all | Only critical requests |

### Usage

```python
from services.llm_provider import UnifiedLLMClient

client = UnifiedLLMClient()

# Request with throttling
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
    session_id="my_session",  # Track usage per session
    priority="normal"          # low, normal, high, critical
)

# Throttler automatically:
# 1. Checks if request is within limits
# 2. Records actual token usage after completion
# 3. Throttles or queues if limits approached
```

### Check Throttle Status

```python
from services.token_throttle import get_throttler

throttler = get_throttler()

# Check specific session
stats = throttler.get_stats("my_session")
print(f"Tokens used this hour: {stats['tokens_hour']}")
print(f"Current throttle level: {stats['throttle_level']}")

# Check all sessions
all_stats = throttler.get_stats()
print(f"Global tokens/day: {all_stats['global']['tokens_day']}")
```

### Priority Levels

Use priority to control throttling behavior:

```python
# Critical - always allowed (even at CRITICAL throttle)
response = client.messages.create(..., priority="critical")

# High - allowed up to HARD throttle
response = client.messages.create(..., priority="high")

# Normal - allowed up to SOFT throttle
response = client.messages.create(..., priority="normal")

# Low - queued at SOFT throttle, blocked at HARD
response = client.messages.create(..., priority="low")
```

## Cost Optimization Strategies

### Strategy 1: Use Delegation for Auto-Optimization

Let the delegator choose the cheapest model for each task:

```python
from services.task_delegator import get_delegator
from services.llm_provider import UnifiedLLMClient

delegator = get_delegator()
client = UnifiedLLMClient()

# Task is analyzed and routed to optimal agent/model
result = delegator.delegate_task("Fix the CSS styling")

# Use the recommended model
response = client.messages.create(
    model=result.model,  # Automatically chooses Haiku (cheap)
    ...
)
```

**Savings:** 80% for UI/docs tasks, 0% for coding tasks (quality matters)

### Strategy 2: Manual Model Selection

Explicitly choose cheaper models for background tasks:

```python
# Expensive (current session)
export CLAUDE_MODEL=claude-sonnet-4-5-20250929

# Cheap (other sessions) - 80% savings
export CLAUDE_MODEL=claude-3-5-haiku-20241022

# Free (development) - 100% savings
export LLM_DEFAULT_PROVIDER=ollama
```

### Strategy 3: Priority-Based Queueing

Use low priority for non-urgent tasks:

```python
# Urgent - use expensive model immediately
response = client.messages.create(..., priority="high")

# Non-urgent - queue and use cheaper model later
response = client.messages.create(..., priority="low")
```

## Session Setup Examples

### Premium Session (Current)
```bash
# This session - keep on Sonnet 4.5
tmux new-session -s premium
# No env vars needed - defaults to Sonnet 4.5
```

### Budget Session (Background Workers)
```bash
# Background tasks - use Haiku (80% savings)
tmux new-session -s background
export CLAUDE_MODEL=claude-3-5-haiku-20241022
export SESSION_ID=background_worker
python3 workers/task_worker.py
```

### UI Session (Comet Agent)
```bash
# UI tasks routed to Comet automatically
tmux new-session -s comet
export SESSION_ID=comet_agent
# Comet automatically uses Haiku for speed
```

### Coding Session (Codex Agent)
```bash
# Coding tasks routed to Codex automatically
tmux new-session -s codex
export SESSION_ID=codex_agent
# Codex uses Sonnet 4.5 for quality
```

### Development Session (Free)
```bash
# Development - use free Ollama
tmux new-session -s dev
export LLM_DEFAULT_PROVIDER=ollama
export SESSION_ID=dev_session
```

## Monitoring & Alerts

### View Token Usage

```bash
# Via Python
from services.token_throttle import get_throttler
throttler = get_throttler()
print(throttler.get_stats())

# Via Dashboard API (coming soon)
curl http://localhost:8080/api/throttle/stats
```

### Throttle Events

All throttle events are logged to `/tmp/token_throttle.db`:

```sql
-- View recent throttle events
SELECT * FROM throttle_events ORDER BY timestamp DESC LIMIT 10;

-- View usage history
SELECT session_id, SUM(tokens_used) as total, SUM(cost) as total_cost
FROM usage_history
WHERE timestamp > datetime('now', '-1 day')
GROUP BY session_id;
```

### Alerts

Configure alerts in `services/token_throttle.py`:

```python
config = ThrottleConfig(
    warning_threshold=0.70,    # Alert at 70%
    soft_threshold=0.80,       # Throttle at 80%
    hard_threshold=0.90,       # Block at 90%
)
```

## Best Practices

### 1. Set Session IDs
Always set `SESSION_ID` environment variable for tracking:
```bash
export SESSION_ID=worker_1
```

### 2. Use Appropriate Priority
- `critical`: Production incidents, security issues
- `high`: Important features, urgent bugs
- `normal`: Standard development work
- `low`: Documentation, research, cleanup

### 3. Let Delegation Choose
Trust the delegator to select the optimal model:
```python
result = delegator.delegate_task(task)
# Uses Haiku for docs, Sonnet for coding
```

### 4. Monitor Usage
Check throttle stats regularly:
```python
stats = throttler.get_stats("my_session")
if stats['throttle_level'] == 'WARNING':
    print("Approaching token limit!")
```

### 5. Configure Limits
Adjust limits based on your budget:
```python
from services.token_throttle import ThrottleConfig, TokenThrottler

config = ThrottleConfig(
    tokens_per_day=500000,    # 500K tokens/day
    cost_per_day=25.0,        # $25/day limit
)
throttler = TokenThrottler(config)
```

## Cost Savings Examples

### Example 1: Mixed Workload
**Scenario:** 50% UI tasks, 30% coding, 20% docs

**Without Optimization:**
- All tasks use Sonnet 4.5: $18/day

**With Delegation:**
- UI tasks → Haiku: $3/day (50%)
- Coding → Sonnet 4.5: $5.40/day (30%)
- Docs → Haiku: $0.72/day (20%)
- **Total: $9.12/day (49% savings)**

### Example 2: Aggressive Optimization
**Scenario:** Same workload + Ollama for development

**With Full Optimization:**
- UI tasks → Comet (Haiku): $3/day
- Coding → Codex (Sonnet 4.5): $5.40/day
- Docs → Haiku: $0.72/day
- Development → Ollama (free): $0/day
- **Total: $9.12/day + free dev (60% total savings)**

## Troubleshooting

### Request Throttled
```
RuntimeError: Request throttled: HARD. Token limit exceeded.
```

**Solution:**
1. Check usage: `throttler.get_stats("my_session")`
2. Wait for hourly reset
3. Use higher priority if critical
4. Switch to free Ollama temporarily

### Task Misclassified
```
# Task routed to wrong agent
result = delegator.delegate_task("Fix the API endpoint")
# -> Routed to Haiku instead of Codex
```

**Solution:**
- Explicitly specify task type:
  ```python
  result = delegator.delegate_task(
      "Fix the API endpoint",
      task_type=TaskType.CODING  # Force coding classification
  )
  ```

### High Costs
**Solution:**
1. Check which sessions are using most tokens
2. Route more tasks through delegation
3. Use Haiku/Ollama for non-critical work
4. Enable throttling with stricter limits

## Configuration Files

### Throttle Config
Location: `services/token_throttle.py`

```python
class ThrottleConfig:
    tokens_per_hour: int = 100000
    tokens_per_day: int = 1000000
    cost_per_day: float = 50.0
    warning_threshold: float = 0.70
    ...
```

### Delegation Config
Location: `services/task_delegator.py`

```python
AGENT_ROUTING = {
    TaskType.UI: AgentType.COMET,
    TaskType.CODING: AgentType.CODEX,
    TaskType.DOCUMENTATION: AgentType.CLAUDE_HAIKU,
    ...
}
```

## API Reference

See source files for complete API:
- `services/token_throttle.py` - Token throttling
- `services/task_delegator.py` - Task delegation
- `services/llm_provider.py` - LLM provider with integration

## Questions?

- Token usage dashboard: Coming in Phase 3
- Budget alerts: Configure in ThrottleConfig
- Custom routing rules: Modify AGENT_ROUTING dict
