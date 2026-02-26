# Extension WebSocket Connection Fix

**Status**: RESOLVED
**Date**: 2026-02-21
**Issue**: InvalidStateError on WebSocket send in onopen handler

## Problem

Chrome extension background service worker was getting:
```
InvalidStateError: Failed to execute 'send' on 'WebSocket': Still in CONNECTING state.
```

This occurred because `ws.onopen` was firing before the WebSocket connection was truly ready, and we attempted to send immediately.

## Root Cause

The `onopen` event fires when the connection is transitioning to OPEN state, but in some browsers/contexts (especially extension service workers), the `readyState` may still be `CONNECTING` at that moment. Attempting `ws.send()` at this point fails.

## Solution: Message Queue System

Instead of sending immediately in `onopen`, we queue messages and process them via a background interval:

### Key Components

1. **sendWhenReady(message)** - Queue function
   - Checks if `readyState === WebSocket.OPEN` before sending
   - If not ready, queues message and starts background processor
   - Uses `setInterval` to retry every 100ms

2. **processSendQueue()** - Background processor
   - Runs every 100ms when messages are queued
   - Sends all queued messages once connection is truly OPEN
   - Cleans up interval when queue is empty

3. **Clean onopen handler**
   - Just marks `connected = true`
   - Starts heartbeat
   - Calls `processSendQueue()` to handle any queued messages
   - Queues initial CONNECTED event via `sendWhenReady()`

### Console Output (Expected)

```
>>> Message queued (ws state: 0)
>>> Processing send queue, 1 messages waiting
✓ Queued message sent
```

## Files

- **Pink Laptop**: `/Users/jgirmay/Desktop/chrome_extension_fixed/background.js`
- **Mac Mini**: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect-dev4/chrome_extension/background.js`
- **GAIA Reference**: `/Users/jgirmay/Desktop/gitrepo/GAIA_HOME/architect_extension_background.js`

## Critical Settings

| Variable | Value | Notes |
|----------|-------|-------|
| WS_URL | `ws://100.112.58.92:8765` | Mac Mini server IP |
| RECONNECT_DELAY | 2000ms | Retry interval |
| HEARTBEAT_INTERVAL | 30000ms | Keep-alive ping |
| Queue check | 100ms | Message retry interval |

## Testing Checklist

- [x] Extension loads without errors
- [x] Message queue system queues messages when not ready
- [x] Background processor sends queued messages
- [x] Connected event sent successfully
- [x] Full state reported after connection
- [x] Heartbeat running
- [x] No InvalidStateError in console

## Future Improvements

1. Consider using Promise-based approach for cleaner async handling
2. Add metrics/monitoring for queue depth and send latency
3. Implement exponential backoff for reconnection attempts
4. Add circuit breaker pattern for repeated failures

## References

- Chrome Extension MV3 Service Worker docs
- WebSocket API spec
- Message queue pattern implementation
