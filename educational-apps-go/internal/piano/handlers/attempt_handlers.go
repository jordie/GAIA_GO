package handlers

import (
	"strconv"

	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/piano/models"
	"github.com/architect/educational-apps/internal/piano/services"
	"github.com/gin-gonic/gin"
)

// RecordAttempt records a new piano attempt
func RecordAttempt(c *gin.Context) {
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

	var req models.CreateAttemptRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	attempt, err := services.RecordAttempt(uint(userID), req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(201, attempt)
}

// GetUserAttempts retrieves all attempts for the current user
func GetUserAttempts(c *gin.Context) {
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

	result, err := services.GetUserAttempts(uint(userID), pageNum, pageSizeNum)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, result)
}

// GetExerciseAttempts retrieves all attempts for an exercise
func GetExerciseAttempts(c *gin.Context) {
	exerciseID, err := strconv.ParseUint(c.Param("id"), 10, 32)
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

	result, err := services.GetExerciseAttempts(uint(exerciseID), pageNum, pageSizeNum)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, result)
}

// GetUserExerciseStats retrieves performance stats for a user on an exercise
func GetUserExerciseStats(c *gin.Context) {
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

	exerciseID, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	stats, err := services.GetUserExerciseStats(uint(userID), uint(exerciseID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, stats)
}
