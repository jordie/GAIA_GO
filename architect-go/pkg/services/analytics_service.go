package services

import (
	"context"
	"time"

	"architect-go/pkg/dto"
)

// EventAnalyticsService provides event analytics functionality
type EventAnalyticsService interface {
	// GetTimeline returns event count timeline
	GetTimeline(ctx context.Context, startDate, endDate time.Time, granularity string) ([]dto.EventTimelineResponse, error)

	// GetByType returns events grouped by type
	GetByType(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)

	// GetByUser returns events grouped by user
	GetByUser(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)

	// GetByProject returns events grouped by project
	GetByProject(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)

	// GetRetention analyzes user retention metrics
	GetRetention(ctx context.Context, cohortDate time.Time) ([]dto.EventRetentionResponse, error)

	// GetCohortAnalysis performs cohort analysis
	GetCohortAnalysis(ctx context.Context, startDate, endDate time.Time) ([][]dto.CohortAnalysisResponse, error)

	// GetFunnel analyzes user funnel metrics
	GetFunnel(ctx context.Context, funnelName string, startDate, endDate time.Time) (*dto.EventFunnelResponse, error)

	// GetCorrelation finds correlated events
	GetCorrelation(ctx context.Context, startDate, endDate time.Time, eventType string) ([]dto.EventCorrelationResponse, error)

	// GetAnomalies detects anomalies in event data
	GetAnomalies(ctx context.Context, startDate, endDate time.Time, metric string) ([]dto.AnomalyResponse, error)

	// GetForecast generates time series forecast
	GetForecast(ctx context.Context, startDate, endDate time.Time, periods int) ([]dto.ForecastResponse, error)

	// GetTopActions returns top user actions
	GetTopActions(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)

	// GetUserJourney analyzes user journey paths
	GetUserJourney(ctx context.Context, userID string, startDate, endDate time.Time) ([]dto.EventTimelineResponse, error)

	// GetSessionAnalysis analyzes session metrics
	GetSessionAnalysis(ctx context.Context, startDate, endDate time.Time) (*dto.EngagementMetricsResponse, error)

	// Export exports event analytics data
	Export(ctx context.Context, req *dto.AnalyticsExportRequest) (*dto.AnalyticsExportResponse, error)
}

// ErrorAnalyticsService provides error analytics functionality
type ErrorAnalyticsService interface {
	// GetTimeline returns error count timeline
	GetTimeline(ctx context.Context, startDate, endDate time.Time, granularity string) ([]dto.ErrorTimelineResponse, error)

	// GetByType returns errors grouped by type
	GetByType(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)

	// GetBySeverity returns errors grouped by severity
	GetBySeverity(ctx context.Context, startDate, endDate time.Time) ([]dto.ErrorBySeverityResponse, error)

	// GetBySource returns errors grouped by source
	GetBySource(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)

	// GetImpact analyzes error impact on business
	GetImpact(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.ErrorImpactResponse, error)

	// GetDistribution returns error distribution
	GetDistribution(ctx context.Context, startDate, endDate time.Time) ([]dto.ErrorBySeverityResponse, error)

	// GetRootCauses identifies root causes of errors
	GetRootCauses(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.RootCauseResponse, error)

	// GetAffectedUsers returns users affected by errors
	GetAffectedUsers(ctx context.Context, startDate, endDate time.Time, errorType string) (int64, error)

	// GetMTBF returns mean time between failures
	GetMTBF(ctx context.Context, startDate, endDate time.Time) (*dto.MTBFResponse, error)

	// GetMTTR returns mean time to resolution
	GetMTTR(ctx context.Context, startDate, endDate time.Time) ([]dto.MTTRResponse, error)

	// GetTrends analyzes error trends
	GetTrends(ctx context.Context, startDate, endDate time.Time, periods int) ([]dto.ErrorTimelineResponse, error)

	// GetClustering performs error clustering
	GetClustering(ctx context.Context, startDate, endDate time.Time) ([]dto.ErrorClusterResponse, error)

	// PredictErrors predicts future error rates
	PredictErrors(ctx context.Context, startDate, endDate time.Time, periods int) ([]dto.ForecastResponse, error)

	// GetHotspots identifies error hotspots
	GetHotspots(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.BottleneckResponse, error)

	// Export exports error analytics data
	Export(ctx context.Context, req *dto.AnalyticsExportRequest) (*dto.AnalyticsExportResponse, error)
}

