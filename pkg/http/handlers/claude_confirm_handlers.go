package handlers

import (
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/jgirmay/GAIA_GO/pkg/services/claude_confirm"
)

// ClaudeConfirmHandlers handles HTTP requests for Claude confirmation management
type ClaudeConfirmHandlers struct {
	confirmationService *claude_confirm.ConfirmationService
}

// NewClaudeConfirmHandlers creates a new handler
func NewClaudeConfirmHandlers(svc *claude_confirm.ConfirmationService) *ClaudeConfirmHandlers {
	return &ClaudeConfirmHandlers{
		confirmationService: svc,
	}
}

// RegisterRoutes registers all Claude confirmation routes
func (h *ClaudeConfirmHandlers) RegisterRoutes(router *chi.Mux) {
	router.Route("/api/claude/confirm", func(r chi.Router) {
		// Confirmation request processing
		r.Post("/request", h.ProcessConfirmation)
		r.Get("/history/{sessionID}", h.GetConfirmationHistory)
		r.Get("/stats/{sessionID}", h.GetSessionStats)

		// Pattern management
		r.Get("/patterns", h.ListPatterns)
		r.Post("/patterns", h.CreatePattern)
		r.Get("/patterns/{patternID}", h.GetPattern)
		r.Put("/patterns/{patternID}", h.UpdatePattern)
		r.Delete("/patterns/{patternID}", h.DeletePattern)

		// Session preferences
		r.Get("/preferences/{sessionID}", h.GetSessionPreference)
		r.Post("/preferences/{sessionID}", h.SetSessionPreference)

		// Global statistics
		r.Get("/stats", h.GetGlobalStats)
		r.Get("/patterns/stats/{patternID}", h.GetPatternStats)
	})
}

// ProcessConfirmation handles a new confirmation request
func (h *ClaudeConfirmHandlers) ProcessConfirmation(w http.ResponseWriter, r *http.Request) {
	var req claude_confirm.ConfirmationRequest

	if err := readJSONBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request format", "invalid_format")
		return
	}

	// Validate required fields
	if req.SessionID == "" || req.PermissionType == "" || req.ResourceType == "" {
		sendError(w, http.StatusBadRequest, "Missing required fields", nil)
		return
	}

	// Process the confirmation
	decision, reason, err := h.confirmationService.ProcessConfirmation(r.Context(), &req)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to process confirmation", err)
		return
	}

	response := map[string]interface{}{
		"decision": decision,
		"reason":   reason,
		"request_id": req.ID,
		"timestamp": req.Timestamp,
	}

	sendJSON(w, http.StatusOK, response)
}

// GetConfirmationHistory retrieves confirmation history for a session
func (h *ClaudeConfirmHandlers) GetConfirmationHistory(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")
	if sessionID == "" {
		sendError(w, http.StatusBadRequest, "Missing sessionID", nil)
		return
	}

	limit := 50 // default
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil {
			limit = parsed
		}
	}

	history, err := h.confirmationService.GetConfirmationHistory(r.Context(), sessionID, limit)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to get history", err)
		return
	}

	sendJSON(w, http.StatusOK, map[string]interface{}{
		"session_id": sessionID,
		"count":      len(history),
		"history":    history,
	})
}

// GetSessionStats returns statistics for a session
func (h *ClaudeConfirmHandlers) GetSessionStats(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")
	if sessionID == "" {
		sendError(w, http.StatusBadRequest, "Missing sessionID", nil)
		return
	}

	stats, err := h.confirmationService.GetSessionStats(r.Context(), sessionID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to get stats", err)
		return
	}

	sendJSON(w, http.StatusOK, map[string]interface{}{
		"session_id":             sessionID,
		"total_requests":         stats.TotalRequests,
		"approved_by_pattern":    stats.ApprovedByPattern,
		"approved_by_ai":         stats.ApprovedByAI,
		"approved_by_user":       stats.ApprovedByUser,
		"denied":                 stats.Denied,
		"approval_rate":          float64(stats.ApprovedByPattern+stats.ApprovedByAI) / float64(stats.TotalRequests) * 100,
		"average_response_time_ms": stats.AverageResponseTime,
	})
}

// ListPatterns returns all approval patterns
func (h *ClaudeConfirmHandlers) ListPatterns(w http.ResponseWriter, r *http.Request) {
	var enabled *bool
	if e := r.URL.Query().Get("enabled"); e != "" {
		b := e == "true"
		enabled = &b
	}

	limit := 100
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil {
			limit = parsed
		}
	}

	patterns, err := h.confirmationService.ListPatterns(r.Context(), enabled, limit)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to list patterns", err)
		return
	}

	sendJSON(w, http.StatusOK, map[string]interface{}{
		"count":    len(patterns),
		"patterns": patterns,
	})
}

