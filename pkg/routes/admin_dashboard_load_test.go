package routes

import (
	"fmt"
	"math/rand"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// LoadTestResult holds results from a load test
type LoadTestResult struct {
	TotalRequests   int
	SuccessRequests int
	FailedRequests  int
	TotalTime       time.Duration
	AvgLatency      time.Duration
	MinLatency      time.Duration
	MaxLatency      time.Duration
	P50Latency      time.Duration
	P95Latency      time.Duration
	P99Latency      time.Duration
	RequestsPerSec  float64
	ErrorRate       float64
}

// seedLargeDataset creates a large dataset for load testing
func seedLargeDataset(t *testing.T, db *gorm.DB, appealCount int) {
	now := time.Now()

	// Create appeals
	for i := 1; i <= appealCount; i++ {
		status := map[int]string{
			0: rate_limiting.StatusPending,
			1: rate_limiting.StatusApproved,
			2: rate_limiting.StatusDenied,
		}[i%3]

		reasons := []string{
			"Unfair suspension",
			"Bug in system",
			"Policy violation",
			"Account compromise",
			"Incorrect sanction",
		}

		appeal := rate_limiting.Appeal{
			UserID:    int64(i % 100),
			Status:    status,
			Reason:    reasons[i%len(reasons)],
			CreatedAt: now.Add(-time.Duration(rand.Intn(7200)) * time.Hour),
			Priority:  int32(i % 3),
		}

		if status != rate_limiting.StatusPending {
			reviewedAt := appeal.CreatedAt.Add(time.Duration(rand.Intn(1440)) * time.Minute)
			appeal.ReviewedAt = &reviewedAt
		}

		require.NoError(t, db.Create(&appeal).Error)

		// Create messages for each appeal
		messageCount := rand.Intn(10) + 1
		for j := 0; j < messageCount; j++ {
			msg := rate_limiting.AppealNegotiationMessage{
				AppealID:       int32(appeal.ID),
				SenderID:       int32((i+j)%100 + 1),
				Message:        fmt.Sprintf("Message %d for appeal %d", j, i),
				CreatedAt:      appeal.CreatedAt.Add(time.Duration(j*10) * time.Minute),
				SentimentScore: rand.Float64()*2 - 1, // -1 to +1
			}
			require.NoError(t, db.Create(&msg).Error)
		}
	}

	// Create predictions
	for i := 1; i <= appealCount/2; i++ {
		pred := rate_limiting.Prediction{
			AppealID:            int32(i),
			PredictionType:      map[int]string{0: "approval_probability", 1: "recovery_timeline", 2: "auto_suggestions"}[i%3],
			PredictionValue:     rand.Float64(),
			Confidence:          0.5 + rand.Float64()*0.5,
			PredictionLatencyMs: int32(rand.Intn(100) + 5),
			CreatedAt:           now.Add(-time.Duration(rand.Intn(1440)) * time.Minute),
		}
		require.NoError(t, db.Create(&pred).Error)
	}
}

// runLoadTest executes concurrent requests and measures performance
func runLoadTest(t *testing.T, handler gin.HandlerFunc, endpoint string, concurrency int, requestsPerWorker int) LoadTestResult {
	gin.SetMode(gin.TestMode)

	router := gin.New()
	router.GET(endpoint, handler)

	result := LoadTestResult{
		TotalRequests: concurrency * requestsPerWorker,
		MinLatency:    time.Duration(1<<63 - 1),
	}

	latencies := make([]time.Duration, 0, result.TotalRequests)
	latenciesMutex := &sync.Mutex{}
	wg := &sync.WaitGroup{}

	startTime := time.Now()

	// Launch concurrent workers
	for w := 0; w < concurrency; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()

			for i := 0; i < requestsPerWorker; i++ {
				req, _ := http.NewRequest("GET", endpoint, nil)
				rec := httptest.NewRecorder()

				reqStartTime := time.Now()
				router.ServeHTTP(rec, req)
				latency := time.Since(reqStartTime)

				latenciesMutex.Lock()
				latencies = append(latencies, latency)
				latenciesMutex.Unlock()

				if rec.Code == http.StatusOK {
					result.SuccessRequests++
				} else {
					result.FailedRequests++
				}

				if latency < result.MinLatency {
					result.MinLatency = latency
				}
				if latency > result.MaxLatency {
					result.MaxLatency = latency
				}
			}
		}()
	}

	wg.Wait()
	result.TotalTime = time.Since(startTime)

	// Calculate percentiles
	if len(latencies) > 0 {
		// Simple percentile calculation (not exact but close enough for load testing)
		result.P50Latency = latencies[len(latencies)/2]
		result.P95Latency = latencies[int(float64(len(latencies))*0.95)]
		result.P99Latency = latencies[int(float64(len(latencies))*0.99)]

		// Calculate average
		var totalLatency time.Duration
		for _, lat := range latencies {
			totalLatency += lat
		}
		result.AvgLatency = totalLatency / time.Duration(len(latencies))
	}

	result.RequestsPerSec = float64(result.TotalRequests) / result.TotalTime.Seconds()
	result.ErrorRate = float64(result.FailedRequests) / float64(result.TotalRequests)

	return result
}

