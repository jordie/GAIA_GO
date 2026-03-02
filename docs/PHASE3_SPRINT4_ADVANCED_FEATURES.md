# Phase 3 Sprint 4: Advanced Appeal Features & ML-Powered Intelligence

## Overview

Phase 3 Sprint 4 implements the final layer of appeal sophistication, adding real-time negotiation capabilities and machine learning-powered intelligence systems. This sprint transforms the appeal system from a static submission/review process into a dynamic dialog-based negotiation platform with predictive analytics.

## Architecture

### Service Dependencies

```
├── AppealNegotiationService
│   ├── Depends on: appeals, appeal_negotiation_messages tables
│   ├── Provides: Real-time messaging, thread management, sentiment analysis
│   └── Integrates with: API routes for user/admin interfaces
│
└── MLPredictionService
    ├── Depends on: reputation_scores, user_analytics_summary, appeals, violations tables
    ├── Provides: Prediction models, confidence scoring, recommendations
    └── Integrates with: API routes for analytics endpoints
```

### Technology Stack

- **Language**: Go 1.21+
- **Database**: SQLite with WAL mode
- **Testing**: Go testing package with table-driven tests
- **API Framework**: Gin web framework
- **Analytics**: In-memory statistical calculations

## Detailed Implementation

### 1. Appeal Negotiation Service

**File**: `pkg/services/rate_limiting/appeal_negotiation_service.go`

#### Purpose

Enables asynchronous, real-time back-and-forth communication between users and administrators about appeals. Supports message threading, sentiment tracking, and conversation analysis.

#### Key Data Structures

```go
// MessageType represents the type of negotiation message
type MessageType string

const (
    MessageTypeMessage      MessageType = "message"
    MessageTypeQuestion     MessageType = "question"
    MessageTypeClarification MessageType = "clarification"
    MessageTypeProposal     MessageType = "proposal"
)

// SenderType represents who sent the message
type SenderType string

const (
    SenderTypeUser  SenderType = "user"
    SenderTypeAdmin SenderType = "admin"
)

// NegotiationMessage represents a single message in appeal negotiation
type NegotiationMessage struct {
    ID             int64
    AppealID       int
    SenderID       int
    SenderType     SenderType
    Message        string
    MessageType    MessageType
    Metadata       datatypes.JSONMap
    AttachmentURLs []string
    SentimentScore *float64      // -1.0 to 1.0
    LanguageScore  *float64      // 0.0 to 1.0 (quality/clarity)
    IsPinned       bool
    CreatedAt      time.Time
    UpdatedAt      time.Time
}

// NegotiationThread represents the complete negotiation conversation
type NegotiationThread struct {
    AppealID      int                    `json:"appeal_id"`
    Messages      []NegotiationMessage   `json:"messages"`
    MessageCount  int                    `json:"message_count"`
    UserMessages  int                    `json:"user_messages"`
    AdminMessages int                    `json:"admin_messages"`
    LastUpdate    time.Time              `json:"last_update"`
    AvgSentiment  *float64               `json:"avg_sentiment"`
    AvgQuality    *float64               `json:"avg_quality"`
}
```

#### Core Methods

**SendMessage(ctx, appealID, senderID, senderType, message, messageType, metadata, attachmentURLs)**

Sends a negotiation message and updates appeal status.

```go
// Updates appeal status from pending to reviewing
ans.db.WithContext(ctx).
    Table("appeals").
    Where("id = ? AND status = ?", appealID, StatusPending).
    Update("status", StatusReviewing)
```

**GetNegotiationThread(ctx, appealID)**

Retrieves complete conversation thread with aggregated metrics:
- Message count by type (user vs admin)
- Average sentiment across all messages
- Average quality/language score
- Last update timestamp

**GetUserConversations(ctx, userID, limit, offset)**

Paginated retrieval of all appeals with negotiation activity for a specific user.

**GetAdminConversations(ctx, limit, offset)**

Retrieves appeals with recent negotiation activity (last 7 days) for admin review.

**PinMessage/UnpinMessage(ctx, messageID)**

