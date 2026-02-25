package services

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	_ "github.com/mattn/go-sqlite3"
	"github.com/architect/educational-apps/internal/migration/models"
)

// TestMigrationServiceCreation tests service creation
func TestMigrationServiceCreation(t *testing.T) {
	config := &models.MigrationConfig{
		SourceType:     "sqlite",
		SourcePath:     ":memory:",
		TargetType:     "postgres",
		TargetHost:     "localhost",
		TargetPort:     5432,
		TargetDatabase: "test_db",
		TargetUser:     "postgres",
		TargetPassword: "password",
		BatchSize:      1000,
	}

	service, err := NewMigrationService(config)
	if err != nil {
		t.Fatalf("Failed to create migration service: %v", err)
	}

	if service.config != config {
		t.Error("Service config not set correctly")
	}
}

// TestMigrationServiceStartStop tests service connection lifecycle
func TestMigrationServiceStartStop(t *testing.T) {
	// Create a temporary SQLite database for testing
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	config := &models.MigrationConfig{
		SourceType: "sqlite",
		SourcePath: dbPath,
		BatchSize:  100,
	}

	service, err := NewMigrationService(config)
	if err != nil {
		t.Fatalf("Failed to create migration service: %v", err)
	}

	// Note: We can't test PostgreSQL connection without a running instance
	// This test just verifies SQLite connection works
	if err := service.ConnectDatabases(); err != nil {
		// PostgreSQL connection may fail, but SQLite should succeed
		if service.sourceDB == nil {
			t.Fatalf("Failed to connect to SQLite: %v", err)
		}
	}

	// Clean up
	if err := service.CloseConnections(); err != nil {
		t.Logf("Warning: Failed to close connections: %v", err)
	}
}

// TestMigrationStatusTracking tests migration status lifecycle
func TestMigrationStatusTracking(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	config := &models.MigrationConfig{
		SourceType: "sqlite",
		SourcePath: dbPath,
		BatchSize:  100,
	}

	service, err := NewMigrationService(config)
	if err != nil {
		t.Fatalf("Failed to create migration service: %v", err)
	}

	// Test StartMigration
	status, err := service.StartMigration()
	if err != nil {
		t.Fatalf("Failed to start migration: %v", err)
	}

	if status.Status != models.MigrationStatusInProgress {
		t.Errorf("Expected status %s, got %s", models.MigrationStatusInProgress, status.Status)
	}

	if status.SourceDB != "sqlite" {
		t.Errorf("Expected source DB 'sqlite', got '%s'", status.SourceDB)
	}

	// Test CompleteMigration
	finalStatus := service.CompleteMigration()
	if finalStatus.Status != models.MigrationStatusCompleted {
		t.Errorf("Expected status %s, got %s", models.MigrationStatusCompleted, finalStatus.Status)
	}

	// Test FailMigration
	service.status = &models.MigrationStatus{
		Status:    models.MigrationStatusInProgress,
		StartTime: status.StartTime,
	}

	testErr := fmt.Errorf("test error")
	failedStatus := service.FailMigration(testErr)
	if failedStatus.Status != models.MigrationStatusFailed {
		t.Errorf("Expected status %s, got %s", models.MigrationStatusFailed, failedStatus.Status)
	}

	if failedStatus.ErrorMessage != testErr.Error() {
		t.Errorf("Expected error message '%s', got '%s'", testErr.Error(), failedStatus.ErrorMessage)
	}
}

