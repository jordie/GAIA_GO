package routes

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// RegisterAppealEnhancementsRoutes registers Phase 3 Sprint 3 enhancement routes
func RegisterAppealEnhancementsRoutes(
	router *gin.Engine,
	db *gorm.DB,
	appealSvc *rate_limiting.AppealService,
	analyticsSvc *rate_limiting.AnalyticsService,
	notificationSvc *rate_limiting.AppealNotificationService,
	historySvc *rate_limiting.AppealHistoryService,
	peerAnalyticsSvc *rate_limiting.PeerAnalyticsService,
	bulkOps *rate_limiting.AdminBulkOperationsService,
) {
	// Appeal notification routes (authenticated)
	notifications := router.Group("/api/appeals/notifications")
	{
		notifications.GET("/:appealID", getAppealNotifications(notificationSvc))
		notifications.POST("/:notificationID/read", markNotificationAsRead(notificationSvc))
		notifications.GET("/stats", getNotificationStats(notificationSvc))
	}

	// Appeal history/timeline routes (authenticated)
	timeline := router.Group("/api/appeals/timeline")
	{
		timeline.GET("/:appealID", getAppealTimeline(historySvc))
		timeline.GET("/user/history", getUserAppealHistory(historySvc))
		timeline.GET("/timing/metrics", getTimingMetrics(historySvc))
		timeline.GET("/status/distribution", getStatusDistribution(historySvc))
	}

	// Peer comparison routes (authenticated)
	peer := router.Group("/api/user/peer")
	{
		peer.GET("/comparison", getUserPeerComparison(peerAnalyticsSvc))
		peer.GET("/tier/statistics", getTierStatistics(peerAnalyticsSvc))
		peer.GET("/all-tiers/statistics", getAllTiersStatistics(peerAnalyticsSvc))
		peer.GET("/insights", getPeerInsights(peerAnalyticsSvc))
	}

	// Admin bulk operations routes (admin only)
	admin := router.Group("/api/admin/bulk-operations")
	{
		admin.POST("/approve", bulkApproveAppeals(bulkOps, historySvc))
		admin.POST("/deny", bulkDenyAppeals(bulkOps, historySvc))
		admin.POST("/assign-priority", bulkAssignPriority(bulkOps, historySvc))
		admin.GET("/status/:operationID", getBulkOperationStatus(bulkOps))
		admin.GET("/operations", getAdminBulkOperations(bulkOps))
		admin.GET("/statistics", getBulkOperationStats(bulkOps))
	}
}

// Appeal Notification Routes

// getAppealNotifications returns notifications for an appeal
func getAppealNotifications(notificationSvc *rate_limiting.AppealNotificationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		notifications, err := notificationSvc.GetNotifications(c.Request.Context(), appealID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve notifications"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"notifications": notifications,
			"count":         len(notifications),
		})
	}
}

// markNotificationAsRead marks notification as read
func markNotificationAsRead(notificationSvc *rate_limiting.AppealNotificationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		notificationID, err := strconv.ParseInt(c.Param("notificationID"), 10, 64)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid notification ID"})
			return
		}

		err = notificationSvc.MarkAsRead(c.Request.Context(), notificationID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to mark as read"})
			return
		}

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

// getNotificationStats returns notification statistics
func getNotificationStats(notificationSvc *rate_limiting.AppealNotificationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats, err := notificationSvc.GetNotificationStats(c.Request.Context())
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve stats"})
			return
		}

		c.JSON(http.StatusOK, stats)
	}
}

// Appeal History/Timeline Routes

// getAppealTimeline returns appeal timeline
func getAppealTimeline(historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		timeline, err := historySvc.GetAppealTimeline(c.Request.Context(), appealID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve timeline"})
			return
		}

		c.JSON(http.StatusOK, timeline)
	}
}

// getUserAppealHistory returns user's appeal history
func getUserAppealHistory(historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		limit := 20
		offset := 0

		if l := c.Query("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		if o := c.Query("offset"); o != "" {
			if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
				offset = parsed
			}
		}

		history, err := historySvc.GetUserAppealHistory(c.Request.Context(), userID, limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve history"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"history": history,
			"count":   len(history),
		})
	}
}

// getTimingMetrics returns timing metrics
func getTimingMetrics(historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		metrics, err := historySvc.GetTimingMetrics(c.Request.Context())
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve metrics"})
			return
		}

		c.JSON(http.StatusOK, metrics)
	}
}

// getStatusDistribution returns status distribution
func getStatusDistribution(historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		distribution, err := historySvc.GetStatusDistribution(c.Request.Context())
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve distribution"})
			return
		}

		c.JSON(http.StatusOK, distribution)
	}
}

