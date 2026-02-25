package api

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"sync"
	"time"

	"github.com/architect/go_wrapper/cluster"
	"github.com/architect/go_wrapper/data"
	"github.com/architect/go_wrapper/stream"
)

// Server provides HTTP API for agent management
type Server struct {
	agents           map[string]*AgentSession
	mu               sync.RWMutex
	host             string
	port             int
	startedAt        time.Time
	sseManager       *SSEManager
	metricsCollector *MetricsCollector
	wsManager        *WSManager

	// Database stores (optional)
	extractionStore *data.ExtractionStore
	sessionStore    *data.SessionStore
	queryAPI        *QueryAPI
	replayAPI       *ReplayAPI
	profilingAPI    *ProfilingAPI

	// Cluster support (optional)
	clusterEnabled  bool
	clusterCoordinator *cluster.ClusterCoordinator
	clusterAPI      *cluster.ClusterAPI
	localNode       *cluster.Node
}

// AgentSession represents an active agent with its wrapper
type AgentSession struct {
	Name           string
	Wrapper        *stream.ProcessWrapper
	Extractor      *stream.Extractor
	CommandHandler *stream.CommandHandler
	Cmd            *exec.Cmd
	PID            int
	StartedAt      time.Time
	Status         string // running, stopped, failed
	mu             sync.RWMutex
}

// NewServer creates a new API server
func NewServer(host string, port int) *Server {
	s := &Server{
		agents:           make(map[string]*AgentSession),
		host:             host,
		port:             port,
		startedAt:        time.Now(),
		sseManager:       NewSSEManager(),
		metricsCollector: NewMetricsCollector(),
		profilingAPI:     NewProfilingAPI(),
	}
	s.wsManager = NewWSManager(s)

	return s
}

// EnableDatabase enables database persistence with Query and Replay APIs
func (s *Server) EnableDatabase(dbPath string) error {
	// Create database stores
	extractionStore, err := data.NewExtractionStore(dbPath)
	if err != nil {
		return fmt.Errorf("failed to create extraction store: %w", err)
	}

	sessionStore, err := data.NewSessionStore(dbPath)
	if err != nil {
		extractionStore.Close()
		return fmt.Errorf("failed to create session store: %w", err)
	}

	// Create API handlers
	s.extractionStore = extractionStore
	s.sessionStore = sessionStore
	s.queryAPI = NewQueryAPI(extractionStore, sessionStore)
	s.replayAPI = NewReplayAPI(extractionStore, sessionStore, stream.NewBroadcaster())

	log.Printf("Database enabled: %s", dbPath)
	return nil
}

// EnableCluster enables cluster mode with multi-node coordination
func (s *Server) EnableCluster(nodeID string) error {
	// Create cluster coordinator
	coordinator := cluster.NewClusterCoordinator(
		nodeID,
		30*time.Second,  // heartbeat interval
		60*time.Second,  // health check interval
	)

	// Create local node
	localNode := cluster.NewNode(nodeID, s.host, s.host, s.port)
	localNode.MaxAgents = 100 // Default max agents
	localNode.AddService("wrapper")
	localNode.AddService("streaming")

	if s.extractionStore != nil {
		localNode.AddService("database")
	}

	// Register local node
	if err := coordinator.RegisterNode(localNode); err != nil {
		return fmt.Errorf("failed to register local node: %w", err)
	}

	// Start coordinator
	if err := coordinator.Start(); err != nil {
		return fmt.Errorf("failed to start coordinator: %w", err)
	}

	// Promote to leader (will participate in election)
	coordinator.PromoteToLeader()

	// Create cluster API
	s.clusterCoordinator = coordinator
	s.clusterAPI = cluster.NewClusterAPI(coordinator)
	s.localNode = localNode
	s.clusterEnabled = true

	log.Printf("Cluster mode enabled - Node ID: %s", nodeID)
	return nil
}

