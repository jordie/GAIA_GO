package multiplayer

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// WebSocketHub manages WebSocket connections and routing
type WebSocketHub struct {
	roomManager *GameRoomManager
	sessionMgr  *session.Manager
	upgrader    websocket.Upgrader
	conns       map[*websocket.Conn]*PlayerConnection
	connsMutex  sync.RWMutex
	broadcast   chan []byte
	register    chan *websocket.Conn
	unregister  chan *websocket.Conn
}

// NewWebSocketHub creates a new WebSocket hub
func NewWebSocketHub(roomManager *GameRoomManager, sessionMgr *session.Manager) *WebSocketHub {
	hub := &WebSocketHub{
		roomManager: roomManager,
		sessionMgr:  sessionMgr,
		upgrader: websocket.Upgrader{
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
			CheckOrigin: func(r *http.Request) bool {
				return true // Allow all origins for now (configure as needed)
			},
		},
		conns:      make(map[*websocket.Conn]*PlayerConnection),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *websocket.Conn, 256),
		unregister: make(chan *websocket.Conn, 256),
	}

	// Start hub event loop
	go hub.run()

	return hub
}

// UpgradeConnection upgrades HTTP connection to WebSocket
func (h *WebSocketHub) UpgradeConnection(w http.ResponseWriter, r *http.Request, roomID string) (*websocket.Conn, error) {
	conn, err := h.upgrader.Upgrade(w, r, nil)
	if err != nil {
		return nil, err
	}

	// Authenticate user via session_id query parameter
	sessionID := r.URL.Query().Get("session_id")
	if sessionID == "" {
		conn.Close()
		return nil, ErrPlayerNotInRoom // Indicate auth failure
	}

	sess, err := h.sessionMgr.GetSession(sessionID)
	if err != nil {
		conn.Close()
		return nil, err
	}

	// Create player connection
	player := &PlayerConnection{
		UserID:      sess.UserID,
		Username:    sess.Username,
		Conn:        conn,
		SendChan:    make(chan []byte, 64), // Buffered channel for non-blocking sends
		RoomID:      roomID,
		IsReady:     false,
		Mutex:       sync.RWMutex{},
	}

	// Store connection
	h.connsMutex.Lock()
	h.conns[conn] = player
	h.connsMutex.Unlock()

	return conn, nil
}

// GetPlayer retrieves a player by connection
func (h *WebSocketHub) GetPlayer(conn *websocket.Conn) *PlayerConnection {
	h.connsMutex.RLock()
	defer h.connsMutex.RUnlock()
	return h.conns[conn]
}

// RemoveConnection removes a connection from the hub
func (h *WebSocketHub) RemoveConnection(conn *websocket.Conn) {
	h.connsMutex.Lock()
	delete(h.conns, conn)
	h.connsMutex.Unlock()
}

// run manages the hub's event loop
func (h *WebSocketHub) run() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			// Periodic cleanup/health check
			h.connsMutex.RLock()
			connCount := len(h.conns)
			h.connsMutex.RUnlock()
			log.Printf("[WebSocketHub] Active connections: %d\n", connCount)
		}
	}
}

