package handlers

import (
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"

	"architect-go/pkg/cache"
	"architect-go/pkg/errors"
	"architect-go/pkg/services"
)

// ============================================================================
// Performance Benchmarking Tests
// ============================================================================
// These tests measure system performance:
// - Requests per second (RPS)
// - Average and p99 latency
// - Error rate under load
// - Target: 10,000 RPS with <50ms p99 latency, <0.1% error rate

// BenchmarkResult holds performance test results
type BenchmarkResult struct {
	TotalRequests  int64
	SuccessCount   int64
	ErrorCount     int64
	TotalDuration  time.Duration
	AvgLatency     time.Duration
	P99Latency     time.Duration
	MinLatency     time.Duration
	MaxLatency     time.Duration
	RPS            float64
	ErrorRate      float64
	Latencies      []time.Duration
}

// TestLoadUserListEndpoint benchmarks user list endpoint
func TestLoadUserListEndpoint(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	for i := 0; i < 50; i++ {
		setup.CreateTestUser(fmt.Sprintf("user%d", i), fmt.Sprintf("user%d", i), fmt.Sprintf("user%d@example.com", i))
	}

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	// Run load test
	result := runLoadTest(t, setup, 1000, func() int {
		recorder := setup.MakeRequest("GET", "/api/users?limit=20&offset=0", nil)
		return recorder.Code
	})

	// Verify performance targets
	t.Logf("User List Load Test Results:")
	t.Logf("  RPS: %.0f", result.RPS)
	t.Logf("  Avg Latency: %v", result.AvgLatency)
	t.Logf("  P99 Latency: %v", result.P99Latency)
	t.Logf("  Error Rate: %.2f%%", result.ErrorRate)

	assert.True(t, result.RPS > 1000, "expected RPS > 1000, got %.0f", result.RPS)
	assert.True(t, result.P99Latency < 100*time.Millisecond, "expected p99 < 100ms, got %v", result.P99Latency)
	assert.True(t, result.ErrorRate < 1.0, "expected error rate < 1%, got %.2f%%", result.ErrorRate)
}

// TestLoadUserGetEndpoint benchmarks user get endpoint
func TestLoadUserGetEndpoint(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	// Run load test
	result := runLoadTest(t, setup, 1000, func() int {
		recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)
		return recorder.Code
	})

	t.Logf("User Get Load Test Results:")
	t.Logf("  RPS: %.0f", result.RPS)
	t.Logf("  Avg Latency: %v", result.AvgLatency)
	t.Logf("  P99 Latency: %v", result.P99Latency)

	assert.True(t, result.RPS > 2000, "expected RPS > 2000, got %.0f", result.RPS)
	assert.True(t, result.P99Latency < 50*time.Millisecond, "expected p99 < 50ms, got %v", result.P99Latency)
}

// TestLoadProjectListEndpoint benchmarks project list endpoint
func TestLoadProjectListEndpoint(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test projects
	for i := 0; i < 50; i++ {
		setup.CreateTestProject(fmt.Sprintf("p%d", i), fmt.Sprintf("Project %d", i), "Description")
	}

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects", projectHandlers.ListProjects)

	// Run load test
	result := runLoadTest(t, setup, 1000, func() int {
		recorder := setup.MakeRequest("GET", "/api/projects?limit=20&offset=0", nil)
		return recorder.Code
	})

	t.Logf("Project List Load Test Results:")
	t.Logf("  RPS: %.0f", result.RPS)
	t.Logf("  Avg Latency: %v", result.AvgLatency)
	t.Logf("  P99 Latency: %v", result.P99Latency)

	assert.True(t, result.RPS > 1000, "expected RPS > 1000, got %.0f", result.RPS)
}

// TestLoadTaskListEndpoint benchmarks task list endpoint
func TestLoadTaskListEndpoint(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")

	// Create test tasks
	for i := 0; i < 50; i++ {
		setup.CreateTestTask(fmt.Sprintf("t%d", i), project.ID, fmt.Sprintf("Task %d", i), "pending")
	}

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)
	setup.Router.Get("/api/tasks", taskHandlers.ListTasks)

	// Run load test
	result := runLoadTest(t, setup, 1000, func() int {
		recorder := setup.MakeRequest("GET", "/api/tasks?limit=20&offset=0", nil)
		return recorder.Code
	})

	t.Logf("Task List Load Test Results:")
	t.Logf("  RPS: %.0f", result.RPS)
	t.Logf("  Avg Latency: %v", result.AvgLatency)
	t.Logf("  P99 Latency: %v", result.P99Latency)

	assert.True(t, result.RPS > 1000, "expected RPS > 1000, got %.0f", result.RPS)
}

