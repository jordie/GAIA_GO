package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"architect-go/pkg/errors"
	"architect-go/pkg/services"
)

// AnalyticsHandlers handles analytics-related HTTP requests
type AnalyticsHandlers struct {
	eventAnalytics      *services.EventAnalyticsServiceImpl
	presenceAnalytics   *services.PresenceAnalyticsServiceImpl
	activityAnalytics   *services.ActivityAnalyticsServiceImpl
	performanceAnalytics *services.PerformanceAnalyticsServiceImpl
	userAnalytics       *services.UserAnalyticsServiceImpl
	errorAnalytics      *services.ErrorAnalyticsServiceImpl
	errorHandler        *errors.ErrorHandler
}

// NewAnalyticsHandlers creates a new analytics handlers instance
func NewAnalyticsHandlers(
	eventAnalytics *services.EventAnalyticsServiceImpl,
	presenceAnalytics *services.PresenceAnalyticsServiceImpl,
	activityAnalytics *services.ActivityAnalyticsServiceImpl,
	performanceAnalytics *services.PerformanceAnalyticsServiceImpl,
	userAnalytics *services.UserAnalyticsServiceImpl,
	errorAnalytics *services.ErrorAnalyticsServiceImpl,
	errorHandler *errors.ErrorHandler,
) *AnalyticsHandlers {
	return &AnalyticsHandlers{
		eventAnalytics:       eventAnalytics,
		presenceAnalytics:    presenceAnalytics,
		activityAnalytics:    activityAnalytics,
		performanceAnalytics: performanceAnalytics,
		userAnalytics:        userAnalytics,
		errorAnalytics:       errorAnalytics,
		errorHandler:         errorHandler,
	}
}

// Event Analytics Handlers

// GetEventTimeline returns event timeline data
func (h *AnalyticsHandlers) GetEventTimeline(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "day"
	}
	interval := r.URL.Query().Get("interval")
	if interval == "" {
		interval = "hour"
	}

	timeline, err := h.eventAnalytics.GetTimeline(r.Context(), time.Now().AddDate(0, 0, -30), time.Now(), interval)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"timeline": timeline})
}

// GetEventTrends returns event trends
func (h *AnalyticsHandlers) GetEventTrends(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "day"
	}

	data, err := h.eventAnalytics.GetByType(r.Context(), time.Now().AddDate(0, 0, -30), time.Now(), 100)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"period": period,
		"data":   data,
	})
}

// GetEventsByType returns events grouped by type
func (h *AnalyticsHandlers) GetEventsByType(w http.ResponseWriter, r *http.Request) {
	limit := 100
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil {
			limit = parsed
		}
	}

	events, err := h.eventAnalytics.GetByType(r.Context(), time.Now().AddDate(0, 0, -30), time.Now(), limit)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"events": events})
}

// GetFunnelAnalysis returns funnel analysis
func (h *AnalyticsHandlers) GetFunnelAnalysis(w http.ResponseWriter, r *http.Request) {
	funnelName := r.URL.Query().Get("name")
	if funnelName == "" {
		funnelName = "default"
	}

	funnel, err := h.eventAnalytics.GetFunnel(r.Context(), funnelName, time.Now().AddDate(0, 0, -30), time.Now())
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"funnel": funnel})
}

// Presence Analytics Handlers

// GetPresenceTrends returns presence trends
func (h *AnalyticsHandlers) GetPresenceTrends(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "day"
	}
	interval := r.URL.Query().Get("interval")
	if interval == "" {
		interval = "hour"
	}

	data, summary, err := h.presenceAnalytics.GetPresenceTrends(r.Context(), period, interval)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"data":    data,
		"summary": summary,
	})
}

// GetUserEngagementMetrics returns user engagement metrics
func (h *AnalyticsHandlers) GetUserEngagementMetrics(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		h.errorHandler.HandleError(w, r, fmt.Errorf("user_id is required"))
		return
	}

	days := 30
	if d := r.URL.Query().Get("days"); d != "" {
		if parsed, err := strconv.Atoi(d); err == nil {
			days = parsed
		}
	}

	metrics, err := h.presenceAnalytics.GetUserEngagementMetrics(r.Context(), userID, days)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"metrics": metrics})
}

