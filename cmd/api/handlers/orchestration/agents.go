package orchestration

import (
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api/dtos"
	"github.com/jgirmay/GAIA_GO/internal/orchestration/agents"
)

// AgentHandler handles AI agent bridge HTTP requests
type AgentHandler struct {
	bridge *agents.Bridge
}

// NewAgentHandler creates a new agent handler
func NewAgentHandler(bridge *agents.Bridge) *AgentHandler {
	return &AgentHandler{
		bridge: bridge,
	}
}

// RegisterRoutes registers agent routes
func (h *AgentHandler) RegisterRoutes(router *gin.RouterGroup) {
	agentsGroup := router.Group("/agents")
	{
		agentsGroup.GET("", h.ListAgents)
		agentsGroup.GET("/:agentID", h.GetAgent)
		agentsGroup.GET("/:agentID/stats", h.GetAgentStats)

		agentsGroup.POST("/execute", h.ExecuteTask)
		agentsGroup.POST("/execute-parallel", h.ExecuteParallel)

		agentsGroup.GET("/results/:taskID", h.GetResult)
	}
}

// ListAgents lists all registered agents
// @Summary List agents
// @Description Returns all registered AI agents
// @Tags Agents
// @Produce json
// @Success 200 {array} dtos.AgentResponse
// @Router /api/orchestration/agents [get]
func (h *AgentHandler) ListAgents(c *gin.Context) {
	agentList := h.bridge.ListAgents()

	var responses []*dtos.AgentResponse
	for _, agent := range agentList {
		responses = append(responses, &dtos.AgentResponse{
			ID:            string(agent.GetID()),
			Type:          agent.GetType(),
			Status:        string(agent.GetStatus()),
			Capabilities:  capabilitiesToStrings(agent.GetCapabilities()),
			ActiveTasks:   agent.GetActiveTaskCount(),
			QueuedTasks:   agent.GetQueueLength(),
			IsAvailable:   agent.IsAvailable(),
		})
	}

	c.JSON(http.StatusOK, responses)
}

// GetAgent retrieves a specific agent
// @Summary Get agent
// @Description Retrieves details of a specific agent
// @Tags Agents
// @Produce json
// @Param agentID path string true "Agent ID (claude or gemini)"
// @Success 200 {object} dtos.AgentResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/agents/{agentID} [get]
func (h *AgentHandler) GetAgent(c *gin.Context) {
	agentID := c.Param("agentID")

	agent, err := h.bridge.GetAgent(agents.AgentID(agentID))
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "agent_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	response := &dtos.AgentResponse{
		ID:            string(agent.GetID()),
		Type:          agent.GetType(),
		Status:        string(agent.GetStatus()),
		Capabilities:  capabilitiesToStrings(agent.GetCapabilities()),
		ActiveTasks:   agent.GetActiveTaskCount(),
		QueuedTasks:   agent.GetQueueLength(),
		IsAvailable:   agent.IsAvailable(),
	}

	c.JSON(http.StatusOK, response)
}

// GetAgentStats retrieves statistics for an agent
// @Summary Get agent stats
// @Description Retrieves performance statistics for a specific agent
// @Tags Agents
// @Produce json
// @Param agentID path string true "Agent ID (claude or gemini)"
// @Success 200 {object} dtos.AgentStatsResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/agents/{agentID}/stats [get]
func (h *AgentHandler) GetAgentStats(c *gin.Context) {
	agentID := c.Param("agentID")

	stats, err := h.bridge.GetAgentStats(agents.AgentID(agentID))
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "agent_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	response := &dtos.AgentStatsResponse{
		AgentID:         string(stats.AgentID),
		Status:          string(stats.Status),
		TotalTasks:      stats.TotalTasks,
		SuccessfulTasks: stats.SuccessfulTasks,
		FailedTasks:     stats.FailedTasks,
		ActiveTasks:     stats.ActiveTasks,
		QueuedTasks:     stats.QueuedTasks,
		SuccessRate:     stats.SuccessRate,
		LastUsed:        stats.LastUsed,
	}

	c.JSON(http.StatusOK, response)
}

