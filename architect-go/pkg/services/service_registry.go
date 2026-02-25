package services

import (
	"architect-go/pkg/cache"
	"architect-go/pkg/repository"
)

// Registry holds all service instances
type Registry struct {
	// Phase 3.1 Services
	ProjectService   ProjectService
	TaskService      TaskService
	UserService      UserService
	DashboardService DashboardService
	WorkerService    WorkerService

	// Phase 3.2 Services
	EventLogService          EventLogService
	ErrorLogService          ErrorLogService
	NotificationService      NotificationService
	IntegrationService       IntegrationService
	WebhookService           WebhookService
	SessionTrackingService   SessionTrackingService
	AuditLogService          AuditLogService
	RealTimeEventService     RealTimeEventService
	IntegrationHealthService IntegrationHealthService

	// Phase 3.3 Services - Analytics & Reporting
	EventAnalyticsService       EventAnalyticsService
	ErrorAnalyticsService       ErrorAnalyticsService
	PerformanceAnalyticsService PerformanceAnalyticsService
	UserAnalyticsService        UserAnalyticsService

	// Phase 4.3 Services - Presence & Activity Tracking
	PresenceService PresenceService
	ActivityService ActivityService
}

// NewRegistry creates a new service registry
func NewRegistry(repos *repository.Registry) *Registry {
	return &Registry{
		// Phase 3.1 Services - instantiate with basic repositories
		ProjectService:   NewProjectService(repos.ProjectRepository),
		TaskService:      NewTaskService(repos.TaskRepository),
		UserService:      NewUserService(repos.UserRepository),
		DashboardService: NewDashboardService(repos),
		WorkerService:    NewWorkerService(repos.WorkerRepository),

		// Phase 3.2 Services - instantiate with extended repositories
		EventLogService:          NewEventLogService(repos.EventLogRepository),
		ErrorLogService:          NewErrorLogService(repos.ErrorLogRepository),
		NotificationService:      NewNotificationService(repos.NotificationRepository),
		IntegrationService:       NewIntegrationService(repos.IntegrationRepository),
		WebhookService:           NewWebhookService(repos.WebhookRepository),
		SessionTrackingService:   NewSessionTrackingService(repos.SessionRepository),
		AuditLogService:          NewAuditLogService(repos.AuditLogRepository),
		RealTimeEventService:     NewRealTimeEventService(repos.RealTimeRepository),
		IntegrationHealthService: NewIntegrationHealthService(repos.IntegrationHealthRepository),

		// Phase 3.3 Services - Analytics & Reporting - instantiate with analytics repository
		EventAnalyticsService:       NewEventAnalyticsService(repos.AnalyticsRepository),
		ErrorAnalyticsService:       NewErrorAnalyticsService(repos.AnalyticsRepository),
		PerformanceAnalyticsService: NewPerformanceAnalyticsService(repos.AnalyticsRepository),
		UserAnalyticsService:        NewUserAnalyticsService(repos.AnalyticsRepository),

		// Phase 4.3 Services - Presence & Activity
		PresenceService: NewPresenceService(repos.PresenceRepository, repos.ActivityRepository),
		ActivityService: NewActivityService(repos.ActivityRepository),
	}
}

// NewRegistryWithCache creates a new service registry with cache support
func NewRegistryWithCache(repos *repository.Registry, cm *cache.CacheManager) *Registry {
	return &Registry{
		// Phase 3.1 Services - with cache support
		ProjectService:   NewProjectServiceWithCache(repos.ProjectRepository, cm),
		TaskService:      NewTaskServiceWithCache(repos.TaskRepository, cm),
		UserService:      NewUserServiceWithCache(repos.UserRepository, cm),
		DashboardService: NewDashboardService(repos),
		WorkerService:    NewWorkerService(repos.WorkerRepository),

		// Phase 3.2 Services - instantiate with extended repositories (unchanged)
		EventLogService:          NewEventLogService(repos.EventLogRepository),
		ErrorLogService:          NewErrorLogService(repos.ErrorLogRepository),
		NotificationService:      NewNotificationService(repos.NotificationRepository),
		IntegrationService:       NewIntegrationService(repos.IntegrationRepository),
		WebhookService:           NewWebhookService(repos.WebhookRepository),
		SessionTrackingService:   NewSessionTrackingService(repos.SessionRepository),
		AuditLogService:          NewAuditLogService(repos.AuditLogRepository),
		RealTimeEventService:     NewRealTimeEventService(repos.RealTimeRepository),
		IntegrationHealthService: NewIntegrationHealthService(repos.IntegrationHealthRepository),

		// Phase 3.3 Services - Analytics & Reporting (unchanged)
		EventAnalyticsService:       NewEventAnalyticsService(repos.AnalyticsRepository),
		ErrorAnalyticsService:       NewErrorAnalyticsService(repos.AnalyticsRepository),
		PerformanceAnalyticsService: NewPerformanceAnalyticsService(repos.AnalyticsRepository),
		UserAnalyticsService:        NewUserAnalyticsService(repos.AnalyticsRepository),

		// Phase 4.3 Services - Presence & Activity with cache (dispatcher will be added separately)
		PresenceService: NewPresenceService(repos.PresenceRepository, repos.ActivityRepository),
		ActivityService: NewActivityService(repos.ActivityRepository),
	}
}

// NewRegistryWithCacheAndHub creates a new service registry with cache support and hub-aware real-time service
func NewRegistryWithCacheAndHub(repos *repository.Registry, cm *cache.CacheManager, hub realtimePushHub) *Registry {
	return &Registry{
		// Phase 3.1 Services - with cache support
		ProjectService:   NewProjectServiceWithCache(repos.ProjectRepository, cm),
		TaskService:      NewTaskServiceWithCache(repos.TaskRepository, cm),
		UserService:      NewUserServiceWithCache(repos.UserRepository, cm),
		DashboardService: NewDashboardService(repos),
		WorkerService:    NewWorkerService(repos.WorkerRepository),

		// Phase 3.2 Services - instantiate with extended repositories (unchanged)
		EventLogService:          NewEventLogService(repos.EventLogRepository),
		ErrorLogService:          NewErrorLogService(repos.ErrorLogRepository),
		NotificationService:      NewNotificationService(repos.NotificationRepository),
		IntegrationService:       NewIntegrationService(repos.IntegrationRepository),
		WebhookService:           NewWebhookService(repos.WebhookRepository),
		SessionTrackingService:   NewSessionTrackingService(repos.SessionRepository),
		AuditLogService:          NewAuditLogService(repos.AuditLogRepository),
		RealTimeEventService:     NewRealTimeEventServiceWithHub(repos.RealTimeRepository, hub),
		IntegrationHealthService: NewIntegrationHealthService(repos.IntegrationHealthRepository),

		// Phase 3.3 Services - Analytics & Reporting (unchanged)
		EventAnalyticsService:       NewEventAnalyticsService(repos.AnalyticsRepository),
		ErrorAnalyticsService:       NewErrorAnalyticsService(repos.AnalyticsRepository),
		PerformanceAnalyticsService: NewPerformanceAnalyticsService(repos.AnalyticsRepository),
		UserAnalyticsService:        NewUserAnalyticsService(repos.AnalyticsRepository),

		// Phase 4.3 Services - Presence & Activity with cache (dispatcher wired separately in server)
		PresenceService: NewPresenceService(repos.PresenceRepository, repos.ActivityRepository),
		ActivityService: NewActivityService(repos.ActivityRepository),
	}
}
