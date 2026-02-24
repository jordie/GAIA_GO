package api

import "time"

// ============================================================================
// SHARED REQUEST/RESPONSE DTOS
// ============================================================================

// SaveSessionRequest is used to save a session result across multiple apps
type SaveSessionRequest struct {
	// Common fields
	Difficulty string  `json:"difficulty" binding:"required"`
	Score      int     `json:"score"`
	Accuracy   float64 `json:"accuracy" binding:"required"`
	TotalTime  int     `json:"total_time" binding:"required"`

	// Math-specific
	Operation      string `json:"operation,omitempty"`
	TotalQuestions int    `json:"total_questions,omitempty"`
	CorrectAnswers int    `json:"correct_answers,omitempty"`

	// Piano-specific
	Level           int    `json:"level,omitempty"`
	Hand            string `json:"hand,omitempty"`
	TotalNotes      int    `json:"total_notes,omitempty"`
	CorrectNotes    int    `json:"correct_notes,omitempty"`
	PieceID         string `json:"piece_id,omitempty"`
	ExerciseType    string `json:"exercise_type,omitempty"`

	// Reading-specific
	SessionID      string `json:"session_id,omitempty"`
	WordsCompleted int    `json:"words_completed,omitempty"`
	ReadingSpeed   int    `json:"reading_speed,omitempty"`

	// Typing-specific
	WPM                 int    `json:"wpm,omitempty"`
	RawWPM              int    `json:"raw_wpm,omitempty"`
	TestType            string `json:"test_type,omitempty"`
	TestDuration        int    `json:"test_duration,omitempty"`
	TotalCharacters     int    `json:"total_characters,omitempty"`
	CorrectCharacters   int    `json:"correct_characters,omitempty"`
	IncorrectCharacters int    `json:"incorrect_characters,omitempty"`
	Errors              int    `json:"errors,omitempty"`
	TextSnippet         string `json:"text_snippet,omitempty"`
}

// StatsResponse represents unified statistics format
type StatsResponse struct {
	TotalSessions   int       `json:"total_sessions"`
	AverageScore    float64   `json:"average_score"`
	BestScore       float64   `json:"best_score"`
	TotalTime       int       `json:"total_time"`
	LastUpdated     time.Time `json:"last_updated,omitempty"`
	AverageAccuracy float64   `json:"average_accuracy,omitempty"`
}

// LeaderboardRequest represents a leaderboard query
type LeaderboardRequest struct {
	Limit  int `form:"limit" binding:"max=100"`
	Offset int `form:"offset"`
}

// LeaderboardEntry represents a single leaderboard entry
type LeaderboardEntry struct {
	Rank      int     `json:"rank"`
	UserID    int64   `json:"user_id"`
	Username  string  `json:"username"`
	Score     float64 `json:"score"`
	Value     float64 `json:"value,omitempty"`
	Metric    string  `json:"metric"`
	AppName   string  `json:"app_name,omitempty"`
	CreatedAt time.Time `json:"created_at,omitempty"`
}

// ============================================================================
// APP-SPECIFIC REQUEST DTOs
// ============================================================================

// Math DTOs
type GenerateProblemRequest struct {
	Operation  string `json:"operation" binding:"required"`
	Difficulty string `json:"difficulty" binding:"required"`
}

type CheckAnswerRequest struct {
	ProblemID      string  `json:"problem_id" binding:"required"`
	UserAnswer     float64 `json:"user_answer" binding:"required"`
	CorrectAnswer  float64 `json:"correct_answer" binding:"required"`
	TimeTaken      float64 `json:"time_taken"`
}

type MathWeaknessRequest struct {
	Operation  string `json:"operation" binding:"required"`
	Difficulty string `json:"difficulty"`
}

// Piano DTOs
type CreateUserRequest struct {
	Username string `json:"username" binding:"required,min=2,max=50"`
}

type SaveNoteEventRequest struct {
	Note      string `json:"note" binding:"required"`
	Hand      string `json:"hand" binding:"required"`
	IsCorrect bool   `json:"is_correct"`
	Duration  int    `json:"duration"`
}

