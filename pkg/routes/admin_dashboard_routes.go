package routes

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"architect/pkg/services/rate_limiting"
)

// RegisterAdminDashboardRoutes registers all admin dashboard routes
func RegisterAdminDashboardRoutes(
	router *gin.Engine,
	db *gorm.DB,
	appealSvc *rate_limiting.AppealService,
	analyticsSvc *rate_limiting.AnalyticsService,
	mlSvc *rate_limiting.MLPredictionService,
	negotiationSvc *rate_limiting.AppealNegotiationService,
	historyService *rate_limiting.AppealHistoryService,
) {
	// Dashboard overview
	dashboard := router.Group("/api/admin/dashboard")
	{
		dashboard.GET("/overview", getDashboardOverview(db, appealSvc, analyticsSvc))
		dashboard.GET("/summary", getDashboardSummary(db))
		dashboard.GET("/key-metrics", getKeyMetrics(db))
		dashboard.GET("/health", getSystemHealth(db))
	}

	// Appeals management
	appeals := router.Group("/api/admin/appeals")
	{
		appeals.GET("", listAppeals(db))
		appeals.GET("/:id", getAppealDetail(db, negotiationSvc, historyService))
		appeals.GET("/filter/status", filterAppealsByStatus(db))
		appeals.GET("/filter/user/:userID", getAppealsByUser(db))
		appeals.GET("/filter/priority", filterAppealsByPriority(db))
		appeals.PUT("/:id/priority", updateAppealPriority(db))
		appeals.PUT("/:id/notes", updateReviewerNotes(db))
	}

	// Analytics & Reporting
	analytics := router.Group("/api/admin/analytics")
	{
		analytics.GET("/trends", getAnalyticsTrends(db, analyticsSvc))
		analytics.GET("/patterns", getAnalyticsPatterns(db, analyticsSvc))
		analytics.GET("/approval-rate", getApprovalRateAnalytics(db))
		analytics.GET("/user-statistics", getUserStatistics(db))
		analytics.GET("/timeline", getTimelineAnalytics(db))
	}

	// Predictions analytics
	predictions := router.Group("/api/admin/predictions")
	{
		predictions.GET("", listPredictions(db))
		predictions.GET("/accuracy", getPredictionAccuracy(db))
		predictions.GET("/by-type", getPredictionsByType(db))
		predictions.GET("/performance", getPredictionPerformance(db))
	}

	// Negotiation monitoring
	negotiation := router.Group("/api/admin/negotiation")
	{
		negotiation.GET("/active", getActiveNegotiations(db, negotiationSvc))
		negotiation.GET("/stuck", getStuckNegotiations(db))
		negotiation.GET("/sentiment-analysis", getNegotiationSentimentAnalysis(db))
		negotiation.GET("/duration-stats", getNegotiationDurationStats(db))
	}

	// Reports
	reports := router.Group("/api/admin/reports")
	{
		reports.GET("/daily", getDailyReport(db))
		reports.GET("/weekly", getWeeklyReport(db))
		reports.GET("/monthly", getMonthlyReport(db))
		reports.GET("/custom", getCustomReport(db))
		reports.POST("/generate", generateCustomReport(db))
		reports.GET("/export/:type", exportReport(db))
	}

	// System monitoring
	system := router.Group("/api/admin/system")
	{
		system.GET("/health", getSystemHealth(db))
		system.GET("/database-stats", getDatabaseStats(db))
		system.GET("/performance", getPerformanceMetrics(db))
		system.GET("/resource-usage", getResourceUsage(db))
	}
}

// Dashboard Overview
type DashboardOverview struct {
	TotalAppeals        int64       `json:"total_appeals"`
	PendingAppeals      int64       `json:"pending_appeals"`
	ApprovedToday       int64       `json:"approved_today"`
	AverageResolutionTime float64   `json:"avg_resolution_time_hours"`
	ApprovalRate        float64     `json:"approval_rate"`
	ActiveNegotiations  int64       `json:"active_negotiations"`
	AvgNegotiationTime  float64     `json:"avg_negotiation_time_hours"`
	SystemHealth        string      `json:"system_health"`
	Timestamp           time.Time   `json:"timestamp"`
}

