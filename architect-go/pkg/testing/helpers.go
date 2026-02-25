package testing

import (
	"context"
	"fmt"
	"log"
	"testing"
	"time"

	"gorm.io/gorm"

	"architect-go/pkg/config"
	"architect-go/pkg/database"
	"architect-go/pkg/repository"
)

// TestContext holds testing context and resources
type TestContext struct {
	T          *testing.T
	DB         *gorm.DB
	DBManager  *database.Manager
	Repos      *RepositorySet
	Ctx        context.Context
}

// RepositorySet holds all repository instances for testing
type RepositorySet struct {
	ProjectRepo       repository.ProjectRepository
	TaskRepo          repository.TaskRepository
	UserRepo          repository.UserRepository
	WorkerRepo        repository.WorkerRepository
	WorkerQueueRepo   repository.WorkerQueueRepository
	SessionRepo       repository.SessionRepository
	EventLogRepo      repository.EventLogRepository
	ErrorLogRepo      repository.ErrorLogRepository
	NotificationRepo  repository.NotificationRepository
	IntegrationRepo   repository.IntegrationRepository
}

// NewTestContext creates a new test context with database
func NewTestContext(t *testing.T) *TestContext {
	// Create test database config
	cfg := &config.Config{
		Database: config.DatabaseConfig{
			Host:           "localhost",
			Port:           5432,
			User:           "architect_test",
			Password:       "test",
			Database:       "architect_test",
			MaxConnections: 5,
			MinConnections: 1,
			SSLMode:        "disable",
		},
	}

	// Initialize database
	db, err := database.New(cfg)
	if err != nil {
		t.Fatalf("Failed to initialize test database: %v", err)
	}

	// Create database manager
	dbManager, err := database.NewManager(db.GetDB(), cfg)
	if err != nil {
		t.Fatalf("Failed to create database manager: %v", err)
	}

	// Start database manager
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := dbManager.Start(ctx); err != nil {
		t.Fatalf("Failed to start database manager: %v", err)
	}

	// Run migrations
	result := dbManager.RunMigrations()
	if !result.Success {
		t.Fatalf("Failed to run migrations: %v", result.Error)
	}

	// Create repositories
	repos := &RepositorySet{
		ProjectRepo:      repository.NewProjectRepository(db.GetDB()),
		TaskRepo:         repository.NewTaskRepository(db.GetDB()),
		UserRepo:         repository.NewUserRepository(db.GetDB()),
		WorkerRepo:       repository.NewWorkerRepository(db.GetDB()),
		WorkerQueueRepo:  repository.NewWorkerQueueRepository(db.GetDB()),
		SessionRepo:      repository.NewSessionRepository(db.GetDB()),
		EventLogRepo:     repository.NewEventLogRepository(db.GetDB()),
		ErrorLogRepo:     repository.NewErrorLogRepository(db.GetDB()),
		NotificationRepo: repository.NewNotificationRepository(db.GetDB()),
		IntegrationRepo:  repository.NewIntegrationRepository(db.GetDB()),
	}

	return &TestContext{
		T:         t,
		DB:        db.GetDB(),
		DBManager: dbManager,
		Repos:     repos,
		Ctx:       context.Background(),
	}
}

// Cleanup cleans up the test context
func (tc *TestContext) Cleanup() {
	// Clean up database
	if err := tc.DBManager.Stop(); err != nil {
		log.Printf("Failed to stop database manager: %v", err)
	}
}

// CleanupTables clears all test tables
func (tc *TestContext) CleanupTables() {
	tables := []string{
		"notifications",
		"sessions",
		"event_logs",
		"error_logs",
		"worker_queue",
		"workers",
		"tasks",
		"integrations",
		"users",
		"projects",
	}

	for _, table := range tables {
		if err := tc.DB.Exec(fmt.Sprintf("DELETE FROM %s", table)).Error; err != nil {
			tc.T.Logf("Failed to clean table %s: %v", table, err)
		}
	}
}

// AssertNoError asserts that err is nil
func (tc *TestContext) AssertNoError(err error, msg string) {
	if err != nil {
		tc.T.Errorf("%s: %v", msg, err)
	}
}

// AssertError asserts that err is not nil
func (tc *TestContext) AssertError(err error, msg string) {
	if err == nil {
		tc.T.Errorf("%s: expected error but got nil", msg)
	}
}

// AssertEqual asserts that expected equals actual
func (tc *TestContext) AssertEqual(expected interface{}, actual interface{}, msg string) {
	if expected != actual {
		tc.T.Errorf("%s: expected %v but got %v", msg, expected, actual)
	}
}

// AssertNotEqual asserts that expected does not equal actual
func (tc *TestContext) AssertNotEqual(expected interface{}, actual interface{}, msg string) {
	if expected == actual {
		tc.T.Errorf("%s: expected %v to not equal %v", msg, expected, actual)
	}
}

// AssertNil asserts that value is nil
func (tc *TestContext) AssertNil(value interface{}, msg string) {
	if value != nil {
		tc.T.Errorf("%s: expected nil but got %v", msg, value)
	}
}

// AssertNotNil asserts that value is not nil
func (tc *TestContext) AssertNotNil(value interface{}, msg string) {
	if value == nil {
		tc.T.Errorf("%s: expected non-nil value", msg)
	}
}

// Timeout returns a context with timeout
func (tc *TestContext) Timeout(d time.Duration) context.Context {
	ctx, _ := context.WithTimeout(tc.Ctx, d)
	return ctx
}
