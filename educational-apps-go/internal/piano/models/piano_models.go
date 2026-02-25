package models

import (
	"time"
)

// Note represents a musical note
type Note struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	NoteName   string    `gorm:"unique;not null" json:"note_name"`
	FrequencyHz float64  `gorm:"not null" json:"frequency_hz"`
	MIDINumber int       `gorm:"not null" json:"midi_number"`
	CreatedAt  time.Time `json:"created_at"`
}

// Exercise represents a piano exercise
type Exercise struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	Title           string    `gorm:"not null" json:"title"`
	Description     string    `json:"description"`
	DifficultyLevel int       `gorm:"check:difficulty_level >= 1 AND difficulty_level <= 5" json:"difficulty_level"`
	NotesSequence   string    `gorm:"not null" json:"notes_sequence"` // Comma-separated notes
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

// Attempt represents a user's attempt at an exercise
type Attempt struct {
	ID                 uint      `gorm:"primaryKey" json:"id"`
	UserID             uint      `gorm:"not null;index" json:"user_id"`
	ExerciseID         uint      `gorm:"not null" json:"exercise_id"`
	NotesPlayed        string    `gorm:"not null" json:"notes_played"` // Comma-separated notes
	IsCorrect          bool      `gorm:"not null" json:"is_correct"`
	AccuracyPercentage *float64  `json:"accuracy_percentage"`
	ResponseTimeMs     *int      `json:"response_time_ms"`
	AttemptedAt        time.Time `gorm:"autoCreateTime" json:"attempted_at"`
	Exercise           *Exercise `json:"exercise,omitempty"`
}

// Progress represents user progress in piano app
type Progress struct {
	ID                       uint      `gorm:"primaryKey" json:"id"`
	UserID                   uint      `gorm:"unique;not null;index" json:"user_id"`
	CurrentDifficultyLevel   int       `gorm:"default:1" json:"current_difficulty_level"`
	TotalExercisesCompleted  int       `gorm:"default:0" json:"total_exercises_completed"`
	AverageAccuracyPercentage float64  `gorm:"default:0" json:"average_accuracy_percentage"`
	UpdatedAt                time.Time `json:"updated_at"`
}

// CreateExerciseRequest is the request body for creating an exercise
type CreateExerciseRequest struct {
	Title           string `json:"title" binding:"required,min=1,max=255"`
	Description     string `json:"description"`
	DifficultyLevel int    `json:"difficulty_level" binding:"required,min=1,max=5"`
	NotesSequence   string `json:"notes_sequence" binding:"required"`
}

// CreateAttemptRequest is the request body for recording an attempt
type CreateAttemptRequest struct {
	ExerciseID  uint   `json:"exercise_id" binding:"required"`
	NotesPlayed string `json:"notes_played" binding:"required"`
	IsCorrect   bool   `json:"is_correct"`
	AccuracyPercentage *float64 `json:"accuracy_percentage"`
	ResponseTimeMs *int `json:"response_time_ms"`
}

// ExerciseResponse is the response body for exercise data
type ExerciseResponse struct {
	ID              uint      `json:"id"`
	Title           string    `json:"title"`
	Description     string    `json:"description"`
	DifficultyLevel int       `json:"difficulty_level"`
	NotesSequence   string    `json:"notes_sequence"`
	CreatedAt       time.Time `json:"created_at"`
}

// AttemptResponse is the response body for attempt data
type AttemptResponse struct {
	ID                 uint      `json:"id"`
	ExerciseID         uint      `json:"exercise_id"`
	NotesPlayed        string    `json:"notes_played"`
	IsCorrect          bool      `json:"is_correct"`
	AccuracyPercentage *float64  `json:"accuracy_percentage"`
	ResponseTimeMs     *int      `json:"response_time_ms"`
	AttemptedAt        time.Time `json:"attempted_at"`
}

// DatabasePaginatedResult represents paginated response
type DatabasePaginatedResult struct {
	Total      int64       `json:"total"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	TotalPages int64       `json:"total_pages"`
	Data       interface{} `json:"data"`
}

// ProgressWithUserInfo is the response for leaderboard entries
type ProgressWithUserInfo struct {
	Rank                       int     `json:"rank"`
	UserID                     uint    `json:"user_id"`
	CurrentDifficultyLevel     int     `json:"current_difficulty_level"`
	TotalExercisesCompleted    int     `json:"total_exercises_completed"`
	AverageAccuracyPercentage float64 `json:"average_accuracy_percentage"`
}
