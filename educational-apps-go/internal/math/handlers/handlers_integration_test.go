package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/math/models"
	"github.com/architect/educational-apps/internal/math/repository"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"
)

func setupTestRouter(t *testing.T) *gin.Engine {
	database.DB = setupTestDB(t)
	router := gin.New()

	// Register routes
	mathGroup := router.Group("/api/math")
	mathGroup.POST("/problems/generate", GenerateProblem)
	mathGroup.POST("/problems/check", CheckAnswer)
	mathGroup.POST("/sessions/save", SaveSession)
	mathGroup.GET("/stats", GetStats)
	mathGroup.GET("/weaknesses", GetWeaknesses)
	mathGroup.GET("/practice-plan", GetPracticePlan)
	mathGroup.GET("/learning-profile", GetLearningProfile)

	return router
}

func setupTestDB(t *testing.T) *gorm.DB {
	// For testing, we'll use an in-memory SQLite database
	db, err := gorm.Open("sqlite", ":memory:")
	require.NoError(t, err)

	// Migrate all models
	db.AutoMigrate(
		&models.User{},
		&models.MathProblem{},
		&models.SessionResult{},
		&models.QuestionHistory{},
		&models.Mistake{},
		&models.Mastery{},
		&models.LearningProfile{},
		&models.PerformancePattern{},
		&models.RepetitionSchedule{},
	)

	// Create test user
	user := &models.User{ID: 1, Username: "testuser"}
	db.Create(user)

	return db
}

func TestGenerateProblem(t *testing.T) {
	router := setupTestRouter(t)

	tests := []struct {
		name           string
		request        models.GenerateProblemRequest
		expectedStatus int
		shouldHaveHint bool
	}{
		{
			name: "generate addition problem",
			request: models.GenerateProblemRequest{
				Mode:       "addition",
				Difficulty: "easy",
			},
			expectedStatus: 200,
			shouldHaveHint: true,
		},
		{
			name: "generate multiplication problem",
			request: models.GenerateProblemRequest{
				Mode:       "multiplication",
				Difficulty: "medium",
			},
			expectedStatus: 200,
			shouldHaveHint: true,
		},
		{
			name: "default to addition if mode empty",
			request: models.GenerateProblemRequest{
				Difficulty: "easy",
			},
			expectedStatus: 200,
			shouldHaveHint: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			body, _ := json.Marshal(tt.request)
			req := httptest.NewRequest("POST", "/api/math/problems/generate", bytes.NewBuffer(body))
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("user_id", "1")

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)

			var response models.GenerateProblemResponse
			err := json.Unmarshal(w.Body.Bytes(), &response)
			assert.NoError(t, err)
			assert.NotEmpty(t, response.Question)
			assert.NotEmpty(t, response.Answer)
			assert.NotEmpty(t, response.FactFamily)
			if tt.shouldHaveHint {
				assert.NotEmpty(t, response.Hint)
			}
		})
	}
}

func TestCheckAnswer(t *testing.T) {
	router := setupTestRouter(t)

	tests := []struct {
		name           string
		request        models.CheckAnswerRequest
		expectedStatus int
		expectCorrect  bool
	}{
		{
			name: "correct answer",
			request: models.CheckAnswerRequest{
				Question:      "2+3",
				UserAnswer:    "5",
				CorrectAnswer: "5",
				TimeTaken:     1.5,
				FactFamily:    "plus_one",
				Mode:          "addition",
			},
			expectedStatus: 200,
			expectCorrect:  true,
		},
		{
			name: "incorrect answer",
			request: models.CheckAnswerRequest{
				Question:      "2+3",
				UserAnswer:    "4",
				CorrectAnswer: "5",
				TimeTaken:     2.0,
				FactFamily:    "plus_one",
				Mode:          "addition",
			},
			expectedStatus: 200,
			expectCorrect:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			body, _ := json.Marshal(tt.request)
			req := httptest.NewRequest("POST", "/api/math/problems/check", bytes.NewBuffer(body))
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("user_id", "1")

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)

			var response models.CheckAnswerResponse
			err := json.Unmarshal(w.Body.Bytes(), &response)
			assert.NoError(t, err)
			assert.Equal(t, tt.expectCorrect, response.IsCorrect)
			assert.NotEmpty(t, response.Explanation)
		})
	}
}

func TestSaveSession(t *testing.T) {
	router := setupTestRouter(t)

	request := models.SaveSessionRequest{
		Mode:            "addition",
		Difficulty:      "easy",
		TotalQuestions:  10,
		CorrectAnswers:  8,
		TotalTime:       45.5,
	}

	body, _ := json.Marshal(request)
	req := httptest.NewRequest("POST", "/api/math/sessions/save", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response["success"].(bool))
}

func TestGetStats(t *testing.T) {
	router := setupTestRouter(t)

	// Create test data
	session := &models.SessionResult{
		UserID:         1,
		Mode:           "addition",
		Difficulty:     "easy",
		TotalQuestions: 10,
		CorrectAnswers: 8,
		TotalTime:      45.5,
		AverageTime:    4.55,
		Accuracy:       80.0,
	}
	database.DB.Create(session)

	req := httptest.NewRequest("GET", "/api/math/stats", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.SessionStatistics
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, uint(1), response.UserID)
	assert.GreaterOrEqual(t, response.TotalSessions, 0)
}

func TestGetWeaknesses(t *testing.T) {
	router := setupTestRouter(t)

	// Create test mistake
	mistake := &models.Mistake{
		UserID:        1,
		Question:      "7+8",
		CorrectAnswer: "15",
		UserAnswer:    "14",
		Mode:          "addition",
		FactFamily:    "plus_one",
		ErrorCount:    2,
	}
	database.DB.Create(mistake)

	req := httptest.NewRequest("GET", "/api/math/weaknesses?mode=addition", nil)
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

	// Create test session for statistics
	session := &models.SessionResult{
		UserID:         1,
		Mode:           "addition",
		Difficulty:     "easy",
		TotalQuestions: 5,
		CorrectAnswers: 5,
		TotalTime:      20.0,
		AverageTime:    4.0,
		Accuracy:       100.0,
	}
	database.DB.Create(session)

	req := httptest.NewRequest("GET", "/api/math/practice-plan", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.PracticePlanResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.NotEmpty(t, response.RecommendedMode)
	assert.GreaterOrEqual(t, response.EstimatedTime, int64(0))
}

func TestGetLearningProfile(t *testing.T) {
	router := setupTestRouter(t)

	req := httptest.NewRequest("GET", "/api/math/learning-profile", nil)
	req.Header.Set("user_id", "1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)

	var response models.LearningProfile
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, uint(1), response.UserID)
	assert.NotEmpty(t, response.LearningStyle)
}

func TestMissingUserID(t *testing.T) {
	router := setupTestRouter(t)

	tests := []struct {
		name   string
		method string
		path   string
	}{
		{"CheckAnswer no user_id", "POST", "/api/math/problems/check"},
		{"SaveSession no user_id", "POST", "/api/math/sessions/save"},
		{"GetStats no user_id", "GET", "/api/math/stats"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var req *http.Request
			if tt.method == "POST" {
				body, _ := json.Marshal(map[string]string{})
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
