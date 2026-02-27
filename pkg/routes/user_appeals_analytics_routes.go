package routes

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"architect/pkg/services/rate_limiting"
)

// RegisterUserAppealsAnalyticsRoutes registers appeal and analytics API routes
func RegisterUserAppealsAnalyticsRoutes(router *gin.Engine, db *gorm.DB,
	appealSvc *rate_limiting.AppealService, analyticsSvc *rate_limiting.AnalyticsService) {

	// User appeal routes (authenticated)
	appeals := router.Group("/api/appeals")
	{
		appeals.POST("/submit", submitAppeal(appealSvc))
		appeals.GET("/my-appeals", getMyAppeals(appealSvc))
		appeals.GET("/my-appeals/:status", getMyAppealsByStatus(appealSvc))
		appeals.GET("/:appealID", getAppealDetails(appealSvc))
		appeals.DELETE("/:appealID", withdrawAppeal(appealSvc))
		appeals.GET("/reasons", getAppealReasons(appealSvc))
		appeals.GET("/stats", getMyAppealStats(appealSvc))
	}

	// Analytics routes (authenticated)
	analytics := router.Group("/api/analytics")
	{
		analytics.GET("/trends", getTrendAnalysis(analyticsSvc))
		analytics.GET("/trends/:days", getTrendAnalysisDays(analyticsSvc))
		analytics.GET("/patterns", getBehaviorPatterns(analyticsSvc))
		analytics.GET("/recommendations", getRecommendations(analyticsSvc))
		analytics.GET("/usage-patterns", getUsagePatterns(analyticsSvc))
	}

	// Admin appeal routes
	admin := router.Group("/api/admin/appeals")
	{
		admin.GET("/pending", getPendingAppeals(appealSvc))
		admin.GET("/metrics", getAppealMetrics(appealSvc))
		admin.POST("/:appealID/review", reviewAppeal(appealSvc))
		admin.GET("/queue", getAppealQueue(db))
	}
}

// submitAppeal submits a new appeal
func submitAppeal(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		var req struct {
			ViolationID    int    `json:"violation_id" binding:"required"`
			Reason         string `json:"reason" binding:"required"`
			Description    string `json:"description" binding:"required"`
			Evidence       string `json:"evidence"`
			RequestedAction string `json:"requested_action" binding:"required"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		ctx := c.Request.Context()
		appeal, err := appealSvc.SubmitAppeal(ctx, userID, req.ViolationID, struct {
			Reason          string
			Description     string
			Evidence        string
			RequestedAction string
		}{
			Reason:          req.Reason,
			Description:     req.Description,
			Evidence:        req.Evidence,
			RequestedAction: req.RequestedAction,
		})

		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, appeal)
	}
}

// getMyAppeals returns user's appeals
func getMyAppeals(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		ctx := c.Request.Context()
		appeals, err := appealSvc.GetUserAppeals(ctx, userID, nil)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve appeals"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"appeals": appeals,
			"count":   len(appeals),
		})
	}
}

// getMyAppealsByStatus returns appeals filtered by status
func getMyAppealsByStatus(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		status := rate_limiting.AppealStatus(c.Param("status"))
		ctx := c.Request.Context()
		appeals, err := appealSvc.GetUserAppeals(ctx, userID, &status)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve appeals"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":  status,
			"appeals": appeals,
			"count":   len(appeals),
		})
	}
}

// getAppealDetails returns single appeal details
func getAppealDetails(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		// TODO: Implement appeal details retrieval with permission check
		c.JSON(http.StatusOK, gin.H{"message": "Appeal details endpoint"})
	}
}

// withdrawAppeal allows user to withdraw their appeal
func withdrawAppeal(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		ctx := c.Request.Context()
		err = appealSvc.WithdrawAppeal(ctx, userID, appealID)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

// getAppealReasons returns available appeal reasons
func getAppealReasons(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()
		reasons, err := appealSvc.GetAppealReasons(ctx)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve reasons"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"reasons": reasons,
			"count":   len(reasons),
		})
	}
}

// getMyAppealStats returns user's appeal statistics
func getMyAppealStats(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		ctx := c.Request.Context()
		stats, err := appealSvc.GetAppealStats(ctx, userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve stats"})
			return
		}

		c.JSON(http.StatusOK, stats)
	}
}

// getTrendAnalysis returns reputation trends
func getTrendAnalysis(analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		ctx := c.Request.Context()
		trends, err := analyticsSvc.GetReputationTrends(ctx, userID, 30)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve trends"})
			return
		}

		c.JSON(http.StatusOK, trends)
	}
}

// getTrendAnalysisDays returns trends for specific number of days
func getTrendAnalysisDays(analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		days, err := strconv.Atoi(c.Param("days"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid days value"})
			return
		}

		ctx := c.Request.Context()
		trends, err := analyticsSvc.GetReputationTrends(ctx, userID, days)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve trends"})
			return
		}

		c.JSON(http.StatusOK, trends)
	}
}

// getBehaviorPatterns returns detected behavior patterns
func getBehaviorPatterns(analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		ctx := c.Request.Context()
		patterns, err := analyticsSvc.GetBehaviorPatterns(ctx, userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve patterns"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"patterns": patterns,
			"count":    len(patterns),
		})
	}
}

// getRecommendations returns personalized recommendations
func getRecommendations(analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		ctx := c.Request.Context()
		recommendations, err := analyticsSvc.GetPersonalizedRecommendations(ctx, userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve recommendations"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"recommendations": recommendations,
			"count":          len(recommendations),
		})
	}
}

// getUsagePatterns returns usage pattern analysis
func getUsagePatterns(analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		ctx := c.Request.Context()
		patterns, err := analyticsSvc.GetUsagePatterns(ctx, userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve usage patterns"})
			return
		}

		c.JSON(http.StatusOK, patterns)
	}
}

// Admin routes

// getPendingAppeals returns appeals pending review
func getPendingAppeals(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := 50
		if l := c.Query("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		ctx := c.Request.Context()
		appeals, err := appealSvc.GetPendingAppeals(ctx, limit)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve appeals"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"appeals": appeals,
			"count":   len(appeals),
		})
	}
}

// getAppealMetrics returns appeal statistics
func getAppealMetrics(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()
		metrics, err := appealSvc.GetAppealMetrics(ctx)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve metrics"})
			return
		}

		c.JSON(http.StatusOK, metrics)
	}
}

// reviewAppeal processes an appeal review
func reviewAppeal(appealSvc *rate_limiting.AppealService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		var req struct {
			Action         string  `json:"action" binding:"required"`
			ApprovedPoints *float64 `json:"approved_points"`
			Comment        string  `json:"comment"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		reviewedBy := "admin" // Would come from session
		action := rate_limiting.AppealStatus(req.Action)
		approvedPoints := 0.0
		if req.ApprovedPoints != nil {
			approvedPoints = *req.ApprovedPoints
		}

		ctx := c.Request.Context()
		err = appealSvc.ReviewAppeal(ctx, appealID, reviewedBy, action, approvedPoints, req.Comment)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

// getAppealQueue returns appeals in priority order
func getAppealQueue(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		// TODO: Implement appeal queue retrieval from view
		c.JSON(http.StatusOK, gin.H{"queue": []interface{}{}})
	}
}
