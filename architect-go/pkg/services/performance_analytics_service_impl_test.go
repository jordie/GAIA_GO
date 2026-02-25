package services

import (
	"context"
	"testing"
	"time"

	"architect-go/pkg/dto"
)

// Tests for PerformanceAnalyticsService

func TestGetLatency(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getLatencyMetricsFunc: func(ctx context.Context, sd, ed, g string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"timestamp": startDate,
					"p50":       float64(45.5),
					"p95":       float64(125.3),
					"p99":       float64(250.8),
					"mean":      float64(78.2),
					"min":       float64(12.5),
					"max":       float64(1500.0),
					"std_dev":   float64(85.3),
				},
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	results, err := service.GetLatency(context.Background(), startDate, endDate, "day")

	if err != nil {
		t.Fatalf("GetLatency failed: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected results, got empty")
	}

	if results[0].P95 > 150 {
		t.Errorf("Expected P95 <= 150, got %f", results[0].P95)
	}

	if results[0].Mean < 0 {
		t.Errorf("Expected mean >= 0, got %f", results[0].Mean)
	}
}

func TestGetThroughput(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getThroughputMetricsFunc: func(ctx context.Context, sd, ed, g string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"timestamp":       startDate,
					"requests_per_sec": float64(1250),
					"success_per_sec":  float64(1243),
					"errors_per_sec":   float64(7),
					"peak_throughput":  float64(2100),
				},
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	results, err := service.GetThroughput(context.Background(), startDate, endDate, "hour")

	if err != nil {
		t.Fatalf("GetThroughput failed: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected results, got empty")
	}

	if results[0].RequestsPerSec < 1000 {
		t.Errorf("Expected RequestsPerSec >= 1000, got %f", results[0].RequestsPerSec)
	}

	if results[0].ErrorsPerSec < 0 {
		t.Errorf("Expected ErrorsPerSec >= 0, got %f", results[0].ErrorsPerSec)
	}
}

func TestGetAvailability(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getAvailabilityMetricsFunc: func(ctx context.Context, sd, ed string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"period":                       "2026-01-18 to 2026-02-17",
				"up_time_seconds":              float64(2592000),
				"down_time_seconds":            float64(3600),
				"availability_percent":        float64(99.865),
				"error_budget_used_percent":    float64(0.135),
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	result, err := service.GetAvailability(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetAvailability failed: %v", err)
	}

	if result.AvailabilityPercent < 99.0 {
		t.Errorf("Expected availability >= 99.0, got %f", result.AvailabilityPercent)
	}

	if result.ErrorBudgetUsed > 1.0 {
		t.Errorf("Expected error budget <= 1.0, got %f", result.ErrorBudgetUsed)
	}
}

func TestGetSLOTracking(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getSLOTrackingFunc: func(ctx context.Context, sd, ed, sloName string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"slo_name":              sloName,
				"target":                float64(99.95),
				"current":               float64(99.92),
				"status":                "at_risk",
				"error_budget":          float64(0.048),
				"remaining_budget":      float64(0.024),
				"projected_status_end_of_month": "at_risk",
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	result, err := service.GetSLOTracking(context.Background(), startDate, endDate, "availability")

	if err != nil {
		t.Fatalf("GetSLOTracking failed: %v", err)
	}

	if result.Target != 99.95 {
		t.Errorf("Expected target 99.95, got %f", result.Target)
	}

	if result.Current > result.Target {
		t.Errorf("Current (%f) should be <= target (%f)", result.Current, result.Target)
	}

	if result.Status != "at_risk" {
		t.Errorf("Expected status 'at_risk', got '%s'", result.Status)
	}
}

func TestGetBottlenecks(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getPerformanceBottlenecksFunc: func(ctx context.Context, sd, ed string, limit int) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"bottleneck_type":              "Database",
					"location":                     "user_query_index",
					"impact_percentage":            float64(42.5),
					"affected_endpoints":           []interface{}{"/api/users", "/api/search"},
					"recommendation":               "Add database index on created_at",
					"estimated_improvement_percent": float64(35.0),
				},
				{
					"bottleneck_type":              "External API",
					"location":                     "payment_gateway",
					"impact_percentage":            float64(28.3),
					"affected_endpoints":           []interface{}{"/api/checkout", "/api/payments"},
					"recommendation":               "Implement caching for payment status",
					"estimated_improvement_percent": float64(25.0),
				},
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	results, err := service.GetBottlenecks(context.Background(), startDate, endDate, 10)

	if err != nil {
		t.Fatalf("GetBottlenecks failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 bottlenecks, got %d", len(results))
	}

	if results[0].BottleneckType != "Database" {
		t.Errorf("Expected bottleneck_type 'Database', got '%s'", results[0].BottleneckType)
	}

	if results[0].ImpactPercentage < 0 || results[0].ImpactPercentage > 100 {
		t.Errorf("Expected impact between 0-100, got %f", results[0].ImpactPercentage)
	}
}

func TestDetectDegradation(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		detectPerformanceDegradationFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"timestamp":              endDate.Add(-12 * time.Hour),
					"expected_value":         float64(85.0),
					"actual_value":           float64(245.0),
					"deviation_percentage":   float64(188.0),
					"anomaly_score":          float64(0.87),
					"description":            "Performance degradation detected",
				},
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	results, err := service.DetectDegradation(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("DetectDegradation failed: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected degradation results, got empty")
	}

	if results[0].AnomalyScore < 0.8 {
		t.Errorf("Expected anomaly score >= 0.8, got %f", results[0].AnomalyScore)
	}
}