Marks important messages for quick reference without sorting through thread.

**AnalyzeConversationTone(ctx, appealID)**

Sentiment analysis returning:
- User sentiment: Average sentiment of user messages
- Admin sentiment: Average sentiment of admin messages
- Overall sentiment: Thread-wide average
- Conversation health: Qualitative assessment (positive/neutral/negative)
- Tone trend: Improvement/deterioration/stable based on first half vs second half

**GetNegotiationMetrics(ctx)**

System-wide metrics:
- Total negotiations active
- Average messages per appeal
- Average resolution time
- Distribution of user vs admin messages
- Overall sentiment distribution

#### Helper Functions

```go
// calculateAverage computes mean of float slice
func calculateAverage(values []float64) float64

// determineConversationHealth assesses negotiation health
func determineConversationHealth(thread *NegotiationThread) string
    // Returns: "positive" (sentiment > 0.3)
    //          "neutral" (-0.3 to 0.3)
    //          "negative" (sentiment < -0.3)

// analyzeToneTrend analyzes how tone changes over time
func analyzeToneTrend(messages []NegotiationMessage) string
    // Compares first half vs second half of conversation
    // Returns: "improving" (change > 0.2)
    //          "stable" (-0.2 to 0.2)
    //          "deteriorating" (change < -0.2)
```

#### Use Cases

1. **User Questions Appeal Decision**
   - User sends message asking why appeal was denied
   - Admin responds with explanation
   - Negotiation tracked and analyzed

2. **Admin Requests Clarification**
   - Admin asks user for additional evidence
   - User provides supporting documents
   - Conversation pinned for reference

3. **Proposal-Based Resolution**
   - User proposes different violation category
   - Admin discusses feasibility
   - Conversation influences final decision

4. **Sentiment Monitoring**
   - System detects increasingly negative tone
   - Alerts admins to potential escalation
   - Enables proactive de-escalation

### 2. ML Prediction Service

**File**: `pkg/services/rate_limiting/ml_prediction_service.go`

#### Purpose

Applies machine learning models to predict user behavior and appeal outcomes. Provides data-driven recommendations for users and administrators.

#### Key Data Structures

```go
// PredictionType represents the type of ML prediction
type PredictionType string

const (
    PredictionTypeRecoveryTimeline   PredictionType = "recovery_timeline"
    PredictionTypeApprovalProbability PredictionType = "approval_probability"
    PredictionTypeLanguageQuality    PredictionType = "language_quality"
)

// ReputationRecoveryPrediction represents recovery timeline
type ReputationRecoveryPrediction struct {
    UserID               int       `json:"user_id"`
    CurrentScore         float64   `json:"current_score"`
    TargetScore          float64   `json:"target_score"`
    EstimatedDaysToTarget int      `json:"estimated_days_to_target"`
    WeeklyChangeRate     float64   `json:"weekly_change_rate"`
    ConfidenceLevel      float64   `json:"confidence_level"`      // 0.0-1.0
    RequiredActions      []string  `json:"required_actions"`
}

// AppealProbability represents approval probability
type AppealProbability struct {
    AppealID            int       `json:"appeal_id"`
    ApprovalProbability float64   `json:"approval_probability"`   // 0.0-1.0
    DenialProbability   float64   `json:"denial_probability"`     // 0.0-1.0
    Confidence          float64   `json:"confidence"`             // 0.0-1.0
    KeyFactors          []string  `json:"key_factors"`
    RecommendedStrategy string    `json:"recommended_strategy"`
}

// AutoAppealSuggestion represents auto-appeal recommendation
type AutoAppealSuggestion struct {
    UserID                    int       `json:"user_id"`
    ViolationID               int       `json:"violation_id"`
    SuggestionReason          string    `json:"suggestion_reason"`
    Confidence                float64   `json:"confidence"`           // 0.0-1.0
    PredictedSuccessRate      float64   `json:"predicted_success_rate"`
    SuggestedStrategy         string    `json:"suggested_strategy"`
    SupportingEvidence        []string  `json:"supporting_evidence"`
    SimilarSuccessCount       int       `json:"similar_success_count"`
    GeneratedAt               time.Time `json:"generated_at"`
    UserAccepted              bool      `json:"user_accepted"`
    AppealCreatedFromSuggestion bool    `json:"appeal_created_from_suggestion"`
    CreatedAt                 time.Time `json:"created_at"`
}

// Prediction represents an ML prediction record
type Prediction struct {
    ID                int64
    AppealID          *int
    UserID            int
    PredictionType    PredictionType
    PredictionValue   float64
    Confidence        float64                  // 0.0-1.0
    SupportingFactors datatypes.JSONMap
    ModelVersion      string
    PredictedAt       time.Time
    ActualValue       *float64                 // For accuracy tracking
    AccuracyCheckedAt *time.Time
    CreatedAt         time.Time
}
```

