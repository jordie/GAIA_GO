package routes

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// setupTestDB creates an in-memory SQLite database for testing
func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	require.NoError(t, err)

	// Create tables
	db.AutoMigrate(
		&rate_limiting.Appeal{},
		&rate_limiting.AppealNegotiationMessage{},
		&rate_limiting.Prediction{},
	)

	return db
}

// seedTestData inserts sample data for testing
func seedTestData(t *testing.T, db *gorm.DB) {
	now := time.Now()

	// Create test appeals
	appeals := []rate_limiting.Appeal{
		{
			UserID:       1,
			Status:       rate_limiting.StatusPending,
			Reason:       "Unfair suspension",
			CreatedAt:    now.Add(-72 * time.Hour),
			ReviewedAt:   nil,
			Priority:     1,
		},
		{
			UserID:       2,
			Status:       rate_limiting.StatusApproved,
			Reason:       "Bug in system",
			CreatedAt:    now.Add(-48 * time.Hour),
			ReviewedAt:   &now,
			Priority:     2,
		},
		{
			UserID:       1,
			Status:       rate_limiting.StatusDenied,
			Reason:       "Policy violation",
			CreatedAt:    now.Add(-24 * time.Hour),
			ReviewedAt:   &now,
			Priority:     1,
		},
	}

	for _, appeal := range appeals {
		require.NoError(t, db.Create(&appeal).Error)
	}

	// Create test negotiation messages
	messages := []rate_limiting.AppealNegotiationMessage{
		{
			AppealID:  1,
			SenderID:  1,
			Message:   "I believe I was unfairly suspended",
			CreatedAt: now.Add(-48 * time.Hour),
		},
		{
			AppealID:  1,
			SenderID:  999,
			Message:   "We reviewed your case and found no errors",
			CreatedAt: now.Add(-47 * time.Hour),
		},
	}

	for _, msg := range messages {
		require.NoError(t, db.Create(&msg).Error)
	}

	// Create test predictions
	predictions := []rate_limiting.Prediction{
		{
			AppealID:            1,
			PredictionType:      "approval_probability",
			PredictionValue:     0.75,
			Confidence:          0.85,
			PredictionLatencyMs: 25,
			CreatedAt:           now,
		},
		{
			AppealID:            2,
			PredictionType:      "recovery_timeline",
			PredictionValue:     7,
			Confidence:          0.90,
			PredictionLatencyMs: 22,
			CreatedAt:           now.Add(-24 * time.Hour),
		},
	}

	for _, pred := range predictions {
		require.NoError(t, db.Create(&pred).Error)
	}
}

// TestGetDashboardOverview tests the dashboard overview endpoint
func TestGetDashboardOverview(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}

	handler := getDashboardOverview(db, appealSvc, analyticsSvc)
	router.GET("/dashboard/overview", handler)

	req, _ := http.NewRequest("GET", "/dashboard/overview", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response DashboardOverview
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.Equal(t, int64(3), response.TotalAppeals)
	assert.Equal(t, int64(1), response.PendingAppeals)
	assert.Greater(t, response.ApprovalRate, 0.0)
	assert.Greater(t, response.AvgNegotiationTime, 0.0)
	assert.Equal(t, "healthy", response.SystemHealth)
}

// TestGetDashboardSummary tests the summary endpoint
func TestGetDashboardSummary(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := getDashboardSummary(db)
	router.GET("/dashboard/summary", handler)

	req, _ := http.NewRequest("GET", "/dashboard/summary", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.NotNil(t, response["appeals"])
	assert.NotNil(t, response["negotiation"])
	assert.NotNil(t, response["predictions"])
}

// TestGetKeyMetrics tests the key metrics endpoint
func TestGetKeyMetrics(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := getKeyMetrics(db)
	router.GET("/dashboard/key-metrics", handler)

	tests := []struct {
		name   string
		query  string
		verify func(t *testing.T, response gin.H)
	}{
		{
			name:  "24 hour metrics",
			query: "?range=24h",
			verify: func(t *testing.T, response gin.H) {
				assert.NotNil(t, response["submission_rate"])
				assert.NotNil(t, response["approval_rate"])
				assert.Equal(t, "24h", response["time_range"])
			},
		},
		{
			name:  "7 day metrics",
			query: "?range=7d",
			verify: func(t *testing.T, response gin.H) {
				assert.Equal(t, "7d", response["time_range"])
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, _ := http.NewRequest("GET", "/dashboard/key-metrics"+tt.query, nil)
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, http.StatusOK, w.Code)

			var response gin.H
			err := json.Unmarshal(w.Body.Bytes(), &response)
			require.NoError(t, err)

			tt.verify(t, response)
		})
	}
}

