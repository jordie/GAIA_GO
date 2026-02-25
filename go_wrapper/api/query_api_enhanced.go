package api

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/architect/go_wrapper/data"
)

// QueryFilter represents a single filter condition
type QueryFilter struct {
	Field    string      `json:"field"`
	Operator string      `json:"operator"` // eq, ne, gt, gte, lt, lte, in, like, regex
	Value    interface{} `json:"value"`
}

// QueryParams represents advanced query parameters
type QueryParams struct {
	Filters      []QueryFilter          `json:"filters"`
	Logic        string                 `json:"logic"`         // AND or OR
	Sort         string                 `json:"sort"`          // field to sort by
	SortOrder    string                 `json:"sort_order"`    // asc or desc
	Limit        int                    `json:"limit"`
	Offset       int                    `json:"offset"`
	Aggregations map[string]interface{} `json:"aggregations"` // aggregation definitions
	GroupBy      []string               `json:"group_by"`     // fields to group by
}

// AggregationResult represents aggregation computation results
type AggregationResult struct {
	Count   int                    `json:"count"`
	Sum     float64                `json:"sum,omitempty"`
	Avg     float64                `json:"avg,omitempty"`
	Min     float64                `json:"min,omitempty"`
	Max     float64                `json:"max,omitempty"`
	Groups  map[string]interface{} `json:"groups,omitempty"`
	Buckets []TimeBucket           `json:"buckets,omitempty"`
}

// TimeBucket represents a time-based aggregation bucket
type TimeBucket struct {
	Timestamp time.Time              `json:"timestamp"`
	Key       string                 `json:"key"`
	Count     int                    `json:"count"`
	Metrics   map[string]interface{} `json:"metrics"`
}

