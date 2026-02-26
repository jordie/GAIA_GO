# Post-Deployment Monitoring Setup Guide

## Quick Start (5 minutes)

### Step 1: Make Monitoring Script Executable
```bash
chmod +x /path/to/GAIA_GO/automated_monitoring.sh
```

### Step 2: Initialize Monitoring
```bash
./automated_monitoring.sh setup
```

### Step 3: Start Continuous Monitoring
```bash
# Run in foreground (for testing)
./automated_monitoring.sh run

# Or run in background
nohup ./automated_monitoring.sh run > /tmp/monitoring.out 2>&1 &

# Or use screen/tmux
tmux new-session -d -s monitoring './automated_monitoring.sh run'
```

### Step 4: Check Monitoring Status
```bash
./automated_monitoring.sh status

# View latest metrics
tail -20 /tmp/rate_limiting_monitoring/monitoring.log

# View alerts
tail -20 /tmp/rate_limiting_monitoring/alerts.log
```

---

## 7-Day Validation Timeline

### Day 1: Immediate Post-Deployment

**Morning:**
1. Deploy to production (follow `PRODUCTION_DEPLOYMENT_GUIDE.md`)
2. Start monitoring script
3. Check dashboard accessibility
4. Verify all API endpoints working

**Throughout Day:**
- Monitor every 15 minutes
- Check for any critical alerts
- Verify no auto-throttling
- Document baseline metrics

**Evening:**
- Generate first daily report
- Review error logs
- Send status update to team

### Days 2-3: Stability Validation

**Daily:**
- Run `./automated_monitoring.sh status` at 9 AM
- Review hourly reports
- Check for errors or warnings
- Validate system performance

**Alert Triggers:**
- CPU > 95% → Investigate processes
- Memory > 95% → Check for leaks
- Errors > 10 → Review logs
- Violations spike → Analyze sources

### Days 4-5: Baseline Establishment

**Metrics to Establish:**
- Average hourly request volume
- Typical violation rate
- Baseline CPU/memory usage
- Database query performance
- Error frequency

**Commands:**
```bash
# Export baseline metrics
cp /tmp/rate_limiting_monitoring/metrics.json \
   baseline_metrics_day4.json

# Analyze patterns
./analyze_baseline.sh baseline_metrics_day4.json
```

### Days 6-7: Fine-Tuning

**If Violations Too Low:**
- Reduce rate limit values
- Target 1-5% violation rate
- Test new rules

**If Violations Too High:**
- Review violation sources
- Whitelist legitimate traffic
- Increase limits if needed

**If Resource Usage High:**
- Optimize database queries
- Enable query caching
- Consider scaling

**Final Validation:**
- Run integration tests
- Verify all endpoints
- Test rollback procedure
- Sign off on stability

---

## Daily Monitoring Checklist

Create `daily_checklist.sh`:

```bash
#!/bin/bash

echo "=== Daily Monitoring Checklist ==="
echo "Date: $(date)"
echo ""

# 1. API Health
echo "1. API Endpoint Health:"
for endpoint in config stats violations resource-health dashboard; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Cookie: user=admin" \
        "http://localhost:8080/api/rate-limiting/$endpoint")
    if [ "$STATUS" = "200" ]; then
        echo "   ✓ $endpoint: OK"
    else
        echo "   ✗ $endpoint: FAILED (HTTP $STATUS)"
    fi
done

# 2. System Health
echo ""
echo "2. System Health:"
HEALTH=$(curl -s -H "Cookie: user=admin" \
    http://localhost:8080/api/rate-limiting/resource-health)
echo "   CPU: $(echo $HEALTH | jq '.current.cpu_percent')%"
echo "   Memory: $(echo $HEALTH | jq '.current.memory_percent')%"
echo "   Throttling: $(echo $HEALTH | jq '.throttling')"

# 3. Error Count
echo ""
echo "3. System Errors (24h):"
ERROR_COUNT=$(grep -c "ERROR" /tmp/monitoring.log 2>/dev/null || echo "0")
echo "   Total Errors: $ERROR_COUNT"

# 4. Violation Metrics
echo ""
echo "4. Rate Limiting Activity:"
STATS=$(curl -s -H "Cookie: user=admin" \
    "http://localhost:8080/api/rate-limiting/stats?days=1")
echo "   Requests (24h): $(echo $STATS | jq '.stats.total_requests')"
echo "   Violations (24h): $(echo $STATS | jq '.stats.total_violations')"

# 5. Database Status
echo ""
echo "5. Database Status:"
if [ -f "data/prod/architect.db" ]; then
    SIZE=$(du -h data/prod/architect.db | cut -f1)
    echo "   Database size: $SIZE"
    echo "   Last backup: $(ls -lt data/prod/backups/ | head -2 | tail -1 | awk '{print $6, $7, $8}')"
else
    echo "   ✗ Database not found!"
fi

# 6. Status
echo ""
if [ "$ERROR_COUNT" -gt 5 ]; then
    echo "STATUS: ⚠️  Review errors above"
else
    echo "STATUS: ✅ All systems operational"
fi

echo ""
echo "Next: Review /tmp/rate_limiting_monitoring/daily_report*.md"
```