#### Core Methods

**PredictReputationRecovery(ctx, userID)**

Estimates how long it will take for a user to recover their reputation to target score.

Algorithm:
1. Fetch user's current score and tier from `reputation_scores`
2. Determine target score based on tier:
   - flagged → 20.0
   - standard → 80.0
   - trusted → 100.0
3. Calculate weekly change rate from `user_analytics_summary.trend_direction`:
   - improving → +2.5/week
   - declining → -2.0/week
   - stable → +0.5/week
4. Calculate days to target: `(targetScore - currentScore) / weeklyRate * 7`
5. Determine confidence:
   - Base: 0.7
   - With projected score data: 0.85
6. Generate required actions (base 3, add "address violations" if declining)

Example output:
```json
{
    "user_id": 42,
    "current_score": 35.0,
    "target_score": 80.0,
    "estimated_days_to_target": 90,
    "weekly_change_rate": 2.5,
    "confidence_level": 0.85,
    "required_actions": [
        "Maintain clean API usage without violations",
        "Monitor reputation trends regularly",
        "Review and comply with rate limiting policies",
        "Address recent violations immediately"
    ]
}
```

**PredictAppealApprovalProbability(ctx, appealID)**

Predicts likelihood an appeal will be approved using multi-factor model.

Algorithm:
1. Fetch appeal details (reason, created_at) and user history (total appeals, successful appeals)
2. Initialize base probability: 0.5
3. Add factor based on appeal reason:
   - system_error: +0.20
   - false_positive: +0.15
   - legitimate_use: +0.10
   - shared_account: +0.05
   - learning_curve: +0.08
   - burst_needed: +0.03
   - other: +0.02
4. Add factor based on user success rate: +(successRate * 0.2)
5. Add factor based on recency:
   - < 1 day old: +0.05
   - > 7 days old: -0.05
6. Clamp to [0.0, 1.0]
7. Calculate denial probability: 1.0 - approval
8. Determine confidence:
   - Base: 0.75
   - With history (> 5 appeals): 0.85
9. Generate key factors and recommend strategy

Example output:
```json
{
    "appeal_id": 5,
    "approval_probability": 0.72,
    "denial_probability": 0.28,
    "confidence": 0.85,
    "key_factors": [
        "Appeal reason: system_error",
        "User success rate: 80.0%",
        "Historical data suggests approval is more likely"
    ],
    "recommended_strategy": "Strong case - emphasize factual evidence and compliance with policies"
}
```

**SuggestAutoAppeal(ctx, userID)**

Identifies violations suitable for appeal based on similar success patterns.

Algorithm:
1. Fetch recent violations (last 30 days, limit 5)
2. For each violation:
   a. Check if already appealed (skip if yes)
   b. Count similar violations with successful appeals (same violation type, other users)
   c. Calculate confidence based on similarity count:
      - ≥ 5 similar: 0.85
      - ≥ 3 similar: 0.75
      - ≥ 1 similar: 0.65
      - < 1: skip (too low confidence)
   d. Set reason: "pattern_match" if similarities > 0, else "high_confidence_fp"
   e. Generate strategy: reference similar appeals if many similarities
   f. Create suggestion record

Only suggests violations with confidence ≥ 0.60.

