# Pink Laptop Deployment Instructions

## Quick Summary
- **Target**: Pink MacBook (192.168.1.172)
- **SSH**: `jgirmay@192.168.1.172`
- **Dashboard**: http://100.112.58.92:8151
- **Setup Time**: ~30-45 minutes

---

## Deployment Steps

### Step 1: Access Pink Laptop

**From main machine**:
```bash
ssh jgirmay@192.168.1.172
```

**Or via hostname**:
```bash
ssh jgirmay@pink-laptop.local
```

**Or via Tailscale**:
```bash
ssh jgirmay@100.112.58.92
```

### Step 2: Navigate to Architect Directory

```bash
cd ~/architect
```

If directory doesn't exist:
```bash
# Clone or pull the repo
git clone https://github.com/your-repo/architect.git ~/architect
cd ~/architect
```

### Step 3: Preview Setup (Dry-Run)

```bash
./scripts/setup_node_complete.sh \
  --dry-run \
  --node-name pink-laptop \
  --dashboard-url http://100.112.58.92:8151
```

**Expected output**:
```
✓ OS detected: macos
✓ System dependencies ready
✓ Ollama configured (port: 11434)
✓ Gemini CLI configured
✓ Docker ready
✓ Python environment ready
✓ Node agent configured
✓ Health checks passed
✓ Setup script completed!
```

### Step 4: Run Full Setup

**Basic setup (core components only)**:
```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://100.112.58.92:8151
```

**Full setup (with all optional components)**:
```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://100.112.58.92:8151 \
  --with-webui \
  --with-anythingllm \
  --with-n8n
```

**Custom ports** (if needed):
```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://100.112.58.92:8151 \
  --node-port 9001 \
  --ollama-port 11435 \
  --with-webui
```

### Step 5: Configure API Keys

Edit the environment file:
```bash
nano ~/.architect_node.env
```

Add your API keys:
```bash
export GOOGLE_API_KEY=your_gemini_api_key_here
export ANTHROPIC_API_KEY=your_claude_api_key_here
export OPENAI_API_KEY=your_openai_api_key_here (optional)
```

Save and exit (`Ctrl+X`, `Y`, `Enter`)

### Step 6: Start All Services

```bash
./scripts/start_all_services.sh
```

**Expected output**:
```
Starting Ollama...
Starting node agent...
Starting OpenWebUI...
Starting AnythingLLM...
All services started!
Dashboard: http://100.112.58.92:8151
Ollama: http://localhost:11434
```

### Step 7: Verify Deployment

**Check Ollama health**:
```bash
curl http://localhost:11434/api/tags
```

**Check Node Agent**:
```bash
curl http://localhost:9000/health
```

**Check node in dashboard**:
```bash
curl http://100.112.58.92:8151/api/nodes | jq '.nodes[] | select(.name=="pink-laptop")'
```

**Pull a test model**:
```bash
ollama pull mistral
```

---

## What Gets Installed

### Core Components (Always)
| Component | Port | Purpose |
|-----------|------|---------|
| Ollama | 11434 | Local LLM runtime |
| Gemini CLI | - | Google AI integration |
| Node Agent | 9000 | Metrics reporting |
| Claude Code | - | Task execution |

### Optional Components (With Flags)
| Component | Port | Flag |
|-----------|------|------|
| OpenWebUI | 3000 | `--with-webui` |
| AnythingLLM | 3001 | `--with-anythingllm` |
| n8n | 5678 | `--with-n8n` |

---

## After Setup - Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Dashboard | http://100.112.58.92:8151 | Project management |
| Ollama | http://localhost:11434 | LLM health check |
| OpenWebUI | http://localhost:3000 | Chat interface (if installed) |
| AnythingLLM | http://localhost:3001 | RAG system (if installed) |
| n8n | http://localhost:5678 | Workflows (if installed) |

---

## Troubleshooting

### Setup Script Not Found
```bash
cd ~/architect/scripts
ls -l setup_node_complete.sh

# Make executable
chmod +x setup_node_complete.sh
```

