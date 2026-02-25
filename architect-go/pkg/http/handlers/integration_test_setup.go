package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"sync/atomic"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
	"architect-go/pkg/services"
)

// dbCounter ensures each test gets a unique in-memory database name
var dbCounter uint64

// TestSetup contains all test dependencies
type TestSetup struct {
	DB              *gorm.DB
	Router          chi.Router
	RepoRegistry    *repository.Registry
	ServiceRegistry *services.Registry
	T               *testing.T
}

// NewTestSetup creates a new test setup with in-memory SQLite database
func NewTestSetup(t *testing.T) *TestSetup {
	// Each test gets its own unique in-memory database to avoid UNIQUE constraint conflicts
	dbID := atomic.AddUint64(&dbCounter, 1)
	dsn := fmt.Sprintf("file:testdb_%d_%s?mode=memory&cache=shared", dbID, uuid.New().String())
	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{})
	require.NoError(t, err, "failed to open test database")

	// Auto-migrate models
	err = db.AutoMigrate(
		&models.Project{},
		&models.Task{},
		&models.Worker{},
		&models.WorkerQueue{},
		&models.User{},
		&models.Session{},
		&models.EventLog{},
		&models.ErrorLog{},
		&models.Notification{},
		&models.Integration{},
		&models.AuditLog{},
	)
	require.NoError(t, err, "failed to migrate test database")

	// Create repository registry
	repoRegistry := repository.NewRegistry(db)

	// Create service registry
	serviceRegistry := services.NewRegistry(repoRegistry)

	// Create router
	router := chi.NewRouter()

	return &TestSetup{
		DB:              db,
		Router:          router,
		RepoRegistry:    repoRegistry,
		ServiceRegistry: serviceRegistry,
		T:               t,
	}
}

// MakeRequest makes an HTTP request to the test server
func (ts *TestSetup) MakeRequest(method, path string, body interface{}) *httptest.ResponseRecorder {
	var reqBody []byte
	var err error

	if body != nil {
		reqBody, err = json.Marshal(body)
		require.NoError(ts.T, err, "failed to marshal request body")
	}

	req := httptest.NewRequest(method, path, bytes.NewReader(reqBody))
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	// Add request ID header
	req.Header.Set("X-Request-ID", "test-request-id")

	w := httptest.NewRecorder()
	ts.Router.ServeHTTP(w, req)

	return w
}

// DecodeResponse decodes JSON response body
func (ts *TestSetup) DecodeResponse(recorder *httptest.ResponseRecorder, v interface{}) error {
	return json.Unmarshal(recorder.Body.Bytes(), v)
}

// CreateTestUser creates a test user in the database
func (ts *TestSetup) CreateTestUser(id, name, email string) *models.User {
	user := &models.User{
		ID:       id,
		Username: name,
		Email:    email,
	}
	err := ts.DB.Create(user).Error
	require.NoError(ts.T, err, "failed to create test user")
	return user
}

// CreateTestProject creates a test project in the database
func (ts *TestSetup) CreateTestProject(id, name, description string) *models.Project {
	project := &models.Project{
		ID:          id,
		Name:        name,
		Description: description,
		Status:      "active",
	}
	err := ts.DB.Create(project).Error
	require.NoError(ts.T, err, "failed to create test project")
	return project
}

// CreateTestEventLog creates a test event log in the database
func (ts *TestSetup) CreateTestEventLog(eventType, source, userID string) *models.EventLog {
	event := &models.EventLog{
		ID:        uuid.New().String(),
		EventType: eventType,
		Source:    source,
		UserID:    userID,
		Message:   "Test event",
	}
	err := ts.DB.Create(event).Error
	require.NoError(ts.T, err, "failed to create test event log")
	return event
}

// CreateTestErrorLog creates a test error log in the database
func (ts *TestSetup) CreateTestErrorLog(errorType, severity, source string) *models.ErrorLog {
	errorLog := &models.ErrorLog{
		ID:        uuid.New().String(),
		ErrorType: errorType,
		Severity:  severity,
		Source:    source,
		Message:   "Test error",
	}
	err := ts.DB.Create(errorLog).Error
	require.NoError(ts.T, err, "failed to create test error log")
	return errorLog
}

// CreateTestTask creates a test task in the database
func (ts *TestSetup) CreateTestTask(id, projectID, title, status string) *models.Task {
	task := &models.Task{
		ID:        id,
		ProjectID: projectID,
		Title:     title,
		Status:    status,
	}
	err := ts.DB.Create(task).Error
	require.NoError(ts.T, err, "failed to create test task")
	return task
}

// CreateTestNotification creates a test notification in the database
func (ts *TestSetup) CreateTestNotification(userID, title, notificationType string) *models.Notification {
	notification := &models.Notification{
		ID:     uuid.New().String(),
		UserID: userID,
		Title:  title,
		Type:   notificationType,
	}
	err := ts.DB.Create(notification).Error
	require.NoError(ts.T, err, "failed to create test notification")
	return notification
}

// AssertResponseStatus asserts that response status code matches expected
func (ts *TestSetup) AssertResponseStatus(recorder *httptest.ResponseRecorder, expectedStatus int) {
	require.Equal(ts.T, expectedStatus, recorder.Code,
		"expected status %d but got %d: %s", expectedStatus, recorder.Code, recorder.Body.String())
}

// AssertResponseError asserts that response contains error message
func (ts *TestSetup) AssertResponseError(recorder *httptest.ResponseRecorder, expectedErrorMsg string) {
	var errorResponse map[string]interface{}
	err := ts.DecodeResponse(recorder, &errorResponse)
	require.NoError(ts.T, err, "failed to decode error response")
	require.Contains(ts.T, errorResponse["error"].(string), expectedErrorMsg)
}

// Cleanup cleans up test resources
func (ts *TestSetup) Cleanup() {
	sqlDB, err := ts.DB.DB()
	if err == nil {
		sqlDB.Close()
	}
}
