# Production Deployment Checklist

## Pre-Deployment (72 hours before cutover)

### Environment Preparation
- [ ] PostgreSQL production instance provisioned
- [ ] PostgreSQL backups configured (daily snapshots)
- [ ] PostgreSQL replication setup (if high availability needed)
- [ ] Redis cache cluster deployed
- [ ] Network connectivity verified
- [ ] SSL/TLS certificates installed
- [ ] DNS records updated (but not activated)
- [ ] Load balancer configured and tested
- [ ] Nginx/reverse proxy configured
- [ ] Firewall rules updated

### Code & Build
- [ ] All branches merged to main
- [ ] Latest code tagged as release candidate
- [ ] Go binaries compiled and tested
- [ ] Docker images built and pushed to registry
- [ ] All CI/CD pipelines passing
- [ ] Security scanning completed
- [ ] Code review approved
- [ ] Documentation updated

### Database Preparation
- [ ] PostgreSQL schema created
- [ ] Indexes created on all tables
- [ ] Connection pool configured (max_connections, pool_size)
- [ ] Replication configured
- [ ] Backup jobs configured
- [ ] Monitoring setup complete
- [ ] Slow query log enabled

### Monitoring & Alerting
- [ ] Prometheus configured and running
- [ ] Grafana dashboards created
- [ ] Alert rules configured
- [ ] PagerDuty/on-call setup
- [ ] Logging (ELK/CloudWatch) configured
- [ ] Log aggregation working
- [ ] Metrics collection verified
- [ ] Health check endpoints tested

### Testing
- [ ] Integration tests passed on staging
- [ ] Load testing completed (target: 5000 req/s)
- [ ] Failover testing passed
- [ ] Rollback testing passed
- [ ] Authentication/authorization verified
- [ ] CORS configuration validated
- [ ] API endpoint validation complete
- [ ] Dry-run migration successful

### Documentation
- [ ] Runbook documented and reviewed
- [ ] Rollback procedures documented
- [ ] Emergency contacts list created
- [ ] Escalation procedures defined
- [ ] Monitoring dashboard URLs documented
- [ ] Password/credential management plan in place
- [ ] Communication plan prepared

---

## 24 Hours Before Cutover

### Final Verifications
- [ ] All systems online and healthy
- [ ] Database backups recent and verified
- [ ] Network connectivity confirmed
- [ ] Load balancer health checks passing
- [ ] Staging environment mirrors production
- [ ] All team members available
- [ ] Communication channels open
- [ ] War room setup (Zoom/conference call)

### Last Minute Tests
- [ ] Database connectivity test
- [ ] Application startup test
- [ ] API endpoint test (sample requests)
- [ ] Cache connectivity test
- [ ] Logging test (verify logs are flowing)
- [ ] Metrics collection test
- [ ] Health check endpoints verified

### Notification
- [ ] Team notified of cutover time
- [ ] Stakeholders notified
- [ ] Maintenance window announced to users (if applicable)
- [ ] Support team briefed on changes
- [ ] Escalation contacts confirmed

---

## Day of Cutover

### 2 Hours Before (Pre-cutover preparation)

- [ ] War room established
- [ ] All participants online and ready
- [ ] Communication channels verified
- [ ] Monitoring dashboards open
- [ ] Logs/metrics live-streaming
- [ ] Runbook reviewed with team
- [ ] Backup systems verified
- [ ] Network connectivity double-checked

### Cutover Phase 1: Canary (10% traffic)

**Pre-deployment**:
- [ ] All systems operational
- [ ] Database replicated and healthy
- [ ] Cache warmed
- [ ] Monitoring actively watching

**Deployment**:
- [ ] Deploy Go app to 1 of 3 instances
- [ ] Verify startup logs
- [ ] Verify database connectivity
- [ ] Verify cache connectivity
- [ ] Configure load balancer for 10% traffic to Go app
- [ ] Start monitoring metrics

**Monitoring (30 min - 1 hour)**:
- [ ] Error rate < 1%
- [ ] Response latency normal
- [ ] No database errors
- [ ] No memory leaks observed
- [ ] Cache hit rate > 80%
- [ ] No authentication failures
- [ ] No user complaints in logs

**Decision point**: Proceed to 50% traffic if all metrics green

### Cutover Phase 2: Staged Rollout (50% traffic)

**Pre-deployment**:
- [ ] Phase 1 metrics reviewed and approved
- [ ] Team confident moving forward
- [ ] Monitoring focused on key metrics

**Deployment**:
- [ ] Deploy to second Go app instance
- [ ] Verify startup and connectivity
- [ ] Configure load balancer for 50/50 split
- [ ] Monitor metrics for 1-2 hours

