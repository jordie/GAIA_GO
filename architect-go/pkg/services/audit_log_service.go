package services

import (
	"context"

	"architect-go/pkg/models"
)

// AuditLogService defines audit logging business logic (append-only, immutable)
type AuditLogService interface {
	// CreateAuditLog creates new audit log entry (append-only)
	CreateAuditLog(ctx context.Context, userID string, action string, resource string, resourceID string, changes map[string]interface{}) (*models.AuditLog, error)

	// GetAuditLog retrieves audit log entry
	GetAuditLog(ctx context.Context, id string) (*models.AuditLog, error)

	// ListAuditLogs retrieves all audit logs with pagination
	ListAuditLogs(ctx context.Context, limit, offset int) ([]*models.AuditLog, int64, error)

	// GetAuditLogsByUser retrieves audit logs for specific user
	GetAuditLogsByUser(ctx context.Context, userID string, limit, offset int) ([]*models.AuditLog, int64, error)

	// GetAuditLogsByResource retrieves audit logs for specific resource
	GetAuditLogsByResource(ctx context.Context, resourceType string, resourceID string, limit, offset int) ([]*models.AuditLog, int64, error)

	// GetAuditLogsByAction retrieves audit logs for specific action
	GetAuditLogsByAction(ctx context.Context, action string, limit, offset int) ([]*models.AuditLog, int64, error)

	// GetRecentAuditLogs retrieves recent audit entries
	GetRecentAuditLogs(ctx context.Context, limit int) ([]*models.AuditLog, error)

	// ExportAuditTrail exports audit trail in specified format
	ExportAuditTrail(ctx context.Context, format string) (*EventExportResponse, error)

	// SearchAuditLogs performs advanced search on audit logs
	SearchAuditLogs(ctx context.Context, req *AuditSearchRequest) ([]*models.AuditLog, int64, error)

	// GetAuditTimeline retrieves timeline view of audit events
	GetAuditTimeline(ctx context.Context, limit, offset int) ([]map[string]interface{}, int64, error)

	// GetAuditStats returns audit log statistics
	GetAuditStats(ctx context.Context) (*AuditStatsResponse, error)

	// GenerateComplianceReport generates compliance report
	GenerateComplianceReport(ctx context.Context, startDate string, endDate string) (*ComplianceReportResponse, error)

	// UpdateRetentionPolicy updates audit log retention settings
	UpdateRetentionPolicy(ctx context.Context, policy map[string]interface{}) error

	// GetRetentionPolicy retrieves current retention settings
	GetRetentionPolicy(ctx context.Context) (map[string]interface{}, error)

	// ArchiveOldLogs archives old audit logs (immutable copy)
	ArchiveOldLogs(ctx context.Context, beforeDate string) (int64, error)

	// PurgeOldLogs permanently removes old audit logs (admin only)
	PurgeOldLogs(ctx context.Context, beforeDate string) (int64, error)

	// GetResourceChangeHistory retrieves complete change history for resource
	GetResourceChangeHistory(ctx context.Context, resourceID string, limit, offset int) ([]*models.AuditLog, int64, error)

	// GetPermissionChanges retrieves all permission-related changes
	GetPermissionChanges(ctx context.Context, limit, offset int) ([]PermissionChangeResponse, int64, error)

	// LogPermissionChange logs permission change (wrapper)
	LogPermissionChange(ctx context.Context, userID string, permission string, action string, grantedBy string) error

	// VerifyIntegrity verifies audit log integrity (tamper detection)
	VerifyIntegrity(ctx context.Context) (map[string]interface{}, error)

	// GetIntegrityCheckStatus retrieves last integrity check status
	GetIntegrityCheckStatus(ctx context.Context) (map[string]interface{}, error)

	// GetUserActionSummary retrieves summary of user actions
	GetUserActionSummary(ctx context.Context, userID string) (map[string]interface{}, error)

	// GetResourceModificationHistory retrieves modification history
	GetResourceModificationHistory(ctx context.Context, resourceID string) (map[string]interface{}, error)

	// GetSensitiveActionLog retrieves sensitive operations
	GetSensitiveActionLog(ctx context.Context, limit, offset int) ([]*models.AuditLog, int64, error)

	// GetDataAccessLog retrieves data access events
	GetDataAccessLog(ctx context.Context, limit, offset int) ([]*models.AuditLog, int64, error)

	// IsAuditLogImmutable verifies if log cannot be modified
	IsAuditLogImmutable(ctx context.Context, id string) (bool, error)

	// VerifyAuditLogSignature verifies integrity signature of log
	VerifyAuditLogSignature(ctx context.Context, id string) (bool, error)

	// RegenerateIntegritySignatures regenerates all integrity signatures
	RegenerateIntegritySignatures(ctx context.Context) error

	// ExportForCompliance exports logs for compliance audit
	ExportForCompliance(ctx context.Context, format string, startDate string, endDate string) (*EventExportResponse, error)

	// GetComplianceAuditTrail retrieves compliance-relevant audit trail
	GetComplianceAuditTrail(ctx context.Context, standard string) ([]map[string]interface{}, error)

	// GetAuditMetrics retrieves audit performance metrics
	GetAuditMetrics(ctx context.Context) (map[string]interface{}, error)

	// GetAnomalies detects anomalies in audit logs
	GetAnomalies(ctx context.Context) ([]map[string]interface{}, error)

	// GetUserBehaviorPattern analyzes user behavior patterns
	GetUserBehaviorPattern(ctx context.Context, userID string) (map[string]interface{}, error)

	// AlertOnAnomalies sets up alerts for detected anomalies
	AlertOnAnomalies(ctx context.Context, threshold int) error

	// GetFailureAuditLog retrieves failed operation logs
	GetFailureAuditLog(ctx context.Context, limit, offset int) ([]*models.AuditLog, int64, error)

	// GetSecurityEventLog retrieves security-relevant events
	GetSecurityEventLog(ctx context.Context, limit, offset int) ([]*models.AuditLog, int64, error)
}
