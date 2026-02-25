# Milestone Worker Quick Start

Get the milestone planning worker running in 2 minutes.

## TL;DR

```bash
# Scan all projects now
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
./scripts/milestone_planner.sh scan

# View results
ls -lh data/milestones/
cat data/milestones/architect_summary.md

# Start as daemon
./scripts/milestone_planner.sh start
./scripts/milestone_planner.sh status
```

## Installation

No installation needed! All dependencies are part of Python 3 standard library.

## Basic Usage

### 1. Run Immediate Scan

```bash
# Scan all active projects
./scripts/milestone_planner.sh scan

# Scan specific project
./scripts/milestone_planner.sh scan architect
./scripts/milestone_planner.sh scan basic_edu_apps_final
```

**Output**: JSON and markdown files in `data/milestones/`

### 2. Start Worker Daemon

```bash
# Start background worker (polls for tasks every 5 minutes)
./scripts/milestone_planner.sh start

# Check status
./scripts/milestone_planner.sh status

# View logs
./scripts/milestone_planner.sh logs

# Stop worker
./scripts/milestone_planner.sh stop
```

### 3. Create Dashboard Task

```bash
# Create task for all projects
python3 scripts/create_milestone_task.py

# Create task for specific project
python3 scripts/create_milestone_task.py architect

# High priority task
python3 scripts/create_milestone_task.py --priority 1
```

The worker will automatically claim and process the task.

## View Results

### Summary Reports
```bash
# List all summaries
ls -lh data/milestones/*_summary.md

# View architect summary
cat data/milestones/architect_summary.md

# View basic_edu_apps summary
cat data/milestones/basic_edu_apps_final_summary.md
```

### JSON Data
```bash
# Latest milestone file
ls -lt data/milestones/*.json | head -1

# View JSON with formatting
python3 -m json.tool data/milestones/architect_milestones_*.json | less
```

### Statistics
```python
import json
from pathlib import Path

# Load latest architect milestones
files = sorted(Path('data/milestones').glob('architect_milestones_*.json'))
data = json.load(files[-1].open())

print(f"Project: {data['project']}")
print(f"Tasks: {data['total_tasks']}")
print(f"Milestones: {data['total_milestones']}")
print(f"\nCategories:")
for cat, count in data['tasks_by_category']['by_category'].items():
    print(f"  {cat}: {count}")
```

## Common Commands

```bash
# Start worker
./scripts/milestone_planner.sh start

# Check if running
./scripts/milestone_planner.sh status

# Scan now (doesn't require worker running)
./scripts/milestone_planner.sh scan

# Scan specific project
./scripts/milestone_planner.sh scan claude_browser_agent

# Watch logs in real-time
./scripts/milestone_planner.sh logs

# Restart worker
./scripts/milestone_planner.sh restart

# Stop worker
./scripts/milestone_planner.sh stop

# Clean old files (>30 days)
./scripts/milestone_planner.sh clean
```

## Integration with Dashboard

### Queue a Task
```bash
# Via script
python3 scripts/create_milestone_task.py architect

# Via curl
curl -X POST http://100.112.58.92:8080/api/tasks \
  -u architect:peace5 \
  -H "Content-Type: application/json" \
  -d '{"task_type":"milestone","task_data":{"project":"architect"},"priority":2}'
```

### Check Task Status
```bash
# Via dashboard web UI
open http://100.112.58.92:8080
# Login: architect / peace5
# Navigate to Tasks panel

# Via API
curl http://100.112.58.92:8080/api/tasks \
  -u architect:peace5 | python3 -m json.tool
```

## Output Structure

```
data/milestones/
├── architect_milestones_20251225_013140.json    # Full data
├── architect_summary.md                         # Readable report
├── claude_browser_agent_milestones_*.json
├── claude_browser_agent_summary.md
├── basic_edu_apps_final_milestones_*.json
├── basic_edu_apps_final_summary.md
├── mentor_v2_milestones_*.json
└── mentor_v2_summary.md
```

## Example Output

### Summary Report (`architect_summary.md`)
```markdown
# Architect - Milestone Plan

Generated: 2025-12-25 01:31:27

## Summary
- Total Tasks: 41
- Total Milestones: 7
- Estimated Total Hours: 122.0
- Estimated Duration: 6.5 days

## Task Breakdown
### By Category
- Feature: 33
- Bug: 1
- Test: 6
- Deployment: 1

## Milestones
### 1. Architect - Planning & Setup
- Phase: Planning
- Start: 2025-12-25
- Target: 2025-12-28
- Tasks: 5
- Estimated Hours: 12.0
...
```

### JSON Structure
```json
{
  "project": "architect",
  "generated_at": "2025-12-25T01:31:27",
  "total_tasks": 41,
  "total_milestones": 7,
  "milestones": [
    {
      "id": "architect_planning",
      "name": "Architect - Planning & Setup",
      "phase": "planning",
      "start_date": "2025-12-25T00:00:00",
      "target_date": "2025-12-28T00:00:00",
      "total_hours": 12.0,
      "status": "pending",
      "tasks": [...]
    }
  ],
  "tasks_by_category": {
    "by_category": {"feature": 33, "bug": 1},
    "by_priority": {"priority_2": 1, "priority_3": 40},
    "by_complexity": {"simple": 15, "medium": 20, "complex": 6}
  }
}
```

## Troubleshooting

### Worker won't start
```bash
# Check if already running
ps aux | grep milestone_worker

# Check logs
tail -50 /tmp/architect_milestone_worker.log

# Remove stale PID
rm /tmp/architect_milestone_worker.pid

# Try again
./scripts/milestone_planner.sh start
```

### No tasks found
```bash
# Verify project path exists
ls -la /Users/jgirmay/Desktop/gitrepo/pyWork/architect/

# Check for TODO files
find /Users/jgirmay/Desktop/gitrepo/pyWork/architect/ -name "TODO.md"

# Review logs
./scripts/milestone_planner.sh logs
```

### Dashboard connection fails
```bash
# Check dashboard is running
curl http://100.112.58.92:8080/health

# Check environment variable
echo $ARCHITECT_URL

# Test with custom URL
ARCHITECT_URL=http://localhost:8080 ./scripts/milestone_planner.sh scan
```

## Advanced Usage

### Custom Poll Interval
```bash
# Poll every 10 minutes instead of 5
python3 workers/milestone_worker.py --daemon --poll-interval 600
```

### Run Without Dashboard
```bash
# Direct scan (no dashboard integration)
python3 workers/milestone_worker.py --scan
```

### Add New Project
Edit `workers/milestone_worker.py`:
```python
ACTIVE_PROJECTS = {
    'my_project': {
        'path': PROJECT_ROOT / 'my_project',
        'description': 'My project description',
        'key_files': ['TODO.md', 'README.md']
    }
}
```

## Next Steps

1. **Review generated milestones** - Check summary files for accuracy
2. **Start daemon** - Run worker continuously to process dashboard tasks
3. **Integrate with workflow** - Create tasks from dashboard or scripts
4. **Track progress** - Update task status as work completes
5. **Re-scan periodically** - Generate fresh plans as TODOs change

## See Also

- Full Documentation: `MILESTONE_WORKER.md`
- Worker Code: `workers/milestone_worker.py`
- Helper Script: `scripts/milestone_planner.sh`
- Output README: `data/milestones/README.md`
