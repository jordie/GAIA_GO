package stream

import (
	"sync"
	"time"
)

// EventType represents the type of broadcast event
type EventType string

const (
	EventTypeLog        EventType = "log"
	EventTypeExtraction EventType = "extraction"
	EventTypeState      EventType = "state"
	EventTypeComplete   EventType = "complete"
	EventTypeError      EventType = "error"
)

// BroadcastEvent represents an event to be broadcast
type BroadcastEvent struct {
	Type      EventType
	Timestamp time.Time
	Data      map[string]interface{}
}

// EventListener is a function that receives broadcast events
type EventListener func(BroadcastEvent)

// Broadcaster manages event listeners and broadcasts events
type Broadcaster struct {
	listeners []EventListener
	mu        sync.RWMutex
}

// NewBroadcaster creates a new broadcaster
func NewBroadcaster() *Broadcaster {
	return &Broadcaster{
		listeners: make([]EventListener, 0),
	}
}

// AddListener adds an event listener
func (b *Broadcaster) AddListener(listener EventListener) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.listeners = append(b.listeners, listener)
}

// RemoveAllListeners clears all listeners
func (b *Broadcaster) RemoveAllListeners() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.listeners = make([]EventListener, 0)
}

// Broadcast sends an event to all listeners
func (b *Broadcaster) Broadcast(event BroadcastEvent) {
	b.mu.RLock()
	listeners := make([]EventListener, len(b.listeners))
	copy(listeners, b.listeners)
	b.mu.RUnlock()

	// Call listeners asynchronously to avoid blocking
	for _, listener := range listeners {
		go listener(event)
	}
}

// BroadcastLog broadcasts a log line event
func (b *Broadcaster) BroadcastLog(stream string, line string, lineNum int) {
	event := BroadcastEvent{
		Type:      EventTypeLog,
		Timestamp: time.Now(),
		Data: map[string]interface{}{
			"stream":   stream, // stdout or stderr
			"line":     line,
			"line_num": lineNum,
		},
	}
	b.Broadcast(event)
}

// BroadcastExtraction broadcasts an extraction match event
func (b *Broadcaster) BroadcastExtraction(match Match) {
	event := BroadcastEvent{
		Type:      EventTypeExtraction,
		Timestamp: time.Now(),
		Data: map[string]interface{}{
			"type":     match.Type,
			"pattern":  match.Pattern,
			"value":    match.Value,
			"line":     match.Line,
			"line_num": match.LineNum,
			"metadata": match.Metadata,
		},
	}
	b.Broadcast(event)
}

// BroadcastState broadcasts a state change event
func (b *Broadcaster) BroadcastState(state string, details map[string]interface{}) {
	event := BroadcastEvent{
		Type:      EventTypeState,
		Timestamp: time.Now(),
		Data: map[string]interface{}{
			"state":   state,
			"details": details,
		},
	}
	b.Broadcast(event)
}

// BroadcastComplete broadcasts a completion event
func (b *Broadcaster) BroadcastComplete(exitCode int, duration time.Duration) {
	event := BroadcastEvent{
		Type:      EventTypeComplete,
		Timestamp: time.Now(),
		Data: map[string]interface{}{
			"exit_code": exitCode,
			"duration":  duration.String(),
		},
	}
	b.Broadcast(event)
}

// BroadcastError broadcasts an error event
func (b *Broadcaster) BroadcastError(error string, details map[string]interface{}) {
	event := BroadcastEvent{
		Type:      EventTypeError,
		Timestamp: time.Now(),
		Data: map[string]interface{}{
			"error":   error,
			"details": details,
		},
	}
	b.Broadcast(event)
}

// GetListenerCount returns the number of registered listeners
func (b *Broadcaster) GetListenerCount() int {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return len(b.listeners)
}
