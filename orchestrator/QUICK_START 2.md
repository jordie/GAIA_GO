# Goal Engine Quick Start Guide

## 5-Minute Setup

### 1. Test the Goal Engine

```bash
# View current strategic vision
python3 orchestrator/goal_engine.py --show-vision

# Analyze current project state
python3 orchestrator/goal_engine.py --show-state

# Preview tasks that would be generated (dry run)
python3 orchestrator/goal_engine.py --dry-run
```

### 2. Generate Your First Tasks

```bash
# Generate and queue up to 3 tasks
python3 orchestrator/goal_engine.py --generate --max-tasks 3
```

This will:
- Analyze your current state (projects, revenue, blockers)
- Generate tasks aligned with strategic vision
- Prioritize by revenue impact and strategic alignment
- Queue tasks to assigner worker for execution

### 3. Monitor Task Execution

```bash
# Check assigner worker status
python3 workers/assigner_worker.py --status

# View queued prompts
python3 workers/assigner_worker.py --prompts

# View active sessions
python3 workers/assigner_worker.py --sessions
```

### 4. Learn from Patterns (After Some Tasks Complete)

```bash
# Analyze task outcomes and update routing patterns
python3 orchestrator/goal_engine.py --learn
```

This improves session routing based on actual success rates.

## Daily Workflow

### Morning: Generate Tasks
```bash
python3 orchestrator/goal_engine.py --generate --max-tasks 3
```

### Evening: Check Progress
```bash
python3 workers/assigner_worker.py --prompts
```

### Weekly: Learn and Optimize
```bash
python3 orchestrator/goal_engine.py --learn
```

## Automated Setup (Cron)

Add to crontab (`crontab -e`):

```bash
# Daily at 9 AM - Generate 3 tasks
0 9 * * * cd /path/to/architect && python3 orchestrator/goal_engine.py --generate --max-tasks 3 >> /tmp/goal_engine.log 2>&1

# Weekly on Sunday at 10 PM - Learn from patterns
0 22 * * 0 cd /path/to/architect && python3 orchestrator/goal_engine.py --learn >> /tmp/goal_engine.log 2>&1
```

Or use the provided script:

```bash
# Make script executable
chmod +x scripts/run_goal_engine.sh

# Run manually
./scripts/run_goal_engine.sh

# Or add to cron
0 9 * * * cd /path/to/architect && ./scripts/run_goal_engine.sh
```

## Customizing Strategic Vision

### Update Primary Goal

```bash
python3 orchestrator/goal_engine.py --update-vision \
    --field primary_goal \
    --value "Launch EDU apps with 100 paying subscribers"
```

### Update Focus Areas

```bash
python3 orchestrator/goal_engine.py --update-vision \
    --field focus_areas \
    --value '["payment_integration", "user_acquisition", "retention", "automation"]'
```

### Update Revenue Targets

```bash
python3 orchestrator/goal_engine.py --update-vision \
    --field revenue_targets \
    --value '{"month_3": 999, "month_6": 2500, "year_1": 10000}'
```

## Tracking Revenue

Add revenue data to improve task generation:

```sql
-- Connect to database
sqlite3 data/architect.db

-- Add revenue tracking entry
INSERT INTO revenue_tracking (
    project_id,
    period_start,
    period_end,
    actual_revenue,
    projected_revenue,
    subscriptions,
    churn_rate
) VALUES (
    1,  -- Basic EDU Apps project ID
    '2026-02-01',
    '2026-02-28',
    0,    -- Actual revenue this month
    999,  -- Projected revenue
    0,    -- Number of subscriptions
    0.0   -- Churn rate
);
```

## Using the API

Start the API server:

```bash
python3 scripts/goal_engine_api.py --port 5555
```

Then use curl or your application:

```bash
# Generate tasks
curl -X POST http://localhost:5555/api/goal-engine/generate \
    -H "Content-Type: application/json" \
    -d '{"max_tasks": 3}'

# Get vision
curl http://localhost:5555/api/goal-engine/vision

# Get state
curl http://localhost:5555/api/goal-engine/state

# Learn from patterns
curl -X POST http://localhost:5555/api/goal-engine/learn
```

## Common Commands Reference

### Generation
```bash
# Generate tasks
python3 orchestrator/goal_engine.py --generate

# Dry run (preview)
python3 orchestrator/goal_engine.py --dry-run

# Limit tasks
python3 orchestrator/goal_engine.py --generate --max-tasks 5
```

### Information
```bash
# Show vision
python3 orchestrator/goal_engine.py --show-vision

# Show state
python3 orchestrator/goal_engine.py --show-state

# Show revenue
python3 orchestrator/goal_engine.py --show-revenue
```

### Learning
```bash
# Analyze patterns
python3 orchestrator/goal_engine.py --learn
```

### Update
```bash
# Update vision field
python3 orchestrator/goal_engine.py --update-vision --field FIELD --value VALUE
```

## Troubleshooting

### No Tasks Generated?

1. Check strategic vision exists:
   ```bash
   python3 orchestrator/goal_engine.py --show-vision
   ```

2. Check if projects are active:
   ```bash
   sqlite3 data/architect.db "SELECT id, name, status FROM projects"
   ```

3. Run with verbose output:
   ```bash
   python3 orchestrator/goal_engine.py --dry-run 2>&1 | grep -A 5 "Generated"
   ```

### Tasks Not Executing?

1. Check assigner worker is running:
   ```bash
   python3 workers/assigner_worker.py --status
   ```

2. Start if not running:
   ```bash
   python3 workers/assigner_worker.py --daemon
   ```

3. Check sessions are available:
   ```bash
   python3 workers/assigner_worker.py --sessions
   ```

### Pattern Learning Not Working?

1. Ensure tasks have completed:
   ```bash
   sqlite3 data/assigner/assigner.db "SELECT COUNT(*) FROM prompts WHERE status='completed'"
   ```

2. Check time range (last 30 days):
   ```bash
   python3 orchestrator/goal_engine.py --learn
   ```

## Next Steps

1. **Run Daily**: Set up cron to generate tasks automatically
2. **Track Revenue**: Add revenue data regularly
3. **Monitor Patterns**: Review learning results weekly
4. **Refine Vision**: Update strategic goals as business evolves
5. **Scale**: Increase max_tasks as system capacity grows

## Support

- Full documentation: `orchestrator/GOAL_ENGINE_README.md`
- Implementation summary: `GOAL_ENGINE_SUMMARY.md`
- Code: `orchestrator/goal_engine.py`

## Example Session

```bash
$ python3 orchestrator/goal_engine.py --dry-run
INFO:GoalEngine:============================================================
INFO:GoalEngine:Goal-Oriented Task Engine - Generating Tasks
INFO:GoalEngine:============================================================
INFO:GoalEngine:Generated 7 tasks from vision
INFO:GoalEngine:After deduplication: 7 unique tasks
INFO:GoalEngine:DRY RUN - Not queuing tasks

======================================================================
TASK GENERATION SUMMARY
======================================================================
Generated:        7 tasks
Unique:           7 tasks
Queued:           0 tasks
Skipped:          0 duplicates
Revenue Impact:   $2850.00/month
======================================================================

TASKS (DRY RUN - NOT QUEUED):

1. [10] Implement Stripe payment integration for Basic EDU subscription tiers
   Category:   revenue
   Project:    Basic EDU Apps
   Revenue:    $1000.00/month
   Alignment:  100.0%
   Session:    dev_worker1
   Reasoning:  Critical for revenue - currently $999 behind target
```

Ready to start generating revenue-focused tasks!
