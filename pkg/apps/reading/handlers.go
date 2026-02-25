package reading

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

// RegisterHandlers registers all reading app routes
func RegisterHandlers(router *gin.RouterGroup, app *ReadingApp, sessionMgr *session.Manager, businessMetrics *metrics.BusinessMetricsRegistry) {
	// Word retrieval (CRITICAL: No repetition!)
	router.POST("/api/get_words", func(c *gin.Context) {
		handleGetWords(c, app)
	})

	router.GET("/api/get_words_by_level", func(c *gin.Context) {
		handleGetWordsByLevel(c, app)
	})

	// Word mastery tracking
	router.POST("/api/mark_word_correct", func(c *gin.Context) {
		handleMarkWordCorrect(c, app, sessionMgr, businessMetrics)
	})

	router.POST("/api/mark_word_error", func(c *gin.Context) {
		handleMarkWordError(c, app, sessionMgr, businessMetrics)
	})

	router.POST("/api/record_word_attempt", func(c *gin.Context) {
		handleRecordWordAttempt(c, app)
	})

	// Statistics and progress
	router.GET("/api/stats", func(c *gin.Context) {
		handleGetStats(c, app, sessionMgr)
	})

	router.GET("/api/user_progress", func(c *gin.Context) {
		handleGetUserProgress(c, app)
	})

	router.GET("/api/word_mastery/:word", func(c *gin.Context) {
		handleGetWordMastery(c, app)
	})

	// Session management
	router.POST("/api/sessions/create", func(c *gin.Context) {
		handleCreateSession(c, app)
	})

	router.POST("/api/sessions/complete", func(c *gin.Context) {
		handleCompleteSession(c, app, businessMetrics)
	})

	// Leaderboard
	router.GET("/api/leaderboard", func(c *gin.Context) {
		handleGetLeaderboard(c, app)
	})
}

// ============================================================================
// WORD RETRIEVAL HANDLERS (NO REPETITION)
// ============================================================================

// handleGetWords returns unique words for practice
// CRITICAL: Implements NO REPETITION logic - words must not repeat in session
func handleGetWords(c *gin.Context, app *ReadingApp) {
	var req api.GetWordsRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	if req.Count == 0 {
		req.Count = 20 // Default
	}
	if req.Count > 50 {
		req.Count = 50 // Max 50 per request to prevent excessive load
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1 // Default guest user
	}

	// Get unique words, excluding any already used in this session
	// CRITICAL: This preserves the NO REPETITION requirement
	words, err := app.GetWordsForPractice(userID, req.Count, req.ExcludeWords)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	if len(words) == 0 {
		api.RespondWith(c, http.StatusOK, gin.H{
			"success": false,
			"message": "No new words available. Practice more to improve!",
			"words":   []Word{},
			"count":   0,
		})
		return
	}

	api.WordsListResponse(c, words, len(words))
}

// handleGetWordsByLevel returns all words at a specific level
func handleGetWordsByLevel(c *gin.Context, app *ReadingApp) {
	level := c.DefaultQuery("level", "1")
	levelNum, err := strconv.Atoi(level)
	if err != nil || levelNum < 1 {
		levelNum = 1
	}

	rows, err := app.db.Query(`
		SELECT id, word, level, phonetic, definition, example_sentence, category, difficulty, created_at
		FROM words
		WHERE level = ?
		ORDER BY word ASC
	`, levelNum)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}
	defer rows.Close()

	var words []Word
	for rows.Next() {
		var w Word
		var exampleSentence *string
		if err := rows.Scan(&w.ID, &w.Word, &w.Level, &w.Phonetic, &w.Definition,
			&exampleSentence, &w.Category, &w.Difficulty, &w.CreatedAt); err != nil {
			continue
		}
		if exampleSentence != nil {
			w.ExampleSentence = *exampleSentence
		}
		words = append(words, w)
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"success": true,
		"words":   words,
		"level":   levelNum,
		"count":   len(words),
	})
}

// ============================================================================
// WORD MASTERY HANDLERS
// ============================================================================

// handleMarkWordCorrect records a correct word attempt
func handleMarkWordCorrect(c *gin.Context, app *ReadingApp, sessionMgr *session.Manager, businessMetrics *metrics.BusinessMetricsRegistry) {
	var req api.MarkWordCorrectRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	if err := app.RecordWordAttempt(userID, req.Word, true); err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Award XP for correct answer
	sessionMgr.AddUserXP(userID, 5)

	// Record metrics
	if businessMetrics != nil {
		businessMetrics.RecordXPEarned("reading", 5)
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"success": true,
		"message": "Word recorded correctly",
	})
}

// handleMarkWordError records an incorrect word attempt
func handleMarkWordError(c *gin.Context, app *ReadingApp, sessionMgr *session.Manager, businessMetrics *metrics.BusinessMetricsRegistry) {
	var req api.MarkWordIncorrectRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	if err := app.RecordWordAttempt(userID, req.Word, false); err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Award partial XP for attempt
	sessionMgr.AddUserXP(userID, 1)

	// Record metrics
	if businessMetrics != nil {
		businessMetrics.RecordXPEarned("reading", 1)
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"success": true,
		"message": "Word error recorded",
	})
}

