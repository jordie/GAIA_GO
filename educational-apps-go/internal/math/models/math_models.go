package models

import (
	"time"
)

// User represents a math app user
type User struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	Username   string    `gorm:"unique;not null" json:"username"`
	CreatedAt  time.Time `json:"created_at"`
	LastActive time.Time `json:"last_active"`
}

// MathProblem represents a generated math problem
type MathProblem struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	Mode         string    `json:"mode"` // addition, subtraction, multiplication, division, mixed
	Difficulty   string    `json:"difficulty"` // easy, medium, hard, expert
	Operand1     int       `json:"operand1"`
	Operand2     int       `json:"operand2"`
	Operator     string    `json:"operator"` // +, -, *, /
	CorrectAnswer int      `json:"correct_answer"`
	CreatedAt    time.Time `json:"created_at"`
}

// SessionResult represents a complete practice session
type SessionResult struct {
	ID                 uint      `gorm:"primaryKey" json:"id"`
	UserID             uint      `gorm:"not null;index" json:"user_id"`
	Mode               string    `json:"mode"`
	Difficulty         string    `json:"difficulty"`
	TotalQuestions     int       `json:"total_questions"`
	CorrectAnswers     int       `json:"correct_answers"`
	TotalTime          float64   `json:"total_time"` // seconds
	AverageTime        float64   `json:"average_time"` // seconds
	Accuracy           float64   `json:"accuracy"` // percentage
	CreatedAt          time.Time `json:"created_at"`
}

// QuestionHistory tracks individual questions answered
type QuestionHistory struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	UserID        uint      `gorm:"not null;index" json:"user_id"`
	Question      string    `json:"question"`
	UserAnswer    string    `json:"user_answer"`
	CorrectAnswer string    `json:"correct_answer"`
	IsCorrect     bool      `json:"is_correct"`
	TimeTaken     float64   `json:"time_taken"` // seconds
	FactFamily    string    `json:"fact_family"`
	Mode          string    `json:"mode"`
	CreatedAt     time.Time `json:"created_at"`
}

// Mistake tracks repeated errors
type Mistake struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	UserID        uint      `gorm:"not null;index" json:"user_id"`
	Question      string    `json:"question"`
	CorrectAnswer string    `json:"correct_answer"`
	UserAnswer    string    `json:"user_answer"`
	Mode          string    `json:"mode"`
	FactFamily    string    `json:"fact_family"`
	ErrorCount    int       `json:"error_count"`
	LastError     time.Time `json:"last_error"`
}

// Mastery tracks mastery level for individual facts
type Mastery struct {
	ID                   uint      `gorm:"primaryKey" json:"id"`
	UserID               uint      `gorm:"not null;index" json:"user_id"`
	Fact                 string    `json:"fact"`
	Mode                 string    `json:"mode"`
	CorrectStreak        int       `json:"correct_streak"`
	TotalAttempts        int       `json:"total_attempts"`
	MasteryLevel         float64   `json:"mastery_level"` // 0-100
	LastPracticed        time.Time `json:"last_practiced"`
	AverageResponseTime  float64   `json:"average_response_time"`
	FastestTime          float64   `json:"fastest_time"`
	SlowestTime          float64   `json:"slowest_time"`
}

// LearningProfile tracks user's learning characteristics
type LearningProfile struct {
	ID                 uint      `gorm:"primaryKey" json:"id"`
	UserID             uint      `gorm:"unique;not null;index" json:"user_id"`
	LearningStyle      string    `json:"learning_style"` // visual, sequential, global
	PreferredTimeOfDay string    `json:"preferred_time_of_day"` // morning, afternoon, evening
	AttentionSpan      int       `json:"attention_span"` // seconds
	BestStreakTime     string    `json:"best_streak_time"`
	WeakTimeOfDay      string    `json:"weak_time_of_day"`
	AvgSessionLength   int       `json:"avg_session_length"` // seconds
	TotalPracticeTime  int       `json:"total_practice_time"` // seconds
	ProfileUpdated     time.Time `json:"profile_updated"`
}

