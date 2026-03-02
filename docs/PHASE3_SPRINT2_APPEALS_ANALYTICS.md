# Phase 3, Sprint 2: Appeal Management & Advanced Analytics

**Status**: ✅ Complete
**Lines of Code**: ~2,200
**Components**: 2 services, 17 API endpoints, 2 database tables (+ 5 aggregation tables), 7 views, 25 test scenarios

## Overview

Phase 3 Sprint 2 introduces a comprehensive **Appeal Management System** and **Advanced Analytics Engine** that empower users to contest reputation violations and receive personalized improvement recommendations.

### Key Objectives

1. **Appeal Management**: Enable users to appeal reputation violations within a 30-day window
2. **Intelligent Analysis**: Provide trend analysis, pattern detection, and score projections
3. **Personalized Guidance**: Generate context-aware recommendations based on user state
4. **Admin Oversight**: Give administrators tools to review and resolve appeals
5. **Data-Driven Insights**: Store analytics data for historical analysis and trending

### Problem Solved

Before this sprint:
- Users had no recourse if violations were incorrect or applied unfairly
- No visibility into reputation trends or behavioral patterns
- No guidance on how to improve reputation
- Violations were permanent without appeal mechanism

After this sprint:
- Users can appeal violations within 30 days
- Complete visibility into reputation trends with projections
- Automated pattern detection (bursts, unusual timing, spikes)
- Personalized recommendations based on user's specific situation
- Full audit trail for compliance and dispute resolution

## Architecture

### Component Structure

```
├── Appeal System
│   ├── AppealService: Core appeal lifecycle management
│   ├── Database: appeals table + appeal_reasons reference
│   └── Routes: User and admin endpoints
│
├── Analytics System
│   ├── AnalyticsService: Trends, patterns, recommendations
│   ├── Database: Aggregation tables + analytical views
│   └── Routes: User endpoints for analytics data
│
└── Supporting Infrastructure
    ├── Database views for fast querying
    ├── 25 test scenarios for quality assurance
    └── Background jobs (appeal expiration)
```

### Design Principles

**Appeal Management:**
- **30-Day Window**: Appeals must be submitted within 30 days of violation
- **Deduplication**: Only one pending appeal per violation to prevent spam
- **Audit Trail**: Full history of appeal submission, review, and resolution
- **Automatic Restoration**: Approved appeals immediately restore reputation points

**Analytics:**
- **Trend Analysis**: Compare first half vs. second half to detect trends
- **Volatility Measurement**: Use standard deviation to assess stability
- **Predictive Scoring**: Linear regression on last 7 days extrapolated to 30 days
- **Pattern Detection**: Aggregate anomalies by type over 30 days
- **Tiered Recommendations**: Prioritize high-impact suggestions first

## Services

### Appeal Service

**File**: `pkg/services/rate_limiting/appeal_service.go`

#### Data Models

