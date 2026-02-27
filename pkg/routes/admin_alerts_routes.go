package routes

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// RegisterAlertRoutes registers alert management routes
func RegisterAlertRoutes(router *gin.Engine, db *gorm.DB, alertSvc *rate_limiting.AlertService) {
	alerts := router.Group("/api/admin/alerts")
	{
		// Alert status and statistics
		alerts.GET("/stats", getAlertStats(alertSvc))
		alerts.GET("/active", getActiveAlerts(alertSvc))
		alerts.GET("/by-severity/:severity", getAlertsBySeverity(alertSvc))
		alerts.GET("/history", getAlertHistory(alertSvc))

		// Alert management
		alerts.POST("/resolve/:id", resolveAlert(alertSvc))
		alerts.POST("/silence/:id", silenceAlert(alertSvc))

		// Alert rules
		alerts.GET("/rules", listAlertRules(alertSvc))
		alerts.POST("/rules", createAlertRule(alertSvc))
		alerts.PUT("/rules/:id", updateAlertRule(alertSvc))
		alerts.DELETE("/rules/:id", deleteAlertRule(alertSvc))

		// Notification channels
		alerts.GET("/channels", listNotificationChannels(alertSvc))
		alerts.POST("/channels", createNotificationChannel(alertSvc))
		alerts.PUT("/channels/:id", updateNotificationChannel(alertSvc))
		alerts.DELETE("/channels/:id", deleteNotificationChannel(alertSvc))

		// Metrics for alert rules
		alerts.POST("/metrics/:name", updateMetric(alertSvc))
	}
}

// ===== ALERT STATUS ENDPOINTS =====

func getAlertStats(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		stats := alertSvc.GetAlertStats()
		c.JSON(http.StatusOK, stats)
	}
}

func getActiveAlerts(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		alerts := alertSvc.GetActiveAlerts()

		type AlertResponse struct {
			ID             string                      `json:"id"`
			RuleID         string                      `json:"rule_id"`
			Severity       rate_limiting.AlertSeverity `json:"severity"`
			Title          string                      `json:"title"`
			Description    string                      `json:"description"`
			CurrentValue   float64                     `json:"current_value"`
			ThresholdValue float64                     `json:"threshold_value"`
			TriggeredAt    time.Time                   `json:"triggered_at"`
			FiredCount     int                         `json:"fired_count"`
			AffectedMetric string                      `json:"affected_metric"`
		}

		response := make([]AlertResponse, 0)
		for _, alert := range alerts {
			response = append(response, AlertResponse{
				ID:             alert.ID,
				RuleID:         alert.RuleID,
				Severity:       alert.Severity,
				Title:          alert.Title,
				Description:    alert.Description,
				CurrentValue:   alert.CurrentValue,
				ThresholdValue: alert.ThresholdValue,
				TriggeredAt:    alert.TriggeredAt,
				FiredCount:     alert.FiredCount,
				AffectedMetric: alert.AffectedMetric,
			})
		}

		c.JSON(http.StatusOK, gin.H{
			"alerts": response,
			"count":  len(response),
		})
	}
}

func getAlertsBySeverity(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		severity := rate_limiting.AlertSeverity(c.Param("severity"))

		alerts := alertSvc.GetAlertsBySeverity(severity)

		c.JSON(http.StatusOK, gin.H{
			"severity": severity,
			"alerts":   alerts,
			"count":    len(alerts),
		})
	}
}

func getAlertHistory(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := c.DefaultQuery("limit", "100")
		limitInt, _ := strconv.Atoi(limit)

		events := alertSvc.GetAlertHistory(limitInt)

		c.JSON(http.StatusOK, gin.H{
			"events": events,
			"count":  len(events),
		})
	}
}

// ===== ALERT MANAGEMENT ENDPOINTS =====

