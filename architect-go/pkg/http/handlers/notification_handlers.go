package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"architect-go/pkg/errors"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// NotificationHandlers handles notification management HTTP requests
type NotificationHandlers struct {
	service    services.NotificationService
	errHandler *errors.Handler
}

// NewNotificationHandlers creates new notification handlers
func NewNotificationHandlers(service services.NotificationService, errHandler *errors.Handler) *NotificationHandlers {
	return &NotificationHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// CreateNotification handles POST /api/notifications
func (nh *NotificationHandlers) CreateNotification(w http.ResponseWriter, r *http.Request) {
	var req services.CreateNotificationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	notification, err := nh.service.CreateNotification(r.Context(), &req)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{"notification": notification})
}

// GetNotification handles GET /api/notifications/{id}
func (nh *NotificationHandlers) GetNotification(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	notification, err := nh.service.GetNotification(r.Context(), id)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"notification": notification})
}

// ListNotifications handles GET /api/notifications/user/{userID} or GET /api/notifications
func (nh *NotificationHandlers) ListNotifications(w http.ResponseWriter, r *http.Request) {
	// Accept userID from path param or query string
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		userID = r.URL.Query().Get("user_id")
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

	notifications, total, err := nh.service.ListNotifications(r.Context(), userID, limit, offset)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"notifications": notifications,
		"total":         total,
		"limit":         limit,
		"offset":        offset,
	})
}

// ListUnreadNotifications handles GET /api/notifications/user/{userID}/unread or GET /api/notifications/unread
func (nh *NotificationHandlers) ListUnreadNotifications(w http.ResponseWriter, r *http.Request) {
	// Accept userID from path param or query string
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		userID = r.URL.Query().Get("user_id")
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

	notifications, total, err := nh.service.ListUnreadNotifications(r.Context(), userID, limit, offset)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"notifications": notifications,
		"total":         total,
		"limit":         limit,
		"offset":        offset,
	})
}

// ListRecentNotifications handles GET /api/notifications/user/{userID}/recent
func (nh *NotificationHandlers) ListRecentNotifications(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	limit := 10
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	notifications, err := nh.service.ListRecentNotifications(r.Context(), userID, limit)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"notifications": notifications})
}

// SendNotification handles POST /api/notifications/send
func (nh *NotificationHandlers) SendNotification(w http.ResponseWriter, r *http.Request) {
	var req services.SendNotificationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.SendNotification(r.Context(), &req); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "sent"})
}

// SendBulkNotifications handles POST /api/notifications/send-bulk
func (nh *NotificationHandlers) SendBulkNotifications(w http.ResponseWriter, r *http.Request) {
	var req struct {
		NotificationID string   `json:"notification_id"`
		UserIDs        []string `json:"user_ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.SendBulkNotifications(r.Context(), req.NotificationID, req.UserIDs); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "sent"})
}

// UpdateNotification handles PUT /api/notifications/{id}
func (nh *NotificationHandlers) UpdateNotification(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.CreateNotificationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	notification, err := nh.service.UpdateNotification(r.Context(), id, &req)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(notification)
}

// DeleteNotification handles DELETE /api/notifications/{id}
func (nh *NotificationHandlers) DeleteNotification(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.DeleteNotification(r.Context(), id); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// MarkAsRead handles POST /api/notifications/{id}/mark-read
func (nh *NotificationHandlers) MarkAsRead(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.MarkAsRead(r.Context(), id); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "marked_read"})
}

// MarkAllAsRead handles POST /api/notifications/user/{userID}/mark-all-read
func (nh *NotificationHandlers) MarkAllAsRead(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.MarkAllAsRead(r.Context(), userID); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "marked_read"})
}

// MarkAsUnread handles POST /api/notifications/{id}/mark-unread
func (nh *NotificationHandlers) MarkAsUnread(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.MarkAsUnread(r.Context(), id); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "marked_unread"})
}

// DismissNotification handles POST /api/notifications/{id}/dismiss
func (nh *NotificationHandlers) DismissNotification(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.DismissNotification(r.Context(), id); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "dismissed"})
}

// GetUserPreferences handles GET /api/notifications/user/{userID}/preferences
func (nh *NotificationHandlers) GetUserPreferences(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	preferences, err := nh.service.GetUserPreferences(r.Context(), userID)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(preferences)
}

// UpdateUserPreferences handles PUT /api/notifications/user/{userID}/preferences
func (nh *NotificationHandlers) UpdateUserPreferences(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.NotificationPreferencesRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.UpdateUserPreferences(r.Context(), userID, &req); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
}

// GetAvailableChannels handles GET /api/notifications/channels
func (nh *NotificationHandlers) GetAvailableChannels(w http.ResponseWriter, r *http.Request) {
	channels, err := nh.service.GetAvailableChannels(r.Context())
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"channels": channels})
}

// TestChannel handles POST /api/notifications/test-channel/{channel}
func (nh *NotificationHandlers) TestChannel(w http.ResponseWriter, r *http.Request) {
	channel := chi.URLParam(r, "channel")
	if channel == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_CHANNEL", "Channel is required"), httputil.GetTraceID(r))
		return
	}

	var req struct {
		UserID string `json:"user_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.TestChannel(r.Context(), channel, req.UserID); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "sent"})
}

// GetAvailableTemplates handles GET /api/notifications/templates
func (nh *NotificationHandlers) GetAvailableTemplates(w http.ResponseWriter, r *http.Request) {
	templates, err := nh.service.GetAvailableTemplates(r.Context())
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"templates": templates})
}

