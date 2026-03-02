# Reputation System User Guide

## Overview

The GAIA GO Reputation System provides comprehensive user behavior tracking and adaptive rate limiting based on reputation scores. This guide covers system concepts, usage, and administration.

---

## System Concepts

### Reputation Score (0-100)

Each user has a reputation score that:
- Starts at **50** (neutral)
- Increases with clean requests (+1 point per 100 allowed requests)
- Decreases with violations (-3 to -9 points based on severity)
- Automatically decays towards 50 weekly (±5 points/week)
- Affects their rate limit multiplier

### Tiers

Scores automatically map to tiers:

| Tier | Score Range | Multiplier | Limit Impact | Characteristics |
|------|------------|-----------|--------------|-----------------|
| **Flagged** | 0-20 | 0.5x | Halved | Multiple violations detected, user abuse pattern |
| **Standard** | 20-80 | 1.0x | Normal | Default tier for new users |
| **Trusted** | 80-100 | 1.5x | +50% | Good behavior history |
| **Premium (VIP)** | Any | 2.0x | Doubled | Manual admin override, corporate accounts |

### Rate Limit Multiplier

The multiplier adjusts base rate limits:

```
Adjusted Limit = Base Limit × Multiplier
```

**Example:**
- API endpoint: 1000 requests/minute
- Flagged user (0.5x): 500 requests/minute
- Trusted user (1.5x): 1500 requests/minute
- Premium VIP (2.0x): 2000 requests/minute

---

## How It Works

### Request Processing

```
User Makes Request
    ↓
Get user reputation score (cached, 5-min TTL)
    ↓
Calculate multiplier based on score
    ↓
Apply multiplier to rate limit
    ↓
Check if within adjusted limit
    ↓
    ├─ ALLOWED:
    │   ├─ Increment clean request counter
    │   ├─ Gradually increase reputation
    │   └─ Return 200 OK
    │
    └─ BLOCKED:
        ├─ Record violation event
        ├─ Apply penalty to reputation (severity-based)
        ├─ Update tier and multiplier
        └─ Return 429 Too Many Requests
```

### Violation Severity

Different resource types have different penalties:

| Resource Type | Severity | Penalty | Reason |
|---------------|----------|---------|--------|
| **Login** | 3 | -9 points | Security risk, brute force |
| **Default** | 2 | -6 points | Standard violations |
| **API Call** | 1 | -3 points | Less critical |

### Decay System

Every week, reputation scores automatically move towards neutral (50):

- **Above 50:** Score decreases by 5
- **Below 50:** Score increases by 5
- **Equals 50:** No change

**Purpose:** Prevent permanent punishment, allow recovery

**Example:**
```
Day 1:  User violates, score drops to 20 (flagged)
Day 8:  Decay applied, score rises to 25
Day 15: Decay applied, score rises to 30
Day 36: Decay applied, score reaches 50 (standard)
```

---

## Admin Dashboard

Access at: **`http://localhost:8080/admin/reputation`**

### Dashboard Tab

**Metrics:**
- Total users tracked
- Distribution by tier (flagged, standard, trusted, premium)
- Average reputation score
- Recent events

**Purpose:** System-wide overview at a glance

### Users Tab

**Features:**
- List all users with reputation details
- Search by user ID
- Filter by tier
- View individual metrics:
  - Current score with visual bar
  - Tier classification
  - Multiplier value
  - VIP status and expiration
  - Violation count
  - Clean requests count

**Actions:**
- **Edit**: Manually adjust user score (admin override)
- **VIP**: Assign VIP tier with expiration date

**Pagination:** 20 users per page

### Events Tab

**Search:**
- By user ID (required)
- By event type (violation, clean, decay, manual)

**Displays:**
- User ID
- Event type with color-coded badge
- Severity (for violations)
- Description
- Score change (green = positive, red = negative)
- Timestamp

**Purpose:** Audit trail and violation investigation

### Trends Tab

**Analytics:**
- 7, 14, or 30-day views
- Daily breakdown of:
  - Total violations
  - Total clean requests
  - Decay events
  - Overall event count

**Purpose:** Identify patterns and trends

### Settings Tab

**Tier Configuration:**
- View all tier definitions
- Score ranges
- Multipliers
- Descriptions

**Decay Management:**
- Trigger manual decay job
- Run immediately instead of waiting for weekly schedule

---

## API Endpoints

### List Users
```bash
GET /api/admin/reputation/users?page=1&limit=50
```

Response:
```json
{
  "users": [
    {
      "user_id": 123,
      "score": 75,
      "tier": "trusted",
      "multiplier": 1.5,
      "vip_tier": null,
      "violation_count": 2,
      "clean_requests": 450,
      "last_updated": "2026-02-26T10:30:00Z",
      "created_at": "2026-01-15T09:00:00Z"
    }
  ],
  "total": 1250,
  "page": 1,
  "limit": 50,
  "total_pages": 25
}
```

### Get User Details
```bash
GET /api/admin/reputation/users/{userID}
```

### Get Reputation History
```bash
GET /api/admin/reputation/users/{userID}/history?days=7
```