type UpdateLevelRequest struct {
	Level int `json:"level" binding:"required,min=1"`
}

type UpdateGoalProgressRequest struct {
	GoalID   int64 `json:"goal_id" binding:"required"`
	Progress int   `json:"progress" binding:"required,min=0"`
}

// Reading DTOs
type GetWordsRequest struct {
	Count           int      `json:"count" binding:"max=50"`
	Level           int      `json:"level"`
	ExcludeWords    []string `json:"exclude_words"`
	IncludeMastered bool     `json:"include_mastered"`
}

type MarkWordCorrectRequest struct {
	Word string `json:"word" binding:"required"`
}

type MarkWordIncorrectRequest struct {
	Word string `json:"word" binding:"required"`
}

// Typing DTOs
type SaveResultRequest struct {
	WPM                 int    `json:"wpm" binding:"required"`
	Accuracy            float64 `json:"accuracy" binding:"required"`
	TestType            string  `json:"test_type" binding:"required"`
	TestDuration        int    `json:"test_duration" binding:"required"`
	TotalCharacters     int    `json:"total_characters"`
	CorrectCharacters   int    `json:"correct_characters"`
	IncorrectCharacters int    `json:"incorrect_characters"`
	RawWPM              int    `json:"raw_wpm"`
	Errors              int    `json:"errors"`
	TextSnippet         string  `json:"text_snippet"`
}

type RaceFinishRequest struct {
	WPM        int     `json:"wpm" binding:"required"`
	Accuracy   float64 `json:"accuracy" binding:"required"`
	Placement  int     `json:"placement" binding:"required"`
	RaceTime   float64 `json:"race_time" binding:"required"`
	Difficulty string  `json:"difficulty" binding:"required"`
}

type GetUsersRequest struct {
	Limit  int `form:"limit" binding:"max=100"`
	Offset int `form:"offset"`
	SortBy string `form:"sort_by"` // "xp", "accuracy", "speed"
}

// ============================================================================
// APP-SPECIFIC RESPONSE DTOs
// ============================================================================

// ProblemResponse represents a generated problem
type ProblemResponse struct {
	ID            string  `json:"id"`
	Operation     string  `json:"operation"`
	Operand1      int     `json:"operand1"`
	Operand2      int     `json:"operand2"`
	Difficulty    string  `json:"difficulty"`
	CorrectAnswer float64 `json:"correct_answer"`
}

// SessionResultResponse represents the result of saving a session
type SessionResultResponse struct {
	ID        int64     `json:"id"`
	UserID    int64     `json:"user_id"`
	AppName   string    `json:"app_name"`
	Score     int       `json:"score"`
	Accuracy  float64   `json:"accuracy"`
	XPEarned  int       `json:"xp_earned"`
	CreatedAt time.Time `json:"created_at"`
}

