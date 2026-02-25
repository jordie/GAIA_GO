package api

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/architect/go_wrapper/stream"
	"github.com/gorilla/websocket"
)

// WebSocket upgrader with permissive settings for development
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins in development
	},
}

// WSMessage represents a WebSocket message
type WSMessage struct {
	Type      string                 `json:"type"`       // command, response, status, error
	Timestamp time.Time              `json:"timestamp"`
	AgentName string                 `json:"agent"`
	Command   string                 `json:"command,omitempty"`
	Data      map[string]interface{} `json:"data,omitempty"`
	RequestID string                 `json:"request_id,omitempty"`
	Error     string                 `json:"error,omitempty"`
}

// WSConnection represents a single WebSocket connection
type WSConnection struct {
	agentName string
	conn      *websocket.Conn
	send      chan []byte
	mu        sync.Mutex
	closeChan chan struct{}
	closed    bool
}

// WSManager manages all WebSocket connections
type WSManager struct {
	connections map[string]map[string]*WSConnection // agent → connID → connection
	mu          sync.RWMutex
	server      *Server
}

// NewWSManager creates a new WebSocket manager
func NewWSManager(server *Server) *WSManager {
	return &WSManager{
		connections: make(map[string]map[string]*WSConnection),
		server:      server,
	}
}

// HandleWebSocket handles WebSocket connection requests
func (wm *WSManager) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	// Extract agent name from path
	agentName := r.URL.Path[len("/ws/agents/"):]
	if agentName == "" {
		http.Error(w, "agent name required", http.StatusBadRequest)
		return
	}

	// Upgrade HTTP connection to WebSocket
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[WebSocket] Failed to upgrade connection: %v", err)
		return
	}

	// Create connection object
	connID := fmt.Sprintf("%s-%d", r.RemoteAddr, time.Now().UnixNano())
	wsConn := &WSConnection{
		agentName: agentName,
		conn:      conn,
		send:      make(chan []byte, 256),
		closeChan: make(chan struct{}),
		closed:    false,
	}

	// Register connection
	wm.register(agentName, connID, wsConn)
	defer wm.unregister(agentName, connID)

	log.Printf("[WebSocket] Client connected: agent=%s, conn=%s", agentName, connID)

	// Send connection success message
	welcome := WSMessage{
		Type:      "connected",
		Timestamp: time.Now(),
		AgentName: agentName,
		Data:      map[string]interface{}{"conn_id": connID},
	}
	wsConn.SendMessage(welcome)

	// Start read and write pumps
	go wsConn.writePump()
	wsConn.readPump(wm)
}

// register adds a connection to the manager
func (wm *WSManager) register(agentName, connID string, conn *WSConnection) {
	wm.mu.Lock()
	defer wm.mu.Unlock()

	if wm.connections[agentName] == nil {
		wm.connections[agentName] = make(map[string]*WSConnection)
	}
	wm.connections[agentName][connID] = conn
}

// unregister removes a connection from the manager
func (wm *WSManager) unregister(agentName, connID string) {
	wm.mu.Lock()
	defer wm.mu.Unlock()

	if conns, ok := wm.connections[agentName]; ok {
		if conn, ok := conns[connID]; ok {
			conn.Close()
			delete(conns, connID)

			if len(conns) == 0 {
				delete(wm.connections, agentName)
			}

			log.Printf("[WebSocket] Client disconnected: agent=%s, conn=%s", agentName, connID)
		}
	}
}

// Broadcast sends a message to all connections for an agent
func (wm *WSManager) Broadcast(agentName string, message WSMessage) {
	wm.mu.RLock()
	defer wm.mu.RUnlock()

	if conns, ok := wm.connections[agentName]; ok {
		data, err := json.Marshal(message)
		if err != nil {
			log.Printf("[WebSocket] Failed to marshal message: %v", err)
			return
		}

		for connID, conn := range conns {
			select {
			case conn.send <- data:
				// Message sent
			default:
				// Channel full, skip (slow client)
				log.Printf("[WebSocket] Skipping slow client: agent=%s, conn=%s", agentName, connID)
			}
		}
	}
}

// GetConnectionCount returns the number of active connections for an agent
func (wm *WSManager) GetConnectionCount(agentName string) int {
	wm.mu.RLock()
	defer wm.mu.RUnlock()

	if conns, ok := wm.connections[agentName]; ok {
		return len(conns)
	}
	return 0
}

// GetTotalConnections returns the total number of active connections
func (wm *WSManager) GetTotalConnections() int {
	wm.mu.RLock()
	defer wm.mu.RUnlock()

	total := 0
	for _, conns := range wm.connections {
		total += len(conns)
	}
	return total
}

// Close closes a connection
func (c *WSConnection) Close() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.closed {
		c.closed = true
		close(c.closeChan)
		close(c.send)
		c.conn.Close()
	}
}

