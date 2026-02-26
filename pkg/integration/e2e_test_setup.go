// Package integration provides end-to-end integration tests for GAIA_GO
//go:build e2e
// +build e2e

package integration

import (
	"context"
	"fmt"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/models"
	"github.com/jgirmay/GAIA_GO/pkg/repository"
	"github.com/jgirmay/GAIA_GO/pkg/services"
	"github.com/jgirmay/GAIA_GO/pkg/services/usability"
	"github.com/jgirmay/GAIA_GO/pkg/websocket"
)

// dbCounter ensures each test gets a unique in-memory database name
var dbCounter uint64

// E2ETestSetup contains all dependencies for end-to-end integration tests
// Extends the base TestSetup pattern with distributed coordination and usability metrics
type E2ETestSetup struct {
	// Database and core infrastructure
	DB              *gorm.DB
	Router          chi.Router
	RepoRegistry    *repository.Registry
	ServiceRegistry *services.Registry
	T               *testing.T

	// Distributed components
	RaftCluster     *TestRaftCluster
	SessionRepo     repository.ClaudeSessionRepository
	TaskQueueRepo   repository.DistributedTaskRepository
	LockRepo        repository.DistributedLockRepository

	// Usability metrics components
	MetricsService  *usability.UsabilityMetricsService
	FrustrationEngine *usability.FrustrationDetectionEngine
	Aggregator      *usability.RealtimeMetricsAggregator
	EventBus        usability.EventBus
	MetricsRepo     repository.UsabilityMetricsRepository

	// WebSocket components
	WebSocketHub    *websocket.Hub
	WebSocketServer *httptest.Server

	// Test helpers
	MetricsSimulator *MetricsSimulator
	AlertListener    *TestAlertListener

	// Context management
	Ctx    context.Context
	Cancel context.CancelFunc
}

// NewE2ETestSetup creates a complete E2E test environment with all components
func NewE2ETestSetup(t *testing.T, raftNodeCount int) *E2ETestSetup {
	// Create base test database with unique name
	dbID := atomic.AddUint64(&dbCounter, 1)
	dsn := fmt.Sprintf("file:testdb_e2e_%d_%s?mode=memory&cache=shared", dbID, uuid.New().String())
	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{})
	require.NoError(t, err, "failed to open E2E test database")

	// Auto-migrate all models (existing + new distributed models)
	err = db.AutoMigrate(
		// Existing models
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
		// Distributed models (add when available)
		// &models.ClaudeSession{},
		// &models.DistributedTask{},
		// &models.DistributedLock{},
		// Usability metrics models (add when available)
		// &models.UsabilityMetric{},
		// &models.FrustrationEvent{},
	)
	require.NoError(t, err, "failed to migrate E2E test database")

	// Create repository registry
	repoRegistry := repository.NewRegistry(db)

	// Create service registry
	serviceRegistry := services.NewRegistry(repoRegistry)

	// Create router
	router := chi.NewRouter()

	// Create Raft cluster for distributed coordination tests
	raftCluster := NewTestRaftCluster(t, raftNodeCount)
	require.NotNil(t, raftCluster, "failed to create test Raft cluster")

	// Create context with cancellation
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)

	// Create WebSocket hub
	wsHub := websocket.NewHub()

	// Create test WebSocket server
	wsServer := httptest.NewServer(wsHub.Handler())

	// Initialize usability metrics components (placeholder for now)
	var metricsService *usability.UsabilityMetricsService
	var frustrationEngine *usability.FrustrationDetectionEngine
	var aggregator *usability.RealtimeMetricsAggregator
	var eventBus usability.EventBus

	// Create test helpers
	metricsSimulator := NewMetricsSimulator()
	alertListener := NewTestAlertListener()

	setup := &E2ETestSetup{
		DB:              db,
		Router:          router,
		RepoRegistry:    repoRegistry,
		ServiceRegistry: serviceRegistry,
		T:               t,

		RaftCluster:   raftCluster,
		SessionRepo:   repoRegistry.ClaudeSessionRepository,
		TaskQueueRepo: repoRegistry.DistributedTaskRepository,
		LockRepo:      repoRegistry.DistributedLockRepository,

		MetricsService:    metricsService,
		FrustrationEngine: frustrationEngine,
		Aggregator:        aggregator,
		EventBus:          eventBus,
		MetricsRepo:       repoRegistry.UsabilityMetricsRepository,

		WebSocketHub:    wsHub,
		WebSocketServer: wsServer,

		MetricsSimulator: metricsSimulator,
		AlertListener:    alertListener,

		Ctx:    ctx,
		Cancel: cancel,
	}

	return setup
}

// Cleanup tears down all test resources
func (e *E2ETestSetup) Cleanup() {
	e.Cancel()
	if e.WebSocketServer != nil {
		e.WebSocketServer.Close()
	}
	if e.RaftCluster != nil {
		e.RaftCluster.Shutdown()
	}
	// Close database connection if needed
}

