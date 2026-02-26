package websocket

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// Message represents a WebSocket message
type Message struct {
	Type      string        `json:"type"`      // "stats", "violation", "alert", "ping"
	Timestamp time.Time     `json:"timestamp"`
	Data      interface{}   `json:"data,omitempty"`
	ClientID  string        `json:"client_id,omitempty"`
}

// Client represents a connected WebSocket client
type Client struct {
	ID       string
	conn     *websocket.Conn
	send     chan Message
	done     chan struct{}
	lastSeen time.Time
	mu       sync.Mutex
}

// StatsMessage represents system statistics
type StatsMessage struct {
	TotalUsers            int64                  `json:"total_users"`
	CommandsToday         int64                  `json:"commands_today"`
	AverageThrottleFactor float64                `json:"average_throttle_factor"`
	ViolationsToday       int64                  `json:"violations_today"`
	HighUtilizationCount  int64                  `json:"high_utilization_count"`
	SystemLoad            map[string]interface{} `json:"system_load"`
}

// ViolationMessage represents a quota violation
type ViolationMessage struct {
	UserID      int64  `json:"user_id"`
	Username    string `json:"username"`
	CommandType string `json:"command_type"`
	Period      string `json:"period"`
	Limit       int64  `json:"limit"`
	Attempted   int64  `json:"attempted"`
	Message     string `json:"message"`
}

// AlertMessage represents an alert trigger
type AlertMessage struct {
	AlertID      int64  `json:"alert_id"`
	AlertType    string `json:"alert_type"`
	Severity     string `json:"severity"`
	UserID       int64  `json:"user_id,omitempty"`
	Username     string `json:"username,omitempty"`
	Message      string `json:"message"`
	ActionNeeded bool   `json:"action_needed"`
}

// QuotaBroadcaster manages WebSocket connections and broadcasts real-time data
type QuotaBroadcaster struct {
	db                *gorm.DB
	analyticsService  *rate_limiting.QuotaAnalytics
	alertEngine       *rate_limiting.AlertEngine
	quotaService      *rate_limiting.CommandQuotaService
	clients           map[*Client]bool
	broadcast         chan Message
	register          chan *Client
	unregister        chan *Client
	ticker            *time.Ticker
	done              chan struct{}
	mu                sync.RWMutex
	lastViolationTime time.Time
	lastAlertTime     time.Time
}

// NewQuotaBroadcaster creates a new quota broadcaster
func NewQuotaBroadcaster(
	db *gorm.DB,
	analyticsService *rate_limiting.QuotaAnalytics,
	alertEngine *rate_limiting.AlertEngine,
	quotaService *rate_limiting.CommandQuotaService,
) *QuotaBroadcaster {
	return &QuotaBroadcaster{
		db:               db,
		analyticsService: analyticsService,
		alertEngine:      alertEngine,
		quotaService:     quotaService,
		clients:          make(map[*Client]bool),
		broadcast:        make(chan Message, 100),
		register:         make(chan *Client, 10),
		unregister:       make(chan *Client, 10),
		ticker:           time.NewTicker(5 * time.Second),
		done:             make(chan struct{}),
		lastViolationTime: time.Now(),
		lastAlertTime:     time.Now(),
	}
}

// Start begins the broadcaster loop
func (qb *QuotaBroadcaster) Start(ctx context.Context) {
	go qb.run(ctx)
}

// Stop gracefully shuts down the broadcaster
func (qb *QuotaBroadcaster) Stop() {
	qb.ticker.Stop()
	close(qb.done)

	// Close all client connections
	qb.mu.Lock()
	for client := range qb.clients {
		close(client.send)
		delete(qb.clients, client)
	}
	qb.mu.Unlock()
}

// RegisterClient adds a new client
func (qb *QuotaBroadcaster) RegisterClient(conn *websocket.Conn) *Client {
	client := &Client{
		ID:       uuid.New().String(),
		conn:     conn,
		send:     make(chan Message, 50),
		done:     make(chan struct{}),
		lastSeen: time.Now(),
	}

	qb.register <- client
	return client
}

// UnregisterClient removes a client
func (qb *QuotaBroadcaster) UnregisterClient(client *Client) {
	qb.unregister <- client
}

// Broadcast sends a message to all connected clients
func (qb *QuotaBroadcaster) Broadcast(msg Message) {
	select {
	case qb.broadcast <- msg:
	case <-qb.done:
		// Broadcaster is stopped
	}
}

// BroadcastViolation sends a violation message to all clients
func (qb *QuotaBroadcaster) BroadcastViolation(violation ViolationMessage) {
	msg := Message{
		Type:      "violation",
		Timestamp: time.Now(),
		Data:      violation,
	}
	qb.Broadcast(msg)
}

// BroadcastAlert sends an alert message to all clients
func (qb *QuotaBroadcaster) BroadcastAlert(alert AlertMessage) {
	msg := Message{
		Type:      "alert",
		Timestamp: time.Now(),
		Data:      alert,
	}
	qb.Broadcast(msg)
}

// GetClientCount returns the number of connected clients
func (qb *QuotaBroadcaster) GetClientCount() int {
	qb.mu.RLock()
	defer qb.mu.RUnlock()
	return len(qb.clients)
}

