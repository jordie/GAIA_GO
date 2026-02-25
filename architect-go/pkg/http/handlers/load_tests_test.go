package handlers

import (
	"fmt"
	"testing"

	"github.com/stretchr/testify/require"

	"architect-go/pkg/errors"
)

// TestLoadEventLogHandlers_ListEvents performs load testing on ListEvents endpoint
func TestLoadEventLogHandlers_ListEvents(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 100; i++ {
		setup.CreateTestEventLog(fmt.Sprintf("type-%d", i%5), "dashboard", user.ID)
	}

	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)
	setup.Router.Get("/api/event-logs", eventLogHandlers.ListEvents)

	// Run light load test
	config := LightLoadTestConfig()
	tester := NewLoadTester(setup.Router, config)
	result := tester.RunLoad("GET", "/api/event-logs?limit=20&offset=0")

	// Assertions
	t.Logf(result.String())
	require.Greater(t, result.SuccessfulRequests, int64(0), "should have successful requests")
	require.Less(t, result.ErrorRate, 5.0, "error rate should be less than 5%")
	require.Greater(t, result.RequestsPerSecond, 10.0, "should handle at least 10 req/s")
	require.Less(t, result.AverageLatency.Milliseconds(), int64(100), "average latency should be less than 100ms")
}

// TestLoadEventLogHandlers_GetEvent performs load testing on GetEvent endpoint
func TestLoadEventLogHandlers_GetEvent(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	event := setup.CreateTestEventLog("user_action", "dashboard", user.ID)

	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)
	setup.Router.Get("/api/event-logs/{id}", eventLogHandlers.GetEvent)

	// Run light load test
	config := LightLoadTestConfig()
	tester := NewLoadTester(setup.Router, config)
	result := tester.RunLoad("GET", fmt.Sprintf("/api/event-logs/%s", event.ID))

	// Assertions
	t.Logf(result.String())
	require.Greater(t, result.SuccessfulRequests, int64(0), "should have successful requests")
	require.Less(t, result.ErrorRate, 5.0, "error rate should be less than 5%")
	require.Greater(t, result.RequestsPerSecond, 50.0, "single resource retrieval should be faster, >50 req/s")
	require.Less(t, result.AverageLatency.Milliseconds(), int64(50), "average latency should be less than 50ms")
}

// TestLoadErrorLogHandlers_ListErrors performs load testing on ListErrors endpoint
func TestLoadErrorLogHandlers_ListErrors(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	for i := 0; i < 100; i++ {
		setup.CreateTestErrorLog(fmt.Sprintf("error-%d", i%10), "critical", "api")
	}

	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)
	setup.Router.Get("/api/error-logs", errorLogHandlers.ListErrors)

	// Run light load test
	config := LightLoadTestConfig()
	tester := NewLoadTester(setup.Router, config)
	result := tester.RunLoad("GET", "/api/error-logs?limit=20&offset=0")

	// Assertions
	t.Logf(result.String())
	require.Greater(t, result.SuccessfulRequests, int64(0), "should have successful requests")
	require.Less(t, result.ErrorRate, 5.0, "error rate should be less than 5%")
}

// TestLoadNotificationHandlers_ListNotifications performs load testing on ListNotifications endpoint
func TestLoadNotificationHandlers_ListNotifications(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 100; i++ {
		setup.CreateTestNotification(user.ID, fmt.Sprintf("Notification %d", i), "info")
	}

	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)
	setup.Router.Get("/api/notifications", notificationHandlers.ListNotifications)

	// Run light load test
	config := LightLoadTestConfig()
	tester := NewLoadTester(setup.Router, config)
	result := tester.RunLoad("GET", "/api/notifications?limit=20&offset=0")

	// Assertions
	t.Logf(result.String())
	require.Greater(t, result.SuccessfulRequests, int64(0), "should have successful requests")
	require.Less(t, result.ErrorRate, 5.0, "error rate should be less than 5%")
}

// TestLoadConcurrentRequests tests high concurrency scenarios
func TestLoadConcurrentRequests(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 50; i++ {
		setup.CreateTestEventLog(fmt.Sprintf("type-%d", i%5), "dashboard", user.ID)
		setup.CreateTestNotification(user.ID, fmt.Sprintf("Notif %d", i), "info")
	}

	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	setup.Router.Get("/api/event-logs", eventLogHandlers.ListEvents)
	setup.Router.Get("/api/notifications", notificationHandlers.ListNotifications)

	// Run concurrent load test with medium concurrency
	config := LoadTestConfig{
		NumConcurrentRequests: 20,
		TotalRequests:         500,
	}
	tester := NewLoadTester(setup.Router, config)
	result := tester.RunLoad("GET", "/api/event-logs?limit=20&offset=0")

	// Assertions
	t.Logf(result.String())
	require.Greater(t, result.SuccessfulRequests, int64(0), "should handle concurrent requests")
	require.Less(t, result.ErrorRate, 10.0, "error rate should be acceptable under load")
	require.Greater(t, result.RequestsPerSecond, 5.0, "should maintain reasonable throughput")
}

// TestLoadUnderStressConditions tests system under high stress
func TestLoadUnderStressConditions(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping stress test in short mode")
	}

	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create substantial test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 200; i++ {
		setup.CreateTestEventLog(fmt.Sprintf("type-%d", i%5), "dashboard", user.ID)
	}

	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)
	setup.Router.Get("/api/event-logs", eventLogHandlers.ListEvents)

	// Run heavy load test
	config := HeavyLoadTestConfig()
	tester := NewLoadTester(setup.Router, config)
	result := tester.RunLoad("GET", "/api/event-logs?limit=20&offset=0")

	// Assertions - more lenient for stress test
	t.Logf(result.String())
	require.Greater(t, result.SuccessfulRequests, int64(0), "should handle stress")
	require.Less(t, result.ErrorRate, 20.0, "error rate should be acceptable under stress")
}

// TestLoadScalability tests if performance degrades with data size
func TestLoadScalability(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create medium amount of test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 1000; i++ {
		setup.CreateTestEventLog(fmt.Sprintf("type-%d", i%10), "dashboard", user.ID)
	}

	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)
	setup.Router.Get("/api/event-logs", eventLogHandlers.ListEvents)

	// Run load test with pagination to test scalability
	config := LoadTestConfig{
		NumConcurrentRequests: 10,
		TotalRequests:         200,
	}
	tester := NewLoadTester(setup.Router, config)
	result := tester.RunLoad("GET", "/api/event-logs?limit=50&offset=0")

	// Assertions
	t.Logf("Scalability Test Results (1000 records):%s", result.String())
	require.Greater(t, result.SuccessfulRequests, int64(0), "should handle large datasets")
	require.Less(t, result.ErrorRate, 15.0, "error rate should remain acceptable")
	require.Less(t, result.AverageLatency.Milliseconds(), int64(500), "latency should not explode with data size")
}