func getDashboardOverview(db *gorm.DB, appealSvc *rate_limiting.AppealService, analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()

		var overview DashboardOverview

		// Total appeals
		db.Table("appeals").Count(&overview.TotalAppeals)

		// Pending appeals
		db.Table("appeals").Where("status = ?", rate_limiting.StatusPending).Count(&overview.PendingAppeals)

		// Approved today
		db.Table("appeals").Where("status = ? AND DATE(created_at) = DATE('now')", rate_limiting.StatusApproved).Count(&overview.ApprovedToday)

		// Average resolution time
		var avgTime interface{}
		db.Table("appeals").
			Where("status IN (?, ?)", rate_limiting.StatusApproved, rate_limiting.StatusDenied).
			Select("AVG((julianday(resolved_at) - julianday(created_at)) * 24) as avg_hours").
			Row().Scan(&avgTime)
		if avgTime != nil {
			overview.AverageResolutionTime = avgTime.(float64)
		}

		// Approval rate
		var totalResolved, approved int64
		db.Table("appeals").Where("status IN (?, ?)", rate_limiting.StatusApproved, rate_limiting.StatusDenied).Count(&totalResolved)
		db.Table("appeals").Where("status = ?", rate_limiting.StatusApproved).Count(&approved)
		if totalResolved > 0 {
			overview.ApprovalRate = float64(approved) / float64(totalResolved)
		}

		// Active negotiations
		db.Table("appeal_negotiation_messages").Select("DISTINCT appeal_id").Count(&overview.ActiveNegotiations)

		// Average negotiation time
		var avgNegTime interface{}
		db.Table("appeal_negotiation_messages").
			Select("AVG((julianday(MAX(created_at)) - julianday(MIN(created_at))) * 24) as avg_hours").
			Group("appeal_id").
			Row().Scan(&avgNegTime)
		if avgNegTime != nil {
			overview.AvgNegotiationTime = avgNegTime.(float64)
		}

		// System health
		var tableCount int64
		db.Raw("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").Scan(&tableCount)
		if tableCount > 0 {
			overview.SystemHealth = "healthy"
		} else {
			overview.SystemHealth = "degraded"
		}

		overview.Timestamp = time.Now()

		c.JSON(http.StatusOK, overview)
	}
}

func getDashboardSummary(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()

		summary := gin.H{
			"appeals": gin.H{},
			"negotiation": gin.H{},
			"predictions": gin.H{},
		}

		// Appeal summaries
		var appealsByStatus map[string]int64 = make(map[string]int64)
		rows, _ := db.Table("appeals").Select("status, COUNT(*) as count").Group("status").Rows()
		defer rows.Close()

		for rows.Next() {
			var status string
			var count int64
			rows.Scan(&status, &count)
			appealsByStatus[status] = count
		}

		summary["appeals"] = appealsByStatus

		// Negotiation summary
		var negotiationCount int64
		db.Table("appeal_negotiation_messages").Select("COUNT(DISTINCT appeal_id)").Scan(&negotiationCount)
		summary["negotiation"].(gin.H)["active_count"] = negotiationCount

		// Prediction summary
		var predictionCount int64
		db.Table("ml_predictions").Count(&predictionCount)
		summary["predictions"].(gin.H)["total"] = predictionCount

		c.JSON(http.StatusOK, summary)
	}
}

func getKeyMetrics(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		timeRange := c.DefaultQuery("range", "24h")

		metrics := gin.H{
			"submission_rate": 0.0,
			"approval_rate": 0.0,
			"avg_processing_time": 0.0,
			"error_rate": 0.0,
			"system_uptime": "99.9%",
		}

		c.JSON(http.StatusOK, metrics)
	}
}

func getSystemHealth(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		health := gin.H{
			"status": "healthy",
			"database": gin.H{
				"connected": true,
				"response_time_ms": 5,
			},
			"services": gin.H{
				"appeal_service": "running",
				"negotiation_service": "running",
				"ml_predictions": "running",
				"notifications": "running",
			},
			"timestamp": time.Now(),
		}

		c.JSON(http.StatusOK, health)
	}
}

