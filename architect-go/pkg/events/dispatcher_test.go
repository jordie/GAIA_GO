package events

import (
	"testing"
	"time"

	"architect-go/pkg/websocket"
)

// MockHub implements a mock WebSocket hub for testing
type MockHub struct {
	broadcastedMessages []broadcastRecord
	unicastMessages     []unicastRecord
	clients             []*websocket.Client
}

type broadcastRecord struct {
	msg *websocket.Message
}

type unicastRecord struct {
	userID string
	msg    *websocket.Message
}

func (m *MockHub) Broadcast(msg *websocket.Message) {
	m.broadcastedMessages = append(m.broadcastedMessages, broadcastRecord{msg: msg})
}

func (m *MockHub) SendToUserID(userID string, msg *websocket.Message) {
	m.unicastMessages = append(m.unicastMessages, unicastRecord{userID: userID, msg: msg})
}

func (m *MockHub) GetClients() []*websocket.Client {
	return m.clients
}

func (m *MockHub) BroadcastToChannel(channel string, msg *websocket.Message) {
	// This is a no-op in the mock since we test broadcastToSubscribers directly
}

// Test helper: Create a mock client for testing
func createMockClient(id string, userID string, subscriptions []string) *websocket.Client {
	metadata := make(map[string]interface{})
	if len(subscriptions) > 0 {
		metadata["subscriptions"] = subscriptions
	}

	return &websocket.Client{
		ID:       id,
		UserID:   userID,
		Send:     make(chan *websocket.Message, 10),
		Metadata: metadata,
	}
}

func TestHubEventDispatcher_BroadcastToAll(t *testing.T) {
	// Setup
	mockHub := &MockHub{
		broadcastedMessages: []broadcastRecord{},
		unicastMessages:     []unicastRecord{},
		clients:             []*websocket.Client{},
	}

	dispatcher := &HubEventDispatcher{hub: mockHub}

	// Execute
	event := Event{
		Type: EventTaskCreated,
		Data: map[string]interface{}{"task_id": "123", "title": "Test Task"},
	}
	dispatcher.Dispatch(event)

	// Verify - message should be broadcast
	if len(mockHub.broadcastedMessages) != 1 {
		t.Errorf("Expected 1 broadcast, got %d", len(mockHub.broadcastedMessages))
	}
	if mockHub.broadcastedMessages[0].msg.Type != EventTaskCreated {
		t.Errorf("Expected type %s, got %s", EventTaskCreated, mockHub.broadcastedMessages[0].msg.Type)
	}
}

func TestHubEventDispatcher_SendToUser(t *testing.T) {
	// Setup
	userID := "user123"
	mockHub := &MockHub{
		broadcastedMessages: []broadcastRecord{},
		unicastMessages:     []unicastRecord{},
		clients:             []*websocket.Client{},
	}

	dispatcher := &HubEventDispatcher{hub: mockHub}

	// Execute
	event := Event{
		Type:   EventTaskCompleted,
		UserID: userID,
		Data:   map[string]interface{}{"task_id": "456"},
	}
	dispatcher.Dispatch(event)

	// Verify - message should be sent to user
	if len(mockHub.unicastMessages) != 1 {
		t.Errorf("Expected 1 unicast, got %d", len(mockHub.unicastMessages))
	}
	if mockHub.unicastMessages[0].userID != userID {
		t.Errorf("Expected userID %s, got %s", userID, mockHub.unicastMessages[0].userID)
	}
	if mockHub.unicastMessages[0].msg.Type != EventTaskCompleted {
		t.Errorf("Expected type %s, got %s", EventTaskCompleted, mockHub.unicastMessages[0].msg.Type)
	}
}

