# Phase 2 Sprint 1: Reputation System Implementation Plan

**Status:** Ready to Start
**Timeline:** 2 weeks (2026-02-26 to 2026-03-12)
**Depends on:** Phase 11.4 (completed ✅)
**Goal:** Complete reputation system with database persistence and scoring

---

## Overview

Build a comprehensive reputation tracking system that monitors user behavior and dynamically adjusts rate limits based on user reputation scores. This enables:

- Distinguishing legitimate users from abusers
- Progressive penalties for repeat violators
- Rewards for clean behavior
- VIP user management
- Automatic tier assignment

---

## Sprint 1-2 Deliverables

### Week 1: Database Schema & Core Services
- [x] Database migrations (already created)
- [ ] ReputationManager service class
- [ ] ReputationScorer calculation engine
- [ ] Event tracking and audit trail
- [ ] Unit tests (8+ test cases)

### Week 2: Integration & Testing
- [ ] Integration with rate limiter
- [ ] Admin API endpoints for reputation management
- [ ] Dashboard UI for reputation monitoring
- [ ] Integration tests (6+ scenarios)
- [ ] Performance benchmarks

---

## Implementation Details

### 1. Database Schema (Already Created)

**Tables:**
- `user_reputation` - User reputation scores and tier
- `reputation_events` - Audit trail of reputation changes
- `vip_users` - VIP tier assignments with multipliers

**Schema Review:**
```sql
-- User Reputation Scores
user_reputation (
  id INTEGER PRIMARY KEY,
  user_id INTEGER UNIQUE,
  reputation_score REAL (0-100),
  tier TEXT ('standard', 'premium', 'enterprise', 'internal'),
  last_violation TIMESTAMP,
  total_violations INTEGER,
  total_clean_requests INTEGER,
  decay_last_applied TIMESTAMP
)

-- Reputation Events (audit trail)
reputation_events (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  event_type TEXT ('violation', 'clean_request', 'decay', 'manual_adjust'),
  severity INTEGER (1-5),
  description TEXT,
  score_delta REAL,
  timestamp TIMESTAMP
)

-- VIP User Tiers
vip_users (
  id INTEGER PRIMARY KEY,
  user_id INTEGER UNIQUE,
  tier TEXT,
  limit_multiplier REAL (default 1.0),
  notes TEXT,
  approved_by INTEGER,
  approved_at TIMESTAMP
)
```

### 2. ReputationManager Service (NEW)

**File:** `pkg/services/rate_limiting/reputation_manager.go`

**Responsibilities:**
- Load/save reputation scores from database
- Calculate reputation score changes
- Apply automatic decay
- Track user events
- Manage VIP assignments

**Key Methods:**
```go
type ReputationManager struct {
    db *gorm.DB
    cache map[int]*UserReputation
    cacheMutex sync.RWMutex
}

// GetUserReputation(userID int) -> *UserReputation
// RecordViolation(userID int, severity int, description string) -> error
// RecordCleanRequest(userID int) -> error
// SetVIPTier(userID int, tier string, multiplier float64) -> error
// GetAdaptiveLimit(userID int, baseLimit int) -> int
// ApplyRepDecay(userID int) -> error
// GetRepHistory(userID int, days int) -> []RepEvent
```

**Reputation Scoring Logic:**
```
Base Score: 50 (neutral)
Range: 0-100

Score Changes:
  + Clean request: +0.1 per 100 requests
  - Rate limit violation: -5 (standard), -10 (repeated)
  - Account suspension: -50
  + Tier promotion: +10
  - Tier demotion: -15

Automatic Decay:
  - Applied weekly
  - Returns 1 point towards 50 if below
  - Returns 1 point towards 50 if above (max 100)
  - Incentivizes good behavior (score decays to middle)

VIP Multipliers:
  - standard: 1.0x (default)
  - premium: 1.5x (manually assigned)
  - enterprise: 2.5x
  - internal: 5.0x (staff accounts)

Tier Assignment:
  - score < 30: flagged (2x violations = suspension)
  - score 30-50: standard
  - score 50-75: trusted
  - score > 75: premium
  (override with manual VIP assignment)
```

### 3. Integration with Rate Limiter

**File:** `pkg/services/rate_limiting/rate_limiter.go` (modified)

