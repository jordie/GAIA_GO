package handlers

import (
	"net/http"
	"strconv"

	"github.com/architect/educational-apps/internal/migration/models"
	"github.com/architect/educational-apps/internal/migration/services"
	"github.com/gin-gonic/gin"
)

// StartMigration initiates a migration from SQLite to PostgreSQL
// POST /api/v1/migration/start
func StartMigration(c *gin.Context) {
	var req models.MigrationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Create migration config from request
	config := &models.MigrationConfig{
		SourceType:     "sqlite",
		SourcePath:     req.SourceDBPath,
		TargetType:     "postgres",
		TargetHost:     req.TargetDBHost,
		TargetPort:     req.TargetDBPort,
		TargetDatabase: req.TargetDBName,
		TargetUser:     req.TargetDBUser,
		TargetPassword: req.TargetDBPassword,
		DryRun:         req.DryRun,
		SkipValidation: req.SkipValidation,
		BatchSize:      1000,
		EnableLogging:  true,
		LogLevel:       "info",
	}

	// Create migration service
	migrationService, err := services.NewMigrationService(config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Connect to databases
	if err := migrationService.ConnectDatabases(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Start migration
	_, err = migrationService.StartMigration()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Execute migration
	if err := migrationService.MigrateAllTables(); err != nil {
		failStatus := migrationService.FailMigration(err)
		c.JSON(http.StatusInternalServerError, failStatus)
		return
	}

	// Validate data (unless skipped)
	if !req.SkipValidation {
		validations, issues, err := migrationService.ValidateData()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		// Check for validation failures
		for _, isValid := range validations {
			if !isValid {
				c.JSON(http.StatusBadRequest, gin.H{
					"error":       "Data validation failed",
					"issues":      issues,
					"validations": validations,
				})
				return
			}
		}
	}

	// Complete migration
	finalStatus := migrationService.CompleteMigration()

	// Close connections
	migrationService.CloseConnections()

	c.JSON(http.StatusOK, finalStatus)
}

// GetMigrationStatus returns the status of a migration
// GET /api/v1/migration/:id/status
func GetMigrationStatus(c *gin.Context) {
	// In a real implementation, migrations would be stored in a database
	// For now, return a placeholder response
	migrationID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"migration_id": migrationID,
		"message":      "Migration status tracking requires database storage. Implement MigrationStatus persistence.",
	})
}

// GetMigrationSummary returns a summary of migration results
// GET /api/v1/migration/:id/summary
func GetMigrationSummary(c *gin.Context) {
	migrationID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"migration_id": migrationID,
		"message":      "Migration summary tracking requires database storage. Implement MigrationSummaryResponse persistence.",
	})
}

// RollbackMigration rolls back a completed migration
// POST /api/v1/migration/:id/rollback
func RollbackMigration(c *gin.Context) {
	migrationID, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid migration id"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"migration_id": migrationID,
		"status":       "Rollback initiated",
		"message":      "Rollback implementation requires transaction history. Implement rollback logic.",
	})
}

// ValidateMigration validates data integrity without performing migration
// POST /api/v1/migration/validate
func ValidateMigration(c *gin.Context) {
	var req models.MigrationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Create migration config
	config := &models.MigrationConfig{
		SourceType:     "sqlite",
		SourcePath:     req.SourceDBPath,
		TargetType:     "postgres",
		TargetHost:     req.TargetDBHost,
		TargetPort:     req.TargetDBPort,
		TargetDatabase: req.TargetDBName,
		TargetUser:     req.TargetDBUser,
		TargetPassword: req.TargetDBPassword,
		DryRun:         true, // Always dry-run for validation
		SkipValidation: false,
		BatchSize:      1000,
		EnableLogging:  true,
		LogLevel:       "info",
	}

	// Create migration service
	migrationService, err := services.NewMigrationService(config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Connect to databases
	if err := migrationService.ConnectDatabases(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Validate data
	validations, issues, err := migrationService.ValidateData()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	migrationService.CloseConnections()

	c.JSON(http.StatusOK, gin.H{
		"validations": validations,
		"issues":      issues,
		"valid":       len(issues) == 0,
	})
}

// DryRunMigration performs a dry-run migration without writing data
// POST /api/v1/migration/dry-run
func DryRunMigration(c *gin.Context) {
	var req models.MigrationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Create migration config with dry-run enabled
	config := &models.MigrationConfig{
		SourceType:     "sqlite",
		SourcePath:     req.SourceDBPath,
		TargetType:     "postgres",
		TargetHost:     req.TargetDBHost,
		TargetPort:     req.TargetDBPort,
		TargetDatabase: req.TargetDBName,
		TargetUser:     req.TargetDBUser,
		TargetPassword: req.TargetDBPassword,
		DryRun:         true, // Dry-run enabled
		SkipValidation: req.SkipValidation,
		BatchSize:      1000,
		EnableLogging:  true,
		LogLevel:       "info",
	}

	// Create migration service
	migrationService, err := services.NewMigrationService(config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Connect to databases
	if err := migrationService.ConnectDatabases(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Start migration
	_, err = migrationService.StartMigration()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Execute migration (dry-run - no actual writes)
	if err := migrationService.MigrateAllTables(); err != nil {
		failStatus := migrationService.FailMigration(err)
		c.JSON(http.StatusInternalServerError, failStatus)
		return
	}

	// Validate data
	validations, issues, err := migrationService.ValidateData()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	migrationService.CloseConnections()

	summary := migrationService.GenerateMigrationReport()
	summary.Validations = validations
	summary.IssuesFound = issues

	c.JSON(http.StatusOK, summary)
}

// GetMigrationSchema returns the schema mapping for a table
// GET /api/v1/migration/schema/:table
func GetMigrationSchema(c *gin.Context) {
	tableName := c.Param("table")

	// Check if table is supported
	supported := false
	for _, t := range models.SupportedTables {
		if t == tableName {
			supported = true
			break
		}
	}

	if !supported {
		c.JSON(http.StatusNotFound, gin.H{"error": "table not found in supported tables"})
		return
	}

	// Return schema info (simplified)
	c.JSON(http.StatusOK, gin.H{
		"table":           tableName,
		"supported":       true,
		"type_mapping":    models.SQLiteToPostgresTypeMap,
		"total_tables":    len(models.SupportedTables),
		"supported_types": len(models.SQLiteToPostgresTypeMap),
	})
}

// ListSupportedTables returns all tables that can be migrated
// GET /api/v1/migration/tables
func ListSupportedTables(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"supported_tables": models.SupportedTables,
		"total_count":      len(models.SupportedTables),
	})
}
