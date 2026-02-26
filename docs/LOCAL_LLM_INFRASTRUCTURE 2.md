# Local LLM Infrastructure & Data Flow

This document describes the local AI infrastructure that reduces dependency on remote LLMs (Claude, OpenAI, etc.) by running models and tools locally.

## Overview

The Architect Dashboard uses a hybrid approach: **local-first with remote fallback**. This provides resilience, cost savings, and privacy while maintaining access to cutting-edge remote models when needed.

```
┌─────────────────────────────────────────────────────────────────┐
│                     ARCHITECT DASHBOARD                          │
│                  (Project Management & Orchestration)            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ├── Local LLM Stack (Primary)
                       │   └── Fallback to Remote (Claude, OpenAI)
                       │
┌──────────────────────┴──────────────────────────────────────────┐
│                     LOCAL AI INFRASTRUCTURE                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐           │
│  │   Ollama   │───▶│ LocalAI    │───▶│  OpenWebUI │           │
│  │   (Models) │    │ (REST API) │    │    (Chat)  │           │
│  └────────────┘    └────────────┘    └────────────┘           │
│        │                  │                  │                  │
│        │                  │                  │                  │
│        ▼                  ▼                  ▼                  │
│  ┌────────────────────────────────────────────────────┐       │
│  │              n8n Workflow Automation                │       │
│  │        (Agents, Task Routing, Orchestration)        │       │
│  └────────────────────────────────────────────────────┘       │
│        │                                                        │
│        ├──────┬──────────┬──────────┬──────────┐             │
│        ▼      ▼          ▼          ▼          ▼             │
│  ┌─────────┐ ┌──────┐ ┌─────────┐ ┌────────┐ ┌──────┐     │
│  │AnythingLLM│Whisper│WhisperX │ │Stable  │ │ComfyUI│     │
│  │   (RAG)  │ (STT) │  (STT)  │ │Diffusion│ │(Image)│     │
│  │          │       │         │ │ (Image)│ │       │     │
│  └─────────┘ └──────┘ └─────────┘ └────────┘ └──────┘     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Ollama - Local Model Runner

**Purpose**: Run Large Language Models (LLMs) locally on your hardware.

**Key Features**:
- Run models like Llama 3.2, Mistral, CodeLlama, Phi-3
- GPU acceleration (CUDA, Metal, ROCm)
- Model hot-swapping
- Low-latency inference
- No internet required once models are downloaded

**Installation**:
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve

# Pull a model
ollama pull llama3.2
ollama pull codellama
```

**Integration with Architect**:
```python
# services/llm_provider.py
from ollama import Client

client = Client(host='http://localhost:11434')
response = client.generate(
    model='llama3.2',
    prompt='Fix this bug in the authentication module'
)
```

**Data Flow**:
```
Architect → Ollama (localhost:11434) → Model Inference → Response
```

---

### 2. LocalAI - OpenAI-Compatible REST API

**Purpose**: Drop-in replacement for OpenAI API that runs locally.

**Key Features**:
- OpenAI API-compatible endpoints (`/v1/chat/completions`, `/v1/embeddings`)
- Supports multiple model backends (Ollama, llama.cpp, vLLM)
- Multi-modal support (text, image, audio)
- Function calling support
- Embedding generation for RAG

**Installation**:
```bash
# Docker deployment
docker run -p 8080:8080 \
  -v $PWD/models:/models \
  -ti --rm quay.io/go-skynet/local-ai:latest

# Or build from source
git clone https://github.com/mudler/LocalAI
cd LocalAI
docker-compose up -d
```

**Configuration** (`config/localai.yaml`):
```yaml
name: llama3
backend: llama-cpp
parameters:
  model: llama-3-8b-instruct.gguf
  temperature: 0.7
  top_k: 40
  top_p: 0.9
context_size: 4096
f16: true
```

**Integration with Architect**:
```python
# Use standard OpenAI SDK
import openai

openai.api_base = "http://localhost:8080/v1"
openai.api_key = "not-needed"

response = openai.ChatCompletion.create(
    model="llama3",
    messages=[{"role": "user", "content": "Explain this codebase"}]
)
```

**Data Flow**:
```
Architect → LocalAI (localhost:8080) → Ollama/llama.cpp → Response
```

