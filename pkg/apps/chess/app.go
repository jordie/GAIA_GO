package chess

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/jgirmay/GAIA_GO/internal/models"
)

// ChessApp manages all chess-related operations
type ChessApp struct {
	db *sql.DB
}

// NewChessApp creates a new ChessApp instance
func NewChessApp(db *sql.DB) *ChessApp {
	return &ChessApp{db: db}
}

// CreateGame creates a new chess game between two players
func (app *ChessApp) CreateGame(whitePlayerID, blackPlayerID int64, timeControl string, timePerSide int) (*models.ChessGame, error) {
	game := &models.ChessGame{
		WhitePlayerID: whitePlayerID,
		BlackPlayerID: blackPlayerID,
		Status:        "active",
		TimeControl:   timeControl,
		TimePerSide:   timePerSide,
		WhiteTimeLeft: timePerSide,
		BlackTimeLeft: timePerSide,
		BoardState:    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", // Standard starting FEN
		CurrentTurn:   "white",
		CreatedAt:     time.Now(),
	}

	result, err := app.db.Exec(
		`INSERT INTO chess_games (white_player_id, black_player_id, status, time_control,
		 time_per_side, white_time_left, black_time_left, board_state, current_turn, created_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		game.WhitePlayerID, game.BlackPlayerID, game.Status, game.TimeControl,
		game.TimePerSide, game.WhiteTimeLeft, game.BlackTimeLeft, game.BoardState,
		game.CurrentTurn, game.CreatedAt,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to create game: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return nil, fmt.Errorf("failed to get game id: %w", err)
	}

	game.ID = id
	return game, nil
}

// GetGame retrieves a game by ID
func (app *ChessApp) GetGame(gameID int64) (*models.ChessGame, error) {
	game := &models.ChessGame{}

	err := app.db.QueryRow(
		`SELECT id, white_player_id, black_player_id, status, time_control, time_per_side,
		        white_time_left, black_time_left, board_state, current_turn, winner, win_reason,
		        started_at, completed_at, created_at
		 FROM chess_games WHERE id = ?`,
		gameID,
	).Scan(&game.ID, &game.WhitePlayerID, &game.BlackPlayerID, &game.Status,
		&game.TimeControl, &game.TimePerSide, &game.WhiteTimeLeft, &game.BlackTimeLeft,
		&game.BoardState, &game.CurrentTurn, &game.Winner, &game.WinReason,
		&game.StartedAt, &game.CompletedAt, &game.CreatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("game not found")
		}
		return nil, fmt.Errorf("failed to get game: %w", err)
	}

	return game, nil
}

// RecordMove saves a move to the game history
func (app *ChessApp) RecordMove(gameID int64, moveNumber int, fromSquare, toSquare, piece, notation string, isCapture, isCheck, isCheckmate bool) (*models.ChessMove, error) {
	move := &models.ChessMove{
		GameID:                gameID,
		MoveNumber:            moveNumber,
		FromSquare:            fromSquare,
		ToSquare:              toSquare,
		Piece:                 piece,
		IsCapture:             isCapture,
		IsCheck:               isCheck,
		IsCheckmate:           isCheckmate,
		AlgebraicNotation:     notation,
		Timestamp:             time.Now(),
	}

	result, err := app.db.Exec(
		`INSERT INTO chess_moves (game_id, move_number, from_square, to_square, piece,
		 is_capture, is_check, is_checkmate, algebraic_notation, timestamp)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		move.GameID, move.MoveNumber, move.FromSquare, move.ToSquare, move.Piece,
		move.IsCapture, move.IsCheck, move.IsCheckmate, move.AlgebraicNotation, move.Timestamp,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to record move: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return nil, fmt.Errorf("failed to get move id: %w", err)
	}

	move.ID = id
	return move, nil
}

// GetGameMoves retrieves all moves for a game
func (app *ChessApp) GetGameMoves(gameID int64) ([]models.ChessMove, error) {
	rows, err := app.db.Query(
		`SELECT id, game_id, move_number, from_square, to_square, piece,
		        is_capture, is_check, is_checkmate, algebraic_notation, timestamp
		 FROM chess_moves WHERE game_id = ? ORDER BY move_number ASC`,
		gameID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get moves: %w", err)
	}
	defer rows.Close()

	var moves []models.ChessMove
	for rows.Next() {
		var move models.ChessMove
		if err := rows.Scan(&move.ID, &move.GameID, &move.MoveNumber, &move.FromSquare,
			&move.ToSquare, &move.Piece, &move.IsCapture, &move.IsCheck, &move.IsCheckmate,
			&move.AlgebraicNotation, &move.Timestamp); err != nil {
			continue
		}
		moves = append(moves, move)
	}

	return moves, nil
}

// UpdateGameStatus updates the status and result of a game
func (app *ChessApp) UpdateGameStatus(gameID int64, status, winReason string, winnerID *int64) error {
	_, err := app.db.Exec(
		`UPDATE chess_games SET status = ?, win_reason = ?, winner = ?, completed_at = ? WHERE id = ?`,
		status, winReason, winnerID, time.Now(), gameID,
	)
	return err
}

