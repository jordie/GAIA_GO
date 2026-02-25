# Process Supervisor - File Reference

## Directory Structure

```
/Users/jgirmay/Desktop/gitrepo/pyWork/architect/
├── supervisor/                          # Process supervisor system
│   ├── __init__.py                     # Python module initialization
│   ├── process_supervisor.py           # Main supervisor daemon (29KB)
│   ├── health_checks.py                # Health check system (15KB)
│   ├── supervisor_integration.py       # Dashboard integration (16KB)
│   ├── api_routes.py                   # Flask API routes (9KB)
│   ├── supervisorctl.py                # CLI management tool (14KB)
│   ├── supervisor_config.json          # Service configuration (6KB)
│   ├── setup.sh                        # Setup script (7KB)
│   ├── verify.sh                       # Verification script (4KB)
│   ├── README.md                       # Full documentation (15KB)
│   ├── IMPLEMENTATION_SUMMARY.md       # Implementation details (16KB)
│   ├── QUICKSTART.md                   # Quick start guide (8KB)
│   └── FILES.md                        # This file
│
├── data/
│   └── architect.db                    # SQLite database (with 3 new tables)
│
└── app.py                              # Dashboard (needs API integration)
```

## File Details

### Core System Files

#### `process_supervisor.py` (29KB, executable)

**Purpose**: Main supervisor daemon that monitors and manages services

**Key Classes**:
- `ServiceState` - Enum for service states
- `ServiceMetrics` - Service performance metrics dataclass
- `ManagedService` - Service configuration and state dataclass
- `ProcessSupervisor` - Main supervisor class

**Key Methods**:
- `start()` - Start supervisor daemon
- `stop()` - Stop supervisor and all services
- `_start_service()` - Start a service
- `_stop_service()` - Stop a service
- `_supervise_service()` - Monitor a service
- `_run_health_check()` - Execute health checks
- `_handle_service_failure()` - Handle failures and restart
- `_update_service_metrics()` - Update performance metrics

**Usage**:
```bash
# Start as daemon
python3 process_supervisor.py --daemon

# Start in foreground
python3 process_supervisor.py

# Stop
python3 process_supervisor.py --stop

# Status
python3 process_supervisor.py --status
```

---

#### `health_checks.py` (15KB, executable)

**Purpose**: Health check system with multiple check types

**Key Classes**:
- `HealthStatus` - Enum for health states
- `HealthCheckResult` - Result dataclass
- `HealthChecker` - Health check executor

**Check Types**:
- HTTP health checks with status/content validation
- TCP port availability checks
- Process health and responsiveness checks
- Custom script execution checks
- Health history and summaries

**Usage**:
```python
from supervisor.health_checks import HealthChecker

checker = HealthChecker()

# HTTP check
result = checker.check_http('http://localhost:8080/health')

# TCP check
result = checker.check_tcp('localhost', 8080)

# Process check
result = checker.check_process(12345)

# Get health summary
summary = checker.get_health_summary('architect-prod')
```

---

#### `supervisor_integration.py` (16KB)

**Purpose**: Integration with architect dashboard database

**Key Class**: `SupervisorIntegration`

**Database Tables Created**:
- `supervisor_services` - Service state and configuration
- `supervisor_metrics` - Performance metrics (CPU, memory, health)
- `supervisor_events` - Event log (started, stopped, failed, etc.)

**Key Methods**:
- `update_service_state()` - Update service in database
- `record_metrics()` - Record performance metrics
- `log_event()` - Log supervisor events
- `create_alert()` - Create health alerts
- `get_service_status()` - Get service status
- `get_service_metrics()` - Get metrics history
- `get_service_events()` - Get event history
- `get_dashboard_summary()` - Get summary for dashboard
- `cleanup_old_data()` - Cleanup old metrics/events

**Usage**:
```python
from supervisor.supervisor_integration import SupervisorIntegration

integration = SupervisorIntegration()

# Update service state
integration.update_service_state('architect-prod', {
    'name': 'Architect Dashboard',
    'state': 'running',
    'pid': 12345
})

# Record metrics
integration.record_metrics('architect-prod', {
    'cpu_percent': 5.2,
    'memory_mb': 128.5
})

# Log event
integration.log_event('architect-prod', 'started', 'Service started')

# Get summary
summary = integration.get_dashboard_summary()
```

---

#### `api_routes.py` (9KB)

**Purpose**: Flask API routes for web interface

