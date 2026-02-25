# Chrome Extension Setup Guide

## Overview

The Architect Browser Agent is a Chrome extension that enables autonomous browser automation by connecting your actual Chrome browser to the Architect server. Unlike Selenium/Playwright which launches separate browser instances, this runs in your real browser with all your existing logins and sessions.

## Architecture

```
Chrome Browser                      Architect Server
┌──────────────────┐               ┌─────────────────┐
│  Extension       │               │                 │
│  ├─ background.js│◄─WebSocket───┤  WS Server      │
│  ├─ content.js   │               │  (port 8765)    │
│  └─ popup.html   │               │                 │
│                  │               │  ┌──────────────┤
│  Real browser    │               │  │ Task Planner │
│  All your logins │               │  │ (TODO)       │
│  All your cookies│               │  └──────────────┤
└──────────────────┘               └─────────────────┘
```

## Phase E1: WebSocket Bridge (CURRENT)

**Status:** ✅ Complete

**Components:**
- Chrome extension (`chrome_extension/`)
- WebSocket server (`services/browser_ws_server.py`)
- Bidirectional communication
- Event streaming (tab/group/page changes)
- Command execution (tab management, screenshots)

## Installation

### 1. Install Python Dependencies

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Install websockets library
pip3 install websockets
```

### 2. Load Extension in Chrome

1. Open Chrome
2. Go to `chrome://extensions/`
3. Enable "Developer mode" (toggle switch in top right)
4. Click "Load unpacked"
5. Navigate to `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/chrome_extension`
6. Select the folder
7. Extension should appear with "Architect Browser Agent" title

### 3. Start WebSocket Server

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
python3 services/browser_ws_server.py
```

You should see:
```
✓ Server listening on ws://localhost:8765
Waiting for Chrome extension to connect...
```

### 4. Verify Connection

1. Click the Architect extension icon in Chrome toolbar
2. Popup should show "✓ Connected to Architect Server"
3. Server console should show: "Client connected: ..."

### 5. Check Browser Events

In server console, open/close tabs and watch events stream:

```
Event: TAB_CREATED
Tab created: 12345 - New Tab
Event: PAGE_LOADED
Page loaded: 12345 - Google
Event: TAB_CLOSED
Tab closed: 12345
```

## Testing

### Test 1: Verify WebSocket Connection

**Chrome:**
1. Open DevTools (F12)
2. Go to background service worker:
   - `chrome://extensions/` → Architect → "service worker"
3. Should see: `[Architect] Connected to server`

**Server:**
```bash
python3 services/browser_ws_server.py
```
Should see: `Client connected: ...`

### Test 2: Tab Events

**Action:** Open a new tab in Chrome

**Expected server output:**
```
Event: TAB_CREATED
Tab created: 12345 - New Tab
Event: PAGE_LOADED
Page loaded: 12345 - Google
```

### Test 3: DOM Extraction (Content Script)

**Chrome DevTools console (on any webpage):**
```javascript
chrome.runtime.sendMessage({
  action: 'EXTRACT_ELEMENTS'
}, (response) => console.log(response));
```

**Expected response:**
```javascript
{
  pageTitle: "Example Domain",
  url: "https://example.com",
  links: [{index: 1, text: "More information...", href: "..."}],
  buttons: [],
  forms: [],
  headings: ["Example Domain"]
}
```

### Test 4: Send Command from Server

**Add to `browser_ws_server.py` (uncomment demo_task):**

The server will send `GET_TABS` command every 60 seconds and log the result.

## Available Commands

### Tab Management

**GET_TABS** - List all tabs
```python
{"command": True, "id": "cmd-1", "action": "GET_TABS"}
```

**OPEN_TAB** - Open new tab
```python
{"command": True, "id": "cmd-2", "action": "OPEN_TAB", "params": {"url": "https://example.com"}}
```

**CLOSE_TAB** - Close tab
```python
{"command": True, "id": "cmd-3", "action": "CLOSE_TAB", "tabId": 12345}
```

**NAVIGATE** - Navigate tab to URL
```python
{"command": True, "id": "cmd-4", "action": "NAVIGATE", "tabId": 12345, "params": {"url": "https://example.com"}}
```

### Tab Groups

**CREATE_GROUP** - Create tab group
```python
{
  "command": True,
  "id": "cmd-5",
  "action": "CREATE_GROUP",
  "params": {
    "tabIds": [12345, 12346],
    "title": "Research",
    "color": "blue"
  }
}
```

**COLLAPSE_GROUP** - Collapse group
```python
{"command": True, "id": "cmd-6", "action": "COLLAPSE_GROUP", "params": {"groupId": 1}}
```

### DOM Interaction

**EXTRACT_ELEMENTS** - Get actionable elements from page
```python
{
  "command": True,
  "id": "cmd-7",
  "action": "EXTRACT_ELEMENTS",
  "target": "content",
  "tabId": 12345
}
```

**CLICK** - Click element
```python
{
  "command": True,
  "id": "cmd-8",
  "action": "CLICK",
  "target": "content",
  "tabId": 12345,
  "params": {"selector": "#login-button"}
}
```