// HandleAdvancedQuery handles POST /api/query/advanced
func (qa *QueryAPI) HandleAdvancedQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var params QueryParams
	if err := json.NewDecoder(r.Body).Decode(&params); err != nil {
		http.Error(w, fmt.Sprintf("Invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	// Set defaults
	if params.Logic == "" {
		params.Logic = "AND"
	}
	if params.Limit == 0 {
		params.Limit = 100
	}
	if params.SortOrder == "" {
		params.SortOrder = "desc"
	}

	// Build SQL query
	query, args := qa.buildAdvancedQuery(params)

	// Execute query
	db := qa.extractionStore.GetDB()
	rows, err := db.Query(query, args...)
	if err != nil {
		http.Error(w, fmt.Sprintf("Query failed: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	// Scan results
	extractions, err := qa.scanExtractions(rows)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to scan results: %v", err), http.StatusInternalServerError)
		return
	}

	// Apply aggregations if requested
	var aggregations map[string]interface{}
	if len(params.Aggregations) > 0 || len(params.GroupBy) > 0 {
		aggregations = qa.computeAggregations(extractions, params)
	}

	response := map[string]interface{}{
		"extractions":  extractions,
		"total":        len(extractions),
		"aggregations": aggregations,
		"params":       params,
	}

	writeJSON(w, http.StatusOK, response)
}

// buildAdvancedQuery constructs SQL query from parameters
func (qa *QueryAPI) buildAdvancedQuery(params QueryParams) (string, []interface{}) {
	query := `
		SELECT id, agent_name, session_id, timestamp, event_type, pattern,
		       matched_value, original_line, line_number, metadata_json,
		       code_block_language, risk_level, auto_confirmable
		FROM extraction_events
	`

	args := make([]interface{}, 0)
	whereClauses := make([]string, 0)

	// Build WHERE clauses from filters
	for _, filter := range params.Filters {
		clause, arg := qa.buildFilterClause(filter)
		if clause != "" {
			whereClauses = append(whereClauses, clause)
			if arg != nil {
				args = append(args, arg)
			}
		}
	}

	// Combine WHERE clauses
	if len(whereClauses) > 0 {
		logic := " AND "
		if strings.ToUpper(params.Logic) == "OR" {
			logic = " OR "
		}
		query += " WHERE " + strings.Join(whereClauses, logic)
	}

	// Add ORDER BY
	if params.Sort != "" {
		query += fmt.Sprintf(" ORDER BY %s %s", params.Sort, strings.ToUpper(params.SortOrder))
	} else {
		query += " ORDER BY timestamp DESC"
	}

	// Add LIMIT and OFFSET
	query += fmt.Sprintf(" LIMIT %d OFFSET %d", params.Limit, params.Offset)

	return query, args
}

// buildFilterClause builds a single WHERE clause
func (qa *QueryAPI) buildFilterClause(filter QueryFilter) (string, interface{}) {
	field := filter.Field
	operator := strings.ToLower(filter.Operator)
	value := filter.Value

	switch operator {
	case "eq", "=":
		return fmt.Sprintf("%s = ?", field), value
	case "ne", "!=":
		return fmt.Sprintf("%s != ?", field), value
	case "gt", ">":
		return fmt.Sprintf("%s > ?", field), value
	case "gte", ">=":
		return fmt.Sprintf("%s >= ?", field), value
	case "lt", "<":
		return fmt.Sprintf("%s < ?", field), value
	case "lte", "<=":
		return fmt.Sprintf("%s <= ?", field), value
	case "like":
		return fmt.Sprintf("%s LIKE ?", field), value
	case "in":
		// Handle IN operator with array values
		if arr, ok := value.([]interface{}); ok {
			placeholders := make([]string, len(arr))
			for i := range placeholders {
				placeholders[i] = "?"
			}
			return fmt.Sprintf("%s IN (%s)", field, strings.Join(placeholders, ",")), arr[0]
		}
	case "between":
		// Handle BETWEEN operator
		if arr, ok := value.([]interface{}); ok && len(arr) == 2 {
			return fmt.Sprintf("%s BETWEEN ? AND ?", field), arr
		}
	case "isnull":
		return fmt.Sprintf("%s IS NULL", field), nil
	case "isnotnull":
		return fmt.Sprintf("%s IS NOT NULL", field), nil
	}

	return "", nil
}

// computeAggregations computes aggregations on results
func (qa *QueryAPI) computeAggregations(extractions []*data.ExtractionEvent, params QueryParams) map[string]interface{} {
	result := make(map[string]interface{})

	// Group by if specified
	if len(params.GroupBy) > 0 {
		groups := qa.groupExtractions(extractions, params.GroupBy)
		result["groups"] = groups
	}

	// Compute basic aggregations
	if len(params.Aggregations) > 0 {
		for aggName, aggDef := range params.Aggregations {
			aggDefMap, ok := aggDef.(map[string]interface{})
			if !ok {
				continue
			}

			aggType := aggDefMap["type"].(string)
			aggField := ""
			if field, ok := aggDefMap["field"].(string); ok {
				aggField = field
			}

			switch aggType {
			case "count":
				result[aggName] = len(extractions)
			case "value_count":
				result[aggName] = qa.countDistinct(extractions, aggField)
			case "terms":
				result[aggName] = qa.termsAggregation(extractions, aggField, 10)
			case "stats":
				result[aggName] = qa.statsAggregation(extractions, aggField)
			case "percentiles":
				result[aggName] = qa.percentilesAggregation(extractions, aggField, []float64{50, 95, 99})
			case "date_histogram":
				interval := "hour"
				if iv, ok := aggDefMap["interval"].(string); ok {
					interval = iv
				}
				result[aggName] = qa.dateHistogram(extractions, interval)
			}
		}
	}

	return result
}

// groupExtractions groups extractions by specified fields
func (qa *QueryAPI) groupExtractions(extractions []*data.ExtractionEvent, groupBy []string) map[string][]interface{} {
	groups := make(map[string][]interface{})

	for _, ext := range extractions {
		key := qa.getGroupKey(ext, groupBy)
		if groups[key] == nil {
			groups[key] = make([]interface{}, 0)
		}
		groups[key] = append(groups[key], ext)
	}

	return groups
}

// getGroupKey generates a group key from extraction and fields
func (qa *QueryAPI) getGroupKey(ext *data.ExtractionEvent, fields []string) string {
	parts := make([]string, len(fields))
	for i, field := range fields {
		switch field {
		case "event_type":
			parts[i] = ext.EventType
		case "pattern":
			parts[i] = ext.Pattern
		case "risk_level":
			parts[i] = ext.RiskLevel
		case "agent_name":
			parts[i] = ext.AgentName
		default:
			parts[i] = "unknown"
		}
	}
	return strings.Join(parts, "|")
}

// countDistinct counts unique values in a field
func (qa *QueryAPI) countDistinct(extractions []*data.ExtractionEvent, field string) int {
	seen := make(map[string]bool)
	for _, ext := range extractions {
		value := qa.getFieldValue(ext, field)
		seen[value] = true
	}
	return len(seen)
}

// termsAggregation returns top N terms by count
func (qa *QueryAPI) termsAggregation(extractions []*data.ExtractionEvent, field string, limit int) map[string]interface{} {
	counts := make(map[string]int)
	for _, ext := range extractions {
		value := qa.getFieldValue(ext, field)
		counts[value]++
	}

	// Sort by count
	type termCount struct {
		Term  string `json:"term"`
		Count int    `json:"count"`
	}

	terms := make([]termCount, 0, len(counts))
	for term, count := range counts {
		terms = append(terms, termCount{Term: term, Count: count})
	}

	sort.Slice(terms, func(i, j int) bool {
		return terms[i].Count > terms[j].Count
	})

	if len(terms) > limit {
		terms = terms[:limit]
	}

	return map[string]interface{}{
		"buckets":     terms,
		"total_terms": len(counts),
	}
}

// statsAggregation computes statistical metrics
func (qa *QueryAPI) statsAggregation(extractions []*data.ExtractionEvent, field string) map[string]interface{} {
	values := make([]float64, 0)

	for _, ext := range extractions {
		// For now, use line numbers as numeric values
		if field == "line_number" {
			values = append(values, float64(ext.LineNumber))
		}
	}

	if len(values) == 0 {
		return map[string]interface{}{
			"count": 0,
		}
	}

	sort.Float64s(values)

	sum := 0.0
	for _, v := range values {
		sum += v
	}

	return map[string]interface{}{
		"count": len(values),
		"min":   values[0],
		"max":   values[len(values)-1],
		"avg":   sum / float64(len(values)),
		"sum":   sum,
	}
}

// percentilesAggregation computes percentile values
func (qa *QueryAPI) percentilesAggregation(extractions []*data.ExtractionEvent, field string, percentiles []float64) map[string]interface{} {
	values := make([]float64, 0)

	for _, ext := range extractions {
		if field == "line_number" {
			values = append(values, float64(ext.LineNumber))
		}
	}

	if len(values) == 0 {
		return map[string]interface{}{"count": 0}
	}

	sort.Float64s(values)

	result := make(map[string]interface{})
	for _, p := range percentiles {
		index := int(float64(len(values)) * p / 100.0)
		if index >= len(values) {
			index = len(values) - 1
		}
		key := fmt.Sprintf("p%.0f", p)
		result[key] = values[index]
	}

	return result
}

// dateHistogram creates time-based histogram
func (qa *QueryAPI) dateHistogram(extractions []*data.ExtractionEvent, interval string) map[string]interface{} {
	buckets := make(map[string]*TimeBucket)

	for _, ext := range extractions {
		bucketKey := qa.getBucketKey(ext.Timestamp, interval)

		if buckets[bucketKey] == nil {
			buckets[bucketKey] = &TimeBucket{
				Timestamp: qa.truncateTime(ext.Timestamp, interval),
				Key:       bucketKey,
				Count:     0,
				Metrics:   make(map[string]interface{}),
			}
		}

		buckets[bucketKey].Count++
	}

	// Convert to sorted slice
	bucketList := make([]TimeBucket, 0, len(buckets))
	for _, bucket := range buckets {
		bucketList = append(bucketList, *bucket)
	}

	sort.Slice(bucketList, func(i, j int) bool {
		return bucketList[i].Timestamp.Before(bucketList[j].Timestamp)
	})

	return map[string]interface{}{
		"buckets": bucketList,
		"total":   len(bucketList),
	}
}

// getBucketKey generates bucket key for time interval
func (qa *QueryAPI) getBucketKey(t time.Time, interval string) string {
	switch interval {
	case "minute":
		return t.Truncate(time.Minute).Format(time.RFC3339)
	case "hour":
		return t.Truncate(time.Hour).Format(time.RFC3339)
	case "day":
		return t.Truncate(24 * time.Hour).Format("2006-01-02")
	case "week":
		// Truncate to Monday
		weekday := t.Weekday()
		if weekday == 0 {
			weekday = 7
		}
		monday := t.AddDate(0, 0, -int(weekday)+1)
		return monday.Truncate(24 * time.Hour).Format("2006-01-02")
	case "month":
		return t.Format("2006-01")
	default:
		return t.Truncate(time.Hour).Format(time.RFC3339)
	}
}

// truncateTime truncates time to interval
func (qa *QueryAPI) truncateTime(t time.Time, interval string) time.Time {
	switch interval {
	case "minute":
		return t.Truncate(time.Minute)
	case "hour":
		return t.Truncate(time.Hour)
	case "day":
		return t.Truncate(24 * time.Hour)
	case "week":
		weekday := t.Weekday()
		if weekday == 0 {
			weekday = 7
		}
		monday := t.AddDate(0, 0, -int(weekday)+1)
		return monday.Truncate(24 * time.Hour)
	case "month":
		return time.Date(t.Year(), t.Month(), 1, 0, 0, 0, 0, t.Location())
	default:
		return t.Truncate(time.Hour)
	}
}

// getFieldValue extracts field value from extraction
func (qa *QueryAPI) getFieldValue(ext *data.ExtractionEvent, field string) string {
	switch field {
	case "event_type":
		return ext.EventType
	case "pattern":
		return ext.Pattern
	case "risk_level":
		return ext.RiskLevel
	case "agent_name":
		return ext.AgentName
	case "session_id":
		return ext.SessionID
	default:
		return ""
	}
}

// scanExtractions scans SQL rows into extraction events
func (qa *QueryAPI) scanExtractions(rows *sql.Rows) ([]*data.ExtractionEvent, error) {
	var extractions []*data.ExtractionEvent

	for rows.Next() {
		var event data.ExtractionEvent
		var metadataJSON sql.NullString
		var codeBlockLang sql.NullString
		var riskLevel sql.NullString

		err := rows.Scan(
			&event.ID,
			&event.AgentName,
			&event.SessionID,
			&event.Timestamp,
			&event.EventType,
			&event.Pattern,
			&event.MatchedValue,
			&event.OriginalLine,
			&event.LineNumber,
			&metadataJSON,
			&codeBlockLang,
			&riskLevel,
			&event.AutoConfirmable,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan extraction: %w", err)
		}

		// Parse metadata JSON
		if metadataJSON.Valid {
			if err := json.Unmarshal([]byte(metadataJSON.String), &event.Metadata); err != nil {
				return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
			}
		}

		if codeBlockLang.Valid {
			event.CodeBlockLang = codeBlockLang.String
		}

		if riskLevel.Valid {
			event.RiskLevel = riskLevel.String
		}

		extractions = append(extractions, &event)
	}

	return extractions, rows.Err()
}

// HandleSearchQuery handles GET /api/query/search
func (qa *QueryAPI) HandleSearchQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	searchTerm := query.Get("q")
	agentName := query.Get("agent")
	limitStr := query.Get("limit")

	if searchTerm == "" {
		http.Error(w, "search term (q) required", http.StatusBadRequest)
		return
	}

	limit := 100
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil {
			limit = parsed
		}
	}

	// Search across multiple fields
	searchPattern := "%" + searchTerm + "%"
	sqlQuery := `
		SELECT id, agent_name, session_id, timestamp, event_type, pattern,
		       matched_value, original_line, line_number, metadata_json,
		       code_block_language, risk_level, auto_confirmable
		FROM extraction_events
		WHERE (matched_value LIKE ? OR original_line LIKE ? OR pattern LIKE ?)
	`

	args := []interface{}{searchPattern, searchPattern, searchPattern}

	if agentName != "" {
		sqlQuery += " AND agent_name = ?"
		args = append(args, agentName)
	}

	sqlQuery += " ORDER BY timestamp DESC LIMIT ?"
	args = append(args, limit)

	// Execute query
	db := qa.extractionStore.GetDB()
	rows, err := db.Query(sqlQuery, args...)
	if err != nil {
		http.Error(w, fmt.Sprintf("Search failed: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	// Scan results
	extractions, err := qa.scanExtractions(rows)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to scan results: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"results":     extractions,
		"total":       len(extractions),
		"search_term": searchTerm,
		"agent":       agentName,
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleTrendAnalysis handles GET /api/query/trends
func (qa *QueryAPI) HandleTrendAnalysis(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	query := r.URL.Query()
	agentName := query.Get("agent")
	metric := query.Get("metric")    // event_count, error_rate, etc.
	interval := query.Get("interval") // hour, day, week
	days := 7

	if daysStr := query.Get("days"); daysStr != "" {
		if parsed, err := strconv.Atoi(daysStr); err == nil {
			days = parsed
		}
	}

	if agentName == "" {
		http.Error(w, "agent parameter required", http.StatusBadRequest)
		return
	}

	if interval == "" {
		interval = "hour"
	}

	// Get extractions for time range
	since := time.Now().AddDate(0, 0, -days)
	extractions, err := qa.extractionStore.GetExtractionsByAgent(agentName, 10000)
	if err != nil {
		http.Error(w, fmt.Sprintf("Query failed: %v", err), http.StatusInternalServerError)
		return
	}

	// Filter by time range
	filteredExtractions := make([]*data.ExtractionEvent, 0)
	for _, ext := range extractions {
		if ext.Timestamp.After(since) {
			filteredExtractions = append(filteredExtractions, ext)
		}
	}

	// Compute trend buckets
	buckets := qa.computeTrendBuckets(filteredExtractions, interval, metric)

	// Detect anomalies (simple moving average)
	anomalies := qa.detectAnomalies(buckets, 2.0) // 2 std deviations

	response := map[string]interface{}{
		"agent":     agentName,
		"metric":    metric,
		"interval":  interval,
		"days":      days,
		"buckets":   buckets,
		"anomalies": anomalies,
		"total":     len(filteredExtractions),
	}

	writeJSON(w, http.StatusOK, response)
}

// computeTrendBuckets computes metric values per time bucket
func (qa *QueryAPI) computeTrendBuckets(extractions []*data.ExtractionEvent, interval string, metric string) []TimeBucket {
	bucketMap := make(map[string]*TimeBucket)

	for _, ext := range extractions {
		key := qa.getBucketKey(ext.Timestamp, interval)

		if bucketMap[key] == nil {
			bucketMap[key] = &TimeBucket{
				Timestamp: qa.truncateTime(ext.Timestamp, interval),
				Key:       key,
				Count:     0,
				Metrics:   make(map[string]interface{}),
			}
		}

		bucket := bucketMap[key]
		bucket.Count++

		// Track error rate
		if ext.EventType == "error" {
			if bucket.Metrics["errors"] == nil {
				bucket.Metrics["errors"] = 0
			}
			bucket.Metrics["errors"] = bucket.Metrics["errors"].(int) + 1
		}
	}

	// Convert to sorted slice and compute derived metrics
	buckets := make([]TimeBucket, 0, len(bucketMap))
	for _, bucket := range bucketMap {
		// Compute error rate
		if bucket.Count > 0 {
			errors := 0
			if bucket.Metrics["errors"] != nil {
				errors = bucket.Metrics["errors"].(int)
			}
			bucket.Metrics["error_rate"] = float64(errors) / float64(bucket.Count)
		}

		buckets = append(buckets, *bucket)
	}

	sort.Slice(buckets, func(i, j int) bool {
		return buckets[i].Timestamp.Before(buckets[j].Timestamp)
	})

	return buckets
}

// detectAnomalies detects anomalous buckets using statistical methods
func (qa *QueryAPI) detectAnomalies(buckets []TimeBucket, threshold float64) []string {
	if len(buckets) < 3 {
		return []string{}
	}

	// Compute mean and std deviation of counts
	sum := 0.0
	for _, bucket := range buckets {
		sum += float64(bucket.Count)
	}
	mean := sum / float64(len(buckets))

	variance := 0.0
	for _, bucket := range buckets {
		diff := float64(bucket.Count) - mean
		variance += diff * diff
	}
	stdDev := 0.0
	if len(buckets) > 1 {
		stdDev = variance / float64(len(buckets)-1)
	}

	// Find anomalies
	anomalies := make([]string, 0)
	for _, bucket := range buckets {
		deviation := (float64(bucket.Count) - mean) / stdDev
		if deviation > threshold || deviation < -threshold {
			anomalies = append(anomalies, bucket.Key)
		}
	}

	return anomalies
}

// RegisterEnhancedQueryRoutes registers enhanced query routes
func (qa *QueryAPI) RegisterEnhancedQueryRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/query/advanced", qa.HandleAdvancedQuery)
	mux.HandleFunc("/api/query/search", qa.HandleSearchQuery)
	mux.HandleFunc("/api/query/trends", qa.HandleTrendAnalysis)
}
