# Milestone Planning Worker

A daemon worker that scans active projects and generates development milestone plans for the Architect dashboard.

## Overview

The Milestone Worker automates project planning by:
1. Scanning project directories for active work items
2. Reading TODO files, plan files, and code comments
3. Extracting tasks with priority, complexity, and category
4. Generating milestone plans with multi-day development phases
5. Outputting structured JSON and markdown reports
6. Integrating with the Architect dashboard task queue

## Features

### Task Discovery
- Scans TODO.md files for uncompleted checklist items
- Parses plan files from `.claude/plans/` directories
- Finds TODO/FIXME/HACK comments in Python code
- Extracts guidance from CLAUDE.md files

### Intelligent Classification
- **Priority Detection**: Critical, High, Medium, Low, Very Low (1-5)
  - Keywords: "critical", "urgent", "blocking", "fix", "bug", "nice to have"
  - Section context: "Priority", "Fixes", "Future", etc.

- **Complexity Estimation**: Simple, Medium, Complex
  - Complex: architecture, refactor, migration, framework
  - Simple: add, update, fix typo, rename, document
  - Hour estimates: 1h (simple), 4h (medium), 16h (complex)

- **Category Assignment**: feature, bug, test, deployment, documentation
  - Auto-categorized based on keywords and section headers

### Milestone Generation
Creates structured milestones across phases:
- **Planning**: Documentation, setup, high-priority initialization
- **Development**: Feature implementation, bug fixes (chunked into manageable groups)
- **Testing**: Test suite creation and QA tasks
- **Deployment**: Release preparation and deployment tasks

Each milestone includes:
- Unique ID and descriptive name
- Start and target dates
- Task breakdown with priorities
- Total estimated hours
- Status tracking

## Active Projects

The worker scans these projects by default:

### architect
- **Path**: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect`
- **Description**: Dashboard with testing, deployment, migrations
- **Key Files**: TODO.md, OPERATIONS.md, app.py, .claude/plans/*.md

### claude_browser_agent
- **Path**: `/Users/jgirmay/Desktop/gitrepo/pyWork/claude_browser_agent`
- **Description**: Browser automation framework
- **Key Files**: README.md, automation.py, core/*.py

### basic_edu_apps_final
- **Path**: `/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final`
- **Description**: Educational applications suite
- **Key Files**: TODO.md, CLAUDE.md, unified_app.py

### shared_services
- **Path**: `/Users/jgirmay/Desktop/gitrepo/pyWork/shared_services`
- **Description**: Vault and centralized services
- **Key Files**: vault/*.py, deploy.sh

## Usage

### Command Line

```bash
# Run immediate scan of all projects
python3 milestone_worker.py --scan

# Scan specific project
python3 milestone_worker.py --scan --project architect

# Run as daemon (polls for tasks every 5 minutes)
python3 milestone_worker.py --daemon

# Run with custom poll interval (10 minutes)
python3 milestone_worker.py --daemon --poll-interval 600
```

### Helper Script

```bash
# Start worker as daemon
./scripts/milestone_planner.sh start

# Check worker status
./scripts/milestone_planner.sh status

# Run immediate scan
./scripts/milestone_planner.sh scan

# Scan specific project
./scripts/milestone_planner.sh scan architect

# View logs
./scripts/milestone_planner.sh logs

# Stop worker
./scripts/milestone_planner.sh stop

# Clean old milestone files (>30 days)
./scripts/milestone_planner.sh clean
```

## Output

All milestone plans are saved to `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/milestones/`

### JSON Output
Files: `{project}_milestones_{timestamp}.json`

```json
{
  "project": "architect",
  "generated_at": "2025-12-25T01:30:00",
  "total_tasks": 42,
  "total_milestones": 5,
  "milestones": [
    {
      "id": "architect_planning",
      "name": "Architect - Planning & Setup",
      "phase": "planning",
      "start_date": "2025-12-25T00:00:00",
      "target_date": "2025-12-28T00:00:00",
      "total_hours": 12.0,
      "tasks": [...]
    }
  ],
  "tasks_by_category": {
    "by_category": {"feature": 15, "bug": 10, "test": 8},
    "by_priority": {"priority_1": 5, "priority_2": 12},
    "by_complexity": {"simple": 10, "medium": 20, "complex": 12}
  }
}
```

### Markdown Summary
Files: `{project}_summary.md`

Human-readable reports with:
- Summary statistics
- Task breakdown by category and priority
- Milestone details with task lists
- Estimated hours and duration

## Dashboard Integration

The worker integrates with the Architect dashboard via the task queue API.

### Register Worker
On startup, registers with:
```json
{
  "id": "milestone-worker-abc123",
  "worker_type": "milestone",
  "capabilities": ["milestone", "planning", "project_scan"]
}
```

### Claim Tasks
Claims tasks with types: `milestone`, `planning`, `project_scan`

### Task Data Format
```json
{
  "task_type": "milestone",
  "task_data": {
    "project": "architect"  // optional, scans all if omitted
  }
}
```

### Result Format
```json
{
  "success": true,
  "projects_scanned": ["architect", "claude_browser_agent"],
  "results": {
    "architect": {
      "tasks_found": 42,
      "milestones_created": 5,
      "output_file": "/path/to/output.json",
      "summary_file": "/path/to/summary.md"
    }
  }
}
```

## Creating Dashboard Tasks

### Via API
```bash
curl -X POST http://100.112.58.92:8080/api/tasks \
  -H "Content-Type: application/json" \
  -u architect:peace5 \
  -d '{
    "task_type": "milestone",
    "task_data": {"project": "architect"},
    "priority": 2
  }'
