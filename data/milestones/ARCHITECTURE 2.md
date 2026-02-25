# Milestone Planning System - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Milestone Planning System                     │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────┐
│   User Interface     │         │  Architect Dashboard │
│                      │         │   (port 8080)        │
│  - CLI Commands      │◄───────►│                      │
│  - Helper Scripts    │  HTTP   │  - Task Queue        │
│  - Dashboard UI      │  API    │  - Worker Registry   │
└──────────────────────┘         │  - Web Interface     │
                                 └──────────────────────┘
                                           │
                                           │ Claims Tasks
                                           ▼
                        ┌──────────────────────────────────┐
                        │   Milestone Worker (Daemon)      │
                        │                                  │
                        │  - Task Claiming                 │
                        │  - Heartbeat                     │
                        │  - Result Reporting              │
                        └──────────────────────────────────┘
                                           │
                                           │ Scans
                                           ▼
                        ┌──────────────────────────────────┐
                        │      MilestoneScanner            │
                        │                                  │
                        │  Reads from:                     │
                        │  ├─ TODO.md files                │
                        │  ├─ .claude/plans/*.md           │
                        │  ├─ Python code (TODO comments)  │
                        │  └─ CLAUDE.md files              │
                        └──────────────────────────────────┘
                                           │
                                           │ Extracts Tasks
                                           ▼
                        ┌──────────────────────────────────┐
                        │    Task Classification           │
                        │                                  │
                        │  - Priority (1-5)                │
                        │  - Complexity (S/M/C)            │
                        │  - Category (Feature/Bug/...)    │
                        │  - Hour Estimation               │
                        └──────────────────────────────────┘
                                           │
                                           │ Classified Tasks
                                           ▼
                        ┌──────────────────────────────────┐
                        │     MilestonePlanner             │
                        │                                  │
                        │  Generates Phases:               │
                        │  ├─ Planning                     │
                        │  ├─ Development (chunked)        │
                        │  ├─ Testing                      │
                        │  └─ Deployment                   │
                        └──────────────────────────────────┘
                                           │
                                           │ Milestone Plans
                                           ▼
                        ┌──────────────────────────────────┐
                        │      Output Generation           │
                        │                                  │
                        │  Formats:                        │
                        │  ├─ JSON (structured data)       │
                        │  └─ Markdown (readable report)   │
                        └──────────────────────────────────┘
                                           │
                                           │ Saves to
                                           ▼
                        ┌──────────────────────────────────┐
                        │   data/milestones/               │
                        │                                  │
                        │  - {project}_milestones_*.json   │
                        │  - {project}_summary.md          │
                        │  - README.md                     │
                        └──────────────────────────────────┘
```

## Data Flow

```
┌─────────────┐
│   Trigger   │
│             │
│ Manual Scan │
│ Dashboard   │
│ Task Queue  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                    Project Scanning                      │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │   TODO.md  │  │ Plans/*.md │  │ Code TODOs │       │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘       │
│         │               │               │              │
│         └───────────────┴───────────────┘              │
│                         │                               │
│                         ▼                               │
│                  ┌─────────────┐                       │
│                  │ Parse Lines │                       │
│                  └──────┬──────┘                       │
│                         │                               │
│                         ▼                               │
│                  ┌─────────────┐                       │
│                  │Extract Items│                       │
│                  └──────┬──────┘                       │
│                         │                               │
└─────────────────────────┼───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 Task Classification                      │
│                                                          │
│  Input: Raw task text + context                         │
│  Output: Structured Task object                         │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Priority   │  │  Complexity  │  │   Category   │ │
│  │   Detection  │  │  Estimation  │  │  Assignment  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │          │
│         │ Keywords        │ Keywords        │ Keywords │
│         │ Context         │ Context         │ Context  │
│         │                 │                 │          │
│         └─────────────────┴─────────────────┘          │
│                           │                             │
│                           ▼                             │
│                  ┌─────────────────┐                   │
│                  │  Task Object    │                   │
│                  │  - title        │                   │
│                  │  - priority     │                   │
│                  │  - complexity   │                   │
│                  │  - category     │                   │
│                  │  - hours        │                   │
│                  └─────────┬───────┘                   │
└──────────────────────────┼─────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Milestone Planning                      │
│                                                          │
│  Input: List of Task objects                            │
│  Output: Milestone objects with task assignments        │
│                                                          │
│  Step 1: Group by Category                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │Features │ │  Bugs   │ │  Tests  │ │ Deploy  │     │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘     │
│       │           │           │           │           │
│  Step 2: Sort by Priority                              │
│       │           │           │           │           │
│       ▼           ▼           ▼           ▼           │
│  ┌────────────────────────────────────────────────┐   │
│  │         Prioritized Task Lists                 │   │
│  └────────────────────────────────────────────────┘   │
│                           │                            │
│  Step 3: Create Milestone Phases                      │
│                           │                            │
│       ┌───────────────────┼───────────────────┐       │
│       │                   │                   │       │
│       ▼                   ▼                   ▼       │
│  ┌─────────┐       ┌─────────┐       ┌─────────┐    │
│  │Planning │       │  Dev    │       │Testing/ │    │
│  │Phase    │───────│Phases   │───────│Deploy   │    │
│  │         │       │(chunked)│       │Phases   │    │
│  └─────────┘       └─────────┘       └─────────┘    │
│                                                       │
│  Each Milestone Contains:                            │
│  - ID, Name, Description                             │
│  - Phase (planning/dev/test/deploy)                  │
│  - Start/Target Dates                                │
│  - Task List                                         │
│  - Total Hours                                       │
│  - Status                                            │
└──────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Output Generation                      │
│                                                          │
│  ┌──────────────────┐        ┌──────────────────┐      │
│  │  JSON Format     │        │ Markdown Format  │      │
│  │                  │        │                  │      │
│  │ - Full data      │        │ - Summary stats  │      │
│  │ - All fields     │        │ - Task lists     │      │
│  │ - Categorization │        │ - Readable       │      │
│  │ - Machine        │        │ - Human          │      │
│  │   readable       │        │   readable       │      │
│  └────────┬─────────┘        └────────┬─────────┘      │
│           │                           │                 │
│           ▼                           ▼                 │
│  {project}_milestones.json   {project}_summary.md      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Component Architecture

```
milestone_worker.py
├── Task (dataclass)
│   ├── title: str
│   ├── description: str
│   ├── priority: int (1-5)
│   ├── complexity: str (simple/medium/complex)
│   ├── estimated_hours: float
│   ├── category: str
│   ├── dependencies: List[str]
│   ├── source_file: str
│   └── line_number: int
│
├── Milestone (dataclass)
│   ├── id: str
│   ├── name: str
│   ├── description: str
│   ├── phase: str (planning/development/testing/deployment)
│   ├── start_date: str (ISO)
│   ├── target_date: str (ISO)
│   ├── tasks: List[Task]
│   ├── total_hours: float
│   └── status: str (pending/in_progress/completed)
│
├── MilestoneScanner
│   ├── __init__(project_config)
│   ├── scan() → List[Task]
│   ├── _scan_todo_files() → List[Task]
│   ├── _scan_plan_files() → List[Task]
│   ├── _scan_code_todos() → List[Task]
│   ├── _scan_claude_files() → List[Task]
│   ├── _parse_todo_content(content) → List[Task]
│   ├── _parse_plan_content(content) → List[Task]
│   ├── _infer_priority(text, section) → int
│   ├── _infer_complexity(text) → str
│   ├── _infer_category(text, section) → str
│   └── _estimate_hours(complexity) → float
│
├── MilestonePlanner
│   ├── __init__(project_name)
│   ├── generate_milestones(tasks) → List[Milestone]
│   ├── _group_tasks(tasks) → Dict[str, List[Task]]
│   ├── _create_planning_milestone(grouped) → List[Milestone]
│   ├── _create_development_milestones(grouped) → List[Milestone]
│   ├── _create_testing_milestone(grouped) → List[Milestone]
│   └── _create_deployment_milestone(grouped) → List[Milestone]
│
└── MilestoneWorker
    ├── __init__(worker_id, poll_interval)
    ├── start() → void
    ├── stop() → void
    ├── _register() → void
    ├── _heartbeat() → void
    ├── _claim_task() → Optional[Dict]
    ├── _run_milestone_task(task) → Dict
    ├── _complete_task(task_id, result) → void
    ├── _fail_task(task_id, error) → void
    ├── _categorize_tasks(tasks) → Dict
    └── _generate_summary_report(name, milestones, tasks, file) → void
```

## File System Layout

```
architect/
├── workers/
│   ├── milestone_worker.py          # Main worker (863 lines)
│   ├── MILESTONE_WORKER.md          # Full documentation
│   └── QUICKSTART_MILESTONE.md      # Quick start guide
│
├── scripts/
│   ├── milestone_planner.sh         # Management script
│   ├── create_milestone_task.py     # Task creator
│   ├── milestone-worker.service     # systemd service
│   └── install_milestone_service.sh # Service installer
│
├── data/
│   └── milestones/
│       ├── README.md                # Output documentation
│       ├── {project}_milestones_{timestamp}.json
│       └── {project}_summary.md
│
├── MILESTONE_PLANNING.md            # System overview
└── IMPLEMENTATION_SUMMARY.md        # Implementation details
```

## Classification Logic

```
┌─────────────────────────────────────────────────────────┐
│                  Priority Detection                      │
│                                                          │
│  Text + Section Context                                 │
│          │                                               │
│          ▼                                               │
│  ┌─────────────────────────────────────┐               │
│  │  Keyword Matching                   │               │
│  │                                      │               │
│  │  Priority 1 (Critical)               │               │
│  │  - critical, urgent, blocking, asap  │               │
│  │  - "Priority" section                │               │
│  │                                      │               │
│  │  Priority 2 (High)                   │               │
│  │  - important, fix, bug, error        │               │
│  │  - "Fix/Bug" section                 │               │
│  │                                      │               │
│  │  Priority 3 (Medium) - DEFAULT       │               │
│  │                                      │               │
│  │  Priority 4 (Low)                    │               │
│  │  - nice to have, wish, future        │               │
│  │  - "Future" section                  │               │
│  │                                      │               │
│  │  Priority 5 (Very Low)               │               │
│  │  - maybe, optional                   │               │
│  └──────────────┬──────────────────────┘               │
│                 │                                        │
│                 ▼                                        │
│            Priority: 1-5                                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                Complexity Estimation                     │
│                                                          │
│  Task Text                                               │
│      │                                                   │
│      ▼                                                   │
│  ┌──────────────────────────────────┐                  │
│  │ Keyword Analysis                 │                  │
│  │                                  │                  │
│  │ Complex (16 hours):              │                  │
│  │ - architecture                   │                  │
│  │ - refactor                       │                  │
│  │ - migration                      │                  │
│  │ - framework                      │                  │
│  │ - integration                    │                  │
│  │ - system, redesign, rebuild      │                  │
│  │                                  │                  │
│  │ Simple (1 hour):                 │                  │
│  │ - add, update                    │                  │
│  │ - fix typo, rename               │                  │
│  │ - document, comment              │                  │
│  │                                  │                  │
│  │ Medium (4 hours): DEFAULT        │                  │
│  └────────────┬─────────────────────┘                  │
│               │                                         │
│               ▼                                         │
│    Complexity: simple/medium/complex                    │
│    Hours: 1 / 4 / 16                                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  Category Assignment                     │
│                                                          │
│  Task Text + Section                                     │
│      │                                                   │
│      ▼                                                   │
│  ┌──────────────────────────────────┐                  │
│  │ Category Matching                │                  │
│  │                                  │                  │
│  │ Test:                            │                  │
│  │ - test, testing, verify          │                  │
│  │                                  │                  │
│  │ Deployment:                      │                  │
│  │ - deploy, deployment, release    │                  │
│  │                                  │                  │
│  │ Documentation:                   │                  │
│  │ - document, docs, readme         │                  │
│  │                                  │                  │
│  │ Bug:                             │                  │
│  │ - fix, bug, error, issue         │                  │
│  │                                  │                  │
│  │ Feature: DEFAULT                 │                  │
│  └────────────┬─────────────────────┘                  │
│               │                                         │
│               ▼                                         │
│    Category: feature/bug/test/deployment/documentation  │
└─────────────────────────────────────────────────────────┘
```

## Integration Flow

```
┌──────────────────────────────────────────────────────────┐
│              Dashboard Integration Flow                   │
└──────────────────────────────────────────────────────────┘

1. Worker Startup
   │
   ├─> Register with Dashboard
   │   POST /api/workers/register
   │   {
   │     "id": "milestone-worker-abc123",
   │     "worker_type": "milestone",
   │     "capabilities": ["milestone", "planning", "project_scan"]
   │   }
   │
   └─> Enter Main Loop

2. Polling Loop (every 5 minutes)
   │
   ├─> Send Heartbeat
   │   POST /api/workers/{id}/heartbeat
   │   {
   │     "status": "idle" | "busy",
   │     "current_task_id": null | 123
   │   }
   │
   └─> Claim Task
       POST /api/tasks/claim
       {
         "worker_id": "milestone-worker-abc123",
         "task_types": ["milestone", "planning", "project_scan"]
       }
       │
       ├─> No Task Available
       │   └─> Sleep 5 minutes, repeat
       │
       └─> Task Claimed
           │
           ├─> Execute Task
           │   ├─> Scan Projects
           │   ├─> Generate Milestones
           │   └─> Save Output
           │
           ├─> Success
           │   POST /api/tasks/{id}/complete
           │   {
           │     "worker_id": "milestone-worker-abc123",
           │     "result": {
           │       "success": true,
           │       "projects_scanned": [...],
           │       "results": {...}
           │     }
           │   }
           │
           └─> Failure
               POST /api/tasks/{id}/fail
               {
                 "worker_id": "milestone-worker-abc123",
                 "error": "Error message..."
               }
```

## Execution Timeline

```
Time    Event
────────────────────────────────────────────────────────
00:00   Worker starts
00:00   Register with dashboard
00:00   First heartbeat
00:00   Claim task (none available)
00:00   Sleep 300s

05:00   Heartbeat
05:00   Claim task (milestone task available!)
05:00   ├─> Start scanning architect
05:01   ├─> Found 41 tasks
05:01   ├─> Generate 7 milestones
05:01   ├─> Save JSON and markdown
05:01   └─> Report complete
05:01   Sleep 300s

10:00   Heartbeat
10:00   Claim task (none available)
10:00   Sleep 300s

...continues indefinitely...
```

## Error Handling

```
┌─────────────────────────────────────────────────────────┐
│                    Error Handling                        │
└─────────────────────────────────────────────────────────┘

Task Execution
    │
    ├─> Try: Execute Task
    │   ├─> Scan Projects
    │   │   └─> Try/Catch: Log warnings for unreadable files
    │   │
    │   ├─> Generate Milestones
    │   │   └─> Validate: Skip empty task lists
    │   │
    │   └─> Save Output
    │       └─> Try/Catch: Create directory if needed
    │
    ├─> Success
    │   └─> Report to dashboard
    │
    └─> Failure
        ├─> Log error with stack trace
        ├─> Report failure to dashboard
        └─> Continue polling (don't crash)

Dashboard Connection Errors
    │
    ├─> Register: Catch, log warning, continue
    ├─> Heartbeat: Catch, ignore (silent)
    ├─> Claim: Catch, log debug, return None
    └─> Complete/Fail: Catch, log error

Signal Handling
    │
    ├─> SIGTERM: Graceful shutdown
    ├─> SIGINT: Graceful shutdown
    └─> Set _running = False, exit main loop
```

## Performance Characteristics

```
┌─────────────────────────────────────────────────────────┐
│                  Performance Metrics                     │
└─────────────────────────────────────────────────────────┘

Project Scanning:
- architect: ~33ms (41 tasks)
- claude_browser_agent: ~14ms (42 tasks)
- basic_edu_apps_final: ~390ms (1,213 tasks)
- mentor_v2: ~836ms (56 tasks)

Total Scan Time: ~1.3 seconds for all projects

Memory Usage:
- Worker process: ~25MB resident
- Peak during scan: ~40MB

Output Files:
- JSON: 20KB - 224KB per project
- Markdown: 3KB - 38KB per project
- Total: ~350KB for all projects

Poll Interval: 300 seconds (5 minutes)
CPU Usage: <1% (mostly idle)
```

This architecture provides a robust, scalable solution for automated milestone planning across multiple projects.
