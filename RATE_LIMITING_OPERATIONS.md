# Rate Limiting Operations Runbook

## Quick Start

### Access the Dashboard
```
http://localhost:8080/rate-limiting-dashboard
```
Requires login with admin credentials.

### Monitor Status
```bash
# Check real-time status
curl -H "Cookie: user=admin" http://localhost:8080/api/rate-limiting/dashboard
```

---

## Standard Operations

### 1. View Current Configuration

**Dashboard Method:**
1. Navigate to `/rate-limiting-dashboard`
2. Scroll to "Active Rate Limit Rules" section
3. View all active configurations

**API Method:**
```bash
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config | jq
```

**CLI Method:**
```bash
./configure_rate_limits.sh
```

---

### 2. Create a New Rate Limit Rule

**Web Method:**
1. Use API endpoint (curl command below)
2. Changes appear in dashboard within 30 seconds

**API Method:**
```bash
curl -X POST http://localhost:8080/api/rate-limiting/config \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "strict_api_limit",
    "scope": "ip",
    "scope_value": "192.168.1.100",
    "limit_type": "requests_per_minute",
    "limit_value": 50,
    "resource_type": "api_call"
  }'
```

**Parameters:**
- `rule_name`: Unique identifier for the rule
- `scope`: `ip`, `user`, `api_key`, or `resource`
- `scope_value`: Target value (IP, user ID, API key, or NULL for default)
- `limit_type`: `requests_per_minute`, `requests_per_hour`, or `daily_quota`
- `limit_value`: Maximum allowed requests
- `resource_type`: Optional - `login`, `create`, `upload`, `api_call`, or `default`

---

### 3. Update an Existing Rule

```bash
curl -X PUT http://localhost:8080/api/rate-limiting/config/strict_api_limit \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{
    "limit_value": 100,
    "enabled": true
  }'
```

---

### 4. Disable a Rule

```bash
curl -X PUT http://localhost:8080/api/rate-limiting/config/rule_name \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

---

### 5. Check Rate Limit Statistics

**Dashboard:**
1. View "Total Requests (24h)" and "Rate Limit Violations" cards
2. View hourly trend charts

**API:**
```bash
# Last 24 hours
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=1" | jq

# Custom period
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=7" | jq
```

---

### 6. View Recent Violations

**Dashboard:**
1. Scroll to "Recent Violations" section
2. Shows last hour's violations

**API:**
```bash
# Last hour
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=1" | jq

# Custom period
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=24" | jq
```

---

### 7. Check System Health & Resource Usage

**Dashboard:**
1. View "System CPU Usage" and "System Memory Usage" cards
2. View "Throttling Status" for auto-throttle state
3. View 6-hour trend charts

**API:**
```bash
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/resource-health | jq
```

---

### 8. View Resource Trends

**API:**
```bash
# Last 6 hours
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/resource-trends?hours=6" | jq

# Custom period
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/resource-trends?hours=24" | jq
```

---

## Troubleshooting

### Issue: Legitimate Requests Being Blocked

**Diagnosis:**
1. Check dashboard for recent violations
2. Identify the client IP/user
3. Review the rate limit rule

**Solution:**
```bash
# Option 1: Increase the limit
curl -X PUT http://localhost:8080/api/rate-limiting/config/rule_name \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"limit_value": 200}'  # Increase from 100 to 200

# Option 2: Create exception for specific IP
curl -X POST http://localhost:8080/api/rate-limiting/config \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "whitelist_trusted_ip",
    "scope": "ip",
    "scope_value": "192.168.1.100",
    "limit_type": "requests_per_minute",
    "limit_value": 10000,
    "resource_type": null
  }'
