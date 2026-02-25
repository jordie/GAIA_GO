package services

import (
	"time"
)

// ==================== EVENT LOG DTOs ====================

type CreateEventRequest struct {
	Type        string                 `json:"type"`
	Source      string                 `json:"source"`
	UserID      string                 `json:"user_id,omitempty"`
	ProjectID   string                 `json:"project_id,omitempty"`
	Description string                 `json:"description,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Tags        []string               `json:"tags,omitempty"`
}

type UpdateEventRequest struct {
	Description string                 `json:"description,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Status      string                 `json:"status,omitempty"`
}

type EventResponse struct {
	ID          string                 `json:"id"`
	Type        string                 `json:"type"`
	Source      string                 `json:"source"`
	UserID      string                 `json:"user_id,omitempty"`
	ProjectID   string                 `json:"project_id,omitempty"`
	Description string                 `json:"description,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Tags        []string               `json:"tags,omitempty"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
}

type ListEventsRequest struct {
	Type      string    `json:"type,omitempty"`
	Source    string    `json:"source,omitempty"`
	UserID    string    `json:"user_id,omitempty"`
	ProjectID string    `json:"project_id,omitempty"`
	StartDate time.Time `json:"start_date,omitempty"`
	EndDate   time.Time `json:"end_date,omitempty"`
	Tags      []string  `json:"tags,omitempty"`
	Limit     int       `json:"limit"`
	Offset    int       `json:"offset"`
}

type EventFilterRequest struct {
	Types      []string  `json:"types,omitempty"`
	Sources    []string  `json:"sources,omitempty"`
	UserIDs    []string  `json:"user_ids,omitempty"`
	ProjectIDs []string  `json:"project_ids,omitempty"`
	DateRange  struct {
		Start time.Time `json:"start"`
		End   time.Time `json:"end"`
	} `json:"date_range,omitempty"`
	SearchQuery string `json:"search_query,omitempty"`
}

type EventStatsResponse struct {
	TotalEvents   int64                     `json:"total_events"`
	EventsByType  map[string]int64          `json:"events_by_type"`
	EventsBySource map[string]int64         `json:"events_by_source"`
	EventsByUser  map[string]int64          `json:"events_by_user"`
	TimeRange     struct {
		Start time.Time `json:"start"`
		End   time.Time `json:"end"`
	} `json:"time_range"`
}

type EventTimelineResponse struct {
	Events []EventResponse `json:"events"`
	Total  int64           `json:"total"`
}

type EventExportResponse struct {
	Format   string `json:"format"`
	URL      string `json:"url"`
	ExpiresAt time.Time `json:"expires_at"`
	Size     int64  `json:"size"`
}

type EventTagRequest struct {
	Tag string `json:"tag"`
}

type EventSearchRequest struct {
	Query  string `json:"query"`
	Limit  int    `json:"limit"`
	Offset int    `json:"offset"`
}

type EventRelatedRequest struct {
	EventID string `json:"event_id"`
	Limit   int    `json:"limit"`
}

// ==================== ERROR LOG DTOs ====================

