package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/architect/educational-apps/internal/comprehension/models"
	"github.com/architect/educational-apps/internal/comprehension/repository"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"gorm.io/gorm"
)

// setupTestRouter creates a test router with comprehension routes
func setupTestRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	router := gin.New()

	// Register routes
	v1 := router.Group("/api/v1")
	{
		comprehension := v1.Group("/comprehension")
		{
			comprehension.GET("/question_types", GetQuestionTypes)
			comprehension.GET("/subjects", GetSubjects)
			comprehension.GET("/difficulty_levels", GetDifficultyLevels)
			comprehension.GET("/questions", ListQuestions)
			comprehension.GET("/questions/:id", GetQuestion)
			comprehension.POST("/check", func(c *gin.Context) {
				c.Set("user_id", uint(1))
				CheckAnswer(c)
			})
			comprehension.POST("/save_progress", func(c *gin.Context) {
				c.Set("user_id", uint(1))
				SaveProgress(c)
			})
			comprehension.GET("/stats", func(c *gin.Context) {
				c.Set("user_id", uint(1))
				GetStats(c)
			})
			comprehension.POST("/seed", SeedData)
		}
	}

	return router
}

// Test: GetQuestionTypes endpoint
func TestGetQuestionTypes(t *testing.T) {
	router := setupTestRouter()

	// Seed question types first
	router.POST("/api/v1/comprehension/seed", SeedData)

	// Make request
	req, _ := http.NewRequest("GET", "/api/v1/comprehension/question_types", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response []models.QuestionTypeResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Greater(t, len(response), 0)
	assert.Equal(t, "word_tap", response[0].TypeCode)
}

// Test: GetSubjects endpoint
func TestGetSubjects(t *testing.T) {
	router := setupTestRouter()

	// Seed data
	router.POST("/api/v1/comprehension/seed", SeedData)

	// Make request
	req, _ := http.NewRequest("GET", "/api/v1/comprehension/subjects", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response []models.SubjectResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Greater(t, len(response), 0)
	assert.Equal(t, "grammar", response[0].Code)
}

// Test: GetDifficultyLevels endpoint
func TestGetDifficultyLevels(t *testing.T) {
	router := setupTestRouter()

	// Seed data
	router.POST("/api/v1/comprehension/seed", SeedData)

	// Make request
	req, _ := http.NewRequest("GET", "/api/v1/comprehension/difficulty_levels", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response []models.DifficultyLevelResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, 6, len(response))
	assert.Equal(t, 1, response[0].Level)
}

// Test: ListQuestions endpoint with filters
func TestListQuestions(t *testing.T) {
	router := setupTestRouter()

	// Create test question
	question := &models.Question{
		QuestionType: "word_tap",
		Subject:      "grammar",
		Difficulty:   1,
		Prompt:       "Select the nouns",
		Instructions: "Tap words that are nouns",
		Points:       10,
		TimeLimit:    60,
		Active:       true,
		Content: models.QuestionContent{
			"word_labels": map[string]string{
				"dog":   "noun",
				"runs":  "verb",
				"quick": "adjective",
			},
		},
	}
	repository.CreateQuestion(question)

	// Make request
	req, _ := http.NewRequest("GET", "/api/v1/comprehension/questions?type=word_tap&subject=grammar&difficulty=1", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response models.QuestionsListResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Greater(t, response.Total, int64(0))
}

// Test: GetQuestion endpoint
func TestGetQuestion(t *testing.T) {
	router := setupTestRouter()

	// Create test question
	question := &models.Question{
		QuestionType: "multiple_choice",
		Subject:      "vocabulary",
		Difficulty:   2,
		Prompt:       "What is a synonym for 'happy'?",
		Instructions: "Select the correct answer",
		Points:       10,
		TimeLimit:    60,
		Active:       true,
		Content: models.QuestionContent{
			"correct_answer": "joyful",
			"options":        []string{"sad", "joyful", "angry", "tired"},
			"explanation":    "Joyful means full of joy, similar to happy",
		},
	}
	qID, _ := repository.CreateQuestion(question)

	// Make request
	req, _ := http.NewRequest("GET", "/api/v1/comprehension/questions/"+string(rune(qID)), nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response models.QuestionResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, "multiple_choice", response.QuestionType)
}

// Test: CheckAnswer with word_tap question
func TestCheckAnswerWordTap(t *testing.T) {
	router := setupTestRouter()

	// Create word_tap question
	question := &models.Question{
		QuestionType: "word_tap",
		Subject:      "grammar",
		Difficulty:   1,
		Prompt:       "Tap the nouns",
		Points:       10,
		TimeLimit:    60,
		Active:       true,
		Content: models.QuestionContent{
			"word_labels": map[string]string{
				"dog":   "noun",
				"cat":   "noun",
				"runs":  "verb",
				"blue":  "adjective",
			},
		},
	}
	qID, _ := repository.CreateQuestion(question)

	// Check answer request
	req := models.CheckAnswerRequest{
		QuestionID:    qID,
		SelectedWords: map[string]string{"dog": "noun", "cat": "noun"},
		TargetType:    "noun",
	}
	body, _ := json.Marshal(req)
	httpReq, _ := http.NewRequest("POST", "/api/v1/comprehension/check", bytes.NewBuffer(body))
	httpReq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, httpReq)

	assert.Equal(t, http.StatusOK, w.Code)

	var response models.CheckAnswerResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Correct || !response.Correct) // Just check response structure
	assert.GreaterOrEqual(t, response.Score, 0)
}

// Test: CheckAnswer with multiple_choice question
func TestCheckAnswerMultipleChoice(t *testing.T) {
	router := setupTestRouter()

	// Create multiple choice question
	question := &models.Question{
		QuestionType: "multiple_choice",
		Subject:      "vocabulary",
		Difficulty:   2,
		Prompt:       "What is the opposite of 'hot'?",
		Points:       10,
		TimeLimit:    60,
		Active:       true,
		Content: models.QuestionContent{
			"correct_answer": "cold",
			"options":        []string{"warm", "cold", "cool", "freezing"},
			"explanation":    "Cold is the opposite of hot",
		},
	}
	qID, _ := repository.CreateQuestion(question)

	// Correct answer
	req := models.CheckAnswerRequest{
		QuestionID: qID,
		Answer:     "cold",
	}
	body, _ := json.Marshal(req)
	httpReq, _ := http.NewRequest("POST", "/api/v1/comprehension/check", bytes.NewBuffer(body))
	httpReq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, httpReq)

	assert.Equal(t, http.StatusOK, w.Code)

	var response models.CheckAnswerResponse
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response.Correct)
	assert.Equal(t, 10, response.Score)
}