---

### 3. OpenWebUI - User-Friendly Chat Interface

**Purpose**: ChatGPT-like web UI for local models.

**Key Features**:
- Multi-user support with authentication
- Chat history and search
- Model switching on-the-fly
- Document upload and RAG
- Prompt templates and shortcuts
- Dark/light themes

**Installation**:
```bash
docker run -d -p 3000:8080 \
  -v open-webui:/app/backend/data \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

**Integration with Architect**:
- Accessible via dashboard link: `http://localhost:3000`
- Users can test prompts before automating them
- Export chat sessions as context for autopilot runs

**Data Flow**:
```
User → OpenWebUI (localhost:3000) → Ollama (localhost:11434) → Model
```

---

### 4. n8n - Workflow Automation & Agent Builder

**Purpose**: Build AI-powered agents and automate tasks without code.

**Key Features**:
- Visual workflow editor
- 400+ integrations (GitHub, Slack, databases, etc.)
- AI agent templates (RAG, web scraping, task delegation)
- Scheduled workflows
- Error handling and retries
- Self-hosted and secure

**Installation**:
```bash
docker run -d -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  -e N8N_BASIC_AUTH_ACTIVE=true \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=yourpassword \
  --name n8n \
  n8nio/n8n
```

**Example Workflow** (Architect → n8n → LLM):
```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│  Webhook   │────▶│Parse GitHub│────▶│LLM Analysis│────▶│Create Task │
│ (from      │     │Issue       │     │(via Ollama)│     │(Architect) │
│ Architect) │     │            │     │            │     │            │
└────────────┘     └────────────┘     └────────────┘     └────────────┘
```

**Integration with Architect**:
```python
# Trigger n8n workflow from Architect
import requests

webhook_url = "http://localhost:5678/webhook/analyze-pr"
data = {
    "repo": "myorg/myrepo",
    "pr_number": 123,
    "model": "codellama"
}
response = requests.post(webhook_url, json=data)
```

**Data Flow**:
```
Architect → n8n (localhost:5678) → Ollama/LocalAI → GitHub → Architect
```

---

### 5. AnythingLLM - All-in-One RAG & Document Chat

**Purpose**: Retrieval-Augmented Generation (RAG) for chatting with your documents.

**Key Features**:
- Ingest documents (PDF, TXT, DOCX, code files)
- Vector embeddings (local or remote)
- Multi-workspace support
- Supports Ollama, LocalAI, OpenAI, Claude
- Browser extension for web scraping
- Agent mode (web search, code execution)

**Installation**:
```bash
# Desktop app (macOS/Windows/Linux)
# Download from: https://anythingllm.com/download

# Or Docker
docker run -d -p 3001:3001 \
  -v ~/anythingllm:/app/server/storage \
  -e STORAGE_DIR="/app/server/storage" \
  --name anythingllm \
  anythingllm/anythingllm:latest
```

**Configuration for Ollama**:
1. Open AnythingLLM → Settings → LLM
2. Select "Ollama"
3. Set URL: `http://localhost:11434`
4. Choose model: `llama3.2`

**Integration with Architect**:
```python
# Use AnythingLLM API to query project documentation
import requests

response = requests.post('http://localhost:3001/api/v1/workspace/architect/chat',
    json={
        "message": "What is the authentication flow?",
        "mode": "query"
    },
    headers={"Authorization": f"Bearer {api_key}"}
)
```

**Data Flow**:
```
Documents → AnythingLLM (localhost:3001) → Embeddings → Vector DB → Ollama → Response
```

---

### 6. Whisper & WhisperX - Speech-to-Text

**Purpose**: High-accuracy local speech transcription.

**Key Features**:
- **Whisper**: OpenAI's transcription model (runs locally)
- **WhisperX**: Enhanced version with word-level timestamps and diarization
- Multiple language support
- Real-time or batch processing
- No cloud API costs

**Installation**:
```bash
# Install Whisper
pip install openai-whisper

# Install WhisperX
pip install whisperx

# Download model
whisper --model medium --output_dir ./transcripts audio.mp3
```

**Integration with Architect**:
```python
# Transcribe voice notes for task creation
import whisper

model = whisper.load_model("base")
result = model.transcribe("voice_note.mp3")
text = result["text"]

# Create task from transcription
create_task(title="Voice Note", description=text)
```