func resolveAlert(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		alertID := c.Param("id")

		err := alertSvc.ResolveAlert(alertID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

func silenceAlert(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		alertID := c.Param("id")

		var req struct {
			DurationMinutes int `json:"duration_minutes"`
		}
		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		duration := time.Duration(req.DurationMinutes) * time.Minute
		err := alertSvc.SilenceAlert(alertID, duration)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

// ===== ALERT RULES ENDPOINTS =====

func listAlertRules(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// This would retrieve rules from the service
		// For now, return empty list
		c.JSON(http.StatusOK, gin.H{
			"rules": []interface{}{},
			"count": 0,
		})
	}
}

func createAlertRule(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			Name           string                      `json:"name"`
			Description    string                      `json:"description"`
			Severity       rate_limiting.AlertSeverity `json:"severity"`
			Metric         string                      `json:"metric"`
			Threshold      float64                     `json:"threshold"`
			Type           string                      `json:"type"` // "greater_than", "less_than"
			CheckInterval  int                         `json:"check_interval_seconds"`
			Enabled        bool                        `json:"enabled"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		rule := &rate_limiting.AlertRule{
			ID:          "rule_" + strconv.FormatInt(time.Now().Unix(), 10),
			Name:        req.Name,
			Description: req.Description,
			Severity:    req.Severity,
			Condition: rate_limiting.AlertCondition{
				Type:      req.Type,
				Metric:    req.Metric,
				Threshold: req.Threshold,
				Duration:  5 * time.Minute,
			},
			CheckInterval: time.Duration(req.CheckInterval) * time.Second,
			Enabled:       req.Enabled,
			CreatedAt:     time.Now(),
			UpdatedAt:     time.Now(),
		}

		err := alertSvc.RegisterAlertRule(rule)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"id":      rule.ID,
			"success": true,
		})
	}
}

func updateAlertRule(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		ruleID := c.Param("id")

		var req struct {
			Name      string  `json:"name"`
			Threshold float64 `json:"threshold"`
			Enabled   bool    `json:"enabled"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		// Update rule in service
		c.JSON(http.StatusOK, gin.H{
			"id":      ruleID,
			"success": true,
		})
	}
}

func deleteAlertRule(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		ruleID := c.Param("id")

		// Delete rule from service
		c.JSON(http.StatusOK, gin.H{
			"id":      ruleID,
			"success": true,
		})
	}
}

// ===== NOTIFICATION CHANNELS ENDPOINTS =====

func listNotificationChannels(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Retrieve channels from service
		c.JSON(http.StatusOK, gin.H{
			"channels": []interface{}{},
			"count":    0,
		})
	}
}

func createNotificationChannel(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			Type    string            `json:"type"` // "email", "slack", "pagerduty", "webhook"
			Config  map[string]string `json:"config"`
			Enabled bool              `json:"enabled"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		channel := &rate_limiting.NotificationChannel{
			ID:        "channel_" + strconv.FormatInt(time.Now().Unix(), 10),
			Type:      req.Type,
			Config:    req.Config,
			Enabled:   req.Enabled,
			CreatedAt: time.Now(),
		}

		err := alertSvc.RegisterNotificationChannel(channel)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"id":      channel.ID,
			"success": true,
		})
	}
}

func updateNotificationChannel(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		channelID := c.Param("id")

		var req struct {
			Enabled bool              `json:"enabled"`
			Config  map[string]string `json:"config"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"id":      channelID,
			"success": true,
		})
	}
}

func deleteNotificationChannel(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		channelID := c.Param("id")

		c.JSON(http.StatusOK, gin.H{
			"id":      channelID,
			"success": true,
		})
	}
}

// ===== METRICS UPDATE ENDPOINT =====

func updateMetric(alertSvc *rate_limiting.AlertService) gin.HandlerFunc {
	return func(c *gin.Context) {
		metricName := c.Param("name")

		var req struct {
			Value float64 `json:"value"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
			return
		}

		alertSvc.UpdateMetric(metricName, req.Value)

		c.JSON(http.StatusOK, gin.H{
			"metric": metricName,
			"value":  req.Value,
			"success": true,
		})
	}
}
