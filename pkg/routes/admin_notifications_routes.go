package routes

import (
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"gorm.io/gorm"

	"gaia_go/pkg/services/rate_limiting"
)

// NotificationRoutes registers notification management endpoints
func NotificationRoutes(router chi.Router, db *gorm.DB, ns *rate_limiting.NotificationService) {
	router.Route("/api/notifications", func(r chi.Router) {
		// Get user notifications
		r.Get("/", getNotifications(ns))

		// Mark notification as read
		r.Put("/{notificationID}/read", markAsRead(ns))

		// Mark all as read
		r.Put("/read-all", markAllAsRead(ns))

		// Acknowledge notification
		r.Put("/{notificationID}/acknowledge", acknowledgeNotification(ns))

		// Get unread count
		r.Get("/unread-count", getUnreadCount(ns))

		// Get notification stats
		r.Get("/stats", getNotificationStats(ns))

		// Get notification preferences
		r.Get("/preferences", getNotificationPreferences(ns))

		// Update notification preferences
		r.Put("/preferences", updateNotificationPreferences(ns))
	})

	// Admin routes
	router.Route("/api/admin/notifications", func(r chi.Router) {
		// Get all notifications for user (admin)
		r.Get("/users/{userID}", getAdminNotifications(ns))

		// Delete notification
		r.Delete("/{notificationID}", deleteNotification(ns))

		// Cleanup old notifications
		r.Post("/cleanup", cleanupNotifications(ns))
	})
}

// getNotifications returns current user's notifications
func getNotifications(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: Get current user ID from session/auth
		userID := 1 // Placeholder

		unreadOnly := r.URL.Query().Get("unread") == "true"
		limit := 50
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		notifications, err := ns.GetNotifications(userID, unreadOnly, limit)
		if err != nil {
			http.Error(w, "Error fetching notifications", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, map[string]interface{}{
			"notifications": notifications,
			"total":         len(notifications),
		})
	}
}

// markAsRead marks a notification as read
func markAsRead(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		notificationID, err := strconv.Atoi(chi.URLParam(r, "notificationID"))
		if err != nil {
			http.Error(w, "Invalid notification ID", http.StatusBadRequest)
			return
		}

		if err := ns.MarkAsRead(notificationID); err != nil {
			http.Error(w, "Error marking as read", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": "Notification marked as read",
		})
	}
}

// markAllAsRead marks all notifications as read
func markAllAsRead(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: Get current user ID from session/auth
		userID := 1 // Placeholder

		if err := ns.MarkAllAsRead(userID); err != nil {
			http.Error(w, "Error marking all as read", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": "All notifications marked as read",
		})
	}
}

// acknowledgeNotification acknowledges and reads a notification
func acknowledgeNotification(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		notificationID, err := strconv.Atoi(chi.URLParam(r, "notificationID"))
		if err != nil {
			http.Error(w, "Invalid notification ID", http.StatusBadRequest)
			return
		}

		if err := ns.AcknowledgeNotification(notificationID); err != nil {
			http.Error(w, "Error acknowledging notification", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": "Notification acknowledged",
		})
	}
}

// getUnreadCount returns count of unread notifications
func getUnreadCount(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: Get current user ID from session/auth
		userID := 1 // Placeholder

		count, err := ns.GetUnreadCount(userID)
		if err != nil {
			http.Error(w, "Error fetching unread count", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, map[string]interface{}{
			"unread_count": count,
		})
	}
}

// getNotificationStats returns notification statistics
func getNotificationStats(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: Get current user ID from session/auth
		userID := 1 // Placeholder

		stats, err := ns.GetNotificationStats(userID)
		if err != nil {
			http.Error(w, "Error fetching stats", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, stats)
	}
}

// getNotificationPreferences returns user notification preferences
func getNotificationPreferences(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: Get current user ID from session/auth
		userID := 1 // Placeholder

		prefs, err := ns.GetNotificationPreferences(userID)
		if err != nil {
			http.Error(w, "Error fetching preferences", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, prefs)
	}
}

// updateNotificationPreferences updates user notification preferences
func updateNotificationPreferences(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: Get current user ID from session/auth
		userID := 1 // Placeholder

		var prefs map[string]interface{}
		if err := decodeJSON(r, &prefs); err != nil {
			http.Error(w, "Invalid request body", http.StatusBadRequest)
			return
		}

		if err := ns.UpdateNotificationPreferences(userID, prefs); err != nil {
			http.Error(w, "Error updating preferences", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": "Preferences updated",
		})
	}
}

// Admin Routes

// getAdminNotifications returns notifications for a user (admin only)
func getAdminNotifications(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, err := strconv.Atoi(chi.URLParam(r, "userID"))
		if err != nil {
			http.Error(w, "Invalid user ID", http.StatusBadRequest)
			return
		}

		limit := 50
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		notifications, err := ns.GetNotifications(userID, false, limit)
		if err != nil {
			http.Error(w, "Error fetching notifications", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, map[string]interface{}{
			"user_id":         userID,
			"notifications":   notifications,
			"total":           len(notifications),
		})
	}
}

// deleteNotification deletes a notification (admin)
func deleteNotification(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		notificationID, err := strconv.Atoi(chi.URLParam(r, "notificationID"))
		if err != nil {
			http.Error(w, "Invalid notification ID", http.StatusBadRequest)
			return
		}

		// TODO: Implement actual deletion in database
		_ = notificationID

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": "Notification deleted",
		})
	}
}

// cleanupNotifications removes old notifications
func cleanupNotifications(ns *rate_limiting.NotificationService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Days int `json:"days"`
		}

		if err := decodeJSON(r, &req); err != nil || req.Days <= 0 {
			req.Days = 30 // Default to 30 days
		}

		cutoff := time.Now().AddDate(0, 0, -req.Days)
		count, err := ns.CleanupOldNotifications(cutoff)
		if err != nil {
			http.Error(w, "Error cleaning up notifications", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"deleted": count,
			"message": "Old notifications cleaned up",
		})
	}
}