func TestHubEventDispatcher_BroadcastToChannel(t *testing.T) {
	// Setup
	channelName := "project-updates"
	client1 := createMockClient("client1", "user1", []string{channelName})
	client2 := createMockClient("client2", "user2", []string{})

	mockHub := &MockHub{
		broadcastedMessages: []broadcastRecord{},
		unicastMessages:     []unicastRecord{},
		clients:             []*websocket.Client{client1, client2},
	}

	dispatcher := &HubEventDispatcher{hub: mockHub}

	// Execute
	event := Event{
		Type:    EventProjectUpdated,
		Channel: channelName,
		Data:    map[string]interface{}{"project_id": "789"},
	}
	dispatcher.Dispatch(event)

	// Verify - only client1 (subscribed to channel) should receive message
	if len(client1.Send) == 0 {
		t.Error("Expected message on subscribed client1")
	}
	if len(client2.Send) > 0 {
		t.Error("Expected no message on non-subscribed client2")
	}
}

func TestBroadcastToSubscribers_NoSubscribers(t *testing.T) {
	// Setup
	client1 := createMockClient("client1", "user1", []string{})  // no subscriptions
	client2 := createMockClient("client2", "user2", []string{}) // no subscriptions

	mockHub := &MockHub{
		broadcastedMessages: []broadcastRecord{},
		unicastMessages:     []unicastRecord{},
		clients:             []*websocket.Client{client1, client2},
	}

	dispatcher := &HubEventDispatcher{hub: mockHub}

	// Execute
	event := Event{
		Type:    EventRealTimePublish,
		Channel: "some-channel",
		Data:    map[string]interface{}{"message": "test"},
	}
	dispatcher.Dispatch(event)

	// Verify - no messages should be queued
	if len(client1.Send) > 0 {
		t.Error("Expected no messages when no clients subscribe to channel")
	}
	if len(client2.Send) > 0 {
		t.Error("Expected no messages when no clients subscribe to channel")
	}
}

func TestBroadcastToSubscribers_MultipleSubscribers(t *testing.T) {
	// Setup
	channelName := "notifications"
	client1 := createMockClient("client1", "user1", []string{channelName})
	client2 := createMockClient("client2", "user2", []string{channelName})
	client3 := createMockClient("client3", "user3", []string{"other-channel"})

	mockHub := &MockHub{
		broadcastedMessages: []broadcastRecord{},
		unicastMessages:     []unicastRecord{},
		clients:             []*websocket.Client{client1, client2, client3},
	}

	dispatcher := &HubEventDispatcher{hub: mockHub}

	// Execute
	event := Event{
		Type:    EventTaskUpdated,
		Channel: channelName,
		Data:    map[string]interface{}{"task_id": "999"},
	}
	dispatcher.Dispatch(event)

	// Verify - client1 and client2 should receive, client3 should not
	if len(client1.Send) == 0 {
		t.Error("Expected message on client1 (subscribed to channel)")
	}
	if len(client2.Send) == 0 {
		t.Error("Expected message on client2 (subscribed to channel)")
	}
	if len(client3.Send) > 0 {
		t.Error("Expected no message on client3 (not subscribed to channel)")
	}
}

func TestDispatcher_NilHub(t *testing.T) {
	// Setup - nil hub
	dispatcher := &HubEventDispatcher{hub: nil}

	// Execute - should not panic
	event := Event{
		Type: EventTaskCreated,
		Data: map[string]interface{}{"task_id": "123"},
	}

	// This should handle nil gracefully
	dispatcher.Dispatch(event)

	// Verify - no panic occurred
	t.Log("Nil hub handled gracefully")
}

func TestIsClientSubscribedToChannel_WhenSubscribed(t *testing.T) {
	// Setup
	dispatcher := &HubEventDispatcher{hub: nil}
	client := createMockClient("c1", "u1", []string{"channel-a", "channel-b"})

	// Execute & Verify
	if !dispatcher.isClientSubscribedToChannel(client, "channel-a") {
		t.Error("Expected client to be subscribed to channel-a")
	}
	if !dispatcher.isClientSubscribedToChannel(client, "channel-b") {
		t.Error("Expected client to be subscribed to channel-b")
	}
}

