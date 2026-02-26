package usability

import (
	"sync"
	"time"
)

// EventBus defines the interface for publishing and subscribing to usability events
type EventBus interface {
	// PublishFrustrationEvent publishes a frustration event to all subscribers
	PublishFrustrationEvent(event *FrustrationEvent)

	// PublishSatisfactionRating publishes a satisfaction rating event
	PublishSatisfactionRating(studentID, appName string, rating int, feedback string)

	// PublishMetricEvent publishes a generic metric event
	PublishMetricEvent(metric *Metric)

	// Subscribe adds a listener to frustration events
	Subscribe(listener FrustrationEventListener)

	// Unsubscribe removes a listener from frustration events
	Unsubscribe(listener FrustrationEventListener)

	// Close closes the event bus and cleans up resources
	Close()
}

// FrustrationEventListener defines the interface for frustration event handlers
type FrustrationEventListener interface {
	OnFrustrationDetected(event *FrustrationEvent)
}

// SimpleEventBus is a basic in-memory implementation of EventBus
type SimpleEventBus struct {
	mu                 sync.RWMutex
	frustrationListeners []FrustrationEventListener
	frustrationHistory []*FrustrationEvent
	maxHistorySize    int
	done               chan struct{}
	eventChan          chan interface{}
}

// NewSimpleEventBus creates a new in-memory event bus
func NewSimpleEventBus(bufferSize int, maxHistorySize int) *SimpleEventBus {
	if bufferSize == 0 {
		bufferSize = 100
	}
	if maxHistorySize == 0 {
		maxHistorySize = 1000
	}

	bus := &SimpleEventBus{
		frustrationListeners: make([]FrustrationEventListener, 0),
		frustrationHistory:   make([]*FrustrationEvent, 0, maxHistorySize),
		maxHistorySize:       maxHistorySize,
		done:                 make(chan struct{}),
		eventChan:            make(chan interface{}, bufferSize),
	}

	// Start background event processor
	go bus.processEvents()

	return bus
}

// PublishFrustrationEvent publishes a frustration event
func (b *SimpleEventBus) PublishFrustrationEvent(event *FrustrationEvent) {
	if event == nil {
		return
	}

	select {
	case <-b.done:
		return
	case b.eventChan <- event:
		// Event queued
	default:
		// Buffer full, skip event (prevent blocking)
	}
}

// PublishSatisfactionRating publishes a satisfaction rating event
func (b *SimpleEventBus) PublishSatisfactionRating(studentID, appName string, rating int, feedback string) {
	event := map[string]interface{}{
		"type":        "satisfaction_rating",
		"student_id":  studentID,
		"app_name":    appName,
		"rating":      rating,
		"feedback":    feedback,
		"timestamp":   time.Now(),
	}

	select {
	case <-b.done:
		return
	case b.eventChan <- event:
		// Event queued
	default:
		// Buffer full, skip event
	}
}

// PublishMetricEvent publishes a generic metric event
func (b *SimpleEventBus) PublishMetricEvent(metric *Metric) {
	if metric == nil {
		return
	}

	event := map[string]interface{}{
		"type":        "metric",
		"student_id":  metric.StudentID,
		"app_name":    metric.AppName,
		"metric_type": metric.MetricType,
		"metric_value": metric.MetricValue,
		"timestamp":   metric.Timestamp,
	}

	select {
	case <-b.done:
		return
	case b.eventChan <- event:
		// Event queued
	default:
		// Buffer full, skip event
	}
}

// Subscribe adds a frustration event listener
func (b *SimpleEventBus) Subscribe(listener FrustrationEventListener) {
	if listener == nil {
		return
	}

	b.mu.Lock()
	defer b.mu.Unlock()

	b.frustrationListeners = append(b.frustrationListeners, listener)
}

// Unsubscribe removes a frustration event listener
func (b *SimpleEventBus) Unsubscribe(listener FrustrationEventListener) {
	if listener == nil {
		return
	}

	b.mu.Lock()
	defer b.mu.Unlock()

	// Find and remove the listener
	for i, l := range b.frustrationListeners {
		if l == listener {
			b.frustrationListeners = append(b.frustrationListeners[:i], b.frustrationListeners[i+1:]...)
			break
		}
	}
}

// GetFrustrationHistory returns the recent frustration event history
func (b *SimpleEventBus) GetFrustrationHistory(limit int) []*FrustrationEvent {
	b.mu.RLock()
	defer b.mu.RUnlock()

	if limit <= 0 || limit > len(b.frustrationHistory) {
		limit = len(b.frustrationHistory)
	}

	// Return most recent events
	history := make([]*FrustrationEvent, limit)
	copy(history, b.frustrationHistory[len(b.frustrationHistory)-limit:])
	return history
}

// processEvents handles events from the channel
func (b *SimpleEventBus) processEvents() {
	for {
		select {
		case <-b.done:
			return
		case event := <-b.eventChan:
			if event == nil {
				continue
			}

			if frustrationEvent, ok := event.(*FrustrationEvent); ok {
				b.handleFrustrationEvent(frustrationEvent)
			}
		}
	}
}

// handleFrustrationEvent notifies all listeners and stores in history
func (b *SimpleEventBus) handleFrustrationEvent(event *FrustrationEvent) {
	b.mu.Lock()

	// Store in history
	b.frustrationHistory = append(b.frustrationHistory, event)
	if len(b.frustrationHistory) > b.maxHistorySize {
		b.frustrationHistory = b.frustrationHistory[len(b.frustrationHistory)-b.maxHistorySize:]
	}

	// Get current listeners
	listeners := make([]FrustrationEventListener, len(b.frustrationListeners))
	copy(listeners, b.frustrationListeners)

	b.mu.Unlock()

	// Notify all listeners (outside lock to avoid deadlocks)
	for _, listener := range listeners {
		// Call listener in goroutine to prevent blocking
		go listener.OnFrustrationDetected(event)
	}
}

// Close closes the event bus
func (b *SimpleEventBus) Close() {
	select {
	case <-b.done:
		// Already closed
		return
	default:
		close(b.done)
		close(b.eventChan)

		// Drain remaining events
		for event := range b.eventChan {
			if frustrationEvent, ok := event.(*FrustrationEvent); ok {
				b.handleFrustrationEvent(frustrationEvent)
			}
		}
	}
}

// NoOpEventBus is a no-op implementation of EventBus for testing
type NoOpEventBus struct{}

// NewNoOpEventBus creates a no-op event bus
func NewNoOpEventBus() *NoOpEventBus {
	return &NoOpEventBus{}
}

// PublishFrustrationEvent does nothing
func (b *NoOpEventBus) PublishFrustrationEvent(event *FrustrationEvent) {}

// PublishSatisfactionRating does nothing
func (b *NoOpEventBus) PublishSatisfactionRating(studentID, appName string, rating int, feedback string) {}

// PublishMetricEvent does nothing
func (b *NoOpEventBus) PublishMetricEvent(metric *Metric) {}

// Subscribe does nothing
func (b *NoOpEventBus) Subscribe(listener FrustrationEventListener) {}

// Unsubscribe does nothing
func (b *NoOpEventBus) Unsubscribe(listener FrustrationEventListener) {}

// Close does nothing
func (b *NoOpEventBus) Close() {}
