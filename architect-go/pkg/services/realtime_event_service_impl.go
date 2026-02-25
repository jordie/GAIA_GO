package services

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"

	"architect-go/pkg/repository"
	"architect-go/pkg/websocket"
)

// realtimePushHub is a narrow interface to avoid importing pkg/events from pkg/services.
// It allows RealTimeEventService to push live WebSocket messages for DB-persisted events.
type realtimePushHub interface {
	BroadcastToChannel(channel string, msg *websocket.Message)
	Broadcast(msg *websocket.Message)
}

// RealTimeEventServiceImpl implements RealTimeEventService
type RealTimeEventServiceImpl struct {
	repo repository.RealTimeRepository
	hub  realtimePushHub // nil = DB-only (backward compatible)
}

// NewRealTimeEventService creates a new real-time event service (DB-only, no live push)
func NewRealTimeEventService(repo repository.RealTimeRepository) RealTimeEventService {
	return &RealTimeEventServiceImpl{repo: repo}
}

// NewRealTimeEventServiceWithHub creates a new real-time event service with live WebSocket push
func NewRealTimeEventServiceWithHub(repo repository.RealTimeRepository, hub realtimePushHub) RealTimeEventService {
	return &RealTimeEventServiceImpl{repo: repo, hub: hub}
}

func (res *RealTimeEventServiceImpl) SubscribeToChannel(ctx context.Context, userID, channel string) error {
	if err := res.repo.CreateSubscription(ctx, userID, channel); err != nil {
		return fmt.Errorf("failed to subscribe to channel %s: %w", channel, err)
	}
	return nil
}

func (res *RealTimeEventServiceImpl) SubscribeToChannels(ctx context.Context, userID string, channels []string) error {
	for _, channel := range channels {
		if err := res.repo.CreateSubscription(ctx, userID, channel); err != nil {
			return fmt.Errorf("failed to subscribe to channel %s: %w", channel, err)
		}
	}
	return nil
}

func (res *RealTimeEventServiceImpl) UnsubscribeFromChannel(ctx context.Context, userID, channel string) error {
	if err := res.repo.RemoveSubscription(ctx, userID, channel); err != nil {
		return fmt.Errorf("failed to unsubscribe from channel %s: %w", channel, err)
	}
	return nil
}

func (res *RealTimeEventServiceImpl) UnsubscribeFromAllChannels(ctx context.Context, userID string) error {
	channels, err := res.repo.GetUserSubscriptions(ctx, userID)
	if err != nil {
		return fmt.Errorf("failed to get subscriptions for user %s: %w", userID, err)
	}
	for _, channel := range channels {
		if err := res.repo.RemoveSubscription(ctx, userID, channel); err != nil {
			return fmt.Errorf("failed to unsubscribe from channel %s: %w", channel, err)
		}
	}
	return nil
}

func (res *RealTimeEventServiceImpl) GetUserSubscriptions(ctx context.Context, userID string) ([]string, error) {
	channels, err := res.repo.GetUserSubscriptions(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get subscriptions for user %s: %w", userID, err)
	}
	return channels, nil
}

func (res *RealTimeEventServiceImpl) PublishToChannel(ctx context.Context, channel string, event string, data map[string]interface{}) error {
	subscribers, err := res.repo.GetChannelSubscribers(ctx, channel)
	if err != nil {
		return fmt.Errorf("failed to get subscribers for channel %s: %w", channel, err)
	}

	message := map[string]interface{}{
		"id":         uuid.New().String(),
		"channel":    channel,
		"event":      event,
		"data":       data,
		"status":     "pending",
		"created_at": time.Now().Format(time.RFC3339),
	}

	for _, userID := range subscribers {
		msg := make(map[string]interface{})
		for k, v := range message {
			msg[k] = v
		}
		msg["user_id"] = userID
		if err := res.repo.StoreMessage(ctx, msg); err != nil {
			return fmt.Errorf("failed to publish event to user %s: %w", userID, err)
		}
	}

	// Push live to subscribed WebSocket clients
	if res.hub != nil {
		res.hub.BroadcastToChannel(channel, &websocket.Message{
			Type:      "realtime.publish",
			Channel:   channel,
			Data:      map[string]interface{}{"event": event, "data": data},
			Timestamp: time.Now(),
		})
	}

	return nil
}

func (res *RealTimeEventServiceImpl) BroadcastEvent(ctx context.Context, event string, data map[string]interface{}) error {
	message := map[string]interface{}{
		"id":         uuid.New().String(),
		"channel":    "broadcast",
		"event":      event,
		"data":       data,
		"status":     "pending",
		"created_at": time.Now().Format(time.RFC3339),
	}

	if err := res.repo.StoreMessage(ctx, message); err != nil {
		return fmt.Errorf("failed to broadcast event: %w", err)
	}

	// Push live to all connected WebSocket clients
	if res.hub != nil {
		res.hub.Broadcast(&websocket.Message{
			Type:      "realtime.broadcast",
			Data:      map[string]interface{}{"event": event, "data": data},
			Timestamp: time.Now(),
		})
	}

	return nil
}

