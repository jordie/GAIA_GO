# Troubleshooting Guide

This guide covers common issues and solutions for the Architect Dashboard.

## Quick Diagnostics

Run these commands to quickly diagnose common issues:

```bash
# Check if dashboard is running
./deploy.sh status

# Check dashboard logs
tail -f /tmp/architect_dashboard.log

# Test API health
curl http://localhost:8080/health

# Check database
sqlite3 data/architect.db ".tables"
```

## Common Issues

### Dashboard Won't Start

#### Port Already in Use

**Symptom**: Error message "Address already in use"

**Solution**:
```bash
# Find process using port 8080
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
python3 app.py --port 8081
```

#### Python Dependencies Missing

**Symptom**: ImportError or ModuleNotFoundError

**Solution**:
```bash
pip install -r requirements.txt
```

#### Database Locked

**Symptom**: "database is locked" errors

**Solution**:
```bash
# Stop all processes accessing the database
./deploy.sh stop
pkill -f "python3.*app.py"
pkill -f "python3.*task_worker"

# Restart
./deploy.sh
```

#### Permission Denied

**Symptom**: Cannot write to data directory

**Solution**:
```bash
# Fix permissions
chmod -R 755 data/
chown -R $USER:$USER data/
```

### Authentication Issues

#### Can't Login

**Symptom**: Login fails with correct credentials

**Check**:
```bash
# Verify credentials
echo $ARCHITECT_USER
echo $ARCHITECT_PASSWORD

# Default credentials:
# Username: architect
# Password: peace5
```

**Solution**: Reset credentials via environment:
```bash
export ARCHITECT_USER="admin"
export ARCHITECT_PASSWORD="newpassword"
./deploy.sh restart
```

#### Session Expired

**Symptom**: Redirected to login unexpectedly

**Solution**: Sessions expire after inactivity. Increase session timeout:
```python
# In app.py, modify:
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
```

### Node Connection Issues

#### Node Not Appearing in Dashboard

**Symptom**: Node agent running but not visible in UI

**Diagnose**:
```bash
# On worker node, check agent status
python3 distributed/node_agent.py --status

# Check if dashboard is reachable
curl http://dashboard-ip:8080/health

# Check agent logs
cat /tmp/architect_node_agent.log
```

**Solutions**:
1. Verify network connectivity between nodes
2. Check firewall rules allow port 8080
3. Ensure correct dashboard URL in agent config

#### Node Shows as Offline

**Symptom**: Node appears but status is "offline"

**Causes**:
- Node agent not running
- Heartbeat timeout exceeded (default 120s)
- Network connectivity issues

**Solution**:
```bash
# Restart node agent
python3 distributed/node_agent.py --stop
python3 distributed/node_agent.py --daemon

# Check heartbeat is being sent
tail -f /tmp/architect_node_agent.log
```

#### SSH Connection Failures

**Symptom**: Cannot execute commands on remote nodes

**Diagnose**:
```bash
# Test SSH manually
ssh -v user@node-hostname

# Check SSH pool stats
curl http://localhost:8080/api/ssh/pool/stats
```

**Solutions**:
1. Set up SSH key authentication
2. Check SSH service running on target node
3. Verify hostname resolves correctly
4. Clean up stale connections:
   ```bash
   curl -X POST http://localhost:8080/api/ssh/pool/cleanup
   ```

### Task Queue Issues

#### Tasks Stuck in Pending

**Symptom**: Tasks created but never processed

**Diagnose**:
```bash
# Check worker status
python3 workers/task_worker.py --status

# List pending tasks
curl http://localhost:8080/api/tasks?status=pending
```

**Solutions**:
1. Start/restart task worker:
   ```bash
   python3 workers/task_worker.py --daemon
   ```
2. Check worker can claim tasks:
   ```bash
   curl -X POST http://localhost:8080/api/tasks/claim \
     -H "Content-Type: application/json" \
     -d '{"worker_id": "test", "task_types": ["shell"]}'
   ```

#### Task Worker Not Connecting

**Symptom**: Worker running but not claiming tasks

**Solutions**:
1. Check worker registration:
   ```bash
   curl http://localhost:8080/api/workers
   ```
2. Verify task types match:
   - Worker claims specific types (shell, python, git, etc.)
   - Ensure task type matches worker capabilities

### tmux Issues

#### Sessions Not Showing

**Symptom**: tmux sessions exist but not visible in dashboard

**Solution**:
```bash
# Refresh sessions manually
curl -X POST http://localhost:8080/api/tmux/sessions/refresh

# Check tmux is running
tmux list-sessions
```

#### Cannot Send Commands

**Symptom**: Commands not reaching tmux session

**Diagnose**:
```bash
# Test tmux send-keys directly
tmux send-keys -t session_name "echo test" Enter
```

**Solutions**:
1. Verify session name matches exactly
2. Check session isn't in a blocking state
3. Restart the tmux session if corrupted

### Database Issues

#### Corrupted Database

**Symptom**: SQL errors, missing tables

**Solution**:
```bash
# Backup current database
cp data/architect.db data/architect.db.corrupted

# Check integrity
sqlite3 data/architect.db "PRAGMA integrity_check"

# If corrupted, restore from backup
cp data/architect.db.backup data/architect.db

# Or reinitialize (loses data)
rm data/architect.db
./deploy.sh
```