### Get User Events
```bash
GET /api/admin/reputation/users/{userID}/events?limit=20&type=violation
```

### Update User Reputation
```bash
curl -X PUT http://localhost:8080/api/admin/reputation/users/123 \
  -H "Content-Type: application/json" \
  -d '{
    "score": 80,
    "description": "Admin review - violation evidence insufficient"
  }'
```

### Set VIP Tier
```bash
curl -X POST http://localhost:8080/api/admin/reputation/users/123/vip \
  -H "Content-Type: application/json" \
  -d '{
    "tier": "premium",
    "expires_at": "2026-03-26T00:00:00Z",
    "reason": "Corporate partner agreement"
  }'
```

### Remove VIP Tier
```bash
curl -X DELETE http://localhost:8080/api/admin/reputation/users/123/vip
```

### Get Statistics
```bash
GET /api/admin/reputation/stats
```

### Get Trends
```bash
GET /api/admin/reputation/trends?days=30
```

### Get Tier Information
```bash
GET /api/admin/reputation/tiers
```

### Trigger Decay
```bash
curl -X POST http://localhost:8080/api/admin/reputation/decay
```

---

## Common Scenarios

### Scenario 1: Brute Force Attack Detection

**Situation:** User 456 attempts 50 failed logins in 5 minutes

**System Response:**
1. First 10 attempts: Allowed (standard user)
2. 11th attempt: Rate limit triggered (login severity = 3, -9 points)
   - Score: 50 → 41
   - Tier: standard → flagged
   - Multiplier: 1.0x → 0.5x
3. 12-50 attempts: Blocked (user now at 0.5x limit)
4. User is flagged for review

**Resolution:**
- Admin reviews events
- Either: Reset score to 50 (clear false positive) or maintain flagged status

### Scenario 2: Legitimate User Recovering

**Situation:** User 789 has score of 15 (flagged)

**Recovery Path:**
1. User makes clean requests (no violations)
   - 100 clean requests: +1 point → Score 16
   - 500 clean requests: +5 points → Score 20
   - 3500 clean requests: +35 points → Score 50 (back to standard)
2. Weekly decay also helps (±5 points/week towards neutral)
3. After ~30 days: Can reach trusted tier (score 80)

### Scenario 3: VIP Corporate Partner

**Situation:** New enterprise customer needs 2x rate limits

**Setup:**
1. Admin goes to Users tab
2. Clicks "VIP" on user 999
3. Sets:
   - Tier: Premium
   - Expires: 90 days from now
   - Reason: "Annual enterprise contract"
4. User 999 now has 2.0x multiplier regardless of reputation score

**Auto-expiration:**
- On expiration date, VIP tier automatically removed
- User reverts to reputation-based multiplier

### Scenario 4: Investigating Suspicious Activity

**Situation:** Need to review potential API abuse

**Steps:**
1. Go to Events tab
2. Enter user ID and select "violation" type
3. Click Search
4. Review event timeline:
   - Pattern of violations
   - Severity of each
   - Resource types targeted
5. Decide if legitimate (false positive) or actual abuse
6. If legitimate: Use Edit button to restore score

---

## Administrative Tasks

### Weekly Decay Job

**Automatic (runs weekly):**
- All users: Score moves 5 points towards neutral (50)
- Prevents permanent low scores
- Ensures system doesn't remember old violations forever

**Manual Trigger:**
- Settings tab → "Apply Weekly Decay Now"
- Useful after mass violation review

### Score Auditing

**When to review scores:**
- After major security incident
- When product changes (new API endpoints)
- Before important events
- Quarterly reputation health check

**How to audit:**
1. Dashboard tab → Check tier distribution
2. Users tab → Sort by score
3. Events tab → Review recent violations
4. Identify suspicious patterns

### False Positive Correction

**If users report rate limiting without cause:**
1. Go to Users tab
2. Find user by ID
3. Click "Edit" button
4. Review violation events
5. If confirmed false positive:
   - Increase score to neutral (50) or higher
   - Add reason: "False positive - XX pattern review"
   - Submit

### Performance Monitoring

**Monitor reputation system health:**
- Dashboard → "Average Score" metric
- Should generally stay around 50
- If trending down: May indicate legitimate issues or overly aggressive limits
- If trending up: May indicate throttling is too lenient

---

## API Usage Examples

### Get All Flagged Users
```bash
curl 'http://localhost:8080/api/admin/reputation/users?page=1&limit=100' \
  | jq '.users[] | select(.tier == "flagged")'
```

### Find Recent Violations
```bash
for user_id in {100..150}; do
  curl -s "http://localhost:8080/api/admin/reputation/users/$user_id/events?type=violation&limit=5" \
    | jq -c "{user_id: .user_id, violation_count: (.events | length)}"
done
```

### Reset User to Neutral
```bash
curl -X PUT http://localhost:8080/api/admin/reputation/users/123 \
  -H "Content-Type: application/json" \
  -d '{
    "score": 50,
    "description": "Manual reset after investigation - false positive confirmed"
  }'
```

