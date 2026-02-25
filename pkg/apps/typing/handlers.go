package typing

import (
	"database/sql"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
	"github.com/jgirmay/GAIA_GO/internal/models"
	"github.com/jgirmay/GAIA_GO/internal/session"
	"github.com/jgirmay/GAIA_GO/pkg/apps/typing/multiplayer"
)

// RegisterHandlers registers all typing app handlers with the router
func RegisterHandlers(router *gin.RouterGroup, app *TypingApp, sessionMgr *session.Manager) {
	// User endpoints
	router.GET("/current-user", app.handleGetCurrentUser)
	router.GET("/users", app.handleGetUsers)
	router.POST("/users", app.handleCreateUser(sessionMgr))

	// Practice endpoints
	router.GET("/text", app.handleGetText)
	router.POST("/save-result", middleware.RequireAuth(), app.handleSaveResult)
	router.GET("/stats", middleware.RequireAuth(), app.handleGetStats)
	router.GET("/leaderboard", app.handleGetLeaderboard)

	// Race endpoints (AI)
	router.POST("/race/start", app.handleRaceStart)
	router.POST("/race/finish", middleware.RequireAuth(), app.handleRaceFinish(sessionMgr))
	router.GET("/race/stats", app.handleRaceStats)
	router.GET("/race/leaderboard", app.handleRaceLeaderboard)

	// Multiplayer endpoints
	registerMultiplayerRoutes(router, app, sessionMgr)
}

// registerMultiplayerRoutes registers multiplayer-specific routes
func registerMultiplayerRoutes(router *gin.RouterGroup, app *TypingApp, sessionMgr *session.Manager) {
	// Initialize multiplayer components
	roomManager := multiplayer.NewGameRoomManager(app.db, app)
	wsHub := multiplayer.NewWebSocketHub(roomManager, sessionMgr)

	// Register multiplayer handlers
	RegisterMultiplayerHandlers(router, roomManager, wsHub, sessionMgr)
}

// ============================================================================
// USER ENDPOINTS
// ============================================================================

func (app *TypingApp) handleGetCurrentUser(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	username, _ := middleware.GetUsername(c)

	api.RespondWith(c, http.StatusOK, gin.H{
		"user_id":  userID,
		"username": username,
	})
}

func (app *TypingApp) handleGetUsers(c *gin.Context) {
	rows, err := app.db.Query(`SELECT id, username FROM users ORDER BY username`)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}
	defer rows.Close()

	var users []api.UserResponseTyping
	for rows.Next() {
		var user api.UserResponseTyping
		if scanErr := rows.Scan(&user.ID, &user.Username); scanErr != nil {
			continue
		}
		users = append(users, user)
	}

	// Use RawArrayResponse adapter to maintain backward compatibility
	api.RawArrayResponse(c, users)
}

