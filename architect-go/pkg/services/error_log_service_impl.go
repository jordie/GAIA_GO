package services

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// ErrorLogServiceImpl implements ErrorLogService
type ErrorLogServiceImpl struct {
	repo repository.ErrorLogRepository
}

// NewErrorLogService creates a new error log service
func NewErrorLogService(repo repository.ErrorLogRepository) ErrorLogService {
	return &ErrorLogServiceImpl{repo: repo}
}

func (els *ErrorLogServiceImpl) LogError(ctx context.Context, req *LogErrorRequest) (*models.ErrorLog, error) {
	// Marshal Metadata to JSON
	var metadata json.RawMessage
	if req.Metadata != nil {
		if data, err := json.Marshal(req.Metadata); err == nil {
			metadata = data
		}
	}

	// Marshal Tags to JSON
	var tags json.RawMessage
	if len(req.Tags) > 0 {
		if data, err := json.Marshal(req.Tags); err == nil {
			tags = data
		}
	}

	errorLog := &models.ErrorLog{
		ID:         uuid.New().String(),
		ErrorType:  req.ErrorType,
		Message:    req.Message,
		Source:     req.Source,
		Severity:   req.Severity,
		StackTrace: req.StackTrace,
		Timestamp:  time.Now(),
		Status:     "new",
		Count:      1,
		Metadata:   metadata,
		Tags:       tags,
	}

	if err := els.repo.Create(ctx, errorLog); err != nil {
		return nil, fmt.Errorf("failed to log error: %w", err)
	}

	return errorLog, nil
}

func (els *ErrorLogServiceImpl) GetError(ctx context.Context, id string) (*models.ErrorLog, error) {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get error: %w", err)
	}
	return errorLog, nil
}

func (els *ErrorLogServiceImpl) ListErrors(ctx context.Context, req *LogErrorRequest, limit, offset int) ([]*models.ErrorLog, int64, error) {
	filters := make(map[string]interface{})
	if req.ErrorType != "" {
		filters["error_type"] = req.ErrorType
	}
	if req.Source != "" {
		filters["source"] = req.Source
	}
	if req.Severity != "" {
		filters["severity"] = req.Severity
	}

	errors, total, err := els.repo.List(ctx, filters, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list errors: %w", err)
	}

	return errors, total, nil
}

func (els *ErrorLogServiceImpl) ListErrorsByType(ctx context.Context, errorType string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errors, total, err := els.repo.GetByType(ctx, errorType, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list errors by type: %w", err)
	}
	return errors, total, nil
}

func (els *ErrorLogServiceImpl) ListErrorsBySource(ctx context.Context, source string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errors, total, err := els.repo.GetBySource(ctx, source, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list errors by source: %w", err)
	}
	return errors, total, nil
}

func (els *ErrorLogServiceImpl) ListErrorsBySeverity(ctx context.Context, severity string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errors, total, err := els.repo.GetBySeverity(ctx, severity, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list errors by severity: %w", err)
	}
	return errors, total, nil
}

func (els *ErrorLogServiceImpl) ListCriticalErrors(ctx context.Context, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errors, total, err := els.repo.GetBySeverity(ctx, "critical", limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list critical errors: %w", err)
	}
	return errors, total, nil
}

func (els *ErrorLogServiceImpl) ListRecentErrors(ctx context.Context, limit int) ([]*models.ErrorLog, error) {
	errors, err := els.repo.ListRecent(ctx, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to list recent errors: %w", err)
	}
	return errors, nil
}

func (els *ErrorLogServiceImpl) UpdateErrorStatus(ctx context.Context, id string, req *ResolveErrorRequest) (*models.ErrorLog, error) {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("error not found: %w", err)
	}

	errorLog.Status = req.Status
	if req.Resolution != "" {
		// Unmarshal existing metadata or create new map
		metadataMap := make(map[string]interface{})
		if len(errorLog.Metadata) > 0 {
			_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
		}
		metadataMap["resolution"] = req.Resolution
		metadataMap["resolved_at"] = time.Now()

		// Marshal back to JSON
		if data, err := json.Marshal(metadataMap); err == nil {
			errorLog.Metadata = data
		}
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return nil, fmt.Errorf("failed to update error status: %w", err)
	}

	return errorLog, nil
}

func (els *ErrorLogServiceImpl) ArchiveError(ctx context.Context, id string) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	// Unmarshal existing metadata or create new map
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}
	metadataMap["archived"] = true
	metadataMap["archived_at"] = time.Now()

	// Marshal back to JSON
	if data, err := json.Marshal(metadataMap); err == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to archive error: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) DeleteError(ctx context.Context, id string) error {
	if err := els.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete error: %w", err)
	}
	return nil
}

