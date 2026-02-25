# Post-Deployment Monitoring & Validation Plan

## 7-Day Validation Period

**Timeline:** Days 1-7 after production deployment
**Status:** Close monitoring during critical window
**Goal:** Validate system performance and stability before normal operations

---

## Day 1: Deployment & Immediate Validation

### Morning (Deployment Window)

**Pre-Deployment (30 min before):**
```bash
# 1. Verify database backup
ls -lh data/prod/backups/architect_predeployment_*.db

# 2. Backup current config
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config > \
  config_predeployment_$(date +%Y%m%d).json

# 3. Clear logs
echo "" > /tmp/monitoring.log
```

**Deployment (apply changes):**
- Follow `PRODUCTION_DEPLOYMENT_GUIDE.md` Phase 2

**Post-Deployment (30 min after):**
```bash
# 1. Check all services running
curl http://localhost:8080/health | jq .

# 2. Verify dashboard accessible
curl -H "Cookie: user=admin" \
  http://localhost:8080/rate-limiting-dashboard | grep -q "Rate Limiting" && echo "DASHBOARD OK"

# 3. Verify API endpoints
for endpoint in config stats violations resource-health dashboard; do
  curl -H "Cookie: user=admin" \
    "http://localhost:8080/api/rate-limiting/$endpoint" | jq -r '.success // .status' && \
    echo "✓ $endpoint OK"
done

# 4. Check logs for errors
grep -i error /tmp/monitoring.log | head -10
```

### Afternoon (4-Hour Monitoring)

**Every 15 minutes:**
```bash
# Check health
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/resource-health | \
  jq '{cpu: .current.cpu_percent, memory: .current.memory_percent, throttling: .throttling}'
```

**Every hour:**
```bash
# Check statistics
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=1" | \
  jq '{requests: .stats.total_requests, violations: .stats.total_violations}'

# Check for errors in logs
tail -50 /tmp/monitoring.log | grep -i error | wc -l
```

### Evening (Manual Review)

**4 PM:**
- Review dashboard for anomalies
- Check error count in logs
- Verify no auto-throttling active
- Document any issues

**8 PM:**
- Final health check
- Confirm all systems nominal
- Send end-of-day report

**Checklist Day 1:**
- [ ] Deployment completed successfully
- [ ] All API endpoints responding
- [ ] Dashboard functional
- [ ] No critical errors in logs
- [ ] CPU < 50%, Memory < 60%
- [ ] No violations (baseline check)
- [ ] Database performing well
- [ ] Background tasks running

---

## Day 2-3: Stability Validation

### Morning (8 AM)

```bash
# Review overnight logs
tail -100 /tmp/monitoring.log | grep -E "ERROR|WARN"

# Check cumulative statistics
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=1" | jq .

# Check resource trends
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/resource-trends?hours=24" | jq .
```

### Ongoing Monitoring

**Every 2 hours:**
```bash
# Light health check
curl -s http://localhost:8080/health | jq -r '.status'
```

**Daily Summary (4 PM):**
```bash
cat > /tmp/daily_summary_$(date +%Y%m%d).txt << 'EOF'
Date: $(date)

Total Requests: $(curl -H "Cookie: user=admin" "http://localhost:8080/api/rate-limiting/stats?days=1" | jq '.stats.total_requests')
Total Violations: $(curl -H "Cookie: user=admin" "http://localhost:8080/api/rate-limiting/stats?days=1" | jq '.stats.total_violations')
Average CPU: $(ps aux | grep python | grep app.py | awk '{print $3}')%
Average Memory: $(ps aux | grep python | grep app.py | awk '{print $4}')%

Errors: $(grep -c "ERROR" /tmp/monitoring.log || echo "0")
Warnings: $(grep -c "WARN" /tmp/monitoring.log || echo "0")

Status: OPERATIONAL
EOF
cat /tmp/daily_summary_$(date +%Y%m%d).txt
```

### Alert Conditions (Days 2-3)

If any of these occur, investigate immediately:

| Condition | Action |
|-----------|--------|
| CPU > 80% for 5+ min | Check for runaway processes |
| Memory > 80% for 5+ min | Restart app if growing |
| Violations > 50/hour | Review violation source |
| Database errors | Check DB file health |
| Dashboard not loading | Restart app |
| Any ERROR in logs | Investigate and document |

---

## Day 4-5: Performance Baseline

### Establish Baselines

```bash
# Collect 48-hour metrics
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=2" > \
  metrics_baseline_day4_$(date +%Y%m%d).json

# Analyze request patterns
cat metrics_baseline_day4_*.json | jq '.stats | {
  total_requests,
  avg_hourly: (.total_requests / 48),
  total_violations,
  violation_rate: (.total_violations / .total_requests * 100)
}'

# Check resource trends
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/resource-trends?hours=48" | \
  jq '{
    avg_cpu: (. | map(.cpu_percent) | add / length),
    avg_memory: (. | map(.memory_percent) | add / length),
    max_cpu: (. | map(.cpu_percent) | max),
    max_memory: (. | map(.memory_percent) | max)
  }'
```

