# Week 12: Production Cutover & Optimization Plan

## Overview

**Objective**: Deploy Go migration to production with zero downtime, gradual traffic shifting, and full monitoring.

**Duration**: Week 12 of 12-week migration
**Risk Level**: Medium (mitigated by gradual rollout)
**Rollback Plan**: Python app remains in read-only mode as backup

---

## Deployment Strategy

### Phase 1: Staging Verification (Days 1-2)

```
┌─────────────────────────────────────────┐
│  1. Deploy to Staging Environment       │
│     ├─ Build Go binaries                │
│     ├─ Setup PostgreSQL (staging)       │
│     └─ Configure connection pooling     │
├─────────────────────────────────────────┤
│  2. Run Data Migration (Dry-run)        │
│     ├─ Execute migration-cli --dry-run  │
│     ├─ Verify row counts                │
│     └─ Check checksums                  │
├─────────────────────────────────────────┤
│  3. Comprehensive Testing               │
│     ├─ All 14 analytics endpoints       │
│     ├─ All 5 app endpoints              │
│     ├─ Performance baselines            │
│     └─ Load testing (1000 req/s)        │
├─────────────────────────────────────────┤
│  4. Security Verification               │
│     ├─ Authentication tests             │
│     ├─ Authorization checks             │
│     ├─ SQL injection prevention         │
│     └─ CORS configuration               │
└─────────────────────────────────────────┘
```

### Phase 2: Production Migration (Day 3)

```
┌─────────────────────────────────────────┐
│  1. Pre-Migration Checks                │
│     ├─ Backup SQLite databases          │
│     ├─ Backup PostgreSQL                │
│     └─ Verify all systems healthy       │
├─────────────────────────────────────────┤
│  2. Execute Data Migration              │
│     ├─ Run migration-cli --mode migrate │
│     ├─ Monitor progress in real-time    │
│     ├─ Validate data integrity         │
│     └─ Generate final report            │
├─────────────────────────────────────────┤
│  3. Database Failover                   │
│     ├─ Update Python app to read-only   │
│     ├─ Verify no writes to SQLite       │
│     └─ Configure backup rotation        │
└─────────────────────────────────────────┘
```

### Phase 3: Traffic Shifting (Days 4-7)

```
Phase 3a: Canary Deployment (10% traffic)
┌──────────────────────┐
│  Production          │
├──────────────────────┤
│  Go App (10%)  ──┐   │
│                 │   │
│  Python (90%)  ◄┘   │
│                     │
│  Monitoring: 24h    │
│  Success Rate: 99%  │
└──────────────────────┘

Phase 3b: Staged Rollout (50% traffic)
┌──────────────────────┐
│  Production          │
├──────────────────────┤
│  Go App (50%)  ──┐   │
│                 ├──► Load Balancer
│  Python (50%)  ◄┘   │
│                     │
│  Monitoring: 24h    │
│  Success Rate: 99%  │
└──────────────────────┘

Phase 3c: Full Cutover (100% traffic)
┌──────────────────────┐
│  Production          │
├──────────────────────┤
│  Go App (100%) ──┐   │
│                 ├──► Load Balancer
│  Python (0%)   ◄┘   │
│                     │
│  Python: Read-only  │
│  Monitoring: 7d     │
└──────────────────────┘
```

---

## Infrastructure Requirements

### Production Environment

```yaml
Services:
  - Go Unified App (3 replicas)
  - PostgreSQL (primary + replica)
  - Redis (caching layer)
  - Nginx (load balancer)
  - Prometheus (metrics)
  - Grafana (dashboards)
  - ELK Stack (logging)

Resources per Go App Instance:
  CPU: 2 cores (minimum 1 core)
  Memory: 512MB (minimum 256MB)
  Disk: 10GB (logs + cache)

Database (PostgreSQL):
  CPU: 4 cores
  Memory: 8GB
  Disk: 100GB SSD
  Backup: Daily snapshots
```

