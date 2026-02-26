# Education App Integration Guide

Complete guide for integrating education applications with GAIA_GO's usability metrics infrastructure.

---

## Table of Contents

1. [Overview](#overview)
2. [Supported Apps](#supported-apps)
3. [SDK Integration](#sdk-integration)
4. [Metric Types](#metric-types)
5. [Performance Thresholds](#performance-thresholds)
6. [API Endpoints](#api-endpoints)
7. [Examples](#examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Education App SDK enables seamless integration of education applications with GAIA_GO's real-time metrics collection and analysis system. It provides:

- **Automatic Metric Collection**: Buffer and flush metrics with configurable intervals
- **Anomaly Detection**: Identify unusual patterns based on performance thresholds
- **Event Handling**: React to application-specific events with custom handlers
- **Real-time Aggregation**: Metrics are aggregated and made available to teacher dashboards
- **Frustration Detection**: Automatic detection of student frustration patterns

---

## Supported Apps

The SDK includes built-in preset configurations for 5 education apps:

### 1. Typing Application
```go
metrics := []string{
    "words_per_minute",
    "accuracy_percentage",
    "error_count",
    "correction_count",
    "session_duration",
}
```

### 2. Mathematics Application
```go
metrics := []string{
    "problems_solved",
    "problems_correct",
    "accuracy_percentage",
    "time_per_problem",
    "difficulty_level",
}
```

### 3. Reading Application
```go
metrics := []string{
    "words_read",
    "reading_speed",
    "comprehension_score",
    "focus_time",
    "page_completion_rate",
}
```

### 4. Piano Application
```go
metrics := []string{
    "notes_played",
    "notes_correct",
    "accuracy_percentage",
    "tempo_bpm",
    "hand_coordination_score",
}
```

### 5. Comprehension Application
```go
metrics := []string{
    "questions_answered",
    "questions_correct",
    "accuracy_percentage",
    "confidence_score",
    "comprehension_level",
}
```

---

## SDK Integration

### Installation

The SDK is part of GAIA_GO's services package:

```go
import "github.com/jgirmay/GAIA_GO/pkg/services"
```

### Initialization

Initialize the SDK for a student session:

```go
// Create SDK instance
sdk := services.NewEducationAppSDK(
    appID,          // Unique app identifier
    appName,        // Display name
    metricsService, // *RealtimeMetricsAggregator instance
)

// Initialize for student session
err := sdk.Initialize(ctx, studentID, sessionID)
if err != nil {
    log.Fatal(err)
}

// Set performance thresholds
sdk.SetPerformanceThreshold(services.PerformanceThreshold{
    Name:           "response_time",
    WarningValue:   500,    // milliseconds
    CriticalValue:  1000,
    Unit:           "ms",
    CheckFrequency: 10 * time.Second,
})
```

### Recording Metrics

Record individual metrics:

```go
err := sdk.RecordMetric(ctx,
    "words_per_minute",
    65.5,
    "wpm",
)
```

Record metrics with metadata:

```go
err := sdk.RecordMetricWithMetadata(ctx,
    "accuracy_percentage",
    92.3,
    "%",
    map[string]interface{}{
        "error_type": "spelling",
        "context": "middle_word",
    },
)
```

### Recording Events

Record application events:

```go
err := sdk.RecordEvent(ctx,
    "quiz_completed",  // eventType
    "low",             // severity: 'low', 'medium', 'high', 'critical'
    map[string]interface{}{
        "score": 85,
        "time_taken": 120,
        "questions": 10,
    },
)
```

### Event Handlers

Register custom event handlers:

```go
sdk.RegisterEventHandler("quiz_completed", func(event *services.AppEvent) error {
    if event.Details["score"].(float64) < 60 {
        // Take action for low scores
        log.Printf("Low score detected: %v", event.Details["score"])
    }
    return nil
})
```

### Closing the SDK

Always close the SDK when done:

```go
err := sdk.Close(ctx)
if err != nil {
    log.Printf("Error closing SDK: %v", err)
}
```

---

## Metric Types

### Common Metrics

| Metric | Type | Unit | Range | Description |
|--------|------|------|-------|-------------|
| `accuracy_percentage` | Float | % | 0-100 | Percentage of correct responses |
| `response_time` | Float | ms | 0+ | Time to respond in milliseconds |
| `error_count` | Integer | count | 0+ | Number of errors |
| `completion_rate` | Float | % | 0-100 | Percentage of task completed |
| `time_spent` | Float | sec | 0+ | Time spent on task in seconds |
| `attempts` | Integer | count | 0+ | Number of attempts |

### App-Specific Metrics

**Typing App:**
- `words_per_minute`: WPM speed measurement
- `error_count`: Number of typing errors
- `correction_count`: Number of self-corrections

**Math App:**
- `problems_solved`: Total problems completed
- `problems_correct`: Correct answers
- `difficulty_level`: Current difficulty (1-10)

**Reading App:**
- `words_read`: Total words processed
- `reading_speed`: Words per minute
- `comprehension_score`: Understanding measure (0-100)

**Piano App:**
- `notes_played`: Total notes executed
- `notes_correct`: Correct notes
- `tempo_bpm`: Beats per minute

**Comprehension App:**
- `questions_answered`: Total questions
- `questions_correct`: Correct answers
- `confidence_score`: Self-assessed confidence (0-100)

---

## Performance Thresholds

Define performance thresholds for anomaly detection:

```go
thresholds := []services.PerformanceThreshold{
    {
        Name:           "response_time",
        WarningValue:   500,      // Warn if >= 500ms
        CriticalValue:  1000,     // Critical if >= 1000ms
        Unit:           "ms",
        CheckFrequency: 10 * time.Second,
    },
    {
        Name:           "error_rate",
        WarningValue:   0.10,     // Warn if >= 10%
        CriticalValue:  0.25,     // Critical if >= 25%
        Unit:           "%",
        CheckFrequency: 10 * time.Second,
    },
}

for _, threshold := range thresholds {
    sdk.SetPerformanceThreshold(threshold)
}
```

---

## API Endpoints

### Record Metric

**POST** `/api/metrics/record`

Request body:
```json
{
    "student_id": "student-123",
    "session_id": "session-456",
    "app_name": "Typing Application",
    "metric_type": "words_per_minute",
    "metric_value": 65.5,
    "unit": "wpm",
    "metadata": {
        "focus_level": "high",
        "distractions": 0
    }
}
```

Response:
```json
{
    "status": "recorded",
    "id": "metric-789"
}
```

### Get Student Metrics

**GET** `/api/metrics/student/{sessionID}`

Response:
```json
{
    "student_id": "student-123",
    "session_id": "session-456",
    "app_name": "Typing Application",
    "average_metrics": {
        "words_per_minute": 65.2,
        "accuracy_percentage": 94.5
    },
    "peak_metrics": {
        "words_per_minute": 72.3,
        "accuracy_percentage": 98.0
    },
    "min_metrics": {
        "words_per_minute": 58.1,
        "accuracy_percentage": 85.0
    },
    "total_count": 150,
    "anomalous_count": 3,
    "health_score": 88.5,
    "frustration_level": "low",
    "recommendations": [
        "Student performing well",
        "Consider advancing to more challenging material"
    ]
}
```

### Get Classroom Metrics

**GET** `/api/metrics/classroom/{classroomID}`

Response:
```json
{
    "classroom_id": "class-123",
    "total_students": 25,
    "active_students": 24,
    "average_health_score": 82.3,
    "struggling_students": [
        {
            "student_id": "student-456",
            "health_score": 45.2,
            "frustration_level": "high",
            "issue_description": "High error rate on word accuracy",
            "recommended_action": "Provide personalized feedback"
        }
    ],
    "last_update_time": "2026-02-25T14:30:00Z",
    "classroom_health_trend": "improving"
}
```

### Get Metrics Health

**GET** `/api/metrics/health`

Response:
```json
{
    "total_metrics": 45230,
    "active_sessions": 28,
    "aggregated_students": 150,
    "classroom_metrics": 3,
    "buffer_size": 0,
    "aggregation_interval_ms": 10000,
    "window_size_minutes": 5
}
```

---

## Examples

### Complete Typing App Integration

```go
package main

import (
    "context"
    "log"
    "time"

    "github.com/jgirmay/GAIA_GO/pkg/services"
)

func main() {
    ctx := context.Background()

    // Create metrics aggregator
    aggregator := services.NewRealtimeMetricsAggregator(nil, nil)
    err := aggregator.Start(ctx)
    if err != nil {
        log.Fatal(err)
    }
    defer aggregator.Stop()

    // Create SDK instance
    sdk := services.NewEducationAppSDK(
        "typing-app-001",
        "Typing Application",
        aggregator,
    )

    // Initialize for student
    err = sdk.Initialize(ctx, "student-123", "session-456")
    if err != nil {
        log.Fatal(err)
    }
    defer sdk.Close(ctx)

    // Set thresholds
    sdk.SetPerformanceThreshold(services.PerformanceThreshold{
        Name:           "response_time",
        WarningValue:   500,
        CriticalValue:  1000,
        Unit:           "ms",
        CheckFrequency: 10 * time.Second,
    })

    // Simulate typing session
    metrics := []struct {
        metricType string
        value      float64
    }{
        {"words_per_minute", 62.5},
        {"accuracy_percentage", 94.3},
        {"error_count", 2},
    }

    for _, m := range metrics {
        err := sdk.RecordMetric(ctx, m.metricType, m.value, "")
        if err != nil {
            log.Printf("Error recording metric: %v", err)
        }
    }

    // Record completion event
    err = sdk.RecordEvent(ctx, "session_completed", "low", map[string]interface{}{
        "duration": 600,
        "words_typed": 500,
    })
    if err != nil {
        log.Printf("Error recording event: %v", err)
    }

    // Get aggregated metrics
    time.Sleep(15 * time.Second) // Wait for aggregation
    studentMetrics := aggregator.GetStudentMetrics("session-456")
    if studentMetrics != nil {
        log.Printf("Health Score: %.2f", studentMetrics.HealthScore)
        log.Printf("Frustration Level: %s", studentMetrics.FrustrationLevel)
    }
}
```

### Math App with Difficulty Progression

```go
sdk.SetPerformanceThreshold(services.PerformanceThreshold{
    Name:           "accuracy_percentage",
    WarningValue:   70,
    CriticalValue:  50,
    Unit:           "%",
    CheckFrequency: 5 * time.Second,
})

// Adjust difficulty based on performance
err := sdk.RecordMetricWithMetadata(ctx,
    "problems_correct",
    8.0,
    "count",
    map[string]interface{}{
        "problems_total": 10,
        "difficulty_level": 5,
        "time_spent": 120,
    },
)
```

---

## Troubleshooting

### Metrics Not Appearing in Dashboard

1. **Check aggregator status**: Verify metrics aggregator is running
2. **Verify session initialization**: Ensure `Initialize()` was called
3. **Check buffer flush**: Metrics are buffered with 5-second flush interval
4. **Review error logs**: Check for any recording errors

### High Anomaly Scores

- **Cause**: Performance exceeding configured thresholds
- **Solution**: Review and adjust threshold values based on expected performance
- **Investigate**: Look at metadata for context about the anomaly

### Missing Metadata

- **Cause**: Recording metrics without optional metadata
- **Solution**: Use `RecordMetricWithMetadata()` for additional context
- **Example**: Include error types, environmental factors, etc.

### Frustration Detection Not Triggering

- **Current Status**: Placeholder implementation (returns "low" always)
- **Task 22**: Full frustration detection engine optimized in Phase 10 Sprint 3
- **Timeline**: Enhanced detection available after Task 22 completion

### Performance Issues

- **Buffer Size**: Check `aggregation_interval` and `window_size` settings
- **Query Performance**: Classroom metrics queries may slow with large datasets
- **Solution**: Consider pagination for large classroom queries

---

## Next Steps

1. Choose an education app to integrate
2. Set up performance thresholds
3. Implement metric recording in your app
4. Register event handlers for app-specific events
5. Monitor metrics via teacher dashboard
6. Provide feedback on metrics accuracy

---

## Support

- **Documentation**: [GAIA_GO Metrics Guide](./METRICS_GUIDE.md)
- **Teacher Dashboard**: [Dashboard Integration](./TEACHER_DASHBOARD.md)
- **Examples**: See `/pkg/services/education_app_sdk.go` for complete API

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| Feb 25, 2026 | 1.0 | Initial integration guide |

---

Questions? Contact the GAIA_GO team.