// handleRecordWordAttempt is an alias for mark_word_correct/error in one endpoint
func handleRecordWordAttempt(c *gin.Context, app *ReadingApp) {
	var req struct {
		Word      string `json:"word" binding:"required"`
		IsCorrect bool   `json:"is_correct"`
	}

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	if err := app.RecordWordAttempt(userID, req.Word, req.IsCorrect); err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"success":    true,
		"is_correct": req.IsCorrect,
	})
}

// ============================================================================
// STATISTICS HANDLERS
// ============================================================================

// handleGetStats retrieves user's reading statistics
func handleGetStats(c *gin.Context, app *ReadingApp, sessionMgr *session.Manager) {
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

// handleGetUserProgress retrieves user's reading progress
func handleGetUserProgress(c *gin.Context, app *ReadingApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	var progress struct {
		CurrentLevel        int
		TotalWordsMastered  int
		LastUpdated         string
	}

	err = app.db.QueryRow(`
		SELECT COALESCE(current_level, 1), COALESCE(total_words_mastered, 0),
		       COALESCE(last_updated, datetime('now'))
		FROM user_progress
		WHERE user_id = ?
	`, userID).Scan(&progress.CurrentLevel, &progress.TotalWordsMastered, &progress.LastUpdated)

	if err != nil && err != sql.ErrNoRows {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.UserProgressResponse(c, progress.CurrentLevel, progress.TotalWordsMastered, progress.LastUpdated)
}

// handleGetWordMastery retrieves mastery data for a specific word
func handleGetWordMastery(c *gin.Context, app *ReadingApp) {
	word := c.Param("word")
	if word == "" {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	mastery, err := app.GetWordMastery(userID, word)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	if mastery == nil {
		api.MasteryResponse(c, nil)
		return
	}

	api.MasteryResponse(c, mastery)
}

// ============================================================================
// SESSION HANDLERS
// ============================================================================

// handleCreateSession creates a new reading practice session
func handleCreateSession(c *gin.Context, app *ReadingApp) {
	var req api.ReadingSessionRequest

	if err := c.BindJSON(&req); err != nil {
		req.Level = 1 // Default to level 1
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	session := app.CreatePracticeSession(userID, req.Level)

	// Save to database
	_, err = app.db.Exec(`
		INSERT INTO reading_sessions (id, user_id, level, total_words, started_at)
		VALUES (?, ?, ?, ?, ?)
	`, session.ID, session.UserID, session.Level, session.TotalWords, session.StartedAt)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"success":    true,
		"session_id": session.ID,
		"level":      session.Level,
	})
}

// handleCompleteSession marks a reading session as complete
func handleCompleteSession(c *gin.Context, app *ReadingApp, businessMetrics *metrics.BusinessMetricsRegistry) {
	var req api.CompleteSessionRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	// Calculate accuracy
	var accuracy float64
	if req.WordsCompleted > 0 {
		accuracy = float64(req.CorrectAnswers*100) / float64(req.WordsCompleted)
	}

	_, err := app.db.Exec(`
		UPDATE reading_sessions
		SET words_completed = ?, accuracy = ?, total_time = ?, completed_at = datetime('now')
		WHERE id = ?
	`, req.WordsCompleted, accuracy, req.TotalTime, req.SessionID)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Record metrics
	if businessMetrics != nil {
		businessMetrics.RecordSessionCompleted("reading")
		businessMetrics.RecordReadingPassageCompleted("level_unknown")
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"success":  true,
		"accuracy": accuracy,
	})
}

// ============================================================================
// LEADERBOARD HANDLER
// ============================================================================

// handleGetLeaderboard retrieves the reading leaderboard
func handleGetLeaderboard(c *gin.Context, app *ReadingApp) {
	var req api.LeaderboardRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		req.Limit = 10
		req.Offset = 0
	}

	if req.Limit <= 0 || req.Limit > 100 {
		req.Limit = 10
	}

	rows, err := app.db.Query(`
		SELECT u.username, COUNT(DISTINCT wm.word) as words_mastered,
		       ROUND(AVG(CASE WHEN wm.total_attempts > 0 THEN (wm.correct_count * 100.0 / wm.total_attempts) ELSE 0 END), 1) as avg_accuracy
		FROM users u
		LEFT JOIN word_mastery wm ON u.id = wm.user_id
		GROUP BY u.id, u.username
		ORDER BY words_mastered DESC, avg_accuracy DESC
		LIMIT ?
	`, req.Limit)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}
	defer rows.Close()

	var entries []api.ReadingLeaderboardEntry
	for rows.Next() {
		var entry api.ReadingLeaderboardEntry
		var accuracy *float64
		if err := rows.Scan(&entry.Username, &entry.WordsMastered, &accuracy); err != nil {
			continue
		}
		if accuracy != nil {
			entry.AverageAccuracy = *accuracy
		}
		entries = append(entries, entry)
	}

	api.ReadingLeaderboardResponse(c, entries, len(entries))
}