// SendMessage sends a message to the client
func (c *WSConnection) SendMessage(msg WSMessage) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return fmt.Errorf("connection closed")
	}

	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}

	select {
	case c.send <- data:
		return nil
	default:
		return fmt.Errorf("send channel full")
	}
}

// readPump reads messages from the WebSocket connection
func (c *WSConnection) readPump(wm *WSManager) {
	defer func() {
		c.Close()
	}()

	// Set read deadline
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("[WebSocket] Read error: %v", err)
			}
			break
		}

		// Parse message
		var msg WSMessage
		if err := json.Unmarshal(message, &msg); err != nil {
			log.Printf("[WebSocket] Failed to parse message: %v", err)
			continue
		}

		// Set timestamp if not provided
		if msg.Timestamp.IsZero() {
			msg.Timestamp = time.Now()
		}

		// Set agent name from connection
		msg.AgentName = c.agentName

		// Handle message based on type
		switch msg.Type {
		case "command":
			wm.handleCommand(c, msg)
		case "ping":
			c.SendMessage(WSMessage{
				Type:      "pong",
				Timestamp: time.Now(),
				AgentName: c.agentName,
			})
		default:
			log.Printf("[WebSocket] Unknown message type: %s", msg.Type)
		}
	}
}

// writePump writes messages to the WebSocket connection
func (c *WSConnection) writePump() {
	ticker := time.NewTicker(54 * time.Second)
	defer func() {
		ticker.Stop()
		c.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				// Channel closed
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			if err := c.conn.WriteMessage(websocket.TextMessage, message); err != nil {
				log.Printf("[WebSocket] Write error: %v", err)
				return
			}

		case <-ticker.C:
			// Send ping
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}

		case <-c.closeChan:
			return
		}
	}
}

// handleCommand processes a command message
func (wm *WSManager) handleCommand(conn *WSConnection, msg WSMessage) {
	// Check if agent exists
	wm.server.mu.RLock()
	agent, exists := wm.server.agents[msg.AgentName]
	wm.server.mu.RUnlock()

	if !exists {
		conn.SendMessage(WSMessage{
			Type:      "error",
			Timestamp: time.Now(),
			AgentName: msg.AgentName,
			RequestID: msg.RequestID,
			Error:     "agent not found",
		})
		return
	}

	// Use CommandHandler if available
	if agent.CommandHandler != nil {
		// Convert WSMessage to stream.Command
		streamCmd := stream.Command{
			Type:      msg.Command,
			Data:      msg.Data,
			RequestID: msg.RequestID,
		}

		// Execute command through handler
		cmdResponse := agent.CommandHandler.HandleCommand(streamCmd)

		// Convert response back to WSMessage
		response := WSMessage{
			Type:      "response",
			Timestamp: time.Now(),
			AgentName: msg.AgentName,
			RequestID: cmdResponse.RequestID,
			Command:   msg.Command,
			Data:      cmdResponse.Data,
		}

		if !cmdResponse.Success {
			response.Type = "error"
			response.Error = cmdResponse.Message
		} else if cmdResponse.Message != "" {
			if response.Data == nil {
				response.Data = make(map[string]interface{})
			}
			response.Data["message"] = cmdResponse.Message
		}

		// Send response
		conn.SendMessage(response)

		// Broadcast command execution to all clients
		wm.Broadcast(msg.AgentName, WSMessage{
			Type:      "status",
			Timestamp: time.Now(),
			AgentName: msg.AgentName,
			Command:   msg.Command,
			Data:      map[string]interface{}{"executed_by": "websocket", "success": cmdResponse.Success},
		})

		return
	}

	// Fallback to old implementation if CommandHandler not available
	response := WSMessage{
		Type:      "response",
		Timestamp: time.Now(),
		AgentName: msg.AgentName,
		RequestID: msg.RequestID,
		Command:   msg.Command,
		Data:      make(map[string]interface{}),
	}

	switch msg.Command {
	case "get_state":
		response.Data["status"] = agent.Status
		response.Data["started_at"] = agent.StartedAt
		response.Data["pid"] = agent.PID

	default:
		response.Type = "error"
		response.Error = fmt.Sprintf("command handler not available for: %s", msg.Command)
	}

	conn.SendMessage(response)
}

// GetStats returns WebSocket connection statistics
func (wm *WSManager) GetStats() map[string]interface{} {
	wm.mu.RLock()
	defer wm.mu.RUnlock()

	agentConns := make(map[string]int)
	for agentName, conns := range wm.connections {
		agentConns[agentName] = len(conns)
	}

	return map[string]interface{}{
		"total_connections": wm.GetTotalConnections(),
		"agents":            agentConns,
	}
}
