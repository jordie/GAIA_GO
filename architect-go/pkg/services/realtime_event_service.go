package services

import (
	"context"
	"fmt"

	"architect-go/pkg/repository"
)

// RealTimeEventServiceImpl implements RealTimeEventService
type RealTimeEventServiceImpl struct {
	repo repository.RealTimeRepository
}

// NewRealTimeEventService creates a new real-time event service
func NewRealTimeEventService(repo repository.RealTimeRepository) *RealTimeEventServiceImpl {
	return &RealTimeEventServiceImpl{repo: repo}
}

// PublishToChannel publishes an event to a specific channel
func (s *RealTimeEventServiceImpl) PublishToChannel(ctx context.Context, channel string, event map[string]interface{}) error {
	if s.repo == nil {
		return fmt.Errorf("realtime repository not configured")
	}
	return s.repo.PublishToChannel(ctx, channel, event)
}

// BroadcastEvent broadcasts an event to all subscribers
func (s *RealTimeEventServiceImpl) BroadcastEvent(ctx context.Context, event map[string]interface{}) error {
	if s.repo == nil {
		return fmt.Errorf("realtime repository not configured")
	}
	eventType, ok := event["type"].(string)
	if !ok {
		eventType = "broadcast"
	}
	return s.repo.BroadcastEvent(ctx, eventType, event)
}

// GetStreamMetrics returns metrics about real-time streams
func (s *RealTimeEventServiceImpl) GetStreamMetrics(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"status": "operational",
		"streams_active": 0,
		"events_per_second": 0,
	}, nil
}
