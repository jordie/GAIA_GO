package websocket

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Conn wraps a WebSocket connection
type Conn struct {
	ws            *websocket.Conn
	mu            sync.Mutex
	closed        bool
	readDeadline  time.Duration
	writeDeadline time.Duration
}

// WebSocket upgrader
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		// Allow all origins for now
		return true
	},
}

// NewConn creates a new WebSocket connection
func NewConn(ws *websocket.Conn) *Conn {
	return &Conn{
		ws:            ws,
		readDeadline:  60 * time.Second,
		writeDeadline: 10 * time.Second,
	}
}

// UpgradeHTTP upgrades an HTTP connection to WebSocket
func UpgradeHTTP(w http.ResponseWriter, r *http.Request) (*Conn, error) {
	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to upgrade connection: %w", err)
	}

	conn := NewConn(ws)
	ws.SetReadDeadline(time.Now().Add(conn.readDeadline))
	ws.SetPongHandler(func(string) error {
		ws.SetReadDeadline(time.Now().Add(conn.readDeadline))
		return nil
	})

	return conn, nil
}

// ReadMessage reads a message from the connection
func (c *Conn) ReadMessage() (*Message, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return nil, fmt.Errorf("connection closed")
	}

	_, data, err := c.ws.ReadMessage()
	if err != nil {
		if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
			log.Printf("WebSocket error: %v", err)
		}
		return nil, err
	}

	var msg Message
	if err := json.Unmarshal(data, &msg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal message: %w", err)
	}

	return &msg, nil
}

// WriteMessage writes a message to the connection
func (c *Conn) WriteMessage(msg *Message) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return fmt.Errorf("connection closed")
	}

	data, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	c.ws.SetWriteDeadline(time.Now().Add(c.writeDeadline))
	return c.ws.WriteMessage(websocket.TextMessage, data)
}

// WriteJSON writes a JSON message to the connection
func (c *Conn) WriteJSON(v interface{}) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return fmt.Errorf("connection closed")
	}

	c.ws.SetWriteDeadline(time.Now().Add(c.writeDeadline))
	return c.ws.WriteJSON(v)
}

// WriteControl writes a control message (ping, pong, etc.)
func (c *Conn) WriteControl(messageType int, data []byte) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return fmt.Errorf("connection closed")
	}

	c.ws.SetWriteDeadline(time.Now().Add(c.writeDeadline))
	return c.ws.WriteControl(messageType, data, time.Now().Add(10*time.Second))
}

// Ping sends a ping message to keep connection alive
func (c *Conn) Ping() error {
	return c.WriteControl(websocket.PingMessage, []byte{})
}

// Close closes the connection
func (c *Conn) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return nil
	}

	c.closed = true
	_ = c.ws.WriteControl(websocket.CloseMessage, []byte{}, time.Now().Add(10*time.Second))
	return c.ws.Close()
}

// IsClosed returns true if the connection is closed
func (c *Conn) IsClosed() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.closed
}

// RemoteAddr returns the remote address
func (c *Conn) RemoteAddr() string {
	return c.ws.RemoteAddr().String()
}

// SetReadDeadline sets the read deadline
func (c *Conn) SetReadDeadline(d time.Duration) {
	c.readDeadline = d
}

// SetWriteDeadline sets the write deadline
func (c *Conn) SetWriteDeadline(d time.Duration) {
	c.writeDeadline = d
}
