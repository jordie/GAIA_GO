# Browser Automation - Simple Planner Test

## Overview

This is a proof-of-concept autonomous browser agent that demonstrates:
- WebSocket communication with Chrome extension
- Text-first element extraction (no screenshots)
- Simple rule-based decision making
- Multi-step navigation

## Test Case: Find Saba's Wednesday Classes

**Goal:** Find out what classes are available for Saba on Wednesdays at AquaTech

**How it works:**
1. Opens AquaTech website
2. Extracts actionable elements (links, buttons, forms)
3. Decides which element to click based on goal
4. Clicks and waits for page load
5. Repeats until goal is achieved or max steps reached

## Quick Start

### Terminal 1: Start WebSocket Server

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
python3 services/browser_ws_server.py
```

You should see:
```
✓ Server listening on ws://localhost:8765
Waiting for Chrome extension to connect...
```

### Terminal 2: Load Chrome Extension

1. Open Chrome
2. Go to `chrome://extensions/`
3. Enable "Developer mode" (toggle in top right)
4. Click "Load unpacked"
5. Select: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/chrome_extension`
6. Click the extension icon - should show "✓ Connected to Architect Server"

You should see in Terminal 1:
```
Client connected: ... from ...
Event: CONNECTED
Event: FULL_STATE
✓ Browser state received: X tabs
```

### Terminal 3: Run Test

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
./test_chrome_extension.sh
```

Or run directly:
```bash
python3 workers/browser_automation/simple_planner.py \
  "Find classes available for Saba on Wednesdays" \
  https://www.aquatechswim.com
```

## Expected Output

```
🎯 Goal: Find classes available for Saba on Wednesdays
🌐 Starting URL: https://www.aquatechswim.com
======================================================================

→ Sent: OPEN_TAB (id: cmd-1)
✓ Opened tab 12345: https://www.aquatechswim.com
Waiting for page to load (tab 12345)...
✓ Page loaded

📍 Step 1/10
→ Sent: EXTRACT_ELEMENTS (id: cmd-2)
✓ Extracted: 15 links, 3 buttons, 1 forms
→ Sent: GET_PAGE_TEXT (id: cmd-3)
✓ Got page text: 2500 chars
💡 Decision: Click 'a[href="/customer-portal"]'
→ Sent: CLICK (id: cmd-4)
✓ Clicked: a[href="/customer-portal"]

📍 Step 2/10
→ Sent: EXTRACT_ELEMENTS (id: cmd-5)
✓ Extracted: 8 links, 5 buttons, 2 forms
→ Sent: GET_PAGE_TEXT (id: cmd-6)
✓ Got page text: 1800 chars
💡 Decision: Click 'a[href="/my-account"]'
→ Sent: CLICK (id: cmd-7)
✓ Clicked: a[href="/my-account"]

📍 Step 3/10
✅ Found relevant information!

Extracting schedule information...

📅 Schedule Information:
  Saba Girmay
  Tuesday 5:00p SILVERFISH/GOLDFISH - ALAMEDA
  Wednesday 4:00p SEAHORSE - ALAMEDA
  Billing Cycle: Feb11-Mar10
  Monthly Payment: $175.00
```

## How It Works

### 1. Connection Phase

```python
planner = SimplePlanner()
await planner.connect()
```

- Connects to `ws://localhost:8765`
- Waits for `FULL_STATE` event from extension
- Builds browser state model (tabs, groups)

### 2. Task Execution Phase

```python
await planner.execute_task(goal, start_url)
```

**For each step:**
1. **Extract elements** - Get all links, buttons, forms from page
2. **Get page text** - Full page content for matching
3. **Decide action** - Rule-based selection (TODO: replace with LLM)
4. **Execute action** - Click element
5. **Wait for load** - Wait for page to finish loading
6. **Check goal** - Is the answer on this page?

### 3. Text-First Approach

**No screenshots!** The planner:
- ✅ Extracts structured data (links, buttons, forms)
- ✅ Gets page text for keyword matching
- ✅ Makes decisions on text alone
- ❌ Never sends screenshots

This is **10-100x faster** than screenshot-based AI.

### 4. Simple Decision Logic

Current implementation uses rules:
```python
def decide_next_action(goal, elements, page_text):
    if "schedule" in goal.lower():
        # Find links with schedule-related text
        for link in elements["links"]:
            if "schedule" in link["text"].lower():
                return link["selector"]
```