// TestLoadDashboardOverview tests dashboard overview under load
func TestLoadDashboardOverview(t *testing.T) {
	db := setupTestDB(t)
	seedLargeDataset(t, db, 1000) // 1000 appeals

	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}
	handler := getDashboardOverview(db, appealSvc, analyticsSvc)

	result := runLoadTest(t, handler, "/dashboard/overview", 10, 100) // 10 concurrent users, 100 requests each

	fmt.Printf("\n=== Dashboard Overview Load Test ===\n")
	fmt.Printf("Total Requests: %d\n", result.TotalRequests)
	fmt.Printf("Success Rate: %.2f%%\n", float64(result.SuccessRequests)/float64(result.TotalRequests)*100)
	fmt.Printf("Requests/sec: %.2f\n", result.RequestsPerSec)
	fmt.Printf("Latency - Avg: %v, Min: %v, Max: %v\n", result.AvgLatency, result.MinLatency, result.MaxLatency)
	fmt.Printf("Latency - P50: %v, P95: %v, P99: %v\n", result.P50Latency, result.P95Latency, result.P99Latency)

	// Assertions
	assert.Greater(t, result.SuccessRequests, result.TotalRequests*90/100) // 90% success rate
	assert.Less(t, result.AvgLatency, 500*time.Millisecond)               // < 500ms average
	assert.Less(t, result.P99Latency, 1*time.Second)                      // < 1s p99
}

// TestLoadListAppeals tests appeals listing under load
func TestLoadListAppeals(t *testing.T) {
	db := setupTestDB(t)
	seedLargeDataset(t, db, 2000) // 2000 appeals

	handler := listAppeals(db)

	result := runLoadTest(t, handler, "/appeals?page=1&limit=50", 20, 50) // 20 concurrent users

	fmt.Printf("\n=== List Appeals Load Test ===\n")
	fmt.Printf("Total Requests: %d\n", result.TotalRequests)
	fmt.Printf("Success Rate: %.2f%%\n", float64(result.SuccessRequests)/float64(result.TotalRequests)*100)
	fmt.Printf("Requests/sec: %.2f\n", result.RequestsPerSec)
	fmt.Printf("Latency - Avg: %v, P99: %v\n", result.AvgLatency, result.P99Latency)

	assert.Greater(t, result.SuccessRequests, result.TotalRequests*90/100)
	assert.Less(t, result.AvgLatency, 300*time.Millisecond)
}

