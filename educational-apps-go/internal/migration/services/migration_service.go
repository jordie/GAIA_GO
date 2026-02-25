package services

import (
	"crypto/md5"
	"database/sql"
	"fmt"
	"io"
	"log"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"

	"github.com/architect/educational-apps/internal/migration/models"
)

// MigrationService handles data migration between databases
type MigrationService struct {
	sourceDB *sql.DB
	targetDB *gorm.DB
	config   *models.MigrationConfig
	status   *models.MigrationStatus
	logger   *log.Logger
}

// NewMigrationService creates a new migration service
func NewMigrationService(config *models.MigrationConfig) (*MigrationService, error) {
	logger := log.New(log.Writer(), "[MIGRATION] ", log.LstdFlags|log.Lshortfile)

	return &MigrationService{
		config: config,
		logger: logger,
	}, nil
}

// ConnectDatabases establishes connections to source and target databases
func (ms *MigrationService) ConnectDatabases() error {
	ms.logger.Println("Connecting to source database (SQLite)...")

	// Connect to SQLite
	sourceDB, err := sql.Open("sqlite3", ms.config.SourcePath)
	if err != nil {
		return fmt.Errorf("failed to connect to SQLite: %w", err)
	}

	if err := sourceDB.Ping(); err != nil {
		return fmt.Errorf("failed to ping SQLite: %w", err)
	}

	ms.sourceDB = sourceDB
	ms.logger.Println("✓ Connected to SQLite")

	ms.logger.Println("Connecting to target database (PostgreSQL)...")

	// Connect to PostgreSQL
	dsn := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		ms.config.TargetHost,
		ms.config.TargetPort,
		ms.config.TargetUser,
		ms.config.TargetPassword,
		ms.config.TargetDatabase,
	)

	targetDB, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return fmt.Errorf("failed to connect to PostgreSQL: %w", err)
	}

	ms.targetDB = targetDB
	ms.logger.Println("✓ Connected to PostgreSQL")

	return nil
}

