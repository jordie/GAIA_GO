package services

import (
	"context"
	"testing"

	"architect-go/pkg/websocket"
)

// mockPushHub implements realtimePushHub for testing
type mockPushHub struct {
	broadcastCalled         bool
	broadcastToChannelCalled bool
	lastBroadcastMsg        *websocket.Message
	lastChannelMsg          *websocket.Message
	lastChannel             string
}

func (m *mockPushHub) BroadcastToChannel(channel string, msg *websocket.Message) {
	m.broadcastToChannelCalled = true
	m.lastChannel = channel
	m.lastChannelMsg = msg
}

func (m *mockPushHub) Broadcast(msg *websocket.Message) {
	m.broadcastCalled = true
	m.lastBroadcastMsg = msg
}

// mockRepository implements RealTimeRepository for testing
type mockRealTimeRepository struct {
	storeMessageCalled bool
	getChannelSubscribersCalled bool
	lastStoredMessage  map[string]interface{}
	subscribers        []string
}

func (m *mockRealTimeRepository) StoreMessage(ctx context.Context, message map[string]interface{}) error {
	m.storeMessageCalled = true
	m.lastStoredMessage = message
	return nil
}

func (m *mockRealTimeRepository) GetChannelSubscribers(ctx context.Context, channel string) ([]string, error) {
	m.getChannelSubscribersCalled = true
	return m.subscribers, nil
}

func (m *mockRealTimeRepository) CreateSubscription(ctx context.Context, userID, channel string) error {
	return nil
}

func (m *mockRealTimeRepository) RemoveSubscription(ctx context.Context, userID, channel string) error {
	return nil
}

func (m *mockRealTimeRepository) GetUserSubscriptions(ctx context.Context, userID string) ([]string, error) {
	return nil, nil
}

func (m *mockRealTimeRepository) GetOnlineUsers(ctx context.Context) ([]string, error) {
	return nil, nil
}

func (m *mockRealTimeRepository) GetPresence(ctx context.Context, userID string) (map[string]interface{}, error) {
	return nil, nil
}

func (m *mockRealTimeRepository) CreatePresenceRecord(ctx context.Context, userID, status string) error {
	return nil
}

func (m *mockRealTimeRepository) GetPendingMessages(ctx context.Context, userID string, limit int) ([]map[string]interface{}, error) {
	return nil, nil
}

func (m *mockRealTimeRepository) RemoveMessage(ctx context.Context, eventID string) error {
	return nil
}

// TestPublishToChannelPushesLive verifies PublishToChannel calls hub.BroadcastToChannel
func TestPublishToChannelPushesLive(t *testing.T) {
	mockRepo := &mockRealTimeRepository{
		subscribers: []string{"user1", "user2"},
	}
	mockHub := &mockPushHub{}

	service := NewRealTimeEventServiceWithHub(mockRepo, mockHub)

	ctx := context.Background()
	err := service.PublishToChannel(ctx, "test-channel", "test.event", map[string]interface{}{"data": "value"})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if !mockRepo.storeMessageCalled {
		t.Fatal("Expected StoreMessage to be called")
	}

	if !mockHub.broadcastToChannelCalled {
		t.Fatal("Expected BroadcastToChannel to be called")
	}

	if mockHub.lastChannel != "test-channel" {
		t.Errorf("Expected channel 'test-channel', got '%s'", mockHub.lastChannel)
	}

	if mockHub.lastChannelMsg.Type != "realtime.publish" {
		t.Errorf("Expected message type 'realtime.publish', got '%s'", mockHub.lastChannelMsg.Type)
	}

	if mockHub.lastChannelMsg.Channel != "test-channel" {
		t.Errorf("Expected message channel 'test-channel', got '%s'", mockHub.lastChannelMsg.Channel)
	}
}

// TestBroadcastEventPushesLive verifies BroadcastEvent calls hub.Broadcast
func TestBroadcastEventPushesLive(t *testing.T) {
	mockRepo := &mockRealTimeRepository{}
	mockHub := &mockPushHub{}

	service := NewRealTimeEventServiceWithHub(mockRepo, mockHub)

	ctx := context.Background()
	err := service.BroadcastEvent(ctx, "test.broadcast", map[string]interface{}{"data": "value"})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if !mockRepo.storeMessageCalled {
		t.Fatal("Expected StoreMessage to be called")
	}

	if !mockHub.broadcastCalled {
		t.Fatal("Expected Broadcast to be called")
	}

	if mockHub.lastBroadcastMsg.Type != "realtime.broadcast" {
		t.Errorf("Expected message type 'realtime.broadcast', got '%s'", mockHub.lastBroadcastMsg.Type)
	}
}

// TestPublishNilHubNoPanic verifies Nil hub → no panic; DB write still happens
func TestPublishNilHubNoPanic(t *testing.T) {
	mockRepo := &mockRealTimeRepository{
		subscribers: []string{"user1"},
	}

	// Create service with nil hub (backward compatible)
	service := NewRealTimeEventService(mockRepo)

	ctx := context.Background()

	// This should not panic even without hub
	err := service.PublishToChannel(ctx, "test-channel", "test.event", map[string]interface{}{"data": "value"})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if !mockRepo.storeMessageCalled {
		t.Fatal("Expected StoreMessage to be called even with nil hub")
	}

	// Test passes if no panic occurred
}

// TestBroadcastNilHubNoPanic verifies Nil hub → no panic; DB write still happens
func TestBroadcastNilHubNoPanic(t *testing.T) {
	mockRepo := &mockRealTimeRepository{}

	// Create service with nil hub (backward compatible)
	service := NewRealTimeEventService(mockRepo)

	ctx := context.Background()

	// This should not panic even without hub
	err := service.BroadcastEvent(ctx, "test.broadcast", map[string]interface{}{"data": "value"})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if !mockRepo.storeMessageCalled {
		t.Fatal("Expected StoreMessage to be called even with nil hub")
	}

	// Test passes if no panic occurred
}