// PerformanceAnalyticsService provides performance analytics functionality
type PerformanceAnalyticsService interface {
	// GetLatency returns latency metrics
	GetLatency(ctx context.Context, startDate, endDate time.Time, granularity string) ([]dto.LatencyAnalyticsResponse, error)

	// GetThroughput returns request throughput metrics
	GetThroughput(ctx context.Context, startDate, endDate time.Time, granularity string) ([]dto.ThroughputAnalyticsResponse, error)

	// GetSaturation returns resource saturation metrics
	GetSaturation(ctx context.Context, startDate, endDate time.Time, resourceType string) ([]dto.SaturationResponse, error)

	// GetAvailability returns availability metrics
	GetAvailability(ctx context.Context, startDate, endDate time.Time) (*dto.AvailabilityResponse, error)

	// GetSLOTracking returns SLO compliance tracking
	GetSLOTracking(ctx context.Context, startDate, endDate time.Time, sloName string) (*dto.SLOTrackingResponse, error)

	// GetTrending returns performance trending
	GetTrending(ctx context.Context, startDate, endDate time.Time, metric string) ([]dto.LatencyAnalyticsResponse, error)

	// GetByEndpoint returns performance metrics by endpoint
	GetByEndpoint(ctx context.Context, startDate, endDate time.Time) ([]dto.EventsByTypeResponse, error)

	// GetByUser returns performance metrics by user
	GetByUser(ctx context.Context, startDate, endDate time.Time, userID string) (*dto.LatencyAnalyticsResponse, error)

	// GetByRegion returns performance metrics by region
	GetByRegion(ctx context.Context, startDate, endDate time.Time) ([]dto.EventsByTypeResponse, error)

	// GetCapacityPlanning returns capacity planning data
	GetCapacityPlanning(ctx context.Context, startDate, endDate time.Time, periods int) ([]dto.ForecastResponse, error)

	// PredictCapacity predicts capacity needs
	PredictCapacity(ctx context.Context, growthRate float64, periods int) ([]dto.ForecastResponse, error)

	// DetectDegradation detects performance degradation
	DetectDegradation(ctx context.Context, startDate, endDate time.Time) ([]dto.AnomalyResponse, error)

	// GetBottlenecks identifies performance bottlenecks
	GetBottlenecks(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.BottleneckResponse, error)

	// GetOptimizationSuggestions provides optimization recommendations
	GetOptimizationSuggestions(ctx context.Context, startDate, endDate time.Time) ([]dto.BottleneckResponse, error)

	// ComparePerformance compares performance across periods
	ComparePerformance(ctx context.Context, period1Start, period1End, period2Start, period2End time.Time) (map[string]interface{}, error)

	// Export exports performance analytics data
	Export(ctx context.Context, req *dto.AnalyticsExportRequest) (*dto.AnalyticsExportResponse, error)
}

// UserAnalyticsService provides user analytics functionality
type UserAnalyticsService interface {
	// GetActivity returns user activity timeline
	GetActivity(ctx context.Context, startDate, endDate time.Time, granularity string) ([]dto.UserActivityResponse, error)

	// GetEngagement returns user engagement metrics
	GetEngagement(ctx context.Context, startDate, endDate time.Time) (*dto.EngagementMetricsResponse, error)

	// GetFeatureAdoption returns feature adoption metrics
	GetFeatureAdoption(ctx context.Context, startDate, endDate time.Time, featureName string) (*dto.FeatureAdoptionResponse, error)

	// GetLifetimeValue returns user lifetime value
	GetLifetimeValue(ctx context.Context, userID string) (*dto.UserLifetimeValueResponse, error)

	// PredictChurn predicts user churn risk
	PredictChurn(ctx context.Context, userID string) (*dto.ChurnPredictionResponse, error)

	// GetSegmentation returns user segmentation analysis
	GetSegmentation(ctx context.Context, startDate, endDate time.Time) ([]dto.UserSegmentResponse, error)

	// GetPersonas returns user personas
	GetPersonas(ctx context.Context) ([]dto.UserPersonaResponse, error)

	// GetBehaviorPatterns returns user behavior patterns
	GetBehaviorPatterns(ctx context.Context, startDate, endDate time.Time) ([]map[string]interface{}, error)

	// GetLoyaltyScore returns user loyalty score
	GetLoyaltyScore(ctx context.Context, userID string) (float64, error)

	// GetSatisfactionMetrics returns user satisfaction metrics
	GetSatisfactionMetrics(ctx context.Context, startDate, endDate time.Time) (map[string]interface{}, error)

	// CalculateNPS calculates Net Promoter Score
	CalculateNPS(ctx context.Context, startDate, endDate time.Time) (*dto.NPSResponse, error)

	// GetDemographics returns user demographic information
	GetDemographics(ctx context.Context, startDate, endDate time.Time) ([]dto.UserSegmentResponse, error)

	// GetGeographyAnalysis returns geographic analysis
	GetGeographyAnalysis(ctx context.Context, startDate, endDate time.Time) ([]dto.UserSegmentResponse, error)

	// AnalyzeDeviceUsage analyzes device and browser usage
	AnalyzeDeviceUsage(ctx context.Context, startDate, endDate time.Time) ([]dto.UserSegmentResponse, error)

	// Export exports user analytics data
	Export(ctx context.Context, req *dto.AnalyticsExportRequest) (*dto.AnalyticsExportResponse, error)
}