**Data Flow**:
```
Audio → Whisper/WhisperX → Text → Architect (Task/Note Creation)
```

---

### 7. Stable Diffusion & ComfyUI - Local Image Generation

**Purpose**: Generate images locally without cloud APIs.

**Key Features**:
- **Stable Diffusion**: Open-source image generation model
- **ComfyUI**: Node-based UI for advanced workflows (ControlNet, LoRA, upscaling)
- Full control over prompts and parameters
- Fast iteration with local GPU
- No per-image costs

**Installation**:
```bash
# ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
python main.py

# Access UI at http://localhost:8188
```

**Integration with Architect**:
```python
# Generate diagrams or mockups via API
import requests
import json

prompt = {
    "prompt": "architecture diagram showing microservices with API gateway",
    "negative_prompt": "blurry, low quality",
    "steps": 30,
    "cfg_scale": 7
}

response = requests.post('http://localhost:8188/api/prompt', json=prompt)
```

**Data Flow**:
```
Text Prompt → ComfyUI (localhost:8188) → Stable Diffusion → Image → Architect
```

---

## Unified Data Flow

### Scenario 1: Code Review with Local LLMs

```
┌──────────────────────────────────────────────────────────────┐
│ 1. GitHub webhook notifies Architect of new PR              │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Architect sends PR diff to n8n workflow                  │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. n8n fetches relevant docs from AnythingLLM (RAG)        │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. n8n sends context + diff to Ollama (CodeLlama)          │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Ollama generates review with suggestions                 │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. n8n posts review to GitHub and creates Architect task    │
└──────────────────────────────────────────────────────────────┘
```

**Cost**: $0.00 (all local)
**Latency**: ~5-15 seconds
**Privacy**: Full control (no data leaves your network)

---

### Scenario 2: Hybrid Approach (Local → Remote Fallback)

```
┌──────────────────────────────────────────────────────────────┐
│ 1. User requests code generation via Architect              │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Architect tries Ollama (llama3.2) first                  │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ├── ✓ Success? → Return code
                        │
                        └── ✗ Failure/Timeout?
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Fallback to Claude Sonnet 4.5 (remote)                   │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        └── ✗ Still failing?
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Final fallback to OpenAI GPT-4                           │
└──────────────────────────────────────────────────────────────┘
```

**Priority Order**:
1. **Local LLM** (Ollama/LocalAI) - Free, fast, private
2. **Claude API** - High quality, moderate cost
3. **OpenAI API** - Widely compatible, higher cost

---

## Configuration

### Environment Variables

Add to `.env` or `config/env_config.py`:

```bash
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

# LocalAI
LOCALAI_BASE_URL=http://localhost:8080/v1
LOCALAI_API_KEY=not-needed

# n8n
N8N_WEBHOOK_URL=http://localhost:5678/webhook/architect

# AnythingLLM
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-api-key

# Whisper
WHISPER_MODEL=base  # tiny, base, small, medium, large

# Stable Diffusion
COMFYUI_URL=http://localhost:8188

# Fallback to remote LLMs
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-proj-xxxxx

# Failover settings
LLM_FAILOVER_ENABLED=true
LLM_DEFAULT_PROVIDER=ollama
LLM_FALLBACK_ORDER=ollama,claude,openai
```

### YAML Configuration (`config/llm_providers.yaml`)

```yaml
providers:
  ollama:
    enabled: true
    host: ${OLLAMA_HOST}
    model: llama3.2
    timeout: 60
    priority: 1  # Try first

  localai:
    enabled: true
    base_url: ${LOCALAI_BASE_URL}
    model: llama3
    timeout: 60
    priority: 2  # Try second

  claude:
    enabled: true
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-sonnet-4-5-20250929
    timeout: 120
    priority: 3  # Try third

  openai:
    enabled: true
    api_key: ${OPENAI_API_KEY}
    model: gpt-4-turbo
    timeout: 120
    priority: 4  # Last resort

failover:
  enabled: true
  retry_on_error: true
  max_retries: 2
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 300
```

---

## Benefits of Local-First Architecture

### Cost Savings

