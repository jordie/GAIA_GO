# Manual WebSocket Refresh Fix Test

## Overview
This guide provides step-by-step instructions to manually verify the WebSocket refresh fix works correctly in the browser.

## Prerequisites
- Server running at http://100.112.58.92:8080
- Browser with Developer Tools (Chrome, Firefox, Safari)

## Test Procedure

### Test 1: Initial Connection & Room Subscription

1. **Open Dashboard**
   ```
   http://100.112.58.92:8080/
   ```

2. **Open Browser Console** (F12 or Cmd+Option+I)

3. **Verify Initial Connection**
   - Look for console message:
     ```
     [Socket] Connected to server
     [Socket] Rejoining rooms for panel overview: ['stats', 'activity']
     ```
   - Check WebSocket indicator in header (should be green/online)

4. **Expected Result**: ✓ Console shows connection and room subscriptions for 'overview' panel

---

### Test 2: Panel Switching & Room Changes

1. **Navigate to Errors Panel**
   - Click "Errors" in sidebar

2. **Check Console Logs**
   - Look for:
     ```
     [Navigation] Loading panel data for: errors
     [Socket] Joined room: errors
     [Socket] Joined room: stats
     ```

3. **Expected Result**: ✓ Console shows rooms changed to ['errors', 'stats']

---

### Test 3: WebSocket Reconnection (Critical Test)

1. **While on Errors Panel**, open browser console

2. **Force Disconnect WebSocket**
   ```javascript
   SocketManager.socket.disconnect()
   ```

3. **Wait for Auto-Reconnect** (2-5 seconds)

4. **Check Console for Reconnection**
   - Look for:
     ```
     [Socket] Disconnected: io client disconnect
     [Socket] Connected to server
     [Socket] Rejoining rooms for panel errors: ['errors', 'stats']
     ```

5. **Verify Room Subscriptions**
   ```javascript
   // Check current rooms
   console.log('Current rooms:', Array.from(SocketManager.currentRooms));
   ```
   - Should show: `['errors', 'stats']`

6. **Expected Result**: ✓ Reconnection automatically rejoins correct rooms for current panel

---

### Test 4: Real-time Updates After Reconnection

1. **While still on Errors panel after reconnection**, trigger an error event:
   - In another terminal/tab:
     ```bash
     curl -X POST http://100.112.58.92:8080/api/log_error \
       -H "Content-Type: application/json" \
       -d '{"message": "Test error after reconnection", "level": "error"}'
     ```

2. **Check Console for Update**
   ```
   [Socket] Errors update received
   ```

3. **Verify Dashboard Updates**
   - Errors panel should refresh automatically
   - New error should appear in the list

4. **Expected Result**: ✓ Real-time updates working after reconnection

---

### Test 5: Multiple Panel Switches + Reconnection

1. **Navigate through multiple panels**:
   - Overview → Errors → Queue → Tmux → back to Errors

2. **Force Disconnect Again**
   ```javascript
   SocketManager.socket.disconnect()
   ```

3. **Wait for Reconnection**

4. **Check Console**
   ```
   [Socket] Connected to server
   [Socket] Rejoining rooms for panel errors: ['errors', 'stats']
   ```

5. **Expected Result**: ✓ Always rejoins correct rooms for current panel

---

## Debugging Commands

### Check Current Panel
```javascript
console.log('Current panel:', currentPanel);
```

### Check Socket Connection
```javascript
console.log('Connected:', SocketManager.connected);
console.log('Socket:', SocketManager.socket);
```

### Check Subscribed Rooms
```javascript
console.log('Subscribed rooms:', Array.from(SocketManager.currentRooms));
```

### Check Panel-Room Mapping
```javascript
const panelRoomMap = {
    'overview': ['stats', 'activity'],
    'errors': ['errors', 'stats'],
    'tmux': ['tmux'],
    'queue': ['queue', 'stats'],
    'nodes': ['nodes']
};
console.log('Expected rooms for', currentPanel, ':', panelRoomMap[currentPanel]);
```

### Manual Room Join
```javascript
SocketManager.joinRoom('test-room');
```

### Monitor All Socket Events
```javascript
// Add this to see ALL socket events
SocketManager.socket.onAny((event, ...args) => {
    console.log('[Socket Event]', event, args);
});
```

---

## Expected Behavior Summary

| Action | Before Fix | After Fix |
|--------|-----------|-----------|
| Initial connection | Joins ['stats', 'tasks'] | Joins rooms for current panel |
| Navigate to Errors | Joins ['errors', 'stats'] | Joins ['errors', 'stats'] ✓ |
| Disconnect/Reconnect | Rejoins ['stats', 'tasks'] ❌ | Rejoins ['errors', 'stats'] ✓ |
| Real-time updates | Broken after reconnect ❌ | Working after reconnect ✓ |

---

## Troubleshooting

### Issue: No console logs appear
- **Solution**: Make sure browser console is set to show all log levels (not just errors)

### Issue: Socket won't reconnect
- **Solution**: Check server is running. Try refreshing page.

### Issue: currentPanel is undefined
- **Solution**: This is expected if testing outside dashboard context. Load dashboard first.

### Issue: Rooms not rejoining
- **Solution**: Check if fix was applied correctly in dashboard.html around line 10338

---

## Success Criteria

✅ All tests pass if:
1. Initial connection joins correct rooms for current panel
2. Panel switching changes room subscriptions
3. Reconnection rejoins rooms based on current panel (not hardcoded)
4. Real-time updates work after reconnection
5. Console logs show expected room join messages

---

## Test Report Template

```
=== WebSocket Refresh Fix Test Report ===
Date: ___________
Tester: ___________
Browser: ___________

Test 1 - Initial Connection:        [ PASS / FAIL ]
Test 2 - Panel Switching:            [ PASS / FAIL ]
Test 3 - Reconnection:               [ PASS / FAIL ]
Test 4 - Real-time Updates:          [ PASS / FAIL ]
Test 5 - Multiple Switches:          [ PASS / FAIL ]

Notes:
_____________________________________________
_____________________________________________

Overall Result: [ PASS / FAIL ]
```

---

**Test Duration**: ~5 minutes
**Difficulty**: Easy
**Automation**: Partial (automated test available in test_websocket_refresh_fix.py)
