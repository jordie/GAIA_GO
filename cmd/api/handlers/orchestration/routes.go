package orchestration

import (
	"database/sql"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/orchestration/agents"
	sessionmgr "github.com/jgirmay/GAIA_GO/internal/orchestration/session"
	"github.com/jgirmay/GAIA_GO/internal/orchestration/scaffold"
	svccoord "github.com/jgirmay/GAIA_GO/internal/orchestration/services"
	"github.com/jgirmay/GAIA_GO/internal/orchestration/workflow"
)

// OrchestratorComponents holds all orchestration platform components
type OrchestratorComponents struct {
	SessionManager  *sessionmgr.Manager
	Orchestrator    *workflow.Orchestrator
	Scaffolder      *scaffold.Scaffolder
	Coordinator     *svccoord.Coordinator
	Bridge          *agents.Bridge
}

// NewOrchestratorComponents initializes all orchestration components
func NewOrchestratorComponents(db *sql.DB, maxSessions, maxServices int) (*OrchestratorComponents, error) {
	// Initialize Component 1: Session Manager
	sessionManager, err := sessionmgr.NewManager(db, maxSessions)
	if err != nil {
		return nil, err
	}

	// Initialize Component 2: Workflow Orchestrator
	executor := workflow.NewExecutor("")
	orchestrator := workflow.NewOrchestrator(db, executor, 10)

	// Initialize Component 3: Scaffolder
	// Assuming GAIA home dir is set up elsewhere
	scaffolder, err := scaffold.NewScaffolder("/home/user/.gaia/templates")
	if err != nil {
		return nil, err
	}

	// Initialize Component 4: Service Coordinator
	serviceCoordinator := svccoord.NewCoordinator(db, maxServices)

	// Initialize Component 5: Agent Bridge
	agentBridge := agents.NewBridge(db, 4)

	return &OrchestratorComponents{
		SessionManager: sessionManager,
		Orchestrator:   orchestrator,
		Scaffolder:     scaffolder,
		Coordinator:    serviceCoordinator,
		Bridge:         agentBridge,
	}, nil
}

// RegisterRoutes registers all orchestration routes with the router
func RegisterRoutes(router *gin.Engine, components *OrchestratorComponents) {
	// Create orchestration API group
	api := router.Group("/api/orchestration")

	// Component 1: Sessions
	sessionHandler := NewSessionHandler(components.SessionManager)
	sessionHandler.RegisterRoutes(api)

	// Component 2: Workflows
	parser := workflow.NewParser("")
	workflowHandler := NewWorkflowHandler(components.Orchestrator, parser)
	workflowHandler.RegisterRoutes(api)

	// Component 3: Scaffolder
	scaffoldHandler := NewScaffoldHandler(components.Scaffolder)
	scaffoldHandler.RegisterRoutes(api)

	// Component 4: Services
	serviceHandler := NewServiceHandler(components.Coordinator)
	serviceHandler.RegisterRoutes(api)

	// Component 5: Agents
	agentHandler := NewAgentHandler(components.Bridge)
	agentHandler.RegisterRoutes(api)

	// Health endpoint for orchestration platform
	api.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":   "healthy",
			"platform": "GAIA_GO Orchestration",
		})
	})

	// Status endpoint
	api.GET("/status", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"sessions": gin.H{
				"status": "initialized",
			},
			"workflows": gin.H{
				"status": "initialized",
			},
			"scaffolder": gin.H{
				"status": "initialized",
			},
			"services": gin.H{
				"status": "initialized",
			},
			"agents": gin.H{
				"status": "initialized",
			},
		})
	})
}

// Close gracefully shuts down all orchestration components
func (oc *OrchestratorComponents) Close() error {
	// Close in reverse order of dependencies
	if oc.Bridge != nil {
		_ = oc.Bridge.Close()
	}
	if oc.Coordinator != nil {
		_ = oc.Coordinator.Close()
	}
	if oc.Orchestrator != nil {
		_ = oc.Orchestrator.Close()
	}
	if oc.SessionManager != nil {
		_ = oc.SessionManager.Close()
	}
	return nil
}
