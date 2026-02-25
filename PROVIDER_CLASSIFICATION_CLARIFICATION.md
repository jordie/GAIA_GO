# Provider Classification Clarification

**Issue**: Documentation incorrectly labeled Comet as "API" when it's browser automation
**Status**: ✅ CORRECTED

---

## Correct Provider Classification

### By Implementation Type

| Provider | Type | Implementation | Cost |
|----------|------|----------------|------|
| **Claude** | Cloud API | REST API (Anthropic) | Premium ($3/$15/M) |
| **OpenAI** | Cloud API | REST API (OpenAI) | Expensive ($10/$30/M) |
| **Gemini** | Cloud API | REST API (Google) | Affordable ($0.15/$0.60/M) |
| **Ollama** | Local HTTP | HTTP API (Local) | Free |
| **AnythingLLM** | Local HTTP | HTTP API (Local) | Free |
| **Comet** | **Browser Automation** | AppleScript/WebSocket (macOS) | Free* |

**Key Difference**: Comet is **NOT an API** - it's browser automation that interacts with the Comet browser's Perplexity sidebar.

---

## Detailed Provider Types

### Cloud APIs (REST, direct LLM calls)
```
Claude   → Direct API call to Anthropic servers → Response
OpenAI   → Direct API call to OpenAI servers → Response
Gemini   → Direct API call to Google servers → Response
```

### Local HTTP APIs (HTTP interface, local or self-hosted)
```
Ollama      → HTTP request to localhost:11434 → Response
AnythingLLM → HTTP request to localhost:3001 → Response
```

### Browser Automation (macOS only, UI-based)
```
Comet → AppleScript activates browser
     → Opens Perplexity sidebar (Option+A)
     → Types question (System Events keystroke)
     → Submits (Enter key)
     → Waits for response
     → Reads from sidebar
     → Returns text
```

---

## Why Comet is Different

### APIs (Other 5 Providers)
- **Direct interaction**: Send JSON, get JSON back
- **Fast**: 1-5 seconds typically
- **Stateless**: Each request independent
- **Scriptable**: Can batch, pipeline, parallelize
- **Reliable**: Consistent responses

### Browser Automation (Comet)
- **UI-based interaction**: Controls keyboard/mouse/window
- **Slow**: 5-15 seconds (UI rendering, waits)
- **Stateful**: Browser state matters
- **Limited**: macOS only (uses AppleScript)
- **Fragile**: Depends on UI layout not changing

---

## Correct Terminology

### Old (Incorrect) Classification
```
6 APIs:
- Claude (API)
- Ollama (Local)
- OpenAI (API)
- Gemini (API)
- AnythingLLM (Local RAG)
- Comet (API)  ← WRONG! Not an API
```

### New (Correct) Classification
```
5 API Providers + 1 Browser Automation:

APIs (5):
- Claude (Cloud REST API)
- Ollama (Local HTTP API)
- OpenAI (Cloud REST API)
- Gemini (Cloud REST API)
- AnythingLLM (Local HTTP API)

Browser Automation (1):
- Comet (macOS browser automation)
```

---

## Updated Provider Descriptions

### For System Documentation

**Claude**
- Type: Cloud REST API
- Provider: Anthropic
- Quality: ⭐⭐⭐⭐⭐ (Best)
- Cost: $3/$15 per 1M tokens
- Speed: Fast (1-3s)
- Use: Complex reasoning, high-quality work

**OpenAI (GPT-4)**
- Type: Cloud REST API
- Provider: OpenAI
- Quality: ⭐⭐⭐⭐⭐ (Excellent)
- Cost: $10/$30 per 1M tokens
- Speed: Fast (1-3s)
- Use: Fallback to Claude, general tasks

**Gemini**
- Type: Cloud REST API
- Provider: Google
- Quality: ⭐⭐⭐⭐ (Very Good)
- Cost: $0.15/$0.60 per 1M tokens
- Speed: Fast (1-3s)
- Use: Cost-optimized tasks (95% savings)

**Ollama**
- Type: Local HTTP API
- Provider: Self-hosted
- Quality: ⭐⭐⭐ (Good for local)
- Cost: Free
- Speed: Fast (local)
- Use: Private, offline work

**AnythingLLM**
- Type: Local HTTP API (RAG)
- Provider: Self-hosted
- Quality: ⭐⭐⭐⭐ (Good with RAG)
- Cost: Free
- Speed: Medium (RAG processing)
- Use: Document Q&A, knowledge base

**Comet**
- Type: **Browser Automation** (NOT API)
- Interface: AppleScript (macOS) / WebSocket
- Quality: ⭐⭐⭐⭐ (Uses Perplexity AI)
- Cost: Free (requires Perplexity sub)
- Speed: Slow (5-15s, UI-based)
- Use: Web research, form automation

---

## System Diagram (Corrected)

### Provider Types in UnifiedLLMClient

```
┌─────────────────────────────────────────────────────┐
│         UnifiedLLMClient (6 Providers)              │
└──────────────────┬──────────────────────────────────┘
                   │
      ┌────────────┼────────────┬──────────────┐
      ▼            ▼            ▼              ▼
  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────┐
  │ Cloud   │  │ Local   │  │ Browser │  │   (Others)   │
  │  APIs   │  │  APIs   │  │Automation│  │              │
  └────┬────┘  └────┬────┘  └────┬────┘  └──────────────┘
       │            │             │
   ┌───┴────┬──┐ ┌──┴──┐    ┌────┴──┐
   │        │  │ │     │    │       │
   ▼        ▼  ▼ ▼     ▼    ▼       ▼
Claude  Gemini OpenAI Ollama AnythingLLM Comet
                                    (Not an API)
```

