package websocket

import (
	"log"
	"sync"
	"time"
)

// Message represents a WebSocket message
type Message struct {
	Type      string    `json:"type"`
	Data      interface{} `json:"data"`
	Timestamp time.Time `json:"timestamp"`
	UserID    string    `json:"user_id,omitempty"`
	ClientID  string    `json:"client_id,omitempty"`
	Channel   string    `json:"channel,omitempty"`
}

// Client represents a connected WebSocket client
type Client struct {
	ID       string
	Hub      *Hub
	Conn     *Conn
	Send     chan *Message
	UserID   string
	Metadata map[string]interface{}
	mu       sync.RWMutex
}

// Hub maintains active client connections
type Hub struct {
	// Map of client ID to client
	clients map[string]*Client

	// Channel for registering new clients
	register chan *Client

	// Channel for unregistering clients
	unregister chan *Client

	// Channel for broadcasting messages
	broadcast chan *BroadcastMessage

	// Channel for user-specific messages
	unicast chan *UnicastMessage

	// Mutex for protecting clients map
	mu sync.RWMutex

	// Stopped flag
	stopped bool
}

// BroadcastMessage represents a message to broadcast to all clients
type BroadcastMessage struct {
	Message   *Message
	ExcludeID string // Exclude this client from broadcast
}

// UnicastMessage represents a message for a specific client
type UnicastMessage struct {
	ClientID string
	Message  *Message
}

// NewHub creates a new WebSocket hub
func NewHub() *Hub {
	return &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client, 256),
		unregister: make(chan *Client, 256),
		broadcast:  make(chan *BroadcastMessage, 256),
		unicast:    make(chan *UnicastMessage, 256),
	}
}

// Start begins the hub's event loop
func (h *Hub) Start() {
	go h.run()
	log.Println("WebSocket hub started")
}

// Stop gracefully stops the hub
func (h *Hub) Stop() {
	h.mu.Lock()
	defer h.mu.Unlock()

	if h.stopped {
		return
	}

	h.stopped = true

	// Close all client connections
	for id, client := range h.clients {
		client.Close()
		delete(h.clients, id)
	}

	// Close channels
	close(h.register)
	close(h.unregister)
	close(h.broadcast)
	close(h.unicast)

	log.Println("WebSocket hub stopped")
}

// run processes hub events
func (h *Hub) run() {
	for {
		select {
		case client := <-h.register:
			h.registerClient(client)

		case client := <-h.unregister:
			h.unregisterClient(client)

		case msg := <-h.broadcast:
			h.broadcastMessage(msg)

		case msg := <-h.unicast:
			h.unicastMessage(msg)
		}
	}
}

// registerClient adds a new client to the hub
func (h *Hub) registerClient(client *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()

	// Check if client ID already exists
	if existing, ok := h.clients[client.ID]; ok {
		// Close the old connection
		existing.Close()
	}

	h.clients[client.ID] = client

	log.Printf("Client registered: %s (user: %s, total: %d)", client.ID, client.UserID, len(h.clients))

	// Send welcome message
	client.Send <- &Message{
		Type:      "welcome",
		Data:      map[string]interface{}{"client_id": client.ID},
		Timestamp: time.Now(),
	}

	// Broadcast client joined event
	h.broadcast <- &BroadcastMessage{
		Message: &Message{
			Type: "client_joined",
			Data: map[string]interface{}{
				"client_id": client.ID,
				"user_id":   client.UserID,
				"timestamp": time.Now(),
			},
			Timestamp: time.Now(),
		},
		ExcludeID: client.ID,
	}
}

// unregisterClient removes a client from the hub
func (h *Hub) unregisterClient(client *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if _, ok := h.clients[client.ID]; !ok {
		return
	}

	delete(h.clients, client.ID)
	close(client.Send)

	log.Printf("Client unregistered: %s (user: %s, total: %d)", client.ID, client.UserID, len(h.clients))

	// Broadcast client left event
	h.broadcast <- &BroadcastMessage{
		Message: &Message{
			Type: "client_left",
			Data: map[string]interface{}{
				"client_id": client.ID,
				"timestamp": time.Now(),
			},
			Timestamp: time.Now(),
		},
	}
}

