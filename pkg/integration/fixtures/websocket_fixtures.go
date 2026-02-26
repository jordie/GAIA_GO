//go:build e2e
// +build e2e

package fixtures

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/stretchr/testify/require"
)

// TestWebSocketClient is a test client for WebSocket connections
type TestWebSocketClient struct {
	t              *testing.T
	url            string
	conn           *websocket.Conn
	messages       []interface{}
	mu             sync.RWMutex
	connected      bool
	lastMessageAt  time.Time
	reconnectCount int
}

// WebSocketMessage represents a message sent over WebSocket
type WebSocketMessage struct {
	Type      string      `json:"type"`
	StudentID string      `json:"student_id,omitempty"`
	TeacherID string      `json:"teacher_id,omitempty"`
	Severity  string      `json:"severity,omitempty"`
	Data      interface{} `json:"data,omitempty"`
	Timestamp time.Time   `json:"timestamp,omitempty"`
}

// NewTestWebSocketClient creates a new test WebSocket client
func NewTestWebSocketClient(t *testing.T, url string) *TestWebSocketClient {
	return &TestWebSocketClient{
		t:         t,
		url:       url,
		messages:  make([]interface{}, 0),
		connected: false,
	}
}

// Connect establishes a WebSocket connection to the server
func (c *TestWebSocketClient) Connect(ctx context.Context) error {
	wsURL := c.convertHTTPtoWS(c.url)

	conn, _, err := websocket.DefaultDialer.DialContext(ctx, wsURL, nil)
	if err != nil {
		return fmt.Errorf("failed to connect to WebSocket: %w", err)
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	c.conn = conn
	c.connected = true
	c.reconnectCount++

	// Start message listener in background
	go c.listenForMessages()

	return nil
}

// SubscribeToClassroom subscribes to classroom alerts
func (c *TestWebSocketClient) SubscribeToClassroom(classroomID string) error {
	if !c.IsConnected() {
		return fmt.Errorf("WebSocket not connected")
	}

	msg := WebSocketMessage{
		Type: "subscribe",
		Data: map[string]string{
			"channel": fmt.Sprintf("classroom:%s", classroomID),
		},
	}

	return c.SendMessage(&msg)
}

// SubscribeToTeacherAlerts subscribes to teacher-specific alerts
func (c *TestWebSocketClient) SubscribeToTeacherAlerts(teacherID string) error {
	if !c.IsConnected() {
		return fmt.Errorf("WebSocket not connected")
	}

	msg := WebSocketMessage{
		Type:      "subscribe",
		TeacherID: teacherID,
		Data: map[string]string{
			"channel": fmt.Sprintf("teacher:%s", teacherID),
		},
	}

	return c.SendMessage(&msg)
}

// WaitForAlert waits for the next alert with a timeout
func (c *TestWebSocketClient) WaitForAlert(timeout time.Duration) (*WebSocketMessage, error) {
	deadline := time.Now().Add(timeout)
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			c.mu.RLock()
			if len(c.messages) > 0 {
				// Get the most recent message
				msgInterface := c.messages[len(c.messages)-1]
				c.mu.RUnlock()

				if msg, ok := msgInterface.(*WebSocketMessage); ok {
					return msg, nil
				}
			} else {
				c.mu.RUnlock()
			}

			if time.Now().After(deadline) {
				return nil, fmt.Errorf("alert timeout after %v", timeout)
			}
		}
	}
}

// GetReceivedAlerts returns all alerts received so far
func (c *TestWebSocketClient) GetReceivedAlerts() []*WebSocketMessage {
	c.mu.RLock()
	defer c.mu.RUnlock()

	alerts := make([]*WebSocketMessage, 0)
	for _, msgInterface := range c.messages {
		if msg, ok := msgInterface.(*WebSocketMessage); ok {
			alerts = append(alerts, msg)
		}
	}
	return alerts
}

// SendIntervention sends a teacher intervention action
func (c *TestWebSocketClient) SendIntervention(studentID string, action string) error {
	if !c.IsConnected() {
		return fmt.Errorf("WebSocket not connected")
	}

	msg := WebSocketMessage{
		Type:      "intervention",
		StudentID: studentID,
		Data: map[string]string{
			"action": action,
		},
		Timestamp: time.Now(),
	}

	return c.SendMessage(&msg)
}

// SendMessage sends a message over the WebSocket
func (c *TestWebSocketClient) SendMessage(msg *WebSocketMessage) error {
	c.mu.Lock()
	if !c.connected || c.conn == nil {
		c.mu.Unlock()
		return fmt.Errorf("WebSocket not connected")
	}

	conn := c.conn
	c.mu.Unlock()

	return conn.WriteJSON(msg)
}

