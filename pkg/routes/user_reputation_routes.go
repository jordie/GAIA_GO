package routes

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"architect/pkg/services/rate_limiting"
)

// RegisterUserReputationRoutes registers user-facing reputation API routes
func RegisterUserReputationRoutes(router *gin.Engine, db *gorm.DB, urs *rate_limiting.UserReputationService) {
	api := router.Group("/api/reputation")
	{
		// Get current user's reputation (requires auth)
		api.GET("/me", func(c *gin.Context) {
			// In production, extract from session/JWT
			userID := c.GetInt("user_id")
			if userID == 0 {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
				return
			}
			getMyReputation(urs)(c)
		})

		// Get reputation for specific user (public or specific permissions)
		api.GET("/user/:userID", getUserReputation(urs))

		// Get tier information
		api.GET("/tiers", getAllTierExplanations(urs))
		api.GET("/tiers/:tier", getTierExplanation(urs))

		// Get FAQ
		api.GET("/faq", getReputationFAQ(urs))

		// User violations and appeals
		api.GET("/violations", func(c *gin.Context) {
			userID := c.GetInt("user_id")
			if userID == 0 {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
				return
			}
			getMyViolations(urs, db)(c)
		})

		// Get trends
		api.GET("/trends", func(c *gin.Context) {
			userID := c.GetInt("user_id")
			if userID == 0 {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
				return
			}
			getReputationTrends(urs)(c)
		})

		// Rate limit status
		api.GET("/rate-limit-status", func(c *gin.Context) {
			userID := c.GetInt("user_id")
			if userID == 0 {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
				return
			}
			getRateLimitStatus(urs)(c)
		})
	}
}

// getMyReputation returns current user's reputation
func getMyReputation(urs *rate_limiting.UserReputationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")

		ctx := c.Request.Context()
		view, err := urs.GetUserReputationView(ctx, userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve reputation"})
			return
		}

		c.JSON(http.StatusOK, view)
	}
}

// getUserReputation returns reputation for a specific user
func getUserReputation(urs *rate_limiting.UserReputationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := strconv.Atoi(c.Param("userID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}

		// Check permissions - in production, would verify access rights
		ctx := c.Request.Context()
		view, err := urs.GetUserReputationView(ctx, userID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
			return
		}

		c.JSON(http.StatusOK, view)
	}
}

// getAllTierExplanations returns all tier information
func getAllTierExplanations(urs *rate_limiting.UserReputationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		tiers := urs.GetAllTierExplanations()

		c.JSON(http.StatusOK, gin.H{
			"tiers": tiers,
			"count": len(tiers),
		})
	}
}

// getTierExplanation returns information for a specific tier
func getTierExplanation(urs *rate_limiting.UserReputationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		tier := c.Param("tier")

		explanation := urs.GetTierExplanation(tier)
		if explanation == nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Tier not found"})
			return
		}

		c.JSON(http.StatusOK, explanation)
	}
}

// getReputationFAQ returns FAQ
func getReputationFAQ(urs *rate_limiting.UserReputationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		faq := urs.GetReputationFAQ()

		c.JSON(http.StatusOK, gin.H{
			"faq":   faq,
			"count": len(faq),
		})
	}
}

// getMyViolations returns current user's violation history
func getMyViolations(urs *rate_limiting.UserReputationService, db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")

		limit := 20
		if l := c.Query("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		violations := urs.GetRecentViolations(userID, limit)

		c.JSON(http.StatusOK, gin.H{
			"user_id":    userID,
			"violations": violations,
			"count":      len(violations),
		})
	}
}

// getRateLimitStatus returns current rate limit status
func getRateLimitStatus(urs *rate_limiting.UserReputationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")

		ctx := c.Request.Context()
		view, err := urs.GetUserReputationView(ctx, userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve status"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"user_id":          userID,
			"rate_limit_info":  view.RateLimitInfo,
			"current_usage_pct": view.RateLimitInfo.UsagePercent,
			"throttle_active":   view.RateLimitInfo.ThrottleMultiplier < 1.0,
		})
	}
}

// getReputationTrends returns reputation trends for user
func getReputationTrends(urs *rate_limiting.UserReputationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")

		days := 30
		if d := c.Query("days"); d != "" {
			if parsed, err := strconv.Atoi(d); err == nil && parsed > 0 && parsed <= 365 {
				days = parsed
			}
		}

		ctx := c.Request.Context()
		trends, err := urs.GetReputationTrends(ctx, userID, days)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve trends"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"user_id": userID,
			"days":    days,
			"trends":  trends,
			"count":   len(trends),
		})
	}
}

// Helper methods for UserReputationService to expose private methods
// These would normally be part of the service

// getRecentViolations wrapper (public)
func (urs *rate_limiting.UserReputationService) GetRecentViolations(userID int, limit int) []rate_limiting.ViolationSummary {
	return urs.getRecentViolations(userID, limit)
}
