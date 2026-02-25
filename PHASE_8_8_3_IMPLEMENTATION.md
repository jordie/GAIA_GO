# Phase 8.8.3: Cross-App Broadcast Handlers Implementation

**Status**: READY TO QUEUE
**Priority**: 8
**Location**: `pkg/dashboard/sync_broadcaster.go`
**Language**: Go
**Estimated LOC**: 350+
**Estimated Time**: 6-8 hours

---

## Overview

Implement `SyncBroadcaster` to enable real-time cross-application data synchronization across 4 educational apps:
- **Typing App** - WPM (0-200) → normalize to 0-100
- **Math App** - Accuracy (0-100%) → already normalized
- **Reading App** - Comprehension (0-100%) → already normalized
- **Piano App** - Composite Score (0-1000) → normalize to 0-100

## Critical Requirement: Phase 8.8.1 Must Be Complete First

This phase depends on data structures defined in Phase 8.8.1:
- User progress models
- Leaderboard entries
- Achievement records
- Session state

**BLOCKER**: Cannot proceed without Phase 8.8.1 being available in imports.

---

## Architecture

### SyncBroadcaster Struct

```go
type SyncBroadcaster struct {
    mu sync.RWMutex
    eventBus *events.Bus
    realtimeHub *realtime.Hub
    metrics map[string]interface{}
    cache map[string]CachedBroadcast
}

type CachedBroadcast struct {
    Data interface{}
    Timestamp time.Time
    TTL time.Duration
}
```

### Key Methods

1. **BroadcastUserProgress()**
   - Aggregates user stats across all 4 apps
   - Normalizes metrics to 0-100 scale
   - Broadcasts to `user:{id}:sync:all` channel
   - Non-blocking with goroutine

2. **BroadcastCrossAppLeaderboard()**
   - Calculates unified rankings
   - Combines normalized scores
   - Broadcasts to `sync:leaderboard` channel
   - Updates every 30 seconds or on significant change

3. **PropagateAchievements()**
   - Listens to achievement events from each app
   - Publishes unified achievement event
   - Broadcasts to `sync:achievements` channel
   - Triggers notifications for users

4. **BroadcastSessionActivity()**
   - Collects activity from all active sessions
   - Broadcasts to `activity:all-apps` channel
   - Includes: app name, user ID, activity type, timestamp
   - Rate-limited to 1 broadcast per second

5. **HandleAppSpecificUpdates()**
   - Routes app-specific metrics
   - Handles failures gracefully
   - Retries with exponential backoff
   - Logs errors without panicking

---

## Channel Naming Convention

All broadcasts use consistent naming pattern:

```
{category}:{subcategory}:{identifier}
```

**Examples:**
- `user:123:sync:all` - All cross-app updates for user 123
- `sync:leaderboard` - Global leaderboard updates
- `sync:leaderboard:typing` - Typing app leaderboard
- `sync:achievements` - Achievement notifications
- `activity:all-apps` - Global activity stream
- `app:typing:metrics` - Typing app metrics
- `app:math:metrics` - Math app metrics
- `app:reading:metrics` - Reading app metrics
- `app:piano:metrics` - Piano app metrics

---

## Normalization Algorithm

Each app returns metrics on different scales. Implementation must normalize:

### Typing App
```go
normalizedWPM := actualWPM / 2.0  // 0-200 → 0-100
```

### Math App
```go
normalizedAccuracy := accuracy  // 0-100 already
```

### Reading App
```go
normalizedComprehension := comprehension  // 0-100 already
```

### Piano App
```go
normalizedScore := pianoScore / 10.0  // 0-1000 → 0-100
```

### Combined Score
```go
combinedScore := (normalizedWPM + normalizedAccuracy +
                  normalizedComprehension + normalizedScore) / 4.0
```

---

## Integration Points

### Event Bus Integration

```go
// Listen for events from each app
broadcaster.eventBus.Subscribe("typing:progress", broadcaster.handleTypingUpdate)
broadcaster.eventBus.Subscribe("math:progress", broadcaster.handleMathUpdate)
broadcaster.eventBus.Subscribe("reading:progress", broadcaster.handleReadingUpdate)
broadcaster.eventBus.Subscribe("piano:progress", broadcaster.handlePianoUpdate)

// Publish unified events
broadcaster.eventBus.Publish(&events.Event{
    Type: "sync:user_progress",
    UserID: userID,
    App: "all",
    Data: progress,
})
```

### Realtime Hub Integration

```go
// Broadcast to WebSocket clients
broadcaster.realtimeHub.Broadcast("user:123:sync:all", map[string]interface{}{
    "typing_score": 75,
    "math_score": 82,
    "reading_score": 88,
    "piano_score": 79,
    "combined": 81,
    "timestamp": time.Now(),
})
```

---

## Thread Safety Pattern

All implementations must use RWMutex:

