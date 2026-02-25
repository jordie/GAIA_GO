package api

import (
	"fmt"
	"net/http"
	"sort"
	"sync"
	"time"

	"github.com/architect/go_wrapper/stream"
)

// MetricsCollector collects and aggregates metrics from agents
type MetricsCollector struct {
	agents         map[string]*AgentMetrics
	mu             sync.RWMutex
	startTime      time.Time
	totalEvents    int64
	totalLogs      int64
	totalExtracts  int64
	extractsByType map[string]int64
}

// AgentMetrics holds metrics for a single agent
type AgentMetrics struct {
	Name           string
	Status         string
	StartedAt      time.Time
	CompletedAt    *time.Time
	Duration       time.Duration
	ExitCode       int
	LogLines       int64
	Extractions    int64
	CodeBlocks     int64
	Errors         int64
	BytesProcessed int64
	ExtractionRate float64 // extractions per second
	LogRate        float64 // logs per second
}

// NewMetricsCollector creates a new metrics collector
func NewMetricsCollector() *MetricsCollector {
	return &MetricsCollector{
		agents:         make(map[string]*AgentMetrics),
		startTime:      time.Now(),
		extractsByType: make(map[string]int64),
	}
}

// RecordAgentStart records when an agent starts
func (mc *MetricsCollector) RecordAgentStart(name string) {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	mc.agents[name] = &AgentMetrics{
		Name:      name,
		Status:    "running",
		StartedAt: time.Now(),
	}
}

// RecordAgentComplete records when an agent completes
func (mc *MetricsCollector) RecordAgentComplete(name string, exitCode int, duration time.Duration) {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	if agent, exists := mc.agents[name]; exists {
		now := time.Now()
		agent.CompletedAt = &now
		agent.Duration = duration
		agent.ExitCode = exitCode
		agent.Status = "completed"

		// Calculate rates
		if duration.Seconds() > 0 {
			agent.ExtractionRate = float64(agent.Extractions) / duration.Seconds()
			agent.LogRate = float64(agent.LogLines) / duration.Seconds()
		}
	}
}

// RecordLog records a log line
func (mc *MetricsCollector) RecordLog(agentName string, bytes int64) {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	mc.totalLogs++
	mc.totalEvents++

	if agent, exists := mc.agents[agentName]; exists {
		agent.LogLines++
		agent.BytesProcessed += bytes
	}
}

// RecordExtraction records an extraction
func (mc *MetricsCollector) RecordExtraction(agentName string, extractType string) {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	mc.totalExtracts++
	mc.totalEvents++
	mc.extractsByType[extractType]++

	if agent, exists := mc.agents[agentName]; exists {
		agent.Extractions++

		if extractType == string(stream.PatternTypeCodeBlock) {
			agent.CodeBlocks++
		}
		if extractType == string(stream.PatternTypeError) {
			agent.Errors++
		}
	}
}

// GetMetrics returns current metrics
func (mc *MetricsCollector) GetMetrics() map[string]interface{} {
	mc.mu.RLock()
	defer mc.mu.RUnlock()

	uptime := time.Since(mc.startTime)
	runningAgents := 0
	completedAgents := 0

	for _, agent := range mc.agents {
		if agent.Status == "running" {
			runningAgents++
		} else if agent.Status == "completed" {
			completedAgents++
		}
	}

	return map[string]interface{}{
		"uptime_seconds":    uptime.Seconds(),
		"total_agents":      len(mc.agents),
		"running_agents":    runningAgents,
		"completed_agents":  completedAgents,
		"total_events":      mc.totalEvents,
		"total_logs":        mc.totalLogs,
		"total_extractions": mc.totalExtracts,
		"extractions_by_type": mc.extractsByType,
		"events_per_second": float64(mc.totalEvents) / uptime.Seconds(),
	}
}

// GetAgentMetrics returns metrics for all agents
func (mc *MetricsCollector) GetAgentMetrics() []*AgentMetrics {
	mc.mu.RLock()
	defer mc.mu.RUnlock()

	metrics := make([]*AgentMetrics, 0, len(mc.agents))
	for _, agent := range mc.agents {
		metrics = append(metrics, agent)
	}

	// Sort by start time (newest first)
	sort.Slice(metrics, func(i, j int) bool {
		return metrics[i].StartedAt.After(metrics[j].StartedAt)
	})

	return metrics
}

