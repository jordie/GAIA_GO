# Process Supervisor System

Advanced process supervision system for managing critical services with auto-restart, health monitoring, and dashboard integration.

## Overview

This supervisor system provides:

- **Auto-restart on failure** with exponential backoff
- **Health checks** (HTTP, TCP, process monitoring)
- **Resource monitoring** (CPU, memory limits)
- **Graceful shutdown** handling
- **Dependency management** between services
- **Integration** with architect dashboard
- **Detailed logging** and metrics
- **CLI management** interface

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Process Supervisor (process_supervisor.py)            │
│  - Monitors and manages services                       │
│  - Executes health checks                              │
│  - Handles auto-restart with backoff                   │
│  - Collects metrics                                    │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
  ┌──────────┐ ┌─────────┐ ┌──────────┐
  │Dashboard │ │Reading  │ │Pharmacy  │
  │8080/8081 │ │App 5063 │ │App 7085  │
  └──────────┘ └─────────┘ └──────────┘
        │
        ▼
  ┌──────────────────────────────────┐
  │  Architect Dashboard             │
  │  - Supervisor API endpoints      │
  │  - Metrics database              │
  │  - Event logging                 │
  │  - Health monitoring UI          │
  └──────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
# Install required Python packages
pip3 install psutil requests flask

# Verify installation
python3 -c "import psutil, requests, flask; print('Dependencies OK')"
```

### 2. Configure Services

Edit `supervisor_config.json` to add or modify services:

```json
{
  "services": {
    "my-service": {
      "enabled": true,
      "priority": 1,
      "critical": true,
      "command": "python3",
      "args": ["/path/to/app.py", "--port", "8080"],
      "working_directory": "/path/to/project",
      "environment": {
        "APP_ENV": "prod",
        "PORT": "8080"
      },
      "health_check": {
        "type": "http",
        "endpoint": "http://localhost:8080/health",
        "interval": 30,
        "timeout": 10
      },
      "restart_policy": {
        "max_retries": 5,
        "retry_delay": 10,
        "backoff_multiplier": 2
      },
      "auto_restart": true
    }
  }
}
```

### 3. Start Supervisor

```bash
# Start in foreground (for testing)
python3 supervisor/process_supervisor.py

# Start as daemon
python3 supervisor/process_supervisor.py --daemon

# Check status
python3 supervisor/process_supervisor.py --status

# Stop daemon
python3 supervisor/process_supervisor.py --stop
```

### 4. Use CLI to Manage Services

```bash
# Make CLI executable
chmod +x supervisor/supervisorctl.py

# Show all services
./supervisor/supervisorctl.py status

# Show specific service
./supervisor/supervisorctl.py status architect-prod

# Start/stop/restart service
./supervisor/supervisorctl.py start architect-prod
./supervisor/supervisorctl.py stop reading-app
./supervisor/supervisorctl.py restart pharma

# View logs
./supervisor/supervisorctl.py logs architect-prod
./supervisor/supervisorctl.py logs architect-prod -f  # Follow logs

# Check health
./supervisor/supervisorctl.py health
./supervisor/supervisorctl.py health architect-prod

# View events
./supervisor/supervisorctl.py events
./supervisor/supervisorctl.py events architect-prod

# Show summary
./supervisor/supervisorctl.py summary
```

## Configuration Reference

### Service Configuration

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Enable/disable service |
| `priority` | integer | Start order (lower = first) |
| `critical` | boolean | Mark as critical service |
| `name` | string | Display name |
| `description` | string | Service description |
| `command` | string | Executable command |
| `args` | array | Command arguments |
| `working_directory` | string | Working directory |
| `environment` | object | Environment variables |
| `health_check` | object | Health check configuration |
| `restart_policy` | object | Restart policy configuration |
| `resource_limits` | object | Resource limits |
| `auto_restart` | boolean | Auto-restart on failure |
| `restart_on_exit` | boolean | Restart on clean exit |
| `graceful_shutdown` | object | Graceful shutdown config |
| `dependencies` | array | Service dependencies |

### Health Check Types

#### HTTP Health Check

```json
{
  "type": "http",
  "endpoint": "http://localhost:8080/health",
  "interval": 30,
  "timeout": 10,
  "expected_status": 200,
  "expected_content": "healthy",
  "fallback_check": {
    "type": "tcp",
    "port": 8080
  }
}
```

#### TCP Health Check

```json
{
  "type": "tcp",
  "host": "localhost",
  "port": 8080,
  "interval": 30,
  "timeout": 5
}
```

#### Process Health Check

```json
{
  "type": "process",
  "interval": 30
}
```

### Restart Policy

```json
{
  "max_retries": 5,
  "retry_delay": 10,
  "backoff_multiplier": 2,
  "max_backoff": 300
}
```

- **max_retries**: Maximum restart attempts before marking FATAL
- **retry_delay**: Initial delay before restart (seconds)
- **backoff_multiplier**: Multiplier for exponential backoff
- **max_backoff**: Maximum backoff delay (seconds)

Example backoff sequence with `retry_delay=10`, `backoff_multiplier=2`:
- Attempt 1: 10s
- Attempt 2: 20s
- Attempt 3: 40s
- Attempt 4: 80s
- Attempt 5: 160s

### Resource Limits

```json
{
  "max_memory_mb": 1024,
  "max_cpu_percent": 80
}
```

Warnings are logged when limits are exceeded.

### Graceful Shutdown

```json
{
  "enabled": true,
  "timeout": 30,
  "signal": "SIGTERM"
}
```

## Dashboard Integration

### Add API Routes to app.py

Add to your `app.py`:

```python
# Import supervisor routes
from supervisor.api_routes import register_supervisor_routes

