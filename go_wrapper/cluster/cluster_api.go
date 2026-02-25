package cluster

import (
	"encoding/json"
	"net/http"
	"strconv"
)

// ClusterAPI provides HTTP endpoints for cluster management
type ClusterAPI struct {
	coordinator *ClusterCoordinator
}

// NewClusterAPI creates a new cluster API
func NewClusterAPI(coordinator *ClusterCoordinator) *ClusterAPI {
	return &ClusterAPI{
		coordinator: coordinator,
	}
}

// RegisterClusterRoutes registers all cluster endpoints
func (ca *ClusterAPI) RegisterClusterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/cluster/nodes", ca.handleNodes)
	mux.HandleFunc("/api/cluster/nodes/", ca.handleNodeDetail)
	mux.HandleFunc("/api/cluster/assignments", ca.handleAssignments)
	mux.HandleFunc("/api/cluster/stats", ca.handleStats)
	mux.HandleFunc("/api/cluster/leader", ca.handleLeader)
	mux.HandleFunc("/api/cluster/balance", ca.handleBalance)
}

// handleNodes lists all nodes or registers a new node
func (ca *ClusterAPI) handleNodes(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		ca.listNodes(w, r)
	case http.MethodPost:
		ca.registerNode(w, r)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

// listNodes returns all cluster nodes
func (ca *ClusterAPI) listNodes(w http.ResponseWriter, r *http.Request) {
	nodes := ca.coordinator.GetRegistry().GetAll()

	nodeInfo := make([]map[string]interface{}, 0, len(nodes))
	for _, node := range nodes {
		nodeInfo = append(nodeInfo, node.GetInfo())
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"nodes": nodeInfo,
		"count": len(nodes),
	})
}

// registerNode registers a new node with the cluster
func (ca *ClusterAPI) registerNode(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ID         string   `json:"id"`
		Hostname   string   `json:"hostname"`
		IPAddress  string   `json:"ip_address"`
		Port       int      `json:"port"`
		MaxAgents  int      `json:"max_agents"`
		Services   []string `json:"services"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Create node
	node := NewNode(req.ID, req.Hostname, req.IPAddress, req.Port)
	node.MaxAgents = req.MaxAgents
	node.Services = req.Services

	// Register with coordinator
	if err := ca.coordinator.RegisterNode(node); err != nil {
		if err == ErrNodeAlreadyExists {
			http.Error(w, err.Error(), http.StatusConflict)
		} else {
			http.Error(w, err.Error(), http.StatusInternalServerError)
		}
		return
	}

	writeJSON(w, http.StatusCreated, map[string]interface{}{
		"success": true,
		"node":    node.GetInfo(),
	})
}

// handleNodeDetail handles operations on a specific node
func (ca *ClusterAPI) handleNodeDetail(w http.ResponseWriter, r *http.Request) {
	// Extract node ID from path
	nodeID := r.URL.Path[len("/api/cluster/nodes/"):]
	if nodeID == "" {
		http.Error(w, "node ID required", http.StatusBadRequest)
		return
	}

	switch r.Method {
	case http.MethodGet:
		ca.getNode(w, r, nodeID)
	case http.MethodPost:
		ca.updateNodeHeartbeat(w, r, nodeID)
	case http.MethodDelete:
		ca.unregisterNode(w, r, nodeID)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

// getNode returns details for a specific node
func (ca *ClusterAPI) getNode(w http.ResponseWriter, r *http.Request, nodeID string) {
	node, err := ca.coordinator.GetRegistry().Get(nodeID)
	if err != nil {
		http.Error(w, "node not found", http.StatusNotFound)
		return
	}

	writeJSON(w, http.StatusOK, node.GetInfo())
}

// updateNodeHeartbeat updates a node's heartbeat and metrics
func (ca *ClusterAPI) updateNodeHeartbeat(w http.ResponseWriter, r *http.Request, nodeID string) {
	var req struct {
		CPUUsage    float64 `json:"cpu_usage"`
		MemoryUsage float64 `json:"memory_usage"`
		DiskUsage   float64 `json:"disk_usage"`
		LoadAverage float64 `json:"load_average"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := ca.coordinator.GetRegistry().UpdateHeartbeat(
		nodeID,
		req.CPUUsage,
		req.MemoryUsage,
		req.DiskUsage,
		req.LoadAverage,
	)

	if err != nil {
		http.Error(w, "node not found", http.StatusNotFound)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
	})
}

// unregisterNode removes a node from the cluster
func (ca *ClusterAPI) unregisterNode(w http.ResponseWriter, r *http.Request, nodeID string) {
	err := ca.coordinator.UnregisterNode(nodeID)
	if err != nil {
		if err == ErrNodeNotFound {
			http.Error(w, "node not found", http.StatusNotFound)
		} else {
			http.Error(w, err.Error(), http.StatusInternalServerError)
		}
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
	})
}

// handleAssignments lists all agent assignments
func (ca *ClusterAPI) handleAssignments(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	assignments := ca.coordinator.GetAllAssignments()

	assignmentInfo := make([]map[string]interface{}, 0, len(assignments))
	for _, assignment := range assignments {
		assignmentInfo = append(assignmentInfo, map[string]interface{}{
			"agent_name":  assignment.AgentName,
			"node_id":     assignment.NodeID,
			"assigned_at": assignment.AssignedAt.Format("2006-01-02T15:04:05Z07:00"),
			"status":      assignment.Status,
		})
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"assignments": assignmentInfo,
		"count":       len(assignments),
	})
}

// handleStats returns cluster statistics
func (ca *ClusterAPI) handleStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	stats := ca.coordinator.GetClusterStats()
	writeJSON(w, http.StatusOK, stats)
}

// handleLeader returns the current leader or promotes this node
func (ca *ClusterAPI) handleLeader(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		leader, err := ca.coordinator.GetRegistry().GetLeader()
		if err != nil {
			http.Error(w, "no leader elected", http.StatusNotFound)
			return
		}

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"leader": leader.GetInfo(),
		})

	case http.MethodPost:
		// Promote this node to leader
		if err := ca.coordinator.PromoteToLeader(); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"success":   true,
			"is_leader": true,
		})

	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

// handleBalance triggers load balancing or changes strategy
func (ca *ClusterAPI) handleBalance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	strategy := query.Get("strategy")

	if strategy != "" {
		// Change balancing strategy
		ca.coordinator.GetBalancer().SetStrategy(LoadBalancingStrategy(strategy))

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"success":  true,
			"strategy": strategy,
		})
		return
	}

	// Trigger rebalancing
	if err := ca.coordinator.GetBalancer().Rebalance(); err != nil {
		http.Error(w, err.Error(), http.StatusNotImplemented)
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
	})
}

// Helper functions

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// ParsePort extracts port from query parameter
func ParsePort(r *http.Request, defaultPort int) int {
	portStr := r.URL.Query().Get("port")
	if portStr == "" {
		return defaultPort
	}

	port, err := strconv.Atoi(portStr)
	if err != nil || port <= 0 || port > 65535 {
		return defaultPort
	}

	return port
}

// ParseMaxAgents extracts max_agents from query parameter
func ParseMaxAgents(r *http.Request, defaultMax int) int {
	maxStr := r.URL.Query().Get("max_agents")
	if maxStr == "" {
		return defaultMax
	}

	max, err := strconv.Atoi(maxStr)
	if err != nil || max <= 0 {
		return defaultMax
	}

	return max
}