#### Missing Columns

**Symptom**: "no such column" errors

**Cause**: Schema migration didn't run

**Solution**: The app auto-migrates on startup. If still failing:
```bash
# Stop the app
./deploy.sh stop

# Check current schema
sqlite3 data/architect.db ".schema"

# Restart to trigger migrations
./deploy.sh
```

#### Database Too Large

**Symptom**: Slow queries, large file size

**Solutions**:
1. Vacuum the database:
   ```bash
   sqlite3 data/architect.db "VACUUM"
   ```
2. Archive old data:
   ```sql
   DELETE FROM activity_log WHERE created_at < datetime('now', '-30 days');
   DELETE FROM errors WHERE status = 'resolved' AND updated_at < datetime('now', '-7 days');
   ```

### Performance Issues

#### Slow Dashboard Loading

**Diagnose**:
```bash
# Check server response time
time curl http://localhost:8080/api/stats

# Check database size
ls -lh data/architect.db
```

**Solutions**:
1. Enable caching headers
2. Archive old data
3. Add database indexes:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_tasks_status ON task_queue(status);
   CREATE INDEX IF NOT EXISTS idx_errors_status ON errors(status);
   ```

#### High Memory Usage

**Diagnose**:
```bash
# Check Python process memory
ps aux | grep "python3.*app.py"

# Monitor over time
watch -n 5 'ps aux | grep "python3.*app.py"'
```

**Solutions**:
1. Restart the dashboard periodically
2. Limit in-memory caching
3. Use pagination for large result sets

### Error Aggregation Issues

#### Errors Not Appearing

**Symptom**: Errors logged but not visible

**Check**:
```bash
# Log a test error
curl -X POST http://localhost:8080/api/errors \
  -H "Content-Type: application/json" \
  -d '{"error_type": "test", "message": "Test error"}'

# Query errors
curl http://localhost:8080/api/errors
```

**Solutions**:
1. Check filter settings in UI
2. Verify error has required fields
3. Check database for entry:
   ```sql
   SELECT * FROM errors ORDER BY id DESC LIMIT 5;
   ```

#### Error Count Not Incrementing

**Symptom**: Same error shows count=1 even with multiple occurrences

**Cause**: Error deduplication uses (error_type, message, source)

**Solution**: This is expected behavior. Check occurrence_count:
```sql
SELECT error_type, message, occurrence_count FROM errors;
```

### Health Monitoring Issues

#### Alerts Not Triggering

**Symptom**: Metrics exceed threshold but no alerts

**Check**:
1. Verify thresholds are set:
   ```bash
   curl http://localhost:8080/api/nodes/1/health
   ```
2. Check heartbeat is sending metrics:
   ```bash
   # On worker node
   tail -f /tmp/architect_node_agent.log
   ```

#### False Positives

**Symptom**: Alerts triggering incorrectly

**Solutions**:
1. Adjust thresholds:
   ```bash
   export ARCHITECT_CPU_WARNING=90
   export ARCHITECT_CPU_CRITICAL=98
   ```
2. Increase heartbeat frequency to smooth spikes

## Log Locations

| Component | Log Location |
|-----------|--------------|
| Dashboard | /tmp/architect_dashboard.log |
| Node Agent | /tmp/architect_node_agent.log |
| Task Worker | /tmp/architect_task_worker.log |
| Assigner | /tmp/architect_assigner.log |

## Debug Mode

Enable debug logging:

```bash
# Via environment
export FLASK_DEBUG=1
export PYTHONUNBUFFERED=1

# Or in app.py
app.config['DEBUG'] = True
```

## Getting Help

### Collect Diagnostics

```bash
#!/bin/bash
# Create diagnostic bundle
mkdir -p /tmp/architect_diag
./deploy.sh status > /tmp/architect_diag/status.txt
curl http://localhost:8080/health > /tmp/architect_diag/health.json
curl http://localhost:8080/api/stats > /tmp/architect_diag/stats.json
curl http://localhost:8080/api/nodes > /tmp/architect_diag/nodes.json
cp /tmp/architect_dashboard.log /tmp/architect_diag/
sqlite3 data/architect.db ".tables" > /tmp/architect_diag/tables.txt
tar czf architect_diagnostics.tar.gz /tmp/architect_diag
```

### Check API Endpoints

```bash
# List all available endpoints
curl http://localhost:8080/api/docs | jq '.endpoints | length'

# Get endpoint documentation
curl http://localhost:8080/api/docs/categories
```

## Recovery Procedures

### Full Reset

**Warning**: This deletes all data!

```bash
./deploy.sh stop
rm -rf data/architect.db
rm -rf data/assigner/assigner.db
./deploy.sh
```

### Restore from Backup

```bash
./deploy.sh stop
cp data/architect.db data/architect.db.broken
cp /backup/architect.db.$(date +%Y%m%d) data/architect.db
./deploy.sh
```

### Migrate to New Server

```bash
# On old server
./deploy.sh stop
tar czf architect_backup.tar.gz data/ ssl/ .env

# On new server
tar xzf architect_backup.tar.gz
pip install -r requirements.txt
./deploy.sh
```
