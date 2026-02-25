package manager

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/architect/go_wrapper/stream"
)

// Task represents a development task
type Task struct {
	ID          string                 `json:"id"`
	Description string                 `json:"description"`
	Priority    int                    `json:"priority"`
	AssignedTo  string                 `json:"assigned_to"`
	Status      string                 `json:"status"` // pending, in_progress, completed, failed
	CreatedAt   time.Time              `json:"created_at"`
	StartedAt   *time.Time             `json:"started_at,omitempty"`
	CompletedAt *time.Time             `json:"completed_at,omitempty"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// Agent represents a wrapped agent (claude, gemini, etc.)
type Agent struct {
	Name        string                 `json:"name"`
	Type        string                 `json:"type"` // claude, gemini, codex
	Wrapper     *stream.ProcessWrapper `json:"-"`
	Status      string                 `json:"status"` // idle, busy, offline
	CurrentTask *Task                  `json:"current_task,omitempty"`
	StartedAt   time.Time              `json:"started_at"`
	TasksCompleted int                 `json:"tasks_completed"`
}

// Manager handles task distribution and agent management
type Manager struct {
	agents      map[string]*Agent
	tasks       map[string]*Task
	taskQueue   []*Task
	mu          sync.RWMutex
	host        string
	port        int
	goals       []string // Development goals for alignment
	stopChan    chan struct{} // Channel to stop background tasks
}

// NewManager creates a new task manager
func NewManager(host string, port int) *Manager {
	return &Manager{
		agents:    make(map[string]*Agent),
		tasks:     make(map[string]*Task),
		taskQueue: make([]*Task, 0),
		host:      host,
		port:      port,
		goals:     make([]string, 0),
		stopChan:  make(chan struct{}),
	}
}

// Start starts the manager HTTP server
func (m *Manager) Start() error {
	mux := http.NewServeMux()

	// Task endpoints
	mux.HandleFunc("/api/manager/tasks", m.handleTasks)
	mux.HandleFunc("/api/manager/tasks/assign", m.handleAssignTask)
	mux.HandleFunc("/api/manager/tasks/", m.handleTaskOperations)

	// Agent endpoints
	mux.HandleFunc("/api/manager/agents", m.handleAgents)
	mux.HandleFunc("/api/manager/agents/", m.handleAgentDetail)
	mux.HandleFunc("/api/manager/agents/register", m.handleRegisterAgent)

	// Goal alignment
	mux.HandleFunc("/api/manager/goals", m.handleGoals)
	mux.HandleFunc("/api/manager/status", m.handleStatus)

	// Integration with architect assigner
	mux.HandleFunc("/api/manager/assigner/sync", m.handleAssignerSync)

	handler := corsMiddleware(mux)

	addr := fmt.Sprintf("%s:%d", m.host, m.port)
	log.Printf("Manager starting on %s", addr)
	log.Printf("Endpoints:")
	log.Printf("  POST /api/manager/tasks - Create task")
	log.Printf("  GET  /api/manager/tasks - List tasks")
	log.Printf("  POST /api/manager/tasks/assign - Assign task to agent")
	log.Printf("  POST /api/manager/tasks/<id>/complete - Mark task complete")
	log.Printf("  GET  /api/manager/agents - List agents")
	log.Printf("  POST /api/manager/agents/register - Register agent")
	log.Printf("  GET  /api/manager/status - Manager status")

	// Start background task completion detector
	go m.startTaskCompletionDetector()
	log.Printf("Task completion detector started")

	return http.ListenAndServe(addr, handler)
}

// RegisterAgent registers a new agent with the manager
func (m *Manager) RegisterAgent(name, agentType string, wrapper *stream.ProcessWrapper) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, exists := m.agents[name]; exists {
		return fmt.Errorf("agent %s already registered", name)
	}

	agent := &Agent{
		Name:           name,
		Type:           agentType,
		Wrapper:        wrapper,
		Status:         "idle",
		StartedAt:      time.Now(),
		TasksCompleted: 0,
	}

	m.agents[name] = agent
	log.Printf("Registered agent: %s (type: %s)", name, agentType)

	return nil
}

// CreateTask creates a new task
func (m *Manager) CreateTask(description string, priority int, metadata map[string]interface{}) (*Task, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	task := &Task{
		ID:          fmt.Sprintf("task-%d", time.Now().Unix()),
		Description: description,
		Priority:    priority,
		Status:      "pending",
		CreatedAt:   time.Now(),
		Metadata:    metadata,
	}

	m.tasks[task.ID] = task
	m.taskQueue = append(m.taskQueue, task)

	log.Printf("Created task: %s (priority: %d)", task.ID, task.Priority)

	// Try to assign immediately if agents available
	go m.autoAssign()

	return task, nil
}

// autoAssign automatically assigns pending tasks to idle agents
func (m *Manager) autoAssign() {
	m.mu.Lock()
	defer m.mu.Unlock()

	if len(m.taskQueue) == 0 {
		return
	}

	// Find idle agents
	for _, agent := range m.agents {
		if agent.Status == "idle" && len(m.taskQueue) > 0 {
			task := m.taskQueue[0]
			m.taskQueue = m.taskQueue[1:]

			m.assignTaskToAgent(task, agent)
		}
	}
}

// assignTaskToAgent assigns a task to a specific agent
func (m *Manager) assignTaskToAgent(task *Task, agent *Agent) error {
	now := time.Now()
	task.AssignedTo = agent.Name
	task.Status = "in_progress"
	task.StartedAt = &now

	agent.Status = "busy"
	agent.CurrentTask = task

	log.Printf("Assigned task %s to agent %s", task.ID, agent.Name)

	// TODO: Send task to agent via wrapper
	// This would involve sending prompts through the wrapper to claude/gemini

	return nil
}

// CompleteTask marks a task as completed and updates agent status
func (m *Manager) CompleteTask(taskID string, success bool) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	task, exists := m.tasks[taskID]
	if !exists {
		return fmt.Errorf("task %s not found", taskID)
	}

	now := time.Now()
	task.CompletedAt = &now

	if success {
		task.Status = "completed"
		log.Printf("Task %s completed successfully", taskID)
	} else {
		task.Status = "failed"
		log.Printf("Task %s failed", taskID)
	}

	// Update agent status
	if task.AssignedTo != "" {
		agent, exists := m.agents[task.AssignedTo]
		if exists {
			agent.Status = "idle"
			agent.CurrentTask = nil
			if success {
				agent.TasksCompleted++
			}
			log.Printf("Agent %s is now idle (tasks completed: %d)", agent.Name, agent.TasksCompleted)

			// Trigger auto-assignment for next task
			go m.autoAssign()
		}
	}

	return nil
}

// FailTask marks a task as failed
func (m *Manager) FailTask(taskID string, reason string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	task, exists := m.tasks[taskID]
	if !exists {
		return fmt.Errorf("task %s not found", taskID)
	}

	now := time.Now()
	task.CompletedAt = &now
	task.Status = "failed"

	if task.Metadata == nil {
		task.Metadata = make(map[string]interface{})
	}
	task.Metadata["failure_reason"] = reason

	log.Printf("Task %s failed: %s", taskID, reason)

	// Update agent status
	if task.AssignedTo != "" {
		agent, exists := m.agents[task.AssignedTo]
		if exists {
			agent.Status = "idle"
			agent.CurrentTask = nil
			log.Printf("Agent %s is now idle after task failure", agent.Name)

			// Trigger auto-assignment for next task
			go m.autoAssign()
		}
	}

	return nil
}

// DetectTaskCompletion checks for task completion signals and updates task status
// This method examines busy agents and their current tasks to determine if completion
// signals are present (e.g., wrapper output patterns, timeout, manual markers)
func (m *Manager) DetectTaskCompletion() {
	m.mu.RLock()
	busyAgents := make([]*Agent, 0)
	for _, agent := range m.agents {
		if agent.Status == "busy" && agent.CurrentTask != nil {
			busyAgents = append(busyAgents, agent)
		}
	}
	m.mu.RUnlock()

	for _, agent := range busyAgents {
		task := agent.CurrentTask

		// Check for completion signals
		completed := false
		success := true
		reason := ""

		// 1. Check for timeout (tasks running longer than 30 minutes)
		if task.StartedAt != nil {
			duration := time.Since(*task.StartedAt)
			if duration > 30*time.Minute {
				completed = true
				success = false
				reason = fmt.Sprintf("Task timeout after %v", duration)
			}
		}

		// 2. Check wrapper output for completion patterns
		if agent.Wrapper != nil {
			// Read recent output from wrapper
			output := agent.Wrapper.GetRecentOutput(1024)

			// Look for completion indicators in output
			completionPatterns := []string{
				"task completed",
				"successfully finished",
				"done",
				"completed successfully",
				"task done",
			}

			failurePatterns := []string{
				"error:",
				"failed:",
				"exception:",
				"task failed",
				"cannot complete",
			}

			for _, pattern := range completionPatterns {
				if containsPattern(output, pattern) {
					completed = true
					success = true
					break
				}
			}

			if !completed {
				for _, pattern := range failurePatterns {
					if containsPattern(output, pattern) {
						completed = true
						success = false
						reason = "Failure pattern detected in output"
						break
					}
				}
			}
		}

		// 3. Check metadata for manual completion marker
		if task.Metadata != nil {
			if marker, ok := task.Metadata["completion_marker"]; ok {
				completed = true
				success = marker == "success"
				if !success {
					if r, ok := task.Metadata["failure_reason"].(string); ok {
						reason = r
					}
				}
			}
		}

		// Complete the task if signals detected
		if completed {
			if success {
				m.CompleteTask(task.ID, true)
			} else {
				m.FailTask(task.ID, reason)
			}
		}
	}
}

// startTaskCompletionDetector runs DetectTaskCompletion periodically in background
func (m *Manager) startTaskCompletionDetector() {
	ticker := time.NewTicker(10 * time.Second) // Check every 10 seconds
	defer ticker.Stop()

	log.Printf("Task completion detector running (checking every 10 seconds)")

	for {
		select {
		case <-ticker.C:
			m.DetectTaskCompletion()
		case <-m.stopChan:
			log.Printf("Task completion detector stopped")
			return
		}
	}
}

// Stop gracefully shuts down the manager
func (m *Manager) Stop() {
	close(m.stopChan)
	log.Printf("Manager shutdown initiated")
}

// containsPattern checks if output contains a pattern (case-insensitive)
func containsPattern(output, pattern string) bool {
	outputLower := string([]byte(output)) // Simple case handling
	patternLower := string([]byte(pattern))

	// Simple substring search (could be improved with regex)
	for i := 0; i <= len(outputLower)-len(patternLower); i++ {
		match := true
		for j := 0; j < len(patternLower); j++ {
			c1 := outputLower[i+j]
			c2 := patternLower[j]
			// Simple case-insensitive comparison
			if c1 >= 'A' && c1 <= 'Z' {
				c1 += 32 // Convert to lowercase
			}
			if c2 >= 'A' && c2 <= 'Z' {
				c2 += 32
			}
			if c1 != c2 {
				match = false
				break
			}
		}
		if match {
			return true
		}
	}
	return false
}

// HTTP Handlers

func (m *Manager) handleTasks(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		m.listTasks(w, r)
	case http.MethodPost:
		m.createTaskHTTP(w, r)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (m *Manager) listTasks(w http.ResponseWriter, r *http.Request) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	tasks := make([]*Task, 0, len(m.tasks))
	for _, task := range m.tasks {
		tasks = append(tasks, task)
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"tasks": tasks,
		"count": len(tasks),
		"queue": len(m.taskQueue),
	})
}

func (m *Manager) createTaskHTTP(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Description string                 `json:"description"`
		Priority    int                    `json:"priority"`
		Metadata    map[string]interface{} `json:"metadata"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	task, err := m.CreateTask(req.Description, req.Priority, req.Metadata)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	writeJSON(w, http.StatusCreated, task)
}

