package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"architect-go/pkg/errors"
	"architect-go/pkg/events"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// RealTimeEventHandlers handles real-time event streaming HTTP requests
type RealTimeEventHandlers struct {
	service    services.RealTimeEventService
	errHandler *errors.Handler
	dispatcher events.EventDispatcher
}

// NewRealTimeEventHandlers creates new real-time event handlers
func NewRealTimeEventHandlers(service services.RealTimeEventService, errHandler *errors.Handler) *RealTimeEventHandlers {
	return &RealTimeEventHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// NewRealTimeEventHandlersWithDispatcher creates new real-time event handlers with event dispatcher
func NewRealTimeEventHandlersWithDispatcher(service services.RealTimeEventService, errHandler *errors.Handler, dispatcher events.EventDispatcher) *RealTimeEventHandlers {
	return &RealTimeEventHandlers{
		service:    service,
		errHandler: errHandler,
		dispatcher: dispatcher,
	}
}

// SubscribeToChannel handles POST /api/realtime/subscribe/{channel}
func (rh *RealTimeEventHandlers) SubscribeToChannel(w http.ResponseWriter, r *http.Request) {
	channel := chi.URLParam(r, "channel")
	if channel == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_CHANNEL", "Channel is required"), httputil.GetTraceID(r))
		return
	}

	var req struct {
		UserID string `json:"user_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		rh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.SubscribeToChannel(r.Context(), req.UserID, channel); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "subscribed"})
}

// UnsubscribeFromChannel handles POST /api/realtime/unsubscribe/{channel}
func (rh *RealTimeEventHandlers) UnsubscribeFromChannel(w http.ResponseWriter, r *http.Request) {
	channel := chi.URLParam(r, "channel")
	if channel == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_CHANNEL", "Channel is required"), httputil.GetTraceID(r))
		return
	}

	var req struct {
		UserID string `json:"user_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		rh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.UnsubscribeFromChannel(r.Context(), req.UserID, channel); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "unsubscribed"})
}

// GetUserSubscriptions handles GET /api/realtime/user/{userID}/subscriptions
func (rh *RealTimeEventHandlers) GetUserSubscriptions(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	subscriptions, err := rh.service.GetUserSubscriptions(r.Context(), userID)
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"subscriptions": subscriptions})
}

// PublishToChannel handles POST /api/realtime/publish/{channel}
func (rh *RealTimeEventHandlers) PublishToChannel(w http.ResponseWriter, r *http.Request) {
	channel := chi.URLParam(r, "channel")
	if channel == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_CHANNEL", "Channel is required"), httputil.GetTraceID(r))
		return
	}

	var req struct {
		Event string                 `json:"event"`
		Data  map[string]interface{} `json:"data"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		rh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.PublishToChannel(r.Context(), channel, req.Event, req.Data); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Dispatch event
	if rh.dispatcher != nil {
		rh.dispatcher.Dispatch(events.Event{
			Type:    events.EventRealTimePublish,
			Channel: channel,
			Data: map[string]interface{}{
				"event":   req.Event,
				"data":    req.Data,
				"channel": channel,
			},
		})
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "published"})
}

// BroadcastEvent handles POST /api/realtime/broadcast
func (rh *RealTimeEventHandlers) BroadcastEvent(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Event string                 `json:"event"`
		Data  map[string]interface{} `json:"data"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		rh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.BroadcastEvent(r.Context(), req.Event, req.Data); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Dispatch event
	if rh.dispatcher != nil {
		rh.dispatcher.Dispatch(events.Event{
			Type:    events.EventRealTimePublish,
			Channel: "broadcast",
			Data: map[string]interface{}{
				"event": req.Event,
				"data":  req.Data,
			},
		})
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "broadcasted"})
}

// SendDirectMessage handles POST /api/realtime/message
func (rh *RealTimeEventHandlers) SendDirectMessage(w http.ResponseWriter, r *http.Request) {
	var req struct {
		FromUserID string `json:"from_user_id"`
		ToUserID   string `json:"to_user_id"`
		Message    string `json:"message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		rh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.SendDirectMessage(r.Context(), req.FromUserID, req.ToUserID, req.Message); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "sent"})
}

// ListAvailableChannels handles GET /api/realtime/channels
func (rh *RealTimeEventHandlers) ListAvailableChannels(w http.ResponseWriter, r *http.Request) {
	channels, err := rh.service.ListAvailableChannels(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"channels": channels})
}

// GetChannelInfo handles GET /api/realtime/channels/{channel}/info
func (rh *RealTimeEventHandlers) GetChannelInfo(w http.ResponseWriter, r *http.Request) {
	channel := chi.URLParam(r, "channel")
	if channel == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_CHANNEL", "Channel is required"), httputil.GetTraceID(r))
		return
	}

	info, err := rh.service.GetChannelInfo(r.Context(), channel)
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(info)
}

// GetChannelSubscribers handles GET /api/realtime/channels/{channel}/subscribers
func (rh *RealTimeEventHandlers) GetChannelSubscribers(w http.ResponseWriter, r *http.Request) {
	channel := chi.URLParam(r, "channel")
	if channel == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_CHANNEL", "Channel is required"), httputil.GetTraceID(r))
		return
	}

	subscribers, err := rh.service.GetChannelSubscribers(r.Context(), channel)
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"subscribers": subscribers})
}

// CreateChannel handles POST /api/realtime/channels
func (rh *RealTimeEventHandlers) CreateChannel(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name        string `json:"name"`
		Description string `json:"description"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		rh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	channelID, err := rh.service.CreateChannel(r.Context(), req.Name, req.Description)
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"channel_id": channelID})
}

