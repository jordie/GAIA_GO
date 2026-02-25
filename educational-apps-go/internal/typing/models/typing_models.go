package models

import (
	"time"
)

// User represents a typing app user
type User struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	Username  string    `gorm:"unique;not null" json:"username"`
	CreatedAt time.Time `json:"created_at"`
	LastActive time.Time `json:"last_active"`
}

// TypingExercise represents a typing exercise
type TypingExercise struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	Title          string    `gorm:"not null" json:"title"`
	Content        string    `gorm:"not null" json:"content"`
	Category       string    `json:"category"` // common_words, programming, quotes, etc
	DifficultyLevel int      `json:"difficulty_level"`
	WordCount      int       `json:"word_count"`
	CharacterCount int       `json:"character_count"`
	CreatedAt      time.Time `json:"created_at"`
}

// TypingResult represents a user's typing test result
type TypingResult struct {
	ID                 uint      `gorm:"primaryKey" json:"id"`
	UserID             uint      `gorm:"not null;index" json:"user_id"`
	ExerciseID         *uint     `json:"exercise_id,omitempty"`
	WPM                int       `gorm:"not null" json:"wpm"`
	Accuracy           float64   `gorm:"not null" json:"accuracy"`
	TestType           string    `json:"test_type"` // timed, words, accuracy
	TestDuration       int       `json:"test_duration"` // in seconds
	TotalCharacters    int       `json:"total_characters"`
	CorrectCharacters  int       `json:"correct_characters"`
	IncorrectCharacters int      `json:"incorrect_characters"`
	CreatedAt          time.Time `gorm:"autoCreateTime" json:"created_at"`
	User               *User     `json:"user,omitempty"`
}

// UserStats represents aggregated user statistics
type UserStats struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	UserID           uint      `gorm:"unique;not null;index" json:"user_id"`
	TotalTests       int       `gorm:"default:0" json:"total_tests"`
	AverageWPM       float64   `gorm:"default:0" json:"average_wpm"`
	AverageAccuracy  float64   `gorm:"default:0" json:"average_accuracy"`
	BestWPM          int       `gorm:"default:0" json:"best_wpm"`
	TotalTimeTyped   int       `gorm:"default:0" json:"total_time_typed"` // in seconds
	LastUpdated      time.Time `json:"last_updated"`
	User             *User     `json:"user,omitempty"`
}

// CreateUserRequest is the request to create a new user
type CreateUserRequest struct {
	Username string `json:"username" binding:"required,min=2,max=20"`
}

// SwitchUserRequest is the request to switch users
type SwitchUserRequest struct {
	UserID uint `json:"user_id" binding:"required"`
}

// GetTextRequest is the request to get typing text
type GetTextRequest struct {
	Type      string `json:"type" binding:"required"` // words, time, or category
	WordCount int    `json:"word_count" binding:"min=1,max=1000"`
	Category  string `json:"category"` // common_words, programming, quotes, paragraphs, numbers, special_characters
	Duration  int    `json:"duration"` // for time mode (seconds)
}

// SaveResultRequest is the request to save a typing result
type SaveResultRequest struct {
	WPM                 int     `json:"wpm" binding:"required,min=0,max=500"`
	Accuracy            float64 `json:"accuracy" binding:"required,min=0,max=100"`
	TestType            string  `json:"test_type" binding:"required"`
	TestDuration        int     `json:"test_duration" binding:"required,min=0"`
	TotalCharacters     int     `json:"total_characters" binding:"required,min=0"`
	CorrectCharacters   int     `json:"correct_characters" binding:"required,min=0"`
	IncorrectCharacters int     `json:"incorrect_characters" binding:"required,min=0"`
	ExerciseID          *uint   `json:"exercise_id,omitempty"`
}

// UserResponse is the response for user data
type UserResponse struct {
	ID         uint      `json:"id"`
	Username   string    `json:"username"`
	CreatedAt  time.Time `json:"created_at"`
	LastActive time.Time `json:"last_active"`
}

// TypingResultResponse is the response for typing result data
type TypingResultResponse struct {
	ID                  uint      `json:"id"`
	WPM                 int       `json:"wpm"`
	Accuracy            float64   `json:"accuracy"`
	TestType            string    `json:"test_type"`
	TestDuration        int       `json:"test_duration"`
	TotalCharacters     int       `json:"total_characters"`
	CorrectCharacters   int       `json:"correct_characters"`
	IncorrectCharacters int       `json:"incorrect_characters"`
	CreatedAt           time.Time `json:"created_at"`
}

// LeaderboardEntry represents a leaderboard position
type LeaderboardEntry struct {
	Rank     int     `json:"rank"`
	Username string  `json:"username"`
	WPM      int     `json:"wpm"`
	Accuracy float64 `json:"accuracy"`
	TestType string  `json:"test_type"`
	Date     time.Time `json:"date"`
}

// GetTextResponse is the response for text generation
type GetTextResponse struct {
	Text            string `json:"text"`
	WordCount       int    `json:"word_count"`
	CharacterCount  int    `json:"character_count"`
	Category        string `json:"category"`
}

// UserStatsResponse is the response for user statistics
type UserStatsResponse struct {
	UserStats    UserStats              `json:"user_stats"`
	RecentResults []TypingResultResponse `json:"recent_results"`
	BestScores   map[string]interface{} `json:"best_scores"`
	CurrentUser  string                 `json:"current_user"`
}

// LeaderboardResponse is the response for leaderboard data
type LeaderboardResponse struct {
	TopWPM      []LeaderboardEntry `json:"top_wpm"`
	TopAccuracy []LeaderboardEntry `json:"top_accuracy"`
}

// PaginatedTypingResults for paginated responses
type PaginatedTypingResults struct {
	Total      int64                 `json:"total"`
	Page       int                   `json:"page"`
	PageSize   int                   `json:"page_size"`
	TotalPages int64                 `json:"total_pages"`
	Data       []TypingResultResponse `json:"data"`
}
