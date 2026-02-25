package models

import "time"

// User represents a reading app user
type User struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	Username  string    `gorm:"unique;not null" json:"username"`
	CreatedAt time.Time `json:"created_at"`
	LastActive time.Time `json:"last_active"`
}

// Word represents a vocabulary word for reading practice
type Word struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	Word      string    `gorm:"not null" json:"word"`
	CreatedAt time.Time `json:"created_at"`
}

// ReadingResult tracks a single reading practice session result
type ReadingResult struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	UserID          uint      `gorm:"index" json:"user_id"`
	User            *User     `gorm:"foreignKey:UserID" json:"-"`
	ExpectedWords   string    `gorm:"type:text" json:"expected_words"` // JSON array
	RecognizedText  string    `gorm:"type:text" json:"recognized_text"`
	Accuracy        float64   `json:"accuracy"` // Percentage 0-100
	WordsCorrect    int       `json:"words_correct"`
	WordsTotal      int       `json:"words_total"`
	ReadingSpeed    float64   `json:"reading_speed"` // WPM
	SessionDuration float64   `json:"session_duration"` // Seconds
	CreatedAt       time.Time `json:"created_at"`
}

// WordPerformance tracks mastery of individual words
type WordPerformance struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	Word           string    `gorm:"unique;not null;index" json:"word"`
	CorrectCount   int       `json:"correct_count"`
	IncorrectCount int       `json:"incorrect_count"`
	Mastery        float64   `json:"mastery"` // 0-100
	LastPracticed  time.Time `json:"last_practiced"`
	CreatedAt      time.Time `json:"created_at"`
}