Run daily:
```bash
chmod +x daily_checklist.sh
./daily_checklist.sh
```

---

## Monitoring Dashboards

### Web Dashboard
- **URL:** http://localhost:8080/rate-limiting-dashboard
- **Refresh:** Every 30 seconds
- **Features:** Real-time metrics, charts, violations list

### Terminal Dashboard
```bash
# Install watch (if not present)
brew install watch  # macOS
sudo apt-get install watch  # Linux

# Watch health status in real-time
watch -n 5 'curl -s -H "Cookie: user=admin" http://localhost:8080/api/rate-limiting/resource-health | jq .'

# Watch statistics
watch -n 10 'curl -s -H "Cookie: user=admin" "http://localhost:8080/api/rate-limiting/stats?days=1" | jq .stats'
```

---

## Alert Configuration

### Slack Integration (Optional)

```bash
# Set webhook URL
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Add to monitoring script
send_slack_alert() {
    local message=$1
    curl -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-Type: application/json' \
        -d "{\"text\": \"$message\"}"
}
```

### Email Alerts (Optional)

```bash
# Add to monitoring script
send_email_alert() {
    local email=$1
    local subject=$2
    local body=$3

    mail -s "$subject" "$email" << EOF
$body

Generated: $(date)
EOF
}
```

---

## Rollback During Validation Period

If critical issues found (Days 1-7), follow rollback procedure:

```bash
# 1. Stop application
pkill -f "python3 app.py"

# 2. Restore database backup
cp data/prod/backups/architect_predeployment_*.db data/prod/architect.db

# 3. Restore code to previous version
git reset --hard origin/production~1

# 4. Start application
python3 app.py &

# 5. Verify restoration
curl http://localhost:8080/health

# 6. Document incident
cat > incident_report_$(date +%Y%m%d_%H%M%S).md << 'EOF'
# Incident Report

**Time:** $(date)
**Type:** Rollback
**Reason:** [Describe issue]

## Actions Taken
1. Stopped application
2. Restored database backup
3. Reverted code
4. Restarted services

## Result
[Describe outcome]

## Root Cause
[Analyze root cause]

## Prevention
[How to prevent in future]
EOF
```

---

## Transition to Production

### Criteria for Signing Off

After 7 days of monitoring, sign off when all are true:

- [ ] Zero critical incidents
- [ ] No unplanned restarts
- [ ] System stable (no memory leaks)
- [ ] Performance within baseline
- [ ] Error rate < 1%
- [ ] Violation rate stable
- [ ] On-call team trained
- [ ] Runbooks verified
- [ ] Backups working
- [ ] Dashboard accurate

### Transition Procedure

**Day 8:**
```bash
# 1. Stop continuous monitoring
pkill -f automated_monitoring.sh

# 2. Generate final report
./automated_monitoring.sh report

# 3. Archive monitoring data
tar -czf monitoring_week1_$(date +%Y%m%d).tar.gz \
    /tmp/rate_limiting_monitoring/

# 4. Move to weekly monitoring
# (Update cron job to weekly instead of continuous)
```

**Day 8+:**
```bash
# Set up weekly monitoring (not continuous)
# Add to crontab:
# 0 9 * * 1 /path/to/daily_checklist.sh >> /tmp/weekly_monitoring.log

# Set up monthly reviews
# 0 9 1 * * /path/to/monthly_review.sh >> /tmp/monthly_review.log
```

---

## Support Resources

### For On-Call Engineers
- **Quick Reference:** RATE_LIMITING_QUICK_REFERENCE.md
- **Operations Guide:** RATE_LIMITING_OPERATIONS.md
- **Troubleshooting:** RATE_LIMITING_OPERATIONS.md#troubleshooting

### For Incident Response
- **Rollback Procedure:** PRODUCTION_DEPLOYMENT_GUIDE.md
- **Alert Thresholds:** POST_DEPLOYMENT_MONITORING.md#alert-configuration
- **Escalation Path:** RATE_LIMITING_QUICK_REFERENCE.md#escalation-path

### For Analysis
- **Baseline Report:** /tmp/rate_limiting_monitoring/daily_report_*.md
- **Metrics Export:** /tmp/rate_limiting_monitoring/metrics.json
- **Alert History:** /tmp/rate_limiting_monitoring/alerts.log

---

## Files Created

| File | Purpose |
|------|---------|
| `POST_DEPLOYMENT_MONITORING.md` | Comprehensive 7-day monitoring plan |
| `automated_monitoring.sh` | Automated metric collection and alerting |
| `daily_checklist.sh` | Daily health check script |
| `POST_DEPLOYMENT_SETUP_GUIDE.md` | This file |

---

## Next Steps After Validation

Once 7-day validation complete and signed off:

1. **Advanced Monitoring:** Set up Prometheus/Grafana integration
2. **Automated Alerts:** Configure Slack/PagerDuty integration
3. **Historical Analysis:** Archive baseline data
4. **Capacity Planning:** Use metrics to plan scaling
5. **Performance Optimization:** Fine-tune based on real-world patterns
6. **Advanced Features:** Implement ML-based anomaly detection (next phase)

---

**Status:** Ready to implement immediately after production deployment
**Last Updated:** 2026-02-25
