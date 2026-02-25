package models

import (
	"time"
)

// ========== MIGRATION STATUS & LOGGING ==========

// MigrationStatus tracks migration progress
type MigrationStatus struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	Status        string    `json:"status"` // "pending", "in_progress", "completed", "failed", "rolled_back"
	StartTime     time.Time `json:"start_time"`
	EndTime       time.Time `json:"end_time,omitempty"`
	SourceDB      string    `json:"source_db"` // "sqlite"
	TargetDB      string    `json:"target_db"` // "postgres"
	TotalRecords  int       `json:"total_records"`
	MigratedRecords int    `json:"migrated_records"`
	FailedRecords int      `json:"failed_records"`
	ErrorMessage  string    `json:"error_message,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// MigrationLog records individual migration operations
type MigrationLog struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	MigrationID   uint      `json:"migration_id"`
	TableName     string    `json:"table_name"`
	Operation     string    `json:"operation"` // "select", "insert", "validate", "rollback"
	RecordsProcessed int    `json:"records_processed"`
	Duration      int       `json:"duration"` // milliseconds
	Status        string    `json:"status"` // "success", "error", "warning"
	Message       string    `json:"message"`
	CreatedAt     time.Time `json:"created_at"`
}

// DataValidation tracks validation results
type DataValidation struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	MigrationID     uint      `json:"migration_id"`
	TableName       string    `json:"table_name"`
	SourceCount     int       `json:"source_count"`
	TargetCount     int       `json:"target_count"`
	Matched         bool      `json:"matched"`
	ChecksumMatch   bool      `json:"checksum_match"`
	SourceChecksum  string    `json:"source_checksum"`
	TargetChecksum  string    `json:"target_checksum"`
	IssuesFound     string    `json:"issues_found,omitempty"`
	CreatedAt       time.Time `json:"created_at"`
}

// ========== MIGRATION REQUEST/RESPONSE TYPES ==========

// MigrationRequest initiates a migration
type MigrationRequest struct {
	SourceDBPath   string `json:"source_db_path" binding:"required"`
	TargetDBHost   string `json:"target_db_host" binding:"required"`
	TargetDBPort   int    `json:"target_db_port" binding:"required"`
	TargetDBName   string `json:"target_db_name" binding:"required"`
	TargetDBUser   string `json:"target_db_user" binding:"required"`
	TargetDBPassword string `json:"target_db_password" binding:"required"`
	DryRun         bool   `json:"dry_run"` // Don't actually migrate, just validate
	SkipValidation bool   `json:"skip_validation"`
}

// MigrationProgressResponse reports migration status
type MigrationProgressResponse struct {
	MigrationID     uint      `json:"migration_id"`
	Status          string    `json:"status"`
	TotalRecords    int       `json:"total_records"`
	MigratedRecords int       `json:"migrated_records"`
	FailedRecords   int       `json:"failed_records"`
	Percentage      float64   `json:"percentage"`
	ElapsedTime     int       `json:"elapsed_time"` // seconds
	EstimatedTime   int       `json:"estimated_time,omitempty"` // seconds
	ErrorMessage    string    `json:"error_message,omitempty"`
}

// MigrationSummaryResponse summarizes migration results
type MigrationSummaryResponse struct {
	MigrationID      uint              `json:"migration_id"`
	Status           string            `json:"status"`
	TotalRecords     int               `json:"total_records"`
	MigratedRecords  int               `json:"migrated_records"`
	FailedRecords    int               `json:"failed_records"`
	Duration         int               `json:"duration"` // seconds
	TablesProcessed  []string          `json:"tables_processed"`
	Validations      map[string]bool   `json:"validations"`
	IssuesFound      []string          `json:"issues_found"`
	Recommendations  []string          `json:"recommendations"`
}

// RollbackRequest initiates a rollback
type RollbackRequest struct {
	MigrationID uint `json:"migration_id" binding:"required"`
}

// ========== MIGRATION STATISTICS ==========

// MigrationStats provides detailed statistics
type MigrationStats struct {
	TotalTables      int       `json:"total_tables"`
	CompletedTables  int       `json:"completed_tables"`
	TotalRecords     int       `json:"total_records"`
	MigratedRecords  int       `json:"migrated_records"`
	FailedRecords    int       `json:"failed_records"`
	StartTime        time.Time `json:"start_time"`
	EndTime          time.Time `json:"end_time"`
	Duration         int       `json:"duration"` // seconds
	AverageRecordsPerSecond float64 `json:"average_records_per_second"`
	TableStats       map[string]TableMigrationStats `json:"table_stats"`
}

// TableMigrationStats tracks per-table statistics
type TableMigrationStats struct {
	TableName        string `json:"table_name"`
	SourceCount      int    `json:"source_count"`
	TargetCount      int    `json:"target_count"`
	MigratedCount    int    `json:"migrated_count"`
	FailedCount      int    `json:"failed_count"`
	Duration         int    `json:"duration"` // milliseconds
	Status           string `json:"status"`
	ErrorMessages    []string `json:"error_messages,omitempty"`
}

// ========== MIGRATION CONFIGURATION ==========

// MigrationConfig defines database connection parameters
type MigrationConfig struct {
	SourceType       string
	SourcePath       string
	TargetType       string
	TargetHost       string
	TargetPort       int
	TargetDatabase   string
	TargetUser       string
	TargetPassword   string
	DryRun           bool
	SkipValidation   bool
	BatchSize        int // Records to process per batch
	EnableLogging    bool
	LogLevel         string // "error", "warn", "info", "debug"
}

// ========== TABLE SCHEMA MAPPING ==========

// ColumnMapping defines how a column should be transformed
type ColumnMapping struct {
	SourceColumn string `json:"source_column"`
	TargetColumn string `json:"target_column"`
	SourceType   string `json:"source_type"` // SQLite type
	TargetType   string `json:"target_type"` // PostgreSQL type
	Transform    string `json:"transform,omitempty"` // transformation logic
}

// TableMapping defines table-level migration rules
type TableMapping struct {
	SourceTable     string           `json:"source_table"`
	TargetTable     string           `json:"target_table"`
	Columns         []ColumnMapping  `json:"columns"`
	PrimaryKey      string           `json:"primary_key"`
	ForeignKeys     []string         `json:"foreign_keys,omitempty"`
	Indexes         []string         `json:"indexes,omitempty"`
	RequiresOrdering string          `json:"requires_ordering,omitempty"` // Order by clause
}

// ========== DATA TYPE MAPPING ==========

// Type mappings from SQLite to PostgreSQL
var SQLiteToPostgresTypeMap = map[string]string{
	"INTEGER":         "INTEGER",
	"TEXT":            "TEXT",
	"REAL":            "DOUBLE PRECISION",
	"BLOB":            "BYTEA",
	"BOOLEAN":         "BOOLEAN",
	"TIMESTAMP":       "TIMESTAMP WITH TIME ZONE",
	"DATETIME":        "TIMESTAMP WITH TIME ZONE",
	"DATE":            "DATE",
	"TIME":            "TIME",
	"NUMERIC":         "NUMERIC",
	"DECIMAL":         "DECIMAL",
	"JSON":            "JSONB",
	"VARCHAR":         "VARCHAR",
	"CHAR":            "CHAR",
	"FLOAT":           "FLOAT",
	"DOUBLE":          "DOUBLE PRECISION",
	"BIGINT":          "BIGINT",
	"SMALLINT":        "SMALLINT",
}

// ========== MIGRATION CONSTANTS ==========

const (
	// Migration statuses
	MigrationStatusPending    = "pending"
	MigrationStatusInProgress = "in_progress"
	MigrationStatusCompleted  = "completed"
	MigrationStatusFailed     = "failed"
	MigrationStatusRolledBack = "rolled_back"

	// Operation types
	OperationSelect   = "select"
	OperationInsert   = "insert"
	OperationUpdate   = "update"
	OperationValidate = "validate"
	OperationRollback = "rollback"

	// Result statuses
	ResultSuccess = "success"
	ResultError   = "error"
	ResultWarning = "warning"

	// Default batch size for processing records
	DefaultBatchSize = 1000

	// Default log level
	DefaultLogLevel = "info"
)

// ========== MIGRATION TABLES LIST ==========

// SupportedTables lists all tables to be migrated
var SupportedTables = []string{
	// Core user tables
	"users",
	"user_profiles",

	// Gamification
	"user_xp",
	"xp_log",
	"user_streak",
	"achievement",
	"user_achievement",

	// Analytics
	"app_progress",
	"subject_mastery",
	"learning_goal",
	"user_note",
	"activity_log_entry",

	// Math app
	"math_problem",
	"session_result",
	"question_history",
	"mistake",
	"mastery",
	"learning_profile",
	"performance_pattern",
	"repetition_schedule",

	// Reading app
	"word",
	"reading_result",
	"word_performance",
	"quiz",
	"question",
	"quiz_attempt",
	"reading_learning_profile",
	"reading_streak",

	// Comprehension app
	"question_type",
	"subject",
	"difficulty_level",
	"question",
	"user_progress",
	"user_stats",
}