```go
// Appeal represents a user's appeal of a violation
type Appeal struct {
    ID               int           `json:"id"`
    UserID           int           `json:"user_id"`
    ViolationID      int           `json:"violation_id"`
    Status           AppealStatus  `json:"status"`              // pending, reviewing, approved, denied, expired, withdrawn
    Priority         AppealPriority `json:"priority"`           // low, medium, high, critical
    Reason           string        `json:"reason"`             // Code of appeal reason
    Description      string        `json:"description"`        // Detailed explanation
    Evidence         string        `json:"evidence"`           // JSON array of file URLs
    ReputationLost   float64       `json:"reputation_lost"`
    RequestedAction  string        `json:"requested_action"`   // restore, reduce, investigate
    ReviewedBy       *string       `json:"reviewed_by"`        // Admin who reviewed
    ReviewComment    *string       `json:"review_comment"`     // Admin's decision notes
    Resolution       *string       `json:"resolution"`         // Final resolution
    ApprovedPoints   *float64      `json:"approved_points"`    // Points to restore if approved
    CreatedAt        time.Time     `json:"created_at"`
    UpdatedAt        time.Time     `json:"updated_at"`
    ExpiresAt        time.Time     `json:"expires_at"`         // 30-day expiration
    ResolvedAt       *time.Time    `json:"resolved_at"`
}

// AppealStatus enum
type AppealStatus string
const (
    StatusPending   AppealStatus = "pending"
    StatusReviewing AppealStatus = "reviewing"
    StatusApproved  AppealStatus = "approved"
    StatusDenied    AppealStatus = "denied"
    StatusExpired   AppealStatus = "expired"
    StatusWithdrawn AppealStatus = "withdrawn"
)

// AppealReason represents predefined appeal reason options
type AppealReason struct {
    ID          int    `json:"id"`
    Code        string `json:"code"`       // false_positive, system_error, etc.
    Name        string `json:"name"`
    Description string `json:"description"`
    Priority    string `json:"priority"`  // low, medium, high
    Enabled     bool   `json:"enabled"`
}

// AppealMetrics represents system-wide appeal statistics
type AppealMetrics struct {
    TotalAppeals        int64   `json:"total_appeals"`
    PendingCount        int64   `json:"pending_count"`
    ApprovedCount       int64   `json:"approved_count"`
    DeniedCount         int64   `json:"denied_count"`
    ApprovalRate        float64 `json:"approval_rate"`     // %
    AvgResolutionHours  float64 `json:"avg_resolution_hours"`
    TotalPointsRestored float64 `json:"total_points_restored"`
}
```

#### Default Appeal Reasons

```go
// Automatically initialized on service creation
{
    "false_positive":    "System incorrectly flagged legitimate usage",
    "system_error":      "System error or bug caused incorrect violation",
    "legitimate_use":    "Usage was legitimate but triggered alerting system",
    "burst_needed":      "Spike was intentional and necessary for business",
    "shared_account":    "Multiple users share this account (different usage patterns)",
    "learning_curve":    "New user learning system, now compliant",
    "other":             "Other reason not listed above"
}
```

#### Core Methods

**SubmitAppeal(ctx, userID, violationID, details) → Appeal, error**
- Validates 30-day appeal window from violation date
- Prevents duplicate pending appeals on same violation
- Creates appeal with auto-expiration in 30 days
- Returns error if window expired or duplicate exists
- Sets initial priority based on reason

**GetUserAppeals(ctx, userID, status) → []Appeal, error**
- Returns user's appeals with optional status filter
- Ordered by created_at descending (newest first)
- If status provided, filters to specific status only

**GetPendingAppeals(ctx, limit) → []Appeal, error**
- Returns appeals pending admin review
- Ordered by priority (critical → high → medium → low)
- Limited to specified count (for pagination)

**ReviewAppeal(ctx, appealID, reviewedBy, action, approvedPoints, comment) → error**
- Processes admin review of appeal
- Marks appeal as "reviewing" during processing
- On approval: sets status, stores approved points, triggers reputation restoration
- On denial: sets status and stores denial reason
- Records reviewer identity and timestamp
- Returns error if appeal not in "pending" status

**WithdrawAppeal(ctx, userID, appealID) → error**
- Allows user to withdraw their pending appeal
- Only allowed if appeal status is "pending" or "reviewing"
- Sets status to "withdrawn"
- User cannot re-appeal same violation

**GetAppealReasons(ctx) → []AppealReason, error**
- Returns all enabled appeal reason options
- Used by client to populate reason selection dropdown

**GetAppealMetrics(ctx) → AppealMetrics, error**
- Calculates system-wide appeal statistics
- Queries appeals view for pre-computed values
- Returns metrics for dashboard display

**GetAppealStats(ctx, userID) → map, error**
- Returns user-specific statistics
- Includes: total appeals, success rate, avg time to resolution
- Used to prevent appeal spam by users with low success rates