**GetModelPerformance(ctx, predictionType)**

Returns accuracy metrics for a prediction model.

Calculates:
- `total_predictions`: All predictions of this type from last 3 months
- `verified_predictions`: Predictions with actual_value set
- `avg_confidence`: Mean confidence across predictions
- `accuracy_percent`: Percentage where |predicted - actual| < 0.1
- `data_quality`: "high" (≥70% verified), "medium" (≥40%), or "low"

Example output:
```json
{
    "prediction_type": "recovery_timeline",
    "total_predictions": 250,
    "verified_predictions": 180,
    "avg_confidence": 0.78,
    "accuracy_percent": 82.5,
    "data_quality": "high"
}
```

#### Helper Functions

```go
// storePrediction stores a prediction in the database
func (mps *MLPredictionService) storePrediction(
    ctx context.Context,
    appealID *int,
    userID int,
    predictionType PredictionType,
    value float64,
    confidence float64,
    factors map[string]interface{},
) error

// determineDataQuality assesses prediction model data quality
func determineDataQuality(verified, total int64) string
    // verified / total ratio determines quality level
```

#### Model Assumptions

The ML service makes reasonable assumptions about user behavior:

1. **Reputation Recovery**: Linear change in score per week (conservative estimate)
2. **Appeal Approval**: Discrete factors contribute independently to probability
3. **Pattern Matching**: Similar violations with successful appeals indicate viability
4. **Confidence**: Increases with historical data volume
5. **Data Quality**: Verified predictions (with actual outcomes) improve model over time

#### Model Limitations

- Models are rule-based heuristics, not trained machine learning
- Require historical data to be effective
- Don't account for policy changes
- Assume past patterns predict future outcomes
- Confidence scores should guide, not guarantee, decisions

#### Accuracy Tracking

The service supports post-prediction accuracy validation:

```go
// After appeal outcome is known, update actual_value
UPDATE ml_predictions
SET actual_value = ?, accuracy_checked_at = CURRENT_TIMESTAMP
WHERE id = ?
```

This enables continuous model improvement and performance monitoring.

### 3. Database Schema

**File**: `migrations/058_phase3_sprint4_advanced_features.sql`

#### New Tables

**appeal_negotiation_messages**
```sql
CREATE TABLE appeal_negotiation_messages (
    id INTEGER PRIMARY KEY,
    appeal_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL,        -- 'user' or 'admin'
    message TEXT NOT NULL,
    message_type TEXT DEFAULT 'message', -- 'message', 'question', 'clarification', 'proposal'
    metadata TEXT,                    -- JSON
    attachment_urls TEXT,             -- JSON array
    sentiment_score REAL,             -- -1.0 to 1.0, NULL if not analyzed
    language_score REAL,              -- 0.0 to 1.0, NULL if not analyzed
    is_pinned BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
)
```

Enables comprehensive negotiation history with sentiment tracking.

**appeal_mediations**
```sql
CREATE TABLE appeal_mediations (
    id INTEGER PRIMARY KEY,
    appeal_id INTEGER NOT NULL UNIQUE,
    mediation_status TEXT,           -- 'active', 'resolved', 'escalated'
    dispute_reason TEXT,
    mediator_id INTEGER,
    mediator_notes TEXT,
    final_resolution TEXT,
    mediation_started_at TIMESTAMP,
    mediation_ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
)
```

Tracks formal mediation processes for complex disputes.

**ml_predictions**
```sql
CREATE TABLE ml_predictions (
    id INTEGER PRIMARY KEY,
    appeal_id INTEGER,
    user_id INTEGER NOT NULL,
    prediction_type TEXT NOT NULL,   -- 'recovery_timeline', 'approval_probability', 'language_quality'
    prediction_value REAL NOT NULL,
    confidence REAL NOT NULL,        -- 0.0-1.0
    supporting_factors TEXT,         -- JSON map of contributing factors
    model_version TEXT DEFAULT 'v1.0',
    predicted_at TIMESTAMP NOT NULL,
    actual_value REAL,               -- For post-prediction accuracy validation
    accuracy_checked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
)
```

