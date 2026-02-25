# Real-Time Multiplayer Typing Races

## Overview

The typing app now supports real-time multiplayer racing where 2-4 players compete simultaneously. The system uses WebSockets for real-time communication and preserves existing AI race mode functionality.

## Architecture

```
Client (Browser) ──HTTP──> Lobby Endpoints (create/list/join rooms)
       │
       └──WebSocket──> GameRoomManager ──> GameRoom 1 (waiting)
                              │          ├─> GameRoom 2 (racing)
                              │          └─> GameRoom N (finished)
                              │
                              └──> WebSocketHub (broadcasting)
```

### Race Lifecycle

1. **Create room** (HTTP) → waiting state
2. **Players join** (WebSocket) → mark ready
3. **All ready** → 3-second countdown → racing state
4. **Players type** → broadcast progress updates
5. **All finish** → calculate placements → award XP → finished state
6. **Cleanup** after 5 minutes

## Files Structure

### New Files Created

- `pkg/apps/typing/multiplayer/messages.go` - WebSocket message types (join, ready, progress, finish, etc.)
- `pkg/apps/typing/multiplayer/websocket_hub.go` - WebSocket connection management, authentication, broadcasting
- `pkg/apps/typing/multiplayer/player.go` - PlayerConnection wrapper with progress tracking
- `pkg/apps/typing/multiplayer/game_room.go` - Game room state machine (waiting→countdown→racing→finished)
- `pkg/apps/typing/multiplayer/room_manager.go` - Room lifecycle and cleanup
- `pkg/apps/typing/multiplayer/errors.go` - Error definitions
- `pkg/apps/typing/multiplayer/rate_limiter.go` - Token bucket rate limiting and progress validation
- `pkg/apps/typing/multiplayer/multiplayer_test.go` - Unit tests
- `pkg/apps/typing/multiplayer_handlers.go` - HTTP and WebSocket handlers
- `migrations/002_multiplayer_typing.sql` - Database schema

### Modified Files

- `pkg/apps/typing/handlers.go` - Registers multiplayer routes
- `go.mod` - Added github.com/gorilla/websocket v1.5.3

## API Endpoints

### HTTP (Lobby Management)

- `POST /api/typing/multiplayer/rooms` - Create room
  ```json
  {
    "name": "Cool Race",
    "difficulty": "medium",
    "word_count": 30
  }
  ```

- `GET /api/typing/multiplayer/rooms` - List available rooms

- `DELETE /api/typing/multiplayer/rooms/:room_id` - Leave/delete room

- `GET /api/typing/multiplayer/history` - User's race history

- `GET /api/typing/multiplayer/stats` - User's multiplayer stats

### WebSocket (Real-Time Racing)

- `GET /ws/typing/race/:room_id?session_id=xxx` - Race connection

**Client → Server Messages:**
- `join` - Join room
- `ready` - Mark ready to start
- `progress` - Typing progress {position, wpm, accuracy}
- `finish` - Complete race {wpm, accuracy, time}
- `leave` - Leave room
- `ping` - Heartbeat

**Server → Client Messages:**
- `player_joined` - New player entered
- `player_left` - Player exited
- `player_ready` - Ready status changed
- `countdown` - Race countdown (3, 2, 1)
- `race_start` - Race begins {text, players}
- `player_update` - Progress update broadcast
- `player_finished` - Player completed race
- `race_complete` - All players finished with results
- `error` - Error message
- `pong` - Heartbeat response

## Database Schema

### race_rooms Table

Stores active and completed races:
- `id` - Unique room ID
- `name` - Room name
- `host_user_id` - Creator of room
- `race_text` - Text to type in race
- `word_count` - Number of words
- `difficulty` - Race difficulty (easy, medium, hard)
- `max_players` - Maximum players allowed (default: 4)
- `min_players` - Minimum to start (default: 2)
- `state` - Room state (waiting, countdown, racing, finished)
- `created_at`, `started_at`, `finished_at` - Timestamps

### race_participants Table

Stores results for each player in a race:
- `race_id` - Foreign key to race_rooms
- `user_id` - Player's user ID
- `username` - Player's username
- `placement` - Final placement (1st, 2nd, 3rd, 4th)
- `wpm` - Final words per minute
- `accuracy` - Final accuracy percentage
- `race_time` - Total race duration
- `xp_earned` - XP awarded for this race

## Key Concurrency Patterns

### Room Access (RWMutex)

```go
// Read with RLock
func (m *GameRoomManager) GetRoom(id string) (*GameRoom, error) {
    m.mu.RLock()
    room, exists := m.rooms[id]
    m.mu.RUnlock()
    return room, nil
}

// Write with Lock
func (m *GameRoomManager) CreateRoom(...) (*GameRoom, error) {
    m.mu.Lock()
    defer m.mu.Unlock()
    m.rooms[roomID] = room
    return room, nil
}
```

### Non-Blocking Broadcast

```go
func (r *GameRoom) Broadcast(message []byte) {
    r.PlayersMutex.RLock()
    defer r.PlayersMutex.RUnlock()

    for _, player := range r.Players {
        select {
        case player.SendChan <- message:
            // Queued successfully
        default:
            // Channel full, skip (slow client)
        }
    }
}
```

