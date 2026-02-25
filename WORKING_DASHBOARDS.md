# Working Dashboards - Quick Reference

## ✅ Available Dashboards

### 1. Main Dashboard
**URL**: http://100.112.58.92:8151/

**Features**:
- Agent list and status
- Real-time log streaming
- Create/stop agents
- Health monitoring

### 2. Enhanced Dashboard
**URL**: http://100.112.58.92:8151/enhanced

**Features**:
- Advanced agent management
- Enhanced UI
- Additional metrics

## 🔌 API Endpoints (All Working)

### Health Check
```bash
curl http://100.112.58.92:8151/api/health
```

### List Agents
```bash
curl http://100.112.58.92:8151/api/agents
```

### Create Agent via API
```bash
curl -X POST http://100.112.58.92:8151/api/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "test-agent", "command": "bash"}'
```

### Get Agent Details
```bash
curl http://100.112.58.92:8151/api/agents/<agent-name>
```

### Stop Agent
```bash
curl -X DELETE http://100.112.58.92:8151/api/agents/<agent-name>
```

## 📋 Agent Management (Recommended)

Since the web dashboards are basic, use the command-line tools for full functionality:

### View Status
```bash
python3 agent_task_router.py status
```

### Assign Task
```bash
python3 agent_task_router.py assign \
  "Task description" \
  /path/to/work/dir \
  agent-name
```

### Monitor Locks
```bash
python3 file_lock_manager.py list
```

### Attach to Agent
```bash
tmux attach -t dev-backend-1
```

### Watch Activity
```bash
# Real-time status
watch -n 2 'python3 agent_task_router.py status'

# View logs
tail -f /tmp/agent_locks/dev-backend-1.log
```

## 🎯 Recommended Workflow

1. **Use CLI tools** for task management (agent_task_router.py)
2. **Use tmux** to interact directly with agents
3. **Use dashboards** for high-level monitoring only

The file locking system and task router provide much more functionality than the web dashboards!

---

**Note**: The advanced dashboard routes (interactive, performance, database, query, replay) are not available in this apiserver version.
