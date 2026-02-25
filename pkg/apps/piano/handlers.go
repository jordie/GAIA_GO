package piano

import (
	"database/sql"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
	"github.com/jgirmay/GAIA_GO/internal/metrics"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// RegisterHandlers registers all piano app routes
func RegisterHandlers(router *gin.RouterGroup, app *PianoApp, sessionMgr *session.Manager, businessMetrics *metrics.BusinessMetricsRegistry) {
	// Practice sessions
	router.POST("/api/save_session", func(c *gin.Context) {
		handleSaveSession(c, app, sessionMgr, businessMetrics)
	})

	// Note analytics
	router.GET("/api/get_note_analytics", func(c *gin.Context) {
		handleGetNoteAnalytics(c, app)
	})

	router.POST("/api/save_note_event", func(c *gin.Context) {
		handleSaveNoteEvent(c, app)
	})

	// Statistics
	router.GET("/api/get_stats", func(c *gin.Context) {
		handleGetStats(c, app)
	})

	// User management
	router.GET("/api/users", func(c *gin.Context) {
		handleGetUsers(c, app)
	})

	router.POST("/api/users", func(c *gin.Context) {
		handleCreateUser(c, app)
	})

	router.POST("/api/users/:id", func(c *gin.Context) {
		handleSetUser(c, app)
	})

	// Level management
	router.GET("/api/user/level", func(c *gin.Context) {
		handleGetUserLevel(c, app)
	})

	router.POST("/api/user/level", func(c *gin.Context) {
		handleUpdateUserLevel(c, app)
	})

	// Streak system
	router.GET("/api/streak", func(c *gin.Context) {
		handleGetStreak(c, app)
	})

	// Goals system
	router.GET("/api/goals", func(c *gin.Context) {
		handleGetGoals(c, app)
	})

	router.POST("/api/goals/update", func(c *gin.Context) {
		handleUpdateGoalProgress(c, app)
	})

	// Achievements/badges
	router.GET("/api/badges", func(c *gin.Context) {
		handleGetBadges(c, app)
	})

	// Warmups
	router.GET("/api/warmups", func(c *gin.Context) {
		handleGetWarmups(c)
	})

	router.POST("/api/warmups/:id/start", func(c *gin.Context) {
		handleStartWarmup(c, app)
	})

	router.POST("/api/warmups/complete", func(c *gin.Context) {
		handleCompleteWarmup(c, app)
	})

	// Central sync
	router.POST("/api/central/sync", func(c *gin.Context) {
		handleCentralSync(c, app, sessionMgr)
	})
}

// ============================================================================
// SESSION HANDLERS
// ============================================================================

func handleSaveSession(c *gin.Context, app *PianoApp, sessionMgr *session.Manager, businessMetrics *metrics.BusinessMetricsRegistry) {
	var req api.SaveSessionRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	session := &PracticeSession{
		Level:           req.Level,
		Hand:            Hand(req.Hand),
		Score:           req.Score,
		Accuracy:        req.Accuracy,
		TotalNotes:      req.TotalNotes,
		CorrectNotes:    req.CorrectNotes,
		AvgResponseTime: 0, // Not in SaveSessionRequest, can be added if needed
		Duration:        req.TotalTime,
	}

	sessionID, err := app.SavePracticeSession(userID, session)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Update streak
	app.UpdateStreak(userID)

	// Award XP
	xpReward := int64(10 + (req.Score / 10))
	sessionMgr.AddUserXP(userID, xpReward)

	// Check for badge unlocks
	checkAndAwardBadges(app, userID, businessMetrics)

	// Record metrics
	if businessMetrics != nil {
		businessMetrics.RecordSessionCompleted("piano")
		businessMetrics.RecordXPEarned("piano", int(xpReward))

		// Determine difficulty based on level
		difficulty := "beginner"
		if req.Level >= 5 {
			difficulty = "intermediate"
		}
		if req.Level >= 10 {
			difficulty = "advanced"
		}
		businessMetrics.RecordPianoSongPlayed(difficulty)
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"session_id": sessionID,
		"xp_earned":  xpReward,
	})
}

// ============================================================================
// ANALYTICS HANDLERS
// ============================================================================

func handleSaveNoteEvent(c *gin.Context, app *PianoApp) {
	var req api.SaveNoteEventRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	err = app.RecordNoteAttempt(userID, req.Note, Hand(req.Hand), req.IsCorrect)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"message": "Note recorded",
	})
}

func handleGetNoteAnalytics(c *gin.Context, app *PianoApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	analytics, err := app.GetNoteAnalytics(userID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.NoteAnalyticsResponse(c, analytics, len(analytics))
}

// ============================================================================
// STATISTICS HANDLERS
// ============================================================================

func handleGetStats(c *gin.Context, app *PianoApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	stats, err := app.GetUserStats(userID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.StatsNestedResponse(c, stats)
}

// ============================================================================
// USER MANAGEMENT HANDLERS
// ============================================================================

func handleGetUsers(c *gin.Context, app *PianoApp) {
	// Simple stub - returns list of users
	api.RespondWith(c, http.StatusOK, gin.H{
		"users": []map[string]interface{}{},
	})
}

func handleCreateUser(c *gin.Context, app *PianoApp) {
	var req api.CreateUserRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"user_id":  1,
		"username": req.Username,
	})
}

