package api

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
)

// SSEEvent represents a server-sent event
type SSEEvent struct {
	Type      string                 `json:"type"`       // log, extraction, state, complete
	Timestamp time.Time              `json:"timestamp"`
	AgentName string                 `json:"agent_name"`
	Data      map[string]interface{} `json:"data"`
}

// SSEClient represents a connected SSE client
type SSEClient struct {
	ID         string
	AgentName  string
	Channel    chan SSEEvent
	Connected  bool
	ConnectedAt time.Time
	LastPing   time.Time
	mu         sync.RWMutex
}

// SSEManager manages SSE connections for multiple agents
type SSEManager struct {
	clients map[string]map[string]*SSEClient // agentName -> clientID -> client
	mu      sync.RWMutex
}

// NewSSEManager creates a new SSE manager
func NewSSEManager() *SSEManager {
	manager := &SSEManager{
		clients: make(map[string]map[string]*SSEClient),
	}

	// Start cleanup goroutine
	go manager.cleanupDisconnected()

	return manager
}

// RegisterClient registers a new SSE client for an agent
func (m *SSEManager) RegisterClient(agentName, clientID string) *SSEClient {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.clients[agentName] == nil {
		m.clients[agentName] = make(map[string]*SSEClient)
	}

	client := &SSEClient{
		ID:          clientID,
		AgentName:   agentName,
		Channel:     make(chan SSEEvent, 100), // Buffer 100 events
		Connected:   true,
		ConnectedAt: time.Now(),
		LastPing:    time.Now(),
	}

	m.clients[agentName][clientID] = client
	log.Printf("[SSE] Client %s connected to agent %s", clientID, agentName)

	return client
}

// UnregisterClient removes a client
func (m *SSEManager) UnregisterClient(agentName, clientID string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if clients, exists := m.clients[agentName]; exists {
		if client, exists := clients[clientID]; exists {
			client.mu.Lock()
			client.Connected = false
			close(client.Channel)
			client.mu.Unlock()

			delete(clients, clientID)
			log.Printf("[SSE] Client %s disconnected from agent %s", clientID, agentName)

			// Clean up empty agent maps
			if len(clients) == 0 {
				delete(m.clients, agentName)
			}
		}
	}
}

// Broadcast sends an event to all clients of an agent
func (m *SSEManager) Broadcast(agentName string, event SSEEvent) {
	m.mu.RLock()
	clients := m.clients[agentName]
	m.mu.RUnlock()

	if clients == nil {
		return
	}

	for _, client := range clients {
		client.mu.RLock()
		connected := client.Connected
		client.mu.RUnlock()

		if connected {
			select {
			case client.Channel <- event:
				// Event sent successfully
			default:
				// Channel full, client is slow - disconnect
				log.Printf("[SSE] Client %s is slow, disconnecting", client.ID)
				go m.UnregisterClient(agentName, client.ID)
			}
		}
	}
}

// GetClientCount returns number of connected clients for an agent
func (m *SSEManager) GetClientCount(agentName string) int {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if clients, exists := m.clients[agentName]; exists {
		return len(clients)
	}
	return 0
}

// GetAllStats returns connection statistics
func (m *SSEManager) GetAllStats() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()

	stats := map[string]interface{}{
		"total_agents":  len(m.clients),
		"total_clients": 0,
		"agents":        make(map[string]int),
	}

	totalClients := 0
	for agentName, clients := range m.clients {
		count := len(clients)
		stats["agents"].(map[string]int)[agentName] = count
		totalClients += count
	}
	stats["total_clients"] = totalClients

	return stats
}

// cleanupDisconnected removes disconnected clients periodically
func (m *SSEManager) cleanupDisconnected() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		m.mu.Lock()
		for agentName, clients := range m.clients {
			for clientID, client := range clients {
				client.mu.RLock()
				connected := client.Connected
				lastPing := client.LastPing
				client.mu.RUnlock()

				// Remove clients that haven't pinged in 2 minutes
				if !connected || time.Since(lastPing) > 2*time.Minute {
					client.mu.Lock()
					if client.Connected {
						client.Connected = false
						close(client.Channel)
					}
					client.mu.Unlock()

					delete(clients, clientID)
					log.Printf("[SSE] Cleaned up stale client %s from agent %s", clientID, agentName)
				}
			}

			// Clean up empty agent maps
			if len(clients) == 0 {
				delete(m.clients, agentName)
			}
		}
		m.mu.Unlock()
	}
}

// HandleSSE handles SSE connections for an agent
func (m *SSEManager) HandleSSE(w http.ResponseWriter, r *http.Request, agentName string) {
	// Check if SSE is supported
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "SSE not supported", http.StatusInternalServerError)
		return
	}

	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Generate client ID
	clientID := fmt.Sprintf("client-%d", time.Now().UnixNano())

	// Register client
	client := m.RegisterClient(agentName, clientID)
	defer m.UnregisterClient(agentName, clientID)

	// Send connection event
	connEvent := SSEEvent{
		Type:      "connected",
		Timestamp: time.Now(),
		AgentName: agentName,
		Data: map[string]interface{}{
			"client_id": clientID,
			"message":   "Connected to agent stream",
		},
	}
	m.sendEvent(w, flusher, connEvent)

	// Create ping ticker
	pingTicker := time.NewTicker(15 * time.Second)
	defer pingTicker.Stop()

	// Stream events
	for {
		select {
		case event, ok := <-client.Channel:
			if !ok {
				// Channel closed
				return
			}

			// Send event
			m.sendEvent(w, flusher, event)

			// Update last ping time
			client.mu.Lock()
			client.LastPing = time.Now()
			client.mu.Unlock()

		case <-pingTicker.C:
			// Send keep-alive ping
			pingEvent := SSEEvent{
				Type:      "ping",
				Timestamp: time.Now(),
				AgentName: agentName,
				Data: map[string]interface{}{
					"message": "keep-alive",
				},
			}
			m.sendEvent(w, flusher, pingEvent)

		case <-r.Context().Done():
			// Client disconnected
			return
		}
	}
}

// sendEvent sends an SSE event to the client
func (m *SSEManager) sendEvent(w http.ResponseWriter, flusher http.Flusher, event SSEEvent) {
	// Marshal event data
	data, err := json.Marshal(event)
	if err != nil {
		log.Printf("[SSE] Error marshaling event: %v", err)
		return
	}

	// Write SSE format: "event: type\ndata: json\n\n"
	fmt.Fprintf(w, "event: %s\n", event.Type)
	fmt.Fprintf(w, "data: %s\n\n", data)
	flusher.Flush()
}
