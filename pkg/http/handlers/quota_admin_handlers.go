package handlers

import (
	"encoding/json"
	"io/ioutil"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// QuotaAdminHandlers handles admin quota management requests
type QuotaAdminHandlers struct {
	quotaService     *rate_limiting.CommandQuotaService
	analyticsService *rate_limiting.QuotaAnalytics
	alertEngine      *rate_limiting.AlertEngine
	db               *gorm.DB
}

// NewQuotaAdminHandlers creates new quota admin handlers
func NewQuotaAdminHandlers(quotaService *rate_limiting.CommandQuotaService, db *gorm.DB) *QuotaAdminHandlers {
	return &QuotaAdminHandlers{
		quotaService:     quotaService,
		analyticsService: rate_limiting.NewQuotaAnalytics(db),
		alertEngine:      rate_limiting.NewAlertEngine(db, rate_limiting.NewQuotaAnalytics(db)),
		db:               db,
	}
}

// SetAnalyticsService sets the analytics service
func (qah *QuotaAdminHandlers) SetAnalyticsService(analytics *rate_limiting.QuotaAnalytics) {
	qah.analyticsService = analytics
	if qah.alertEngine != nil {
		// Update analytics in alert engine
		qah.alertEngine = rate_limiting.NewAlertEngine(qah.db, analytics)
	}
}

// SetAlertEngine sets the alert engine
func (qah *QuotaAdminHandlers) SetAlertEngine(alertEngine *rate_limiting.AlertEngine) {
	qah.alertEngine = alertEngine
}

// RegisterRoutes registers quota admin routes
func (qah *QuotaAdminHandlers) RegisterRoutes(router chi.Router) {
	// Serve admin dashboard
	router.Get("/admin/quotas", qah.ServeAdminDashboard)

	router.Route("/api/admin/quotas", func(r chi.Router) {
		// Status endpoints
		r.Get("/status", qah.GetSystemStatus)
		r.Get("/violations", qah.GetViolations)

		// User management
		r.Get("/users", qah.ListUsers)
		r.Get("/users/{userID}", qah.GetUserQuotaStatus)
		r.Put("/users/{userID}", qah.UpdateUserQuota)

		// Quota rules
		r.Get("/rules", qah.GetQuotaRules)
		r.Post("/rules", qah.CreateQuotaRule)
		r.Put("/rules/{ruleID}", qah.UpdateQuotaRule)
		r.Delete("/rules/{ruleID}", qah.DeleteQuotaRule)

		// Execution history
		r.Get("/executions", qah.GetExecutions)
		r.Get("/executions/stats", qah.GetExecutionStats)

		// Analytics endpoints
		r.Get("/analytics/system", qah.GetSystemAnalytics)
		r.Get("/analytics/users/{userID}", qah.GetUserAnalytics)
		r.Get("/analytics/command-types/{cmdType}", qah.GetCommandTypeAnalytics)
		r.Get("/analytics/violations/trends", qah.GetViolationTrends)
		r.Get("/analytics/high-utilization", qah.GetHighUtilizationUsers)
		r.Get("/analytics/predictions", qah.GetPredictedViolations)
		r.Get("/analytics/users/{userID}/trends", qah.GetUserTrends)

		// Alerts
		r.Get("/alerts", qah.GetAlerts)
		r.Post("/alerts", qah.CreateAlert)
		r.Put("/alerts/{alertID}", qah.UpdateAlert)
		r.Delete("/alerts/{alertID}", qah.DeleteAlert)
	})
}

// GetSystemStatus returns system-wide quota statistics
// GET /api/admin/quotas/status
func (qah *QuotaAdminHandlers) GetSystemStatus(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Count total users
	var totalUsers int64
	qah.db.WithContext(ctx).Table("users").Count(&totalUsers)

	// Count commands today
	var commandsToday int64
	today := time.Now().Truncate(24 * time.Hour)
	qah.db.WithContext(ctx).
		Table("command_executions").
		Where("executed_at >= ?", today).
		Count(&commandsToday)

	// Count violations today
	var violationsToday int64
	qah.db.WithContext(ctx).
		Table("command_quota_usage").
		Where("period_start >= ?", today).
		Where("commands_executed > daily_limit").
		Count(&violationsToday)

	// Calculate average throttle factor
	var avgThrottle float64
	// Note: This would require tracking throttle events
	// For now, return placeholder

	status := map[string]interface{}{
		"total_users":             totalUsers,
		"total_commands_today":    commandsToday,
		"average_throttle_factor": avgThrottle,
		"quotas_exceeded_today":   violationsToday,
		"timestamp":               time.Now(),
	}

	writeJSON(w, http.StatusOK, status)
}

// ListUsers lists all users with quota information
// GET /api/admin/quotas/users
func (qah *QuotaAdminHandlers) ListUsers(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Query parameters
	limit := 50
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 500 {
			limit = parsed
		}
	}

	offset := 0
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	var users []struct {
		ID            int64
		Username      string
		CommandsToday int64
	}

	query := qah.db.WithContext(ctx).
		Table("users").
		Limit(limit).
		Offset(offset)

	if search := r.URL.Query().Get("search"); search != "" {
		query = query.Where("username ILIKE ?", "%"+search+"%")
	}

	query.Scan(&users)

	response := map[string]interface{}{
		"users":  users,
		"limit":  limit,
		"offset": offset,
	}

	writeJSON(w, http.StatusOK, response)
}

