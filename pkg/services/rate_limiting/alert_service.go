package rate_limiting

import (
	"fmt"
	"sync"
	"time"
)

// AlertSeverity defines the alert severity level
type AlertSeverity string

const (
	SeverityCritical AlertSeverity = "critical"
	SeverityWarning  AlertSeverity = "warning"
	SeverityInfo     AlertSeverity = "info"
)

// AlertStatus defines the alert status
type AlertStatus string

const (
	AlertStatusActive   AlertStatus = "active"
	AlertStatusResolved AlertStatus = "resolved"
	AlertStatusSilenced AlertStatus = "silenced"
)

// AlertRule defines a rule that triggers alerts
type AlertRule struct {
	ID                string
	Name              string
	Description       string
	Severity          AlertSeverity
	Condition         AlertCondition
	ThresholdValue    float64
	CheckInterval     time.Duration
	ReevaluationDelay time.Duration
	Enabled           bool
	CreatedAt         time.Time
	UpdatedAt         time.Time
}

// AlertCondition defines the condition to check
type AlertCondition struct {
	Type      string  // "greater_than", "less_than", "equals", "percentage_change"
	Metric    string  // "appeal_submission_rate", "error_rate", "latency_p99", etc.
	Threshold float64
	Duration  time.Duration // How long condition must persist before alert
}

// Alert represents an active alert
type Alert struct {
	ID              string
	RuleID          string
	Severity        AlertSeverity
	Status          AlertStatus
	Title           string
	Description     string
	CurrentValue    float64
	ThresholdValue  float64
	TriggeredAt     time.Time
	ResolvedAt      *time.Time
	FiredCount      int
	LastFiredAt     time.Time
	SilencedUntil   *time.Time
	AffectedMetric  string
}

// AlertEvent represents a historical alert event
type AlertEvent struct {
	ID          string
	AlertID     string
	RuleID      string
	EventType   string // "triggered", "resolved", "silenced"
	Severity    AlertSeverity
	Value       float64
	Threshold   float64
	Message     string
	Timestamp   time.Time
	Metadata    map[string]interface{}
}

// NotificationChannel defines where alerts are sent
type NotificationChannel struct {
	ID        string
	Type      string // "email", "slack", "pagerduty", "webhook"
	Config    map[string]string
	Enabled   bool
	CreatedAt time.Time
}

// AlertService manages alert rules and active alerts
type AlertService struct {
	rules              map[string]*AlertRule
	alerts             map[string]*Alert
	events             []AlertEvent
	notificationChans  map[string]*NotificationChannel
	activeMetrics      map[string]float64
	metricsMutex       sync.RWMutex
	alertsMutex        sync.RWMutex
	evaluationTickers  map[string]*time.Ticker
	stopChannels       map[string]chan bool
}

// NewAlertService creates a new alert service
func NewAlertService() *AlertService {
	return &AlertService{
		rules:             make(map[string]*AlertRule),
		alerts:            make(map[string]*Alert),
		events:            make([]AlertEvent, 0),
		notificationChans: make(map[string]*NotificationChannel),
		activeMetrics:     make(map[string]float64),
		evaluationTickers: make(map[string]*time.Ticker),
		stopChannels:      make(map[string]chan bool),
	}
}

// RegisterAlertRule registers a new alert rule
func (s *AlertService) RegisterAlertRule(rule *AlertRule) error {
	if rule.ID == "" {
		return fmt.Errorf("alert rule must have an ID")
	}

	s.alertsMutex.Lock()
	defer s.alertsMutex.Unlock()

	s.rules[rule.ID] = rule

	// Start evaluation loop for this rule
	if rule.Enabled {
		s.startRuleEvaluation(rule.ID)
	}

	return nil
}

// UpdateMetric updates the current value of a metric
func (s *AlertService) UpdateMetric(metricName string, value float64) {
	s.metricsMutex.Lock()
	defer s.metricsMutex.Unlock()

	s.activeMetrics[metricName] = value
}

// GetMetric retrieves the current value of a metric
func (s *AlertService) GetMetric(metricName string) float64 {
	s.metricsMutex.RLock()
	defer s.metricsMutex.RUnlock()

	return s.activeMetrics[metricName]
}

// startRuleEvaluation starts the evaluation loop for a rule
func (s *AlertService) startRuleEvaluation(ruleID string) {
	rule, exists := s.rules[ruleID]
	if !exists {
		return
	}

	stopChan := make(chan bool)
	s.stopChannels[ruleID] = stopChan

	ticker := time.NewTicker(rule.CheckInterval)
	s.evaluationTickers[ruleID] = ticker

	go func() {
		for {
			select {
			case <-ticker.C:
				s.evaluateRule(ruleID)
			case <-stopChan:
				ticker.Stop()
				return
			}
		}
	}()
}