// run is the main broadcaster loop
func (qb *QuotaBroadcaster) run(ctx context.Context) {
	statsTimer := time.NewTimer(5 * time.Second)
	heartbeatTicker := time.NewTicker(10 * time.Second)
	timeoutTicker := time.NewTicker(30 * time.Second)

	defer func() {
		statsTimer.Stop()
		heartbeatTicker.Stop()
		timeoutTicker.Stop()
	}()

	for {
		select {
		case <-qb.done:
			return

		case <-ctx.Done():
			return

		// Register new client
		case client := <-qb.register:
			qb.mu.Lock()
			qb.clients[client] = true
			qb.mu.Unlock()
			log.Printf("[WS] Client registered: %s (total: %d)", client.ID, len(qb.clients))

			// Start client message handler
			go qb.handleClient(client)

		// Unregister client
		case client := <-qb.unregister:
			qb.mu.Lock()
			if _, ok := qb.clients[client]; ok {
				delete(qb.clients, client)
				close(client.send)
			}
			qb.mu.Unlock()
			log.Printf("[WS] Client unregistered: %s (total: %d)", client.ID, len(qb.clients))

		// Broadcast message to all clients
		case msg := <-qb.broadcast:
			qb.mu.RLock()
			for client := range qb.clients {
				select {
				case client.send <- msg:
				default:
					// Client's send channel is full, skip
					log.Printf("[WS] Failed to send message to client %s (channel full)", client.ID)
				}
			}
			qb.mu.RUnlock()

		// Periodic stats broadcast
		case <-statsTimer.C:
			if qb.analyticsService != nil {
				stats := qb.getSystemStats(ctx)
				if stats != nil {
					msg := Message{
						Type:      "stats",
						Timestamp: time.Now(),
						Data:      stats,
					}
					select {
					case qb.broadcast <- msg:
					default:
						log.Printf("[WS] Broadcast channel full, skipping stats")
					}
				}
			}
			statsTimer.Reset(5 * time.Second)

		// Periodic heartbeat
		case <-heartbeatTicker.C:
			msg := Message{
				Type:      "ping",
				Timestamp: time.Now(),
			}
			qb.mu.RLock()
			for client := range qb.clients {
				select {
				case client.send <- msg:
				default:
					log.Printf("[WS] Failed to send heartbeat to client %s", client.ID)
				}
			}
			qb.mu.RUnlock()

		// Timeout detection
		case <-timeoutTicker.C:
			qb.detectTimeouts()
		}
	}
}

// handleClient manages individual client connections
func (qb *QuotaBroadcaster) handleClient(client *Client) {
	// Configure WebSocket
	client.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	client.conn.SetPongHandler(func(string) error {
		client.mu.Lock()
		client.lastSeen = time.Now()
		client.mu.Unlock()
		client.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	// Send messages to client
	go func() {
		for {
			select {
			case <-client.done:
				return
			case msg, ok := <-client.send:
				if !ok {
					client.conn.WriteMessage(websocket.CloseMessage, []byte{})
					return
				}

				err := client.conn.WriteJSON(msg)
				if err != nil {
					qb.UnregisterClient(client)
					return
				}
			}
		}
	}()

	// Read messages from client (for ping/pong)
	for {
		var msg json.RawMessage
		err := client.conn.ReadJSON(&msg)
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("[WS] Client read error: %v", err)
			}
			qb.UnregisterClient(client)
			close(client.done)
			return
		}

		// Update last seen time
		client.mu.Lock()
		client.lastSeen = time.Now()
		client.mu.Unlock()
	}
}

// detectTimeouts removes clients that haven't communicated in 30+ seconds
func (qb *QuotaBroadcaster) detectTimeouts() {
	now := time.Now()
	qb.mu.Lock()

	for client := range qb.clients {
		client.mu.Lock()
		lastSeen := client.lastSeen
		client.mu.Unlock()

		if now.Sub(lastSeen) > 30*time.Second {
			log.Printf("[WS] Client timeout: %s", client.ID)
			qb.mu.Unlock()
			qb.UnregisterClient(client)
			qb.mu.Lock()
		}
	}
	qb.mu.Unlock()
}

// getSystemStats retrieves current system statistics
func (qb *QuotaBroadcaster) getSystemStats(ctx context.Context) *StatsMessage {
	if qb.analyticsService == nil {
		return nil
	}

	// Get system stats from analytics service
	stats, err := qb.analyticsService.GetSystemStats(ctx)
	if err != nil {
		log.Printf("[WS] Error getting system stats: %v", err)
		return nil
	}

	return &StatsMessage{
		TotalUsers:            stats.TotalUsers,
		CommandsToday:         stats.TotalCommandsToday,
		AverageThrottleFactor: stats.AverageThrottleFactor,
		ViolationsToday:       stats.QuotasExceededToday,
		HighUtilizationCount:  stats.HighUtilizationCount,
		SystemLoad: map[string]interface{}{
			"cpu_percent":      stats.SystemLoad.CPUPercent,
			"memory_percent":   stats.SystemLoad.MemoryPercent,
			"throttle_active":  stats.SystemLoad.ThrottleActive,
		},
	}
}
