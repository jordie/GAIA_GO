# GAIA_GO Orchestration Platform - Integration Guide

Complete guide for integrating the orchestration platform API endpoints into the main GAIA_GO application.

## Overview

The API endpoints are organized in 5 groups corresponding to the 5 orchestration components:
1. **Sessions** (`/api/orchestration/sessions`) - Tmux session management
2. **Workflows** (`/api/orchestration/workflows`) - Task orchestration
3. **Scaffold** (`/api/orchestration/scaffold`) - Project generation
4. **Services** (`/api/orchestration/services`) - Service lifecycle
5. **Agents** (`/api/orchestration/agents`) - AI agent coordination

## Step 1: File Structure Setup

### Create Handler Directory
```bash
mkdir -p cmd/api/handlers/orchestration
```

### Files Already Created
```
cmd/api/handlers/orchestration/
├── sessions.go        # Session management handlers
├── workflows.go       # Workflow orchestration handlers
├── scaffold.go        # Project scaffolding handlers
├── services.go        # Service coordination handlers
├── agents.go          # AI agent bridge handlers
└── routes.go          # Main router setup
```

### DTOs File
```
internal/api/dtos/
└── orchestration.go   # All request/response data models
```

## Step 2: Integration into Main Application

### Modify `cmd/server/main.go`

Add initialization code at application startup:

```go
package main

import (
	"database/sql"
	"log"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/cmd/api/handlers/orchestration"
	// ... other imports
)

func main() {
	// ... existing initialization code ...

	var db *sql.DB
	// db initialization code

	// Initialize orchestration components
	components, err := orchestration.NewOrchestratorComponents(db, 50, 50)
	if err != nil {
		log.Fatalf("Failed to initialize orchestration components: %v", err)
	}
	defer components.Close()

	// Create Gin router
	router := gin.Default()

	// Register all orchestration routes
	orchestration.RegisterRoutes(router, components)

	// Start server
	if err := router.Run(":8080"); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
```

### Alternative: Modular Integration

If your application already has a router setup, integrate like this:

```go
package main

import (
	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/cmd/api/handlers/orchestration"
	// ... other imports
)

func setupOrchestrationRoutes(engine *gin.Engine, db *sql.DB) error {
	// Initialize components
	components, err := orchestration.NewOrchestratorComponents(db, 50, 50)
	if err != nil {
		return fmt.Errorf("orchestration initialization failed: %w", err)
	}

	// Register routes on existing engine
	orchestration.RegisterRoutes(engine, components)

	return nil
}

func main() {
	// ... existing code ...

	engine := gin.Default()

	// Setup orchestration routes
	if err := setupOrchestrationRoutes(engine, db); err != nil {
		log.Fatalf("Failed to setup orchestration: %v", err)
	}

	// ... rest of application setup ...

	engine.Run()
}
```

## Step 3: Database Setup

### Run Migrations

Ensure these migrations are executed in order:

```go
// In your migration runner
migrations := []string{
	"migrations/010_gaia_sessions.sql",
	"migrations/011_gaia_workflows.sql",
	"migrations/012_gaia_services.sql",
	"migrations/013_gaia_agents.sql",
}

for _, migration := range migrations {
	data, err := ioutil.ReadFile(migration)
	if err != nil {
		return fmt.Errorf("failed to read migration: %w", err)
	}

	if _, err := db.Exec(string(data)); err != nil {
		return fmt.Errorf("migration failed: %w", err)
	}
}
```

## Step 4: GAIA Home Directory Setup

### Create Configuration Structure

```bash
# Create GAIA home directory
mkdir -p $HOME/.gaia/{sessions,workflows/definitions,templates,services,logs}

# Create config file
cat > $HOME/.gaia/config.toml << 'EOF'
[gaia]
version = "1.0.0"
home = "$HOME/.gaia"

[tmux]
default_shell = "/bin/zsh"
max_sessions = 50
auto_cleanup = true
cleanup_threshold_hours = 24

[agents]
claude_code_path = "claude"
gemini_path = "gemini"
max_parallel_agents = 4
timeout_minutes = 30

[workflows]
max_concurrent = 10
default_timeout_minutes = 60
retry_failed_tasks = true
max_retries = 3

[services]
max_services = 100
auto_restart = true
health_check_interval_seconds = 30

[logging]
level = "info"
max_file_size_mb = 100
EOF
```

### Create Template Directories

```bash
# Go API template
mkdir -p $HOME/.gaia/templates/go-api/{files,migrations}
cat > $HOME/.gaia/templates/go-api/template.yaml << 'EOF'
name: go-api
display_name: Go REST API
language: go
framework: gin
version: 1.0.0
variables:
  - name: module_path
    required: true
    type: string
  - name: port
    required: false
    default: "8080"
directories:
  - cmd/server
  - internal/api
  - internal/models
  - migrations
hooks:
  post_generate:
    - go mod tidy
    - git init
EOF
```

## Step 5: Initialize Components at Runtime

