package repository

import (
	"time"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/comprehension/models"
	"gorm.io/gorm/clause"
)

// ========== QUESTION TYPE REPOSITORY ==========

// GetQuestionTypes retrieves all available question types
func GetQuestionTypes() ([]*models.QuestionType, error) {
	var types []*models.QuestionType
	result := database.DB.Find(&types)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch question types", result.Error.Error())
	}
	return types, nil
}

// GetQuestionTypeByCode retrieves a question type by code
func GetQuestionTypeByCode(typeCode string) (*models.QuestionType, error) {
	var qtype models.QuestionType
	result := database.DB.Where("type_code = ?", typeCode).First(&qtype)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch question type", result.Error.Error())
	}
	return &qtype, nil
}

// CreateQuestionType creates a new question type
func CreateQuestionType(qtype *models.QuestionType) error {
	result := database.DB.Create(qtype)
	return result.Error
}

// ========== SUBJECT REPOSITORY ==========

// GetSubjects retrieves all subjects
func GetSubjects() ([]*models.Subject, error) {
	var subjects []*models.Subject
	result := database.DB.Order("sort_order ASC").Find(&subjects)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch subjects", result.Error.Error())
	}
	return subjects, nil
}

// GetSubjectByCode retrieves a subject by code
func GetSubjectByCode(code string) (*models.Subject, error) {
	var subject models.Subject
	result := database.DB.Where("code = ?", code).First(&subject)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch subject", result.Error.Error())
	}
	return &subject, nil
}

// CreateSubject creates a new subject
func CreateSubject(subject *models.Subject) error {
	result := database.DB.Create(subject)
	return result.Error
}

// ========== DIFFICULTY LEVEL REPOSITORY ==========

// GetDifficultyLevels retrieves all difficulty levels
func GetDifficultyLevels() ([]*models.DifficultyLevel, error) {
	var levels []*models.DifficultyLevel
	result := database.DB.Order("level ASC").Find(&levels)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch difficulty levels", result.Error.Error())
	}
	return levels, nil
}

// GetDifficultyLevel retrieves a difficulty level by number
func GetDifficultyLevel(level int) (*models.DifficultyLevel, error) {
	var dl models.DifficultyLevel
	result := database.DB.Where("level = ?", level).First(&dl)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch difficulty level", result.Error.Error())
	}
	return &dl, nil
}

// CreateDifficultyLevel creates a new difficulty level
func CreateDifficultyLevel(level *models.DifficultyLevel) error {
	result := database.DB.Create(level)
	return result.Error
}

// ========== QUESTION REPOSITORY ==========

// GetQuestion retrieves a single question by ID
func GetQuestion(questionID uint) (*models.Question, error) {
	var question models.Question
	result := database.DB.Where("id = ? AND active = ?", questionID, true).First(&question)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch question", result.Error.Error())
	}
	return &question, nil
}

// GetQuestions retrieves paginated questions with filters
func GetQuestions(filters map[string]interface{}, limit, offset int) ([]*models.Question, int64, error) {
	var questions []*models.Question
	var total int64

	query := database.DB.Where("active = ?", true)

	// Apply filters
	if qtype, ok := filters["question_type"]; ok {
		query = query.Where("question_type = ?", qtype)
	}
	if subject, ok := filters["subject"]; ok {
		query = query.Where("subject = ?", subject)
	}
	if difficulty, ok := filters["difficulty"]; ok {
		query = query.Where("difficulty = ?", difficulty)
	}

	// Count total
	result := query.Model(&models.Question{}).Count(&total)
	if result.Error != nil {
		return nil, 0, errors.Internal("failed to count questions", result.Error.Error())
	}

	// Fetch paginated results
	result = query.Limit(limit).Offset(offset).Find(&questions)
	if result.Error != nil {
		return nil, 0, errors.Internal("failed to fetch questions", result.Error.Error())
	}

	return questions, total, nil
}

