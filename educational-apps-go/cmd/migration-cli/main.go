package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/architect/educational-apps/internal/migration/models"
	"github.com/architect/educational-apps/internal/migration/services"
)

func main() {
	// Define command-line flags
	mode := flag.String("mode", "migrate", "Operation mode: migrate, validate, dry-run, rollback, list-tables")
	sourceDB := flag.String("source", "", "Path to source SQLite database")
	targetHost := flag.String("target-host", "localhost", "Target PostgreSQL host")
	targetPort := flag.Int("target-port", 5432, "Target PostgreSQL port")
	targetDB := flag.String("target-db", "educational_apps", "Target PostgreSQL database name")
	targetUser := flag.String("target-user", "postgres", "Target PostgreSQL user")
	targetPass := flag.String("target-pass", "", "Target PostgreSQL password")
	dryRun := flag.Bool("dry-run", false, "Run migration in dry-run mode (no actual writes)")
	skipValidation := flag.Bool("skip-validation", false, "Skip data validation after migration")
	verbose := flag.Bool("verbose", true, "Enable verbose logging")
	help := flag.Bool("help", false, "Show help message")

	flag.Parse()

	if *help {
		showHelp()
		return
	}

	// Handle mode: list-tables
	if strings.ToLower(*mode) == "list-tables" {
		listSupportedTables()
		return
	}

	// Validate required parameters for other modes
	if *sourceDB == "" {
		log.Fatal("Error: --source is required")
	}

	// Create migration config
	config := &models.MigrationConfig{
		SourceType:     "sqlite",
		SourcePath:     *sourceDB,
		TargetType:     "postgres",
		TargetHost:     *targetHost,
		TargetPort:     *targetPort,
		TargetDatabase: *targetDB,
		TargetUser:     *targetUser,
		TargetPassword: *targetPass,
		DryRun:         *dryRun,
		SkipValidation: *skipValidation,
		BatchSize:      1000,
		EnableLogging:  *verbose,
		LogLevel:       "info",
	}

	// Create migration service
	migrationService, err := services.NewMigrationService(config)
	if err != nil {
		log.Fatalf("Failed to create migration service: %v", err)
	}

	// Connect to databases
	fmt.Println("Connecting to databases...")
	if err := migrationService.ConnectDatabases(); err != nil {
		log.Fatalf("Failed to connect to databases: %v", err)
	}
	defer migrationService.CloseConnections()

	// Execute requested operation
	switch strings.ToLower(*mode) {
	case "migrate":
		executeMigration(migrationService)

	case "validate":
		executeValidation(migrationService)

	case "dry-run":
		executeDryRun(migrationService)

	case "rollback":
		executeRollback(migrationService)

	default:
		log.Fatalf("Unknown mode: %s. Use --help for available modes.", *mode)
	}
}

func executeMigration(ms *services.MigrationService) {
	fmt.Println("\n========================================")
	fmt.Println("Starting SQLite → PostgreSQL Migration")
	fmt.Println("========================================\n")

	// Start migration
	fmt.Println("1. Initializing migration...")
	status, err := ms.StartMigration()
	if err != nil {
		log.Fatalf("Failed to start migration: %v", err)
	}
	fmt.Printf("   Migration ID: %d\n", status.ID)
	fmt.Printf("   Start Time: %v\n\n", status.StartTime)

	// Migrate tables
	fmt.Println("2. Migrating data...")
	if err := ms.MigrateAllTables(); err != nil {
		failStatus := ms.FailMigration(err)
		fmt.Printf("   ✗ Migration failed!\n")
		fmt.Printf("   Error: %v\n", failStatus.ErrorMessage)
		os.Exit(1)
	}

	// Validate data
	fmt.Println("\n3. Validating data integrity...")
	validations, issues, err := ms.ValidateData()
	if err != nil {
		log.Fatalf("Failed to validate data: %v", err)
	}

	allValid := true
	for table, valid := range validations {
		if valid {
			fmt.Printf("   ✓ %s: valid\n", table)
		} else {
			fmt.Printf("   ✗ %s: MISMATCH\n", table)
			allValid = false
		}
	}

	if !allValid && len(issues) > 0 {
		fmt.Println("\n   Issues found:")
		for _, issue := range issues {
			fmt.Printf("   - %s\n", issue)
		}
		_ = ms.FailMigration(fmt.Errorf("validation failed"))
		os.Exit(1)
	}

	// Complete migration
	fmt.Println("\n4. Finalizing migration...")
	finalStatus := ms.CompleteMigration()

	// Print summary
	fmt.Println("\n========================================")
	fmt.Println("Migration Summary")
	fmt.Println("========================================")
	fmt.Printf("Status:            %s\n", finalStatus.Status)
	fmt.Printf("Total Records:     %d\n", finalStatus.TotalRecords)
	fmt.Printf("Migrated Records:  %d\n", finalStatus.MigratedRecords)
	fmt.Printf("Failed Records:    %d\n", finalStatus.FailedRecords)
	fmt.Printf("Duration:          %v\n", finalStatus.EndTime.Sub(finalStatus.StartTime))
	fmt.Println("========================================\n")

	fmt.Println("✓ Migration completed successfully!")
}

