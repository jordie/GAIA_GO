# 🏗️ Architect Browser Extension - GAIA Bidirectional Messaging

**Status**: IMPLEMENTED
**Date**: 2026-02-21
**Type**: Phase 3.2 - Browser-to-GAIA Integration

## Overview

The Architect Browser Agent extension now features **bidirectional messaging** with GAIA_HOME:

1. **Extension → GAIA**: Send captured Perplexity conversations and user messages
2. **GAIA → Extension**: Receive task responses, commands, and status messages
3. **Real-time Sidebar**: Messages display in extension popup with live refresh

## Architecture

```
┌──────────────────────────┐
│ Architect Browser Agent  │
│  (Chrome Extension)      │
├──────────────────────────┤
│ • Popup UI (sidebar)     │
│ • Message capture        │
│ • GAIA messaging         │
└────────────┬─────────────┘
             │ WebSocket
             ↓ ws://100.112.58.92:8765
┌──────────────────────────┐
│ GAIA_HOME Server         │
│ (Mac Mini)               │
├──────────────────────────┤
│ • Message routing        │
│ • Task processing        │
│ • Conversation storage   │
└──────────────────────────┘
```

## Features

### 1. Perplexity Conversation Capture

**Button**: "📸 Capture Current Conversation"
**Location**: Extension popup

**How it works**:
1. User navigates to Perplexity conversation
2. Clicks "Capture Current Conversation" button
3. Extension injects `extractConversationData()` code on the page
4. Extracts:
   - Conversation ID from URL (new format: `/search/query-ID`)
   - Title from page DOM
   - Message count
   - Timestamp
5. Stores locally in `chrome.storage.local.capturedConversations`
6. **Automatically sends to GAIA** via WebSocket

**Key Advantages**:
- ✅ No passive content script needed
- ✅ Bypasses Cloudflare Access restrictions
- ✅ User-triggered (more reliable)
- ✅ Works on any page dynamically

### 2. GAIA Messaging Sidebar

**Location**: Extension popup "💬 GAIA Messages" section

**Features**:
- **Receive messages** from GAIA_HOME (displays last 10)
- **Send messages** to GAIA using input box
- **Auto-refresh** every 3 seconds
- **Timestamped** message display
- **Real-time** status updates

**Message Flow**:
```
User types → popup.js → background.js → WebSocket → GAIA
                                              ↓
                                    Server processes
                                              ↓
GAIA sends back → background.js → popup displays → User sees response
```

## API Specification

### Extension → GAIA Messages

#### Perplexity Conversation Captured

```json
{
  "event": "PERPLEXITY_CONVERSATION_CAPTURED",
  "type": "conversation_capture",
  "source": "extension",
  "timestamp": 1708694400000,
  "data": {
    "id": "w2qPIyRxSH.V_P3P08lASQ",
    "title": "What is the weather in Walnut?",
    "url": "https://www.perplexity.ai/search/what-is-the-weather-in-walnut-EdNAA5r_TQKoWTgt1EUyKw",
    "messageCount": 5,
    "capturedAt": "2026-02-21T15:00:00.000Z",
    "domain": "perplexity.ai"
  }
}
```

#### User Message to GAIA

```json
{
  "event": "EXTENSION_MESSAGE",
  "type": "user_message",
  "source": "extension",
  "timestamp": 1708694400000,
  "content": "Please analyze this conversation",
  "data": {
    "contextType": "perplexity_conversation",
    "customData": {}
  }
}
```

### GAIA → Extension Messages

#### Message from GAIA

```json
{
  "event": "GAIA_MESSAGE",
  "type": "status_update|command|response|notification",
  "data": {
    "content": "Conversation stored successfully",
    "type": "success|warning|error|info",
    "id": "msg-abc123"
  }
}
```

#### Task Response from GAIA

```json
{
  "event": "TASK_RESPONSE",
  "data": {
    "taskId": "task-123",
    "status": "completed|failed|pending",
    "result": { "analyzed": true, "summary": "..." }
  }
}
```

## Implementation Files

### Updated Files

| File | Changes |
|------|---------|
| `background.js` | Added GAIA message handlers, conversation routing |
| `popup.html` | Added "💬 GAIA Messages" section with message display |
| `popup.js` | Added message sender/receiver, conversation capture logic |
| `manifest.json` | Already has Perplexity content script (for fallback) |

### Key Functions

**background.js**:
- `sendConversationToGAIA(conversationData)` - Send conversation to GAIA
- `handleGAIAMessage(data)` - Process incoming messages
- `handleTaskResponse(data)` - Handle task completion responses
- Message handlers in `chrome.runtime.onMessage` listener

**popup.js**:
- `captureCurrentConversation()` - Inject code and capture
- `extractConversationData()` - Run on Perplexity page
- `loadGAIAMessages()` - Refresh message list from service worker
- `sendGAIAMessage()` - Send message via service worker to GAIA

## Testing Checklist

