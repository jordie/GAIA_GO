package rate_limiting

import (
	"context"
	"fmt"
	"sync"
	"time"

	"gorm.io/gorm"
)

// Alert Types
const (
	AlertTypeHighUtilization    = "high_utilization"     // >80% quota used
	AlertTypeQuotaViolation     = "quota_violation"      // Exceeded limit
	AlertTypeSustainedThrottling = "sustained_throttling" // >50% commands throttled
	AlertTypeSystemLoad         = "high_system_load"     // CPU/memory critical
	AlertTypeAnomalies          = "usage_anomalies"      // Unusual patterns
	AlertTypeApproachingLimit   = "approaching_limit"    // >90% quota used
)

// Alert Severity Levels (defined in models.go)

// Alert Status
const (
	AlertStatusNew        = "new"
	AlertStatusMonitoring = "monitoring"
	AlertStatusResolved   = "resolved"
	AlertStatusMuted      = "muted"
)

// Notification Channels
const (
	NotificationEmail   = "email"
	NotificationWebhook = "webhook"
	NotificationSlack   = "slack"
	NotificationDashboard = "dashboard"
)

// AlertRule defines when to trigger alerts
type AlertRule struct {
	ID                 int64
	Name               string
	Description        string
	AlertType          string
	Condition          string              // e.g., "usage > 80", "violations > 5"
	Threshold          float64
	Period             string              // "daily", "hourly", "realtime"
	Enabled            bool
	NotificationChannels []string          // email, webhook, slack, dashboard
	NotifyUsers        bool                // Notify affected users
	NotifyAdmins       bool                // Notify admins
	Severity           string              // low, medium, high, critical
	CreatedAt          time.Time
	UpdatedAt          time.Time
}