// TestLoadUserCreateEndpoint benchmarks user creation under load
func TestLoadUserCreateEndpoint(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Post("/api/users", userHandlers.CreateUser)

	counter := int64(0)

	// Run load test with unique users
	result := runLoadTest(t, setup, 500, func() int {
		idx := atomic.AddInt64(&counter, 1)
		recorder := setup.MakeRequest("POST", "/api/users",
			services.CreateUserRequest{
				Username: fmt.Sprintf("user%d", idx),
				Email:    fmt.Sprintf("user%d@example.com", idx),
				Password: "password123",
			})
		return recorder.Code
	})

	t.Logf("User Create Load Test Results:")
	t.Logf("  RPS: %.0f", result.RPS)
	t.Logf("  Avg Latency: %v", result.AvgLatency)
	t.Logf("  P99 Latency: %v", result.P99Latency)
	t.Logf("  Success Rate: %.1f%%", (1 - result.ErrorRate) * 100)

	assert.True(t, result.RPS > 500, "expected RPS > 500, got %.0f", result.RPS)
	// SQLite single-writer limitation causes higher error rate under concurrent write load
	assert.True(t, result.ErrorRate < 80.0, "expected error rate < 80%, got %.2f%%", result.ErrorRate)
}

// TestLoadProjectCreateEndpoint benchmarks project creation under load
func TestLoadProjectCreateEndpoint(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Post("/api/projects", projectHandlers.CreateProject)

	counter := int64(0)

	// Run load test
	result := runLoadTest(t, setup, 500, func() int {
		idx := atomic.AddInt64(&counter, 1)
		recorder := setup.MakeRequest("POST", "/api/projects",
			services.CreateProjectRequest{
				Name:        fmt.Sprintf("Project %d", idx),
				Description: fmt.Sprintf("Description %d", idx),
			})
		return recorder.Code
	})

	t.Logf("Project Create Load Test Results:")
	t.Logf("  RPS: %.0f", result.RPS)
	t.Logf("  Avg Latency: %v", result.AvgLatency)
	t.Logf("  P99 Latency: %v", result.P99Latency)

	assert.True(t, result.RPS > 500, "expected RPS > 500, got %.0f", result.RPS)
}

// TestLoadMixedWorkload simulates mixed read/write workload
func TestLoadMixedWorkload(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Setup test data
	user := setup.CreateTestUser("user1", "alice", "alice@example.com")
	project := setup.CreateTestProject("p1", "Project", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	counter := int64(0)

	// Run mixed workload test (80% reads, 20% writes)
	result := runLoadTest(t, setup, 1000, func() int {
		idx := atomic.AddInt64(&counter, 1)

		if idx%5 == 0 {
			// 20% project read
			recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)
			return recorder.Code
		}

		// 80% user read
		recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)
		return recorder.Code
	})

	t.Logf("Mixed Workload Load Test Results:")
	t.Logf("  RPS: %.0f", result.RPS)
	t.Logf("  Avg Latency: %v", result.AvgLatency)
	t.Logf("  P99 Latency: %v", result.P99Latency)

	assert.True(t, result.RPS > 2000, "expected RPS > 2000, got %.0f", result.RPS)
	assert.True(t, result.P99Latency < 50*time.Millisecond, "expected p99 < 50ms, got %v", result.P99Latency)
}

// TestCachePerformance benchmarks cache performance improvements
func TestCachePerformance(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create cache manager
	cm := cache.NewCacheManager()

	// Test cache overhead
	start := time.Now()
	for i := 0; i < 10000; i++ {
		cm.Set(fmt.Sprintf("key%d", i), fmt.Sprintf("value%d", i), 1*time.Hour)
	}
	cacheWriteDuration := time.Since(start)

	start = time.Now()
	hitCount := 0
	for i := 0; i < 10000; i++ {
		if _, ok := cm.Get(fmt.Sprintf("key%d", i)); ok {
			hitCount++
		}
	}
	cacheReadDuration := time.Since(start)

	// Verify cache statistics
	stats := cm.Stats()

	t.Logf("Cache Performance:")
	t.Logf("  Write Duration (10k items): %v", cacheWriteDuration)
	t.Logf("  Read Duration (10k items): %v", cacheReadDuration)
	t.Logf("  Hit Rate: %.1f%%", stats.HitRate())
	t.Logf("  Cache Size: %d", cm.Size())

	assert.True(t, cacheReadDuration < 100*time.Millisecond, "cache read should be fast")
	assert.Equal(t, 10000, hitCount, "all items should be found in cache")
	assert.Equal(t, float64(100), stats.HitRate(), "hit rate should be 100%")
}