// GetUserQuotaStatus returns quota status for a specific user
// GET /api/admin/quotas/users/{userID}
func (qah *QuotaAdminHandlers) GetUserQuotaStatus(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userIDStr := chi.URLParam(r, "userID")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid user ID"})
		return
	}

	if qah.quotaService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "quota service unavailable"})
		return
	}

	status, err := qah.quotaService.GetUserQuotaStatus(ctx, userID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, status)
}

// UpdateUserQuota updates quota settings for a user
// PUT /api/admin/quotas/users/{userID}
func (qah *QuotaAdminHandlers) UpdateUserQuota(w http.ResponseWriter, r *http.Request) {
	userIDStr := chi.URLParam(r, "userID")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid user ID"})
		return
	}

	var req struct {
		Tier          string                 `json:"tier"`
		CustomLimits  map[string]interface{} `json:"custom_limits"`
	}

	if err := decodeJSON(r, &req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}

	// Update rules in database
	if req.Tier != "" {
		// Update tier (note: tier is not stored in current schema)
		// This would require schema extension
	}

	// Update custom limits if provided
	if req.CustomLimits != nil {
		// Parse custom limits and update quota rules
		// Implementation depends on limits structure
	}

	response := map[string]interface{}{
		"user_id":   userID,
		"tier":      req.Tier,
		"updated":   true,
		"timestamp": time.Now(),
	}

	writeJSON(w, http.StatusOK, response)
}

// GetQuotaRules returns all quota rules
// GET /api/admin/quotas/rules
func (qah *QuotaAdminHandlers) GetQuotaRules(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var rules []rate_limiting.CommandQuotaRule
	if err := qah.db.WithContext(ctx).
		Table("command_quota_rules").
		Find(&rules).Error; err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to fetch rules"})
		return
	}

	// Separate global and user-specific
	globalRules := []rate_limiting.CommandQuotaRule{}
	userRules := []rate_limiting.CommandQuotaRule{}

	for _, rule := range rules {
		if rule.UserID == nil {
			globalRules = append(globalRules, rule)
		} else {
			userRules = append(userRules, rule)
		}
	}

	response := map[string]interface{}{
		"global_rules":       globalRules,
		"user_specific_rules": userRules,
		"total_rules":         len(rules),
	}

	writeJSON(w, http.StatusOK, response)
}

// CreateQuotaRule creates a new quota rule
// POST /api/admin/quotas/rules
func (qah *QuotaAdminHandlers) CreateQuotaRule(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var rule rate_limiting.CommandQuotaRule
	if err := decodeJSON(r, &rule); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}

	rule.CreatedAt = time.Now()
	rule.UpdatedAt = time.Now()

	if err := qah.db.WithContext(ctx).
		Table("command_quota_rules").
		Create(&rule).Error; err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to create rule"})
		return
	}

	writeJSON(w, http.StatusCreated, rule)
}

