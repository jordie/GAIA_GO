package routes

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"architect/pkg/services/rate_limiting"
)

// RegisterAppealAdvancedFeaturesRoutes registers Phase 3 Sprint 4 routes
func RegisterAppealAdvancedFeaturesRoutes(
	router *gin.Engine,
	db *gorm.DB,
	negotiationSvc *rate_limiting.AppealNegotiationService,
	mlPredictionSvc *rate_limiting.MLPredictionService,
) {
	// Appeal negotiation routes
	negotiation := router.Group("/api/appeals/negotiation")
	{
		negotiation.POST("/:appealID/message", sendNegotiationMessage(negotiationSvc))
		negotiation.GET("/:appealID/thread", getNegotiationThread(negotiationSvc))
		negotiation.GET("/user/conversations", getUserConversations(negotiationSvc))
		negotiation.GET("/admin/conversations", getAdminConversations(negotiationSvc))
		negotiation.POST("/:appealID/pin/:messageID", pinMessage(negotiationSvc))
		negotiation.POST("/:appealID/unpin/:messageID", unpinMessage(negotiationSvc))
		negotiation.GET("/:appealID/pinned", getPinnedMessages(negotiationSvc))
		negotiation.GET("/:appealID/tone-analysis", analyzeConversationTone(negotiationSvc))
		negotiation.GET("/statistics", getNegotiationMetrics(negotiationSvc))
	}

	// ML prediction routes
	predictions := router.Group("/api/predictions")
	{
		predictions.GET("/user/recovery/:userID", getUserRecoveryPrediction(mlPredictionSvc))
		predictions.GET("/appeal/approval/:appealID", getAppealApprovalProbability(mlPredictionSvc))
		predictions.GET("/user/auto-appeals/:userID", getUserAutoAppealSuggestions(mlPredictionSvc))
		predictions.GET("/model-performance", getModelPerformance(mlPredictionSvc))
	}
}

// Negotiation Endpoints

// sendNegotiationMessage sends a negotiation message
func sendNegotiationMessage(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		userID := c.GetInt("user_id")
		if userID == 0 {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		var req struct {
			Message        string `json:"message" binding:"required"`
			MessageType    string `json:"message_type"`
			AttachmentURLs []string `json:"attachment_urls"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		msg, err := negotiationSvc.SendMessage(
			c.Request.Context(),
			appealID,
			userID,
			rate_limiting.SenderTypeUser,
			req.Message,
			rate_limiting.MessageType(req.MessageType),
			nil,
			req.AttachmentURLs,
		)

		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, msg)
	}
}

// getNegotiationThread retrieves conversation thread
func getNegotiationThread(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		thread, err := negotiationSvc.GetNegotiationThread(c.Request.Context(), appealID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve thread"})
			return
		}

		c.JSON(http.StatusOK, thread)
	}
}

// getUserConversations retrieves user's conversations
func getUserConversations(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
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

		conversations, err := negotiationSvc.GetUserConversations(c.Request.Context(), userID, limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve conversations"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"conversations": conversations,
			"count":         len(conversations),
		})
	}
}

// getAdminConversations retrieves active negotiations for admin
func getAdminConversations(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := 20
		offset := 0

		conversations, err := negotiationSvc.GetAdminConversations(c.Request.Context(), limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve conversations"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"conversations": conversations,
			"count":         len(conversations),
		})
	}
}

// pinMessage pins a message
func pinMessage(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		messageID, err := strconv.ParseInt(c.Param("messageID"), 10, 64)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid message ID"})
			return
		}

		err = negotiationSvc.PinMessage(c.Request.Context(), messageID)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Failed to pin message"})
			return
		}

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

// unpinMessage unpins a message
func unpinMessage(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		messageID, err := strconv.ParseInt(c.Param("messageID"), 10, 64)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid message ID"})
			return
		}

		err = negotiationSvc.UnpinMessage(c.Request.Context(), messageID)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Failed to unpin message"})
			return
		}

		c.JSON(http.StatusOK, gin.H{"success": true})
	}
}

// getPinnedMessages retrieves pinned messages
func getPinnedMessages(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		messages, err := negotiationSvc.GetPinnedMessages(c.Request.Context(), appealID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve pinned messages"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"messages": messages,
			"count":    len(messages),
		})
	}
}

// analyzeConversationTone analyzes sentiment
func analyzeConversationTone(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		analysis, err := negotiationSvc.AnalyzeConversationTone(c.Request.Context(), appealID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to analyze tone"})
			return
		}

		c.JSON(http.StatusOK, analysis)
	}
}

// getNegotiationMetrics returns statistics
func getNegotiationMetrics(negotiationSvc *rate_limiting.AppealNegotiationService) gin.HandlerFunc {
	return func(c *gin.Context) {
		metrics, err := negotiationSvc.GetNegotiationMetrics(c.Request.Context())
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve metrics"})
			return
		}

		c.JSON(http.StatusOK, metrics)
	}
}

// ML Prediction Endpoints

// getUserRecoveryPrediction predicts reputation recovery timeline
func getUserRecoveryPrediction(mlPredictionSvc *rate_limiting.MLPredictionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := strconv.Atoi(c.Param("userID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}

		prediction, err := mlPredictionSvc.PredictReputationRecovery(c.Request.Context(), userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to predict recovery"})
			return
		}

		c.JSON(http.StatusOK, prediction)
	}
}

// getAppealApprovalProbability predicts approval probability
func getAppealApprovalProbability(mlPredictionSvc *rate_limiting.MLPredictionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		appealID, err := strconv.Atoi(c.Param("appealID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid appeal ID"})
			return
		}

		probability, err := mlPredictionSvc.PredictAppealApprovalProbability(c.Request.Context(), appealID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to predict probability"})
			return
		}

		c.JSON(http.StatusOK, probability)
	}
}

// getUserAutoAppealSuggestions generates auto-appeal suggestions
func getUserAutoAppealSuggestions(mlPredictionSvc *rate_limiting.MLPredictionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := strconv.Atoi(c.Param("userID"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}

		suggestions, err := mlPredictionSvc.SuggestAutoAppeal(c.Request.Context(), userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to generate suggestions"})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"suggestions": suggestions,
			"count":       len(suggestions),
		})
	}
}

// getModelPerformance returns ML model metrics
func getModelPerformance(mlPredictionSvc *rate_limiting.MLPredictionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		predictionType := c.Query("type")
		if predictionType == "" {
			predictionType = "recovery_timeline"
		}

		performance, err := mlPredictionSvc.GetModelPerformance(
			c.Request.Context(),
			rate_limiting.PredictionType(predictionType),
		)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve performance"})
			return
		}

		c.JSON(http.StatusOK, performance)
	}
}