---

## Code Implications

### CometProvider Class
```python
class CometProvider(BaseProvider):
    """Comet browser automation provider (NOT an API)."""

    def _create_completion_impl(self, messages, **kwargs):
        # This doesn't call an API
        # Instead, it:
        # 1. Uses AppleScript to control macOS
        # 2. Activates Comet browser
        # 3. Opens Perplexity sidebar
        # 4. Types and submits query
        # 5. Waits for UI response
        # 6. Extracts text from sidebar
        # 7. Returns response
```

### Why It's Still a "Provider"
Even though Comet isn't an API, it's called a "provider" because:
- Fits the same interface as other providers
- Implements `_create_completion_impl()`
- Returns `LLMResponse` in same format
- Can be used in failover chain
- Has cost tracking (free)
- Can be selected/routed like others

---

## Failover Chain (Corrected Classification)

```
1. Claude (Cloud API - Premium quality)
   ↓
2. Ollama (Local API - Free)
   ↓
3. AnythingLLM (Local API - Free RAG)
   ↓
4. Gemini (Cloud API - Cheap, 95% savings)
   ↓
5. Comet (Browser Automation - Free research)
   ↓
6. OpenAI (Cloud API - Expensive fallback)
```

---

## Performance Characteristics

### APIs (Fast)
| Provider | Latency | Throughput | Good For |
|----------|---------|-----------|----------|
| Claude | 1-3s | 100s req/min | Complex work |
| Gemini | 1-3s | 100s req/min | Cost optimization |
| OpenAI | 1-3s | 100s req/min | General tasks |
| Ollama | <1s | 1000s req/min | Batch work |
| AnythingLLM | 2-5s | 100s req/min | RAG queries |

### Browser Automation (Slow)
| Provider | Latency | Throughput | Good For |
|----------|---------|-----------|----------|
| Comet | 5-15s | 1 req/min | Web research |

---

## Updated Status Matrix

### Provider Status (Corrected)

| Provider | Type | Status | Integration | Quality |
|----------|------|--------|-------------|---------|
| Claude | Cloud API | ✅ | ✅ | ⭐⭐⭐⭐⭐ |
| Gemini | Cloud API | ✅ | ✅ | ⭐⭐⭐⭐ |
| OpenAI | Cloud API | ✅ | ✅ | ⭐⭐⭐⭐⭐ |
| Ollama | Local API | ✅ | ✅ | ⭐⭐⭐ |
| AnythingLLM | Local API | ✅ | ✅ | ⭐⭐⭐⭐ |
| Comet | Browser Automation | ✅ | ✅ | ⭐⭐⭐⭐ |

---

## Why This Matters

### Correct Classification Helps
1. **Selection**: Choose right tool for job
   - Task needs API speed? Use Claude/Gemini/OpenAI
   - Task needs privacy? Use Ollama/AnythingLLM
   - Task needs web research? Use Comet

2. **Expectations**: Understand limitations
   - Comet is slow (UI-based, not API)
   - Comet is macOS-only
   - Comet needs browser window visible
   - Ollama is free but needs local setup

3. **Optimization**: Route correctly
   - Don't route high-throughput tasks to Comet
   - Use Comet only for web research
   - Use APIs for general work
   - Use local for private/offline

4. **Documentation**: Clear communication
   - "Browser automation" vs "API" very different
   - Users understand tradeoffs
   - Prevents misuse/frustration

---

## Recommendations

### Update Documentation Everywhere
1. ❌ "6 API providers" → ✅ "5 API providers + browser automation"
2. ❌ "Comet (API)" → ✅ "Comet (Browser Automation)"
3. Add note: "Not all providers are APIs - Comet uses browser automation"
4. Include performance characteristics table

### Update Code Comments
```python
# BEFORE: Misleading
# 6 LLM providers: Claude, Ollama, OpenAI, Gemini, AnythingLLM, Comet

# AFTER: Correct
# 5 LLM APIs + 1 browser automation:
# - Cloud APIs: Claude, Gemini, OpenAI
# - Local APIs: Ollama, AnythingLLM
# - Browser Automation: Comet (Perplexity web UI)
```

### Update Configuration
```yaml
# Add clarifying comments
providers:
  # Cloud REST APIs
  claude: ...
  gemini: ...
  openai: ...

  # Local HTTP APIs
  ollama: ...
  anythingllm: ...

  # Browser Automation (not an API!)
  comet: ...  # Uses AppleScript/UI, not HTTP API
```

---

## Summary

**Correction**: Comet is **not an API provider** - it's **browser automation**

**Key Points**:
- 5 LLM APIs (Claude, Gemini, OpenAI, Ollama, AnythingLLM)
- 1 Browser Automation (Comet)
- All work together in same failover chain
- Each has different characteristics
- Use correct tool for job

**Classification Matters** for:
- Setting expectations
- Performance planning
- Proper routing
- User understanding
- System documentation

---

**Status**: ✅ CLARIFIED
**Action**: Update all documentation and code comments
**Impact**: Better user understanding, correct expectations