### Background Cleanup

```go
func (m *GameRoomManager) cleanupStaleRooms() {
    ticker := time.NewTicker(1 * time.Minute)
    for range ticker.C {
        m.mu.Lock()
        for id, room := range m.rooms {
            if shouldCleanup(room) {
                delete(m.rooms, id)
            }
        }
        m.mu.Unlock()
    }
}
```

## Security & Validation

### Authentication

- Extract `session_id` from WebSocket query params
- Validate with existing session.Manager
- Reject expired/invalid sessions

### Progress Validation

- Position can't go backwards
- Position can't skip >5 chars (network buffer tolerance)
- WPM must be <250 (world record is ~216)
- Accuracy must be 0-100

### Rate Limiting

- Max 20 messages/sec per connection (token bucket)
- Room name validation (alphanumeric, spaces, hyphens)
- Input sanitization for SQL queries

## State Machine

```
[WAITING] ─── Player joins
    │
    ├─ All ready & >= minPlayers
    │
[COUNTDOWN] ─── 3 second countdown
    │
    ├─ 0 seconds
    │
[RACING] ─── Players type and finish
    │
    ├─ All players finished OR 5 min timeout
    │
[FINISHED] ─── Save results to DB
    │
    └─ Cleanup after 5 minutes
```

## XP Calculation

Same as AI races:
- **Base XP**: 10
- **Placement Bonus**: 1st=50, 2nd=30, 3rd=15, 4th=0
- **Accuracy Bonus**: 100%=25, ≥95%=15, <95%=0
- **Speed Bonus**: ≥60 WPM=20, ≥40 WPM=10, <40=0
- **Difficulty Multiplier**: easy=1.0x, medium=1.2x, hard=1.5x

## Backward Compatibility

- ✅ Zero breaking changes to existing AI race endpoints
- ✅ `POST /api/typing/race/start` still returns AI opponents
- ✅ `POST /api/typing/race/finish` still saves AI results
- ✅ New columns have DEFAULT 0 (no migration issues)
- ✅ Existing racing_stats rows work without modification

## Running Locally

### Apply Migrations

```bash
# Migrations run automatically on server startup via go-migrate or similar
# Or manually: sqlite3 app.db < migrations/002_multiplayer_typing.sql
```

### Test the Multiplayer System

```bash
# Run unit tests
go test -v ./pkg/apps/typing/multiplayer/...

# Run full typing app tests
go test -v ./pkg/apps/typing/...

# Build the app
go build -o app ./cmd/main.go
./app
```

### Test Endpoints

```bash
# Create a multiplayer room
curl -X POST http://localhost:8080/api/typing/multiplayer/rooms \
  -H "X-Session-ID: YOUR_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Speed Racing",
    "difficulty": "medium",
    "word_count": 30
  }'

# List available rooms
curl http://localhost:8080/api/typing/multiplayer/rooms

# Get user stats
curl http://localhost:8080/api/typing/multiplayer/stats \
  -H "X-Session-ID: YOUR_SESSION_ID"
```

## Joining a Race (WebSocket)

```javascript
const roomId = "room-uuid-from-create";
const sessionId = "your-session-id";
const ws = new WebSocket(`ws://localhost:8080/ws/typing/race/${roomId}?session_id=${sessionId}`);

ws.onopen = () => {
  // Join the room
  ws.send(JSON.stringify({
    type: "join",
    room_id: roomId,
    payload: {
      room_id: roomId,
      username: "Your Name",
      user_id: 123
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log("Message type:", msg.type);
  console.log("Payload:", msg.payload);
};

// Mark ready
ws.send(JSON.stringify({
  type: "ready",
  room_id: roomId,
  payload: { is_ready: true }
}));

// Send progress updates
ws.send(JSON.stringify({
  type: "progress",
  room_id: roomId,
  payload: {
    position: 45,
    wpm: 72,
    accuracy: 97.3
  }
}));

// Finish race
ws.send(JSON.stringify({
  type: "finish",
  room_id: roomId,
  payload: {
    wpm: 75,
    accuracy: 98.1,
    race_time: 23.456
  }
}));
```

## Performance Considerations

- **Non-blocking sends**: Buffered channels (64 messages) prevent slow clients from blocking
- **Cleanup**: Background goroutine removes finished rooms after 5 minutes
- **Rate limiting**: Token bucket prevents message floods
- **Connection limits**: Max 1000 concurrent rooms per manager

## Future Enhancements

- [ ] Private/password-protected rooms
- [ ] Replay system for completed races
- [ ] Spectator mode
- [ ] Ranked matchmaking
- [ ] Tournament support
- [ ] Custom race texts/categories
- [ ] Friend challenges

## Testing

All tests pass:
```
✓ TestGameRoomCreation - Room initialization
✓ TestPlayerConnection - Progress validation
✓ TestRateLimiter - Token bucket rate limiting
✓ TestValidRoomName - Room name validation
```

Run tests with:
```bash
go test -v ./pkg/apps/typing/multiplayer/...
```
