package testing

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"time"
)

// MockServer provides a mock API server for testing
type MockServer struct {
	Server *httptest.Server
	mu     sync.RWMutex
	agents map[string]*MockAgent
}

// MockAgent represents a mock agent
type MockAgent struct {
	Name      string    `json:"name"`
	Command   string    `json:"command"`
	PID       int       `json:"pid"`
	Status    string    `json:"status"`
	StartedAt time.Time `json:"started_at"`
	Env       string    `json:"env,omitempty"`
}

// NewMockServer creates a new mock API server
func NewMockServer() *MockServer {
	ms := &MockServer{
		agents: make(map[string]*MockAgent),
	}

	mux := http.NewServeMux()

	// Health endpoint
	mux.HandleFunc("/api/health", ms.handleHealth)

	// Agents endpoints
	mux.HandleFunc("/api/agents", ms.handleAgents)
	mux.HandleFunc("/api/agents/", ms.handleAgentByName)

	// Metrics endpoint
	mux.HandleFunc("/api/metrics", ms.handleMetrics)
	mux.HandleFunc("/api/metrics/prometheus", ms.handlePrometheus)
	mux.HandleFunc("/api/metrics/influxdb", ms.handleInfluxDB)

	ms.Server = httptest.NewServer(mux)
	return ms
}

// Close shuts down the mock server
func (ms *MockServer) Close() {
	ms.Server.Close()
}

// AddAgent adds a mock agent
func (ms *MockServer) AddAgent(name, command string, pid int) {
	ms.mu.Lock()
	defer ms.mu.Unlock()

	ms.agents[name] = &MockAgent{
		Name:      name,
		Command:   command,
		PID:       pid,
		Status:    "running",
		StartedAt: time.Now(),
	}
}

// RemoveAgent removes a mock agent
func (ms *MockServer) RemoveAgent(name string) {
	ms.mu.Lock()
	defer ms.mu.Unlock()
	delete(ms.agents, name)
}

// GetAgent gets a mock agent by name
func (ms *MockServer) GetAgent(name string) *MockAgent {
	ms.mu.RLock()
	defer ms.mu.RUnlock()
	return ms.agents[name]
}

func (ms *MockServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ms.mu.RLock()
	agentCount := len(ms.agents)
	ms.mu.RUnlock()

	health := map[string]interface{}{
		"status":     "healthy",
		"uptime":     "1h0m0s",
		"started_at": time.Now().Add(-1 * time.Hour).Format(time.RFC3339),
		"agents":     agentCount,
		"version":    "1.0.0-test",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health)
}

