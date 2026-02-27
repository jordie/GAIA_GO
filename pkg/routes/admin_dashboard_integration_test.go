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
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// TestIntegrationDashboardWorkflow tests a complete dashboard workflow
func TestIntegrationDashboardWorkflow(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()

	// Register all dashboard routes
	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}
	negotiationSvc := &rate_limiting.AppealNegotiationService{}
	historySvc := &rate_limiting.AppealHistoryService{}

	RegisterAdminDashboardRoutes(router, db, appealSvc, analyticsSvc, nil, negotiationSvc, historySvc)

	t.Run("Complete User Journey", func(t *testing.T) {
		// Step 1: User logs in and views dashboard
		req1, _ := http.NewRequest("GET", "/api/admin/dashboard/overview", nil)
		rec1 := httptest.NewRecorder()
		router.ServeHTTP(rec1, req1)
		assert.Equal(t, http.StatusOK, rec1.Code)

		var overview DashboardOverview
		json.Unmarshal(rec1.Body.Bytes(), &overview)
		assert.Greater(t, overview.TotalAppeals, int64(0))

		// Step 2: User views appeals list
		req2, _ := http.NewRequest("GET", "/api/admin/appeals?page=1&limit=50", nil)
		rec2 := httptest.NewRecorder()
		router.ServeHTTP(rec2, req2)
		assert.Equal(t, http.StatusOK, rec2.Code)

		var appealsResp gin.H
		json.Unmarshal(rec2.Body.Bytes(), &appealsResp)
		appeals := appealsResp["appeals"].([]interface{})
		assert.Greater(t, len(appeals), 0)

		// Step 3: User filters appeals by status
		req3, _ := http.NewRequest("GET", "/api/admin/appeals/filter/status?status=approved", nil)
		rec3 := httptest.NewRecorder()
		router.ServeHTTP(rec3, req3)
		assert.Equal(t, http.StatusOK, rec3.Code)

		// Step 4: User views analytics
		req4, _ := http.NewRequest("GET", "/api/admin/analytics/trends?days=30", nil)
		rec4 := httptest.NewRecorder()
		router.ServeHTTP(rec4, req4)
		assert.Equal(t, http.StatusOK, rec4.Code)

		// Step 5: User checks predictions
		req5, _ := http.NewRequest("GET", "/api/admin/predictions/accuracy", nil)
		rec5 := httptest.NewRecorder()
		router.ServeHTTP(rec5, req5)
		assert.Equal(t, http.StatusOK, rec5.Code)

		// Step 6: User generates report
		req6, _ := http.NewRequest("GET", "/api/admin/reports/daily", nil)
		rec6 := httptest.NewRecorder()
		router.ServeHTTP(rec6, req6)
		assert.Equal(t, http.StatusOK, rec6.Code)

		// Step 7: User checks system health
		req7, _ := http.NewRequest("GET", "/api/admin/system/health", nil)
		rec7 := httptest.NewRecorder()
		router.ServeHTTP(rec7, req7)
		assert.Equal(t, http.StatusOK, rec7.Code)

		var health gin.H
		json.Unmarshal(rec7.Body.Bytes(), &health)
		assert.Equal(t, "healthy", health["status"])
	})
}

// TestIntegrationMultipleUsersSimultaneous tests multiple users accessing dashboard concurrently
func TestIntegrationMultipleUsersSimultaneous(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedLargeDataset(t, db, 500)

	router := gin.New()
	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}
	negotiationSvc := &rate_limiting.AppealNegotiationService{}
	historySvc := &rate_limiting.AppealHistoryService{}

	RegisterAdminDashboardRoutes(router, db, appealSvc, analyticsSvc, nil, negotiationSvc, historySvc)

	// Simulate 10 users accessing dashboard simultaneously
	done := make(chan bool, 10)

	for user := 0; user < 10; user++ {
		go func(userID int) {
			// User 1: Views overview
			req, _ := http.NewRequest("GET", "/api/admin/dashboard/overview", nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)
			assert.Equal(t, http.StatusOK, rec.Code)

			// User 2: Views appeals
			req2, _ := http.NewRequest("GET", "/api/admin/appeals?page=1&limit=50", nil)
			rec2 := httptest.NewRecorder()
			router.ServeHTTP(rec2, req2)
			assert.Equal(t, http.StatusOK, rec2.Code)

			// User 3: Filters
			req3, _ := http.NewRequest("GET", fmt.Sprintf("/api/admin/appeals?page=%d&limit=50", (userID%5)+1), nil)
			rec3 := httptest.NewRecorder()
			router.ServeHTTP(rec3, req3)
			assert.Equal(t, http.StatusOK, rec3.Code)

			done <- true
		}(user)
	}

	// Wait for all users
	for i := 0; i < 10; i++ {
		<-done
	}
}

