# Architect Dashboard - Complete System Documentation

**Version:** 2.0
**Last Updated:** February 7, 2026
**Author:** Jordan Girmay with Claude Sonnet 4.5

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Database Schema](#database-schema)
5. [API Reference](#api-reference)
6. [Workers & Automation](#workers--automation)
7. [Session Management](#session-management)
8. [Monitoring & Health](#monitoring--health)
9. [Security](#security)
10. [Deployment](#deployment)
11. [Troubleshooting](#troubleshooting)
12. [Maintenance](#maintenance)

---

## System Overview

### What is Architect Dashboard?

Architect Dashboard is a distributed project management and automation platform that orchestrates development work across multiple Claude AI sessions, manages tmux-based workflows, and provides comprehensive monitoring and health tracking.

### Key Capabilities

- **Project Management**: Track projects, features, bugs, and milestones
- **Autonomous Development**: AI-powered code generation and improvement
- **Session Orchestration**: Manage multiple Claude sessions via tmux
- **Task Queue**: Distributed background task processing
- **Health Monitoring**: Real-time system health and performance tracking
- **SMS Notifications**: Operational status updates via Dialpad
- **Secure Vault**: Encrypted credential storage
- **Auto-Confirmation**: Automatic approval of AI prompts

### System Statistics

- **18 Projects** under management
- **4 Claude Sessions** (3 coding + 1 manager)
- **6+ Background Workers** for automation
- **Real-time Monitoring** on ports 8080/8081
- **Hourly SMS Updates** for operational visibility

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Architect Dashboard                       │
│                     (Flask Web App)                          │
│                   Ports: 8080, 8081                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──> SQLite Databases
             │    ├── architect.db (main)
             │    ├── assigner.db (session tracking)
             │    └── site_health.db (monitoring)
             │
             ├──> Background Workers
             │    ├── assigner_worker.py
             │    ├── auto_confirm_worker.py
             │    ├── persistent_orchestrator.py
             │    ├── continuous_improvement_worker.py
             │    ├── task_worker.py
             │    └── milestone_worker.py
             │
             ├──> Claude Sessions (tmux)
             │    ├── architect (coding)
             │    ├── dev_worker1 (coding)
             │    ├── dev_worker2 (coding)
             │    └── claude_orchestrator (manager)
             │
             └──> External Services
                  ├── Dialpad (SMS)
                  ├── GitHub (version control)
                  └── Google Sheets (optional sync)
```

### Technology Stack

- **Backend**: Python 3.14, Flask
- **Database**: SQLite3
- **Session Manager**: tmux
- **AI Provider**: Claude API (Anthropic)
- **Notifications**: Dialpad SMS API
- **Version Control**: Git
- **Deployment**: Shell scripts, systemd (optional)

### Network Topology

- **Primary Dashboard**: http://localhost:8080
- **Monitor Dashboard**: http://100.112.58.92:8081/monitor.html
- **API Endpoints**: REST API on port 8080
- **Database**: File-based SQLite (no network exposure)

---

## Core Components

### 1. Flask Application (app.py)

**Purpose**: Main web application providing UI and REST API

**Key Features**:
- Password-protected dashboard
- Project/feature/bug tracking
- Real-time session monitoring
- Task queue management
- Secure vault for credentials

**Ports**:
- 8080: Primary dashboard
- 8081: Monitor view

**Authentication**:
- Username: `architect` (case-insensitive)
- Password: `peace5`
- Session timeout: 1 hour
- Override via environment variables

### 2. Database Layer

#### Main Database (architect.db)

**Size**: ~1MB (optimized from 29MB)

**Tables**:
- `projects`: Project definitions
- `features`: Feature specifications
- `bugs`: Bug tracking
- `task_queue`: Background tasks
- `secrets`: Encrypted credentials
- `claude_interactions`: AI interaction logs (max 1000)
- `claude_patterns`: Auto-approval patterns
- `milestone_summaries`: Generated milestones

#### Assigner Database (assigner.db)

**Size**: ~220KB

**Tables**:
- `sessions`: tmux session tracking
- `prompts`: Prompt queue and history
- `assignment_history`: Assignment logs
- `lost_and_found`: Failed assignments

#### Health Database (site_health.db)

**Size**: ~3.2MB

**Tables**:
- `health_checks`: System health metrics
- `outages`: Downtime tracking

### 3. Session Management

#### Active Claude Sessions

| Session | Role | Provider | Status |
|---------|------|----------|--------|
| architect | Coding | Claude | Active |
| dev_worker1 | Coding | Claude | Active |
| dev_worker2 | Coding | Claude | Active |
| claude_orchestrator | Manager | Claude | Active |

#### Session States

- **idle**: Waiting for input (> 30 minutes)
- **busy**: Actively processing
- **waiting_input**: Ready for input

#### Session Specialties

- **coding**: General software development
- **manager**: Orchestration and planning

### 4. Workers & Background Processes

#### Assigner Worker

**Script**: `workers/assigner_worker.py`

**Purpose**: Dispatch prompts to available Claude sessions

**Features**:
- Auto-detects idle sessions
- Priority-based queuing
- Timeout handling (default: 30 minutes)
- Retry logic (max: 3 attempts)
- Session affinity

**Run**:
```bash
python3 workers/assigner_worker.py --daemon
```

#### Auto-Confirm Worker

**Script**: `workers/auto_confirm_worker.py`

**Purpose**: Automatically confirm Claude prompts

**Features**:
- Monitors sessions every 2-4 minutes
- Random confirmation delays (2-5 seconds)
- Detects bash, edits, and other confirmable prompts
- Single-instance enforcement

**Run**:
```bash
python3 workers/auto_confirm_worker.py
```

#### Persistent Orchestrator

**Script**: `workers/persistent_orchestrator.py`

**Purpose**: Execute long-term development plans

**Features**:
- Phase-based execution
- Progress tracking (currently 31% Phase 1)
- Idle detection and action
- Cycle-based operation (1-minute intervals)

**Current Work**: LLM Provider Failover Implementation

**Run**:
```bash
python3 workers/persistent_orchestrator.py
```

#### Continuous Improvement Worker

**Script**: `workers/continuous_improvement_worker.py`

**Purpose**: Generate system improvement suggestions

**Features**:
- 5-minute cycles
- System health analysis
- LLM-powered suggestions
- Auto-suggestion queueing

**Run**:
```bash
python3 workers/continuous_improvement_worker.py --daemon
```

#### Task Worker

**Script**: `workers/task_worker.py`

**Purpose**: Process background tasks from queue

**Supported Task Types**:
- `shell`: Execute shell commands
- `python`: Run Python scripts
- `git`: Git operations
- `deploy`: Deployment scripts
- `test`: Run tests
- `build`: Build projects

**Run**:
```bash
python3 workers/task_worker.py --daemon
```

#### Milestone Worker

**Script**: `workers/milestone_worker.py`

**Purpose**: Scan projects and generate development milestones

**Features**:
- Scans TODO files, code comments, plans
- Generates JSON and Markdown milestone reports
- Phases and task breakdown
- Estimated hours and timelines

**Run**:
```bash
python3 workers/milestone_worker.py --scan
```

---

## Database Schema

### Projects Table

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    source_path TEXT,
    status TEXT DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Status Values**: `active`, `archived`, `paused`

### Features Table

```sql
CREATE TABLE features (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    milestone_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    spec TEXT,
    status TEXT DEFAULT 'draft',
    priority INTEGER DEFAULT 0,
    assigned_to TEXT,
    assigned_node TEXT,
    tmux_session TEXT,
    estimated_hours REAL,
    actual_hours REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

**Status Values**: `draft`, `in_progress`, `completed`, `blocked`

### Sessions Table (assigner.db)

```sql
CREATE TABLE sessions (
    name TEXT PRIMARY KEY,
    status TEXT DEFAULT 'unknown',
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_task_id INTEGER,
    working_dir TEXT,
    is_claude INTEGER DEFAULT 0,
    last_output TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    provider TEXT,
    specialty TEXT DEFAULT 'general',
    success_rate REAL DEFAULT 0.0,
    avg_completion_time INTEGER DEFAULT 0,
    total_tasks_completed INTEGER DEFAULT 0,
    total_tasks_failed INTEGER DEFAULT 0,
    FOREIGN KEY (current_task_id) REFERENCES prompts(id)
);
```

### Prompts Table (assigner.db)

```sql
CREATE TABLE prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'api',
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    assigned_session TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    response TEXT,
    error TEXT,
    metadata TEXT,
    target_session TEXT,
    target_provider TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    timeout_minutes INTEGER DEFAULT 30,
    archived INTEGER DEFAULT 0,
    archived_at TIMESTAMP
);
```

**Status Values**: `pending`, `assigned`, `in_progress`, `completed`, `failed`, `cancelled`

### Secrets Table

```sql
CREATE TABLE secrets (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    encrypted_value TEXT NOT NULL,
    service TEXT,
    category TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INTEGER DEFAULT 0
);
```

**Categories**: `api_key`, `password`, `token`, `certificate`, `ssh_key`, `env_var`, `general`

**Encryption**: XOR cipher with key 42 (simple obfuscation, not production-grade)

---

## API Reference

### Authentication

All API endpoints except `/api/errors` require authentication via session cookie.

**Login**:
```bash
POST /login
Content-Type: application/x-www-form-urlencoded

username=architect&password=peace5
```

### Projects

#### List Projects
```bash
GET /api/projects
```

**Response**:
```json
[
  {
    "id": 1,
    "name": "architect",
    "description": "Dashboard project",
    "status": "active",
    "source_path": "/path/to/architect"
  }
]
```

#### Create Project
```bash
POST /api/projects
Content-Type: application/json

{
  "name": "my-project",
  "description": "Project description",
  "source_path": "/path/to/project",
  "status": "active",
  "priority": 1
}
```

#### Update Project
```bash
PUT /api/projects/<id>
Content-Type: application/json

{
  "status": "archived"
}
```

### Features

#### List Features
```bash
GET /api/features?project_id=1&status=in_progress
```

#### Create Feature
```bash
POST /api/features
Content-Type: application/json

{
  "project_id": 1,
  "title": "Implement user authentication",
  "description": "Add JWT-based auth",
  "status": "draft",
  "priority": 1,
  "estimated_hours": 8.0
}
```

### Prompts (Assigner)

#### Queue Prompt
```bash
POST /api/assigner/send
Content-Type: application/json

{
  "content": "Fix the authentication bug in app.py",
  "priority": 5,
  "target_session": "dev_claude",
  "timeout_minutes": 60,
  "metadata": {"project": "auth"}
}
```

**Response**:
```json
{
  "prompt_id": 42,
  "success": true
}
```

#### Get Queue Status
```bash
GET /api/assigner/status
```

**Response**:
```json
{
  "pending": 3,
  "in_progress": 2,
  "completed_today": 15,
  "failed_today": 1
}
```

### Secrets (Vault)

#### List Secrets
```bash
GET /api/secrets
```

**Response** (values hidden):
```json
[
  {
    "id": 1,
    "name": "DIALPAD_API_KEY",
    "category": "api_key",
    "description": "Dialpad SMS API key",
    "created_at": "2026-02-06T12:00:00"
  }
]
```

#### View Secret
```bash
GET /api/secrets/<id>
```

**Response** (value decrypted):
```json
{
  "id": 1,
  "name": "DIALPAD_API_KEY",
  "value": "decrypted_key_value",
  "category": "api_key"
}
```

#### Create Secret
```bash
POST /api/secrets
Content-Type: application/json

{
  "name": "GITHUB_TOKEN",
  "value": "ghp_xxxxxxxxxxxx",
  "category": "token",
  "description": "GitHub personal access token"
}
```

### Health & Monitoring

#### Get Statistics
```bash
GET /api/stats
```

**Response**:
```json
{
  "projects": 18,
  "active_features": 7,
  "pending_tasks": 12,
  "active_sessions": 4,
  "workers": 6
}
```

#### Health Check
```bash
GET /health
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-07T00:00:00Z"
}
```

---

## Workers & Automation

### Starting All Workers

```bash
#!/bin/bash
# Start all automation workers

# Assigner Worker
nohup python3 workers/assigner_worker.py --daemon > logs/assigner.log 2>&1 &

# Auto-Confirm Worker
python3 workers/auto_confirm_worker.py &

# Persistent Orchestrator
nohup python3 workers/persistent_orchestrator.py > logs/orchestrator.log 2>&1 &

# Continuous Improvement Worker
nohup python3 workers/continuous_improvement_worker.py --daemon > logs/ci.log 2>&1 &

# Task Workers (3 instances)
for i in {1..3}; do
  nohup python3 workers/task_worker.py --worker-id worker-$i --daemon > logs/task_worker_$i.log 2>&1 &
done

echo "All workers started"
```

### Stopping All Workers

```bash
pkill -f assigner_worker
pkill -f auto_confirm_worker
pkill -f persistent_orchestrator
pkill -f continuous_improvement_worker
pkill -f task_worker
```

### Checking Worker Status

```bash
ps aux | grep -E "(assigner|auto_confirm|persistent|continuous|task_worker)" | grep -v grep
```

---

## Session Management

### Creating Claude Sessions

```bash
# Create coding session
tmux new-session -d -s dev_worker3 'claude'

# Create manager session
tmux new-session -d -s project_manager 'claude'
```

### Registering Sessions

Sessions are auto-detected by the assigner worker. Manual registration:

```bash
sqlite3 data/assigner/assigner.db "INSERT INTO sessions (name, provider, specialty, is_claude) VALUES ('dev_worker3', 'claude', 'coding', 1)"
```

### Monitoring Sessions

**Via Dashboard**: http://localhost:8080/dashboard

**Via API**:
```bash
GET /api/assigner/sessions
```

**Via CLI**:
```bash
python3 workers/assigner_worker.py --sessions
```

### Sending Commands to Sessions

```bash
# Via tmux
tmux send-keys -t architect "echo 'Hello from command line'" C-m

# Via API
POST /api/tmux/send
{
  "session": "architect",
  "command": "ls -la"
}

# Via assigner
python3 workers/assigner_worker.py --send "Analyze the codebase" --target architect
```

---

## Monitoring & Health

### SMS Status Updates

**Service**: Dialpad SMS
**Frequency**: Hourly (configurable)
**Recipient**: +15103886759

**Update Format**:
```
🔧 Architect 10:00PM

Sessions: 4 active, 0 idle
  Claude: 4 | Codex: 2

Prompts: 0 queued | 0 active | 3 done (1h)

Tasks: 0 pending | 0 active

Features: 8 active | 2 done (24h)

Health: ✅ HEALTHY
```

**Health Indicators**:
- ✅ HEALTHY: All systems operational
- ⚠️ DEGRADED: Issues detected (stuck tasks, idle sessions, etc.)

**Configuring Updates**:
```bash
# Change interval
vim workers/send_updates.py
# Update default interval in parser (line 59)

# Change phone number
# Update default in parser (line 58)

# Manual test
python3 workers/send_updates.py --once
```

### Monitor Dashboard

**URL**: http://100.112.58.92:8081/monitor.html

**Features**:
- Real-time session status
- Live task tracking
- Worker health indicators
- Auto-refresh every 10 seconds

**Starting Monitor**:
```bash
python3 app.py --port 8081
```

### Log Files

**Location**: `logs/`

| Log File | Purpose |
|----------|---------|
| `app_8080.log` | Main dashboard |
| `app_8081.log` | Monitor dashboard |
| `assigner.log` | Prompt assignment |
| `auto_confirm.log` | Auto-confirmation |
| `orchestrator.log` | Persistent orchestrator |
| `ci.log` | Continuous improvement |
| `updates.log` | SMS updates |
| `status_errors.log` | Status system errors |

**Viewing Logs**:
```bash
# Real-time tail
tail -f logs/app_8080.log

# Last 100 lines
tail -100 logs/assigner.log

# Search for errors
grep -i error logs/*.log
```

---

## Security

### Authentication

**Password Protection**:
- All dashboard routes require login
- Session-based authentication
- 1-hour session timeout
- Secure cookie settings (HttpOnly, SameSite)

**Credentials**:
```bash
export ARCHITECT_USER=admin
export ARCHITECT_PASSWORD=your_secure_password
```

### Secrets Vault

**Encryption**: XOR cipher (key: 42)

⚠️ **Warning**: This is basic obfuscation, not production-grade encryption. For production, use:
- Fernet (symmetric encryption)
- AWS Secrets Manager
- HashiCorp Vault
- Encrypted environment variables

**Accessing Secrets**:
```python
import sqlite3

def get_secret(name):
    conn = sqlite3.connect('data/architect.db')
    cursor = conn.cursor()
    cursor.execute("SELECT encrypted_value FROM secrets WHERE name = ?", (name,))
    encrypted = cursor.fetchone()[0]
    conn.close()

    # Decrypt (XOR with 42)
    return ''.join(chr(ord(c) ^ 42) for c in encrypted)
```

### Network Security

**Recommendations**:
1. Run behind reverse proxy (nginx)
2. Enable HTTPS with SSL certificates
3. Restrict port access via firewall
4. Use VPN for remote access
5. Enable rate limiting

**SSL Setup**:
```bash
./deploy.sh --ssl
```

---

## Deployment

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/jordie/architect.git
cd architect

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize database
python3 -c "from app import init_db; init_db()"

# 4. Start dashboard
./deploy.sh

# 5. Access dashboard
open http://localhost:8080
```

### Production Deployment

#### Using deploy.sh

```bash
# Start with SSL
./deploy.sh --ssl

# Start as daemon
./deploy.sh --daemon

# Check status
./deploy.sh status

# Stop
./deploy.sh stop

# Restart
./deploy.sh restart
```

#### Manual Deployment

```bash
# 1. Set environment variables
export ARCHITECT_USER=admin
export ARCHITECT_PASSWORD=secure_password_here
export SESSION_TIMEOUT=7200  # 2 hours
export PORT=8080

# 2. Start Flask app
gunicorn -w 4 -b 0.0.0.0:8080 app:app --daemon --error-logfile logs/gunicorn_error.log --access-logfile logs/gunicorn_access.log

# 3. Start workers
./scripts/start_workers.sh

# 4. Verify
curl http://localhost:8080/health
```

#### Systemd Service

Create `/etc/systemd/system/architect.service`:

```ini
[Unit]
Description=Architect Dashboard
After=network.target

[Service]
Type=simple
User=architect
WorkingDirectory=/opt/architect
ExecStart=/usr/bin/python3 /opt/architect/app.py
Restart=always
RestartSec=10
Environment=PORT=8080
Environment=ARCHITECT_USER=admin
Environment=ARCHITECT_PASSWORD=peace5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable architect
sudo systemctl start architect
sudo systemctl status architect
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Server port |
| `HOST` | 0.0.0.0 | Server host |
| `ARCHITECT_USER` | architect | Login username |
| `ARCHITECT_PASSWORD` | peace5 | Login password |
| `SESSION_TIMEOUT` | 3600 | Session timeout (seconds) |
| `SESSION_COOKIE_SECURE` | false | HTTPS-only cookies |
| `SECRET_KEY` | (auto) | Flask secret key |

---

## Troubleshooting

### Common Issues

#### 1. Database Locked Error

**Symptom**: `database is locked` errors in logs

**Cause**: Multiple processes accessing SQLite simultaneously

**Fix**:
```bash
# Enable WAL mode for better concurrency
sqlite3 data/architect.db "PRAGMA journal_mode=WAL;"
sqlite3 data/assigner/assigner.db "PRAGMA journal_mode=WAL;"
```

#### 2. Monitor Page Not Loading

**Symptom**: http://100.112.58.92:8081/monitor.html returns 404 or connection refused

**Fix**:
```bash
# Check if app is running on 8081
lsof -i :8081

# If not running, start it
python3 app.py --port 8081 &
```

#### 3. Auto-Confirm Not Working

**Symptom**: Claude sessions waiting indefinitely for confirmation

**Fix**:
```bash
# Kill and restart auto-confirm worker
pkill -9 -f auto_confirm_worker
python3 workers/auto_confirm_worker.py &

# Verify it's running
ps aux | grep auto_confirm
```

#### 4. Prompts Not Being Assigned

**Symptom**: Prompts stuck in `pending` status

**Fix**:
```bash
# Check assigner worker
python3 workers/assigner_worker.py --status

# Check for idle sessions
python3 workers/assigner_worker.py --sessions

# Restart assigner
pkill -f assigner_worker
python3 workers/assigner_worker.py --daemon &
```

#### 5. Database Bloat

**Symptom**: Slow queries, large database files

**Fix**:
```bash
# Clean up old records
sqlite3 data/architect.db "DELETE FROM claude_interactions WHERE id NOT IN (SELECT id FROM claude_interactions ORDER BY created_at DESC LIMIT 1000)"

# Vacuum to reclaim space
sqlite3 data/architect.db "VACUUM"

# Optimize and rebuild
sqlite3 data/architect.db ".dump" | sqlite3 data/architect_optimized.db
mv data/architect.db data/architect_backup.db
mv data/architect_optimized.db data/architect.db
```

#### 6. High Memory Usage

**Symptom**: Python processes consuming excessive RAM

**Fix**:
```bash
# Check memory usage
ps aux | grep python | awk '{print $2, $4, $11}' | sort -k2 -rn

# Restart high-memory processes
pkill -f worker_name
# Then restart individually

# Monitor memory over time
watch -n 5 'ps aux | grep python | awk "{print \$2, \$4, \$11}" | sort -k2 -rn | head -5'
```

---

## Maintenance

### Daily Tasks

1. **Check Worker Status**
   ```bash
   ./scripts/check_workers.sh
   ```

2. **Review Logs for Errors**
   ```bash
   grep -i error logs/*.log | tail -20
   ```

3. **Verify SMS Updates**
   - Check phone for hourly status messages
   - Confirm system health indicators

### Weekly Tasks

1. **Database Cleanup**
   ```bash
   # Clean old claude_interactions
   sqlite3 data/architect.db "DELETE FROM claude_interactions WHERE created_at < datetime('now', '-7 days')"

   # Clean old health_checks
   sqlite3 data/site_health.db "DELETE FROM health_checks WHERE created_at < datetime('now', '-7 days')"

   # Vacuum
   sqlite3 data/architect.db "VACUUM"
   sqlite3 data/site_health.db "VACUUM"
   ```

2. **Backup Databases**
   ```bash
   mkdir -p backups/$(date +%Y%m%d)
   cp data/architect.db backups/$(date +%Y%m%d)/
   cp data/assigner/assigner.db backups/$(date +%Y%m%d)/
   ```

3. **Review Metrics**
   - Check milestone progress
   - Review completed features
   - Analyze session utilization

### Monthly Tasks

1. **Update Dependencies**
   ```bash
   pip list --outdated
   pip install -U package_name
   pip freeze > requirements.txt
   ```

2. **Security Audit**
   - Review secret access logs
   - Rotate API keys
   - Update passwords

3. **Performance Optimization**
   - Analyze database query performance
   - Review worker efficiency
   - Optimize slow endpoints

### Database Maintenance Schedule

**Auto-Cleanup Script** (`scripts/db_cleanup.sh`):

```bash
#!/bin/bash
# Daily database cleanup

# Keep only last 1000 claude_interactions
sqlite3 data/architect.db "DELETE FROM claude_interactions WHERE id NOT IN (SELECT id FROM claude_interactions ORDER BY created_at DESC LIMIT 1000)"

# Keep only last 7 days of health_checks
sqlite3 data/site_health.db "DELETE FROM health_checks WHERE created_at < datetime('now', '-7 days')"

# Keep only last 30 days of prompts
sqlite3 data/assigner/assigner.db "DELETE FROM prompts WHERE status IN ('completed', 'failed') AND completed_at < datetime('now', '-30 days')"

# Vacuum all databases
sqlite3 data/architect.db "VACUUM"
sqlite3 data/site_health.db "VACUUM"
sqlite3 data/assigner/assigner.db "VACUUM"

echo "Database cleanup complete"
```

**Add to crontab**:
```bash
# Run daily at 3 AM
0 3 * * * /path/to/architect/scripts/db_cleanup.sh >> /path/to/architect/logs/cleanup.log 2>&1
```

---

## Appendix

### File Structure

```
architect/
├── app.py                    # Main Flask application
├── deploy.sh                 # Deployment script
├── requirements.txt          # Python dependencies
├── utils.py                  # Utility functions
├── CLAUDE.md                 # Claude Code instructions
├── README.md                 # Project overview
│
├── templates/
│   ├── login.html           # Login page
│   ├── dashboard.html       # Main dashboard
│   └── monitor.html         # Live monitor
│
├── static/
│   ├── css/                 # Stylesheets
│   └── js/                  # JavaScript files
│
├── data/
│   ├── architect.db         # Main database
│   ├── site_health.db       # Health monitoring
│   ├── assigner/
│   │   └── assigner.db      # Session tracking
│   └── milestones/          # Generated milestone files
│
├── scripts/
│   ├── session_terminal.py  # Interactive CLI
│   └── db_cleanup.sh        # Database maintenance
│
├── workers/
│   ├── assigner_worker.py           # Prompt dispatcher
│   ├── auto_confirm_worker.py       # Auto-confirmation
│   ├── persistent_orchestrator.py   # Long-term execution
│   ├── continuous_improvement_worker.py  # System improvements
│   ├── task_worker.py               # Background tasks
│   ├── milestone_worker.py          # Milestone generation
│   ├── dialpad_sms.py              # SMS integration
│   └── send_updates.py             # Status updates
│
├── services/
│   ├── llm_provider.py      # LLM abstraction layer
│   └── circuit_breaker.py   # Fault tolerance
│
├── migrations/              # Database migrations
│   ├── 001_initial.sql
│   └── ...
│
├── logs/                    # Log files
│   ├── app_8080.log
│   ├── assigner.log
│   └── ...
│
└── docs/
    ├── ARCHITECT_SYSTEM_DOCUMENTATION.md  # This file
    └── SELF_HEALING_SYSTEM.md
```

### Quick Reference Commands

```bash
# Start everything
./deploy.sh --daemon
./scripts/start_workers.sh

# Stop everything
./deploy.sh stop
pkill -f worker

# Check status
./deploy.sh status
ps aux | grep -E "(app.py|worker)" | grep -v grep

# View logs
tail -f logs/app_8080.log

# Database query
sqlite3 data/architect.db "SELECT * FROM projects"

# Send test SMS
python3 workers/send_updates.py --once

# Queue prompt
python3 workers/assigner_worker.py --send "Your task here"

# Check sessions
python3 workers/assigner_worker.py --sessions
```

### Support & Contact

**Project Repository**: https://github.com/jordie/architect
**Issues**: https://github.com/jordie/architect/issues
**Author**: Jordan Girmay (jgirmay@gmail.com)

---

**End of Documentation**

*Generated by Claude Sonnet 4.5 on February 7, 2026*
