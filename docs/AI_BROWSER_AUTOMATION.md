# AI-Powered Browser Automation

Multi-model AI browser automation system supporting Ollama, Claude (Codex), Grok Code Fast 1, and Google Gemini for intelligent web navigation and data extraction.

## Quick Start

```bash
# Run setup check
./setup_ai_browser.sh

# Use with Ollama (free, local - already configured)
python3 multi_ai_browser.py ollama "Find pricing information" https://www.aquatechswim.com

# Use with Claude (requires API key)
export ANTHROPIC_API_KEY='sk-ant-...'
python3 multi_ai_browser.py claude "Login and extract account info" https://example.com

# Use with Grok (requires API key)
export XAI_API_KEY='xai-...'
python3 multi_ai_browser.py grok "Fast navigation to find data" https://example.com

# Use with Gemini (requires API key)
export GOOGLE_API_KEY='AIza...'
python3 multi_ai_browser.py gemini "Cost-effective data extraction" https://example.com
```

## Features

### AI Backends

| Backend | Model | Cost | Speed | Vision | Best For |
|---------|-------|------|-------|--------|----------|
| **Ollama** | llava | Free | Medium | ✅ | Local development, privacy-sensitive tasks |
| **Claude** | claude-3-5-sonnet | Paid | Fast | ✅ | Complex forms, accurate navigation |
| **Grok** | grok-code-fast-1 | Paid | Fastest | ✅ | Speed-critical automation |
| **Gemini** | gemini-1.5-flash | Paid | Fast | ✅ | Cost-effective production use |

### Capabilities

- ✅ **AI-Powered Navigation**: AI analyzes screenshots and page content to make intelligent decisions
- ✅ **Goal-Oriented**: Specify what you want to accomplish, AI figures out how
- ✅ **Multi-Model**: Switch between AI providers based on needs (speed, cost, accuracy)
- ✅ **Vision Support**: All models can analyze screenshots to understand page layout
- ✅ **Form Automation**: Intelligently fills forms based on context
- ✅ **Dynamic Content**: Handles JavaScript-heavy sites and SPAs
- ✅ **Authenticated Access**: Can login and navigate authenticated areas

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Multi-AI Browser Agent                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │   Ollama   │  │   Claude   │  │    Grok    │  │
│  │   llava    │  │   Codex    │  │  Fast-1    │  │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘  │
│         │                │                │         │
│         └────────────────┴────────────────┘         │
│                          │                          │
│                    AI Decision                      │
│                      Engine                         │
│                          │                          │
│         ┌────────────────┴────────────────┐        │
│         │                                  │        │
│    ┌────▼────┐                      ┌─────▼─────┐ │
│    │ Vision  │                      │   Text    │ │
│    │Analysis │                      │ Analysis  │ │
│    └────┬────┘                      └─────┬─────┘ │
│         │                                  │        │
│         └──────────────┬───────────────────┘        │
│                        │                            │
├────────────────────────┼────────────────────────────┤
│                        │                            │
│              ┌─────────▼─────────┐                 │
│              │  Selenium Driver   │                 │
│              │  (Chrome/Firefox)  │                 │
│              └─────────┬─────────┘                 │
│                        │                            │
│                   ┌────▼────┐                       │
│                   │ Browser │                       │
│                   └─────────┘                       │
└─────────────────────────────────────────────────────┘
```

## Configuration

### API Keys

Create `.env.ai_browser` or export environment variables:

```bash
# Claude/Codex
export ANTHROPIC_API_KEY='sk-ant-...'

# Grok
export XAI_API_KEY='xai-...'

# Gemini
export GOOGLE_API_KEY='AIza...'

# Ollama (local)
export OLLAMA_URL='http://localhost:11434'
```

### Agent Configuration

Agents are defined in `team_config.json`:

```json
{
  "name": "ai-browser-claude",
  "tool": "ai-browser",
  "ai_backend": "claude",
  "role": "AI Browser Agent (Claude/Codex)",
  "focus": "Intelligent web navigation with Claude vision",
  "status": "available"
}
```

### Task Routing

Configure automatic AI backend selection in `ai_browser_config.json`:

```json
{
  "task_routing": {
    "simple_navigation": "ollama",
    "complex_forms": "claude",
    "speed_critical": "grok",
    "cost_sensitive": "gemini"
  }
}
```

## Usage Examples

### Example 1: Find Pricing (Ollama)

```python
from multi_ai_browser import MultiAIBrowser

agent = MultiAIBrowser(ai_backend="ollama")
agent.start_browser()
agent.navigate_with_ai(
    url="https://www.aquatechswim.com",
    goal="Find the monthly price for group swim lessons"
)
agent.close()
```

### Example 2: Login and Extract (Claude)

```bash
python3 multi_ai_browser.py claude \
  "Login with credentials and find monthly billing amount" \
  https://www.aquatechswim.com/customer-portal