```

### Via Python
```python
import requests

response = requests.post(
    'http://100.112.58.92:8080/api/tasks',
    auth=('architect', 'peace5'),
    json={
        'task_type': 'milestone',
        'task_data': {'project': 'architect'},
        'priority': 2
    }
)
print(response.json())
```

### Using the create_milestone_task.py script
```bash
python3 scripts/create_milestone_task.py               # Scan all projects
python3 scripts/create_milestone_task.py architect     # Scan specific project
```

## Architecture

### MilestoneScanner
Scans projects and extracts tasks:
- `scan()` - Main entry point
- `_scan_todo_files()` - Parse TODO.md files
- `_scan_plan_files()` - Parse .claude/plans/*.md
- `_scan_code_todos()` - Find code comments
- `_scan_claude_files()` - Extract from CLAUDE.md
- `_infer_priority()` - Classify priority 1-5
- `_infer_complexity()` - Classify simple/medium/complex
- `_infer_category()` - Classify feature/bug/test/etc

### MilestonePlanner
Generates milestone plans from tasks:
- `generate_milestones()` - Main planner
- `_group_tasks()` - Group by category and priority
- `_create_planning_milestone()` - Planning phase
- `_create_development_milestones()` - Dev phases (chunked)
- `_create_testing_milestone()` - Testing phase
- `_create_deployment_milestone()` - Deployment phase

### MilestoneWorker
Background daemon worker:
- `start()` - Main event loop
- `_register()` - Register with dashboard
- `_heartbeat()` - Send periodic heartbeat
- `_claim_task()` - Claim milestone tasks
- `_run_milestone_task()` - Execute task
- `_complete_task()` / `_fail_task()` - Report results

## Configuration

### Environment Variables
- `TAILSCALE_IP` - Dashboard IP (default: 100.112.58.92)
- `ARCHITECT_URL` - Dashboard URL (default: http://{TAILSCALE_IP}:8080)

### Files
- **PID**: `/tmp/architect_milestone_worker.pid`
- **Logs**: `/tmp/architect_milestone_worker.log`
- **Output**: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/milestones/`

### Worker Settings
- Default poll interval: 300 seconds (5 minutes)
- Customizable via `--poll-interval` flag

## Extending

### Add New Projects
Edit `ACTIVE_PROJECTS` in `milestone_worker.py`:

```python
ACTIVE_PROJECTS = {
    'my_project': {
        'path': PROJECT_ROOT / 'my_project',
        'description': 'My awesome project',
        'key_files': ['TODO.md', 'README.md', 'src/*.py']
    }
}
```

### Custom Task Parsers
Add scanner methods to `MilestoneScanner`:

```python
def _scan_custom_format(self) -> List[Task]:
    """Parse custom task format."""
    tasks = []
    # Your parsing logic here
    return tasks
```

### Custom Milestone Phases
Add planner methods to `MilestonePlanner`:

```python
def _create_custom_milestone(self, grouped: Dict) -> List[Milestone]:
    """Create custom milestone type."""
    # Your milestone logic here
    return milestones
```

## Troubleshooting

### Worker won't start
- Check if already running: `./scripts/milestone_planner.sh status`
- Check logs: `tail -f /tmp/architect_milestone_worker.log`
- Verify Python 3: `python3 --version`

### No tasks found
- Verify project paths exist
- Check TODO.md files have uncompleted `- [ ]` items
- Ensure plan files exist in `.claude/plans/`
- Review logs for scan errors

### Dashboard integration fails
- Verify dashboard is running: `curl http://100.112.58.92:8080/health`
- Check network connectivity to Tailscale IP
- Review worker registration logs

### Incorrect task classification
- Review keyword lists in `_infer_priority()`, `_infer_complexity()`, `_infer_category()`
- Add project-specific keywords
- Adjust section name matching

## Maintenance

### Log Rotation
Logs grow continuously. Rotate periodically:
```bash
# Manual rotation
mv /tmp/architect_milestone_worker.log /tmp/architect_milestone_worker.log.old

# Restart worker to create fresh log
./scripts/milestone_planner.sh restart
```

### Clean Old Files
Remove milestone files older than 30 days:
```bash
./scripts/milestone_planner.sh clean
```

### Update Worker
After code changes:
```bash
# Stop worker
./scripts/milestone_planner.sh stop

# Restart with new code
./scripts/milestone_planner.sh start
```

## See Also

- Architect Dashboard: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/CLAUDE.md`
- Test Worker: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/workers/test_worker.py`
- Task Queue API: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/app.py` (lines 2895-3051)