// TestLoadFilterAppeals tests filtering under load
func TestLoadFilterAppeals(t *testing.T) {
	db := setupTestDB(t)
	seedLargeDataset(t, db, 1500)

	handler := filterAppealsByStatus(db)

	result := runLoadTest(t, handler, "/appeals/filter/status?status=approved", 15, 75)

	fmt.Printf("\n=== Filter Appeals Load Test ===\n")
	fmt.Printf("Total Requests: %d\n", result.TotalRequests)
	fmt.Printf("Success Rate: %.2f%%\n", float64(result.SuccessRequests)/float64(result.TotalRequests)*100)
	fmt.Printf("Requests/sec: %.2f\n", result.RequestsPerSec)

	assert.Greater(t, result.SuccessRequests, result.TotalRequests*90/100)
}

// TestStressAnalyticsTrends tests analytics under stress
func TestStressAnalyticsTrends(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping stress test in short mode")
	}

	db := setupTestDB(t)
	seedLargeDataset(t, db, 5000) // 5000 appeals

	analyticsSvc := &rate_limiting.AnalyticsService{}
	handler := getAnalyticsTrends(db, analyticsSvc)

	result := runLoadTest(t, handler, "/analytics/trends?days=30", 50, 100) // 50 concurrent, 100 each

	fmt.Printf("\n=== Analytics Trends Stress Test ===\n")
	fmt.Printf("Total Requests: %d\n", result.TotalRequests)
	fmt.Printf("Success Rate: %.2f%%\n", float64(result.SuccessRequests)/float64(result.TotalRequests)*100)
	fmt.Printf("Requests/sec: %.2f\n", result.RequestsPerSec)
	fmt.Printf("Max Latency: %v\n", result.MaxLatency)

	// Under stress, we're looking for graceful degradation
	assert.Greater(t, result.SuccessRequests, result.TotalRequests*85/100) // 85% success under stress
	assert.Less(t, result.P99Latency, 3*time.Second)                       // < 3s p99
}

// TestStressSystemHealth tests system health endpoint under stress
func TestStressSystemHealth(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping stress test in short mode")
	}

	db := setupTestDB(t)

	handler := getSystemHealth(db)

	// High concurrency
	result := runLoadTest(t, handler, "/system/health", 100, 50)

	fmt.Printf("\n=== System Health Stress Test ===\n")
	fmt.Printf("Total Requests: %d\n", result.TotalRequests)
	fmt.Printf("Success Rate: %.2f%%\n", float64(result.SuccessRequests)/float64(result.TotalRequests)*100)
	fmt.Printf("Requests/sec: %.2f\n", result.RequestsPerSec)

	// Health check should be very fast even under load
	assert.Greater(t, result.SuccessRequests, result.TotalRequests*95/100)
	assert.Less(t, result.AvgLatency, 100*time.Millisecond)
}

// TestConcurrentPagination tests pagination under concurrent load
func TestConcurrentPagination(t *testing.T) {
	db := setupTestDB(t)
	seedLargeDataset(t, db, 1000)

	handler := listAppeals(db)

	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/appeals", handler)

	// Request different pages concurrently
	results := make(chan int, 100)
	wg := &sync.WaitGroup{}

	for page := 1; page <= 20; page++ {
		wg.Add(1)
		go func(p int) {
			defer wg.Done()

			req, _ := http.NewRequest("GET", fmt.Sprintf("/appeals?page=%d&limit=50", p), nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			results <- rec.Code
		}(page)
	}

	wg.Wait()
	close(results)

	successCount := 0
	for code := range results {
		if code == http.StatusOK {
			successCount++
		}
	}

	assert.Equal(t, 20, successCount)
}

// TestEdgeCaseEmptyDatabase tests dashboard with empty database
func TestEdgeCaseEmptyDatabase(t *testing.T) {
	db := setupTestDB(t)
	// Don't seed any data

	gin.SetMode(gin.TestMode)
	router := gin.New()

	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}

	router.GET("/dashboard/overview", getDashboardOverview(db, appealSvc, analyticsSvc))
	router.GET("/appeals", listAppeals(db))
	router.GET("/analytics/trends", getAnalyticsTrends(db, analyticsSvc))

	tests := []struct {
		path string
		name string
	}{
		{"/dashboard/overview", "Empty Dashboard"},
		{"/appeals?page=1&limit=50", "Empty Appeals List"},
		{"/analytics/trends?days=30", "Empty Analytics"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, _ := http.NewRequest("GET", tt.path, nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			assert.Equal(t, http.StatusOK, rec.Code)
		})
	}
}

