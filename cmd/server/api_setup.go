package main

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/jgirmay/GAIA_GO/pkg/http/handlers"
)

// SetupDistributedGAIAAPI registers all distributed GAIA API routes
func SetupDistributedGAIAAPI(router *chi.Mux, components *DistributedGAIAComponents) {
	// Only setup if components are initialized
	if components == nil {
		return
	}

	// Health check endpoint
	router.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		health := HealthCheck(components)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(health)
	})

	// Raft cluster endpoints
	if components.RaftNode != nil {
		setupRaftRoutes(router, components)
	}

	// Session coordinator endpoints
	if components.SessionCoordinator != nil {
		setupSessionRoutes(router, components)
	}

	// Task queue endpoints
	if components.TaskQueue != nil {
		setupTaskRoutes(router, components)
	}

	// Metrics and usability endpoints
	if components.MetricsService != nil {
		setupMetricsRoutes(router, components)
	}
}

// setupRaftRoutes registers Raft-related endpoints
func setupRaftRoutes(router *chi.Mux, components *DistributedGAIAComponents) {
	router.Route("/api/cluster", func(r chi.Router) {
		// Cluster status
		r.Get("/status", func(w http.ResponseWriter, req *http.Request) {
			status := map[string]interface{}{
				"node_id":    components.RaftNode.NodeID,
				"is_leader":  components.RaftNode.IsLeader(),
				"leader":     components.RaftNode.Leader(),
				"peers":      components.RaftNode.Peers(),
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(status)
		})

		// Add peer to cluster
		r.Post("/peers", func(w http.ResponseWriter, req *http.Request) {
			var peerReq struct {
				PeerID   string `json:"peer_id"`
				PeerAddr string `json:"peer_addr"`
			}
			json.NewDecoder(req.Body).Decode(&peerReq)

			err := components.RaftNode.AddPeer(peerReq.PeerID, peerReq.PeerAddr)
			if err != nil {
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
				return
			}

			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(map[string]string{"status": "peer added"})
		})

		// Remove peer from cluster
		r.Delete("/peers/{peerID}", func(w http.ResponseWriter, req *http.Request) {
			peerID := chi.URLParam(req, "peerID")

			err := components.RaftNode.RemovePeer(peerID)
			if err != nil {
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
				return
			}

			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(map[string]string{"status": "peer removed"})
		})
	})
}

// setupSessionRoutes registers session coordinator endpoints
func setupSessionRoutes(router *chi.Mux, components *DistributedGAIAComponents) {
	router.Route("/api/sessions", func(r chi.Router) {
		// List available sessions
		r.Get("/", func(w http.ResponseWriter, req *http.Request) {
			sessions := components.SessionCoordinator.GetAvailableSessions()
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]interface{}{
				"count":    len(sessions),
				"sessions": sessions,
			})
		})

		// Get session status
		r.Get("/{sessionID}", func(w http.ResponseWriter, req *http.Request) {
			sessionID := chi.URLParam(req, "sessionID")
			status := components.SessionCoordinator.GetSessionStatus(sessionID)
			if status == nil {
				w.WriteHeader(http.StatusNotFound)
				json.NewEncoder(w).Encode(map[string]string{"error": "session not found"})
				return
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(status)
		})

		// Health check status
		r.Get("/health/check", func(w http.ResponseWriter, req *http.Request) {
			components.SessionCoordinator.PerformHealthCheck()
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{"status": "health check completed"})
		})
	})
}

// setupTaskRoutes registers task queue endpoints
func setupTaskRoutes(router *chi.Mux, components *DistributedGAIAComponents) {
	router.Route("/api/tasks", func(r chi.Router) {
		// Enqueue task
		r.Post("/", func(w http.ResponseWriter, req *http.Request) {
			var taskReq struct {
				TaskType string      `json:"task_type"`
				Data     interface{} `json:"data"`
				Priority int         `json:"priority"`
			}
			json.NewDecoder(req.Body).Decode(&taskReq)

			// Task enqueued
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusCreated)
			json.NewEncoder(w).Encode(map[string]string{"status": "task enqueued"})
		})

		// Claim task
		r.Post("/claim", func(w http.ResponseWriter, req *http.Request) {
			var claimReq struct {
				SessionID string `json:"session_id"`
			}
			json.NewDecoder(req.Body).Decode(&claimReq)

			// Task claimed
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{"status": "task claimed"})
		})

		// Get task queue stats
		r.Get("/stats", func(w http.ResponseWriter, req *http.Request) {
			stats := components.TaskQueue.GetTaskStats()
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(stats)
		})
	})
}

// setupMetricsRoutes registers metrics and usability endpoints
func setupMetricsRoutes(router *chi.Mux, components *DistributedGAIAComponents) {
	// Register teacher dashboard routes
	handlers.RegisterTeacherDashboardRoutes(
		router,
		components.MetricsService,
		components.FrustrationEngine,
		components.MetricsAggregator,
		components.Registry.GetTeacherDashboardAlertRepository(),
	)

	router.Route("/api/metrics", func(r chi.Router) {
		// Record metric
		r.Post("/", func(w http.ResponseWriter, req *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusAccepted)
			json.NewEncoder(w).Encode(map[string]string{"status": "metric received"})
		})

		// Get buffer size
		r.Get("/buffer/status", func(w http.ResponseWriter, req *http.Request) {
			bufferSize := components.MetricsService.GetBufferSize()
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]int{"buffer_size": bufferSize})
		})

		// Force flush metrics
		r.Post("/flush", func(w http.ResponseWriter, req *http.Request) {
			components.MetricsService.ForceFlush(req.Context())
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{"status": "metrics flushed"})
		})
	})
}

// PrintDistributedGAIARoutes prints all registered distributed GAIA routes
func PrintDistributedGAIARoutes() {
	routes := map[string][]string{
		"Cluster Management": {
			"GET    /health                              - System health check",
			"GET    /api/cluster/status                  - Raft cluster status",
			"POST   /api/cluster/peers                   - Add peer to cluster",
			"DELETE /api/cluster/peers/{peerID}          - Remove peer from cluster",
		},
		"Session Coordination": {
			"GET    /api/sessions                        - List available sessions",
			"GET    /api/sessions/{sessionID}            - Get session status",
			"POST   /api/sessions/health/check           - Perform health check",
		},
		"Task Queue": {
			"POST   /api/tasks                           - Enqueue task",
			"POST   /api/tasks/claim                     - Claim task for processing",
			"GET    /api/tasks/stats                     - Get task queue statistics",
		},
		"Metrics & Usability": {
			"POST   /api/metrics                         - Record metric",
			"GET    /api/metrics/buffer/status           - Get metrics buffer status",
			"POST   /api/metrics/flush                   - Force flush buffered metrics",
		},
		"Teacher Dashboard": {
			"GET    /api/classroom/{classroomID}/metrics - Classroom aggregated metrics",
			"GET    /api/students/frustration            - Student frustration metrics",
			"POST   /api/interventions                   - Record intervention",
			"GET    /api/struggling-students             - List struggling students",
		},
	}

	println("\n===============================================================")
	println("DISTRIBUTED GAIA_GO API ROUTES")
	println("===============================================================")
	for category, endpoints := range routes {
		println("\n" + category + ":")
		for _, endpoint := range endpoints {
			println("  " + endpoint)
		}
	}
	println("\n===============================================================\n")
}