### Network Configuration

```
Internet
   │
   ▼
┌─────────────┐
│  Nginx      │◄─── Load Balancer
└─────────────┘
   │
   ├─► Go App 1 (Port 8080)
   ├─► Go App 2 (Port 8080)
   └─► Go App 3 (Port 8080)
       │
       ▼
   ┌──────────────────┐
   │  PostgreSQL      │
   │  (Port 5432)     │
   └──────────────────┘
       │
       ▼
   ┌──────────────────┐
   │  Backup Store    │
   │  (S3/Glacier)    │
   └──────────────────┘
```

---

## Monitoring & Alerting

### Key Metrics to Track

| Metric | Threshold | Action |
|--------|-----------|--------|
| Error Rate | > 1% | Page on-call |
| Latency (p95) | > 500ms | Investigate |
| CPU Usage | > 80% | Scale up |
| Memory Usage | > 85% | Alert |
| Database Connections | > 90% pool | Scale connections |
| Disk Space | < 10% free | Cleanup/expand |

### Health Check Endpoints

```go
GET /health
Response: {
  "status": "healthy",
  "timestamp": "2026-02-20T10:00:00Z",
  "version": "1.0.0",
  "database": "connected",
  "cache": "connected",
  "checks": {
    "database_latency_ms": 5,
    "cache_latency_ms": 2,
    "disk_free_gb": 45,
    "memory_usage_percent": 35
  }
}

GET /health/readiness
Response: { "ready": true }

GET /health/liveness
Response: { "alive": true }
```

### Prometheus Metrics

```
# Application Metrics
app_requests_total{endpoint, method, status}
app_request_duration_seconds{endpoint}
app_errors_total{type, endpoint}

# Database Metrics
db_connections_active
db_query_duration_seconds{query_type}
db_pool_wait_seconds

# System Metrics
process_cpu_seconds_total
process_resident_memory_bytes
go_goroutines
```

---

## Rollback Procedures

### Automatic Rollback Triggers

```
Condition 1: Error Rate Spike
  If error_rate > 5% for 5 consecutive minutes
  → Shift 50% traffic back to Python
  → Alert on-call engineer
  → Investigate root cause

Condition 2: Database Connectivity Loss
  If db_connection_errors > 10% for 2 minutes
  → Failover to backup database
  → Alert database team
  → Check connection pool

Condition 3: High Latency
  If p95_latency > 2000ms for 10 minutes
  → Reduce Go traffic to 10%
  → Check for resource constraints
  → Optimize queries if needed

Condition 4: Memory Leak Detection
  If memory_usage growing steadily without plateau
  → Restart affected instances
  → Collect heap dumps
  → Analyze for leak source
```

### Manual Rollback Steps

```bash
# Step 1: Stop traffic to Go App
nginx_config.conf:
  upstream backend {
    server python_app:5000 max_fails=3 fail_timeout=30s;
    # server go_app:8080 down;  # Commented out
  }
  sudo systemctl reload nginx

# Step 2: Verify Python App Health
curl http://localhost:5000/health

# Step 3: Update DNS if needed
# Point production.domain.com back to python_app

# Step 4: Monitor logs
tail -f /var/log/app.log | grep ERROR

# Step 5: Investigate Go App
# Check logs, metrics, database connections

# Step 6: Restore from backup if data corruption
migration-cli --mode rollback --migration-id <id>
```

---

## Performance Optimization Targets

### Current Baseline (Go/Gin)
- Request Latency (p50): <10ms
- Request Latency (p95): <50ms
- Throughput: 25,000 req/s
- Memory per instance: 15MB idle, 100MB under load
- CPU usage: <10% at 5,000 req/s

### Optimization Areas

#### 1. Database Query Optimization
```go
// Before: N+1 query problem
users := repository.GetUsers()
for _, user := range users {
    xp := repository.GetUserXP(user.ID)  // 1000 queries!
}

// After: Batched query
users := repository.GetUsersWithXP()  // 1 query with JOIN
```

