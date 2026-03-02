package routes

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// RegisterRateLimitingRoutes registers rate limiting management routes
func RegisterRateLimitingRoutes(router *gin.Engine, db *gorm.DB, limiter rate_limiting.RateLimiter) {
	admin := router.Group("/api/admin/rate-limiting")
	{
		// Statistics and monitoring
		admin.GET("/stats", getRateLimitStats(limiter))
		admin.GET("/usage/:system/:scope/:value", getRateLimitUsage(limiter))
		admin.GET("/violations/:system", getViolations(limiter))
		admin.GET("/violations/:system/stats", getViolationStats(limiter))
		admin.GET("/metrics/summary", getRateLimitMetricsSummary(limiter))

		// Rule management
		admin.GET("/rules/:system", listRateLimitRules(limiter))
		admin.POST("/rules", createRateLimitRule(limiter))
		admin.PUT("/rules/:id", updateRateLimitRule(limiter))
		admin.DELETE("/rules/:id", deleteRateLimitRule(limiter))
		admin.GET("/rules/:system/:id", getRateLimitRule(limiter))

		// Quota management
		admin.GET("/quotas/:system/:scope/:value", getQuota(limiter))
		admin.POST("/quotas/:system/:scope/:value/increment", incrementQuota(limiter))

		// System management
		admin.POST("/cleanup/buckets", cleanupOldBuckets(limiter))
		admin.POST("/cleanup/violations", cleanupOldViolations(limiter))
		admin.POST("/cleanup/metrics", cleanupOldMetrics(limiter))
		admin.GET("/health", getRateLimitingHealth())
	}
}

// ===== STATISTICS ENDPOINTS =====

func getRateLimitStats(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		system := c.DefaultQuery("system", "global")
		days := c.DefaultQuery("days", "7")
		daysInt, _ := strconv.Atoi(days)

		// Get stats from limiter
		// For now, return basic structure
		stats := map[string]interface{}{
			"system":          system,
			"days_analyzed":   daysInt,
			"timestamp":       time.Now(),
		}

		c.JSON(http.StatusOK, stats)
	}
}

func getRateLimitUsage(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		system := c.Param("system")
		scope := c.Param("scope")
		value := c.Param("value")

		usage, err := limiter.GetUsage(c.Request.Context(), system, scope, value)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, usage)
	}
}

func getViolations(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		system := c.Param("system")
		hours := c.DefaultQuery("hours", "24")
		hoursInt, _ := strconv.Atoi(hours)

		since := time.Now().Add(-time.Duration(hoursInt) * time.Hour)

		violations, err := limiter.GetViolations(c.Request.Context(), system, since)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"violations": violations,
			"count":      len(violations),
			"hours":      hoursInt,
		})
	}
}

func getViolationStats(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		system := c.Param("system")

		stats, err := limiter.GetViolationStats(c.Request.Context(), system)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, stats)
	}
}

func getRateLimitMetricsSummary(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Return basic metrics summary
		summary := map[string]interface{}{
			"timestamp":           time.Now(),
			"total_rules":         0,
			"enabled_rules":       0,
			"total_violations":    0,
			"violations_24h":      0,
			"active_quotas":       0,
			"system_status":       "healthy",
		}

		c.JSON(http.StatusOK, summary)
	}
}

// ===== RULE MANAGEMENT ENDPOINTS =====

func listRateLimitRules(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		system := c.Param("system")

		rules, err := limiter.GetRules(c.Request.Context(), system)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"rules": rules,
			"count": len(rules),
		})
	}
}

func getRateLimitRule(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		ruleID := c.Param("id")
		ruleIDInt, err := strconv.ParseInt(ruleID, 10, 64)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid rule ID"})
			return
		}

		rule, err := limiter.GetRule(c.Request.Context(), ruleIDInt)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		if rule == nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Rule not found"})
			return
		}

		c.JSON(http.StatusOK, rule)
	}
}

