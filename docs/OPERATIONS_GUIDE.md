# Operations Guide: Reputation System

Comprehensive guide for operating and maintaining the GAIA_GO Phase 3 reputation management system in production.

## Table of Contents

1. [Deployment](#deployment)
2. [Configuration](#configuration)
3. [Monitoring & Alerting](#monitoring--alerting)
4. [Troubleshooting](#troubleshooting)
5. [Database Management](#database-management)
6. [Maintenance](#maintenance)
7. [Disaster Recovery](#disaster-recovery)
8. [Performance Tuning](#performance-tuning)

## Deployment

### Automated Deployment

The reputation system includes a comprehensive deployment script:

```bash
# Deploy with default settings (development environment)
./scripts/deploy_reputation_system.sh

# Deploy to specific environment
./scripts/deploy_reputation_system.sh --environment production

# Deploy with custom database path
./scripts/deploy_reputation_system.sh --database /var/lib/gaia/architect.db

# Enable verbose output
./scripts/deploy_reputation_system.sh --verbose
```

### Deployment Steps

The deployment script automatically:
1. Checks prerequisites (Go, SQLite)
2. Backs up existing database
3. Runs database migrations
4. Validates schema
5. Compiles services
6. Runs tests
7. Generates configuration files
8. Sets up monitoring
9. Configures systemd service
10. Performs health checks

### Prerequisites

```bash
# Go 1.21+
go version

# SQLite3
sqlite3 --version

# Bash 4+
bash --version
```

### Manual Deployment

If automated deployment is not suitable:

```bash
# 1. Backup database
cp data/architect.db data/backups/architect_$(date +%s).db

# 2. Apply migrations
./scripts/manage_migrations.sh apply

# 3. Validate schema
./scripts/manage_migrations.sh validate

# 4. Compile services
go build -v ./pkg/services/rate_limiting/...

# 5. Run tests
go test -v ./pkg/services/rate_limiting/...

# 6. Start services
# (depends on your deployment method)
```

## Configuration

### Environment Variables

```bash
# Database
export DATABASE_PATH="/var/lib/gaia/architect.db"

# Deployment
export ENVIRONMENT="production"
export LOG_LEVEL="info"

# Features
export ENABLE_NOTIFICATIONS="true"
export ENABLE_ML_PREDICTIONS="true"

# Performance
export MAX_DB_CONNECTIONS="10"
export CACHE_ENABLED="true"
export CACHE_TTL_MINUTES="60"

# Monitoring
export METRICS_ENABLED="true"
export METRICS_PORT="9090"
export HEALTH_CHECK_INTERVAL="60"
```

### Configuration Files

```
config/
├── reputation_development.yml   # Development config
├── reputation_staging.yml       # Staging config
├── reputation_production.yml    # Production config
├── reputation_monitoring.yml    # Monitoring config
└── secrets/
    ├── database_password        # Database credentials
    └── api_keys.yml             # External service keys
```

### Production Configuration Template

```yaml
reputation:
  # Business Rules
  appeal_window_days: 30
  appeal_max_per_user_per_month: 10
  negotiation_timeout_hours: 72

  # Performance
  batch_size: 100
  cache_enabled: true
  cache_ttl_minutes: 60

  # Notifications
  notification_enabled: true
  notification_retry_attempts: 3
  notification_retry_interval_seconds: 300

  # ML Predictions
  ml_model_version: "v1.0"
  ml_confidence_threshold: 0.60
  ml_cache_ttl_minutes: 1440

database:
  path: "/var/lib/gaia/architect.db"
  max_connections: 10
  wal_mode: true
  journal_mode: "WAL"
  cache_size: 100000

logging:
  level: "info"
  format: "json"
  output: "syslog"

monitoring:
  metrics_enabled: true
  metrics_port: 9090
  health_check_interval_seconds: 60
  profiling_enabled: false
```

## Monitoring & Alerting

### Starting Monitoring

```bash
# Start Prometheus
prometheus --config.file=config/reputation_monitoring.yml &

# Start Alertmanager
alertmanager --config.file=config/alertmanager.yml &

# Start Grafana
docker run -d -p 3000:3000 grafana/grafana &
```

### Key Metrics to Monitor

| Metric | Target | Alert |
|--------|--------|-------|
| Appeal Submission Rate | < 100/min | > 100/min |
| Appeal Error Rate | < 1% | > 5% |
| Appeal Processing Latency | < 500ms p95 | > 1000ms p95 |
| Negotiation Duration | < 72 hours avg | > 24 hours p95 |
| ML Prediction Latency | < 100ms p99 | > 500ms p99 |
| Database Connections | < 8 active | > 0.8 of max |
| API Error Rate | < 0.1% | > 1% |

### Grafana Dashboards

Pre-configured dashboards:
- **Overview**: System-wide metrics
- **Appeals**: Appeal processing analytics
- **Negotiation**: Negotiation statistics
- **ML**: Prediction performance
- **Infrastructure**: System resources

### Alert Response

When alerts fire:

1. **Critical Severity**
   - Immediate response required
   - Page on-call engineer
   - Start incident management

2. **Warning Severity**
   - Response within 30 minutes
   - Investigate root cause
   - Plan corrective action

3. **Info Severity**
   - Monitor and document
   - Plan optimization if pattern emerges

## Troubleshooting

### Appeal Submission Failing

**Symptoms:** Appeals cannot be submitted, errors in logs

**Diagnosis:**
```bash
# Check database connectivity
sqlite3 /var/lib/gaia/architect.db "SELECT COUNT(*) FROM appeals"

# Review recent logs
tail -f /var/log/reputation/appeal_errors.log

# Check schema
./scripts/manage_migrations.sh validate
```

**Resolution:**
1. Verify database is accessible
2. Check disk space
3. Review recent migrations
4. Restart service if corrupted

### High Negotiation Latency

**Symptoms:** Negotiation messages slow, timeouts

**Diagnosis:**
```bash
# Check large threads
sqlite3 /var/lib/gaia/architect.db \
  "SELECT appeal_id, COUNT(*) FROM appeal_negotiation_messages GROUP BY appeal_id ORDER BY COUNT(*) DESC LIMIT 10"

# Monitor database performance
sqlite3 /var/lib/gaia/architect.db "PRAGMA integrity_check"
```

**Resolution:**
1. Archive old messages (> 6 months)
2. Rebuild indexes
3. Increase cache size
4. Scale database connections

### ML Prediction Timeouts

**Symptoms:** Predictions timing out, low confidence

**Diagnosis:**
```bash
# Check prediction performance
sqlite3 /var/lib/gaia/architect.db \
  "SELECT prediction_type, COUNT(*), AVG(confidence) FROM ml_predictions GROUP BY prediction_type"

# Review model performance
tail -f /var/log/reputation/ml_predictions.log
```

**Resolution:**
1. Verify model data freshness
2. Check computation resources
3. Reduce batch size
4. Consider model optimization

### Database Growing Too Fast

**Symptoms:** Disk space filling, queries slowing

**Diagnosis:**
```bash
# Check table sizes
./scripts/manage_migrations.sh stats

# Find large tables
sqlite3 /var/lib/gaia/architect.db \
  "SELECT name, COUNT(*) FROM (SELECT 'appeals' as name FROM appeals UNION ALL SELECT 'negotiation_messages' FROM appeal_negotiation_messages) GROUP BY name"
```

**Resolution:**
1. Archive old records (> 1 year)
2. Implement retention policy
3. Compress older data
4. Consider partitioning strategy

### High CPU Usage

**Symptoms:** System slow, CPU near 100%

**Diagnosis:**
```bash
# Profile CPU usage
go tool pprof http://localhost:9090/debug/pprof/profile

# Check slow queries
sqlite3 /var/lib/gaia/architect.db ".timer on"
```

**Resolution:**
1. Optimize slow queries
2. Add indexes
3. Increase cache size
4. Scale horizontally

## Database Management

### Backup & Restore

```bash
# Automatic backup before migration
./scripts/manage_migrations.sh backup

# Manual backup
cp /var/lib/gaia/architect.db /var/lib/gaia/backups/architect_$(date +%s).db

# Restore from backup
cp /var/lib/gaia/backups/architect_XXXXXX.db /var/lib/gaia/architect.db

# List backups
ls -lh /var/lib/gaia/backups/
```

### Database Optimization

```bash
# Analyze tables for optimization
sqlite3 /var/lib/gaia/architect.db "ANALYZE"

# Rebuild indexes
sqlite3 /var/lib/gaia/architect.db "REINDEX"

# Vacuum (optimize file)
sqlite3 /var/lib/gaia/architect.db "VACUUM"

# Integrity check
sqlite3 /var/lib/gaia/architect.db "PRAGMA integrity_check"
```

### Data Archival

```bash
# Archive appeals older than 1 year
sqlite3 /var/lib/gaia/architect.db << 'SQL'
CREATE TABLE appeals_archive AS
SELECT * FROM appeals
WHERE created_at < datetime('now', '-1 year')
AND status IN ('approved', 'denied', 'expired');

DELETE FROM appeals
WHERE created_at < datetime('now', '-1 year')
AND status IN ('approved', 'denied', 'expired');

ANALYZE;
VACUUM;
SQL
```

### Migration Management

```bash
# Check applied migrations
./scripts/manage_migrations.sh status

# List available migrations
./scripts/manage_migrations.sh list

# Validate schema
./scripts/manage_migrations.sh validate

# Generate report
./scripts/manage_migrations.sh report
```

## Maintenance

### Daily Tasks

```bash
# Check system health
./scripts/deploy_reputation_system.sh # runs health check

# Verify backups
ls -lh data/backups/ | head -5

# Review alerts
# (check alerting system)

# Monitor key metrics
# (check Grafana dashboards)
```

### Weekly Tasks

```bash
# Analyze database
sqlite3 data/architect.db "ANALYZE"

# Review logs for errors
grep ERROR /var/log/reputation/*.log | tail -20

# Check disk space
df -h /var/lib/gaia

# Verify backups exist and are recent
find data/backups -mtime -1
```

### Monthly Tasks

```bash
# Run full test suite
go test -v ./pkg/services/rate_limiting/...

# Update documentation
# (review and update operational docs)

# Archive old records
# (run archival script)

# Review and optimize slow queries
# (identify and optimize)

# Generate monthly report
./scripts/manage_migrations.sh report
```

### Quarterly Tasks

```bash
# Perform disaster recovery drill
# (restore from backup to test system)

# Review and update runbooks
# (update operations guides)

# Capacity planning review
# (analyze growth trends)

# Security audit
# (review access controls)
```

## Disaster Recovery

### Recovery Procedures

**Database Corruption:**
1. Stop services
2. Restore from latest backup
3. Verify schema with `validate` command
4. Run health checks
5. Restart services

**Data Loss:**
1. Restore from backup
2. Check backup integrity
3. Verify data completeness
4. Resume normal operations

**Complete System Failure:**
1. Restore from latest backup
2. Re-run migrations
3. Verify all services
4. Restore configuration
5. Re-establish connections

### Testing Recovery

```bash
# Test restore procedure
TEST_DB="/tmp/test_restore.db"
cp data/architect.db "$TEST_DB"

# Run migrations
DATABASE_PATH="$TEST_DB" ./scripts/manage_migrations.sh validate

# Verify data
sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM appeals"

# Cleanup
rm "$TEST_DB"
```

### Recovery Time Objectives (RTO)

| Scenario | RTO | RPO |
|----------|-----|-----|
| Database Corruption | 30 minutes | 5 minutes |
| Data Loss | 1 hour | 1 hour |
| Complete Failure | 4 hours | 1 hour |
| Partial Failure | 15 minutes | Real-time |

## Performance Tuning

### Database Tuning

```bash
# Optimize connection pool
# config/reputation_production.yml
database:
  max_connections: 20  # Adjust based on load

# Enable query cache
cache_enabled: true
cache_ttl_minutes: 60

# WAL mode (faster writes)
journal_mode: "WAL"
wal_autocheckpoint: 1000
```

### Indexing Strategy

Critical indexes for performance:
```sql
-- Appeal lookups by user and status
CREATE INDEX idx_appeals_user_status ON appeals(user_id, status);

-- Message thread retrieval
CREATE INDEX idx_messages_appeal_created ON appeal_negotiation_messages(appeal_id, created_at);

-- Negotiation duration calculation
CREATE INDEX idx_messages_appeal_timestamps ON appeal_negotiation_messages(appeal_id, created_at);

-- ML predictions by type
CREATE INDEX idx_predictions_type_user ON ml_predictions(prediction_type, user_id);
```

### Query Optimization

```bash
# Enable query profiling
sqlite3 /var/lib/gaia/architect.db ".timer on"

# Find slow queries
sqlite3 /var/lib/gaia/architect.db "EXPLAIN QUERY PLAN" <query>

# Optimize with indexes
# Review EXPLAIN output for full table scans
# Add indexes for frequent predicates
```

### Resource Allocation

| Component | Development | Staging | Production |
|-----------|-------------|---------|------------|
| DB Connections | 5 | 10 | 20 |
| Cache TTL | 5 min | 15 min | 60 min |
| Worker Threads | 2 | 4 | 8+ |
| Memory | 512MB | 2GB | 8GB+ |
| CPU | 2 cores | 4 cores | 8+ cores |

## Runbooks

### Restart Service

```bash
# Graceful shutdown
systemctl stop reputation-system

# Start service
systemctl start reputation-system

# Verify running
systemctl status reputation-system
```

### Scale Horizontally

```bash
# If using multiple nodes:

# 1. Deploy to new node
./scripts/deploy_reputation_system.sh --environment production

# 2. Update load balancer
# (add new node to pool)

# 3. Monitor metrics
# (verify distribution)

# 4. Gradually shift traffic
# (if needed)
```

### Emergency Escalation

For critical issues:
1. Page on-call engineer
2. Create incident in incident management system
3. Gather system state (logs, metrics)
4. Execute appropriate runbook
5. Document response and resolution

## Support & Escalation

**For operational issues:**
- Level 1: Check dashboards, review logs
- Level 2: Execute appropriate runbook
- Level 3: Page infrastructure team
- Level 4: Database administrator
- Level 5: Incident commander

**Contact Information:**
- On-Call: /etc/opsgenie/contacts
- Escalation: ops-team@example.com
- Incident Channel: #reputation-incidents

## Additional Resources

- [Deployment Scripts](../scripts/)
- [Testing Guide](TESTING_GUIDE.md)
- [Monitoring Configuration](../config/reputation_monitoring.yml)
- [Migration Management](../scripts/manage_migrations.sh)
