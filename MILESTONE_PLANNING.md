# Milestone Planning System

Automated milestone planning for the Architect dashboard.

## Overview

The Milestone Planning Worker automates project planning by scanning active projects, extracting work items, and generating structured milestone plans with multi-day development phases.

### Key Features

- Automated task discovery from TODO files, plan files, and code comments
- Intelligent priority, complexity, and category classification
- Multi-day development phase planning
- JSON and markdown output formats
- Integration with Architect dashboard task queue
- Daemon mode with configurable polling
- Per-project or global scanning

### Statistics (2025-12-25)

Latest scan across all active projects:

| Project | Tasks | Milestones | Est. Hours | Duration |
|---------|-------|------------|------------|----------|
| architect | 41 | 7 | 122 | 6.5 days |
| claude_browser_agent | 42 | 7 | 124 | 6.5 days |
| basic_edu_apps_final | 1,213 | 38 | 1,455 | 20 days |
| mentor_v2 | 56 | 8 | 136 | 7 days |
| **Total** | **1,352** | **60** | **1,837** | **40 days** |

## Quick Start

```bash
# Run immediate scan
./scripts/milestone_planner.sh scan

# View results
cat data/milestones/architect_summary.md

# Start daemon
./scripts/milestone_planner.sh start

# Create dashboard task
python3 scripts/create_milestone_task.py architect
```

## Files Created

### Core Worker
- **`workers/milestone_worker.py`** - Main worker daemon (863 lines)
  - MilestoneScanner class - Scans projects and extracts tasks
  - MilestonePlanner class - Generates milestone plans from tasks
  - MilestoneWorker class - Background daemon with dashboard integration

### Helper Scripts
- **`scripts/milestone_planner.sh`** - Management script (171 lines)
  - start/stop/status/restart commands
  - Immediate scan triggers
  - Log viewing
  - Cleanup utilities

- **`scripts/create_milestone_task.py`** - Task creator (78 lines)
  - Creates milestone tasks in dashboard queue
  - Project filtering
  - Priority setting

### Service Files
- **`scripts/milestone-worker.service`** - systemd service definition
- **`scripts/install_milestone_service.sh`** - Service installer

### Documentation
- **`workers/MILESTONE_WORKER.md`** - Complete documentation (515 lines)
- **`workers/QUICKSTART_MILESTONE.md`** - Quick start guide (310 lines)
- **`data/milestones/README.md`** - Output directory documentation (235 lines)

### Total: 2,172 lines of code and documentation

## Architecture

### Task Discovery Pipeline

```
Project Directory
    ├─> TODO.md files          → Parse checkbox items
    ├─> .claude/plans/*.md     → Parse action items
    ├─> Code (*.py)            → Find TODO/FIXME comments
    └─> CLAUDE.md              → Extract known issues
                ↓
        Task Classification
            ├─> Priority (1-5)
            ├─> Complexity (simple/medium/complex)
            ├─> Category (feature/bug/test/deployment/doc)
            └─> Estimated Hours
                ↓
        Milestone Planning
            ├─> Planning Phase
            ├─> Development Phases (chunked)
            ├─> Testing Phase
            └─> Deployment Phase
                ↓
        Output Generation
            ├─> JSON (full data)
            └─> Markdown (summary)
```

### Data Flow

```
1. Manual Trigger or Dashboard Task
        ↓
2. Worker Claims Task
        ↓
3. Scan Project(s)
        ├─> Read TODO files
        ├─> Parse plan files
        ├─> Extract code TODOs
        └─> Process CLAUDE.md
        ↓
4. Generate Milestones
        ├─> Group by category
        ├─> Prioritize tasks
        └─> Organize into phases
        ↓
5. Save Output
        ├─> data/milestones/{project}_milestones_{ts}.json
        └─> data/milestones/{project}_summary.md
        ↓
6. Report Results to Dashboard
```

## Active Projects

### Configured for Scanning

