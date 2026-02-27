package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupBulkTestDB creates test database for bulk operations
func setupBulkTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.Exec(`
		CREATE TABLE appeals (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			status TEXT DEFAULT 'pending',
			priority TEXT DEFAULT 'medium',
			reason TEXT,
			description TEXT,
			evidence TEXT,
			reputation_lost REAL,
			requested_action TEXT,
			reviewed_by TEXT,
			review_comment TEXT,
			resolution TEXT,
			approved_points REAL,
			created_at TIMESTAMP,
			updated_at TIMESTAMP,
			expires_at TIMESTAMP,
			resolved_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_status_changes (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			user_id INTEGER,
			old_status TEXT,
			new_status TEXT,
			changed_by TEXT,
			reason TEXT,
			metadata TEXT,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE bulk_appeal_operations (
			id INTEGER PRIMARY KEY,
			operation_id TEXT UNIQUE,
			admin_id INTEGER,
			operation_type TEXT,
			filter_criteria TEXT,
			total_selected INTEGER,
			total_processed INTEGER,
			total_succeeded INTEGER,
			total_failed INTEGER,
			status TEXT,
			error_message TEXT,
			started_at TIMESTAMP,
			completed_at TIMESTAMP,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_notifications (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			user_id INTEGER,
			notification_type TEXT,
			channel TEXT,
			recipient TEXT,
			subject TEXT,
			body TEXT,
			status TEXT,
			created_at TIMESTAMP
		)
	`)

	return db
}

// TestBulkOperationsServiceCreation tests service initialization
func TestBulkOperationsServiceCreation(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	if bos == nil {
		t.Errorf("Failed to create bulk operations service")
	}
}

// TestBulkApproveAppeals tests bulk approval
func TestBulkApproveAppeals(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create pending appeals
	for i := 1; i <= 5; i++ {
		appeal := &Appeal{
			ID:          i,
			UserID:      100 + i,
			Status:      StatusPending,
			Priority:    "medium",
			CreatedAt:   time.Now(),
			ExpiresAt:   time.Now().AddDate(0, 0, 30),
		}
		db.Table("appeals").Create(appeal)
	}

	criteria := map[string]interface{}{
		"status":   "pending",
		"priority": "medium",
	}

	operation, err := bos.BulkApproveAppeals(
		context.Background(),
		1, // adminID
		criteria,
		50.0, // approvedPoints
		"Auto-approved",
	)

	if err != nil {
		t.Errorf("Failed to bulk approve: %v", err)
	}

	if operation == nil {
		t.Errorf("Operation is nil")
	}

	if operation.TotalSelected != 5 {
		t.Errorf("Expected 5 selected, got %d", operation.TotalSelected)
	}

	if operation.TotalSucceeded != 5 {
		t.Errorf("Expected 5 succeeded, got %d", operation.TotalSucceeded)
	}

	// Verify appeals were approved
	var approvedCount int64
	db.Table("appeals").
		Where("status = ?", StatusApproved).
		Count(&approvedCount)

	if approvedCount != 5 {
		t.Errorf("Expected 5 approved appeals, got %d", approvedCount)
	}
}

// TestBulkDenyAppeals tests bulk denial
func TestBulkDenyAppeals(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create pending appeals
	for i := 10; i <= 14; i++ {
		appeal := &Appeal{
			ID:        i,
			UserID:    100 + i,
			Status:    StatusPending,
			Priority:  "high",
			CreatedAt: time.Now(),
			ExpiresAt: time.Now().AddDate(0, 0, 30),
		}
		db.Table("appeals").Create(appeal)
	}

	criteria := map[string]interface{}{
		"status":   "pending",
		"priority": "high",
	}

	operation, err := bos.BulkDenyAppeals(
		context.Background(),
		2,
		criteria,
		"insufficient_evidence",
		"Not approved",
	)

	if err != nil {
		t.Errorf("Failed to bulk deny: %v", err)
	}

	if operation.TotalSucceeded != 5 {
		t.Errorf("Expected 5 succeeded, got %d", operation.TotalSucceeded)
	}

	// Verify appeals were denied
	var deniedCount int64
	db.Table("appeals").
		Where("status = ?", StatusDenied).
		Count(&deniedCount)

	if deniedCount != 5 {
		t.Errorf("Expected 5 denied appeals, got %d", deniedCount)
	}
}

// TestBulkAssignPriority tests bulk priority assignment
func TestBulkAssignPriority(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create appeals with low priority
	for i := 20; i <= 24; i++ {
		appeal := &Appeal{
			ID:        i,
			UserID:    100 + i,
			Status:    StatusPending,
			Priority:  "low",
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)
	}

	criteria := map[string]interface{}{
		"priority": "low",
	}

	operation, err := bos.BulkAssignPriority(
		context.Background(),
		3,
		criteria,
		"critical",
	)

	if err != nil {
		t.Errorf("Failed to assign priority: %v", err)
	}

	if operation.TotalSucceeded != 5 {
		t.Errorf("Expected 5 succeeded, got %d", operation.TotalSucceeded)
	}

	// Verify priorities were updated
	var criticalCount int64
	db.Table("appeals").
		Where("priority = ?", "critical").
		Count(&criticalCount)

	if criticalCount != 5 {
		t.Errorf("Expected 5 critical priority appeals, got %d", criticalCount)
	}
}

