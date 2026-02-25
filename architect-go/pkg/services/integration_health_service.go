package services

import (
	"context"
)

// IntegrationHealthService defines integration monitoring and health business logic
type IntegrationHealthService interface {
	// GetOverallHealth retrieves overall system health status
	GetOverallHealth(ctx context.Context) (*HealthCheckResponse, error)

	// CheckIntegrationHealth checks health of specific integration
	CheckIntegrationHealth(ctx context.Context, integrationID string) (*HealthCheckResponse, error)

	// CheckHealthByType checks health of all integrations of specific type
	CheckHealthByType(ctx context.Context, integrationType string) (map[string]interface{}, error)

	// GetCriticalIssues retrieves critical health issues
	GetCriticalIssues(ctx context.Context) ([]map[string]interface{}, error)

	// GetWarnings retrieves health warnings
	GetWarnings(ctx context.Context) ([]map[string]interface{}, error)

	// RunFullHealthCheck runs comprehensive health check on all integrations
	RunFullHealthCheck(ctx context.Context) (map[string]interface{}, error)

	// RunIntegrationHealthCheck runs full check on specific integration
	RunIntegrationHealthCheck(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetDiagnostics retrieves diagnostic information
	GetDiagnostics(ctx context.Context, integrationID string) (*DiagnosticsResponse, error)

	// GetMetrics retrieves performance metrics
	GetMetrics(ctx context.Context, integrationID string) (*MetricsResponse, error)

	// GetComponentMetrics retrieves metrics for specific component
	GetComponentMetrics(ctx context.Context, integrationID string, component string) (map[string]interface{}, error)

	// GetDependencyStatus checks if integration dependencies are healthy
	GetDependencyStatus(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// VerifyDependencies verifies all dependencies for integration
	VerifyDependencies(ctx context.Context, integrationID string) (bool, error)

	// GetUptimeStats retrieves uptime statistics
	GetUptimeStats(ctx context.Context, integrationID string, period string) (*UptimeResponse, error)

	// GetIncidentHistory retrieves incident history
	GetIncidentHistory(ctx context.Context, integrationID string, limit, offset int) ([]IncidentResponse, int64, error)

	// ReportIncident reports new incident
	ReportIncident(ctx context.Context, integrationID string, severity string, description string) (string, error)

	// ResolveIncident marks incident as resolved
	ResolveIncident(ctx context.Context, incidentID string) error

	// UpdateIncidentStatus updates incident status
	UpdateIncidentStatus(ctx context.Context, incidentID string, status string) error

	// GetActiveIncidents retrieves currently active incidents
	GetActiveIncidents(ctx context.Context) ([]IncidentResponse, error)

	// CreateHealthAlert creates health alert rule
	CreateHealthAlert(ctx context.Context, req *HealthAlertRequest) (string, error)

	// UpdateHealthAlert updates health alert rule
	UpdateHealthAlert(ctx context.Context, alertID string, req *HealthAlertRequest) error

	// DeleteHealthAlert deletes health alert
	DeleteHealthAlert(ctx context.Context, alertID string) error

	// GetActiveAlerts retrieves active health alerts
	GetActiveAlerts(ctx context.Context) ([]map[string]interface{}, error)

	// GetAlertHistory retrieves alert history
	GetAlertHistory(ctx context.Context, limit, offset int) ([]map[string]interface{}, int64, error)

	// GetResponseTimeAnalytics retrieves response time data
	GetResponseTimeAnalytics(ctx context.Context, integrationID string, timeframe string) (map[string]interface{}, error)

	// GetErrorRateAnalytics retrieves error rate analytics
	GetErrorRateAnalytics(ctx context.Context, integrationID string, timeframe string) (map[string]interface{}, error)

	// GetThroughputAnalytics retrieves throughput metrics
	GetThroughputAnalytics(ctx context.Context, integrationID string, timeframe string) (map[string]interface{}, error)

	// GetLatencyPercentiles retrieves latency percentiles (p50, p95, p99)
	GetLatencyPercentiles(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetSLAStatus retrieves SLA compliance status
	GetSLAStatus(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetSLAViolations retrieves SLA violations
	GetSLAViolations(ctx context.Context, integrationID string, limit, offset int) ([]map[string]interface{}, int64, error)

	// GetHealthTrend retrieves health trend over time
	GetHealthTrend(ctx context.Context, integrationID string, timeframe string) (map[string]interface{}, error)

	// PredictHealthIssue predicts potential health issues
	PredictHealthIssue(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetRecommendations retrieves health recommendations
	GetRecommendations(ctx context.Context, integrationID string) ([]string, error)

	// ApplyRecommendation applies recommended action
	ApplyRecommendation(ctx context.Context, integrationID string, recommendation string) error

	// GetAutoRemediationStatus retrieves auto-remediation status
	GetAutoRemediationStatus(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// EnableAutoRemediation enables auto-remediation
	EnableAutoRemediation(ctx context.Context, integrationID string) error

	// DisableAutoRemediation disables auto-remediation
	DisableAutoRemediation(ctx context.Context, integrationID string) error

	// GetRemediationHistory retrieves remediation actions history
	GetRemediationHistory(ctx context.Context, integrationID string, limit, offset int) ([]map[string]interface{}, int64, error)

	// GetEndpointStatus retrieves status of integration endpoints
	GetEndpointStatus(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// CheckEndpointHealth checks individual endpoint
	CheckEndpointHealth(ctx context.Context, integrationID string, endpoint string) (map[string]interface{}, error)

	// GetDatabaseHealth checks database connectivity
	GetDatabaseHealth(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetCacheHealth checks cache connectivity
	GetCacheHealth(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetNetworkHealth checks network connectivity
	GetNetworkHealth(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetResourceUtilization retrieves resource usage metrics
	GetResourceUtilization(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetConnectionPoolHealth checks connection pool health
	GetConnectionPoolHealth(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetQueueHealth checks queue health
	GetQueueHealth(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetRateLimitStatus retrieves rate limit metrics
	GetRateLimitStatus(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetCapacityMetrics retrieves capacity information
	GetCapacityMetrics(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// ForecastCapacity forecasts capacity needs
	ForecastCapacity(ctx context.Context, integrationID string, days int) (map[string]interface{}, error)

	// GetComplianceStatus checks compliance status
	GetComplianceStatus(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetSecurityStatus checks security status
	GetSecurityStatus(ctx context.Context, integrationID string) (map[string]interface{}, error)

	// GetAuditReport generates audit report
	GetAuditReport(ctx context.Context, integrationID string, timeframe string) (map[string]interface{}, error)
}
