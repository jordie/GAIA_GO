# Multi-Node Agent Cluster Setup

## 🌐 Cluster Overview

### Primary Node (Orchestrator)
- **Name**: Main Server
- **Tailscale IP**: 100.112.58.92
- **Local IP**: 192.168.1.231
- **Role**: Orchestrator, API Server, Task Router
- **Agents**: 8 management agents (dev, qa, managers, ops)

### Worker Nodes

#### Node 1: Pink Laptop
- **Name**: pink-laptop
- **IP**: 192.168.1.172
- **Role**: Worker
- **Status**: ✅ Deployed
- **Location**: ~/agent_deployment
- **Agents**: Ready to spawn

## 🚀 Node 1 (Pink Laptop) - Quick Start

### Start the Node

```bash
# SSH to pink laptop
ssh 192.168.1.172

# Navigate to deployment
cd ~/agent_deployment

# Start API server
./start_node.sh
```

### Spawn Agents on Pink Laptop

```bash
# Spawn a Claude agent
./start_agent.sh pink-dev-1 claude

# Spawn a Gemini agent
./start_agent.sh pink-dev-2 gemini

# List running agents
tmux list-sessions
```

### Assign Tasks to Remote Agents

From the **primary node** (100.112.58.92):

```bash
# First, update team_config.json to include pink laptop agents
python3 << 'EOF'
import json

config = json.load(open('team_config.json'))
config['agents'].extend([
    {
        "name": "pink-dev-1",
        "tool": "claude",
        "role": "Remote Developer",
        "focus": "Distributed tasks",
        "node": "pink-laptop",
        "node_ip": "192.168.1.172",
        "status": "running"
    },
    {
        "name": "pink-dev-2",
        "tool": "gemini",
        "role": "Remote Developer",
        "focus": "Distributed tasks",
        "node": "pink-laptop",
        "node_ip": "192.168.1.172",
        "status": "running"
    }
])

with open('team_config.json', 'w') as f:
    json.dump(config, f, indent=2)

print("✅ Added pink laptop agents to team config")
EOF

# Now assign tasks
python3 agent_task_router.py assign \
  "Process data files" \
  /tmp/data_processing \
  pink-dev-1
```

## 🔒 File Locking Across Nodes

The file locking system works across nodes using **shared NFS/network storage** or **distributed lock coordination**.

### Option 1: Shared Lock Directory (NFS)

```bash
# On primary node, share lock directory via NFS
sudo apt-get install nfs-kernel-server
echo "/tmp/agent_locks 192.168.1.0/24(rw,sync,no_subtree_check)" | sudo tee -a /etc/exports
sudo exportfs -a

# On pink laptop, mount shared locks
sudo apt-get install nfs-common
sudo mount 192.168.1.231:/tmp/agent_locks /tmp/agent_locks
```

### Option 2: Redis-Based Distributed Locks

```bash
# On primary node, install Redis
docker run -d -p 6379:6379 redis:latest

# Update file_lock_manager.py to use Redis backend
# (Future enhancement)
```

## 📊 Monitoring Cluster

### From Primary Node

```bash
# View all agents (local + remote)
python3 agent_task_router.py status

# View all locks
python3 file_lock_manager.py list

# Check pink laptop health
curl http://192.168.1.172:8151/api/health
```

### From Pink Laptop

```bash
# View local agents
tmux list-sessions

# Check API server
curl http://localhost:8151/api/health

# View locks
python3 file_lock_manager.py list
```

## 🎯 Task Distribution Strategies

### 1. Manual Assignment
```bash
# Assign specific tasks to specific nodes
python3 agent_task_router.py assign \
  "Heavy computation task" \
  /data/processing \
  pink-dev-1
```

### 2. Round-Robin
```python
# Distribute tasks evenly across nodes
agents = ["dev-backend-1", "pink-dev-1", "pink-dev-2"]
for i, task in enumerate(tasks):
    agent = agents[i % len(agents)]
    assign_task(task, agent)
```