| Task | Remote (Claude) | Local (Ollama) | Savings |
|------|----------------|----------------|---------|
| 1M tokens input | $3.00 | $0.00 | 100% |
| 1M tokens output | $15.00 | $0.00 | 100% |
| 10k code reviews/month | ~$450 | $0.00 | **$450/mo** |
| 100k chat messages/month | ~$3,000 | $0.00 | **$3,000/mo** |

### Privacy & Security

- **No data transmission** to third parties
- **Full audit trail** of prompts and responses
- **GDPR/HIPAA compliant** (data never leaves your infrastructure)
- **Offline capable** (no internet dependency)

### Performance

- **Lower latency** (no network round-trip)
- **No rate limits** (unlimited requests)
- **Predictable performance** (dedicated hardware)
- **Fine-tuning control** (customize models for your use case)

### Resilience

- **No vendor lock-in** (switch models anytime)
- **No API outages** (local infrastructure always available)
- **Graceful degradation** (local → remote fallback)
- **Cost control** (budget caps, usage tracking)

---

## Implementation Roadmap

### Phase 1: Setup Local Infrastructure (Week 1-2)

- [ ] Install Ollama and pull models (`llama3.2`, `codellama`)
- [ ] Deploy LocalAI with OpenAI-compatible API
- [ ] Set up OpenWebUI for user testing
- [ ] Install AnythingLLM and ingest project docs

### Phase 2: Integration with Architect (Week 3-4)

- [ ] Implement `UnifiedLLMClient` with failover logic
- [ ] Add Ollama provider adapter
- [ ] Add LocalAI provider adapter
- [ ] Update `workers/crawler_service.py` to use local LLMs
- [ ] Add circuit breakers for each provider

### Phase 3: Advanced Workflows (Week 5-6)

- [ ] Deploy n8n and create agent workflows
- [ ] Set up Whisper for voice task creation
- [ ] Configure ComfyUI for diagram generation
- [ ] Build RAG pipeline with AnythingLLM

### Phase 4: Monitoring & Optimization (Week 7-8)

- [ ] Add LLM provider dashboard panel
- [ ] Track cost savings vs remote LLMs
- [ ] Tune failover thresholds
- [ ] Benchmark local vs remote latency
- [ ] Document best practices

---

## Troubleshooting

### Ollama Not Responding

```bash
# Check if service is running
ps aux | grep ollama

# Restart Ollama
killall ollama
ollama serve

# Test connectivity
curl http://localhost:11434/api/tags
```

### n8n Workflow Fails

```bash
# Check n8n logs
docker logs n8n

# Verify webhook URL
curl -X POST http://localhost:5678/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### AnythingLLM Can't Connect to Ollama

- Ensure Ollama is running: `curl http://localhost:11434`
- Check firewall rules allow local connections
- In AnythingLLM settings, use `http://host.docker.internal:11434` if running in Docker

### Low Performance on Local Models

- **Use GPU acceleration**: Install CUDA/ROCm drivers
- **Reduce model size**: Use quantized models (Q4, Q5)
- **Increase context window**: May improve quality but slower
- **Adjust batch size**: Tune for your GPU memory

---

## Next Steps

1. **Review the LLM Provider Failover Implementation Plan** in `/Users/jgirmay/.claude/plans/zesty-toasting-sunset.md`
2. **Start with Ollama setup**: `ollama pull llama3.2 && ollama pull codellama`
3. **Test OpenWebUI**: Visit `http://localhost:3000` after deployment
4. **Ingest project docs into AnythingLLM**: Create RAG workspace for Architect
5. **Monitor usage**: Track local vs remote LLM requests in dashboard

---

## Resources

- [Ollama Documentation](https://ollama.com/docs)
- [LocalAI GitHub](https://github.com/mudler/LocalAI)
- [OpenWebUI Docs](https://docs.openwebui.com)
- [n8n Workflow Templates](https://n8n.io/workflows)
- [AnythingLLM Guide](https://docs.anythingllm.com)
- [Whisper GitHub](https://github.com/openai/whisper)
- [ComfyUI Wiki](https://github.com/comfyanonymous/ComfyUI/wiki)

---

**Last Updated**: 2026-02-04
**Maintainer**: Architect Dashboard Team