// evaluateRule evaluates a single rule against current metrics
func (s *AlertService) evaluateRule(ruleID string) {
	s.alertsMutex.Lock()
	rule := s.rules[ruleID]
	s.alertsMutex.Unlock()

	if rule == nil || !rule.Enabled {
		return
	}

	// Get current metric value
	currentValue := s.GetMetric(rule.Condition.Metric)

	// Evaluate condition
	conditionMet := s.evaluateCondition(rule.Condition, currentValue)

	s.alertsMutex.Lock()
	defer s.alertsMutex.Unlock()

	// Check if alert already exists
	existingAlert := s.findAlertByRuleID(ruleID)

	if conditionMet {
		if existingAlert == nil {
			// Create new alert
			alert := &Alert{
				ID:             fmt.Sprintf("alert_%d", time.Now().Unix()),
				RuleID:         ruleID,
				Severity:       rule.Severity,
				Status:         AlertStatusActive,
				Title:          rule.Name,
				Description:    rule.Description,
				CurrentValue:   currentValue,
				ThresholdValue: rule.Condition.Threshold,
				TriggeredAt:    time.Now(),
				FiredCount:     1,
				LastFiredAt:    time.Now(),
				AffectedMetric: rule.Condition.Metric,
			}

			s.alerts[alert.ID] = alert
			s.recordAlertEvent(alert, "triggered")

			// Send notifications
			s.sendNotifications(alert)
		} else {
			// Update existing alert
			existingAlert.FiredCount++
			existingAlert.LastFiredAt = time.Now()
			existingAlert.CurrentValue = currentValue

			s.recordAlertEvent(existingAlert, "fired")
		}
	} else if existingAlert != nil {
		// Condition no longer met, resolve alert
		now := time.Now()
		existingAlert.Status = AlertStatusResolved
		existingAlert.ResolvedAt = &now

		s.recordAlertEvent(existingAlert, "resolved")

		// Send resolution notification
		s.sendNotifications(existingAlert)
	}
}

// evaluateCondition evaluates an alert condition
func (s *AlertService) evaluateCondition(condition AlertCondition, value float64) bool {
	switch condition.Type {
	case "greater_than":
		return value > condition.Threshold
	case "less_than":
		return value < condition.Threshold
	case "equals":
		return value == condition.Threshold
	case "percentage_change":
		// Would implement percentage change logic
		return false
	default:
		return false
	}
}

// findAlertByRuleID finds an active alert for a rule
func (s *AlertService) findAlertByRuleID(ruleID string) *Alert {
	for _, alert := range s.alerts {
		if alert.RuleID == ruleID && alert.Status == AlertStatusActive {
			return alert
		}
	}
	return nil
}

// GetActiveAlerts returns all active alerts
func (s *AlertService) GetActiveAlerts() []*Alert {
	s.alertsMutex.RLock()
	defer s.alertsMutex.RUnlock()

	active := make([]*Alert, 0)
	for _, alert := range s.alerts {
		if alert.Status == AlertStatusActive {
			active = append(active, alert)
		}
	}
	return active
}

// GetAlertsBySeverity returns alerts of a specific severity
func (s *AlertService) GetAlertsBySeverity(severity AlertSeverity) []*Alert {
	s.alertsMutex.RLock()
	defer s.alertsMutex.Unlock()

	alerts := make([]*Alert, 0)
	for _, alert := range s.alerts {
		if alert.Severity == severity && alert.Status == AlertStatusActive {
			alerts = append(alerts, alert)
		}
	}
	return alerts
}

// ResolveAlert manually resolves an alert
func (s *AlertService) ResolveAlert(alertID string) error {
	s.alertsMutex.Lock()
	defer s.alertsMutex.Unlock()

	alert, exists := s.alerts[alertID]
	if !exists {
		return fmt.Errorf("alert not found: %s", alertID)
	}

	now := time.Now()
	alert.Status = AlertStatusResolved
	alert.ResolvedAt = &now

	s.recordAlertEvent(alert, "resolved")

	return nil
}

// SilenceAlert silences an alert until a specific time
func (s *AlertService) SilenceAlert(alertID string, duration time.Duration) error {
	s.alertsMutex.Lock()
	defer s.alertsMutex.Unlock()

	alert, exists := s.alerts[alertID]
	if !exists {
		return fmt.Errorf("alert not found: %s", alertID)
	}

	silencedUntil := time.Now().Add(duration)
	alert.SilencedUntil = &silencedUntil
	alert.Status = AlertStatusSilenced

	s.recordAlertEvent(alert, "silenced")

	return nil
}