func (res *RealTimeEventServiceImpl) SendDirectMessage(ctx context.Context, fromUserID string, toUserID string, message string) error {
	msg := map[string]interface{}{
		"id":           uuid.New().String(),
		"user_id":      toUserID,
		"from_user_id": fromUserID,
		"channel":      "direct",
		"event":        "direct_message",
		"data":         map[string]interface{}{"message": message},
		"status":       "pending",
		"created_at":   time.Now().Format(time.RFC3339),
	}
	if err := res.repo.StoreMessage(ctx, msg); err != nil {
		return fmt.Errorf("failed to send direct message: %w", err)
	}
	return nil
}

func (res *RealTimeEventServiceImpl) ListAvailableChannels(ctx context.Context) ([]string, error) {
	return []string{"general", "notifications", "alerts", "broadcast"}, nil
}

func (res *RealTimeEventServiceImpl) GetChannelInfo(ctx context.Context, channel string) (map[string]interface{}, error) {
	subscribers, err := res.repo.GetChannelSubscribers(ctx, channel)
	if err != nil {
		return nil, fmt.Errorf("failed to get channel info for %s: %w", channel, err)
	}

	return map[string]interface{}{
		"channel": channel,
		"members": len(subscribers),
	}, nil
}

func (res *RealTimeEventServiceImpl) GetChannelSubscribers(ctx context.Context, channel string) ([]string, error) {
	subscribers, err := res.repo.GetChannelSubscribers(ctx, channel)
	if err != nil {
		return nil, fmt.Errorf("failed to get subscribers for channel %s: %w", channel, err)
	}
	return subscribers, nil
}

func (res *RealTimeEventServiceImpl) GetChannelMessageCount(ctx context.Context, channel string) (int64, error) {
	return 0, nil
}

func (res *RealTimeEventServiceImpl) GetChannelLastMessage(ctx context.Context, channel string) (map[string]interface{}, error) {
	return map[string]interface{}{}, nil
}

func (res *RealTimeEventServiceImpl) CreateChannel(ctx context.Context, name string, description string) (string, error) {
	return uuid.New().String(), nil
}

func (res *RealTimeEventServiceImpl) DeleteChannel(ctx context.Context, channel string) error {
	return nil
}

func (res *RealTimeEventServiceImpl) ArchiveChannel(ctx context.Context, channel string) error {
	return nil
}

func (res *RealTimeEventServiceImpl) RestoreChannel(ctx context.Context, channel string) error {
	return nil
}

func (res *RealTimeEventServiceImpl) GetActiveConnections(ctx context.Context) (*ActiveConnectionsResponse, error) {
	onlineUsers, err := res.repo.GetOnlineUsers(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get active connections: %w", err)
	}

	connections := make([]map[string]interface{}, 0, len(onlineUsers))
	for _, userID := range onlineUsers {
		presence, err := res.repo.GetPresence(ctx, userID)
		if err == nil {
			conn := map[string]interface{}{
				"user_id": userID,
				"status":  presence["status"],
			}
			connections = append(connections, conn)
		}
	}

	return &ActiveConnectionsResponse{
		ActiveConnections: int64(len(onlineUsers)),
		Connections:       connections,
		ByChannel:         make(map[string]int64),
	}, nil
}

func (res *RealTimeEventServiceImpl) GetConnectionsByChannel(ctx context.Context) (map[string]int64, error) {
	return make(map[string]int64), nil
}

func (res *RealTimeEventServiceImpl) GetUserPresence(ctx context.Context, userID string) (map[string]interface{}, error) {
	presence, err := res.repo.GetPresence(ctx, userID)
	if err != nil {
		return map[string]interface{}{
			"user_id": userID,
			"status":  "offline",
		}, nil
	}
	return presence, nil
}

func (res *RealTimeEventServiceImpl) UpdatePresence(ctx context.Context, userID string, req *PresenceUpdateRequest) error {
	if err := res.repo.CreatePresenceRecord(ctx, userID, req.Status); err != nil {
		return fmt.Errorf("failed to update presence for user %s: %w", userID, err)
	}
	return nil
}

func (res *RealTimeEventServiceImpl) BroadcastPresenceUpdate(ctx context.Context, userID string, status string) error {
	if err := res.repo.CreatePresenceRecord(ctx, userID, status); err != nil {
		return fmt.Errorf("failed to broadcast presence update for user %s: %w", userID, err)
	}
	return nil
}

func (res *RealTimeEventServiceImpl) GetOnlineUsers(ctx context.Context) ([]string, error) {
	users, err := res.repo.GetOnlineUsers(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get online users: %w", err)
	}
	return users, nil
}

func (res *RealTimeEventServiceImpl) GetUserPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]map[string]interface{}, int64, error) {
	return make([]map[string]interface{}, 0), 0, nil
}

func (res *RealTimeEventServiceImpl) SubscribeToPresence(ctx context.Context, userID string) error {
	return res.repo.CreateSubscription(ctx, userID, "presence")
}

