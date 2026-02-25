# Goal-Oriented Autonomous Task Engine

## Overview

The Goal Engine transforms strategic vision into actionable tasks, automatically prioritizing and routing them to the appropriate sessions based on revenue potential, strategic alignment, and learned execution patterns.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Strategic Vision (Database)                                │
│  - Business goals and focus areas                           │
│  - Revenue targets and success metrics                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Goal Engine (orchestrator/goal_engine.py)                  │
│  1. Read strategic vision from database                     │
│  2. Analyze current state (projects, features, revenue)     │
│  3. Generate tactical tasks to advance vision               │
│  4. Prioritize by revenue, alignment, dependencies          │
│  5. Route to optimal session based on learned patterns      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Assigner Worker (workers/assigner_worker.py)               │
│  - Receives tasks from Goal Engine                          │
│  - Routes to appropriate Claude sessions                    │
│  - Tracks execution and outcomes                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Pattern Learning                                           │
│  - Analyzes task outcomes and session performance           │
│  - Updates routing preferences                              │
│  - Improves success rates over time                         │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Database-Driven Strategic Vision

Strategic vision is stored in the database (`strategic_vision` table) with:
- **Statement**: Overall mission/vision
- **Primary Goal**: Current top priority
- **Focus Areas**: Key areas of focus (e.g., payment_integration, automation)
- **Revenue Targets**: Monthly/yearly revenue goals
- **Success Metrics**: KPIs to track progress

### 2. Revenue-Aware Prioritization

Tasks are prioritized by:
1. **Revenue Impact**: Estimated monthly revenue impact ($)
2. **Priority Level**: 0-10 scale based on category
3. **Strategic Alignment**: How well task aligns with vision (0.0-1.0)

Priority levels:
- **10**: Revenue-generating tasks (payment, subscriptions)
- **9**: Critical bugs/blockers
- **8**: Strategic alignment tasks
- **7**: Automation/force multipliers
- **6**: Quality improvements
- **5**: Technical debt reduction
- **4**: Enhancements

### 3. Intelligent Session Routing

The engine learns which sessions perform best for each task category by:
- Tracking success/failure rates per session per category
- Measuring average completion times
- Routing future tasks to highest-performing sessions

### 4. Dependency Tracking

Tasks can specify dependencies on other tasks, ensuring:
- Blocking tasks complete first
- Prerequisites are satisfied before starting
- Logical execution order

### 5. State Analysis

The engine analyzes:
- **Project Status**: Completion percentages, blockers
- **Revenue Metrics**: Current vs target, gap analysis
- **Opportunities**: Near-completion projects (80%+ done)
- **Blockers**: Critical bugs preventing progress

## Database Schema