func (els *ErrorLogServiceImpl) ResolveError(ctx context.Context, id string, req *ResolveErrorRequest) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	errorLog.Status = "resolved"

	// Unmarshal existing metadata or create new map
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}

	if req.Resolution != "" {
		metadataMap["resolution"] = req.Resolution
	}
	metadataMap["resolved_at"] = time.Now()

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to resolve error: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) AssignError(ctx context.Context, id string, userID string) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	// Unmarshal existing metadata or create new map
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}
	metadataMap["assigned_to"] = userID
	metadataMap["assigned_at"] = time.Now()

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to assign error: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) CreateBugFromError(ctx context.Context, id string, req *CreateBugFromErrorRequest) (*models.Bug, error) {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("error not found: %w", err)
	}

	title := req.Title
	if title == "" {
		title = errorLog.Message
	}
	description := req.Description
	if description == "" {
		description = fmt.Sprintf("Error Type: %s\n\nStack Trace:\n%s", errorLog.ErrorType, errorLog.StackTrace)
	}
	severity := req.Severity
	if severity == "" {
		severity = errorLog.Severity
	}

	bug := &models.Bug{
		ID:          uuid.New().String(),
		ProjectID:   req.ProjectID,
		Title:       title,
		Description: description,
		Severity:    severity,
		Status:      "new",
		CreatedAt:   time.Now(),
	}

	// Mark error as converted to bug
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}
	metadataMap["bug_id"] = bug.ID
	metadataMap["converted_at"] = time.Now()

	if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return nil, fmt.Errorf("failed to update error after bug creation: %w", err)
	}

	return bug, nil
}

func (els *ErrorLogServiceImpl) GetErrorHistory(ctx context.Context, id string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return nil, 0, fmt.Errorf("error not found: %w", err)
	}

	filters := make(map[string]interface{})
	filters["error_type"] = errorLog.ErrorType
	filters["source"] = errorLog.Source

	errors, total, err := els.repo.List(ctx, filters, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get error history: %w", err)
	}

	return errors, total, nil
}

func (els *ErrorLogServiceImpl) GetErrorStats(ctx context.Context, req *ErrorStatsRequest) (*ErrorStatsResponse, error) {
	startDate := req.StartDate.Format(time.RFC3339)
	endDate := req.EndDate.Format(time.RFC3339)
	_, err := els.repo.GetStats(ctx, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to get error stats: %w", err)
	}

	return &ErrorStatsResponse{
		TotalErrors:      0,
		ErrorsByType:     map[string]int64{},
		ErrorsBySource:   map[string]int64{},
		ErrorsBySeverity: map[string]int64{},
	}, nil
}

func (els *ErrorLogServiceImpl) GetErrorSummary(ctx context.Context, groupBy string) (map[string]int64, error) {
	filters := make(map[string]interface{})
	errors, _, err := els.repo.List(ctx, filters, 10000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to get error summary: %w", err)
	}

	summary := make(map[string]int64)
	for _, errLog := range errors {
		var key string
		switch groupBy {
		case "type":
			key = errLog.ErrorType
		case "source":
			key = errLog.Source
		case "severity":
			key = errLog.Severity
		case "status":
			key = errLog.Status
		default:
			key = "unknown"
		}

		summary[key]++
	}

	return summary, nil
}

func (els *ErrorLogServiceImpl) GetTrendingErrors(ctx context.Context, timeWindow string, limit int) ([]*models.ErrorLog, error) {
	// In a real implementation, this would filter by timeWindow
	filters := make(map[string]interface{})
	errors, _, err := els.repo.List(ctx, filters, limit, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to get trending errors: %w", err)
	}
	return errors, nil
}

func (els *ErrorLogServiceImpl) SearchErrors(ctx context.Context, query string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errors, total, err := els.repo.Search(ctx, query, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to search errors: %w", err)
	}
	return errors, total, nil
}

func (els *ErrorLogServiceImpl) ExportErrors(ctx context.Context, format string) (*EventExportResponse, error) {
	_, _, err := els.repo.List(ctx, make(map[string]interface{}), 10000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to export errors: %w", err)
	}

	switch format {
	case "json", "csv":
		// valid formats
	default:
		return nil, fmt.Errorf("unsupported export format: %s", format)
	}

	return &EventExportResponse{
		Format:    format,
		ExpiresAt: time.Now().Add(24 * time.Hour),
		Size:      0,
	}, nil
}

func (els *ErrorLogServiceImpl) GetFullStackTrace(ctx context.Context, id string) (string, error) {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return "", fmt.Errorf("error not found: %w", err)
	}
	return errorLog.StackTrace, nil
}