### Baseline Metrics

**Target Metrics (based on tests):**
- Requests per hour: 0 (initial baseline)
- Violations per hour: < 1 (normal)
- Average CPU: < 30%
- Average Memory: < 50%
- P99 Latency: < 10ms
- Error Rate: < 0.1%

### Document Findings

```bash
cat > /tmp/baseline_report_day4.md << 'EOF'
# Baseline Metrics Report - Day 4

## Request Volume
- Total requests (24h): XXX
- Avg hourly rate: XXX
- Peak hour: XXX

## Violation Metrics
- Total violations (24h): XXX
- Violation rate: XXX%
- Top violation sources: XXX

## Resource Usage
- Average CPU: XX%
- Peak CPU: XX%
- Average Memory: XX%
- Peak Memory: XX%

## System Health
- Database queries: <10ms (p99)
- Background tasks: Running
- Auto-throttle events: X
- Error count: X

## Recommendations
1. If high violation rate: Review/adjust rate limit rules
2. If high resource usage: Optimize queries or add caching
3. If errors present: Address root causes before scaling

EOF
cat /tmp/baseline_report_day4.md
```

---

## Day 6-7: Fine-Tuning & Escalation

### Performance Optimization

**If violations too low:**
```bash
# May indicate limits are too high, consider reducing

# Current rules
curl -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/config | jq '.configs[] | {name: .rule_name, limit: .limit_value}'

# Example: Reduce default limit from 1000 to 500
curl -X PUT http://localhost:8080/api/rate-limiting/config/default_global \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{"limit_value": 500}'
```

**If violations too high:**
```bash
# Analyze violation patterns
curl -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=24" | \
  jq '.violations | group_by(.scope_value) | sort_by(length) | reverse | .[0:10] | map({ip: .[0].scope_value, count: length})'

# Whitelist legitimate sources
curl -X POST http://localhost:8080/api/rate-limiting/config \
  -H "Cookie: user=admin" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "whitelist_api_partner",
    "scope": "ip",
    "scope_value": "PARTNER_IP",
    "limit_type": "requests_per_minute",
    "limit_value": 5000
  }'
```

### Validation Checklist (Day 6-7)

- [ ] System stable for 6+ days
- [ ] No critical errors
- [ ] Performance within baseline
- [ ] All tests still passing
- [ ] Dashboard accurate
- [ ] Database size normal
- [ ] Backups working
- [ ] On-call team confident
- [ ] Documentation updated
- [ ] Ready for normal operations

---

## Monitoring Dashboard Setup

### Create Custom Dashboard Script

```bash
#!/bin/bash
# daily_monitoring.sh - Run at 9 AM daily

echo "========================================"
echo "Rate Limiting Daily Monitoring Report"
echo "Date: $(date)"
echo "========================================"

# 1. System Health
echo ""
echo "SYSTEM HEALTH:"
curl -s -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/resource-health | \
  jq '{cpu: .current.cpu_percent, memory: .current.memory_percent, throttling: .throttling}'

# 2. Today's Statistics
echo ""
echo "TODAY'S STATISTICS (24h):"
curl -s -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=1" | \
  jq '.stats | {requests: .total_requests, violations: .total_violations, violation_rate: (.total_violations / .total_requests * 100)}'

# 3. Violations Summary
echo ""
echo "TOP VIOLATION SOURCES:"
curl -s -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/violations?hours=24" | \
  jq '.violations | group_by(.scope_value) | sort_by(length) | reverse | .[0:5] | map({source: .[0].scope_value, violations: length})'

# 4. Error Count
echo ""
echo "SYSTEM ERRORS:"
ERROR_COUNT=$(grep -c "ERROR" /tmp/monitoring.log || echo "0")
WARN_COUNT=$(grep -c "WARN" /tmp/monitoring.log || echo "0")
echo "Errors: $ERROR_COUNT, Warnings: $WARN_COUNT"

# 5. Status
echo ""
if [ "$ERROR_COUNT" -gt 5 ] || grep -q "CRITICAL" /tmp/monitoring.log; then
  echo "STATUS: ⚠️  ATTENTION NEEDED"
else
  echo "STATUS: ✅ HEALTHY"
fi

echo "========================================"
```

### Set Up Cron Job

```bash
# Add to crontab
crontab -e

# Add this line:
0 9 * * * bash /path/to/daily_monitoring.sh >> /tmp/monitoring_reports.log 2>&1
```

