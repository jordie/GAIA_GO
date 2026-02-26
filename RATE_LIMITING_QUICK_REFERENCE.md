# Rate Limiting Quick Reference Guide

**For on-call engineers - keep this handy**

---

## Emergency Commands

### 🚨 System Down / All Requests Blocked

```bash
# 1. Check if services running
curl http://localhost:8080/health

# 2. Restart app
pkill -f "python3 app.py"
sleep 2
python3 app.py &

# 3. Verify
curl -H "Cookie: user=admin" http://localhost:8080/api/rate-limiting/config
```

### 🚨 High Violation Rate (> 100/hour)

```bash
# Check for attack
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=1" | \
  jq '.violations | group_by(.scope_value) | sort_by(length) | reverse | .[0:5]'

# If legitimate traffic: increase limit
curl -X PUT http://localhost:8080/api/rate-limiting/config/default_global \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"limit_value": 2000}'

# If attack: block IP
curl -X POST http://localhost:8080/api/rate-limiting/config \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "block_'$(date +%s)'",
    "scope": "ip",
    "scope_value": "ATTACKER_IP_HERE",
    "limit_type": "requests_per_minute",
    "limit_value": 0
  }'
```

### 🚨 CPU/Memory Critical (> 95%)

```bash
# Check what's running
ps aux | head -1 && ps aux | sort -rn -k3 | head -5

# Kill runaway processes
pkill -f "process_name"

# If it's the app, restart
pkill -f "python3 app.py"
sleep 2
python3 app.py &
```

---

## Key Metrics at a Glance

### Dashboard URL
```
http://localhost:8080/rate-limiting-dashboard
```
(Requires admin login)

### Health Check
```bash
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/resource-health" | \
  jq '{cpu: .current.cpu_percent, memory: .current.memory_percent, throttling: .throttling}'
```

### Last Hour Violations
```bash
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=1" | \
  jq '.violations | length'
```

---

## Common Operations

### View All Rules
```bash
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config | jq '.configs[] | {name: .rule_name, limit: .limit_value, type: .limit_type}'
```

### Create Rule (Template)
```bash
curl -X POST http://localhost:8080/api/rate-limiting/config \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "rule_name_here",
    "scope": "ip",
    "scope_value": "ip_address_or_null",
    "limit_type": "requests_per_minute",
    "limit_value": 100,
    "resource_type": "api_call"
  }'
```

### Update Limit Value
```bash
curl -X PUT http://localhost:8080/api/rate-limiting/config/RULE_NAME \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"limit_value": NEW_VALUE}'
```

### Disable Rule
```bash
curl -X PUT http://localhost:8080/api/rate-limiting/config/RULE_NAME \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

---

## Severity Matrix

| Symptom | Severity | Action | Impact |
|---------|----------|--------|--------|
| Violations > 100/hr | 🟡 HIGH | Check attack source | Possible abuse |
| Throttling ON > 5min | 🔴 CRITICAL | Restart / Scale | Service degradation |
| CPU > 95% | 🔴 CRITICAL | Kill processes / Restart | Potential outage |
| Memory > 95% | 🔴 CRITICAL | Restart app | Memory leak risk |
| Dashboard unavailable | 🟡 HIGH | Restart app | Visibility loss |
| Database errors | 🔴 CRITICAL | Check DB file / Restore backup | Data loss risk |

---

## Response Times

- **Dashboard load:** < 2 seconds
- **Rule creation:** < 500ms
- **Rate limit check:** < 5ms
- **Violation record:** < 10ms

If slower, database may be degraded.

---

## File Locations

```
Code:       /path/to/GAIA_GO/services/rate_limiting.py
Database:   /path/to/GAIA_GO/data/prod/architect.db
Backups:    /path/to/GAIA_GO/data/prod/backups/
Logs:       /tmp/monitoring.log
```

---

## Escalation Path

1. **Yourself (5 min):** Check dashboard, restart if needed
2. **Database Admin (15 min):** Database issues, restore backups
3. **Devops (30 min):** Scaling, infrastructure changes
4. **Architect (1 hour):** Major architectural changes

---

## After Hours Contact

- 🔴 Critical: Page oncall-critical
- 🟡 High: Slack #incidents
- 🟢 Low: Next morning standup

---

**Print this page and keep at your desk!**
