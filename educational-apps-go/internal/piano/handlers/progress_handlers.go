package handlers

import (
	"strconv"

	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/piano/services"
	"github.com/gin-gonic/gin"
)

// GetUserProgress retrieves current user's progress
func GetUserProgress(c *gin.Context) {
	// Get user ID from context
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

	progress, err := services.GetUserProgress(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, progress)
}

// GetLeaderboard retrieves top performers
func GetLeaderboard(c *gin.Context) {
	// Query parameters
	limit := c.DefaultQuery("limit", "10")

	// Parse parameters
	limitNum, err := strconv.Atoi(limit)
	if err != nil || limitNum < 1 || limitNum > 100 {
		limitNum = 10
	}

	leaderboard, err := services.GetLeaderboard(limitNum)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, gin.H{
		"leaderboard": leaderboard,
		"total":       len(leaderboard),
	})
}

// ResetProgress resets user's progress (admin only)
func ResetProgress(c *gin.Context) {
	// Get user ID from context
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

	if err := services.ResetUserProgress(uint(userID)); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, gin.H{"message": "progress reset successfully"})
}
