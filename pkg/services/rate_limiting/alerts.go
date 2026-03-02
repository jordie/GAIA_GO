package rate_limiting

import (
	"time"
)

// Alert Types
const (
	AlertTypeHighUtilization     = "high_utilization"     // >80% quota used
	AlertTypeQuotaViolation      = "quota_violation"      // Exceeded limit
	AlertTypeSustainedThrottling = "sustained_throttling" // >50% commands throttled
	AlertTypeSystemLoad          = "high_system_load"     // CPU/memory critical
	AlertTypeAnomalies           = "usage_anomalies"      // Unusual patterns
	AlertTypeApproachingLimit    = "approaching_limit"    // >90% quota used
)

// Alert Status constants (defined in alert_service.go)

// AlertNotification represents a sent notification
// This is used for tracking notification delivery
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

// Note: The primary alert management system is in alert_service.go
// The AlertService provides in-memory alert rule management and evaluation
