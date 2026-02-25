package tmux

import (
	"log"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
)

// RegisterRoutes registers tmux session grouping routes
func RegisterRoutes(router *gin.RouterGroup, service *Service) {
	group := router.Group("/tmux")
	{
		// Get grouped sessions
		group.GET("/groups", handleGetGroupedSessions(service))

		// Project management
		group.GET("/projects", handleGetProjects(service))

		// Session assignment
		group.POST("/assign", handleAssignSession(service))

		// Session configuration
		group.POST("/environment", handleSetEnvironment(service))
		group.POST("/worker", handleSetWorker(service))

		// Group preferences
		group.POST("/toggle/:group_id", handleToggleCollapsed(service))
		group.POST("/collapse-all", handleCollapseAll(service))
		group.POST("/expand-all", handleExpandAll(service))

		// Auto-assignment
		group.POST("/auto-assign", handleAutoAssign(service))
	}
}

// handleGetGroupedSessions returns all sessions grouped by project
func handleGetGroupedSessions(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()

		grouped, err := service.GetSessionsGrouped(ctx)
		if err != nil {
			log.Printf("[ERROR] Failed to get grouped sessions: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		// Fetch user preferences if authenticated
		userID, err := middleware.GetUserID(c)
		if err == nil && userID > 0 {
			prefs, err := service.GetGroupPreferences(ctx, int(userID))
			if err == nil {
				// Apply preferences to groups
				for i := range grouped.Groups {
					if collapsed, exists := prefs[grouped.Groups[i].ID]; exists {
						grouped.Groups[i].Collapsed = collapsed
					}
				}
			}
		}

		api.RespondWith(c, http.StatusOK, gin.H{"data": grouped})
	}
}

// handleGetProjects returns all projects
func handleGetProjects(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()

		projects, err := service.GetProjects(ctx)
		if err != nil {
			log.Printf("[ERROR] Failed to get projects: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{"data": projects})
	}
}

// handleAssignSession assigns a session to a project
func handleAssignSession(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req AssignSessionRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		if req.SessionName == "" {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		ctx := c.Request.Context()
		if err := service.AssignSessionToProject(ctx, req.SessionName, req.ProjectID); err != nil {
			log.Printf("[ERROR] Failed to assign session: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"success": true,
			"message": "Session assigned successfully",
		})
	}
}

// handleSetEnvironment sets the environment for a session
func handleSetEnvironment(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req SetEnvironmentRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		if req.SessionName == "" {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		if req.Environment == "" {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		ctx := c.Request.Context()
		if err := service.SetSessionEnvironment(ctx, req.SessionName, req.Environment); err != nil {
			log.Printf("[ERROR] Failed to set environment: %v", err)
			api.RespondWithError(c, api.NewError(
				api.ErrCodeInvalidRequest,
				err.Error(),
				http.StatusBadRequest,
			))
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"success": true,
			"message": "Environment set successfully",
		})
	}
}

// handleSetWorker marks a session as a worker
func handleSetWorker(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req SetWorkerRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		if req.SessionName == "" {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		ctx := c.Request.Context()
		if err := service.SetSessionWorker(ctx, req.SessionName, req.IsWorker); err != nil {
			log.Printf("[ERROR] Failed to set worker flag: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"success": true,
			"message": "Worker flag set successfully",
		})
	}
}

// handleToggleCollapsed toggles the collapsed state of a group
func handleToggleCollapsed(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		groupID := c.Param("group_id")
		if groupID == "" {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		userID, err := middleware.GetUserID(c)
		if err != nil || userID <= 0 {
			api.RespondWithError(c, api.ErrUnauthorized)
			return
		}

		ctx := c.Request.Context()
		newState, err := service.ToggleGroupCollapsed(ctx, int(userID), groupID)
		if err != nil {
			log.Printf("[ERROR] Failed to toggle group: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"success":   true,
			"collapsed": newState,
		})
	}
}

// handleCollapseAll collapses all groups for a user
func handleCollapseAll(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := middleware.GetUserID(c)
		if err != nil || userID <= 0 {
			api.RespondWithError(c, api.ErrUnauthorized)
			return
		}

		ctx := c.Request.Context()

		// Get all projects to collapse
		projects, err := service.GetProjects(ctx)
		if err != nil {
			log.Printf("[ERROR] Failed to get projects: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		groupIDs := make([]string, 0)
		for _, p := range projects {
			groupIDs = append(groupIDs, "project_"+strconv.Itoa(p.ID))
		}

		if err := service.SetCollapsedBulk(ctx, int(userID), groupIDs, true); err != nil {
			log.Printf("[ERROR] Failed to collapse all: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"success": true,
			"message": "All groups collapsed",
		})
	}
}

// handleExpandAll expands all groups for a user
func handleExpandAll(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := middleware.GetUserID(c)
		if err != nil || userID <= 0 {
			api.RespondWithError(c, api.ErrUnauthorized)
			return
		}

		ctx := c.Request.Context()

		// Get all projects to expand
		projects, err := service.GetProjects(ctx)
		if err != nil {
			log.Printf("[ERROR] Failed to get projects: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		groupIDs := make([]string, 0)
		for _, p := range projects {
			groupIDs = append(groupIDs, "project_"+strconv.Itoa(p.ID))
		}

		if err := service.SetCollapsedBulk(ctx, int(userID), groupIDs, false); err != nil {
			log.Printf("[ERROR] Failed to expand all: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{
			"success": true,
			"message": "All groups expanded",
		})
	}
}

// handleAutoAssign performs auto-assignment of sessions
func handleAutoAssign(service *Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()

		result, err := service.AutoAssignSessions(ctx)
		if err != nil {
			log.Printf("[ERROR] Failed to auto-assign sessions: %v", err)
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		api.RespondWith(c, http.StatusOK, gin.H{"data": result})
	}
}