// recordAlertEvent records an alert event in history
func (s *AlertService) recordAlertEvent(alert *Alert, eventType string) {
	event := AlertEvent{
		ID:        fmt.Sprintf("event_%d", time.Now().UnixNano()),
		AlertID:   alert.ID,
		RuleID:    alert.RuleID,
		EventType: eventType,
		Severity:  alert.Severity,
		Value:     alert.CurrentValue,
		Threshold: alert.ThresholdValue,
		Message:   fmt.Sprintf("%s: %s (%v / %v)", eventType, alert.Title, alert.CurrentValue, alert.ThresholdValue),
		Timestamp: time.Now(),
		Metadata: map[string]interface{}{
			"metric": alert.AffectedMetric,
			"count":  alert.FiredCount,
		},
	}

	s.events = append(s.events, event)

	// Keep only last 10000 events
	if len(s.events) > 10000 {
		s.events = s.events[1:]
	}
}

// GetAlertHistory returns alert events in reverse chronological order
func (s *AlertService) GetAlertHistory(limit int) []AlertEvent {
	s.alertsMutex.RLock()
	defer s.alertsMutex.RUnlock()

	start := len(s.events) - limit
	if start < 0 {
		start = 0
	}

	history := make([]AlertEvent, 0)
	for i := len(s.events) - 1; i >= start && i >= 0; i-- {
		history = append(history, s.events[i])
	}

	return history
}

// RegisterNotificationChannel registers a notification channel
func (s *AlertService) RegisterNotificationChannel(channel *NotificationChannel) error {
	if channel.ID == "" {
		return fmt.Errorf("notification channel must have an ID")
	}

	s.alertsMutex.Lock()
	defer s.alertsMutex.Unlock()

	s.notificationChans[channel.ID] = channel
	return nil
}

// sendNotifications sends alert notifications to configured channels
func (s *AlertService) sendNotifications(alert *Alert) {
	for _, channel := range s.notificationChans {
		if !channel.Enabled {
			continue
		}

		go s.sendNotification(channel, alert)
	}
}

// sendNotification sends alert to a specific notification channel
func (s *AlertService) sendNotification(channel *NotificationChannel, alert *Alert) {
	switch channel.Type {
	case "email":
		s.sendEmailNotification(channel, alert)
	case "slack":
		s.sendSlackNotification(channel, alert)
	case "pagerduty":
		s.sendPagerDutyNotification(channel, alert)
	case "webhook":
		s.sendWebhookNotification(channel, alert)
	}
}

// sendEmailNotification sends alert via email
func (s *AlertService) sendEmailNotification(channel *NotificationChannel, alert *Alert) {
	// Implementation would use email service
	fmt.Printf("[EMAIL] Alert: %s - %s (Value: %.2f, Threshold: %.2f)\n",
		alert.Severity, alert.Title, alert.CurrentValue, alert.ThresholdValue)
}

// sendSlackNotification sends alert via Slack
func (s *AlertService) sendSlackNotification(channel *NotificationChannel, alert *Alert) {
	// Implementation would use Slack API
	fmt.Printf("[SLACK] Alert: %s - %s (Value: %.2f, Threshold: %.2f)\n",
		alert.Severity, alert.Title, alert.CurrentValue, alert.ThresholdValue)
}

// sendPagerDutyNotification sends alert via PagerDuty
func (s *AlertService) sendPagerDutyNotification(channel *NotificationChannel, alert *Alert) {
	// Implementation would use PagerDuty API
	fmt.Printf("[PAGERDUTY] Alert: %s - %s (Value: %.2f, Threshold: %.2f)\n",
		alert.Severity, alert.Title, alert.CurrentValue, alert.ThresholdValue)
}

// sendWebhookNotification sends alert via webhook
func (s *AlertService) sendWebhookNotification(channel *NotificationChannel, alert *Alert) {
	// Implementation would POST to webhook URL
	fmt.Printf("[WEBHOOK] Alert: %s - %s (Value: %.2f, Threshold: %.2f)\n",
		alert.Severity, alert.Title, alert.CurrentValue, alert.ThresholdValue)
}

// Stop stops all rule evaluation loops
func (s *AlertService) Stop() {
	s.alertsMutex.Lock()
	defer s.alertsMutex.Unlock()

	for ruleID, stopChan := range s.stopChannels {
		if ticker, exists := s.evaluationTickers[ruleID]; exists {
			ticker.Stop()
		}
		close(stopChan)
	}
}

// GetAlertStats returns statistics about alerts
func (s *AlertService) GetAlertStats() map[string]interface{} {
	s.alertsMutex.RLock()
	defer s.alertsMutex.RUnlock()

	critical := 0
	warning := 0
	info := 0

	for _, alert := range s.alerts {
		if alert.Status != AlertStatusActive {
			continue
		}

		switch alert.Severity {
		case SeverityCritical:
			critical++
		case SeverityWarning:
			warning++
		case SeverityInfo:
			info++
		}
	}

	return map[string]interface{}{
		"total_alerts":       len(s.alerts),
		"active_alerts":      critical + warning + info,
		"critical":           critical,
		"warning":            warning,
		"info":               info,
		"total_events":       len(s.events),
		"registered_rules":   len(s.rules),
		"notification_chans": len(s.notificationChans),
	}
}