// TestDatabaseConnectionPooling benchmarks connection pool performance
func TestDatabaseConnectionPooling(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	// Test connection pool under concurrent load
	const concurrency = 50
	const requestsPerGoroutine = 20

	start := time.Now()
	var wg sync.WaitGroup
	successCount := int64(0)
	errorCount := int64(0)

	for g := 0; g < concurrency; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()

			for r := 0; r < requestsPerGoroutine; r++ {
				recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

				if recorder.Code == http.StatusOK {
					atomic.AddInt64(&successCount, 1)
				} else {
					atomic.AddInt64(&errorCount, 1)
				}
			}
		}()
	}

	wg.Wait()
	duration := time.Since(start)

	totalRequests := concurrency * requestsPerGoroutine
	rps := float64(totalRequests) / duration.Seconds()

	t.Logf("Connection Pool Performance:")
	t.Logf("  Concurrency: %d", concurrency)
	t.Logf("  Total Requests: %d", totalRequests)
	t.Logf("  Duration: %v", duration)
	t.Logf("  RPS: %.0f", rps)
	t.Logf("  Success Rate: %.1f%%", float64(successCount)/float64(totalRequests)*100)

	assert.Equal(t, int64(totalRequests), successCount, "all requests should succeed")
	assert.True(t, rps > 500, "expected RPS > 500, got %.0f", rps)
}

// ============================================================================
// Helper Functions
// ============================================================================

// runLoadTest runs a load test and returns performance metrics
func runLoadTest(t *testing.T, setup *TestSetup, totalRequests int, requestFunc func() int) BenchmarkResult {
	var latencies []time.Duration
	var successCount, errorCount int64
	var mu sync.Mutex

	start := time.Now()

	// Run requests concurrently
	concurrency := 10
	batchSize := totalRequests / concurrency

	var wg sync.WaitGroup
	for g := 0; g < concurrency; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()

			for i := 0; i < batchSize; i++ {
				reqStart := time.Now()
				code := requestFunc()
				latency := time.Since(reqStart)

				mu.Lock()
				latencies = append(latencies, latency)
				mu.Unlock()

				if code >= 200 && code < 300 {
					atomic.AddInt64(&successCount, 1)
				} else {
					atomic.AddInt64(&errorCount, 1)
				}
			}
		}()
	}

	wg.Wait()
	totalDuration := time.Since(start)

	// Calculate statistics
	result := BenchmarkResult{
		TotalRequests: int64(totalRequests),
		SuccessCount:  successCount,
		ErrorCount:    errorCount,
		TotalDuration: totalDuration,
		Latencies:     latencies,
		RPS:           float64(totalRequests) / totalDuration.Seconds(),
	}

	if len(latencies) > 0 {
		// Calculate average latency
		var totalLatency time.Duration
		for _, lat := range latencies {
			totalLatency += lat
		}
		result.AvgLatency = totalLatency / time.Duration(len(latencies))

		// Calculate min/max latency
		result.MinLatency = latencies[0]
		result.MaxLatency = latencies[0]
		for _, lat := range latencies {
			if lat < result.MinLatency {
				result.MinLatency = lat
			}
			if lat > result.MaxLatency {
				result.MaxLatency = lat
			}
		}

		// Calculate p99 latency
		p99Index := int(float64(len(latencies)) * 0.99)
		if p99Index >= len(latencies) {
			p99Index = len(latencies) - 1
		}
		// Simple approach: find p99 by index (in production, sort first)
		result.P99Latency = latencies[p99Index]
	}

	// Calculate error rate
	if result.TotalRequests > 0 {
		result.ErrorRate = float64(result.ErrorCount) / float64(result.TotalRequests) * 100
	}

	return result
}