func TestComparePerformance(t *testing.T) {
	period1Start := time.Now().AddDate(0, 0, -60)
	period1End := time.Now().AddDate(0, 0, -30)
	period2Start := time.Now().AddDate(0, 0, -30)
	period2End := time.Now()

	mockRepo := &MockAnalyticsRepository{
		comparePerformanceFunc: func(ctx context.Context, p1s, p1e, p2s, p2e string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"period_1": map[string]interface{}{
					"start_date":     p1s,
					"end_date":       p1e,
					"avg_latency_ms": float64(95.5),
					"request_count":  float64(50000),
				},
				"period_2": map[string]interface{}{
					"start_date":     p2s,
					"end_date":       p2e,
					"avg_latency_ms": float64(78.3),
					"request_count":  float64(62000),
				},
				"comparison": map[string]interface{}{
					"latency_change_percent": float64(-18.0),
					"request_change_percent": float64(24.0),
					"improvement":            true,
				},
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	result, err := service.ComparePerformance(context.Background(), period1Start, period1End, period2Start, period2End)

	if err != nil {
		t.Fatalf("ComparePerformance failed: %v", err)
	}

	if result == nil {
		t.Error("Expected comparison result, got nil")
	}

	if comparison, ok := result["comparison"].(map[string]interface{}); ok {
		if improvement, ok := comparison["improvement"].(bool); ok && !improvement {
			t.Error("Expected improvement to be true")
		}
	}
}

func TestGetOptimizationSuggestions(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getOptimizationSuggestionsFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"bottleneck_type":              "Database",
					"location":                     "query_slow_users",
					"impact_percentage":            float64(25.5),
					"recommendation":               "Add index on created_at column",
					"estimated_improvement_percent": float64(35.0),
				},
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	results, err := service.GetOptimizationSuggestions(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetOptimizationSuggestions failed: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected optimization suggestions")
	}

	if results[0].EstimatedImprovement <= 0 {
		t.Errorf("Expected positive improvement estimate, got %f", results[0].EstimatedImprovement)
	}
}

func TestPredictCapacity(t *testing.T) {
	mockRepo := &MockAnalyticsRepository{
		predictCapacityNeedsFunc: func(ctx context.Context, growthRate float64, periods int) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"timestamp":         time.Now().AddDate(0, 1, 0),
					"forecasted_value":  float64(1050),
					"lower_bound":       float64(945),
					"upper_bound":       float64(1155),
					"confidence":        float64(0.85),
				},
				{
					"timestamp":         time.Now().AddDate(0, 2, 0),
					"forecasted_value":  float64(1103),
					"lower_bound":       float64(992),
					"upper_bound":       float64(1214),
					"confidence":        float64(0.80),
				},
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	results, err := service.PredictCapacity(context.Background(), 0.05, 2)

	if err != nil {
		t.Fatalf("PredictCapacity failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 forecast results, got %d", len(results))
	}

	if results[0].ForecastedValue <= 0 {
		t.Errorf("Expected positive forecasted value, got %f", results[0].ForecastedValue)
	}

	if results[0].Confidence < 0.7 {
		t.Errorf("Expected confidence >= 0.7, got %f", results[0].Confidence)
	}
}

func TestPerformanceExport(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		exportAnalyticsFunc: func(ctx context.Context, sd, ed string, metrics []string, format string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"export_id":  "export_perf_789",
				"status":     "completed",
				"created_at": time.Now(),
				"expires_at": time.Now().AddDate(0, 0, 7),
			}, nil
		},
	}

	service := NewPerformanceAnalyticsService(mockRepo)
	result, err := service.Export(context.Background(), &dto.AnalyticsExportRequest{
		Format:    "excel",
		StartDate: startDate,
		EndDate:   endDate,
		Metrics:   []string{"latency_p95", "throughput", "availability"},
	})

	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}

	if result.Status != "completed" {
		t.Errorf("Expected status 'completed', got '%s'", result.Status)
	}
}
