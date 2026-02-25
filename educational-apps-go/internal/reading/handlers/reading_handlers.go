package handlers

import (
	"strconv"
	"strings"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/reading/models"
	"github.com/architect/educational-apps/internal/reading/services"
	"github.com/gin-gonic/gin"
)

// GetWords retrieves available words for reading practice
func GetWords(c *gin.Context) {
	req := models.GetWordsRequest{
		Limit: 50,
	}

	// Optional query parameter for limit
	if limitStr := c.DefaultQuery("limit", "50"); limitStr != "" {
		if limit, err := strconv.Atoi(limitStr); err == nil && limit > 0 && limit <= 100 {
			req.Limit = limit
		}
	}

	words, err := services.GetWords(req.Limit)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, models.WordListResponse{
		Words: words,
		Total: len(words),
	})
}

// SaveReadingResult saves reading practice session
func SaveReadingResult(c *gin.Context) {
	userIDStr, exists := c.Get("user_id")
	if !exists {
		middleware.JSONErrorResponse(c, nil)
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	var req models.SaveReadingResultRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	result, err := services.SaveReadingResult(uint(userID), req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(201, result)
}

// GetReadingStats retrieves user reading statistics
func GetReadingStats(c *gin.Context) {
	userIDStr, exists := c.Get("user_id")
	if !exists {
		middleware.JSONErrorResponse(c, nil)
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	stats, err := services.GetReadingStats(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, stats)
}

// GetWeaknesses identifies words needing practice
func GetWeaknesses(c *gin.Context) {
	userIDStr, exists := c.Get("user_id")
	if !exists {
		middleware.JSONErrorResponse(c, nil)
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	weakAreas, err := services.GetWeakAreas(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, weakAreas)
}

// GetPracticePlan generates personalized reading plan
func GetPracticePlan(c *gin.Context) {
	userIDStr, exists := c.Get("user_id")
	if !exists {
		middleware.JSONErrorResponse(c, nil)
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	plan, err := services.GeneratePracticePlan(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, plan)
}

// GetLearningProfile retrieves user's learning profile
func GetLearningProfile(c *gin.Context) {
	userIDStr, exists := c.Get("user_id")
	if !exists {
		middleware.JSONErrorResponse(c, nil)
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	profile, err := services.GetOrCreateLearningProfile(uint(userID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, profile)
}

// ListQuizzes retrieves all quizzes
func ListQuizzes(c *gin.Context) {
	quizzes, err := services.ListQuizzes()
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, gin.H{
		"quizzes": quizzes,
		"total":   len(quizzes),
	})
}

// GetQuiz retrieves a specific quiz
func GetQuiz(c *gin.Context) {
	quizIDStr := c.Param("id")
	quizID, err := strconv.ParseUint(quizIDStr, 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	quiz, err := services.GetQuiz(uint(quizID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, quiz)
}

// CreateQuiz creates a new quiz
func CreateQuiz(c *gin.Context) {
	var req models.CreateQuizRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	quizID, err := services.CreateQuiz(req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(201, gin.H{
		"quiz_id": quizID,
		"message": "Quiz created successfully",
	})
}

// SubmitQuiz submits quiz answers and returns results
func SubmitQuiz(c *gin.Context) {
	userIDStr, exists := c.Get("user_id")
	if !exists {
		middleware.JSONErrorResponse(c, nil)
		return
	}

	userID, err := strconv.ParseUint(userIDStr.(string), 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	quizIDStr := c.Param("id")
	quizID, err := strconv.ParseUint(quizIDStr, 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	var req models.SubmitQuizRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	result, err := services.SubmitQuiz(uint(userID), uint(quizID), req)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, result)
}

// GetQuizResults retrieves quiz attempt results
func GetQuizResults(c *gin.Context) {
	attemptIDStr := c.Param("attempt_id")
	attemptID, err := strconv.ParseUint(attemptIDStr, 10, 32)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	result, err := services.GetQuizResults(uint(attemptID))
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(200, result)
}

// AddWord adds a new word to the vocabulary database with comprehensive validation
func AddWord(c *gin.Context) {
	var req models.AddWordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	// Comprehensive input validation
	if validationErr := validateWordInput(req.Word); validationErr != nil {
		middleware.JSONErrorResponse(c, validationErr)
		return
	}

	// Call service layer
	response, err := services.AddWord(req.Word)
	if err != nil {
		middleware.JSONErrorResponse(c, err)
		return
	}

	c.JSON(201, response)
}

// validateWordInput performs comprehensive validation on word input
func validateWordInput(word string) *errors.AppError {
	// Trim whitespace
	word = strings.TrimSpace(word)

	// Check minimum length (after trimming)
	if len(word) == 0 {
		return errors.Validation("word cannot be empty", "word must contain at least one character after trimming whitespace")
	}

	// Check maximum length
	if len(word) > 100 {
		return errors.Validation("word is too long", "word must not exceed 100 characters")
	}

	// Check for invalid characters (only letters, hyphens, and apostrophes allowed)
	for _, ch := range word {
		if !((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch == '-' || ch == '\'' || ch == ' ') {
			return errors.Validation("word contains invalid characters", "word must contain only letters, hyphens, apostrophes, and spaces")
		}
	}

	// Check for SQL injection patterns (additional layer of protection)
	sqlInjectionPatterns := []string{";", "--", "/*", "*/", "xp_", "sp_", "DROP", "DELETE", "INSERT", "UPDATE", "SELECT", "EXEC", "EXECUTE"}
	lowerWord := strings.ToLower(word)
	for _, pattern := range sqlInjectionPatterns {
		if strings.Contains(lowerWord, strings.ToLower(pattern)) && pattern != "-" {
			return errors.Validation("word contains suspicious patterns", "word contains potentially malicious SQL patterns")
		}
	}

	// Check for XSS patterns
	xssPatterns := []string{"<", ">", "{", "}", "[", "]", "javascript:", "onerror=", "onload="}
	for _, pattern := range xssPatterns {
		if strings.Contains(lowerWord, pattern) {
			return errors.Validation("word contains invalid markup", "word cannot contain special markup characters or scripting patterns")
		}
	}

	// Verify word is not purely numeric (educational words should have letters)
	hasLetter := false
	for _, ch := range word {
		if (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') {
			hasLetter = true
			break
		}
	}
	if !hasLetter {
		return errors.Validation("word must contain at least one letter", "word cannot be purely numeric or symbolic")
	}

	return nil
}
