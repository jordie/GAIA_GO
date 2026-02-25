package api

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/architect/go_wrapper/data"
	"github.com/architect/go_wrapper/stream"
)

// ReplayAPI handles session replay functionality
type ReplayAPI struct {
	extractionStore *data.ExtractionStore
	sessionStore    *data.SessionStore
	broadcaster     *stream.Broadcaster
}

// NewReplayAPI creates a new replay API handler
func NewReplayAPI(extractionStore *data.ExtractionStore, sessionStore *data.SessionStore, broadcaster *stream.Broadcaster) *ReplayAPI {
	return &ReplayAPI{
		extractionStore: extractionStore,
		sessionStore:    sessionStore,
		broadcaster:     broadcaster,
	}
}

// HandleReplaySession handles GET /api/replay/session/:id
func (ra *ReplayAPI) HandleReplaySession(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract session ID from path
	path := strings.TrimPrefix(r.URL.Path, "/api/replay/session/")
	sessionID := strings.TrimSpace(path)

	if sessionID == "" {
		http.Error(w, "session ID required", http.StatusBadRequest)
		return
	}

	// Parse query parameters
	query := r.URL.Query()
	speedStr := query.Get("speed")
	formatStr := query.Get("format")

	// Parse playback speed (default 1.0x)
	speed := 1.0
	if speedStr != "" {
		if parsed, err := strconv.ParseFloat(speedStr, 64); err == nil && parsed > 0 && parsed <= 10 {
			speed = parsed
		}
	}

	// Get session details
	session, err := ra.sessionStore.GetSession(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			http.Error(w, "Session not found", http.StatusNotFound)
		} else {
			http.Error(w, fmt.Sprintf("Failed to get session: %v", err), http.StatusInternalServerError)
		}
		return
	}

	// Get all extractions for this session
	extractions, err := ra.extractionStore.GetExtractionsBySession(sessionID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get extractions: %v", err), http.StatusInternalServerError)
		return
	}

	if len(extractions) == 0 {
		http.Error(w, "No extractions found for this session", http.StatusNotFound)
		return
	}

	// Get state changes
	stateChanges, err := ra.sessionStore.GetStateChanges(sessionID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get state changes: %v", err), http.StatusInternalServerError)
		return
	}

	// Return different formats based on request
	if formatStr == "json" {
		// Return all data as JSON (no streaming)
		response := map[string]interface{}{
			"session":        session,
			"extractions":    extractions,
			"state_changes":  stateChanges,
			"total_events":   len(extractions),
			"playback_speed": speed,
		}
		writeJSON(w, http.StatusOK, response)
		return
	}

	// Stream events via Server-Sent Events (SSE)
	ra.streamReplay(w, r, session, extractions, stateChanges, speed)
}