// PrometheusExporter handles Prometheus metrics endpoint
func (s *Server) handlePrometheusMetrics(w http.ResponseWriter, r *http.Request) {
	metrics := s.metricsCollector.GetMetrics()
	agentMetrics := s.metricsCollector.GetAgentMetrics()

	w.Header().Set("Content-Type", "text/plain; version=0.0.4")

	// System metrics
	fmt.Fprintf(w, "# HELP go_wrapper_uptime_seconds Uptime in seconds\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_uptime_seconds gauge\n")
	fmt.Fprintf(w, "go_wrapper_uptime_seconds %.2f\n", metrics["uptime_seconds"])

	fmt.Fprintf(w, "# HELP go_wrapper_agents_total Total number of agents\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agents_total gauge\n")
	fmt.Fprintf(w, "go_wrapper_agents_total %d\n", metrics["total_agents"])

	fmt.Fprintf(w, "# HELP go_wrapper_agents_running Number of running agents\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agents_running gauge\n")
	fmt.Fprintf(w, "go_wrapper_agents_running %d\n", metrics["running_agents"])

	fmt.Fprintf(w, "# HELP go_wrapper_agents_completed Number of completed agents\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agents_completed gauge\n")
	fmt.Fprintf(w, "go_wrapper_agents_completed %d\n", metrics["completed_agents"])

	fmt.Fprintf(w, "# HELP go_wrapper_events_total Total number of events\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_events_total counter\n")
	fmt.Fprintf(w, "go_wrapper_events_total %d\n", metrics["total_events"])

	fmt.Fprintf(w, "# HELP go_wrapper_logs_total Total number of log lines\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_logs_total counter\n")
	fmt.Fprintf(w, "go_wrapper_logs_total %d\n", metrics["total_logs"])

	fmt.Fprintf(w, "# HELP go_wrapper_extractions_total Total number of extractions\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_extractions_total counter\n")
	fmt.Fprintf(w, "go_wrapper_extractions_total %d\n", metrics["total_extractions"])

	fmt.Fprintf(w, "# HELP go_wrapper_events_per_second Events processed per second\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_events_per_second gauge\n")
	fmt.Fprintf(w, "go_wrapper_events_per_second %.2f\n", metrics["events_per_second"])

	// Extractions by type
	if extractsByType, ok := metrics["extractions_by_type"].(map[string]int64); ok {
		fmt.Fprintf(w, "# HELP go_wrapper_extractions_by_type Extractions by pattern type\n")
		fmt.Fprintf(w, "# TYPE go_wrapper_extractions_by_type counter\n")
		for extractType, count := range extractsByType {
			fmt.Fprintf(w, "go_wrapper_extractions_by_type{type=\"%s\"} %d\n", extractType, count)
		}
	}

	// Per-agent metrics
	fmt.Fprintf(w, "# HELP go_wrapper_agent_log_lines Log lines per agent\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agent_log_lines counter\n")
	for _, agent := range agentMetrics {
		fmt.Fprintf(w, "go_wrapper_agent_log_lines{agent=\"%s\",status=\"%s\"} %d\n",
			agent.Name, agent.Status, agent.LogLines)
	}

	fmt.Fprintf(w, "# HELP go_wrapper_agent_extractions Extractions per agent\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agent_extractions counter\n")
	for _, agent := range agentMetrics {
		fmt.Fprintf(w, "go_wrapper_agent_extractions{agent=\"%s\",status=\"%s\"} %d\n",
			agent.Name, agent.Status, agent.Extractions)
	}

	fmt.Fprintf(w, "# HELP go_wrapper_agent_code_blocks Code blocks per agent\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agent_code_blocks counter\n")
	for _, agent := range agentMetrics {
		fmt.Fprintf(w, "go_wrapper_agent_code_blocks{agent=\"%s\",status=\"%s\"} %d\n",
			agent.Name, agent.Status, agent.CodeBlocks)
	}

	fmt.Fprintf(w, "# HELP go_wrapper_agent_errors Errors per agent\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agent_errors counter\n")
	for _, agent := range agentMetrics {
		fmt.Fprintf(w, "go_wrapper_agent_errors{agent=\"%s\",status=\"%s\"} %d\n",
			agent.Name, agent.Status, agent.Errors)
	}

	fmt.Fprintf(w, "# HELP go_wrapper_agent_duration_seconds Agent duration in seconds\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agent_duration_seconds gauge\n")
	for _, agent := range agentMetrics {
		duration := agent.Duration.Seconds()
		if agent.Status == "running" {
			duration = time.Since(agent.StartedAt).Seconds()
		}
		fmt.Fprintf(w, "go_wrapper_agent_duration_seconds{agent=\"%s\",status=\"%s\"} %.2f\n",
			agent.Name, agent.Status, duration)
	}

	fmt.Fprintf(w, "# HELP go_wrapper_agent_exit_code Agent exit code\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_agent_exit_code gauge\n")
	for _, agent := range agentMetrics {
		if agent.Status == "completed" {
			fmt.Fprintf(w, "go_wrapper_agent_exit_code{agent=\"%s\"} %d\n",
				agent.Name, agent.ExitCode)
		}
	}

	// SSE metrics
	sseStats := s.sseManager.GetAllStats()
	fmt.Fprintf(w, "# HELP go_wrapper_sse_clients Number of connected SSE clients\n")
	fmt.Fprintf(w, "# TYPE go_wrapper_sse_clients gauge\n")
	fmt.Fprintf(w, "go_wrapper_sse_clients %d\n", sseStats["total_clients"])
}

