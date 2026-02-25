# Cluster Setup Guide

This guide explains how to set up a multi-node Architect Dashboard cluster for distributed project management.

## Architecture Overview

```
                    ┌─────────────────┐
                    │   Dashboard     │
                    │   (Master)      │
                    │   :8080         │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Node 1      │   │   Node 2      │   │   Node N      │
│  node_agent   │   │  node_agent   │   │  node_agent   │
│  task_worker  │   │  task_worker  │   │  task_worker  │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Components

| Component | Description | Location |
|-----------|-------------|----------|
| Dashboard | Central web UI and API server | Master node |
| Node Agent | Reports metrics to dashboard | Each worker node |
| Task Worker | Processes queued tasks | Each worker node |
| SSH Pool | Manages SSH connections | Master node |

## Prerequisites

### On All Nodes
- Python 3.10+
- SSH server running
- Network connectivity to master node

### On Master Node Only
- SQLite 3
- tmux (optional, for session management)

## Installation

### Step 1: Clone Repository on All Nodes

```bash
git clone https://github.com/yourrepo/architect.git
cd architect
pip install -r requirements.txt
```

### Step 2: Start Dashboard on Master Node

```bash
# Start with default settings
./deploy.sh

# Or with HTTPS
./deploy.sh --ssl

# Or run as daemon
./deploy.sh --daemon
```

The dashboard will be available at `http://master-ip:8080`

### Step 3: Configure Worker Nodes

On each worker node, configure the dashboard URL:

```bash
export ARCHITECT_DASHBOARD_URL="http://master-ip:8080"
```

Or create a config file at `~/.architect/config.json`:

```json
{
  "dashboard_url": "http://master-ip:8080",
  "node_name": "worker-1",
  "capabilities": ["python", "docker", "git"]
}
```

### Step 4: Start Node Agent on Each Worker

```bash
# Run in foreground
python3 distributed/node_agent.py --dashboard http://master-ip:8080

# Run as daemon
python3 distributed/node_agent.py --dashboard http://master-ip:8080 --daemon

# Check status
python3 distributed/node_agent.py --status

# Stop daemon
python3 distributed/node_agent.py --stop
```

### Step 5: Start Task Worker on Each Worker

```bash
# Run in foreground
python3 workers/task_worker.py

# Run as daemon
python3 workers/task_worker.py --daemon

# Check status
python3 workers/task_worker.py --status

# Stop daemon
python3 workers/task_worker.py --stop
```

## Node Registration

Nodes automatically register when the node agent starts. To manually register:

```bash
curl -X POST http://master-ip:8080/api/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "worker-1",
    "hostname": "worker1.local",
    "ip_address": "192.168.1.100",
    "capabilities": ["python", "docker"]
  }'
```

## Health Monitoring

### Configure Health Thresholds

Health thresholds can be configured via environment variables:

```bash
export ARCHITECT_CPU_WARNING=80
export ARCHITECT_CPU_CRITICAL=95
export ARCHITECT_MEMORY_WARNING=85
export ARCHITECT_MEMORY_CRITICAL=95
export ARCHITECT_DISK_WARNING=80
export ARCHITECT_DISK_CRITICAL=90
export ARCHITECT_HEARTBEAT_TIMEOUT=120
```

### Default Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| CPU Usage | 80% | 95% |
| Memory Usage | 85% | 95% |
| Disk Usage | 80% | 90% |
| Load Average | 4.0 | 8.0 |
| Heartbeat Timeout | 120s | - |

### Health Status Levels

- **healthy**: All metrics within normal range
- **warning**: One or more metrics exceed warning threshold
- **critical**: One or more metrics exceed critical threshold
- **offline**: No heartbeat received within timeout period

## Load Balancing

The dashboard uses weighted scoring for task distribution:

| Factor | Weight |
|--------|--------|
| CPU Usage | 40% |
| Memory Usage | 30% |
| Active Tasks | 20% |
| Health Status | 10% |

### Assign Task to Best Node

```bash
curl -X POST http://master-ip:8080/api/tasks/assign-optimal \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "shell",
    "requirements": ["python", "docker"]
  }'
```

### Get Node Recommendations

```bash
curl http://master-ip:8080/api/nodes/recommend?count=3
```

### View Task Distribution

```bash
curl http://master-ip:8080/api/nodes/distribution
```

## SSH Connection Pooling

For distributed operations, SSH connection pooling is enabled by default:

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| max_connections_per_host | 3 | Max simultaneous connections per host |
| connection_timeout | 30s | SSH connection timeout |
| idle_timeout | 300s | Time before idle connection is closed |