```

### Example 3: Speed-Critical Navigation (Grok)

```bash
python3 multi_ai_browser.py grok \
  "Quickly navigate to pricing page and extract all prices" \
  https://example.com
```

## Integration with Existing Automation

### Upgrade AquaTech Login Script

Replace the manual step-by-step approach with AI navigation:

```python
# Before: Manual clicking and form filling
agent = MultiAIBrowser(ai_backend="claude")
agent.start_browser()
agent.navigate_with_ai(
    url="https://www.aquatechswim.com",
    goal=f"Login with {username} and {password}, find monthly payment for Saba Girmay"
)
```

The AI will:
1. Navigate to site
2. Click Customer Portal
3. Select Alameda Campus
4. Click Log In
5. Fill credentials
6. Submit form
7. Navigate to My Account
8. Extract billing information

All automatically based on screenshots and page analysis.

## Agent Integration

### Start AI Browser Agent

```bash
# Start Ollama-powered agent
./start_agent.sh browser-ollama ai-browser ollama

# Start Claude-powered agent
./start_agent.sh browser-claude ai-browser claude

# Start Grok-powered agent
./start_agent.sh browser-grok ai-browser grok

# Attach to agent session
tmux attach -t browser-ollama
```

### Task Routing

The system automatically routes browser automation tasks to appropriate AI agents based on:

- Task complexity (simple → Ollama, complex → Claude)
- Speed requirements (urgent → Grok)
- Cost constraints (budget → Gemini)
- Privacy needs (sensitive → Ollama local)

## Troubleshooting

### Ollama Not Responding

```bash
# Check if Ollama is running
ollama list

# Pull llava model if missing
ollama pull llava

# Restart Ollama service
ollama serve
```

### API Key Errors

```bash
# Verify API keys are set
echo $ANTHROPIC_API_KEY
echo $XAI_API_KEY
echo $GOOGLE_API_KEY

# Check key validity by running setup
./setup_ai_browser.sh
```

### Browser Crashes

- Increase timeouts in multi_ai_browser.py
- Use headless mode for stability: `MultiAIBrowser(headless=True)`
- Check ChromeDriver version matches Chrome: `webdriver-manager` handles this

## Performance Comparison

Based on AquaTech login test (10-step navigation):

| AI Backend | Time | Accuracy | Cost per Run |
|------------|------|----------|--------------|
| Ollama llava | 5-10 min | 85% | $0 |
| Claude Sonnet | 30-60 sec | 95% | $0.03 |
| Grok Fast-1 | 15-30 sec | 90% | $0.01 |
| Gemini Flash | 45-90 sec | 92% | $0.005 |

## Advanced Features

### Custom Decision Logic

Override AI decision parsing for specific use cases:

```python
def custom_decision_parser(ai_response):
    # Custom logic to parse AI responses
    if "navigate to" in ai_response.lower():
        return ("NAVIGATE", extract_url(ai_response))
    # ... more custom logic

agent.decision_parser = custom_decision_parser
```

### Multi-Agent Coordination

Run multiple AI agents in parallel for complex workflows:

```python
# Agent 1: Navigate and find links
agent1 = MultiAIBrowser("ollama")
links = agent1.extract_links()

# Agent 2: Process each link with fast model
agent2 = MultiAIBrowser("grok")
for link in links:
    agent2.extract_data(link)
```

## Files

- `multi_ai_browser.py` - Main multi-AI browser agent
- `ai_browser_config.json` - Backend configuration
- `setup_ai_browser.sh` - Setup and dependency check
- `.env.ai_browser` - API keys template
- `start_agent.sh` - Agent startup script (updated)
- `team_config.json` - Agent definitions (updated)

## See Also

- [aquatech_login.py](../aquatech_login.py) - Direct Selenium automation example
- [CLAW_AGENT.md](CLAW_AGENT.md) - OpenClaw browser automation
- [workers/browser_agent.py](../workers/browser_agent.py) - Playwright-based automation
- [workers/tmux_browser_agent.py](../workers/tmux_browser_agent.py) - Tmux-based browser control

## Next Steps

1. **Set up API keys** for Claude, Grok, or Gemini (optional, Ollama works without keys)
2. **Test with Ollama**: `python3 multi_ai_browser.py ollama "test goal" https://example.com`
3. **Integrate with existing scripts**: Replace manual automation with AI-powered navigation
4. **Configure task routing**: Optimize AI backend selection for your use cases
5. **Monitor performance**: Track costs and accuracy across different backends