# After creating Flask app
app = Flask(__name__)

# Register supervisor routes
register_supervisor_routes(app)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/supervisor/status` | GET | Get all services status |
| `/api/supervisor/services/<id>` | GET | Get specific service details |
| `/api/supervisor/services/<id>/start` | POST | Start service |
| `/api/supervisor/services/<id>/stop` | POST | Stop service |
| `/api/supervisor/services/<id>/restart` | POST | Restart service |
| `/api/supervisor/services/<id>/health` | GET | Get service health |
| `/api/supervisor/health` | GET | Get overall health |
| `/api/supervisor/metrics` | POST | Receive metrics (internal) |
| `/api/supervisor/events` | GET | Get recent events |
| `/api/supervisor/summary` | GET | Get dashboard summary |
| `/api/supervisor/reload` | POST | Reload configuration |

### Example API Usage

```bash
# Get status
curl http://localhost:8080/api/supervisor/status | jq

# Get specific service
curl http://localhost:8080/api/supervisor/services/architect-prod | jq

# Restart service
curl -X POST http://localhost:8080/api/supervisor/services/architect-prod/restart

# Get health
curl http://localhost:8080/api/supervisor/health | jq

# Get events
curl http://localhost:8080/api/supervisor/events?limit=20 | jq

# Get summary
curl http://localhost:8080/api/supervisor/summary | jq
```

## Database Schema

The supervisor creates these tables in `data/architect.db`:

### supervisor_services

Stores service state and configuration.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Service identifier (primary key) |
| `name` | TEXT | Display name |
| `description` | TEXT | Description |
| `state` | TEXT | Current state |
| `pid` | INTEGER | Process ID |
| `port` | INTEGER | Service port |
| `start_time` | TIMESTAMP | Start time |
| `uptime_seconds` | INTEGER | Uptime in seconds |
| `restart_count` | INTEGER | Total restart count |
| `last_restart` | TIMESTAMP | Last restart time |
| `priority` | INTEGER | Start priority |
| `critical` | INTEGER | Critical flag (0/1) |
| `auto_restart` | INTEGER | Auto-restart flag (0/1) |

### supervisor_metrics

Stores performance metrics.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment ID |
| `service_id` | TEXT | Service identifier |
| `timestamp` | TIMESTAMP | Metric timestamp |
| `cpu_percent` | REAL | CPU usage percentage |
| `memory_mb` | REAL | Memory usage in MB |
| `health_status` | TEXT | Health status |
| `response_time_ms` | REAL | Health check response time |

### supervisor_events

Stores supervisor events.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment ID |
| `service_id` | TEXT | Service identifier |
| `event_type` | TEXT | Event type |
| `timestamp` | TIMESTAMP | Event timestamp |
| `message` | TEXT | Event message |
| `details` | TEXT | JSON details |

## Service States

| State | Description |
|-------|-------------|
| `stopped` | Service is stopped |
| `starting` | Service is starting |
| `running` | Service is running normally |
| `stopping` | Service is stopping |
| `failed` | Service failed |
| `backoff` | Service in backoff period before restart |
| `fatal` | Service exceeded max restart attempts |

## Logging

Logs are stored in:
- **Supervisor log**: `/tmp/process_supervisor.log`
- **Service logs**: `/tmp/supervisor_logs/<service-id>.log`

## Health Monitoring

The supervisor runs health checks at configured intervals:

1. **HTTP checks**: Verify endpoint returns expected status/content
2. **TCP checks**: Verify port is listening
3. **Process checks**: Verify process is running and responsive

Health check failures trigger:
- Logging of failure
- Increment failure counter
- Auto-restart after max failures threshold

## Best Practices

### 1. Always Configure Health Checks

```json
{
  "health_check": {
    "type": "http",
    "endpoint": "http://localhost:8080/health",
    "interval": 30,
    "fallback_check": {
      "type": "tcp",
      "port": 8080
    }
  }
}
```

Always include a fallback TCP check in case the HTTP endpoint fails.

### 2. Set Appropriate Resource Limits

```json
{
  "resource_limits": {
    "max_memory_mb": 1024,
    "max_cpu_percent": 80
  }
}
```

Prevents services from consuming excessive resources.

### 3. Use Graceful Shutdown

```json
{
  "graceful_shutdown": {
    "enabled": true,
    "timeout": 30,
    "signal": "SIGTERM"
  }
}
```

Allows services to clean up before termination.

### 4. Configure Exponential Backoff

```json
{
  "restart_policy": {
    "max_retries": 5,
    "retry_delay": 10,
    "backoff_multiplier": 2,
    "max_backoff": 300
  }
}
```

Prevents rapid restart loops and gives services time to recover.

### 5. Mark Critical Services

```json
{
  "critical": true
}
```

Critical services get higher priority monitoring and immediate alerts.

## Integration with Existing Health Monitor

The supervisor integrates with the existing `workers/health_monitor.py`:

- Supervisor focuses on **process management**
- Health monitor focuses on **system-wide health**
- Both send metrics to dashboard
- Both create alerts in health_alerts table

You can run both simultaneously for comprehensive monitoring.

## Troubleshooting

### Service won't start

1. Check configuration: `cat supervisor/supervisor_config.json`
2. Check service logs: `tail -f /tmp/supervisor_logs/<service-id>.log`
3. Check supervisor log: `tail -f /tmp/process_supervisor.log`
4. Verify command and args are correct
5. Check working directory exists and has correct permissions

### Health checks failing

1. Verify endpoint is accessible: `curl http://localhost:8080/health`
2. Check if service is actually running: `ps aux | grep <service>`
3. Review health check configuration
4. Check firewall/network settings
5. Try TCP fallback check