// StartMigration initializes migration process
func (ms *MigrationService) StartMigration() (*models.MigrationStatus, error) {
	ms.status = &models.MigrationStatus{
		Status:      models.MigrationStatusInProgress,
		StartTime:   time.Now(),
		SourceDB:    "sqlite",
		TargetDB:    "postgres",
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	ms.logger.Printf("Starting migration (DryRun: %v)\n", ms.config.DryRun)

	return ms.status, nil
}

// MigrateAllTables migrates all supported tables
func (ms *MigrationService) MigrateAllTables() error {
	totalRecords := 0
	migratedRecords := 0
	failedRecords := 0

	for _, tableName := range models.SupportedTables {
		ms.logger.Printf("Migrating table: %s\n", tableName)

		rowsAffected, rowsFailed, err := ms.MigrateTable(tableName)
		if err != nil {
			ms.logger.Printf("⚠ Error migrating %s: %v\n", tableName, err)
			ms.status.ErrorMessage = fmt.Sprintf("Failed to migrate %s: %v", tableName, err)
			failedRecords += rowsFailed
			continue
		}

		totalRecords += rowsAffected + rowsFailed
		migratedRecords += rowsAffected

		ms.logger.Printf("✓ Migrated %s: %d records\n", tableName, rowsAffected)
	}

	ms.status.TotalRecords = totalRecords
	ms.status.MigratedRecords = migratedRecords
	ms.status.FailedRecords = failedRecords

	return nil
}

// MigrateTable migrates a single table
func (ms *MigrationService) MigrateTable(tableName string) (int, int, error) {
	start := time.Now()

	// Get row count from source
	var rowCount int64
	err := ms.sourceDB.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM %s", tableName)).Scan(&rowCount)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get row count: %w", err)
	}

	ms.logger.Printf("  Found %d rows in %s\n", rowCount, tableName)

	if rowCount == 0 {
		return 0, 0, nil
	}

	// Get column information from source
	rows, err := ms.sourceDB.Query(fmt.Sprintf("PRAGMA table_info(%s)", tableName))
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get table info: %w", err)
	}
	defer rows.Close()

	var columnNames []string
	for rows.Next() {
		var cid int
		var name string
		var dataType string
		var notnull int
		var dfltValue interface{}
		var pk int

		err := rows.Scan(&cid, &name, &dataType, &notnull, &dfltValue, &pk)
		if err == nil {
			columnNames = append(columnNames, name)
		}
	}

	// Build SELECT query
	columnList := ""
	for i, col := range columnNames {
		if i > 0 {
			columnList += ", "
		}
		columnList += col
	}

	selectQuery := fmt.Sprintf("SELECT %s FROM %s", columnList, tableName)

	// Process in batches
	migratedRows := 0
	failedRows := 0
	batchSize := ms.config.BatchSize
	if batchSize == 0 {
		batchSize = models.DefaultBatchSize
	}

	offset := 0
	for {
		sourceRows, err := ms.sourceDB.Query(
			fmt.Sprintf("%s LIMIT ? OFFSET ?", selectQuery),
			batchSize,
			offset,
		)
		if err != nil {
			return migratedRows, failedRows, fmt.Errorf("failed to query source: %w", err)
		}

		batchMigrated := 0

		for sourceRows.Next() {
			// Read row from source
			values := make([]interface{}, len(columnNames))
			valuePtrs := make([]interface{}, len(columnNames))
			for i := range columnNames {
				valuePtrs[i] = &values[i]
			}

			if err := sourceRows.Scan(valuePtrs...); err != nil {
				failedRows++
				continue
			}

			// Insert into target (unless dry-run)
			if !ms.config.DryRun {
				// Build INSERT statement
				placeholders := ""
				for i := range columnNames {
					if i > 0 {
						placeholders += ", "
					}
					placeholders += fmt.Sprintf("$%d", i+1)
				}

				insertQuery := fmt.Sprintf(
					"INSERT INTO %s (%s) VALUES (%s)",
					tableName,
					columnList,
					placeholders,
				)

				if err := ms.targetDB.Exec(insertQuery, values...).Error; err != nil {
					ms.logger.Printf("  ⚠ Failed to insert row: %v\n", err)
					failedRows++
					continue
				}
			}

			batchMigrated++
			migratedRows++
		}

		sourceRows.Close()

		if batchMigrated < batchSize {
			break
		}

		offset += batchSize
		ms.logger.Printf("  Processed %d/%d rows\n", migratedRows, rowCount)
	}

	duration := time.Since(start)
	ms.logger.Printf("  Completed in %v\n", duration)

	return migratedRows, failedRows, nil
}

// ValidateData validates data integrity after migration
func (ms *MigrationService) ValidateData() (map[string]bool, []string, error) {
	ms.logger.Println("\nValidating migrated data...")

	validations := make(map[string]bool)
	issues := make([]string, 0)

	for _, tableName := range models.SupportedTables {
		// Get counts
		var sourceCount int64
		ms.sourceDB.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM %s", tableName)).
			Scan(&sourceCount)

		var targetCount int64
		if err := ms.targetDB.Raw(
			fmt.Sprintf("SELECT COUNT(*) FROM %s", tableName),
		).Scan(&targetCount).Error; err != nil {
			issues = append(issues, fmt.Sprintf("%s: Failed to count target rows", tableName))
			validations[tableName] = false
			continue
		}

		// Validate counts
		if sourceCount == targetCount {
			ms.logger.Printf("✓ %s: %d rows (matched)\n", tableName, sourceCount)
			validations[tableName] = true
		} else {
			ms.logger.Printf("✗ %s: Source %d, Target %d (MISMATCH)\n",
				tableName, sourceCount, targetCount)
			validations[tableName] = false
			issues = append(issues, fmt.Sprintf(
				"%s: Source %d rows, Target %d rows",
				tableName, sourceCount, targetCount))
		}
	}

	return validations, issues, nil
}