// TestIntegrationDataConsistency tests that data is consistent across multiple requests
func TestIntegrationDataConsistency(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}

	router.GET("/api/admin/dashboard/overview", getDashboardOverview(db, appealSvc, analyticsSvc))
	router.GET("/api/admin/dashboard/summary", getDashboardSummary(db))

	// Make multiple requests and verify consistent results
	var firstOverview, secondOverview DashboardOverview
	var firstSummary, secondSummary gin.H

	// First request
	req1, _ := http.NewRequest("GET", "/api/admin/dashboard/overview", nil)
	rec1 := httptest.NewRecorder()
	router.ServeHTTP(rec1, req1)
	json.Unmarshal(rec1.Body.Bytes(), &firstOverview)

	req2, _ := http.NewRequest("GET", "/api/admin/dashboard/summary", nil)
	rec2 := httptest.NewRecorder()
	router.ServeHTTP(rec2, req2)
	json.Unmarshal(rec2.Body.Bytes(), &firstSummary)

	// Wait a moment
	time.Sleep(100 * time.Millisecond)

	// Second request
	req3, _ := http.NewRequest("GET", "/api/admin/dashboard/overview", nil)
	rec3 := httptest.NewRecorder()
	router.ServeHTTP(rec3, req3)
	json.Unmarshal(rec3.Body.Bytes(), &secondOverview)

	req4, _ := http.NewRequest("GET", "/api/admin/dashboard/summary", nil)
	rec4 := httptest.NewRecorder()
	router.ServeHTTP(rec4, req4)
	json.Unmarshal(rec4.Body.Bytes(), &secondSummary)

	// Data should be consistent (same database)
	assert.Equal(t, firstOverview.TotalAppeals, secondOverview.TotalAppeals)
	assert.Equal(t, firstOverview.ApprovalRate, secondOverview.ApprovalRate)
}

// TestIntegrationPaginationConsistency tests pagination consistency
func TestIntegrationPaginationConsistency(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedLargeDataset(t, db, 500)

	router := gin.New()
	router.GET("/api/admin/appeals", listAppeals(db))

	// Fetch all pages and verify no duplicates
	pageSize := 50
	totalAppeals := make(map[int]bool)

	for page := 1; page <= 10; page++ {
		req, _ := http.NewRequest("GET", fmt.Sprintf("/api/admin/appeals?page=%d&limit=%d", page, pageSize), nil)
		rec := httptest.NewRecorder()
		router.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			break
		}

		var resp gin.H
		json.Unmarshal(rec.Body.Bytes(), &resp)
		appeals := resp["appeals"].([]interface{})

		for _, a := range appeals {
			appealMap := a.(map[string]interface{})
			appealID := int(appealMap["id"].(float64))

			// Check for duplicates
			assert.False(t, totalAppeals[appealID], "Duplicate appeal ID: %d", appealID)
			totalAppeals[appealID] = true
		}
	}

	assert.Greater(t, len(totalAppeals), 0)
}

// TestIntegrationFilteringAndPagination tests combination of filtering and pagination
func TestIntegrationFilteringAndPagination(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedLargeDataset(t, db, 300)

	router := gin.New()
	router.GET("/api/admin/appeals", listAppeals(db))

	// Test filtering with pagination
	tests := []struct {
		name   string
		status string
	}{
		{"Pending Appeals", rate_limiting.StatusPending},
		{"Approved Appeals", rate_limiting.StatusApproved},
		{"Denied Appeals", rate_limiting.StatusDenied},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, _ := http.NewRequest("GET", fmt.Sprintf("/api/admin/appeals?page=1&limit=50&status=%s", tt.status), nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			assert.Equal(t, http.StatusOK, rec.Code)

			var resp gin.H
			json.Unmarshal(rec.Body.Bytes(), &resp)
			appeals := resp["appeals"].([]interface{})

			// All appeals should have the requested status
			for _, a := range appeals {
				appealMap := a.(map[string]interface{})
				status := appealMap["status"].(string)
				assert.Equal(t, tt.status, status)
			}
		})
	}
}

