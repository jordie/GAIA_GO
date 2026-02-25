package handlers

import (
	"strconv"

	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/typing/models"
	"github.com/architect/educational-apps/internal/typing/services"
	"github.com/gin-gonic/gin"
)

// SaveResult saves a typing test result
func SaveResult(c *gin.Context) {
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

	var req models.SaveResultRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	result, err := services.SaveResult(uint(userID), req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(201, gin.H{
		"success": true,
		"result":  result,
	})
}

// GetUserResults gets the current user's typing results
func GetUserResults(c *gin.Context) {
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

	// Query parameters
	page := c.DefaultQuery("page", "1")
	pageSize := c.DefaultQuery("page_size", "20")

	// Parse parameters
	pageNum, err := strconv.Atoi(page)
	if err != nil || pageNum < 1 {
		pageNum = 1
	}

	pageSizeNum, err := strconv.Atoi(pageSize)
	if err != nil || pageSizeNum < 1 || pageSizeNum > 100 {
		pageSizeNum = 20
	}

	results, err := services.GetUserResults(uint(userID), pageNum, pageSizeNum)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, results)
}

// GetLeaderboard gets the global leaderboard
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

	c.JSON(200, leaderboard)
}
