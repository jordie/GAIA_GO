# GAIA_GO Tmux Session Grouping Implementation

## Overview

This implementation adds comprehensive tmux session management with project-based grouping to GAIA_GO. It organizes 4 concurrent projects (basic_edu, rando, architect, gaia_improvements) into logical groups for better development workflow management.

## Architecture

### Go-Native Implementation
- **Language**: Pure Go (no Python dependencies)
- **Database**: SQLite extension to `education_central.db`
- **API**: Gin HTTP routes at `/api/tmux/*`
- **Session Detection**: Real-time via `tmux list-sessions` command

## Database Schema

Three new tables created in Migration 004:

### 1. `projects` Table
Defines the 4 core project groups:

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    icon TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Seed Data**:
- `basic_edu` - 🎓 Basic Education Apps (Order 1)
- `rando` - 🎲 Rando Project (Order 2)
- `architect` - 🏗️ Architect System (Order 3)
- `gaia_improvements` - ⚡ GAIA Improvements (Order 4)

### 2. `tmux_sessions` Table
Tracks individual tmux sessions with metadata:

```sql
CREATE TABLE tmux_sessions (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    project_id INTEGER,
    environment TEXT DEFAULT 'dev',
    is_worker BOOLEAN DEFAULT 0,
    attached BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
```

**Key Fields**:
- `project_id` - Links session to a project
- `environment` - One of: dev, staging, prod
- `is_worker` - True if session is a worker/daemon
- `attached` - Synced from tmux (real-time attachment status)

### 3. `session_group_prefs` Table
Stores user UI preferences for collapsed/expanded groups:

```sql
CREATE TABLE session_group_prefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    group_id TEXT NOT NULL,
    collapsed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    UNIQUE(user_id, group_id)
);
```

## Service Layer

**Location**: `internal/tmux/`

### Models (`models.go`)
- `Project` - Project metadata
- `TmuxSession` - Individual session with metadata
- `SessionGroup` - Grouped collection of sessions
- `GroupedSessions` - Complete grouped response
- Request/Response DTOs for API endpoints

### Service (`service.go`)

**Core Methods**:

#### `GetSessionsGrouped(ctx context.Context) (*GroupedSessions, error)`
Main entry point - syncs tmux sessions and returns grouped structure:
- Calls `syncTmuxSessions()` to update database
- Fetches all sessions and projects
- Groups by project → environment → type
- Returns JSON-serializable structure

#### `syncTmuxSessions(ctx context.Context) error`
Syncs tmux list-sessions output with database:
- Executes `tmux list-sessions -F "#{session_name}"`
- Upserts new sessions to database
- Marks deleted sessions as detached
- Gracefully handles tmux server not running

#### `groupSessions(sessions []TmuxSession, projects []Project) *GroupedSessions`
Groups sessions by project with metadata:
- Creates `SessionGroup` for each project
- Groups unassigned sessions separately
- Counts attached/total per group
- Maintains project display order

#### `AutoAssignSessions(ctx context.Context) (*AutoAssignResult, error)`
Pattern-based auto-assignment with priorities:

1. **Worker Detection** (Highest Priority)
   - Detects: contains "worker", "queue", or "daemon"
   - Sets: `is_worker=true`, no project assignment

2. **Project Slug Matching**
   - Matches: `basic_edu_*`, `rando_*`, `architect_*`, `gaia_improvements_*`
   - Sets: corresponding `project_id`

3. **Environment Detection**
   - Detects: `_dev`, `_staging`, `_prod` suffix
   - Sets: corresponding `environment` field

#### Session Management Methods
- `AssignSessionToProject(ctx, sessionName, projectID)` - Manual assignment
- `SetSessionEnvironment(ctx, sessionName, environment)` - Set dev/staging/prod
- `SetSessionWorker(ctx, sessionName, isWorker)` - Mark as worker
- `ToggleGroupCollapsed(ctx, userID, groupID)` - Toggle UI state
- `SetCollapsedBulk(ctx, userID, groupIDs, collapsed)` - Bulk operations

#### Query Methods
- `GetProjects(ctx)` - List all projects
- `GetGroupPreferences(ctx, userID)` - Fetch user UI preferences
- `getAllSessions(ctx)` - Query active sessions
- `getProjects(ctx)` - Query all projects

## API Routes

**Base Path**: `/api/tmux/`

### Session Grouping
```
GET /api/tmux/groups
```
Returns grouped sessions with applied user preferences. Requires authentication to fetch preferences.

