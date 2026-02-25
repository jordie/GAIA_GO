# Disaster Recovery Guide

This guide covers disaster recovery procedures for architect-go.

## Table of Contents

1. [Recovery Objectives](#recovery-objectives)
2. [Backup Strategy](#backup-strategy)
3. [Database Recovery](#database-recovery)
4. [Application Recovery](#application-recovery)
5. [Incident Response](#incident-response)
6. [Testing & Validation](#testing-validation)

## Recovery Objectives

### RTO & RPO

| Objective | Target | Description |
|-----------|--------|-------------|
| **RTO** | 15 minutes | Time to recover service |
| **RPO** | 1 hour | Maximum data loss acceptable |
| **MTBF** | >7 days | Mean time between failures |
| **MTTR** | <5 minutes | Mean time to repair |

### Critical Paths

1. Database availability (CRITICAL)
2. Application availability (CRITICAL)
3. Cache layer (IMPORTANT)
4. External integrations (OPTIONAL)

## Backup Strategy

### Database Backups

#### PostgreSQL

**Daily Backup Script**
```bash
#!/bin/bash
BACKUP_DIR="/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/architect_$DATE.sql.gz"

# Create backup
pg_dump -U postgres architect | gzip > "$BACKUP_FILE"

# Upload to S3
aws s3 cp "$BACKUP_FILE" s3://backups/architect/

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "architect_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
```

**Backup Verification**
```bash
# List backups
ls -lh /backups/postgresql/

# Test restore to temporary database
createdb architect_test
pg_restore -d architect_test < architect_backup.sql
dropdb architect_test
```

#### SQLite

**Daily Backup Script**
```bash
#!/bin/bash
SOURCE="/data/architect.db"
BACKUP_DIR="/backups/sqlite"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/architect_$DATE.db.gz"

# Create backup
gzip -c "$SOURCE" > "$BACKUP_FILE"

# Upload to S3
aws s3 cp "$BACKUP_FILE" s3://backups/architect/

# Cleanup old backups
find "$BACKUP_DIR" -name "architect_*.db.gz" -mtime +30 -delete
```

### Backup Storage

**AWS S3**
```bash
# Setup S3 bucket
aws s3 mb s3://architect-backups

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket architect-backups \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket architect-backups \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Setup lifecycle policy (archive old backups)
aws s3api put-bucket-lifecycle-configuration \
  --bucket architect-backups \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "Archive",
      "Status": "Enabled",
      "Transitions": [{
        "Days": 30,
        "StorageClass": "GLACIER"
      }],
      "Expiration": {
        "Days": 90
      }
    }]
  }'
```

### Backup Schedule

- **Frequency**: Every 6 hours
- **Retention**: 30 days in S3, 90 days in Glacier
- **Testing**: Daily restore test on staging
- **Notification**: Alert if backup fails

## Database Recovery

### PostgreSQL Recovery

#### From Recent Backup

```bash
# 1. Stop the application
kubectl scale deployment architect-go --replicas=0

# 2. Check database status
psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# 3. Stop PostgreSQL
sudo systemctl stop postgresql

# 4. Backup current database
cp -r /var/lib/postgresql/main /var/lib/postgresql/main.backup

# 5. Restore from backup
pg_restore -U postgres -d architect /backups/architect_backup.sql

# 6. Start PostgreSQL
sudo systemctl start postgresql

# 7. Verify restoration
psql -U postgres -d architect -c "SELECT COUNT(*) FROM users;"

# 8. Restart application
kubectl scale deployment architect-go --replicas=3
```

#### From Point-in-Time Recovery (PITR)

```bash
# 1. List available backups
aws s3 ls s3://architect-backups/ --recursive

# 2. Download backup
aws s3 cp s3://architect-backups/architect_20260218_120000.sql.gz ./

# 3. Restore
gunzip -c architect_backup.sql.gz | psql -U postgres architect

# 4. Verify
psql -U postgres -c "SELECT * FROM pg_stat_database WHERE datname='architect';"
```

### SQLite Recovery

```bash
# 1. Stop application
kubectl scale deployment architect-go --replicas=0

# 2. Backup current database
cp /data/architect.db /data/architect.db.corrupted

# 3. Download backup from S3
aws s3 cp s3://architect-backups/architect_20260218_120000.db.gz ./

# 4. Restore
gunzip -c architect_backup.db.gz > /data/architect.db

# 5. Verify integrity
sqlite3 /data/architect.db "PRAGMA integrity_check;"

# 6. Restart application
kubectl scale deployment architect-go --replicas=3
```

### Database Consistency Checks

```sql
-- Check for orphaned records
SELECT id, user_id FROM projects WHERE user_id NOT IN (SELECT id FROM users);

-- Check for missing references
SELECT id FROM tasks WHERE project_id NOT IN (SELECT id FROM projects);

-- Verify data integrity
PRAGMA integrity_check;

-- Check foreign key constraints
PRAGMA foreign_key_check;
```

## Application Recovery

### Container Failure

```bash
# 1. Check pod status
kubectl describe pod <pod-name>

# 2. View recent logs
kubectl logs <pod-name> --tail=100

# 3. Restart pod
kubectl delete pod <pod-name>

# 4. Monitor restart
kubectl get pod <pod-name> -w

# 5. Verify health
curl http://<pod-ip>:8080/health
```

### Deployment Failure

```bash
# 1. Check deployment status
kubectl rollout status deployment/architect-go

# 2. View recent events
kubectl describe deployment architect-go

# 3. Rollback to previous version
kubectl rollout undo deployment/architect-go

# 4. Monitor rollback
kubectl rollout status deployment/architect-go

# 5. Verify health check endpoints
kubectl port-forward svc/architect-go 8080:80
curl http://localhost:8080/health/detailed
```

### Data Corruption Recovery

```bash
# 1. Detect corruption
curl http://localhost:8080/health/detailed

# 2. Check logs for errors
kubectl logs deployment/architect-go | grep -i error

# 3. Backup corrupted data (for forensics)
kubectl cp architect-go/<pod-name>:/data ./corrupted-data

# 4. Restore from backup
kubectl exec <pod-name> -- \
  cp /backups/architect.db /data/architect.db

# 5. Verify integrity
kubectl exec <pod-name> -- \
  sqlite3 /data/architect.db "PRAGMA integrity_check;"

# 6. Monitor for errors
kubectl logs -f deployment/architect-go
```

## Incident Response

### Severity Levels

| Level | Impact | Response Time | Actions |
|-------|--------|---------------|---------|
| **P1** | Complete outage | <5 min | Immediate escalation, full incident response |
| **P2** | Major degradation | <15 min | Team engagement, status page update |
| **P3** | Minor issues | <1 hour | Investigation, monitoring |
| **P4** | Non-critical | <24 hours | Standard procedures |

### P1: Complete Outage Response

```bash
# 1. Page on-call team
# Send alert: PagerDuty, Slack, SMS

# 2. Assess situation (1 min)
kubectl get deployments
kubectl get pods
curl http://localhost:8080/health

# 3. Check logs (2 min)
kubectl logs -f deployment/architect-go

# 4. Attempt recovery:

# Option A: Restart pods
kubectl rollout restart deployment/architect-go

# Option B: Rollback deployment
kubectl rollout undo deployment/architect-go

# Option C: Restore database
# Follow database recovery procedures above

# 5. Verify recovery (5 min)
curl http://localhost:8080/health/detailed
kubectl get pods

# 6. Post-incident review
# Document root cause
# Create action items
# Update runbooks
```

### Communication

**Status Page Update**
```
Investigating: Architect-Go service degradation
- Monitoring: Database connection issues
- Impact: ~10% of users affected
- ETA: 15 minutes
```

**Incident Log**
```
[15:23] P1 alert triggered - high error rate
[15:24] Initial response - paging on-call team
[15:26] Root cause identified - database connection pool exhausted
[15:28] Action taken - scaling database connections
[15:30] Recovery verified - error rate returned to normal
[15:31] Status page updated - incident declared resolved
```

## Testing & Validation

### Backup Restoration Testing

**Weekly Restore Test**
```bash
# Create restore test job in Kubernetes
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: backup-restore-test
spec:
  template:
    spec:
      containers:
      - name: restore-test
        image: architect-go:latest
        command:
          - /bin/sh
          - -c
          - |
            # Download latest backup
            aws s3 cp s3://architect-backups/latest.sql.gz ./

            # Restore to test database
            gunzip -c latest.sql.gz | psql -U test architect_test

            # Verify
            psql -U test -d architect_test -c "SELECT COUNT(*) FROM users;"

            # Cleanup
            dropdb architect_test
      restartPolicy: Never
  backoffLimit: 3
EOF
```

### Failover Testing

```bash
# 1. Schedule maintenance window
# 2. Setup replica database
# 3. Promote replica to primary
# 4. Update connection string
# 5. Verify all services connect correctly
# 6. Monitor for errors
# 7. Failback to original
```

### Disaster Recovery Drill

**Monthly DR Drill**
```
Date: Last Friday of month
Duration: 2 hours
Scope: Full system recovery simulation

1. Backup restoration (30 min)
2. Application deployment (20 min)
3. Health verification (10 min)
4. Failover testing (30 min)
5. Post-drill review (10 min)

Success Criteria:
- All data restored correctly
- RTO < 15 minutes
- RPO < 1 hour
- Zero data loss
- All health checks pass
```

## Recovery Procedures Quick Reference

| Scenario | RTO | Procedure |
|----------|-----|-----------|
| Pod crash | 2 min | Auto-restart by Kubernetes |
| Deployment failure | 5 min | kubectl rollout undo |
| Database connection issue | 5 min | Scale connections, restart |
| Data corruption | 15 min | Restore from backup |
| Complete outage | 15 min | Full DR procedure |
| Regional failure | 30 min | Switch to backup region |

## Contacts

- **On-call**: See PagerDuty schedule
- **DBA**: database-team@example.com
- **Ops Lead**: ops-lead@example.com
- **VP Engineering**: vp-eng@example.com

## Document Control

- **Last Updated**: 2026-02-18
- **Version**: 1.0
- **Next Review**: 2026-05-18
- **Owner**: Infrastructure Team