// UserResponse represents a user profile
type UserResponse struct {
	ID           int64     `json:"id"`
	Username     string    `json:"username"`
	Level        int       `json:"level,omitempty"`
	TotalXP      int       `json:"total_xp,omitempty"`
	AverageScore float64   `json:"average_score,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
}

// WordMasteryResponse represents word mastery level
type WordMasteryResponse struct {
	Word         string `json:"word"`
	MasteryLevel int    `json:"mastery_level"` // 0-5
	AttemptCount int    `json:"attempt_count"`
	CorrectCount int    `json:"correct_count"`
}

// ============================================================================
// MATH APP - Response DTOs
// ============================================================================

// CheckAnswerResponse represents the result of checking a math answer
type CheckAnswerResponse struct {
	Correct        bool    `json:"correct"`
	ExpectedAnswer float64 `json:"expected_answer"`
	UserAnswer     float64 `json:"user_answer"`
	TimeTaken      float64 `json:"time_taken"`
}

// MathStatsResponse represents math-specific user statistics
type MathStatsResponse struct {
	TotalProblemsSolved int     `json:"total_problems_solved"`
	AverageAccuracy     float64 `json:"average_accuracy"`
	BestAccuracy        float64 `json:"best_accuracy"`
	TotalTimeSpent      int     `json:"total_time_spent"`
}

// MathLeaderboardEntry represents a single entry in the math leaderboard
type MathLeaderboardEntry struct {
	Username            string  `json:"username"`
	AverageAccuracy     float64 `json:"average_accuracy"`
	TotalProblemsSolved int     `json:"total_problems_solved"`
	TotalTimeSpent      int     `json:"total_time_spent"`
}

// ============================================================================
// TYPING APP - Request DTOs
// ============================================================================

// RaceStartRequest represents a request to start a typing race
type RaceStartRequest struct {
	WordCount  int    `json:"word_count"`
	Difficulty string `json:"difficulty"`
}

// ============================================================================
// TYPING APP - Response DTOs
// ============================================================================

// UserResponseTyping represents a user in typing app context
type UserResponseTyping struct {
	ID       int64  `json:"id"`
	Username string `json:"username"`
}

// RecentTypingResult represents a recent typing result
type RecentTypingResult struct {
	WPM       int       `json:"wpm"`
	Accuracy  float64   `json:"accuracy"`
	TestType  string    `json:"test_type"`
	CreatedAt time.Time `json:"created_at"`
}

// TypingStatsDetailedResponse represents detailed typing statistics with recent results
type TypingStatsDetailedResponse struct {
	UserStats     interface{}         `json:"user_stats"`
	RecentResults []RecentTypingResult `json:"recent_results"`
}

// RacingStatsResponse represents racing statistics for a user
type RacingStatsResponse struct {
	TotalRaces int `json:"total_races"`
	Wins       int `json:"wins"`
	Podiums    int `json:"podiums"`
	TotalXP    int `json:"total_xp"`
	AvgWPM     int `json:"avg_wpm"`
	CurrentCar string `json:"current_car"`
}

// LeaderboardResult represents a leaderboard result entry
type LeaderboardResult struct {
	WPM       int       `json:"wpm"`
	Accuracy  float64   `json:"accuracy"`
	TestType  string    `json:"test_type"`
	CreatedAt time.Time `json:"created_at"`
	Username  string    `json:"username"`
}

// RaceLeaderboardResult represents a race leaderboard entry
type RaceLeaderboardResult struct {
	Username   string `json:"username"`
	Wins       int    `json:"wins"`
	TotalRaces int    `json:"total_races"`
	TotalXP    int    `json:"total_xp"`
}

// ============================================================================
// READING APP - Request DTOs
// ============================================================================

// ReadingSessionRequest represents a request to create a reading session
type ReadingSessionRequest struct {
	Level int `json:"level"`
}

// CompleteSessionRequest represents a request to complete a reading session
type CompleteSessionRequest struct {
	SessionID      string `json:"session_id" binding:"required"`
	WordsCompleted int    `json:"words_completed"`
	CorrectAnswers int    `json:"correct_answers"`
	TotalTime      int    `json:"total_time"`
}

// ============================================================================
// READING APP - Response DTOs
// ============================================================================

// ReadingProgressResponse represents user reading progress
type ReadingProgressResponse struct {
	CurrentLevel        int    `json:"current_level"`
	TotalWordsMastered  int    `json:"total_words_mastered"`
	LastUpdated         string `json:"last_updated"`
}

// ReadingLeaderboardEntry represents a reading leaderboard entry
type ReadingLeaderboardEntry struct {
	Username        string  `json:"username"`
	WordsMastered   int     `json:"words_mastered"`
	AverageAccuracy float64 `json:"average_accuracy"`
}

// ============================================================================
// PIANO APP - Request DTOs
// ============================================================================

// CompleteWarmupRequest represents a request to complete a warmup
type CompleteWarmupRequest struct {
	WarmupID int64   `json:"warmup_id" binding:"required"`
	Score    int     `json:"score"`
	Accuracy float64 `json:"accuracy"`
}

// ============================================================================
// PIANO APP - Response DTOs
// ============================================================================

// PianoStatsResponse represents piano-specific user statistics
type PianoStatsResponse struct {
	AverageLevelAchieved int     `json:"average_level_achieved,omitempty"`
	TotalSessionsCount   int     `json:"total_sessions_count,omitempty"`
	AverageAccuracy      float64 `json:"average_accuracy,omitempty"`
	AverageResponseTime  float64 `json:"average_response_time,omitempty"`
}

// StreakResponse represents user's current streak information
type StreakResponse struct {
	CurrentStreak int `json:"current_streak"`
	BestStreak    int `json:"best_streak"`
	LastPractice  string `json:"last_practice,omitempty"`
}

// GoalResponse represents a user's learning goal
type GoalResponse struct {
	ID         int64  `json:"id"`
	Title      string `json:"title"`
	Progress   int    `json:"progress"`
	Target     int    `json:"target"`
	Completed  bool   `json:"completed"`
	CreatedAt  string `json:"created_at,omitempty"`
}

// AchievementResponse represents a badge/achievement earned by user
type AchievementResponse struct {
	ID          int64  `json:"id"`
	BadgeID     string `json:"badge_id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	IconURL     string `json:"icon_url,omitempty"`
	UnlockedAt  string `json:"unlocked_at,omitempty"`
}