Comprehensive prediction history with accuracy tracking.

**appeal_classifications_extended**
```sql
CREATE TABLE appeal_classifications_extended (
    id INTEGER PRIMARY KEY,
    appeal_id INTEGER NOT NULL,
    primary_classification TEXT,
    secondary_classifications TEXT,   -- JSON array
    auto_approvable BOOLEAN,
    confidence REAL,                 -- Model confidence in classification
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
)
```

Enhanced classification beyond original reason.

**appeal_language_analysis**
```sql
CREATE TABLE appeal_language_analysis (
    id INTEGER PRIMARY KEY,
    appeal_id INTEGER NOT NULL,
    quality_score REAL,              -- 0.0-1.0
    clarity_score REAL,              -- 0.0-1.0
    evidence_quality_score REAL,     -- 0.0-1.0
    tone_score REAL,                 -- -1.0 to 1.0
    keywords_extracted TEXT,         -- JSON array
    summary_generated TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
)
```

Linguistic analysis of appeal submissions.

**auto_appeal_suggestions**
```sql
CREATE TABLE auto_appeal_suggestions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    violation_id INTEGER NOT NULL,
    suggestion_reason TEXT,
    confidence REAL,
    predicted_success_rate REAL,
    user_accepted BOOLEAN DEFAULT 0,
    appeal_created_from_suggestion BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (violation_id) REFERENCES violations(id)
)
```

Tracks auto-appeal recommendations and user acceptance.

**user_appeal_statistics**
```sql
CREATE TABLE user_appeal_statistics (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    total_appeals INTEGER DEFAULT 0,
    approved_appeals INTEGER DEFAULT 0,
    denied_appeals INTEGER DEFAULT 0,
    appeal_success_rate REAL,
    avg_resolution_days REAL,
    negotiation_count INTEGER DEFAULT 0,
    last_appeal_date TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
```

Cached user-level appeal statistics for quick analytics.

#### Indexes

All new tables indexed for common query patterns:

```sql
CREATE INDEX idx_negotiation_messages_appeal ON appeal_negotiation_messages(appeal_id);
CREATE INDEX idx_negotiation_messages_sender ON appeal_negotiation_messages(sender_id, sender_type);
CREATE INDEX idx_negotiation_messages_created ON appeal_negotiation_messages(appeal_id, created_at);
CREATE INDEX idx_predictions_user ON ml_predictions(user_id);
CREATE INDEX idx_predictions_type ON ml_predictions(prediction_type, created_at);
CREATE INDEX idx_predictions_appeal ON ml_predictions(appeal_id);
CREATE INDEX idx_auto_appeals_user ON auto_appeal_suggestions(user_id);
CREATE INDEX idx_user_stats_user ON user_appeal_statistics(user_id);
```

#### Analytical Views

**negotiation_activity**
```sql
CREATE VIEW negotiation_activity AS
SELECT
    a.id as appeal_id,
    a.user_id,
    COUNT(anm.id) as message_count,
    SUM(CASE WHEN anm.sender_type = 'user' THEN 1 ELSE 0 END) as user_messages,
    SUM(CASE WHEN anm.sender_type = 'admin' THEN 1 ELSE 0 END) as admin_messages,
    AVG(anm.sentiment_score) as avg_sentiment,
    MAX(anm.created_at) as last_message_at
FROM appeals a
LEFT JOIN appeal_negotiation_messages anm ON a.id = anm.appeal_id
GROUP BY a.id, a.user_id
```

**mediation_queue**
```sql
CREATE VIEW mediation_queue AS
SELECT
    am.id,
    am.appeal_id,
    a.user_id,
    a.violation_id,
    am.mediation_status,
    DATETIME('now') - am.mediation_started_at as mediation_duration_hours,
    am.mediator_id
FROM appeal_mediations am
JOIN appeals a ON am.appeal_id = a.id
WHERE am.mediation_status = 'active'
ORDER BY am.mediation_started_at ASC
```

