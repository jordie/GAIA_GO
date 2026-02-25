# Environment Isolation - Feature Environments

## 🎯 Purpose

Avoid race conditions and conflicts between the main architect session and feature development work.

---

## 🏗️ Setup

### Feature Branch
```bash
Branch: feature/week2-advanced-features-0214
Status: Active
Commits: Week 2 advanced features (scraping, quality scoring, multi-project)
```

### Feature Environment
```bash
Environment: env_1
Port: 8081 (isolated from main:8080)
Data Dir: feature_environments/env_1/data/
Log File: feature_environments/env_1/dashboard.log
PID File: feature_environments/env_1/dashboard.pid
```

---

## 📊 Services Running

### Main Architect Session (Port 8080)
- **Status**: Can run independently
- **Purpose**: Main development work
- **Data**: `data/` directory
- **Access**: http://localhost:8080

### Feature Environment 1 (Port 8081)
- **Status**: Running (PID: 20869)
- **Purpose**: Week 2 feature development
- **Data**: `feature_environments/env_1/data/`
- **Access**: http://localhost:8081
- **Branch**: feature/week2-advanced-features-0214

---

## 🔧 Management Commands

### Start Feature Dashboard
```bash
feature_environments/env_1/start_dashboard.sh
```

### Stop Feature Dashboard
```bash
# Read PID from file
PID=$(cat feature_environments/env_1/dashboard.pid 2>/dev/null)
kill $PID

# Or force kill all on port 8081
pkill -f "web_dashboard.py.*8081"
```

### Check Status
```bash
# Test if running
curl http://localhost:8081/api/health

# View logs
tail -f feature_environments/env_1/dashboard.log

# Check process
ps aux | grep "web_dashboard.*8081"
```

---

## 🔄 Isolation Strategy

### Port Isolation
- **Main**: Port 8080
- **Env 1**: Port 8081
- **Env 2-5**: Ports 8082-8085 (available)

### Data Isolation
```
main/
  data/                          # Main data directory
    routing_stats.json
    quality_scores.json
    auto_confirm_activity.json
    perplexity_results/
    auto_execution/

feature_environments/
  env_1/
    data/                        # Isolated data directory
      routing_stats.json
      quality_scores.json
      ...
    dashboard.log
    dashboard.pid
    web_dashboard_config.sh
    start_dashboard.sh
```

### Branch Isolation
- Main work stays on `main` or other feature branches
- Week 2 work isolated in `feature/week2-advanced-features-0214`
- No conflicts between branches

---

## 🚀 Benefits

### No Race Conditions
- ✅ Different ports prevent conflicts
- ✅ Separate data directories
- ✅ Independent processes

### Safe Development
- ✅ Feature work doesn't affect main session
- ✅ Can test without breaking production
- ✅ Easy rollback if needed

### Clean Separation
- ✅ Feature branches for code
- ✅ Feature environments for runtime
- ✅ Clear ownership of changes

---

## 📋 Environment Configuration

### web_dashboard.py
```python
# Supports port override
python3 web_dashboard.py --port 8081

# Detects environment
feature_env = os.environ.get("FEATURE_ENV", "main")
```

### start_dashboard.sh
```bash
export FEATURE_ENV="env_1"
export WEB_DASHBOARD_PORT="8081"
python3 web_dashboard.py --port 8081
```

---

## 🧪 Testing Both Environments

### Main Environment
```bash
curl http://localhost:8080/api/health
# If running main dashboard

# Data location
ls data/routing_stats.json
```

### Feature Environment 1
```bash
curl http://localhost:8081/api/health
# Should return: {"status": "ok", "timestamp": "..."}

# Data location
ls feature_environments/env_1/data/routing_stats.json
```

---

## 🔮 Future Environments

### Available Slots
- **env_2**: Port 8082
- **env_3**: Port 8083
- **env_4**: Port 8084
- **env_5**: Port 8085

### Creating New Environment
```bash
# 1. Create directory
mkdir -p feature_environments/env_2

# 2. Create config
cat > feature_environments/env_2/start_dashboard.sh <<'EOF'
#!/bin/bash
export FEATURE_ENV="env_2"
python3 web_dashboard.py --port 8082 > feature_environments/env_2/dashboard.log 2>&1 &
echo $! > feature_environments/env_2/dashboard.pid
EOF

# 3. Make executable
chmod +x feature_environments/env_2/start_dashboard.sh

# 4. Start
feature_environments/env_2/start_dashboard.sh
```

---

## 📊 Current Status

```bash
Main Session:
  Port: 8080
  Status: Available (stopped to avoid conflict)
  Data: data/

Feature Env 1 (Week 2):
  Port: 8081
  Status: Running (PID: 20869)
  Data: feature_environments/env_1/data/
  Branch: feature/week2-advanced-features-0214
  URL: http://localhost:8081
```

---

## 🎯 Best Practices

### Development Workflow
1. **Create feature branch**: `git checkout -b feature/name`
2. **Use feature environment**: Start on isolated port
3. **Develop in isolation**: No conflicts with main
4. **Test thoroughly**: Verify in feature env first
5. **Merge when ready**: Merge to main after testing

### Avoid Conflicts
- ✅ Always use different ports
- ✅ Use separate data directories
- ✅ Check process isn't already running
- ✅ Stop main session if needed

### Clean Up
```bash
# When done with feature
pkill -f "web_dashboard.*8081"
rm feature_environments/env_1/dashboard.pid

# Keep data for reference
# Or clean up: rm -rf feature_environments/env_1/data/
```

---

## 🎉 Success Criteria

**Environment Isolation**: ✅ ACHIEVED

- ✅ Feature dashboard running on port 8081
- ✅ Separate from main session (port 8080)
- ✅ Isolated data directory
- ✅ Feature branch isolation
- ✅ No race conditions possible
- ✅ Safe concurrent development

---

**Access Feature Environment**: http://localhost:8081 🚀

**Access Main Environment**: http://localhost:8080 (when running)