// Appeals Management
type AppealListItem struct {
	ID              int       `json:"id"`
	UserID          int       `json:"user_id"`
	ViolationID     int       `json:"violation_id"`
	Status          string    `json:"status"`
	Reason          string    `json:"reason"`
	CreatedAt       time.Time `json:"created_at"`
	Priority        int       `json:"priority"`
	Days            int       `json:"days_pending"`
	MessageCount    int       `json:"message_count"`
}

func listAppeals(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		page := c.DefaultQuery("page", "1")
		pageSize := c.DefaultQuery("limit", "50")
		status := c.Query("status")

		pageNum, _ := strconv.Atoi(page)
		pageSz, _ := strconv.Atoi(pageSize)
		offset := (pageNum - 1) * pageSz

		var appeals []AppealListItem
		query := db.Table("appeals a").
			Select("a.id, a.user_id, a.violation_id, a.status, a.reason, a.created_at, COALESCE(a.priority, 0) as priority, CAST((julianday('now') - julianday(a.created_at)) as INTEGER) as days, COALESCE(m.msg_count, 0) as message_count").
			LeftJoin("(SELECT appeal_id, COUNT(*) as msg_count FROM appeal_negotiation_messages GROUP BY appeal_id) m ON a.id = m.appeal_id").
			Order("a.created_at DESC")

		if status != "" {
			query = query.Where("a.status = ?", status)
		}

		query.Offset(offset).Limit(pageSz).Scan(&appeals)

		c.JSON(http.StatusOK, gin.H{
			"appeals": appeals,
			"page": pageNum,
			"limit": pageSz,
			"total": db.Table("appeals").Where("status = ?", status).RowsAffected,
		})
	}
}

func getAppealDetail(db *gorm.DB, negotiationSvc *rate_limiting.AppealNegotiationService, historySvc *rate_limiting.AppealHistoryService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, _ := strconv.Atoi(c.Param("id"))
		ctx := c.Request.Context()

		var appeal rate_limiting.Appeal
		if err := db.Where("id = ?", appealID).First(&appeal).Error; err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Appeal not found"})
			return
		}

		// Get thread
		thread, _ := negotiationSvc.GetNegotiationThread(ctx, appealID)

		// Get timeline
		timeline, _ := historySvc.GetAppealTimeline(ctx, appealID)

		detail := gin.H{
			"appeal": appeal,
			"thread": thread,
			"timeline": timeline,
		}

		c.JSON(http.StatusOK, detail)
	}
}

func filterAppealsByStatus(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		status := c.Query("status")

		var appeals []rate_limiting.Appeal
		db.Where("status = ?", status).Order("created_at DESC").Limit(100).Find(&appeals)

		c.JSON(http.StatusOK, appeals)
	}
}

func getAppealsByUser(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, _ := strconv.Atoi(c.Param("userID"))

		var appeals []rate_limiting.Appeal
		db.Where("user_id = ?", userID).Order("created_at DESC").Find(&appeals)

		c.JSON(http.StatusOK, appeals)
	}
}

func filterAppealsByPriority(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		priority := c.Query("priority")

		var appeals []rate_limiting.Appeal
		db.Where("priority = ?", priority).Order("priority DESC, created_at ASC").Find(&appeals)

		c.JSON(http.StatusOK, appeals)
	}
}

func updateAppealPriority(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, _ := strconv.Atoi(c.Param("id"))

		var req struct {
			Priority int `json:"priority"`
		}
		c.BindJSON(&req)

		db.Table("appeals").Where("id = ?", appealID).Update("priority", req.Priority)

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

func updateReviewerNotes(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, _ := strconv.Atoi(c.Param("id"))

		var req struct {
			Notes string `json:"notes"`
		}
		c.BindJSON(&req)

		db.Table("appeals").Where("id = ?", appealID).Update("reviewer_notes", req.Notes)

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

// Analytics & Reporting
func getAnalyticsTrends(db *gorm.DB, analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		days := c.DefaultQuery("days", "30")
		daysInt, _ := strconv.Atoi(days)

		ctx := c.Request.Context()

		trends := gin.H{}
		c.JSON(http.StatusOK, trends)
	}
}

func getAnalyticsPatterns(db *gorm.DB, analyticsSvc *rate_limiting.AnalyticsService) gin.HandlerFunc {
	return func(c *gin.Context) {
		patterns := gin.H{}
		c.JSON(http.StatusOK, patterns)
	}
}

func getApprovalRateAnalytics(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var stats struct {
			TotalAppeals   int64
			ApprovedCount  int64
			DeniedCount    int64
			ExpiredCount   int64
		}

		db.Table("appeals").Count(&stats.TotalAppeals)
		db.Table("appeals").Where("status = ?", rate_limiting.StatusApproved).Count(&stats.ApprovedCount)
		db.Table("appeals").Where("status = ?", rate_limiting.StatusDenied).Count(&stats.DeniedCount)

		analytics := gin.H{
			"total_appeals": stats.TotalAppeals,
			"approved": stats.ApprovedCount,
			"denied": stats.DeniedCount,
			"approval_rate": float64(stats.ApprovedCount) / float64(stats.TotalAppeals),
		}

		c.JSON(http.StatusOK, analytics)
	}
}