1. **architect** - Dashboard with testing, deployment, migrations
   - `/Users/jgirmay/Desktop/gitrepo/pyWork/architect`
   - Key Files: TODO.md, OPERATIONS.md, app.py, .claude/plans/*.md

2. **claude_browser_agent** - Browser automation framework
   - `/Users/jgirmay/Desktop/gitrepo/pyWork/claude_browser_agent`
   - Key Files: README.md, automation.py, core/*.py

3. **basic_edu_apps_final** - Educational applications suite
   - `/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final`
   - Key Files: TODO.md, CLAUDE.md, unified_app.py

4. **mentor_v2** - Mentor application v2
   - `/Users/jgirmay/Desktop/gitrepo/pyWork/mentor_v2`
   - Key Files: TODO.md, CLAUDE.md, *.py, templates/*.html

### Adding New Projects

Edit `workers/milestone_worker.py`:

```python
ACTIVE_PROJECTS = {
    'new_project': {
        'path': PROJECT_ROOT / 'new_project',
        'description': 'Project description',
        'key_files': ['TODO.md', 'README.md', 'src/*.py']
    }
}
```

## Output Format

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
      "description": "Initial planning, documentation, and project setup",
      "phase": "planning",
      "start_date": "2025-12-25T00:00:00",
      "target_date": "2025-12-28T00:00:00",
      "total_hours": 12.0,
      "status": "pending",
      "tasks": [
        {
          "title": "Create migration system",
          "description": "Create migration system",
          "priority": 3,
          "complexity": "complex",
          "estimated_hours": 16.0,
          "category": "feature",
          "dependencies": [],
          "source_file": "/path/to/TODO.md",
          "line_number": 42
        }
      ]
    }
  ],
  "tasks_by_category": {
    "by_category": {"feature": 33, "bug": 1, "test": 6, "deployment": 1},
    "by_priority": {"priority_2": 1, "priority_3": 40},
    "by_complexity": {"simple": 15, "medium": 20, "complex": 6}
  }
}
```

### Markdown Summary

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

### By Priority
- Priority 2: 1
- Priority 3: 40

## Milestones

### 1. Architect - Planning & Setup
- Phase: Planning
- Start: 2025-12-25
- Target: 2025-12-28
- Tasks: 5
- Estimated Hours: 12.0

**Tasks:**
- [C] Create migration system
- [M] Create race view HTML structure
...
```

## Usage Guide

### Command Line

```bash
# Immediate scan
python3 workers/milestone_worker.py --scan                 # All projects
python3 workers/milestone_worker.py --scan --project arch  # Specific project

# Daemon mode
python3 workers/milestone_worker.py --daemon               # Default 5 min poll
python3 workers/milestone_worker.py --daemon --poll-interval 600  # 10 min poll
```

### Helper Script

```bash
./scripts/milestone_planner.sh start      # Start daemon
./scripts/milestone_planner.sh stop       # Stop daemon
./scripts/milestone_planner.sh status     # Check status
./scripts/milestone_planner.sh restart    # Restart
./scripts/milestone_planner.sh scan       # Scan all now
./scripts/milestone_planner.sh scan arch  # Scan specific
./scripts/milestone_planner.sh logs       # Tail logs
./scripts/milestone_planner.sh clean      # Clean old files
```

### Dashboard Integration

```bash
# Create task for all projects
python3 scripts/create_milestone_task.py

# Create task for specific project
python3 scripts/create_milestone_task.py architect

# High priority
python3 scripts/create_milestone_task.py --priority 1

# Via API
curl -X POST http://100.112.58.92:8080/api/tasks \
  -u architect:peace5 \
  -H "Content-Type: application/json" \
  -d '{"task_type":"milestone","task_data":{"project":"architect"},"priority":2}'
```

## Classification Rules

### Priority Detection (1-5)

| Priority | Keywords | Context |
|----------|----------|---------|
| 1 (Critical) | critical, urgent, blocking, asap | Priority section |
| 2 (High) | important, fix, bug, error | Fix/Bug section |
| 3 (Medium) | (default) | General tasks |
| 4 (Low) | nice to have, wish, future | Future section |
| 5 (Very Low) | maybe, optional | Optional items |

### Complexity Estimation

| Complexity | Hours | Keywords |
|------------|-------|----------|
| Complex | 16 | architecture, refactor, migration, framework, integration, system, redesign |
| Medium | 4 | (default) |
| Simple | 1 | add, update, fix typo, rename, document, comment |

### Category Assignment

| Category | Keywords |
|----------|----------|
| Test | test, testing, verify |
| Deployment | deploy, deployment, release |
| Documentation | document, docs, readme |
| Bug | fix, bug, error, issue |
| Feature | (default) |

## Milestone Phases

### Planning Phase
- Documentation and specification tasks
- Project setup and initialization
- High-priority setup items
- Duration: 3-7 days

### Development Phases
- Feature implementation (10 tasks per chunk)
- Bug fixes (top 15)
- Code enhancements
- Duration: 7-20 days per phase

### Testing Phase
- Test suite creation (top 10 test tasks)
- QA and verification
- Test infrastructure
- Duration: 5-7 days

### Deployment Phase
- Release preparation
- Deployment scripts
- Production configuration
- Duration: 3-5 days

## Monitoring and Maintenance

### Logs

```bash
# Real-time logs
tail -f /tmp/architect_milestone_worker.log

# Recent activity
tail -50 /tmp/architect_milestone_worker.log

# Search for errors
grep ERROR /tmp/architect_milestone_worker.log
```

### Worker Status

```bash
# Check if running
./scripts/milestone_planner.sh status

# Or manually
ps aux | grep milestone_worker

# Check PID file
cat /tmp/architect_milestone_worker.pid
```

### Output Files

```bash
# List all milestone files
ls -lht data/milestones/

# Count files
ls data/milestones/*.json | wc -l

# Check disk usage
du -sh data/milestones/
```

### Cleanup

```bash
# Remove files older than 30 days
./scripts/milestone_planner.sh clean

# Manual cleanup
find data/milestones/ -name "*.json" -mtime +30 -delete
find data/milestones/ -name "*.md" -mtime +30 ! -name "README.md" -delete
```

## Integration Points

### Architect Dashboard

The worker integrates with these dashboard APIs:

- `POST /api/workers/register` - Register worker on startup
- `POST /api/workers/{id}/heartbeat` - Periodic heartbeat
- `POST /api/tasks/claim` - Claim milestone tasks
- `POST /api/tasks/{id}/complete` - Report success
- `POST /api/tasks/{id}/fail` - Report failure

### Task Data Format

```json
{
  "task_type": "milestone",
  "task_data": {
    "project": "architect"  // optional
  },
  "priority": 2
}
```

### Result Format

```json
{
  "success": true,
  "projects_scanned": ["architect", "claude_browser_agent"],
  "results": {
    "architect": {
      "tasks_found": 41,
      "milestones_created": 7,
      "output_file": "/path/to/architect_milestones_*.json",
      "summary_file": "/path/to/architect_summary.md"
    }
  }
}
```

## Production Deployment

### systemd Service

```bash
# Install service
sudo ./scripts/install_milestone_service.sh

# Start service
sudo systemctl start milestone-worker

# Enable on boot
sudo systemctl enable milestone-worker

# Check status
sudo systemctl status milestone-worker

# View logs
journalctl -u milestone-worker -f
```

### Environment Variables

```bash
export TAILSCALE_IP=100.112.58.92
export ARCHITECT_URL=http://100.112.58.92:8080
```

## Troubleshooting

### Worker won't start
```bash
# Check for existing process
ps aux | grep milestone_worker

# Remove stale PID
rm /tmp/architect_milestone_worker.pid

# Check logs
tail -50 /tmp/architect_milestone_worker.log

# Verify Python 3
python3 --version
```

### No tasks found
```bash
# Verify project paths
ls -la /Users/jgirmay/Desktop/gitrepo/pyWork/architect/

# Check TODO files exist
find /path/to/project -name "TODO.md"

# Review scanner logs
grep "Scanning project" /tmp/architect_milestone_worker.log
```

### Dashboard connection fails
```bash
# Test dashboard connectivity
curl http://100.112.58.92:8080/health

# Verify environment
echo $ARCHITECT_URL

# Test with custom URL
ARCHITECT_URL=http://localhost:8080 ./scripts/milestone_planner.sh scan
```

### Incorrect classification
- Review classification rules in `workers/milestone_worker.py`
- Check keyword lists in `_infer_priority()`, `_infer_complexity()`, `_infer_category()`
- Add project-specific keywords
- Adjust section name matching

## Future Enhancements

Potential improvements to consider:

1. **Dependency Detection** - Parse task dependencies from descriptions
2. **Resource Estimation** - Track which developers have skills for tasks
3. **Progress Tracking** - Integrate with git commits and PR status
4. **Smart Scheduling** - Account for developer availability and velocity
5. **Milestone Templates** - Predefined milestone structures for common project types
6. **Historical Analysis** - Learn from past estimates to improve accuracy
7. **Dashboard UI** - Visual milestone timeline in Architect dashboard
8. **Notifications** - Alert when milestones are at risk or completed
9. **API Extensions** - REST API for external tools to query milestones
10. **Custom Parsers** - Plugin system for project-specific task formats

## See Also

- Architect Dashboard: `CLAUDE.md`
- Test Worker: `workers/test_worker.py`
- Task Worker: `workers/task_worker.py`
- Operations Guide: `OPERATIONS.md`

## Support

For issues or questions:
1. Check logs: `/tmp/architect_milestone_worker.log`
2. Review documentation: `workers/MILESTONE_WORKER.md`
3. Try quick start guide: `workers/QUICKSTART_MILESTONE.md`
4. Check output README: `data/milestones/README.md`