**ml_model_performance**
```sql
CREATE VIEW ml_model_performance AS
SELECT
    prediction_type,
    COUNT(*) as total_predictions,
    COUNT(actual_value) as verified_predictions,
    AVG(confidence) as avg_confidence,
    COUNT(CASE WHEN ABS(prediction_value - actual_value) < 0.1 THEN 1 END) * 100.0 /
    COUNT(actual_value) as accuracy_percent,
    model_version
FROM ml_predictions
WHERE created_at > DATETIME('now', '-3 months')
GROUP BY prediction_type, model_version
```

**auto_appeal_effectiveness**
```sql
CREATE VIEW auto_appeal_effectiveness AS
SELECT
    suggestion_reason,
    COUNT(*) as total_suggestions,
    COUNT(CASE WHEN user_accepted = 1 THEN 1 END) as accepted,
    COUNT(CASE WHEN user_accepted = 1 THEN 1 END) * 100.0 /
    COUNT(*) as acceptance_rate,
    AVG(predicted_success_rate) as avg_predicted_rate
FROM auto_appeal_suggestions
GROUP BY suggestion_reason
```

### 4. API Routes

**File**: `pkg/routes/appeal_advanced_features_routes.go`

#### Negotiation Endpoints

**POST /api/appeals/negotiation/:appealID/message**

Send a negotiation message on an appeal.

Request:
```json
{
    "message": "Can you provide more details about the violation?",
    "message_type": "question",
    "attachment_urls": ["https://example.com/evidence.pdf"]
}
```

Response:
```json
{
    "id": 123,
    "appeal_id": 5,
    "sender_id": 42,
    "sender_type": "user",
    "message": "Can you provide more details about the violation?",
    "message_type": "question",
    "is_pinned": false,
    "created_at": "2024-02-20T10:30:00Z"
}
```

**GET /api/appeals/negotiation/:appealID/thread**

Retrieve complete negotiation thread for an appeal.

Response:
```json
{
    "appeal_id": 5,
    "messages": [...],
    "message_count": 12,
    "user_messages": 5,
    "admin_messages": 7,
    "last_update": "2024-02-20T14:20:00Z",
    "avg_sentiment": 0.35,
    "avg_quality": 0.82
}
```

**GET /api/appeals/negotiation/user/conversations**

Get all active conversations for current user (paginated).

Query parameters:
- `limit`: Page size (1-100, default 20)
- `offset`: Pagination offset (default 0)

**GET /api/appeals/negotiation/admin/conversations**

Get active negotiations for admin review (last 7 days, paginated).

**POST /api/appeals/negotiation/:appealID/pin/:messageID**

Pin a message for importance.

**POST /api/appeals/negotiation/:appealID/unpin/:messageID**

Remove pin from message.

**GET /api/appeals/negotiation/:appealID/pinned**

Get all pinned messages for an appeal.

**GET /api/appeals/negotiation/:appealID/tone-analysis**

Analyze conversation sentiment and health.

Response:
```json
{
    "user_sentiment": 0.25,
    "admin_sentiment": 0.45,
    "overall_sentiment": 0.35,
    "conversation_health": "positive",
    "tone_trend": "improving"
}
```

**GET /api/appeals/negotiation/statistics**

Get system-wide negotiation metrics.

Response:
```json
{
    "total_negotiations": 156,
    "avg_messages_per_appeal": 8.3,
    "avg_user_messages": 3.1,
    "avg_admin_messages": 5.2,
    "avg_sentiment": 0.28,
    "avg_quality": 0.79
}
```

#### ML Prediction Endpoints

**GET /api/predictions/user/recovery/:userID**

Predict reputation recovery timeline for a user.

Response:
```json
{
    "user_id": 42,
    "current_score": 35.0,
    "target_score": 80.0,
    "estimated_days_to_target": 90,
    "weekly_change_rate": 2.5,
    "confidence_level": 0.85,
    "required_actions": [
        "Maintain clean API usage without violations",
        "Monitor reputation trends regularly",
        "Review and comply with rate limiting policies"
    ]
}
```