// TestListAppeals tests the appeals listing endpoint
func TestListAppeals(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := listAppeals(db)
	router.GET("/appeals", handler)

	req, _ := http.NewRequest("GET", "/appeals?page=1&limit=50", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	appeals := response["appeals"].([]interface{})
	assert.Greater(t, len(appeals), 0)
	assert.Equal(t, float64(1), response["page"])
	assert.Equal(t, float64(50), response["limit"])
}

// TestFilterAppealsByStatus tests status filtering
func TestFilterAppealsByStatus(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := filterAppealsByStatus(db)
	router.GET("/appeals/filter/status", handler)

	req, _ := http.NewRequest("GET", "/appeals/filter/status?status=approved", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var appeals []rate_limiting.Appeal
	err := json.Unmarshal(w.Body.Bytes(), &appeals)
	require.NoError(t, err)

	assert.Greater(t, len(appeals), 0)
	for _, appeal := range appeals {
		assert.Equal(t, rate_limiting.StatusApproved, appeal.Status)
	}
}

// TestGetAnalyticsTrends tests the trends endpoint
func TestGetAnalyticsTrends(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	analyticsSvc := &rate_limiting.AnalyticsService{}
	handler := getAnalyticsTrends(db, analyticsSvc)
	router.GET("/analytics/trends", handler)

	req, _ := http.NewRequest("GET", "/analytics/trends?days=30", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.NotNil(t, response["submissions"])
	assert.NotNil(t, response["approvals"])
	assert.NotNil(t, response["denials"])
	assert.Equal(t, float64(30), response["period_days"])
}

// TestGetAnalyticsPatterns tests the patterns endpoint
func TestGetAnalyticsPatterns(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	analyticsSvc := &rate_limiting.AnalyticsService{}
	handler := getAnalyticsPatterns(db, analyticsSvc)
	router.GET("/analytics/patterns", handler)

	req, _ := http.NewRequest("GET", "/analytics/patterns", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.NotNil(t, response["top_reasons"])
}

// TestGetApprovalRateAnalytics tests the approval rate endpoint
func TestGetApprovalRateAnalytics(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := getApprovalRateAnalytics(db)
	router.GET("/analytics/approval-rate", handler)

	req, _ := http.NewRequest("GET", "/analytics/approval-rate", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.Equal(t, float64(3), response["total_appeals"])
	assert.Greater(t, response["approval_rate"], 0.0)
}

// TestListPredictions tests the predictions listing endpoint
func TestListPredictions(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := listPredictions(db)
	router.GET("/predictions", handler)

	req, _ := http.NewRequest("GET", "/predictions", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var predictions []rate_limiting.Prediction
	err := json.Unmarshal(w.Body.Bytes(), &predictions)
	require.NoError(t, err)

	assert.Greater(t, len(predictions), 0)
}

// TestGetPredictionAccuracy tests the accuracy endpoint
func TestGetPredictionAccuracy(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := getPredictionAccuracy(db)
	router.GET("/predictions/accuracy", handler)

	req, _ := http.NewRequest("GET", "/predictions/accuracy", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.Greater(t, response["total_predictions"], float64(0))
	assert.Greater(t, response["avg_confidence"], 0.0)
}

// TestGetDailyReport tests the daily report endpoint
func TestGetDailyReport(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	handler := getDailyReport(db)
	router.GET("/reports/daily", handler)

	req, _ := http.NewRequest("GET", "/reports/daily", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.NotNil(t, response["summary"])
	assert.Equal(t, "daily", response["report_type"])
}

// TestGetSystemHealth tests the health endpoint
func TestGetSystemHealth(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)

	router := gin.New()
	handler := getSystemHealth(db)
	router.GET("/system/health", handler)

	req, _ := http.NewRequest("GET", "/system/health", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.Equal(t, "healthy", response["status"])
	assert.NotNil(t, response["database"])
	assert.NotNil(t, response["services"])
}

// TestGetDatabaseStats tests the database stats endpoint
func TestGetDatabaseStats(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)

	router := gin.New()
	handler := getDatabaseStats(db)
	router.GET("/system/database-stats", handler)

	req, _ := http.NewRequest("GET", "/system/database-stats", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response gin.H
	err := json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.Greater(t, response["table_count"], float64(0))
	assert.Greater(t, response["index_count"], float64(-1))
}

// BenchmarkDashboardOverview benchmarks the overview endpoint
func BenchmarkDashboardOverview(b *testing.B) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(&testing.T{})
	seedTestData(&testing.T{}, db)

	router := gin.New()
	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}
	handler := getDashboardOverview(db, appealSvc, analyticsSvc)
	router.GET("/dashboard/overview", handler)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("GET", "/dashboard/overview", nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}

// BenchmarkListAppeals benchmarks the appeals listing endpoint
func BenchmarkListAppeals(b *testing.B) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(&testing.T{})
	seedTestData(&testing.T{}, db)

	router := gin.New()
	handler := listAppeals(db)
	router.GET("/appeals", handler)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("GET", "/appeals?page=1&limit=50", nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}

// BenchmarkFilterAppealsByStatus benchmarks the filtering endpoint
func BenchmarkFilterAppealsByStatus(b *testing.B) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(&testing.T{})
	seedTestData(&testing.T{}, db)

	router := gin.New()
	handler := filterAppealsByStatus(db)
	router.GET("/appeals/filter/status", handler)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("GET", "/appeals/filter/status?status=approved", nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}