// NoteAnalyticsEntry represents analytics for a single note
type NoteAnalyticsEntry struct {
	Note         string  `json:"note"`
	Hand         string  `json:"hand"`
	Attempts     int     `json:"attempts"`
	CorrectCount int     `json:"correct_count"`
	Accuracy     float64 `json:"accuracy"`
}

// WarmupResponse represents a piano warmup exercise
type WarmupResponse struct {
	ID          int64    `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Notes       []string `json:"notes"`
}

// CentralSyncResponse represents synchronized user data across apps
type CentralSyncResponse struct {
	Stats      interface{} `json:"stats,omitempty"`
	Badges     interface{} `json:"badges,omitempty"`
	UserID     int64       `json:"user_id,omitempty"`
	LastSync   string      `json:"last_sync,omitempty"`
}

// ============================================================================
// CHESS APP - Request DTOs
// ============================================================================

// CreateGameRequest represents a request to create a new chess game
type CreateGameRequest struct {
	OpponentID  int64  `json:"opponent_id" binding:"required"`
	TimeControl string `json:"time_control" binding:"required"` // "bullet", "blitz", "rapid", "classical"
	TimePerSide int    `json:"time_per_side" binding:"required"`
	Difficulty  string `json:"difficulty,omitempty"` // Optional AI difficulty
}

// MakeMoveRequest represents a request to make a chess move
type MakeMoveRequest struct {
	GameID     int64  `json:"game_id" binding:"required"`
	FromSquare string `json:"from_square" binding:"required"` // e.g., "e2"
	ToSquare   string `json:"to_square" binding:"required"`   // e.g., "e4"
	Promotion  string `json:"promotion,omitempty"`            // "queen", "rook", "bishop", "knight"
}

// ValidateMoveRequest represents a request to validate a move
type ValidateMoveRequest struct {
	GameID     int64  `json:"game_id" binding:"required"`
	FromSquare string `json:"from_square" binding:"required"`
	ToSquare   string `json:"to_square" binding:"required"`
	Piece      string `json:"piece" binding:"required"`
	BoardState string `json:"board_state" binding:"required"` // FEN notation
}

// ResignGameRequest represents a request to resign from a game
type ResignGameRequest struct {
	GameID int64  `json:"game_id" binding:"required"`
	Reason string `json:"reason,omitempty"`
}

// AcceptGameRequest represents accepting a game invitation
type AcceptGameRequest struct {
	GameID int64 `json:"game_id" binding:"required"`
}

// InviteRequest represents sending a game invitation
type InviteRequest struct {
	OpponentID  int64  `json:"opponent_id" binding:"required"`
	TimeControl string `json:"time_control" binding:"required"`
}

// FollowRequest represents following a player
type FollowRequest struct {
	PlayerID int64 `json:"player_id" binding:"required"`
}

// ListGamesRequest represents a request to list games
type ListGamesRequest struct {
	Status string `form:"status"`
	Limit  int    `form:"limit" binding:"max=100"`
	Offset int    `form:"offset"`
}

// RecordResultRequest represents recording a game result
type RecordResultRequest struct {
	GameID     int64  `json:"game_id" binding:"required"`
	WinnerID   int64  `json:"winner_id" binding:"required"`
	ResultType string `json:"result_type" binding:"required"` // "checkmate", "resignation", "timeout", "stalemate"
	Duration   int    `json:"duration"`
	MoveCount  int    `json:"move_count"`
}

// ============================================================================
// CHESS APP - Response DTOs
// ============================================================================

// GameResponse represents complete game state
type GameResponse struct {
	ID            int64      `json:"id"`
	WhitePlayer   PlayerInfo `json:"white_player"`
	BlackPlayer   PlayerInfo `json:"black_player"`
	Status        string     `json:"status"`
	TimeControl   string     `json:"time_control"`
	BoardState    string     `json:"board_state"`    // FEN
	Moves         []ChessMove `json:"moves,omitempty"`
	CurrentTurn   string     `json:"current_turn"`
	IsCheck       bool       `json:"is_check"`
	IsCheckmate   bool       `json:"is_checkmate"`
	IsStalemate   bool       `json:"is_stalemate"`
	Winner        *int64     `json:"winner,omitempty"`
	WinReason     string     `json:"win_reason,omitempty"`
	CreatedAt     time.Time  `json:"created_at"`
}

// ChessMove for response
type ChessMove struct {
	MoveNumber        int    `json:"move_number"`
	FromSquare        string `json:"from_square"`
	ToSquare          string `json:"to_square"`
	Piece             string `json:"piece"`
	AlgebraicNotation string `json:"algebraic_notation"`
	IsCapture         bool   `json:"is_capture"`
	IsCheck           bool   `json:"is_check"`
}

// ValidationResponse represents move validation result
type ValidationResponse struct {
	Valid              bool   `json:"valid"`
	Reason             string `json:"reason,omitempty"`
	IsCapture          bool   `json:"is_capture"`
	IsCastle           bool   `json:"is_castle"`
	IsEnPassant        bool   `json:"is_en_passant"`
	RequiresPromotion  bool   `json:"requires_promotion"`
	NextBoardState     string `json:"next_board_state,omitempty"` // FEN after move
}

// PlayerProfileResponse represents chess player profile
type ChessPlayerProfileResponse struct {
	PlayerID       int64         `json:"player_id"`
	Username       string        `json:"username"`
	ProfilePicture string        `json:"profile_picture,omitempty"`
	Bio            string        `json:"bio,omitempty"`
	Rating         int           `json:"rating"`
	RatingTier     string        `json:"rating_tier"`
	Stats          ChessPlayerStatsResponse `json:"stats"`
	Achievements   []Achievement `json:"achievements,omitempty"`
	RecentGames    []GameSummary `json:"recent_games,omitempty"`
	JoinedAt       time.Time     `json:"joined_at"`
}

// ChessPlayerStatsResponse represents player statistics
type ChessPlayerStatsResponse struct {
	GamesPlayed         int     `json:"games_played"`
	Wins                int     `json:"wins"`
	Losses              int     `json:"losses"`
	Draws               int     `json:"draws"`
	WinRate             float64 `json:"win_rate"`
	AverageGameDuration int     `json:"average_game_duration"`
	FavoriteOpening     string  `json:"favorite_opening,omitempty"`
	BestRating          int     `json:"best_rating"`
	LowestRating        int     `json:"lowest_rating"`
}

// Achievement for response
type Achievement struct {
	ID          int64     `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	IconURL     string    `json:"icon_url,omitempty"`
	EarnedAt    time.Time `json:"earned_at,omitempty"`
}