// GetPresenceHeatmap returns presence heatmap
func (h *AnalyticsHandlers) GetPresenceHeatmap(w http.ResponseWriter, r *http.Request) {
	days := 30
	if d := r.URL.Query().Get("days"); d != "" {
		if parsed, err := strconv.Atoi(d); err == nil {
			days = parsed
		}
	}

	heatmap, err := h.presenceAnalytics.GetPresenceHeatmap(r.Context(), days)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"heatmap": heatmap})
}

// Activity Analytics Handlers

// GetActivityTrends returns activity trends
func (h *AnalyticsHandlers) GetActivityTrends(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "day"
	}
	action := r.URL.Query().Get("action")

	data, summary, err := h.activityAnalytics.GetActivityTrends(r.Context(), period, action)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"data":    data,
		"summary": summary,
	})
}

// GetTopActiveUsers returns top active users
func (h *AnalyticsHandlers) GetTopActiveUsers(w http.ResponseWriter, r *http.Request) {
	days := 30
	limit := 10

	if d := r.URL.Query().Get("days"); d != "" {
		if parsed, err := strconv.Atoi(d); err == nil {
			days = parsed
		}
	}
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil {
			limit = parsed
		}
	}

	users, err := h.activityAnalytics.GetTopUsers(r.Context(), days, limit)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"users": users})
}

// Performance Analytics Handlers

// GetRequestMetrics returns request performance metrics
func (h *AnalyticsHandlers) GetRequestMetrics(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "hour"
	}

	metrics, err := h.performanceAnalytics.GetRequestMetrics(r.Context(), period)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"metrics": metrics})
}

// GetSystemMetrics returns system metrics
func (h *AnalyticsHandlers) GetSystemMetrics(w http.ResponseWriter, r *http.Request) {
	metrics, err := h.performanceAnalytics.GetSystemMetrics(r.Context())
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"metrics": metrics})
}

// GetDatabaseMetrics returns database metrics
func (h *AnalyticsHandlers) GetDatabaseMetrics(w http.ResponseWriter, r *http.Request) {
	metrics, err := h.performanceAnalytics.GetDatabaseMetrics(r.Context())
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"metrics": metrics})
}

// GetCacheMetrics returns cache metrics
func (h *AnalyticsHandlers) GetCacheMetrics(w http.ResponseWriter, r *http.Request) {
	metrics, err := h.performanceAnalytics.GetCacheMetrics(r.Context())
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"metrics": metrics})
}

// User Analytics Handlers

// GetUserGrowth returns user growth metrics
func (h *AnalyticsHandlers) GetUserGrowth(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "month"
	}

	growth, err := h.userAnalytics.GetUserGrowth(r.Context(), period)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"growth": growth})
}

// GetUserRetention returns user retention metrics
func (h *AnalyticsHandlers) GetUserRetention(w http.ResponseWriter, r *http.Request) {
	cohortDate := time.Now().AddDate(0, -1, 0)

	retention, err := h.userAnalytics.GetUserRetention(r.Context(), cohortDate)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"retention": retention})
}

// Error Analytics Handlers

// GetErrorMetrics returns error metrics
func (h *AnalyticsHandlers) GetErrorMetrics(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "hour"
	}

	metrics, err := h.errorAnalytics.GetErrorMetrics(r.Context(), period)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"metrics": metrics})
}

// GetTopErrors returns most common errors
func (h *AnalyticsHandlers) GetTopErrors(w http.ResponseWriter, r *http.Request) {
	limit := 10
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil {
			limit = parsed
		}
	}

	topErrors, err := h.errorAnalytics.GetTopErrors(r.Context(), limit)
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"errors": topErrors})
}

// GetCriticalErrors returns critical errors
func (h *AnalyticsHandlers) GetCriticalErrors(w http.ResponseWriter, r *http.Request) {
	errors, err := h.errorAnalytics.GetCriticalErrors(r.Context())
	if err != nil {
		h.errorHandler.HandleError(w, r, err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"errors": errors})
}

// RegisterAnalyticsRoutes registers analytics routes
func RegisterAnalyticsRoutes(r interface{}, h *AnalyticsHandlers) {
	// Implementation for chi or other router
	// Routes will be registered in server.go
}
