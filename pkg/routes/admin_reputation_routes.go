package routes

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"gorm.io/gorm"

	"gaia_go/pkg/services/rate_limiting"
)

// AdminReputationRoutes registers reputation management endpoints
func AdminReputationRoutes(router chi.Router, db *gorm.DB, rm *rate_limiting.ReputationManager) {
	// Serve admin dashboard HTML
	router.Get("/admin/reputation", serveReputationDashboard())

	router.Route("/api/admin/reputation", func(r chi.Router) {
		// List all users with their reputation
		r.Get("/users", listUsers(rm))

		// Get specific user reputation
		r.Get("/users/{userID}", getUser(rm))

		// Get user reputation history
		r.Get("/users/{userID}/history", getUserHistory(rm))

		// Get user reputation events
		r.Get("/users/{userID}/events", getUserEvents(rm))

		// Update user reputation (admin override)
		r.Put("/users/{userID}", updateUserReputation(rm))

		// Set VIP tier for user
		r.Post("/users/{userID}/vip", setVIPTier(rm))

		// Remove VIP tier from user
		r.Delete("/users/{userID}/vip", removeVIPTier(rm))

		// Get all reputation tiers
		r.Get("/tiers", getTiers())

		// Get reputation statistics
		r.Get("/stats", getStats(rm))

		// Get reputation trends
		r.Get("/trends", getTrends(rm))

		// Trigger decay for all users
		r.Post("/decay", triggerDecay(rm))
	})
}

// listUsers returns all users with reputation scores
func listUsers(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Get pagination params
		page := 1
		limit := 50

		if p := r.URL.Query().Get("page"); p != "" {
			if parsed, err := strconv.Atoi(p); err == nil && parsed > 0 {
				page = parsed
			}
		}

		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		// Get all users from reputation system
		users, total, err := rm.GetAllUsers(page, limit)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error fetching users: %v", err), http.StatusInternalServerError)
			return
		}

		// Format response
		response := map[string]interface{}{
			"users":       users,
			"total":       total,
			"page":        page,
			"limit":       limit,
			"total_pages": (total + limit - 1) / limit,
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, response)
	}
}

// getUser returns reputation details for a specific user
func getUser(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, err := strconv.Atoi(chi.URLParam(r, "userID"))
		if err != nil {
			http.Error(w, "Invalid user ID", http.StatusBadRequest)
			return
		}

		rep, err := rm.GetUserReputation(userID)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error fetching reputation: %v", err), http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, rep)
	}
}

// getUserHistory returns reputation history for a user
func getUserHistory(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, err := strconv.Atoi(chi.URLParam(r, "userID"))
		if err != nil {
			http.Error(w, "Invalid user ID", http.StatusBadRequest)
			return
		}

		// Get optional days parameter (default 7)
		days := 7
		if d := r.URL.Query().Get("days"); d != "" {
			if parsed, err := strconv.Atoi(d); err == nil && parsed > 0 {
				days = parsed
			}
		}

		history, err := rm.GetRepHistory(userID, days)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error fetching history: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, map[string]interface{}{
			"user_id": userID,
			"days":    days,
			"history": history,
		})
	}
}

// getUserEvents returns recent events for a user
func getUserEvents(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, err := strconv.Atoi(chi.URLParam(r, "userID"))
		if err != nil {
			http.Error(w, "Invalid user ID", http.StatusBadRequest)
			return
		}

		// Get pagination params
		limit := 20
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		// Get event type filter (optional)
		eventType := r.URL.Query().Get("type")

		events, total, err := rm.GetUserEvents(userID, limit, eventType)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error fetching events: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, map[string]interface{}{
			"user_id": userID,
			"events":  events,
			"total":   total,
			"limit":   limit,
		})
	}
}

// updateUserReputation allows admin override of user reputation
func updateUserReputation(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, err := strconv.Atoi(chi.URLParam(r, "userID"))
		if err != nil {
			http.Error(w, "Invalid user ID", http.StatusBadRequest)
			return
		}

		var req struct {
			Score       int    `json:"score"`
			Tier        string `json:"tier"`
			Description string `json:"description"`
		}

		if err := decodeJSON(r, &req); err != nil {
			http.Error(w, "Invalid request body", http.StatusBadRequest)
			return
		}

		// Validate score range
		if req.Score < 0 || req.Score > 100 {
			http.Error(w, "Score must be between 0 and 100", http.StatusBadRequest)
			return
		}

		// Update reputation
		err = rm.SetUserReputation(userID, req.Score, req.Description)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error updating reputation: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": fmt.Sprintf("Updated user %d reputation to %d", userID, req.Score),
		})
	}
}