### Pool Statistics

```bash
curl http://master-ip:8080/api/ssh/pool/stats
```

### Cleanup Idle Connections

```bash
curl -X POST http://master-ip:8080/api/ssh/pool/cleanup
```

### Execute Command on Node

```bash
curl -X POST http://master-ip:8080/api/ssh/execute \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": 1,
    "command": "uptime"
  }'
```

### Broadcast to All Nodes

```bash
curl -X POST http://master-ip:8080/api/ssh/broadcast \
  -H "Content-Type: application/json" \
  -d '{"command": "df -h"}'
```

## Cluster Visualization

### View Topology

```bash
curl http://master-ip:8080/api/cluster/topology
```

Returns graph data with nodes and edges for visualization.

### View Task Flow

```bash
curl http://master-ip:8080/api/cluster/flow
```

### View Cluster Stats

```bash
curl http://master-ip:8080/api/cluster/stats
```

## Security Configuration

### Enable HTTPS

```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Start with SSL
./deploy.sh --ssl
```

### Configure Authentication

```bash
export ARCHITECT_USER="admin"
export ARCHITECT_PASSWORD="your-secure-password"
```

### SSH Key Setup

For passwordless SSH between nodes:

```bash
# On master node
ssh-keygen -t ed25519 -f ~/.ssh/architect_key
ssh-copy-id -i ~/.ssh/architect_key.pub user@worker-node
```

## Systemd Service Files

### Dashboard Service

Create `/etc/systemd/system/architect-dashboard.service`:

```ini
[Unit]
Description=Architect Dashboard
After=network.target

[Service]
Type=simple
User=architect
WorkingDirectory=/opt/architect
ExecStart=/usr/bin/python3 app.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Node Agent Service

Create `/etc/systemd/system/architect-agent.service`:

```ini
[Unit]
Description=Architect Node Agent
After=network.target

[Service]
Type=simple
User=architect
WorkingDirectory=/opt/architect
Environment=ARCHITECT_DASHBOARD_URL=http://master-ip:8080
ExecStart=/usr/bin/python3 distributed/node_agent.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### Task Worker Service

Create `/etc/systemd/system/architect-worker.service`:

```ini
[Unit]
Description=Architect Task Worker
After=network.target

[Service]
Type=simple
User=architect
WorkingDirectory=/opt/architect
ExecStart=/usr/bin/python3 workers/task_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable Services

```bash
sudo systemctl enable architect-dashboard  # On master
sudo systemctl enable architect-agent      # On workers
sudo systemctl enable architect-worker     # On workers
sudo systemctl start architect-dashboard
sudo systemctl start architect-agent
sudo systemctl start architect-worker
```

## Docker Deployment

### Dockerfile for Dashboard

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "app.py", "--host", "0.0.0.0"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  dashboard:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
    environment:
      - ARCHITECT_USER=admin
      - ARCHITECT_PASSWORD=secure-password

  worker:
    build: .
    command: python workers/task_worker.py
    environment:
      - ARCHITECT_DASHBOARD_URL=http://dashboard:8080
    depends_on:
      - dashboard
```

## Scaling

### Add More Workers

Simply start node agent and task worker on additional machines:

```bash
python3 distributed/node_agent.py --dashboard http://master-ip:8080 --daemon
python3 workers/task_worker.py --daemon
```

### High Availability (Future)

For HA setup, consider:
- PostgreSQL instead of SQLite
- Redis for session/cache
- HAProxy or nginx for load balancing
- Multiple dashboard instances

## Monitoring

### View All Nodes

```bash
curl http://master-ip:8080/api/nodes
```

### View Node Health Summary

```bash
curl http://master-ip:8080/api/nodes/health
```

### View Active Alerts

```bash
curl http://master-ip:8080/api/nodes/alerts
```

### Dashboard Stats

```bash
curl http://master-ip:8080/api/stats
```

## Backup

### Database Backup

```bash
# Stop dashboard
./deploy.sh stop

# Backup database
cp data/architect.db data/architect.db.backup.$(date +%Y%m%d)

# Restart dashboard
./deploy.sh
```

### Automated Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backup/architect"
mkdir -p $BACKUP_DIR
cp /opt/architect/data/architect.db "$BACKUP_DIR/architect.db.$(date +%Y%m%d)"
find $BACKUP_DIR -name "*.db.*" -mtime +7 -delete
```
