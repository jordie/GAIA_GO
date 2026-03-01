package rate_limiting

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestAlertServiceBasic tests basic alert service functionality
func TestAlertServiceBasic(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	// Create an alert rule
	rule := &AlertRule{
		ID:          "test_rule_1",
		Name:        "High Error Rate",
		Description: "Alert when error rate exceeds 5%",
		Severity:    SeverityCritical,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "error_rate",
			Threshold: 0.05,
			Duration:  1 * time.Minute,
		},
		CheckInterval: 10 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	err := alertSvc.RegisterAlertRule(rule)
	require.NoError(t, err)

	// Verify rule was registered
	stats := alertSvc.GetAlertStats()
	assert.Equal(t, float64(1), stats["registered_rules"])
}

// TestAlertTriggering tests alert triggering logic
func TestAlertTriggering(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	// Register rule
	rule := &AlertRule{
		ID:       "test_rule_trigger",
		Name:     "Test Alert",
		Severity: SeverityWarning,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "test_metric",
			Threshold: 100,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	err := alertSvc.RegisterAlertRule(rule)
	require.NoError(t, err)

	// Update metric below threshold
	alertSvc.UpdateMetric("test_metric", 50)
	time.Sleep(2 * time.Second)

	// Should be no active alerts
	activeAlerts := alertSvc.GetActiveAlerts()
	assert.Equal(t, 0, len(activeAlerts))

	// Update metric above threshold
	alertSvc.UpdateMetric("test_metric", 150)
	time.Sleep(2 * time.Second)

	// Should have active alert
	activeAlerts = alertSvc.GetActiveAlerts()
	assert.Greater(t, len(activeAlerts), 0)

	// Alert should have correct values
	alert := activeAlerts[0]
	assert.Equal(t, "Test Alert", alert.Title)
	assert.Equal(t, 150.0, alert.CurrentValue)
	assert.Equal(t, 100.0, alert.ThresholdValue)
	assert.Equal(t, AlertStatusActive, alert.Status)
}

// TestAlertResolution tests alert resolution
func TestAlertResolution(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	rule := &AlertRule{
		ID:       "test_rule_resolve",
		Name:     "Resolution Test",
		Severity: SeverityCritical,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "cpu_usage",
			Threshold: 80,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	alertSvc.RegisterAlertRule(rule)

	// Trigger alert
	alertSvc.UpdateMetric("cpu_usage", 90)
	time.Sleep(2 * time.Second)

	activeAlerts := alertSvc.GetActiveAlerts()
	require.Greater(t, len(activeAlerts), 0)

	alertID := activeAlerts[0].ID

	// Manually resolve alert
	err := alertSvc.ResolveAlert(alertID)
	require.NoError(t, err)

	// Check alert is resolved
	activeAlerts = alertSvc.GetActiveAlerts()
	assert.Equal(t, 0, len(activeAlerts))
}

// TestAlertSilencing tests alert silencing
func TestAlertSilencing(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	rule := &AlertRule{
		ID:       "test_rule_silence",
		Name:     "Silence Test",
		Severity: SeverityWarning,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "memory_usage",
			Threshold: 85,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	alertSvc.RegisterAlertRule(rule)

	// Trigger alert
	alertSvc.UpdateMetric("memory_usage", 90)
	time.Sleep(2 * time.Second)

	activeAlerts := alertSvc.GetActiveAlerts()
	require.Greater(t, len(activeAlerts), 0)

	alertID := activeAlerts[0].ID

	// Silence alert
	err := alertSvc.SilenceAlert(alertID, 5*time.Minute)
	require.NoError(t, err)

	// Alert should now be silenced
	assert.NotNil(t, activeAlerts[0].SilencedUntil)
}

// TestAlertBySeverity tests filtering alerts by severity
func TestAlertBySeverity(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	// Register critical rule
	criticalRule := &AlertRule{
		ID:       "critical_rule",
		Name:     "Critical Alert",
		Severity: SeverityCritical,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "critical_metric",
			Threshold: 100,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	// Register warning rule
	warningRule := &AlertRule{
		ID:       "warning_rule",
		Name:     "Warning Alert",
		Severity: SeverityWarning,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "warning_metric",
			Threshold: 75,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	alertSvc.RegisterAlertRule(criticalRule)
	alertSvc.RegisterAlertRule(warningRule)

	// Trigger both alerts
	alertSvc.UpdateMetric("critical_metric", 150)
	alertSvc.UpdateMetric("warning_metric", 80)
	time.Sleep(2 * time.Second)

	// Get critical alerts
	criticalAlerts := alertSvc.GetAlertsBySeverity(SeverityCritical)
	assert.Equal(t, 1, len(criticalAlerts))

	// Get warning alerts
	warningAlerts := alertSvc.GetAlertsBySeverity(SeverityWarning)
	assert.Equal(t, 1, len(warningAlerts))
}

// TestAlertHistory tests alert history recording
func TestAlertHistory(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	rule := &AlertRule{
		ID:       "history_rule",
		Name:     "History Test",
		Severity: SeverityWarning,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "history_metric",
			Threshold: 100,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	alertSvc.RegisterAlertRule(rule)

	// Trigger alert
	alertSvc.UpdateMetric("history_metric", 150)
	time.Sleep(2 * time.Second)

	// Get history
	history := alertSvc.GetAlertHistory(10)
	assert.Greater(t, len(history), 0)

	// Most recent event should be alert trigger
	event := history[0]
	assert.Equal(t, "triggered", event.EventType)
	assert.Equal(t, SeverityWarning, event.Severity)
}

// TestMultipleAlerts tests multiple alerts at same time
func TestMultipleAlerts(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	// Register 3 rules
	for i := 1; i <= 3; i++ {
		rule := &AlertRule{
			ID:       "multi_rule_" + string(rune(i)),
			Name:     "Multi Alert " + string(rune(i)),
			Severity: SeverityWarning,
			Condition: AlertCondition{
				Type:      "greater_than",
				Metric:    "metric_" + string(rune(i)),
				Threshold: 50,
			},
			CheckInterval: 1 * time.Second,
			Enabled:       true,
			CreatedAt:     time.Now(),
		}
		alertSvc.RegisterAlertRule(rule)
	}

	// Trigger all rules
	for i := 1; i <= 3; i++ {
		alertSvc.UpdateMetric("metric_"+string(rune(i)), 100)
	}

	time.Sleep(2 * time.Second)

	// Check active alerts
	activeAlerts := alertSvc.GetActiveAlerts()
	assert.Greater(t, len(activeAlerts), 0)
}

// TestAlertServiceNotificationChannels tests notification channel registration
func TestAlertServiceNotificationChannels(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	// Register email channel
	emailChannel := &NotificationChannel{
		ID:   "email_channel",
		Type: "email",
		Config: map[string]string{
			"recipients": "admin@example.com",
		},
		Enabled:   true,
		CreatedAt: time.Now(),
	}

	err := alertSvc.RegisterNotificationChannel(emailChannel)
	require.NoError(t, err)

	// Register slack channel
	slackChannel := &NotificationChannel{
		ID:   "slack_channel",
		Type: "slack",
		Config: map[string]string{
			"webhook_url": "https://hooks.slack.com/...",
		},
		Enabled:   true,
		CreatedAt: time.Now(),
	}

	err = alertSvc.RegisterNotificationChannel(slackChannel)
	require.NoError(t, err)

	// Stats should show 2 channels
	stats := alertSvc.GetAlertStats()
	assert.Equal(t, float64(2), stats["notification_chans"])
}

// TestAlertStats tests alert statistics
func TestAlertStats(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	// Initial stats
	stats := alertSvc.GetAlertStats()
	assert.Equal(t, float64(0), stats["active_alerts"])

	// Register and trigger critical alert
	criticalRule := &AlertRule{
		ID:       "stats_critical",
		Name:     "Critical",
		Severity: SeverityCritical,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "critical",
			Threshold: 100,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	alertSvc.RegisterAlertRule(criticalRule)
	alertSvc.UpdateMetric("critical", 150)
	time.Sleep(2 * time.Second)

	// Check stats
	stats = alertSvc.GetAlertStats()
	assert.Greater(t, stats["active_alerts"], float64(0))
	assert.Greater(t, stats["critical"], float64(0))
}

// TestAlertFiringCount tests alert firing count increments
func TestAlertFiringCount(t *testing.T) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	rule := &AlertRule{
		ID:       "firing_rule",
		Name:     "Firing Test",
		Severity: SeverityWarning,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "firing_metric",
			Threshold: 100,
		},
		CheckInterval: 1 * time.Second,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	alertSvc.RegisterAlertRule(rule)

	// Trigger metric
	alertSvc.UpdateMetric("firing_metric", 150)
	time.Sleep(2 * time.Second)

	activeAlerts := alertSvc.GetActiveAlerts()
	require.Greater(t, len(activeAlerts), 0)

	initialCount := activeAlerts[0].FiredCount
	assert.Greater(t, initialCount, 0)

	// Keep metric high and wait for re-evaluation
	time.Sleep(2 * time.Second)

	activeAlerts = alertSvc.GetActiveAlerts()
	require.Greater(t, len(activeAlerts), 0)

	// Firing count should have increased
	newCount := activeAlerts[0].FiredCount
	assert.Greater(t, newCount, initialCount)
}

// BenchmarkAlertEvaluation benchmarks alert rule evaluation
func BenchmarkAlertEvaluation(b *testing.B) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	rule := &AlertRule{
		ID:       "bench_rule",
		Name:     "Benchmark",
		Severity: SeverityWarning,
		Condition: AlertCondition{
			Type:      "greater_than",
			Metric:    "bench_metric",
			Threshold: 100,
		},
		CheckInterval: 1 * time.Millisecond,
		Enabled:       true,
		CreatedAt:     time.Now(),
	}

	alertSvc.RegisterAlertRule(rule)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		alertSvc.UpdateMetric("bench_metric", float64(i%200))
	}
}

// BenchmarkMultipleRules benchmarks multiple rule evaluation
func BenchmarkMultipleRules(b *testing.B) {
	alertSvc := NewAlertService()
	defer alertSvc.Stop()

	// Register 10 rules
	for i := 0; i < 10; i++ {
		rule := &AlertRule{
			ID:       "bench_rule_" + string(rune(i)),
			Name:     "Benchmark " + string(rune(i)),
			Severity: SeverityWarning,
			Condition: AlertCondition{
				Type:      "greater_than",
				Metric:    "bench_metric_" + string(rune(i)),
				Threshold: 100,
			},
			CheckInterval: 100 * time.Millisecond,
			Enabled:       true,
			CreatedAt:     time.Now(),
		}
		alertSvc.RegisterAlertRule(rule)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		for j := 0; j < 10; j++ {
			alertSvc.UpdateMetric("bench_metric_"+string(rune(j)), float64((i+j)%200))
		}
	}
}
