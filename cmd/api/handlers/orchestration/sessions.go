package orchestration

import (
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api/dtos"
	sessionmgr "github.com/jgirmay/GAIA_GO/internal/orchestration/session"
)

// SessionHandler handles session-related HTTP requests
type SessionHandler struct {
	sessionManager *sessionmgr.Manager
}

// NewSessionHandler creates a new session handler
func NewSessionHandler(manager *sessionmgr.Manager) *SessionHandler {
	return &SessionHandler{
		sessionManager: manager,
	}
}

// RegisterRoutes registers session routes
func (h *SessionHandler) RegisterRoutes(router *gin.RouterGroup) {
	sessions := router.Group("/sessions")
	{
		sessions.POST("", h.CreateSession)
		sessions.GET("", h.ListSessions)
		sessions.GET("/:sessionID", h.GetSession)
		sessions.DELETE("/:sessionID", h.DestroySession)

		sessions.POST("/:sessionID/windows", h.CreateWindow)
		sessions.POST("/:sessionID/windows/:windowID/panes", h.CreatePane)
		sessions.POST("/:sessionID/windows/:windowID/panes/:paneID/send-keys", h.SendKeys)
		sessions.GET("/:sessionID/windows/:windowID/panes/:paneID/capture", h.CapturePane)
	}
}

