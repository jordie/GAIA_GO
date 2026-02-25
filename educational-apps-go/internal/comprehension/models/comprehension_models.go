package models

import (
	"database/sql/driver"
	"encoding/json"
	"time"
)

// QuestionType represents a question format (word_tap, multiple_choice, etc.)
type QuestionType struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	TypeCode         string    `gorm:"unique;not null" json:"type_code"`
	TypeName         string    `gorm:"not null" json:"type_name"`
	Description      string    `json:"description"`
	RenderTemplate   string    `json:"render_template"`
	CreatedAt        time.Time `json:"created_at"`
}

// Subject represents a topic area (Grammar, Vocabulary, etc.)
type Subject struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	Code        string    `gorm:"unique;not null" json:"code"`
	Name        string    `gorm:"not null" json:"name"`
	Description string    `json:"description"`
	Icon        string    `json:"icon"`
	Color       string    `json:"color"`
	SortOrder   int       `json:"sort_order"`
	CreatedAt   time.Time `json:"created_at"`
}

// DifficultyLevel represents a difficulty tier (1-5)
type DifficultyLevel struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	Level       int       `gorm:"unique;not null" json:"level"`
	Name        string    `gorm:"not null" json:"name"`
	Description string    `json:"description"`
	MinAge      int       `json:"min_age"`
	MaxAge      int       `json:"max_age"`
	CreatedAt   time.Time `json:"created_at"`
}

// QuestionContent holds flexible JSON content based on question type
// Each question type has different content structure
type QuestionContent map[string]interface{}

// Scan implements sql.Scanner interface
func (qc QuestionContent) Scan(value interface{}) error {
	bytes, ok := value.([]byte)
	if !ok {
		return nil
	}
	return json.Unmarshal(bytes, (*map[string]interface{})(&qc))
}

// Value implements driver.Valuer interface
func (qc QuestionContent) Value() (driver.Value, error) {
	return json.Marshal(qc)
}

// Question represents a comprehension question
type Question struct {
	ID             uint              `gorm:"primaryKey" json:"id"`
	QuestionType   string            `gorm:"index;not null" json:"question_type"`
	Subject        string            `gorm:"index;not null" json:"subject"`
	Difficulty     int               `gorm:"index;not null" json:"difficulty"`
	Content        QuestionContent   `gorm:"type:json" json:"content"`
	Prompt         string            `gorm:"type:text" json:"prompt"`
	Instructions   string            `gorm:"type:text" json:"instructions"`
	Points         int               `gorm:"default:10" json:"points"`
	TimeLimit      int               `gorm:"default:60" json:"time_limit"` // seconds
	Tags           string            `gorm:"type:text" json:"tags"`
	Source         string            `json:"source"`
	Active         bool              `gorm:"default:true" json:"active"`
	CreatedAt      time.Time         `json:"created_at"`
}

// UserProgress tracks completion of individual questions
type UserProgress struct {
	ID             uint            `gorm:"primaryKey" json:"id"`
	UserID         uint            `gorm:"index;not null" json:"user_id"`
	QuestionID     uint            `gorm:"index;not null" json:"question_id"`
	QuestionType   string          `json:"question_type"`
	Subject        string          `json:"subject"`
	Difficulty     int             `json:"difficulty"`
	Correct        bool            `json:"correct"`
	Score          int             `json:"score"`
	MaxScore       int             `json:"max_score"`
	TimeTaken      int             `json:"time_taken"` // seconds
	Attempts       int             `gorm:"default:1" json:"attempts"`
	UserAnswer     json.RawMessage `gorm:"type:json" json:"user_answer"`
	CompletedAt    time.Time       `json:"completed_at"`
	CreatedAt      time.Time       `json:"created_at"`
}

// UserStats aggregates user statistics by subject
type UserStats struct {
	ID                   uint      `gorm:"primaryKey" json:"id"`
	UserID               uint      `gorm:"index;unique:uq_user_subject,not null" json:"user_id"`
	Subject              string    `gorm:"index;unique:uq_user_subject,not null" json:"subject"`
	QuestionsAttempted   int       `gorm:"default:0" json:"questions_attempted"`
	QuestionsCorrect     int       `gorm:"default:0" json:"questions_correct"`
	TotalScore           int       `gorm:"default:0" json:"total_score"`
	BestStreak           int       `gorm:"default:0" json:"best_streak"`
	CurrentStreak        int       `gorm:"default:0" json:"current_streak"`
	TotalTime            int       `gorm:"default:0" json:"total_time"` // seconds
	LastPractice         time.Time `json:"last_practice"`
	CreatedAt            time.Time `json:"created_at"`
	UpdatedAt            time.Time `json:"updated_at"`
}