func TestIsClientSubscribedToChannel_WhenNotSubscribed(t *testing.T) {
	// Setup
	dispatcher := &HubEventDispatcher{hub: nil}
	client := createMockClient("c1", "u1", []string{"channel-a"})

	// Execute & Verify
	if dispatcher.isClientSubscribedToChannel(client, "channel-b") {
		t.Error("Expected client NOT to be subscribed to channel-b")
	}
}

func TestIsClientSubscribedToChannel_NoMetadata(t *testing.T) {
	// Setup
	dispatcher := &HubEventDispatcher{hub: nil}
	client := &websocket.Client{
		ID:       "c1",
		UserID:   "u1",
		Send:     make(chan *websocket.Message, 1),
		Metadata: nil,
	}

	// Execute & Verify
	if dispatcher.isClientSubscribedToChannel(client, "any-channel") {
		t.Error("Expected no subscription with nil metadata")
	}
}

func TestIsClientSubscribedToChannel_NilClient(t *testing.T) {
	// Setup
	dispatcher := &HubEventDispatcher{hub: nil}

	// Execute & Verify - should not panic
	result := dispatcher.isClientSubscribedToChannel(nil, "channel")
	if result {
		t.Error("Expected false for nil client")
	}
}

func TestEvent_AllFields(t *testing.T) {
	// Verify Event struct can be populated with all fields
	event := Event{
		Type:    EventProjectCreated,
		Channel: "projects",
		UserID:  "user123",
		Data: map[string]interface{}{
			"id":   "proj-456",
			"name": "My Project",
		},
	}

	if event.Type != EventProjectCreated {
		t.Errorf("Expected type %s, got %s", EventProjectCreated, event.Type)
	}
	if event.Channel != "projects" {
		t.Errorf("Expected channel 'projects', got %s", event.Channel)
	}
	if event.UserID != "user123" {
		t.Errorf("Expected userID 'user123', got %s", event.UserID)
	}

	data := event.Data.(map[string]interface{})
	if data["id"] != "proj-456" {
		t.Error("Expected project id in data")
	}
}

func TestDispatcher_MultipleEvents(t *testing.T) {
	// Setup
	mockHub := &MockHub{
		broadcastedMessages: []broadcastRecord{},
		unicastMessages:     []unicastRecord{},
		clients:             []*websocket.Client{},
	}

	dispatcher := &HubEventDispatcher{hub: mockHub}

	events := []Event{
		{Type: EventTaskCreated, Data: map[string]interface{}{"id": "t1"}},
		{Type: EventTaskUpdated, Data: map[string]interface{}{"id": "t2"}},
		{Type: EventProjectCreated, Data: map[string]interface{}{"id": "p1"}},
	}

	// Execute - dispatch multiple events
	for _, evt := range events {
		dispatcher.Dispatch(evt)
	}

	// Verify - all events dispatched
	if len(mockHub.broadcastedMessages) != 3 {
		t.Errorf("Expected 3 broadcasts, got %d", len(mockHub.broadcastedMessages))
	}
}

func TestMessage_Timestamp(t *testing.T) {
	// Setup
	mockHub := &MockHub{
		broadcastedMessages: []broadcastRecord{},
		unicastMessages:     []unicastRecord{},
		clients:             []*websocket.Client{},
	}

	dispatcher := &HubEventDispatcher{hub: mockHub}

	// Execute
	before := time.Now()
	event := Event{
		Type: EventTaskCreated,
		Data: map[string]interface{}{"id": "t1"},
	}
	dispatcher.Dispatch(event)
	after := time.Now()

	// Verify - message timestamp should be between before and after
	msg := mockHub.broadcastedMessages[0].msg
	if msg.Timestamp.Before(before) || msg.Timestamp.After(after) {
		t.Error("Expected message timestamp to be recent")
	}
}