**Blueprint**: `supervisor_bp` (prefix: `/api/supervisor`)

**Endpoints**:
```
GET  /api/supervisor/status                    # Get all services
GET  /api/supervisor/services/<id>             # Get service details
POST /api/supervisor/services/<id>/start       # Start service
POST /api/supervisor/services/<id>/stop        # Stop service
POST /api/supervisor/services/<id>/restart     # Restart service
GET  /api/supervisor/services/<id>/health      # Get service health
GET  /api/supervisor/health                    # Get overall health
POST /api/supervisor/metrics                   # Receive metrics
GET  /api/supervisor/events                    # Get events
GET  /api/supervisor/summary                   # Get summary
POST /api/supervisor/reload                    # Reload config
```

**Integration**:
```python
# Add to app.py
from supervisor.api_routes import register_supervisor_routes

register_supervisor_routes(app)
```

---

#### `supervisorctl.py` (14KB, executable)

**Purpose**: Command-line interface for management

**Commands**:
- `status [service]` - Show service status
- `start <service>` - Start service
- `stop <service>` - Stop service
- `restart <service>` - Restart service
- `logs <service> [-f] [-n N]` - View logs
- `health [service]` - Show health status
- `events [service] [-n N]` - Show events
- `summary` - Show summary
- `reload` - Reload configuration

**Usage**:
```bash
# Status
./supervisorctl.py status
./supervisorctl.py status architect-prod

# Control
./supervisorctl.py start architect-prod
./supervisorctl.py stop reading-app
./supervisorctl.py restart pharma

# Logs
./supervisorctl.py logs architect-prod
./supervisorctl.py logs architect-prod -f
./supervisorctl.py logs architect-prod -n 100

# Monitoring
./supervisorctl.py health
./supervisorctl.py events
./supervisorctl.py summary
```

---

### Configuration Files

#### `supervisor_config.json` (6KB)

**Purpose**: Service configuration in JSON format

**Structure**:
```json
{
  "version": "1.0",
  "global": {
    "check_interval": 30,
    "restart_delay": 5,
    "max_restart_attempts": 3,
    "log_directory": "/tmp/supervisor_logs",
    "pid_directory": "/tmp/supervisor_pids"
  },
  "services": {
    "service-id": {
      "enabled": true,
      "priority": 1,
      "critical": true,
      "name": "Display Name",
      "command": "python3",
      "args": ["app.py", "--port", "8080"],
      "working_directory": "/path/to/project",
      "environment": {...},
      "health_check": {...},
      "restart_policy": {...},
      "resource_limits": {...},
      "graceful_shutdown": {...}
    }
  },
  "notifications": {...},
  "monitoring": {...}
}
```

**Pre-configured Services**:
- `architect-prod` (8080) - ENABLED
- `architect-qa` (8081) - ENABLED
- `reading-app` (5063) - ENABLED
- `pharma` (7085) - DISABLED

---

### Setup and Utility Scripts

#### `setup.sh` (7KB, executable)

**Purpose**: Interactive setup script

**Features**:
- Dependency checking and installation
- Directory creation
- Script permission setup
- Configuration validation
- Database initialization
- Supervisor start/stop/restart
- Interactive menu or auto mode

**Usage**:
```bash
# Automatic setup
./setup.sh --auto

# Interactive menu
./setup.sh
```

**Menu Options**:
1. Full setup
2. Install dependencies only
3. Initialize database only
4. Start supervisor
5. Stop supervisor
6. Restart supervisor
7. Show status
8. View logs
9. Exit

---

#### `verify.sh` (4KB, executable)

**Purpose**: Verification script to check installation

**Checks**:
- Core files present and executable
- Configuration valid JSON
- Documentation present
- Python dependencies installed
- Required directories exist
- Database accessible
- Supervisor status
- Configured services

**Usage**:
```bash
./verify.sh
```

**Output**:
- ✓ PASS - Check passed
- ⚠ WARN - Warning (non-critical)
- ✗ FAIL - Check failed

---

### Documentation Files

#### `README.md` (15KB)

**Comprehensive documentation including**:
- Overview and architecture
- Quick start guide
- Configuration reference
- Health check documentation
- API documentation
- CLI usage
- Database schema
- Best practices
- Troubleshooting
- Migration from supervisord

---

#### `IMPLEMENTATION_SUMMARY.md` (16KB)

**Implementation details including**:
- What was implemented
- File structure
- Setup instructions
- Integration with existing systems
- Current status
- Next steps
- Monitoring and maintenance
- Configuration examples

