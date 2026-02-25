# Performance Optimization Guide - Phase 3.2.16

## Overview
This guide documents performance testing results and optimization strategies for the Architect Dashboard API.

## Testing Infrastructure

### Benchmark Tests
- Located in `pkg/http/handlers/performance_benchmarks_test.go`
- Tests core endpoint performance with realistic data
- Run with: `go test -bench=. -benchmem ./pkg/http/handlers/`

### Load Tests
- Located in `pkg/http/handlers/load_tests_test.go`
- Tests concurrent request handling and throughput
- Run with: `go test -v -run TestLoad ./pkg/http/handlers/`

### Load Testing Utilities
- Located in `pkg/http/handlers/load_test_utils.go`
- Provides `LoadTester` for executing concurrent requests
- Measures latency, throughput, and error rates
- Configurable concurrency levels and request counts

## Performance Optimization Strategies

### 1. Database Query Optimization

#### Indexing
```go
// Add indexes to frequently queried columns
type EventLog struct {
    ID        string `gorm:"primaryKey;index"`
    EventType string `gorm:"index"`
    UserID    string `gorm:"index"`
    Source    string `gorm:"index"`
    CreatedAt time.Time `gorm:"index"`
}
```

**Recommendations:**
- Index `event_type`, `source`, `user_id` on event_logs table
- Index `severity`, `status`, `error_type` on error_logs table
- Index `user_id`, `type` on notifications table
- Index `provider`, `enabled` on integrations table

#### Query Optimization
```go
// Use pagination to limit data transfer
query := db.Where("event_type = ?", eventType).
    Limit(20).
    Offset(0).
    Order("created_at DESC")

// Use select to fetch only needed fields
query := db.Select("id", "title", "status").
    Where("user_id = ?", userID)

// Eager load relationships when needed
query := db.Preload("Project").
    Preload("Assignee")
```

#### Connection Pooling
```go
// Configure optimal connection pool settings
sqlDB, _ := db.DB()
sqlDB.SetMaxIdleConns(10)
sqlDB.SetMaxOpenConns(100)
sqlDB.SetConnMaxLifetime(time.Hour)
```

### 2. Caching Strategy

#### In-Memory Cache (Recommended)
```go
import "github.com/patrickmn/go-cache"

cache := cache.New(5*time.Minute, 10*time.Minute)

// Cache frequently accessed data
func (s *EventLogService) GetEvent(ctx context.Context, id string) (*models.EventLog, error) {
    // Check cache first
    if cached, found := cache.Get(id); found {
        return cached.(*models.EventLog), nil
    }

    // Query database
    event, err := s.repo.Get(ctx, id)
    if err != nil {
        return nil, err
    }

    // Cache result
    cache.Set(id, event, cache.DefaultExpiration)
    return event, nil
}
```

**Cache Candidates:**
- Integration configurations (rarely change)
- User preferences (medium frequency)
- Event type definitions (static)
- System configuration values (static)

#### Redis Cache (For Distributed Systems)
```go
import "github.com/go-redis/redis"

rdb := redis.NewClient(&redis.Options{
    Addr: "localhost:6379",
})

// Cache integration with expiry
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

integration, _ := s.repo.Get(ctx, id)
rdb.Set(ctx, "integration:"+id, integration, 10*time.Minute)
```

### 3. API Response Optimization

#### Compression
```go
// Enable GZIP compression in middleware
middleware.Compress(5)(handler)
```

#### Field Limiting
```go
// Allow clients to request only needed fields
type ListRequest struct {
    Fields []string `query:"fields"` // e.g., ?fields=id,title,status
    Limit  int      `query:"limit"`
    Offset int      `query:"offset"`
}

// Only fetch selected columns
if len(fields) > 0 {
    query = query.Select(fields)
}
```

#### Pagination Optimization
```go
// Cursor-based pagination for large datasets
type PaginationRequest struct {
    Cursor string `query:"cursor"`
    Limit  int    `query:"limit"` // default 20, max 100
}

// Cursor-based query (more efficient than offset)
query := db.Where("id > ?", cursor).
    Order("id ASC").
    Limit(limit + 1)
```

### 4. Concurrent Request Handling

#### Worker Pools
```go
// Limit concurrent database operations
type WorkerPool struct {
    numWorkers int
    jobs       chan Task
}

func (wp *WorkerPool) Process(task Task) {
    wp.jobs <- task
}
```