**Response**:
```json
{
  "success": true,
  "data": {
    "groups": [
      {
        "id": "project_1",
        "name": "Basic Education Apps",
        "icon": "🎓",
        "collapsed": false,
        "sessions": [...],
        "attached_count": 2,
        "total_count": 3
      }
    ],
    "total_sessions": 10,
    "total_attached": 4,
    "unassigned_count": 1
  }
}
```

### Project Management
```
GET /api/tmux/projects
```
Lists all available projects.

### Session Assignment
```
POST /api/tmux/assign
Content-Type: application/json

{
  "session_name": "basic_edu_server_dev",
  "project_id": 1
}
```

### Environment Configuration
```
POST /api/tmux/environment
Content-Type: application/json

{
  "session_name": "basic_edu_server_dev",
  "environment": "dev"  // or "staging", "prod"
}
```

### Worker Management
```
POST /api/tmux/worker
Content-Type: application/json

{
  "session_name": "worker_queue_1",
  "is_worker": true
}
```

### Group Preferences
```
POST /api/tmux/toggle/:group_id
```
Toggle collapsed state for a group (requires authentication).

```
POST /api/tmux/collapse-all
POST /api/tmux/expand-all
```
Bulk operations (require authentication).

### Auto-Assignment
```
POST /api/tmux/auto-assign
```
Run pattern-based auto-assignment on unassigned sessions.

**Response**:
```json
{
  "success": true,
  "data": {
    "success": true,
    "assigned": 8,
    "message": "Successfully auto-assigned 8 sessions"
  }
}
```

## Session Setup Script

**Location**: `scripts/setup_project_sessions.sh`

Creates test tmux sessions for all 4 projects.

### Usage

**Create all sessions**:
```bash
./scripts/setup_project_sessions.sh setup
```

**Create specific project**:
```bash
./scripts/setup_project_sessions.sh setup --project basic_edu
```

**List sessions**:
```bash
./scripts/setup_project_sessions.sh list
```

**Cleanup**:
```bash
./scripts/setup_project_sessions.sh cleanup
```

### Created Sessions

**basic_edu** (dev):
- `basic_edu_server_dev`
- `basic_edu_tests_dev`
- `basic_edu_editor_dev`

**rando** (dev):
- `rando_shell_dev`
- `rando_experiment_dev`

**architect** (prod/dev):
- `architect_dashboard_prod`
- `architect_api_dev`

**gaia_improvements** (dev/staging):
- `gaia_improvements_build_dev`
- `gaia_improvements_tests_staging`

**Workers**:
- `worker_queue_1`

## Integration with Main Server

**File**: `cmd/server/main.go`

1. **Import**:
   ```go
   "github.com/jgirmay/GAIA_GO/internal/tmux"
   ```

2. **Initialize service** (line ~35):
   ```go
   tmuxService := tmux.NewService(db)
   log.Printf("[INFO] Tmux session grouping service initialized")
   ```

3. **Register routes** (line ~53):
   ```go
   apiGroup := appRouter.GetEngine().Group("/api")
   tmux.RegisterRoutes(apiGroup, tmuxService)
   log.Printf("[INFO] Tmux session grouping routes registered")
   ```

4. **Database migration**: Automatically included in `runMigrations()`

## Implementation Details

### Thread Safety
- Uses `sync.RWMutex` for concurrent access
- Read operations acquire RLock
- Write operations (assignments, preferences) acquire Lock
- Safe for concurrent HTTP requests

### Error Handling
- Uses standard API error types from `internal/api`
- Returns appropriate HTTP status codes:
  - 200 OK - Success
  - 400 Bad Request - Invalid input
  - 401 Unauthorized - Auth required
  - 500 Internal Server Error - DB/system errors
- Graceful fallback if tmux server not running

### Graceful Degradation
If tmux is not running:
- `listTmuxSessions()` returns empty list (no error)
- API still returns cached database data
- Sync still attempts but logs warning

### Auto-Assignment Logic
Example: `basic_edu_server_dev`
1. Check if contains worker keywords → No
2. Check project slug match → `basic_edu_` matches → Set project_id=1
3. Extract environment → `_dev` suffix → Set environment="dev"
4. Result: `{project_id: 1, environment: "dev", is_worker: false}`

## Multi-Environment Support

Each environment maintains separate database:
- **dev**: `environments/dev/data/dev_gaia.db`
- **staging**: `environments/staging/data/staging_gaia.db`
- **prod**: `environments/prod/data/prod_gaia.db`