**ExpireOldAppeals(ctx) → error**
- Background job to mark old appeals as expired
- Called periodically (typically daily)
- Marks appeals as "expired" if expires_at < now

#### Initialization

```go
func NewAppealService(db *gorm.DB) *AppealService {
    as := &AppealService{db: db}
    as.initializeAppealReasons()  // Creates 7 default reasons if not exist
    return as
}
```

### Analytics Service

**File**: `pkg/services/rate_limiting/analytics_service.go`

#### Data Models

```go
// TrendPoint represents a single data point in trend analysis
type TrendPoint struct {
    Date       string  `json:"date"`        // YYYY-MM-DD
    Score      float64 `json:"score"`       // Reputation score
    Tier       string  `json:"tier"`        // Current tier
    Violations int     `json:"violations"`  // Violations this day
    Successful int     `json:"successful"`  // Clean requests this day
    Change     float64 `json:"change"`      // Change from previous day
}

// TrendAnalysis represents comprehensive trend data
type TrendAnalysis struct {
    TimePeriod      string       `json:"time_period"`        // "7d", "30d", "90d"
    Points          []TrendPoint `json:"points"`             // Daily data points
    AvgScore        float64      `json:"avg_score"`          // Average over period
    MaxScore        float64      `json:"max_score"`          // Peak score
    MinScore        float64      `json:"min_score"`          // Lowest score
    Trend           string       `json:"trend"`              // "improving", "declining", "stable"
    Volatility      float64      `json:"volatility"`         // Std deviation
    ProjectedScore  float64      `json:"projected_score"`    // Estimated 30-day score
}

// BehaviorPattern represents a detected usage pattern
type BehaviorPattern struct {
    PatternType    string    `json:"pattern_type"`     // burst, unusual_time, resource_spike
    Frequency      int       `json:"frequency"`        // Times detected
    LastDetected   time.Time `json:"last_detected"`
    Severity       int       `json:"severity"`         // 1-5 scale
    Impact         float64   `json:"impact"`           // Reputation impact
    Recommendation string    `json:"recommendation"`   // Advice for user
}

// Recommendation represents personalized improvement suggestion
type Recommendation struct {
    Priority    string  `json:"priority"`         // low, medium, high, critical
    Title       string  `json:"title"`
    Description string  `json:"description"`
    Action      string  `json:"action"`           // Specific action to take
    ExpectedGain float64 `json:"expected_gain"`   // Estimated reputation gain
}
```

#### Core Methods

**GetReputationTrends(ctx, userID, days) → TrendAnalysis, error**

Calculates reputation trend over specified period (7, 30, or 90 days).

```go
// Algorithm:
// 1. Query reputation_events grouped by day
// 2. Sum score changes per day
// 3. Calculate daily running total (cumulative score)
// 4. Compute statistics: avg, min, max, std deviation
// 5. Determine trend by comparing first half vs. second half
// 6. Project score 30 days forward using linear regression
```

**Trend Classification:**
```
First half avg vs. Second half avg:
- If second > first by 5%+ → "improving"
- If second < first by 5%+ → "declining"
- Otherwise → "stable"
```

**Score Projection:**
```
1. Take last 7 days of scores
2. Calculate daily change: (day7 - day1) / 7
3. Project: lastWeekAvg + (dailyChange × 30 days)
4. Cap at 0-100 bounds
```

**GetBehaviorPatterns(ctx, userID) → []BehaviorPattern, error**

Detects behavioral patterns from last 30 days of anomaly detection data.

**Pattern Types:**
- **burst**: Sudden spike in request volume (2.0x baseline)
- **unusual_time**: Requests at off-peak hours (3.0x off-peak rate)
- **resource_spike**: High rate of violations in short period (>10/hour)

Returns aggregated count for each pattern type detected.

**GetPersonalizedRecommendations(ctx, userID) → []Recommendation, error**

