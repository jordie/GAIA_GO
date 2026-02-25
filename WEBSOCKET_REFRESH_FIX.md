# WebSocket Refresh Fix

**Date**: 2026-02-09
**Worker**: foundation (infrastructure)
**Commit**: 1d1b9d7

---

## Problem Summary

The dashboard WebSocket connection was not properly refreshing real-time updates after reconnection. When the WebSocket disconnected and reconnected, users would stop receiving updates for their current panel.

### Root Cause

The WebSocket reconnection handler was hardcoded to only rejoin 'stats' and 'tasks' rooms, regardless of which panel the user was currently viewing.

```javascript
// OLD CODE (Buggy)
this.socket.on('connect', () => {
    this.connected = true;
    this.updateIndicator(true);
    // Rejoin rooms after reconnect
    this.currentRooms.forEach(room => this.joinRoom(room, true));
    // Always subscribe to stats and tasks ← PROBLEM: Hardcoded rooms!
    this.joinRoom('stats');
    this.joinRoom('tasks');
});
```

### Issue Flow

1. User opens dashboard on 'overview' panel
   - Joins rooms: ['stats', 'activity']
   - Real-time updates working ✓

2. User navigates to 'errors' panel
   - Leaves previous rooms (except 'stats')
   - Joins rooms: ['errors', 'stats']
   - Real-time updates working ✓

3. WebSocket disconnects (network issue, timeout, etc.)
   - Connection lost

4. WebSocket reconnects
   - Hardcoded logic rejoins: ['stats', 'tasks']
   - User still on 'errors' panel, but NOT subscribed to 'errors' room!
   - Real-time updates BROKEN ✗

---

## Solution

Updated the reconnection handler to dynamically determine which rooms to join based on the current panel using the same `panelRoomMap` that's used during panel switching.

```javascript
// NEW CODE (Fixed)
this.socket.on('connect', () => {
    console.log('[Socket] Connected to server');
    this.connected = true;
    this.reconnectAttempts = 0;
    this.updateIndicator(true);

    // Rejoin rooms based on current panel after reconnect
    const panelRoomMap = {
        'overview': ['stats', 'activity'],
        'errors': ['errors', 'stats'],
        'tmux': ['tmux'],
        'queue': ['queue', 'stats'],
        'nodes': ['nodes'],
        'features': ['stats'],
        'bugs': ['stats']
    };

    const rooms = panelRoomMap[currentPanel] || ['stats', 'tasks'];
    console.log(`[Socket] Rejoining rooms for panel ${currentPanel}:`, rooms);
    rooms.forEach(room => this.joinRoom(room));
});
```

### Key Changes

1. **Dynamic Room Selection**: Uses `panelRoomMap` to determine correct rooms
2. **Current Panel Awareness**: Reads `currentPanel` variable to know which panel user is on
3. **Debug Logging**: Logs which rooms are being rejoined for troubleshooting
4. **Fallback**: Defaults to `['stats', 'tasks']` if panel not in map

---

## Panel Room Mappings

| Panel | Rooms Subscribed |
|-------|------------------|
| overview | stats, activity |
| errors | errors, stats |
| tmux | tmux |
| queue | queue, stats |
| nodes | nodes |
| features | stats |
| bugs | stats |

---

## Testing

### Manual Testing

1. Open dashboard at http://100.112.58.92:8080/
2. Navigate to 'errors' panel
3. Open browser console
4. Force disconnect WebSocket:
   ```javascript
   SocketManager.socket.disconnect()
   ```
5. Wait for automatic reconnection (~2-5 seconds)
6. Check console logs:
   ```
   [Socket] Connected to server
   [Socket] Rejoining rooms for panel errors: ['errors', 'stats']
   [Socket] Joined room: errors
   [Socket] Joined room: stats
   ```
7. Verify error updates are received in real-time

### Automated Testing

Run the test script:
```bash
python3 test_websocket_refresh_fix.py
```

