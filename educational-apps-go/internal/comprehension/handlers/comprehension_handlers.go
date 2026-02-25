package handlers

import (
	"net/http"
	"strconv"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/comprehension/models"
	"github.com/architect/educational-apps/internal/comprehension/repository"
	"github.com/architect/educational-apps/internal/comprehension/services"
	"github.com/gin-gonic/gin"
)

// GetQuestionTypes returns all available question types
// GET /api/v1/comprehension/question_types
func GetQuestionTypes(c *gin.Context) {
	types, err := repository.GetQuestionTypes()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	response := make([]models.QuestionTypeResponse, len(types))
	for i, t := range types {
		response[i] = models.QuestionTypeResponse{
			ID:             t.ID,
			TypeCode:       t.TypeCode,
			TypeName:       t.TypeName,
			Description:    t.Description,
			RenderTemplate: t.RenderTemplate,
		}
	}

	c.JSON(http.StatusOK, response)
}

// GetSubjects returns all subjects
// GET /api/v1/comprehension/subjects
func GetSubjects(c *gin.Context) {
	subjects, err := repository.GetSubjects()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	response := make([]models.SubjectResponse, len(subjects))
	for i, s := range subjects {
		response[i] = models.SubjectResponse{
			ID:          s.ID,
			Code:        s.Code,
			Name:        s.Name,
			Description: s.Description,
			Icon:        s.Icon,
			Color:       s.Color,
			SortOrder:   s.SortOrder,
		}
	}

	c.JSON(http.StatusOK, response)
}

// GetDifficultyLevels returns all difficulty levels
// GET /api/v1/comprehension/difficulty_levels
func GetDifficultyLevels(c *gin.Context) {
	levels, err := repository.GetDifficultyLevels()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	response := make([]models.DifficultyLevelResponse, len(levels))
	for i, l := range levels {
		response[i] = models.DifficultyLevelResponse{
			ID:          l.ID,
			Level:       l.Level,
			Name:        l.Name,
			Description: l.Description,
			MinAge:      l.MinAge,
			MaxAge:      l.MaxAge,
		}
	}

	c.JSON(http.StatusOK, response)
}

// ListQuestions returns paginated questions
// GET /api/v1/comprehension/questions?type=word_tap&subject=grammar&difficulty=1&limit=10&offset=0
func ListQuestions(c *gin.Context) {
	// Parse query parameters
	limit := 10
	if l, err := strconv.Atoi(c.DefaultQuery("limit", "10")); err == nil && l > 0 && l <= 100 {
		limit = l
	}

	offset := 0
	if o, err := strconv.Atoi(c.DefaultQuery("offset", "0")); err == nil && o >= 0 {
		offset = o
	}

	// Build filters
	filters := make(map[string]interface{})
	if qtype := c.Query("type"); qtype != "" {
		filters["question_type"] = qtype
	}
	if subject := c.Query("subject"); subject != "" {
		filters["subject"] = subject
	}
	if difficulty := c.Query("difficulty"); difficulty != "" {
		if d, err := strconv.Atoi(difficulty); err == nil {
			filters["difficulty"] = d
		}
	}

	// Get questions
	questions, total, err := repository.GetQuestions(filters, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Convert to response format
	response := make([]models.QuestionResponse, len(questions))
	for i, q := range questions {
		response[i] = models.QuestionResponse{
			ID:           q.ID,
			QuestionType: q.QuestionType,
			Subject:      q.Subject,
			Difficulty:   q.Difficulty,
			Content:      q.Content,
			Prompt:       q.Prompt,
			Instructions: q.Instructions,
			Points:       q.Points,
			TimeLimit:    q.TimeLimit,
			Tags:         q.Tags,
		}
	}

	c.JSON(http.StatusOK, models.QuestionsListResponse{
		Questions: response,
		Total:     total,
		Limit:     limit,
		Offset:    offset,
	})
}

// GetQuestion returns a single question by ID
// GET /api/v1/comprehension/questions/:id
func GetQuestion(c *gin.Context) {
	id, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid question id"})
		return
	}

	question, err := repository.GetQuestion(uint(id))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if question == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "question not found"})
		return
	}

	response := models.QuestionResponse{
		ID:           question.ID,
		QuestionType: question.QuestionType,
		Subject:      question.Subject,
		Difficulty:   question.Difficulty,
		Content:      question.Content,
		Prompt:       question.Prompt,
		Instructions: question.Instructions,
		Points:       question.Points,
		TimeLimit:    question.TimeLimit,
		Tags:         question.Tags,
	}

	c.JSON(http.StatusOK, response)
}

