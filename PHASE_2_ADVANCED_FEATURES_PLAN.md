# Phase 2: Advanced Rate Limiting Features

## Overview

Build upon the production-tested foundation with intelligent, adaptive features that improve security and user experience.

**Timeline:** Week 2-4 after production deployment
**Status:** Planning phase
**Goal:** Implement 3 major advanced features

---

## Phase 2 Feature Set

### 1. ML-Based Anomaly Detection

**What it does:**
- Learns normal traffic patterns in Week 1
- Detects unusual behavior (bot attacks, scraping, abuse)
- Automatically adjusts thresholds
- Generates insights and alerts

**Implementation:**
```python
# services/anomaly_detection.py (NEW)
class AnomalyDetector:
    def __init__(self):
        self.baseline = None
        self.model = None

    def learn_baseline(self, metrics_data):
        """Learn normal traffic patterns from Week 1 data"""
        # Use statistical analysis:
        # - Mean/std dev of request rate
        # - Time-of-day patterns
        # - Geographic distribution
        # - User behavior patterns

    def detect_anomaly(self, current_metrics):
        """Detect if current traffic is anomalous"""
        # Compare against baseline
        # Return: (is_anomaly, confidence_score, anomaly_type)

    def update_limits(self, anomaly):
        """Automatically adjust rate limits if anomaly detected"""
        # Increase limits for legitimate spikes
        # Decrease for suspected attacks
        pass
```

**Metrics to track:**
- Request rate (requests/minute)
- Unique IPs (geographical origin)
- User agents (bot detection)
- Request patterns (time-of-day, days-of-week)
- Response times (performance anomalies)
- Error rates (system health)

**Training data:** 7 days of baseline metrics (collected during Week 1)

**Benefits:**
- Reduce false positives
- Auto-respond to attacks
- Improve user experience for legitimate traffic
- Better security posture

---

### 2. Adaptive Rate Limiting

**What it does:**
- Adjusts limits based on system load
- Prioritizes VIP users/API keys
- Learns user patterns and adjusts individually
- Balances between security and usability

**Implementation:**
```python
# services/adaptive_limiter.py (NEW)
class AdaptiveLimiter:
    def __init__(self):
        self.vip_users = {}
        self.user_patterns = {}
        self.system_load = 0

    def get_adaptive_limit(self, user_id, default_limit):
        """Get limit adjusted for user and system state"""

        # 1. Base limit
        limit = default_limit

        # 2. VIP adjustment
        if user_id in self.vip_users:
            limit = self.vip_users[user_id]['limit_multiplier'] * limit

        # 3. User pattern adjustment
        if user_id in self.user_patterns:
            pattern = self.user_patterns[user_id]
            if pattern['is_normal']:
                limit = limit * 1.5  # Increase for predictable users

        # 4. System load adjustment
        if self.system_load > 80:
            limit = limit * 0.8  # Reduce under load
        elif self.system_load < 30:
            limit = limit * 1.2  # Increase if plenty of capacity

        return int(limit)

    def learn_user_pattern(self, user_id, metrics):
        """Learn individual user's normal behavior"""
        # Track: request frequency, time of day, endpoint patterns
        # Determine: is this user's behavior predictable?

    def mark_vip(self, user_id, multiplier=2.0):
        """Mark user as VIP with priority access"""
        self.vip_users[user_id] = {
            'limit_multiplier': multiplier,
            'marked_at': datetime.now()
        }
```

**Features:**
- VIP tier system (premium users get higher limits)
- Behavioral learning (recognize legitimate heavy users)
- Load-aware limiting (adjust based on system capacity)
- Individual user profiles (track patterns per user)

**Configuration:**
```json
{
  "vip_tiers": {
    "standard": 1.0,
    "premium": 2.0,
    "enterprise": 5.0,
    "internal": 10.0
  },
  "system_load_adjustment": {
    "critical": 0.5,
    "high": 0.8,
    "normal": 1.0,
    "low": 1.2
  }
}
```

**Benefits:**
- Better user experience for known good users
- Automatic capacity management
- Premium revenue opportunity
- Fairness in resource allocation

---

### 3. User Reputation System

**What it does:**
- Builds reputation scores for users/IPs
- Grants higher limits to trusted users
- Penalizes repeat violators
- Creates feedback loop for improvement

