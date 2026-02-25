package handlers

import (
	"net/http"
	"strconv"
	"time"

	"github.com/architect/educational-apps/internal/analytics/models"
	"github.com/architect/educational-apps/internal/analytics/repository"
	"github.com/architect/educational-apps/internal/analytics/services"
	"github.com/gin-gonic/gin"
)

// ========== GAMIFICATION ENDPOINTS ==========

// GetGamificationProfile returns user's gamification status
// GET /api/v1/analytics/gamification/profile
func GetGamificationProfile(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	profile, err := services.GetUserGamificationProfile(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, profile)
}

// AwardXP awards XP to a user
// POST /api/v1/analytics/xp
func AwardXP(c *gin.Context) {
	var req models.AwardXPRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := services.AwardXPAndCheckAchievements(req.UserID, req.Amount, req.Source, req.Reason); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Return updated profile
	profile, _ := services.GetUserGamificationProfile(req.UserID)
	c.JSON(http.StatusOK, profile)
}

// CheckInStreak handles daily streak check-in
// POST /api/v1/analytics/streak/checkin
func CheckInStreak(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	if err := repository.UpdateStreak(userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	streak, _ := repository.GetUserStreak(userID)
	c.JSON(http.StatusOK, streak)
}

// GetAchievements returns all available achievements
// GET /api/v1/analytics/achievements
func GetAchievements(c *gin.Context) {
	achievements, err := repository.GetAchievements()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, achievements)
}

// GetUserAchievements returns user's unlocked achievements
// GET /api/v1/analytics/achievements/user
func GetUserAchievements(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	achievements, err := repository.GetUserAchievements(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, achievements)
}

// ========== PROFILE ENDPOINTS ==========

// GetUserProfile returns comprehensive user profile
// GET /api/v1/analytics/profile
func GetUserProfile(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	profile, err := services.GetUserProfile(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, profile)
}

// ========== LEADERBOARD ENDPOINTS ==========

// GetLeaderboard returns ranked users
// GET /api/v1/analytics/leaderboard?period=all&limit=10
func GetLeaderboard(c *gin.Context) {
	period := c.DefaultQuery("period", "all")
	limit := 10
	if l, err := strconv.Atoi(c.DefaultQuery("limit", "10")); err == nil && l > 0 && l <= 100 {
		limit = l
	}

	leaderboard, err := services.GetLeaderboard(period, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, leaderboard)
}

// ========== ANALYTICS ENDPOINTS ==========

// GetDashboard returns user's dashboard summary
// GET /api/v1/analytics/dashboard
func GetDashboard(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	// Get profile
	profile, _ := services.GetUserProfile(userID)

	// Get leaderboard
	leaderboard, _ := services.GetLeaderboard("all", 10)

	// Get recommendations
	recommendations, _ := services.GetRecommendations(userID)

	// Get recent activity
	activity, _ := services.GetRecentActivity(userID, 10)

	// Get goals
	goals, _ := repository.GetUserGoals(userID)

	dashboard := models.DashboardResponse{
		Profile:        *profile,
		Leaderboard:    leaderboard.Entries,
		RecentActivity: activity,
		Goals:          goals,
		Recommendations: recommendations,
	}

	c.JSON(http.StatusOK, dashboard)
}

// GetUserStats returns aggregated user statistics
// GET /api/v1/analytics/stats
func GetUserStats(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	stats, err := services.AggregateUserStats(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// GetRecommendations returns personalized recommendations
// GET /api/v1/analytics/recommendations
func GetRecommendations(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	recommendations, err := services.GetRecommendations(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"recommendations": recommendations})
}

// ========== GOALS ENDPOINTS ==========

// GetUserGoals returns user's learning goals
// GET /api/v1/analytics/goals
func GetUserGoals(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	goals, err := repository.GetUserGoals(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, goals)
}

// CreateGoal creates a new learning goal
// POST /api/v1/analytics/goals
func CreateGoal(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	var req struct {
		Title       string    `json:"title" binding:"required"`
		Description string    `json:"description"`
		App         string    `json:"app"` // "all", "math", "reading", etc.
		TargetValue int       `json:"target_value"`
		TargetDate  time.Time `json:"target_date"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	goalID, err := services.CreateLearningGoal(userID, req.Title, req.Description, req.App, req.TargetValue, req.TargetDate)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"goal_id": goalID})
}

// UpdateGoal updates a learning goal
// PUT /api/v1/analytics/goals/:id
func UpdateGoal(c *gin.Context) {
	_, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	goalID, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid goal id"})
		return
	}

	var req struct {
		Title       string    `json:"title"`
		Description string    `json:"description"`
		Status      string    `json:"status"`
		TargetValue int       `json:"target_value"`
		TargetDate  time.Time `json:"target_date"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	goal := &models.LearningGoal{
		ID:          uint(goalID),
		Title:       req.Title,
		Description: req.Description,
		Status:      req.Status,
		TargetValue: req.TargetValue,
		TargetDate:  req.TargetDate,
	}

	if err := repository.UpdateGoal(goal); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "goal updated"})
}

// DeleteGoal deletes a learning goal
// DELETE /api/v1/analytics/goals/:id
func DeleteGoal(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	goalID, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid goal id"})
		return
	}

	if err := repository.DeleteGoal(uint(goalID), userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "goal deleted"})
}

// ========== ACTIVITY ENDPOINTS ==========

// GetRecentActivity returns user's recent activities
// GET /api/v1/analytics/activity
func GetRecentActivity(c *gin.Context) {
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	limit := 20
	if l, err := strconv.Atoi(c.DefaultQuery("limit", "20")); err == nil && l > 0 && l <= 100 {
		limit = l
	}

	activity, err := services.GetRecentActivity(userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, activity)
}

// ========== SEED ENDPOINTS ==========

// SeedAchievements initializes achievement data
// POST /api/v1/analytics/seed
func SeedAchievements(c *gin.Context) {
	if err := repository.SeedAchievements(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "achievements seeded successfully"})
}
