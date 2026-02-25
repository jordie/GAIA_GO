package handlers

import (
	"context"
	"net/http"
	"sync"

	"github.com/go-chi/chi/v5"

	"architect-go/pkg/events"
)

// mockEventDispatcher implements EventDispatcher for testing
type mockEventDispatcher struct {
	dispatchedEvents []events.Event
	mu               sync.Mutex
}

func (m *mockEventDispatcher) Dispatch(event events.Event) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.dispatchedEvents = append(m.dispatchedEvents, event)
}

// setURLParam sets a URL parameter in the request for testing
func setURLParam(r *http.Request, key, value string) *http.Request {
	rctx := chi.NewRouteContext()
	rctx.URLParams.Add(key, value)
	// chi.Context implements context.Context through its parentCtx
	// We need to wrap it properly
	ctx := context.WithValue(r.Context(), chi.RouteCtxKey, rctx)
	return r.WithContext(ctx)
}

// setURLParamMultiple sets multiple URL parameters in the request for testing
func setURLParamMultiple(r *http.Request, params map[string]string) *http.Request {
	rctx := chi.NewRouteContext()
	for key, value := range params {
		rctx.URLParams.Add(key, value)
	}
	ctx := context.WithValue(r.Context(), chi.RouteCtxKey, rctx)
	return r.WithContext(ctx)
}