**Next step:** Replace with LLM call:
- Simple choice → Ollama (local, fast, free)
- Complex reasoning → Claude Code
- Form filling → Map data to fields

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Simple Planner (Python)                                │
│  ├─ Connect to WebSocket                                │
│  ├─ Send commands (OPEN_TAB, EXTRACT_ELEMENTS, CLICK)  │
│  ├─ Receive events (PAGE_LOADED, COMMAND_RESULT)       │
│  └─ Decision loop (extract → decide → execute)         │
└──────────────────┬──────────────────────────────────────┘
                   │ WebSocket
                   ▼
┌─────────────────────────────────────────────────────────┐
│  WebSocket Server (browser_ws_server.py)                │
│  ├─ Route commands to extension                        │
│  ├─ Forward events from extension                      │
│  └─ Maintain browser state                             │
└──────────────────┬──────────────────────────────────────┘
                   │ WebSocket
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Chrome Extension                                        │
│  ├─ background.js: Execute Chrome API commands         │
│  └─ content.js: Extract elements, click, type          │
└─────────────────────────────────────────────────────────┘
```

## Available Commands

The planner can send these commands:

| Command | Purpose | Example |
|---------|---------|---------|
| `OPEN_TAB` | Open URL in new tab | `await planner.open_url(url)` |
| `EXTRACT_ELEMENTS` | Get links/buttons/forms | `await planner.extract_elements(tab_id)` |
| `GET_PAGE_TEXT` | Get full page text | `await planner.get_page_text(tab_id)` |
| `CLICK` | Click element | `await planner.click_element(tab_id, selector)` |
| `TYPE_TEXT` | Type into field | Send `TYPE_TEXT` command |
| `SCREENSHOT` | Capture visible tab | Send `SCREENSHOT` command |

See `simple_planner.py` for full API.

## Limitations (Current)

**Rule-based decisions only:**
- Uses simple keyword matching
- Can't handle complex navigation
- No learning or adaptation

**No form filling:**
- Can click but not fill forms yet
- Need to add TYPE_TEXT and SELECT_OPTION

**No caching:**
- Repeats navigation every time
- Should cache successful paths

## Next Steps

### Short Term (This Week)

1. **Add LLM decision making**
   - Replace `decide_next_action()` with Ollama call
   - Format: "Goal: X. Available actions: [1,2,3]. Pick number."
   - Use local Ollama for speed (llama3.2)

2. **Add form filling**
   - Implement `type_text()` method
   - Implement `select_option()` method
   - Map goal data to form fields

3. **Test on real AquaTech workflow**
   - Navigate to customer portal
   - Login (use saved cookies from real browser)
   - Find schedule
   - Extract class info

### Medium Term (Next 2 Weeks)

4. **Add site knowledge caching**
   - Save successful navigation paths
   - Second run should use cache (0 AI calls)
   - Store in `data/site_knowledge/`

5. **Integrate with Goal Engine**
   - Accept tasks from task queue
   - Report results back
   - Schedule recurring tasks

6. **Add Comet AI integration**
   - Read Comet sidebar for page context
   - Ask Comet for help on complex pages
   - Use Comet responses to make decisions

### Long Term (Next Month)

7. **Tab group management**
   - Organize tabs by task category
   - Collapse/expand groups
   - Auto-cleanup completed tasks

8. **Parallel task execution**
   - Run multiple tasks across tabs
   - Resource allocation
   - Conflict detection

## Files

```
workers/browser_automation/
├── simple_planner.py      # This planner (POC)
├── README.md              # This file
└── (future)
    ├── planner.py         # Full planner with LLM
    ├── cache.py           # Site knowledge cache
    ├── extractor.py       # Element extraction
    └── decision.py        # LLM decision routing
```

## Debugging

**Extension not connecting:**
- Check server is running: `python3 services/browser_ws_server.py`
- Check extension loaded: `chrome://extensions/`
- Check extension popup: Should show "✓ Connected"

**Commands timing out:**
- Check Chrome DevTools console for errors
- Check background service worker logs: `chrome://extensions/` → service worker
- Increase timeout in `wait_for_result()`

**Decision logic not working:**
- Check extracted elements: Are the expected links present?
- Check page text: Does it contain expected keywords?
- Add debug prints in `decide_next_action()`

**Page not loading:**
- Increase sleep time after click
- Check if page uses JavaScript navigation
- Try waiting for specific element instead of PAGE_LOADED event

## Success Metrics

**For this test:**
- ✅ Extension connects to server
- ✅ Planner sends commands successfully
- ✅ Extension extracts elements from page
- ✅ Planner makes navigation decisions
- ✅ Finds Saba's Wednesday class information

**Expected result:**
```
Wednesday 4:00p SEAHORSE - ALAMEDA
```

This proves the autonomous loop works end-to-end! 🎯