// PerformancePattern tracks performance by time/day
type PerformancePattern struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	UserID          uint      `gorm:"not null;index" json:"user_id"`
	HourOfDay       int       `json:"hour_of_day"` // 0-23
	DayOfWeek       int       `json:"day_of_week"` // 0-6 (Sunday-Saturday)
	AverageAccuracy float64   `json:"average_accuracy"`
	AverageSpeed    float64   `json:"average_speed"` // seconds
	SessionCount    int       `json:"session_count"`
	LastUpdated     time.Time `json:"last_updated"`
}

// RepetitionSchedule tracks spaced repetition for facts
type RepetitionSchedule struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	UserID      uint      `gorm:"not null;index" json:"user_id"`
	Fact        string    `json:"fact"`
	Mode        string    `json:"mode"`
	NextReview  time.Time `json:"next_review"`
	IntervalDays int      `json:"interval_days"`
	EaseFactor  float64   `json:"ease_factor"` // 1.3-3.0
	ReviewCount int       `json:"review_count"`
}

// Request/Response Models

type GenerateProblemRequest struct {
	Mode         string `json:"mode" binding:"required,oneof=addition subtraction multiplication division mixed"`
	Difficulty   string `json:"difficulty" binding:"required,oneof=easy medium hard expert"`
	PracticeType string `json:"practice_type" binding:"oneof=random focused smart review"` // random, focused, smart, review
}

type CheckAnswerRequest struct {
	Question      string  `json:"question" binding:"required"`
	UserAnswer    string  `json:"user_answer" binding:"required"`
	CorrectAnswer string  `json:"correct_answer" binding:"required"`
	TimeTaken     float64 `json:"time_taken" binding:"required,gt=0"`
	Mode          string  `json:"mode" binding:"required"`
	FactFamily    string  `json:"fact_family"`
}

type SaveSessionRequest struct {
	Mode           string `json:"mode" binding:"required"`
	Difficulty     string `json:"difficulty" binding:"required"`
	TotalQuestions int    `json:"total_questions" binding:"required,gt=0"`
	CorrectAnswers int    `json:"correct_answers" binding:"required,gte=0"`
	TotalTime      float64 `json:"total_time" binding:"required,gt=0"`
}

type CreateUserRequest struct {
	Username string `json:"username" binding:"required,min=2,max=20"`
}

type GenerateProblemResponse struct {
	Question   string `json:"question"`
	Answer     string `json:"answer"`
	FactFamily string `json:"fact_family"`
	Hint       string `json:"hint"`
	IsReview   bool   `json:"is_review,omitempty"`
	ErrorCount int    `json:"error_count,omitempty"`
}

type CheckAnswerResponse struct {
	IsCorrect    bool    `json:"is_correct"`
	Explanation  string  `json:"explanation"`
	NewMastery   float64 `json:"new_mastery,omitempty"`
	NextReviewIn string  `json:"next_review_in,omitempty"`
}

type SessionStatistics struct {
	UserID             uint                    `json:"user_id"`
	Username           string                  `json:"username"`
	TotalSessions      int                     `json:"total_sessions"`
	AverageAccuracy    float64                 `json:"average_accuracy"`
	AverageTime        float64                 `json:"average_time"`
	BestAccuracy       float64                 `json:"best_accuracy"`
	StrengthAreas      map[string]float64      `json:"strength_areas"`
	WeakAreas          map[string]float64      `json:"weak_areas"`
	OverallMastery     float64                 `json:"overall_mastery"`
	RecentSessions     []*SessionResult        `json:"recent_sessions"`
	LearningProfile    *LearningProfile        `json:"learning_profile,omitempty"`
	PerformancePattern map[string]interface{} `json:"performance_pattern,omitempty"`
}

type WeakAreasResponse struct {
	Weaknesses []map[string]interface{} `json:"weaknesses"`
	Suggestions []string               `json:"suggestions"`
}

type PracticePlanResponse struct {
	RecommendedMode       string   `json:"recommended_mode"`
	RecommendedDifficulty string   `json:"recommended_difficulty"`
	FocusAreas            []string `json:"focus_areas"`
	EstimatedTime         int      `json:"estimated_time"` // seconds
	Rationale             string   `json:"rationale"`
}