// GetTemplateByID handles GET /api/notifications/templates/{templateID}
func (nh *NotificationHandlers) GetTemplateByID(w http.ResponseWriter, r *http.Request) {
	templateID := chi.URLParam(r, "templateID")
	if templateID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TEMPLATE_ID", "Template ID is required"), httputil.GetTraceID(r))
		return
	}

	template, err := nh.service.GetTemplateByID(r.Context(), templateID)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(template)
}

// CreateTemplate handles POST /api/notifications/templates
func (nh *NotificationHandlers) CreateTemplate(w http.ResponseWriter, r *http.Request) {
	var req services.TemplateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	template, err := nh.service.CreateTemplate(r.Context(), &req)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(template)
}

// UpdateTemplate handles PUT /api/notifications/templates/{templateID}
func (nh *NotificationHandlers) UpdateTemplate(w http.ResponseWriter, r *http.Request) {
	templateID := chi.URLParam(r, "templateID")
	if templateID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TEMPLATE_ID", "Template ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.TemplateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	template, err := nh.service.UpdateTemplate(r.Context(), templateID, &req)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(template)
}

// DeleteTemplate handles DELETE /api/notifications/templates/{templateID}
func (nh *NotificationHandlers) DeleteTemplate(w http.ResponseWriter, r *http.Request) {
	templateID := chi.URLParam(r, "templateID")
	if templateID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TEMPLATE_ID", "Template ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.DeleteTemplate(r.Context(), templateID); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// PreviewTemplate handles POST /api/notifications/templates/{templateID}/preview
func (nh *NotificationHandlers) PreviewTemplate(w http.ResponseWriter, r *http.Request) {
	templateID := chi.URLParam(r, "templateID")
	if templateID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TEMPLATE_ID", "Template ID is required"), httputil.GetTraceID(r))
		return
	}

	var data map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	preview, err := nh.service.PreviewTemplate(r.Context(), templateID, data)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"preview": preview})
}

// GetDeliveryStatus handles GET /api/notifications/{notificationID}/delivery-status
func (nh *NotificationHandlers) GetDeliveryStatus(w http.ResponseWriter, r *http.Request) {
	notificationID := chi.URLParam(r, "notificationID")
	if notificationID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_NOTIFICATION_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := nh.service.GetDeliveryStatus(r.Context(), notificationID)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"delivery_status": status})
}

// GetDeliveryHistory handles GET /api/notifications/user/{userID}/delivery-history
func (nh *NotificationHandlers) GetDeliveryHistory(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
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

	history, total, err := nh.service.GetDeliveryHistory(r.Context(), userID, limit, offset)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"delivery_history": history,
		"total":            total,
		"limit":            limit,
		"offset":           offset,
	})
}

// GetNotificationStats handles GET /api/notifications/user/{userID}/stats
func (nh *NotificationHandlers) GetNotificationStats(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	stats, err := nh.service.GetNotificationStats(r.Context(), userID)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetProjectNotifications handles GET /api/notifications/project/{projectID}
func (nh *NotificationHandlers) GetProjectNotifications(w http.ResponseWriter, r *http.Request) {
	projectID := chi.URLParam(r, "projectID")
	if projectID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PROJECT_ID", "Project ID is required"), httputil.GetTraceID(r))
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

	notifications, total, err := nh.service.GetProjectNotifications(r.Context(), projectID, limit, offset)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"notifications": notifications,
		"total":         total,
		"limit":         limit,
		"offset":        offset,
	})
}

// SearchNotifications handles GET /api/notifications/search
func (nh *NotificationHandlers) SearchNotifications(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")
	if query == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_QUERY", "Search query is required"), httputil.GetTraceID(r))
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

	notifications, total, err := nh.service.SearchNotifications(r.Context(), query, limit, offset)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"notifications": notifications,
		"total":         total,
		"limit":         limit,
		"offset":        offset,
	})
}