// User represents a comprehension app user
type User struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	Username  string    `gorm:"unique;not null" json:"username"`
	CreatedAt time.Time `json:"created_at"`
	LastActive time.Time `json:"last_active"`
}

// === REQUEST/RESPONSE TYPES ===

// CheckAnswerRequest is the request body for answer validation
type CheckAnswerRequest struct {
	QuestionID   uint                   `json:"question_id" binding:"required,gt=0"`
	Answer       string                 `json:"answer"`
	SelectedWords map[string]string      `json:"selected_words"`
	TargetType   string                 `json:"target_type"`
	SelectedIndex int                   `json:"selected_index"`
	UserInput    string                 `json:"user_input"`
}

// CheckAnswerResponse is the response for answer validation
type CheckAnswerResponse struct {
	Correct           bool                   `json:"correct"`
	Score             int                    `json:"score"`
	MaxScore          int                    `json:"max_score"`
	CorrectAnswer     interface{}            `json:"correct_answer,omitempty"`
	Explanation       string                 `json:"explanation,omitempty"`
	Feedback          map[string]interface{} `json:"feedback,omitempty"`
	UserAnswer        interface{}            `json:"user_answer"`
}

// SaveProgressRequest saves user progress after answering
type SaveProgressRequest struct {
	QuestionID uint                   `json:"question_id" binding:"required,gt=0"`
	Correct    bool                   `json:"correct"`
	Score      int                    `json:"score"`
	MaxScore   int                    `json:"max_score"`
	TimeTaken  int                    `json:"time_taken"`
	UserAnswer json.RawMessage        `json:"user_answer"`
}

// UserProgressResponse returns user progress data
type UserProgressResponse struct {
	ID             uint            `json:"id"`
	QuestionID     uint            `json:"question_id"`
	Correct        bool            `json:"correct"`
	Score          int             `json:"score"`
	MaxScore       int             `json:"max_score"`
	TimeTaken      int             `json:"time_taken"`
	CompletedAt    time.Time       `json:"completed_at"`
}

// UserStatsResponse returns aggregated statistics
type UserStatsResponse struct {
	UserID               uint      `json:"user_id"`
	Subject              string    `json:"subject"`
	QuestionsAttempted   int       `json:"questions_attempted"`
	QuestionsCorrect     int       `json:"questions_correct"`
	Accuracy             float64   `json:"accuracy"`
	TotalScore           int       `json:"total_score"`
	BestStreak           int       `json:"best_streak"`
	CurrentStreak        int       `json:"current_streak"`
	AverageTimePerQuestion float64 `json:"average_time_per_question"`
	LastPractice         time.Time `json:"last_practice"`
}

// QuestionsListResponse returns paginated questions
type QuestionsListResponse struct {
	Questions []QuestionResponse `json:"questions"`
	Total     int64              `json:"total"`
	Limit     int                `json:"limit"`
	Offset    int                `json:"offset"`
}

// QuestionResponse returns a single question
type QuestionResponse struct {
	ID             uint            `json:"id"`
	QuestionType   string          `json:"question_type"`
	Subject        string          `json:"subject"`
	Difficulty     int             `json:"difficulty"`
	Content        QuestionContent `json:"content"`
	Prompt         string          `json:"prompt"`
	Instructions   string          `json:"instructions"`
	Points         int             `json:"points"`
	TimeLimit      int             `json:"time_limit"`
	Tags           string          `json:"tags"`
}

// QuestionTypeResponse returns question type info
type QuestionTypeResponse struct {
	ID             uint   `json:"id"`
	TypeCode       string `json:"type_code"`
	TypeName       string `json:"type_name"`
	Description    string `json:"description"`
	RenderTemplate string `json:"render_template"`
}

// SubjectResponse returns subject info
type SubjectResponse struct {
	ID          uint   `json:"id"`
	Code        string `json:"code"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Icon        string `json:"icon"`
	Color       string `json:"color"`
	SortOrder   int    `json:"sort_order"`
}

// DifficultyLevelResponse returns difficulty level info
type DifficultyLevelResponse struct {
	ID          uint   `json:"id"`
	Level       int    `json:"level"`
	Name        string `json:"name"`
	Description string `json:"description"`
	MinAge      int    `json:"min_age"`
	MaxAge      int    `json:"max_age"`
}
