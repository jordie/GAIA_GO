package services

import (
	"context"
	"time"
)

// PresenceAnalyticsService defines analytics operations for presence data
type PresenceAnalyticsService interface {
	// GetPresenceTrends returns presence trends over a period
	GetPresenceTrends(ctx context.Context, period string, interval string) ([]interface{}, map[string]interface{}, error)

	// GetUserEngagementMetrics returns engagement metrics for users
	GetUserEngagementMetrics(ctx context.Context, userID string, days int) (map[string]interface{}, error)

	// GetPresenceHeatmap returns a 24x7 activity heatmap
	GetPresenceHeatmap(ctx context.Context, days int) (map[string]interface{}, error)
}

// ActivityAnalyticsService defines analytics operations for activity data
type ActivityAnalyticsService interface {
	// GetActivityTrends returns activity trends over a period
	GetActivityTrends(ctx context.Context, period string, action string) ([]interface{}, map[string]interface{}, error)

	// GetTopUsers returns the top users by activity count
	GetTopUsers(ctx context.Context, days int, limit int) ([]interface{}, error)

	// GetActivityStats returns aggregate activity statistics
	GetActivityStats(ctx context.Context, userID string) (map[string]int64, error)
}

// TrendData represents a single trend data point
type TrendData struct {
	Timestamp            time.Time
	OnlineCount          int
	OnlinePercentage     float64
	PeakTime             string
	AvgSessionDuration   int
}

// EngagementMetrics represents user engagement metrics
type EngagementMetrics struct {
	ActiveUsers          int
	TotalUsers           int
	EngagementRate       float64
	AvgSessionDuration   int
	SessionCount         int
	ActivityHeatmap      map[string][]int
}

// ActivityTrendData represents activity trend data
type ActivityTrendData struct {
	Timestamp   time.Time
	Action      string
	Count       int
	UniqueUsers int
}

// UserActivityStats represents per-user activity statistics
type UserActivityStats struct {
	UserID        string
	Username      string
	ActionCount   int
	UniqueActions int
	LastActivity  time.Time
}