**Changes:**
```go
// Add reputation manager field
type PostgresRateLimiter struct {
    db *gorm.DB
    reputation *ReputationManager  // NEW
    ...
}

// Modify CheckLimit to use reputation
func (r *PostgresRateLimiter) CheckLimit(ctx context.Context, scope string, value string) (bool, *RateLimitInfo) {
    // Get base limit
    baseLimit := r.getBaseLimit(scope, value)

    // If user, adjust for reputation (NEW)
    if scope == "user" {
        userID := parseInt(value)
        reputation := r.reputation.GetUserReputation(userID)
        baseLimit = r.reputation.GetAdaptiveLimit(userID, baseLimit)
    }

    // Check against adjusted limit
    return r.checkAgainstLimit(baseLimit)
}

// After limit violation, record in reputation (NEW)
func (r *PostgresRateLimiter) RecordViolation(...) {
    ...
    // NEW: Record reputation event
    if scope == "user" {
        r.reputation.RecordViolation(userID, severity, reason)
    }
}
```

### 4. Admin API Endpoints (NEW)

**Base path:** `/api/admin/reputation`

```
GET    /api/admin/reputation/users         - List users with reputation scores
GET    /api/admin/reputation/users/{id}    - Get user reputation details
POST   /api/admin/reputation/users/{id}    - Update user reputation
GET    /api/admin/reputation/events        - Audit trail of reputation events
GET    /api/admin/reputation/tiers         - List VIP tier assignments
POST   /api/admin/reputation/tiers/{id}    - Assign VIP tier
DELETE /api/admin/reputation/tiers/{id}    - Remove VIP tier
GET    /api/admin/reputation/stats         - Reputation statistics
POST   /api/admin/reputation/decay         - Manual decay application (admin only)
```

**Example Responses:**

```json
GET /api/admin/reputation/users/123
{
  "user_id": 123,
  "reputation_score": 72.5,
  "tier": "premium",
  "vip_multiplier": 1.5,
  "total_violations": 2,
  "total_clean_requests": 450,
  "last_violation": "2026-02-25T14:30:00Z",
  "days_since_violation": 1,
  "status": "good",
  "adaptive_limit": 1500,  // 1000 * 1.5
  "trend": "improving"
}

GET /api/admin/reputation/stats
{
  "total_users": 542,
  "average_score": 58.3,
  "tier_distribution": {
    "standard": 450,
    "premium": 65,
    "enterprise": 20,
    "internal": 7
  },
  "violations_today": 12,
  "violations_week": 78,
  "users_flagged": 8,
  "users_suspended": 2
}
```

### 5. Dashboard UI (NEW)

**File:** `templates/admin_reputation_dashboard.html`

**Tabs:**
1. **Overview** - Reputation distribution chart
2. **Users** - Sortable user table with scores
3. **Events** - Audit trail of reputation changes
4. **VIP Management** - Tier assignments
5. **Alerts** - Flagged users and violations

**Features:**
- Real-time reputation score updates
- Search/filter users
- Bulk tier assignments
- Manual score adjustments
- Event filtering and export

---

## Implementation Tasks

### Week 1 Tasks

#### Day 1-2: Setup & Core Service
```
Task 1: Create ReputationManager service class
├─ File: pkg/services/rate_limiting/reputation_manager.go
├─ Lines: 400+
├─ Methods:
│  ├─ NewReputationManager(db *gorm.DB) *ReputationManager
│  ├─ GetUserReputation(userID int) *UserReputation
│  ├─ RecordViolation(userID, severity, desc)
│  ├─ RecordCleanRequest(userID)
│  ├─ ApplyRepDecay(userID)
│  └─ GetAdaptiveLimit(userID, baseLimit)
├─ Dependencies: GORM, rate_limiting models
└─ Tests: 6+ unit tests

Task 2: Create ReputationScorer calculation engine
├─ File: pkg/services/rate_limiting/reputation_scorer.go
├─ Lines: 250+
├─ Functions:
│  ├─ CalculateScoreDelta(event) float64
│  ├─ ApplyDecay(currentScore) float64
│  ├─ GetTierForScore(score) string
│  ├─ GetAdaptiveMultiplier(score, vipTier) float64
│  └─ IsUserFlagged(score) bool
├─ Tests: 4+ unit tests
└─ Performance: < 1ms per calculation
```

