package handlers

import (
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// LoadTestResult contains results from a load test
type LoadTestResult struct {
	TotalRequests      int64
	SuccessfulRequests int64
	FailedRequests     int64
	TotalDuration      time.Duration
	AverageLatency     time.Duration
	MinLatency         time.Duration
	MaxLatency         time.Duration
	RequestsPerSecond  float64
	ErrorRate          float64
	StatusCodeCounts   map[int]int64
	statusCodeMu       sync.Mutex
}

// LoadTestConfig contains configuration for load tests
type LoadTestConfig struct {
	NumConcurrentRequests int
	TotalRequests         int
	TimeoutPerRequest     time.Duration
}

// LoadTester performs load testing
type LoadTester struct {
	config LoadTestConfig
	router http.Handler
}

// NewLoadTester creates a new load tester
func NewLoadTester(router http.Handler, config LoadTestConfig) *LoadTester {
	return &LoadTester{
		config: config,
		router: router,
	}
}

// RunLoad executes a load test with concurrent requests
func (lt *LoadTester) RunLoad(method, path string) *LoadTestResult {
	result := &LoadTestResult{
		StatusCodeCounts: make(map[int]int64),
		MinLatency:       time.Duration(^uint64(0) >> 1), // Max duration
	}

	var wg sync.WaitGroup
	var successCount int64
	var failCount int64
	var totalLatency int64

	startTime := time.Now()

	// Distribute requests across concurrent workers
	requestsPerWorker := lt.config.TotalRequests / lt.config.NumConcurrentRequests
	remainder := lt.config.TotalRequests % lt.config.NumConcurrentRequests

	for w := 0; w < lt.config.NumConcurrentRequests; w++ {
		wg.Add(1)
		numRequests := requestsPerWorker
		if w < remainder {
			numRequests++
		}

		go func() {
			defer wg.Done()
			for i := 0; i < numRequests; i++ {
				latency := lt.executeRequest(method, path, result)
				if latency > 0 {
					atomic.AddInt64(&successCount, 1)
					atomic.AddInt64(&totalLatency, latency.Nanoseconds())

					// Update min/max latency (using compare-and-swap for simplicity)
					for {
						oldMin := atomic.LoadInt64((*int64)(&result.MinLatency))
						if latency.Nanoseconds() < oldMin {
							if atomic.CompareAndSwapInt64((*int64)(&result.MinLatency), oldMin, latency.Nanoseconds()) {
								break
							}
						} else {
							break
						}
					}

					for {
						oldMax := atomic.LoadInt64((*int64)(&result.MaxLatency))
						if latency.Nanoseconds() > oldMax {
							if atomic.CompareAndSwapInt64((*int64)(&result.MaxLatency), oldMax, latency.Nanoseconds()) {
								break
							}
						} else {
							break
						}
					}
				} else {
					atomic.AddInt64(&failCount, 1)
				}
			}
		}()
	}

	wg.Wait()
	endTime := time.Now()

	// Calculate results
	result.TotalDuration = endTime.Sub(startTime)
	result.TotalRequests = int64(lt.config.TotalRequests)
	result.SuccessfulRequests = successCount
	result.FailedRequests = failCount
	result.RequestsPerSecond = float64(result.SuccessfulRequests) / result.TotalDuration.Seconds()

	if result.SuccessfulRequests > 0 {
		result.AverageLatency = time.Duration(totalLatency / result.SuccessfulRequests)
	}

	if result.TotalRequests > 0 {
		result.ErrorRate = float64(result.FailedRequests) / float64(result.TotalRequests) * 100
	}

	return result
}

// executeRequest executes a single request and measures latency
func (lt *LoadTester) executeRequest(method, path string, result *LoadTestResult) time.Duration {
	start := time.Now()

	req, _ := http.NewRequest(method, path, nil)
	req.Header.Set("X-Request-ID", fmt.Sprintf("load-test-%d", time.Now().UnixNano()))

	w := &responseWriter{
		statusCode: http.StatusOK,
		header:     make(http.Header),
	}

	lt.router.ServeHTTP(w, req)

	latency := time.Since(start)

	// Track status code (only apply timeout check if timeout is configured)
	if lt.config.TimeoutPerRequest > 0 && latency > lt.config.TimeoutPerRequest {
		return 0 // Request timed out
	}

	result.statusCodeMu.Lock()
	result.StatusCodeCounts[w.statusCode]++
	result.statusCodeMu.Unlock()

	return latency
}

// responseWriter implements http.ResponseWriter for tracking responses
type responseWriter struct {
	statusCode int
	header     http.Header
	body       []byte
}

func (rw *responseWriter) Header() http.Header {
	return rw.header
}

func (rw *responseWriter) Write(b []byte) (int, error) {
	rw.body = append(rw.body, b...)
	return len(b), nil
}

func (rw *responseWriter) WriteHeader(statusCode int) {
	rw.statusCode = statusCode
}

// String returns a formatted string representation of the load test results
func (ltr *LoadTestResult) String() string {
	return fmt.Sprintf(`
=== Load Test Results ===
Total Requests:       %d
Successful:           %d
Failed:               %d
Total Duration:       %v
Average Latency:      %v
Min Latency:          %v
Max Latency:          %v
Requests/Second:      %.2f
Error Rate:           %.2f%%
Status Codes:         %v
`,
		ltr.TotalRequests,
		ltr.SuccessfulRequests,
		ltr.FailedRequests,
		ltr.TotalDuration,
		ltr.AverageLatency,
		ltr.MinLatency,
		ltr.MaxLatency,
		ltr.RequestsPerSecond,
		ltr.ErrorRate,
		ltr.StatusCodeCounts,
	)
}

// DefaultLoadTestConfig returns default load test configuration
func DefaultLoadTestConfig() LoadTestConfig {
	return LoadTestConfig{
		NumConcurrentRequests: 10,
		TotalRequests:         1000,
		TimeoutPerRequest:     5 * time.Second,
	}
}

// LightLoadTestConfig returns a light load test configuration
func LightLoadTestConfig() LoadTestConfig {
	return LoadTestConfig{
		NumConcurrentRequests: 5,
		TotalRequests:         100,
		TimeoutPerRequest:     5 * time.Second,
	}
}

// HeavyLoadTestConfig returns a heavy load test configuration
func HeavyLoadTestConfig() LoadTestConfig {
	return LoadTestConfig{
		NumConcurrentRequests: 50,
		TotalRequests:         5000,
		TimeoutPerRequest:     5 * time.Second,
	}
}