func (els *ErrorLogServiceImpl) AddErrorTag(ctx context.Context, id string, tag string) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	// Unmarshal existing tags
	var tagSlice []string
	if len(errorLog.Tags) > 0 {
		_ = json.Unmarshal(errorLog.Tags, &tagSlice)
	}
	if tagSlice == nil {
		tagSlice = make([]string, 0)
	}

	// Check if tag already exists
	for _, t := range tagSlice {
		if t == tag {
			return nil
		}
	}

	tagSlice = append(tagSlice, tag)

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(tagSlice); marshalErr == nil {
		errorLog.Tags = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to add tag: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) RemoveErrorTag(ctx context.Context, id string, tag string) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	// Unmarshal existing tags
	var tagSlice []string
	if len(errorLog.Tags) > 0 {
		_ = json.Unmarshal(errorLog.Tags, &tagSlice)
	}
	if tagSlice == nil {
		return nil
	}

	newTags := make([]string, 0)
	for _, t := range tagSlice {
		if t != tag {
			newTags = append(newTags, t)
		}
	}

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(newTags); marshalErr == nil {
		errorLog.Tags = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to remove tag: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) GetErrorsByTag(ctx context.Context, tag string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errors, total, err := els.repo.GetByTag(ctx, tag, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get errors by tag: %w", err)
	}
	return errors, total, nil
}

func (els *ErrorLogServiceImpl) AddErrorComment(ctx context.Context, id string, req *ErrorCommentRequest) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	// Unmarshal existing metadata or create new map
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}

	// Get existing comments
	var comments []interface{}
	if existing, ok := metadataMap["comments"]; ok {
		if commentsSlice, ok := existing.([]interface{}); ok {
			comments = commentsSlice
		}
	}
	if comments == nil {
		comments = make([]interface{}, 0)
	}

	comment := map[string]interface{}{
		"user_id":   req.UserID,
		"text":      req.Comment,
		"timestamp": time.Now(),
	}

	comments = append(comments, comment)
	metadataMap["comments"] = comments

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to add comment: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) GetErrorComments(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error) {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return nil, 0, fmt.Errorf("error not found: %w", err)
	}

	comments := make([]map[string]interface{}, 0)

	if len(errorLog.Metadata) > 0 {
		var metadataMap map[string]interface{}
		if jsonErr := json.Unmarshal(errorLog.Metadata, &metadataMap); jsonErr == nil {
			if commentsRaw, ok := metadataMap["comments"].([]interface{}); ok {
				for i, c := range commentsRaw {
					if i >= offset && i < offset+limit {
						if comment, ok := c.(map[string]interface{}); ok {
							comments = append(comments, comment)
						}
					}
				}
			}
		}
	}

	return comments, int64(len(comments)), nil
}

func (els *ErrorLogServiceImpl) GetErrorsByProject(ctx context.Context, projectID string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	errors, total, err := els.repo.GetByProject(ctx, projectID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get errors by project: %w", err)
	}
	return errors, total, nil
}

func (els *ErrorLogServiceImpl) GetErrorsByUser(ctx context.Context, userID string, limit, offset int) ([]*models.ErrorLog, int64, error) {
	filters := make(map[string]interface{})
	if userID != "" {
		filters["user_id"] = userID
	}

	errors, total, err := els.repo.List(ctx, filters, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get errors by user: %w", err)
	}

	return errors, total, nil
}

func (els *ErrorLogServiceImpl) DeduplicateErrors(ctx context.Context) ([]ErrorGroupResponse, error) {
	errors, _, err := els.repo.List(ctx, make(map[string]interface{}), 10000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to get errors for deduplication: %w", err)
	}

	grouped := make(map[string][]*models.ErrorLog)
	for _, e := range errors {
		key := fmt.Sprintf("%s:%s", e.ErrorType, e.Source)
		grouped[key] = append(grouped[key], e)
	}

	result := make([]ErrorGroupResponse, 0)
	for key, errs := range grouped {
		if len(errs) == 0 {
			continue
		}

		// Build representative from first error
		rep := errs[0]
		representative := ErrorResponse{
			ID:        rep.ID,
			ErrorType: rep.ErrorType,
			Message:   rep.Message,
			Source:    rep.Source,
			Severity:  rep.Severity,
			Status:    rep.Status,
			CreatedAt: rep.CreatedAt,
			UpdatedAt: rep.UpdatedAt,
		}

		// Build similar list (rest of errors)
		similar := make([]ErrorResponse, 0, len(errs)-1)
		for _, e := range errs[1:] {
			similar = append(similar, ErrorResponse{
				ID:        e.ID,
				ErrorType: e.ErrorType,
				Message:   e.Message,
				Source:    e.Source,
				Severity:  e.Severity,
				Status:    e.Status,
				CreatedAt: e.CreatedAt,
				UpdatedAt: e.UpdatedAt,
			})
		}

		result = append(result, ErrorGroupResponse{
			GroupID:        key,
			Representative: representative,
			Count:          int64(len(errs)),
			Similar:        similar,
		})
	}

	return result, nil
}