// TestMigrationTableProcessing tests single table migration logic
func TestMigrationTableProcessing(t *testing.T) {
	// Create a temporary SQLite database with test data
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	// Create and populate test database
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		t.Fatalf("Failed to create SQLite database: %v", err)
	}
	defer db.Close()

	// Create users table with test data
	if _, err := db.Exec(`
		CREATE TABLE users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT NOT NULL UNIQUE,
			email TEXT,
			created_at TIMESTAMP
		)
	`); err != nil {
		t.Fatalf("Failed to create users table: %v", err)
	}

	// Insert test data
	testData := []struct {
		username string
		email    string
	}{
		{"user1", "user1@example.com"},
		{"user2", "user2@example.com"},
		{"user3", "user3@example.com"},
	}

	for _, data := range testData {
		if _, err := db.Exec(
			"INSERT INTO users (username, email) VALUES (?, ?)",
			data.username, data.email,
		); err != nil {
			t.Fatalf("Failed to insert test data: %v", err)
		}
	}

	if err := db.Close(); err != nil {
		t.Fatalf("Failed to close database: %v", err)
	}

	// Now test the migration service
	config := &models.MigrationConfig{
		SourceType:    "sqlite",
		SourcePath:    dbPath,
		DryRun:        true, // Dry-run mode
		BatchSize:     10,
		EnableLogging: false,
	}

	service, err := NewMigrationService(config)
	if err != nil {
		t.Fatalf("Failed to create migration service: %v", err)
	}

	if err := service.ConnectDatabases(); err != nil {
		t.Fatalf("Failed to connect to databases: %v", err)
	}
	defer service.CloseConnections()

	// Test MigrateTable (dry-run mode)
	migratedRows, failedRows, err := service.MigrateTable("users")
	if err != nil {
		t.Fatalf("Failed to migrate users table: %v", err)
	}

	expectedRows := int64(len(testData))
	if int64(migratedRows) != expectedRows {
		t.Errorf("Expected %d migrated rows, got %d", expectedRows, migratedRows)
	}

	if failedRows != 0 {
		t.Errorf("Expected 0 failed rows, got %d", failedRows)
	}
}

// TestCalculateChecksum tests checksum calculation
func TestCalculateChecksum(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	// Create test database
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		t.Fatalf("Failed to create SQLite database: %v", err)
	}

	// Create and populate test table
	if _, err := db.Exec(`
		CREATE TABLE test_checksums (
			id INTEGER PRIMARY KEY,
			value TEXT
		)
	`); err != nil {
		t.Fatalf("Failed to create test table: %v", err)
	}

	if _, err := db.Exec(
		"INSERT INTO test_checksums (id, value) VALUES (1, 'test')",
	); err != nil {
		t.Fatalf("Failed to insert test data: %v", err)
	}

	if err := db.Close(); err != nil {
		t.Fatalf("Failed to close database: %v", err)
	}

	// Test checksum calculation
	config := &models.MigrationConfig{
		SourceType: "sqlite",
		SourcePath: dbPath,
	}

	service, err := NewMigrationService(config)
	if err != nil {
		t.Fatalf("Failed to create migration service: %v", err)
	}

	if err := service.ConnectDatabases(); err != nil {
		t.Fatalf("Failed to connect to databases: %v", err)
	}
	defer service.CloseConnections()

	checksum, err := service.CalculateChecksum(service.sourceDB, "test_checksums")
	if err != nil {
		t.Fatalf("Failed to calculate checksum: %v", err)
	}

	if checksum == "" {
		t.Error("Checksum should not be empty")
	}

	// Verify checksum is consistent
	checksum2, err := service.CalculateChecksum(service.sourceDB, "test_checksums")
	if err != nil {
		t.Fatalf("Failed to calculate checksum second time: %v", err)
	}

	if checksum != checksum2 {
		t.Errorf("Checksums should be identical, got %s and %s", checksum, checksum2)
	}

	t.Logf("Generated checksum: %s", checksum)
}

// TestMigrationDryRun tests dry-run migration
func TestMigrationDryRun(t *testing.T) {
	if os.Getenv("SKIP_INTEGRATION_TESTS") != "" {
		t.Skip("Skipping integration test")
	}

	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test.db")

	// Create test database
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		t.Fatalf("Failed to create SQLite database: %v", err)
	}

	// Create test table
	if _, err := db.Exec(`
		CREATE TABLE dry_run_test (
			id INTEGER PRIMARY KEY,
			name TEXT
		)
	`); err != nil {
		t.Fatalf("Failed to create test table: %v", err)
	}

	// Insert test data
	for i := 1; i <= 5; i++ {
		if _, err := db.Exec(
			"INSERT INTO dry_run_test (id, name) VALUES (?, ?)",
			i, fmt.Sprintf("item%d", i),
		); err != nil {
			t.Fatalf("Failed to insert test data: %v", err)
		}
	}

	if err := db.Close(); err != nil {
		t.Fatalf("Failed to close database: %v", err)
	}

	// Run migration in dry-run mode
	config := &models.MigrationConfig{
		SourceType:    "sqlite",
		SourcePath:    dbPath,
		DryRun:        true,
		BatchSize:     2,
		EnableLogging: false,
	}

	service, err := NewMigrationService(config)
	if err != nil {
		t.Fatalf("Failed to create migration service: %v", err)
	}

	if err := service.ConnectDatabases(); err != nil {
		t.Fatalf("Failed to connect to databases: %v", err)
	}
	defer service.CloseConnections()

	// Test dry-run migration
	if _, err := service.StartMigration(); err != nil {
		t.Fatalf("Failed to start migration: %v", err)
	}

	// Note: MigrateAllTables would try to migrate all tables in SupportedTables
	// For dry-run testing with a single table, we test MigrateTable directly
	migratedRows, failedRows, err := service.MigrateTable("dry_run_test")
	if err != nil {
		t.Fatalf("Failed to migrate table: %v", err)
	}

	if migratedRows != 5 {
		t.Errorf("Expected 5 migrated rows, got %d", migratedRows)
	}

	if failedRows != 0 {
		t.Errorf("Expected 0 failed rows, got %d", failedRows)
	}

	finalStatus := service.CompleteMigration()
	if finalStatus.Status != models.MigrationStatusCompleted {
		t.Errorf("Expected status COMPLETED, got %s", finalStatus.Status)
	}
}