#### 2. Connection Pooling
```go
// Configured in database.go
postgres:
  max_idle_connections: 5
  max_open_connections: 20
  connection_max_lifetime: 5 minutes

sqlite (dev):
  max_idle_connections: 2
  max_open_connections: 5
  connection_max_lifetime: 10 minutes
```

#### 3. Caching Strategy
```go
// Add Redis caching for frequently accessed data
- User profiles: 1 hour TTL
- Leaderboards: 5 minute TTL
- Achievements: 24 hour TTL
- Settings: 12 hour TTL

Cache warming:
- Leaderboards: Precompute daily
- User counts: Update hourly
- Top users: Cache top 100
```

#### 4. API Response Compression
```go
// Enable GZIP compression in middleware
middleware.GzipMiddleware()
// Reduces response size by 70% for JSON
// Threshold: compress if response > 1KB
```

---

## Cutover Day Schedule

### Timeline

```
06:00 AM - Deploy to Production
  ├─ Build Go binaries
  ├─ Pull latest code
  ├─ Run tests
  └─ Deploy to canary instances

06:30 AM - Run Pre-flight Checks
  ├─ Health check endpoints
  ├─ Database connectivity
  ├─ Cache connectivity
  └─ Load balancer status

07:00 AM - Execute Data Migration
  ├─ Backup all databases
  ├─ Run migration-cli --mode migrate
  ├─ Validate data integrity
  └─ Generate migration report

07:30 AM - Enable 10% Traffic (Canary)
  ├─ Update load balancer config
  ├─ Monitor metrics closely
  ├─ Watch for errors (target: <0.1%)
  └─ Verify response times

08:00 AM - Canary Phase Complete
  ├─ Review metrics from 1 hour
  ├─ Check error logs
  ├─ Verify user complaints: 0
  └─ Proceed if all green

08:30 AM - Shift to 50% Traffic
  ├─ Update load balancer
  ├─ Continue monitoring
  ├─ Prepare for issues

09:00 AM - Notify Stakeholders
  ├─ Email update to team
  ├─ Dashboard status page update
  └─ Customer notification ready

09:30 AM - 50% Phase Complete
  ├─ Review metrics (6 hours now)
  ├─ Check database performance
  ├─ Verify no data loss

10:00 AM - Full Cutover (100% Go)
  ├─ Update load balancer
  ├─ Disable Python app writes
  ├─ Monitor intensively for 24h
  └─ Keep team on standby

7:00 PM - Monitor & Stabilize
  ├─ Check all critical endpoints
  ├─ Verify background jobs
  ├─ Monitor error rates
  └─ Adjust caching if needed

Next Day - Post-Cutover Review
  ├─ Analyze 24h metrics
  ├─ Review error logs
  ├─ Compare with baselines
  ├─ Document lessons learned
  └─ Plan optimizations
```

---

## Verification Checklist

### Pre-Production (Staging)

- [ ] All 14 analytics endpoints working
- [ ] All 5 app endpoints working
- [ ] Authentication/authorization working
- [ ] Database queries optimized
- [ ] Caching working correctly
- [ ] Load testing passed (1000 req/s)
- [ ] Error handling working
- [ ] Logging capturing all events
- [ ] Monitoring dashboards displaying data
- [ ] Alerting rules configured

### Production Canary (10%)

- [ ] Health check endpoints responding
- [ ] Error rate < 1%
- [ ] Latency p95 < 100ms
- [ ] Database connections normal
- [ ] No data corruption observed
- [ ] No user complaints received
- [ ] Cache hit rates > 80%
- [ ] Metrics being collected

### Production Staged (50%)

- [ ] Error rate still < 1%
- [ ] Database performance stable
- [ ] CPU/Memory within limits
- [ ] Response times acceptable
- [ ] No cascading failures
- [ ] Backup procedures working

### Production Full (100%)