// CreatePattern creates a new approval pattern
func (h *ClaudeConfirmHandlers) CreatePattern(w http.ResponseWriter, r *http.Request) {
	var pattern claude_confirm.ApprovalPattern

	if err := readJSON(r, &pattern); err != nil {
		sendError(w, http.StatusBadRequest, "Invalid pattern format", err)
		return
	}

	// Validate required fields
	if pattern.Name == "" || pattern.PermissionType == "" || pattern.ResourceType == "" {
		sendError(w, http.StatusBadRequest, "Missing required pattern fields", nil)
		return
	}

	if err := h.confirmationService.CreatePattern(r.Context(), &pattern); err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to create pattern", err)
		return
	}

	sendJSON(w, http.StatusCreated, map[string]interface{}{
		"pattern_id": pattern.ID,
		"message":    "Pattern created successfully",
	})
}

// GetPattern retrieves a specific pattern
func (h *ClaudeConfirmHandlers) GetPattern(w http.ResponseWriter, r *http.Request) {
	patternID := chi.URLParam(r, "patternID")
	if patternID == "" {
		sendError(w, http.StatusBadRequest, "Missing patternID", nil)
		return
	}

	pattern, err := h.confirmationService.GetPattern(r.Context(), patternID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to get pattern", err)
		return
	}

	if pattern == nil {
		sendError(w, http.StatusNotFound, "Pattern not found", nil)
		return
	}

	sendJSON(w, http.StatusOK, pattern)
}

// UpdatePattern updates an existing pattern
func (h *ClaudeConfirmHandlers) UpdatePattern(w http.ResponseWriter, r *http.Request) {
	patternID := chi.URLParam(r, "patternID")
	if patternID == "" {
		sendError(w, http.StatusBadRequest, "Missing patternID", nil)
		return
	}

	var updates map[string]interface{}
	if err := readJSON(r, &updates); err != nil {
		sendError(w, http.StatusBadRequest, "Invalid update format", err)
		return
	}

	if err := h.confirmationService.UpdatePattern(r.Context(), patternID, updates); err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to update pattern", err)
		return
	}

	sendJSON(w, http.StatusOK, map[string]interface{}{
		"message": "Pattern updated successfully",
	})
}

// DeletePattern deletes a pattern
func (h *ClaudeConfirmHandlers) DeletePattern(w http.ResponseWriter, r *http.Request) {
	patternID := chi.URLParam(r, "patternID")
	if patternID == "" {
		sendError(w, http.StatusBadRequest, "Missing patternID", nil)
		return
	}

	if err := h.confirmationService.DeletePattern(r.Context(), patternID); err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to delete pattern", err)
		return
	}

	sendJSON(w, http.StatusOK, map[string]interface{}{
		"message": "Pattern deleted successfully",
	})
}

// GetSessionPreference retrieves session approval preferences
func (h *ClaudeConfirmHandlers) GetSessionPreference(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")
	if sessionID == "" {
		sendError(w, http.StatusBadRequest, "Missing sessionID", nil)
		return
	}

	pref, err := h.confirmationService.GetSessionPreference(r.Context(), sessionID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to get preference", err)
		return
	}

	if pref == nil {
		// Return default preferences
		sendJSON(w, http.StatusOK, map[string]interface{}{
			"session_id":       sessionID,
			"allow_all":        false,
			"use_ai_fallback":  true,
			"pattern_ids":      []string{},
		})
		return
	}

	sendJSON(w, http.StatusOK, pref)
}

// SetSessionPreference sets approval preferences for a session
func (h *ClaudeConfirmHandlers) SetSessionPreference(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")
	if sessionID == "" {
		sendError(w, http.StatusBadRequest, "Missing sessionID", nil)
		return
	}

	var pref claude_confirm.SessionApprovalPreference
	if err := readJSON(r, &pref); err != nil {
		sendError(w, http.StatusBadRequest, "Invalid preference format", err)
		return
	}

	pref.SessionID = sessionID

	if err := h.confirmationService.SetSessionPreference(r.Context(), &pref); err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to set preference", err)
		return
	}

	sendJSON(w, http.StatusOK, map[string]interface{}{
		"message": "Preference updated successfully",
	})
}

// GetGlobalStats returns global confirmation statistics
func (h *ClaudeConfirmHandlers) GetGlobalStats(w http.ResponseWriter, r *http.Request) {
	stats, err := h.confirmationService.GetGlobalStats(r.Context())
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to get stats", err)
		return
	}

	sendJSON(w, http.StatusOK, stats)
}

// GetPatternStats returns statistics for a specific pattern
func (h *ClaudeConfirmHandlers) GetPatternStats(w http.ResponseWriter, r *http.Request) {
	patternID := chi.URLParam(r, "patternID")
	if patternID == "" {
		sendError(w, http.StatusBadRequest, "Missing patternID", nil)
		return
	}

	pm := claude_confirm.NewPatternMatcher(nil) // Would need db from context
	stats, err := pm.GetPatternStats(r.Context(), patternID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "Failed to get pattern stats", err)
		return
	}

	sendJSON(w, http.StatusOK, stats)
}
