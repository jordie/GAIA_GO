# Phase 2: Advanced Features - Quick Start Guide

## Ready to Start Phase 2?

✅ **Prerequisites Met:**
- Phase 1 (Operations) complete
- Production validation passed (7 days)
- Baseline metrics collected
- Team trained and confident
- System stable and performing

---

## Starting Phase 2 (Week 1 After Validation)

### Step 1: Review Architecture (Day 1)
```bash
# Read Phase 2 plan
cat PHASE_2_ADVANCED_FEATURES_PLAN.md

# Understand the 3 features:
# 1. Anomaly Detection (ML)
# 2. Adaptive Limiting (Smart scaling)
# 3. Reputation System (Trust scores)

# Review code structure
ls -la services/
# Will add:
# - anomaly_detection.py (NEW)
# - adaptive_limiter.py (NEW)
# - reputation_system.py (NEW)
```

### Step 2: Set Up Feature Branches (Day 2)
```bash
# Create feature branch
git checkout -b feature/phase2-advanced-features-$(date +%m%d)

# Create feature flag configuration
cat > config/feature_flags.py << 'EOF'
"""Feature flags for Phase 2 advanced features"""

FEATURES = {
    'anomaly_detection': {
        'enabled': False,
        'rollout_percentage': 0,
        'min_data_days': 7,
        'confidence_threshold': 0.8,
    },
    'adaptive_limiting': {
        'enabled': False,
        'rollout_percentage': 0,
        'vip_tiers_enabled': False,
        'behavioral_learning': False,
    },
    'reputation_system': {
        'enabled': False,
        'rollout_percentage': 0,
        'auto_adjust_limits': False,
        'reputation_decay': 0.99,
    }
}

def is_feature_enabled(feature_name, user_id=None):
    """Check if feature is enabled for user"""
    feature = FEATURES.get(feature_name, {})
    if not feature.get('enabled'):
        return False

    # Rollout percentage check
    rollout = feature.get('rollout_percentage', 0)
    if user_id:
        # Hash user_id to consistent rollout
        user_hash = hash(str(user_id)) % 100
        return user_hash < rollout

    return rollout > 0
EOF

git add config/feature_flags.py
git commit -m "Add feature flags for Phase 2"
```

### Step 3: Create Database Migration (Day 2)
```bash
# Create migration file
cat > migrations/051_advanced_features.sql << 'EOF'
-- Phase 2 Advanced Features Schema

-- User Reputation
CREATE TABLE IF NOT EXISTS user_reputation (
    user_id INTEGER PRIMARY KEY,
    reputation_score REAL DEFAULT 50,
    last_violation TIMESTAMP,
    total_violations INTEGER DEFAULT 0,
    total_clean_requests INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reputation Events
CREATE TABLE IF NOT EXISTS reputation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_reputation(user_id)
);

-- Anomaly Detection
CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anomaly_type TEXT NOT NULL,
    confidence REAL,
    affected_users INTEGER,
    response_action TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- VIP Users
CREATE TABLE IF NOT EXISTS vip_users (
    user_id INTEGER PRIMARY KEY,
    tier TEXT NOT NULL,
    limit_multiplier REAL DEFAULT 1.0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Baseline Metrics (for anomaly detection)
CREATE TABLE IF NOT EXISTS baseline_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    metric_hour INTEGER,
    avg_request_rate REAL,
    std_dev_request_rate REAL,
    avg_violation_rate REAL,
    geographic_distribution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_reputation_score ON user_reputation(reputation_score);
CREATE INDEX idx_reputation_events ON reputation_events(user_id, timestamp);
CREATE INDEX idx_anomalies_type ON anomalies(anomaly_type, detected_at);
CREATE INDEX idx_baseline_date ON baseline_metrics(metric_date, metric_hour);
EOF

# Test migration
sqlite3 data/prod/architect.db < migrations/051_advanced_features.sql
```

---

## Implementation Order

### Week 1: Reputation System (Easiest)
```python
# 1. Create services/reputation_system.py
# 2. Integrate with rate_limiting.py
# 3. Record events on each request
# 4. Test scoring logic

# Core:
- ReputationSystem class (200 lines)
- Database schema (✓)
- Event recording (50 lines)
- Score calculation (50 lines)

# Tests:
- 16 unit tests
- Integration with rate limiter
```

**Tasks:**
- [ ] Create ReputationSystem class
- [ ] Implement event recording
- [ ] Implement score calculation
- [ ] Write 16 unit tests
- [ ] Integrate with rate limiter
- [ ] Test with real data

**Expected Duration:** 3-4 days

---

### Week 2: Adaptive Limiting (Medium)
```python
# 1. Create services/adaptive_limiter.py
# 2. VIP tier support
# 3. Load-aware limiting
# 4. User behavior learning

# Core:
- AdaptiveLimiter class (200 lines)
- VIP management (50 lines)
- Load adjustment (50 lines)
- Pattern learning (50 lines)

# Tests:
- 12 unit tests
- Integration with reputation
```

