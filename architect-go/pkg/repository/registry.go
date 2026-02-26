package repository

import "database/sql"

// Registry coordinates all repository instances
type Registry struct {
	ProjectRepository           ProjectRepository
	TaskRepository              TaskRepository
	UserRepository              UserRepository
	WorkerRepository            WorkerRepository
	WorkerQueueRepository       WorkerQueueRepository
	SessionRepository           SessionRepository
	EventLogRepository          EventLogRepository
	ErrorLogRepository          ErrorLogRepository
	NotificationRepository      NotificationRepository
	IntegrationRepository       IntegrationRepository
	WebhookRepository           WebhookRepository
	AuditLogRepository          AuditLogRepository
	RealTimeRepository          RealTimeRepository
	IntegrationHealthRepository IntegrationHealthRepository
	AnalyticsRepository         AnalyticsRepository
	PresenceRepository          PresenceRepository
	ActivityRepository          ActivityRepository
	EventRepository             EventRepository
	ErrorRepository             ErrorRepository
	MetricsRepository           MetricsRepository
}

// NewRegistry creates a new repository registry
func NewRegistry(db *sql.DB) *Registry {
	return &Registry{
		ProjectRepository:           NewProjectRepository(db),
		TaskRepository:              NewTaskRepository(db),
		UserRepository:              NewUserRepository(db),
		WorkerRepository:            NewWorkerRepository(db),
		WorkerQueueRepository:       NewWorkerQueueRepository(db),
		SessionRepository:           NewSessionRepository(db),
		EventLogRepository:          NewEventLogRepository(db),
		ErrorLogRepository:          NewErrorLogRepository(db),
		NotificationRepository:      NewNotificationRepository(db),
		IntegrationRepository:       NewIntegrationRepository(db),
		WebhookRepository:           NewWebhookRepository(db),
		AuditLogRepository:          NewAuditLogRepository(db),
		RealTimeRepository:          NewRealTimeRepository(db),
		IntegrationHealthRepository: NewIntegrationHealthRepository(db),
		AnalyticsRepository:         NewAnalyticsRepository(db),
		PresenceRepository:          NewPresenceRepository(db),
		ActivityRepository:          NewActivityRepository(db),
		EventRepository:             NewEventRepository(db),
		ErrorRepository:             NewErrorRepository(db),
		MetricsRepository:           NewMetricsRepository(db),
	}
}