### Service keeps restarting

1. Check service logs for crash reason
2. Review resource limits
3. Check for port conflicts: `lsof -i :<port>`
4. Verify dependencies are available
5. Check system resources: `top`, `df -h`

### Supervisor won't stop

```bash
# Find supervisor process
ps aux | grep process_supervisor

# Force kill if needed
kill -9 <pid>

# Remove PID file
rm /tmp/process_supervisor.pid
```

## Migration from supervisord

If you're migrating from traditional supervisord:

1. Convert `/etc/supervisor/conf.d/*.conf` to JSON format
2. Update service paths and commands
3. Add health checks (not available in supervisord)
4. Configure restart policies
5. Test in development environment first

Example conversion:

**supervisord config:**
```ini
[program:myapp]
command=/usr/bin/python3 /app/app.py
directory=/app
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/myapp.log
```

**Supervisor config:**
```json
{
  "my-app": {
    "enabled": true,
    "command": "python3",
    "args": ["/app/app.py"],
    "working_directory": "/app",
    "auto_restart": true,
    "restart_on_exit": true,
    "health_check": {
      "type": "process"
    }
  }
}
```

## Performance

- **Check interval**: 30s (configurable)
- **Memory overhead**: ~50-100MB
- **CPU usage**: <1% (idle), 2-5% (active monitoring)
- **Disk usage**: Logs rotate automatically

## Security Considerations

- Supervisor runs as current user (no root required)
- Service logs are world-readable (adjust permissions if needed)
- No network exposure (local monitoring only)
- Dashboard API should be behind authentication
- PID files in `/tmp` (consider using dedicated directory)

## Future Enhancements

- [ ] IPC mechanism for real-time control (instead of API polling)
- [ ] Service dependency resolution (start B after A)
- [ ] Web UI dashboard panel
- [ ] Email/SMS notifications
- [ ] Service groups (start/stop multiple services)
- [ ] Rolling restarts (zero-downtime updates)
- [ ] Resource usage predictions
- [ ] Auto-scaling based on metrics

## Support

For issues or questions:
1. Check logs: `/tmp/process_supervisor.log`
2. Review configuration: `supervisor/supervisor_config.json`
3. Run status check: `./supervisor/supervisorctl.py status`
4. Check dashboard integration: `curl http://localhost:8080/api/supervisor/summary`

## License

Part of the Architect Dashboard project.
