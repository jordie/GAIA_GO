# Browser Automation Project Management System

Complete system for managing projects using Comet tab groups + Google Sheets + Perplexity AI.

## Architecture

```
Comet Browser (Tab Groups)
    ↓
Extension API (Read tab groups, tabs)
    ↓
Project Database (Projects → Tab Groups → Tabs)
    ↓
Google Sheets (Progress tracking)
    ↓
Google Docs (Detailed findings)
```

## Components

### 1. Project Manager (`project_manager.py`)
- **Projects**: Top-level organization (e.g., "Ethiopia Trip")
- **Tab Groups**: Tasks within project (e.g., "Tickets", "Hotels")
- **Tabs**: Individual research items
- **Templates**: Reusable project structures

### 2. Google Sheets Sync (`google_sheets_sync.py`)
- Syncs project data to Google Sheets
- Auto-updates progress, status, notes
- Creates formatted sheets with headers
- Shareable tracking dashboard

### 3. Project Orchestrator (`project_orchestrator.py`)
- Imports Comet tab groups into projects
- Syncs data to Google Sheets
- Monitors progress automatically
- Cleanup and organization tools

### 4. Browser CLI (`browser_cli.py`)
- Interactive command-line interface
- Integrates with all components
- Session management
- Perplexity conversation tracking

## Setup

### 1. Install Dependencies

```bash
pip install gspread google-auth google-auth-oauthlib google-auth-httplib2
```

### 2. Google Sheets API Setup

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable **Google Sheets API** and **Google Drive API**
4. Create **Service Account** credentials
5. Download JSON credentials
6. Save as `google_credentials.json` in this directory
7. Share your Google Sheets with the service account email

### 3. Create Project Template

```python
from project_manager import ProjectManager

pm = ProjectManager()

# Create travel planning template
pm.create_template(
    "travel-planning",
    "Template for trip planning",
    tab_groups=[
        {"name": "Tickets", "description": "Flights", "color": "blue"},
        {"name": "Hotels", "description": "Accommodation", "color": "green"},
        {"name": "Activities", "description": "Things to do", "color": "yellow"},
        {"name": "Logistics", "description": "Transport", "color": "red"}
    ],
    sheet_columns=["Task", "Status", "Progress", "Notes", "Links", "Cost"]
)
```

## Usage

### Interactive CLI

```bash
./browser_cli.py
```

**Commands:**
```
> open aquatechswim.com                # Open URL
> ask Check swim class prices          # Ask Perplexity
> library                               # Open Perplexity library
> save session trip-planning            # Save session
> sessions                              # List all sessions
> quit                                  # Exit
```

### Import Existing Tab Groups

```bash
python3 project_orchestrator.py

# Interactive mode:
# 1. Shows all your Comet tab groups
# 2. Import to a project
# 3. Sync to Google Sheets
```

### Create Project from Template

```python
from project_manager import ProjectManager

pm = ProjectManager()

# Create Ethiopia trip from template
project_id = pm.create_project_from_template(
    "ethiopia-trip",
    "travel-planning"
)

# View project
project = pm.get_project("ethiopia-trip")
print(project)
```

### Sync to Google Sheets

```python
from project_orchestrator import ProjectOrchestrator
import asyncio

async def sync():
    orch = ProjectOrchestrator()
    await orch.connect()

    # Import current tab groups
    await orch.import_tab_groups_to_project("ethiopia-trip")

    # Sync to Google Sheets
    sheet_url = await orch.sync_project_to_sheets("ethiopia-trip")
    print(f"Tracking sheet: {sheet_url}")

asyncio.run(sync())
```

### Monitor Project Progress

```python
# Auto-sync every 60 seconds
await orch.monitor_project_progress("ethiopia-trip", interval=60)
```

## Example Workflow: Ethiopia Trip

### 1. Create Project Structure

```bash
python3 -c "
from project_manager import ProjectManager
pm = ProjectManager()
pm.create_project_from_template('ethiopia-trip', 'travel-planning')
"
```

### 2. Organize Browser Tab Groups

In Comet:
- Create tab group "Tickets" (blue)
  - kayak.com flight search
  - ethiopian airlines
  - google flights

- Create tab group "Hotels" (green)
  - booking.com Addis
  - hotel reviews

- Create tab group "Activities" (yellow)
  - things to do Addis
  - tour companies

- Create tab group "Logistics" (red)
  - visa requirements
  - travel insurance
  - vaccinations

### 3. Import to Project

```bash
python3 project_orchestrator.py

# Choose: Import all groups to project
# Name: ethiopia-trip
```

### 4. Extract Data with Perplexity

```bash
./browser_cli.py

> open kayak.com
> ask Find cheapest flights to Addis Ababa in March 2026, return as table

> open booking.com
> ask Find top 5 rated hotels in Addis under $100/night, return as table

# Data automatically tracked in project
```

### 5. Sync to Google Sheets

```bash
python3 -c "
import asyncio
from project_orchestrator import ProjectOrchestrator

async def sync():
    orch = ProjectOrchestrator()
    await orch.connect()
    await orch.sync_project_to_sheets('ethiopia-trip')

asyncio.run(sync())
"
```

### 6. View Progress Dashboard

Google Sheet shows:
| Task | Status | Progress | Notes | Links | Updated |
|------|--------|----------|-------|-------|---------|
| Tickets | in_progress | 60% | Found 3 options | kayak.com, ethiopian.com | 2026-02-13 |
| Hotels | pending | 20% | Researching | booking.com | 2026-02-13 |
| Activities | not_started | 0% | | | |
| Logistics | in_progress | 80% | Visa done | | 2026-02-13 |

## Advanced Features

### Custom Templates

```python
pm.create_template(
    "software-launch",
    "Product launch template",
    tab_groups=[
        {"name": "Development", "color": "blue"},
        {"name": "Marketing", "color": "green"},
        {"name": "Sales", "color": "yellow"},
        {"name": "Support", "color": "red"}
    ],
    sheet_columns=["Milestone", "Owner", "Status", "Due Date", "Notes"]
)
```

### Auto-Update on Tab Changes

The system can monitor tab group changes and auto-sync to Google Sheets:

```python
# Monitor continuously
await orch.monitor_project_progress("ethiopia-trip", interval=60)
```

### Multi-Project Management

```python
# List all projects
projects = pm.list_projects()

for p in projects:
    print(f"{p['name']}: {p['avg_progress']}% complete")
```

## Database Schema

```sql
projects
├── tab_groups
│   └── tabs
│       └── extracted_data
└── sync_log

templates
└── tab_group_schema
```

## Benefits

✓ **Organize chaos** - Clean up messy tab groups
✓ **Track progress** - Visual dashboard in Google Sheets
✓ **Collaborate** - Share sheets with team
✓ **Automate research** - Perplexity extracts data
✓ **Templated workflows** - Reuse proven structures
✓ **Multi-project** - Manage many projects simultaneously
✓ **Historical tracking** - Database keeps full history

## Next Steps

1. Install dependencies
2. Set up Google Sheets API
3. Create your first template
4. Import existing tab groups
5. Start tracking projects!