func createRateLimitRule(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			SystemID     string `json:"system_id"`
			Scope        string `json:"scope"`
			ScopeValue   *string `json:"scope_value"`
			LimitType    string `json:"limit_type"`
			LimitValue   int    `json:"limit_value"`
			ResourceType *string `json:"resource_type"`
			Priority     int    `json:"priority"`
			Enabled      bool   `json:"enabled"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		rule := rate_limiting.Rule{
			SystemID:     req.SystemID,
			Scope:        req.Scope,
			ScopeValue:   getStringValue(req.ScopeValue),
			LimitType:    rate_limiting.LimitType(req.LimitType),
			LimitValue:   req.LimitValue,
			ResourceType: getStringValue(req.ResourceType),
			Priority:     req.Priority,
			Enabled:      req.Enabled,
		}

		ruleID, err := limiter.CreateRule(c.Request.Context(), rule)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"id":      ruleID,
			"success": true,
		})
	}
}

func updateRateLimitRule(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		ruleID := c.Param("id")
		ruleIDInt, err := strconv.ParseInt(ruleID, 10, 64)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid rule ID"})
			return
		}

		var req struct {
			LimitValue   *int `json:"limit_value"`
			Priority     *int `json:"priority"`
			Enabled      *bool `json:"enabled"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		// Get existing rule
		rule, err := limiter.GetRule(c.Request.Context(), ruleIDInt)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		if rule == nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Rule not found"})
			return
		}

		// Update fields
		if req.LimitValue != nil {
			rule.LimitValue = *req.LimitValue
		}
		if req.Priority != nil {
			rule.Priority = *req.Priority
		}
		if req.Enabled != nil {
			rule.Enabled = *req.Enabled
		}

		if err := limiter.UpdateRule(c.Request.Context(), *rule); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"id":      ruleID,
			"success": true,
		})
	}
}

func deleteRateLimitRule(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		ruleID := c.Param("id")
		ruleIDInt, err := strconv.ParseInt(ruleID, 10, 64)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid rule ID"})
			return
		}

		if err := limiter.DeleteRule(c.Request.Context(), ruleIDInt); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"id":      ruleID,
			"success": true,
		})
	}
}

// ===== QUOTA MANAGEMENT ENDPOINTS =====

func getQuota(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		system := c.Param("system")
		scope := c.Param("scope")
		value := c.Param("value")
		resourceType := c.DefaultQuery("resource_type", "")

		quota, err := limiter.GetQuota(c.Request.Context(), system, scope, value, resourceType)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		if quota == nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "Quota not found"})
			return
		}

		c.JSON(http.StatusOK, quota)
	}
}

func incrementQuota(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		system := c.Param("system")
		scope := c.Param("scope")
		value := c.Param("value")

		var req struct {
			Amount       int    `json:"amount"`
			ResourceType string `json:"resource_type"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		if req.Amount <= 0 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Amount must be positive"})
			return
		}

		if err := limiter.IncrementQuota(c.Request.Context(), system, scope, value, req.ResourceType, req.Amount); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"system":  system,
			"scope":   scope,
			"value":   value,
			"amount":  req.Amount,
		})
	}
}

// ===== SYSTEM MANAGEMENT ENDPOINTS =====

func cleanupOldBuckets(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		days := c.DefaultQuery("days", "7")
		daysInt, _ := strconv.Atoi(days)

		before := time.Now().Add(-time.Duration(daysInt*24) * time.Hour)

		count, err := limiter.CleanupOldBuckets(c.Request.Context(), before)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":      true,
			"deleted":      count,
			"before_date":  before,
			"retention_days": daysInt,
		})
	}
}

func cleanupOldViolations(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		days := c.DefaultQuery("days", "30")
		daysInt, _ := strconv.Atoi(days)

		before := time.Now().Add(-time.Duration(daysInt*24) * time.Hour)

		count, err := limiter.CleanupOldViolations(c.Request.Context(), before)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":      true,
			"deleted":      count,
			"before_date":  before,
			"retention_days": daysInt,
		})
	}
}

func cleanupOldMetrics(limiter rate_limiting.RateLimiter) gin.HandlerFunc {
	return func(c *gin.Context) {
		days := c.DefaultQuery("days", "90")
		daysInt, _ := strconv.Atoi(days)

		before := time.Now().Add(-time.Duration(daysInt*24) * time.Hour)

		count, err := limiter.CleanupOldMetrics(c.Request.Context(), before)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":      true,
			"deleted":      count,
			"before_date":  before,
			"retention_days": daysInt,
		})
	}
}

func getRateLimitingHealth() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"timestamp": time.Now(),
			"service":   "rate-limiting",
			"version":   "1.0",
		})
	}
}

// ===== HELPER FUNCTIONS =====

func getStringValue(ptr *string) string {
	if ptr == nil {
		return ""
	}
	return *ptr
}