type LogErrorRequest struct {
	ErrorType   string                 `json:"error_type"`
	Message     string                 `json:"message"`
	Source      string                 `json:"source"`
	StackTrace  string                 `json:"stack_trace,omitempty"`
	Severity    string                 `json:"severity"`
	UserID      string                 `json:"user_id,omitempty"`
	ProjectID   string                 `json:"project_id,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Tags        []string               `json:"tags,omitempty"`
}

type ErrorResponse struct {
	ID        string                 `json:"id"`
	ErrorType string                 `json:"error_type"`
	Message   string                 `json:"message"`
	Source    string                 `json:"source"`
	Severity  string                 `json:"severity"`
	Status    string                 `json:"status"`
	UserID    string                 `json:"user_id,omitempty"`
	ProjectID string                 `json:"project_id,omitempty"`
	Tags      []string               `json:"tags,omitempty"`
	OccurrenceCount int64             `json:"occurrence_count"`
	FirstSeen time.Time              `json:"first_seen"`
	LastSeen  time.Time              `json:"last_seen"`
	CreatedAt time.Time              `json:"created_at"`
	UpdatedAt time.Time              `json:"updated_at"`
}

type ErrorListResponse struct {
	Errors []ErrorResponse `json:"errors"`
	Total  int64           `json:"total"`
	Limit  int             `json:"limit"`
	Offset int             `json:"offset"`
}

type ErrorStatsRequest struct {
	StartDate time.Time `json:"start_date"`
	EndDate   time.Time `json:"end_date"`
	GroupBy   string    `json:"group_by"` // type, source, severity, user
}

type ErrorStatsResponse struct {
	TotalErrors      int64                     `json:"total_errors"`
	ErrorsByType     map[string]int64          `json:"errors_by_type"`
	ErrorsBySource   map[string]int64          `json:"errors_by_source"`
	ErrorsBySeverity map[string]int64          `json:"errors_by_severity"`
	ResolutionStats  struct {
		Resolved   int64 `json:"resolved"`
		Unresolved int64 `json:"unresolved"`
		Dismissed  int64 `json:"dismissed"`
	} `json:"resolution_stats"`
}

type ErrorGroupResponse struct {
	GroupID        string           `json:"group_id"`
	Representative ErrorResponse    `json:"representative"`
	Count          int64            `json:"count"`
	Similar        []ErrorResponse  `json:"similar,omitempty"`
}

type ResolveErrorRequest struct {
	Status       string `json:"status"`
	Resolution   string `json:"resolution,omitempty"`
	ResolutionBy string `json:"resolution_by,omitempty"`
}

type CreateBugFromErrorRequest struct {
	Title        string `json:"title,omitempty"`
	Description  string `json:"description,omitempty"`
	ProjectID    string `json:"project_id"`
	Severity     string `json:"severity,omitempty"`
	AssignedTo   string `json:"assigned_to,omitempty"`
}

type ErrorAlertRequest struct {
	Condition   string `json:"condition"` // count > X in time period
	Threshold   int    `json:"threshold"`
	TimePeriod  string `json:"time_period"` // 1h, 24h, 7d
	Action      string `json:"action"`      // email, slack, pagerduty
	Recipients  []string `json:"recipients,omitempty"`
}

type ErrorCommentRequest struct {
	Comment string `json:"comment"`
	UserID  string `json:"user_id,omitempty"`
}

// ==================== NOTIFICATION DTOs ====================

type CreateNotificationRequest struct {
	Title       string                 `json:"title"`
	Message     string                 `json:"message"`
	NotificationType string             `json:"type"`
	Priority    string                 `json:"priority"`
	Recipients  []string               `json:"recipients"`
	Channels    []string               `json:"channels,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	ScheduledAt *time.Time             `json:"scheduled_at,omitempty"`
}

type NotificationResponse struct {
	ID            string    `json:"id"`
	Title         string    `json:"title"`
	Message       string    `json:"message"`
	Type          string    `json:"type"`
	Priority      string    `json:"priority"`
	Status        string    `json:"status"`
	ReadAt        *time.Time `json:"read_at,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

type NotificationPreferencesRequest struct {
	EmailEnabled       bool     `json:"email_enabled"`
	SlackEnabled       bool     `json:"slack_enabled"`
	InAppEnabled       bool     `json:"in_app_enabled"`
	SMSEnabled         bool     `json:"sms_enabled"`
	Categories         map[string]bool `json:"categories,omitempty"`
	QuietHours         struct {
		Enabled bool   `json:"enabled"`
		Start   string `json:"start"`
		End     string `json:"end"`
	} `json:"quiet_hours,omitempty"`
	DoNotDisturb bool `json:"do_not_disturb"`
}

type SendNotificationRequest struct {
	NotificationID string   `json:"notification_id"`
	UserIDs        []string `json:"user_ids"`
	Channels       []string `json:"channels,omitempty"`
}

type MarkReadRequest struct {
	Read bool `json:"read"`
}

type TemplateRequest struct {
	Name    string `json:"name"`
	Subject string `json:"subject,omitempty"`
	Body    string `json:"body"`
	Type    string `json:"type"`
}

type NotificationRuleRequest struct {
	Name        string            `json:"name"`
	Trigger     string            `json:"trigger"`
	Conditions  map[string]interface{} `json:"conditions,omitempty"`
	Actions     []string          `json:"actions"`
	Channels    []string          `json:"channels,omitempty"`
	Enabled     bool              `json:"enabled"`
}

type ScheduleNotificationRequest struct {
	NotificationID string    `json:"notification_id"`
	ScheduledAt    time.Time `json:"scheduled_at"`
	Recurring      *string   `json:"recurring,omitempty"` // daily, weekly, monthly
}

type NotificationDeliveryResponse struct {
	NotificationID string    `json:"notification_id"`
	UserID         string    `json:"user_id"`
	Channel        string    `json:"channel"`
	Status         string    `json:"status"`
	DeliveredAt    time.Time `json:"delivered_at,omitempty"`
	FailureReason  string    `json:"failure_reason,omitempty"`
}

// ==================== INTEGRATION DTOs ====================

type CreateIntegrationRequest struct {
	Name        string                 `json:"name"`
	Provider    string                 `json:"provider"`
	Type        string                 `json:"type"`
	Config      map[string]interface{} `json:"config"`
	Credentials map[string]string      `json:"credentials"`
	Enabled     bool                   `json:"enabled"`
}

type UpdateIntegrationRequest struct {
	Name        string                 `json:"name,omitempty"`
	Config      map[string]interface{} `json:"config,omitempty"`
	Credentials map[string]string      `json:"credentials,omitempty"`
	Enabled     *bool                  `json:"enabled,omitempty"`
}

type IntegrationResponse struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Provider    string                 `json:"provider"`
	Type        string                 `json:"type"`
	Status      string                 `json:"status"`
	Enabled     bool                   `json:"enabled"`
	LastSync    *time.Time             `json:"last_sync,omitempty"`
	NextSync    *time.Time             `json:"next_sync,omitempty"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
}

