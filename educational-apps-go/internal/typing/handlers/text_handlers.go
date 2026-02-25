package handlers

import (
	"strconv"

	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/typing/models"
	"github.com/architect/educational-apps/internal/typing/services"
	"github.com/gin-gonic/gin"
)

// GetText generates typing practice text
func GetText(c *gin.Context) {
	var req models.GetTextRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	response, err := services.GenerateText(req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, response)
}

// GetStats gets the current user's typing statistics
func GetStats(c *gin.Context) {
	// Get user ID from context (set by auth middleware)
	userIDStr, exists := c.Get("user_id")
	if !exists {
		middleware.JSONErrorResponse(c, nil)
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	stats, err := services.GetUserStats(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, stats)
}