**TYPE_TEXT** - Type into field
```python
{
  "command": True,
  "id": "cmd-9",
  "action": "TYPE_TEXT",
  "target": "content",
  "tabId": 12345,
  "params": {
    "selector": "#username",
    "text": "myusername",
    "clear": True
  }
}
```

### Comet AI

**READ_COMET** - Read Comet sidebar state
```python
{
  "command": True,
  "id": "cmd-10",
  "action": "READ_COMET",
  "target": "content",
  "tabId": 12345
}
```

**WRITE_COMET** - Write to Comet input
```python
{
  "command": True,
  "id": "cmd-11",
  "action": "WRITE_COMET",
  "target": "content",
  "tabId": 12345,
  "params": {"text": "What should I click to register?"}
}
```

**SUBMIT_COMET** - Submit Comet query
```python
{
  "command": True,
  "id": "cmd-12",
  "action": "SUBMIT_COMET",
  "target": "content",
  "tabId": 12345
}
```

## Events Pushed to Server

The extension automatically pushes these events:

- `CONNECTED` - Extension connected to server
- `FULL_STATE` - Complete browser state (tabs, groups, windows)
- `TAB_CREATED` - New tab opened
- `TAB_CLOSED` - Tab closed
- `PAGE_LOADED` - Page finished loading
- `TAB_ACTIVATED` - Tab focused
- `GROUP_CREATED` - Tab group created
- `GROUP_UPDATED` - Tab group changed
- `NAVIGATION_DONE` - Navigation completed
- `COMET_RESPONSE` - New Comet AI response detected
- `COMMAND_RESULT` - Result of command execution

## Debugging

### Extension Logs

**Background Script Logs:**
1. Go to `chrome://extensions/`
2. Find "Architect Browser Agent"
3. Click "service worker" link
4. DevTools console opens showing background.js logs

**Content Script Logs:**
1. Open any webpage
2. Open DevTools (F12)
3. Console tab shows content.js logs

### Server Logs

All events and commands are logged to stdout with timestamps.

### Common Issues

**Extension not connecting:**
- Check if server is running: `python3 services/browser_ws_server.py`
- Check server is on port 8765
- Check Chrome console for WebSocket errors
- Try clicking "Reconnect" in extension popup

**Commands not executing:**
- Check command format (must have `command: true`, `id`, `action`)
- For content script commands, must include `target: 'content'` and `tabId`
- Check COMMAND_RESULT event for error message

**Comet not detected:**
- Comet sidebar must be visible on the page
- Wait 1 second after page load for observer to start
- Check content script logs for "Comet sidebar detected"

## Next Phases

### Phase E2: Content Script + DOM Interaction ✅
- Complete DOM reading/writing
- Element extraction
- Form interaction
- **Status:** Implemented in content.js

### Phase E3: Comet AI Integration ✅
- Monitor Comet sidebar
- Read/write prompts
- Capture responses
- **Status:** Implemented in content.js

### Phase E4: Autonomous Task Loop (TODO)
- Build planner (`workers/browser_automation/planner.py`)
- Integrate with Goal Engine task queue
- Site knowledge caching
- Tab group management by task
- **Status:** Next priority

### Phase E5: Parallel Execution (TODO)
- Multiple tasks across tabs
- Resource allocation
- Concurrency management

## Files

```
chrome_extension/
├── manifest.json          # Extension manifest
├── background.js          # WebSocket client + Chrome APIs
├── content.js             # DOM interaction + Comet
├── offscreen.html         # Keepalive
├── offscreen.js           # Heartbeat
├── popup.html             # Extension popup
├── popup.js               # Popup logic
└── README.md              # Extension docs

services/
└── browser_ws_server.py   # WebSocket server

docs/
└── CHROME_EXTENSION_SETUP.md  # This file
```

## Success Criteria (Phase E1)

- [x] Extension loads in Chrome without errors
- [x] WebSocket connection established
- [x] Server receives CONNECTED event
- [x] Server receives FULL_STATE with tabs/groups
- [x] Server receives TAB_CREATED when opening tabs
- [x] Server receives PAGE_LOADED when navigation completes
- [x] Server can send GET_TABS command
- [x] Extension can extract DOM elements
- [x] Extension can detect Comet sidebar
- [x] Popup shows connection status

**Result:** Phase E1 complete! ✅

## Comparison to Failed Selenium Approach

| Aspect | Selenium | Chrome Extension |
|--------|----------|------------------|
| Browser | Separate headless instance | User's real browser |
| Logins | Must re-authenticate | Already logged in |
| Sessions | Separate cookies | User's real cookies |
| Comet AI | Not available | Native integration |
| Resource usage | Heavy (new browser) | Lightweight |
| Local LLM accuracy | 0% (failed) | N/A (uses existing sessions) |
| Setup complexity | High | Medium |
| User visibility | Hidden | Visible (can watch) |

The Chrome extension approach eliminates the authentication and cookie management problems that plagued the Selenium approach, and provides direct access to Comet AI for reasoning.