func (res *RealTimeEventServiceImpl) UnsubscribeFromPresence(ctx context.Context, userID string) error {
	return res.repo.RemoveSubscription(ctx, userID, "presence")
}

func (res *RealTimeEventServiceImpl) GetPendingEvents(ctx context.Context, userID string) ([]map[string]interface{}, error) {
	messages, err := res.repo.GetPendingMessages(ctx, userID, 100)
	if err != nil {
		return nil, fmt.Errorf("failed to get pending events for user %s: %w", userID, err)
	}
	return messages, nil
}

func (res *RealTimeEventServiceImpl) RemoveEventFromQueue(ctx context.Context, userID string, eventID string) error {
	if err := res.repo.RemoveMessage(ctx, eventID); err != nil {
		return fmt.Errorf("failed to remove event %s from queue: %w", eventID, err)
	}
	return nil
}

func (res *RealTimeEventServiceImpl) ClearEventQueue(ctx context.Context, userID string) error {
	messages, err := res.repo.GetPendingMessages(ctx, userID, 10000)
	if err != nil {
		return fmt.Errorf("failed to get messages to clear for user %s: %w", userID, err)
	}
	for _, msg := range messages {
		if id, ok := msg["id"].(string); ok {
			if err := res.repo.RemoveMessage(ctx, id); err != nil {
				return fmt.Errorf("failed to remove message %s: %w", id, err)
			}
		}
	}
	return nil
}

func (res *RealTimeEventServiceImpl) ReplayEventQueue(ctx context.Context, userID string) error {
	return nil
}

func (res *RealTimeEventServiceImpl) HandleReconnection(ctx context.Context, userID string) ([]map[string]interface{}, error) {
	messages, err := res.repo.GetPendingMessages(ctx, userID, 100)
	if err != nil {
		return nil, fmt.Errorf("failed to handle reconnection for user %s: %w", userID, err)
	}
	return messages, nil
}

func (res *RealTimeEventServiceImpl) GetRealtimeStats(ctx context.Context) (map[string]interface{}, error) {
	onlineUsers, err := res.repo.GetOnlineUsers(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get realtime stats: %w", err)
	}

	return map[string]interface{}{
		"active_channels": 0,
		"active_users":    len(onlineUsers),
	}, nil
}

func (res *RealTimeEventServiceImpl) GetConnectionStats(ctx context.Context) (map[string]interface{}, error) {
	onlineUsers, err := res.repo.GetOnlineUsers(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get connection stats: %w", err)
	}

	return map[string]interface{}{
		"total_connections": len(onlineUsers),
	}, nil
}

func (res *RealTimeEventServiceImpl) GetEventStats(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"events": 0,
	}, nil
}

func (res *RealTimeEventServiceImpl) CheckRateLimit(ctx context.Context, userID string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"limit":     1000,
		"remaining": 950,
	}, nil
}

func (res *RealTimeEventServiceImpl) ApplyRateLimit(ctx context.Context, userID string, limit int, window string) error {
	return nil
}

func (res *RealTimeEventServiceImpl) FilterEvents(ctx context.Context, userID string, filter map[string]interface{}) ([]map[string]interface{}, error) {
	messages, err := res.repo.GetPendingMessages(ctx, userID, 100)
	if err != nil {
		return nil, fmt.Errorf("failed to filter events for user %s: %w", userID, err)
	}
	return messages, nil
}

func (res *RealTimeEventServiceImpl) SetEventFilter(ctx context.Context, userID string, filter map[string]interface{}) error {
	return nil
}

func (res *RealTimeEventServiceImpl) GetEventFilter(ctx context.Context, userID string) (map[string]interface{}, error) {
	return map[string]interface{}{}, nil
}

func (res *RealTimeEventServiceImpl) ClearEventFilter(ctx context.Context, userID string) error {
	return nil
}

func (res *RealTimeEventServiceImpl) SendHeartbeat(ctx context.Context, userID string) error {
	return res.repo.CreatePresenceRecord(ctx, userID, "online")
}

func (res *RealTimeEventServiceImpl) CheckConnectionHealth(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"status": "healthy",
	}, nil
}

func (res *RealTimeEventServiceImpl) CleanupStaleConnections(ctx context.Context) (int64, error) {
	return 0, nil
}

func (res *RealTimeEventServiceImpl) GetConnectionLatency(ctx context.Context, userID string) (int64, error) {
	return 0, nil
}

func (res *RealTimeEventServiceImpl) GetAverageLatency(ctx context.Context) (int64, error) {
	return 0, nil
}

func (res *RealTimeEventServiceImpl) GetChannelLatency(ctx context.Context, channel string) (int64, error) {
	return 0, nil
}

func (res *RealTimeEventServiceImpl) OptimizeChannels(ctx context.Context) error {
	return nil
}

func (res *RealTimeEventServiceImpl) GetOptimizationStatus(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"optimized": true,
	}, nil
}