---

#### `QUICKSTART.md` (8KB)

**Quick start guide including**:
- 5-minute setup
- Common commands
- Testing procedures
- Configuration examples
- Troubleshooting
- Success checklist

---

#### `FILES.md` (This file)

**File reference including**:
- Directory structure
- Detailed file descriptions
- Usage examples
- Key classes and methods

---

### Module Files

#### `__init__.py` (1KB)

**Purpose**: Python module initialization

**Exports**:
- `ProcessSupervisor`
- `ServiceState`
- `HealthChecker`
- `HealthStatus`
- `SupervisorIntegration`

**Usage**:
```python
from supervisor import ProcessSupervisor, HealthChecker
from supervisor.supervisor_integration import SupervisorIntegration

supervisor = ProcessSupervisor()
supervisor.start()
```

---

## Runtime Files

### Created During Operation

```
/tmp/
├── process_supervisor.pid           # Supervisor PID file
├── process_supervisor.log           # Supervisor log
├── supervisor_logs/                 # Service logs directory
│   ├── architect-prod.log
│   ├── architect-qa.log
│   ├── reading-app.log
│   └── pharma.log
└── supervisor_pids/                 # Service PID files
    ├── architect-prod.pid
    ├── architect-qa.pid
    ├── reading-app.pid
    └── pharma.pid
```

---

## Database Tables

### Created in `data/architect.db`

#### `supervisor_services`

```sql
CREATE TABLE supervisor_services (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    state TEXT NOT NULL,
    pid INTEGER,
    port INTEGER,
    start_time TIMESTAMP,
    uptime_seconds INTEGER DEFAULT 0,
    restart_count INTEGER DEFAULT 0,
    last_restart TIMESTAMP,
    priority INTEGER DEFAULT 999,
    critical INTEGER DEFAULT 0,
    auto_restart INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `supervisor_metrics`

```sql
CREATE TABLE supervisor_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cpu_percent REAL,
    memory_mb REAL,
    health_status TEXT,
    response_time_ms REAL,
    FOREIGN KEY (service_id) REFERENCES supervisor_services(id)
);
```

#### `supervisor_events`

```sql
CREATE TABLE supervisor_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message TEXT,
    details TEXT,
    FOREIGN KEY (service_id) REFERENCES supervisor_services(id)
);
```

---

## Dependencies

### Python Packages Required

- `psutil` - Process and system utilities
- `requests` - HTTP client for health checks
- `flask` - Web framework for API routes
- `sqlite3` - Database (built-in)

### Install

```bash
pip3 install psutil requests flask
```

---

## File Permissions

All scripts should be executable:

```bash
chmod +x supervisor/*.py
chmod +x supervisor/*.sh
```

---

## Size Summary

| Component | Size | Files |
|-----------|------|-------|
| Core system | 60KB | 4 files |
| Configuration | 6KB | 1 file |
| Scripts | 11KB | 2 files |
| Documentation | 39KB | 4 files |
| Module | 1KB | 1 file |
| **Total** | **117KB** | **12 files** |

---

## Quick Reference

### Start Supervisor
```bash
./supervisor/setup.sh --auto
```

### Check Status
```bash
./supervisor/supervisorctl.py status
```

### View Logs
```bash
tail -f /tmp/process_supervisor.log
./supervisor/supervisorctl.py logs architect-prod -f
```

### Stop Supervisor
```bash
python3 ./supervisor/process_supervisor.py --stop
```

### Verify Installation
```bash
./supervisor/verify.sh
```

---

## Integration Points

### With Existing Systems

1. **Health Monitor** (`workers/health_monitor.py`)
   - Complementary monitoring
   - Both can run simultaneously
   - Share database tables

2. **Dashboard** (`app.py`)
   - Add API routes via `register_supervisor_routes(app)`
   - Use database tables for display
   - Send metrics to dashboard

3. **Services** (`data/services.json`)
   - Reference for port mappings
   - Service definitions

4. **Database** (`data/architect.db`)
   - Three new tables
   - Integrates with existing tables

---

## Support

For detailed documentation, see:
- `README.md` - Full documentation
- `QUICKSTART.md` - Quick start guide
- `IMPLEMENTATION_SUMMARY.md` - Implementation details

For issues:
1. Check logs: `/tmp/process_supervisor.log`
2. Run verification: `./supervisor/verify.sh`
3. Check status: `./supervisor/supervisorctl.py status`