Generates tailored suggestions based on user's current situation.

**Recommendation Rules:**
```
1. Low Reputation (score < 20):
   - Priority: CRITICAL
   - Action: Make 1000+ clean requests
   - Expected gain: 15 points

2. Moderate Reputation (20 ≤ score < 50):
   - Priority: HIGH
   - Action: Maintain clean usage for 14 days
   - Expected gain: 10 points

3. Recent Violations (past 7 days):
   - Priority: HIGH
   - Action: Audit code for rate limiting issues
   - Expected gain: 5 × violation_count

4. Low Activity (< 100 clean requests/week):
   - Priority: MEDIUM
   - Action: Increase to 100+ clean requests/week
   - Expected gain: 3 points

5. Tier Progression:
   - If tier = "flagged" (score < 20):
     - Show path to "standard" (need 20 points)
   - If tier = "standard" (20 ≤ score < 80):
     - Show path to "trusted" (need 80 points)
   - If tier = "trusted" (score ≥ 80):
     - Offer VIP status (2x rate limits)

6. Consistency Reward:
   - If no violations in 7 days AND > 500 clean requests:
     - Priority: LOW
     - Title: "Exceptional Usage Pattern"
```

**GetUsagePatterns(ctx, userID) → map[string]interface{}, error**

Analyzes hourly distribution of API requests over last 7 days.

**Returns:**
- `hourly_distribution`: []{ hour, requests }
- `peak_hour`: 0-23
- `shift_pattern`: "day" (9-17), "night" (20-6), "mixed"
- `day_requests`: Total 9-17 requests
- `night_requests`: Total 20-6 requests

**Helper Functions:**
- `calculateAverage(values)` → Mean
- `calculateMax(values)` → Maximum
- `calculateMin(values)` → Minimum
- `calculateStdDev(values)` → Standard deviation
- `determineTrend(scores)` → "improving" | "declining" | "stable"
- `projectScore(scores)` → float64

## Database Schema

### Tables

#### `appeals`

Full audit trail for user appeals of violations.

```sql
CREATE TABLE appeals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    violation_id INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, reviewing, approved, denied, expired, withdrawn
    priority VARCHAR(50) NOT NULL DEFAULT 'medium', -- low, medium, high, critical
    reason VARCHAR(100) NOT NULL,                    -- Appeal reason code
    description TEXT NOT NULL,                        -- Detailed explanation
    evidence TEXT,                                    -- JSON array of file URLs
    reputation_lost DECIMAL(10,2) NOT NULL,          -- Points lost in violation
    requested_action VARCHAR(50) NOT NULL,           -- restore, reduce, investigate
    reviewed_by VARCHAR(100),                        -- Admin reviewer
    review_comment TEXT,                             -- Admin's notes
    resolution VARCHAR(100),                         -- Final resolution
    approved_points DECIMAL(10,2),                   -- Points to restore
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,                   -- 30-day expiration
    resolved_at TIMESTAMP                            -- When resolved
);

-- Indexes for fast querying
CREATE INDEX idx_appeals_user_id ON appeals(user_id);
CREATE INDEX idx_appeals_violation_id ON appeals(violation_id);
CREATE INDEX idx_appeals_status ON appeals(status);
CREATE INDEX idx_appeals_priority ON appeals(priority);
CREATE INDEX idx_appeals_created_at ON appeals(created_at DESC);
CREATE INDEX idx_appeals_expires_at ON appeals(expires_at);
CREATE INDEX idx_appeals_user_status ON appeals(user_id, status);
```

#### `appeal_reasons`

Reference table for predefined appeal reason options.