// Start starts the HTTP server
func (s *Server) Start() error {
	mux := http.NewServeMux()

	// API endpoints
	mux.HandleFunc("/api/agents", s.handleAgents)
	mux.HandleFunc("/api/agents/", s.handleAgentDetail)
	mux.HandleFunc("/api/health", s.handleHealth)
	mux.HandleFunc("/api/sse/stats", s.handleSSEStats)

	// Metrics endpoints
	mux.HandleFunc("/metrics", s.handlePrometheusMetrics)
	mux.HandleFunc("/api/metrics", s.handleMetricsJSON)
	mux.HandleFunc("/api/metrics/influxdb", s.handleMetricsInfluxDB)

	// WebSocket endpoints
	mux.HandleFunc("/ws/agents/", s.wsManager.HandleWebSocket)
	mux.HandleFunc("/api/ws/stats", s.handleWSStats)

	// Database Query and Replay APIs (if enabled)
	if s.queryAPI != nil {
		s.queryAPI.RegisterQueryRoutes(mux)
		s.queryAPI.RegisterEnhancedQueryRoutes(mux)
		log.Printf("Query API endpoints registered (standard + enhanced)")
	}
	if s.replayAPI != nil {
		s.replayAPI.RegisterReplayRoutes(mux)
		log.Printf("Replay API endpoints registered")
	}

	// Profiling API (always enabled)
	if s.profilingAPI != nil {
		s.profilingAPI.RegisterProfilingRoutes(mux)
		log.Printf("Profiling API endpoints registered")
	}

	// Cluster API (if enabled)
	if s.clusterAPI != nil {
		s.clusterAPI.RegisterClusterRoutes(mux)
		log.Printf("Cluster API endpoints registered")
	}

	// Static files
	mux.HandleFunc("/", s.handleDashboard)
	mux.HandleFunc("/enhanced", s.handleDashboardEnhanced)
	mux.HandleFunc("/database", s.handleDashboardDatabase)
	mux.HandleFunc("/interactive", s.handleDashboardInteractive)
	mux.HandleFunc("/replay", s.handleDashboardReplay)
	mux.HandleFunc("/query", s.handleDashboardQuery)
	mux.HandleFunc("/performance", s.handleDashboardPerformance)
	mux.HandleFunc("/test-sse", s.handleTestSSE)

	// CORS middleware
	handler := corsMiddleware(mux)

	addr := fmt.Sprintf("%s:%d", s.host, s.port)
	log.Printf("Starting API server on %s", addr)
	log.Printf("Dashboard (Basic) available at http://%s", addr)
	log.Printf("Dashboard (Enhanced) available at http://%s/enhanced", addr)
	log.Printf("Dashboard (Interactive) available at http://%s/interactive", addr)
	log.Printf("Dashboard (Replay) available at http://%s/replay", addr)
	log.Printf("Dashboard (Query Builder) available at http://%s/query", addr)
	log.Printf("Dashboard (Performance) available at http://%s/performance", addr)
	log.Printf("SSE test client at http://%s/test-sse", addr)
	log.Printf("SSE streaming available at /api/agents/:name/stream")
	log.Printf("WebSocket connections at ws://%s/ws/agents/:name", addr)

	if s.queryAPI != nil {
		log.Printf("Database Explorer available at http://%s/database", addr)
		log.Printf("Query API: GET /api/query/extractions, /api/query/sessions, etc.")
	}
	if s.replayAPI != nil {
		log.Printf("Replay API: GET /api/replay/session/:id, /api/replay/export/:id")
	}
	if s.clusterAPI != nil {
		log.Printf("Cluster API: GET /api/cluster/nodes, /api/cluster/stats, etc.")
		log.Printf("Cluster mode: Node %s (Leader: %v)", s.localNode.ID, s.clusterCoordinator.IsLeader())
	}

	return http.ListenAndServe(addr, handler)
}

// handleHealth returns server health status
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	health := map[string]interface{}{
		"status":     "healthy",
		"uptime":     time.Since(s.startedAt).String(),
		"agents":     len(s.agents),
		"started_at": s.startedAt.Format(time.RFC3339),
	}

	writeJSON(w, http.StatusOK, health)
}

