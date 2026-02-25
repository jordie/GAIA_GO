package dto

import "time"

// Event Analytics DTOs

// EventTimelineResponse represents a point in event timeline
type EventTimelineResponse struct {
	Timestamp time.Time `json:"timestamp"`
	Count     int64     `json:"count"`
	EventType string    `json:"event_type"`
}

// EventsByTypeResponse represents events grouped by type
type EventsByTypeResponse struct {
	Type  string `json:"type"`
	Count int64  `json:"count"`
}

// EventRetentionResponse represents retention metrics
type EventRetentionResponse struct {
	Period        string  `json:"period"`
	RetainedUsers int64   `json:"retained_users"`
	RetentionRate float64 `json:"retention_rate"`
}

// CohortAnalysisResponse represents cohort analysis data
type CohortAnalysisResponse struct {
	Week  string `json:"week"`
	Count int    `json:"count"`
}

// EventFunnelResponse represents funnel analysis
type EventFunnelResponse struct {
	Name  string       `json:"name"`
	Steps []FunnelStep `json:"steps"`
}

// FunnelStep represents a step in the funnel
type FunnelStep struct {
	Name      string  `json:"name"`
	Count     int64   `json:"count"`
	Dropoff   float64 `json:"dropoff"`
	Retention float64 `json:"retention"`
}

// EventCorrelationResponse represents event correlations
type EventCorrelationResponse struct {
	EventType   string  `json:"event_type"`
	Correlation float64 `json:"correlation"`
	Frequency   int64   `json:"frequency"`
}

// AnomalyResponse represents detected anomalies
type AnomalyResponse struct {
	Timestamp time.Time `json:"timestamp"`
	Value     int64     `json:"value"`
	Threshold int64     `json:"threshold"`
	Severity  string    `json:"severity"`
}

// ForecastResponse represents forecasted values
type ForecastResponse struct {
	Period      string  `json:"period"`
	Forecast    float64 `json:"forecast"`
	Confidence  float64 `json:"confidence"`
	LowerBound  float64 `json:"lower_bound"`
	UpperBound  float64 `json:"upper_bound"`
}

// EngagementMetricsResponse represents engagement metrics
type EngagementMetricsResponse struct {
	ActiveUsers        int64 `json:"active_users"`
	TotalSessions      int64 `json:"total_sessions"`
	AvgSessionDuration int   `json:"avg_session_duration"`
	EngagementRate     float64 `json:"engagement_rate"`
}

// Presence Analytics DTOs

// PresenceTrendRequest represents presence trend request
type PresenceTrendRequest struct {
	Period   string `json:"period"`
	Interval string `json:"interval"`
}

// PresenceTrendResponse represents presence trend response
type PresenceTrendResponse struct {
	Data    []interface{}         `json:"data"`
	Summary map[string]interface{} `json:"summary"`
}

// User Analytics DTOs

// UserGrowthResponse represents user growth metrics
type UserGrowthResponse struct {
	Period         string  `json:"period"`
	TotalUsers     int64   `json:"total_users"`
	NewUsers       int64   `json:"new_users"`
	GrowthRate     float64 `json:"growth_rate"`
	MonthlyGrowth  float64 `json:"monthly_growth"`
	ChurnRate      float64 `json:"churn_rate"`
	NetGrowth      float64 `json:"net_growth"`
}

// UserRetentionResponse represents user retention metrics
type UserRetentionResponse struct {
	CohortDate     string  `json:"cohort_date"`
	Day1Retention  float64 `json:"day_1_retention"`
	Day7Retention  float64 `json:"day_7_retention"`
	Day30Retention float64 `json:"day_30_retention"`
	RetentionTrend string  `json:"retention_trend"`
	CohortSize     int64   `json:"cohort_size"`
}

// UserChurnResponse represents user churn metrics
type UserChurnResponse struct {
	Days            int     `json:"days"`
	ChurnedUsers    int64   `json:"churned_users"`
	ChurnRate       float64 `json:"churn_rate"`
	AtRiskUsers     int64   `json:"at_risk_users"`
	MainChurnReason string  `json:"main_churn_reason"`
	RetentionScore  float64 `json:"retention_score"`
}

