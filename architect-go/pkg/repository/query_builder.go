package repository

import (
	"fmt"
	"strings"
	"time"
)

// QueryBuilder builds complex SQL queries for analytics
type QueryBuilder struct {
	selectFields []string
	fromTable    string
	joins        []string
	whereClause  string
	groupBy      []string
	orderBy      string
	limit        int
	offset       int
	params       []interface{}
}

// NewQueryBuilder creates a new query builder
func NewQueryBuilder() *QueryBuilder {
	return &QueryBuilder{
		selectFields: []string{},
		joins:        []string{},
		params:       []interface{}{},
	}
}

// Select adds fields to select
func (qb *QueryBuilder) Select(fields ...string) *QueryBuilder {
	qb.selectFields = append(qb.selectFields, fields...)
	return qb
}

// From sets the main table
func (qb *QueryBuilder) From(table string) *QueryBuilder {
	qb.fromTable = table
	return qb
}

// Join adds a join clause
func (qb *QueryBuilder) Join(joinClause string) *QueryBuilder {
	qb.joins = append(qb.joins, joinClause)
	return qb
}

// Where adds a where condition
func (qb *QueryBuilder) Where(condition string, params ...interface{}) *QueryBuilder {
	if qb.whereClause == "" {
		qb.whereClause = condition
	} else {
		qb.whereClause += " AND " + condition
	}
	qb.params = append(qb.params, params...)
	return qb
}

// GroupBy adds group by clause
func (qb *QueryBuilder) GroupBy(fields ...string) *QueryBuilder {
	qb.groupBy = append(qb.groupBy, fields...)
	return qb
}

// OrderBy sets order by clause
func (qb *QueryBuilder) OrderBy(field, direction string) *QueryBuilder {
	if qb.orderBy == "" {
		qb.orderBy = fmt.Sprintf("%s %s", field, direction)
	} else {
		qb.orderBy += fmt.Sprintf(", %s %s", field, direction)
	}
	return qb
}

// Limit sets limit
func (qb *QueryBuilder) Limit(limit int) *QueryBuilder {
	qb.limit = limit
	return qb
}

// Offset sets offset
func (qb *QueryBuilder) Offset(offset int) *QueryBuilder {
	qb.offset = offset
	return qb
}

// Build generates the SQL query
func (qb *QueryBuilder) Build() (string, []interface{}) {
	var query strings.Builder

	// SELECT clause
	if len(qb.selectFields) == 0 {
		query.WriteString("SELECT *")
	} else {
		query.WriteString("SELECT " + strings.Join(qb.selectFields, ", "))
	}

	// FROM clause
	query.WriteString(" FROM " + qb.fromTable)

	// JOIN clauses
	for _, join := range qb.joins {
		query.WriteString(" " + join)
	}

	// WHERE clause
	if qb.whereClause != "" {
		query.WriteString(" WHERE " + qb.whereClause)
	}

	// GROUP BY clause
	if len(qb.groupBy) > 0 {
		query.WriteString(" GROUP BY " + strings.Join(qb.groupBy, ", "))
	}

	// ORDER BY clause
	if qb.orderBy != "" {
		query.WriteString(" ORDER BY " + qb.orderBy)
	}

	// LIMIT clause
	if qb.limit > 0 {
		query.WriteString(fmt.Sprintf(" LIMIT %d", qb.limit))
	}

	// OFFSET clause
	if qb.offset > 0 {
		query.WriteString(fmt.Sprintf(" OFFSET %d", qb.offset))
	}

	return query.String(), qb.params
}

// AdvancedFilterRequest represents advanced filtering options
type AdvancedFilterRequest struct {
	Filters      map[string]interface{} `json:"filters"`
	DateRange    *DateRangeFilter       `json:"date_range,omitempty"`
	Sorting      *SortingOption         `json:"sorting,omitempty"`
	Pagination   *PaginationOption      `json:"pagination,omitempty"`
	Aggregations []string               `json:"aggregations,omitempty"`
	GroupBy      []string               `json:"group_by,omitempty"`
	Having       map[string]interface{} `json:"having,omitempty"`
}

// DateRangeFilter represents a date range filter
type DateRangeFilter struct {
	StartDate time.Time `json:"start_date"`
	EndDate   time.Time `json:"end_date"`
	Field     string    `json:"field"`
}

// SortingOption represents sorting configuration
type SortingOption struct {
	Field     string `json:"field"`
	Direction string `json:"direction"` // "asc" or "desc"
}

// PaginationOption represents pagination configuration
type PaginationOption struct {
	Limit  int `json:"limit"`
	Offset int `json:"offset"`
}

// ApplyAdvancedFilter applies advanced filters to query builder
func (qb *QueryBuilder) ApplyAdvancedFilter(req *AdvancedFilterRequest) *QueryBuilder {
	// Apply base filters
	for key, value := range req.Filters {
		qb.Where(fmt.Sprintf("%s = ?", key), value)
	}

	// Apply date range
	if req.DateRange != nil {
		qb.Where(
			fmt.Sprintf("%s BETWEEN ? AND ?", req.DateRange.Field),
			req.DateRange.StartDate,
			req.DateRange.EndDate,
		)
	}

	// Apply group by
	if len(req.GroupBy) > 0 {
		qb.GroupBy(req.GroupBy...)
	}

	// Apply sorting
	if req.Sorting != nil {
		qb.OrderBy(req.Sorting.Field, req.Sorting.Direction)
	}

	// Apply pagination
	if req.Pagination != nil {
		qb.Limit(req.Pagination.Limit)
		qb.Offset(req.Pagination.Offset)
	}

	return qb
}

// QueryExecutor handles query execution results
type QueryExecutor struct {
	query  string
	params []interface{}
}

// NewQueryExecutor creates a new query executor
func NewQueryExecutor(query string, params []interface{}) *QueryExecutor {
	return &QueryExecutor{
		query:  query,
		params: params,
	}
}

// GetQuery returns the SQL query
func (qe *QueryExecutor) GetQuery() string {
	return qe.query
}

// GetParams returns the query parameters
func (qe *QueryExecutor) GetParams() []interface{} {
	return qe.params
}

// MetricsAggregator handles metrics aggregation
type MetricsAggregator struct {
	data   []map[string]interface{}
	fields []string
}

// NewMetricsAggregator creates a new metrics aggregator
func NewMetricsAggregator(data []map[string]interface{}, fields []string) *MetricsAggregator {
	return &MetricsAggregator{
		data:   data,
		fields: fields,
	}
}

// Sum calculates sum of a numeric field
func (ma *MetricsAggregator) Sum(field string) int64 {
	var total int64
	for _, row := range ma.data {
		if val, ok := row[field]; ok {
			if num, ok := val.(int64); ok {
				total += num
			}
		}
	}
	return total
}

// Average calculates average of a numeric field
func (ma *MetricsAggregator) Average(field string) float64 {
	total := ma.Sum(field)
	if len(ma.data) == 0 {
		return 0
	}
	return float64(total) / float64(len(ma.data))
}

// Count returns count of records
func (ma *MetricsAggregator) Count() int64 {
	return int64(len(ma.data))
}

// GroupBy groups data by a field
func (ma *MetricsAggregator) GroupBy(field string) map[string][]map[string]interface{} {
	groups := make(map[string][]map[string]interface{})
	for _, row := range ma.data {
		if key, ok := row[field]; ok {
			keyStr := fmt.Sprintf("%v", key)
			groups[keyStr] = append(groups[keyStr], row)
		}
	}
	return groups
}