// HandleConnection handles a new WebSocket connection and reads messages
func (h *WebSocketHub) HandleConnection(conn *websocket.Conn, player *PlayerConnection) {
	defer func() {
		h.RemoveConnection(conn)
		conn.Close()

		// Notify room of disconnect
		if player.RoomID != "" {
			room, err := h.roomManager.GetRoom(player.RoomID)
			if err == nil {
				room.HandlePlayerDisconnect(player.UserID)
			}
		}
	}()

	// Set up connection parameters
	conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	conn.SetPongHandler(func(string) error {
		conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	// Start goroutine to send messages to client
	go h.writePump(conn, player)

	// Read messages from client
	h.readPump(conn, player)
}

// readPump reads messages from the WebSocket connection
func (h *WebSocketHub) readPump(conn *websocket.Conn, player *PlayerConnection) {
	defer conn.Close()

	conn.SetReadLimit(512 * 1024) // 512KB limit
	conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	conn.SetPongHandler(func(string) error {
		conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("[WebSocket] Unexpected close: %v\n", err)
			}
			break
		}

		// Parse message
		var msg WSMessage
		if err := json.Unmarshal(message, &msg); err != nil {
			continue // Skip invalid messages
		}

		// Route message based on type
		h.routeMessage(player, msg)
	}
}

// writePump sends messages to the WebSocket connection
func (h *WebSocketHub) writePump(conn *websocket.Conn, player *PlayerConnection) {
	ticker := time.NewTicker(54 * time.Second)
	defer func() {
		ticker.Stop()
		conn.Close()
	}()

	for {
		select {
		case message, ok := <-player.SendChan:
			conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				// Hub closed the channel
				conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			if err := conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}

		case <-ticker.C:
			conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// routeMessage routes messages to appropriate handlers
func (h *WebSocketHub) routeMessage(player *PlayerConnection, msg WSMessage) {
	switch msg.Type {
	case MsgTypeJoin:
		h.handleJoin(player, msg)
	case MsgTypeReady:
		h.handleReady(player, msg)
	case MsgTypeProgress:
		h.handleProgress(player, msg)
	case MsgTypeFinish:
		h.handleFinish(player, msg)
	case MsgTypeLeave:
		h.handleLeave(player, msg)
	case MsgTypePing:
		h.handlePing(player)
	}
}

// handleJoin processes player join
func (h *WebSocketHub) handleJoin(player *PlayerConnection, msg WSMessage) {
	var payload JoinPayload
	data, _ := json.Marshal(msg.Payload)
	if err := json.Unmarshal(data, &payload); err != nil {
		sendError(player, "INVALID_JOIN", "Invalid join message")
		return
	}

	// Get room
	room, err := h.roomManager.GetRoom(payload.RoomID)
	if err != nil {
		sendError(player, "ROOM_NOT_FOUND", "Room does not exist")
		return
	}

	// Add player to room
	if err := room.AddPlayer(player); err != nil {
		sendError(player, "JOIN_FAILED", err.Error())
		return
	}

	player.RoomID = payload.RoomID
}

// handleReady processes ready status change
func (h *WebSocketHub) handleReady(player *PlayerConnection, msg WSMessage) {
	var payload ReadyPayload
	data, _ := json.Marshal(msg.Payload)
	if err := json.Unmarshal(data, &payload); err != nil {
		sendError(player, "INVALID_READY", "Invalid ready message")
		return
	}

	// Get room
	room, err := h.roomManager.GetRoom(player.RoomID)
	if err != nil {
		sendError(player, "ROOM_NOT_FOUND", "Room does not exist")
		return
	}

	// Update ready status
	if err := room.SetPlayerReady(player.UserID, payload.IsReady); err != nil {
		sendError(player, "READY_FAILED", err.Error())
		return
	}
}

// handleProgress processes typing progress
func (h *WebSocketHub) handleProgress(player *PlayerConnection, msg WSMessage) {
	var payload ProgressPayload
	data, _ := json.Marshal(msg.Payload)
	if err := json.Unmarshal(data, &payload); err != nil {
		sendError(player, "INVALID_PROGRESS", "Invalid progress message")
		return
	}

	// Get room
	room, err := h.roomManager.GetRoom(player.RoomID)
	if err != nil {
		return
	}

	// Validate and update progress
	if err := room.UpdatePlayerProgress(player.UserID, payload); err != nil {
		sendError(player, "PROGRESS_FAILED", err.Error())
		return
	}
}

// handleFinish processes race completion
func (h *WebSocketHub) handleFinish(player *PlayerConnection, msg WSMessage) {
	var payload FinishPayload
	data, _ := json.Marshal(msg.Payload)
	if err := json.Unmarshal(data, &payload); err != nil {
		sendError(player, "INVALID_FINISH", "Invalid finish message")
		return
	}

	// Get room
	room, err := h.roomManager.GetRoom(player.RoomID)
	if err != nil {
		return
	}

	// Mark player as finished
	room.MarkPlayerFinished(player.UserID, payload)
}

// handleLeave processes player leaving
func (h *WebSocketHub) handleLeave(player *PlayerConnection, msg WSMessage) {
	if player.RoomID == "" {
		return
	}

	room, err := h.roomManager.GetRoom(player.RoomID)
	if err != nil {
		return
	}

	room.RemovePlayer(player.UserID)
}

// handlePing responds to ping
func (h *WebSocketHub) handlePing(player *PlayerConnection) {
	pong := WSMessage{
		Type: MsgTypePong,
	}
	sendMessage(player, pong)
}

// ==================== Helper Functions ====================

// sendMessage sends a message to a player
func sendMessage(player *PlayerConnection, msg WSMessage) {
	data, _ := json.Marshal(msg)
	select {
	case player.SendChan <- data:
	default:
		// Channel full, skip (slow client)
		log.Printf("[WebSocket] Send channel full for player %d\n", player.UserID)
	}
}

// sendError sends an error message to a player
func sendError(player *PlayerConnection, code, message string) {
	msg := WSMessage{
		Type: MsgTypeError,
		Payload: ErrorPayload{
			Code:    code,
			Message: message,
		},
	}
	sendMessage(player, msg)
}

// BroadcastToRoom sends a message to all players in a room
func BroadcastToRoom(room *GameRoom, msg WSMessage) {
	data, _ := json.Marshal(msg)
	room.Broadcast(data)
}
