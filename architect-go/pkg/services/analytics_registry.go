package services

import (
	"architect-go/pkg/cache"
	"architect-go/pkg/metrics"
	"architect-go/pkg/repository"
)

// AnalyticsRegistry holds all analytics service instances
type AnalyticsRegistry struct {
	// Event Analytics
	EventAnalyticsService       *EventAnalyticsServiceImpl
	PresenceAnalyticsService    *PresenceAnalyticsServiceImpl
	ActivityAnalyticsService    *ActivityAnalyticsServiceImpl
	PerformanceAnalyticsService *PerformanceAnalyticsServiceImpl
	UserAnalyticsService        *UserAnalyticsServiceImpl
	ErrorAnalyticsService       *ErrorAnalyticsServiceImpl

	// Real-time Services
	RealTimeEventService *RealTimeEventServiceImpl

	// Cache Management
	CacheManager *cache.CacheManager

	// Query Builder
	QueryBuilder *repository.QueryBuilder
}

// NewAnalyticsRegistry creates a new analytics service registry
func NewAnalyticsRegistry(repos *repository.Registry) *AnalyticsRegistry {
	cacheManager := cache.NewCacheManager()
	metricsInstance := metrics.NewMetrics()

	return &AnalyticsRegistry{
		// Event Analytics
		EventAnalyticsService:       &EventAnalyticsServiceImpl{repo: repos.EventRepository},
		PresenceAnalyticsService:    &PresenceAnalyticsServiceImpl{repo: repos.PresenceRepository},
		ActivityAnalyticsService:    &ActivityAnalyticsServiceImpl{repo: repos.ActivityRepository},
		PerformanceAnalyticsService: &PerformanceAnalyticsServiceImpl{metrics: metricsInstance},
		UserAnalyticsService:        &UserAnalyticsServiceImpl{repo: repos.UserRepository},
		ErrorAnalyticsService:       &ErrorAnalyticsServiceImpl{repo: repos.ErrorRepository},

		// Real-time Services
		RealTimeEventService: &RealTimeEventServiceImpl{repo: repos.RealTimeRepository},

		// Cache Management
		CacheManager: cacheManager,

		// Query Builder
		QueryBuilder: repository.NewQueryBuilder(),
	}
}

// NewAnalyticsRegistryWithCache creates analytics registry with caching enabled
func NewAnalyticsRegistryWithCache(repos *repository.Registry, cm *cache.CacheManager) *AnalyticsRegistry {
	metricsInstance := metrics.NewMetrics()

	return &AnalyticsRegistry{
		// Event Analytics with cache-aware implementations (to be enhanced)
		EventAnalyticsService:       &EventAnalyticsServiceImpl{repo: repos.EventRepository},
		PresenceAnalyticsService:    &PresenceAnalyticsServiceImpl{repo: repos.PresenceRepository},
		ActivityAnalyticsService:    &ActivityAnalyticsServiceImpl{repo: repos.ActivityRepository},
		PerformanceAnalyticsService: &PerformanceAnalyticsServiceImpl{metrics: metricsInstance},
		UserAnalyticsService:        &UserAnalyticsServiceImpl{repo: repos.UserRepository},
		ErrorAnalyticsService:       &ErrorAnalyticsServiceImpl{repo: repos.ErrorRepository},

		// Real-time Services
		RealTimeEventService: &RealTimeEventServiceImpl{repo: repos.RealTimeRepository},

		// Cache Management
		CacheManager: cm,

		// Query Builder
		QueryBuilder: repository.NewQueryBuilder(),
	}
}

// GetService retrieves a service by name
func (ar *AnalyticsRegistry) GetService(serviceName string) interface{} {
	switch serviceName {
	case "event_analytics":
		return ar.EventAnalyticsService
	case "presence_analytics":
		return ar.PresenceAnalyticsService
	case "activity_analytics":
		return ar.ActivityAnalyticsService
	case "performance_analytics":
		return ar.PerformanceAnalyticsService
	case "user_analytics":
		return ar.UserAnalyticsService
	case "error_analytics":
		return ar.ErrorAnalyticsService
	case "realtime_event":
		return ar.RealTimeEventService
	default:
		return nil
	}
}