```

### Issue: High Violation Rate

**Diagnosis:**
```bash
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=1" | jq '.violations | length'
```

**Possible Causes:**
1. **Legitimate Traffic Spike**: Check dashboard - if CPU/memory low, increase limits
2. **DDoS Attack**: CPU/memory spike + many unique IPs
3. **Bot Activity**: Same IP repeatedly hitting limits
4. **Misconfigured Client**: Check recent violations for patterns

**Actions:**
```bash
# Investigate violation pattern
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=1" | \
  jq '.violations | group_by(.scope_value) | map({ip: .[0].scope_value, count: length})'

# If legitimate, update rule
curl -X PUT http://localhost:8080/api/rate-limiting/config/rule_name \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"limit_value": 500}'
```

### Issue: System Auto-Throttling Active

**Diagnosis:**
1. Check dashboard - "Throttling Status" = ON
2. Check CPU/Memory cards for high values

**Solutions:**
```bash
# Option 1: Identify resource hog
# Check system processes
ps aux | sort -rn -k3 | head -5  # Top CPU processes
ps aux | sort -rn -k4 | head -5  # Top Memory processes

# Option 2: Adjust thresholds if needed (requires code modification)
# In services/resource_monitor.py:
# self.high_load_threshold = 80  # Change to 85
# self.critical_load_threshold = 95  # Change to 96

# Option 3: Scale infrastructure
# - Add more CPU/memory
# - Optimize slow queries
# - Increase database connection pool
```

### Issue: Dashboard Not Showing Data

**Diagnosis:**
```bash
# 1. Check if services are running
curl -H "Cookie: user=admin" \
  http://localhost:8080/health | jq '.services'

# 2. Check if API endpoints accessible
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config

# 3. Check logs
tail -50 /tmp/monitoring.log | grep -i error
```

**Solutions:**
1. Restart the application:
   ```bash
   pkill -f "python3 app.py"
   python3 app.py &
   ```

2. Check database:
   ```bash
   sqlite3 data/prod/architect.db ".tables" | grep rate_limit
   ```

3. Verify migrations applied:
   ```bash
   sqlite3 data/prod/architect.db \
     "SELECT COUNT(*) FROM rate_limit_configs;"
   ```

---

## Maintenance Tasks

### Daily (Automated)

- ✅ Cleanup old violations (7-day retention) - automatic via background task
- ✅ Resource metrics recording - every 60 seconds
- ✅ Database cleanup - hourly

### Weekly

**Review Statistics:**
```bash
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=7" | jq '.stats'
```

**Check Trends:**
```bash
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/resource-trends?hours=168" | jq
```

### Monthly

**Generate Report:**
```bash
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=30" | jq > report_$(date +%Y%m%d).json
```

**Review Rule Effectiveness:**
1. Open dashboard
2. Click "Download Report"
3. Analyze traffic patterns
4. Adjust rules based on patterns

**Database Maintenance:**
```bash
# Backup before maintenance
sqlite3 data/prod/architect.db ".backup data/prod/backups/architect_$(date +%Y%m%d).db"

# Vacuum to reclaim space
sqlite3 data/prod/architect.db "VACUUM;"
```

---

## Alert Conditions

Monitor these conditions and take action:

### 🔴 Critical Alerts

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Violation Rate | > 100/hour | Check logs for attack pattern |
| CPU Usage | > 95% | Investigate resource hogs |
| Memory Usage | > 95% | Check for memory leaks |
| Auto-Throttle | > 5 min continuous | Scale infrastructure |
| DB Errors | Any | Check database connectivity |

### 🟡 Warning Alerts

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Violation Rate | > 50/hour | Monitor closely |
| CPU Usage | > 80% | Watch for trends |
| Memory Usage | > 80% | Monitor for growth |
| Failed Requests | > 1% | Check error logs |

### 🟢 Healthy

| Condition | Range |
|-----------|-------|
| Violation Rate | < 10/hour |
| CPU Usage | < 70% |
| Memory Usage | < 70% |
| Throttling | OFF |
| Error Rate | < 0.1% |

---

## Performance Tuning

### Reduce Resource Usage

1. **Increase Cleanup Retention**
   - Current: 7 days for violations, 30 days for metrics
   - Modify in `services/background_tasks.py`
   - Longer retention = more disk usage

2. **Adjust Metrics Recording Interval**
   - Current: Every 60 seconds
   - Modify in `services/background_tasks.py`
   - Longer interval = less database writes

3. **Optimize Database**
   ```bash
   # Analyze query performance
   sqlite3 data/prod/architect.db ".eqp" "SELECT * FROM rate_limit_violations"

   # Check index usage
   sqlite3 data/prod/architect.db "PRAGMA index_info(idx_violations_scope);"
   ```

### Increase Throughput

1. **Database Connection Pool**
   - Modify in `db.py`
   - Increase from current 2-10 to 20-50

2. **Background Task Threads**
   - Modify in `services/background_tasks.py`
   - Use thread pool instead of single threads

3. **Caching**
   - Implement in-memory cache for rate limit rules
   - Cache TTL: 5 minutes

---

## Backup & Recovery

### Manual Backup

```bash
# Backup database
cp data/prod/architect.db data/prod/backups/architect_$(date +%Y%m%d_%H%M%S).db