// DeleteChannel handles DELETE /api/realtime/channels/{channel}
func (rh *RealTimeEventHandlers) DeleteChannel(w http.ResponseWriter, r *http.Request) {
	channel := chi.URLParam(r, "channel")
	if channel == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_CHANNEL", "Channel is required"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.DeleteChannel(r.Context(), channel); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetActiveConnections handles GET /api/realtime/connections
func (rh *RealTimeEventHandlers) GetActiveConnections(w http.ResponseWriter, r *http.Request) {
	connections, err := rh.service.GetActiveConnections(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(connections)
}

// GetConnectionsByChannel handles GET /api/realtime/connections/by-channel
func (rh *RealTimeEventHandlers) GetConnectionsByChannel(w http.ResponseWriter, r *http.Request) {
	connections, err := rh.service.GetConnectionsByChannel(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"connections": connections})
}

// GetUserPresence handles GET /api/realtime/user/{userID}/presence
func (rh *RealTimeEventHandlers) GetUserPresence(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	presence, err := rh.service.GetUserPresence(r.Context(), userID)
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(presence)
}

// UpdatePresence handles POST /api/realtime/user/{userID}/presence
func (rh *RealTimeEventHandlers) UpdatePresence(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.PresenceUpdateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		rh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.UpdatePresence(r.Context(), userID, &req); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
}

// GetOnlineUsers handles GET /api/realtime/online-users
func (rh *RealTimeEventHandlers) GetOnlineUsers(w http.ResponseWriter, r *http.Request) {
	users, err := rh.service.GetOnlineUsers(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"users": users})
}

// GetUserPresenceHistory handles GET /api/realtime/user/{userID}/presence-history
func (rh *RealTimeEventHandlers) GetUserPresenceHistory(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	limit, offset := 20, 0
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	history, total, err := rh.service.GetUserPresenceHistory(r.Context(), userID, limit, offset)
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"history": history,
		"total":   total,
		"limit":   limit,
		"offset":  offset,
	})
}

// GetPendingEvents handles GET /api/realtime/user/{userID}/pending-events
func (rh *RealTimeEventHandlers) GetPendingEvents(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	events, err := rh.service.GetPendingEvents(r.Context(), userID)
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"events": events})
}

// ClearEventQueue handles DELETE /api/realtime/user/{userID}/event-queue
func (rh *RealTimeEventHandlers) ClearEventQueue(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.ClearEventQueue(r.Context(), userID); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "cleared"})
}

// GetRealtimeStats handles GET /api/realtime/stats
func (rh *RealTimeEventHandlers) GetRealtimeStats(w http.ResponseWriter, r *http.Request) {
	stats, err := rh.service.GetRealtimeStats(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetConnectionStats handles GET /api/realtime/connection-stats
func (rh *RealTimeEventHandlers) GetConnectionStats(w http.ResponseWriter, r *http.Request) {
	stats, err := rh.service.GetConnectionStats(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetEventStats handles GET /api/realtime/event-stats
func (rh *RealTimeEventHandlers) GetEventStats(w http.ResponseWriter, r *http.Request) {
	stats, err := rh.service.GetEventStats(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// CheckConnectionHealth handles GET /api/realtime/health
func (rh *RealTimeEventHandlers) CheckConnectionHealth(w http.ResponseWriter, r *http.Request) {
	health, err := rh.service.CheckConnectionHealth(r.Context())
	if err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

// SendHeartbeat handles POST /api/realtime/user/{userID}/heartbeat
func (rh *RealTimeEventHandlers) SendHeartbeat(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		rh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := rh.service.SendHeartbeat(r.Context(), userID); err != nil {
		rh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "pong"})
}

// RegisterRealTimeEventRoutes registers real-time event routes
func RegisterRealTimeEventRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *RealTimeEventHandlers) {
	r.Post("/subscribe/{channel}", handlers.SubscribeToChannel)
	r.Post("/unsubscribe/{channel}", handlers.UnsubscribeFromChannel)
	r.Get("/user/{userID}/subscriptions", handlers.GetUserSubscriptions)
	r.Post("/publish/{channel}", handlers.PublishToChannel)
	r.Post("/broadcast", handlers.BroadcastEvent)
	r.Post("/message", handlers.SendDirectMessage)
	r.Get("/channels", handlers.ListAvailableChannels)
	r.Get("/channels/{channel}/info", handlers.GetChannelInfo)
	r.Get("/channels/{channel}/subscribers", handlers.GetChannelSubscribers)
	r.Post("/channels", handlers.CreateChannel)
	r.Delete("/channels/{channel}", handlers.DeleteChannel)
	r.Get("/connections", handlers.GetActiveConnections)
	r.Get("/connections/by-channel", handlers.GetConnectionsByChannel)
	r.Get("/user/{userID}/presence", handlers.GetUserPresence)
	r.Post("/user/{userID}/presence", handlers.UpdatePresence)
	r.Get("/online-users", handlers.GetOnlineUsers)
	r.Get("/user/{userID}/presence-history", handlers.GetUserPresenceHistory)
	r.Get("/user/{userID}/pending-events", handlers.GetPendingEvents)
	r.Delete("/user/{userID}/event-queue", handlers.ClearEventQueue)
	r.Get("/stats", handlers.GetRealtimeStats)
	r.Get("/connection-stats", handlers.GetConnectionStats)
	r.Get("/event-stats", handlers.GetEventStats)
	r.Get("/health", handlers.CheckConnectionHealth)
	r.Post("/user/{userID}/heartbeat", handlers.SendHeartbeat)
}