- [ ] All metrics green
- [ ] Database fully migrated
- [ ] Python app in read-only mode
- [ ] 24-hour monitoring passed
- [ ] Team satisfied with stability
- [ ] Documentation updated

---

## Documentation Updates

### For Operations Team
- [ ] Deployment runbook
- [ ] Troubleshooting guide
- [ ] Rollback procedures
- [ ] Monitoring setup guide
- [ ] On-call playbooks

### For Development Team
- [ ] API documentation
- [ ] Configuration guide
- [ ] Performance tuning tips
- [ ] Common issues & solutions

### For Users
- [ ] Feature announcements
- [ ] Performance improvements
- [ ] Known limitations
- [ ] Support contact info

---

## Success Criteria

**Week 12 Success = All of:**

- ✅ Data migration completed with 100% data integrity
- ✅ Zero downtime during cutover
- ✅ 99%+ service availability after cutover
- ✅ Response latency < 50ms (p95)
- ✅ Error rate < 1%
- ✅ Database performing within SLA
- ✅ All features working in production
- ✅ Zero data loss
- ✅ Team confident with stability
- ✅ Documentation complete

---

## Post-Launch (Week 12+)

### Week 1 Post-Launch
- Monitor metrics continuously
- Address any performance issues
- Optimize slow queries
- Fine-tune cache TTLs
- Collect performance data

### Week 2-4 Post-Launch
- Decommission Python app
- Archive SQLite backups
- Optimize infrastructure costs
- Plan future enhancements
- Conduct retrospective

### Performance Targets Met?
- [ ] 20-30x improvement over Python (expected 25x)
- [ ] Sub-100ms latency achieved
- [ ] Throughput > 20,000 req/s
- [ ] Memory usage < 100MB per instance
- [ ] CPU efficiency improved

---

## Team Assignments

| Role | Person | Responsibilities |
|------|--------|------------------|
| **Deployment Lead** | DevOps | Orchestrate cutover |
| **Database DBA** | Database Team | Migration monitoring |
| **Backend Lead** | Lead Dev | Code validation |
| **QA Lead** | QA Team | Testing verification |
| **On-Call Eng** | TBD | Immediate incident response |
| **Comms Lead** | Product | Stakeholder updates |

---

## Risk Mitigation

### Known Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Data loss in migration | Low | Critical | Backups, dry-run, validation |
| Database performance degradation | Medium | High | Connection pool tuning, caching |
| Authentication failures | Low | Critical | Pre-prod testing, fallback |
| Load balancer misconfiguration | Low | High | Testing, rollback ready |
| Memory leak in Go app | Low | Medium | Heap dumps, monitoring |

### Contingency Plans

```
IF error_rate spikes:
  THEN reduce traffic to Go immediately
  AND investigate root cause
  AND consider rollback

IF database becomes unavailable:
  THEN failover to replica
  AND alert database team
  AND page on-call

IF users report data loss:
  THEN rollback migration immediately
  AND restore from backup
  AND investigate root cause

IF performance degrades:
  THEN analyze slow queries
  AND scale horizontally
  AND optimize indexes
```

---

## Week 12 Completion Criteria

**Production Deployment Complete When:**

1. ✅ Go app handling 100% production traffic
2. ✅ Zero downtime achieved
3. ✅ Data migration verified (100% integrity)
4. ✅ All endpoints operational in production
5. ✅ Performance within SLA
6. ✅ Monitoring and alerting active
7. ✅ Team confident in stability
8. ✅ Python app in maintenance mode
9. ✅ Backups and DR verified
10. ✅ Documentation complete

**Project Complete When:**
- 9,860+ lines of Go code in production
- 20-30x performance improvement verified
- 12-week migration fully delivered
- Zero data loss confirmed
- Team trained on new system

---

## Next Phase: Optimization & Enhancement

After successful production deployment:
- Performance tuning (caching, query optimization)
- Feature enhancements based on production data
- Cost optimization
- Additional app integrations
- Expansion to microservices if needed