// GameSummary for response (already defined above in PlayerInfo)

// LeaderboardResponse represents leaderboard entries
type ChessLeaderboardResponse struct {
	Entries []ChessLeaderboardEntryResponse `json:"entries"`
	Total   int                              `json:"total"`
}

// ChessLeaderboardEntryResponse represents a leaderboard entry
type ChessLeaderboardEntryResponse struct {
	Rank        int    `json:"rank"`
	PlayerID    int64  `json:"player_id"`
	Username    string `json:"username"`
	Rating      int    `json:"rating"`
	GamesPlayed int    `json:"games_played"`
	WinRate     float64 `json:"win_rate"`
	RatingTier  string `json:"rating_tier"`
}

// GameListResponse represents a list of games
type GameListResponse struct {
	Games []GameResponse `json:"games"`
	Total int            `json:"total"`
}

// GameReplayResponse represents game replay data
type GameReplayResponse struct {
	ID            int64     `json:"id"`
	WhitePlayer   PlayerInfo `json:"white_player"`
	BlackPlayer   PlayerInfo `json:"black_player"`
	Moves         []ChessMove `json:"moves"`
	StartingBoard string    `json:"starting_board"` // FEN
	Result        string    `json:"result"`
	Duration      int       `json:"duration"`
}

// GameAnalysisResponse represents game analysis
type GameAnalysisResponse struct {
	GameID       int64  `json:"game_id"`
	Opening      string `json:"opening"`
	OpeningECO   string `json:"opening_eco,omitempty"`
	BestMoveMissed int  `json:"best_moves_missed"`
	GamePhase    string `json:"game_phase"` // "opening", "middle", "endgame"
	Complexity   int    `json:"complexity"` // 1-10 scale
}

