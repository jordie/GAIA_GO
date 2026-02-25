# GAIA_GO Orchestration Platform - API Endpoints

Complete REST API documentation for the GAIA_GO Orchestration Platform with all 5 components.

## Base URL
```
http://localhost:8080/api/orchestration
```

## Table of Contents
1. [Component 1: Tmux Sessions](#component-1-tmux-sessions)
2. [Component 2: Workflow Orchestrator](#component-2-workflow-orchestrator)
3. [Component 3: Project Scaffolder](#component-3-project-scaffolder)
4. [Component 4: Service Coordinator](#component-4-service-coordinator)
5. [Component 5: AI Agent Bridge](#component-5-ai-agent-bridge)
6. [Health & Status](#health--status)

---

## Component 1: Tmux Sessions

Manage GAIA development sessions with tmux windows and panes.

### Create Session
Create a new development session.

```http
POST /api/orchestration/sessions
Content-Type: application/json

{
  "name": "dev-session",
  "project_path": "/path/to/project",
  "shell": "/bin/zsh",
  "metadata": {
    "team": "backend",
    "project_type": "api"
  },
  "tags": ["development", "active"]
}
```

**Response (201)**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "dev-session",
  "project_path": "/path/to/project",
  "status": "active",
  "created_at": "2025-02-24T10:30:00Z",
  "last_active": "2025-02-24T10:35:00Z",
  "metadata": {
    "team": "backend",
    "project_type": "api"
  },
  "tags": ["development", "active"]
}
```

### List Sessions
Get all active sessions.

```http
GET /api/orchestration/sessions
```

**Response (200)**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "dev-session",
    "project_path": "/path/to/project",
    "status": "active",
    "created_at": "2025-02-24T10:30:00Z",
    "last_active": "2025-02-24T10:35:00Z",
    "metadata": {},
    "tags": []
  }
]
```

### Get Session Details
Retrieve a specific session.

```http
GET /api/orchestration/sessions/{sessionID}
```

**Response (200)**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "dev-session",
  "project_path": "/path/to/project",
  "status": "active",
  "created_at": "2025-02-24T10:30:00Z",
  "last_active": "2025-02-24T10:35:00Z",
  "metadata": {},
  "tags": []
}
```

### Create Window
Add a new window to a session.

```http
POST /api/orchestration/sessions/{sessionID}/windows
Content-Type: application/json

{
  "name": "editor"
}
```

**Response (201)**
```json
{
  "id": "window-123",
  "name": "editor",
  "index": 0,
  "active": false,
  "created_at": "2025-02-24T10:31:00Z"
}
```

### Create Pane
Split a window to create a new pane.

```http
POST /api/orchestration/sessions/{sessionID}/windows/{windowID}/panes
Content-Type: application/json

{
  "command": "nvim",
  "work_dir": "/path/to/project",
  "vertical": true
}
```

**Response (201)**
```json
{
  "id": "pane-456",
  "index": 0,
  "command": "nvim",
  "work_dir": "/path/to/project",
  "active": false,
  "created_at": "2025-02-24T10:32:00Z"
}
```

### Send Keys to Pane
Execute commands in a pane.

```http
POST /api/orchestration/sessions/{sessionID}/windows/{windowID}/panes/{paneID}/send-keys
Content-Type: application/json

{
  "keys": "go run main.go",
  "send_enter": true
}
```

**Response (200)**
```json
{
  "message": "Keys sent successfully"
}
```

### Capture Pane Output
Get the current contents of a pane.

```http
GET /api/orchestration/sessions/{sessionID}/windows/{windowID}/panes/{paneID}/capture
```

**Response (200)**
```json
{
  "content": "$ go run main.go\nServer running on :8080\n",
  "pane": "550e8400-e29b-41d4-a716-446655440000:window-123.pane-456"
}
```

### Destroy Session
Kill a session.

```http
DELETE /api/orchestration/sessions/{sessionID}
```

**Response (204)** - No content

---

## Component 2: Workflow Orchestrator

Execute parallel workflows with task dependency resolution.

### Create Workflow
Create a workflow from YAML definition.

```http
POST /api/orchestration/workflows
Content-Type: application/json

{
  "definition": "name: build-and-deploy\nvariables:\n  env: production\ntasks:\n  - id: build\n    name: Build Application\n    type: shell\n    agent: system\n    command: make build\n    dependencies: []\n  - id: test\n    name: Run Tests\n    type: test\n    agent: system\n    command: make test\n    dependencies: [build]\n  - id: deploy\n    name: Deploy to Production\n    type: shell\n    agent: system\n    command: make deploy\n    dependencies: [test]",
  "variables": {
    "env": "production"
  }
}
```

**Response (201)**
```json
{
  "id": "workflow-789",
  "name": "build-and-deploy",
  "description": "",
  "version": "",
  "status": "pending",
  "variables": {
    "env": "production"
  },
  "created_at": "2025-02-24T10:40:00Z",
  "started_at": null,
  "completed_at": null
}
```

### List Workflows
Get all workflows, optionally filtered by status.

```http
GET /api/orchestration/workflows?status=running
```

**Response (200)**
```json
[
  {
    "id": "workflow-789",
    "name": "build-and-deploy",
    "status": "running",
    "created_at": "2025-02-24T10:40:00Z",
    "started_at": "2025-02-24T10:41:00Z",
    "completed_at": null
  }
]
```

### Start Workflow
Begin executing a workflow.

```http
POST /api/orchestration/workflows/{workflowID}/start
Content-Type: application/json

{
  "variables": {
    "env": "staging"
  }
}
```

**Response (200)**
```json
{
  "id": "workflow-789",
  "name": "build-and-deploy",
  "status": "running",
  "started_at": "2025-02-24T10:41:00Z",
  "variables": {
    "env": "staging"
  }
}
```

### Get Workflow Status
Get detailed status including all tasks.

```http
GET /api/orchestration/workflows/{workflowID}/status
```

**Response (200)**
```json
{
  "workflow": {
    "id": "workflow-789",
    "name": "build-and-deploy",
    "status": "running",
    "created_at": "2025-02-24T10:40:00Z",
    "started_at": "2025-02-24T10:41:00Z",
    "completed_at": null
  },
  "tasks": [
    {
      "id": "build",
      "name": "Build Application",
      "type": "shell",
      "agent": "system",
      "status": "completed",
      "output": "Building...\nBuild successful!",
      "started_at": "2025-02-24T10:41:00Z",
      "completed_at": "2025-02-24T10:43:00Z",
      "retry_count": 0,
      "max_retries": 0
    },
    {
      "id": "test",
      "name": "Run Tests",
      "type": "test",
      "agent": "system",
      "status": "running",
      "started_at": "2025-02-24T10:43:00Z",
      "completed_at": null,
      "retry_count": 0,
      "max_retries": 0
    }
  ],
  "progress": {
    "total": 3,
    "completed": 1,
    "failed": 0,
    "percentage": 33
  }
}
```

### Get Task Logs
Retrieve output from a specific task.

```http
GET /api/orchestration/workflows/{workflowID}/tasks/{taskID}/logs
```

**Response (200)**
```json
{
  "task_id": "build",
  "logs": "Building application...\nCompiling Go code...\nBuild successful!"
}
```

### Stop Workflow
Cancel a running workflow.

```http
POST /api/orchestration/workflows/{workflowID}/stop
```

**Response (200)**
```json
{
  "message": "Workflow stopped"
}
```

---

## Component 3: Project Scaffolder

Rapidly generate projects from templates.

### List Templates
Get all available project templates.

```http
GET /api/orchestration/scaffold/templates
```

**Response (200)**
```json
[
  {
    "name": "go-api",
    "display_name": "Go REST API",
    "description": "REST API with Go and Gin",
    "version": "1.0.0",
    "language": "go",
    "framework": "gin"
  },
  {
    "name": "react-app",
    "display_name": "React Application",
    "description": "React app with Vite and TypeScript",
    "version": "1.0.0",
    "language": "typescript",
    "framework": "react"
  }
]
```

### Get Template Details
Get full template information including variables.

```http
GET /api/orchestration/scaffold/templates/go-api
```

**Response (200)**
```json
{
  "name": "go-api",
  "display_name": "Go REST API",
  "description": "REST API with Go and Gin",
  "version": "1.0.0",
  "language": "go",
  "framework": "gin",
  "variables": [
    {
      "name": "module_path",
      "description": "Go module path (e.g., github.com/user/project)",
      "type": "string",
      "required": true,
      "default": null
    },
    {
      "name": "port",
      "description": "Server port",
      "type": "string",
      "required": false,
      "default": "8080"
    }
  ],
  "hooks": {
    "pre_generate": [],
    "post_generate": ["go mod tidy", "git init"]
  }
}
```

### Generate Project
Create a new project from a template.

```http
POST /api/orchestration/scaffold
Content-Type: application/json

{
  "name": "my-api",
  "template": "go-api",
  "path": "/home/user/projects/my-api",
  "variables": {
    "module_path": "github.com/user/my-api",
    "port": "8080"
  }
}
```

**Response (201)**
```json
{
  "project_name": "my-api",
  "project_path": "/home/user/projects/my-api",
  "template": "go-api",
  "created_at": "2025-02-24T10:50:00Z",
  "files_count": 12,
  "dirs_count": 5
}
```

### Validate Project
Check if a generated project is valid.

```http
POST /api/orchestration/scaffold/validate
Content-Type: application/json

{
  "path": "/home/user/projects/my-api"
}
```

**Response (200)**
```json
{
  "is_valid": true,
  "message": "Project is valid",
  "path": "/home/user/projects/my-api"
}
```

---

## Component 4: Service Coordinator

Manage application services with health checks.

### Register Service
Register a new service for management.

```http
POST /api/orchestration/services
Content-Type: application/json

{
  "name": "api-server",
  "type": "api",
  "command": "go",
  "args": ["run", "cmd/server/main.go"],
  "work_dir": "/path/to/project",
  "port": 8080,
  "environment": {
    "ENV": "development",
    "PORT": "8080"
  },
  "health_check": {
    "type": "http",
    "endpoint": "http://localhost:8080/health",
    "interval": "30s",
    "timeout": "5s",
    "retries": 3
  },
  "auto_restart": true
}
```

**Response (201)**
```json
{
  "id": "service-001",
  "name": "api-server",
  "type": "api",
  "command": "go",
  "status": "stopped",
  "port": 8080,
  "process_id": 0,
  "restarts": 0,
  "health_status": "",
  "created_at": "2025-02-24T11:00:00Z"
}
```

### List Services
Get all registered services.

```http
GET /api/orchestration/services
```

**Response (200)**
```json
[
  {
    "id": "service-001",
    "name": "api-server",
    "status": "running",
    "port": 8080,
    "process_id": 12345,
    "restarts": 0,
    "health_status": "healthy",
    "started_at": "2025-02-24T11:01:00Z",
    "created_at": "2025-02-24T11:00:00Z"
  }
]
```

### Start Service
Start a registered service.

```http
POST /api/orchestration/services/{serviceID}/start
```

**Response (200)**
```json
{
  "id": "service-001",
  "name": "api-server",
  "status": "running",
  "process_id": 12345,
  "started_at": "2025-02-24T11:01:00Z"
}
```

### Health Check
Check the health status of a service.

```http
GET /api/orchestration/services/{serviceID}/health
```

**Response (200)**
```json
{
  "service_id": "service-001",
  "is_healthy": true,
  "last_check_time": "2025-02-24T11:05:00Z",
  "failure_count": 0,
  "last_error": "",
  "response_time_ms": 125
}
```

### Get Logs
Retrieve service logs.

```http
GET /api/orchestration/services/{serviceID}/logs?lines=50
```

**Response (200)**
```json
{
  "service_id": "service-001",
  "logs": "INFO: Server starting on :8080\nINFO: Database connected\nINFO: Ready to serve requests",
  "lines": 50
}
```

### Get Metrics
Get service performance metrics.

```http
GET /api/orchestration/services/{serviceID}/metrics
```

**Response (200)**
```json
{
  "service_id": "service-001",
  "cpu_percent": 2.5,
  "memory_mb": 125,
  "pid": 12345,
  "uptime_seconds": 300,
  "restart_count": 0,
  "health_checks_passed": 10,
  "health_checks_failed": 0
}
```

### Stop Service
Stop a running service.

```http
POST /api/orchestration/services/{serviceID}/stop?graceful=true
```

**Response (200)**
```json
{
  "id": "service-001",
  "name": "api-server",
  "status": "stopped",
  "stopped_at": "2025-02-24T11:10:00Z"
}
```

### Restart Service
Restart a service (stop then start).

```http
POST /api/orchestration/services/{serviceID}/restart
```

**Response (200)**
```json
{
  "id": "service-001",
  "name": "api-server",
  "status": "running",
  "restarts": 1,
  "started_at": "2025-02-24T11:11:00Z"
}
```

### Unregister Service
Remove a service from management.

```http
DELETE /api/orchestration/services/{serviceID}
```

**Response (204)** - No content

---

## Component 5: AI Agent Bridge

Coordinate Claude Code and Gemini AI agents.

### List Agents
Get all registered AI agents.

```http
GET /api/orchestration/agents
```

**Response (200)**
```json
[
  {
    "id": "claude",
    "type": "claude_code",
    "status": "available",
    "capabilities": ["code_generation", "code_review", "refactoring"],
    "active_tasks": 0,
    "queued_tasks": 0,
    "is_available": true
  },
  {
    "id": "gemini",
    "type": "gemini",
    "status": "available",
    "capabilities": ["code_generation", "documentation"],
    "active_tasks": 0,
    "queued_tasks": 0,
    "is_available": true
  }
]
```

### Execute Task
Execute a task with a specific agent.

```http
POST /api/orchestration/agents/execute
Content-Type: application/json

{
  "agent": "claude",
  "task_type": "code_generation",
  "instruction": "Write a REST API endpoint for user management in Go",
  "work_dir": "/path/to/project",
  "timeout": "30m",
  "priority": 5,
  "context": {
    "framework": "gin",
    "database": "postgresql"
  }
}
```

**Response (200)**
```json
{
  "task_id": "task-001",
  "agent_id": "claude",
  "success": true,
  "output": "Created user API endpoint with full CRUD operations...",
  "modified_files": [
    "cmd/server/handlers/users.go",
    "internal/models/user.go"
  ],
  "duration_ms": 45000,
  "completed_at": "2025-02-24T11:20:00Z"
}
```

### Execute Parallel
Execute multiple tasks in parallel across agents.

```http
POST /api/orchestration/agents/execute-parallel
Content-Type: application/json

{
  "tasks": [
    {
      "agent": "claude",
      "instruction": "Implement REST API for user management",
      "work_dir": "/path/to/project",
      "timeout": "30m"
    },
    {
      "agent": "gemini",
      "instruction": "Create React components for user interface",
      "work_dir": "/path/to/project/frontend",
      "timeout": "30m"
    }
  ]
}
```

**Response (200)**
```json
[
  {
    "task_id": "task-001",
    "agent_id": "claude",
    "success": true,
    "output": "Backend API implementation complete...",
    "modified_files": ["cmd/server/handlers/users.go"],
    "duration_ms": 45000,
    "completed_at": "2025-02-24T11:20:00Z"
  },
  {
    "task_id": "task-002",
    "agent_id": "gemini",
    "success": true,
    "output": "React components created...",
    "modified_files": ["src/components/UserManagement.tsx"],
    "duration_ms": 38000,
    "completed_at": "2025-02-24T11:19:00Z"
  }
]
```

### Get Agent Statistics
Retrieve performance statistics for an agent.

```http
GET /api/orchestration/agents/claude/stats
```

**Response (200)**
```json
{
  "agent_id": "claude",
  "status": "available",
  "total_tasks": 125,
  "successful_tasks": 120,
  "failed_tasks": 5,
  "active_tasks": 0,
  "queued_tasks": 0,
  "success_rate": 96.0,
  "last_used": "2025-02-24T11:20:00Z"
}
```

### Get Task Result
Retrieve the result of a completed task.

```http
GET /api/orchestration/agents/results/{taskID}
```

**Response (200)**
```json
{
  "task_id": "task-001",
  "agent_id": "claude",
  "success": true,
  "output": "Task completed successfully...",
  "modified_files": ["src/main.go"],
  "duration_ms": 45000,
  "completed_at": "2025-02-24T11:20:00Z"
}
```

---

## Health & Status

### Health Check
Check if orchestration platform is healthy.

```http
GET /api/orchestration/health
```

**Response (200)**
```json
{
  "status": "healthy",
  "platform": "GAIA_GO Orchestration"
}
```

### Platform Status
Get status of all orchestration components.

```http
GET /api/orchestration/status
```

**Response (200)**
```json
{
  "sessions": {
    "status": "initialized"
  },
  "workflows": {
    "status": "initialized"
  },
  "scaffolder": {
    "status": "initialized"
  },
  "services": {
    "status": "initialized"
  },
  "agents": {
    "status": "initialized"
  }
}
```

---

## Error Responses

All endpoints return standardized error responses:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "status_code": 400,
  "timestamp": "2025-02-24T11:00:00Z"
}
```

### Common HTTP Status Codes
- **200 OK** - Successful request
- **201 Created** - Resource created successfully
- **204 No Content** - Successful request with no response body
- **400 Bad Request** - Invalid request parameters
- **404 Not Found** - Resource not found
- **500 Internal Server Error** - Server error

---

## Integration Examples

### Complete Workflow: Scaffold + Start Services + Execute Workflow

```bash
# 1. Generate project from template
curl -X POST http://localhost:8080/api/orchestration/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-api",
    "template": "go-api",
    "path": "/home/user/projects/my-api",
    "variables": {
      "module_path": "github.com/user/my-api"
    }
  }'

# 2. Register services
curl -X POST http://localhost:8080/api/orchestration/services \
  -H "Content-Type: application/json" \
  -d '{
    "name": "api-server",
    "command": "go",
    "args": ["run", "cmd/server/main.go"],
    "work_dir": "/home/user/projects/my-api",
    "port": 8080,
    "health_check": {
      "type": "http",
      "endpoint": "http://localhost:8080/health"
    },
    "auto_restart": true
  }'

# 3. Start service
curl -X POST http://localhost:8080/api/orchestration/services/{serviceID}/start

# 4. Create and start workflow
curl -X POST http://localhost:8080/api/orchestration/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "definition": "name: deploy\ntasks:\n  - id: build\n    type: shell\n    command: make build\n    agent: system"
  }'

# 5. Execute workflow with agents
curl -X POST http://localhost:8080/api/orchestration/workflows/{workflowID}/start
```

---

## Rate Limiting & Quotas

- Session creation: 100 sessions max
- Service management: 50 services max
- Concurrent workflows: 10 workflows max
- Agent tasks: 4 concurrent tasks per agent

---

## WebSocket Support (Future)

Real-time updates for:
- Workflow progress
- Service status changes
- Task output streaming

```
ws://localhost:8080/api/orchestration/ws/{workflowID}
```