// RecordGameResult saves the final result of a game
func (app *ChessApp) RecordGameResult(gameID, winnerID, loserID int64, resultType string, duration, moveCount int) (*models.ChessGameResult, error) {
	// Calculate rating delta (simplified)
	ratingDelta := 16 // Standard chess rating change

	result := &models.ChessGameResult{
		GameID:      gameID,
		WinnerID:    winnerID,
		LoserID:     loserID,
		ResultType:  resultType,
		Duration:    duration,
		MoveCount:   moveCount,
		RatingDelta: ratingDelta,
		XPEarned:    ratingDelta * 5, // 5 XP per rating point
		RecordedAt:  time.Now(),
	}

	_, err := app.db.Exec(
		`INSERT INTO chess_game_results (game_id, winner_id, loser_id, result_type, duration, move_count, rating_delta, xp_earned, recorded_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		result.GameID, result.WinnerID, result.LoserID, result.ResultType,
		result.Duration, result.MoveCount, result.RatingDelta, result.XPEarned, result.RecordedAt,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to record result: %w", err)
	}

	return result, nil
}

// GetPlayerStats retrieves player's chess statistics
func (app *ChessApp) GetPlayerStats(playerID int64) (*models.ChessPlayerStats, error) {
	stats := &models.ChessPlayerStats{PlayerID: playerID}

	err := app.db.QueryRow(
		`SELECT id, player_id, games_played, wins, losses, draws, win_rate,
		        average_game_duration, favorite_opening, favorite_color, best_rating, lowest_rating, last_updated
		 FROM chess_player_stats WHERE player_id = ?`,
		playerID,
	).Scan(&stats.ID, &stats.PlayerID, &stats.GamesPlayed, &stats.Wins, &stats.Losses,
		&stats.Draws, &stats.WinRate, &stats.AverageGameDuration, &stats.FavoriteOpening,
		&stats.FavoriteColor, &stats.BestRating, &stats.LowestRating, &stats.LastUpdated,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			// Return default stats if player has no record yet
			return stats, nil
		}
		return nil, fmt.Errorf("failed to get player stats: %w", err)
	}

	return stats, nil
}

// GetLeaderboard retrieves the chess leaderboard
func (app *ChessApp) GetLeaderboard(limit, offset int) ([]models.ChessLeaderboardEntry, error) {
	rows, err := app.db.Query(
		`SELECT id, player_id, username, rating, games_played, win_rate, rating_tier, created_at
		 FROM chess_leaderboard ORDER BY rating DESC LIMIT ? OFFSET ?`,
		limit, offset,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get leaderboard: %w", err)
	}
	defer rows.Close()

	var entries []models.ChessLeaderboardEntry
	for rows.Next() {
		var entry models.ChessLeaderboardEntry
		if err := rows.Scan(&entry.Rank, &entry.PlayerID, &entry.Username, &entry.Rating,
			&entry.GamesPlayed, &entry.WinRate, &entry.RatingTier, &entry.CreatedAt); err != nil {
			continue
		}
		entry.Rank = offset + 1 + len(entries)
		entries = append(entries, entry)
	}

	return entries, nil
}

// ListActiveGames retrieves active games for a player
func (app *ChessApp) ListActiveGames(playerID int64, limit, offset int) ([]models.ChessGame, error) {
	rows, err := app.db.Query(
		`SELECT id, white_player_id, black_player_id, status, time_control, time_per_side,
		        white_time_left, black_time_left, board_state, current_turn, winner, win_reason,
		        started_at, completed_at, created_at
		 FROM chess_games
		 WHERE (white_player_id = ? OR black_player_id = ?) AND status = 'active'
		 ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		playerID, playerID, limit, offset,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to list games: %w", err)
	}
	defer rows.Close()

	var games []models.ChessGame
	for rows.Next() {
		var game models.ChessGame
		if err := rows.Scan(&game.ID, &game.WhitePlayerID, &game.BlackPlayerID, &game.Status,
			&game.TimeControl, &game.TimePerSide, &game.WhiteTimeLeft, &game.BlackTimeLeft,
			&game.BoardState, &game.CurrentTurn, &game.Winner, &game.WinReason,
			&game.StartedAt, &game.CompletedAt, &game.CreatedAt); err != nil {
			continue
		}
		games = append(games, game)
	}

	return games, nil
}

// ResignGame marks a game as resigned
func (app *ChessApp) ResignGame(gameID int64, resigningPlayerID int64) error {
	game, err := app.GetGame(gameID)
	if err != nil {
		return err
	}

	var winnerID int64
	if resigningPlayerID == game.WhitePlayerID {
		winnerID = game.BlackPlayerID
	} else {
		winnerID = game.WhitePlayerID
	}

	return app.UpdateGameStatus(gameID, "resigned", "resignation", &winnerID)
}
