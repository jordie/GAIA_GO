# AnythingLLM Installation Guide

## Overview
AnythingLLM is an all-in-one AI application with built-in RAG, AI agents, and local LLM support.

## Prerequisites
- Docker Desktop 4.37.1 or later
- 4GB+ RAM available for Docker
- 10GB+ disk space

## Quick Install (Docker)

### 1. Start Docker Desktop
```bash
open -a Docker
# Wait for Docker to start (check menu bar icon)
```

### 2. Install AnythingLLM
```bash
# Set storage location
export STORAGE_LOCATION=$HOME/anythingllm

# Create storage directory
mkdir -p $STORAGE_LOCATION
touch "$STORAGE_LOCATION/.env"

# Pull and run container
docker run -d \
  -p 3001:3001 \
  -v ${STORAGE_LOCATION}:/app/server/storage \
  -v ${STORAGE_LOCATION}/.env:/app/server/.env \
  -e STORAGE_DIR="/app/server/storage" \
  --name anythingllm \
  mintplexlabs/anythingllm:latest
```

### 3. Access Application
Open: http://localhost:3001

## Mac-Specific Notes

### Accessing Host Services from Container
If you're running other services (Chroma, LocalAI, LMStudio) on your Mac:
- Use: `http://host.docker.internal:PORT`
- Example: `http://host.docker.internal:11434` for Ollama

### Connect to Ollama
```bash
# In AnythingLLM settings:
LLM Provider: Ollama
Base URL: http://host.docker.internal:11434
Model: llama3.2
```

## Docker Management

### Check Status
```bash
docker ps | grep anythingllm
```

### View Logs
```bash
docker logs anythingllm -f
```

### Restart
```bash
docker restart anythingllm
```

### Stop
```bash
docker stop anythingllm
```

### Update to Latest
```bash
docker pull mintplexlabs/anythingllm:latest
docker stop anythingllm
docker rm anythingllm
# Run install command again (step 2)
```

## Integration with LLM Provider System

AnythingLLM is configured in the failover chain:

```
Claude → Conductor → AnythingLLM → Ollama → OpenAI
```

### API Configuration
```python
# In llm_provider.py
anythingllm_config = ProviderConfig(
    enabled=True,
    endpoint="http://localhost:3001",
    timeout=60.0,
    cost_per_1k_prompt=0.0,  # Free, uses local models
    cost_per_1k_completion=0.0,
)
```

### Environment Variables
```bash
export ANYTHINGLLM_URL="http://localhost:3001"
export ANYTHINGLLM_API_KEY=""  # Optional if auth enabled
```

## Features Used in Failover

- **Local LLM Support**: Uses Ollama models via host.docker.internal
- **RAG Capabilities**: Document search and embedding
- **No API Costs**: Fully local operation
- **Fast Inference**: Direct connection to local models

## Troubleshooting

### Port Already in Use
```bash
# Check what's using port 3001
lsof -i :3001
# Kill the process or use different port with -p flag
```

### Connection Issues
```bash
# Verify container is running
docker ps | grep anythingllm

# Check container logs
docker logs anythingllm --tail 50

# Restart container
docker restart anythingllm
```

### Storage Location
Data is persisted at: `$HOME/anythingllm/`
- Database: `$HOME/anythingllm/anythingllm.db`
- Documents: `$HOME/anythingllm/documents/`
- Models: `$HOME/anythingllm/models/`

## Resources

- Official Docs: https://docs.anythingllm.com
- GitHub: https://github.com/Mintplex-Labs/anything-llm
- Docker Hub: https://hub.docker.com/r/mintplexlabs/anythingllm
