package math

import (
	"fmt"
	"io"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// RegisterHandlers registers all math app routes
func RegisterHandlers(router *gin.RouterGroup, app *MathApp, sessionMgr *session.Manager) {
	// Problem generation endpoints
	router.POST("/api/generate_problem", func(c *gin.Context) {
		handleGenerateProblem(c, app)
	})

	// Speech-to-text endpoints (CRITICAL)
	router.POST("/api/transcribe", func(c *gin.Context) {
		handleTranscribeAudio(c)
	})

	router.POST("/api/check_speech_answer", func(c *gin.Context) {
		handleCheckSpeechAnswer(c)
	})

	// Answer checking
	router.POST("/api/check_answer", func(c *gin.Context) {
		handleCheckAnswer(c, app, sessionMgr)
	})

	// Practice session endpoints
	router.POST("/api/save_session", func(c *gin.Context) {
		handleSaveSession(c, app, sessionMgr)
	})

	// Stats endpoints
	router.GET("/api/stats", func(c *gin.Context) {
		handleGetStats(c, app, sessionMgr)
	})

	router.GET("/api/leaderboard", func(c *gin.Context) {
		handleGetLeaderboard(c, app)
	})
}

// handleGenerateProblem generates a new math problem
func handleGenerateProblem(c *gin.Context, app *MathApp) {
	var req api.GenerateProblemRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	problem := app.GenerateProblem(req.Operation, req.Difficulty)
	api.RespondWith(c, http.StatusOK, problem)
}

// ============================================================================
// SPEECH-TO-TEXT HANDLERS (CRITICAL)
// ============================================================================

// handleTranscribeAudio transcribes audio using Whisper API
// This is the critical endpoint for speech-to-text
// CRITICAL: Uses multipart form for audio file upload - not JSON binding
func handleTranscribeAudio(c *gin.Context) {
	// Get audio file from multipart form
	file, err := c.FormFile("audio")
	if err != nil {
		api.TranscribeAudioErrorResponse(c, http.StatusBadRequest, "No audio file provided")
		return
	}

	// Open the file
	src, err := file.Open()
	if err != nil {
		api.TranscribeAudioErrorResponse(c, http.StatusInternalServerError, "Failed to read audio file")
		return
	}
	defer src.Close()

	// Read file content
	audioData, err := io.ReadAll(src)
	if err != nil {
		api.TranscribeAudioErrorResponse(c, http.StatusInternalServerError, "Failed to read audio data")
		return
	}

	// Transcribe using Whisper API
	transcribedText, confidence, err := TranscribeAudio(audioData, file.Filename)
	if err != nil {
		api.TranscribeAudioErrorResponse(c, http.StatusInternalServerError, fmt.Sprintf("Transcription failed: %v", err))
		return
	}

	api.TranscribeAudioSuccessResponse(c, transcribedText, confidence)
}

// handleCheckSpeechAnswer checks if a spoken answer matches the expected answer
// CRITICAL: Uses CheckSpeechAnswerRequest DTO with required fields
func handleCheckSpeechAnswer(c *gin.Context) {
	var req api.CheckSpeechAnswerRequest

	if err := c.BindJSON(&req); err != nil {
		api.TranscribeAudioErrorResponse(c, http.StatusBadRequest, "Invalid request")
		return
	}

	// Default tolerance to 0.01 if not provided
	tolerance := req.Tolerance
	if tolerance == 0 {
		tolerance = 0.01
	}

	// Check the answer
	result := CheckSpeechAnswer(req.SpokenText, req.ExpectedAnswer, tolerance)

	api.CheckSpeechAnswerSuccessResponse(c, result.IsMatch, result.SpokenNumber, result.ExpectedNumber, result.MatchType, result.Feedback, result.Score)
}

// ============================================================================
// ANSWER AND SESSION HANDLERS
// ============================================================================

// handleCheckAnswer checks a regular typed answer
func handleCheckAnswer(c *gin.Context, app *MathApp, sessionMgr *session.Manager) {
	var req api.CheckAnswerRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	// Check if answer is correct (with small tolerance for floating point)
	isCorrect := CheckAnswerCorrect(req.UserAnswer, req.CorrectAnswer, 0.01)

	response := api.CheckAnswerResponse{
		Correct:        isCorrect,
		ExpectedAnswer: req.CorrectAnswer,
		UserAnswer:     req.UserAnswer,
		TimeTaken:      req.TimeTaken,
	}

	api.RespondWith(c, http.StatusOK, response)
}

// handleSaveSession saves a practice session
func handleSaveSession(c *gin.Context, app *MathApp, sessionMgr *session.Manager) {
	userID, err := middleware.GetUserID(c)
	if err != nil || userID == 0 {
		api.RespondWithError(c, api.ErrUnauthorized)
		return
	}

	var req api.SaveSessionRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	accuracy := CalculateAccuracy(req.CorrectAnswers, req.TotalQuestions)
	averageTime := CalculateAverageTime(req.TotalTime, req.TotalQuestions)

	// Save to database
	result, err := app.db.Exec(`
		INSERT INTO math_results (
			user_id, operation, difficulty, total_questions, correct_answers,
			accuracy, average_time, total_time, mode
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'practice')
	`,
		userID, req.Operation, req.Difficulty, req.TotalQuestions,
		req.CorrectAnswers, accuracy, averageTime, req.TotalTime,
	)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	resultID, _ := result.LastInsertId()

	// Calculate and award XP
	xpEarned := int64(CalculateMathXP(fmt.Sprintf("%.1f%%", accuracy), req.Difficulty))
	_ = sessionMgr.AddUserXP(userID, xpEarned)

	api.RespondWith(c, http.StatusOK, gin.H{
		"success":      true,
		"result_id":    resultID,
		"accuracy":     accuracy,
		"average_time": averageTime,
		"xp_earned":    xpEarned,
	})
}

// handleGetStats retrieves user statistics
func handleGetStats(c *gin.Context, app *MathApp, sessionMgr *session.Manager) {
	userID, err := middleware.GetUserID(c)
	if err != nil || userID == 0 {
		api.RespondWithError(c, api.ErrUnauthorized)
		return
	}

	var stats api.MathStatsResponse

	dbErr := app.db.QueryRow(`
		SELECT COALESCE(total_problems_solved, 0),
		       COALESCE(average_accuracy, 0),
		       COALESCE(best_accuracy, 0),
		       COALESCE(total_time_spent, 0)
		FROM math_stats
		WHERE user_id = ?
	`, userID).Scan(&stats.TotalProblemsSolved, &stats.AverageAccuracy,
		&stats.BestAccuracy, &stats.TotalTimeSpent)

	if dbErr != nil {
		// User has no stats yet - return zero values
		stats = api.MathStatsResponse{
			TotalProblemsSolved: 0,
			AverageAccuracy:     0,
			BestAccuracy:        0,
			TotalTimeSpent:      0,
		}
	}

	api.RespondWith(c, http.StatusOK, stats)
}

// handleGetLeaderboard retrieves the math leaderboard
func handleGetLeaderboard(c *gin.Context, app *MathApp) {
	var req api.LeaderboardRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		// Use defaults if binding fails
		req.Limit = 10
		req.Offset = 0
	}

	// Apply default and max limit
	if req.Limit <= 0 || req.Limit > 100 {
		req.Limit = 10
	}

	rows, err := app.db.Query(`
		SELECT u.username, ms.average_accuracy, ms.total_problems_solved, ms.total_time_spent
		FROM math_stats ms
		JOIN users u ON ms.user_id = u.id
		ORDER BY ms.average_accuracy DESC, ms.total_problems_solved DESC
		LIMIT ?
	`, req.Limit)

	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}
	defer rows.Close()

	var entries []api.MathLeaderboardEntry
	for rows.Next() {
		var entry api.MathLeaderboardEntry
		if err := rows.Scan(&entry.Username, &entry.AverageAccuracy,
			&entry.TotalProblemsSolved, &entry.TotalTimeSpent); err != nil {
			continue
		}
		entries = append(entries, entry)
	}

	// Use adapter to maintain backward compatibility with old response format
	api.LegacyLeaderboardResponse(c, entries, len(entries))
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

// CheckAnswerCorrect checks if a user's answer matches the expected answer
func CheckAnswerCorrect(userAnswer, expectedAnswer, tolerance float64) bool {
	diff := userAnswer - expectedAnswer
	if diff < 0 {
		diff = -diff
	}
	return diff <= tolerance
}