**Monitoring**:
- [ ] Error rate < 1%
- [ ] Latency stable
- [ ] Database performance acceptable
- [ ] No memory issues
- [ ] Cache working correctly
- [ ] Session continuity verified

**Decision point**: Proceed to full cutover if all green

### Cutover Phase 3: Full Deployment (100% traffic)

**Pre-deployment**:
- [ ] 50% phase stable for 2+ hours
- [ ] No critical issues identified
- [ ] Team ready for full cutover

**Deployment**:
- [ ] Deploy to third Go app instance
- [ ] Configure load balancer: 100% to Go, 0% to Python
- [ ] Verify all Go instances healthy
- [ ] Verify Python app accessibility (for rollback)
- [ ] Configure Python app to read-only mode

**Intensive monitoring (first 24 hours)**:
- [ ] Error rate < 1% (target: < 0.1%)
- [ ] Latency p95 < 100ms
- [ ] CPU usage < 60%
- [ ] Memory stable
- [ ] Database connections normal
- [ ] No memory leaks
- [ ] No stuck requests
- [ ] Background jobs running
- [ ] Cache hit rates optimal
- [ ] Database replication lag < 100ms

### Post-Cutover (First 24 Hours)

**Team on standby**:
- [ ] On-call engineer available
- [ ] Database DBA available
- [ ] Backend lead available
- [ ] QA team monitoring

**Continuous monitoring**:
- [ ] Check metrics every 30 minutes first 2 hours
- [ ] Check metrics every 1 hour next 6 hours
- [ ] Check metrics every 4 hours next 16 hours
- [ ] Daily review after 24 hours

**Automated alerts active**:
- [ ] PagerDuty alerting on-call
- [ ] Slack notifications enabled
- [ ] Email alerts configured
- [ ] Escalation rules in place

**Common issues to watch for**:
- [ ] N+1 database queries
- [ ] Connection pool exhaustion
- [ ] Memory leaks in goroutines
- [ ] Cache invalidation issues
- [ ] Authentication token issues
- [ ] Rate limiting problems
- [ ] Timeout issues

---

## Post-Cutover (48-72 hours)

### Stability Verification
- [ ] 99%+ uptime achieved
- [ ] Error rate < 0.1%
- [ ] Latency within SLA
- [ ] Database performance good
- [ ] No customer complaints
- [ ] No data corruption
- [ ] All features working
- [ ] Performance improvement verified

### Optimization
- [ ] Review slow queries log
- [ ] Identify bottlenecks
- [ ] Optimize database indexes if needed
- [ ] Tune cache TTLs
- [ ] Adjust connection pool size
- [ ] Review log files for errors

### Cleanup
- [ ] Archive cutover logs
- [ ] Document any issues found
- [ ] Update runbooks with lessons learned
- [ ] Remove Python app write access if confident
- [ ] Schedule decommissioning of Python app
- [ ] Schedule archive of SQLite backups

---

## Rollback Triggers

**Immediate Rollback If**:
- [ ] Error rate > 5% sustained
- [ ] Database connection failures
- [ ] Data corruption detected
- [ ] Major features non-functional
- [ ] Performance degradation > 50%
- [ ] Security breach detected
- [ ] Data loss confirmed

**Graceful Rollback If**:
- [ ] Unacceptable latency (> 1 second)
- [ ] Memory leak detected
- [ ] Cache issues causing widespread problems
- [ ] Unexpected bugs in critical features

---

## Success Criteria

**Week 12 Complete When**:

1. ✅ Data migration verified (100% data integrity)
2. ✅ Zero downtime cutover achieved
3. ✅ 99%+ service availability post-cutover
4. ✅ Error rate < 1% (target 0.1%)
5. ✅ Latency p95 < 100ms (target 50ms)
6. ✅ Database performance good
7. ✅ Cache working correctly
8. ✅ All endpoints functional
9. ✅ No data loss
10. ✅ Team confident in stability
11. ✅ 20-30x performance improvement verified
12. ✅ Documentation complete
13. ✅ Post-launch monitoring active

---

## Contact Information

| Role | Person | Phone | Slack |
|------|--------|-------|-------|
| Deployment Lead | TBD | | |
| Database DBA | TBD | | |
| Backend Lead | TBD | | |
| QA Lead | TBD | | |
| On-Call | TBD | | |
| Escalation | Manager | | |

---

## War Room Setup

**Conference Bridge**: [Add details]
**Zoom**: [Add link]
**Slack Channel**: #cutover-war-room
**Log Aggregation**: [Add link to logs]
**Metrics Dashboard**: [Add Grafana link]
**Runbook**: [Add link]

---

## Notes

```
Space for cutover notes during deployment
```

---