**Tasks:**
- [ ] Create AdaptiveLimiter class
- [ ] Implement VIP tier system
- [ ] Implement load-aware scaling
- [ ] Implement pattern learning
- [ ] Write 12 unit tests
- [ ] Integrate with reputation system
- [ ] Create VIP management API

**Expected Duration:** 4-5 days

---

### Week 3-4: Anomaly Detection (Complex)
```python
# 1. Create services/anomaly_detection.py
# 2. Learn baseline from Week 1 production data
# 3. Detect anomalies in real-time
# 4. Auto-respond or alert

# Core:
- AnomalyDetector class (200 lines)
- Baseline learning (100 lines)
- Detection algorithms (100 lines)
- Response/alerting (50 lines)

# Tests:
- 12 unit tests
- Integration with reputation + adaptive
```

**Tasks:**
- [ ] Collect and analyze Week 1 metrics
- [ ] Create AnomalyDetector class
- [ ] Implement baseline learning
- [ ] Implement detection algorithms
- [ ] Implement auto-response
- [ ] Write 12 unit tests
- [ ] Integration testing with other features
- [ ] Performance benchmarking

**Expected Duration:** 5-7 days

---

## Development Checklist

### Phase 2 Week 1 (Reputation System)
```
Day 1:
  [ ] Create reputation_system.py skeleton
  [ ] Define ReputationSystem class
  [ ] Design event recording mechanism

Day 2:
  [ ] Implement score calculation
  [ ] Add event persistence to database
  [ ] Create unit tests (8 tests)

Day 3:
  [ ] Implement decay mechanics
  [ ] Add score thresholds
  [ ] Add more unit tests (8 tests)
  [ ] Integration test with rate limiter

Day 4:
  [ ] Test with production data
  [ ] Verify score distribution
  [ ] Bug fixes and optimizations
  [ ] Code review

Day 5:
  [ ] Merge to main
  [ ] Feature flag set to 0% rollout
  [ ] Document usage
```

### Phase 2 Week 2 (Adaptive Limiting)
```
Day 1:
  [ ] Create adaptive_limiter.py skeleton
  [ ] Design VIP tier system
  [ ] Define load adjustment logic

Day 2:
  [ ] Implement get_adaptive_limit()
  [ ] Implement VIP management
  [ ] Create unit tests (6 tests)

Day 3:
  [ ] Implement load-aware scaling
  [ ] Implement pattern learning
  [ ] Add more unit tests (6 tests)

Day 4:
  [ ] Integration with reputation system
  [ ] Test interaction between features
  [ ] Performance testing

Day 5:
  [ ] Merge to main
  [ ] Feature flag set to 0% rollout
  [ ] Document API endpoints
```

### Phase 2 Weeks 3-4 (Anomaly Detection)
```
Days 1-2:
  [ ] Analyze Week 1 production metrics
  [ ] Design baseline model
  [ ] Create anomaly_detection.py

Days 3-4:
  [ ] Implement baseline learning
  [ ] Implement detection algorithms
  [ ] Create unit tests (8 tests)

Days 5-6:
  [ ] Implement auto-response
  [ ] Add alerting
  [ ] Integration testing

Days 7-8:
  [ ] Performance benchmarking
  [ ] Load testing
  [ ] Feature interaction testing
  [ ] Code review
```

---

## Testing Strategy

### Unit Tests (40+ total)
```bash
# Run tests for each feature
pytest tests/unit/test_reputation_system.py -v
pytest tests/unit/test_adaptive_limiter.py -v
pytest tests/unit/test_anomaly_detection.py -v

# Integration tests
pytest tests/integration/test_phase2_features.py -v

# Check coverage
pytest --cov=services tests/
# Target: > 85% coverage
```

### Integration Testing
```bash
# Test interaction between features
# Reputation + Adaptive Limiting
# Adaptive Limiting + Anomaly Detection
# All 3 together

# Verify backward compatibility
# Old rate limiting still works
# New features don't break existing API
```

### Production Testing (Staging)
```bash
# Test in staging with production data
# Feature flag rollout: 1% → 5% → 10% → 50% → 100%
# Monitor metrics at each step
# Easy rollback at any point
```

---

## Rollout Plan

### Staging (Week 4)
```
Day 1:
  [ ] Deploy to staging
  [ ] Feature flags: 0% (disabled)
  [ ] Verify no issues

Days 2-3:
  [ ] Enable reputation system (100%)
  [ ] Verify scoring works
  [ ] Monitor performance

Days 4-5:
  [ ] Enable adaptive limiting (100%)
  [ ] Test VIP adjustments
  [ ] Monitor resource usage

Days 6-7:
  [ ] Enable anomaly detection (100%)
  [ ] Test with known patterns
  [ ] Verify alerting
```

### Production Canary (Week 5)
```
Day 1:
  [ ] Deploy to production
  [ ] All features: 0% rollout
  [ ] Verify no issues

Days 2-3:
  [ ] Reputation system: 5% rollout
  [ ] Monitor metrics
  [ ] A/B test comparison

Days 4-5:
  [ ] Reputation system: 25% rollout
  [ ] Adaptive limiting: 5% rollout
  [ ] A/B test continues

Days 6-7:
  [ ] Reputation system: 100% rollout
  [ ] Adaptive limiting: 25% rollout
  [ ] Anomaly detection: 5% rollout
  [ ] Monitor all metrics
```