func (m *Manager) handleTaskOperations(w http.ResponseWriter, r *http.Request) {
	// Extract task ID and operation from path
	// Format: /api/manager/tasks/{taskID} or /api/manager/tasks/{taskID}/complete
	path := r.URL.Path[len("/api/manager/tasks/"):]

	// Split path to get taskID and optional operation
	parts := []string{}
	current := ""
	for i := 0; i < len(path); i++ {
		if path[i] == '/' {
			if current != "" {
				parts = append(parts, current)
				current = ""
			}
		} else {
			current += string(path[i])
		}
	}
	if current != "" {
		parts = append(parts, current)
	}

	if len(parts) == 0 {
		http.Error(w, "Task ID required", http.StatusBadRequest)
		return
	}

	taskID := parts[0]

	// Handle /complete operation
	if len(parts) > 1 && parts[1] == "complete" {
		m.handleCompleteTask(w, r, taskID)
		return
	}

	// Default: Get task detail
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	m.mu.RLock()
	task, exists := m.tasks[taskID]
	m.mu.RUnlock()

	if !exists {
		http.Error(w, "Task not found", http.StatusNotFound)
		return
	}

	writeJSON(w, http.StatusOK, task)
}

func (m *Manager) handleCompleteTask(w http.ResponseWriter, r *http.Request, taskID string) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		Success bool   `json:"success"`
		Reason  string `json:"reason,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	var err error
	if req.Success {
		err = m.CompleteTask(taskID, true)
	} else {
		reason := req.Reason
		if reason == "" {
			reason = "Manually marked as failed"
		}
		err = m.FailTask(taskID, reason)
	}

	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"message": "Task updated",
		"task_id": taskID,
		"status":  map[bool]string{true: "completed", false: "failed"}[req.Success],
	})
}

func (m *Manager) handleAssignTask(w http.ResponseWriter, r *http.Request) {
	var req struct {
		TaskID    string `json:"task_id"`
		AgentName string `json:"agent_name"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	task, exists := m.tasks[req.TaskID]
	if !exists {
		http.Error(w, "Task not found", http.StatusNotFound)
		return
	}

	agent, exists := m.agents[req.AgentName]
	if !exists {
		http.Error(w, "Agent not found", http.StatusNotFound)
		return
	}

	if err := m.assignTaskToAgent(task, agent); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"message": "Task assigned",
		"task_id": task.ID,
		"agent":   agent.Name,
	})
}

