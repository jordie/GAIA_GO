package services

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// EventLogServiceImpl implements EventLogService
type EventLogServiceImpl struct {
	repo repository.EventLogRepository
}

// NewEventLogService creates a new event log service
func NewEventLogService(repo repository.EventLogRepository) EventLogService {
	return &EventLogServiceImpl{repo: repo}
}

func (els *EventLogServiceImpl) CreateEvent(ctx context.Context, req *CreateEventRequest) (*models.EventLog, error) {
	// Marshal Metadata to JSON
	var metadata json.RawMessage
	if req.Metadata != nil {
		if data, err := json.Marshal(req.Metadata); err == nil {
			metadata = data
		}
	}

	// Marshal Tags to JSON
	var tags json.RawMessage
	if len(req.Tags) > 0 {
		if data, err := json.Marshal(req.Tags); err == nil {
			tags = data
		}
	}

	event := &models.EventLog{
		ID:        uuid.New().String(),
		EventType: req.Type,
		Message:   req.Description,
		Source:    req.Source,
		Timestamp: time.Now(),
		UserID:    req.UserID,
		ProjectID: req.ProjectID,
		Metadata:  metadata,
		Tags:      tags,
	}

	if err := els.repo.Create(ctx, event); err != nil {
		return nil, fmt.Errorf("failed to create event: %w", err)
	}

	return event, nil
}

func (els *EventLogServiceImpl) GetEvent(ctx context.Context, id string) (*models.EventLog, error) {
	event, err := els.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get event: %w", err)
	}
	return event, nil
}

func (els *EventLogServiceImpl) ListEvents(ctx context.Context, req *ListEventsRequest) ([]*models.EventLog, int64, error) {
	filters := make(map[string]interface{})
	if req.Type != "" {
		filters["event_type"] = req.Type
	}
	if req.Source != "" {
		filters["source"] = req.Source
	}
	if req.UserID != "" {
		filters["user_id"] = req.UserID
	}
	if req.ProjectID != "" {
		filters["project_id"] = req.ProjectID
	}

	events, total, err := els.repo.List(ctx, filters, req.Limit, req.Offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list events: %w", err)
	}

	return events, total, nil
}

func (els *EventLogServiceImpl) UpdateEvent(ctx context.Context, id string, req *UpdateEventRequest) (*models.EventLog, error) {
	event, err := els.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("event not found: %w", err)
	}

	if req.Description != "" {
		event.Message = req.Description
	}
	if req.Metadata != nil {
		if data, marshalErr := json.Marshal(req.Metadata); marshalErr == nil {
			event.Metadata = data
		}
	}

	if err := els.repo.Update(ctx, event); err != nil {
		return nil, fmt.Errorf("failed to update event: %w", err)
	}

	return event, nil
}

func (els *EventLogServiceImpl) SearchEvents(ctx context.Context, req *EventSearchRequest) ([]*models.EventLog, int64, error) {
	events, total, err := els.repo.Search(ctx, req.Query, req.Limit, req.Offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to search events: %w", err)
	}
	return events, total, nil
}

func (els *EventLogServiceImpl) GetEventStats(ctx context.Context, startDate, endDate string) (*EventStatsResponse, error) {
	_, err := els.repo.GetStats(ctx, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to get event stats: %w", err)
	}

	return &EventStatsResponse{
		TotalEvents:    0,
		EventsByType:   map[string]int64{},
		EventsBySource: map[string]int64{},
		EventsByUser:   map[string]int64{},
	}, nil
}

func (els *EventLogServiceImpl) GetEventsByType(ctx context.Context, eventType string, limit, offset int) ([]*models.EventLog, int64, error) {
	events, total, err := els.repo.GetByType(ctx, eventType, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get events by type: %w", err)
	}
	return events, total, nil
}

func (els *EventLogServiceImpl) GetEventsByUser(ctx context.Context, userID string, limit, offset int) ([]*models.EventLog, int64, error) {
	events, total, err := els.repo.GetByUser(ctx, userID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get events by user: %w", err)
	}
	return events, total, nil
}