### Batch VIP Assignment
```bash
for user_id in 100 101 102; do
  curl -X POST "http://localhost:8080/api/admin/reputation/users/$user_id/vip" \
    -H "Content-Type: application/json" \
    -d '{
      "tier": "premium",
      "expires_at": "2026-12-26T00:00:00Z",
      "reason": "Annual subscription 2026"
    }'
done
```

---

## Database Queries

### Find Trending Down Users
```sql
SELECT
  rs.user_id,
  rs.score,
  rs.tier,
  COUNT(re.id) as violations_7days
FROM reputation_scores rs
LEFT JOIN reputation_events re
  ON rs.user_id = re.user_id
  AND re.event_type = 'violation'
  AND re.created_at > NOW() - INTERVAL '7 days'
WHERE rs.score < 30
GROUP BY rs.user_id
ORDER BY violations_7days DESC
LIMIT 20;
```

### Export User Reputation Report
```sql
SELECT
  user_id,
  score,
  tier,
  multiplier,
  violation_count,
  clean_requests,
  last_updated
FROM reputation_scores
WHERE last_updated > NOW() - INTERVAL '30 days'
ORDER BY score ASC;
```

### Identify VIP Expiring Soon
```sql
SELECT
  user_id,
  vip_tier,
  vip_expires_at,
  NOW() + INTERVAL '7 days' as alert_date
FROM reputation_scores
WHERE vip_tier IS NOT NULL
  AND vip_expires_at IS NOT NULL
  AND vip_expires_at BETWEEN NOW() AND NOW() + INTERVAL '7 days'
ORDER BY vip_expires_at ASC;
```

---

## Troubleshooting

### User Claims They're Flagged Unfairly

**Steps:**
1. Go to Events tab
2. Search user ID
3. Review violation events
4. Check if violations are legitimate

**Resolution:**
- If legitimate issue: Use Edit to increase score to 50+
- If system error: Investigate the triggering code
- Consider tuning severity levels if too aggressive

### Dashboard Shows Wrong Statistics

**Causes:**
- Cache not invalidated
- Database has stale data
- API latency

**Resolution:**
- Refresh page (browser cache clear)
- Check database directly for truth
- Verify network connectivity

### VIP Tier Not Applied

**Check:**
1. VIP tier shows in user details
2. VIP hasn't expired
3. Is multiplier 2.0x?

**If not applied:**
- Cache may be stale (5-min TTL)
- Try again after waiting
- Check database directly

### Decay Not Running

**Verify:**
1. Go to Settings tab
2. Click "Apply Weekly Decay Now"
3. Check events for decay entries

**If manual decay fails:**
- Check database connection
- Check migrations are applied
- Review server logs

---

## Best Practices

### 1. Regular Monitoring
- Check Dashboard weekly
- Review tier distribution
- Watch for sudden changes

### 2. Incident Response
- When users report rate limiting issues
- Review Events tab immediately
- Make decision within 24 hours
- Document reason in score change

### 3. Tuning
- Start with conservative penalties
- Monitor for false positives
- Adjust severity levels if needed
- Test changes on non-production first

### 4. Communication
- Document all manual score changes with clear reasons
- Inform users when they reach milestones (flagged/trusted)
- Explain rate limiting with reputation context

### 5. Privacy
- Respect user privacy when investigating
- Don't expose other users' violations
- Maintain confidentiality of investigations

---

## Integration with Rate Limiting

### How Reputation Affects Limits

Rate limiting rules are applied with reputation adjustment:

```go
// Example: Default API endpoint limit = 1000/min
baseLimit := 1000

// For different users:
flaggedUser := baseLimit * 0.5  // 500/min
standardUser := baseLimit * 1.0 // 1000/min
trustedUser := baseLimit * 1.5  // 1500/min
vipUser := baseLimit * 2.0      // 2000/min
```

### Resource-Specific Penalties

Some resources have stricter limits due to security:
- **Login attempts:** Severity 3 (-9 points) - Authentication risk
- **API calls:** Severity 1 (-3 points) - Less critical
- **Default:** Severity 2 (-6 points) - Standard violation

---

## FAQ

**Q: How long does reputation take to recover?**
A: With weekly decay and clean requests: ~4-6 weeks for flagged users to reach standard tier.

**Q: Can I permanently flag a user?**
A: Technically no - decay will eventually bring them to neutral. Use VIP tier with 0.5x multiplier instead.

**Q: What if a user gets flagged by a bug?**
A: Use Edit button to manually set score to neutral (50) and document the reason.

**Q: Can users see their reputation?**
A: Currently only admins. Future enhancement: Expose via `/api/me/reputation` endpoint.

**Q: How are VIP expirations handled?**
A: Automatically on expiration date - reverts to reputation-based multiplier.

**Q: What's the maximum score?**
A: 100. Trusted tier is 80-100, but further improvements have diminishing returns.

---

## Support

For issues or questions:
1. Check Dashboard → Trends for patterns
2. Review Events for specific user history
3. Check database directly for truth
4. Review server logs for rate limiter errors

---

**Last Updated:** February 26, 2026
**Version:** 1.0 - Phase 2 Sprint 1
**Status:** Production Ready