**GET /api/predictions/appeal/approval/:appealID**

Predict approval probability for an appeal.

Response:
```json
{
    "appeal_id": 5,
    "approval_probability": 0.72,
    "denial_probability": 0.28,
    "confidence": 0.85,
    "key_factors": [
        "Appeal reason: system_error",
        "User success rate: 80.0%",
        "Historical data suggests approval is more likely"
    ],
    "recommended_strategy": "Strong case - emphasize factual evidence and compliance with policies"
}
```

**GET /api/predictions/user/auto-appeals/:userID**

Get auto-appeal suggestions for a user.

Response:
```json
{
    "suggestions": [
        {
            "user_id": 42,
            "violation_id": 105,
            "suggestion_reason": "pattern_match",
            "confidence": 0.82,
            "predicted_success_rate": 0.82,
            "suggested_strategy": "Reference similar successful appeals and patterns",
            "supporting_evidence": [
                "Similar violations have been successfully appealed"
            ],
            "similar_success_count": 7,
            "created_at": "2024-02-20T10:00:00Z"
        }
    ],
    "count": 1
}
```

**GET /api/predictions/model-performance**

Get ML model performance metrics.

Query parameters:
- `type`: Prediction type filter (recovery_timeline, approval_probability, language_quality)

Response:
```json
{
    "prediction_type": "recovery_timeline",
    "total_predictions": 250,
    "verified_predictions": 180,
    "avg_confidence": 0.78,
    "accuracy_percent": 82.5,
    "data_quality": "high"
}
```

## Testing

**File**: `pkg/services/rate_limiting/appeal_negotiation_service_test.go`

Comprehensive test coverage with 10 test scenarios:

1. **TestNegotiationServiceCreation** - Service initialization
2. **TestSendMessage** - Message creation and storage
3. **TestGetNegotiationThread** - Thread retrieval with aggregation
4. **TestGetUserConversations** - User conversation pagination
5. **TestGetAdminConversations** - Admin queue retrieval
6. **TestPinMessage** - Message pinning functionality
7. **TestGetPinnedMessages** - Pinned message retrieval
8. **TestAnalyzeConversationTone** - Sentiment analysis
9. **TestGetNegotiationMetrics** - System metrics
10. **TestMessageTypes** - Type validation
11. **TestSenderTypes** - Sender type validation

Benchmarks:
- **BenchmarkSendMessage** - Message sending performance
- **BenchmarkGetNegotiationThread** - Thread retrieval performance

**File**: `pkg/services/rate_limiting/ml_prediction_service_test.go`

Comprehensive test coverage with 12 test scenarios:

1. **TestMLPredictionServiceCreation** - Service initialization
2. **TestPredictReputationRecovery** - Recovery timeline calculation
3. **TestPredictAppealApprovalProbability** - Approval probability scoring
4. **TestSuggestAutoAppeal** - Auto-appeal suggestion generation
5. **TestGetModelPerformance** - Model metrics retrieval
6. **TestReputationRecoveryDeclining** - Declining trend prediction
7. **TestApprovalProbabilityHighConfidence** - High confidence scoring
8. **TestPredictionTypes** - Type validation
9. **TestModelPerformanceMetrics** - Performance calculation
10. **TestAutoAppealFiltering** - Confidence threshold filtering
11. **TestMultiFactorProbability** - Multi-factor model validation
12. **TestPredictionStorage** - Database persistence

Benchmarks:
- **BenchmarkPredictReputationRecovery** - Recovery prediction performance
- **BenchmarkPredictAppealApprovalProbability** - Approval prediction performance

All tests use SQLite in-memory database for isolation and speed.

## Integration Points

### With Sprint 3 Services

- **History Service**: Appeal negotiation messages trigger status changes recorded in history
- **Bulk Operations**: ML predictions inform bulk approve/deny decisions
- **Notifications**: ML confidence thresholds can trigger notification strategies

### With Sprint 2 Services

- **Appeal Service**: Negotiation messages update appeal status during review
- **Analytics Service**: Recovery timeline predictions inform trend analysis

