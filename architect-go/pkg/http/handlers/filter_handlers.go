package handlers

import (
	"net/http"
	"strconv"
	"time"

	"architect-go/pkg/errors"
	"architect-go/pkg/repository"
)

// ParsePaginationParams parses pagination parameters from the request
func ParsePaginationParams(r *http.Request, defaultLimit, maxLimit int) (limit, offset int, err error) {
	limit = defaultLimit
	offset = 0

	if l := r.URL.Query().Get("limit"); l != "" {
		parsed, err := strconv.Atoi(l)
		if err != nil || parsed <= 0 {
			return 0, 0, errors.ValidationErrorf("INVALID_LIMIT", "Limit must be a positive integer")
		}
		if parsed > maxLimit {
			parsed = maxLimit
		}
		limit = parsed
	}

	if o := r.URL.Query().Get("offset"); o != "" {
		parsed, err := strconv.Atoi(o)
		if err != nil || parsed < 0 {
			return 0, 0, errors.ValidationErrorf("INVALID_OFFSET", "Offset must be a non-negative integer")
		}
		offset = parsed
	}

	return limit, offset, nil
}

// ParseTimeRange parses start_time and end_time query parameters (ISO 8601 format)
func ParseTimeRange(r *http.Request) (start, end *time.Time, err error) {
	startStr := r.URL.Query().Get("start_time")
	endStr := r.URL.Query().Get("end_time")

	if startStr != "" {
		startTime, err := time.Parse(time.RFC3339, startStr)
		if err != nil {
			return nil, nil, errors.ValidationErrorf("INVALID_START_TIME", "Invalid start_time format (use ISO 8601)")
		}
		start = &startTime
	}

	if endStr != "" {
		endTime, err := time.Parse(time.RFC3339, endStr)
		if err != nil {
			return nil, nil, errors.ValidationErrorf("INVALID_END_TIME", "Invalid end_time format (use ISO 8601)")
		}
		end = &endTime
	}

	// Validate start <= end
	if start != nil && end != nil && start.After(*end) {
		return nil, nil, errors.ValidationErrorf("INVALID_TIME_RANGE", "start_time must be before end_time")
	}

	return start, end, nil
}

// ParseSortParams parses sort_by and sort_order query parameters
func ParseSortParams(r *http.Request, allowedFields []string) (field, direction string, err error) {
	field = "timestamp"
	direction = "desc"

	if s := r.URL.Query().Get("sort_by"); s != "" {
		// Validate field is in allowed list
		valid := false
		for _, allowed := range allowedFields {
			if s == allowed {
				valid = true
				break
			}
		}
		if !valid {
			return "", "", errors.ValidationErrorf("INVALID_SORT_FIELD", "Invalid sort field")
		}
		field = s
	}

	if d := r.URL.Query().Get("sort_order"); d != "" {
		if d != "asc" && d != "desc" {
			return "", "", errors.ValidationErrorf("INVALID_SORT_ORDER", "Sort order must be 'asc' or 'desc'")
		}
		direction = d
	}

	return field, direction, nil
}

// BuildActivityFilters builds ActivityFilters from query parameters
func BuildActivityFilters(r *http.Request) (repository.ActivityFilters, error) {
	filters := repository.ActivityFilters{
		UserID:       r.URL.Query().Get("user_id"),
		Action:       r.URL.Query().Get("action"),
		ResourceType: r.URL.Query().Get("resource_type"),
		ResourceID:   r.URL.Query().Get("resource_id"),
	}

	// Parse time range if provided
	start, end, err := ParseTimeRange(r)
	if err != nil {
		return filters, err
	}
	if start != nil {
		filters.StartTime = interface{}(start)
	}
	if end != nil {
		filters.EndTime = interface{}(end)
	}

	return filters, nil
}
