package services

import (
	"context"

	"architect-go/pkg/models"
)

// EventLogService defines event logging business logic
type EventLogService interface {
	// CreateEvent creates a new event log entry
	CreateEvent(ctx context.Context, req *CreateEventRequest) (*models.EventLog, error)

	// GetEvent retrieves an event by ID
	GetEvent(ctx context.Context, id string) (*models.EventLog, error)

	// ListEvents retrieves events with filtering and pagination
	ListEvents(ctx context.Context, req *ListEventsRequest) ([]*models.EventLog, int64, error)

	// UpdateEvent updates event metadata
	UpdateEvent(ctx context.Context, id string, req *UpdateEventRequest) (*models.EventLog, error)

	// SearchEvents performs full-text search on events
	SearchEvents(ctx context.Context, req *EventSearchRequest) ([]*models.EventLog, int64, error)

	// GetEventStats returns statistics about events
	GetEventStats(ctx context.Context, startDate, endDate string) (*EventStatsResponse, error)

	// GetEventsByType retrieves events filtered by type
	GetEventsByType(ctx context.Context, eventType string, limit, offset int) ([]*models.EventLog, int64, error)

	// GetEventsByUser retrieves events created by a specific user
	GetEventsByUser(ctx context.Context, userID string, limit, offset int) ([]*models.EventLog, int64, error)

	// GetEventsByProject retrieves events related to a specific project
	GetEventsByProject(ctx context.Context, projectID string, limit, offset int) ([]*models.EventLog, int64, error)

	// GetEventTimeline retrieves events in chronological order
	GetEventTimeline(ctx context.Context, req *ListEventsRequest) (*EventTimelineResponse, error)

	// ExportEvents exports events in specified format (json, csv)
	ExportEvents(ctx context.Context, format string, filters *EventFilterRequest) (*EventExportResponse, error)

	// ArchiveEvents marks events as archived
	ArchiveEvents(ctx context.Context, eventIDs []string) error

	// DeleteEvents permanently deletes events (admin only)
	DeleteEvents(ctx context.Context, eventIDs []string) error

	// AddEventTag adds a tag to an event
	AddEventTag(ctx context.Context, eventID string, req *EventTagRequest) error

	// RemoveEventTag removes a tag from an event
	RemoveEventTag(ctx context.Context, eventID string, tag string) error

	// GetEventsByTag retrieves events with a specific tag
	GetEventsByTag(ctx context.Context, tag string, limit, offset int) ([]*models.EventLog, int64, error)

	// GetRelatedEvents retrieves events related to a specific event
	GetRelatedEvents(ctx context.Context, eventID string, limit int) ([]*models.EventLog, error)

	// GetEventImpact analyzes impact of an event
	GetEventImpact(ctx context.Context, eventID string) (map[string]interface{}, error)

	// GetAggregatedEvents returns aggregated view of events
	GetAggregatedEvents(ctx context.Context, groupBy string, filters *EventFilterRequest) (map[string]interface{}, error)

	// GetAvailableFilters returns available filter options
	GetAvailableFilters(ctx context.Context) (map[string]interface{}, error)

	// GetTrendingEvents returns currently trending events
	GetTrendingEvents(ctx context.Context, timeWindow string, limit int) ([]*models.EventLog, error)

	// GetEventSources returns list of available event sources
	GetEventSources(ctx context.Context) ([]string, error)

	// GetEventTypes returns list of available event types
	GetEventTypes(ctx context.Context) ([]string, error)

	// BulkCreateEvents creates multiple events in batch
	BulkCreateEvents(ctx context.Context, requests []*CreateEventRequest) ([]*models.EventLog, error)

	// BulkDeleteEvents deletes multiple events
	BulkDeleteEvents(ctx context.Context, eventIDs []string) error

	// GetRetentionPolicy retrieves event retention settings
	GetRetentionPolicy(ctx context.Context) (map[string]interface{}, error)

	// UpdateRetentionPolicy updates event retention settings
	UpdateRetentionPolicy(ctx context.Context, policy map[string]interface{}) error

	// PurgeOldEvents removes events older than specified date (admin only)
	PurgeOldEvents(ctx context.Context, beforeDate string) (int64, error)

	// CleanupDeletedEvents performs cleanup of soft-deleted events
	CleanupDeletedEvents(ctx context.Context) (int64, error)

	// VerifyDataIntegrity checks data integrity of event logs
	VerifyDataIntegrity(ctx context.Context) (map[string]interface{}, error)

	// SubscribeToEventType subscribes user to event type notifications
	SubscribeToEventType(ctx context.Context, userID string, eventType string) error

	// UnsubscribeFromEventType unsubscribes user from event type notifications
	UnsubscribeFromEventType(ctx context.Context, userID string, eventType string) error

	// GetUserSubscriptions retrieves user's event subscriptions
	GetUserSubscriptions(ctx context.Context, userID string) ([]string, error)

	// NotifyAboutEvent sends notification about an event
	NotifyAboutEvent(ctx context.Context, eventID string, userIDs []string) error
}
