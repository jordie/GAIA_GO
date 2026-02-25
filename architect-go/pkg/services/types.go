package services

import (
	"context"
	"time"

	"architect-go/pkg/dto"
)

// EventAnalyticsService defines the event analytics service interface
type EventAnalyticsService interface {
	GetTimeline(ctx context.Context, startDate, endDate time.Time, granularity string) ([]dto.EventTimelineResponse, error)
	GetByType(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)
	GetByUser(ctx context.Context, userID string, startDate, endDate time.Time) ([]dto.EventsByTypeResponse, error)
	GetByProject(ctx context.Context, startDate, endDate time.Time, limit int) ([]dto.EventsByTypeResponse, error)
	GetRetention(ctx context.Context, cohortDate time.Time) ([]dto.EventRetentionResponse, error)
	GetCohortAnalysis(ctx context.Context, startDate, endDate time.Time) ([][]dto.CohortAnalysisResponse, error)
	GetFunnel(ctx context.Context, funnelName string, startDate, endDate time.Time) (*dto.EventFunnelResponse, error)
	GetCorrelation(ctx context.Context, startDate, endDate time.Time) ([]dto.EventCorrelationResponse, error)
	GetAnomalies(ctx context.Context, startDate, endDate time.Time, threshold string) ([]dto.AnomalyResponse, error)
	GetForecast(ctx context.Context, days int) ([]dto.ForecastResponse, error)
	GetTopActions(ctx context.Context, limit int) ([]dto.EventFunnelResponse, error)
	GetUserJourney(ctx context.Context, userID string, startDate, endDate time.Time) ([]dto.EventsByTypeResponse, error)
	GetSessionAnalysis(ctx context.Context, startDate, endDate time.Time) (dto.SessionAnalysisResponse, error)
}

// PresenceAnalyticsService defines the presence analytics service interface
type PresenceAnalyticsService interface {
	// Empty interface for now - concrete implementations will satisfy it
}

// ActivityAnalyticsService defines the activity analytics service interface
type ActivityAnalyticsService interface {
	// Empty interface for now - concrete implementations will satisfy it
}

// Note: UserAnalyticsService is defined in user_analytics_service_impl.go
// Note: ErrorAnalyticsService is defined in error_analytics_service_impl.go

// RealTimeEventService defines the real-time event service interface
type RealTimeEventService interface {
	// Empty interface for now - concrete implementations will satisfy it
}

// Note: PerformanceAnalyticsService is defined in performance_analytics_service_impl.go