### Option A: Eager Initialization (Recommended)

Initialize components when the application starts:

```go
// In main.go or app initialization
func initializeApp(db *sql.DB) (*orchestration.OrchestratorComponents, error) {
	// Initialize orchestration components
	components, err := orchestration.NewOrchestratorComponents(db, 50, 50)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize orchestration: %w", err)
	}

	// Verify all components are working
	agents := components.Bridge.ListAgents()
	if len(agents) == 0 {
		log.Println("warning: no AI agents registered")
	}

	services, err := components.Coordinator.ListServices()
	if err != nil {
		log.Printf("warning: service coordinator initialization: %v", err)
	}

	return components, nil
}
```

### Option B: Lazy Initialization

Initialize components on first request:

```go
var orchestrationComponents *orchestration.OrchestratorComponents
var initOnce sync.Once

func getOrchestratorComponents(db *sql.DB) (*orchestration.OrchestratorComponents, error) {
	var err error
	initOnce.Do(func() {
		orchestrationComponents, err = orchestration.NewOrchestratorComponents(db, 50, 50)
	})
	return orchestrationComponents, err
}
```

## Step 6: Middleware Integration

### Add Metrics Middleware

```go
// Add before orchestration routes
router.Use(func(c *gin.Context) {
	start := time.Now()
	path := c.Request.URL.Path

	c.Next()

	duration := time.Since(start)
	if path == "/api/orchestration/health" {
		return // Skip logging health checks
	}

	log.Printf("[ORCHESTRATION] %s %s %d (%dms)",
		c.Request.Method,
		path,
		c.Writer.Status(),
		duration.Milliseconds(),
	)
})
```

### Add Error Handling Middleware

```go
router.Use(func(c *gin.Context) {
	defer func() {
		if err := recover(); err != nil {
			c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
				Error:      "internal_server_error",
				Message:    fmt.Sprintf("%v", err),
				StatusCode: http.StatusInternalServerError,
				Timestamp:  time.Now(),
			})
		}
	}()
	c.Next()
})
```

## Step 7: Health Checks

### Add Application Health Endpoint

```go
router.GET("/health", func(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "healthy",
		"timestamp": time.Now(),
		"version": "1.0.0",
	})
})
```

### Monitor Component Health

```go
func monitorComponents(components *orchestration.OrchestratorComponents) {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		// Check session manager
		sessions, _ := components.SessionManager.ListSessions()
		log.Printf("Active sessions: %d", len(sessions))

		// Check services
		services, _ := components.Coordinator.ListServices()
		log.Printf("Registered services: %d", len(services))

		// Check agents
		agents := components.Bridge.ListAgents()
		log.Printf("Available agents: %d", len(agents))
	}
}
```

## Step 8: Testing the Integration

### Test Health Endpoints

```bash
# Test orchestration health
curl http://localhost:8080/api/orchestration/health

# Test overall health
curl http://localhost:8080/health
```

### Test Session Management

```bash
# Create a session
curl -X POST http://localhost:8080/api/orchestration/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-session",
    "project_path": "/tmp/test",
    "metadata": {"test": "true"}
  }'

# List sessions
curl http://localhost:8080/api/orchestration/sessions
```

### Test Scaffolding

```bash
# List templates
curl http://localhost:8080/api/orchestration/scaffold/templates

# Generate project
curl -X POST http://localhost:8080/api/orchestration/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-project",
    "template": "go-api",
    "path": "/tmp/test-project",
    "variables": {
      "module_path": "github.com/test/test-project"
    }
  }'
```

## Step 9: Environment Configuration

### Support Environment Variables

```go
import "os"

func getOrchestratorConfig() orchestration.OrchestratorComponents {
	// Read from environment or use defaults
	maxSessions := 50
	maxServices := 50

	if envSessions := os.Getenv("GAIA_MAX_SESSIONS"); envSessions != "" {
		if n, err := strconv.Atoi(envSessions); err == nil {
			maxSessions = n
		}
	}

	// Similar for other configs...

	return createComponents(maxSessions, maxServices)
}
```

### Example `.env` File

```env
# Orchestration Configuration
GAIA_MAX_SESSIONS=50
GAIA_MAX_SERVICES=50
GAIA_MAX_WORKFLOWS=10
GAIA_HOME=$HOME/.gaia

# Component Settings
TMUX_SHELL=/bin/zsh
TMUX_MAX_SESSIONS=50
CLAUDE_PATH=claude
GEMINI_PATH=gemini
```

## Step 10: Docker Support

### Dockerfile Updates

```dockerfile
# Ensure tmux is installed for session management
RUN apt-get update && apt-get install -y tmux

# Copy GAIA configuration
COPY .gaia $HOME/.gaia

# Or create at runtime:
RUN mkdir -p $HOME/.gaia/{sessions,workflows,templates,services,logs}
```

### Docker Compose Example