# Backup configuration
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config > rate_limit_config_$(date +%Y%m%d).json
```

### Restore from Backup

```bash
# Stop application
pkill -f "python3 app.py"

# Restore database
cp data/prod/backups/architect_20240101_120000.db data/prod/architect.db

# Restart application
python3 app.py &

# Verify
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config
```

### Restore Configuration Rules

```bash
# Export current
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config > current.json

# Restore from file
jq '.configs[]' backup.json | while read -r config; do
  curl -X POST http://localhost:8080/api/rate-limiting/config \
    -H "Cookie: user=admin" \
    -H "Content-Type: application/json" \
    -d "$config"
done
```

---

## Common Scenarios

### Scenario 1: Gradual Rollout to New Client

**Goal:** Prevent overwhelming system with new client traffic

1. **Create gradual limit increase:**
   ```bash
   # Week 1: 10 req/min
   curl -X POST http://localhost:8080/api/rate-limiting/config \
     -H "Cookie: user=admin" \
     -H "Content-Type: application/json" \
     -d '{
       "rule_name": "new_client_week1",
       "scope": "api_key",
       "scope_value": "new_key_123",
       "limit_type": "requests_per_minute",
       "limit_value": 10
     }'
   ```

2. **Monitor violations daily**
3. **Increase gradually:** 10 → 50 → 100 → 500 → unlimited

### Scenario 2: Maintenance Window - Temporarily Raise Limits

```bash
# Disable all rate limiting during maintenance
curl -X PUT http://localhost:8080/api/rate-limiting/config/default_global \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# ... perform maintenance ...

# Re-enable when done
curl -X PUT http://localhost:8080/api/rate-limiting/config/default_global \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Scenario 3: Block Abusive IP

```bash
# Create blocking rule
curl -X POST http://localhost:8080/api/rate-limiting/config \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "block_abusive_ip",
    "scope": "ip",
    "scope_value": "192.168.1.99",
    "limit_type": "requests_per_minute",
    "limit_value": 0,
    "resource_type": null
  }'
```

---

## Support & Escalation

### Level 1 Support (Self-Service)
- Check dashboard
- Review violations
- Temporarily adjust limits
- Monitor auto-throttle status

### Level 2 Support (System Admin)
- Analyze traffic patterns
- Optimize database
- Adjust thresholds
- Scale infrastructure

### Level 3 Support (Database Recovery)
- Restore from backups
- Rebuild indices
- Migrate to new database
- Emergency replication

---

## References

- [Rate Limiting Implementation Guide](RATE_LIMITING_IMPLEMENTATION_GUIDE.md)
- [Final Implementation Summary](FINAL_IMPLEMENTATION_SUMMARY.md)
- [API Documentation](RATE_LIMITING_ENHANCEMENT.md#api-endpoints)

---

**Last Updated:** 2026-02-25
**Document Version:** 1.0
**Status:** Production Ready