**Implementation:**
```python
# services/reputation_system.py (NEW)
class ReputationSystem:
    def __init__(self):
        self.scores = {}  # user_id -> reputation_score
        self.history = {}  # user_id -> [events]

    def get_reputation(self, user_id):
        """Get user's reputation score (0-100)"""
        if user_id not in self.scores:
            return 50  # Neutral starting point
        return self.scores[user_id]

    def record_event(self, user_id, event_type, severity):
        """Record user action affecting reputation"""
        # event_type: 'rate_limit_violation', 'clean_request', 'error', 'success'
        # severity: 1-10

        if user_id not in self.history:
            self.history[user_id] = []

        self.history[user_id].append({
            'event': event_type,
            'severity': severity,
            'timestamp': datetime.now()
        })

        # Update score based on recent events
        self._update_score(user_id)

    def _update_score(self, user_id):
        """Recalculate reputation score"""
        # Positive events: +1 (clean request, success)
        # Negative events: -5 (violation), -10 (attack)
        # Decay: 0.99x per day (forgive old behavior)
        # Weighted: recent events count more

        score = 50  # Start neutral
        recent = self.history[user_id][-100:]  # Last 100 events

        for event in recent:
            if event['event'] == 'rate_limit_violation':
                score -= event['severity']
            elif event['event'] == 'clean_request':
                score += 0.5

        # Apply decay based on time
        days_since_violation = self._days_since_event(user_id, 'violation')
        score = score * (0.99 ** days_since_violation)

        # Clamp to 0-100
        self.scores[user_id] = max(0, min(100, score))

    def get_limit_modifier(self, user_id):
        """Get rate limit multiplier based on reputation"""
        reputation = self.get_reputation(user_id)

        # Reputation -> limit multiplier
        # 0-25:   0.5x (restricted)
        # 25-50:  0.8x (cautious)
        # 50-75:  1.0x (normal)
        # 75-90:  1.5x (trusted)
        # 90-100: 2.0x (highly trusted)

        if reputation < 25:
            return 0.5
        elif reputation < 50:
            return 0.8
        elif reputation < 75:
            return 1.0
        elif reputation < 90:
            return 1.5
        else:
            return 2.0
```

**Scoring System:**
- **Positive Events:** +1 per 100 clean requests
- **Negative Events:** -5 per violation, -10 per attack
- **Decay:** 0.99x per day (forgive old behavior)
- **Bounds:** 0 (untrusted) to 100 (highly trusted)

**Benefits:**
- Encourage good behavior
- Reward trusted users with better service
- Automatic risk-based enforcement
- Data-driven trust decisions

---

## Implementation Timeline

### Week 1: Foundation
- [ ] Design anomaly detection algorithm
- [ ] Create baseline metrics collection
- [ ] Build reputation scoring system
- [ ] Set up feature flags

### Week 2: Core Implementation
- [ ] Implement AnomalyDetector class
- [ ] Implement AdaptiveLimiter class
- [ ] Implement ReputationSystem class
- [ ] Integration with rate limiting service

### Week 3: Testing & Tuning
- [ ] Unit tests for each feature (30+ tests)
- [ ] Integration tests with real data
- [ ] Performance benchmarks
- [ ] Fine-tune thresholds

### Week 4: Deployment & Monitoring
- [ ] Feature flag rollout (10% → 50% → 100%)
- [ ] A/B testing against baseline
- [ ] Monitor for side effects
- [ ] Gather user feedback

---

## Database Schema Updates

```sql
-- Reputation scores
CREATE TABLE IF NOT EXISTS user_reputation (
    user_id INTEGER PRIMARY KEY,
    reputation_score REAL DEFAULT 50,
    last_violation TIMESTAMP,
    total_violations INTEGER DEFAULT 0,
    total_clean_requests INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reputation events
CREATE TABLE IF NOT EXISTS reputation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,  -- 'violation', 'clean', 'error', 'success'
    severity INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_reputation(user_id)
);

-- Anomaly detections
CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anomaly_type TEXT NOT NULL,  -- 'bot_attack', 'scraping', 'ddos', 'unusual_pattern'
    confidence REAL,
    affected_users INTEGER,
    response_action TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- VIP user configuration
CREATE TABLE IF NOT EXISTS vip_users (
    user_id INTEGER PRIMARY KEY,
    tier TEXT NOT NULL,  -- 'standard', 'premium', 'enterprise', 'internal'
    limit_multiplier REAL DEFAULT 1.0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_reputation_score ON user_reputation(reputation_score);
CREATE INDEX idx_reputation_events_user ON reputation_events(user_id, timestamp);
CREATE INDEX idx_anomalies_type ON anomalies(anomaly_type, detected_at);
```

---

## API Endpoints (New)

```
GET  /api/rate-limiting/user/{id}/reputation
     Returns: {reputation: 50, tier: 'premium', limit_multiplier: 2.0}

POST /api/rate-limiting/vip
     Body: {user_id: 123, tier: 'premium'}
     Marks user as VIP

GET  /api/rate-limiting/anomalies
     Returns: {active_anomalies: [...], resolved_today: 5}

GET  /api/rate-limiting/adaptive-limits/{user_id}
     Returns: Current adaptive limits based on user profile

POST /api/rate-limiting/learn-baseline
     Initiates learning from Week 1 data

GET  /api/rate-limiting/feature-status
     Returns: {anomaly_detection: {enabled, confidence}, ...}
```

---

## Feature Flags

```python
# config/feature_flags.py
FEATURES = {
    'anomaly_detection': {
        'enabled': False,
        'rollout_percentage': 0,  # 0-100
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

# Usage:
if is_feature_enabled('anomaly_detection', user_id):
    anomalies = detector.detect_anomaly(metrics)
```

