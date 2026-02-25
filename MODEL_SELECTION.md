# LLM Model Selection Guide

## Quick Start: Save on API Costs

### Keep Current Session on Premium Model
This session stays on **Claude Sonnet 4.5** (premium quality, higher cost).

### Use Cheaper Models for Other Sessions

**Option 1: Claude Haiku (80% cost savings)**
```bash
# In other Claude sessions, set:
export CLAUDE_MODEL=claude-3-5-haiku-20241022

# Then start your script/service
python3 your_script.py
```

**Option 2: Ollama (100% free, local)**
```bash
# In other sessions, use Ollama instead:
export LLM_DEFAULT_PROVIDER=ollama
export LLM_FAILOVER_ENABLED=true

python3 your_script.py
```

**Option 3: Haiku with Ollama Failover (Best of Both)**
```bash
# Use cheap Haiku, fallback to free Ollama if rate limited
export CLAUDE_MODEL=claude-3-5-haiku-20241022
export LLM_FAILOVER_ENABLED=true
export LLM_DEFAULT_PROVIDER=claude

python3 your_script.py
```

## Model Comparison

| Model | Input Cost | Output Cost | Speed | Quality | Use Case |
|-------|-----------|-------------|-------|---------|----------|
| **Sonnet 4.5** (current) | $3/1M | $15/1M | Fast | Highest | Production, critical work |
| **Sonnet 3.5** | $3/1M | $15/1M | Fast | High | General use |
| **Haiku 3.5** | $1/1M | $5/1M | Fastest | Good | Background tasks, simple queries |
| **Ollama (local)** | Free | Free | Medium | Good | Testing, development, high volume |
| **GPT-4 Turbo** | $10/1M | $30/1M | Medium | High | Backup only |

## Cost Savings Examples

### Scenario: 1M tokens per day

| Configuration | Daily Cost | Monthly Cost | Savings |
|--------------|-----------|--------------|---------|
| All Sonnet 4.5 | $18.00 | $540 | Baseline |
| **Current + Others Haiku** | $6.00 | $180 | **67% saved** |
| **Current + Others Ollama** | $3.00 | $90 | **83% saved** |
| All Ollama | $0.00 | $0 | **100% saved** |

## Per-Session Configuration

### Session 1: Current Session (Premium)
```bash
# No changes needed - already using Sonnet 4.5
# Model: claude-sonnet-4-5-20250929
```

### Session 2-N: Background Workers
```bash
# Option A: Use Haiku
export CLAUDE_MODEL=claude-3-5-haiku-20241022

# Option B: Use Ollama
export LLM_DEFAULT_PROVIDER=ollama
```

## tmux Session Examples

### Premium Session (This One)
```bash
tmux new-session -s premium -d
# Uses default: claude-sonnet-4-5-20250929
```

### Budget Session (Background Tasks)
```bash
tmux new-session -s budget -d
tmux send-keys -t budget "export CLAUDE_MODEL=claude-3-5-haiku-20241022" Enter
tmux send-keys -t budget "python3 workers/crawler_service.py" Enter
```

### Free Session (Development)
```bash
tmux new-session -s dev -d
tmux send-keys -t dev "export LLM_DEFAULT_PROVIDER=ollama" Enter
tmux send-keys -t dev "python3 your_dev_script.py" Enter
```

## Global Configuration

To set defaults for ALL new sessions, add to `~/.bashrc` or `~/.zshrc`:

```bash
# For background/non-interactive sessions
export CLAUDE_MODEL=claude-3-5-haiku-20241022
export LLM_FAILOVER_ENABLED=true
```

Then in your premium session, override:
```bash
export CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

## Failover Strategy

**Recommended Failover Chain:**
1. Claude Haiku (cheap, fast)
2. Ollama (free, local)
3. OpenAI GPT-4 (expensive backup)

```bash
export CLAUDE_MODEL=claude-3-5-haiku-20241022
export LLM_FAILOVER_ENABLED=true
export LLM_DEFAULT_PROVIDER=claude
```

This gives you:
- **80% cost savings** vs Sonnet 4.5
- **Free failover** to Ollama if rate limited
- **Paid backup** to GPT-4 if both fail

## Verify Current Model

Check which model a session is using:

```python
from services.llm_provider import UnifiedLLMClient

client = UnifiedLLMClient()
print(f"Default model: {client.providers['claude'].config.model}")
```

Or check via environment:
```bash
echo "Current model: $CLAUDE_MODEL"
echo "Fallback: ${CLAUDE_MODEL:-claude-sonnet-4-5-20250929}"
```

## Best Practices

1. **Keep 1 premium session** for critical work (this one)
2. **Use Haiku for background tasks** (80% savings)
3. **Use Ollama for development** (100% free)
4. **Enable failover** for all sessions (resilience)
5. **Monitor costs** via dashboard `/api/llm/costs`

## Questions?

- What model am I using? `echo $CLAUDE_MODEL`
- How much am I spending? Check `/api/llm/costs` endpoint
- Is failover working? Check `/api/llm/circuits` endpoint