func handleSetUser(c *gin.Context, app *PianoApp) {
	userIDStr := c.Param("id")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"user_id": userID,
	})
}

// ============================================================================
// LEVEL HANDLERS
// ============================================================================

func handleGetUserLevel(c *gin.Context, app *PianoApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	var level int
	err = app.db.QueryRow(
		"SELECT COALESCE(current_level, 1) FROM user_levels WHERE user_id = ?",
		userID,
	).Scan(&level)

	if err != nil && err != sql.ErrNoRows {
		level = 1
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"level": level,
	})
}

func handleUpdateUserLevel(c *gin.Context, app *PianoApp) {
	var req api.UpdateLevelRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	_, err = app.db.Exec(
		"UPDATE user_levels SET current_level = ? WHERE user_id = ?",
		req.Level, userID,
	)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"level": req.Level,
	})
}

// ============================================================================
// STREAK HANDLERS
// ============================================================================

func handleGetStreak(c *gin.Context, app *PianoApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	streak, err := app.GetStreak(userID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"streak": streak,
	})
}

// ============================================================================
// GOAL HANDLERS
// ============================================================================

func handleGetGoals(c *gin.Context, app *PianoApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	goals, err := app.GetGoals(userID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	if goals == nil {
		goals = []Goal{}
	}

	api.GoalsListResponse(c, goals, len(goals))
}

func handleUpdateGoalProgress(c *gin.Context, app *PianoApp) {
	var req api.UpdateGoalProgressRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	err := app.UpdateGoalProgress(req.GoalID, req.Progress)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"goal_id": req.GoalID,
	})
}

// ============================================================================
// ACHIEVEMENT HANDLERS
// ============================================================================

func handleGetBadges(c *gin.Context, app *PianoApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	badges, err := app.GetAchievements(userID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	if badges == nil {
		badges = []Achievement{}
	}

	api.BadgesListResponse(c, badges, len(badges))
}

// ============================================================================
// WARMUP HANDLERS
// ============================================================================

func handleGetWarmups(c *gin.Context) {
	warmups := []map[string]interface{}{
		{
			"id":          1,
			"name":        "C Major Scale",
			"description": "Practice C Major scale both hands",
			"notes":       []string{"C", "D", "E", "F", "G", "A", "B", "C"},
		},
		{
			"id":          2,
			"name":        "Finger Exercise",
			"description": "Basic finger dexterity exercise",
			"notes":       []string{"C", "D", "E", "F", "G"},
		},
		{
			"id":          3,
			"name":        "Chord Progression",
			"description": "Learn basic chord changes",
			"notes":       []string{"C", "F", "G"},
		},
	}

	api.WarmupListResponse(c, warmups, len(warmups))
}

func handleStartWarmup(c *gin.Context, app *PianoApp) {
	warmupIDStr := c.Param("id")
	warmupID, err := strconv.ParseInt(warmupIDStr, 10, 64)
	if err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, _ := middleware.GetUserID(c)
	if userID == 0 {
		userID = 1
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"warmup_id": warmupID,
		"user_id":   userID,
		"started":   true,
	})
}

func handleCompleteWarmup(c *gin.Context, app *PianoApp) {
	var req api.CompleteWarmupRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"warmup_id": req.WarmupID,
		"score":     req.Score,
		"xp_earned": 5,
	})
}

// ============================================================================
// SYNC HANDLERS
// ============================================================================

func handleCentralSync(c *gin.Context, app *PianoApp, sessionMgr *session.Manager) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	stats, _ := app.GetUserStats(userID)
	badges, _ := app.GetAchievements(userID)

	api.RespondWith(c, http.StatusOK, gin.H{
		"stats":  stats,
		"badges": badges,
	})
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

func checkAndAwardBadges(app *PianoApp, userID int64, businessMetrics *metrics.BusinessMetricsRegistry) {
	// Check for consistency champion (7 day streak)
	streak, _ := app.GetStreak(userID)
	if streak.CurrentStreak >= 7 {
		awarded, _ := app.AwardAchievement(userID, "consistency_champion", 1)
		if awarded && businessMetrics != nil {
			businessMetrics.RecordAchievementUnlocked("piano", "intermediate")
		}
	}

	// Check for level badges
	var level int
	app.db.QueryRow(
		"SELECT COALESCE(current_level, 1) FROM user_levels WHERE user_id = ?",
		userID,
	).Scan(&level)

	if level >= 5 {
		awarded, _ := app.AwardAchievement(userID, "level_5_reached", 1)
		if awarded && businessMetrics != nil {
			businessMetrics.RecordAchievementUnlocked("piano", "beginner")
		}
	}

	// Check accuracy expert (95%+ accuracy)
	stats, _ := app.GetUserStats(userID)
	if avgAcc, ok := stats["average_accuracy"].(float64); ok && avgAcc >= 95 {
		awarded, _ := app.AwardAchievement(userID, "accuracy_expert", 1)
		if awarded && businessMetrics != nil {
			businessMetrics.RecordAchievementUnlocked("piano", "advanced")
		}
	}
}
