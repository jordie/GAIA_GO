package api

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/architect/go_wrapper/data"
)

// QueryAPI handles database query endpoints
type QueryAPI struct {
	extractionStore *data.ExtractionStore
	sessionStore    *data.SessionStore
}

// NewQueryAPI creates a new query API handler
func NewQueryAPI(extractionStore *data.ExtractionStore, sessionStore *data.SessionStore) *QueryAPI {
	return &QueryAPI{
		extractionStore: extractionStore,
		sessionStore:    sessionStore,
	}
}

// HandleQueryExtractions handles GET /api/query/extractions
func (qa *QueryAPI) HandleQueryExtractions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Parse query parameters
	query := r.URL.Query()
	agentName := query.Get("agent")
	eventType := query.Get("type")
	pattern := query.Get("pattern")
	sessionID := query.Get("session")
	limitStr := query.Get("limit")

	if agentName == "" && sessionID == "" {
		http.Error(w, "agent or session parameter required", http.StatusBadRequest)
		return
	}

	limit := 100 // default
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil {
			limit = parsed
		}
	}

	var extractions []*data.ExtractionEvent
	var err error

	// Query based on parameters
	if sessionID != "" {
		extractions, err = qa.extractionStore.GetExtractionsBySession(sessionID)
	} else if pattern != "" {
		extractions, err = qa.extractionStore.GetExtractionsByPattern(agentName, pattern, limit)
	} else if eventType != "" {
		extractions, err = qa.extractionStore.GetExtractionsByType(agentName, eventType, limit)
	} else {
		extractions, err = qa.extractionStore.GetExtractionsByAgent(agentName, limit)
	}

	if err != nil {
		http.Error(w, fmt.Sprintf("Query failed: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"extractions": extractions,
		"total":       len(extractions),
		"filters": map[string]string{
			"agent":   agentName,
			"type":    eventType,
			"pattern": pattern,
			"session": sessionID,
		},
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleQueryCodeBlocks handles GET /api/query/code-blocks
func (qa *QueryAPI) HandleQueryCodeBlocks(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	agentName := query.Get("agent")
	language := query.Get("language")
	limitStr := query.Get("limit")

	if agentName == "" {
		http.Error(w, "agent parameter required", http.StatusBadRequest)
		return
	}

	limit := 100
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil {
			limit = parsed
		}
	}

	blocks, err := qa.extractionStore.GetCodeBlocks(agentName, language, limit)
	if err != nil {
		http.Error(w, fmt.Sprintf("Query failed: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"code_blocks": blocks,
		"total":       len(blocks),
		"filters": map[string]string{
			"agent":    agentName,
			"language": language,
		},
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleQuerySessions handles GET /api/query/sessions
func (qa *QueryAPI) HandleQuerySessions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	agentName := query.Get("agent")
	daysStr := query.Get("days")
	limitStr := query.Get("limit")
	activeOnly := query.Get("active") == "true"

	var sessions []*data.ProcessSession
	var err error

	if activeOnly {
		// Get only active sessions
		sessions, err = qa.sessionStore.GetActiveSessions()
	} else if agentName != "" && daysStr != "" {
		// Get sessions within time range
		days, _ := strconv.Atoi(daysStr)
		if days <= 0 {
			days = 7 // default to 7 days
		}
		sessions, err = qa.sessionStore.GetSessionHistory(agentName, days)
	} else if agentName != "" {
		// Get recent sessions
		limit := 50
		if limitStr != "" {
			if parsed, err := strconv.Atoi(limitStr); err == nil {
				limit = parsed
			}
		}
		sessions, err = qa.sessionStore.GetSessionsByAgent(agentName, limit)
	} else {
		http.Error(w, "agent parameter required (or active=true)", http.StatusBadRequest)
		return
	}

	if err != nil {
		http.Error(w, fmt.Sprintf("Query failed: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"sessions": sessions,
		"total":    len(sessions),
		"filters": map[string]interface{}{
			"agent":  agentName,
			"days":   daysStr,
			"active": activeOnly,
		},
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleQuerySession handles GET /api/query/session/:id
func (qa *QueryAPI) HandleQuerySession(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract session ID from path
	path := strings.TrimPrefix(r.URL.Path, "/api/query/session/")
	sessionID := strings.TrimSpace(path)

	if sessionID == "" {
		http.Error(w, "session ID required", http.StatusBadRequest)
		return
	}

	// Get session details
	session, err := qa.sessionStore.GetSession(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			http.Error(w, "Session not found", http.StatusNotFound)
		} else {
			http.Error(w, fmt.Sprintf("Query failed: %v", err), http.StatusInternalServerError)
		}
		return
	}

	// Get state changes
	stateChanges, err := qa.sessionStore.GetStateChanges(sessionID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get state changes: %v", err), http.StatusInternalServerError)
		return
	}

	// Get extractions for this session
	extractions, err := qa.extractionStore.GetExtractionsBySession(sessionID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get extractions: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"session":          session,
		"state_changes":    stateChanges,
		"extractions":      extractions,
		"extraction_count": len(extractions),
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleQueryAgentStats handles GET /api/query/stats/agent/:name
func (qa *QueryAPI) HandleQueryAgentStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract agent name from path
	path := strings.TrimPrefix(r.URL.Path, "/api/query/stats/agent/")
	agentName := strings.TrimSpace(path)

	if agentName == "" {
		http.Error(w, "agent name required", http.StatusBadRequest)
		return
	}

	// Get extraction stats
	extractionStats, err := qa.extractionStore.GetExtractionStats(agentName)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get extraction stats: %v", err), http.StatusInternalServerError)
		return
	}

	// Get session stats
	sessions, err := qa.sessionStore.GetSessionsByAgent(agentName, 1000)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get sessions: %v", err), http.StatusInternalServerError)
		return
	}

	// Calculate session statistics
	totalSessions := len(sessions)
	completedSessions := 0
	activeSessions := 0
	totalLines := 0
	successfulSessions := 0
	var totalDuration time.Duration
	var firstSession, lastSession time.Time

	for i, session := range sessions {
		if i == 0 {
			lastSession = session.StartedAt
		}
		if i == len(sessions)-1 {
			firstSession = session.StartedAt
		}

		totalLines += session.TotalLinesProcessed

		if session.EndedAt != nil {
			completedSessions++
			duration := session.EndedAt.Sub(session.StartedAt)
			totalDuration += duration

			if session.ExitCode != nil && *session.ExitCode == 0 {
				successfulSessions++
			}
		} else {
			activeSessions++
		}
	}

	avgDuration := time.Duration(0)
	if completedSessions > 0 {
		avgDuration = totalDuration / time.Duration(completedSessions)
	}

	successRate := 0.0
	if completedSessions > 0 {
		successRate = float64(successfulSessions) / float64(completedSessions)
	}

	response := map[string]interface{}{
		"agent_name":  agentName,
		"extractions": extractionStats,
		"sessions": map[string]interface{}{
			"total":                totalSessions,
			"completed":            completedSessions,
			"active":               activeSessions,
			"successful":           successfulSessions,
			"total_lines":          totalLines,
			"avg_duration_seconds": avgDuration.Seconds(),
			"success_rate":         successRate,
			"first_session":        firstSession,
			"last_session":         lastSession,
		},
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleQueryTimeline handles GET /api/query/timeline
func (qa *QueryAPI) HandleQueryTimeline(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	agentName := query.Get("agent")
	fromStr := query.Get("from")
	toStr := query.Get("to")
	limitStr := query.Get("limit")

	if agentName == "" {
		http.Error(w, "agent parameter required", http.StatusBadRequest)
		return
	}

	limit := 1000
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil {
			limit = parsed
		}
	}

	// Parse time range (if provided)
	var fromTime, toTime time.Time
	if fromStr != "" {
		if parsed, err := time.Parse(time.RFC3339, fromStr); err == nil {
			fromTime = parsed
		}
	}
	if toStr != "" {
		if parsed, err := time.Parse(time.RFC3339, toStr); err == nil {
			toTime = parsed
		}
	}

	// Get recent extractions
	extractions, err := qa.extractionStore.GetExtractionsByAgent(agentName, limit)
	if err != nil {
		http.Error(w, fmt.Sprintf("Query failed: %v", err), http.StatusInternalServerError)
		return
	}

	// Filter by time range if specified
	filteredExtractions := make([]*data.ExtractionEvent, 0)
	for _, ext := range extractions {
		if !fromTime.IsZero() && ext.Timestamp.Before(fromTime) {
			continue
		}
		if !toTime.IsZero() && ext.Timestamp.After(toTime) {
			continue
		}
		filteredExtractions = append(filteredExtractions, ext)
	}

	// Group by time buckets (1 hour intervals)
	timeline := make(map[string]map[string]int)
	for _, ext := range filteredExtractions {
		hour := ext.Timestamp.Truncate(time.Hour).Format(time.RFC3339)
		if timeline[hour] == nil {
			timeline[hour] = make(map[string]int)
		}
		timeline[hour][ext.EventType]++
	}

	response := map[string]interface{}{
		"agent":       agentName,
		"timeline":    timeline,
		"total":       len(filteredExtractions),
		"from":        fromTime,
		"to":          toTime,
		"extractions": filteredExtractions,
	}

	writeJSON(w, http.StatusOK, response)
}

// RegisterQueryRoutes registers all query API routes with the given mux
func (qa *QueryAPI) RegisterQueryRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/query/extractions", qa.HandleQueryExtractions)
	mux.HandleFunc("/api/query/code-blocks", qa.HandleQueryCodeBlocks)
	mux.HandleFunc("/api/query/sessions", qa.HandleQuerySessions)
	mux.HandleFunc("/api/query/session/", qa.HandleQuerySession)
	mux.HandleFunc("/api/query/stats/agent/", qa.HandleQueryAgentStats)
	mux.HandleFunc("/api/query/timeline", qa.HandleQueryTimeline)
}