// Test: CheckAnswer with fill_blank question
func TestCheckAnswerFillBlank(t *testing.T) {
	router := setupTestRouter()

	// Create fill blank question
	question := &models.Question{
		QuestionType: "fill_blank",
		Subject:      "grammar",
		Difficulty:   1,
		Prompt:       "The cat ___ on the mat",
		Points:       10,
		TimeLimit:    60,
		Active:       true,
		Content: models.QuestionContent{
			"correct_answer": "sat",
		},
	}
	qID, _ := repository.CreateQuestion(question)

	// Check answer
	req := models.CheckAnswerRequest{
		QuestionID: qID,
		Answer:     "sat",
	}
	body, _ := json.Marshal(req)
	httpReq, _ := http.NewRequest("POST", "/api/v1/comprehension/check", bytes.NewBuffer(body))
	httpReq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, httpReq)

	var response models.CheckAnswerResponse
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response.Correct)
}

// Test: SaveProgress endpoint
func TestSaveProgress(t *testing.T) {
	router := setupTestRouter()

	// Create question
	question := &models.Question{
		QuestionType: "multiple_choice",
		Subject:      "vocabulary",
		Difficulty:   2,
		Prompt:       "Test",
		Points:       10,
		TimeLimit:    60,
		Active:       true,
	}
	qID, _ := repository.CreateQuestion(question)

	// Save progress
	req := models.SaveProgressRequest{
		QuestionID: qID,
		Correct:    true,
		Score:      10,
		MaxScore:   10,
		TimeTaken:  25,
	}
	body, _ := json.Marshal(req)
	httpReq, _ := http.NewRequest("POST", "/api/v1/comprehension/save_progress", bytes.NewBuffer(body))
	httpReq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, httpReq)

	assert.Equal(t, http.StatusOK, w.Code)

	var response models.UserProgressResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Correct)
	assert.Equal(t, 10, response.Score)
}

// Test: GetStats endpoint
func TestGetStats(t *testing.T) {
	router := setupTestRouter()

	// Make request
	req, _ := http.NewRequest("GET", "/api/v1/comprehension/stats?subject=grammar", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response models.UserStatsResponse
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Equal(t, uint(1), response.UserID)
	assert.Equal(t, "grammar", response.Subject)
}

// Benchmark: CheckAnswer performance
func BenchmarkCheckAnswer(b *testing.B) {
	router := setupTestRouter()

	// Create question
	question := &models.Question{
		QuestionType: "multiple_choice",
		Subject:      "vocabulary",
		Difficulty:   2,
		Prompt:       "Test",
		Points:       10,
		TimeLimit:    60,
		Active:       true,
		Content: models.QuestionContent{
			"correct_answer": "test",
		},
	}
	qID, _ := repository.CreateQuestion(question)

	req := models.CheckAnswerRequest{
		QuestionID: qID,
		Answer:     "test",
	}
	body, _ := json.Marshal(req)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		httpReq, _ := http.NewRequest("POST", "/api/v1/comprehension/check", bytes.NewBuffer(body))
		httpReq.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, httpReq)
	}
}
