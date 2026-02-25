# Architect Node Setup Guide

Complete guide for setting up a distributed node (e.g., pink laptop) with all tools for the Architect Dashboard.

## Quick Start

### 1. Download Setup Script

```bash
cd /path/to/architect
curl -o scripts/setup_node_complete.sh https://[your-repo]/scripts/setup_node_complete.sh
chmod +x scripts/setup_node_complete.sh
```

### 2. Run Setup (Dry Run First)

```bash
# Preview what will be installed
./scripts/setup_node_complete.sh --dry-run --node-name pink-laptop

# If everything looks good, run for real
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://192.168.1.100:8080 \
  --with-webui \
  --with-anythingllm
```

### 3. Configure API Keys

Edit `~/.architect_node.env`:

```bash
# Set your API keys
export GOOGLE_API_KEY=your_gemini_key_here
export ANTHROPIC_API_KEY=your_claude_key_here
export OPENAI_API_KEY=your_openai_key_here
```

### 4. Start Services

```bash
./scripts/start_all_services.sh
```

## Available Options

### Basic Setup

```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://192.168.1.100:8080 \
  --node-port 9000
```

### With Web UI

```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://192.168.1.100:8080 \
  --with-webui
```

**Access**: http://localhost:3000

### With RAG System (AnythingLLM)

```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://192.168.1.100:8080 \
  --with-anythingllm
```

**Access**: http://localhost:3001

### With n8n Automation

```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://192.168.1.100:8080 \
  --with-n8n
```

**Access**: http://localhost:5678 (login: admin / architect)

### Full Stack

```bash
./scripts/setup_node_complete.sh \
  --node-name pink-laptop \
  --dashboard-url http://192.168.1.100:8080 \
  --with-webui \
  --with-anythingllm \
  --with-n8n
```

## What Gets Installed

### Core Components

| Component | Port | Purpose |
|-----------|------|---------|
| **Ollama** | 11434 | Local LLM runtime |
| **Gemini CLI** | - | Google AI integration |
| **Node Agent** | 9000 | Metrics & task reporting |
| **Claude Code** | - | Task execution |

### Optional Components

| Component | Port | Purpose |
|-----------|------|---------|
| **OpenWebUI** | 3000 | ChatGPT-like interface |
| **AnythingLLM** | 3001 | RAG & document chat |
| **n8n** | 5678 | Workflow automation |

## Ollama Model Management

### Pull Available Models

```bash
# Code models
ollama pull codellama
ollama pull neural-chat

# General models
ollama pull mistral
ollama pull llama2
ollama pull dolphin-mixtral

# Specialized
ollama pull orca-mini
ollama pull deepseek-coder
```

### List Installed Models

```bash
ollama list
curl http://localhost:11434/api/tags | jq .
```

### Check Ollama Status

```bash
# Health check
curl http://localhost:11434/api/tags

# Local performance
ollama ps
```

## Integration with Architect Dashboard

### Automatic Registration

The node automatically registers with the dashboard at:
- **URL**: `http://192.168.1.100:8080/api/nodes`
- **Name**: Configured via `--node-name` flag
- **Port**: Configured via `--node-port` flag

### View Node in Dashboard

1. Open `http://192.168.1.100:8080`
2. Go to **System > Nodes**
3. Find your node (pink-laptop)
4. Monitor metrics (CPU, memory, disk)

### Send Tasks to Node

Via Assigner Worker:

```bash
# Route task to specific node
python3 workers/assigner_worker.py \
  --send "Fix the authentication bug" \
  --target codex
```

## Troubleshooting

### Ollama Not Starting

```bash
# Check logs
tail -f /tmp/ollama.log

# Restart manually
~/scripts/start_ollama.sh
```

### Node Not Registering

```bash
# Check if dashboard is reachable
curl http://192.168.1.100:8080/health

# Check node agent logs
tail -f /tmp/node_agent.log
```

### API Keys Not Working

```bash
# Verify environment variables
source ~/.architect_node.env
echo $GOOGLE_API_KEY
echo $ANTHROPIC_API_KEY
```

### Docker Services Not Starting

```bash
# Check Docker is running
docker ps

# Check compose files
docker-compose -f docker-compose-webui.yml up

# View logs
docker logs open-webui
```