#### Day 3-5: Integration & Models
```
Task 3: Create reputation models and migrations verification
├─ File: pkg/services/rate_limiting/reputation_models.go
├─ Models:
│  ├─ UserReputation struct
│  ├─ ReputationEvent struct
│  ├─ VIPUser struct
│  └─ ScoreChange struct
├─ Database: Verify migration 050_phase2_reputation.sql
└─ Tests: 2+ model tests

Task 4: Integrate reputation with rate limiter
├─ File: pkg/services/rate_limiting/rate_limiter.go (modify)
├─ Changes:
│  ├─ Add reputation manager field
│  ├─ Modify CheckLimit to adjust for reputation
│  ├─ Record violations in reputation system
│  └─ Update adaptive limits based on score
├─ Tests: 3+ integration tests
└─ No breaking changes to existing API

Task 5: Create unit test suite
├─ File: pkg/services/rate_limiting/reputation_test.go
├─ Tests: 8+ scenarios
│  ├─ Score calculation
│  ├─ Decay logic
│  ├─ Tier assignment
│  ├─ VIP adjustments
│  ├─ Event recording
│  └─ Edge cases
└─ Coverage: > 85%
```

### Week 2 Tasks

#### Day 1-3: Admin APIs
```
Task 6: Create admin API handlers
├─ File: pkg/http/handlers/reputation_handlers.go
├─ Endpoints: 9+ routes
│  ├─ GET /api/admin/reputation/users
│  ├─ GET /api/admin/reputation/users/{id}
│  ├─ POST /api/admin/reputation/users/{id}
│  ├─ GET /api/admin/reputation/events
│  ├─ GET /api/admin/reputation/tiers
│  ├─ POST /api/admin/reputation/tiers/{id}
│  └─ More...
├─ Auth: Admin required for all endpoints
├─ Validation: Input validation + error handling
└─ Tests: 8+ API tests

Task 7: Create dashboard UI
├─ Files:
│  ├─ templates/admin_reputation_dashboard.html (500+ lines)
│  ├─ static/css/admin_reputation.css (300+ lines)
│  ├─ static/js/admin_reputation.js (600+ lines)
├─ Features:
│  ├─ 5-tab interface
│  ├─ Real-time updates
│  ├─ Search/filter
│  ├─ Chart visualizations
│  └─ Bulk operations
└─ Responsive: Mobile-friendly design
```

#### Day 4-5: Testing & Integration
```
Task 8: Integration tests
├─ File: pkg/services/rate_limiting/reputation_integration_test.go
├─ Scenarios: 6+ end-to-end tests
│  ├─ User accumulates violations
│  ├─ Score decay works correctly
│  ├─ Tier changes affect limits
│  ├─ VIP assignment overrides score
│  ├─ API CRUD operations
│  └─ Dashboard displays correct data
├─ Performance:
│  ├─ Reputation lookup: < 5ms
│  ├─ Score calculation: < 1ms
│  ├─ Decay operation: < 10ms
│  └─ 100 concurrent users: < 50ms p99
└─ Coverage: > 85%

Task 9: Documentation & Examples
├─ File: pkg/services/rate_limiting/REPUTATION_GUIDE.md
├─ Content:
│  ├─ Architecture overview
│  ├─ Usage examples
│  ├─ API reference
│  ├─ Configuration guide
│  └─ Troubleshooting
└─ Examples: 5+ code examples
```

---

## Testing Strategy

### Unit Tests (8+ test cases)
```go
// reputation_test.go
TestReputationScoring_BasicCalculation()
TestReputationScoring_DecayLogic()
TestReputationScoring_TierAssignment()
TestReputationScoring_VIPMultiplier()
TestReputationEvent_Recording()
TestReputationEvent_Filtering()
TestReputationCache_Performance()
TestReputationCache_Consistency()
```

### Integration Tests (6+ scenarios)
```go
// reputation_integration_test.go
TestE2E_UserViolationAccumulation()  // User gets violations -> score drops -> limits adjust
TestE2E_ScoreDecayApplication()      // Decay returns score towards 50
TestE2E_TierPromotion()              // Good behavior -> tier upgrade
TestE2E_VIPAssignment()              // VIP tier overrides score
TestE2E_AdminAPICRUD()               // Create/read/update reputation data
TestE2E_DashboardIntegration()       // Dashboard displays correct data
```

### API Tests
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://dev:8080/api/admin/reputation/users/123
# Expect: 200 OK with user reputation data

curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"tier":"premium","multiplier":1.5}' \
  http://dev:8080/api/admin/reputation/tiers/123
# Expect: 201 Created, VIP tier assigned
```

---

## Performance Targets

| Operation | Target | Acceptance |
|-----------|--------|-----------|
| Get user reputation | < 5ms | p99 < 10ms |
| Calculate score change | < 1ms | p99 < 2ms |
| Apply decay operation | < 10ms | p99 < 20ms |
| List users (100 rows) | < 100ms | p99 < 200ms |
| Record violation event | < 5ms | p99 < 10ms |
| 100 concurrent checks | < 50ms p99 | All succeed |

---

## Git Workflow

### Create Feature Branch
```bash
git checkout develop
git checkout -b feature/reputation-system-0226
```

### Commits (example structure)
```
feat: implement reputation manager service (350 lines)
feat: add reputation scorer calculation engine (250 lines)
feat: integrate reputation with rate limiter (100 lines)
feat: create admin reputation API endpoints (400 lines)
feat: build reputation management dashboard (800 lines)
test: add 8+ unit tests for reputation system (300 lines)
test: add 6+ integration tests (400 lines)
docs: add reputation system guide and examples
```

### Pull Request
```
Title: Phase 2 Sprint 1: Reputation System

Description:
- User reputation tracking with 0-100 score
- Automatic tier assignment based on behavior
- VIP user management with tier multipliers
- Reputation decay that returns scores towards 50
- Admin APIs for reputation management
- Dashboard UI for monitoring and adjustments
- 8+ unit tests + 6+ integration tests
- Performance validated: all ops < 20ms p99

Ready for: Code review → Dev deployment → QA testing
```

---

## Deployment Plan

### Dev Deployment
1. Merge to develop
2. Add tag: `deploy/dev/phase2-sprint1`
3. GAIA deploys to dev
4. Run full test suite
5. Monitor for 1 hour

### QA Deployment
1. After dev validation
2. Create PR: develop → qa
3. Add tag: `deploy/qa/phase2-sprint1`
4. GAIA deploys to QA
5. Run load tests for 2-3 days

### Production
1. After QA approval
2. Create PR: qa → main
3. Add tag: `deploy/prod/phase2-sprint1`
4. GAIA deploys to production

---

## Success Criteria

### Functionality
- [x] Database schema exists and tested
- [ ] ReputationManager service functional
- [ ] Score calculations correct
- [ ] Automatic decay works
- [ ] VIP assignments override scores
- [ ] Integration with rate limiter working

### Testing
- [ ] 8+ unit tests passing
- [ ] 6+ integration tests passing
- [ ] API tests all passing
- [ ] > 85% code coverage
- [ ] Performance targets met
- [ ] No regressions in rate limiting

### Documentation
- [ ] Architecture documented
- [ ] API reference complete
- [ ] Examples provided
- [ ] Admin guide written
- [ ] Troubleshooting guide included

### Code Quality
- [ ] No breaking changes
- [ ] Backward compatible
- [ ] Error handling complete
- [ ] Input validation thorough
- [ ] Code review approved
- [ ] Lint checks passed

---

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Score calculation bugs | Unit tests + code review |
| Performance issues under load | Load testing + caching |
| Database schema problems | Migration testing |
| Backward compatibility | Feature flag during rollout |
| Integration issues | Integration tests before merge |

---

## Timeline Summary

```
Week 1 (Feb 26 - Mar 4):  Development
  Day 1-2: Services & Core Logic
  Day 3-5: Integration & Testing

Week 2 (Mar 5 - Mar 12):  APIs & Dashboard
  Day 1-3: Admin endpoints & UI
  Day 4-5: Final testing & documentation

Post-Sprint:
  Day 1: Code review
  Day 2: Dev deployment via GAIA
  Day 3-4: Dev validation
  Day 5: QA promotion
  Day 6-8: QA testing
  Day 9+: Production deployment
```

---

## Sprint 1 Summary

**Start Date:** 2026-02-26
**End Date:** 2026-03-12
**Effort:** ~120 hours developer time
**Deliverables:** 2500+ lines of code + tests + docs
**Follow-up:** Sprint 2 will implement adaptive rate limiting

---

**Ready to start:** Phase 2 Sprint 1 - Reputation System Implementation
