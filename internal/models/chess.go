package models

import "time"

// ============================================================================
// CHESS MODELS
// ============================================================================

// ChessGame represents a complete chess game
type ChessGame struct {
	ID                int64
	WhitePlayerID     int64
	BlackPlayerID     int64
	Status            string    // "pending", "active", "checkmate", "stalemate", "resigned", "timeout"
	TimeControl       string    // "bullet", "blitz", "rapid", "classical"
	TimePerSide       int       // in seconds
	WhiteTimeLeft     int
	BlackTimeLeft     int
	BoardState        string    // FEN notation
	CurrentTurn       string    // "white" or "black"
	Winner            *int64    // nullable
	WinReason         string    // "checkmate", "resignation", "timeout", "stalemate"
	StartedAt         *time.Time
	CompletedAt       *time.Time
	CreatedAt         time.Time
}

// ChessMove represents a single move in a chess game
type ChessMove struct {
	ID                int64
	GameID            int64
	MoveNumber        int
	FromSquare        string // e.g., "e2"
	ToSquare          string // e.g., "e4"
	Piece             string // "pawn", "knight", "bishop", "rook", "queen", "king"
	IsCapture         bool
	IsCheck           bool
	IsCheckmate       bool
	AlgebraicNotation string // e.g., "e4", "Nf3", "Bxc6"
	Promotion         *string // nullable: "queen", "rook", "bishop", "knight"
	Timestamp         time.Time
}

// ChessPlayer represents a chess-specific player profile
type ChessPlayer struct {
	ID              int64
	UserID          int64
	ProfilePicture  string
	Bio             string
	Rating          int
	RatingTier      string // "Bronze", "Silver", "Gold", "Platinum", "Diamond"
	GamesPlayed     int
	Wins            int
	Losses          int
	Draws           int
	LastActiveAt    time.Time
	JoinedAt        time.Time
}

// ChessGameResult represents the outcome of a completed game
type ChessGameResult struct {
	ID            int64
	GameID        int64
	WinnerID      int64
	LoserID       int64
	ResultType    string // "checkmate", "resignation", "timeout", "stalemate"
	Duration      int    // in seconds
	MoveCount     int
	RatingDelta   int
	XPEarned      int
	RecordedAt    time.Time
}

// ChessPlayerStats represents comprehensive player statistics
type ChessPlayerStats struct {
	ID                    int64
	PlayerID              int64
	GamesPlayed           int
	Wins                  int
	Losses                int
	Draws                 int
	WinRate               float64
	AverageGameDuration   int
	FavoriteOpening       string
	FavoriteColor         string // "white" or "black"
	BestRating            int
	LowestRating          int
	LastUpdated           time.Time
}

// ChessLeaderboardEntry represents a player's ranking
type ChessLeaderboardEntry struct {
	Rank       int
	PlayerID   int64
	Username   string
	Rating     int
	GamesPlayed int
	WinRate    float64
	RatingTier string
	CreatedAt  time.Time
}

// ChessAchievement represents a chess-specific achievement
type ChessAchievement struct {
	ID          int64
	Name        string
	Description string
	IconURL     string
	Criteria    string // e.g., "100_games", "checkmate_in_4"
	CreatedAt   time.Time
}

// ChessPlayerAchievement represents a player's earned achievement
type ChessPlayerAchievement struct {
	ID            int64
	PlayerID      int64
	AchievementID int64
	EarnedAt      time.Time
}

// ChessInvitation represents a game invitation between players
type ChessInvitation struct {
	ID           int64
	FromPlayerID int64
	ToPlayerID   int64
	TimeControl  string
	Status       string    // "pending", "accepted", "rejected"
	CreatedAt    time.Time
	RespondedAt  *time.Time
}

// PlayerInfo is a lightweight representation of a player
type PlayerInfo struct {
	ID       int64  `json:"id"`
	Username string `json:"username"`
	Rating   int    `json:"rating"`
	Avatar   string `json:"avatar,omitempty"`
}

// GameSummary is a brief representation of a game for lists
type GameSummary struct {
	ID        int64     `json:"id"`
	Opponent  PlayerInfo `json:"opponent"`
	Result    string    `json:"result"` // "win", "loss", "draw"
	Duration  int       `json:"duration"`
	PlayedAt  time.Time `json:"played_at"`
}
