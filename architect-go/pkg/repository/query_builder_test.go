package repository

import (
	"testing"
	"time"
)

func TestQueryBuilder_Build(t *testing.T) {
	qb := NewQueryBuilder().
		Select("id", "name", "email").
		From("users").
		Where("active = ?", true).
		OrderBy("created_at", "desc").
		Limit(10).
		Offset(0)

	query, params := qb.Build()

	if query == "" {
		t.Error("expected non-empty query")
	}

	if len(params) != 1 {
		t.Errorf("expected 1 parameter, got %d", len(params))
	}

	if params[0] != true {
		t.Errorf("expected true, got %v", params[0])
	}
}

func TestQueryBuilder_WithJoin(t *testing.T) {
	qb := NewQueryBuilder().
		Select("users.id", "users.name", "COUNT(orders.id) as order_count").
		From("users").
		Join("LEFT JOIN orders ON users.id = orders.user_id").
		GroupBy("users.id", "users.name").
		OrderBy("order_count", "desc")

	query, _ := qb.Build()

	if query == "" {
		t.Error("expected non-empty query")
	}

	if !contains(query, "LEFT JOIN") {
		t.Error("expected JOIN clause in query")
	}

	if !contains(query, "GROUP BY") {
		t.Error("expected GROUP BY clause in query")
	}
}

func TestQueryBuilder_WithDateRange(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	qb := NewQueryBuilder().
		Select("*").
		From("events").
		Where("created_at BETWEEN ? AND ?", startDate, endDate)

	_, params := qb.Build()

	if len(params) != 2 {
		t.Errorf("expected 2 parameters, got %d", len(params))
	}
}

func TestAdvancedFilterRequest_ApplyToBuilder(t *testing.T) {
	req := &AdvancedFilterRequest{
		Filters: map[string]interface{}{
			"status": "active",
		},
		DateRange: &DateRangeFilter{
			StartDate: time.Now().AddDate(0, 0, -7),
			EndDate:   time.Now(),
			Field:     "created_at",
		},
		Sorting: &SortingOption{
			Field:     "created_at",
			Direction: "desc",
		},
		Pagination: &PaginationOption{
			Limit:  20,
			Offset: 0,
		},
		GroupBy: []string{"category"},
	}

	qb := NewQueryBuilder().
		From("items").
		ApplyAdvancedFilter(req)

	query, params := qb.Build()

	if query == "" {
		t.Error("expected non-empty query")
	}

	if len(params) != 3 { // status, startDate, endDate
		t.Errorf("expected 3 parameters, got %d", len(params))
	}

	if !contains(query, "GROUP BY") {
		t.Error("expected GROUP BY in query")
	}

	if !contains(query, "LIMIT 20") {
		t.Error("expected LIMIT 20 in query")
	}
}

func TestMetricsAggregator_Sum(t *testing.T) {
	data := []map[string]interface{}{
		{"id": 1, "amount": int64(100)},
		{"id": 2, "amount": int64(200)},
		{"id": 3, "amount": int64(300)},
	}

	agg := NewMetricsAggregator(data, []string{"id", "amount"})
	sum := agg.Sum("amount")

	if sum != 600 {
		t.Errorf("expected sum 600, got %d", sum)
	}
}

func TestMetricsAggregator_Average(t *testing.T) {
	data := []map[string]interface{}{
		{"id": 1, "score": int64(80)},
		{"id": 2, "score": int64(90)},
		{"id": 3, "score": int64(100)},
	}

	agg := NewMetricsAggregator(data, []string{"id", "score"})
	avg := agg.Average("score")

	if avg != 90.0 {
		t.Errorf("expected average 90, got %f", avg)
	}
}

func TestMetricsAggregator_Count(t *testing.T) {
	data := []map[string]interface{}{
		{"id": 1},
		{"id": 2},
		{"id": 3},
	}

	agg := NewMetricsAggregator(data, []string{"id"})
	count := agg.Count()

	if count != 3 {
		t.Errorf("expected count 3, got %d", count)
	}
}

func TestMetricsAggregator_GroupBy(t *testing.T) {
	data := []map[string]interface{}{
		{"category": "A", "value": 100},
		{"category": "B", "value": 200},
		{"category": "A", "value": 150},
	}

	agg := NewMetricsAggregator(data, []string{"category", "value"})
	groups := agg.GroupBy("category")

	if len(groups) != 2 {
		t.Errorf("expected 2 groups, got %d", len(groups))
	}

	if len(groups["A"]) != 2 {
		t.Errorf("expected 2 items in group A, got %d", len(groups["A"]))
	}

	if len(groups["B"]) != 1 {
		t.Errorf("expected 1 item in group B, got %d", len(groups["B"]))
	}
}

func contains(s, substr string) bool {
	return len(s) > 0 && len(substr) > 0 && (s == substr || len(s) > len(substr) && (s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || len(s) > len(substr)+1))
}