type TestConnectionRequest struct {
	Config      map[string]interface{} `json:"config,omitempty"`
	Credentials map[string]string      `json:"credentials,omitempty"`
}

type IntegrationStatsResponse struct {
	ID              string            `json:"id"`
	Provider        string            `json:"provider"`
	Status          string            `json:"status"`
	LastSync        time.Time         `json:"last_sync,omitempty"`
	SyncCount       int64             `json:"sync_count"`
	SuccessCount    int64             `json:"success_count"`
	FailureCount    int64             `json:"failure_count"`
	EventsProcessed int64             `json:"events_processed"`
	AverageLatency  int64             `json:"average_latency_ms"`
}

type SyncStatusResponse struct {
	IntegrationID   string    `json:"integration_id"`
	Status          string    `json:"status"`
	Progress        int       `json:"progress"`
	ItemsProcessed  int64     `json:"items_processed"`
	TotalItems      int64     `json:"total_items"`
	StartedAt       time.Time `json:"started_at"`
	EstimatedEnd    time.Time `json:"estimated_end,omitempty"`
	CurrentPhase    string    `json:"current_phase"`
}

type IntegrationConfigRequest struct {
	Config map[string]interface{} `json:"config"`
}

type RotateCredentialsRequest struct {
	NewCredentials map[string]string `json:"new_credentials"`
}

type MigrateConfigRequest struct {
	FromVersion string                 `json:"from_version"`
	ToVersion   string                 `json:"to_version"`
	Config      map[string]interface{} `json:"config"`
}

type IntegrationHealthRequest struct {
	IntegrationID string `json:"integration_id"`
}

// ==================== WEBHOOK DTOs ====================

type CreateWebhookRequest struct {
	Name         string   `json:"name"`
	URL          string   `json:"url"`
	Events       []string `json:"events"`
	IntegrationID string  `json:"integration_id,omitempty"`
	Active       bool     `json:"active"`
	Secret       string   `json:"secret,omitempty"`
}