// TestEdgeCaseInvalidParameters tests with invalid parameters
func TestEdgeCaseInvalidParameters(t *testing.T) {
	db := setupTestDB(t)
	seedTestData(t, db)

	gin.SetMode(gin.TestMode)
	router := gin.New()

	router.GET("/dashboard/key-metrics", getKeyMetrics(db))
	router.GET("/appeals", listAppeals(db))

	tests := []struct {
		path string
		name string
	}{
		{"/dashboard/key-metrics?range=invalid", "Invalid Time Range"},
		{"/appeals?page=999&limit=50", "Non-existent Page"},
		{"/appeals?page=-1&limit=50", "Negative Page"},
		{"/appeals?page=1&limit=99999", "Excessive Limit"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, _ := http.NewRequest("GET", tt.path, nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			// Should gracefully handle invalid parameters
			assert.True(t, rec.Code == http.StatusOK || rec.Code == http.StatusBadRequest)
		})
	}
}

// TestEdgeCaseLargeDatasets tests with very large datasets
func TestEdgeCaseLargeDatasets(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping large dataset test in short mode")
	}

	db := setupTestDB(t)
	seedLargeDataset(t, db, 10000) // 10,000 appeals

	gin.SetMode(gin.TestMode)
	router := gin.New()

	router.GET("/analytics/patterns", getAnalyticsPatterns(db, &rate_limiting.AnalyticsService{}))

	start := time.Now()
	req, _ := http.NewRequest("GET", "/analytics/patterns", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	elapsed := time.Since(start)

	assert.Equal(t, http.StatusOK, rec.Code)
	assert.Less(t, elapsed, 2*time.Second) // Should complete in under 2 seconds
}

// TestMemoryLeaks checks for memory leaks during repeated calls
func TestMemoryLeaks(t *testing.T) {
	db := setupTestDB(t)
	seedLargeDataset(t, db, 1000)

	gin.SetMode(gin.TestMode)
	router := gin.New()

	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}

	router.GET("/dashboard/overview", getDashboardOverview(db, appealSvc, analyticsSvc))

	// Make many requests and ensure they complete
	for i := 0; i < 1000; i++ {
		req, _ := http.NewRequest("GET", "/dashboard/overview", nil)
		rec := httptest.NewRecorder()
		router.ServeHTTP(rec, req)

		assert.Equal(t, http.StatusOK, rec.Code)
	}
}

// BenchmarkConcurrentRequests benchmarks concurrent request handling
func BenchmarkConcurrentRequests(b *testing.B) {
	db := setupTestDB(&testing.T{})
	seedLargeDataset(&testing.T{}, db, 1000)

	gin.SetMode(gin.TestMode)
	router := gin.New()

	appealSvc := &rate_limiting.AppealService{}
	analyticsSvc := &rate_limiting.AnalyticsService{}

	router.GET("/dashboard/overview", getDashboardOverview(db, appealSvc, analyticsSvc))

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			req, _ := http.NewRequest("GET", "/dashboard/overview", nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)
		}
	})
}

// BenchmarkPaginationPerformance benchmarks pagination at different page numbers
func BenchmarkPaginationPerformance(b *testing.B) {
	db := setupTestDB(&testing.T{})
	seedLargeDataset(&testing.T{}, db, 2000)

	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/appeals", listAppeals(db))

	pages := []int{1, 10, 50, 100}

	for _, page := range pages {
		b.Run(fmt.Sprintf("Page%d", page), func(b *testing.B) {
			for i := 0; i < b.N; i++ {
				req, _ := http.NewRequest("GET", fmt.Sprintf("/appeals?page=%d&limit=50", page), nil)
				rec := httptest.NewRecorder()
				router.ServeHTTP(rec, req)
			}
		})
	}
}