Sessions with `_dev`/`_staging`/`_prod` suffix auto-assign to respective environment field for filtering.

## Session Naming Convention

```
{project_slug}_{purpose}_{environment}
```

**Examples**:
- `basic_edu_server_dev` → Project: basic_edu, Environment: dev
- `architect_dashboard_prod` → Project: architect, Environment: prod
- `worker_queue_1` → Worker session, no project assignment
- `rando_experiment_dev` → Project: rando, Environment: dev

## Testing & Verification

### Manual Testing

1. **Start server**:
   ```bash
   go run cmd/server/main.go
   ```

2. **Create test sessions**:
   ```bash
   ./scripts/setup_project_sessions.sh setup
   ```

3. **Verify sessions created**:
   ```bash
   tmux ls
   ```

4. **Test API**:
   ```bash
   # Get grouped sessions
   curl http://localhost:8080/api/tmux/groups

   # List projects
   curl http://localhost:8080/api/tmux/projects

   # Auto-assign
   curl -X POST http://localhost:8080/api/tmux/auto-assign

   # Assign specific session
   curl -X POST http://localhost:8080/api/tmux/assign \
     -H "Content-Type: application/json" \
     -d '{"session_name": "test_session", "project_id": 1}'
   ```

5. **Verify database**:
   ```bash
   sqlite3 data/education_central.db "SELECT * FROM tmux_sessions;"
   sqlite3 data/education_central.db "SELECT * FROM projects;"
   ```

### Database Verification

Check projects are seeded:
```sql
SELECT id, slug, name, icon FROM projects;
-- Should show 4 rows with basic_edu, rando, architect, gaia_improvements
```

Check sessions are tracked:
```sql
SELECT name, project_id, environment, is_worker, attached FROM tmux_sessions;
```

## Performance Considerations

### Sync Efficiency
- Sync runs on each API call to `/api/tmux/groups`
- Executes single `tmux list-sessions` command
- Updates database with upsert queries
- Marks deleted sessions as detached (keeps history)

### Query Optimization
Indices created for common queries:
- `idx_tmux_sessions_project_id` - Filter by project
- `idx_tmux_sessions_environment` - Filter by environment
- `idx_tmux_sessions_is_worker` - Filter workers
- `idx_tmux_sessions_name` - Session name lookup
- `idx_session_group_prefs_user_id` - User preferences

### Scalability
- Supports unlimited sessions (limited by tmux)
- Supports unlimited users (database persistence)
- Group operations O(n) where n = number of projects
- Session grouping O(m) where m = number of sessions

## Security

### Authentication
- User preferences endpoints require authentication
- Uses existing `middleware.GetUserID()` pattern
- Public endpoints (list, assign) available without auth

### Authorization
- User preferences isolated by user_id
- No cross-user data leakage

### Input Validation
- Session names validated (must exist in tmux)
- Project IDs validated (must exist in projects table)
- Environment values validated (dev/staging/prod only)
- Request bodies validated with JSON schema

## Future Enhancements

Potential improvements (not in MVP):
1. Background sync service (instead of per-request)
2. WebSocket real-time updates
3. Pane/window grouping within sessions
4. Custom project creation via API
5. Session command execution
6. Session output capture
7. Tmux window/pane navigation
8. Session templates for quick setup
9. Metrics/monitoring per group
10. Session activity logging

## Files Changed

### New Files
- `internal/tmux/models.go` - Data structures
- `internal/tmux/service.go` - Business logic
- `internal/tmux/handlers.go` - API handlers
- `migrations/004_tmux_session_grouping.sql` - Schema
- `scripts/setup_project_sessions.sh` - Setup script
- `TMUX_SESSION_GROUPING.md` - This documentation

### Modified Files
- `cmd/server/main.go` - Service initialization and route registration

## Commit

Implemented in commit: `feat: implement tmux session grouping system for GAIA_GO`

Contains:
- Complete service layer with all business logic
- Full API implementation with all endpoints
- Database migration with seed data
- Session setup script with multiple commands
- Server integration and route registration
- Comprehensive documentation

## Summary

The GAIA_GO Tmux Session Grouping system provides:

✅ Project-based session organization
✅ Real-time tmux sync
✅ Pattern-based auto-assignment
✅ User preference persistence
✅ RESTful API for management
✅ Setup script for quick testing
✅ Thread-safe concurrent access
✅ Graceful error handling
✅ Multi-environment support
✅ Production-ready implementation

The system is ready for deployment and can be extended with additional features as needed.