// Alert represents a triggered alert
type Alert struct {
	ID            int64
	RuleID        int64
	AlertType     string
	Severity      string
	Status        string
	UserID        *int64
	Username      *string
	CommandType   *string
	Message       string
	Details       map[string]interface{}
	TriggeredAt   time.Time
	ResolvedAt    *time.Time
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

// AlertNotification represents a sent notification
type AlertNotification struct {
	ID          int64
	AlertID     int64
	Channel     string
	Recipient   string
	SentAt      time.Time
	Status      string // "pending", "sent", "failed"
	ErrorMsg    *string
	CreatedAt   time.Time
}

// NotificationChannel is an interface for sending notifications
type NotificationChannel interface {
	Send(ctx context.Context, alert Alert, recipient string) error
	Name() string
}

// EmailNotifier sends email notifications
type EmailNotifier struct {
	// Configuration would include SMTP settings
}

func (en *EmailNotifier) Send(ctx context.Context, alert Alert, recipient string) error {
	// Placeholder - would integrate with SMTP service
	return nil
}

func (en *EmailNotifier) Name() string {
	return NotificationEmail
}

// WebhookNotifier sends webhook notifications
type WebhookNotifier struct {
	URL string
}

func (wn *WebhookNotifier) Send(ctx context.Context, alert Alert, recipient string) error {
	// Placeholder - would send HTTP POST to webhook URL
	return nil
}

func (wn *WebhookNotifier) Name() string {
	return NotificationWebhook
}

// SlackNotifier sends Slack notifications
type SlackNotifier struct {
	WebhookURL string
	Channel    string
}

func (sn *SlackNotifier) Send(ctx context.Context, alert Alert, recipient string) error {
	// Placeholder - would send message to Slack webhook
	return nil
}

func (sn *SlackNotifier) Name() string {
	return NotificationSlack
}

// DashboardNotifier stores alerts for dashboard display
type DashboardNotifier struct {
	db *gorm.DB
}

func (dn *DashboardNotifier) Send(ctx context.Context, alert Alert, recipient string) error {
	// Already stored in database by alert engine
	return nil
}

func (dn *DashboardNotifier) Name() string {
	return NotificationDashboard
}

// AlertEngine manages alert rules and triggering
type AlertEngine struct {
	db                *gorm.DB
	analytics         *QuotaAnalytics
	notifiers         map[string]NotificationChannel
	rules             []AlertRule
	ruleLock          sync.RWMutex
	checkInterval     time.Duration
	activeAlerts      map[int64]Alert // In-memory cache of active alerts
	alertLock         sync.RWMutex
}

// NewAlertEngine creates a new alert engine
func NewAlertEngine(db *gorm.DB, analytics *QuotaAnalytics) *AlertEngine {
	engine := &AlertEngine{
		db:            db,
		analytics:     analytics,
		notifiers:     make(map[string]NotificationChannel),
		checkInterval: 5 * time.Minute,
		activeAlerts:  make(map[int64]Alert),
	}

	// Register default notifiers
	engine.RegisterNotifier(&DashboardNotifier{db: db})
	engine.RegisterNotifier(&EmailNotifier{})
	engine.RegisterNotifier(&WebhookNotifier{})
	engine.RegisterNotifier(&SlackNotifier{})

	return engine
}

// RegisterNotifier registers a notification channel
func (ae *AlertEngine) RegisterNotifier(notifier NotificationChannel) {
	ae.notifiers[notifier.Name()] = notifier
}

// CreateAlertRule creates a new alert rule
func (ae *AlertEngine) CreateAlertRule(ctx context.Context, rule AlertRule) (int64, error) {
	rule.CreatedAt = time.Now()
	rule.UpdatedAt = time.Now()

	result := ae.db.WithContext(ctx).
		Table("alert_rules").
		Create(&rule)

	if result.Error != nil {
		return 0, fmt.Errorf("failed to create alert rule: %w", result.Error)
	}

	// Invalidate rule cache
	ae.ruleLock.Lock()
	ae.rules = nil
	ae.ruleLock.Unlock()

	return rule.ID, nil
}

// UpdateAlertRule updates an alert rule
func (ae *AlertEngine) UpdateAlertRule(ctx context.Context, id int64, rule AlertRule) error {
	rule.UpdatedAt = time.Now()

	result := ae.db.WithContext(ctx).
		Table("alert_rules").
		Where("id = ?", id).
		Updates(&rule)

	if result.Error != nil {
		return fmt.Errorf("failed to update alert rule: %w", result.Error)
	}

	// Invalidate rule cache
	ae.ruleLock.Lock()
	ae.rules = nil
	ae.ruleLock.Unlock()

	return nil
}

// DeleteAlertRule deletes an alert rule
func (ae *AlertEngine) DeleteAlertRule(ctx context.Context, id int64) error {
	result := ae.db.WithContext(ctx).
		Table("alert_rules").
		Where("id = ?", id).
		Delete(nil)

	if result.Error != nil {
		return fmt.Errorf("failed to delete alert rule: %w", result.Error)
	}

	// Invalidate rule cache
	ae.ruleLock.Lock()
	ae.rules = nil
	ae.ruleLock.Unlock()

	return nil
}

// GetAlertRules returns all alert rules
func (ae *AlertEngine) GetAlertRules(ctx context.Context) ([]AlertRule, error) {
	ae.ruleLock.RLock()
	if ae.rules != nil {
		defer ae.ruleLock.RUnlock()
		return ae.rules, nil
	}
	ae.ruleLock.RUnlock()

	var rules []AlertRule
	result := ae.db.WithContext(ctx).
		Table("alert_rules").
		Where("enabled = true").
		Find(&rules)

	if result.Error != nil {
		return nil, fmt.Errorf("failed to get alert rules: %w", result.Error)
	}

	// Cache rules
	ae.ruleLock.Lock()
	ae.rules = rules
	ae.ruleLock.Unlock()

	return rules, nil
}

// CheckAlerts checks all rules and triggers alerts as needed
func (ae *AlertEngine) CheckAlerts(ctx context.Context) ([]Alert, error) {
	var triggeredAlerts []Alert

	rules, err := ae.GetAlertRules(ctx)
	if err != nil {
		return nil, err
	}

	// Get system stats for threshold checking
	systemStats, err := ae.analytics.GetSystemStats(ctx)
	if err != nil {
		return nil, err
	}

	for _, rule := range rules {
		alerts, err := ae.checkRule(ctx, rule, systemStats)
		if err != nil {
			fmt.Printf("Error checking rule %d: %v\n", rule.ID, err)
			continue
		}
		triggeredAlerts = append(triggeredAlerts, alerts...)
	}

	return triggeredAlerts, nil
}

// checkRule checks a specific rule and triggers alert if conditions met
func (ae *AlertEngine) checkRule(ctx context.Context, rule AlertRule, stats SystemStats) ([]Alert, error) {
	var alerts []Alert

	switch rule.AlertType {
	case AlertTypeHighUtilization:
		alerts = ae.checkHighUtilization(ctx, rule, stats)
	case AlertTypeQuotaViolation:
		alerts = ae.checkQuotaViolations(ctx, rule, stats)
	case AlertTypeSustainedThrottling:
		alerts = ae.checkSustainedThrottling(ctx, rule, stats)
	case AlertTypeSystemLoad:
		alerts = ae.checkSystemLoad(ctx, rule, stats)
	case AlertTypeAnomalies:
		alerts = ae.checkAnomalies(ctx, rule, stats)
	case AlertTypeApproachingLimit:
		alerts = ae.checkApproachingLimit(ctx, rule, stats)
	}

	// Store triggered alerts
	for _, alert := range alerts {
		alert.RuleID = rule.ID
		alert.Status = AlertStatusNew
		alert.Severity = rule.Severity
		alert.TriggeredAt = time.Now()

		if err := ae.storeAlert(ctx, alert); err != nil {
			return nil, fmt.Errorf("failed to store alert: %w", err)
		}

		// Send notifications
		if err := ae.sendNotifications(ctx, alert, rule); err != nil {
			fmt.Printf("Error sending notifications for alert %d: %v\n", alert.ID, err)
		}
	}

	return alerts, nil
}

// checkHighUtilization checks for high quota utilization
func (ae *AlertEngine) checkHighUtilization(ctx context.Context, rule AlertRule, stats SystemStats) []Alert {
	var alerts []Alert

	highUtilUsers, err := ae.analytics.GetHighUtilizationUsers(ctx)
	if err != nil {
		return alerts
	}

	for _, user := range highUtilUsers {
		if user.DailyUtilization > rule.Threshold {
			alert := Alert{
				AlertType: AlertTypeHighUtilization,
				UserID:    &user.UserID,
				Username:  &user.Username,
				Message:   fmt.Sprintf("User %s has %.1f%% daily quota utilization", user.Username, user.DailyUtilization),
				Details: map[string]interface{}{
					"user_id":             user.UserID,
					"daily_utilization":   user.DailyUtilization,
					"weekly_utilization":  user.WeeklyUtilization,
					"monthly_utilization": user.MonthlyUtilization,
				},
			}
			alerts = append(alerts, alert)
		}
	}

	return alerts
}

// checkQuotaViolations checks for quota violations
func (ae *AlertEngine) checkQuotaViolations(ctx context.Context, rule AlertRule, stats SystemStats) []Alert {
	var alerts []Alert

	// Check if violations exceeded threshold
	if float64(stats.QuotasExceededToday) > rule.Threshold {
		alert := Alert{
			AlertType: AlertTypeQuotaViolation,
			Message:   fmt.Sprintf("%d quota violations today", stats.QuotasExceededToday),
			Details: map[string]interface{}{
				"violations_today": stats.QuotasExceededToday,
				"total_users":      stats.TotalUsers,
			},
		}
		alerts = append(alerts, alert)
	}

	return alerts
}

// checkSustainedThrottling checks for sustained throttling
func (ae *AlertEngine) checkSustainedThrottling(ctx context.Context, rule AlertRule, stats SystemStats) []Alert {
	var alerts []Alert

	// Check if average throttle factor indicates throttling
	if stats.AverageThrottleFactor < (1.0 - rule.Threshold/100) {
		alert := Alert{
			AlertType: AlertTypeSustainedThrottling,
			Message:   fmt.Sprintf("Sustained throttling detected: %.0f%% average speed", stats.AverageThrottleFactor*100),
			Details: map[string]interface{}{
				"average_throttle": stats.AverageThrottleFactor,
				"system_load":      stats.SystemLoad,
			},
		}
		alerts = append(alerts, alert)
	}

	return alerts
}

// checkSystemLoad checks for high system load
func (ae *AlertEngine) checkSystemLoad(ctx context.Context, rule AlertRule, stats SystemStats) []Alert {
	var alerts []Alert

	if stats.SystemLoad.CPUPercent > rule.Threshold {
		alert := Alert{
			AlertType: AlertTypeSystemLoad,
			Message:   fmt.Sprintf("High CPU usage: %.1f%%", stats.SystemLoad.CPUPercent),
			Details: map[string]interface{}{
				"cpu_percent":    stats.SystemLoad.CPUPercent,
				"memory_percent": stats.SystemLoad.MemoryPercent,
			},
		}
		alerts = append(alerts, alert)
	}

	if stats.SystemLoad.MemoryPercent > rule.Threshold {
		alert := Alert{
			AlertType: AlertTypeSystemLoad,
			Message:   fmt.Sprintf("High memory usage: %.1f%%", stats.SystemLoad.MemoryPercent),
			Details: map[string]interface{}{
				"cpu_percent":    stats.SystemLoad.CPUPercent,
				"memory_percent": stats.SystemLoad.MemoryPercent,
			},
		}
		alerts = append(alerts, alert)
	}

	return alerts
}

// checkAnomalies checks for usage anomalies
func (ae *AlertEngine) checkAnomalies(ctx context.Context, rule AlertRule, stats SystemStats) []Alert {
	var alerts []Alert
	// Placeholder for ML-based anomaly detection
	return alerts
}

// checkApproachingLimit checks for users approaching limits
func (ae *AlertEngine) checkApproachingLimit(ctx context.Context, rule AlertRule, stats SystemStats) []Alert {
	var alerts []Alert

	highUtilUsers, err := ae.analytics.GetHighUtilizationUsers(ctx)
	if err != nil {
		return alerts
	}

	for _, user := range highUtilUsers {
		if user.DailyUtilization > rule.Threshold && user.DailyUtilization < 100 {
			alert := Alert{
				AlertType: AlertTypeApproachingLimit,
				UserID:    &user.UserID,
				Username:  &user.Username,
				Message:   fmt.Sprintf("User %s approaching daily quota limit (%.1f%%)", user.Username, user.DailyUtilization),
				Details: map[string]interface{}{
					"user_id":           user.UserID,
					"utilization":       user.DailyUtilization,
					"days_until_reset":  user.DaysUntilReset,
					"predicted_violation": user.PredictedViolation,
				},
			}
			alerts = append(alerts, alert)
		}
	}

	return alerts
}

// storeAlert stores an alert in the database
func (ae *AlertEngine) storeAlert(ctx context.Context, alert Alert) error {
	alert.CreatedAt = time.Now()
	alert.UpdatedAt = time.Now()

	result := ae.db.WithContext(ctx).
		Table("alerts").
		Create(&alert)

	if result.Error != nil {
		return fmt.Errorf("failed to store alert: %w", result.Error)
	}

	// Cache active alert
	ae.alertLock.Lock()
	ae.activeAlerts[alert.ID] = alert
	ae.alertLock.Unlock()

	return nil
}

// sendNotifications sends alert notifications through configured channels
func (ae *AlertEngine) sendNotifications(ctx context.Context, alert Alert, rule AlertRule) error {
	for _, channelName := range rule.NotificationChannels {
		notifier, exists := ae.notifiers[channelName]
		if !exists {
			continue
		}

		// Determine recipient
		recipient := ""
		if rule.NotifyUsers && alert.UserID != nil {
			// Get user email from database
			var email string
			ae.db.WithContext(ctx).
				Table("users").
				Where("id = ?", *alert.UserID).
				Select("email").
				Scan(&email)
			recipient = email
		} else if rule.NotifyAdmins {
			// Get admin email (placeholder)
			recipient = "admin@example.com"
		}

		if recipient == "" {
			continue
		}

		// Send notification
		if err := notifier.Send(ctx, alert, recipient); err != nil {
			fmt.Printf("Failed to send notification via %s: %v\n", channelName, err)
		}

		// Log notification
		notification := AlertNotification{
			AlertID:   alert.ID,
			Channel:   channelName,
			Recipient: recipient,
			SentAt:    time.Now(),
			Status:    "sent",
			CreatedAt: time.Now(),
		}

		ae.db.WithContext(ctx).
			Table("alert_notifications").
			Create(&notification)
	}

	return nil
}

// ResolveAlert marks an alert as resolved
func (ae *AlertEngine) ResolveAlert(ctx context.Context, alertID int64) error {
	now := time.Now()
	result := ae.db.WithContext(ctx).
		Table("alerts").
		Where("id = ?", alertID).
		Updates(map[string]interface{}{
			"status":      AlertStatusResolved,
			"resolved_at": now,
			"updated_at":  now,
		})

	if result.Error != nil {
		return fmt.Errorf("failed to resolve alert: %w", result.Error)
	}

	// Update cache
	ae.alertLock.Lock()
	if alert, exists := ae.activeAlerts[alertID]; exists {
		alert.Status = AlertStatusResolved
		alert.ResolvedAt = &now
		ae.activeAlerts[alertID] = alert
	}
	ae.alertLock.Unlock()

	return nil
}

// GetAlerts returns recent alerts with optional filtering
func (ae *AlertEngine) GetAlerts(ctx context.Context, limit int, alertType string) ([]Alert, error) {
	var alerts []Alert

	query := ae.db.WithContext(ctx).
		Table("alerts").
		Order("triggered_at DESC").
		Limit(limit)

	if alertType != "" {
		query = query.Where("alert_type = ?", alertType)
	}

	result := query.Find(&alerts)

	if result.Error != nil {
		return nil, fmt.Errorf("failed to get alerts: %w", result.Error)
	}

	return alerts, nil
}

// GetActiveAlerts returns currently active (unresolved) alerts
func (ae *AlertEngine) GetActiveAlerts(ctx context.Context) ([]Alert, error) {
	var alerts []Alert

	result := ae.db.WithContext(ctx).
		Table("alerts").
		Where("status IN (?, ?)", AlertStatusNew, AlertStatusMonitoring).
		Order("triggered_at DESC").
		Find(&alerts)

	if result.Error != nil {
		return nil, fmt.Errorf("failed to get active alerts: %w", result.Error)
	}

	return alerts, nil
}