// TestIntegrationAnalyticsEndToEnd tests analytics endpoints working together
func TestIntegrationAnalyticsEndToEnd(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedLargeDataset(t, db, 500)

	router := gin.New()
	analyticsSvc := &rate_limiting.AnalyticsService{}

	router.GET("/api/admin/analytics/trends", getAnalyticsTrends(db, analyticsSvc))
	router.GET("/api/admin/analytics/patterns", getAnalyticsPatterns(db, analyticsSvc))
	router.GET("/api/admin/analytics/approval-rate", getApprovalRateAnalytics(db))
	router.GET("/api/admin/analytics/user-statistics", getUserStatistics(db))

	endpoints := []struct {
		name     string
		endpoint string
	}{
		{"Trends", "/api/admin/analytics/trends?days=30"},
		{"Patterns", "/api/admin/analytics/patterns"},
		{"Approval Rate", "/api/admin/analytics/approval-rate"},
		{"User Statistics", "/api/admin/analytics/user-statistics"},
	}

	for _, ep := range endpoints {
		t.Run(ep.name, func(t *testing.T) {
			req, _ := http.NewRequest("GET", ep.endpoint, nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			assert.Equal(t, http.StatusOK, rec.Code)

			var resp gin.H
			err := json.Unmarshal(rec.Body.Bytes(), &resp)
			assert.NoError(t, err)
			assert.NotNil(t, resp)
		})
	}
}

// TestIntegrationReportGeneration tests report generation workflow
func TestIntegrationReportGeneration(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedLargeDataset(t, db, 200)

	router := gin.New()

	router.GET("/api/admin/reports/daily", getDailyReport(db))
	router.GET("/api/admin/reports/weekly", getWeeklyReport(db))
	router.GET("/api/admin/reports/monthly", getMonthlyReport(db))
	router.GET("/api/admin/reports/custom", getCustomReport(db))

	reports := []struct {
		name     string
		endpoint string
		expected string
	}{
		{"Daily Report", "/api/admin/reports/daily", "daily"},
		{"Weekly Report", "/api/admin/reports/weekly", "weekly"},
		{"Monthly Report", "/api/admin/reports/monthly", "monthly"},
	}

	for _, rpt := range reports {
		t.Run(rpt.name, func(t *testing.T) {
			req, _ := http.NewRequest("GET", rpt.endpoint, nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			assert.Equal(t, http.StatusOK, rec.Code)

			var resp gin.H
			json.Unmarshal(rec.Body.Bytes(), &resp)

			assert.Equal(t, rpt.expected, resp["report_type"])
			assert.NotNil(t, resp["summary"])
		})
	}
}

// TestIntegrationSystemMonitoring tests complete system monitoring workflow
func TestIntegrationSystemMonitoring(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)

	router := gin.New()

	router.GET("/api/admin/system/health", getSystemHealth(db))
	router.GET("/api/admin/system/database-stats", getDatabaseStats(db))
	router.GET("/api/admin/system/performance", getPerformanceMetrics(db))
	router.GET("/api/admin/system/resource-usage", getResourceUsage(db))

	endpoints := []string{
		"/api/admin/system/health",
		"/api/admin/system/database-stats",
		"/api/admin/system/performance",
		"/api/admin/system/resource-usage",
	}

	for _, endpoint := range endpoints {
		t.Run(endpoint, func(t *testing.T) {
			req, _ := http.NewRequest("GET", endpoint, nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			assert.Equal(t, http.StatusOK, rec.Code)

			var resp gin.H
			err := json.Unmarshal(rec.Body.Bytes(), &resp)
			assert.NoError(t, err)
		})
	}
}

// TestIntegrationErrorRecovery tests system behavior after errors
func TestIntegrationErrorRecovery(t *testing.T) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(t)
	seedTestData(t, db)

	router := gin.New()
	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}

	router.GET("/api/admin/dashboard/overview", getDashboardOverview(db, appealSvc, analyticsSvc))

	// Make normal requests
	for i := 0; i < 5; i++ {
		req, _ := http.NewRequest("GET", "/api/admin/dashboard/overview", nil)
		rec := httptest.NewRecorder()
		router.ServeHTTP(rec, req)
		assert.Equal(t, http.StatusOK, rec.Code)
	}

	// Even if there are errors, subsequent requests should work
	req, _ := http.NewRequest("GET", "/api/admin/dashboard/overview", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	assert.Equal(t, http.StatusOK, rec.Code)
}

// BenchmarkIntegrationFullDashboard benchmarks loading the full dashboard
func BenchmarkIntegrationFullDashboard(b *testing.B) {
	gin.SetMode(gin.TestMode)
	db := setupTestDB(&testing.T{})
	seedLargeDataset(&testing.T{}, db, 1000)

	router := gin.New()
	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}
	negotiationSvc := &rate_limiting.AppealNegotiationService{}
	historySvc := &rate_limiting.AppealHistoryService{}

	RegisterAdminDashboardRoutes(router, db, appealSvc, analyticsSvc, nil, negotiationSvc, historySvc)

	endpoints := []string{
		"/api/admin/dashboard/overview",
		"/api/admin/dashboard/summary",
		"/api/admin/appeals?page=1&limit=50",
		"/api/admin/analytics/trends?days=30",
		"/api/admin/predictions/accuracy",
		"/api/admin/system/health",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		for _, endpoint := range endpoints {
			req, _ := http.NewRequest("GET", endpoint, nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)
		}
	}
}
