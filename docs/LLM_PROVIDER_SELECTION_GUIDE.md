# LLM Provider Selection Guide

Comprehensive guide for choosing the right LLM provider for different tasks and scenarios.

## Table of Contents

1. [Provider Overview](#provider-overview)
2. [Selection Criteria](#selection-criteria)
3. [Provider Comparison](#provider-comparison)
4. [Use Case Recommendations](#use-case-recommendations)
5. [Cost Optimization](#cost-optimization)
6. [Performance Tuning](#performance-tuning)
7. [Monitoring and Metrics](#monitoring-and-metrics)

---

## Provider Overview

### Available Providers

| Provider | Type | Cost | Speed | Quality | Best For |
|----------|------|------|-------|---------|----------|
| **Claude** | API | $$$  | Fast | Excellent | Complex reasoning, code generation |
| **Ollama** | Local | Free | Very Fast | Good | Simple tasks, high volume |
| **AnythingLLM** | Local | Free | Fast | Good | Document Q&A, RAG |
| **Gemini** | API | $$   | Fast | Very Good | Multimodal tasks, web search |
| **OpenAI** | API | $$$  | Fast | Excellent | General purpose, complex tasks |

### Automatic Failover Chain

The system automatically tries providers in this order:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   Request → Claude (Primary)                    │
│              │                                  │
│              ├─ Success? → Return result        │
│              │                                  │
│              └─ Failed/Busy? → Try Ollama       │
│                                  │              │
│                                  ├─ Success?    │
│                                  │              │
│                                  └─ Failed? →   │
│                                     AnythingLLM │
│                                       │         │
│                                       ├─ Success│
│                                       │         │
│                                       └─ Failed?│
│                                         Gemini  │
│                                           │     │
│                                           └─ →  │
│                                           OpenAI│
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Selection Criteria

### When to Choose Each Provider

#### Claude (Anthropic)
**Choose when you need**:
- Complex reasoning and analysis
- High-quality code generation
- Long context understanding (200K tokens)
- JSON mode and structured output
- API reliability and support

**Avoid when**:
- Budget is constrained
- Simple/repetitive tasks
- Extremely high volume (>10K requests/day)

**Example Tasks**:
- Code review and refactoring
- Architecture design
- Complex data analysis
- Technical writing
- Debugging assistance

#### Ollama (Local)
**Choose when you need**:
- Zero cost operation
- Fast response times (<1s)
- Privacy (data never leaves server)
- High request volume
- Simple/straightforward tasks

**Avoid when**:
- Complex reasoning required
- Long context needed (>8K tokens)
- Specialized knowledge required
- Critical accuracy needed

**Example Tasks**:
- Log parsing
- Simple code generation
- Data extraction
- Text classification
- Repetitive tasks

#### AnythingLLM (Local RAG)
**Choose when you need**:
- Document Q&A
- Knowledge base queries
- Context-aware responses
- Zero cost operation
- Privacy for sensitive docs

**Avoid when**:
- Documents not yet indexed
- Real-time web data needed
- Pure reasoning tasks
- Code generation

**Example Tasks**:
- Documentation search
- Internal knowledge queries
- Policy/procedure lookups
- Historical data analysis

#### Gemini (Google)
**Choose when you need**:
- Multimodal inputs (image + text)
- Web search integration
- Good balance of cost/quality
- Fast prototyping

**Avoid when**:
- Maximum quality required
- No internet access
- Sensitive/confidential data

**Example Tasks**:
- Image analysis
- Web research tasks
- General Q&A
- Content generation

#### OpenAI (GPT-4)
**Choose when you need**:
- Fallback for critical tasks
- Proven reliability
- Broad capability

**Avoid when**:
- Cost is primary concern
- Anthropic or local options work

**Example Tasks**:
- Last resort for complex tasks
- A/B testing vs Claude
- Legacy integrations

---

## Provider Comparison

### Performance Comparison

| Metric | Claude | Ollama | AnythingLLM | Gemini | OpenAI |
|--------|--------|--------|-------------|--------|--------|
| **Response Time** | 2-5s | 0.5-1s | 1-2s | 2-4s | 2-5s |
| **Context Window** | 200K | 8K | 32K | 1M | 128K |
| **Code Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Reasoning** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Reliability** | 99.9% | 99.5% | 95% | 99.8% | 99.9% |
| **Cost (1M tokens)** | $15 | $0 | $0 | $7 | $30 |

### Cost Analysis

**Example Monthly Usage** (100K requests):

| Provider | Input Tokens | Output Tokens | Total Cost |
|----------|--------------|---------------|------------|
| Claude | 50M | 10M | $750 + $150 = $900 |
| Ollama | 50M | 10M | $0 (electricity ~$10) |
| AnythingLLM | 50M | 10M | $0 (electricity ~$10) |
| Gemini | 50M | 10M | $350 + $70 = $420 |
| OpenAI | 50M | 10M | $1500 + $300 = $1800 |

**Cost Optimization Strategy**:
1. Route 80% of simple tasks to Ollama ($0)
2. Route 15% of complex tasks to Claude ($135)
3. Route 5% edge cases to Gemini ($21)
4. **Total**: $156/month vs $900 all-Claude

**Savings**: 83%

---

## Use Case Recommendations

### Code Generation

**Recommended**: Claude > OpenAI > Ollama

**Why**: Code quality and reasoning matter most

**Configuration**:
```python
client = UnifiedLLMClient()
response = client.messages.create(
    model="claude-sonnet-4-5",
    messages=[{"role": "user", "content": "Generate a REST API..."}],
    temperature=0.2  # Lower for consistent code
)
```

### Log Analysis

**Recommended**: Ollama > Claude

**Why**: Simple extraction, high volume, speed matters

**Configuration**:
```python
# Use Ollama directly for speed
response = ollama_client.generate(
    model="llama3.2",
    prompt="Extract error codes from:\n" + logs,
    temperature=0  # Deterministic extraction
)
```

### Documentation Q&A

**Recommended**: AnythingLLM > Claude

**Why**: Pre-indexed docs, fast retrieval, zero cost

**Configuration**:
```python
# Query existing knowledge base
response = anythingllm_client.chat(
    workspace="project-docs",
    message="How do I configure SSL?",
    mode="query"
)
```

### Architecture Design

**Recommended**: Claude > OpenAI > Gemini

**Why**: Complex reasoning, nuanced trade-offs

**Configuration**:
```python
response = client.messages.create(
    model="claude-opus-4-5",  # Use Opus for critical design
    messages=[{"role": "user", "content": "Design a scalable..."}],
    temperature=0.7,  # Balanced creativity
    max_tokens=4096   # Allow detailed response
)
```

### Image Analysis

**Recommended**: Gemini > Claude

**Why**: Native multimodal support, good quality

**Configuration**:
```python
response = gemini_client.generate(
    model="gemini-pro-vision",
    contents=[
        {"text": "What's in this screenshot?"},
        {"image": base64_image}
    ]
)
```

### Batch Processing

**Recommended**: Ollama > Claude (with batching API)

**Why**: High volume, cost matters

**Strategy**:
1. Process 90% with Ollama for speed/cost
2. Route failures to Claude for accuracy
3. Monitor quality metrics
4. Adjust ratio based on success rate

---

## Cost Optimization

### Strategy 1: Tiered Routing

Route tasks based on complexity:

```python
def select_provider(task):
    complexity = analyze_complexity(task)

    if complexity == "simple":
        return "ollama"  # $0, 80% of tasks
    elif complexity == "medium":
        return "claude"  # $$$, 15% of tasks
    else:
        return "claude"  # $$$, 5% of tasks
```

**Expected savings**: 60-80%

### Strategy 2: Caching

Cache common queries to avoid duplicate API calls:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_llm_response(prompt_hash):
    return client.messages.create(...)
```

**Expected savings**: 40-60% for repetitive queries

### Strategy 3: Prompt Optimization

Shorter prompts = lower cost:

**Before** (1000 tokens):
```
Please analyze this code and provide detailed feedback on...
[include entire file]
```

**After** (200 tokens):
```
Review this function for bugs:
[include only relevant function]
```

**Expected savings**: 80% on input tokens

### Strategy 4: Response Length Limits

Set appropriate `max_tokens`:

```python
# Bad: Always request max
max_tokens=4096  # Costs more even if 100 tokens would suffice

# Good: Request what you need
max_tokens=500   # Sufficient for most responses
```

**Expected savings**: 30-50% on output tokens

### Strategy 5: Use Streaming

Stream responses and stop early when you have enough:

```python
for chunk in client.messages.stream(...):
    if is_complete(accumulated_text):
        break  # Stop early, pay less
```

**Expected savings**: 10-20% on output tokens

---

## Performance Tuning

### Latency Optimization

**Goal**: Minimize response time

**Techniques**:

1. **Use Ollama for Speed**:
   - Average: 0.5s vs 3s for API providers
   - Best for: Simple tasks, high QPS

2. **Parallel Requests**:
   ```python
   import asyncio

   async def process_batch(tasks):
       responses = await asyncio.gather(*[
           client.messages.create_async(...)
           for task in tasks
       ])
       return responses
   ```

3. **Local Caching**:
   - Cache common responses
   - Reduce network round-trips
   - Use Redis or in-memory cache

4. **Connection Pooling**:
   - Reuse HTTP connections
   - Reduce TLS handshake overhead

### Quality Optimization

**Goal**: Maximize response quality

**Techniques**:

1. **Use Higher-Tier Models**:
   - Claude Opus vs Sonnet for critical tasks
   - GPT-4 vs GPT-3.5

2. **Adjust Temperature**:
   ```python
   # Factual/deterministic: low temp
   temperature=0.2

   # Creative/varied: high temp
   temperature=0.8
   ```

3. **Few-Shot Examples**:
   ```python
   messages = [
       {"role": "user", "content": "Example input 1"},
       {"role": "assistant", "content": "Example output 1"},
       {"role": "user", "content": "Example input 2"},
       {"role": "assistant", "content": "Example output 2"},
       {"role": "user", "content": "Actual query"}
   ]
   ```

4. **Iterative Refinement**:
   - Generate initial response
   - Ask LLM to critique it
   - Ask LLM to improve based on critique

### Reliability Optimization

**Goal**: Minimize failures and downtime

**Techniques**:

1. **Circuit Breaker** (Already Implemented):
   - Automatically skip failing providers
   - Timeout: 60s before retry
   - Threshold: 5 failures opens circuit

2. **Retry Logic**:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(stop=stop_after_attempt(3), wait=wait_exponential())
   def call_llm(prompt):
       return client.messages.create(...)
   ```

3. **Timeout Configuration**:
   ```python
   client = UnifiedLLMClient(
       timeout=30,  # 30 second timeout
       max_retries=3
   )
   ```

4. **Health Monitoring**:
   - Monitor provider success rates
   - Alert on degradation
   - Auto-failover to backup

---

## Monitoring and Metrics

### Key Metrics to Track

#### 1. Success Rate
```python
success_rate = successful_requests / total_requests * 100
```

**Target**: >95%
**Alert**: <90%

#### 2. Average Latency
```python
avg_latency = sum(response_times) / len(response_times)
```

**Target**: <3s
**Alert**: >10s

#### 3. Cost per Request
```python
cost_per_request = total_cost / total_requests
```

**Target**: <$0.01
**Alert**: >$0.05

#### 4. Failover Rate
```python
failover_rate = failover_count / total_requests * 100
```

**Target**: <5%
**Alert**: >20%

#### 5. Token Usage
```python
tokens_per_request = total_tokens / total_requests
```

**Target**: <2000 tokens
**Alert**: >5000 tokens

### Dashboard Access

Navigate to `/llm-metrics` to view:

- **Provider Comparison**: Success rates, costs, latency by provider
- **Cost Distribution**: Pie chart of spend by provider
- **Request Volume**: Requests over time
- **Token Usage**: Input/output token trends
- **Failover History**: When and why failovers occurred
- **Circuit Breaker Status**: Open/closed state per provider

### Alerts Configuration

Set up alerts for critical thresholds:

```bash
POST /api/llm-metrics/alerts/configure
{
  "success_rate": {
    "warning": 90,
    "critical": 80
  },
  "latency_p95": {
    "warning": 5000,
    "critical": 10000
  },
  "cost_per_request": {
    "warning": 0.03,
    "critical": 0.10
  }
}
```

### Manual Circuit Breaker Control

**Check Status**:
```bash
GET /api/llm-metrics/circuit-breakers
```

**Reset All**:
```bash
POST /api/llm-metrics/reset-circuits
```

**Reset Specific Provider**:
```bash
POST /api/llm-metrics/reset-circuit/claude
```

---

## Decision Tree

Use this decision tree to select the right provider:

```
Is the task simple/repetitive?
├─ Yes → Is privacy critical?
│   ├─ Yes → Use Ollama (local, free, fast)
│   └─ No → Use Ollama (local, free, fast)
│
└─ No → Does it involve images/multimodal?
    ├─ Yes → Use Gemini (native multimodal support)
    │
    └─ No → Is it document Q&A?
        ├─ Yes → Use AnythingLLM (RAG, fast)
        │
        └─ No → Is highest quality required?
            ├─ Yes → Use Claude Opus (best reasoning)
            │
            └─ No → Is cost very constrained?
                ├─ Yes → Use Gemini (good balance)
                └─ No → Use Claude Sonnet (default)
```

---

## Best Practices

### DO:
✅ Start with Ollama for new tasks, upgrade if needed
✅ Monitor costs daily via `/llm-metrics`
✅ Set appropriate `max_tokens` limits
✅ Use caching for repeated queries
✅ Test failover chain regularly
✅ Review provider metrics weekly
✅ Adjust routing based on success rates

### DON'T:
❌ Always use Claude for everything (expensive)
❌ Ignore failover events (indicates issues)
❌ Set unlimited `max_tokens`
❌ Skip caching for common queries
❌ Disable circuit breakers
❌ Ignore cost alerts
❌ Use API providers for simple tasks

---

## Troubleshooting

### High Costs

**Symptom**: Monthly bill higher than expected

**Check**:
```bash
GET /api/llm-metrics/summary
```

**Solutions**:
1. Review cost distribution by provider
2. Identify high-cost endpoints
3. Route more tasks to Ollama
4. Implement caching
5. Reduce `max_tokens` limits

### Low Success Rate

**Symptom**: Many failed requests

**Check**:
```bash
GET /api/llm-metrics/providers
```

**Solutions**:
1. Check circuit breaker status
2. Review error messages
3. Verify API keys valid
4. Check provider service status
5. Increase timeout limits
6. Reset circuit breakers if needed

### Slow Responses

**Symptom**: High latency (>10s)

**Check**:
```bash
GET /api/llm-metrics/latency
```

**Solutions**:
1. Use Ollama for simple tasks
2. Reduce prompt length
3. Lower `max_tokens`
4. Check network connectivity
5. Use streaming for large responses

---

## Appendix

### Environment Variables

```bash
# Enable/disable failover
export LLM_FAILOVER_ENABLED=true

# Set default provider
export LLM_DEFAULT_PROVIDER=claude

# API keys
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...

# Ollama endpoint
export OLLAMA_ENDPOINT=http://localhost:11434

# AnythingLLM endpoint
export ANYTHINGLLM_ENDPOINT=http://localhost:3001
```

### Provider Models

| Provider | Model Name | Context | Best For |
|----------|------------|---------|----------|
| Claude | `claude-sonnet-4-5` | 200K | General purpose |
| Claude | `claude-opus-4-5` | 200K | Complex reasoning |
| Ollama | `llama3.2` | 8K | Simple tasks |
| Ollama | `codellama` | 16K | Code generation |
| Gemini | `gemini-pro` | 1M | General purpose |
| Gemini | `gemini-pro-vision` | 1M | Image analysis |
| OpenAI | `gpt-4` | 128K | Complex tasks |
| OpenAI | `gpt-3.5-turbo` | 16K | Simple tasks |

### API Reference

See `CLAUDE.md` for complete API documentation.

---

**Last Updated**: 2026-02-10
**Version**: 1.0
**Maintainer**: Architect Team