### strategic_vision
```sql
CREATE TABLE strategic_vision (
    id INTEGER PRIMARY KEY,
    statement TEXT NOT NULL,
    primary_goal TEXT,
    focus_areas TEXT,        -- JSON array
    revenue_targets TEXT,    -- JSON object
    success_metrics TEXT,    -- JSON object
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### revenue_tracking
```sql
CREATE TABLE revenue_tracking (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    actual_revenue REAL DEFAULT 0,
    projected_revenue REAL DEFAULT 0,
    subscriptions INTEGER DEFAULT 0,
    churn_rate REAL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

### task_patterns (Learning Database)
```sql
CREATE TABLE task_patterns (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    session_name TEXT NOT NULL,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    total_completion_time REAL DEFAULT 0,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, session_name)
);
```

## Usage Examples

### Generate and Queue Tasks
```bash
# Generate tasks from strategic vision and queue them
python3 orchestrator/goal_engine.py --generate

# Preview tasks without queuing (dry run)
python3 orchestrator/goal_engine.py --dry-run

# Limit number of tasks queued
python3 orchestrator/goal_engine.py --generate --max-tasks 5
```

### View Strategic Information
```bash
# Show strategic vision
python3 orchestrator/goal_engine.py --show-vision

# Show current state analysis
python3 orchestrator/goal_engine.py --show-state

# Show revenue metrics
python3 orchestrator/goal_engine.py --show-revenue
```

### Learn from Execution Patterns
```bash
# Analyze task execution history and update learning database
python3 orchestrator/goal_engine.py --learn
```

### Update Strategic Vision
```bash
# Update primary goal
python3 orchestrator/goal_engine.py --update-vision \
    --field primary_goal \
    --value "Launch EDU apps with 100 paying users"

# Update focus areas (JSON)
python3 orchestrator/goal_engine.py --update-vision \
    --field focus_areas \
    --value '["payment_integration", "user_acquisition", "retention"]'
```

## Integration with Assigner Worker

The Goal Engine integrates with the existing assigner worker:

1. **Task Generation**: Goal Engine generates tasks with metadata
2. **Queue Insertion**: Tasks inserted into `prompts` table in assigner DB
3. **Session Routing**: Tasks routed to preferred session if available
4. **Execution**: Assigner worker picks up and executes tasks
5. **Pattern Learning**: Goal Engine analyzes outcomes and updates patterns

### Task Metadata

Generated tasks include comprehensive metadata:
```json
{
  "category": "revenue",
  "project": "Basic EDU Apps",
  "reasoning": "Critical for revenue - currently $999 behind target",
  "generated_by": "goal_engine",
  "generated_at": "2026-02-07T19:00:00",
  "revenue_impact": 1000.0,
  "strategic_alignment": 1.0,
  "dependencies": []
}
```

## Task Generation Logic

### Vision → Task Examples

**Vision**: "Create revenue streams"
- Task: "Implement Stripe payment integration"
- Priority: 10 (revenue)
- Revenue Impact: $1000/month
- Strategic Alignment: 1.0

**Vision**: "Improve automation"
- Task: "Implement automated deployment pipeline"
- Priority: 7 (automation)
- Revenue Impact: $100/month (time savings)
- Strategic Alignment: 0.7

### State → Task Examples

**State**: "Project 80% complete"
- Task: "Complete remaining 3 features to launch"
- Priority: 8 (strategic)
- Revenue Impact: Based on project type
- Strategic Alignment: 0.8

**State**: "5 critical bugs blocking project"
- Task: "Resolve 5 critical bugs"
- Priority: 9 (critical)
- Revenue Impact: $300/month (if revenue project)
- Strategic Alignment: 0.9

## Automated Scheduling

The Goal Engine can run on a schedule via cron or systemd timer:

### Daily Task Generation (Cron)
```bash
# Add to crontab (crontab -e)
0 9 * * * cd /path/to/architect && python3 orchestrator/goal_engine.py --generate --max-tasks 3 >> /tmp/goal_engine.log 2>&1
```

### Weekly Pattern Learning
```bash
# Learn from execution patterns every Sunday at 10 PM
0 22 * * 0 cd /path/to/architect && python3 orchestrator/goal_engine.py --learn >> /tmp/goal_engine.log 2>&1
```

## API Integration

The Goal Engine can be called programmatically:

```python
from orchestrator.goal_engine import GoalEngine

# Initialize engine
engine = GoalEngine()

# Get strategic vision
vision = engine.get_strategic_vision()

# Analyze current state
state = engine.analyze_current_state()

# Generate tasks
results = engine.generate_and_queue_tasks(
    dry_run=False,
    max_tasks=5
)

print(f"Queued {results['queued']} tasks")
print(f"Revenue impact: ${results['total_revenue_impact']:.2f}/month")

# Learn from patterns
learning_results = engine.learn_from_patterns()
print(f"Updated {learning_results['patterns_updated']} patterns")
```

## Monitoring and Metrics

### Key Metrics to Track

1. **Task Generation Rate**: Tasks generated per run
2. **Queue Success Rate**: % of queued tasks that complete successfully
3. **Revenue Impact**: Total potential revenue from completed tasks
4. **Strategic Alignment**: Average alignment score of queued tasks
5. **Session Performance**: Success rates by session and category

### Example Queries

```sql
-- View task patterns by session
SELECT
    session_name,
    category,
    success_count,
    failure_count,
    ROUND(CAST(success_count AS REAL) / (success_count + failure_count) * 100, 1) as success_rate
FROM task_patterns
WHERE (success_count + failure_count) >= 5
ORDER BY success_rate DESC;

-- Revenue tracking over time
SELECT
    strftime('%Y-%m', period_end) as month,
    SUM(actual_revenue) as total_revenue,
    SUM(projected_revenue) as target_revenue
FROM revenue_tracking
GROUP BY month
ORDER BY month DESC;
```

## Best Practices

### 1. Regular Pattern Learning
Run `--learn` weekly to keep session routing optimized based on recent performance.

### 2. Revenue Tracking
Update `revenue_tracking` table regularly with actual revenue data for accurate gap analysis.

### 3. Vision Updates
Review and update strategic vision monthly to align with business goals.

### 4. Task Limits
Use `--max-tasks` to prevent overwhelming the system with too many simultaneous tasks.

### 5. Monitor Dependencies
Check that dependency tasks complete before dependent tasks are queued.

## Troubleshooting

### No Tasks Generated
- Check strategic vision is set correctly
- Verify projects exist and are marked 'active'
- Check that focus areas match task generation logic

### Tasks Queued but Not Executing
- Verify assigner worker is running
- Check target sessions exist and are idle
- Review assigner worker logs

### Poor Session Routing
- Run `--learn` to update patterns
- Check task_patterns table has sufficient data
- Manually review session performance in assigner DB

## Future Enhancements

- [ ] Multi-criteria optimization (revenue + time + risk)
- [ ] Dependency graph visualization
- [ ] A/B testing for session routing
- [ ] Reinforcement learning for pattern optimization
- [ ] Integration with external analytics (Stripe, GA)
- [ ] Automated vision updates based on performance data
- [ ] Task impact prediction using ML models
- [ ] Portfolio optimization across projects