// setVIPTier sets VIP tier for a user
func setVIPTier(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, err := strconv.Atoi(chi.URLParam(r, "userID"))
		if err != nil {
			http.Error(w, "Invalid user ID", http.StatusBadRequest)
			return
		}

		var req struct {
			Tier      string    `json:"tier"`
			ExpiresAt *time.Time `json:"expires_at"`
			Reason    string    `json:"reason"`
		}

		if err := decodeJSON(r, &req); err != nil {
			http.Error(w, "Invalid request body", http.StatusBadRequest)
			return
		}

		// Default tier if not specified
		if req.Tier == "" {
			req.Tier = "premium"
		}

		// Set VIP tier
		err = rm.SetVIPTier(userID, req.Tier, req.ExpiresAt, req.Reason)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error setting VIP tier: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": fmt.Sprintf("Set user %d to VIP tier: %s", userID, req.Tier),
		})
	}
}

// removeVIPTier removes VIP tier from a user
func removeVIPTier(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, err := strconv.Atoi(chi.URLParam(r, "userID"))
		if err != nil {
			http.Error(w, "Invalid user ID", http.StatusBadRequest)
			return
		}

		// Remove VIP tier
		err = rm.RemoveVIPTier(userID)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error removing VIP tier: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": fmt.Sprintf("Removed VIP tier from user %d", userID),
		})
	}
}

// getTiers returns all available reputation tiers
func getTiers() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		tiers := map[string]interface{}{
			"tiers": []map[string]interface{}{
				{
					"name":        "flagged",
					"score_range": "0-20",
					"multiplier":  0.5,
					"description": "User has multiple violations, rate limits are halved",
				},
				{
					"name":        "standard",
					"score_range": "20-80",
					"multiplier":  1.0,
					"description": "Normal user with default rate limits",
				},
				{
					"name":        "trusted",
					"score_range": "80-100",
					"multiplier":  1.5,
					"description": "Well-behaved user, rate limits are increased by 50%",
				},
				{
					"name":        "premium",
					"score_range": "100+",
					"multiplier":  2.0,
					"description": "Premium VIP user, double rate limits",
				},
			},
			"decay_settings": map[string]interface{}{
				"weekly_decay":       5,
				"direction":          "towards_neutral",
				"neutral_score":      50,
				"min_score":          0,
				"max_score":          100,
			},
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, tiers)
	}
}

// getStats returns reputation system statistics
func getStats(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		stats, err := rm.GetRepStats()
		if err != nil {
			http.Error(w, fmt.Sprintf("Error fetching stats: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, stats)
	}
}

// getTrends returns reputation trends over time
func getTrends(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Get optional days parameter (default 7)
		days := 7
		if d := r.URL.Query().Get("days"); d != "" {
			if parsed, err := strconv.Atoi(d); err == nil && parsed > 0 {
				days = parsed
			}
		}

		trends, err := rm.GetRepTrends(days)
		if err != nil {
			http.Error(w, fmt.Sprintf("Error fetching trends: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		encodeJSON(w, map[string]interface{}{
			"days":   days,
			"trends": trends,
		})
	}
}

// triggerDecay triggers reputation decay for all users
func triggerDecay(rm *rate_limiting.ReputationManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		count, err := rm.ApplyRepDecayAll()
		if err != nil {
			http.Error(w, fmt.Sprintf("Error applying decay: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		encodeJSON(w, map[string]interface{}{
			"success": true,
			"message": fmt.Sprintf("Applied reputation decay to %d users", count),
		})
	}
}

// serveReputationDashboard serves the admin reputation dashboard
func serveReputationDashboard() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		// Serve from templates/admin_reputation.html
		// This would typically be embedded or served from static files
		// For now, return a simple HTML stub with instructions
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`
<!DOCTYPE html>
<html>
<head>
	<title>Reputation Dashboard</title>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
	<div id="app"></div>
	<p>Dashboard loading... Please check that templates/admin_reputation.html is properly served.</p>
	<p><a href="/api/admin/reputation/stats">View API Stats</a></p>
</body>
</html>
		`))
	}
}

// Helper functions for JSON encoding/decoding
func encodeJSON(w http.ResponseWriter, v interface{}) {
	if data, err := json.Marshal(v); err == nil {
		w.Write(data)
	}
}

func decodeJSON(r *http.Request, v interface{}) error {
	defer r.Body.Close()
	return json.NewDecoder(r.Body).Decode(v)
}