// ExecuteTask executes a single agent task
// @Summary Execute task
// @Description Executes a single task with a specified agent
// @Tags Agents
// @Accept json
// @Produce json
// @Param request body dtos.ExecuteAgentTaskRequest true "Task configuration"
// @Success 200 {object} dtos.AgentResultResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/agents/execute [post]
func (h *AgentHandler) ExecuteTask(c *gin.Context) {
	var req dtos.ExecuteAgentTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	task := &agents.AgentTask{
		AgentID:     agents.AgentID(req.AgentID),
		TaskType:    req.TaskType,
		Instruction: req.Instruction,
		Context:     req.Context,
		WorkDir:     req.WorkDir,
		Files:       req.Files,
		Priority:    req.Priority,
		CreatedAt:   time.Now(),
	}

	// Parse timeout
	if req.Timeout != "" {
		if d, err := time.ParseDuration(req.Timeout); err == nil {
			task.Timeout = d
		} else {
			task.Timeout = 30 * time.Minute
		}
	} else {
		task.Timeout = 30 * time.Minute
	}

	result, err := h.bridge.ExecuteTask(c.Request.Context(), task)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "task_execution_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	response := agentResultToResponse(result)
	c.JSON(http.StatusOK, response)
}

// ExecuteParallel executes multiple tasks in parallel
// @Summary Execute parallel
// @Description Executes multiple tasks concurrently
// @Tags Agents
// @Accept json
// @Produce json
// @Param request body dtos.ExecuteParallelRequest true "Tasks to execute"
// @Success 200 {array} dtos.AgentResultResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/agents/execute-parallel [post]
func (h *AgentHandler) ExecuteParallel(c *gin.Context) {
	var req dtos.ExecuteParallelRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	tasks := make([]*agents.AgentTask, len(req.Tasks))
	for i, reqTask := range req.Tasks {
		task := &agents.AgentTask{
			AgentID:     agents.AgentID(reqTask.AgentID),
			TaskType:    reqTask.TaskType,
			Instruction: reqTask.Instruction,
			Context:     reqTask.Context,
			WorkDir:     reqTask.WorkDir,
			Files:       reqTask.Files,
			Priority:    reqTask.Priority,
			CreatedAt:   time.Now(),
		}

		// Parse timeout
		if reqTask.Timeout != "" {
			if d, err := time.ParseDuration(reqTask.Timeout); err == nil {
				task.Timeout = d
			} else {
				task.Timeout = 30 * time.Minute
			}
		} else {
			task.Timeout = 30 * time.Minute
		}

		tasks[i] = task
	}

	results, err := h.bridge.ExecuteParallel(c.Request.Context(), tasks)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "parallel_execution_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	var responses []*dtos.AgentResultResponse
	for _, result := range results {
		if result != nil {
			responses = append(responses, agentResultToResponse(result))
		}
	}

	c.JSON(http.StatusOK, responses)
}

// GetResult retrieves the result of a completed task
// @Summary Get result
// @Description Retrieves the result of a task by task ID
// @Tags Agents
// @Produce json
// @Param taskID path string true "Task ID"
// @Success 200 {object} dtos.AgentResultResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/agents/results/{taskID} [get]
func (h *AgentHandler) GetResult(c *gin.Context) {
	taskID := c.Param("taskID")

	result, err := h.bridge.GetResult(taskID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "result_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	response := agentResultToResponse(result)
	c.JSON(http.StatusOK, response)
}

// Helper functions

func capabilitiesToStrings(capabilities []agents.AgentCapability) []string {
	var result []string
	for _, cap := range capabilities {
		result = append(result, string(cap))
	}
	return result
}

func agentResultToResponse(result *agents.AgentResult) *dtos.AgentResultResponse {
	return &dtos.AgentResultResponse{
		TaskID:        result.TaskID,
		AgentID:       string(result.AgentID),
		Success:       result.Success,
		Output:        result.Output,
		ModifiedFiles: result.ModifiedFiles,
		Error:         result.Error,
		Duration:      result.Duration.Milliseconds(),
		CompletedAt:   result.CompletedAt,
	}
}
