package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"architect-go/pkg/errors"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// DashboardHandlers handles dashboard HTTP requests
type DashboardHandlers struct {
	service    services.DashboardService
	errHandler *errors.Handler
}

// NewDashboardHandlers creates new dashboard handlers
func NewDashboardHandlers(service services.DashboardService, errHandler *errors.Handler) *DashboardHandlers {
	return &DashboardHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// GetDashboard handles GET /api/dashboard
func (dh *DashboardHandlers) GetDashboard(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id")
	if userID == nil {
		dh.errHandler.Handle(w, errors.AuthenticationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	dashboard, err := dh.service.GetDashboard(r.Context(), userID.(string))
	if err != nil {
		dh.errHandler.Handle(w, errors.InternalErrorf("DASHBOARD_ERROR", "Failed to get dashboard"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(dashboard)
}

// GetStatistics handles GET /api/dashboard/statistics
func (dh *DashboardHandlers) GetStatistics(w http.ResponseWriter, r *http.Request) {
	stats, err := dh.service.GetStatistics(r.Context())
	if err != nil {
		dh.errHandler.Handle(w, errors.InternalErrorf("STATISTICS_ERROR", "Failed to get statistics"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetProjectMetrics handles GET /api/dashboard/projects/{id}/metrics
func (dh *DashboardHandlers) GetProjectMetrics(w http.ResponseWriter, r *http.Request) {
	projectID := r.URL.Query().Get("project_id")
	if projectID == "" {
		dh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PROJECT_ID", "Project ID is required"), httputil.GetTraceID(r))
		return
	}

	metrics, err := dh.service.GetProjectMetrics(r.Context(), projectID)
	if err != nil {
		dh.errHandler.Handle(w, errors.InternalErrorf("METRICS_ERROR", "Failed to get metrics"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(metrics)
}

// GetUserActivity handles GET /api/dashboard/users/{id}/activity
func (dh *DashboardHandlers) GetUserActivity(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		userID = r.Context().Value("user_id").(string)
	}

	if userID == "" {
		dh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	activity, err := dh.service.GetUserActivity(r.Context(), userID)
	if err != nil {
		dh.errHandler.Handle(w, errors.InternalErrorf("ACTIVITY_ERROR", "Failed to get activity"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"activity": activity,
	})
}

// GetSummary handles GET /api/dashboard/summary
func (dh *DashboardHandlers) GetSummary(w http.ResponseWriter, r *http.Request) {
	dashboard, err := dh.service.GetStatistics(r.Context())
	if err != nil {
		dh.errHandler.Handle(w, errors.InternalErrorf("SUMMARY_ERROR", "Failed to get summary"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(dashboard)
}

// GetMetricsFilter handles GET /api/dashboard/metrics with filtering
func (dh *DashboardHandlers) GetMetricsFilter(w http.ResponseWriter, r *http.Request) {
	metricType := r.URL.Query().Get("type")
	timeRange := r.URL.Query().Get("range")
	limit := 100
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	// Build metrics response with filters
	metrics := map[string]interface{}{
		"type":       metricType,
		"range":      timeRange,
		"limit":      limit,
		"data":       []interface{}{},
		"total":      0,
		"timestamp":  0,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(metrics)
}

// GetSystemHealth handles GET /api/dashboard/health
func (dh *DashboardHandlers) GetSystemHealth(w http.ResponseWriter, r *http.Request) {
	health := map[string]interface{}{
		"status":     "healthy",
		"timestamp":  0,
		"uptime":     0,
		"components": map[string]string{
			"database":   "operational",
			"cache":      "operational",
			"workers":    "operational",
			"websocket":  "operational",
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

// GetTopProjects handles GET /api/dashboard/projects/top
func (dh *DashboardHandlers) GetTopProjects(w http.ResponseWriter, r *http.Request) {
	limit := 10
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	projects := map[string]interface{}{
		"projects": []interface{}{},
		"limit":    limit,
		"total":    0,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(projects)
}

// GetRecentActivity handles GET /api/dashboard/activity/recent
func (dh *DashboardHandlers) GetRecentActivity(w http.ResponseWriter, r *http.Request) {
	limit := 50
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	activity := map[string]interface{}{
		"activity": []interface{}{},
		"limit":    limit,
		"total":    0,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(activity)
}

// RegisterDashboardRoutes registers dashboard routes
func RegisterDashboardRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
}, handlers *DashboardHandlers) {
	r.Get("/", handlers.GetDashboard)
	r.Get("/statistics", handlers.GetStatistics)
	r.Get("/metrics", handlers.GetMetricsFilter)
	r.Get("/projects/{id}/metrics", handlers.GetProjectMetrics)
	r.Get("/users/{id}/activity", handlers.GetUserActivity)
	r.Get("/summary", handlers.GetSummary)
	r.Get("/health", handlers.GetSystemHealth)
	r.Get("/projects/top", handlers.GetTopProjects)
	r.Get("/activity/recent", handlers.GetRecentActivity)
}