// streamReplay streams session replay events via SSE
func (ra *ReplayAPI) streamReplay(w http.ResponseWriter, r *http.Request, session *data.ProcessSession, extractions []*data.ExtractionEvent, stateChanges []*data.StateChange, speed float64) {
	// Set headers for SSE
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Create flush interface
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	// Send session start event
	fmt.Fprintf(w, "event: session_start\n")
	fmt.Fprintf(w, "data: {\"session_id\":\"%s\",\"agent\":\"%s\",\"started_at\":\"%s\",\"speed\":%.1f}\n\n",
		session.SessionID, session.AgentName, session.StartedAt.Format(time.RFC3339), speed)
	flusher.Flush()

	// Combine and sort all events by timestamp
	type Event struct {
		Timestamp time.Time
		Type      string
		Data      interface{}
	}

	events := make([]Event, 0, len(extractions)+len(stateChanges))

	// Add extractions
	for _, ext := range extractions {
		events = append(events, Event{
			Timestamp: ext.Timestamp,
			Type:      "extraction",
			Data:      ext,
		})
	}

	// Add state changes
	for _, state := range stateChanges {
		events = append(events, Event{
			Timestamp: state.Timestamp,
			Type:      "state_change",
			Data:      state,
		})
	}

	// Sort events by timestamp (simple bubble sort for small datasets)
	for i := 0; i < len(events); i++ {
		for j := i + 1; j < len(events); j++ {
			if events[i].Timestamp.After(events[j].Timestamp) {
				events[i], events[j] = events[j], events[i]
			}
		}
	}

	// Stream events with original timing (adjusted by speed)
	startTime := time.Now()

	for i, event := range events {
		// Check if client disconnected
		select {
		case <-r.Context().Done():
			return
		default:
		}

		// Calculate delay based on original timing
		if i > 0 {
			originalDelay := event.Timestamp.Sub(events[i-1].Timestamp)
			adjustedDelay := time.Duration(float64(originalDelay) / speed)

			// Sleep for adjusted delay
			time.Sleep(adjustedDelay)
		}

		// Send event
		eventType := event.Type
		eventData := formatEventData(event.Data)

		fmt.Fprintf(w, "event: %s\n", eventType)
		fmt.Fprintf(w, "data: %s\n\n", eventData)
		flusher.Flush()
	}

	// Send replay complete event
	duration := time.Since(startTime)
	fmt.Fprintf(w, "event: replay_complete\n")
	fmt.Fprintf(w, "data: {\"session_id\":\"%s\",\"total_events\":%d,\"duration_seconds\":%.2f,\"speed\":%.1f}\n\n",
		session.SessionID, len(events), duration.Seconds(), speed)
	flusher.Flush()
}

// formatEventData formats an event for SSE transmission
func formatEventData(d interface{}) string {
	switch v := d.(type) {
	case *data.ExtractionEvent:
		return fmt.Sprintf(`{"event_type":"%s","pattern":"%s","value":"%s","line":%d,"timestamp":"%s","risk":"%s"}`,
			v.EventType, v.Pattern, escapeJSON(v.MatchedValue), v.LineNumber, v.Timestamp.Format(time.RFC3339), v.RiskLevel)
	case *data.StateChange:
		return fmt.Sprintf(`{"state":"%s","timestamp":"%s"}`,
			v.State, v.Timestamp.Format(time.RFC3339))
	default:
		return "{}"
	}
}

// escapeJSON escapes a string for JSON
func escapeJSON(s string) string {
	s = strings.ReplaceAll(s, "\\", "\\\\")
	s = strings.ReplaceAll(s, "\"", "\\\"")
	s = strings.ReplaceAll(s, "\n", "\\n")
	s = strings.ReplaceAll(s, "\r", "\\r")
	s = strings.ReplaceAll(s, "\t", "\\t")
	return s
}