// Quiz represents a reading comprehension quiz
type Quiz struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	Title       string    `gorm:"not null" json:"title"`
	Description string    `json:"description"`
	PassScore   int       `gorm:"default:70" json:"pass_score"`
	Questions   []Question `gorm:"foreignKey:QuizID" json:"questions,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
}

// Question represents a single quiz question
type Question struct {
	ID            uint   `gorm:"primaryKey" json:"id"`
	QuizID        uint   `gorm:"index;not null" json:"quiz_id"`
	QuestionText  string `gorm:"type:text;not null" json:"question_text"`
	QuestionType  string `json:"question_type"` // multiple_choice, true_false, short_answer
	CorrectAnswer string `json:"correct_answer"`
	OptionA       string `json:"option_a"`
	OptionB       string `json:"option_b"`
	OptionC       string `json:"option_c"`
	OptionD       string `json:"option_d"`
	CreatedAt     time.Time `json:"created_at"`
}

// QuizAttempt represents a user's attempt at a quiz
type QuizAttempt struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	QuizID    uint      `gorm:"index;not null" json:"quiz_id"`
	UserID    uint      `gorm:"index;not null" json:"user_id"`
	User      *User     `gorm:"foreignKey:UserID" json:"-"`
	Quiz      *Quiz     `gorm:"foreignKey:QuizID" json:"-"`
	Score     int       `json:"score"`
	Total     int       `json:"total"`
	Percentage int      `json:"percentage"`
	Passed    bool      `json:"passed"`
	Answers   string    `gorm:"type:text" json:"answers"` // JSON mapping
	TakenAt   time.Time `json:"taken_at"`
	CreatedAt time.Time `json:"created_at"`
}

// LearningProfile tracks user's reading preferences and performance patterns
type LearningProfile struct {
	ID                uint      `gorm:"primaryKey" json:"id"`
	UserID            uint      `gorm:"unique;not null" json:"user_id"`
	User              *User     `gorm:"foreignKey:UserID" json:"-"`
	PreferredReadingLevel string `json:"preferred_reading_level"` // beginner, intermediate, advanced
	AverageReadingSpeed float64 `json:"average_reading_speed"`    // WPM
	AverageAccuracy     float64 `json:"average_accuracy"`         // Percentage
	TotalWordsLearned   int     `json:"total_words_learned"`
	TotalQuizzesAttempted int  `json:"total_quizzes_attempted"`
	AverageQuizScore    float64 `json:"average_quiz_score"`
	ProfileUpdated      time.Time `json:"profile_updated"`
	CreatedAt           time.Time `json:"created_at"`
}

// ReadingStreak tracks consecutive successful reading sessions
type ReadingStreak struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	UserID          uint      `gorm:"unique;not null" json:"user_id"`
	User            *User     `gorm:"foreignKey:UserID" json:"-"`
	CurrentStreak   int       `json:"current_streak"`
	LongestStreak   int       `json:"longest_streak"`
	LastPracticed   time.Time `json:"last_practiced"`
	StreakStartDate time.Time `json:"streak_start_date"`
	CreatedAt       time.Time `json:"created_at"`
}

// API Request/Response DTOs

// GetWordsRequest - request to fetch words
type GetWordsRequest struct {
	Limit int `json:"limit" binding:"required,min=1,max=100"`
}

// AddWordRequest - request to add a word
type AddWordRequest struct {
	Word string `json:"word" binding:"required,min=1,max=100"`
}

// AddWordResponse - response after adding a word
type AddWordResponse struct {
	ID        uint      `json:"id"`
	Word      string    `json:"word"`
	CreatedAt time.Time `json:"created_at"`
	Message   string    `json:"message"`
}

// SaveReadingResultRequest - request to save reading practice result
type SaveReadingResultRequest struct {
	ExpectedWords   []string `json:"expected_words" binding:"required"`
	RecognizedText  string   `json:"recognized_text"`
	Accuracy        float64  `json:"accuracy"`
	WordsCorrect    int      `json:"words_correct"`
	WordsTotal      int      `json:"words_total"`
	ReadingSpeed    float64  `json:"reading_speed"`
	SessionDuration float64  `json:"session_duration"`
}

// ReadingStatsResponse - user reading statistics
type ReadingStatsResponse struct {
	UserID                uint                   `json:"user_id"`
	TotalSessions         int                    `json:"total_sessions"`
	AverageAccuracy       float64                `json:"average_accuracy"`
	AverageSpeed          float64                `json:"average_speed"`
	BestAccuracy          float64                `json:"best_accuracy"`
	BestSpeed             float64                `json:"best_speed"`
	WordsMastered         int                    `json:"words_mastered"`
	WordsInProgress       int                    `json:"words_in_progress"`
	RecentSessions        []*ReadingResult       `json:"recent_sessions"`
	LearningProfile       *LearningProfile       `json:"learning_profile"`
	WeakWords             []*WordPerformance     `json:"weak_words"`
	StrengthWords         []*WordPerformance     `json:"strength_words"`
	CurrentStreak         int                    `json:"current_streak"`
	LongestStreak         int                    `json:"longest_streak"`
}

// CreateQuizRequest - request to create a quiz
type CreateQuizRequest struct {
	Title       string     `json:"title" binding:"required,min=1,max=255"`
	Description string     `json:"description"`
	PassScore   int        `json:"pass_score" binding:"required,min=0,max=100"`
	Questions   []QuestionInput `json:"questions" binding:"required,dive"`
}

// QuestionInput - question data for quiz creation
type QuestionInput struct {
	QuestionText  string `json:"question_text" binding:"required"`
	QuestionType  string `json:"question_type" binding:"required,oneof=multiple_choice true_false short_answer"`
	CorrectAnswer string `json:"correct_answer" binding:"required"`
	OptionA       string `json:"option_a"`
	OptionB       string `json:"option_b"`
	OptionC       string `json:"option_c"`
	OptionD       string `json:"option_d"`
}

// SubmitQuizRequest - request to submit quiz answers
type SubmitQuizRequest struct {
	Answers map[string]string `json:"answers" binding:"required"`
}

// QuizResultResponse - quiz result after submission
type QuizResultResponse struct {
	AttemptID      uint                    `json:"attempt_id"`
	QuizID         uint                    `json:"quiz_id"`
	Score          int                     `json:"score"`
	Total          int                     `json:"total"`
	Percentage     int                     `json:"percentage"`
	Passed         bool                    `json:"passed"`
	QuestionResults []*QuestionResult      `json:"question_results"`
}

// QuestionResult - result for individual question
type QuestionResult struct {
	QuestionID        uint   `json:"question_id"`
	QuestionText      string `json:"question_text"`
	UserAnswer        string `json:"user_answer"`
	CorrectAnswer     string `json:"correct_answer"`
	UserAnswerText    string `json:"user_answer_text"`
	CorrectAnswerText string `json:"correct_answer_text"`
	IsCorrect         bool   `json:"is_correct"`
}

// QuizListResponse - quiz metadata for listing
type QuizListResponse struct {
	ID            uint      `json:"id"`
	Title         string    `json:"title"`
	Description   string    `json:"description"`
	QuestionCount int       `json:"question_count"`
	PassScore     int       `json:"pass_score"`
	CreatedAt     time.Time `json:"created_at"`
}

// QuizDetailResponse - full quiz with questions
type QuizDetailResponse struct {
	ID          uint                   `json:"id"`
	Title       string                 `json:"title"`
	Description string                 `json:"description"`
	PassScore   int                    `json:"pass_score"`
	Questions   []*QuestionDetailResponse `json:"questions"`
	CreatedAt   time.Time              `json:"created_at"`
}

// QuestionDetailResponse - question with options
type QuestionDetailResponse struct {
	ID           uint   `json:"id"`
	QuestionText string `json:"question_text"`
	QuestionType string `json:"question_type"`
	OptionA      string `json:"option_a,omitempty"`
	OptionB      string `json:"option_b,omitempty"`
	OptionC      string `json:"option_c,omitempty"`
	OptionD      string `json:"option_d,omitempty"`
}

// PracticePlanResponse - personalized reading plan
type PracticePlanResponse struct {
	RecommendedLevel string   `json:"recommended_level"`
	FocusWords       []string `json:"focus_words"`
	EstimatedTime    int64    `json:"estimated_time"`
	Rationale        string   `json:"rationale"`
}

// WordListResponse - list of words
type WordListResponse struct {
	Words []*Word `json:"words"`
	Total int     `json:"total"`
}

// WeakAreasResponse - weak areas analysis
type WeakAreasResponse struct {
	WeakWords   []*WordPerformance `json:"weak_words"`
	Suggestions []string           `json:"suggestions"`
}