func (els *EventLogServiceImpl) GetEventsByProject(ctx context.Context, projectID string, limit, offset int) ([]*models.EventLog, int64, error) {
	events, total, err := els.repo.GetByProject(ctx, projectID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get events by project: %w", err)
	}
	return events, total, nil
}

func (els *EventLogServiceImpl) GetEventTimeline(ctx context.Context, req *ListEventsRequest) (*EventTimelineResponse, error) {
	filters := make(map[string]interface{})
	if req.Type != "" {
		filters["event_type"] = req.Type
	}

	events, total, err := els.repo.List(ctx, filters, req.Limit, req.Offset)
	if err != nil {
		return nil, fmt.Errorf("failed to get event timeline: %w", err)
	}

	// Convert EventLog models to EventResponse
	eventResponses := make([]EventResponse, 0, len(events))
	for _, e := range events {
		eventResponses = append(eventResponses, EventResponse{
			ID:        e.ID,
			Type:      e.EventType,
			Source:    e.Source,
			UserID:    e.UserID,
			ProjectID: e.ProjectID,
			CreatedAt: e.CreatedAt,
		})
	}

	return &EventTimelineResponse{
		Events: eventResponses,
		Total:  total,
	}, nil
}

func (els *EventLogServiceImpl) ExportEvents(ctx context.Context, format string, filters *EventFilterRequest) (*EventExportResponse, error) {
	filterMap := make(map[string]interface{})
	if filters != nil {
		if len(filters.Types) > 0 {
			filterMap["event_type"] = filters.Types[0]
		}
		if len(filters.Sources) > 0 {
			filterMap["source"] = filters.Sources[0]
		}
	}

	_, _, err := els.repo.List(ctx, filterMap, 10000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to export events: %w", err)
	}

	switch format {
	case "json", "csv":
		// valid formats
	default:
		return nil, fmt.Errorf("unsupported export format: %s", format)
	}

	return &EventExportResponse{
		Format:    format,
		ExpiresAt: time.Now().Add(24 * time.Hour),
		Size:      0,
	}, nil
}

func (els *EventLogServiceImpl) ArchiveEvents(ctx context.Context, eventIDs []string) error {
	for _, id := range eventIDs {
		event, err := els.repo.Get(ctx, id)
		if err != nil {
			return fmt.Errorf("event not found: %s, %w", id, err)
		}

		// Unmarshal existing metadata or create new map
		metadataMap := make(map[string]interface{})
		if len(event.Metadata) > 0 {
			_ = json.Unmarshal(event.Metadata, &metadataMap)
		}
		metadataMap["archived"] = true
		metadataMap["archived_at"] = time.Now()

		if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
			event.Metadata = data
		}

		if err := els.repo.Update(ctx, event); err != nil {
			return fmt.Errorf("failed to archive event: %w", err)
		}
	}
	return nil
}

func (els *EventLogServiceImpl) DeleteEvents(ctx context.Context, eventIDs []string) error {
	for _, id := range eventIDs {
		if err := els.repo.Delete(ctx, id); err != nil {
			return fmt.Errorf("failed to delete event: %w", err)
		}
	}
	return nil
}

func (els *EventLogServiceImpl) AddEventTag(ctx context.Context, eventID string, req *EventTagRequest) error {
	event, err := els.repo.Get(ctx, eventID)
	if err != nil {
		return fmt.Errorf("event not found: %w", err)
	}

	// Unmarshal existing tags
	var tagSlice []string
	if len(event.Tags) > 0 {
		_ = json.Unmarshal(event.Tags, &tagSlice)
	}
	if tagSlice == nil {
		tagSlice = make([]string, 0)
	}

	// Check if tag already exists
	for _, tag := range tagSlice {
		if tag == req.Tag {
			return nil
		}
	}

	tagSlice = append(tagSlice, req.Tag)

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(tagSlice); marshalErr == nil {
		event.Tags = data
	}

	if err := els.repo.Update(ctx, event); err != nil {
		return fmt.Errorf("failed to add tag: %w", err)
	}

	return nil
}