### With Reputation System (Phase 1 & 2)

- **User Service**: User profile lookup for sender identification
- **Reputation Manager**: Current score fetch for recovery prediction
- **Violation Service**: Violation details for auto-appeal suggestions

## Performance Considerations

### Query Optimization

1. **Negotiation Messages**: Indexed by `(appeal_id, created_at)` for efficient thread retrieval
2. **ML Predictions**: Indexed by `(prediction_type, created_at)` for performance metrics
3. **Auto-Appeals**: Indexed by `(user_id)` for user-specific suggestions

### Caching Opportunities

- Negotiation thread results (expires on new message)
- User peer comparison data (expires daily)
- Model performance metrics (updated hourly)

### Database Scaling

Current schema supports:
- 1M+ negotiation messages
- 100K+ predictions with accuracy validation
- Efficient sentiment analysis across large conversations

For larger scale:
- Archive old negotiation messages (> 1 year)
- Partition ML predictions by type
- Aggregate statistics into summary tables

## Configuration

Services use environment variables or config files:

```bash
# Negotiation Service
NEGOTIATION_SENTIMENT_THRESHOLD=0.3
NEGOTIATION_MAX_MESSAGE_SIZE=5000
NEGOTIATION_ARCHIVE_DAYS=365

# ML Service
ML_CONFIDENCE_MIN_PREDICTION_HISTORY=5
ML_AUTO_APPEAL_CONFIDENCE_THRESHOLD=0.60
ML_MODEL_VERSION="v1.0"
```

## Security Considerations

### Message Privacy

- Negotiation messages marked as user content
- Accessible only to appeal participants (user, assigned admins)
- Audit log tracks all access

### Prediction Transparency

- Users see approval probability but not internal factors
- Admins see complete breakdown with confidence scores
- Models versioned for traceability

### Data Retention

- Messages: 1 year (configurable)
- Predictions: 3 years (audit trail)
- Suggestions: Until accepted or 90 days (whichever first)

## Future Enhancements

1. **Real Sentiment Analysis**: Replace heuristics with NLP model
2. **Dynamic Confidence**: Adjust based on model performance
3. **Appeal Outcomes Integration**: Use actual results for continuous model improvement
4. **Pattern Recognition**: Detect abuse/spam message patterns
5. **Multilingual Support**: Translate messages for admin review
6. **Conversation Summaries**: Auto-generate thread summaries for admins
7. **Distributed Negotiations**: Support external mediators/advocates
8. **A/B Testing**: Test different recommendation strategies

## Deployment Checklist

- [ ] Database migration applied successfully
- [ ] All services compiled and tested
- [ ] API endpoints returning correct responses
- [ ] Message threading working correctly
- [ ] Sentiment analysis calculating properly
- [ ] ML predictions calibrated and validated
- [ ] Admin interface updated with new features
- [ ] Monitoring/alerting for prediction accuracy
- [ ] Load testing at expected scale
- [ ] Documentation updated
- [ ] Team trained on new features
- [ ] Gradual rollout plan prepared

## Related Documentation

- [Phase 3 Sprint 2: Appeals & Analytics](PHASE3_SPRINT2_APPEALS_ANALYTICS.md)
- [Phase 3 Sprint 3: Enhancements](PHASE3_SPRINT3_ENHANCEMENTS.md)
- [Reputation System Architecture](REPUTATION_SYSTEM.md)
- [API Documentation](API.md)
- [Database Schema](DATABASE.md)

## Support & Troubleshooting

### Common Issues

**Messages not appearing in thread:**
- Verify appeal exists and is not archived
- Check `appeal_id` parameter is correct
- Ensure user has permission to view appeal

**Low ML confidence scores:**
- Insufficient historical data (need 5+ appeals for high confidence)
- Recent user account (less than 30 days old)
- Unusual appeal pattern

**Sentiment analysis unavailable:**
- Messages haven't been analyzed yet (async process)
- Language not supported for sentiment analysis

### Contact

For implementation questions or issues, refer to the code comments in services or contact the development team.
