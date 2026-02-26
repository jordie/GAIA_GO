# Architect Browser Agent - Chrome Extension

Autonomous browser automation extension for the Architect project.

## Features

- **Real-time WebSocket connection** to local Architect server (localhost:8765)
- **Tab and tab group management** - organize browser tabs by task category
- **DOM interaction** - read, write, click, type, extract elements
- **Comet AI integration** - monitor sidebar, read responses, submit queries
- **Event-driven architecture** - push all browser state changes to server
- **Autonomous task execution** - server sends commands, extension executes

## Installation

### 1. Install Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `chrome_extension/` directory
5. The Architect icon should appear in your extensions toolbar

### 2. Start the WebSocket Server

From the `architect/` directory:

```bash
python3 services/browser_ws_server.py
```

The server will start on `ws://localhost:8765`.

### 3. Verify Connection

1. Click the Architect extension icon in Chrome
2. Status should show "✓ Connected to Architect Server"
3. Check server logs for connection event

## Usage

### Basic Commands (via Server)

```python
# Send command to extension
{
  "command": true,
  "id": "cmd-123",
  "action": "OPEN_TAB",
  "params": {"url": "https://example.com"}
}
```

### Available Actions

#### Tab Operations
- `GET_TABS` - List all tabs
- `OPEN_TAB` - Create new tab
- `CLOSE_TAB` - Close tab
- `NAVIGATE` - Navigate to URL
- `ACTIVATE_TAB` - Focus tab
- `RELOAD_TAB` - Reload tab

#### Tab Group Operations
- `GET_TAB_GROUPS` - List all groups
- `CREATE_GROUP` - Create tab group
- `UPDATE_GROUP` - Update group properties
- `UNGROUP_TABS` - Remove tabs from group
- `COLLAPSE_GROUP` - Collapse group
- `EXPAND_GROUP` - Expand group

#### DOM Operations (require `target: 'content'`)
- `EXTRACT_ELEMENTS` - Get actionable elements
- `READ_DOM` - Read element content
- `CLICK` - Click element
- `TYPE_TEXT` - Type text into field
- `SUBMIT_FORM` - Submit form
- `SELECT_OPTION` - Select dropdown option
- `SCROLL` - Scroll page
- `WAIT_ELEMENT` - Wait for element to appear

#### Comet AI Operations
- `READ_COMET` - Read Comet sidebar state
- `WRITE_COMET` - Write query to Comet input
- `SUBMIT_COMET` - Submit Comet query
- `SUBSCRIBE_COMET` - Start monitoring Comet responses

### Events Pushed to Server

The extension automatically pushes these events:

- `CONNECTED` - Extension connected
- `FULL_STATE` - Complete browser state
- `TAB_CREATED` - New tab opened
- `TAB_CLOSED` - Tab closed
- `PAGE_LOADED` - Page finished loading
- `TAB_ACTIVATED` - Tab focused
- `GROUP_CREATED` - Tab group created
- `GROUP_UPDATED` - Tab group changed
- `NAVIGATION_DONE` - Navigation completed
- `COMET_RESPONSE` - New Comet AI response
- `COMMAND_RESULT` - Command execution result

## Architecture

```
Extension (Chrome)         WebSocket         Server (Python)
    │                         │                     │
    ├─ background.js ─────────┼─────────────────────┤
    │  - WebSocket client     │                     │
    │  - Chrome API calls     │                     │
    │  - Event forwarding     │                     │
    │                         │                     │
    ├─ content.js ────────────┼─────────────────────┤
    │  - DOM interaction      │                     │
    │  - Comet monitoring     │                     │
    │  - Element extraction   │                     │
    │                         │                     │
    └─ offscreen.js           │                     │
       - Keepalive            │                     │
```

## Development

### Testing the Connection

1. Start server: `python3 services/browser_ws_server.py`
2. Open Chrome DevTools on any page
3. Check console for "[Architect Content] Loaded"
4. Check background service worker logs: `chrome://extensions/` → Architect → "service worker"
5. Should see "[Architect] Connected to server"

### Debugging Commands

Open Chrome DevTools console and run:

```javascript
// Test DOM extraction
chrome.runtime.sendMessage({
  action: 'EXTRACT_ELEMENTS'
}, console.log);

// Test Comet reading
chrome.runtime.sendMessage({
  action: 'READ_COMET'
}, console.log);
```

## File Structure

```
chrome_extension/
├── manifest.json          # Extension manifest (Manifest V3)
├── background.js          # Service worker (WebSocket client)
├── content.js             # Content script (DOM interaction)
├── offscreen.html         # Keepalive document
├── offscreen.js           # Keepalive script
├── popup.html             # Extension popup UI
├── popup.js               # Popup logic
├── icons/                 # Extension icons
└── README.md              # This file
```

## Next Steps

See the main project documentation for:
- Planner implementation (server-side task orchestration)
- Site knowledge caching
- Integration with Goal Engine
- Comet AI autonomous agent loop
