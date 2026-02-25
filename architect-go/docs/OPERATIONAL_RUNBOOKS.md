# Operational Runbooks

Quick reference guides for common production tasks and incident responses.

## Table of Contents

- [Incident Response](#incident-response)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)
- [Emergency Procedures](#emergency-procedures)

---

## Incident Response

### P1: API Completely Down

**Symptoms**: All health checks failing, 100% error rate

**Response SLA**: 5 minutes

**Steps**:

1. **Declare Incident**
   ```
   Slack: @incident-commander DECLARE P1 - API DOWN
   ```

2. **Page On-Call Team**
   ```bash
   curl -X POST https://events.pagerduty.com/v2/enqueue \
     -H 'Content-Type: application/json' \
     -d '{
       "routing_key": "YOUR_ROUTING_KEY",
       "event_action": "trigger",
       "payload": {
         "summary": "Production API Down - P1",
         "severity": "critical",
         "source": "Prometheus"
       }
     }'
   ```

3. **Check Services**
   ```bash
   # Check pod status
   kubectl get pods -n architect-production

   # Check events
   kubectl get events -n architect-production --sort-by='.lastTimestamp' | tail -20

   # Check logs
   kubectl logs deployment/architect-api -n architect-production --all-containers=true
   ```

4. **Immediate Recovery**
   ```bash
   # Option 1: Restart pods
   kubectl rollout restart deployment/architect-api -n architect-production

   # Option 2: Rollback deployment
   kubectl rollout undo deployment/architect-api -n architect-production

   # Option 3: Scale up
   kubectl scale deployment architect-api --replicas=15 -n architect-production
   ```

5. **Verify Recovery**
   ```bash
   # Check health
   curl -k https://api.example.com/health

   # Check error rate
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=rate(http_requests_total{status=~"5.."}[5m])'
   ```

---

### P2: High Error Rate (> 0.1%)

**Symptoms**: Error rate spike, but API responsive

**Response SLA**: 15 minutes

**Runbook**:

1. **Assess Scope**
   ```bash
   # Which endpoints affected?
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=topk(10,rate(http_requests_total{status=~"5.."}[5m])) by (endpoint)'

   # Error type breakdown
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=rate(http_requests_total{status=~"5.."}[5m]) by (status)'
   ```

2. **Check Logs**
   ```bash
   # Get recent errors
   kubectl logs deployment/architect-api -n architect-production \
     --all-containers=true -f | grep ERROR | head -50
   ```

3. **Check Dependencies**
   ```bash
   # Database
   psql $DATABASE_URL -c "SELECT 1;"

   # Redis
   redis-cli ping

   # External services
   curl -I https://external-api.example.com
   ```

4. **Scale or Restart**
   ```bash
   # Scale up
   kubectl scale deployment architect-api --replicas=20 -n architect-production

   # Or restart
   kubectl rollout restart deployment/architect-api -n architect-production
   ```

---

### P3: High Latency (P95 > 300ms)

**Symptoms**: Slow API responses, timeout errors increasing

**Response SLA**: 1 hour

**Investigation**:

1. **Database Performance**
   ```sql
   psql $DATABASE_URL

   -- Find slow queries
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   ORDER BY mean_time DESC LIMIT 10;

   -- Check locks
   SELECT * FROM pg_locks WHERE NOT granted;

   -- Active connections
   SELECT count(*) FROM pg_stat_activity;
   ```

2. **Application Metrics**
   ```bash
   # Query time distribution
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=histogram_quantile(0.99, http_request_duration_seconds)'

   # Database query time
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=histogram_quantile(0.95, db_query_duration_seconds)'
   ```

3. **Resource Usage**
   ```bash
   # CPU usage
   kubectl top pods -n architect-production

   # Memory usage
   kubectl describe nodes | grep -A 5 Allocated

   # Disk I/O
   iostat -x 1
   ```

4. **Optimization**
   - Scale up replica count
   - Analyze and optimize slow queries
   - Increase cache TTL
   - Add database indexes

---

## Common Tasks

### Scaling

**Manual Scale**
```bash
# Increase replicas
kubectl scale deployment architect-api --replicas=20 -n architect-production

# Decrease replicas
kubectl scale deployment architect-api --replicas=10 -n architect-production

# Verify scaling
kubectl rollout status deployment/architect-api -n architect-production
```

**Autoscaling**
```bash
# Check HPA status
kubectl get hpa architect-api -n architect-production

# Check metrics
kubectl get hpa architect-api -n architect-production --watch
```

### Database Operations

**Backup Database**
```bash
# Full backup
pg_dump $DATABASE_URL | gzip > backup_$(date +%s).sql.gz

# Upload to S3
aws s3 cp backup_*.sql.gz s3://backups/architect/
```

**Restore Database**
```bash
# List available backups
aws s3 ls s3://backups/architect/

# Download and restore
aws s3 cp s3://backups/architect/backup_1708172400.sql.gz .
gunzip backup_*.sql.gz
psql $DATABASE_URL < backup_*.sql
```

**View Replication Status**
```bash
# Check replication lag
psql $DATABASE_URL -c "SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;"

# On primary
psql $DATABASE_URL -c "SELECT slot_name, slot_type, active, restart_lsn FROM pg_replication_slots;"
```

### Cache Operations

**Redis Status**
```bash
# Connection info
redis-cli INFO server

# Memory usage
redis-cli INFO memory

# Key statistics
redis-cli INFO keyspace

# Flush cache (CAUTION!)
redis-cli FLUSHDB
```

**Monitor Cache**
```bash
# Real-time commands
redis-cli MONITOR

# Top keys by memory
redis-cli --bigkeys

# Find slow commands
redis-cli SLOWLOG GET 10
```

---

## Troubleshooting

### Pods Not Starting

**Symptoms**: Pods stuck in Pending, CrashLoopBackOff, or ImagePullBackOff

**Check**:
```bash
# Pod status
kubectl describe pod <pod-name> -n architect-production

# Events
kubectl get events -n architect-production --sort-by='.lastTimestamp'

# Node resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

**Fix**:
- ImagePullBackOff: Check registry credentials
- Pending: Check resource availability
- CrashLoopBackOff: Check logs (`kubectl logs <pod>`)

### Memory Leak

**Symptoms**: Memory usage growing over time, eventually OOM

**Detection**:
```bash
# Memory trend
curl http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=container_memory_usage_bytes{pod=~"architect-api.*"}'

# Memory growth rate
curl http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(container_memory_usage_bytes[10m])'
```

**Debug**:
```bash
# Get heap profile
curl http://localhost:6060/debug/pprof/heap > heap.prof
go tool pprof heap.prof

# Get goroutine info
curl http://localhost:6060/debug/pprof/goroutine > goroutines.txt
```

### Database Connection Exhaustion

**Symptoms**: "connection limit exceeded" errors

**Check**:
```bash
psql $DATABASE_URL

-- Connection count
SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;

-- Long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC;
```

**Fix**:
```bash
# Increase connection pool in app
# Or kill idle connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '10 minutes';
```

### High CPU Usage

**Symptoms**: CPU > 80%, slow responses

**Check**:
```bash
# CPU usage by pod
kubectl top pods -n architect-production --sort-by=cpu

# CPU usage by container
docker stats

# Top processes
top
```

**Fix**:
- Scale up replica count
- Optimize hot code paths
- Add caching
- Reduce query load

---

## Emergency Procedures

### Complete Service Failure

**Do This Immediately**:

1. **Declare Emergency**
   ```
   Slack: @incident-commander EMERGENCY - PRODUCTION DOWN
   Page all on-call staff
   ```

2. **Switch to Failover (if configured)**
   ```bash
   # Route traffic to backup region
   ./scripts/failover_to_backup_region.sh
   ```

3. **Manual Recovery**
   ```bash
   # Full restart
   kubectl delete deployment architect-api -n architect-production
   kubectl apply -f k8s/production/deployment.yaml

   # Monitor recovery
   kubectl rollout status deployment/architect-api -n architect-production --timeout=15m
   ```

### Data Loss Scenario

**Do This Immediately**:

1. **Stop Changes**
   ```bash
   # Prevent writes
   kubectl patch deployment architect-api -n architect-production \
     -p '{"spec":{"replicas":0}}'
   ```

2. **Preserve Evidence**
   ```bash
   # Copy database
   pg_dump $DATABASE_URL | gzip > evidence_$(date +%s).sql.gz

   # Copy logs
   kubectl logs deployment/architect-api -n architect-production \
     --all-containers=true > logs.txt
   ```

3. **Restore from Backup**
   ```bash
   # Find latest backup
   aws s3 ls s3://backups/architect/ | tail -1

   # Restore
   aws s3 cp s3://backups/architect/LATEST_BACKUP.sql.gz .
   gunzip LATEST_BACKUP.sql.gz
   psql $DATABASE_URL < LATEST_BACKUP.sql
   ```

4. **Restart Service**
   ```bash
   kubectl patch deployment architect-api -n architect-production \
     -p '{"spec":{"replicas":10}}'
   ```

### DDoS Attack

**Do This Immediately**:

1. **Activate DDoS Protection**
   ```bash
   # Enable WAF rules
   aws wafv2 associate-web-acl \
     --resource-arn $ALB_ARN \
     --web-acl-arn $WAF_ACL_ARN

   # Enable rate limiting
   kubectl patch deployment architect-api -n architect-production \
     --type json -p='[{"op":"add","path":"/spec/template/spec/containers/0/env/-","value":{"name":"RATE_LIMIT","value":"100"}}]'
   ```

2. **Monitor Traffic**
   ```bash
   # Check request patterns
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=rate(http_requests_total[1m]) by (client_ip)'

   # Identify attack IPs
   kubectl logs deployment/architect-api -n architect-production \
     | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | sort | uniq -c | sort -rn
   ```

3. **Block Traffic**
   ```bash
   # Add to WAF blocklist or security group
   aws ec2 authorize-security-group-ingress \
     --group-id $SG_ID \
     --protocol tcp \
     --port 443 \
     --cidr 0.0.0.0/0
   ```

### Communication During Incidents

**Template**:

```
🚨 INCIDENT ALERT 🚨

Service: Architect Dashboard API
Severity: P[1-4]
Status: INVESTIGATING / IDENTIFIED / RESOLVED

Affected: [Which endpoints/features]
Customers: [Estimated % of customers]
Started: [ISO timestamp]
ETA Resolution: [Expected time]

Latest Update (HH:MM UTC):
[1-2 sentence status update]

Follow updates: https://status.example.com
Questions: #incidents channel
```

---

## Escalation Matrix

```
Level 1 (Alert)
  ↓
Engineer On-Call responds within 5 minutes
  ↓
Level 2 (No response or P1/P2)
  ↓
Page Manager + Lead Engineer
  ↓
Level 3 (Still unresolved after 15 min)
  ↓
Page Director + VP Engineering
  ↓
Level 4 (P1 unresolved after 30 min)
  ↓
Declare outage, notify customers
```

---

## Contact Information

**On-Call Schedule**: https://oncall.example.com
**Incident Channel**: #incidents on Slack
**War Room**: https://meet.example.com/war-room
**Status Page**: https://status.example.com

**Key Contacts**:
- Engineering Lead: @eng-lead
- DevOps Lead: @devops-lead
- Security Lead: @security-lead
- VP Engineering: @vp-engineering

---

**Last Updated**: February 2024
**Version**: 1.0.0