// CalculateChecksum calculates checksum for a table
func (ms *MigrationService) CalculateChecksum(db interface{}, tableName string) (string, error) {
	var query string
	var rows *sql.Rows
	var err error

	hash := md5.New()

	if sqlDB, ok := db.(*sql.DB); ok {
		// SQLite
		query = fmt.Sprintf("SELECT * FROM %s ORDER BY rowid", tableName)
		rows, err = sqlDB.Query(query)
	} else if gormDB, ok := db.(*gorm.DB); ok {
		// PostgreSQL
		query = fmt.Sprintf("SELECT * FROM %s ORDER BY id", tableName)
		rows, err = gormDB.Raw(query).Rows()
	} else {
		return "", fmt.Errorf("unsupported database type")
	}

	if err != nil {
		return "", err
	}
	defer rows.Close()

	for rows.Next() {
		cols, _ := rows.Columns()
		values := make([]interface{}, len(cols))
		valuePtrs := make([]interface{}, len(cols))
		for i := range cols {
			valuePtrs[i] = &values[i]
		}
		rows.Scan(valuePtrs...)

		for _, val := range values {
			io.WriteString(hash, fmt.Sprintf("%v", val))
		}
	}

	return fmt.Sprintf("%x", hash.Sum(nil)), nil
}

// CompleteM migration marks migration as completed
func (ms *MigrationService) CompleteMigration() *models.MigrationStatus {
	ms.status.Status = models.MigrationStatusCompleted
	ms.status.EndTime = time.Now()
	ms.status.UpdatedAt = time.Now()

	duration := ms.status.EndTime.Sub(ms.status.StartTime)
	ms.logger.Printf("\n✓ Migration completed in %v\n", duration)
	ms.logger.Printf("  Total records: %d\n", ms.status.TotalRecords)
	ms.logger.Printf("  Migrated: %d\n", ms.status.MigratedRecords)
	ms.logger.Printf("  Failed: %d\n", ms.status.FailedRecords)

	return ms.status
}

// FailMigration marks migration as failed
func (ms *MigrationService) FailMigration(err error) *models.MigrationStatus {
	ms.status.Status = models.MigrationStatusFailed
	ms.status.ErrorMessage = err.Error()
	ms.status.EndTime = time.Now()
	ms.status.UpdatedAt = time.Now()

	ms.logger.Printf("\n✗ Migration failed: %v\n", err)

	return ms.status
}

// CloseConnections closes all database connections
func (ms *MigrationService) CloseConnections() error {
	if ms.sourceDB != nil {
		if err := ms.sourceDB.Close(); err != nil {
			ms.logger.Printf("Error closing SQLite: %v\n", err)
		}
	}

	// Note: GORM handles its own connection closing
	return nil
}

// GenerateMigrationReport creates a summary report
func (ms *MigrationService) GenerateMigrationReport() *models.MigrationSummaryResponse {
	validations, issues, _ := ms.ValidateData()

	tables := make([]string, 0)
	for table := range validations {
		tables = append(tables, table)
	}

	recommendations := []string{}
	if ms.status.FailedRecords > 0 {
		recommendations = append(recommendations,
			fmt.Sprintf("Review and fix %d failed records", ms.status.FailedRecords))
	}

	if len(issues) > 0 {
		recommendations = append(recommendations, "Verify data integrity on mismatched tables")
	}

	duration := 0
	if !ms.status.EndTime.IsZero() {
		duration = int(ms.status.EndTime.Sub(ms.status.StartTime).Seconds())
	}

	return &models.MigrationSummaryResponse{
		MigrationID:     ms.status.ID,
		Status:          ms.status.Status,
		TotalRecords:    ms.status.TotalRecords,
		MigratedRecords: ms.status.MigratedRecords,
		FailedRecords:   ms.status.FailedRecords,
		Duration:        duration,
		TablesProcessed: tables,
		Validations:     validations,
		IssuesFound:     issues,
		Recommendations: recommendations,
	}
}
