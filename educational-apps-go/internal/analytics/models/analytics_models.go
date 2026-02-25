package models

import (
	"time"
)

// ========== GAMIFICATION MODELS ==========

// UserXP represents user experience points
type UserXP struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	UserID       uint      `gorm:"unique;not null" json:"user_id"`
	CurrentXP    int       `gorm:"default:0" json:"current_xp"`
	TotalXP      int       `gorm:"default:0" json:"total_xp"`
	Level        int       `gorm:"default:1" json:"level"`
	LastXPUpdate time.Time `json:"last_xp_update"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

// XPLog records XP awards for tracking
type XPLog struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	UserID    uint      `gorm:"index" json:"user_id"`
	Amount    int       `json:"amount"`
	Source    string    `json:"source"` // "math", "reading", "comprehension", etc.
	Reason    string    `json:"reason"` // "correct_answer", "perfect_score", etc.
	CreatedAt time.Time `json:"created_at"`
}

// UserStreak tracks consecutive activity days
type UserStreak struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	UserID         uint      `gorm:"unique;not null" json:"user_id"`
	CurrentStreak  int       `gorm:"default:0" json:"current_streak"`
	LongestStreak  int       `gorm:"default:0" json:"longest_streak"`
	LastActivityDate time.Time `json:"last_activity_date"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// Achievement represents a badge or milestone
type Achievement struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	Slug        string    `gorm:"unique;not null" json:"slug"`
	Name        string    `gorm:"not null" json:"name"`
	Description string    `json:"description"`
	Icon        string    `json:"icon"` // emoji or icon code
	XPReward    int       `gorm:"default:0" json:"xp_reward"`
	Category    string    `json:"category"` // "milestone", "streak", "perfection", etc.
	CreatedAt   time.Time `json:"created_at"`
}

// UserAchievement tracks which achievements a user has unlocked
type UserAchievement struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	UserID        uint      `gorm:"index" json:"user_id"`
	AchievementID uint      `json:"achievement_id"`
	Achievement   *Achievement `json:"achievement,omitempty"`
	UnlockedAt    time.Time `json:"unlocked_at"`
	CreatedAt     time.Time `json:"created_at"`
}

// ========== ANALYTICS MODELS ==========

// UserProfile aggregates user data across all apps
type UserProfile struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	UserID           uint      `gorm:"unique;not null" json:"user_id"`
	Username         string    `json:"username"`
	DisplayName      string    `json:"display_name"`
	TotalPracticeTime int      `gorm:"default:0" json:"total_practice_time"` // seconds
	LastActive       time.Time `json:"last_active"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
}

// AppProgress tracks per-app statistics
type AppProgress struct {
	ID                  uint      `gorm:"primaryKey" json:"id"`
	UserID              uint      `gorm:"index" json:"user_id"`
	App                 string    `gorm:"index;not null" json:"app"` // "math", "reading", "comprehension"
	ActivitiesCompleted int       `gorm:"default:0" json:"activities_completed"`
	BestScore           float64   `gorm:"default:0" json:"best_score"`
	AverageScore        float64   `gorm:"default:0" json:"average_score"`
	TotalTimeSeconds    int       `gorm:"default:0" json:"total_time_seconds"`
	TotalCorrect        int       `gorm:"default:0" json:"total_correct"`
	TotalAttempts       int       `gorm:"default:0" json:"total_attempts"`
	Accuracy            float64   `gorm:"default:0" json:"accuracy"`
	UpdatedAt           time.Time `json:"updated_at"`
	CreatedAt           time.Time `json:"created_at"`
}

// SubjectMastery tracks user's mastery per subject
type SubjectMastery struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	UserID         uint      `gorm:"index" json:"user_id"`
	App            string    `gorm:"index" json:"app"`
	Subject        string    `gorm:"index" json:"subject"`
	MasteryLevel   float64   `gorm:"default:0" json:"mastery_level"` // 0-100
	QuestionsAttempted int   `gorm:"default:0" json:"questions_attempted"`
	QuestionsCorrect   int   `gorm:"default:0" json:"questions_correct"`
	LastPracticed  time.Time `json:"last_practiced"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// LearningGoal represents a user's learning objective
type LearningGoal struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	UserID     uint      `gorm:"index;not null" json:"user_id"`
	Title      string    `gorm:"not null" json:"title"`
	Description string   `json:"description"`
	App        string    `json:"app"` // "all", "math", "reading", etc.
	TargetValue int      `json:"target_value"`
	TargetDate time.Time `json:"target_date"`
	Status     string    `json:"status"` // "active", "completed", "failed"
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