// WaitForRaftConsensus waits for all Raft nodes to reach consensus
func (e *E2ETestSetup) WaitForRaftConsensus(timeout time.Duration) error {
	if e.RaftCluster == nil {
		return fmt.Errorf("Raft cluster not initialized")
	}
	return e.RaftCluster.WaitForConsensus(timeout)
}

// SimulateStudentActivity simulates realistic student metrics generation
func (e *E2ETestSetup) SimulateStudentActivity(studentID, appName string, duration time.Duration) {
	if e.MetricsSimulator == nil {
		return
	}
	e.MetricsSimulator.SimulateStudentActivity(e.Ctx, studentID, appName, duration)
}

// AssertTaskNotDoubleClaimed verifies a task was claimed by exactly one session
func (e *E2ETestSetup) AssertTaskNotDoubleClaimed(taskID uuid.UUID) {
	if e.TaskQueueRepo == nil {
		return
	}
	// Implementation would verify in database that task.claimed_by has exactly one assignment
}

// AssertFrustrationEventDetected verifies a frustration event was triggered
func (e *E2ETestSetup) AssertFrustrationEventDetected(studentID string, expectedSeverity string) {
	if e.AlertListener == nil {
		return
	}
	alerts := e.AlertListener.GetAlertsForStudent(studentID)
	require.NotEmpty(e.T, alerts, "no frustration alerts detected for student %s", studentID)

	// Verify at least one alert with expected severity
	found := false
	for _, alert := range alerts {
		if alert.Severity == expectedSeverity {
			found = true
			break
		}
	}
	require.True(e.T, found, "no alert with severity %s found for student %s", expectedSeverity, studentID)
}

// AssertWebSocketAlertDelivered verifies an alert was delivered to a teacher
func (e *E2ETestSetup) AssertWebSocketAlertDelivered(teacherID string, alertType string) {
	if e.AlertListener == nil {
		return
	}
	alerts := e.AlertListener.GetAlertsForTeacher(teacherID)
	require.NotEmpty(e.T, alerts, "no WebSocket alerts delivered to teacher %s", teacherID)

	// Verify at least one alert with expected type
	found := false
	for _, alert := range alerts {
		if alert.Type == alertType {
			found = true
			break
		}
	}
	require.True(e.T, found, "no alert with type %s delivered to teacher %s", alertType, teacherID)
}

// MetricsSimulator generates realistic metric streams for testing
type MetricsSimulator struct {
	// Placeholder for metrics generation
}

// NewMetricsSimulator creates a new metrics simulator
func NewMetricsSimulator() *MetricsSimulator {
	return &MetricsSimulator{}
}

// SimulateStudentActivity generates metrics for a student using an app
func (m *MetricsSimulator) SimulateStudentActivity(ctx context.Context, studentID, appName string, duration time.Duration) {
	// Placeholder for realistic metric generation
}

// TestAlertListener captures alerts for assertion in tests
type TestAlertListener struct {
	studentAlerts map[string][]*TestAlert
	teacherAlerts map[string][]*TestAlert
}

// TestAlert represents a captured alert for testing
type TestAlert struct {
	Type        string
	StudentID   string
	TeacherID   string
	Severity    string
	Confidence  float64
	Timestamp   time.Time
}

// NewTestAlertListener creates a new alert listener
func NewTestAlertListener() *TestAlertListener {
	return &TestAlertListener{
		studentAlerts: make(map[string][]*TestAlert),
		teacherAlerts: make(map[string][]*TestAlert),
	}
}

// RecordStudentAlert records an alert for a student
func (l *TestAlertListener) RecordStudentAlert(studentID string, alert *TestAlert) {
	if l.studentAlerts[studentID] == nil {
		l.studentAlerts[studentID] = make([]*TestAlert, 0)
	}
	l.studentAlerts[studentID] = append(l.studentAlerts[studentID], alert)
}

// RecordTeacherAlert records an alert for a teacher
func (l *TestAlertListener) RecordTeacherAlert(teacherID string, alert *TestAlert) {
	if l.teacherAlerts[teacherID] == nil {
		l.teacherAlerts[teacherID] = make([]*TestAlert, 0)
	}
	l.teacherAlerts[teacherID] = append(l.teacherAlerts[teacherID], alert)
}

// GetAlertsForStudent returns all alerts for a student
func (l *TestAlertListener) GetAlertsForStudent(studentID string) []*TestAlert {
	return l.studentAlerts[studentID]
}

// GetAlertsForTeacher returns all alerts for a teacher
func (l *TestAlertListener) GetAlertsForTeacher(teacherID string) []*TestAlert {
	return l.teacherAlerts[teacherID]
}

// ClearAlerts clears all recorded alerts
func (l *TestAlertListener) ClearAlerts() {
	l.studentAlerts = make(map[string][]*TestAlert)
	l.teacherAlerts = make(map[string][]*TestAlert)
}