### Production Full Rollout (Week 6)
```
Day 1:
  [ ] Reputation system: 100% (continue)
  [ ] Adaptive limiting: 50% rollout
  [ ] Anomaly detection: 10% rollout

Day 2-3:
  [ ] Adaptive limiting: 100% rollout
  [ ] Anomaly detection: 25% rollout
  [ ] Final monitoring

Day 4-7:
  [ ] Anomaly detection: 50% → 100% rollout
  [ ] Final verification
  [ ] Success metrics review
  [ ] Documentation updates
```

---

## Success Metrics to Track

### Reputation System
```
□ Score distribution (should be roughly normal)
□ Correlation with behavior (R² > 0.85)
□ Event recording accuracy (100%)
□ Database performance (< 10ms queries)
```

### Adaptive Limiting
```
□ VIP tier adoption (> 10% of users)
□ Load adjustment accuracy (within 10%)
□ Pattern learning quality (> 90% accuracy)
□ User satisfaction (NPS > 40)
```

### Anomaly Detection
```
□ Detection accuracy (> 85%)
□ False positive rate (< 5%)
□ Response time (< 100ms)
□ Model stability (confidence > 0.7)
```

### Overall
```
□ No performance degradation (< 10ms added latency)
□ No unintended side effects
□ Backward compatibility (100%)
□ User complaints (< 1% of traffic)
```

---

## Monitoring & Alerts

### Key Dashboards
```
- Reputation Score Distribution (histogram)
- Adaptive Limit Adjustments (real-time)
- Anomaly Detection Alerts (timeline)
- Feature Impact Metrics (vs baseline)
```

### Alert Conditions
```
- Reputation score stuck at extreme (0 or 100)
- Adaptive limits cause violations to spike
- Anomaly detection high false positive rate (> 10%)
- Features causing latency increase (> 10ms)
```

---

## Documentation to Create

### User-Facing
- [ ] VIP Tier Management Guide
- [ ] Reputation System Explanation
- [ ] How to Improve Your Reputation Score

### Developer
- [ ] Reputation System API Docs
- [ ] Adaptive Limiter Architecture
- [ ] Anomaly Detection Model Details

### Operations
- [ ] Feature Flag Management
- [ ] Alert Runbook for Phase 2
- [ ] Rollback Procedures

---

## Contingency Plans

### If Reputation System Has Issues
```
→ Disable feature flag
→ Investigate scoring logic
→ Fix and re-test
→ Gradual rollout again
```

### If Adaptive Limits Cause Problems
```
→ Reduce VIP multiplier (2.0 → 1.5)
→ Disable behavioral learning
→ Increase conservative thresholds
→ Full rollback if necessary
```

### If Anomaly Detection Causes False Positives
```
→ Increase confidence threshold (0.8 → 0.9)
→ Reduce rollout percentage
→ Improve model training
→ Manual review before action
```

---

## Next Steps (Right Now!)

### Immediate (This Week)
- [ ] Read PHASE_2_ADVANCED_FEATURES_PLAN.md
- [ ] Review RATE_LIMITING_PRODUCT_ROADMAP.md
- [ ] Create feature branch
- [ ] Set up feature flags
- [ ] Create database migration

### Short Term (Next 2 Weeks)
- [ ] Start implementation (reputation system first)
- [ ] Write unit tests
- [ ] Deploy to staging
- [ ] Staging testing

### Medium Term (Week 3-4)
- [ ] Complete all features
- [ ] Integration testing
- [ ] Production canary rollout
- [ ] Monitor metrics

---

## Resources

**Code:**
- PHASE_2_ADVANCED_FEATURES_PLAN.md - Technical details
- services/rate_limiting.py - Current implementation (reference)
- tests/unit/test_rate_limiting.py - Test patterns (reference)

**Documentation:**
- RATE_LIMITING_PRODUCT_ROADMAP.md - 5-phase vision
- POST_DEPLOYMENT_MONITORING.md - Monitoring setup
- RATE_LIMITING_OPERATIONS.md - Operational procedures

**Help:**
- Feature flags in config/feature_flags.py
- Database schema in migrations/051_advanced_features.sql
- Test templates in tests/unit/

---

## Questions?

**Q: What if Phase 2 features break something?**
A: Feature flags allow instant disable with no code change. Full rollback < 5 minutes.

**Q: How long will Phase 2 take?**
A: 4 weeks for full implementation, testing, and rollout.

**Q: What if we don't need all 3 features?**
A: Each feature is independent. Can deploy any subset.

**Q: Can we pause Phase 2?**
A: Yes. Feature flags mean partial deployment is fine.

**Q: What about backward compatibility?**
A: All Phase 2 features are additive. Old API still works.

---

**Status:** Ready to begin
**Timeline:** Start after 7-day production validation
**Expected Completion:** 4 weeks after start
**Next Review:** Weekly progress check