func executeValidation(ms *services.MigrationService) {
	fmt.Println("\n========================================")
	fmt.Println("Data Validation Check")
	fmt.Println("========================================\n")

	validations, issues, err := ms.ValidateData()
	if err != nil {
		log.Fatalf("Failed to validate data: %v", err)
	}

	fmt.Println("Validation Results:")
	for table, valid := range validations {
		if valid {
			fmt.Printf("  ✓ %s: valid\n", table)
		} else {
			fmt.Printf("  ✗ %s: MISMATCH\n", table)
		}
	}

	if len(issues) > 0 {
		fmt.Println("\nIssues Found:")
		for _, issue := range issues {
			fmt.Printf("  - %s\n", issue)
		}
		os.Exit(1)
	}

	fmt.Println("\n✓ All data is valid!")
}

func executeDryRun(ms *services.MigrationService) {
	fmt.Println("\n========================================")
	fmt.Println("Dry-Run Migration (No Data Written)")
	fmt.Println("========================================\n")

	// Start migration
	fmt.Println("1. Initializing dry-run...")
	_, err := ms.StartMigration()
	if err != nil {
		log.Fatalf("Failed to start migration: %v", err)
	}

	// Migrate tables (in dry-run mode)
	fmt.Println("2. Simulating data migration...")
	if err := ms.MigrateAllTables(); err != nil {
		log.Fatalf("Dry-run failed: %v", err)
	}

	// Generate report
	fmt.Println("\n3. Generating migration report...")
	report := ms.GenerateMigrationReport()

	// Print report
	fmt.Println("\n========================================")
	fmt.Println("Migration Report")
	fmt.Println("========================================")
	fmt.Printf("Status:              %s\n", report.Status)
	fmt.Printf("Total Records:       %d\n", report.TotalRecords)
	fmt.Printf("Migrated Records:    %d\n", report.MigratedRecords)
	fmt.Printf("Failed Records:      %d\n", report.FailedRecords)
	fmt.Printf("Duration:            %d seconds\n", report.Duration)
	fmt.Printf("Tables Processed:    %d\n", len(report.TablesProcessed))

	if len(report.Recommendations) > 0 {
		fmt.Println("\nRecommendations:")
		for _, rec := range report.Recommendations {
			fmt.Printf("  - %s\n", rec)
		}
	}

	fmt.Println("========================================\n")

	if report.Status == "completed" && len(report.IssuesFound) == 0 {
		fmt.Println("✓ Dry-run completed successfully!")
		fmt.Println("  Ready to perform full migration.")
	} else if len(report.IssuesFound) > 0 {
		fmt.Println("✗ Dry-run found issues:")
		for _, issue := range report.IssuesFound {
			fmt.Printf("  - %s\n", issue)
		}
		os.Exit(1)
	}
}

func executeRollback(ms *services.MigrationService) {
	fmt.Println("\n========================================")
	fmt.Println("Rollback Not Yet Implemented")
	fmt.Println("========================================\n")

	fmt.Println("Rollback functionality requires transaction history.")
	fmt.Println("For now, use database backups to restore.")
	fmt.Println("\nPlanned rollback features:")
	fmt.Println("  - Transaction-based rollback")
	fmt.Println("  - Truncate target tables")
	fmt.Println("  - Restore from backup")

	os.Exit(1)
}

func listSupportedTables() {
	fmt.Println("\n========================================")
	fmt.Println("Supported Tables for Migration")
	fmt.Println("========================================\n")

	fmt.Printf("Total Tables: %d\n\n", len(models.SupportedTables))

	for i, table := range models.SupportedTables {
		fmt.Printf("%2d. %s\n", i+1, table)
	}

	fmt.Println("\n========================================\n")
}

func showHelp() {
	fmt.Println(`
SQLite to PostgreSQL Migration Tool
====================================

USAGE:
  migration-cli [flags]

MODES:
  migrate      - Perform full migration (default)
  validate     - Check data integrity
  dry-run      - Simulate migration without writing
  rollback     - Rollback a migration (not implemented)
  list-tables  - List all supported tables

FLAGS:
  --source       string   Path to source SQLite database (required for migrate/validate/dry-run)
  --target-host  string   PostgreSQL host (default: localhost)
  --target-port  int      PostgreSQL port (default: 5432)
  --target-db    string   PostgreSQL database name (default: educational_apps)
  --target-user  string   PostgreSQL username (default: postgres)
  --target-pass  string   PostgreSQL password
  --dry-run               Run migration without writing data
  --skip-validation       Skip data validation after migration
  --verbose               Enable verbose logging (default: true)
  --help                  Show this help message

EXAMPLES:
  # Show available tables
  migration-cli --mode list-tables

  # Perform full migration
  migration-cli --mode migrate \
    --source ./reading.db \
    --target-host localhost \
    --target-user postgres \
    --target-pass password123

  # Dry-run migration
  migration-cli --mode dry-run \
    --source ./math.db \
    --target-host localhost \
    --target-user postgres

  # Validate data
  migration-cli --mode validate \
    --source ./typing.db \
    --target-host localhost \
    --target-user postgres
`)
}
