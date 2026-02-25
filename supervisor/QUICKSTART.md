# Process Supervisor - Quick Start Guide

## 5-Minute Setup

### Step 1: Verify Installation

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Run verification script
./supervisor/verify.sh
```

This checks:
- All files are present
- Dependencies are installed
- Configuration is valid
- Database is accessible

### Step 2: Run Setup

```bash
# Automatic setup (recommended)
./supervisor/setup.sh --auto
```

This will:
1. Install missing dependencies
2. Create required directories
3. Initialize database tables
4. Start supervisor daemon
5. Show service status

### Step 3: Verify Running

```bash
# Check supervisor status
./supervisor/supervisorctl.py status

# Expected output:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📊 Supervisor Status
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ✅ Supervisor running
#
# Service              State        PID      Uptime       CPU%     Mem(MB)    Restarts
# ----------------------------------------------------------------------------------
# architect-prod       ✅ running    12345    5m          2.5%     128.3      0
# architect-qa         ✅ running    12346    5m          1.8%     95.2       0
# reading-app          ✅ running    12347    5m          3.2%     156.7      0
```

### Step 4: View Logs

```bash
# Supervisor log
tail -f /tmp/process_supervisor.log

# Service log
./supervisor/supervisorctl.py logs architect-prod -f
```

## Common Commands

### Service Management

```bash
# Show all services
./supervisor/supervisorctl.py status

# Show specific service
./supervisor/supervisorctl.py status architect-prod

# Start service
./supervisor/supervisorctl.py start architect-prod

# Stop service
./supervisor/supervisorctl.py stop architect-prod

# Restart service
./supervisor/supervisorctl.py restart architect-prod
```

### Monitoring

```bash
# Show summary
./supervisor/supervisorctl.py summary

# Show health status
./supervisor/supervisorctl.py health

# Show events
./supervisor/supervisorctl.py events

# Show events for specific service
./supervisor/supervisorctl.py events architect-prod
```

### Logs

```bash
# View logs
./supervisor/supervisorctl.py logs architect-prod

# Follow logs (like tail -f)
./supervisor/supervisorctl.py logs architect-prod -f

# Last 100 lines
./supervisor/supervisorctl.py logs architect-prod -n 100
```

### Supervisor Control

```bash
# Stop supervisor
python3 ./supervisor/process_supervisor.py --stop

# Start supervisor
./supervisor/setup.sh --auto

# Check supervisor status
python3 ./supervisor/process_supervisor.py --status
```

## Testing Auto-Restart

### Test 1: Kill a Process

```bash
# Find PID of a supervised service
./supervisor/supervisorctl.py status

# Kill the process (supervisor will auto-restart)
kill -9 <PID>

# Wait 30 seconds and check status
sleep 30
./supervisor/supervisorctl.py status

# You should see the service running again with restart count = 1
```

### Test 2: Simulate Service Crash

```bash
# View events to see restart
./supervisor/supervisorctl.py events

# Check restart count increased
./supervisor/supervisorctl.py status
```

## Configuration

### Enable Pharma Service

Edit `supervisor/supervisor_config.json`:

```json
{
  "pharma": {
    "enabled": true,  // Change from false
    ...
  }
}
```

Then restart supervisor:

```bash
python3 ./supervisor/process_supervisor.py --stop
sleep 2
./supervisor/setup.sh --auto
```

### Adjust Check Interval

Edit `supervisor/supervisor_config.json`:

```json
{
  "global": {
    "check_interval": 15,  // Check every 15 seconds (default: 30)
    ...
  }
}
```

## Dashboard Integration

### Add API Routes

Edit `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/app.py`:

```python
# Near the top with other imports
from supervisor.api_routes import register_supervisor_routes

# After creating Flask app
app = Flask(__name__)
# ... existing configuration ...

# Add supervisor routes
register_supervisor_routes(app)
```

Restart dashboard:

```bash
./deploy.sh stop
./deploy.sh --daemon
```

### Test API

```bash
# Get status
curl http://localhost:8080/api/supervisor/status | jq

# Get summary
curl http://localhost:8080/api/supervisor/summary | jq

# Get events
curl http://localhost:8080/api/supervisor/events | jq
```

## Troubleshooting

### Supervisor won't start

```bash
# Check for errors
cat /tmp/process_supervisor.log

# Check for stale PID
rm -f /tmp/process_supervisor.pid

# Try starting in foreground to see errors
python3 ./supervisor/process_supervisor.py
```

### Service won't start

```bash
# Check service log
tail -f /tmp/supervisor_logs/<service-id>.log

# Check supervisor log
tail -f /tmp/process_supervisor.log

# Try starting service manually
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
python3 app.py --port 8080
```

### Dependencies missing

```bash
# Install all dependencies
pip3 install psutil requests flask