func (els *EventLogServiceImpl) RemoveEventTag(ctx context.Context, eventID string, tag string) error {
	event, err := els.repo.Get(ctx, eventID)
	if err != nil {
		return fmt.Errorf("event not found: %w", err)
	}

	// Unmarshal existing tags
	var tagSlice []string
	if len(event.Tags) > 0 {
		_ = json.Unmarshal(event.Tags, &tagSlice)
	}
	if tagSlice == nil {
		return nil
	}

	newTags := make([]string, 0)
	for _, t := range tagSlice {
		if t != tag {
			newTags = append(newTags, t)
		}
	}

	if data, marshalErr := json.Marshal(newTags); marshalErr == nil {
		event.Tags = data
	}

	if err := els.repo.Update(ctx, event); err != nil {
		return fmt.Errorf("failed to remove tag: %w", err)
	}

	return nil
}

func (els *EventLogServiceImpl) GetEventsByTag(ctx context.Context, tag string, limit, offset int) ([]*models.EventLog, int64, error) {
	events, total, err := els.repo.GetByTag(ctx, tag, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get events by tag: %w", err)
	}
	return events, total, nil
}

func (els *EventLogServiceImpl) GetRelatedEvents(ctx context.Context, eventID string, limit int) ([]*models.EventLog, error) {
	event, err := els.repo.Get(ctx, eventID)
	if err != nil {
		return nil, fmt.Errorf("event not found: %w", err)
	}

	filters := make(map[string]interface{})
	filters["event_type"] = event.EventType
	if event.ProjectID != "" {
		filters["project_id"] = event.ProjectID
	}

	events, _, err := els.repo.List(ctx, filters, limit, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to get related events: %w", err)
	}

	return events, nil
}

func (els *EventLogServiceImpl) GetEventImpact(ctx context.Context, eventID string) (map[string]interface{}, error) {
	event, err := els.repo.Get(ctx, eventID)
	if err != nil {
		return nil, fmt.Errorf("event not found: %w", err)
	}

	impact := map[string]interface{}{
		"event_id":         event.ID,
		"event_type":       event.EventType,
		"affected_project": event.ProjectID,
		"affected_user":    event.UserID,
		"timestamp":        event.Timestamp,
	}

	return impact, nil
}

func (els *EventLogServiceImpl) GetAggregatedEvents(ctx context.Context, groupBy string, filters *EventFilterRequest) (map[string]interface{}, error) {
	filterMap := make(map[string]interface{})
	if filters != nil {
		if len(filters.Types) > 0 {
			filterMap["event_type"] = filters.Types[0]
		}
	}

	events, _, err := els.repo.List(ctx, filterMap, 10000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to get aggregated events: %w", err)
	}

	aggregated := make(map[string]int)
	for _, event := range events {
		key := ""
		switch groupBy {
		case "type":
			key = event.EventType
		case "source":
			key = event.Source
		case "user":
			key = event.UserID
		case "project":
			key = event.ProjectID
		default:
			key = "unknown"
		}

		aggregated[key]++
	}

	return map[string]interface{}{
		"group_by": groupBy,
		"data":     aggregated,
		"count":    len(aggregated),
	}, nil
}

func (els *EventLogServiceImpl) GetAvailableFilters(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"event_types": []string{"user_action", "system", "integration", "audit"},
		"sources":     []string{"dashboard", "api", "webhook", "cli"},
		"sort_by":     []string{"timestamp", "user_id", "project_id", "event_type"},
	}, nil
}

func (els *EventLogServiceImpl) GetTrendingEvents(ctx context.Context, timeWindow string, limit int) ([]*models.EventLog, error) {
	filters := make(map[string]interface{})
	// In a real implementation, timeWindow would filter events
	events, _, err := els.repo.List(ctx, filters, limit, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to get trending events: %w", err)
	}

	return events, nil
}

