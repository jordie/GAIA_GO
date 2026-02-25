# Concurrent Task Management with Token Metrics

## Overview

The concurrent task management system distributes AI tasks across multiple worker sessions while tracking token usage and enforcing cost limits to keep API expenses low.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Task Manager                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │   Token Throttle System                           │  │
│  │   • Tracks usage per session & globally           │  │
│  │   • Enforces limits: 100K/hour, 1M/day per worker│  │
│  │   • Global limits: 500K/hour, 5M/day              │  │
│  │   • Cost limits: $5/hour, $50/day, $1000/month    │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │   Task Delegator                                  │  │
│  │   • Routes UI tasks → Comet (Haiku - cheap)       │  │
│  │   • Routes coding → Codex (Sonnet - premium)      │  │
│  │   • Routes docs → Haiku (cheap)                   │  │
│  │   • Estimates complexity & tokens                 │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │ Worker1 │      │ Worker2 │      │ Worker3 │
   │ Claude  │      │ Claude  │      │ Claude  │
   └─────────┘      └─────────┘      └─────────┘
```

## Key Features

### 1. Token Usage Tracking

Every task is tracked for token consumption:

```python
# Automatic estimation before sending
estimated_tokens = len(task) // 4 + 1000  # ~4 chars/token + overhead

# Recorded after completion
actual_tokens = estimate_task_tokens(completed_task)
throttler.record_usage(worker, actual_tokens, cost, model)
```

### 2. Cost Optimization

**Multi-tier model selection** based on task complexity:

| Task Type | Model | Cost per 1K tokens | Use Case |
|-----------|-------|-------------------|----------|
| UI/Simple | Haiku | $0.00025 | 80% cheaper than Sonnet |
| Coding | Sonnet 4.5 | $0.003 | High quality code generation |
| Documentation | Haiku | $0.00025 | Simple text generation |
| Analysis | Sonnet 4.5 | $0.003 | Complex reasoning |

**Expected savings**: 20-40% vs uniform Sonnet usage

### 3. Throttle Levels

The system enforces 5 throttle levels:

| Level | Trigger | Action |
|-------|---------|--------|
| 🟢 **NONE** | < 80% of limit | Normal operation |
| 🟡 **WARNING** | 80-90% of limit | Monitor closely |
| 🟠 **SOFT** | 90-95% of limit | Queue low priority tasks |
| 🔴 **HARD** | 95-99% of limit | Only high/critical priority |
| 🚨 **CRITICAL** | > 99% of limit | Only critical emergency tasks |

### 4. Real-time Monitoring

Track usage in real-time:

```bash
# Show current status with metrics
python3 concurrent_task_manager.py
> status

# Show detailed token usage
> metrics

# Show throttle status
> throttle
```

## Usage

### Starting the System

```bash
# Start 3 concurrent workers
tmux new-session -d -s concurrent_worker1 -c "$(pwd)" && \
tmux send-keys -t concurrent_worker1 "claude" Enter

tmux new-session -d -s concurrent_worker2 -c "$(pwd)" && \
tmux send-keys -t concurrent_worker2 "claude" Enter

tmux new-session -d -s concurrent_worker3 -c "$(pwd)" && \
tmux send-keys -t concurrent_worker3 "claude" Enter

# Start task manager
python3 concurrent_task_manager.py
```

### Adding Tasks

**Batch mode:**
```bash
python3 concurrent_task_manager.py \
  "Task 1" \
  "Task 2" \
  "Task 3"
```

**Interactive mode:**
```bash
python3 concurrent_task_manager.py

> add Create a user authentication system
> add Fix responsive styling on mobile
> add Write documentation for API
> status
```

### Monitoring Metrics

**Worker Status with Metrics:**
```
CONCURRENT TASK MANAGER STATUS
================================================================================
Tasks in queue: 0
Total completed: 12
Total tokens used: 48,523
Estimated cost: $0.1456

Global Throttle Status:
  Tokens/hour: 48,523 / 500K  (9.7%)
  Tokens/day:  48,523 / 5M    (0.97%)
  Cost/hour:   $0.15 / $5.00  (3.0%)
  Cost/day:    $0.15 / $50.00 (0.3%)

Worker Status:
  concurrent_worker1   🟢 IDLE     | Done:  4 | Tokens: 15,234 | Task: None
  concurrent_worker2   🔴 BUSY     | Done:  5 | Tokens: 18,542 | Task: Implement authentication
  concurrent_worker3   🟢 IDLE     | Done:  3 | Tokens: 14,747 | Task: None

Throttle Levels:
  concurrent_worker1   🟢 NONE       | Hour: 15,234 | Day: 15,234
  concurrent_worker2   🟢 NONE       | Hour: 18,542 | Day: 18,542
  concurrent_worker3   🟢 NONE       | Hour: 14,747 | Day: 14,747