type WebhookResponse struct {
	ID            string    `json:"id"`
	Name          string    `json:"name"`
	URL           string    `json:"url"`
	Events        []string  `json:"events"`
	IntegrationID string    `json:"integration_id,omitempty"`
	Status        string    `json:"status"`
	Active        bool      `json:"active"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

type DeliveryResponse struct {
	ID        string    `json:"id"`
	WebhookID string    `json:"webhook_id"`
	Event     string    `json:"event"`
	Status    string    `json:"status"`
	StatusCode int      `json:"status_code"`
	Payload   map[string]interface{} `json:"payload"`
	Response  string    `json:"response,omitempty"`
	DeliveredAt time.Time `json:"delivered_at"`
	RetryCount int      `json:"retry_count"`
}

type TestWebhookRequest struct {
	WebhookID string `json:"webhook_id"`
	EventType string `json:"event_type"`
}

type ReplayEventsRequest struct {
	WebhookID string    `json:"webhook_id"`
	StartDate time.Time `json:"start_date"`
	EndDate   time.Time `json:"end_date"`
	Events    []string  `json:"events,omitempty"`
}

type RoutingRuleRequest struct {
	Name        string            `json:"name"`
	EventType   string            `json:"event_type"`
	Conditions  map[string]interface{} `json:"conditions,omitempty"`
	WebhookID   string            `json:"webhook_id"`
	Enabled     bool              `json:"enabled"`
}

type SigningKeyResponse struct {
	KeyID     string    `json:"key_id"`
	Algorithm string    `json:"algorithm"`
	CreatedAt time.Time `json:"created_at"`
	RotatedAt *time.Time `json:"rotated_at,omitempty"`
}

type WebhookStatsResponse struct {
	WebhookID      string    `json:"webhook_id"`
	TotalDeliveries int64    `json:"total_deliveries"`
	SuccessCount   int64     `json:"success_count"`
	FailureCount   int64     `json:"failure_count"`
	AverageLatency int64     `json:"average_latency_ms"`
	LastDelivery   *time.Time `json:"last_delivery,omitempty"`
}

// ==================== SESSION DTOs ====================

type SessionResponse struct {
	ID          string    `json:"id"`
	UserID      string    `json:"user_id"`
	Token       string    `json:"token,omitempty"`
	Status      string    `json:"status"`
	IP          string    `json:"ip,omitempty"`
	UserAgent   string    `json:"user_agent,omitempty"`
	LastActivity time.Time `json:"last_activity"`
	CreatedAt   time.Time `json:"created_at"`
	ExpiresAt   time.Time `json:"expires_at"`
}

type SessionListResponse struct {
	Sessions []SessionResponse `json:"sessions"`
	Total    int64             `json:"total"`
}

type SessionActivityRequest struct {
	Action    string                 `json:"action"`
	Resource  string                 `json:"resource"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

type SessionExtendRequest struct {
	Duration int `json:"duration_seconds"`
}

type SessionStatsResponse struct {
	ActiveSessions    int64              `json:"active_sessions"`
	InactiveSessions  int64              `json:"inactive_sessions"`
	TotalSessions     int64              `json:"total_sessions"`
	AverageSessionDuration int64         `json:"average_session_duration_seconds"`
	UserSessions      map[string]int64   `json:"user_sessions"`
	DeviceStats       map[string]int64   `json:"device_stats"`
}

type ConcurrentUserResponse struct {
	ConcurrentUsers int64 `json:"concurrent_users"`
	PeakUsers       int64 `json:"peak_users"`
	AverageUsers    int64 `json:"average_users"`
}

type SessionPresenceUpdateRequest struct {
	Status    string `json:"status"` // active, idle, away
	Location  string `json:"location,omitempty"`
}

// ==================== AUDIT LOG DTOs ====================

type AuditLogResponse struct {
	ID        string                 `json:"id"`
	Action    string                 `json:"action"`
	UserID    string                 `json:"user_id"`
	Resource  string                 `json:"resource"`
	ResourceID string                `json:"resource_id"`
	Changes   map[string]interface{} `json:"changes,omitempty"`
	Status    string                 `json:"status"`
	Reason    string                 `json:"reason,omitempty"`
	CreatedAt time.Time              `json:"created_at"`
}

type AuditSearchRequest struct {
	UserID    string    `json:"user_id,omitempty"`
	Action    string    `json:"action,omitempty"`
	Resource  string    `json:"resource,omitempty"`
	StartDate time.Time `json:"start_date,omitempty"`
	EndDate   time.Time `json:"end_date,omitempty"`
	Query     string    `json:"query,omitempty"`
	Limit     int       `json:"limit"`
	Offset    int       `json:"offset"`
}

type ComplianceReportResponse struct {
	ReportID      string            `json:"report_id"`
	Period        string            `json:"period"`
	TotalEvents   int64             `json:"total_events"`
	UserActions   map[string]int64   `json:"user_actions"`
	PermissionChanges int64          `json:"permission_changes"`
	DataAccess    int64             `json:"data_access"`
	GeneratedAt   time.Time         `json:"generated_at"`
}

type PermissionChangeResponse struct {
	ID            string    `json:"id"`
	UserID        string    `json:"user_id"`
	Permission    string    `json:"permission"`
	Action        string    `json:"action"` // grant, revoke
	GrantedBy     string    `json:"granted_by,omitempty"`
	RevokedBy     string    `json:"revoked_by,omitempty"`
	Reason        string    `json:"reason,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
}

type AuditStatsResponse struct {
	TotalAuditLogs     int64                     `json:"total_audit_logs"`
	ActionsByType      map[string]int64          `json:"actions_by_type"`
	ActionsByUser      map[string]int64          `json:"actions_by_user"`
	ActionsByResource  map[string]int64          `json:"actions_by_resource"`
	SuccessfulActions  int64                     `json:"successful_actions"`
	FailedActions      int64                     `json:"failed_actions"`
}

// ==================== REAL-TIME EVENT DTOs ====================

type SubscribeRequest struct {
	Channels []string `json:"channels"`
	Filter   map[string]interface{} `json:"filter,omitempty"`
}

type PublishRequest struct {
	Channel string                 `json:"channel"`
	Event   string                 `json:"event"`
	Data    map[string]interface{} `json:"data"`
}

type PresenceUpdateRequest struct {
	UserID string `json:"user_id"`
	Status string `json:"status"` // online, idle, away, offline
	Location string `json:"location,omitempty"`
}

type ChannelListResponse struct {
	Channels []struct {
		Name            string `json:"name"`
		Description     string `json:"description,omitempty"`
		Subscribers     int64  `json:"subscribers"`
		MessageCount    int64  `json:"message_count"`
		LastMessage     *time.Time `json:"last_message,omitempty"`
	} `json:"channels"`
	Total int64 `json:"total"`
}

type ActiveConnectionsResponse struct {
	ActiveConnections int64                          `json:"active_connections"`
	Connections       []map[string]interface{}      `json:"connections"`
	ByChannel         map[string]int64               `json:"by_channel"`
}

type BulkSubscribeRequest struct {
	Channels []string `json:"channels"`
}

// ==================== INTEGRATION HEALTH DTOs ====================

type HealthCheckResponse struct {
	Status     string                 `json:"status"` // healthy, warning, critical
	Components map[string]interface{} `json:"components"`
	Timestamp  time.Time              `json:"timestamp"`
}

type DiagnosticsResponse struct {
	IntegrationID string                 `json:"integration_id"`
	Status        string                 `json:"status"`
	LastCheck     time.Time              `json:"last_check"`
	Issues        []string               `json:"issues,omitempty"`
	Details       map[string]interface{} `json:"details,omitempty"`
}

type MetricsResponse struct {
	Uptime              float64 `json:"uptime_percent"`
	AverageResponseTime int64   `json:"average_response_time_ms"`
	ErrorRate           float64 `json:"error_rate_percent"`
	RequestCount        int64   `json:"request_count"`
	SuccessCount        int64   `json:"success_count"`
	FailureCount        int64   `json:"failure_count"`
}

type IncidentResponse struct {
	ID        string    `json:"id"`
	Integration string  `json:"integration"`
	Severity  string    `json:"severity"`
	Description string  `json:"description"`
	StartedAt time.Time `json:"started_at"`
	ResolvedAt *time.Time `json:"resolved_at,omitempty"`
	Status    string    `json:"status"`
}

type UptimeResponse struct {
	Period           string  `json:"period"`
	UptimePercent    float64 `json:"uptime_percent"`
	Downtime         int64   `json:"downtime_seconds"`
	IncidentCount    int64   `json:"incident_count"`
	LastIncident     *time.Time `json:"last_incident,omitempty"`
}

type HealthAlertRequest struct {
	MetricName  string `json:"metric_name"`
	Operator    string `json:"operator"` // gt, lt, eq
	Threshold   float64 `json:"threshold"`
	Duration    string `json:"duration"`
	Action      string `json:"action"`   // email, slack, pagerduty
}

// ==================== AUDIT LOG DTOs (Additional) ====================

type LogActionRequest struct {
	Action      string                 `json:"action"`
	UserID      string                 `json:"user_id"`
	ResourceType string                `json:"resource_type"`
	ResourceID  string                 `json:"resource_id"`
	Changes     map[string]interface{} `json:"changes,omitempty"`
	Details     map[string]interface{} `json:"details,omitempty"`
}

type AuditReportRequest struct {
	StartDate   time.Time `json:"start_date"`
	EndDate     time.Time `json:"end_date"`
	UserID      string    `json:"user_id,omitempty"`
	Action      string    `json:"action,omitempty"`
	ResourceType string   `json:"resource_type,omitempty"`
	Format      string    `json:"format"` // json, csv, pdf
}

type AuditReportResponse struct {
	ReportID      string                 `json:"report_id"`
	Format        string                 `json:"format"`
	GeneratedAt   time.Time              `json:"generated_at"`
	Entries       []map[string]interface{} `json:"entries,omitempty"`
	URL           string                 `json:"url,omitempty"` // For file-based reports
	ExpiresAt     time.Time              `json:"expires_at,omitempty"`
	RecordCount   int64                  `json:"record_count"`
}

type AuditAlertRequest struct {
	Condition   string   `json:"condition"`   // action_count > X in time_period
	Action      string   `json:"action"`      // email, slack, pagerduty
	Recipients  []string `json:"recipients,omitempty"`
	Threshold   int      `json:"threshold"`
	TimePeriod  string   `json:"time_period"` // 1h, 24h, 7d
	Description string   `json:"description,omitempty"`
}

// ==================== SESSION TRACKING DTOs (Additional) ====================

type CreateSessionRequest struct {
	UserID    string `json:"user_id"`
	IPAddress string `json:"ip_address,omitempty"`
	UserAgent string `json:"user_agent,omitempty"`
}
