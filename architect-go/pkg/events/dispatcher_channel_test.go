package events

import (
	"testing"
	"time"

	"architect-go/pkg/websocket"
)

// mockHubForDispatcher implements HubInterface for testing
type mockHubForDispatcher struct {
	broadcastCalled         bool
	sendToUserIDCalled      bool
	broadcastToChannelCalled bool
	lastBroadcastMsg        *websocket.Message
	lastUserID              string
	lastChannelMsg          *websocket.Message
	lastChannel             string
}

func (m *mockHubForDispatcher) Broadcast(msg *websocket.Message) {
	m.broadcastCalled = true
	m.lastBroadcastMsg = msg
}

func (m *mockHubForDispatcher) SendToUserID(userID string, msg *websocket.Message) {
	m.sendToUserIDCalled = true
	m.lastUserID = userID
	m.lastBroadcastMsg = msg
}

func (m *mockHubForDispatcher) GetClients() []*websocket.Client {
	return nil
}

func (m *mockHubForDispatcher) BroadcastToChannel(channel string, msg *websocket.Message) {
	m.broadcastToChannelCalled = true
	m.lastChannel = channel
	m.lastChannelMsg = msg
}

// TestDispatchWithChannel verifies Channel set → BroadcastToChannel called
func TestDispatchWithChannel(t *testing.T) {
	mockHub := &mockHubForDispatcher{}
	dispatcher := NewHubEventDispatcher(mockHub)

	event := Event{
		Type:      "test.event",
		Channel:   "notifications",
		Data:      map[string]interface{}{"key": "value"},
		Timestamp: time.Now(),
	}

	dispatcher.Dispatch(event)

	if !mockHub.broadcastToChannelCalled {
		t.Fatal("Expected BroadcastToChannel to be called")
	}

	if mockHub.broadcastCalled {
		t.Fatal("Expected Broadcast NOT to be called")
	}

	if mockHub.sendToUserIDCalled {
		t.Fatal("Expected SendToUserID NOT to be called")
	}

	if mockHub.lastChannel != "notifications" {
		t.Errorf("Expected channel 'notifications', got '%s'", mockHub.lastChannel)
	}

	if mockHub.lastChannelMsg.Channel != "notifications" {
		t.Errorf("Expected message channel 'notifications', got '%s'", mockHub.lastChannelMsg.Channel)
	}
}

// TestDispatchWithUserID verifies UserID set → SendToUserID called (UserID takes priority)
func TestDispatchWithUserID(t *testing.T) {
	mockHub := &mockHubForDispatcher{}
	dispatcher := NewHubEventDispatcher(mockHub)

	event := Event{
		Type:      "test.event",
		UserID:    "user1",
		Channel:   "notifications", // Also set, but UserID takes priority
		Data:      map[string]interface{}{"key": "value"},
		Timestamp: time.Now(),
	}

	dispatcher.Dispatch(event)

	if !mockHub.sendToUserIDCalled {
		t.Fatal("Expected SendToUserID to be called")
	}

	if mockHub.broadcastCalled {
		t.Fatal("Expected Broadcast NOT to be called")
	}

	if mockHub.broadcastToChannelCalled {
		t.Fatal("Expected BroadcastToChannel NOT to be called")
	}

	if mockHub.lastUserID != "user1" {
		t.Errorf("Expected userID 'user1', got '%s'", mockHub.lastUserID)
	}

	if mockHub.lastBroadcastMsg.UserID != "user1" {
		t.Errorf("Expected message userID 'user1', got '%s'", mockHub.lastBroadcastMsg.UserID)
	}
}

// TestDispatchNoChannelNoUser verifies neither set → Broadcast called
func TestDispatchNoChannelNoUser(t *testing.T) {
	mockHub := &mockHubForDispatcher{}
	dispatcher := NewHubEventDispatcher(mockHub)

	event := Event{
		Type:      "test.event",
		Data:      map[string]interface{}{"key": "value"},
		Timestamp: time.Now(),
	}

	dispatcher.Dispatch(event)

	if !mockHub.broadcastCalled {
		t.Fatal("Expected Broadcast to be called")
	}

	if mockHub.sendToUserIDCalled {
		t.Fatal("Expected SendToUserID NOT to be called")
	}

	if mockHub.broadcastToChannelCalled {
		t.Fatal("Expected BroadcastToChannel NOT to be called")
	}

	if mockHub.lastBroadcastMsg.Type != "test.event" {
		t.Errorf("Expected message type 'test.event', got '%s'", mockHub.lastBroadcastMsg.Type)
	}
}