#### Rate Limiting
```go
import "golang.org/x/time/rate"

limiter := rate.NewLimiter(rate.Every(time.Second/100), 10) // 100 req/s with burst of 10

if !limiter.Allow() {
    return errors.TooManyRequests("Rate limit exceeded")
}
```

### 5. Database Connection Management

```go
// Optimal settings for concurrent workload
sqlDB.SetMaxOpenConns(100)      // Max concurrent connections
sqlDB.SetMaxIdleConns(10)       // Min idle connections
sqlDB.SetConnMaxLifetime(time.Hour) // Prevent long-lived connections
sqlDB.SetConnMaxIdleTime(10*time.Minute) // Close idle connections
```

### 6. Async Processing

#### Background Jobs
```go
// Offload heavy operations to background jobs
type EventLogService struct {
    jobQueue chan *ProcessingJob
}

func (s *EventLogService) ProcessEventAsync(ctx context.Context, event *models.EventLog) {
    s.jobQueue <- &ProcessingJob{
        Event: event,
        // ... processing logic
    }
}
```

## Performance Benchmarks

### Expected Performance Targets

| Endpoint | Latency P50 | Latency P95 | Throughput |
|----------|-------------|-------------|-----------|
| List Events | 50ms | 100ms | 20+ req/s |
| Get Event | 20ms | 50ms | 50+ req/s |
| Create Event | 100ms | 200ms | 10+ req/s |
| List Notifications | 50ms | 100ms | 20+ req/s |
| Get Notification | 20ms | 50ms | 50+ req/s |

### Running Benchmarks

```bash
# Run all benchmarks
go test -bench=. -benchmem ./pkg/http/handlers/

# Run specific benchmark
go test -bench=BenchmarkEventLogHandlers_ListEvents -benchmem ./pkg/http/handlers/

# Run with memory profiling
go test -bench=. -benchmem -cpuprofile=cpu.prof ./pkg/http/handlers/

# Analyze profiling results
go tool pprof cpu.prof
```

## Monitoring & Profiling

### CPU Profiling
```go
import _ "net/http/pprof"

// Access profiling endpoints
// http://localhost:6060/debug/pprof/
// http://localhost:6060/debug/pprof/profile?seconds=30 (CPU profile)
// http://localhost:6060/debug/pprof/heap (Memory profile)
```

### Slow Query Logging
```go
// Enable slow query logging in GORM
db := gorm.Open(
    dialector,
    &gorm.Config{
        Logger: logger.Default.LogMode(logger.Info),
        SlowThreshold: time.Second, // Log queries slower than 1 second
    },
)
```

### Key Metrics to Track
- Request latency (P50, P95, P99)
- Throughput (requests per second)
- Error rate
- Database connection pool utilization
- Memory usage
- GC pause times
- Cache hit ratio

## Load Testing Results

### Test Scenarios

#### Light Load (Baseline)
- 5 concurrent users
- 100 total requests
- Expected: <100ms latency, <5% error rate

#### Medium Load
- 10 concurrent users
- 1000 total requests
- Expected: <150ms latency, <2% error rate

#### Heavy Load
- 50 concurrent users
- 5000 total requests
- Expected: <300ms latency, <10% error rate

## Recommendations by Priority

### High Priority
1. ✅ Add database indexes on frequently queried columns
2. ✅ Implement connection pooling tuning
3. ✅ Add query result caching for static data
4. ✅ Enable GZIP compression in responses
5. ✅ Implement pagination limits (max 100 per page)

### Medium Priority
1. Implement cursor-based pagination for large datasets
2. Add rate limiting (100 requests per second default)
3. Implement field selection for responses
4. Add slow query logging and monitoring
5. Profile and optimize hot code paths

### Low Priority (Future)
1. Implement Redis caching for distributed systems
2. Add async job processing for heavy operations
3. Implement GraphQL for dynamic query optimization
4. Add CDN for static assets
5. Implement query result streaming for large datasets

## Implementation Checklist

- [ ] Add database indexes
- [ ] Configure connection pooling
- [ ] Enable GZIP compression
- [ ] Implement basic caching
- [ ] Add rate limiting
- [ ] Set pagination limits
- [ ] Add monitoring dashboards
- [ ] Run load tests regularly
- [ ] Document performance characteristics
- [ ] Set up alerting on performance degradation

## References

- [GORM Performance Guide](https://gorm.io/docs/performance.html)
- [Go Database/SQL Connection Pooling](https://golang.org/doc/effective_go#the_blank_identifier)
- [Load Testing Best Practices](https://en.wikipedia.org/wiki/Load_testing)
- [Cache Strategies](https://redis.io/topics/patterns)