// IsConnected returns whether the WebSocket is connected
func (c *TestWebSocketClient) IsConnected() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.connected && c.conn != nil
}

// GetMessageCount returns the total number of messages received
func (c *TestWebSocketClient) GetMessageCount() int {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return len(c.messages)
}

// GetLastMessageTime returns the time of the last received message
func (c *TestWebSocketClient) GetLastMessageTime() time.Time {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.lastMessageAt
}

// GetReconnectCount returns the number of reconnection attempts
func (c *TestWebSocketClient) GetReconnectCount() int {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.reconnectCount
}

// Close closes the WebSocket connection
func (c *TestWebSocketClient) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn != nil {
		c.connected = false
		return c.conn.Close()
	}

	return nil
}

// ClearMessages clears all received messages
func (c *TestWebSocketClient) ClearMessages() {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.messages = make([]interface{}, 0)
}

// listenForMessages listens for incoming messages on the WebSocket
func (c *TestWebSocketClient) listenForMessages() {
	for {
		c.mu.RLock()
		conn := c.conn
		c.mu.RUnlock()

		if conn == nil {
			return
		}

		msg := &WebSocketMessage{}
		err := conn.ReadJSON(msg)
		if err != nil {
			c.mu.Lock()
			c.connected = false
			c.mu.Unlock()
			return
		}

		c.mu.Lock()
		c.messages = append(c.messages, msg)
		c.lastMessageAt = time.Now()
		c.mu.Unlock()
	}
}

// Helper function to convert HTTP URL to WebSocket URL
func (c *TestWebSocketClient) convertHTTPtoWS(httpURL string) string {
	u, err := url.Parse(httpURL)
	if err != nil {
		return httpURL
	}

	if u.Scheme == "http" {
		u.Scheme = "ws"
	} else if u.Scheme == "https" {
		u.Scheme = "wss"
	}

	// Append /ws path if not already present
	if u.Path == "" || u.Path == "/" {
		u.Path = "/ws"
	}

	return u.String()
}

// WebSocketTestHelper provides higher-level WebSocket testing utilities
type WebSocketTestHelper struct {
	clients map[string]*TestWebSocketClient
	mu      sync.RWMutex
}

// NewWebSocketTestHelper creates a new WebSocket test helper
func NewWebSocketTestHelper() *WebSocketTestHelper {
	return &WebSocketTestHelper{
		clients: make(map[string]*TestWebSocketClient),
	}
}

// CreateClient creates a new test WebSocket client
func (h *WebSocketTestHelper) CreateClient(t *testing.T, clientID string, serverURL string) *TestWebSocketClient {
	h.mu.Lock()
	defer h.mu.Unlock()

	client := NewTestWebSocketClient(t, serverURL)
	h.clients[clientID] = client

	return client
}

// GetClient retrieves a test client by ID
func (h *WebSocketTestHelper) GetClient(clientID string) *TestWebSocketClient {
	h.mu.RLock()
	defer h.mu.RUnlock()

	return h.clients[clientID]
}

// GetAllClients returns all test clients
func (h *WebSocketTestHelper) GetAllClients() []*TestWebSocketClient {
	h.mu.RLock()
	defer h.mu.RUnlock()

	clients := make([]*TestWebSocketClient, 0)
	for _, client := range h.clients {
		clients = append(clients, client)
	}
	return clients
}

// CloseAllClients closes all client connections
func (h *WebSocketTestHelper) CloseAllClients() error {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for _, client := range h.clients {
		if err := client.Close(); err != nil {
			return err
		}
	}

	return nil
}

// AssertAllClientsReceived asserts that all clients received a specific message type
func (h *WebSocketTestHelper) AssertAllClientsReceived(t *testing.T, messageType string) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for clientID, client := range h.clients {
		alerts := client.GetReceivedAlerts()
		found := false
		for _, alert := range alerts {
			if alert.Type == messageType {
				found = true
				break
			}
		}
		require.True(t, found, "client %s did not receive %s message", clientID, messageType)
	}
}

// AssertMessageLatency asserts that messages were delivered within latency threshold
func (h *WebSocketTestHelper) AssertMessageLatency(t *testing.T, maxLatency time.Duration) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for clientID, client := range h.clients {
		alerts := client.GetReceivedAlerts()
		for _, alert := range alerts {
			actualLatency := time.Since(alert.Timestamp)
			require.LessOrEqual(t, actualLatency, maxLatency,
				"client %s received message with latency %v > max %v",
				clientID, actualLatency, maxLatency)
		}
	}
}