## Performance Tuning

### Ollama Configuration

Edit `~/.ollama/config.json`:

```json
{
  "num_parallel": 2,
  "max_queue_size": 1000,
  "request_timeout": 300,
  "num_gpu": 1
}
```

**num_parallel**: Increase for more concurrent requests
**num_gpu**: Set to available GPU count for acceleration

### System Resources

Monitor node performance:

```bash
# CPU & Memory
top

# Disk usage
df -h

# Network
netstat -an | grep LISTEN
```

## Environment Variables

### Required

```bash
# Architect Dashboard
export DASHBOARD_URL=http://192.168.1.100:8080

# Node Configuration
export NODE_NAME=pink-laptop
export NODE_PORT=9000
```

### API Keys (set manually)

```bash
# Google Gemini
export GOOGLE_API_KEY=your_key

# OpenAI
export OPENAI_API_KEY=your_key

# Anthropic Claude
export ANTHROPIC_API_KEY=your_key
```

### Optional

```bash
# LLM Provider
export LLM_DEFAULT_PROVIDER=ollama
export LLM_FAILOVER_ENABLED=true

# Metrics
export REPORT_METRICS=true
export METRICS_INTERVAL=30
```

## Stopping Services

### Individual Services

```bash
# Stop Ollama
pkill -f "ollama serve"

# Stop Node Agent
python3 distributed/node_agent.py --stop
```

### Docker Services

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

### All Services

```bash
# Create stop script
cat > scripts/stop_all_services.sh << 'EOF'
#!/bin/bash
pkill -f "ollama serve"
python3 distributed/node_agent.py --stop
docker-compose -f docker-compose-webui.yml down 2>/dev/null
docker-compose -f docker-compose-anythingllm.yml down 2>/dev/null
docker-compose -f docker-compose-n8n.yml down 2>/dev/null
echo "All services stopped"
EOF

chmod +x scripts/stop_all_services.sh
./scripts/stop_all_services.sh
```

## Monitoring

### Dashboard Metrics

The node reports:
- CPU usage
- Memory consumption
- Disk usage
- Network activity
- Active processes
- Service health

### Log Files

```bash
# Ollama logs
tail -f /tmp/ollama.log

# Node agent logs
tail -f /tmp/node_agent.log

# Docker logs
docker logs open-webui
docker logs anythingllm
docker logs n8n
```

### Health Checks

```bash
# Ollama health
curl http://localhost:11434/api/tags

# Node agent health
curl http://localhost:9000/health

# Dashboard health
curl http://192.168.1.100:8080/health
```

## Upgrading

### Ollama

```bash
ollama pull <model-name>  # Auto-updates to latest version
```

### Python Packages

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Docker Images

```bash
docker pull ghcr.io/open-webui/open-webui:latest
docker pull mintplexlabs/anythingllm:latest
docker pull n8nio/n8n:latest

# Restart containers
docker-compose up -d --pull always
```

## Security

### Firewall Configuration

```bash
# macOS (allow incoming connections)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add ~/scripts/start_ollama.sh

# Linux (UFW)
sudo ufw allow 11434  # Ollama
sudo ufw allow 9000   # Node Agent
sudo ufw allow 3000   # OpenWebUI (if needed)
```

### API Key Management

```bash
# Never commit API keys
echo "~/.architect_node.env" >> .gitignore

# Use secure methods to set environment
export GOOGLE_API_KEY=$(pass show google/api-key)
export ANTHROPIC_API_KEY=$(pass show anthropic/api-key)
```

### Dashboard Access

```bash
# Use VPN or SSH tunnel for remote access
ssh -L 8080:localhost:8080 user@dashboard-host
```

## Support

For issues or questions:

1. Check logs in `/tmp/`
2. Run health checks
3. Review environment variables
4. Check Dashboard system status
5. Consult troubleshooting section above

## Additional Resources

- [Ollama Documentation](https://ollama.ai)
- [Google Gemini API](https://ai.google.dev)
- [OpenWebUI GitHub](https://github.com/open-webui/open-webui)
- [AnythingLLM Documentation](https://docs.useanything.com)
- [n8n Documentation](https://docs.n8n.io)
