package services

import (
	"context"

	"architect-go/pkg/models"
)

// ErrorLogService defines error logging and management business logic
type ErrorLogService interface {
	// LogError logs a new error
	LogError(ctx context.Context, req *LogErrorRequest) (*models.ErrorLog, error)

	// GetError retrieves an error by ID
	GetError(ctx context.Context, id string) (*models.ErrorLog, error)

	// ListErrors retrieves errors with filtering and pagination
	ListErrors(ctx context.Context, req *LogErrorRequest, limit, offset int) ([]*models.ErrorLog, int64, error)

	// ListErrorsByType retrieves errors filtered by type
	ListErrorsByType(ctx context.Context, errorType string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// ListErrorsBySource retrieves errors filtered by source
	ListErrorsBySource(ctx context.Context, source string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// ListErrorsBySeverity retrieves errors filtered by severity
	ListErrorsBySeverity(ctx context.Context, severity string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// ListCriticalErrors retrieves only critical errors
	ListCriticalErrors(ctx context.Context, limit, offset int) ([]*models.ErrorLog, int64, error)

	// ListRecentErrors retrieves recently occurred errors
	ListRecentErrors(ctx context.Context, limit int) ([]*models.ErrorLog, error)

	// UpdateErrorStatus updates error status (new, in-progress, resolved, dismissed)
	UpdateErrorStatus(ctx context.Context, id string, req *ResolveErrorRequest) (*models.ErrorLog, error)

	// ArchiveError archives an error
	ArchiveError(ctx context.Context, id string) error

	// DeleteError permanently deletes an error
	DeleteError(ctx context.Context, id string) error

	// ResolveError marks an error as resolved
	ResolveError(ctx context.Context, id string, req *ResolveErrorRequest) error

	// AssignError assigns error to a user
	AssignError(ctx context.Context, id string, userID string) error

	// CreateBugFromError creates a bug from an error log entry
	CreateBugFromError(ctx context.Context, id string, req *CreateBugFromErrorRequest) (*models.Bug, error)

	// GetErrorHistory retrieves all occurrences of an error
	GetErrorHistory(ctx context.Context, id string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// GetErrorStats returns error statistics
	GetErrorStats(ctx context.Context, req *ErrorStatsRequest) (*ErrorStatsResponse, error)

	// GetErrorSummary returns summary statistics by various dimensions
	GetErrorSummary(ctx context.Context, groupBy string) (map[string]int64, error)

	// GetTrendingErrors returns currently trending errors
	GetTrendingErrors(ctx context.Context, timeWindow string, limit int) ([]*models.ErrorLog, error)

	// SearchErrors performs advanced search on errors
	SearchErrors(ctx context.Context, query string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// ExportErrors exports errors in specified format
	ExportErrors(ctx context.Context, format string) (*EventExportResponse, error)

	// GetFullStackTrace retrieves full stack trace for an error
	GetFullStackTrace(ctx context.Context, id string) (string, error)

	// AddErrorTag adds a tag to an error
	AddErrorTag(ctx context.Context, id string, tag string) error

	// RemoveErrorTag removes a tag from an error
	RemoveErrorTag(ctx context.Context, id string, tag string) error

	// GetErrorsByTag retrieves errors with a specific tag
	GetErrorsByTag(ctx context.Context, tag string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// AddErrorComment adds a comment to an error
	AddErrorComment(ctx context.Context, id string, req *ErrorCommentRequest) error

	// GetErrorComments retrieves comments on an error
	GetErrorComments(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error)

	// GetErrorsByProject retrieves errors from a specific project
	GetErrorsByProject(ctx context.Context, projectID string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// GetErrorsByUser retrieves errors related to a specific user
	GetErrorsByUser(ctx context.Context, userID string, limit, offset int) ([]*models.ErrorLog, int64, error)

	// DeduplicateErrors groups similar errors together
	DeduplicateErrors(ctx context.Context) ([]ErrorGroupResponse, error)

	// GetErrorGroups retrieves grouped errors
	GetErrorGroups(ctx context.Context, limit, offset int) ([]ErrorGroupResponse, int64, error)

	// DismissError marks error as dismissed
	DismissError(ctx context.Context, id string) error

	// ReopenError reopens a resolved error
	ReopenError(ctx context.Context, id string) error

	// GetActiveAlerts retrieves active error alerts
	GetActiveAlerts(ctx context.Context) ([]map[string]interface{}, error)

	// CreateAlert creates new error alert rule
	CreateAlert(ctx context.Context, req *ErrorAlertRequest) (string, error)

	// UpdateAlert updates alert rule
	UpdateAlert(ctx context.Context, alertID string, req *ErrorAlertRequest) error

	// DeleteAlert deletes alert rule
	DeleteAlert(ctx context.Context, alertID string) error

	// RetryFailedOperation retries the operation that caused the error
	RetryFailedOperation(ctx context.Context, errorID string) error

	// BulkDeleteErrors deletes multiple errors
	BulkDeleteErrors(ctx context.Context, errorIDs []string) error

	// BulkUpdateStatus updates status for multiple errors
	BulkUpdateStatus(ctx context.Context, errorIDs []string, status string) error

	// DetectErrorPatterns analyzes errors to find patterns
	DetectErrorPatterns(ctx context.Context) (map[string]interface{}, error)

	// CleanupOldErrors removes old error records
	CleanupOldErrors(ctx context.Context, beforeDate string) (int64, error)
}
