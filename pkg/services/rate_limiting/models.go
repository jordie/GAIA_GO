package rate_limiting

import (
	"time"
)

// Rule represents a rate limiting rule
type Rule struct {
	ID           int64
	RuleName     string
	SystemID     string // 'gaia_go', 'gaia_mvp', 'global'
	Scope        string // 'ip', 'session', 'user', 'api_key'
	ScopeValue   string // Specific value or empty for default
	LimitType    string // 'requests_per_second', 'requests_per_minute', 'daily_quota'
	LimitValue   int
	ResourceType string // Endpoint/command type or empty for all
	Enabled      bool
	Priority     int // Lower = applied first
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

// LimitCheckRequest contains request metadata for rate limit check
type LimitCheckRequest struct {
	SystemID     string
	Scope        string
	ScopeValue   string
	ResourceType string
	RequestPath  string
	Method       string
	Headers      map[string]string
	Metadata     map[string]interface{}
}

// Decision is the rate limiting decision
type Decision struct {
	Allowed           bool
	RuleID            int64
	Reason            string
	RetryAfterSeconds int
	Limit             int
	Remaining         int
	ResetTime         time.Time
}

// Usage represents current usage for a scope
type Usage struct {
	Scope             string
	ScopeValue        string
	ResourceType      string
	RequestsAllowed   int
	RequestsBlocked   int
	QuotaLimit        int
	QuotaUsed         int
	QuotaPeriod       string
	ResetTime         time.Time
	AverageRPS        float64
	LastViolationTime *time.Time
}

// Violation represents a rate limit violation
type Violation struct {
	ID             int64
	SystemID       string
	RuleID         *int64
	Scope          string
	ScopeValue     string
	ResourceType   string
	ViolatedLimit  int
	ActualCount    int
	ViolationTime  time.Time
	RequestPath    string
	RequestMethod  string
	UserAgent      string
	Blocked        bool
	Severity       string // 'low', 'medium', 'high', 'critical'
}

// Metric represents rate limiting metrics
type Metric struct {
	ID                  int64
	SystemID            string
	Scope               string
	ScopeValue          string
	Timestamp           time.Time
	RequestsProcessed   int
	RequestsAllowed     int
	RequestsBlocked     int
	AverageResponseTime float64
	CPUUsagePercent     float64
	MemoryUsagePercent  float64
}

// Bucket represents a sliding window bucket
type Bucket struct {
	ID           int64
	RuleID       int64
	SystemID     string
	Scope        string
	ScopeValue   string
	WindowStart  time.Time
	WindowEnd    time.Time
	RequestCount int
	CreatedAt    time.Time
}

// Quota represents a resource quota
type Quota struct {
	ID            int64
	SystemID      string
	Scope         string
	ScopeValue    string
	ResourceType  string
	QuotaPeriod   string // 'daily', 'weekly', 'monthly'
	QuotaLimit    int
	QuotaUsed     int
	PeriodStart   time.Time
	PeriodEnd     time.Time
	LastReset     time.Time
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

// Config contains rate limiter configuration
type Config struct {
	// Cleanup intervals
	BucketCleanupInterval time.Duration // Default: 1 hour
	ViolationRetention    time.Duration // Default: 7 days
	MetricsRetention      time.Duration // Default: 30 days

	// Cache settings
	RuleCacheTTL time.Duration // Default: 5 minutes
	RuleCacheSize int          // Default: 1000 rules

	// Behavior
	EnableMetrics     bool          // Default: true
	EnableViolationTracking bool   // Default: true
	DefaultRetryAfter int           // Default: 60 seconds
	ClockTolerance    time.Duration // Default: 1 second (for clock skew)
}

// DefaultConfig returns default configuration
func DefaultConfig() Config {
	return Config{
		BucketCleanupInterval: 1 * time.Hour,
		ViolationRetention:    7 * 24 * time.Hour,
		MetricsRetention:      30 * 24 * time.Hour,
		RuleCacheTTL:          5 * time.Minute,
		RuleCacheSize:         1000,
		EnableMetrics:         true,
		EnableViolationTracking: true,
		DefaultRetryAfter:     60,
		ClockTolerance:        1 * time.Second,
	}
}

// LimitType constants
const (
	LimitPerSecond  = "requests_per_second"
	LimitPerMinute  = "requests_per_minute"
	LimitPerHour    = "requests_per_hour"
	LimitPerDay     = "daily_quota"
	LimitPerWeek    = "weekly_quota"
	LimitPerMonth   = "monthly_quota"
)

// Scope constants
const (
	ScopeIP      = "ip"
	ScopeSession = "session"
	ScopeUser    = "user"
	ScopeAPIKey  = "api_key"
)

// Severity constants
const (
	SeverityLow      = "low"
	SeverityMedium   = "medium"
	SeverityHigh     = "high"
	SeverityCritical = "critical"
	SeverityWarning  = "warning"
	SeverityInfo     = "info"
)

// Alert Status constants
const (
	AlertStatusActive   = "active"
	AlertStatusResolved = "resolved"
	AlertStatusSilenced = "silenced"
	AlertStatusNew      = "new"
	AlertStatusMonitoring = "monitoring"
	AlertStatusMuted    = "muted"
)

// System ID constants
const (
	SystemGAIAGO = "gaia_go"
	SystemGAIAMVP = "gaia_mvp"
	SystemGlobal = "global"
)