// GameResultResponse represents game result recording
type GameResultResponse struct {
	GameID       int64  `json:"game_id"`
	WinnerID     int64  `json:"winner_id"`
	RatingDelta  int    `json:"rating_delta"`
	XPEarned     int    `json:"xp_earned"`
	AchievementUnlocked string `json:"achievement_unlocked,omitempty"`
}

// InvitationResponse represents game invitation
type InvitationResponse struct {
	ID           int64     `json:"id"`
	FromPlayerID int64     `json:"from_player_id"`
	ToPlayerID   int64     `json:"to_player_id"`
	TimeControl  string    `json:"time_control"`
	Status       string    `json:"status"`
	CreatedAt    time.Time `json:"created_at"`
}

// FriendsListResponse represents player's friend list
type FriendsListResponse struct {
	Friends []PlayerInfo `json:"friends"`
	Total   int          `json:"total"`
}

// RatingHistoryResponse represents rating change history
type RatingHistoryResponse struct {
	Entries []RatingHistoryEntry `json:"entries"`
}

// RatingHistoryEntry represents a single rating change
type RatingHistoryEntry struct {
	GameID         int64     `json:"game_id"`
	OldRating      int       `json:"old_rating"`
	NewRating      int       `json:"new_rating"`
	Delta          int       `json:"delta"`
	OpponentRating int       `json:"opponent_rating"`
	Result         string    `json:"result"` // "win", "loss", "draw"
	RecordedAt     time.Time `json:"recorded_at"`
}

// AchievementsResponse represents available achievements
type AchievementsResponse struct {
	Achievements []Achievement `json:"achievements"`
	Total        int           `json:"total"`
}

// PlayerAchievementsResponse represents player's achievements
type PlayerAchievementsResponse struct {
	PlayerID     int64         `json:"player_id"`
	Achievements []Achievement `json:"achievements"`
	Total        int           `json:"total"`
}

// ============================================================================
// MATH APP - Speech-to-Text DTOs
// ============================================================================

// CheckSpeechAnswerRequest represents a spoken answer validation request
type CheckSpeechAnswerRequest struct {
	SpokenText     string  `json:"spoken_text" binding:"required"`
	ExpectedAnswer float64 `json:"expected_answer" binding:"required"`
	Tolerance      float64 `json:"tolerance"` // Optional, defaults to 0.01
}

// CheckSpeechAnswerResponse represents the result of speech answer validation
type CheckSpeechAnswerResponse struct {
	Success        bool    `json:"success"`
	Match          bool    `json:"match"`
	SpokenNumber   float64 `json:"spoken_number"`
	ExpectedNumber float64 `json:"expected_number"`
	MatchType      string  `json:"match_type"`
	Feedback       string  `json:"feedback"`
	Score          float64 `json:"score"`
}

// TranscribeAudioResponse represents the result of audio transcription
type TranscribeAudioResponse struct {
	Success    bool    `json:"success"`
	Text       string  `json:"text"`
	Confidence float64 `json:"confidence"`
}
