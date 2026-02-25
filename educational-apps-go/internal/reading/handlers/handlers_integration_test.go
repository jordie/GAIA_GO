package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/middleware"
	"github.com/architect/educational-apps/internal/reading/models"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"
)

func setupTestRouter(t *testing.T) *gin.Engine {
	database.DB = setupTestDB(t)
	router := gin.New()

	// Register middleware
	router.Use(middleware.AuthRequired())

	// Register routes
	readingGroup := router.Group("/api/reading")
	readingGroup.GET("/words", GetWords)
	readingGroup.POST("/results", SaveReadingResult)
	readingGroup.GET("/stats", GetReadingStats)
	readingGroup.GET("/weaknesses", GetWeaknesses)
	readingGroup.GET("/practice-plan", GetPracticePlan)
	readingGroup.GET("/learning-profile", GetLearningProfile)
	readingGroup.GET("/quizzes", ListQuizzes)
	readingGroup.POST("/quizzes", CreateQuiz)
	readingGroup.GET("/quizzes/:id", GetQuiz)
	readingGroup.POST("/quizzes/:id/submit", SubmitQuiz)
	readingGroup.GET("/quizzes/attempts/:attempt_id", GetQuizResults)

	return router
}

func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Migrate all models
	db.AutoMigrate(
		&models.User{},
		&models.Word{},
		&models.ReadingResult{},
		&models.WordPerformance{},
		&models.Quiz{},
		&models.Question{},
		&models.QuizAttempt{},
		&models.LearningProfile{},
		&models.ReadingStreak{},
	)

	// Create test user
	user := &models.User{ID: 1, Username: "testuser"}
	db.Create(user)

	// Create test words
	words := []*models.Word{
		{Word: "the"},
		{Word: "and"},
		{Word: "reading"},
		{Word: "practice"},
	}
	for _, w := range words {
		db.Create(w)
	}

	return db
}

func TestGetWords(t *testing.T) {
	router := setupTestRouter(t)

	req := httptest.NewRequest("GET", "/api/reading/words", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.WordListResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Greater(t, response.Total, 0)
}

func TestSaveReadingResult(t *testing.T) {
	router := setupTestRouter(t)

	request := models.SaveReadingResultRequest{
		ExpectedWords:   []string{"the", "and"},
		RecognizedText:  "the and",
		Accuracy:        100.0,
		WordsCorrect:    2,
		WordsTotal:      2,
		ReadingSpeed:    250.0,
		SessionDuration: 60.0,
	}

	body, _ := json.Marshal(request)
	req := httptest.NewRequest("POST", "/api/reading/results", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 201, w.Code)

	var response models.ReadingResult
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, uint(1), response.UserID)
}

func TestGetReadingStats(t *testing.T) {
	router := setupTestRouter(t)

	req := httptest.NewRequest("GET", "/api/reading/stats", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.ReadingStatsResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, uint(1), response.UserID)
}

func TestGetWeaknesses(t *testing.T) {
	router := setupTestRouter(t)

	req := httptest.NewRequest("GET", "/api/reading/weaknesses", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.WeakAreasResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
}

func TestGetPracticePlan(t *testing.T) {
	router := setupTestRouter(t)

	req := httptest.NewRequest("GET", "/api/reading/practice-plan", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.PracticePlanResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.NotEmpty(t, response.RecommendedLevel)
}

func TestGetLearningProfile(t *testing.T) {
	router := setupTestRouter(t)

	req := httptest.NewRequest("GET", "/api/reading/learning-profile", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.LearningProfile
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, uint(1), response.UserID)
}

func TestListQuizzes(t *testing.T) {
	router := setupTestRouter(t)

	req := httptest.NewRequest("GET", "/api/reading/quizzes", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Contains(t, response, "quizzes")
}

func TestCreateQuiz(t *testing.T) {
	router := setupTestRouter(t)

	request := models.CreateQuizRequest{
		Title:       "Reading Comprehension Quiz",
		Description: "Test your reading skills",
		PassScore:   70,
		Questions: []models.QuestionInput{
			{
				QuestionText:  "What is the color of the sky?",
				QuestionType:  "multiple_choice",
				CorrectAnswer: "a",
				OptionA:       "Blue",
				OptionB:       "Red",
				OptionC:       "Green",
				OptionD:       "Yellow",
			},
		},
	}

	body, _ := json.Marshal(request)
	req := httptest.NewRequest("POST", "/api/reading/quizzes", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 201, w.Code)

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Contains(t, response, "quiz_id")
}

func TestMissingUserID(t *testing.T) {
	router := setupTestRouter(t)

	tests := []struct {
		name   string
		method string
		path   string
	}{
		{"SaveReadingResult no user_id", "POST", "/api/reading/results"},
		{"GetReadingStats no user_id", "GET", "/api/reading/stats"},
		{"GetWeaknesses no user_id", "GET", "/api/reading/weaknesses"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var req *http.Request
			if tt.method == "POST" {
				body, _ := json.Marshal(map[string]interface{}{})
				req = httptest.NewRequest(tt.method, tt.path, bytes.NewBuffer(body))
				req.Header.Set("Content-Type", "application/json")
			} else {
				req = httptest.NewRequest(tt.method, tt.path, nil)
			}

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, 400, w.Code)
		})
	}
}