// ScheduleNotification handles POST /api/notifications/schedule
func (nh *NotificationHandlers) ScheduleNotification(w http.ResponseWriter, r *http.Request) {
	var req services.ScheduleNotificationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		nh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	notificationID, err := nh.service.ScheduleNotification(r.Context(), &req)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"notification_id": notificationID})
}

// GetScheduledNotifications handles GET /api/notifications/user/{userID}/scheduled
func (nh *NotificationHandlers) GetScheduledNotifications(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
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

	notifications, total, err := nh.service.GetScheduledNotifications(r.Context(), userID, limit, offset)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"notifications": notifications,
		"total":         total,
		"limit":         limit,
		"offset":        offset,
	})
}

// CancelScheduledNotification handles POST /api/notifications/{notificationID}/cancel-schedule
func (nh *NotificationHandlers) CancelScheduledNotification(w http.ResponseWriter, r *http.Request) {
	notificationID := chi.URLParam(r, "notificationID")
	if notificationID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_NOTIFICATION_ID", "Notification ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.CancelScheduledNotification(r.Context(), notificationID); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "cancelled"})
}

// SubscribeToTopic handles POST /api/notifications/user/{userID}/subscribe/{topic}
func (nh *NotificationHandlers) SubscribeToTopic(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	topic := chi.URLParam(r, "topic")
	if userID == "" || topic == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PARAMS", "User ID and topic are required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.SubscribeToTopic(r.Context(), userID, topic); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "subscribed"})
}

// UnsubscribeFromTopic handles POST /api/notifications/user/{userID}/unsubscribe/{topic}
func (nh *NotificationHandlers) UnsubscribeFromTopic(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	topic := chi.URLParam(r, "topic")
	if userID == "" || topic == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PARAMS", "User ID and topic are required"), httputil.GetTraceID(r))
		return
	}

	if err := nh.service.UnsubscribeFromTopic(r.Context(), userID, topic); err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "unsubscribed"})
}

// GetUserTopics handles GET /api/notifications/user/{userID}/topics
func (nh *NotificationHandlers) GetUserTopics(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		nh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	topics, err := nh.service.GetUserTopics(r.Context(), userID)
	if err != nil {
		nh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"topics": topics})
}

// RegisterNotificationRoutes registers notification routes
func RegisterNotificationRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Put(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *NotificationHandlers) {
	r.Post("/", handlers.CreateNotification)
	r.Get("/{id}", handlers.GetNotification)
	r.Put("/{id}", handlers.UpdateNotification)
	r.Delete("/{id}", handlers.DeleteNotification)
	r.Post("/send", handlers.SendNotification)
	r.Post("/send-bulk", handlers.SendBulkNotifications)
	r.Post("/{id}/mark-read", handlers.MarkAsRead)
	r.Post("/{id}/mark-unread", handlers.MarkAsUnread)
	r.Post("/{id}/dismiss", handlers.DismissNotification)
	r.Get("/user/{userID}", handlers.ListNotifications)
	r.Get("/user/{userID}/unread", handlers.ListUnreadNotifications)
	r.Get("/user/{userID}/recent", handlers.ListRecentNotifications)
	r.Get("/user/{userID}/preferences", handlers.GetUserPreferences)
	r.Put("/user/{userID}/preferences", handlers.UpdateUserPreferences)
	r.Post("/user/{userID}/mark-all-read", handlers.MarkAllAsRead)
	r.Post("/user/{userID}/subscribe/{topic}", handlers.SubscribeToTopic)
	r.Post("/user/{userID}/unsubscribe/{topic}", handlers.UnsubscribeFromTopic)
	r.Get("/user/{userID}/topics", handlers.GetUserTopics)
	r.Get("/user/{userID}/stats", handlers.GetNotificationStats)
	r.Get("/user/{userID}/delivery-history", handlers.GetDeliveryHistory)
	r.Get("/user/{userID}/scheduled", handlers.GetScheduledNotifications)
	r.Get("/channels", handlers.GetAvailableChannels)
	r.Post("/test-channel/{channel}", handlers.TestChannel)
	r.Get("/templates", handlers.GetAvailableTemplates)
	r.Get("/templates/{templateID}", handlers.GetTemplateByID)
	r.Post("/templates", handlers.CreateTemplate)
	r.Put("/templates/{templateID}", handlers.UpdateTemplate)
	r.Delete("/templates/{templateID}", handlers.DeleteTemplate)
	r.Post("/templates/{templateID}/preview", handlers.PreviewTemplate)
	r.Get("/{notificationID}/delivery-status", handlers.GetDeliveryStatus)
	r.Get("/project/{projectID}", handlers.GetProjectNotifications)
	r.Get("/search", handlers.SearchNotifications)
	r.Post("/schedule", handlers.ScheduleNotification)
	r.Post("/{notificationID}/cancel-schedule", handlers.CancelScheduledNotification)
}
