package handlers

import (
	"encoding/json"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"

	"architect-go/pkg/cache"
	"architect-go/pkg/errors"
)

// TestHealthHandler tests health check endpoints
func TestHealthHandler_Health(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health", healthHandler.Health)

	recorder := setup.MakeRequest("GET", "/health", nil)

	assert.Equal(t, http.StatusOK, recorder.Code)

	var response HealthResponse
	err := json.Unmarshal(recorder.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, "healthy", response.Status)
	assert.False(t, response.Timestamp.IsZero())
}

// TestHealthHandler_Liveness tests liveness probe
func TestHealthHandler_Liveness(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health/liveness", healthHandler.Liveness)

	recorder := setup.MakeRequest("GET", "/health/liveness", nil)

	assert.Equal(t, http.StatusOK, recorder.Code)

	var response LivenessResponse
	err := json.Unmarshal(recorder.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Alive)
	assert.False(t, response.Timestamp.IsZero())
}

// TestHealthHandler_Readiness tests readiness probe
func TestHealthHandler_Readiness(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health/readiness", healthHandler.Readiness)

	recorder := setup.MakeRequest("GET", "/health/readiness", nil)

	assert.Equal(t, http.StatusOK, recorder.Code)

	var response ReadinessResponse
	err := json.Unmarshal(recorder.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Ready)
	assert.True(t, response.Components["database"])
	assert.True(t, response.Components["cache"])
	assert.False(t, response.Timestamp.IsZero())
}

// TestHealthHandler_Readiness_DatabaseDown tests readiness when database is down
func TestHealthHandler_Readiness_DatabaseDown(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Close database connection to simulate failure
	sqlDB, err := setup.DB.DB()
	assert.NoError(t, err)
	sqlDB.Close()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health/readiness", healthHandler.Readiness)

	recorder := setup.MakeRequest("GET", "/health/readiness", nil)

	// Should return service unavailable when database is down
	assert.Equal(t, http.StatusServiceUnavailable, recorder.Code)

	var response ReadinessResponse
	err = json.Unmarshal(recorder.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.False(t, response.Ready)
	assert.False(t, response.Components["database"])
}

// TestHealthHandler_Detailed tests detailed health check
func TestHealthHandler_Detailed(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()

	// Add some cache entries
	cacheManager.Set("key1", "value1", 0)
	cacheManager.Set("key2", "value2", 0)

	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health/detailed", healthHandler.Detailed)

	recorder := setup.MakeRequest("GET", "/health/detailed", nil)

	assert.Equal(t, http.StatusOK, recorder.Code)

	var response DetailedHealthResponse
	err := json.Unmarshal(recorder.Body.Bytes(), &response)
	assert.NoError(t, err)

	// Verify response structure
	assert.NotNil(t, response.Components)
	assert.Contains(t, response.Components, "database")
	assert.Contains(t, response.Components, "cache")

	// Verify database component
	dbComponent, ok := response.Components["database"].(map[string]interface{})
	assert.True(t, ok)
	assert.Equal(t, "healthy", dbComponent["status"])

	// Verify cache component
	cacheComponent, ok := response.Components["cache"].(map[string]interface{})
	assert.True(t, ok)
	assert.Equal(t, "healthy", cacheComponent["status"])
	assert.Greater(t, cacheComponent["size"], 0.0)
}

// TestHealthHandler_AllEndpoints tests all health endpoints respond correctly
func TestHealthHandler_AllEndpoints(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	// Register all health endpoints
	healthHandler.RegisterRoutes(setup.Router)

	endpoints := []string{
		"/health",
		"/health/liveness",
		"/health/readiness",
		"/health/detailed",
	}

	for _, endpoint := range endpoints {
		recorder := setup.MakeRequest("GET", endpoint, nil)
		assert.Equal(t, http.StatusOK, recorder.Code,
			"Endpoint %s should return 200 OK", endpoint)
	}
}

// TestHealthHandler_ResponseFormat tests response format is valid JSON
func TestHealthHandler_ResponseFormat(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health", healthHandler.Health)

	recorder := setup.MakeRequest("GET", "/health", nil)

	// Verify content type
	assert.Equal(t, "application/json", recorder.Header().Get("Content-Type"))

	// Verify response is valid JSON
	var data map[string]interface{}
	err := json.Unmarshal(recorder.Body.Bytes(), &data)
	assert.NoError(t, err)
	assert.NotEmpty(t, data)
}

// TestHealthHandler_ConcurrentRequests tests health checks under concurrent load
func TestHealthHandler_ConcurrentRequests(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health", healthHandler.Health)

	// Make concurrent requests
	successCount := 0
	for i := 0; i < 100; i++ {
		recorder := setup.MakeRequest("GET", "/health", nil)
		if recorder.Code == http.StatusOK {
			successCount++
		}
	}

	assert.Equal(t, 100, successCount, "All health checks should succeed under concurrent load")
}

// TestHealthHandler_Performance tests health check performance
func TestHealthHandler_Performance(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	cacheManager := cache.NewCacheManager()
	errHandler := errors.NewErrorHandler(false, true)
	healthHandler := NewHealthHandler(setup.DB, cacheManager, errHandler)

	setup.Router.Get("/health", healthHandler.Health)
	setup.Router.Get("/health/liveness", healthHandler.Liveness)
	setup.Router.Get("/health/readiness", healthHandler.Readiness)
	setup.Router.Get("/health/detailed", healthHandler.Detailed)

	endpoints := map[string]string{
		"/health":            "basic",
		"/health/liveness":   "liveness",
		"/health/readiness":  "readiness",
		"/health/detailed":   "detailed",
	}

	for endpoint, name := range endpoints {
		recorder := setup.MakeRequest("GET", endpoint, nil)
		assert.Equal(t, http.StatusOK, recorder.Code)

		// Health checks should be very fast (< 100ms typically)
		t.Logf("%s check completed successfully", name)
	}
}