// UserNote stores admin notes about students
type UserNote struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	UserID    uint      `gorm:"index;not null" json:"user_id"`
	Content   string    `json:"content"`
	Category  string    `json:"category"` // "general", "behavior", "progress", "concern"
	CreatedBy string    `json:"created_by"` // admin username
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// ========== LEADERBOARD MODELS ==========

// LeaderboardEntry represents a position in a leaderboard
type LeaderboardEntry struct {
	Rank       int       `json:"rank"`
	UserID     uint      `json:"user_id"`
	Username   string    `json:"username"`
	Value      int       `json:"value"` // XP or other metric
	SecondValue float64  `json:"second_value,omitempty"` // accuracy, WPM, etc.
	UpdatedAt  time.Time `json:"updated_at"`
}

// ========== REQUEST/RESPONSE TYPES ==========

// AwardXPRequest is the request to award XP to a user
type AwardXPRequest struct {
	UserID uint   `json:"user_id" binding:"required,gt=0"`
	Amount int    `json:"amount" binding:"required,gt=0"`
	Source string `json:"source" binding:"required"` // app name
	Reason string `json:"reason" binding:"required"` // reason for XP
}

// XPCheckInRequest is the request for daily streak check-in
type XPCheckInRequest struct {
	UserID uint `json:"user_id" binding:"required,gt=0"`
}

// GamificationProfileResponse returns user's gamification status
type GamificationProfileResponse struct {
	UserID        uint                      `json:"user_id"`
	Username      string                    `json:"username"`
	Level         int                       `json:"level"`
	CurrentXP     int                       `json:"current_xp"`
	TotalXP       int                       `json:"total_xp"`
	XPToNextLevel int                       `json:"xp_to_next_level"`
	CurrentStreak int                       `json:"current_streak"`
	LongestStreak int                       `json:"longest_streak"`
	Achievements  []UserAchievementResponse `json:"achievements"`
}

// UserAchievementResponse returns achievement data
type UserAchievementResponse struct {
	ID          uint      `json:"id"`
	Slug        string    `json:"slug"`
	Name        string    `json:"name"`
	Icon        string    `json:"icon"`
	Category    string    `json:"category"`
	UnlockedAt  time.Time `json:"unlocked_at"`
}

// UserProfileResponse returns comprehensive user profile
type UserProfileResponse struct {
	UserID          uint                    `json:"user_id"`
	Username        string                  `json:"username"`
	DisplayName     string                  `json:"display_name"`
	Level           int                     `json:"level"`
	TotalXP         int                     `json:"total_xp"`
	CurrentStreak   int                     `json:"current_streak"`
	LongestStreak   int                     `json:"longest_streak"`
	TotalPracticeTime int                   `json:"total_practice_time"`
	LastActive      time.Time               `json:"last_active"`
	AppProgress     map[string]AppProgressResponse `json:"app_progress"`
	Achievements    []UserAchievementResponse     `json:"achievements"`
}

// AppProgressResponse returns per-app statistics
type AppProgressResponse struct {
	App                 string  `json:"app"`
	ActivitiesCompleted int     `json:"activities_completed"`
	BestScore           float64 `json:"best_score"`
	AverageScore        float64 `json:"average_score"`
	TotalTimeSeconds    int     `json:"total_time_seconds"`
	Accuracy            float64 `json:"accuracy"`
}

// LeaderboardResponse returns ranked users
type LeaderboardResponse struct {
	Period  string                `json:"period"` // "all", "weekly", "daily"
	Entries []*LeaderboardEntry   `json:"entries"`
	UpdatedAt time.Time           `json:"updated_at"`
}

// DashboardResponse returns user's dashboard summary
type DashboardResponse struct {
	Profile       UserProfileResponse      `json:"profile"`
	Leaderboard   []*LeaderboardEntry      `json:"leaderboard,omitempty"`
	RecentActivity []*ActivityLogEntry      `json:"recent_activity,omitempty"`
	Goals         []*LearningGoal          `json:"goals,omitempty"`
	Recommendations []string               `json:"recommendations,omitempty"`
}

// ActivityLogEntry tracks user actions
type ActivityLogEntry struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	UserID    uint      `gorm:"index" json:"user_id"`
	App       string    `json:"app"`
	EventType string    `json:"event_type"` // "completed_question", "achieved_badge", etc.
	Details   string    `json:"details"`
	CreatedAt time.Time `json:"created_at"`
}

// XPLevelThreshold defines XP requirements for each level
type XPLevelThreshold struct {
	Level       int `json:"level"`
	RequiredXP  int `json:"required_xp"`
}

// StreakBonus defines XP bonuses for consecutive days
type StreakBonus struct {
	Days int `json:"days"`
	Bonus int `json:"bonus"`
}
