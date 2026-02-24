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