---

## Testing Strategy

### Unit Tests (40+ tests)
- AnomalyDetector: 12 tests
  - Baseline learning
  - Anomaly detection
  - Confidence scoring
  - False positive rates

- AdaptiveLimiter: 12 tests
  - VIP adjustments
  - Load-based scaling
  - User pattern learning
  - Edge cases

- ReputationSystem: 16 tests
  - Score calculation
  - Event recording
  - Decay mechanics
  - Threshold behavior

### Integration Tests (10+ tests)
- Full pipeline with real data
- Feature interaction
- Performance under load
- Regression against baseline

### A/B Tests (Real Production Data)
- Control: Original rate limiting (10% of traffic)
- Test: With advanced features (90% of traffic)
- Metrics: Violation rate, user satisfaction, false positives

---

## Success Metrics

### Week 1
- [ ] Baseline learned with 7 days of data
- [ ] System detects known attack patterns
- [ ] Reputation system running on all users

### Week 2
- [ ] False positive rate < 5%
- [ ] Anomaly detection 85%+ accurate
- [ ] No performance degradation (< 10ms added latency)

### Week 3
- [ ] Adaptive limits reduce violations by 20%
- [ ] VIP users report better experience
- [ ] Reputation system shows good correlation with behavior

### Week 4
- [ ] 100% rollout with high confidence
- [ ] Net positive impact on user experience
- [ ] Security incidents detected proactively

---

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| False positives block good users | Start with low confidence threshold, use feature flags for gradual rollout |
| Complex interactions cause bugs | Extensive testing, feature flags, canary deployment |
| Performance impact | Monitor latency, use caching, async anomaly detection |
| Gaming the system | Reputation decay, multiple signals, behavioral analysis |
| Data quality issues | Validate baseline, handle missing data, robust error handling |

---

## Configuration Examples

### Conservative (High Security)
```python
ANOMALY_DETECTION = {
    'enabled': True,
    'confidence_threshold': 0.95,  # Only act on very confident detections
    'auto_response': False,        # Manual review before action
}

ADAPTIVE_LIMITER = {
    'enabled': True,
    'vip_multiplier': 1.5,         # VIPs get 50% more
    'load_adjustment': False,      # Don't adjust based on load
}

REPUTATION = {
    'enabled': True,
    'auto_adjust_limits': False,   # Manual adjustment only
    'violation_penalty': 10,       # Heavy penalty for violations
}
```

### Aggressive (User Experience)
```python
ANOMALY_DETECTION = {
    'enabled': True,
    'confidence_threshold': 0.7,   # Act on moderate confidence
    'auto_response': True,         # Automatically adjust
}

ADAPTIVE_LIMITER = {
    'enabled': True,
    'vip_multiplier': 3.0,         # VIPs get 3x more
    'load_adjustment': True,       # Always adjust based on load
}

REPUTATION = {
    'enabled': True,
    'auto_adjust_limits': True,    # Automatic increases for good users
    'violation_penalty': 2,        # Light penalty, quick recovery
}
```

---

## Rollout Strategy

### Phase 1: Internal Testing (Week 1-2)
- Staging environment only
- Team testing and feedback
- Threshold tuning

### Phase 2: Canary Deployment (Week 3)
- 5% of production traffic
- Monitor metrics closely
- Prepare rollback if needed

### Phase 3: Gradual Rollout (Week 4)
- 5% → 25% → 50% → 100%
- Each step: 1-2 days monitoring
- Automatic rollback on anomalies

### Phase 4: Full Production (Week 5)
- 100% traffic
- Monitor for weeks
- Gather feedback for improvements

---

## Post-Launch Improvements

### Month 2
- Geographic-based limiting (different limits by region)
- Time-zone aware patterns (account for regional usage)
- API endpoint-specific reputation (some endpoints trusted more)

### Month 3
- Machine learning model (more sophisticated anomaly detection)
- Behavioral clustering (group similar users)
- Predictive limiting (forecast and prevent issues)

### Month 4
- Integration with security systems
- DDoS-specific detection and response
- Advanced reporting and analytics

---

## Documentation

New files to create:
- PHASE_2_IMPLEMENTATION_GUIDE.md
- ADVANCED_FEATURES_CONFIG.md
- ML_MODEL_DOCUMENTATION.md
- REPUTATION_SYSTEM_GUIDE.md

---

## Success Criteria for Phase 2 Completion

- ✅ All 3 features implemented and tested
- ✅ 40+ unit tests passing
- ✅ Integration tests passing with real data
- ✅ < 10ms added latency
- ✅ < 5% false positive rate
- ✅ Feature flags working correctly
- ✅ A/B test shows positive results
- ✅ 100% rollout to production
- ✅ Documentation complete
- ✅ Team trained on new features

---

**Timeline:** 4 weeks after production validation
**Dependencies:** Week 1 production baseline data
**Status:** Ready to plan in detail