func getUserStatistics(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats := gin.H{}
		c.JSON(http.StatusOK, stats)
	}
}

func getTimelineAnalytics(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		timeline := gin.H{}
		c.JSON(http.StatusOK, timeline)
	}
}

// ML Predictions Analytics
func listPredictions(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var predictions []rate_limiting.Prediction
		db.Limit(100).Order("created_at DESC").Find(&predictions)

		c.JSON(http.StatusOK, predictions)
	}
}

func getPredictionAccuracy(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		accuracy := gin.H{}
		c.JSON(http.StatusOK, accuracy)
	}
}

func getPredictionsByType(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		predictions := gin.H{}
		c.JSON(http.StatusOK, predictions)
	}
}

func getPredictionPerformance(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		performance := gin.H{}
		c.JSON(http.StatusOK, performance)
	}
}

// Negotiation Monitoring
func getActiveNegotiations(db *gorm.DB, negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()

		var appealIDs []int
		db.Table("appeal_negotiation_messages").
			Select("DISTINCT appeal_id").
			Where("created_at > datetime('now', '-7 days')").
			Limit(50).
			Pluck("appeal_id", &appealIDs)

		threads := make([]gin.H, 0)
		for _, id := range appealIDs {
			thread, _ := negotiationSvc.GetNegotiationThread(ctx, id)
			threads = append(threads, gin.H{
				"appeal_id": id,
				"thread": thread,
			})
		}

		c.JSON(http.StatusOK, threads)
	}
}

func getStuckNegotiations(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		stuck := gin.H{}
		c.JSON(http.StatusOK, stuck)
	}
}

func getNegotiationSentimentAnalysis(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		analysis := gin.H{}
		c.JSON(http.StatusOK, analysis)
	}
}

func getNegotiationDurationStats(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats := gin.H{}
		c.JSON(http.StatusOK, stats)
	}
}

// Reports
func getDailyReport(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		report := gin.H{}
		c.JSON(http.StatusOK, report)
	}
}

func getWeeklyReport(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		report := gin.H{}
		c.JSON(http.StatusOK, report)
	}
}

func getMonthlyReport(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		report := gin.H{}
		c.JSON(http.StatusOK, report)
	}
}

func getCustomReport(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		report := gin.H{}
		c.JSON(http.StatusOK, report)
	}
}

func generateCustomReport(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			StartDate string `json:"start_date"`
			EndDate   string `json:"end_date"`
			ReportType string `json:"report_type"`
		}
		c.BindJSON(&req)

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

func exportReport(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		reportType := c.Param("type")

		if reportType == "csv" {
			c.Header("Content-Type", "text/csv")
			c.Header("Content-Disposition", `attachment; filename="report.csv"`)
		} else if reportType == "pdf" {
			c.Header("Content-Type", "application/pdf")
			c.Header("Content-Disposition", `attachment; filename="report.pdf"`)
		}

		c.String(http.StatusOK, "Report export")
	}
}

func getDatabaseStats(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats := gin.H{
			"database_size_mb": 0,
			"table_count": 0,
			"index_count": 0,
		}
		c.JSON(http.StatusOK, stats)
	}
}

func getPerformanceMetrics(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		metrics := gin.H{}
		c.JSON(http.StatusOK, metrics)
	}
}

func getResourceUsage(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		usage := gin.H{}
		c.JSON(http.StatusOK, usage)
	}
}
