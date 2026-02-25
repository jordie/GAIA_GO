package websocket

import (
	"log"
	"net/http"
	"time"

	gorillaws "github.com/gorilla/websocket"
	"github.com/google/uuid"

	"architect-go/pkg/auth"
)

// ClientHandler handles WebSocket client connections
type ClientHandler struct {
	Hub        *Hub
	sessionMgr *auth.SessionManager
}

// NewClientHandler creates a new client handler
func NewClientHandler(hub *Hub) *ClientHandler {
	return &ClientHandler{Hub: hub}
}

// NewClientHandlerWithAuth creates a new client handler with session authentication
func NewClientHandlerWithAuth(hub *Hub, sessionMgr *auth.SessionManager) *ClientHandler {
	return &ClientHandler{Hub: hub, sessionMgr: sessionMgr}
}

// extractWSToken extracts token from query parameter or Authorization header
func extractWSToken(r *http.Request) string {
	// Try query parameter first
	if token := r.URL.Query().Get("token"); token != "" {
		return token
	}
	// Try Authorization header
	if authHeader := r.Header.Get("Authorization"); len(authHeader) > 7 && authHeader[:7] == "Bearer " {
		return authHeader[7:]
	}
	return ""
}

// ServeHTTP handles WebSocket upgrades
func (h *ClientHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	userID := ""

	// Validate session token if auth is enabled (BEFORE upgrade)
	if h.sessionMgr != nil {
		token := extractWSToken(r)
		if token == "" {
			http.Error(w, `{"error":"missing token"}`, http.StatusUnauthorized)
			return
		}

		user, err := h.sessionMgr.ValidateSession(r.Context(), token)
		if err != nil {
			log.Printf("WebSocket auth failed: %v", err)
			http.Error(w, `{"error":"invalid or expired token"}`, http.StatusUnauthorized)
			return
		}

		userID = user.ID
	} else {
		// Fallback: extract user ID from query or header
		userID = r.URL.Query().Get("user_id")
		if userID == "" {
			userID = r.Header.Get("X-User-ID")
		}
	}

	// Upgrade connection
	conn, err := UpgradeHTTP(w, r)
	if err != nil {
		log.Printf("Failed to upgrade connection: %v", err)
		http.Error(w, "Failed to upgrade connection", http.StatusBadRequest)
		return
	}

	// Create client
	clientID := uuid.New().String()
	client := &Client{
		ID:       clientID,
		Hub:      h.Hub,
		Conn:     conn,
		Send:     make(chan *Message, 256),
		UserID:   userID,
		Metadata: make(map[string]interface{}),
	}

	// Register client
	h.Hub.register <- client

	// Start read and write pumps
	go h.readPump(client)
	go h.writePump(client)

	log.Printf("Client connected: %s (user: %s, remote: %s)", clientID, userID, conn.RemoteAddr())
}

// readPump reads messages from the WebSocket connection
func (h *ClientHandler) readPump(client *Client) {
	defer func() {
		client.Hub.unregister <- client
	}()

	for {
		msg, err := client.Conn.ReadMessage()
		if err != nil {
			if !client.Conn.IsClosed() {
				log.Printf("Client %s read error: %v", client.ID, err)
			}
			break
		}

		// Process message
		h.processMessage(client, msg)
	}

	client.Conn.Close()
}

// writePump writes messages to the WebSocket connection
func (h *ClientHandler) writePump(client *Client) {
	ticker := time.NewTicker(30 * time.Second)
	defer func() {
		ticker.Stop()
		client.Conn.Close()
	}()

	for {
		select {
		case msg, ok := <-client.Send:
			if !ok {
				// Channel closed
				client.Conn.WriteControl(gorillaws.CloseMessage, []byte{})
				return
			}

			if err := client.Conn.WriteMessage(msg); err != nil {
				log.Printf("Client %s write error: %v", client.ID, err)
				return
			}

		case <-ticker.C:
			// Send ping to keep connection alive
			if err := client.Conn.Ping(); err != nil {
				log.Printf("Client %s ping error: %v", client.ID, err)
				return
			}
		}
	}
}

// processMessage handles incoming messages
func (h *ClientHandler) processMessage(client *Client, msg *Message) {
	switch msg.Type {
	case "ping":
		h.handlePing(client, msg)

	case "broadcast":
		h.handleBroadcast(client, msg)

	case "direct":
		h.handleDirect(client, msg)

	case "subscribe":
		h.handleSubscribe(client, msg)

	case "unsubscribe":
		h.handleUnsubscribe(client, msg)

	default:
		log.Printf("Unknown message type from client %s: %s", client.ID, msg.Type)
	}
}