func (els *ErrorLogServiceImpl) GetErrorGroups(ctx context.Context, limit, offset int) ([]ErrorGroupResponse, int64, error) {
	groups, err := els.DeduplicateErrors(ctx)
	if err != nil {
		return nil, 0, err
	}

	total := int64(len(groups))

	// Apply pagination
	if offset >= len(groups) {
		return []ErrorGroupResponse{}, total, nil
	}

	endIdx := offset + limit
	if endIdx > len(groups) {
		endIdx = len(groups)
	}

	return groups[offset:endIdx], total, nil
}

func (els *ErrorLogServiceImpl) DismissError(ctx context.Context, id string) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	errorLog.Status = "dismissed"

	// Unmarshal existing metadata or create new map
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}
	metadataMap["dismissed_at"] = time.Now()

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to dismiss error: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) ReopenError(ctx context.Context, id string) error {
	errorLog, err := els.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	errorLog.Status = "new"

	// Unmarshal existing metadata or create new map
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}
	metadataMap["reopened_at"] = time.Now()

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to reopen error: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) GetActiveAlerts(ctx context.Context) ([]map[string]interface{}, error) {
	// In a real implementation, this would query alert configuration
	return []map[string]interface{}{}, nil
}

func (els *ErrorLogServiceImpl) CreateAlert(ctx context.Context, req *ErrorAlertRequest) (string, error) {
	// In a real implementation, this would create alert rules
	alertID := uuid.New().String()
	return alertID, nil
}

func (els *ErrorLogServiceImpl) UpdateAlert(ctx context.Context, alertID string, req *ErrorAlertRequest) error {
	// In a real implementation, this would update alert rules
	return nil
}

func (els *ErrorLogServiceImpl) DeleteAlert(ctx context.Context, alertID string) error {
	// In a real implementation, this would delete alert rules
	return nil
}

func (els *ErrorLogServiceImpl) RetryFailedOperation(ctx context.Context, errorID string) error {
	errorLog, err := els.repo.Get(ctx, errorID)
	if err != nil {
		return fmt.Errorf("error not found: %w", err)
	}

	// Unmarshal existing metadata or create new map
	metadataMap := make(map[string]interface{})
	if len(errorLog.Metadata) > 0 {
		_ = json.Unmarshal(errorLog.Metadata, &metadataMap)
	}
	metadataMap["retry_attempted_at"] = time.Now()

	// Marshal back to JSON
	if data, marshalErr := json.Marshal(metadataMap); marshalErr == nil {
		errorLog.Metadata = data
	}

	if err := els.repo.Update(ctx, errorLog); err != nil {
		return fmt.Errorf("failed to mark retry: %w", err)
	}

	return nil
}

func (els *ErrorLogServiceImpl) BulkDeleteErrors(ctx context.Context, errorIDs []string) error {
	for _, id := range errorIDs {
		if err := els.repo.Delete(ctx, id); err != nil {
			return fmt.Errorf("failed to delete error: %w", err)
		}
	}
	return nil
}

func (els *ErrorLogServiceImpl) BulkUpdateStatus(ctx context.Context, errorIDs []string, status string) error {
	for _, id := range errorIDs {
		errorLog, err := els.repo.Get(ctx, id)
		if err != nil {
			return fmt.Errorf("error not found: %w", err)
		}

		errorLog.Status = status

		if err := els.repo.Update(ctx, errorLog); err != nil {
			return fmt.Errorf("failed to update error status: %w", err)
		}
	}
	return nil
}

func (els *ErrorLogServiceImpl) DetectErrorPatterns(ctx context.Context) (map[string]interface{}, error) {
	errors, _, err := els.repo.List(ctx, make(map[string]interface{}), 10000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to detect patterns: %w", err)
	}

	patterns := make(map[string]int)
	for _, e := range errors {
		patterns[e.ErrorType]++
	}

	return map[string]interface{}{
		"patterns_detected": patterns,
		"total_errors":      len(errors),
	}, nil
}

func (els *ErrorLogServiceImpl) CleanupOldErrors(ctx context.Context, beforeDate string) (int64, error) {
	count, err := els.repo.HardDelete(ctx, beforeDate)
	if err != nil {
		return 0, fmt.Errorf("failed to cleanup old errors: %w", err)
	}
	return count, nil
}