// GetQuestionsBySubjectAndDifficulty retrieves questions for a specific subject/difficulty
func GetQuestionsBySubjectAndDifficulty(subject string, difficulty int, limit int) ([]*models.Question, error) {
	var questions []*models.Question
	result := database.DB.
		Where("subject = ? AND difficulty = ? AND active = ?", subject, difficulty, true).
		Limit(limit).
		Find(&questions)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch questions", result.Error.Error())
	}
	return questions, nil
}

// CreateQuestion creates a new question
func CreateQuestion(question *models.Question) (uint, error) {
	result := database.DB.Create(question)
	if result.Error != nil {
		return 0, errors.Internal("failed to create question", result.Error.Error())
	}
	return question.ID, nil
}

// ========== USER PROGRESS REPOSITORY ==========

// GetUserProgress retrieves a user's progress for a specific question
func GetUserProgress(userID, questionID uint) (*models.UserProgress, error) {
	var progress models.UserProgress
	result := database.DB.Where("user_id = ? AND question_id = ?", userID, questionID).First(&progress)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch user progress", result.Error.Error())
	}
	return &progress, nil
}

// GetUserProgressBySubject retrieves user's progress for a subject
func GetUserProgressBySubject(userID uint, subject string, limit int) ([]*models.UserProgress, error) {
	var progress []*models.UserProgress
	result := database.DB.
		Where("user_id = ? AND subject = ?", userID, subject).
		Order("completed_at DESC").
		Limit(limit).
		Find(&progress)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch user progress", result.Error.Error())
	}
	return progress, nil
}

// SaveUserProgress saves or updates user progress
func SaveUserProgress(progress *models.UserProgress) (uint, error) {
	progress.CompletedAt = time.Now()
	result := database.DB.Create(progress)
	if result.Error != nil {
		return 0, errors.Internal("failed to save progress", result.Error.Error())
	}
	return progress.ID, nil
}

// GetUserRecentProgress retrieves user's recent progress
func GetUserRecentProgress(userID uint, limit int) ([]*models.UserProgress, error) {
	var progress []*models.UserProgress
	result := database.DB.
		Where("user_id = ?", userID).
		Order("completed_at DESC").
		Limit(limit).
		Find(&progress)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch recent progress", result.Error.Error())
	}
	return progress, nil
}

// ========== USER STATS REPOSITORY ==========

// GetUserStats retrieves statistics for a user in a subject
func GetUserStats(userID uint, subject string) (*models.UserStats, error) {
	var stats models.UserStats
	result := database.DB.Where("user_id = ? AND subject = ?", userID, subject).First(&stats)
	if result.Error != nil {
		// Return empty stats if not found (not an error for new users)
		return &models.UserStats{
			UserID:    userID,
			Subject:   subject,
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}, nil
	}
	return &stats, nil
}

// GetUserAllStats retrieves all statistics for a user
func GetUserAllStats(userID uint) ([]*models.UserStats, error) {
	var stats []*models.UserStats
	result := database.DB.Where("user_id = ?", userID).Find(&stats)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch user stats", result.Error.Error())
	}
	return stats, nil
}

// UpdateUserStats updates or creates user statistics
func UpdateUserStats(stats *models.UserStats) error {
	stats.UpdatedAt = time.Now()
	result := database.DB.
		Where("user_id = ? AND subject = ?", stats.UserID, stats.Subject).
		Save(stats)
	if result.Error != nil {
		return errors.Internal("failed to update stats", result.Error.Error())
	}
	return nil
}

// UpsertUserStats creates or updates user statistics
func UpsertUserStats(stats *models.UserStats) error {
	stats.UpdatedAt = time.Now()
	result := database.DB.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "user_id"}, {Name: "subject"}},
		DoUpdates: clause.AssignmentColumns([]string{"questions_attempted", "questions_correct", "total_score", "best_streak", "current_streak", "total_time", "last_practice", "updated_at"}),
	}).Create(stats)
	if result.Error != nil {
		return errors.Internal("failed to upsert stats", result.Error.Error())
	}
	return nil
}

// ========== USER REPOSITORY ==========

