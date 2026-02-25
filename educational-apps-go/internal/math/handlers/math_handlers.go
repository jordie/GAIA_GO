package handlers

import (
	"strconv"

	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/math/models"
	"github.com/architect/educational-apps/internal/math/services"
	"github.com/gin-gonic/gin"
)

// GenerateProblem generates a new math problem
func GenerateProblem(c *gin.Context) {
	// Get user ID from context (optional for public endpoint)
	userIDStr, exists := c.Get("user_id")
	var userID uint = 1 // Default to guest
	if exists {
		if uid, err := strconv.ParseUint(userIDStr.(string), 10, 32); err == nil {
			userID = uint(uid)
		}
	}

	var req models.GenerateProblemRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	problem, err := services.GenerateProblem(userID, req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, problem)
}

// CheckAnswer checks user's answer and updates tracking
func CheckAnswer(c *gin.Context) {
	// Get user ID from context (auth required)
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

	var req models.CheckAnswerRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	response, err := services.CheckAnswer(uint(userID), req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, response)
}

// SaveSession saves a complete practice session
func SaveSession(c *gin.Context) {
	// Get user ID from context (auth required)
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

	var req models.SaveSessionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	if err := services.SaveSession(uint(userID), req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, gin.H{
		"success": true,
		"message": "session saved",
	})
}

// GetStats retrieves user statistics
func GetStats(c *gin.Context) {
	// Get user ID from context (auth required)
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

// GetWeaknesses identifies areas needing practice
func GetWeaknesses(c *gin.Context) {
	// Get user ID from context (auth required)
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

	mode := c.DefaultQuery("mode", "addition")

	weakAreas, err := services.GetWeakAreas(uint(userID), mode)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, weakAreas)
}

// GetPracticePlan generates personalized practice plan
func GetPracticePlan(c *gin.Context) {
	// Get user ID from context (auth required)
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

	plan, err := services.GeneratePracticePlan(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, plan)
}

// GetLearningProfile retrieves user's learning profile
func GetLearningProfile(c *gin.Context) {
	// Get user ID from context (auth required)
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

	profile, err := services.AnalyzeLearningProfile(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, profile)
}