// Performance Analytics DTOs

// RequestMetricsResponse represents request performance metrics
type RequestMetricsResponse struct {
	Period              string  `json:"period"`
	TotalRequests       int64   `json:"total_requests"`
	AvgResponseTime     int     `json:"avg_response_time"`
	P50ResponseTime     int     `json:"p50_response_time"`
	P95ResponseTime     int     `json:"p95_response_time"`
	P99ResponseTime     int     `json:"p99_response_time"`
	RequestsPerSecond   int     `json:"requests_per_second"`
	SuccessRate         float64 `json:"success_rate"`
}

// SystemMetricsResponse represents system metrics
type SystemMetricsResponse struct {
	CPUUsage      float64 `json:"cpu_usage"`
	MemoryUsage   float64 `json:"memory_usage"`
	DiskUsage     float64 `json:"disk_usage"`
	NetworkLatency int     `json:"network_latency"`
	UptimeHours   int64   `json:"uptime_hours"`
	ErrorCount    int     `json:"error_count"`
	WarningCount  int     `json:"warning_count"`
}

// DatabaseMetricsResponse represents database metrics
type DatabaseMetricsResponse struct {
	ConnectionsActive  int     `json:"connections_active"`
	ConnectionsIdle    int     `json:"connections_idle"`
	ConnectionsMax     int     `json:"connections_max"`
	AvgQueryTime       int     `json:"avg_query_time"`
	QueriesPerSecond   int     `json:"queries_per_second"`
	CacheHitRate       float64 `json:"cache_hit_rate"`
	SlowQueries        int     `json:"slow_queries"`
}

// CacheMetricsResponse represents cache metrics
type CacheMetricsResponse struct {
	CacheSize        int64   `json:"cache_size"`
	CacheHitRate     float64 `json:"cache_hit_rate"`
	CacheMissRate    float64 `json:"cache_miss_rate"`
	EvictionRate     float64 `json:"eviction_rate"`
	AvgGetTime       int     `json:"avg_get_time"`
	AvgSetTime       int     `json:"avg_set_time"`
	MemoryUsage      float64 `json:"memory_usage"`
}

// Error Analytics DTOs

// ErrorMetricsResponse represents error metrics
type ErrorMetricsResponse struct {
	Period               string `json:"period"`
	TotalErrors          int64  `json:"total_errors"`
	ErrorRate            float64 `json:"error_rate"`
	UniqueErrors         int    `json:"unique_errors"`
	AvgResolutionTime    int    `json:"avg_resolution_time"`
	CriticalErrors       int    `json:"critical_errors"`
	Warnings             int    `json:"warnings"`
}

// ErrorTrendResponse represents error trends
type ErrorTrendResponse struct {
	StartDate           string  `json:"start_date"`
	EndDate             string  `json:"end_date"`
	Trend               string  `json:"trend"`
	ErrorCountChange    float64 `json:"error_count_change"`
	CriticalErrorTrend  string  `json:"critical_error_trend"`
	RecoveryImprovement float64 `json:"recovery_improvement"`
}

// TopErrorResponse represents top errors
type TopErrorResponse struct {
	Error       string    `json:"error"`
	Count       int64     `json:"count"`
	Percentage  float64   `json:"percentage"`
	Severity    string    `json:"severity"`
	LastOccurred time.Time `json:"last_occurred"`
}

// CriticalErrorResponse represents critical error
type CriticalErrorResponse struct {
	ErrorID string `json:"error_id"`
	Message string `json:"message"`
	Severity string `json:"severity"`
	Count   int64  `json:"count"`
	Status  string `json:"status"`
	Impact  string `json:"impact"`
}

// SessionAnalysisResponse represents session analysis metrics
type SessionAnalysisResponse struct {
	TotalSessions      int64   `json:"total_sessions"`
	AvgSessionDuration int     `json:"avg_session_duration"`
	MaxSessionDuration int     `json:"max_session_duration"`
	MinSessionDuration int     `json:"min_session_duration"`
	BounceRate         float64 `json:"bounce_rate"`
	ActiveUsers        int64   `json:"active_users"`
	EngagementScore    float64 `json:"engagement_score"`
}
