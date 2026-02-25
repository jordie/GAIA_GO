package websocket

import (
	"testing"
	"time"
)

// TestBroadcastToChannelDelivered verifies subscribed client receives message
func TestBroadcastToChannelDelivered(t *testing.T) {
	hub := &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client, 256),
		unregister: make(chan *Client, 256),
		broadcast:  make(chan *BroadcastMessage, 256),
		unicast:    make(chan *UnicastMessage, 256),
	}

	// Create client with nil connection (not used in this test)
	client := &Client{
		ID:       "test-client",
		Hub:      hub,
		Conn:     nil,
		Send:     make(chan *Message, 10),
		UserID:   "user1",
		Metadata: make(map[string]interface{}),
	}

	// Subscribe to channel
	client.SetMetadata("subscriptions", []string{"notifications", "updates"})

	// Register client directly
	hub.mu.Lock()
	hub.clients[client.ID] = client
	hub.mu.Unlock()

	// Send message to channel
	msg := &Message{
		Type:      "test.message",
		Data:      map[string]interface{}{"key": "value"},
		Channel:   "notifications",
		Timestamp: time.Now(),
	}

	hub.BroadcastToChannel("notifications", msg)

	// Check that message was received
	select {
	case received := <-client.Send:
		if received.Type != "test.message" {
			t.Errorf("Expected message type 'test.message', got '%s'", received.Type)
		}
		if received.Channel != "notifications" {
			t.Errorf("Expected channel 'notifications', got '%s'", received.Channel)
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Expected to receive message, but channel was empty")
	}
}

// TestBroadcastToChannelUnsubscribedSkipped verifies unsubscribed client does NOT receive message
func TestBroadcastToChannelUnsubscribedSkipped(t *testing.T) {
	hub := &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client, 256),
		unregister: make(chan *Client, 256),
		broadcast:  make(chan *BroadcastMessage, 256),
		unicast:    make(chan *UnicastMessage, 256),
	}

	// Create client with nil connection (not used in this test)
	client := &Client{
		ID:       "test-client",
		Hub:      hub,
		Conn:     nil,
		Send:     make(chan *Message, 10),
		UserID:   "user1",
		Metadata: make(map[string]interface{}),
	}

	// Subscribe to different channel only
	client.SetMetadata("subscriptions", []string{"alerts"})

	// Register client manually
	hub.mu.Lock()
	hub.clients[client.ID] = client
	hub.mu.Unlock()

	// Send message to different channel
	msg := &Message{
		Type:      "test.message",
		Data:      map[string]interface{}{"key": "value"},
		Channel:   "notifications",
		Timestamp: time.Now(),
	}

	hub.BroadcastToChannel("notifications", msg)

	// Check that message was NOT received
	select {
	case <-client.Send:
		t.Fatal("Expected no message to be received, but received one")
	case <-time.After(100 * time.Millisecond):
		// Expected: no message received
	}
}

// TestBroadcastToChannelSetsChannelField verifies msg.Channel field is preserved
func TestBroadcastToChannelSetsChannelField(t *testing.T) {
	hub := &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client, 256),
		unregister: make(chan *Client, 256),
		broadcast:  make(chan *BroadcastMessage, 256),
		unicast:    make(chan *UnicastMessage, 256),
	}

	// Create client with nil connection (not used in this test)
	client := &Client{
		ID:       "test-client",
		Hub:      hub,
		Conn:     nil,
		Send:     make(chan *Message, 10),
		UserID:   "user1",
		Metadata: make(map[string]interface{}),
	}

	// Subscribe to channel
	client.SetMetadata("subscriptions", []string{"general"})

	// Register client manually
	hub.mu.Lock()
	hub.clients[client.ID] = client
	hub.mu.Unlock()

	// Send message with Channel field set
	originalChannel := "general"
	msg := &Message{
		Type:      "test.message",
		Data:      map[string]interface{}{"key": "value"},
		Channel:   originalChannel,
		Timestamp: time.Now(),
	}

	hub.BroadcastToChannel(originalChannel, msg)

	// Check that Channel field is preserved
	select {
	case received := <-client.Send:
		if received.Channel != originalChannel {
			t.Errorf("Expected channel field '%s', got '%s'", originalChannel, received.Channel)
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("Expected to receive message, but channel was empty")
	}
}

// TestBroadcastToChannelEmpty verifies no-op when no subscribers; no panic
func TestBroadcastToChannelEmpty(t *testing.T) {
	hub := &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client, 256),
		unregister: make(chan *Client, 256),
		broadcast:  make(chan *BroadcastMessage, 256),
		unicast:    make(chan *UnicastMessage, 256),
	}

	// Send message to channel with no subscribers
	msg := &Message{
		Type:      "test.message",
		Data:      map[string]interface{}{"key": "value"},
		Channel:   "empty",
		Timestamp: time.Now(),
	}

	// This should not panic
	hub.BroadcastToChannel("empty", msg)

	// Test passes if no panic occurred
}