```go
func (sb *SyncBroadcaster) BroadcastUserProgress(userID uint) error {
    sb.mu.RLock()
    defer sb.mu.RUnlock()

    // Read operations only
    metrics, exists := sb.metrics[fmt.Sprintf("user:%d", userID)]
    if !exists {
        return fmt.Errorf("user %d not found", userID)
    }

    // Broadcast in non-blocking goroutine
    go func() {
        sb.realtimeHub.Broadcast(
            fmt.Sprintf("user:%d:sync:all", userID),
            metrics,
        )
    }()

    return nil
}
```

---

## Non-Blocking Broadcast Pattern

Always use goroutines to avoid blocking:

```go
// ✅ CORRECT: Non-blocking
go func() {
    if err := sb.realtimeHub.Broadcast(channel, data); err != nil {
        log.WithError(err).Warn("broadcast failed")
        // No panic, continue
    }
}()

// ❌ WRONG: Blocking
sb.realtimeHub.Broadcast(channel, data)  // Blocks caller
```

---

## Error Handling

**Rule**: Errors are logged, never panic

```go
func (sb *SyncBroadcaster) BroadcastSessionActivity(activity Activity) {
    go func() {
        if err := sb.realtimeHub.Broadcast("activity:all-apps", activity); err != nil {
            log.WithFields(log.Fields{
                "activity": activity.Type,
                "user_id": activity.UserID,
                "error": err,
            }).Error("session activity broadcast failed")
            // Continue despite error
        }
    }()
}
```

---

## Caching Strategy

Cache recent broadcasts to avoid redundant processing:

```go
const (
    LeaderboardCacheTTL = 30 * time.Second
    AchievementCacheTTL = 1 * time.Minute
    ActivityCacheTTL = 5 * time.Second
)

func (sb *SyncBroadcaster) shouldBroadcast(key string, ttl time.Duration) bool {
    sb.mu.RLock()
    defer sb.mu.RUnlock()

    if cached, exists := sb.cache[key]; exists {
        if time.Since(cached.Timestamp) < ttl {
            return false  // Skip, still cached
        }
    }
    return true
}
```

---

## Testing Strategy

### Unit Tests

1. **Test metric normalization**
   ```go
   func TestNormalizeTypingScore(t *testing.T) {
       wpm := 140.0
       normalized := normalizeTypingScore(wpm)
       assert.Equal(t, 70.0, normalized)  // 140/2 = 70
   }
   ```

2. **Test non-blocking broadcasts**
   ```go
   func TestBroadcastNonBlocking(t *testing.T) {
       done := make(chan bool)
       go func() {
           broadcaster.BroadcastUserProgress(123)
           done <- true
       }()

       // Should complete quickly (non-blocking)
       select {
       case <-done:
           // Success
       case <-time.After(100 * time.Millisecond):
           t.Fatal("broadcast blocked")
       }
   }
   ```

3. **Test thread safety**
   ```go
   func TestThreadSafety(t *testing.T) {
       var wg sync.WaitGroup
       for i := 0; i < 100; i++ {
           wg.Add(1)
           go func(id int) {
               defer wg.Done()
               broadcaster.BroadcastUserProgress(uint(id))
           }(i)
       }
       wg.Wait()  // Should not deadlock
   }
   ```

4. **Test error handling**
   ```go
   func TestErrorHandling(t *testing.T) {
       broadcaster.realtimeHub = &FailingHub{}
       broadcaster.BroadcastUserProgress(123)  // Should not panic
       // Check logs for error message
   }
   ```

---

## Success Criteria Checklist

- [ ] SyncBroadcaster struct with mutex
- [ ] BroadcastUserProgress() with normalization
- [ ] BroadcastCrossAppLeaderboard() with rankings
- [ ] PropagateAchievements() with event publishing
- [ ] BroadcastSessionActivity() with rate limiting
- [ ] HandleAppSpecificUpdates() with retry logic
- [ ] All methods non-blocking (goroutines)
- [ ] All methods thread-safe (RWMutex)
- [ ] Error logging (no panics)
- [ ] Caching strategy implemented
- [ ] Channel naming consistent
- [ ] Unit tests with >80% coverage
- [ ] Integration with event bus working
- [ ] Integration with realtime hub working
- [ ] 350+ lines of code
- [ ] No deadlocks under concurrent load

---

## Queue Command

```bash
os: Implement Phase 8.8.3 - Cross-App Broadcast Handlers for GAIA dashboard --priority 8
```

---

## References

- Phase 8.8.1: Data structures (dependency)
- `/tmp/phase_8_8_context.txt`: Architectural guidance
- `pkg/events`: Event bus documentation
- `pkg/realtime`: Realtime hub API
- GAIA_HOME: Infrastructure context

---

**Status**: READY FOR IMPLEMENTATION
**Next**: Queue to available developer