### 3. Load-Based
```python
# Assign to least-loaded node
def get_least_loaded_agent():
    # Check CPU/memory on each node
    # Return agent on node with most capacity
    pass
```

## 🌐 Network Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Primary Node (100.112.58.92 / 192.168.1.231)          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Task Router                                     │  │
│  │  - Receives tasks                                │  │
│  │  - Routes to local or remote agents              │  │
│  │  - Manages file locks                            │  │
│  └────────────┬─────────────────────────────────────┘  │
│               │                                         │
│  ┌────────────▼─────────────────┐                      │
│  │  Local Agents (8)            │                      │
│  │  - dev-backend-1             │                      │
│  │  - dev-frontend-1            │                      │
│  │  - qa-tester-1, qa-tester-2  │                      │
│  │  - manager-product, tech     │                      │
│  │  - architect, devops         │                      │
│  └──────────────────────────────┘                      │
└─────────────────────┬───────────────────────────────────┘
                      │
                      │ Network (192.168.1.0/24)
                      │
┌─────────────────────▼───────────────────────────────────┐
│  Worker Node: Pink Laptop (192.168.1.172)              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Local API Server (8151)                         │  │
│  └────────────┬─────────────────────────────────────┘  │
│               │                                         │
│  ┌────────────▼─────────────────┐                      │
│  │  Remote Agents               │                      │
│  │  - pink-dev-1 (Claude)       │                      │
│  │  - pink-dev-2 (Gemini)       │                      │
│  │  - pink-qa-1                 │                      │
│  │  - ...                       │                      │
│  └──────────────────────────────┘                      │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Shared Lock Directory                           │  │
│  │  /tmp/agent_locks (mounted via NFS)              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 🔧 Management Commands

### Add More Nodes

```bash
# Setup another node
./setup_remote_node.sh 192.168.1.XXX node-name

# Update team config
# Add new agents to team_config.json
```

### Remove Node

```bash
# SSH to node
ssh 192.168.1.172

# Stop agents
tmux kill-server

# Stop API server
pkill -f apiserver
```

### Update Node

```bash
# Re-run setup to update files
./setup_remote_node.sh 192.168.1.172 pink-laptop
```

## 📈 Scaling Considerations

| Nodes | Max Agents | Recommended Use |
|-------|------------|-----------------|
| 1 | 10-20 | Development |
| 2-3 | 20-50 | Small team |
| 4-6 | 50-100 | Medium team |
| 7+ | 100+ | Large scale |

## 🚨 Troubleshooting

### Pink Laptop Not Responding

```bash
# Check if node is reachable
ping 192.168.1.172

# Check SSH
ssh 192.168.1.172 "echo OK"

# Check API server
curl http://192.168.1.172:8151/api/health
```

### Lock Conflicts

```bash
# Check locks on primary
python3 file_lock_manager.py list

# Check locks on pink laptop
ssh 192.168.1.172 "cd ~/agent_deployment && python3 file_lock_manager.py list"

# Clean stale locks
python3 file_lock_manager.py cleanup
```

### Agent Not Starting

```bash
# SSH to pink laptop
ssh 192.168.1.172

# Check tmux sessions
tmux list-sessions

# Check logs
tail -f ~/agent_deployment/logs/*.log
```

## 📚 Next Steps

1. ✅ Pink laptop deployed and configured
2. ⏭️ Start API server on pink laptop
3. ⏭️ Spawn agents on pink laptop
4. ⏭️ Test task assignment to remote agents
5. ⏭️ Set up shared lock directory (NFS)
6. ⏭️ Configure automated failover
7. ⏭️ Add monitoring dashboard

---

**Cluster Status**:
- Primary Node: ✅ Running (100.112.58.92)
- Pink Laptop: ✅ Deployed (192.168.1.172)
- Total Capacity: 8 local + unlimited remote agents

**Ready to scale!** 🚀