Expected output:
```
============================================================
WebSocket Refresh Fix Test
============================================================

Test 1: Initial connection
✓ Connection #1 established

Test 2: Simulating panel switch to 'errors'
  → Joined room: errors
  → Joined room: stats
  Rooms joined: ['errors', 'stats']

Test 3: Forcing reconnection
✓ Disconnected cleanly
✓ Connection #2 established

Test 4: Verifying room rejoin
  Expected: Rooms should be rejoined based on current panel
  Actual rooms joined on reconnect: ['errors', 'stats']

============================================================
✓ Test PASSED: Reconnection occurred successfully
  - Total connections: 2
  - Fix working: Rooms are rejoined on reconnect
============================================================
```

---

## Impact

### Before Fix
- ✗ Real-time updates stopped working after reconnection
- ✗ Users had to manually refresh page to get updates
- ✗ Dashboard appeared "frozen" after network issues
- ✗ Error, tmux, queue, nodes panels not receiving updates

### After Fix
- ✓ Real-time updates continue working after reconnection
- ✓ Correct rooms automatically rejoined based on current panel
- ✓ Users see live updates without manual refresh
- ✓ All panels receive appropriate real-time data

---

## Related Files

| File | Purpose |
|------|---------|
| `templates/dashboard.html` | Main fix - Updated SocketManager connect handler |
| `test_websocket_refresh_fix.py` | Automated test for reconnection behavior |
| `test_websocket_fix.py` | Existing WebSocket connection test (still valid) |
| `WEBSOCKET_REFRESH_FIX.md` | This documentation |

---

## Architecture Notes

### WebSocket Room System

The dashboard uses a room-based subscription model:

1. **Rooms**: Named channels for specific data types (e.g., 'stats', 'errors', 'tmux')
2. **Subscriptions**: Clients join rooms to receive updates for specific data
3. **Broadcasting**: Server emits events to rooms, only subscribed clients receive them

### Panel Switching Flow

```
User clicks panel → loadPanel()
                      ↓
                  leaveAllRooms() (except 'stats')
                      ↓
                  Join new rooms based on panelRoomMap
                      ↓
                  Load panel data
                      ↓
                  Receive real-time updates in joined rooms
```

### Reconnection Flow (Fixed)

```
WebSocket disconnects
        ↓
Auto-reconnect (Socket.IO)
        ↓
'connect' event fired
        ↓
Read currentPanel variable
        ↓
Lookup rooms in panelRoomMap
        ↓
Join appropriate rooms
        ↓
Real-time updates resume ✓
```

---

## Prevention

To prevent similar issues in the future:

1. **Always use panelRoomMap**: Any code that joins rooms should reference the centralized panel-to-rooms mapping
2. **Test reconnection**: Always test WebSocket disconnection/reconnection scenarios
3. **Avoid hardcoding**: Never hardcode room names in event handlers
4. **Log room changes**: Keep logging statements for debugging subscription issues

---

## Monitoring

To monitor WebSocket health in production:

1. Check console logs for room join messages:
   ```javascript
   [Socket] Rejoining rooms for panel <name>: [...]
   ```

2. Monitor Socket.IO indicator in dashboard header (green = connected, red = disconnected)

3. Check server logs for room subscription activity:
   ```python
   @socketio.on('join_room')
   def handle_join_room(data):
       room = data.get('room')
       join_room(room)
       emit('room_joined', {'room': room})
   ```

4. Use browser DevTools Network tab to inspect WebSocket frames

---

## Future Improvements

Potential enhancements for the WebSocket system:

1. **Room State Persistence**: Store room subscriptions in localStorage to survive page refreshes
2. **Automatic Panel Detection**: Infer current panel from URL hash for more robust state
3. **Room Health Checks**: Periodically verify room subscriptions are active
4. **Fallback Polling**: Implement HTTP polling fallback when WebSocket fails repeatedly
5. **Connection Quality Monitoring**: Track reconnection frequency and connection duration

---

## Conclusion

The WebSocket refresh fix ensures that real-time dashboard updates continue working correctly after network interruptions or WebSocket reconnections. By dynamically determining which rooms to rejoin based on the current panel, we maintain seamless real-time functionality across all dashboard views.

**Status**: ✅ Fixed and Tested
**Priority**: High (Core functionality)
**Complexity**: Low (Single function modification)
**Risk**: Low (Well-tested, backwards compatible)