```sql
CREATE TABLE appeal_reasons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    priority VARCHAR(50) DEFAULT 'medium',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `reputation_trends`

Aggregated daily reputation data per user.

```sql
CREATE TABLE reputation_trends (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    trend_date DATE NOT NULL,
    avg_score DECIMAL(10,2),
    max_score DECIMAL(10,2),
    min_score DECIMAL(10,2),
    tier VARCHAR(50),
    violation_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reputation_trends_user ON reputation_trends(user_id, trend_date DESC);
```

#### `behavior_patterns_log`

Monthly aggregation of detected behavior patterns.

```sql
CREATE TABLE behavior_patterns_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pattern_type VARCHAR(100) NOT NULL,    -- burst, unusual_time, resource_spike
    frequency INTEGER,                      -- Count this month
    last_detected TIMESTAMP WITH TIME ZONE,
    severity INTEGER,                       -- 1-5
    impact DECIMAL(10,2),                   -- Reputation impact
    month DATE,                             -- YYYY-MM-01 format
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_behavior_patterns_user ON behavior_patterns_log(user_id, month DESC);
```

#### `user_analytics_summary`

Analytics cache table updated periodically (daily/weekly).

```sql
CREATE TABLE user_analytics_summary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    trend_direction VARCHAR(50),             -- improving, declining, stable
    volatility DECIMAL(10,2),
    avg_daily_score DECIMAL(10,2),
    peak_score DECIMAL(10,2),
    lowest_score DECIMAL(10,2),
    projected_30day_score DECIMAL(10,2),
    peak_usage_hour INTEGER,                 -- 0-23
    shift_pattern VARCHAR(50),               -- day, night, mixed
    last_updated TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_analytics_summary_user ON user_analytics_summary(user_id);
```

### Views

**7 analytical views** for fast querying without complex calculations:

1. **appeal_summary** - System-wide metrics
2. **user_appeal_history** - Per-user appeal summary
3. **appeal_trend_analysis** - Weekly trends
4. **pending_appeals_queue** - Admin review queue
5. **improvement_candidates** - Users with positive trends
6. **at_risk_users** - Users needing intervention
7. **usage_pattern_distribution** - Pattern statistics

See `migrations/056_phase3_appeals_analytics.sql` for full view definitions.

## API Endpoints

### Appeal Endpoints

#### User Appeal Routes

**POST /api/appeals/submit**
Submit a new appeal.

```
Request:
{
    "violation_id": 123,
    "reason": "false_positive",
    "description": "This was legitimate API usage...",
    "evidence": "https://...",
    "requested_action": "restore"
}

Response:
{
    "id": 456,
    "user_id": 1,
    "violation_id": 123,
    "status": "pending",
    "priority": "medium",
    "reason": "false_positive",
    "description": "...",
    "evidence": "https://...",
    "reputation_lost": 50.0,
    "requested_action": "restore",
    "expires_at": "2025-03-28T...",
    "created_at": "2025-02-26T..."
}

Status: 201 Created
Errors:
- 400: Invalid request or appeal window expired
- 401: Not authenticated
- 409: Duplicate appeal already pending
```

**GET /api/appeals/my-appeals**
Get all user's appeals.

```
Query Params:
- (none)

Response:
{
    "appeals": [...],
    "count": 5
}

Status: 200 OK
```

**GET /api/appeals/my-appeals/:status**
Get appeals filtered by status.

```
Path Params:
- status: pending, reviewing, approved, denied, expired, withdrawn

Response:
{
    "status": "pending",
    "appeals": [...],
    "count": 2
}

Status: 200 OK
```

**GET /api/appeals/:appealID**
Get details of specific appeal.

```
Response: Appeal object
Status: 200 OK
Errors:
- 400: Invalid appeal ID
- 404: Appeal not found
- 403: Not authorized to view this appeal
```

**DELETE /api/appeals/:appealID**
Withdraw pending appeal.

```
Response:
{
    "success": true
}

Status: 200 OK
Errors:
- 400: Invalid appeal ID
- 403: Cannot withdraw approved/denied appeals
```

**GET /api/appeals/reasons**
Get available appeal reasons.

```
Response:
{
    "reasons": [
        {
            "id": 1,
            "code": "false_positive",
            "name": "System incorrectly flagged legitimate usage",
            "priority": "high"
        },
        ...
    ],
    "count": 7
}

Status: 200 OK
```

**GET /api/appeals/stats**
Get user's appeal statistics.

```
Response:
{
    "total_appeals": 3,
    "approved": 2,
    "denied": 1,
    "pending": 0,
    "approval_rate": 66.7,
    "avg_resolution_hours": 48.5,
    "total_points_restored": 100.0
}

Status: 200 OK
```

### Analytics Endpoints

**GET /api/analytics/trends**
Get reputation trends (defaults to 30 days).

```
Query Params:
- days: 7, 30, or 90 (optional, default: 30)

Response:
{
    "time_period": "30d",
    "points": [
        {
            "date": "2025-02-26",
            "score": 75.5,
            "tier": "trusted",
            "violations": 0,
            "successful": 50,
            "change": 2.3
        },
        ...
    ],
    "avg_score": 72.0,
    "max_score": 85.0,
    "min_score": 60.0,
    "trend": "improving",
    "volatility": 5.2,
    "projected_score": 80.5
}

Status: 200 OK
Errors:
- 401: Not authenticated
```

**GET /api/analytics/trends/:days**
Get trends for specific number of days.

```
Path Params:
- days: 7, 30, or 90

Response: Same as above
```

**GET /api/analytics/patterns**
Get detected behavior patterns.

```
Response:
{
    "patterns": [
        {
            "pattern_type": "burst",
            "frequency": 3,
            "last_detected": "2025-02-25T...",
            "severity": 3,
            "impact": -30.0,
            "recommendation": "Space out your requests..."
        },
        ...
    ],
    "count": 2
}

Status: 200 OK
```

**GET /api/analytics/recommendations**
Get personalized recommendations.

```
Response:
{
    "recommendations": [
        {
            "priority": "high",
            "title": "Stop Recent Violations",
            "description": "You had 2 violations in the last 7 days...",
            "action": "Audit your code for rate limiting issues...",
            "expected_gain": 10.0
        },
        ...
    ],
    "count": 3
}

Status: 200 OK
```

**GET /api/analytics/usage-patterns**
Get hourly usage analysis.

```
Response:
{
    "hourly_distribution": [
        {"hour": 9, "requests": 150},
        {"hour": 10, "requests": 200},
        ...
    ],
    "peak_hour": 14,
    "shift_pattern": "day",
    "day_requests": 2500,
    "night_requests": 300
}

Status: 200 OK
```

### Admin Endpoints

**GET /api/admin/appeals/pending**
Get pending appeals queue.

```
Query Params:
- limit: Max appeals to return (1-100, default: 50)

Response:
{
    "appeals": [...],
    "count": 5
}

Status: 200 OK
Errors:
- 403: Not admin
```

**GET /api/admin/appeals/metrics**
Get system-wide appeal metrics.

```
Response:
{
    "total_appeals": 450,
    "pending_appeals": 12,
    "approved_appeals": 350,
    "denied_appeals": 88,
    "approval_rate": 79.9,
    "avg_resolution_hours": 24.5,
    "total_points_restored": 8500.0
}

Status: 200 OK
Errors:
- 403: Not admin
```

**POST /api/admin/appeals/:appealID/review**
Process admin review of appeal.

```
Request:
{
    "action": "approved",      // approved or denied
    "approved_points": 50.0,   // Points to restore (if approved)
    "comment": "Appeal validated..."
}

Response:
{
    "success": true
}

Status: 200 OK
Errors:
- 400: Invalid action or appeal not pending
- 403: Not admin
```

**GET /api/admin/appeals/queue**
Get priority-ordered appeal queue (coming in future sprint).

```
Response:
{
    "queue": [...]
}

Status: 200 OK
```

## Testing

### Appeal Service Tests

**File**: `pkg/services/rate_limiting/appeal_service_test.go`

11 test scenarios + 2 benchmarks:

1. **TestAppealServiceCreation** - Service initialization and default reasons
2. **TestSubmitAppeal** - Valid appeal submission
3. **TestAppealWindowExpired** - 30-day window enforcement
4. **TestDuplicateAppeal** - Prevents duplicate pending appeals
5. **TestGetUserAppeals** - Retrieval with status filtering
6. **TestReviewAppeal** - Approval workflow with reputation restoration
7. **TestDenyAppeal** - Denial workflow
8. **TestWithdrawAppeal** - User withdrawal
9. **TestGetAppealReasons** - Reason retrieval
10. **TestGetAppealMetrics** - System metrics calculation
11. **TestExpireOldAppeals** - Expiration background job
12. **BenchmarkSubmitAppeal** - Submission performance
13. **BenchmarkReviewAppeal** - Review processing performance

### Analytics Service Tests

**File**: `pkg/services/rate_limiting/analytics_service_test.go`

14 test scenarios + 2 benchmarks:

1. **TestAnalyticsServiceCreation** - Service initialization
2. **TestGetReputationTrends** - Trend calculation accuracy
3. **TestGetBehaviorPatterns** - Pattern detection
4. **TestGetPersonalizedRecommendations** - Recommendation generation
5. **TestGetUsagePatterns** - Usage pattern analysis
6. **TestTrendDetermination** - Trend classification (improving/declining/stable)
7. **TestScoreProjection** - Linear regression projection
8. **TestCalculateStatistics** - Helper function validation (avg, min, max, stddev)
9. **TestNoDataHandling** - Edge cases with empty data
10. **TestRecommendationPriority** - Recommendation prioritization logic
11. **BenchmarkGetReputationTrends** - Trend calculation performance
12. **BenchmarkGetRecommendations** - Recommendation generation performance

### Test Coverage Areas

- **Correctness**: All algorithms produce expected outputs
- **Edge Cases**: Empty data, single data point, missing users
- **Performance**: Operations complete within expected timeframes
- **Isolation**: Tests use in-memory SQLite to avoid side effects
- **Regression**: Existing functionality protected against future changes

## Integration Guide

### 1. Service Registration

In your main application initialization:

```go
import (
    "architect/pkg/services/rate_limiting"
    "architect/pkg/routes"
)

// Create services
appealSvc := rate_limiting.NewAppealService(db)
analyticsSvc := rate_limiting.NewAnalyticsService(db)

// Register routes
routes.RegisterUserAppealsAnalyticsRoutes(
    router,
    db,
    appealSvc,
    analyticsSvc,
)
```

### 2. Database Migration

Run migration before starting application:

```bash
# Using your migration tool
./migrate up 056
```

Or manually apply `migrations/056_phase3_appeals_analytics.sql`.

### 3. Background Jobs

Add appeal expiration background job:

```go
// Run daily
go func() {
    ticker := time.NewTicker(24 * time.Hour)
    for range ticker.C {
        appealSvc.ExpireOldAppeals(context.Background())
    }
}()
```

### 4. Authentication

All endpoints require context with `user_id`:

```go
// In middleware
c.Set("user_id", user.ID)
```

Admin endpoints require admin role verification.

### 5. Reputation Restoration

When appeal is approved, reputation service should restore points:

```go
// In ReviewAppeal method
if action == "approved" && approvedPoints > 0 {
    reputationSvc.RestorePoints(userID, approvedPoints)
}
```

## Configuration

### Appeal Window

Default: **30 days** from violation date

To customize:

```go
type AppealService struct {
    db              *gorm.DB
    appealWindowDays int  // Customize here
}
```

### Recommendation Thresholds

Configure in `GetPersonalizedRecommendations`:

```go
const (
    LowRepScore      = 20.0   // Critical threshold
    ModerateRepScore = 50.0   // High priority threshold
    LowActivityCount = 100    // Low activity threshold
    TrustedTierScore = 80.0   // Score for trusted tier
)
```

### Pattern Detection Thresholds

Configure in `GetBehaviorPatterns`:

```go
const (
    BurstMultiplier     = 2.0   // 2x baseline = burst
    UnusualTimeMultiplier = 3.0 // 3x off-peak = unusual
    SpikeViolationRate  = 10    // > 10/hour = spike
)
```

## Future Enhancements

### Phase 3, Sprint 3

**Appeal Workflow Improvements:**
- Email notifications for appeal status changes
- Detailed violation context in appeal form
- Appeal rejection reasons picker (instead of free text)
- Appeal history/timeline UI
- Bulk appeal processing for admins

**Advanced Analytics:**
- Peer comparison ("You're in top 10% of users")
- ML-based anomaly detection
- Auto-assignment of appeal priority using ML
- Reputation recovery timeline prediction
- Custom report generation

**Automation:**
- Auto-approve clearly legitimate appeals
- Auto-appeal for high-confidence false positives
- Automatic reputation restoration for system errors
- Appeal template library for common cases

### Phase 3, Sprint 4

**Appeal Management UI:**
- Interactive appeal editor with validation
- Evidence file upload support
- Appeal tracking dashboard
- Admin review interface
- Historical appeal analytics

**Advanced Features:**
- Appeal negotiation (back-and-forth with admin)
- Mediation process for disputed appeals
- Appeal category suggestions
- Reputation prediction accuracy tracking
- A/B testing appeal language effectiveness

## Troubleshooting

### Appeals Not Showing in Queue

**Symptom**: Admin endpoint shows no pending appeals

**Causes:**
1. Appeals expired (30-day window passed)
2. All appeals already reviewed
3. Database migration not applied

**Solution**: Check `appeal_summary` view or query appeals directly

### Recommendations Too Generic

**Symptom**: Recommendations don't match user's situation

**Causes:**
1. Analytics service using default data
2. Thresholds too loose or tight
3. Missing event data for user

**Solution**: Verify reputation events are being logged, check thresholds

### Trend Analysis Showing Flat Line

**Symptom**: Always shows "stable" trend

**Causes:**
1. Insufficient data (less than 7 days)
2. All scores same value
3. Change between halves < 5%

**Solution**: Accumulate more data, verify violation/success events logged

### Performance Issues

**Symptom**: Slow trend/recommendation queries

**Causes:**
1. Missing database indexes
2. Large result sets
3. Complex view queries

**Solution**: Verify indexes on reputation_events, user_id, created_at

## Statistics

### Code Metrics

| Metric | Value |
|--------|-------|
| Service Lines | ~850 (appeal + analytics) |
| Test Lines | ~730 |
| Route Lines | ~410 |
| Database Lines | ~213 |
| Total | ~2,200 |

### Test Coverage

| Component | Test Cases | Benchmarks |
|-----------|-----------|-----------|
| Appeal Service | 11 | 2 |
| Analytics Service | 14 | 2 |
| **Total** | **25** | **4** |

### Database Objects

| Type | Count |
|------|-------|
| Tables | 4 (+ 1 from Phase 2) |
| Views | 7 |
| Indexes | 7 |
| Total | 18 |

## References

- **Migration**: `migrations/056_phase3_appeals_analytics.sql`
- **Services**: `pkg/services/rate_limiting/appeal_service.go`, `analytics_service.go`
- **Tests**: `pkg/services/rate_limiting/*_test.go`
- **Routes**: `pkg/routes/user_appeals_analytics_routes.go`

## See Also

- [Phase 3, Sprint 1: User Reputation Portal](PHASE3_SPRINT1_USER_PORTAL.md)
- [Phase 2: Reputation System Core](PHASE2_REPUTATION_SYSTEM.md)
- [Architecture Overview](ARCHITECTURE.md)
