package handlers

import (
	"log"
	"net/http"

	"github.com/gorilla/websocket"
	wssvc "github.com/jgirmay/GAIA_GO/pkg/services/websocket"
)

// QuotaWebSocketHandlers handles WebSocket connections for quota management
type QuotaWebSocketHandlers struct {
	broadcaster *wssvc.QuotaBroadcaster
}

// NewQuotaWebSocketHandlers creates new WebSocket handlers
func NewQuotaWebSocketHandlers(broadcaster *wssvc.QuotaBroadcaster) *QuotaWebSocketHandlers {
	return &QuotaWebSocketHandlers{
		broadcaster: broadcaster,
	}
}

// WebSocket upgrader configuration
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		// In production, implement proper origin checking
		// For now, allow all origins for admin dashboard
		return true
	},
}

// HandleQuotaWebSocket handles WebSocket connections for quota updates
// GET /ws/admin/quotas
func (qwh *QuotaWebSocketHandlers) HandleQuotaWebSocket(w http.ResponseWriter, r *http.Request) {
	// Upgrade HTTP connection to WebSocket
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[WS] Upgrade error: %v", err)
		http.Error(w, "Failed to upgrade to WebSocket", http.StatusBadRequest)
		return
	}

	// Register client with broadcaster
	client := qwh.broadcaster.RegisterClient(conn)

	// Client will be unregistered when connection closes
	log.Printf("[WS] New WebSocket connection: %s", client.ID)
}

// HandleHealthCheck returns WebSocket service health status
// GET /api/ws/health
func (qwh *QuotaWebSocketHandlers) HandleHealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	clientCount := qwh.broadcaster.GetClientCount()

	status := map[string]interface{}{
		"status":              "healthy",
		"connected_clients":   clientCount,
		"max_connections":     1000,
		"broadcast_interval":  "5 seconds",
		"heartbeat_interval":  "10 seconds",
		"connection_timeout":  "30 seconds",
	}

	writeJSON(w, http.StatusOK, status)
}

// BroadcastTestMessage sends a test message to all connected clients
// POST /api/ws/test-broadcast
func (qwh *QuotaWebSocketHandlers) BroadcastTestMessage(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Decode test message from request
	var testData map[string]interface{}
	if err := decodeJSON(r, &testData); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "Invalid request body",
		})
		return
	}

	// Create test message
	msg := wssvc.Message{
		Type: "test",
		Data: testData,
	}

	// Broadcast to all clients
	qwh.broadcaster.Broadcast(msg)

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success":         true,
		"message_sent":    true,
		"clients_reached": qwh.broadcaster.GetClientCount(),
	})
}

// BroadcastViolation manually triggers a violation broadcast
// POST /api/ws/test-violation
func (qwh *QuotaWebSocketHandlers) BroadcastViolation(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var violation wssvc.ViolationMessage
	if err := decodeJSON(r, &violation); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "Invalid violation data",
		})
		return
	}

	qwh.broadcaster.BroadcastViolation(violation)

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success":         true,
		"message_sent":    true,
		"clients_reached": qwh.broadcaster.GetClientCount(),
	})
}

// BroadcastAlert manually triggers an alert broadcast
// POST /api/ws/test-alert
func (qwh *QuotaWebSocketHandlers) BroadcastAlert(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var alert wssvc.AlertMessage
	if err := decodeJSON(r, &alert); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "Invalid alert data",
		})
		return
	}

	qwh.broadcaster.BroadcastAlert(alert)

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success":         true,
		"message_sent":    true,
		"clients_reached": qwh.broadcaster.GetClientCount(),
	})
}
