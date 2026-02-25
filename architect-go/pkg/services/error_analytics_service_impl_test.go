package services

import (
	"context"
	"testing"
	"time"

	"architect-go/pkg/dto"
)

// Tests for ErrorAnalyticsService

func TestGetErrorTimeline(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorTimelineFunc: func(ctx context.Context, sd, ed, g string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"timestamp": startDate,
					"count":     float64(15),
					"rate":      float64(0.25),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	// Need to add method to mock
	mockRepo.getEventTimelineFunc = mockRepo.getErrorTimelineFunc

	results, err := service.GetTimeline(context.Background(), startDate, endDate, "day")

	if err != nil {
		t.Fatalf("GetTimeline failed: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected results, got empty")
	}

	if results[0].Count != 15 {
		t.Errorf("Expected count 15, got %d", results[0].Count)
	}
}

func TestGetErrorsBySeverity(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorsBySeverityFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"severity":  "critical",
					"count":     float64(5),
					"percentage": float64(25.0),
				},
				{
					"severity":  "error",
					"count":     float64(10),
					"percentage": float64(50.0),
				},
				{
					"severity":  "warning",
					"count":     float64(5),
					"percentage": float64(25.0),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	results, err := service.GetBySeverity(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetBySeverity failed: %v", err)
	}

	if len(results) != 3 {
		t.Errorf("Expected 3 results, got %d", len(results))
	}

	if results[0].Severity != "critical" {
		t.Errorf("Expected severity 'critical', got '%s'", results[0].Severity)
	}

	if results[0].Percentage != 25.0 {
		t.Errorf("Expected percentage 25.0, got %f", results[0].Percentage)
	}
}

func TestGetErrorImpact(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorImpactFunc: func(ctx context.Context, sd, ed string, limit int) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"error_type":      "database_connection_error",
					"affected_users":  float64(150),
					"affected_sessions": float64(320),
					"revenue_impact":  float64(2500.00),
					"severity_score":  float64(8.5),
				},
				{
					"error_type":      "payment_timeout",
					"affected_users":  float64(75),
					"affected_sessions": float64(95),
					"revenue_impact":  float64(5000.00),
					"severity_score":  float64(9.2),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	results, err := service.GetImpact(context.Background(), startDate, endDate, 10)

	if err != nil {
		t.Fatalf("GetImpact failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 results, got %d", len(results))
	}

	if results[0].AffectedUsers != 150 {
		t.Errorf("Expected 150 affected users, got %d", results[0].AffectedUsers)
	}

	if results[0].RevenueImpact != 2500.00 {
		t.Errorf("Expected revenue impact 2500.00, got %f", results[0].RevenueImpact)
	}

	if results[1].SeverityScore < 9.0 {
		t.Errorf("Expected severity score >= 9.0, got %f", results[1].SeverityScore)
	}
}

func TestGetErrorRootCauses(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorRootCausesFunc: func(ctx context.Context, sd, ed string, limit int) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"cause":             "database_pool_exhaustion",
					"error_count":       float64(250),
					"percentage":        float64(45.5),
					"first_occurrence":  startDate.Add(2 * time.Hour),
					"last_occurrence":   endDate.Add(-1 * time.Hour),
					"affected_users":    float64(120),
				},
				{
					"cause":             "memory_leak_in_cache",
					"error_count":       float64(180),
					"percentage":        float64(32.7),
					"first_occurrence":  startDate.Add(5 * time.Hour),
					"last_occurrence":   endDate.Add(-30 * time.Minute),
					"affected_users":    float64(85),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	results, err := service.GetRootCauses(context.Background(), startDate, endDate, 10)

	if err != nil {
		t.Fatalf("GetRootCauses failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 results, got %d", len(results))
	}

	if results[0].Cause != "database_pool_exhaustion" {
		t.Errorf("Expected cause 'database_pool_exhaustion', got '%s'", results[0].Cause)
	}

	if results[0].ErrorCount != 250 {
		t.Errorf("Expected error count 250, got %d", results[0].ErrorCount)
	}

	if results[0].Percentage != 45.5 {
		t.Errorf("Expected percentage 45.5, got %f", results[0].Percentage)
	}
}

func TestGetErrorMTTR(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorMTTRFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"error_type":              "database_error",
					"resolved_count":          float64(45),
					"mean_time_to_resolve_seconds": float64(3600),
					"median_time_seconds":     float64(1800),
					"p95_time_seconds":        float64(7200),
				},
				{
					"error_type":              "api_timeout",
					"resolved_count":          float64(28),
					"mean_time_to_resolve_seconds": float64(900),
					"median_time_seconds":     float64(600),
					"p95_time_seconds":        float64(1800),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	results, err := service.GetMTTR(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetMTTR failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 results, got %d", len(results))
	}

	if results[0].ErrorType != "database_error" {
		t.Errorf("Expected error_type 'database_error', got '%s'", results[0].ErrorType)
	}

	if results[0].ResolvedCount != 45 {
		t.Errorf("Expected resolved_count 45, got %d", results[0].ResolvedCount)
	}

	expectedDuration := time.Duration(3600) * time.Second
	if results[0].MeanTimeToResolve != expectedDuration {
		t.Errorf("Expected MTTR %v, got %v", expectedDuration, results[0].MeanTimeToResolve)
	}
}

func TestGetErrorClustering(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorClusteringFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"cluster_id":      "cluster_001",
					"error_count":     float64(85),
					"sample_errors":   []interface{}{"err_001", "err_002", "err_003"},
					"common_patterns": []interface{}{"null_pointer_exception", "in_payment_module"},
					"first_seen":      startDate.Add(2 * time.Hour),
					"last_seen":       endDate.Add(-5 * time.Hour),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	results, err := service.GetClustering(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetClustering failed: %v", err)
	}

	if len(results) != 1 {
		t.Errorf("Expected 1 result, got %d", len(results))
	}

	if results[0].ClusterID != "cluster_001" {
		t.Errorf("Expected cluster_id 'cluster_001', got '%s'", results[0].ClusterID)
	}

	if results[0].ErrorCount != 85 {
		t.Errorf("Expected error_count 85, got %d", results[0].ErrorCount)
	}

	if len(results[0].SampleErrors) != 3 {
		t.Errorf("Expected 3 sample errors, got %d", len(results[0].SampleErrors))
	}
}

func TestGetErrorAffectedUsers(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorAffectedUsersFunc: func(ctx context.Context, sd, ed, errorType string) (int64, error) {
			return 425, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	result, err := service.GetAffectedUsers(context.Background(), startDate, endDate, "payment_error")

	if err != nil {
		t.Fatalf("GetAffectedUsers failed: %v", err)
	}

	if result != 425 {
		t.Errorf("Expected 425 affected users, got %d", result)
	}
}

func TestGetErrorMTBF(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorMTBFFunc: func(ctx context.Context, sd, ed string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"period":                       "2026-01-18 to 2026-02-17",
				"failure_count":                float64(8),
				"mean_time_between_seconds":    float64(259200),
				"min_time_seconds":             float64(86400),
				"max_time_seconds":             float64(604800),
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	result, err := service.GetMTBF(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetMTBF failed: %v", err)
	}

	if result.FailureCount != 8 {
		t.Errorf("Expected failure_count 8, got %d", result.FailureCount)
	}

	expectedMTBF := time.Duration(259200) * time.Second
	if result.MeanTimeBetween != expectedMTBF {
		t.Errorf("Expected MTBF %v, got %v", expectedMTBF, result.MeanTimeBetween)
	}
}

func TestPredictErrors(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorPredictionsFunc: func(ctx context.Context, sd, ed string, periods int) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"timestamp":         endDate.Add(24 * time.Hour),
					"forecasted_value":  float64(18),
					"lower_bound":       float64(12),
					"upper_bound":       float64(24),
					"confidence":        float64(0.80),
				},
				{
					"timestamp":         endDate.Add(48 * time.Hour),
					"forecasted_value":  float64(16),
					"lower_bound":       float64(10),
					"upper_bound":       float64(22),
					"confidence":        float64(0.75),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	results, err := service.PredictErrors(context.Background(), startDate, endDate, 2)

	if err != nil {
		t.Fatalf("PredictErrors failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 forecast results, got %d", len(results))
	}

	if results[0].ForecastedValue != 18 {
		t.Errorf("Expected forecasted value 18, got %f", results[0].ForecastedValue)
	}

	if results[0].Confidence < 0.75 {
		t.Errorf("Expected confidence >= 0.75, got %f", results[0].Confidence)
	}
}

func TestGetErrorHotspots(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getErrorHotspotsFunc: func(ctx context.Context, sd, ed string, limit int) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"bottleneck_type":              "Database",
					"location":                     "query_user_profile",
					"impact_percentage":            float64(35.5),
					"affected_endpoints":           []interface{}{"/api/users", "/api/profile"},
					"recommendation":               "Optimize user profile query",
					"estimated_improvement_percent": float64(40.0),
				},
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	results, err := service.GetHotspots(context.Background(), startDate, endDate, 10)

	if err != nil {
		t.Fatalf("GetHotspots failed: %v", err)
	}

	if len(results) != 1 {
		t.Errorf("Expected 1 result, got %d", len(results))
	}

	if results[0].BottleneckType != "Database" {
		t.Errorf("Expected bottleneck_type 'Database', got '%s'", results[0].BottleneckType)
	}

	if results[0].ImpactPercentage != 35.5 {
		t.Errorf("Expected impact 35.5, got %f", results[0].ImpactPercentage)
	}
}

func TestErrorExport(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		exportAnalyticsFunc: func(ctx context.Context, sd, ed string, metrics []string, format string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"export_id":  "export_err_456",
				"status":     "processing",
				"created_at": time.Now(),
				"expires_at": time.Now().AddDate(0, 0, 7),
				"format":     format,
				"metrics":    metrics,
			}, nil
		},
	}

	service := NewErrorAnalyticsService(mockRepo)
	result, err := service.Export(context.Background(), &dto.AnalyticsExportRequest{
		Format:    "json",
		StartDate: startDate,
		EndDate:   endDate,
		Metrics:   []string{"error_count", "severity_distribution"},
	})

	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}

	if result.Status != "processing" {
		t.Errorf("Expected status 'processing', got '%s'", result.Status)
	}

	if result.ExportID == "" {
		t.Error("Expected non-empty export_id")
	}
}