// Peer Comparison Routes

// getUserPeerComparison returns user's peer comparison
func getUserPeerComparison(peerAnalyticsSvc *rate_limiting.PeerAnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		comparison, err := peerAnalyticsSvc.GetUserPeerComparison(c.Request.Context(), userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve comparison"})
			return
		}

		c.JSON(http.StatusOK, comparison)
	}
}

// getTierStatistics returns tier statistics
func getTierStatistics(peerAnalyticsSvc *rate_limiting.PeerAnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		tier := c.Query("tier")
		if tier == "" {
			tier = "standard"
		}

		stats, err := peerAnalyticsSvc.GetTierStatistics(c.Request.Context(), tier)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve statistics"})
			return
		}

		c.JSON(http.StatusOK, stats)
	}
}

// getAllTiersStatistics returns statistics for all tiers
func getAllTiersStatistics(peerAnalyticsSvc *rate_limiting.PeerAnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats, err := peerAnalyticsSvc.GetAllTiersStatistics(c.Request.Context())
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve statistics"})
			return
		}

		c.JSON(http.StatusOK, stats)
	}
}

// getPeerInsights returns personalized peer insights
func getPeerInsights(peerAnalyticsSvc *rate_limiting.PeerAnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		insights, err := peerAnalyticsSvc.GetInsights(c.Request.Context(), userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve insights"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"insights": insights,
			"count":    len(insights),
		})
	}
}

// Admin Bulk Operations Routes

// bulkApproveAppeals bulk approves appeals
func bulkApproveAppeals(bulkOps *rate_limiting.AdminBulkOperationsService, historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		adminID := c.GetInt("user_id")
		if adminID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		var req struct {
			Criteria       map[string]interface{} `json:"criteria" binding:"required"`
			ApprovedPoints float64                `json:"approved_points" binding:"required"`
			Comment        string                 `json:"comment"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		operation, err := bulkOps.BulkApproveAppeals(
			c.Request.Context(),
			adminID,
			req.Criteria,
			req.ApprovedPoints,
			req.Comment,
		)

		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, operation)
	}
}

// bulkDenyAppeals bulk denies appeals
func bulkDenyAppeals(bulkOps *rate_limiting.AdminBulkOperationsService, historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		adminID := c.GetInt("user_id")
		if adminID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		var req struct {
			Criteria        map[string]interface{} `json:"criteria" binding:"required"`
			RejectionReason string                 `json:"rejection_reason" binding:"required"`
			Comment         string                 `json:"comment"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		operation, err := bulkOps.BulkDenyAppeals(
			c.Request.Context(),
			adminID,
			req.Criteria,
			req.RejectionReason,
			req.Comment,
		)

		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, operation)
	}
}

// bulkAssignPriority bulk assigns priority
func bulkAssignPriority(bulkOps *rate_limiting.AdminBulkOperationsService, historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		adminID := c.GetInt("user_id")
		if adminID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		var req struct {
			Criteria  map[string]interface{} `json:"criteria" binding:"required"`
			Priority  string                 `json:"priority" binding:"required"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		operation, err := bulkOps.BulkAssignPriority(
			c.Request.Context(),
			adminID,
			req.Criteria,
			rate_limiting.AppealPriority(req.Priority),
		)

		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, operation)
	}
}

// getBulkOperationStatus returns bulk operation status
func getBulkOperationStatus(bulkOps *rate_limiting.AdminBulkOperationsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		operationID := c.Param("operationID")
		if operationID == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid operation ID"})
			return
		}

		operation, err := bulkOps.GetBulkOperationStatus(c.Request.Context(), operationID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Operation not found"})
			return
		}

		c.JSON(http.StatusOK, operation)
	}
}

// getAdminBulkOperations returns admin's bulk operations
func getAdminBulkOperations(bulkOps *rate_limiting.AdminBulkOperationsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		adminID := c.GetInt("user_id")
		if adminID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		limit := 20
		offset := 0

		if l := c.Query("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
				limit = parsed
			}
		}

		if o := c.Query("offset"); o != "" {
			if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
				offset = parsed
			}
		}

		operations, err := bulkOps.GetAdminBulkOperations(c.Request.Context(), adminID, limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve operations"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"operations": operations,
			"count":      len(operations),
		})
	}
}

// getBulkOperationStats returns bulk operation statistics
func getBulkOperationStats(bulkOps *rate_limiting.AdminBulkOperationsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats, err := bulkOps.GetBulkOperationStats(c.Request.Context())
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve statistics"})
			return
		}

		c.JSON(http.StatusOK, stats)
	}
}