// TestGetBulkOperationStatus retrieves operation status
func TestGetBulkOperationStatus(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create test appeals
	appeal := &Appeal{
		ID:        30,
		UserID:    130,
		Status:    StatusPending,
		CreatedAt: time.Now(),
	}
	db.Table("appeals").Create(appeal)

	// Run bulk operation
	operation, _ := bos.BulkApproveAppeals(
		context.Background(),
		4,
		map[string]interface{}{"status": "pending"},
		50.0,
		"Test",
	)

	// Get status
	status, err := bos.GetBulkOperationStatus(context.Background(), operation.OperationID)
	if err != nil {
		t.Errorf("Failed to get operation status: %v", err)
	}

	if status.OperationID != operation.OperationID {
		t.Errorf("Operation ID mismatch")
	}

	if status.Status != BulkStatusCompleted {
		t.Errorf("Expected completed status, got %s", status.Status)
	}
}

// TestGetAdminBulkOperations retrieves admin's operations
func TestGetAdminBulkOperations(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create multiple operations
	for i := 40; i <= 42; i++ {
		appeal := &Appeal{
			ID:        i,
			UserID:    100 + i,
			Status:    StatusPending,
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)

		bos.BulkApproveAppeals(
			context.Background(),
			5, // Same admin
			map[string]interface{}{"status": "pending"},
			50.0,
			"Test",
		)
	}

	operations, err := bos.GetAdminBulkOperations(context.Background(), 5, 10, 0)
	if err != nil {
		t.Errorf("Failed to get operations: %v", err)
	}

	if len(operations) < 3 {
		t.Errorf("Expected at least 3 operations, got %d", len(operations))
	}
}

// TestGetBulkOperationStats retrieves statistics
func TestGetBulkOperationStats(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create test data
	for i := 50; i <= 54; i++ {
		appeal := &Appeal{
			ID:        i,
			UserID:    100 + i,
			Status:    StatusPending,
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)
	}

	bos.BulkApproveAppeals(
		context.Background(),
		6,
		map[string]interface{}{"status": "pending"},
		50.0,
		"Test",
	)

	stats, err := bos.GetBulkOperationStats(context.Background())
	if err != nil {
		t.Errorf("Failed to get stats: %v", err)
	}

	if stats["total_operations"] == nil {
		t.Errorf("total_operations not in stats")
	}

	if stats["avg_success_rate_percent"] == nil {
		t.Errorf("avg_success_rate_percent not in stats")
	}
}

// TestBulkOperationFiltering tests appeal filtering
func TestBulkOperationFiltering(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create appeals with different properties
	statuses := []AppealStatus{StatusPending, StatusPending, StatusReviewing, StatusPending}
	priorities := []AppealPriority{"low", "medium", "high", "medium"}

	for i, (status, priority) := range zip(statuses, priorities) {
		appeal := &Appeal{
			ID:        60 + i,
			UserID:    160 + i,
			Status:    status,
			Priority:  priority,
			CreatedAt: time.Now().AddDate(0, 0, -(i+1)), // Vary age
		}
		db.Table("appeals").Create(appeal)
	}

	criteria := map[string]interface{}{
		"status": "pending",
	}

	operation, _ := bos.BulkApproveAppeals(
		context.Background(),
		7,
		criteria,
		50.0,
		"Test",
	)

	// Should have only selected pending appeals
	if operation.TotalSelected != 3 {
		t.Errorf("Expected 3 pending appeals, got %d", operation.TotalSelected)
	}
}

// TestOperationRecording verifies operation is recorded
func TestOperationRecording(t *testing.T) {
	db := setupBulkTestDB(t)
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	appeal := &Appeal{
		ID:        70,
		UserID:    170,
		Status:    StatusPending,
		CreatedAt: time.Now(),
	}
	db.Table("appeals").Create(appeal)

	operation, _ := bos.BulkApproveAppeals(
		context.Background(),
		8,
		map[string]interface{}{"status": "pending"},
		50.0,
		"Test",
	)

	// Verify operation was recorded
	var recorded BulkOperation
	result := db.Table("bulk_appeal_operations").
		Where("operation_id = ?", operation.OperationID).
		First(&recorded)

	if result.Error != nil {
		t.Errorf("Operation not recorded: %v", result.Error)
	}

	if recorded.AdminID != 8 {
		t.Errorf("Expected admin 8, got %d", recorded.AdminID)
	}

	if recorded.Status != BulkStatusCompleted {
		t.Errorf("Expected completed, got %s", recorded.Status)
	}
}

// Helper function for zipping slices
func zip(statuses []AppealStatus, priorities []AppealPriority) [][2]interface{} {
	result := make([][2]interface{}, len(statuses))
	for i := range statuses {
		result[i] = [2]interface{}{statuses[i], priorities[i]}
	}
	return result
}

// BenchmarkBulkApproveAppeals benchmarks bulk approval
func BenchmarkBulkApproveAppeals(b *testing.B) {
	db := setupBulkTestDB(&testing.T{})
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create test appeals
	for i := 1; i <= 100; i++ {
		appeal := &Appeal{
			ID:        i,
			UserID:    100 + i,
			Status:    StatusPending,
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		bos.BulkApproveAppeals(
			context.Background(),
			9,
			map[string]interface{}{"status": "pending"},
			50.0,
			"Bench",
		)
	}
}

// BenchmarkBulkDenyAppeals benchmarks bulk denial
func BenchmarkBulkDenyAppeals(b *testing.B) {
	db := setupBulkTestDB(&testing.T{})
	appealSvc := NewAppealService(db)
	notifSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	bos := NewAdminBulkOperationsService(db, appealSvc, notifSvc, historySvc)

	// Create test appeals
	for i := 200; i <= 299; i++ {
		appeal := &Appeal{
			ID:        i,
			UserID:    100 + i,
			Status:    StatusPending,
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		bos.BulkDenyAppeals(
			context.Background(),
			10,
			map[string]interface{}{"status": "pending"},
			"bench",
			"Benchmark",
		)
	}
}