func (m *Manager) handleAgents(w http.ResponseWriter, r *http.Request) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	agents := make([]*Agent, 0, len(m.agents))
	for _, agent := range m.agents {
		agents = append(agents, agent)
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	})
}

func (m *Manager) handleAgentDetail(w http.ResponseWriter, r *http.Request) {
	agentName := r.URL.Path[len("/api/manager/agents/"):]

	m.mu.RLock()
	agent, exists := m.agents[agentName]
	m.mu.RUnlock()

	if !exists {
		http.Error(w, "Agent not found", http.StatusNotFound)
		return
	}

	writeJSON(w, http.StatusOK, agent)
}

func (m *Manager) handleRegisterAgent(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name string `json:"name"`
		Type string `json:"type"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Note: Wrapper would be passed in when agent is actually started
	if err := m.RegisterAgent(req.Name, req.Type, nil); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	writeJSON(w, http.StatusCreated, map[string]string{
		"message": "Agent registered",
		"name":    req.Name,
		"type":    req.Type,
	})
}

func (m *Manager) handleGoals(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		m.mu.RLock()
		defer m.mu.RUnlock()
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"goals": m.goals,
		})
	case http.MethodPost:
		var req struct {
			Goals []string `json:"goals"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request body", http.StatusBadRequest)
			return
		}
		m.mu.Lock()
		m.goals = req.Goals
		m.mu.Unlock()
		writeJSON(w, http.StatusOK, map[string]string{
			"message": "Goals updated",
		})
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (m *Manager) handleStatus(w http.ResponseWriter, r *http.Request) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	idleAgents := 0
	busyAgents := 0
	for _, agent := range m.agents {
		if agent.Status == "idle" {
			idleAgents++
		} else if agent.Status == "busy" {
			busyAgents++
		}
	}

	pendingTasks := 0
	completedTasks := 0
	failedTasks := 0
	for _, task := range m.tasks {
		switch task.Status {
		case "pending":
			pendingTasks++
		case "completed":
			completedTasks++
		case "failed":
			failedTasks++
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"agents": map[string]int{
			"total": len(m.agents),
			"idle":  idleAgents,
			"busy":  busyAgents,
		},
		"tasks": map[string]int{
			"total":     len(m.tasks),
			"queue":     len(m.taskQueue),
			"pending":   pendingTasks,
			"completed": completedTasks,
			"failed":    failedTasks,
		},
		"goals": len(m.goals),
	})
}

func (m *Manager) handleAssignerSync(w http.ResponseWriter, r *http.Request) {
	// Integration endpoint for architect's assigner worker
	// This endpoint allows syncing tasks from the assigner system

	var req struct {
		Tasks []struct {
			Content  string                 `json:"content"`
			Priority int                    `json:"priority"`
			Metadata map[string]interface{} `json:"metadata"`
		} `json:"tasks"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	created := 0
	for _, taskReq := range req.Tasks {
		if _, err := m.CreateTask(taskReq.Content, taskReq.Priority, taskReq.Metadata); err == nil {
			created++
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"synced": created,
		"total":  len(req.Tasks),
	})
}

// Helper functions

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