func (ms *MockServer) handleAgents(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		ms.handleListAgents(w, r)
	case http.MethodPost:
		ms.handleCreateAgent(w, r)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (ms *MockServer) handleListAgents(w http.ResponseWriter, r *http.Request) {
	ms.mu.RLock()
	defer ms.mu.RUnlock()

	agents := make([]MockAgent, 0, len(ms.agents))
	for _, agent := range ms.agents {
		agents = append(agents, *agent)
	}

	response := map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (ms *MockServer) handleCreateAgent(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name    string `json:"name"`
		Command string `json:"command"`
		Args    string `json:"args,omitempty"`
		Env     string `json:"env,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	if req.Name == "" || req.Command == "" {
		http.Error(w, "Name and command are required", http.StatusBadRequest)
		return
	}

	ms.mu.Lock()
	if _, exists := ms.agents[req.Name]; exists {
		ms.mu.Unlock()
		http.Error(w, "Agent already exists", http.StatusConflict)
		return
	}

	agent := &MockAgent{
		Name:      req.Name,
		Command:   req.Command,
		PID:       1000 + len(ms.agents),
		Status:    "running",
		StartedAt: time.Now(),
		Env:       req.Env,
	}
	ms.agents[req.Name] = agent
	ms.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(agent)
}

func (ms *MockServer) handleAgentByName(w http.ResponseWriter, r *http.Request) {
	// Extract agent name from path
	parts := strings.Split(r.URL.Path, "/")
	if len(parts) < 4 {
		http.Error(w, "Invalid path", http.StatusBadRequest)
		return
	}
	agentName := parts[3]

	// Handle stream endpoint
	if len(parts) == 5 && parts[4] == "stream" {
		ms.handleAgentStreamRequest(w, r, agentName)
		return
	}

	// Handle command endpoint
	if len(parts) == 5 && parts[4] == "command" {
		ms.handleAgentCommand(w, r, agentName)
		return
	}

	switch r.Method {
	case http.MethodGet:
		ms.handleGetAgent(w, r, agentName)
	case http.MethodDelete:
		ms.handleDeleteAgent(w, r, agentName)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (ms *MockServer) handleGetAgent(w http.ResponseWriter, r *http.Request, name string) {
	ms.mu.RLock()
	agent, exists := ms.agents[name]
	ms.mu.RUnlock()

	if !exists {
		http.Error(w, "Agent not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(agent)
}

func (ms *MockServer) handleDeleteAgent(w http.ResponseWriter, r *http.Request, name string) {
	ms.mu.Lock()
	defer ms.mu.Unlock()

	if _, exists := ms.agents[name]; !exists {
		http.Error(w, "Agent not found", http.StatusNotFound)
		return
	}

	delete(ms.agents, name)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "stopped"})
}

func (ms *MockServer) handleAgentCommand(w http.ResponseWriter, r *http.Request, name string) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ms.mu.RLock()
	agent, exists := ms.agents[name]
	ms.mu.RUnlock()

	if !exists {
		http.Error(w, "Agent not found", http.StatusNotFound)
		return
	}

	var req struct {
		Command string `json:"command"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	// Update agent status based on command
	ms.mu.Lock()
	switch req.Command {
	case "pause":
		agent.Status = "paused"
	case "resume":
		agent.Status = "running"
	}
	ms.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (ms *MockServer) handleAgentStreamRequest(w http.ResponseWriter, r *http.Request, name string) {
	ms.mu.RLock()
	_, exists := ms.agents[name]
	ms.mu.RUnlock()

	if !exists {
		http.Error(w, "Agent not found", http.StatusNotFound)
		return
	}

	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	// Send a few test events
	for i := 0; i < 3; i++ {
		fmt.Fprintf(w, "data: [%s] Test log line %d\n\n", time.Now().Format(time.RFC3339), i+1)
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func (ms *MockServer) handleMetrics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ms.mu.RLock()
	defer ms.mu.RUnlock()

	// Build agents array (not map!)
	agents := make([]map[string]interface{}, 0, len(ms.agents))
	for name, agent := range ms.agents {
		duration := time.Since(agent.StartedAt)
		agents = append(agents, map[string]interface{}{
			"name":            name,
			"status":          agent.Status,
			"started_at":      agent.StartedAt.Format(time.RFC3339),
			"duration":        duration.Nanoseconds(),
			"exit_code":       0,
			"log_lines":       1000,
			"extractions":     50,
			"code_blocks":     10,
			"errors":          0,
			"bytes_processed": 50000,
			"extraction_rate": 2.5,
			"log_rate":        100.0,
		})
	}

	response := map[string]interface{}{
		"system": map[string]interface{}{
			"uptime_seconds":    time.Since(time.Now().Add(-1 * time.Hour)).Seconds(),
			"total_agents":      len(ms.agents),
			"running_agents":    len(ms.agents),
			"completed_agents":  0,
		},
		"agents": agents,
		"sse": map[string]interface{}{
			"active_connections": 0,
			"total_messages":     0,
		},
		"version": "4.0.0",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (ms *MockServer) handlePrometheus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprintf(w, "# HELP agent_lines_processed Total lines processed by agent\n")
	fmt.Fprintf(w, "# TYPE agent_lines_processed counter\n")
	fmt.Fprintf(w, "agent_lines_processed{agent=\"test\"} 1000\n")
}

func (ms *MockServer) handleInfluxDB(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprintf(w, "agent_metrics,agent=test lines=1000,events=50\n")
}