### Test 1: Capture Conversation on Perplexity
- [ ] Open Perplexity conversation
- [ ] Click "📸 Capture Current Conversation"
- [ ] Button shows "⏳ Capturing..." then returns to normal
- [ ] See success message: "✓ Captured: {title}"
- [ ] Conversation appears in "🧠 Perplexity Conversations" list
- [ ] Service worker console shows: "✓ Sent conversation to GAIA"

### Test 2: GAIA Messaging
- [ ] Click in "Send message to GAIA..." input
- [ ] Type a test message
- [ ] Press Enter or click 📤 button
- [ ] Message sends (button shows ⏳ temporarily)
- [ ] Service worker logs: "Popup sending message to GAIA"
- [ ] GAIA server receives message

### Test 3: Receive GAIA Messages
- [ ] Ensure GAIA server is sending test messages
- [ ] Messages appear in "💬 GAIA Messages" section
- [ ] Timestamps display correctly
- [ ] Message list auto-refreshes every 3 seconds
- [ ] Oldest messages scroll up when new ones arrive

### Test 4: Error Handling
- [ ] Restart extension while composing message → Error shows
- [ ] WebSocket disconnects → "WebSocket not connected" error
- [ ] Invalid message → Error displays in popup

## Message Sequence Diagram

```
Perplexity Page         Extension Popup      Service Worker       GAIA Server
     │                      │                     │                    │
     │  Click "Capture"     │                     │                    │
     ├─────────────────────→│                     │                    │
     │                      │                     │                    │
     │  Inject code         │                     │                    │
     ├─────────────────────→│                     │                    │
     │                      │  sendMessage()      │                    │
     │  Extract data        │─────────────────→│                    │
     │←─────────────────────┤                     │                    │
     │                      │  Route to WS        │                    │
     │                      │  (handler)          │                    │
     │                      │                     │  PERPLEXITY_       │
     │                      │                     │  CONVERSATION_     │
     │                      │                     │  CAPTURED          │
     │                      │                     │────────────────→│
     │                      │                     │                    │
     │                      │                     │←─── GAIA_MESSAGE ──┤
     │                      │                     │ (confirmation)     │
     │                      │  sendResponse()     │                    │
     │                      │←─────────────────│                    │
     │                      │                     │                    │
     │              Show success                  │                    │
     │              message                       │                    │
     │←─────────────────────┤                     │                    │
```

## Deployment

### On Pink Laptop

1. **Reload Extension**:
   - Go to `chrome://extensions/`
   - Find "Architect Browser Agent"
   - Click reload button

2. **Verify Connection**:
   - Open extension popup
   - Check status indicator (should show ✓ if WebSocket connected)
   - Service worker console should show connection messages

3. **Test Capture**:
   - Go to any Perplexity conversation
   - Click "📸 Capture Current Conversation"
   - Verify message sent to GAIA

### Server Configuration

**WebSocket endpoint**: `ws://100.112.58.92:8765`

**GAIA expects**:
```json
{
  "event": "PERPLEXITY_CONVERSATION_CAPTURED",
  "source": "extension",
  "data": { ... }
}
```

## Troubleshooting

### Issue: "Not on Perplexity" Error

**Cause**: Button clicked on wrong site
**Fix**: Navigate to `https://www.perplexity.ai/search/...` first

### Issue: "WebSocket not connected"

**Cause**: Server unreachable or background script crashed
**Fix**:
1. Reload extension
2. Check server IP: `ws://100.112.58.92:8765` is correct
3. Verify server is running on Mac Mini

### Issue: No GAIA Messages Showing

**Cause**: Background service worker not receiving messages
**Fix**:
1. Check service worker console for errors
2. Verify GAIA server is sending messages
3. Check `chrome.storage.local` for message data

### Issue: "Capture failed: Could not extract conversation data"

**Cause**: Perplexity page structure changed
**Fix**: Update selectors in `extractConversationData()` function:
```javascript
// Current selectors:
titleElement = document.querySelector('h1, [data-testid="conversation-title"], .conversation-title, .chat-header')
messageElements = document.querySelectorAll('[role="article"], .message, [data-testid="message"], .prose')
```

## Future Enhancements

1. **Two-way Conversation Sync**: GAIA sends conversation commands back to extension
2. **Sidebar Persistence**: Keep messaging sidebar always visible
3. **Message History**: Store full message history locally
4. **Message Categories**: Different message types (task, alert, sync)
5. **Read Receipts**: Track message delivery status
6. **Auto-responses**: Automatic replies for certain GAIA messages
7. **Conversation Linking**: Link captured conversations to GAIA tasks

## References

- **Phase 3.1**: WebSocket connection (background.js)
- **Phase 3.2**: Perplexity capture + GAIA messaging (current)
- **Phase 3.3**: Dashboard integration
- **Chrome Extension API**: [Scripting API](https://developer.chrome.com/docs/extensions/reference/scripting/), [Storage API](https://developer.chrome.com/docs/extensions/reference/storage/), [Runtime API](https://developer.chrome.com/docs/extensions/reference/runtime/)
- **WebSocket API**: [MDN Docs](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

---

**Status**: ✅ IMPLEMENTED
**Testing**: Ready for QA
**Production**: Deployed to Pink Laptop