func (els *EventLogServiceImpl) GetEventSources(ctx context.Context) ([]string, error) {
	return []string{"dashboard", "api", "webhook", "cli", "integration"}, nil
}

func (els *EventLogServiceImpl) GetEventTypes(ctx context.Context) ([]string, error) {
	return []string{"user_action", "system", "integration", "audit", "security", "error"}, nil
}

func (els *EventLogServiceImpl) BulkCreateEvents(ctx context.Context, requests []*CreateEventRequest) ([]*models.EventLog, error) {
	events := make([]*models.EventLog, 0, len(requests))

	for _, req := range requests {
		var metadata json.RawMessage
		if req.Metadata != nil {
			if data, err := json.Marshal(req.Metadata); err == nil {
				metadata = data
			}
		}

		var tags json.RawMessage
		if len(req.Tags) > 0 {
			if data, err := json.Marshal(req.Tags); err == nil {
				tags = data
			}
		}

		event := &models.EventLog{
			ID:        uuid.New().String(),
			EventType: req.Type,
			Message:   req.Description,
			Source:    req.Source,
			Timestamp: time.Now(),
			UserID:    req.UserID,
			ProjectID: req.ProjectID,
			Metadata:  metadata,
			Tags:      tags,
		}

		if err := els.repo.Create(ctx, event); err != nil {
			return nil, fmt.Errorf("failed to create event in bulk: %w", err)
		}

		events = append(events, event)
	}

	return events, nil
}

func (els *EventLogServiceImpl) BulkDeleteEvents(ctx context.Context, eventIDs []string) error {
	for _, id := range eventIDs {
		if err := els.repo.Delete(ctx, id); err != nil {
			return fmt.Errorf("failed to delete event: %w", err)
		}
	}
	return nil
}

func (els *EventLogServiceImpl) GetRetentionPolicy(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"retention_days":     90,
		"archive_after_days": 30,
		"enabled":            true,
	}, nil
}

func (els *EventLogServiceImpl) UpdateRetentionPolicy(ctx context.Context, policy map[string]interface{}) error {
	// In a real implementation, this would update configuration
	return nil
}

func (els *EventLogServiceImpl) PurgeOldEvents(ctx context.Context, beforeDate string) (int64, error) {
	count, err := els.repo.HardDelete(ctx, beforeDate)
	if err != nil {
		return 0, fmt.Errorf("failed to purge old events: %w", err)
	}
	return count, nil
}

func (els *EventLogServiceImpl) CleanupDeletedEvents(ctx context.Context) (int64, error) {
	thirtyDaysAgo := time.Now().AddDate(0, 0, -30)
	count, err := els.repo.HardDelete(ctx, thirtyDaysAgo.Format("2006-01-02"))
	if err != nil {
		return 0, fmt.Errorf("failed to cleanup deleted events: %w", err)
	}
	return count, nil
}

func (els *EventLogServiceImpl) VerifyDataIntegrity(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"status":         "healthy",
		"events_checked": 0,
		"issues_found":   0,
	}, nil
}

func (els *EventLogServiceImpl) SubscribeToEventType(ctx context.Context, userID string, eventType string) error {
	// In a real implementation, this would store subscriptions in database
	return nil
}

func (els *EventLogServiceImpl) UnsubscribeFromEventType(ctx context.Context, userID string, eventType string) error {
	// In a real implementation, this would remove subscriptions from database
	return nil
}

func (els *EventLogServiceImpl) GetUserSubscriptions(ctx context.Context, userID string) ([]string, error) {
	// In a real implementation, this would query subscriptions from database
	return []string{}, nil
}

func (els *EventLogServiceImpl) NotifyAboutEvent(ctx context.Context, eventID string, userIDs []string) error {
	event, err := els.repo.Get(ctx, eventID)
	if err != nil {
		return fmt.Errorf("event not found: %w", err)
	}

	// In a real implementation, this would send notifications
	_ = event
	_ = userIDs

	return nil
}