func (app *TypingApp) handleCreateUser(sessionMgr *session.Manager) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req api.CreateUserRequest

		if err := c.ShouldBindJSON(&req); err != nil {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		username := req.Username
		if len(username) < 2 || len(username) > 20 {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		// Check if user exists
		var existingID int64
		err := app.db.QueryRow(`SELECT id FROM users WHERE username = ?`, username).Scan(&existingID)
		if err == nil {
			api.RespondWithError(c, api.ErrConflict)
			return
		}

		// Create user
		user, err := sessionMgr.CreateUser(username)
		if err != nil {
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		// Initialize typing stats
		_, _ = app.db.Exec(
			`INSERT INTO typing_stats (user_id, total_tests) VALUES (?, 0)`,
			user.ID,
		)

		api.RespondWith(c, http.StatusOK, gin.H{
			"success":  true,
			"user_id":  user.ID,
			"username": user.Username,
		})
	}
}

// ============================================================================
// PRACTICE ENDPOINTS
// ============================================================================

func (app *TypingApp) handleGetText(c *gin.Context) {
	testType := c.DefaultQuery("type", "common_words")
	category := c.DefaultQuery("category", "common_words")
	wordCountStr := c.DefaultQuery("word_count", "25")
	wordCount, _ := strconv.Atoi(wordCountStr)

	text := app.GetText(testType, category, wordCount)

	api.RespondWith(c, http.StatusOK, gin.H{
		"text": text,
	})
}

func (app *TypingApp) handleSaveResult(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	var req api.SaveResultRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	// Save result
	result, err := app.db.Exec(
		`INSERT INTO typing_results
		(user_id, wpm, raw_wpm, accuracy, test_type, test_duration,
		 total_characters, correct_characters, incorrect_characters, errors, text_snippet)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		userID, req.WPM, req.RawWPM, req.Accuracy, req.TestType, req.TestDuration,
		req.TotalCharacters, req.CorrectCharacters, req.IncorrectCharacters, req.Errors, req.TextSnippet,
	)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Update user stats
	var stats struct {
		ID              int64
		TotalTests      int
		AverageWPM      float64
		AverageAccuracy float64
		BestWPM         int
	}

	err = app.db.QueryRow(
		`SELECT id, total_tests, average_wpm, average_accuracy, best_wpm
		 FROM typing_stats WHERE user_id = ?`,
		userID,
	).Scan(&stats.ID, &stats.TotalTests, &stats.AverageWPM, &stats.AverageAccuracy, &stats.BestWPM)

	newTotalTests := stats.TotalTests + 1
	newAverageWPM := (stats.AverageWPM*float64(stats.TotalTests) + float64(req.WPM)) / float64(newTotalTests)
	newAverageAccuracy := (stats.AverageAccuracy*float64(stats.TotalTests) + req.Accuracy) / float64(newTotalTests)
	newBestWPM := stats.BestWPM
	if req.WPM > newBestWPM {
		newBestWPM = req.WPM
	}

	_, err = app.db.Exec(
		`UPDATE typing_stats
		 SET total_tests = ?, average_wpm = ?, average_accuracy = ?, best_wpm = ?,
		     last_updated = CURRENT_TIMESTAMP
		 WHERE user_id = ?`,
		newTotalTests, newAverageWPM, newAverageAccuracy, newBestWPM, userID,
	)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	resultID, _ := result.LastInsertId()
	api.RespondWith(c, http.StatusOK, gin.H{
		"success":   true,
		"result_id": resultID,
		"message":   "Result saved successfully",
	})
}

func (app *TypingApp) handleGetStats(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	// Get user stats
	var stats models.TypingStats
	err := app.db.QueryRow(
		`SELECT id, user_id, total_tests, average_wpm, average_accuracy, best_wpm, total_time_typed
		 FROM typing_stats WHERE user_id = ?`,
		userID,
	).Scan(&stats.ID, &stats.UserID, &stats.TotalSessions, &stats.AverageWPM, &stats.AverageAccuracy, &stats.BestWPM, &stats.TotalTime)

	if err != nil && err != sql.ErrNoRows {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Get recent results
	rows, err := app.db.Query(
		`SELECT wpm, accuracy, test_type, created_at FROM typing_results
		 WHERE user_id = ? ORDER BY created_at DESC LIMIT 10`,
		userID,
	)
	defer rows.Close()

	var recentResults []api.RecentTypingResult
	for rows.Next() {
		var result api.RecentTypingResult
		if err := rows.Scan(&result.WPM, &result.Accuracy, &result.TestType, &result.CreatedAt); err != nil {
			continue
		}
		recentResults = append(recentResults, result)
	}

	// Use adapter to maintain old nested format
	api.TypingStatsResponse(c, stats, recentResults)
}

func (app *TypingApp) handleGetLeaderboard(c *gin.Context) {
	// Top WPM scores
	topWPM, _ := app.db.Query(
		`SELECT r.wpm, r.accuracy, r.test_type, r.created_at, u.username
		 FROM typing_results r
		 JOIN users u ON r.user_id = u.id
		 ORDER BY r.wpm DESC LIMIT 10`,
	)
	defer topWPM.Close()

	var topWPMList []api.LeaderboardResult
	for topWPM.Next() {
		var result api.LeaderboardResult
		if err := topWPM.Scan(&result.WPM, &result.Accuracy, &result.TestType, &result.CreatedAt, &result.Username); err != nil {
			continue
		}
		topWPMList = append(topWPMList, result)
	}

	// Top accuracy scores
	topAcc, _ := app.db.Query(
		`SELECT r.wpm, r.accuracy, r.test_type, r.created_at, u.username
		 FROM typing_results r
		 JOIN users u ON r.user_id = u.id
		 WHERE r.wpm >= 30
		 ORDER BY r.accuracy DESC, r.wpm DESC LIMIT 10`,
	)
	defer topAcc.Close()

	var topAccList []api.LeaderboardResult
	for topAcc.Next() {
		var result api.LeaderboardResult
		if err := topAcc.Scan(&result.WPM, &result.Accuracy, &result.TestType, &result.CreatedAt, &result.Username); err != nil {
			continue
		}
		topAccList = append(topAccList, result)
	}

	// Use adapter to maintain dual-list response format
	api.DualTopListResponse(c, topWPMList, topAccList)
}

// ============================================================================
// RACE ENDPOINTS
// ============================================================================

func (app *TypingApp) handleRaceStart(c *gin.Context) {
	var req api.RaceStartRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		req.WordCount = 30
		req.Difficulty = "medium"
	}

	text, opponents := app.GenerateRaceOpponents(req.Difficulty, req.WordCount)

	api.RespondWith(c, http.StatusOK, gin.H{
		"text":        text,
		"word_count":  req.WordCount,
		"difficulty":  req.Difficulty,
		"opponents":   opponents,
	})
}

func (app *TypingApp) handleRaceFinish(sessionMgr *session.Manager) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, _ := middleware.GetUserID(c)

		var req api.RaceFinishRequest

		if err := c.ShouldBindJSON(&req); err != nil {
			api.RespondWithError(c, api.ErrBadRequest)
			return
		}

		// Calculate XP
		xpEarned := CalculateRaceXP(req.WPM, req.Accuracy, req.Placement, req.Difficulty)

		// Save race result
		_, err := app.db.Exec(
			`INSERT INTO races (user_id, difficulty, placement, wpm, accuracy, race_time, xp_earned)
			 VALUES (?, ?, ?, ?, ?, ?, ?)`,
			userID, req.Difficulty, req.Placement, req.WPM, req.Accuracy, req.RaceTime, xpEarned,
		)

		if err != nil {
			api.RespondWithError(c, api.ErrInternalServer)
			return
		}

		// Update racing stats
		var raceStats struct {
			ID       int64
			Wins     int
			Podiums  int
			TotalXP  int
		}

		err = app.db.QueryRow(
			`SELECT id, wins, podiums, total_xp FROM racing_stats WHERE user_id = ?`,
			userID,
		).Scan(&raceStats.ID, &raceStats.Wins, &raceStats.Podiums, &raceStats.TotalXP)

		winsDelta := 0
		if req.Placement == 1 {
			winsDelta = 1
		}
		podiumsDelta := 0
		if req.Placement <= 3 {
			podiumsDelta = 1
		}

		if err == nil {
			_, _ = app.db.Exec(
				`UPDATE racing_stats
				 SET wins = wins + ?, podiums = podiums + ?, total_xp = total_xp + ?
				 WHERE user_id = ?`,
				winsDelta, podiumsDelta, xpEarned, userID,
			)
		} else {
			wins := 0
			if req.Placement == 1 {
				wins = 1
			}
			podiums := 0
			if req.Placement <= 3 {
				podiums = 1
			}
			_, _ = app.db.Exec(
				`INSERT INTO racing_stats (user_id, total_races, wins, podiums, total_xp)
				 VALUES (?, 1, ?, ?, ?)`,
				userID, wins, podiums, xpEarned,
			)
		}

		// Add XP to user
		_ = sessionMgr.AddUserXP(userID, int64(xpEarned))

		api.RespondWith(c, http.StatusOK, gin.H{
			"success":    true,
			"xp_earned":  xpEarned,
			"placement":  req.Placement,
		})
	}
}

func (app *TypingApp) handleRaceStats(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil || userID == 0 {
		response := api.RacingStatsResponse{
			TotalRaces: 0,
			Wins:       0,
			Podiums:    0,
			TotalXP:    0,
			AvgWPM:     0,
			CurrentCar: "🚗",
		}
		api.RespondWith(c, http.StatusOK, response)
		return
	}

	var stats struct {
		TotalRaces int
		Wins       int
		Podiums    int
		TotalXP    int
	}

	err = app.db.QueryRow(
		`SELECT total_races, wins, podiums, total_xp FROM racing_stats WHERE user_id = ?`,
		userID,
	).Scan(&stats.TotalRaces, &stats.Wins, &stats.Podiums, &stats.TotalXP)

	// Calculate average WPM from races
	var avgWPM float64
	_ = app.db.QueryRow(
		`SELECT AVG(wpm) FROM races WHERE user_id = ?`,
		userID,
	).Scan(&avgWPM)

	car := GetCarForXP(stats.TotalXP)

	response := api.RacingStatsResponse{
		TotalRaces: stats.TotalRaces,
		Wins:       stats.Wins,
		Podiums:    stats.Podiums,
		TotalXP:    stats.TotalXP,
		AvgWPM:     int(avgWPM),
		CurrentCar: car,
	}

	api.RespondWith(c, http.StatusOK, response)
}

func (app *TypingApp) handleRaceLeaderboard(c *gin.Context) {
	// Top racers by wins
	topWins, _ := app.db.Query(
		`SELECT u.username, s.wins, s.total_races, s.total_xp
		 FROM racing_stats s
		 JOIN users u ON s.user_id = u.id
		 WHERE s.total_races > 0
		 ORDER BY s.wins DESC LIMIT 10`,
	)
	defer topWins.Close()

	var topWinsList []api.RaceLeaderboardResult
	for topWins.Next() {
		var result api.RaceLeaderboardResult
		if err := topWins.Scan(&result.Username, &result.Wins, &result.TotalRaces, &result.TotalXP); err != nil {
			continue
		}
		topWinsList = append(topWinsList, result)
	}

	// Top racers by XP
	topXP, _ := app.db.Query(
		`SELECT u.username, s.total_xp, s.wins, s.total_races
		 FROM racing_stats s
		 JOIN users u ON s.user_id = u.id
		 WHERE s.total_races > 0
		 ORDER BY s.total_xp DESC LIMIT 10`,
	)
	defer topXP.Close()

	var topXPList []api.RaceLeaderboardResult
	for topXP.Next() {
		var result api.RaceLeaderboardResult
		if err := topXP.Scan(&result.Username, &result.TotalXP, &result.Wins, &result.TotalRaces); err != nil {
			continue
		}
		topXPList = append(topXPList, result)
	}

	// Use adapter to maintain dual-list response format
	api.RaceLeaderboardResponse(c, topWinsList, topXPList)
}