# Verify
python3 -c "import psutil, requests, flask; print('OK')"
```

## Health Checks

### Verify Health Endpoints

```bash
# Test dashboard health
curl http://localhost:8080/health

# Test reading app health
curl http://localhost:5063/health

# Test architect QA health
curl http://localhost:8081/health
```

### Add Health Endpoint to Service

If your service doesn't have a health endpoint, add one:

```python
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })
```

## Performance Monitoring

### View Metrics

```bash
# Get current metrics
./supervisor/supervisorctl.py status

# View historical metrics in database
sqlite3 /Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/architect.db \
  "SELECT * FROM supervisor_metrics ORDER BY timestamp DESC LIMIT 10"
```

### Check Resource Usage

```bash
# View supervisor resource usage
ps aux | grep process_supervisor

# View all supervised services
ps aux | grep -E "app.py|unified_app.py"
```

## Notifications

### Current Channels

1. **Logs** - All events logged to `/tmp/process_supervisor.log`
2. **Database** - Events stored in `supervisor_events` table
3. **Health Alerts** - Critical failures create entries in `health_alerts` table

### Add SMS Notifications (Future)

Edit `supervisor/supervisor_config.json`:

```json
{
  "notifications": {
    "channels": {
      "sms": {
        "enabled": true,
        "provider": "dialpad",
        "numbers": ["+1234567890"]
      }
    }
  }
}
```

## Maintenance

### View Logs

```bash
# Supervisor
tail -100 /tmp/process_supervisor.log

# All service logs
ls -lh /tmp/supervisor_logs/

# Specific service
tail -100 /tmp/supervisor_logs/architect-prod.log
```

### Database Queries

```bash
sqlite3 /Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/architect.db

# View all services
SELECT id, name, state, restart_count FROM supervisor_services;

# View recent events
SELECT timestamp, service_id, event_type, message
FROM supervisor_events
ORDER BY timestamp DESC
LIMIT 20;

# View metrics for a service
SELECT timestamp, cpu_percent, memory_mb, health_status
FROM supervisor_metrics
WHERE service_id = 'architect-prod'
ORDER BY timestamp DESC
LIMIT 10;
```

### Cleanup Old Data

The integration module includes cleanup utilities:

```python
from supervisor.supervisor_integration import SupervisorIntegration

integration = SupervisorIntegration()
integration.cleanup_old_data(days=30)  # Keep last 30 days
```

Or via cron:

```bash
# Add to crontab (run daily at 2 AM)
0 2 * * * cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect && python3 -c "from supervisor.supervisor_integration import SupervisorIntegration; SupervisorIntegration().cleanup_old_data(30)"
```

## Next Steps

1. ✅ **Run verification**: `./supervisor/verify.sh`
2. ✅ **Run setup**: `./supervisor/setup.sh --auto`
3. ✅ **Check status**: `./supervisor/supervisorctl.py status`
4. ✅ **Test auto-restart**: Kill a process and watch it restart
5. ✅ **Add API routes**: Integrate with dashboard
6. ✅ **Enable pharma**: When service is ready
7. ✅ **Monitor logs**: Watch for issues

## Support

### Check Documentation

- **Full docs**: `supervisor/README.md`
- **Implementation**: `supervisor/IMPLEMENTATION_SUMMARY.md`
- **This guide**: `supervisor/QUICKSTART.md`

### Check Status

```bash
./supervisor/supervisorctl.py summary
```

### View Recent Activity

```bash
./supervisor/supervisorctl.py events -n 50
```

### Check Database

```bash
sqlite3 /Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/architect.db \
  "SELECT * FROM supervisor_services"
```

## File Locations

| Component | Location |
|-----------|----------|
| Supervisor code | `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/supervisor/` |
| Configuration | `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/supervisor/supervisor_config.json` |
| Database | `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/architect.db` |
| Supervisor log | `/tmp/process_supervisor.log` |
| Service logs | `/tmp/supervisor_logs/<service-id>.log` |
| PID file | `/tmp/process_supervisor.pid` |
| Service PIDs | `/tmp/supervisor_pids/<service-id>.pid` |

## Success Checklist

- [ ] Verification script passes: `./supervisor/verify.sh`
- [ ] Setup completes successfully: `./supervisor/setup.sh --auto`
- [ ] Supervisor is running: `./supervisor/supervisorctl.py status` shows "✅ Supervisor running"
- [ ] All enabled services are running: Status shows services in "running" state
- [ ] Logs are being written: `tail -f /tmp/process_supervisor.log` shows activity
- [ ] Auto-restart works: Kill a process and it restarts within 30 seconds
- [ ] Health checks pass: Services show healthy status
- [ ] Metrics are recorded: `supervisor_metrics` table has entries
- [ ] Events are logged: `supervisor_events` table has entries

Once all checkboxes are complete, your supervisor system is fully operational!