### Permission Denied
```bash
# Make script executable
chmod +x scripts/setup_node_complete.sh

# Or run with bash explicitly
bash scripts/setup_node_complete.sh --node-name pink-laptop ...
```

### Ollama Not Starting
```bash
# Check if already running
ps aux | grep ollama

# View logs
tail -f /tmp/ollama.log

# Manual start
ollama serve
```

### Node Agent Not Connecting
```bash
# Check if dashboard is reachable
curl http://100.112.58.92:8151/health

# Check node agent logs
tail -f /tmp/node_agent.log
```

### API Keys Not Working
```bash
# Source environment file
source ~/.architect_node.env

# Verify variables
echo $GOOGLE_API_KEY
echo $ANTHROPIC_API_KEY

# If empty, edit the file
nano ~/.architect_node.env
```

---

## Stopping Services

### Individual Services
```bash
# Stop Ollama
pkill -f "ollama serve"

# Stop Node Agent
python3 distributed/node_agent.py --stop
```

### Docker Services (if installed)
```bash
# Stop OpenWebUI
docker-compose -f docker-compose-webui.yml down

# Stop AnythingLLM
docker-compose -f docker-compose-anythingllm.yml down

# Stop n8n
docker-compose -f docker-compose-n8n.yml down

# Stop all
docker-compose down
```

---

## Viewing Logs

```bash
# Ollama logs
tail -f /tmp/ollama.log

# Node agent logs
tail -f /tmp/node_agent.log

# Docker service logs
docker logs open-webui
docker logs anythingllm
docker logs n8n
```

---

## Model Management

### List Installed Models
```bash
ollama list
```

### Pull New Models
```bash
# Recommended models
ollama pull mistral              # Fast, good quality
ollama pull codellama          # Code completion
ollama pull neural-chat        # Chat optimized
ollama pull deepseek-coder     # Code focused

# All available models
ollama pull llama2
ollama pull orca-mini
ollama pull dolphin-mixtral
```

### Check Model Status
```bash
# Health check
curl http://localhost:11434/api/tags | jq

# List running models
ollama ps
```

---

## Dashboard Integration

Once setup is complete, the pink laptop will:
- ✅ Appear in dashboard at **System > Nodes**
- ✅ Report CPU/memory/disk metrics every 30 seconds
- ✅ Accept task assignments from the assigner
- ✅ Execute work on local LLMs (Ollama, Gemini)
- ✅ Respond to health checks

### Sending Tasks to Pink Laptop

From main machine:
```bash
python3 workers/assigner_worker.py \
  --send "Generate a hello world function in Python" \
  --target codex
```

---

## Performance Notes

### For Faster Setup
- Use `--skip-docker` if Docker is already installed
- Skip optional components on first run

### Recommended Ollama Settings
Edit `~/.ollama/config.json`:
```json
{
  "num_parallel": 2,
  "max_queue_size": 1000,
  "request_timeout": 300
}
```

### Monitor Resources
```bash
# CPU & Memory
top

# Disk usage
df -h

# Network connections
netstat -an | grep LISTEN
```

---

## Support

For detailed information, see:
- **Setup Guide**: scripts/NODE_SETUP_GUIDE.md
- **Quick Reference**: scripts/NODE_QUICK_REFERENCE.txt
- **Test Report**: NODE_SETUP_TEST_REPORT.md

---

## Deployment Checklist

- [ ] SSH to pink-laptop (192.168.1.172)
- [ ] Navigate to ~/architect
- [ ] Run dry-run preview
- [ ] Run full setup
- [ ] Configure API keys in ~/.architect_node.env
- [ ] Start all services
- [ ] Verify Ollama: curl http://localhost:11434/api/tags
- [ ] Verify Node Agent: curl http://localhost:9000/health
- [ ] Check dashboard: http://100.112.58.92:8151/api/nodes
- [ ] Pull test model: ollama pull mistral
- [ ] Done! ✅

---

**Status**: Ready for Deployment
**Estimated Time**: 30-45 minutes
