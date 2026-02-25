package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"architect-go/pkg/errors"
	"architect-go/pkg/events"
	"architect-go/pkg/services"
)

// stubRealTimeEventService provides a minimal stub for RealTimeEventService
type stubRealTimeEventService struct {
	services.RealTimeEventService // Embed interface for default implementation
	publishCount                   int
	broadcastCount                 int
}

// PublishToChannel stub implementation
func (s *stubRealTimeEventService) PublishToChannel(ctx context.Context, channel, event string, data map[string]interface{}) error {
	s.publishCount++
	return nil
}

// BroadcastEvent stub implementation
func (s *stubRealTimeEventService) BroadcastEvent(ctx context.Context, event string, data map[string]interface{}) error {
	s.broadcastCount++
	return nil
}

// TestRealTimePublishDispatched tests that PublishToChannel dispatches event
func TestRealTimePublishDispatched(t *testing.T) {
	mockSvc := &stubRealTimeEventService{}
	mockDispatcher := &mockEventDispatcher{}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewRealTimeEventHandlersWithDispatcher(mockSvc, errHandler, mockDispatcher)

	reqBody := map[string]interface{}{
		"event": "test.event",
		"data":  map[string]interface{}{"msg": "hello"},
	}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/realtime/publish/test-channel", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	r = setURLParam(r, "channel", "test-channel")

	handler.PublishToChannel(w, r)

	if len(mockDispatcher.dispatchedEvents) != 1 {
		t.Errorf("expected 1 dispatched event, got %d", len(mockDispatcher.dispatchedEvents))
		return
	}

	event := mockDispatcher.dispatchedEvents[0]
	if event.Type != events.EventRealTimePublish {
		t.Errorf("expected event type %s, got %s", events.EventRealTimePublish, event.Type)
	}
	if event.Channel != "test-channel" {
		t.Errorf("expected channel test-channel, got %s", event.Channel)
	}
}

// TestRealTimeBroadcastDispatched tests that BroadcastEvent dispatches event
func TestRealTimeBroadcastDispatched(t *testing.T) {
	mockSvc := &stubRealTimeEventService{}
	mockDispatcher := &mockEventDispatcher{}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewRealTimeEventHandlersWithDispatcher(mockSvc, errHandler, mockDispatcher)

	reqBody := map[string]interface{}{
		"event": "test.broadcast",
		"data":  map[string]interface{}{"msg": "broadcast"},
	}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/realtime/broadcast", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")

	handler.BroadcastEvent(w, r)

	if len(mockDispatcher.dispatchedEvents) != 1 {
		t.Errorf("expected 1 dispatched event, got %d", len(mockDispatcher.dispatchedEvents))
		return
	}

	event := mockDispatcher.dispatchedEvents[0]
	if event.Type != events.EventRealTimePublish {
		t.Errorf("expected event type %s, got %s", events.EventRealTimePublish, event.Type)
	}
	if event.Channel != "broadcast" {
		t.Errorf("expected channel broadcast, got %s", event.Channel)
	}
}

// TestRealTimeNilDispatcherNoPanic tests that nil dispatcher doesn't panic
func TestRealTimeNilDispatcherNoPanic(t *testing.T) {
	mockSvc := &stubRealTimeEventService{}
	errHandler := errors.NewErrorHandler(false, true)

	// Create handler with nil dispatcher
	handler := NewRealTimeEventHandlers(mockSvc, errHandler)

	reqBody := map[string]interface{}{
		"event": "test.event",
		"data":  map[string]interface{}{"msg": "hello"},
	}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/realtime/publish/test", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	r = setURLParam(r, "channel", "test")

	// Should not panic
	handler.PublishToChannel(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}
}