```

**Detailed Metrics:**
```
> metrics

TOKEN USAGE & COST METRICS
================================================================================
Global Metrics:
  Total tasks completed:  12
  Total tokens used:      48,523
  Estimated total cost:   $0.1456
  Average tokens/task:    4,043
  Average cost/task:      $0.0121

Per-Worker Metrics:
  concurrent_worker1
    Tasks completed:  4
    Tokens used:      15,234
    Estimated cost:   $0.0457
    Avg tokens/task:  3,808

Cost Optimization:
  ✅ Task delegation enabled - routing to optimal models
  ✅ Expected savings: 20-40% vs uniform model usage
```

## Best Practices

### 1. Keep Sessions Under Limits

**Per-session limits:**
- 100K tokens/hour
- 1M tokens/day

**Strategy**: Distribute tasks evenly across workers

### 2. Use Task Delegation

Always enable delegation for automatic model selection:

```python
from services.task_delegator import get_delegator

delegator = get_delegator()
result = delegator.delegate_task("Your task here")
# Automatically selects optimal model
```

### 3. Monitor Throttle Levels

Check throttle status regularly:
```bash
> throttle
```

If any worker reaches 🟡 WARNING or higher, pause and wait for the hourly window to reset.

### 4. Batch Similar Tasks

Group similar tasks to benefit from context reuse:
```bash
# Good - similar tasks together
> add Validate email format
> add Validate phone number format
> add Validate URL format

# Less optimal - mixed task types
> add Validate email format
> add Create responsive navigation
> add Implement authentication
```

### 5. Use Auto-Distribution

For continuous processing:
```bash
> auto
# System will distribute tasks every 10 seconds
# Press Ctrl+C to stop auto mode
```

## Integration with Existing Systems

### Assigner Worker Integration

The concurrent manager can work alongside the assigner worker:

```python
# Assigner handles prompts from queue
# Concurrent manager handles batch parallel tasks

# Use assigner for: Single tasks, delegated tasks, priority routing
# Use concurrent manager for: Batch processing, parallel execution, high throughput
```

### Task Queue Integration

Tasks can be pulled from the main task queue:

```python
# Get tasks from architect dashboard
tasks = get_pending_tasks()

for task in tasks:
    manager.add_task(task['content'])
    manager.distribute_tasks()
```

## Troubleshooting

### High Token Usage

**Symptoms:** Throttle level reaching WARNING or SOFT

**Solutions:**
1. Check task complexity - simplify prompts
2. Reduce concurrent workers (use 2 instead of 3)
3. Enable stricter delegation to favor Haiku
4. Wait for hourly window reset

### Tasks Not Distributing

**Symptoms:** Tasks stuck in queue, workers idle

**Solutions:**
1. Check worker sessions are responsive: `tmux capture-pane -t worker1 -p`
2. Manually trigger distribution: `> distribute`
3. Check throttle limits: `> throttle`
4. Restart workers if needed

### Cost Exceeding Budget

**Symptoms:** Approaching daily/monthly cost limits

**Solutions:**
1. Reduce worker count
2. Use only Haiku model (set delegation to prefer cheap)
3. Implement stricter priority filtering
4. Review task complexity - break into smaller pieces

## Performance Metrics

### Typical Usage Patterns

**Light usage (documentation/simple tasks):**
- Average: 2K tokens/task
- Cost: ~$0.0005/task (Haiku)
- Hourly capacity: ~250 tasks (500K token limit)

**Medium usage (coding tasks):**
- Average: 4K tokens/task
- Cost: ~$0.012/task (Sonnet)
- Hourly capacity: ~125 tasks

**Heavy usage (complex analysis):**
- Average: 8K tokens/task
- Cost: ~$0.024/task (Sonnet)
- Hourly capacity: ~62 tasks

### Cost Projections

**Scenario: 100 tasks/day mixed workload**
- 40% documentation (Haiku): $0.02
- 40% coding (Sonnet): $0.48
- 20% analysis (Sonnet): $0.48
- **Total: ~$0.98/day** ($29.40/month)

**Well under limits:**
- Daily limit: $50.00
- Monthly limit: $1,000.00

## Summary

The concurrent task management system with metrics tracking provides:

✅ **Cost control** - Stay within budget through throttling
✅ **Optimization** - Automatic model selection for 20-40% savings
✅ **Visibility** - Real-time token usage and cost tracking
✅ **Scalability** - Parallel execution across multiple workers
✅ **Safety** - Multi-level throttling prevents runaway costs

By tracking every token and enforcing limits, the system ensures AI-powered automation remains cost-effective and sustainable.