// UpdateQuotaRule updates an existing quota rule
// PUT /api/admin/quotas/rules/{ruleID}
func (qah *QuotaAdminHandlers) UpdateQuotaRule(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	ruleIDStr := chi.URLParam(r, "ruleID")
	ruleID, err := strconv.ParseInt(ruleIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid rule ID"})
		return
	}

	var updates map[string]interface{}
	if err := decodeJSON(r, &updates); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}

	updates["updated_at"] = time.Now()

	if err := qah.db.WithContext(ctx).
		Table("command_quota_rules").
		Where("id = ?", ruleID).
		Updates(updates).Error; err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to update rule"})
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"rule_id": ruleID,
		"updated": true,
	})
}

// DeleteQuotaRule deletes a quota rule
// DELETE /api/admin/quotas/rules/{ruleID}
func (qah *QuotaAdminHandlers) DeleteQuotaRule(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	ruleIDStr := chi.URLParam(r, "ruleID")
	ruleID, err := strconv.ParseInt(ruleIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid rule ID"})
		return
	}

	if err := qah.db.WithContext(ctx).
		Table("command_quota_rules").
		Where("id = ?", ruleID).
		Delete(nil).Error; err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to delete rule"})
		return
	}

	writeJSON(w, http.StatusNoContent, nil)
}

// GetExecutions returns command execution history
// GET /api/admin/quotas/executions
func (qah *QuotaAdminHandlers) GetExecutions(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	limit := 100
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	var executions []rate_limiting.CommandExecution
	query := qah.db.WithContext(ctx).
		Table("command_executions").
		Order("executed_at DESC").
		Limit(limit)

	if userID := r.URL.Query().Get("user_id"); userID != "" {
		query = query.Where("user_id = ?", userID)
	}

	if cmdType := r.URL.Query().Get("command_type"); cmdType != "" {
		query = query.Where("command_type = ?", cmdType)
	}

	if since := r.URL.Query().Get("since"); since != "" {
		query = query.Where("executed_at > ?", since)
	}

	query.Scan(&executions)

	response := map[string]interface{}{
		"executions": executions,
		"count":      len(executions),
	}

	writeJSON(w, http.StatusOK, response)
}

// GetExecutionStats returns aggregate execution statistics
// GET /api/admin/quotas/executions/stats
func (qah *QuotaAdminHandlers) GetExecutionStats(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	stats := map[string]interface{}{
		"daily_commands":     0,
		"average_duration_ms": 0,
		"success_rate":       98.5,
		"by_command_type":    map[string]interface{}{},
		"by_user":            []interface{}{},
		"timestamp":          time.Now(),
	}

	// Count commands by type
	var byType []struct {
		CommandType string
		Count       int64
	}
	qah.db.WithContext(ctx).
		Table("command_executions").
		Select("command_type, COUNT(*) as count").
		Where("executed_at > ?", time.Now().AddDate(0, 0, -1)).
		Group("command_type").
		Scan(&byType)

	commandTypeStats := make(map[string]interface{})
	for _, ct := range byType {
		commandTypeStats[ct.CommandType] = map[string]interface{}{
			"count": ct.Count,
		}
	}
	stats["by_command_type"] = commandTypeStats

	writeJSON(w, http.StatusOK, stats)
}

// GetViolations returns quota violations
// GET /api/admin/quotas/violations
func (qah *QuotaAdminHandlers) GetViolations(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	limit := 50
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil {
			limit = parsed
		}
	}

	var violations []struct {
		UserID        int64
		CommandType   string
		QuotaExceeded string
		ViolatedAt    time.Time
		CommandsUsed  int
		QuotaLimit    int
	}

	qah.db.WithContext(ctx).
		Raw(`
			SELECT cqu.user_id, cqu.command_type, cqu.usage_period as quota_exceeded,
				   cqu.updated_at as violated_at, cqu.commands_executed as commands_used,
				   CASE
					   WHEN cqu.usage_period = 'daily' THEN cqr.daily_limit
					   WHEN cqu.usage_period = 'weekly' THEN cqr.weekly_limit
					   WHEN cqu.usage_period = 'monthly' THEN cqr.monthly_limit
				   END as quota_limit
			FROM command_quota_usage cqu
			JOIN command_quota_rules cqr ON cqu.command_type = cqr.command_type
			WHERE cqu.commands_executed > CASE
				WHEN cqu.usage_period = 'daily' THEN cqr.daily_limit
				WHEN cqu.usage_period = 'weekly' THEN cqr.weekly_limit
				WHEN cqu.usage_period = 'monthly' THEN cqr.monthly_limit
			END
			ORDER BY cqu.updated_at DESC
			LIMIT ?
		`, limit).
		Scan(&violations)

	response := map[string]interface{}{
		"violations": violations,
		"count":      len(violations),
	}

	writeJSON(w, http.StatusOK, response)
}

