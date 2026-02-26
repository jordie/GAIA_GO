package events

import (
	"log"
	"time"

	"architect-go/pkg/websocket"
)

// Event constants for different event types
const (
	EventTaskCreated     = "task.created"
	EventTaskUpdated     = "task.updated"
	EventTaskCompleted   = "task.completed"
	EventProjectCreated  = "project.created"
	EventProjectUpdated  = "project.updated"
	EventRealTimePublish = "realtime.publish"
	EventPresenceOnline  = "presence.online"
	EventPresenceOffline = "presence.offline"
	EventPresenceUpdated = "presence.updated"
	EventActivityLogged  = "activity.logged"
)

// Event represents an application event to be dispatched to connected clients
type Event struct {
	Type      string      // Event type constant (e.g., EventTaskCreated)
	Channel   string      // Optional: channel name for subscriber filtering
	UserID    string      // Optional: send only to this user's WS sessions
	Data      interface{} // Event payload
	Timestamp time.Time   // When event occurred
}

// EventDispatcher sends events to connected WebSocket clients
type EventDispatcher interface {
	Dispatch(event Event)
}

// HubInterface defines the interface for WebSocket hub operations
type HubInterface interface {
	Broadcast(msg *websocket.Message)
	SendToUserID(userID string, msg *websocket.Message)
	GetClients() []*websocket.Client
	BroadcastToChannel(channel string, msg *websocket.Message)
}

// HubEventDispatcher implements EventDispatcher using the WebSocket hub
type HubEventDispatcher struct {
	hub HubInterface
}

// NewHubEventDispatcher creates a new event dispatcher backed by a WebSocket hub
func NewHubEventDispatcher(hub HubInterface) EventDispatcher {
	return &HubEventDispatcher{
		hub: hub,
	}
}

// Dispatch sends an event to connected WebSocket clients
// - If UserID is set, sends only to that user's clients
// - If Channel is set, sends to all clients subscribed to that channel
// - Otherwise, broadcasts to all connected clients
func (d *HubEventDispatcher) Dispatch(event Event) {
	if d.hub == nil {
		log.Printf("Warning: HubEventDispatcher received nil hub, skipping dispatch")
		return
	}

	if event.Timestamp.IsZero() {
		event.Timestamp = time.Now()
	}

	msg := &websocket.Message{
		Type:      event.Type,
		Data:      event.Data,
		Timestamp: event.Timestamp,
		UserID:    event.UserID,
		Channel:   event.Channel,
	}

	// Send to specific user
	if event.UserID != "" {
		d.hub.SendToUserID(event.UserID, msg)
		log.Printf("Event dispatched to user %s: %s", event.UserID, event.Type)
		return
	}

	// Send to channel subscribers
	if event.Channel != "" {
		d.broadcastToSubscribers(event.Channel, msg)
		log.Printf("Event dispatched to channel %s: %s", event.Channel, event.Type)
		return
	}

	// Broadcast to all clients
	d.hub.Broadcast(msg)
	log.Printf("Event broadcasted to all clients: %s", event.Type)
}

// broadcastToSubscribers sends a message to all clients subscribed to a channel
func (d *HubEventDispatcher) broadcastToSubscribers(channel string, msg *websocket.Message) {
	clients := d.hub.GetClients()
	if len(clients) == 0 {
		return
	}

	sentCount := 0
	for _, client := range clients {
		if d.isClientSubscribedToChannel(client, channel) {
			select {
			case client.Send <- msg:
				sentCount++
			default:
				log.Printf("Warning: Drop message for client %s (send channel full)", client.ID)
			}
		}
	}

	if sentCount > 0 {
		log.Printf("Event delivered to %d subscribers of channel %q", sentCount, channel)
	}
}

// isClientSubscribedToChannel checks if a client is subscribed to a channel
// Checks client.Metadata["subscriptions"] which should be []string
func (d *HubEventDispatcher) isClientSubscribedToChannel(client *websocket.Client, channel string) bool {
	if client == nil || client.Metadata == nil {
		return false
	}

	subscriptions, ok := client.Metadata["subscriptions"]
	if !ok {
		return false
	}

	subs, ok := subscriptions.([]string)
	if !ok {
		return false
	}

	for _, sub := range subs {
		if sub == channel {
			return true
		}
	}

	return false
}
