package guessing

import (
	"database/sql"
	"math/rand"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
	"github.com/jgirmay/GAIA_GO/internal/app"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// GuessingApp is a simple number guessing game
type GuessingApp struct {
	db              *sql.DB
	statsManager    *app.StatsManager
	achievementMgr  *app.AchievementManager
}

// NewGuessingApp creates a new guessing game app
func NewGuessingApp(db *sql.DB) *GuessingApp {
	return &GuessingApp{
		db:             db,
		statsManager:   app.NewStatsManager(db),
		achievementMgr: app.NewAchievementManager(db),
	}
}

// GetName implements App interface
func (ga *GuessingApp) GetName() string {
	return "guessing"
}

// GetDisplayName implements App interface
func (ga *GuessingApp) GetDisplayName() string {
	return "Guess the Number"
}

// GetDescription implements App interface
func (ga *GuessingApp) GetDescription() string {
	return "Guess the secret number and compete for the fastest time"
}

// GetVersion implements App interface
func (ga *GuessingApp) GetVersion() string {
	return "1.0.0"
}

// RegisterRoutes implements App interface
func (ga *GuessingApp) RegisterRoutes(router *gin.RouterGroup) {
	router.POST("/start", ga.handleStartGame)
	router.POST("/guess", middleware.RequireAuth(), ga.handleGuess)
	router.GET("/stats", middleware.RequireAuth(), ga.handleGetStats)
	router.GET("/leaderboard", ga.handleGetLeaderboard)
	router.POST("/score", middleware.RequireAuth(), ga.handleSaveScore)
}

// InitDB initializes database tables for the app
func (ga *GuessingApp) InitDB() error {
	_, err := ga.db.Exec(`
		CREATE TABLE IF NOT EXISTS guessing_games (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER,
			secret_number INTEGER NOT NULL,
			guess_count INTEGER DEFAULT 0,
			correct INTEGER DEFAULT 0,
			time_taken REAL,
			difficulty TEXT DEFAULT 'medium',
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			completed_at TIMESTAMP,
			FOREIGN KEY (user_id) REFERENCES users(id)
		)
	`)
	return err
}

// GetUserStats implements App interface
func (ga *GuessingApp) GetUserStats(userID int64) (map[string]interface{}, error) {
	var totalGames, wins int
	var avgGuesses float64

	err := ga.db.QueryRow(`
		SELECT COUNT(*), SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END), AVG(guess_count)
		FROM guessing_games
		WHERE user_id = ?
	`, userID).Scan(&totalGames, &wins, &avgGuesses)

	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}

	highScore, _ := ga.statsManager.GetHighScore(userID, "guessing")

	return map[string]interface{}{
		"total_games": totalGames,
		"wins":        wins,
		"avg_guesses": avgGuesses,
		"high_score":  highScore,
	}, nil
}

// GetLeaderboard implements App interface
func (ga *GuessingApp) GetLeaderboard(limit int) ([]map[string]interface{}, error) {
	return ga.statsManager.GetLeaderboard("guessing", limit)
}

// ============================================================================
// HANDLERS
// ============================================================================

type GameStartRequest struct {
	Difficulty string `json:"difficulty"` // easy (1-50), medium (1-100), hard (1-1000)
}

type GameStartResponse struct {
	GameID     int64  `json:"game_id"`
	Difficulty string `json:"difficulty"`
	Message    string `json:"message"`
}

type GuessRequest struct {
	GameID int64 `json:"game_id"`
	Guess  int   `json:"guess"`
}

type GuessResponse struct {
	Correct bool   `json:"correct"`
	Message string `json:"message"`
	Hint    string `json:"hint,omitempty"`
}

func (ga *GuessingApp) handleStartGame(c *gin.Context) {
	var req GameStartRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		req.Difficulty = "medium"
	}

	userID, _ := middleware.GetUserID(c)

	var max int
	switch req.Difficulty {
	case "easy":
		max = 50
	case "hard":
		max = 1000
	default:
		max = 100
	}

	secretNumber := rand.Intn(max) + 1

	var gameID int64
	result, err := ga.db.Exec(
		`INSERT INTO guessing_games (user_id, secret_number, difficulty) VALUES (?, ?, ?)`,
		userID, secretNumber, req.Difficulty,
	)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	gameID, _ = result.LastInsertId()

	api.RespondWith(c, 200, GameStartResponse{
		GameID:     gameID,
		Difficulty: req.Difficulty,
		Message:    "Guess a number between 1 and " + string(rune(max)),
	})
}

func (ga *GuessingApp) handleGuess(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	var req GuessRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	var secretNumber int
	var correct, guessCount int

	err := ga.db.QueryRow(
		`SELECT secret_number, correct, guess_count FROM guessing_games WHERE id = ? AND user_id = ?`,
		req.GameID, userID,
	).Scan(&secretNumber, &correct, &guessCount)

	if err != nil {
		api.RespondWithError(c, api.ErrNotFound)
		return
	}

	if correct == 1 {
		api.RespondWithError(c, api.ErrConflict) // Already completed
		return
	}

	guessCount++
	isCorrect := req.Guess == secretNumber
	hint := ""

	if !isCorrect {
		if req.Guess < secretNumber {
			hint = "Too low, guess higher"
		} else {
			hint = "Too high, guess lower"
		}
	}

	if isCorrect {
		ga.db.Exec(
			`UPDATE guessing_games SET correct = 1, guess_count = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?`,
			guessCount, req.GameID,
		)
		// Record score (guess count, lower is better)
		ga.statsManager.RecordScore(userID, "guessing", 1000-guessCount)
	} else {
		ga.db.Exec(`UPDATE guessing_games SET guess_count = ? WHERE id = ?`, guessCount, req.GameID)
	}

	api.RespondWith(c, 200, GuessResponse{
		Correct: isCorrect,
		Message: map[bool]string{true: "Correct!", false: "Wrong!"}[isCorrect],
		Hint:    hint,
	})
}

func (ga *GuessingApp) handleGetStats(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	stats, err := ga.GetUserStats(userID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}
	api.RespondWith(c, 200, stats)
}

func (ga *GuessingApp) handleGetLeaderboard(c *gin.Context) {
	leaderboard, err := ga.GetLeaderboard(10)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}
	if leaderboard == nil {
		leaderboard = []map[string]interface{}{}
	}
	api.RespondWith(c, 200, gin.H{"leaderboard": leaderboard})
}

func (ga *GuessingApp) handleSaveScore(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	var req struct {
		Score int `json:"score"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	err := ga.statsManager.RecordScore(userID, "guessing", req.Score)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, 200, gin.H{"success": true})
}