// handleAgents lists all agents or creates a new one
func (s *Server) handleAgents(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		s.listAgents(w, r)
	case http.MethodPost:
		s.createAgent(w, r)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

// listAgents returns all active agents
func (s *Server) listAgents(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	agents := make([]map[string]interface{}, 0, len(s.agents))
	for name, agent := range s.agents {
		agent.mu.RLock()
		agents = append(agents, map[string]interface{}{
			"name":       name,
			"status":     agent.Status,
			"started_at": agent.StartedAt.Format(time.RFC3339),
			"uptime":     time.Since(agent.StartedAt).String(),
		})
		agent.mu.RUnlock()
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	})
}

// createAgent creates a new agent session
func (s *Server) createAgent(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name    string   `json:"name"`
		Command string   `json:"command"`
		Args    []string `json:"args"`
		LogsDir string   `json:"logs_dir"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if req.Name == "" || req.Command == "" {
		http.Error(w, "name and command are required", http.StatusBadRequest)
		return
	}

	s.mu.Lock()
	if _, exists := s.agents[req.Name]; exists {
		s.mu.Unlock()
		http.Error(w, "agent already exists", http.StatusConflict)
		return
	}
	s.mu.Unlock()

	// Create wrapper
	logsDir := req.LogsDir
	if logsDir == "" {
		logsDir = "logs/agents"
	}

	wrapper := stream.NewProcessWrapper(req.Name, logsDir, req.Command, req.Args...)
	extractor := stream.NewExtractor()
	commandHandler := stream.NewCommandHandler(wrapper)

	session := &AgentSession{
		Name:           req.Name,
		Wrapper:        wrapper,
		Extractor:      extractor,
		CommandHandler: commandHandler,
		StartedAt:      time.Now(),
		Status:         "starting",
	}

	// Start the process
	if err := wrapper.Start(); err != nil {
		http.Error(w, fmt.Sprintf("failed to start: %v", err), http.StatusInternalServerError)
		return
	}

	session.Status = "running"

	s.mu.Lock()
	s.agents[req.Name] = session
	s.mu.Unlock()

	writeJSON(w, http.StatusCreated, map[string]interface{}{
		"name":       req.Name,
		"status":     session.Status,
		"started_at": session.StartedAt.Format(time.RFC3339),
	})
}

// handleAgentDetail handles operations on a specific agent
func (s *Server) handleAgentDetail(w http.ResponseWriter, r *http.Request) {
	// Extract agent name from path
	path := r.URL.Path[len("/api/agents/"):]
	if path == "" {
		http.Error(w, "agent name required", http.StatusBadRequest)
		return
	}

	// Check if this is a stream request
	if len(path) > 7 && path[len(path)-7:] == "/stream" {
		agentName := path[:len(path)-7]
		s.handleStream(w, r, agentName)
		return
	}

	name := path
	s.mu.RLock()
	agent, exists := s.agents[name]
	s.mu.RUnlock()

	if !exists {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	switch r.Method {
	case http.MethodGet:
		s.getAgent(w, r, agent)
	case http.MethodDelete:
		s.deleteAgent(w, r, name, agent)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

// getAgent returns agent details and extracted data
func (s *Server) getAgent(w http.ResponseWriter, r *http.Request, agent *AgentSession) {
	agent.mu.RLock()
	defer agent.mu.RUnlock()

	stats := agent.Extractor.GetStats()
	stdoutLog, stderrLog := agent.Wrapper.GetLogPaths()

	response := map[string]interface{}{
		"name":       agent.Name,
		"status":     agent.Status,
		"started_at": agent.StartedAt.Format(time.RFC3339),
		"uptime":     time.Since(agent.StartedAt).String(),
		"extraction": stats,
		"logs": map[string]string{
			"stdout": stdoutLog,
			"stderr": stderrLog,
		},
	}

	// Add extracted matches by type
	if r.URL.Query().Get("include_matches") == "true" {
		response["matches"] = map[string]interface{}{
			"session":      agent.Extractor.GetMatchesByType(stream.PatternTypeSession),
			"code_blocks":  agent.Extractor.GetMatchesByType(stream.PatternTypeCodeBlock),
			"metrics":      agent.Extractor.GetMatchesByType(stream.PatternTypeMetric),
			"errors":       agent.Extractor.GetMatchesByType(stream.PatternTypeError),
			"state":        agent.Extractor.GetMatchesByType(stream.PatternTypeStateChange),
			"file_ops":     agent.Extractor.GetMatchesByType(stream.PatternTypeFileOp),
		}
	}

	writeJSON(w, http.StatusOK, response)
}

// deleteAgent stops and removes an agent
func (s *Server) deleteAgent(w http.ResponseWriter, r *http.Request, name string, agent *AgentSession) {
	agent.mu.Lock()
	agent.Status = "stopping"
	agent.mu.Unlock()

	// Stop the wrapper
	if err := agent.Wrapper.Stop(); err != nil {
		log.Printf("Error stopping agent %s: %v", name, err)
	}

	agent.mu.Lock()
	agent.Status = "stopped"
	agent.mu.Unlock()

	s.mu.Lock()
	delete(s.agents, name)
	s.mu.Unlock()

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"message": "agent stopped",
		"name":    name,
	})
}

// handleStream handles SSE streaming for an agent
func (s *Server) handleStream(w http.ResponseWriter, r *http.Request, agentName string) {
	// Check if agent exists
	s.mu.RLock()
	agent, exists := s.agents[agentName]
	s.mu.RUnlock()

	if !exists {
		http.Error(w, "agent not found", http.StatusNotFound)
		return
	}

	// Attach listeners to broadcasters
	wrapper := agent.Wrapper
	extractor := agent.Extractor

	wrapperBroadcaster := wrapper.GetBroadcaster()
	extractorBroadcaster := extractor.GetBroadcaster()

	// Create listener that forwards events to SSE
	listener := func(event stream.BroadcastEvent) {
		sseEvent := SSEEvent{
			Type:      string(event.Type),
			Timestamp: event.Timestamp,
			AgentName: agentName,
			Data:      event.Data,
		}
		s.sseManager.Broadcast(agentName, sseEvent)
	}

	// Register listeners
	wrapperBroadcaster.AddListener(listener)
	extractorBroadcaster.AddListener(listener)

	// Handle SSE connection
	s.sseManager.HandleSSE(w, r, agentName)
}

// handleSSEStats returns SSE connection statistics
func (s *Server) handleSSEStats(w http.ResponseWriter, r *http.Request) {
	stats := s.sseManager.GetAllStats()
	writeJSON(w, http.StatusOK, stats)
}

// handleWSStats returns WebSocket connection statistics
func (s *Server) handleWSStats(w http.ResponseWriter, r *http.Request) {
	stats := s.wsManager.GetStats()
	writeJSON(w, http.StatusOK, stats)
}

// handleDashboard serves the main dashboard
func (s *Server) handleDashboard(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	http.ServeFile(w, r, "dashboard.html")
}

// handleDashboardEnhanced serves the enhanced dashboard
func (s *Server) handleDashboardEnhanced(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "dashboard_enhanced.html")
}

// handleTestSSE serves the SSE test client
func (s *Server) handleTestSSE(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "test_sse.html")
}

// handleDashboardDatabase serves the database explorer dashboard
func (s *Server) handleDashboardDatabase(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "dashboard_database.html")
}

// Helper functions

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// handleDashboardInteractive serves the interactive dashboard with WebSocket controls
func (s *Server) handleDashboardInteractive(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "dashboard_interactive.html")
}

// handleDashboardReplay serves the session replay viewer dashboard
func (s *Server) handleDashboardReplay(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "dashboard_replay.html")
}

// handleDashboardQuery serves the advanced query builder dashboard
func (s *Server) handleDashboardQuery(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "dashboard_query.html")
}

// handleDashboardPerformance serves the performance monitoring dashboard
func (s *Server) handleDashboardPerformance(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "dashboard_performance.html")
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