// CreateSession creates a new GAIA session
// @Summary Create a new development session
// @Description Creates a new tmux-based development session
// @Tags Sessions
// @Accept json
// @Produce json
// @Param request body dtos.CreateSessionRequest true "Session configuration"
// @Success 201 {object} dtos.SessionResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/sessions [post]
func (h *SessionHandler) CreateSession(c *gin.Context) {
	var req dtos.CreateSessionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	config := sessionmgr.SessionConfig{
		Name:        req.Name,
		ProjectPath: req.ProjectPath,
		Shell:       req.Shell,
		Metadata:    req.Metadata,
		Tags:        req.Tags,
	}

	session, err := h.sessionManager.CreateSession(c.Request.Context(), config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "session_creation_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusCreated, sessionToResponse(session))
}

// ListSessions lists all active sessions
// @Summary List all sessions
// @Description Returns a list of all active GAIA sessions
// @Tags Sessions
// @Produce json
// @Success 200 {array} dtos.SessionResponse
// @Router /api/orchestration/sessions [get]
func (h *SessionHandler) ListSessions(c *gin.Context) {
	sessions, err := h.sessionManager.ListSessions()
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "list_sessions_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	var responses []*dtos.SessionResponse
	for _, session := range sessions {
		responses = append(responses, sessionToResponse(session))
	}

	c.JSON(http.StatusOK, responses)
}

// GetSession retrieves a specific session
// @Summary Get session details
// @Description Retrieves details of a specific session by ID
// @Tags Sessions
// @Produce json
// @Param sessionID path string true "Session ID"
// @Success 200 {object} dtos.SessionResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/sessions/{sessionID} [get]
func (h *SessionHandler) GetSession(c *gin.Context) {
	sessionID := c.Param("sessionID")

	session, err := h.sessionManager.GetSession(sessionID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "session_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, sessionToResponse(session))
}

// DestroySession destroys a session
// @Summary Destroy a session
// @Description Kills a tmux session and removes it from tracking
// @Tags Sessions
// @Param sessionID path string true "Session ID"
// @Success 204
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/sessions/{sessionID} [delete]
func (h *SessionHandler) DestroySession(c *gin.Context) {
	sessionID := c.Param("sessionID")

	if err := h.sessionManager.DestroySession(c.Request.Context(), sessionID); err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "session_destruction_failed",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.Status(http.StatusNoContent)
}

// CreateWindow creates a new window in a session
// @Summary Create a window
// @Description Adds a new window to an existing session
// @Tags Sessions
// @Accept json
// @Produce json
// @Param sessionID path string true "Session ID"
// @Param request body dtos.CreateWindowRequest true "Window configuration"
// @Success 201 {object} dtos.WindowResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/sessions/{sessionID}/windows [post]
func (h *SessionHandler) CreateWindow(c *gin.Context) {
	sessionID := c.Param("sessionID")

	var req dtos.CreateWindowRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	config := sessionmgr.WindowConfig{
		Name: req.Name,
	}

	window, err := h.sessionManager.CreateWindow(c.Request.Context(), sessionID, config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "window_creation_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusCreated, windowToResponse(window))
}

// CreatePane creates a new pane in a window
// @Summary Create a pane
// @Description Splits a window to create a new pane
// @Tags Sessions
// @Accept json
// @Produce json
// @Param sessionID path string true "Session ID"
// @Param windowID path string true "Window ID"
// @Param request body dtos.CreatePaneRequest true "Pane configuration"
// @Success 201 {object} dtos.PaneResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/sessions/{sessionID}/windows/{windowID}/panes [post]
func (h *SessionHandler) CreatePane(c *gin.Context) {
	sessionID := c.Param("sessionID")
	windowID := c.Param("windowID")

	var req dtos.CreatePaneRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	config := sessionmgr.PaneConfig{
		Command:   req.Command,
		WorkDir:   req.WorkDir,
		Reattach:  false,
		Vertical:  req.Vertical,
	}

	pane, err := h.sessionManager.CreatePane(c.Request.Context(), sessionID, windowID, config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "pane_creation_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusCreated, paneToResponse(pane))
}

// SendKeys sends commands to a pane
// @Summary Send keys to pane
// @Description Sends keyboard input to a specific pane
// @Tags Sessions
// @Accept json
// @Param sessionID path string true "Session ID"
// @Param windowID path string true "Window ID"
// @Param paneID path string true "Pane ID"
// @Param request body dtos.SendKeysRequest true "Keys to send"
// @Success 200 {object} dtos.SuccessResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/sessions/{sessionID}/windows/{windowID}/panes/{paneID}/send-keys [post]
func (h *SessionHandler) SendKeys(c *gin.Context) {
	sessionID := c.Param("sessionID")
	windowID := c.Param("windowID")
	paneID := c.Param("paneID")

	var req dtos.SendKeysRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	if err := h.sessionManager.SendKeys(c.Request.Context(), sessionID, windowID, paneID, req.Keys, req.SendEnter); err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "send_keys_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, dtos.SuccessResponse{
		Message: "Keys sent successfully",
	})
}

// CapturePane captures the current contents of a pane
// @Summary Capture pane output
// @Description Retrieves the current text displayed in a pane
// @Tags Sessions
// @Produce json
// @Param sessionID path string true "Session ID"
// @Param windowID path string true "Window ID"
// @Param paneID path string true "Pane ID"
// @Success 200 {object} dtos.CaptureResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/sessions/{sessionID}/windows/{windowID}/panes/{paneID}/capture [get]
func (h *SessionHandler) CapturePane(c *gin.Context) {
	sessionID := c.Param("sessionID")
	windowID := c.Param("windowID")
	paneID := c.Param("paneID")

	output, err := h.sessionManager.CapturePane(c.Request.Context(), sessionID, windowID, paneID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "capture_failed",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, dtos.CaptureResponse{
		Content: output,
		Pane:    fmt.Sprintf("%s:%s.%s", sessionID, windowID, paneID),
	})
}

// Helper functions

func sessionToResponse(session *sessionmgr.Session) *dtos.SessionResponse {
	return &dtos.SessionResponse{
		ID:          session.ID,
		Name:        session.Name,
		ProjectPath: session.ProjectPath,
		Status:      string(session.Status),
		CreatedAt:   session.CreatedAt,
		LastActive:  session.LastActive,
		Metadata:    session.Metadata,
		Tags:        session.Tags,
	}
}

func windowToResponse(window *sessionmgr.Window) *dtos.WindowResponse {
	return &dtos.WindowResponse{
		ID:        window.ID,
		Name:      window.Name,
		Index:     window.Index,
		Active:    window.Active,
		CreatedAt: window.CreatedAt,
	}
}

func paneToResponse(pane *sessionmgr.Pane) *dtos.PaneResponse {
	return &dtos.PaneResponse{
		ID:        pane.ID,
		Index:     pane.Index,
		Command:   pane.Command,
		WorkDir:   pane.WorkDir,
		Active:    pane.Active,
		CreatedAt: pane.CreatedAt,
	}
}