// HandleReplayControl handles POST /api/replay/control/:id
func (ra *ReplayAPI) HandleReplayControl(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract session ID from path
	path := strings.TrimPrefix(r.URL.Path, "/api/replay/control/")
	parts := strings.Split(path, "/")

	if len(parts) < 2 {
		http.Error(w, "session ID and action required", http.StatusBadRequest)
		return
	}

	sessionID := parts[0]
	action := parts[1]

	// Validate action
	validActions := map[string]bool{
		"pause":  true,
		"resume": true,
		"stop":   true,
		"skip":   true,
	}

	if !validActions[action] {
		http.Error(w, fmt.Sprintf("Invalid action: %s (valid: pause, resume, stop, skip)", action), http.StatusBadRequest)
		return
	}

	// For now, return acknowledgment
	// Full implementation would track active replay sessions
	response := map[string]interface{}{
		"session_id": sessionID,
		"action":     action,
		"status":     "acknowledged",
		"message":    "Replay control not yet implemented",
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleReplayExport handles GET /api/replay/export/:id
func (ra *ReplayAPI) HandleReplayExport(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract session ID from path
	path := strings.TrimPrefix(r.URL.Path, "/api/replay/export/")
	sessionID := strings.TrimSpace(path)

	if sessionID == "" {
		http.Error(w, "session ID required", http.StatusBadRequest)
		return
	}

	// Get export format from query
	format := r.URL.Query().Get("format")
	if format == "" {
		format = "json" // default
	}

	// Get session and extractions
	session, err := ra.sessionStore.GetSession(sessionID)
	if err != nil {
		http.Error(w, "Session not found", http.StatusNotFound)
		return
	}

	extractions, err := ra.extractionStore.GetExtractionsBySession(sessionID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get extractions: %v", err), http.StatusInternalServerError)
		return
	}

	stateChanges, err := ra.sessionStore.GetStateChanges(sessionID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to get state changes: %v", err), http.StatusInternalServerError)
		return
	}

	// Export based on format
	switch format {
	case "json":
		exportJSON(w, session, extractions, stateChanges)
	case "csv":
		exportCSV(w, session, extractions)
	case "har":
		exportHAR(w, session, extractions)
	default:
		http.Error(w, fmt.Sprintf("Unsupported format: %s (valid: json, csv, har)", format), http.StatusBadRequest)
	}
}

// exportJSON exports session data as JSON
func exportJSON(w http.ResponseWriter, session *data.ProcessSession, extractions []*data.ExtractionEvent, stateChanges []*data.StateChange) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=%s.json", session.SessionID))

	response := map[string]interface{}{
		"session":       session,
		"extractions":   extractions,
		"state_changes": stateChanges,
		"exported_at":   time.Now().Format(time.RFC3339),
	}

	writeJSON(w, http.StatusOK, response)
}

// exportCSV exports extractions as CSV
func exportCSV(w http.ResponseWriter, session *data.ProcessSession, extractions []*data.ExtractionEvent) {
	w.Header().Set("Content-Type", "text/csv")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=%s.csv", session.SessionID))

	// Write CSV header
	fmt.Fprintf(w, "Timestamp,Type,Pattern,Value,Line,Risk\n")

	// Write extractions
	for _, ext := range extractions {
		fmt.Fprintf(w, "%s,%s,%s,\"%s\",%d,%s\n",
			ext.Timestamp.Format(time.RFC3339),
			ext.EventType,
			ext.Pattern,
			strings.ReplaceAll(ext.MatchedValue, "\"", "\"\""), // Escape quotes
			ext.LineNumber,
			ext.RiskLevel)
	}
}

// exportHAR exports session as HAR (HTTP Archive) format
func exportHAR(w http.ResponseWriter, session *data.ProcessSession, extractions []*data.ExtractionEvent) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=%s.har", session.SessionID))

	// Basic HAR structure
	har := map[string]interface{}{
		"log": map[string]interface{}{
			"version": "1.2",
			"creator": map[string]string{
				"name":    "Go Wrapper Replay",
				"version": "1.0",
			},
			"entries": buildHAREntries(extractions),
		},
	}

	writeJSON(w, http.StatusOK, har)
}

// buildHAREntries converts extractions to HAR entries
func buildHAREntries(extractions []*data.ExtractionEvent) []map[string]interface{} {
	entries := make([]map[string]interface{}, 0, len(extractions))

	for _, ext := range extractions {
		entry := map[string]interface{}{
			"startedDateTime": ext.Timestamp.Format(time.RFC3339),
			"time":            0,
			"request": map[string]interface{}{
				"method": "GET",
				"url":    fmt.Sprintf("extraction://%s/%s", ext.EventType, ext.Pattern),
			},
			"response": map[string]interface{}{
				"status":     200,
				"statusText": "OK",
				"content": map[string]string{
					"text": ext.MatchedValue,
				},
			},
			"_extraction": map[string]interface{}{
				"type":       ext.EventType,
				"pattern":    ext.Pattern,
				"line":       ext.LineNumber,
				"risk_level": ext.RiskLevel,
			},
		}
		entries = append(entries, entry)
	}

	return entries
}

// RegisterReplayRoutes registers all replay API routes
func (ra *ReplayAPI) RegisterReplayRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/replay/session/", ra.HandleReplaySession)
	mux.HandleFunc("/api/replay/control/", ra.HandleReplayControl)
	mux.HandleFunc("/api/replay/export/", ra.HandleReplayExport)
}
