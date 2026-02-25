package orchestration

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api/dtos"
	"github.com/jgirmay/GAIA_GO/internal/orchestration/workflow"
)

// WorkflowHandler handles workflow-related HTTP requests
type WorkflowHandler struct {
	orchestrator *workflow.Orchestrator
	parser       *workflow.Parser
}

// NewWorkflowHandler creates a new workflow handler
func NewWorkflowHandler(orchestrator *workflow.Orchestrator, parser *workflow.Parser) *WorkflowHandler {
	return &WorkflowHandler{
		orchestrator: orchestrator,
		parser:       parser,
	}
}

// RegisterRoutes registers workflow routes
func (h *WorkflowHandler) RegisterRoutes(router *gin.RouterGroup) {
	workflows := router.Group("/workflows")
	{
		workflows.POST("", h.CreateWorkflow)
		workflows.GET("", h.ListWorkflows)
		workflows.GET("/:workflowID", h.GetWorkflow)
		workflows.POST("/:workflowID/start", h.StartWorkflow)
		workflows.POST("/:workflowID/stop", h.StopWorkflow)
		workflows.GET("/:workflowID/status", h.GetWorkflowStatus)
		workflows.GET("/:workflowID/tasks/:taskID", h.GetTask)
		workflows.GET("/:workflowID/tasks/:taskID/logs", h.GetTaskLogs)
	}
}

// CreateWorkflow creates a new workflow from YAML definition
// @Summary Create a workflow
// @Description Creates a new workflow from YAML definition
// @Tags Workflows
// @Accept json
// @Produce json
// @Param request body dtos.CreateWorkflowRequest true "Workflow definition"
// @Success 201 {object} dtos.WorkflowResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/workflows [post]
func (h *WorkflowHandler) CreateWorkflow(c *gin.Context) {
	var req dtos.CreateWorkflowRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	// Parse YAML definition
	def, err := h.parser.Parse(req.Definition)
	if err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "workflow_parse_failed",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	// Create workflow
	wf, err := h.orchestrator.CreateWorkflow(def, req.Variables)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "workflow_creation_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusCreated, workflowToResponse(wf))
}

// ListWorkflows lists all workflows
// @Summary List workflows
// @Description Returns a list of all workflows
// @Tags Workflows
// @Produce json
// @Param status query string false "Filter by status (pending, running, completed, failed)"
// @Success 200 {array} dtos.WorkflowResponse
// @Router /api/orchestration/workflows [get]
func (h *WorkflowHandler) ListWorkflows(c *gin.Context) {
	// Parse optional status filter
	statusStr := c.Query("status")
	var status workflow.WorkflowStatus
	if statusStr != "" {
		status = workflow.WorkflowStatus(statusStr)
	}

	workflows, err := h.orchestrator.ListWorkflows(status)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "list_workflows_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	var responses []*dtos.WorkflowResponse
	for _, wf := range workflows {
		responses = append(responses, workflowToResponse(wf))
	}

	c.JSON(http.StatusOK, responses)
}

// GetWorkflow retrieves a specific workflow
// @Summary Get workflow
// @Description Retrieves a workflow by ID
// @Tags Workflows
// @Produce json
// @Param workflowID path string true "Workflow ID"
// @Success 200 {object} dtos.WorkflowResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/workflows/{workflowID} [get]
func (h *WorkflowHandler) GetWorkflow(c *gin.Context) {
	workflowID := c.Param("workflowID")

	wf, err := h.orchestrator.GetWorkflow(workflowID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "workflow_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, workflowToResponse(wf))
}

// StartWorkflow starts workflow execution
// @Summary Start workflow
// @Description Starts executing a workflow with optional variable overrides
// @Tags Workflows
// @Accept json
// @Produce json
// @Param workflowID path string true "Workflow ID"
// @Param request body dtos.StartWorkflowRequest true "Optional variables"
// @Success 200 {object} dtos.WorkflowResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/workflows/{workflowID}/start [post]
func (h *WorkflowHandler) StartWorkflow(c *gin.Context) {
	workflowID := c.Param("workflowID")

	var req dtos.StartWorkflowRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		// Empty body is OK for starting workflow
		req.Variables = make(map[string]interface{})
	}

	// Merge any provided variables
	wf, err := h.orchestrator.GetWorkflow(workflowID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "workflow_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	// Update workflow variables
	if req.Variables != nil {
		for k, v := range req.Variables {
			wf.Variables[k] = v
		}
	}

	// Start workflow
	if err := h.orchestrator.StartWorkflow(c.Request.Context(), workflowID); err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "workflow_start_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, workflowToResponse(wf))
}

// StopWorkflow stops a running workflow
// @Summary Stop workflow
// @Description Cancels a running workflow
// @Tags Workflows
// @Param workflowID path string true "Workflow ID"
// @Success 200 {object} dtos.SuccessResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/workflows/{workflowID}/stop [post]
func (h *WorkflowHandler) StopWorkflow(c *gin.Context) {
	workflowID := c.Param("workflowID")

	if err := h.orchestrator.StopWorkflow(workflowID); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "workflow_stop_failed",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, dtos.SuccessResponse{
		Message: "Workflow stopped",
	})
}