// handleMetricsJSON returns metrics in JSON format
func (s *Server) handleMetricsJSON(w http.ResponseWriter, r *http.Request) {
	metrics := s.metricsCollector.GetMetrics()
	agentMetrics := s.metricsCollector.GetAgentMetrics()

	// Build response
	response := map[string]interface{}{
		"system":  metrics,
		"agents":  agentMetrics,
		"sse":     s.sseManager.GetAllStats(),
		"version": "4.0.0",
	}

	writeJSON(w, http.StatusOK, response)
}

// handleMetricsInfluxDB returns metrics in InfluxDB line protocol
func (s *Server) handleMetricsInfluxDB(w http.ResponseWriter, r *http.Request) {
	metrics := s.metricsCollector.GetMetrics()
	agentMetrics := s.metricsCollector.GetAgentMetrics()
	timestamp := time.Now().UnixNano()

	w.Header().Set("Content-Type", "text/plain")

	// System metrics
	fmt.Fprintf(w, "go_wrapper,host=localhost uptime_seconds=%.2f %d\n",
		metrics["uptime_seconds"], timestamp)
	fmt.Fprintf(w, "go_wrapper,host=localhost agents_total=%d %d\n",
		metrics["total_agents"], timestamp)
	fmt.Fprintf(w, "go_wrapper,host=localhost agents_running=%d %d\n",
		metrics["running_agents"], timestamp)
	fmt.Fprintf(w, "go_wrapper,host=localhost agents_completed=%d %d\n",
		metrics["completed_agents"], timestamp)
	fmt.Fprintf(w, "go_wrapper,host=localhost events_total=%d %d\n",
		metrics["total_events"], timestamp)
	fmt.Fprintf(w, "go_wrapper,host=localhost logs_total=%d %d\n",
		metrics["total_logs"], timestamp)
	fmt.Fprintf(w, "go_wrapper,host=localhost extractions_total=%d %d\n",
		metrics["total_extractions"], timestamp)
	fmt.Fprintf(w, "go_wrapper,host=localhost events_per_second=%.2f %d\n",
		metrics["events_per_second"], timestamp)

	// Extractions by type
	if extractsByType, ok := metrics["extractions_by_type"].(map[string]int64); ok {
		for extractType, count := range extractsByType {
			fmt.Fprintf(w, "go_wrapper_extractions,host=localhost,type=%s count=%d %d\n",
				extractType, count, timestamp)
		}
	}

	// Per-agent metrics
	for _, agent := range agentMetrics {
		fmt.Fprintf(w, "go_wrapper_agent,host=localhost,agent=%s,status=%s log_lines=%d,extractions=%d,code_blocks=%d,errors=%d %d\n",
			agent.Name, agent.Status, agent.LogLines, agent.Extractions, agent.CodeBlocks, agent.Errors, timestamp)

		duration := agent.Duration.Seconds()
		if agent.Status == "running" {
			duration = time.Since(agent.StartedAt).Seconds()
		}
		fmt.Fprintf(w, "go_wrapper_agent,host=localhost,agent=%s,status=%s duration_seconds=%.2f %d\n",
			agent.Name, agent.Status, duration, timestamp)
	}
}