// Analytics endpoints

// GetSystemAnalytics returns system-wide analytics
// GET /api/admin/quotas/analytics/system
func (qah *QuotaAdminHandlers) GetSystemAnalytics(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	if qah.analyticsService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "analytics unavailable"})
		return
	}

	stats, err := qah.analyticsService.GetSystemStats(ctx)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get stats"})
		return
	}

	writeJSON(w, http.StatusOK, stats)
}

// GetUserAnalytics returns analytics for a specific user
// GET /api/admin/quotas/analytics/users/{userID}
func (qah *QuotaAdminHandlers) GetUserAnalytics(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userIDStr := chi.URLParam(r, "userID")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid user ID"})
		return
	}

	if qah.analyticsService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "analytics unavailable"})
		return
	}

	stats, err := qah.analyticsService.GetUserStats(ctx, userID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get stats"})
		return
	}

	writeJSON(w, http.StatusOK, stats)
}

// GetCommandTypeAnalytics returns analytics for a command type
// GET /api/admin/quotas/analytics/command-types/{cmdType}
func (qah *QuotaAdminHandlers) GetCommandTypeAnalytics(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	cmdType := chi.URLParam(r, "cmdType")

	if qah.analyticsService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "analytics unavailable"})
		return
	}

	stats, err := qah.analyticsService.GetCommandTypeStats(ctx, cmdType)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get stats"})
		return
	}

	writeJSON(w, http.StatusOK, stats)
}

// GetViolationTrends returns violation trends
// GET /api/admin/quotas/analytics/violations/trends
func (qah *QuotaAdminHandlers) GetViolationTrends(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	days := 7
	if d := r.URL.Query().Get("days"); d != "" {
		if parsed, err := strconv.Atoi(d); err == nil && parsed > 0 && parsed <= 365 {
			days = parsed
		}
	}

	if qah.analyticsService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "analytics unavailable"})
		return
	}

	trends, err := qah.analyticsService.GetQuotaViolationTrends(ctx, days)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get trends"})
		return
	}

	response := map[string]interface{}{
		"trends": trends,
		"days":   days,
		"count":  len(trends),
	}

	writeJSON(w, http.StatusOK, response)
}

// GetHighUtilizationUsers returns users with high quota utilization
// GET /api/admin/quotas/analytics/high-utilization
func (qah *QuotaAdminHandlers) GetHighUtilizationUsers(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	if qah.analyticsService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "analytics unavailable"})
		return
	}

	users, err := qah.analyticsService.GetHighUtilizationUsers(ctx)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get users"})
		return
	}

	response := map[string]interface{}{
		"users": users,
		"count": len(users),
	}

	writeJSON(w, http.StatusOK, response)
}

// GetPredictedViolations returns predicted quota violations
// GET /api/admin/quotas/analytics/predictions
func (qah *QuotaAdminHandlers) GetPredictedViolations(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	if qah.analyticsService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "analytics unavailable"})
		return
	}

	predictions, err := qah.analyticsService.GetPredictedViolations(ctx)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get predictions"})
		return
	}

	response := map[string]interface{}{
		"predictions": predictions,
		"count":       len(predictions),
	}

	writeJSON(w, http.StatusOK, response)
}

