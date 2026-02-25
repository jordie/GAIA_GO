package handlers

import (
	"fmt"
	"testing"

	"architect-go/pkg/errors"
)

// BenchmarkEventLogHandlers_ListEvents benchmarks the ListEvents endpoint
func BenchmarkEventLogHandlers_ListEvents(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 100; i++ {
		setup.CreateTestEventLog(fmt.Sprintf("type-%d", i%5), "dashboard", user.ID)
	}

	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)
	setup.Router.Get("/api/event-logs", eventLogHandlers.ListEvents)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", "/api/event-logs?limit=20&offset=0", nil)
	}
}

// BenchmarkEventLogHandlers_GetEvent benchmarks the GetEvent endpoint
func BenchmarkEventLogHandlers_GetEvent(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	event := setup.CreateTestEventLog("user_action", "dashboard", user.ID)

	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)
	setup.Router.Get("/api/event-logs/{id}", eventLogHandlers.GetEvent)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", fmt.Sprintf("/api/event-logs/%s", event.ID), nil)
	}
}

// BenchmarkErrorLogHandlers_ListErrors benchmarks the ListErrors endpoint
func BenchmarkErrorLogHandlers_ListErrors(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	// Create test data
	for i := 0; i < 100; i++ {
		setup.CreateTestErrorLog(fmt.Sprintf("error-%d", i%10), "critical", "api")
	}

	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)
	setup.Router.Get("/api/error-logs", errorLogHandlers.ListErrors)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", "/api/error-logs?limit=20&offset=0", nil)
	}
}

// BenchmarkErrorLogHandlers_GetError benchmarks the GetError endpoint
func BenchmarkErrorLogHandlers_GetError(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	errorLog := setup.CreateTestErrorLog("runtime_error", "critical", "api")

	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)
	setup.Router.Get("/api/error-logs/{id}", errorLogHandlers.GetError)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", fmt.Sprintf("/api/error-logs/%s", errorLog.ID), nil)
	}
}

// BenchmarkNotificationHandlers_ListNotifications benchmarks the ListNotifications endpoint
func BenchmarkNotificationHandlers_ListNotifications(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 100; i++ {
		setup.CreateTestNotification(user.ID, fmt.Sprintf("Notification %d", i), "info")
	}

	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)
	setup.Router.Get("/api/notifications", notificationHandlers.ListNotifications)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", "/api/notifications?limit=20&offset=0", nil)
	}
}

// BenchmarkNotificationHandlers_GetNotification benchmarks the GetNotification endpoint
func BenchmarkNotificationHandlers_GetNotification(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	notification := setup.CreateTestNotification(user.ID, "Test Notification", "alert")

	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)
	setup.Router.Get("/api/notifications/{id}", notificationHandlers.GetNotification)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", fmt.Sprintf("/api/notifications/%s", notification.ID), nil)
	}
}

// BenchmarkSessionTrackingHandlers_ListSessions benchmarks the ListSessions endpoint
func BenchmarkSessionTrackingHandlers_ListSessions(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	for i := 0; i < 50; i++ {
		session := &TestSession{
			ID:     fmt.Sprintf("session-%d", i),
			UserID: user.ID,
		}
		setup.DB.Create(session)
	}

	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)
	setup.Router.Get("/api/sessions", sessionHandlers.ListSessions)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", "/api/sessions?limit=20&offset=0", nil)
	}
}

// BenchmarkIntegrationHandlers_ListIntegrations benchmarks the ListIntegrations endpoint
func BenchmarkIntegrationHandlers_ListIntegrations(b *testing.B) {
	setup := NewTestSetup(&testing.T{})
	defer setup.Cleanup()

	for i := 0; i < 50; i++ {
		integration := &TestIntegration{
			ID:       fmt.Sprintf("int-%d", i),
			Name:     fmt.Sprintf("Integration %d", i),
			Type:     "messaging",
			Provider: "slack",
			Enabled:  true,
		}
		setup.DB.Create(integration)
	}

	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)
	setup.Router.Get("/api/integrations", integrationHandlers.ListIntegrations)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		setup.MakeRequest("GET", "/api/integrations?limit=20&offset=0", nil)
	}
}

// Test models for benchmark data
type TestSession struct {
	ID     string
	UserID string
}

type TestIntegration struct {
	ID       string
	Name     string
	Type     string
	Provider string
	Enabled  bool
}
