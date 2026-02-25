package repository

// Registry coordinates all repository instances
type Registry struct {
<<<<<<< HEAD
	ProjectRepository          ProjectRepository
	TaskRepository             TaskRepository
	UserRepository             UserRepository
	WorkerRepository           WorkerRepository
	WorkerQueueRepository      WorkerQueueRepository
	SessionRepository          SessionRepository
	EventLogRepository         EventLogRepository
	ErrorLogRepository         ErrorLogRepository
	NotificationRepository     NotificationRepository
	IntegrationRepository      IntegrationRepository
	WebhookRepository          WebhookRepository
	AuditLogRepository         AuditLogRepository
	RealTimeRepository         RealTimeRepository
	IntegrationHealthRepository IntegrationHealthRepository
	AnalyticsRepository        AnalyticsRepository
	PresenceRepository         PresenceRepository
	ActivityRepository         ActivityRepository
=======
	EventRepository              EventRepository
	PresenceRepository           PresenceRepository
	ActivityRepository           ActivityRepository
	UserRepository               UserRepository
	ErrorRepository              ErrorRepository
	MetricsRepository            MetricsRepository
	RealTimeRepository           RealTimeRepository
	ProjectRepository            ProjectRepository
	TaskRepository               TaskRepository
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
}

// NewRegistry creates a new repository registry
func NewRegistry() *Registry {
	return &Registry{
<<<<<<< HEAD
		ProjectRepository:          NewProjectRepository(db),
		TaskRepository:             NewTaskRepository(db),
		UserRepository:             NewUserRepository(db),
		WorkerRepository:           NewWorkerRepository(db),
		WorkerQueueRepository:      NewWorkerQueueRepository(db),
		SessionRepository:          NewSessionRepository(db),
		EventLogRepository:         NewEventLogRepository(db),
		ErrorLogRepository:         NewErrorLogRepository(db),
		NotificationRepository:     NewNotificationRepository(db),
		IntegrationRepository:      NewIntegrationRepository(db),
		WebhookRepository:          NewWebhookRepository(db),
		AuditLogRepository:         NewAuditLogRepository(db),
		RealTimeRepository:         NewRealTimeRepository(db),
		IntegrationHealthRepository: NewIntegrationHealthRepository(db),
		AnalyticsRepository:        NewAnalyticsRepository(db),
		PresenceRepository:         NewPresenceRepository(db),
		ActivityRepository:         NewActivityRepository(db),
=======
		// Initialize repositories as needed
		// This will be populated by the application during setup
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
	}
}