---

## Alert Configuration

### Critical Alerts (Page On-Call)

```bash
#!/bin/bash
# check_critical_alerts.sh

ERRORS=$(grep -c "ERROR" /tmp/monitoring.log)
VIOLATIONS=$(curl -s -H "Cookie: user=admin" \
  "http://localhost:8080/api/rate-limiting/stats?days=1" | \
  jq '.stats.total_violations')
CPU=$(curl -s -H "Cookie: user=admin" \
  http://localhost:8080/api/rate-limiting/resource-health | \
  jq '.current.cpu_percent')

if [ "$ERRORS" -gt 10 ]; then
  echo "🚨 CRITICAL: High error count: $ERRORS"
  # Send alert to oncall team
fi

if [ "$VIOLATIONS" -gt 100 ]; then
  echo "🚨 CRITICAL: High violation rate: $VIOLATIONS violations"
  # Send alert
fi

if (( $(echo "$CPU > 95" | bc -l) )); then
  echo "🚨 CRITICAL: CPU critical: ${CPU}%"
  # Send alert
fi
```

---

## Post-Deployment Success Criteria

### Day 1 Success
- [ ] Deployment completed without errors
- [ ] All 10 API endpoints operational
- [ ] Dashboard loading correctly
- [ ] No database errors
- [ ] No critical log errors

### Day 3 Success
- [ ] Zero unplanned restarts
- [ ] System stable (no memory leaks)
- [ ] Performance baseline established
- [ ] On-call team confident with procedures
- [ ] Documentation complete

### Day 7 Success
- [ ] 7-day uptime 100%
- [ ] Performance within expectations
- [ ] Rate limiting actively working
- [ ] No critical issues
- [ ] Ready for normal operations
- [ ] Transition to weekly monitoring

---

## Escalation Procedures

### Level 1: Self-Service (5 min)
1. Check dashboard
2. Review error logs
3. Restart if needed
4. Document issue

### Level 2: On-Call Engineer (15 min)
1. Review Level 1 findings
2. Check database health
3. Run diagnostic queries
4. Update team Slack

### Level 3: Database Admin (30 min)
1. Check database integrity
2. Review query performance
3. Optimize if needed
4. Restore from backup if necessary

### Level 4: Full Incident (60 min)
1. Initiate rollback procedures
2. Post-mortem review
3. Root cause analysis
4. Prevention plan

---

## Daily Checklist Template

```markdown
## Daily Monitoring Checklist - [DATE]

### Morning (9 AM)
- [ ] Check overnight error logs
- [ ] Review system health (CPU, Memory)
- [ ] Verify all API endpoints operational
- [ ] Check for violation spike

### Afternoon (2 PM)
- [ ] Review request volume trends
- [ ] Check database performance
- [ ] Verify background tasks running
- [ ] No throttling events

### Evening (5 PM)
- [ ] Summary statistics review
- [ ] Error count < 5
- [ ] Document any issues
- [ ] Send status update

### Status
- [ ] Healthy
- [ ] Needs Attention
- [ ] Critical Issue

### Notes
[Add any observations, changes made, or alerts]

### Next Day Priorities
- [List any follow-ups needed]
```

---

## Success Metrics

| Metric | Target | Day 1-3 | Day 4-7 |
|--------|--------|---------|---------|
| Uptime | 99.9%+ | ✓ | ✓ |
| Error Count | < 5/day | ✓ | ✓ |
| CPU Usage | < 50% avg | ✓ | ✓ |
| Memory Usage | < 60% avg | ✓ | ✓ |
| P99 Latency | < 10ms | ✓ | ✓ |
| Violation Rate | < 1%/hour | TBD | TBD |
| No Throttling | 100% | ✓ | ✓ |
| Dashboard Accuracy | 100% | ✓ | ✓ |

---

## Transition to Normal Operations (Day 8+)

### Monitoring Frequency
- **Days 1-3:** Every 15 min
- **Days 4-7:** Every 2 hours
- **Week 2+:** Daily automated checks
- **Month 2+:** Weekly reviews

### Handoff Checklist
- [ ] Support team trained
- [ ] Documentation reviewed
- [ ] Escalation procedures understood
- [ ] Dashboard bookmarked
- [ ] Alert procedures tested
- [ ] Rollback plan confirmed

---

## Resources

- **Dashboard:** http://localhost:8080/rate-limiting-dashboard
- **Quick Reference:** RATE_LIMITING_QUICK_REFERENCE.md
- **Operations Runbook:** RATE_LIMITING_OPERATIONS.md
- **Troubleshooting:** RATE_LIMITING_OPERATIONS.md#troubleshooting

---

**Document Version:** 1.0
**Created:** 2026-02-25
**Status:** Ready to implement immediately after production deployment