// TestSupportedTables verifies all supported tables are defined
func TestSupportedTables(t *testing.T) {
	if len(models.SupportedTables) == 0 {
		t.Error("No supported tables defined")
	}

	// Check for required tables
	requiredTables := []string{
		"users",
		"user_xp",
		"user_streak",
		"achievement",
		"user_achievement",
	}

	for _, required := range requiredTables {
		found := false
		for _, supported := range models.SupportedTables {
			if supported == required {
				found = true
				break
			}
		}

		if !found {
			t.Errorf("Required table '%s' not in supported tables", required)
		}
	}

	t.Logf("Total supported tables: %d", len(models.SupportedTables))
}

// TestTypeMapping verifies SQLite to PostgreSQL type mapping
func TestTypeMapping(t *testing.T) {
	if len(models.SQLiteToPostgresTypeMap) == 0 {
		t.Error("No type mappings defined")
	}

	// Check for required type mappings
	requiredTypes := []string{
		"INTEGER",
		"TEXT",
		"REAL",
		"BOOLEAN",
		"TIMESTAMP",
	}

	for _, required := range requiredTypes {
		if _, exists := models.SQLiteToPostgresTypeMap[required]; !exists {
			t.Errorf("Required type mapping '%s' not found", required)
		}
	}

	t.Logf("Total type mappings: %d", len(models.SQLiteToPostgresTypeMap))
}

// BenchmarkMigrateTable benchmarks single table migration
func BenchmarkMigrateTable(b *testing.B) {
	if os.Getenv("SKIP_BENCHMARKS") != "" {
		b.Skip("Skipping benchmark")
	}

	tmpDir := b.TempDir()
	dbPath := filepath.Join(tmpDir, "bench.db")

	// Create and populate test database
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		b.Fatalf("Failed to create SQLite database: %v", err)
	}

	// Create test table
	if _, err := db.Exec(`
		CREATE TABLE bench_test (
			id INTEGER PRIMARY KEY,
			data TEXT
		)
	`); err != nil {
		b.Fatalf("Failed to create test table: %v", err)
	}

	// Insert benchmark data (1000 rows)
	for i := 1; i <= 1000; i++ {
		if _, err := db.Exec(
			"INSERT INTO bench_test (id, data) VALUES (?, ?)",
			i, fmt.Sprintf("data_%d", i),
		); err != nil {
			b.Fatalf("Failed to insert benchmark data: %v", err)
		}
	}

	db.Close()

	// Setup migration service
	config := &models.MigrationConfig{
		SourceType:    "sqlite",
		SourcePath:    dbPath,
		DryRun:        true,
		BatchSize:     100,
		EnableLogging: false,
	}

	service, err := NewMigrationService(config)
	if err != nil {
		b.Fatalf("Failed to create migration service: %v", err)
	}

	if err := service.ConnectDatabases(); err != nil {
		b.Fatalf("Failed to connect to databases: %v", err)
	}
	defer service.CloseConnections()

	// Run benchmark
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _, err := service.MigrateTable("bench_test")
		if err != nil {
			b.Fatalf("Migration failed: %v", err)
		}
	}
}