// GetWorkflowStatus retrieves complete workflow status with tasks
// @Summary Get workflow status
// @Description Returns detailed status of a workflow and all its tasks
// @Tags Workflows
// @Produce json
// @Param workflowID path string true "Workflow ID"
// @Success 200 {object} dtos.WorkflowStatusResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/workflows/{workflowID}/status [get]
func (h *WorkflowHandler) GetWorkflowStatus(c *gin.Context) {
	workflowID := c.Param("workflowID")

	wf, err := h.orchestrator.GetWorkflow(workflowID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "workflow_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	// Build status response
	response := dtos.WorkflowStatusResponse{
		Workflow: workflowToResponse(wf),
	}

	// Add task details
	for _, task := range wf.Tasks {
		response.Tasks = append(response.Tasks, taskToResponse(task))
		response.Progress.Total++

		if task.Status == workflow.TaskStatusCompleted {
			response.Progress.Completed++
		} else if task.Status == workflow.TaskStatusFailed {
			response.Progress.Failed++
		}
	}

	// Calculate percentage
	if response.Progress.Total > 0 {
		response.Progress.Percentage = (response.Progress.Completed * 100) / response.Progress.Total
	}

	c.JSON(http.StatusOK, response)
}

// GetTask retrieves a specific task from a workflow
// @Summary Get task
// @Description Retrieves details of a specific task
// @Tags Workflows
// @Produce json
// @Param workflowID path string true "Workflow ID"
// @Param taskID path string true "Task ID"
// @Success 200 {object} dtos.TaskResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/workflows/{workflowID}/tasks/{taskID} [get]
func (h *WorkflowHandler) GetTask(c *gin.Context) {
	workflowID := c.Param("workflowID")
	taskID := c.Param("taskID")

	task, err := h.orchestrator.GetTask(workflowID, taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "task_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, taskToResponse(task))
}

// GetTaskLogs retrieves the output/logs from a task
// @Summary Get task logs
// @Description Retrieves the output from a completed task
// @Tags Workflows
// @Produce json
// @Param workflowID path string true "Workflow ID"
// @Param taskID path string true "Task ID"
// @Success 200 {object} map[string]interface{}
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/workflows/{workflowID}/tasks/{taskID}/logs [get]
func (h *WorkflowHandler) GetTaskLogs(c *gin.Context) {
	workflowID := c.Param("workflowID")
	taskID := c.Param("taskID")

	logs, err := h.orchestrator.GetTaskLogs(workflowID, taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "logs_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"task_id": taskID,
		"logs":    logs,
	})
}

// Helper functions

func workflowToResponse(wf *workflow.Workflow) *dtos.WorkflowResponse {
	return &dtos.WorkflowResponse{
		ID:          wf.ID,
		Name:        wf.Name,
		Description: wf.Description,
		Version:     wf.Version,
		Status:      string(wf.Status),
		Variables:   wf.Variables,
		CreatedAt:   wf.CreatedAt,
		StartedAt:   wf.StartedAt,
		CompletedAt: wf.CompletedAt,
		Error:       wf.Error,
	}
}

func taskToResponse(task *workflow.Task) *dtos.TaskResponse {
	return &dtos.TaskResponse{
		ID:          task.ID,
		Name:        task.Name,
		Type:        string(task.Type),
		Agent:       string(task.Agent),
		Status:      string(task.Status),
		Output:      task.Output,
		Error:       task.Error,
		StartedAt:   task.StartedAt,
		CompletedAt: task.CompletedAt,
		RetryCount:  task.RetryCount,
		MaxRetries:  task.MaxRetries,
	}
}
