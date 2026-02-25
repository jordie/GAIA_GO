# LLM Provider Comparison Guide

Quick comparison of Claude, Gemini, Ollama, and Codex providers.

## Quick Summary

| Provider | Cost | Speed | Quality | Best For |
|----------|------|-------|---------|----------|
| **Claude** | Paid | Fast | Excellent | Complex reasoning, code |
| **Gemini** | Paid | Fast | Very Good | General tasks, balanced |
| **Ollama** | Free | Medium | Good | Local, offline, prototyping |
| **Codex** | Paid | Fast | Very Good | Code generation |

## Testing Each Provider

### 1. Claude
**Strengths:** Best reasoning, excellent code analysis, careful thinking
**Session:** `gaia_claude_1` (or 2, 3)

```bash
# Test Claude
tmux send-keys -t gaia_claude_1 "What is the best way to optimize a Python loop processing 1M items? Give me 3 approaches with trade-offs." Enter
```

**Test Prompts:**
- "Explain REST APIs in detail for someone new to programming"
- "Debug this Python code and explain the issue: def f(x): return x[10] if x else 0"
- "Design a database schema for a blog platform"

### 2. Gemini
**Strengths:** Balanced quality, good for general tasks, good code examples
**Session:** `gaia_gemini_1-5` (5 instances available)

```bash
# Test Gemini
tmux send-keys -t gaia_gemini_1 "Write a Flask REST API endpoint with proper error handling" Enter
```

**Test Prompts:**
- "Compare SQL and NoSQL databases"
- "Write a JavaScript function that fetches data from an API with retry logic"
- "Explain machine learning in simple terms"

### 3. Ollama (Local)
**Strengths:** Free, runs locally, no API key needed, fast for simple queries
**Session:** `gaia_ollama_1-3`

```bash
# Test Ollama
tmux send-keys -t gaia_ollama_1 "What is Python?" Enter
```

**Test Prompts:**
- "Write a hello world program"
- "Explain what a function is"
- "List 5 Python libraries and what they do"

### 4. Codex (OpenAI)
**Strengths:** Excellent code generation, fast, practical implementations
**Session:** `gaia_codex_1-3`

```bash
# Test Codex
tmux send-keys -t gaia_codex_1 "Generate a Python function that validates email addresses using regex" Enter
```

**Test Prompts:**
- "Write a sorting algorithm in Python"
- "Create a class for managing a shopping cart"
- "Generate a SQL query for finding users with multiple orders"

## Interactive Testing

Attach to any session to test interactively:

```bash
# Claude
tmux attach-session -t gaia_claude_1

# Gemini
tmux attach-session -t gaia_gemini_1

# Ollama
tmux attach-session -t gaia_ollama_1

# Codex
tmux attach-session -t gaia_codex_1
```

Exit with `Ctrl+D` or `/quit`.

## Comparison Test Suite

Run automated comparisons:

```bash
# Quick test across all providers
python3 tools/provider_comparison_simple.py --providers claude gemini ollama codex --complexity quick

# Moderate complexity
python3 tools/provider_comparison_simple.py --providers claude gemini ollama codex --complexity moderate

# Single provider
python3 tools/provider_comparison_simple.py --providers claude --limit 3
```

## Key Differences

### Response Style

**Claude**
- Thorough, detailed explanations
- Considers edge cases
- Good for complex problem-solving
- Example: Takes time to explain reasoning

**Gemini**
- Balanced, structured responses
- Good code examples
- Practical approach
- Example: Gets to the point quickly

**Ollama (Local)**
- Simpler responses
- Good for straightforward questions
- Fast for basic queries
- Example: Shorter, more concise

**Codex**
- Code-focused
- Practical implementations
- Good for hands-on problems
- Example: Prefers showing code over explaining

### Quality by Task Type

#### Code Generation
1. Codex ⭐⭐⭐⭐⭐
2. Claude ⭐⭐⭐⭐⭐
3. Gemini ⭐⭐⭐⭐
4. Ollama ⭐⭐⭐

#### Explanations
1. Claude ⭐⭐⭐⭐⭐
2. Gemini ⭐⭐⭐⭐
3. Codex ⭐⭐⭐⭐
4. Ollama ⭐⭐⭐

#### Reasoning/Problem Solving
1. Claude ⭐⭐⭐⭐⭐
2. Gemini ⭐⭐⭐⭐
3. Codex ⭐⭐⭐⭐
4. Ollama ⭐⭐⭐

#### Local/Offline Use
1. Ollama ⭐⭐⭐⭐⭐ (Only option)
2. Others - Requires API calls

## Cost Estimates

**Per 1M tokens:**
- Claude: $3 (input) - $15 (output)
- Gemini: $0.50 (input) - $1.50 (output)
- Codex (GPT-4): $0.03 (input) - $0.06 (output)
- Ollama: $0 (local, just compute)

## Recommendation

- **Best for Production:** Claude (quality) + Gemini (cost-effective backup)
- **Best for Development:** Claude + Ollama (fast local testing)
- **Best for Code:** Codex (specialized) + Claude (reasoning)
- **Best for Cost:** Gemini + Ollama
- **Best for Privacy:** Ollama (local only)

## Manual Testing Example

Test all 4 providers with the same prompt:

```bash
# Open 4 terminals or tmux windows
tmux new-window -t gaia:0 -n claude && tmux send-keys -t gaia:0 "tmux attach-session -t gaia_claude_1" Enter
tmux new-window -t gaia:1 -n gemini && tmux send-keys -t gaia:1 "tmux attach-session -t gaia_gemini_1" Enter
tmux new-window -t gaia:2 -n ollama && tmux send-keys -t gaia:2 "tmux attach-session -t gaia_ollama_1" Enter
tmux new-window -t gaia:3 -n codex && tmux send-keys -t gaia:3 "tmux attach-session -t gaia_codex_1" Enter

# Now send the same prompt to each:
# "Design a database schema for a blog with users, posts, and comments"
```

Compare:
1. How long each takes to respond
2. Level of detail
3. Code examples provided
4. Explanation clarity
5. Practical applicability

## Pro Tips

1. **Route by Complexity:** Use Claude/Gemini for complex tasks, Ollama for simple ones
2. **Failover Chain:** Try Claude first, fallback to Gemini, then Codex for cost
3. **Local Development:** Use Ollama for fast iteration, Claude for review
4. **Code Tasks:** Use Codex or Claude
5. **Explanations:** Use Claude or Gemini

## Next Steps

1. Test each provider with real prompts from your work
2. Track response times and quality
3. Set up failover priorities in your config
4. Use results to optimize costs and performance
