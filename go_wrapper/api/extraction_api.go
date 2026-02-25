package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"sync"

	"github.com/architect/go_wrapper/stream"
)

// ExtractionAPI provides HTTP endpoints for extraction monitoring
type ExtractionAPI struct {
	extractors map[string]*stream.ConfigurableExtractor
	mu         sync.RWMutex
}

// NewExtractionAPI creates a new extraction API server
func NewExtractionAPI() *ExtractionAPI {
	return &ExtractionAPI{
		extractors: make(map[string]*stream.ConfigurableExtractor),
	}
}

// RegisterExtractor adds an extractor to the API
func (api *ExtractionAPI) RegisterExtractor(agentName string, extractor *stream.ConfigurableExtractor) {
	api.mu.Lock()
	defer api.mu.Unlock()
	api.extractors[agentName] = extractor
}

// UnregisterExtractor removes an extractor
func (api *ExtractionAPI) UnregisterExtractor(agentName string) {
	api.mu.Lock()
	defer api.mu.Unlock()
	delete(api.extractors, agentName)
}

// GetExtractor retrieves an extractor by agent name
func (api *ExtractionAPI) GetExtractor(agentName string) *stream.ConfigurableExtractor {
	api.mu.RLock()
	defer api.mu.RUnlock()
	return api.extractors[agentName]
}

// SetupRoutes configures HTTP routes for the extraction API
func (api *ExtractionAPI) SetupRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/extraction/agents", api.handleListAgents)
	mux.HandleFunc("/api/extraction/events", api.handleGetEvents)
	mux.HandleFunc("/api/extraction/stats", api.handleGetStats)
	mux.HandleFunc("/api/extraction/patterns", api.handleGetPatterns)
	mux.HandleFunc("/api/extraction/patterns/add", api.handleAddPattern)
	mux.HandleFunc("/api/extraction/patterns/remove", api.handleRemovePattern)
	mux.HandleFunc("/api/extraction/config/reload", api.handleReloadConfig)
	mux.HandleFunc("/api/extraction/auto-confirm", api.handleGetAutoConfirmEvents)
}

// handleListAgents returns list of agents with extractors
func (api *ExtractionAPI) handleListAgents(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	api.mu.RLock()
	defer api.mu.RUnlock()

	agents := make([]map[string]interface{}, 0)
	for name, extractor := range api.extractors {
		stats := extractor.GetStats()
		agents = append(agents, map[string]interface{}{
			"name":  name,
			"stats": stats,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	})
}

// handleGetEvents returns extraction events for an agent
func (api *ExtractionAPI) handleGetEvents(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	agentName := r.URL.Query().Get("agent")
	if agentName == "" {
		http.Error(w, "agent parameter required", http.StatusBadRequest)
		return
	}

	extractor := api.GetExtractor(agentName)
	if extractor == nil {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	limit := 100
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil {
			limit = l
		}
	}

	eventType := r.URL.Query().Get("type")
	var events []stream.ExtractedEvent

	if eventType != "" {
		events = extractor.GetEventsByType(eventType)
	} else {
		events = extractor.GetEvents(limit)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agent":  agentName,
		"events": events,
		"count":  len(events),
	})
}

// handleGetStats returns extraction statistics
func (api *ExtractionAPI) handleGetStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	agentName := r.URL.Query().Get("agent")

	if agentName != "" {
		// Stats for specific agent
		extractor := api.GetExtractor(agentName)
		if extractor == nil {
			http.Error(w, "agent not found", http.StatusNotFound)
			return
		}

		stats := extractor.GetStats()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(stats)
		return
	}

	// Stats for all agents
	api.mu.RLock()
	defer api.mu.RUnlock()

	allStats := make(map[string]interface{})
	for name, extractor := range api.extractors {
		allStats[name] = extractor.GetStats()
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agents": allStats,
		"count":  len(allStats),
	})
}

// handleGetPatterns returns configured patterns
func (api *ExtractionAPI) handleGetPatterns(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	agentName := r.URL.Query().Get("agent")
	if agentName == "" {
		http.Error(w, "agent parameter required", http.StatusBadRequest)
		return
	}

	extractor := api.GetExtractor(agentName)
	if extractor == nil {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	config := extractor.GetConfig()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agent":    agentName,
		"version":  config.Version,
		"patterns": config.Patterns,
		"count":    len(config.Patterns),
	})
}

// handleAddPattern adds a new pattern to an agent's extractor
func (api *ExtractionAPI) handleAddPattern(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	agentName := r.URL.Query().Get("agent")
	if agentName == "" {
		http.Error(w, "agent parameter required", http.StatusBadRequest)
		return
	}

	extractor := api.GetExtractor(agentName)
	if extractor == nil {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	var pattern stream.ConfigurablePattern
	if err := json.NewDecoder(r.Body).Decode(&pattern); err != nil {
		http.Error(w, fmt.Sprintf("invalid pattern: %v", err), http.StatusBadRequest)
		return
	}

	config := extractor.GetConfig()
	if err := config.AddPattern(pattern); err != nil {
		http.Error(w, fmt.Sprintf("failed to add pattern: %v", err), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"pattern": pattern.Name,
	})
}

// handleRemovePattern removes a pattern from an agent's extractor
func (api *ExtractionAPI) handleRemovePattern(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	agentName := r.URL.Query().Get("agent")
	patternName := r.URL.Query().Get("pattern")

	if agentName == "" || patternName == "" {
		http.Error(w, "agent and pattern parameters required", http.StatusBadRequest)
		return
	}

	extractor := api.GetExtractor(agentName)
	if extractor == nil {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	config := extractor.GetConfig()
	removed := config.RemovePattern(patternName)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": removed,
		"pattern": patternName,
	})
}

// handleReloadConfig reloads patterns from config file
func (api *ExtractionAPI) handleReloadConfig(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	agentName := r.URL.Query().Get("agent")
	configPath := r.URL.Query().Get("config")

	if agentName == "" || configPath == "" {
		http.Error(w, "agent and config parameters required", http.StatusBadRequest)
		return
	}

	extractor := api.GetExtractor(agentName)
	if extractor == nil {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	if err := extractor.ReloadConfig(configPath); err != nil {
		http.Error(w, fmt.Sprintf("failed to reload config: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"agent":   agentName,
	})
}

// handleGetAutoConfirmEvents returns events that can be auto-confirmed
func (api *ExtractionAPI) handleGetAutoConfirmEvents(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	agentName := r.URL.Query().Get("agent")
	if agentName == "" {
		http.Error(w, "agent parameter required", http.StatusBadRequest)
		return
	}

	extractor := api.GetExtractor(agentName)
	if extractor == nil {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	events := extractor.GetAutoConfirmableEvents()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agent":  agentName,
		"events": events,
		"count":  len(events),
	})
}