// CheckAnswer validates an answer
// POST /api/v1/comprehension/check
func CheckAnswer(c *gin.Context) {
	var req models.CheckAnswerRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Get user ID from context (set by auth middleware)
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	// Check answer
	response, err := services.CheckAnswer(userID, req)
	if err != nil {
		statusCode := http.StatusInternalServerError
		if appErr, ok := err.(*errors.AppError); ok {
			statusCode = appErr.Status
		}
		c.JSON(statusCode, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, response)
}

// SaveProgress saves user progress (legacy endpoint - now handled by CheckAnswer)
// POST /api/v1/comprehension/save_progress
func SaveProgress(c *gin.Context) {
	var req models.SaveProgressRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Get user ID from context
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	// Get question to extract metadata
	question, err := repository.GetQuestion(req.QuestionID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if question == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "question not found"})
		return
	}

	// Save progress
	progress := &models.UserProgress{
		UserID:       userID,
		QuestionID:   req.QuestionID,
		QuestionType: question.QuestionType,
		Subject:      question.Subject,
		Difficulty:   question.Difficulty,
		Correct:      req.Correct,
		Score:        req.Score,
		MaxScore:     req.MaxScore,
		TimeTaken:    req.TimeTaken,
		UserAnswer:   req.UserAnswer,
	}

	progressID, err := repository.SaveUserProgress(progress)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.UserProgressResponse{
		ID:         progressID,
		QuestionID: req.QuestionID,
		Correct:    req.Correct,
		Score:      req.Score,
		MaxScore:   req.MaxScore,
		TimeTaken:  req.TimeTaken,
	})
}

// GetStats returns user statistics
// GET /api/v1/comprehension/stats?subject=grammar
func GetStats(c *gin.Context) {
	// Get user ID from context
	userIDInterface, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not authenticated"})
		return
	}

	userID, ok := userIDInterface.(uint)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user id"})
		return
	}

	// Get all stats or specific subject
	subject := c.Query("subject")

	if subject != "" {
		// Get stats for specific subject
		stats, err := services.GetUserStats(userID, subject)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, stats)
	} else {
		// Get stats for all subjects
		allStats, err := repository.GetUserAllStats(userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		response := make([]models.UserStatsResponse, len(allStats))
		for i, stats := range allStats {
			response[i] = models.UserStatsResponse{
				UserID:             stats.UserID,
				Subject:            stats.Subject,
				QuestionsAttempted: stats.QuestionsAttempted,
				QuestionsCorrect:   stats.QuestionsCorrect,
				TotalScore:         stats.TotalScore,
				BestStreak:         stats.BestStreak,
				CurrentStreak:      stats.CurrentStreak,
				LastPractice:       stats.LastPractice,
			}

			if stats.QuestionsAttempted > 0 {
				response[i].Accuracy = float64(stats.QuestionsCorrect) / float64(stats.QuestionsAttempted)
				response[i].AverageTimePerQuestion = float64(stats.TotalTime) / float64(stats.QuestionsAttempted)
			}
		}

		c.JSON(http.StatusOK, response)
	}
}

// SeedData initializes database with seed content
// POST /api/v1/comprehension/seed (admin only)
func SeedData(c *gin.Context) {
	// Seed question types
	if err := repository.SeedQuestionTypes(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to seed question types"})
		return
	}

	// Seed subjects
	if err := repository.SeedSubjects(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to seed subjects"})
		return
	}

	// Seed difficulty levels
	if err := repository.SeedDifficultyLevels(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to seed difficulty levels"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "seed data loaded successfully"})
}