// handlePing responds to ping messages
func (h *ClientHandler) handlePing(client *Client, msg *Message) {
	response := &Message{
		Type:      "pong",
		Data:      msg.Data,
		Timestamp: time.Now(),
	}
	client.SendMessage(response)
}

// handleBroadcast broadcasts a message to all clients
func (h *ClientHandler) handleBroadcast(client *Client, msg *Message) {
	// Add sender info
	msg.ClientID = client.ID
	msg.UserID = client.UserID
	msg.Timestamp = time.Now()

	// Broadcast to all except sender
	h.Hub.BroadcastExcept(msg, client.ID)

	// Send acknowledgement to sender
	ack := &Message{
		Type: "ack",
		Data: map[string]interface{}{
			"message_type": "broadcast",
			"timestamp":    time.Now(),
		},
		Timestamp: time.Now(),
	}
	client.SendMessage(ack)
}

// handleDirect sends a direct message to a specific client
func (h *ClientHandler) handleDirect(client *Client, msg *Message) {
	data, ok := msg.Data.(map[string]interface{})
	if !ok {
		log.Printf("Invalid direct message format from client %s", client.ID)
		return
	}

	targetID, ok := data["target_id"].(string)
	if !ok {
		log.Printf("Missing target_id in direct message from client %s", client.ID)
		return
	}

	// Add sender info
	msg.ClientID = client.ID
	msg.UserID = client.UserID
	msg.Timestamp = time.Now()

	// Send to target
	h.Hub.SendToClient(targetID, msg)

	// Send acknowledgement to sender
	ack := &Message{
		Type: "ack",
		Data: map[string]interface{}{
			"message_type": "direct",
			"target_id":    targetID,
			"timestamp":    time.Now(),
		},
		Timestamp: time.Now(),
	}
	client.SendMessage(ack)
}

// handleSubscribe handles subscription to channels
func (h *ClientHandler) handleSubscribe(client *Client, msg *Message) {
	data, ok := msg.Data.(map[string]interface{})
	if !ok {
		log.Printf("Invalid subscribe message format from client %s", client.ID)
		return
	}

	channel, ok := data["channel"].(string)
	if !ok {
		log.Printf("Missing channel in subscribe message from client %s", client.ID)
		return
	}

	// Store subscription in client metadata
	subscriptions := client.Metadata["subscriptions"]
	if subscriptions == nil {
		subscriptions = make([]string, 0)
	}

	subs, ok := subscriptions.([]string)
	if !ok {
		subs = make([]string, 0)
	}

	// Add channel if not already subscribed
	found := false
	for _, s := range subs {
		if s == channel {
			found = true
			break
		}
	}

	if !found {
		subs = append(subs, channel)
		client.SetMetadata("subscriptions", subs)
	}

	// Send acknowledgement
	ack := &Message{
		Type: "subscribed",
		Data: map[string]interface{}{
			"channel":   channel,
			"timestamp": time.Now(),
		},
		Timestamp: time.Now(),
	}
	client.SendMessage(ack)

	log.Printf("Client %s subscribed to channel: %s", client.ID, channel)
}

// handleUnsubscribe handles unsubscription from channels
func (h *ClientHandler) handleUnsubscribe(client *Client, msg *Message) {
	data, ok := msg.Data.(map[string]interface{})
	if !ok {
		log.Printf("Invalid unsubscribe message format from client %s", client.ID)
		return
	}

	channel, ok := data["channel"].(string)
	if !ok {
		log.Printf("Missing channel in unsubscribe message from client %s", client.ID)
		return
	}

	// Remove subscription from client metadata
	subscriptions := client.Metadata["subscriptions"]
	if subscriptions != nil {
		if subs, ok := subscriptions.([]string); ok {
			filtered := make([]string, 0)
			for _, s := range subs {
				if s != channel {
					filtered = append(filtered, s)
				}
			}
			client.SetMetadata("subscriptions", filtered)
		}
	}

	// Send acknowledgement
	ack := &Message{
		Type: "unsubscribed",
		Data: map[string]interface{}{
			"channel":   channel,
			"timestamp": time.Now(),
		},
		Timestamp: time.Now(),
	}
	client.SendMessage(ack)

	log.Printf("Client %s unsubscribed from channel: %s", client.ID, channel)
}

// BroadcastToSubscribers broadcasts a message to all subscribers of a channel
func (h *ClientHandler) BroadcastToSubscribers(channel string, msg *Message) {
	clients := h.Hub.GetClients()

	for _, client := range clients {
		subscriptions := client.Metadata["subscriptions"]
		if subscriptions != nil {
			if subs, ok := subscriptions.([]string); ok {
				for _, sub := range subs {
					if sub == channel {
						msg.Data = map[string]interface{}{
							"channel": channel,
							"data":    msg.Data,
						}
						client.SendMessage(msg)
						break
					}
				}
			}
		}
	}
}