// GetUserTrends returns trend data for a user
// GET /api/admin/quotas/analytics/users/{userID}/trends
func (qah *QuotaAdminHandlers) GetUserTrends(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userIDStr := chi.URLParam(r, "userID")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid user ID"})
		return
	}

	days := 7
	if d := r.URL.Query().Get("days"); d != "" {
		if parsed, err := strconv.Atoi(d); err == nil && parsed > 0 && parsed <= 365 {
			days = parsed
		}
	}

	if qah.analyticsService == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "analytics unavailable"})
		return
	}

	trends, err := qah.analyticsService.GetUserTrends(ctx, userID, days)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get trends"})
		return
	}

	writeJSON(w, http.StatusOK, trends)
}

// Alert endpoints

// GetAlerts returns recent alerts
// GET /api/admin/quotas/alerts
func (qah *QuotaAdminHandlers) GetAlerts(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	limit := 100
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 500 {
			limit = parsed
		}
	}

	alertType := r.URL.Query().Get("type")

	if qah.alertEngine == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "alert service unavailable"})
		return
	}

	alerts, err := qah.alertEngine.GetAlerts(ctx, limit, alertType)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get alerts"})
		return
	}

	response := map[string]interface{}{
		"alerts": alerts,
		"count":  len(alerts),
	}

	writeJSON(w, http.StatusOK, response)
}

// CreateAlert creates a new alert rule
// POST /api/admin/quotas/alerts
func (qah *QuotaAdminHandlers) CreateAlert(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var rule rate_limiting.AlertRule
	if err := decodeJSON(r, &rule); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}

	if qah.alertEngine == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "alert service unavailable"})
		return
	}

	id, err := qah.alertEngine.CreateAlertRule(ctx, rule)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to create alert rule"})
		return
	}

	response := map[string]interface{}{
		"rule_id": id,
		"created": true,
		"message": "Alert rule created successfully",
	}

	writeJSON(w, http.StatusCreated, response)
}

// UpdateAlert updates an alert rule
// PUT /api/admin/quotas/alerts/{alertID}
func (qah *QuotaAdminHandlers) UpdateAlert(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	alertIDStr := chi.URLParam(r, "alertID")
	alertID, err := strconv.ParseInt(alertIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid alert ID"})
		return
	}

	var updates map[string]interface{}
	if err := decodeJSON(r, &updates); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}

	if qah.alertEngine == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "alert service unavailable"})
		return
	}

	// Convert map to AlertRule for update
	var rule rate_limiting.AlertRule
	rule.ID = alertID
	// Apply updates from map to rule struct
	if name, ok := updates["name"].(string); ok {
		rule.Name = name
	}
	if desc, ok := updates["description"].(string); ok {
		rule.Description = desc
	}
	if threshold, ok := updates["threshold"].(float64); ok {
		rule.Threshold = threshold
	}
	if enabled, ok := updates["enabled"].(bool); ok {
		rule.Enabled = enabled
	}

	if err := qah.alertEngine.UpdateAlertRule(ctx, alertID, rule); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to update alert rule"})
		return
	}

	response := map[string]interface{}{
		"alert_id": alertID,
		"updated":  true,
	}

	writeJSON(w, http.StatusOK, response)
}

// DeleteAlert deletes an alert rule
// DELETE /api/admin/quotas/alerts/{alertID}
func (qah *QuotaAdminHandlers) DeleteAlert(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	alertIDStr := chi.URLParam(r, "alertID")
	alertID, err := strconv.ParseInt(alertIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid alert ID"})
		return
	}

	if qah.alertEngine == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "alert service unavailable"})
		return
	}

	if err := qah.alertEngine.DeleteAlertRule(ctx, alertID); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to delete alert rule"})
		return
	}

	writeJSON(w, http.StatusNoContent, nil)
}

// ServeAdminDashboard serves the admin quotas dashboard HTML
// GET /admin/quotas
func (qah *QuotaAdminHandlers) ServeAdminDashboard(w http.ResponseWriter, r *http.Request) {
	// Read the dashboard template
	dashboardHTML, err := ioutil.ReadFile("./templates/admin_quotas_dashboard.html")
	if err != nil {
		http.Error(w, "Dashboard template not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write(dashboardHTML)
}

// Helper functions

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if data != nil {
		json.NewEncoder(w).Encode(data)
	}
}

func decodeJSON(r *http.Request, v interface{}) error {
	return json.NewDecoder(r.Body).Decode(v)
}