```yaml
version: '3.8'

services:
  gaia:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - $HOME/.gaia:/root/.gaia
    environment:
      - GAIA_MAX_SESSIONS=50
      - GAIA_MAX_SERVICES=50
    depends_on:
      - db

  db:
    image: sqlite:latest
    volumes:
      - ./data:/data
```

## Step 11: Logging Setup

### Configure Structured Logging

```go
import "log/slog"

func setupLogging() {
	// Create logs directory
	os.MkdirAll(filepath.Join(os.Getenv("HOME"), ".gaia/logs"), 0755)

	// Setup structured logging
	handler := slog.NewJSONHandler(os.Stdout, nil)
	logger := slog.New(handler)
	slog.SetDefault(logger)
}
```

### Log Important Events

```go
// In orchestration handlers
func (h *SessionHandler) CreateSession(c *gin.Context) {
	// ... handler code ...
	slog.Info("session created",
		slog.String("session_id", session.ID),
		slog.String("name", session.Name),
		slog.String("project", session.ProjectPath),
	)
}
```

## Step 12: Shutdown Handling

### Graceful Shutdown

```go
func main() {
	// ... setup code ...

	components, err := orchestration.NewOrchestratorComponents(db, 50, 50)
	if err != nil {
		log.Fatal(err)
	}

	// Setup graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-sigChan
		log.Println("Shutting down orchestration components...")

		// Close orchestration components
		if err := components.Close(); err != nil {
			log.Printf("Error closing components: %v", err)
		}

		// Close database
		db.Close()

		os.Exit(0)
	}()

	// Start server
	router.Run(":8080")
}
```

## Common Integration Patterns

### Pattern 1: Complete Workflow (Scaffold + Build + Deploy)

```go
func handleCompleteWorkflow(c *gin.Context) {
	// 1. Generate project
	scaffoldHandler.GenerateProject(projectName, template, vars)

	// 2. Create workflow
	workflowDef := parseWorkflowYAML(workflowFile)
	workflow := workflowHandler.CreateWorkflow(workflowDef, vars)

	// 3. Execute workflow
	workflowHandler.StartWorkflow(workflow.ID, vars)

	// 4. Monitor progress
	status := workflowHandler.GetWorkflowStatus(workflow.ID)
}
```

### Pattern 2: Multi-Service Deployment

```go
func deployServices(c *gin.Context) {
	// Register all services
	for _, svcConfig := range services {
		serviceHandler.RegisterService(svcConfig)
	}

	// Start services in order
	for _, svcID := range serviceOrder {
		serviceHandler.StartService(svcID)
		time.Sleep(2 * time.Second)

		// Verify health
		health, _ := serviceHandler.HealthCheck(svcID)
		if !health.IsHealthy {
			return fmt.Errorf("service %s health check failed", svcID)
		}
	}
}
```

### Pattern 3: Parallel AI Agent Workflow

```go
func parallelDevelopment(c *gin.Context) {
	tasks := []*dtos.ExecuteAgentTaskRequest{
		{
			AgentID:     "claude",
			Instruction: "Implement backend REST API",
		},
		{
			AgentID:     "gemini",
			Instruction: "Create React UI components",
		},
	}

	results, _ := agentHandler.ExecuteParallel(tasks)

	// Process results
	for _, result := range results {
		if result.Success {
			// Integrate modified files
		}
	}
}
```

## Troubleshooting

### Issue: Sessions not persisting

**Solution**: Ensure SQLite database is properly initialized with migration 010.

### Issue: Tmux commands failing

**Solution**: Verify tmux is installed: `which tmux`

### Issue: Agent tasks timing out

**Solution**: Increase timeout in environment: `AGENT_TIMEOUT=60m`

### Issue: Service health checks failing

**Solution**: Verify health check endpoint is accessible and returns correct status codes.

## Monitoring & Observability

### Metrics to Track

- Session creation/destruction rates
- Workflow execution times
- Task success/failure rates
- Service health check failures
- Agent task latencies

### Performance Considerations

- Max concurrent workflows: 10 (configurable)
- Max concurrent services: 50 (configurable)
- Agent task queue size: 100 (configurable)
- Session cleanup interval: 1 hour

### Resource Limits

```go
const (
	MaxSessions       = 50
	MaxServices       = 50
	MaxConcurrentWFs  = 10
	MaxAgentTasks     = 4
	SessionCleanupAge = 24 * time.Hour
)
```

## Next Steps

1. **Deploy API Endpoints** - Use this integration guide to add to your main app
2. **Create CLI Tools** - Build `gaia-cli` for command-line access
3. **Add WebSocket Support** - Real-time streaming of workflow progress
4. **Implement Advanced Scheduling** - Cron-based workflow execution
5. **Add Multi-Tenant Support** - Separate GAIA homes per tenant

## Support & Documentation

- Full API endpoint documentation: `API_ENDPOINTS.md`
- Implementation summary: `ORCHESTRATION_IMPLEMENTATION_SUMMARY.md`
- Component architecture: Each component's source code
