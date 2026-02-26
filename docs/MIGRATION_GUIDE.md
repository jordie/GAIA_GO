# GAIA_GO Migration Guide

Complete guide for migrating from GAIA_HOME (Python) to GAIA_GO (Go), including session migration, dual-write synchronization, and gradual traffic rollout.

## Table of Contents

1. [Overview](#overview)
2. [Pre-Migration Checklist](#pre-migration-checklist)
3. [Phase 1: Dual-Write Setup](#phase-1-dual-write-setup)
4. [Phase 2: Gradual Rollout](#phase-2-gradual-rollout)
5. [Phase 3: Monitoring & Validation](#phase-3-monitoring--validation)
6. [Phase 4: Cutover](#phase-4-cutover)
7. [Rollback Procedures](#rollback-procedures)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The migration from GAIA_HOME to GAIA_GO uses a **phased approach** to minimize risk:

```
Timeline: 6-8 weeks total

Week 1-2: Setup & Validation
├─ Deploy GAIA_GO infrastructure
├─ Validate session data
└─ Enable dual-write mode

Week 3-4: Gradual Rollout
├─ Route 10% of traffic to GAIA_GO
├─ Monitor for issues
├─ Scale to 50%
└─ Prepare for full cutover

Week 5-6: Monitoring
├─ Run with 50% traffic
├─ Validate all functionality
├─ Test disaster recovery
└─ Plan final cutover

Week 7: Cutover
├─ Route 100% to GAIA_GO
├─ Monitor closely
└─ Keep GAIA_HOME as fallback

Week 8: Deprecation
├─ Archive GAIA_HOME
├─ Document lessons learned
└─ Plan decommissioning
```

---

## Pre-Migration Checklist

Before starting migration, verify:

- [ ] GAIA_GO production infrastructure deployed
- [ ] Database migrations applied
- [ ] Raft cluster healthy (3+ nodes)
- [ ] Backup and recovery tested
- [ ] Session validator tests passing
- [ ] Conflict handler configured
- [ ] Team trained on procedures
- [ ] Communication plan ready
- [ ] Rollback procedures documented
- [ ] Monitoring and alerting active

---

## Phase 1: Dual-Write Setup

### Step 1: Enable Dual-Write Mode

```bash
# Set environment variable to enable dual-write
export DUAL_WRITE_ENABLED=true
export DUAL_WRITE_MODE=go_leads  # GAIA_GO first, then GAIA_HOME

# Deploy configuration
./deploy.sh docker-compose staging
```

### Step 2: Validate Session Migration

```bash
# Test migration with a sample session
curl -X POST http://localhost:8080/api/migration/test \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-001",
    "validate": true
  }'

# Expected response:
{
  "status": "validated",
  "session_id": "test-session-001",
  "python_version": {...},
  "go_version": {...},
  "conflicts": [],
  "validated": true
}
```

### Step 3: Migrate Active Sessions

```bash
# List active sessions in GAIA_HOME
curl -s http://gaia_home:5000/api/sessions | jq '.[] | .id' > /tmp/sessions.txt

# Migrate sessions
for session_id in $(cat /tmp/sessions.txt); do
  curl -X POST http://localhost:8080/api/migration/session \
    -H "Content-Type: application/json" \
    -d "{\"session_id\": \"$session_id\"}"
done

# Verify migrations
curl http://localhost:8080/api/migration/metrics | jq .
```

### Step 4: Enable Dual-Write for All Operations

Once validation passes, enable dual-write for all new sessions:

```bash
# All new sessions will be written to both systems
# GAIA_GO_FIRST strategy: writes must succeed in GAIA_GO, then Python
export DUAL_WRITE_MODE=go_leads
```

---

## Phase 2: Gradual Rollout

### Step 1: Route 10% to GAIA_GO

```bash
# Configure load balancer to send 10% traffic to GAIA_GO
curl -X POST http://localhost/api/traffic-split \
  -H "Content-Type: application/json" \
  -d '{
    "go_percentage": 10,
    "python_percentage": 90
  }'

# Verify split
curl http://localhost/api/traffic-split | jq .
```

### Step 2: Monitor Metrics

```bash
# Check migration progress
watch -n 5 'curl http://localhost:8080/api/migration/metrics | jq .'

# Check dual-write metrics
watch -n 5 'curl http://localhost:8080/api/migration/dual-write-metrics | jq .'

# Key metrics to watch:
# - total_writes: Total dual-write operations
# - successful_writes: Both systems succeeded
# - partial_writes: One system succeeded
# - failed_writes: Both systems failed
# - conflict_resolved: Resolved conflicts
```

### Step 3: Scale to 50% Traffic

After 1-2 days at 10%, scale up:

```bash
# Increase to 50%
curl -X POST http://localhost/api/traffic-split \
  -d '{"go_percentage": 50, "python_percentage": 50}'

# Monitor for 24 hours
# Check error rates, latency, resource usage
```

### Step 4: Final Validation

```bash
# Run comprehensive test suite
./scripts/migration_tests.sh

# Test scenarios:
# - Create sessions (dual-write)
# - Update sessions (sync)
# - Delete sessions (cascading)
# - Handle failures (rollback)
# - Concurrent operations (race conditions)
```

---

## Phase 3: Monitoring & Validation

### Health Checks

```bash
# System health
curl http://localhost:8080/health | jq .

# Migration status
curl http://localhost:8080/api/migration/status | jq .

# Dual-write health
curl http://localhost:8080/api/migration/dual-write-health | jq .

# Raft cluster
curl http://localhost:8080/api/cluster/health | jq .
```

### Error Tracking

```bash
# Check error logs
docker logs gaia_node_1 | grep ERROR | tail -20

# Monitor error rate
curl http://localhost:8080/metrics | grep "gaia_errors_total"

# Alert thresholds:
# - Error rate > 1%: Investigate
# - Error rate > 5%: Pause migration
# - Sync lag > 100ms: Investigate
```

### Performance Metrics

```bash
# Latency comparison
curl http://localhost:8080/api/migration/metrics | jq '.latencies'

# Expected:
{
  "go_latency_p95_ms": 15,
  "python_latency_p95_ms": 20,
  "dual_write_latency_p95_ms": 25
}

# If GO latency >> Python: Investigate bottlenecks
```

---

## Phase 4: Cutover

### Step 1: Final Preparation

```bash
# Verify all systems ready
./scripts/pre_cutover_checklist.sh

# Runs:
# - Database consistency check
# - Raft cluster quorum verification
# - Backup verification
# - DNS propagation check
```

### Step 2: Go Live

```bash
# Announce maintenance window (if needed)
# 1. Set GO traffic to 100%
curl -X POST http://localhost/api/traffic-split \
  -d '{"go_percentage": 100, "python_percentage": 0}'

# 2. Monitor closely (30 minutes minimum)
watch -n 1 'curl http://localhost:8080/health | jq .status'

# 3. Disable dual-write (no longer needed)
export DUAL_WRITE_ENABLED=false

# 4. Keep GAIA_HOME running as fallback for 24 hours
# If critical issues arise, can quickly revert
```

### Step 3: Post-Cutover Monitoring

```bash
# Intensive monitoring for 24 hours
watch -n 10 'curl http://localhost:8080/api/migration/status | jq .'

# Key checks:
# - All endpoints responding
# - Error rate stable
# - Latency acceptable
# - Database replication healthy
# - Backups running

# If any critical issues:
# → Execute rollback procedure
# → Notify stakeholders
# → Investigation begins
```

---

## Rollback Procedures

### Rollback to GAIA_HOME (Quick)

**When**: Critical issues in GAIA_GO discovered during cutover

**Duration**: ~5 minutes (no data loss expected)

```bash
# 1. Redirect traffic back to GAIA_HOME
curl -X POST http://load_balancer/api/traffic-split \
  -d '{"go_percentage": 0, "python_percentage": 100}'

# 2. Verify GAIA_HOME is responding
curl http://gaia_home:5000/health | jq .

# 3. Disable dual-write
export DUAL_WRITE_ENABLED=false

# 4. Notify stakeholders
# "Temporary issue detected, reverted to GAIA_HOME for stability"

# 5. Investigation begins in separate ticket
```

### Recovery Process

After rollback:

```bash
# 1. Identify root cause
# - Check error logs
# - Review metrics during incident
# - Analyze database state

# 2. Fix issue in GAIA_GO
# - Code fix
# - Configuration change
# - Database migration

# 3. Re-enable dual-write
export DUAL_WRITE_ENABLED=true

# 4. Validate fixes
./scripts/migration_tests.sh

# 5. Restart migration from Phase 2, Step 1
```

### Complete Rollback (Rare)

**When**: Unrecoverable data corruption or catastrophic failure

**Duration**: 2-4 hours (may lose recent writes)

```bash
# 1. Stop all GAIA_GO nodes
for node in gaia_node_1 gaia_node_2 gaia_node_3; do
  ssh $node "systemctl stop gaia_go"
done

# 2. Restore PostgreSQL from backup
./scripts/restore_database.sh /backups/gaia_go_backup_latest.dump

# 3. Verify data integrity
psql -c "SELECT COUNT(*) FROM claude_sessions;"

# 4. Route all traffic to GAIA_HOME
curl -X POST http://load_balancer/api/traffic-split \
  -d '{"go_percentage": 0, "python_percentage": 100}'

# 5. Disable dual-write
export DUAL_WRITE_ENABLED=false

# 6. Post-mortem investigation
# - Data loss assessment
# - Cause analysis
# - Prevention measures
```

---

## Troubleshooting

### Symptom: High Dual-Write Error Rate

```bash
# Check error details
curl http://localhost:8080/api/migration/errors?limit=50 | jq '.errors[0:5]'

# Common causes:
# 1. GAIA_HOME service down
#    Solution: Restart GAIA_HOME, check logs
#
# 2. Network connectivity issue
#    Solution: Check firewall rules, DNS resolution
#
# 3. Schema mismatch
#    Solution: Run migrations on both systems
#
# 4. Concurrency issues
#    Solution: Increase dual-write timeout
```

### Symptom: Session Conflicts

```bash
# View conflict details
curl http://localhost:8080/api/migration/conflicts?limit=10 | jq .

# Example conflict:
{
  "session_id": "session-123",
  "field": "status",
  "python_value": "active",
  "go_value": "idle",
  "resolved": false
}

# Resolution strategies:
# 1. Go_Leads: Use GAIA_GO value (configured)
# 2. Manual: Inspect and decide
# 3. Sync: Force sync from source of truth
```

### Symptom: Sync Lag Increasing

```bash
# Check replication status
curl http://localhost:8080/api/migration/sync-lag | jq .

# If lag > 100ms:
# 1. Check database load
#    pg_stat_statements to find slow queries
#
# 2. Reduce write rate
#    Set traffic back to 50% or lower
#
# 3. Scale database
#    Add read replicas, increase connection pool
```

### Symptom: False Positives in Validation

```bash
# Review validation errors
curl http://localhost:8080/api/migration/validation-errors | jq .

# Common false positives:
# - Timestamp rounding (Python vs Go)
# - Enum value representation
# - Metadata field ordering

# Adjust validator if needed
# Edit pkg/migration/state_validator.go

# Re-validate
./scripts/migration_tests.sh --revalidate
```

---

## Success Criteria

### Phase 1 Complete When:
- [ ] All sessions migrated without errors
- [ ] Dual-write metrics show >99% success
- [ ] No data corruption detected
- [ ] Team confidence high

### Phase 2 Complete When:
- [ ] 50% traffic on GAIA_GO for 48+ hours
- [ ] Error rate ≤ 0.5%
- [ ] Latency acceptable
- [ ] All functionality tested
- [ ] Rollback procedure validated

### Phase 3 Complete When:
- [ ] 7+ days stable at 50% traffic
- [ ] Zero unresolved issues
- [ ] Disaster recovery tested
- [ ] Team ready for cutover

### Phase 4 Complete When:
- [ ] 24+ hours at 100% without issues
- [ ] GAIA_HOME can be deprecated
- [ ] Users notified
- [ ] Monitoring established

---

## Post-Migration

### Day 1: Intensive Monitoring
- [ ] Hourly health checks
- [ ] Error rate tracking
- [ ] Performance metrics
- [ ] User feedback

### Week 1: Validation
- [ ] 7-day stability verification
- [ ] Load testing
- [ ] Chaos testing
- [ ] Backup restoration test

### Month 1: Deprecation Planning
- [ ] GAIA_HOME decommission date set
- [ ] Final backups taken
- [ ] Codebase archived
- [ ] Team transition plan

---

## Documentation Generated During Migration

1. **Lessons Learned**: What went well, what to improve
2. **Runbooks**: How to operate GAIA_GO
3. **Disaster Recovery Procedures**: How to recover
4. **Training Materials**: For new teams

---

## Support & Questions

- **Migration Status**: `curl http://localhost:8080/api/migration/status`
- **Error Reports**: `curl http://localhost:8080/api/migration/errors`
- **Metrics Dashboard**: http://localhost:3000 (Grafana)
- **Logs**: `docker logs gaia_node_1 | grep migration`

---

## References

- [DEPLOYMENT.md](./DEPLOYMENT.md) - Infrastructure deployment
- [CLUSTER_OPERATIONS.md](./CLUSTER_OPERATIONS.md) - Cluster management
- [DATABASE_OPTIMIZATION.md](./DATABASE_OPTIMIZATION.md) - Database optimization