// GetOrCreateUser gets or creates a user
func GetOrCreateUser(username string) (uint, error) {
	user := &models.User{Username: username, LastActive: time.Now()}
	result := database.DB.FirstOrCreate(user, models.User{Username: username})
	if result.Error != nil {
		return 0, errors.Internal("failed to get/create user", result.Error.Error())
	}
	return user.ID, nil
}

// UpdateUserActivity updates user's last active time
func UpdateUserActivity(userID uint) error {
	result := database.DB.Model(&models.User{}).Where("id = ?", userID).Update("last_active", time.Now())
	if result.Error != nil {
		return errors.Internal("failed to update user activity", result.Error.Error())
	}
	return nil
}

// ========== SEED DATA ==========

// SeedQuestionTypes seeds initial question types
func SeedQuestionTypes() error {
	types := []models.QuestionType{
		{TypeCode: "word_tap", TypeName: "Word Tap", Description: "Tap words matching a category"},
		{TypeCode: "fill_blank", TypeName: "Fill Blank", Description: "Complete the sentence"},
		{TypeCode: "multiple_choice", TypeName: "Multiple Choice", Description: "Select the correct answer"},
		{TypeCode: "text_entry", TypeName: "Text Entry", Description: "Type your answer"},
		{TypeCode: "analogy", TypeName: "Analogy", Description: "Complete the analogy"},
		{TypeCode: "sentence_order", TypeName: "Sentence Order", Description: "Arrange words in order"},
		{TypeCode: "true_false", TypeName: "True/False", Description: "Determine if statement is true"},
		{TypeCode: "matching", TypeName: "Matching", Description: "Match items from columns"},
	}

	for _, t := range types {
		result := database.DB.FirstOrCreate(&t, models.QuestionType{TypeCode: t.TypeCode})
		if result.Error != nil {
			return result.Error
		}
	}
	return nil
}

// SeedSubjects seeds initial subjects
func SeedSubjects() error {
	subjects := []models.Subject{
		{Code: "grammar", Name: "Grammar", Icon: "📝", Color: "#FF6B6B", SortOrder: 1},
		{Code: "vocabulary", Name: "Vocabulary", Icon: "📚", Color: "#4ECDC4", SortOrder: 2},
		{Code: "comprehension", Name: "Reading Comprehension", Icon: "👁️", Color: "#45B7D1", SortOrder: 3},
		{Code: "analogies", Name: "Analogies", Icon: "🔗", Color: "#F7DC6F", SortOrder: 4},
		{Code: "science", Name: "Science", Icon: "🔬", Color: "#BB8FCE", SortOrder: 5},
		{Code: "social_studies", Name: "Social Studies", Icon: "🌍", Color: "#85C1E2", SortOrder: 6},
		{Code: "current_events", Name: "Current Events", Icon: "📰", Color: "#F8B88B", SortOrder: 7},
		{Code: "math_word_problems", Name: "Math Word Problems", Icon: "🧮", Color: "#52C41A", SortOrder: 8},
	}

	for _, s := range subjects {
		result := database.DB.FirstOrCreate(&s, models.Subject{Code: s.Code})
		if result.Error != nil {
			return result.Error
		}
	}
	return nil
}

// SeedDifficultyLevels seeds initial difficulty levels
func SeedDifficultyLevels() error {
	levels := []models.DifficultyLevel{
		{Level: 1, Name: "Beginner", Description: "Word Types", MinAge: 6, MaxAge: 8},
		{Level: 2, Name: "Elementary", Description: "Sentences", MinAge: 8, MaxAge: 10},
		{Level: 3, Name: "Intermediate", Description: "Vocabulary", MinAge: 10, MaxAge: 12},
		{Level: 4, Name: "Advanced", Description: "Paragraphs", MinAge: 12, MaxAge: 14},
		{Level: 5, Name: "Expert", Description: "Critical Thinking", MinAge: 14, MaxAge: 18},
		{Level: 6, Name: "Master", Description: "Passage Analysis", MinAge: 14, MaxAge: 18},
	}

	for _, l := range levels {
		result := database.DB.FirstOrCreate(&l, models.DifficultyLevel{Level: l.Level})
		if result.Error != nil {
			return result.Error
		}
	}
	return nil
}
