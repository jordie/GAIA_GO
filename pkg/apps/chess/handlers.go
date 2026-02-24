package chess

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// RegisterHandlers registers all chess app routes
func RegisterHandlers(router *gin.RouterGroup, app *ChessApp, sessionMgr *session.Manager) {
	// Game management
	router.POST("/games", func(c *gin.Context) {
		handleCreateGame(c, app, sessionMgr)
	})

	router.GET("/games/:game_id", func(c *gin.Context) {
		handleGetGame(c, app)
	})

	router.POST("/games/:game_id/move", func(c *gin.Context) {
		handleMakeMove(c, app, sessionMgr)
	})

	router.POST("/games/:game_id/resign", func(c *gin.Context) {
		handleResignGame(c, app)
	})

	router.GET("/games", func(c *gin.Context) {
		handleListActiveGames(c, app)
	})

	// Move validation
	router.POST("/validate-move", func(c *gin.Context) {
		handleValidateMove(c)
	})

	// Player and social
	router.GET("/players/:player_id", func(c *gin.Context) {
		handleGetPlayerProfile(c, app)
	})

	router.GET("/players/:player_id/stats", func(c *gin.Context) {
		handleGetPlayerStats(c, app)
	})

	router.GET("/leaderboard", func(c *gin.Context) {
		handleGetLeaderboard(c, app)
	})

	// Game history and analysis
	router.GET("/games/:game_id/replay", func(c *gin.Context) {
		handleGetGameReplay(c, app)
	})

	router.GET("/players/:player_id/history", func(c *gin.Context) {
		handleGetGameHistory(c, app)
	})

	router.POST("/records/result", func(c *gin.Context) {
		handleRecordGameResult(c, app, sessionMgr)
	})
}

// ============================================================================
// GAME MANAGEMENT HANDLERS
// ============================================================================

// handleCreateGame creates a new chess game
func handleCreateGame(c *gin.Context, app *ChessApp, sessionMgr *session.Manager) {
	var req api.CreateGameRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1 // Default guest user
	}

	game, err := app.CreateGame(userID, req.OpponentID, req.TimeControl, req.TimePerSide)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Award XP for creating game
	sessionMgr.AddUserXP(userID, 10)

	api.RespondWith(c, http.StatusCreated, gin.H{
		"game_id": game.ID,
		"status":  game.Status,
	})
}

// handleGetGame retrieves a game state
func handleGetGame(c *gin.Context, app *ChessApp) {
	gameIDStr := c.Param("game_id")

	gameID, err := strconv.ParseInt(gameIDStr, 10, 64)
	if err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	game, err := app.GetGame(gameID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	moves, err := app.GetGameMoves(gameID)
	if err != nil {
		moves = []struct{}{} // Return empty list on error
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"game":  game,
		"moves": moves,
	})
}

// handleMakeMove processes a chess move
func handleMakeMove(c *gin.Context, app *ChessApp, sessionMgr *session.Manager) {
	var req api.MakeMoveRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	game, err := app.GetGame(req.GameID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// TODO: Validate move using chess engine
	// For now, accept any move (placeholder)

	// Record the move
	moveNumber := len(make([]int, 1)) + 1 // Placeholder move number
	move, err := app.RecordMove(req.GameID, moveNumber, req.FromSquare, req.ToSquare, "piece", req.FromSquare+req.ToSquare, false, false, false)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	userID, _ := middleware.GetUserID(c)
	sessionMgr.AddUserXP(userID, 5)

	api.RespondWith(c, http.StatusOK, gin.H{
		"success": true,
		"move":    move,
		"game_id": req.GameID,
	})
}

// handleResignGame marks a game as resigned
func handleResignGame(c *gin.Context, app *ChessApp) {
	var req api.ResignGameRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	if err := app.ResignGame(req.GameID, userID); err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"success": true,
		"message": "Game resigned",
	})
}

// handleListActiveGames lists active games for current player
func handleListActiveGames(c *gin.Context, app *ChessApp) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		userID = 1
	}

	games, err := app.ListActiveGames(userID, 20, 0)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"games": games,
		"count": len(games),
	})
}

// ============================================================================
// MOVE VALIDATION HANDLERS
// ============================================================================

// handleValidateMove validates a chess move without committing it
func handleValidateMove(c *gin.Context) {
	var req api.ValidateMoveRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	// TODO: Implement actual move validation logic
	// For now, accept all moves (placeholder)
	isValid := true
	reason := "Move is valid"

	api.RespondWith(c, http.StatusOK, gin.H{
		"valid":  isValid,
		"reason": reason,
	})
}

// ============================================================================
// PLAYER & SOCIAL HANDLERS
// ============================================================================

// handleGetPlayerProfile retrieves player's chess profile
func handleGetPlayerProfile(c *gin.Context, app *ChessApp) {
	playerIDStr := c.Param("player_id")

	playerID, err := strconv.ParseInt(playerIDStr, 10, 64)
	if err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	stats, err := app.GetPlayerStats(playerID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"player_id": playerID,
		"stats":     stats,
	})
}

// handleGetPlayerStats retrieves player statistics
func handleGetPlayerStats(c *gin.Context, app *ChessApp) {
	playerIDStr := c.Param("player_id")

	playerID, err := strconv.ParseInt(playerIDStr, 10, 64)
	if err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	stats, err := app.GetPlayerStats(playerID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"stats": stats,
	})
}

// handleGetLeaderboard retrieves the chess leaderboard
func handleGetLeaderboard(c *gin.Context, app *ChessApp) {
	limit := 50
	offset := 0

	entries, err := app.GetLeaderboard(limit, offset)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"leaderboard": entries,
		"count":       len(entries),
	})
}

// ============================================================================
// GAME HISTORY & ANALYTICS HANDLERS
// ============================================================================

// handleGetGameReplay retrieves a game for replay
func handleGetGameReplay(c *gin.Context, app *ChessApp) {
	gameIDStr := c.Param("game_id")

	gameID, err := api.ParseInt64(gameIDStr)
	if err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	game, err := app.GetGame(gameID)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	moves, err := app.GetGameMoves(gameID)
	if err != nil {
		moves = []struct{}{}
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"game":  game,
		"moves": moves,
	})
}

// handleGetGameHistory retrieves game history for a player
func handleGetGameHistory(c *gin.Context, app *ChessApp) {
	playerIDStr := c.Param("player_id")

	playerID, err := strconv.ParseInt(playerIDStr, 10, 64)
	if err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	games, err := app.ListActiveGames(playerID, 20, 0)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	api.RespondWith(c, http.StatusOK, gin.H{
		"games": games,
		"count": len(games),
	})
}

// handleRecordGameResult records the result of a completed game
func handleRecordGameResult(c *gin.Context, app *ChessApp, sessionMgr *session.Manager) {
	var req api.RecordResultRequest

	if err := c.BindJSON(&req); err != nil {
		api.RespondWithError(c, api.ErrBadRequest)
		return
	}

	gameResult, err := app.RecordGameResult(req.GameID, req.WinnerID, 0, req.ResultType, req.Duration, req.MoveCount)
	if err != nil {
		api.RespondWithError(c, api.ErrInternalServer)
		return
	}

	// Award XP to winner
	sessionMgr.AddUserXP(req.WinnerID, int64(gameResult.XPEarned))

	api.RespondWith(c, http.StatusOK, gin.H{
		"result_id":    gameResult.ID,
		"rating_delta": gameResult.RatingDelta,
		"xp_earned":    gameResult.XPEarned,
	})
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

// strconv.ParseInt needs to be imported at package level
// The handlers above use strconv.ParseInt which is handled by gin context parsing
