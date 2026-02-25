package events

import (
<<<<<<< HEAD
	"sync"
=======
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
	"testing"
	"time"

	"architect-go/pkg/websocket"
)

<<<<<<< HEAD
// mockHub implements HubInterface for testing
type mockHub struct {
	broadcastCalls         []*websocket.Message
	sendToUserIDCalls      map[string][]*websocket.Message
	broadcastToChannelCalls map[string][]*websocket.Message
	mu                     sync.Mutex
}

func (m *mockHub) Broadcast(msg *websocket.Message) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.broadcastCalls = append(m.broadcastCalls, msg)
}

func (m *mockHub) SendToUserID(userID string, msg *websocket.Message) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.sendToUserIDCalls == nil {
		m.sendToUserIDCalls = make(map[string][]*websocket.Message)
	}
	m.sendToUserIDCalls[userID] = append(m.sendToUserIDCalls[userID], msg)
}

func (m *mockHub) GetClients() []*websocket.Client {
	return nil
}

func (m *mockHub) BroadcastToChannel(channel string, msg *websocket.Message) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.broadcastToChannelCalls == nil {
		m.broadcastToChannelCalls = make(map[string][]*websocket.Message)
	}
	m.broadcastToChannelCalls[channel] = append(m.broadcastToChannelCalls[channel], msg)
}

// TestDispatchBroadcast tests broadcasting events to all clients
func TestDispatchBroadcast(t *testing.T) {
	hub := &mockHub{
		sendToUserIDCalls: make(map[string][]*websocket.Message),
		broadcastToChannelCalls: make(map[string][]*websocket.Message),
	}
	dispatcher := NewHubEventDispatcher(hub)

	// No Channel set, so it will use Broadcast
	event := Event{
		Type:    "test.event",
		Data:    map[string]string{"message": "hello"},
	}

	dispatcher.Dispatch(event)

	if len(hub.broadcastCalls) != 1 {
		t.Errorf("expected 1 broadcast call, got %d", len(hub.broadcastCalls))
	}

	if len(hub.sendToUserIDCalls) != 0 {
		t.Errorf("expected 0 unicast calls for broadcast, got %d", len(hub.sendToUserIDCalls))
	}

	msg := hub.broadcastCalls[0]
	if msg.Type != "test.event" {
		t.Errorf("expected message type test.event, got %s", msg.Type)
	}
}

// TestDispatchUnicast tests sending events to specific user
func TestDispatchUnicast(t *testing.T) {
	hub := &mockHub{
		sendToUserIDCalls: make(map[string][]*websocket.Message),
		broadcastToChannelCalls: make(map[string][]*websocket.Message),
	}
	dispatcher := NewHubEventDispatcher(hub)

	event := Event{
		Type:    "user.notification",
		Channel: "notifications",
		UserID:  "user123", // UserID takes priority
		Data:    map[string]string{"alert": "test alert"},
	}

	dispatcher.Dispatch(event)

	if len(hub.broadcastCalls) != 0 {
		t.Errorf("expected 0 broadcast calls for unicast, got %d", len(hub.broadcastCalls))
	}

	if len(hub.sendToUserIDCalls) != 1 {
		t.Errorf("expected 1 user in sendToUserIDCalls, got %d", len(hub.sendToUserIDCalls))
	}

	if _, ok := hub.sendToUserIDCalls["user123"]; !ok {
		t.Error("expected user123 in sendToUserIDCalls")
	}

	msg := hub.sendToUserIDCalls["user123"][0]
	if msg.Type != "user.notification" {
		t.Errorf("expected message type user.notification, got %s", msg.Type)
	}
	if msg.UserID != "user123" {
		t.Errorf("expected user ID user123, got %s", msg.UserID)
	}
}

// TestDispatchTimestamp tests that events get timestamped
func TestDispatchTimestamp(t *testing.T) {
	hub := &mockHub{
		sendToUserIDCalls: make(map[string][]*websocket.Message),
		broadcastToChannelCalls: make(map[string][]*websocket.Message),
	}
	dispatcher := NewHubEventDispatcher(hub)

	before := time.Now()
	event := Event{
		Type:    "timestamp.test",
		Data:    "data",
=======
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
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
	}
	dispatcher.Dispatch(event)
	after := time.Now()

<<<<<<< HEAD
	msg := hub.broadcastCalls[0]
	if msg.Timestamp.Before(before) || msg.Timestamp.After(after) {
		t.Error("message timestamp not set correctly")
	}
}

// TestDispatchPreserveTimestamp tests that provided timestamps are preserved
func TestDispatchPreserveTimestamp(t *testing.T) {
	hub := &mockHub{
		sendToUserIDCalls: make(map[string][]*websocket.Message),
		broadcastToChannelCalls: make(map[string][]*websocket.Message),
	}
	dispatcher := NewHubEventDispatcher(hub)

	customTime := time.Date(2025, 2, 18, 12, 0, 0, 0, time.UTC)
	event := Event{
		Type:      "timestamp.test",
		Timestamp: customTime,
		Data:      "data",
	}
	dispatcher.Dispatch(event)

	msg := hub.broadcastCalls[0]
	if msg.Timestamp != customTime {
		t.Errorf("expected timestamp %v, got %v", customTime, msg.Timestamp)
	}
}

// TestDispatchMessageContent tests that event data is preserved in message
func TestDispatchMessageContent(t *testing.T) {
	hub := &mockHub{
		sendToUserIDCalls: make(map[string][]*websocket.Message),
		broadcastToChannelCalls: make(map[string][]*websocket.Message),
	}
	dispatcher := NewHubEventDispatcher(hub)

	testData := map[string]interface{}{
		"id":    "123",
		"count": 42,
		"active": true,
	}

	event := Event{
		Type:    "data.test",
		Data:    testData,
	}
	dispatcher.Dispatch(event)

	msg := hub.broadcastCalls[0]
	// Check if data was preserved (reference equality since it's the same object)
	if msg.Data == nil {
		t.Error("event data was nil in message")
	}
	if data, ok := msg.Data.(map[string]interface{}); !ok {
		t.Error("event data not stored correctly in message")
	} else if data["id"] != "123" || data["count"] != 42 || data["active"] != true {
		t.Error("event data was not preserved correctly in message")
=======
	// Verify - message timestamp should be between before and after
	msg := mockHub.broadcastedMessages[0].msg
	if msg.Timestamp.Before(before) || msg.Timestamp.After(after) {
		t.Error("Expected message timestamp to be recent")
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
	}
}