// broadcastMessage sends a message to all connected clients
func (h *Hub) broadcastMessage(bm *BroadcastMessage) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for clientID, client := range h.clients {
		// Skip excluded client
		if clientID == bm.ExcludeID {
			continue
		}

		select {
		case client.Send <- bm.Message:
		default:
			// Client's send channel is full, queue is dropping this message
			log.Printf("Warning: Drop message for client %s (send channel full)", clientID)
		}
	}
}

// unicastMessage sends a message to a specific client
func (h *Hub) unicastMessage(um *UnicastMessage) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	client, ok := h.clients[um.ClientID]
	if !ok {
		log.Printf("Warning: Client not found for unicast: %s", um.ClientID)
		return
	}

	select {
	case client.Send <- um.Message:
	default:
		log.Printf("Warning: Drop message for client %s (send channel full)", um.ClientID)
	}
}

// Broadcast sends a message to all clients
func (h *Hub) Broadcast(msg *Message) {
	select {
	case h.broadcast <- &BroadcastMessage{Message: msg}:
	default:
		log.Printf("Warning: Broadcast channel full, dropping message")
	}
}

// BroadcastExcept sends a message to all clients except one
func (h *Hub) BroadcastExcept(msg *Message, excludeID string) {
	select {
	case h.broadcast <- &BroadcastMessage{Message: msg, ExcludeID: excludeID}:
	default:
		log.Printf("Warning: Broadcast channel full, dropping message")
	}
}

// SendToClient sends a message to a specific client
func (h *Hub) SendToClient(clientID string, msg *Message) {
	select {
	case h.unicast <- &UnicastMessage{ClientID: clientID, Message: msg}:
	default:
		log.Printf("Warning: Unicast channel full, dropping message")
	}
}

// GetClientCount returns the number of connected clients
func (h *Hub) GetClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}

// GetClient returns a client by ID
func (h *Hub) GetClient(clientID string) *Client {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.clients[clientID]
}

// GetClients returns all connected clients
func (h *Hub) GetClients() []*Client {
	h.mu.RLock()
	defer h.mu.RUnlock()

	clients := make([]*Client, 0, len(h.clients))
	for _, client := range h.clients {
		clients = append(clients, client)
	}
	return clients
}

// GetClientsByUserID returns all clients for a specific user
func (h *Hub) GetClientsByUserID(userID string) []*Client {
	h.mu.RLock()
	defer h.mu.RUnlock()

	var result []*Client
	for _, client := range h.clients {
		if client.UserID == userID {
			result = append(result, client)
		}
	}
	return result
}

// SendToUserID sends a message to all clients of a specific user
func (h *Hub) SendToUserID(userID string, msg *Message) {
	clients := h.GetClientsByUserID(userID)
	for _, client := range clients {
		select {
		case client.Send <- msg:
		default:
			log.Printf("Warning: Drop message for user %s (send channel full)", userID)
		}
	}
}

// BroadcastToChannel sends a message to all clients subscribed to a channel
func (h *Hub) BroadcastToChannel(channel string, msg *Message) {
	h.mu.RLock()
	clients := make([]*Client, 0, len(h.clients))
	for _, c := range h.clients {
		clients = append(clients, c)
	}
	h.mu.RUnlock()

	for _, c := range clients {
		subs := c.GetMetadata("subscriptions")
		if subs != nil {
			if channels, ok := subs.([]string); ok {
				for _, sub := range channels {
					if sub == channel {
						c.SendMessage(msg)
						break
					}
				}
			}
		}
	}
}

// Close closes a client connection
func (c *Client) Close() {
	if c.Conn != nil {
		c.Conn.Close()
	}
	c.Hub.unregister <- c
}

// SendMessage sends a message to the client
func (c *Client) SendMessage(msg *Message) {
	select {
	case c.Send <- msg:
	default:
		log.Printf("Warning: Client %s send channel full", c.ID)
	}
}

// GetMetadata returns client metadata
func (c *Client) GetMetadata(key string) interface{} {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.Metadata[key]
}

// SetMetadata sets client metadata
func (c *Client) SetMetadata(key string, value interface{}) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.Metadata == nil {
		c.Metadata = make(map[string]interface{})
	}
	c.Metadata[key] = value
}
