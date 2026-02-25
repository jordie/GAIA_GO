# Database Optimization Guide

## Index Strategy

### EventLog Table Indexes
```sql
-- Primary key (implicit)
CREATE INDEX idx_event_logs_id ON event_logs(id);

-- Query filters
CREATE INDEX idx_event_logs_event_type ON event_logs(event_type);
CREATE INDEX idx_event_logs_source ON event_logs(source);
CREATE INDEX idx_event_logs_user_id ON event_logs(user_id);
CREATE INDEX idx_event_logs_project_id ON event_logs(project_id);

-- Sorting/filtering combinations
CREATE INDEX idx_event_logs_user_type ON event_logs(user_id, event_type);
CREATE INDEX idx_event_logs_type_created ON event_logs(event_type, created_at DESC);

-- Time-based queries
CREATE INDEX idx_event_logs_created_at ON event_logs(created_at DESC);
```

### ErrorLog Table Indexes
```sql
CREATE INDEX idx_error_logs_severity ON error_logs(severity);
CREATE INDEX idx_error_logs_status ON error_logs(status);
CREATE INDEX idx_error_logs_error_type ON error_logs(error_type);
CREATE INDEX idx_error_logs_source ON error_logs(source);
CREATE INDEX idx_error_logs_severity_created ON error_logs(severity, created_at DESC);
CREATE INDEX idx_error_logs_created_at ON error_logs(created_at DESC);
```

### Notification Table Indexes
```sql
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_user_read ON notifications(user_id, read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);
```

### Integration Table Indexes
```sql
CREATE INDEX idx_integrations_type ON integrations(type);
CREATE INDEX idx_integrations_provider ON integrations(provider);
CREATE INDEX idx_integrations_enabled ON integrations(enabled);
CREATE INDEX idx_integrations_type_enabled ON integrations(type, enabled);
```

## Query Optimization Patterns

### Efficient List Queries
```go
// ✅ GOOD - Uses indexes, limits results
query := db.
    Where("event_type = ?", eventType).
    Order("created_at DESC").
    Limit(20).
    Offset(offset).
    Find(&events)

// ❌ BAD - No limit, full table scan
query := db.
    Where("event_type = ?", eventType).
    Find(&events)
```

### Efficient Filtering
```go
// ✅ GOOD - Uses indexes, minimal data
query := db.
    Select("id", "title", "status", "created_at").
    Where("user_id = ? AND type = ?", userID, notificationType).
    Find(&notifications)

// ❌ BAD - Fetches all columns, multiple queries
query := db.Where("user_id = ?", userID).Find(&notifications)
for _, n := range notifications {
    if n.Type != notificationType {
        continue
    }
}
```

### Batch Operations
```go
// ✅ GOOD - Single batch insert
db.CreateInBatches(events, 1000)

// ❌ BAD - One insert per iteration
for _, event := range events {
    db.Create(event)
}
```

## Connection Pool Configuration

### Recommended Settings
```go
sqlDB, _ := db.DB()

// For light load (small deployments)
sqlDB.SetMaxOpenConns(25)
sqlDB.SetMaxIdleConns(5)
sqlDB.SetConnMaxLifetime(time.Hour)
sqlDB.SetConnMaxIdleTime(10 * time.Minute)

// For medium load
sqlDB.SetMaxOpenConns(100)
sqlDB.SetMaxIdleConns(10)
sqlDB.SetConnMaxLifetime(time.Hour)
sqlDB.SetConnMaxIdleTime(10 * time.Minute)

// For heavy load
sqlDB.SetMaxOpenConns(500)
sqlDB.SetMaxIdleConns(50)
sqlDB.SetConnMaxLifetime(30 * time.Minute)
sqlDB.SetConnMaxIdleTime(5 * time.Minute)
```

## Query Profiling

### Enable Slow Query Logging
```go
import "gorm.io/logger"

db := gorm.Open(
    postgres.Open(dsn),
    &gorm.Config{
        Logger: logger.Default.LogMode(logger.Info),
        SlowThreshold: time.Second,
    },
)
```

### Analyze Query Performance
```go
// Check explain plan
var result []map[string]interface{}
db.Raw("EXPLAIN ANALYZE SELECT * FROM event_logs WHERE event_type = ?", "user_action").
    Scan(&result)
```

## Materialized Views (for Complex Queries)

### Event Statistics View
```sql
CREATE MATERIALIZED VIEW event_logs_stats AS
SELECT
    event_type,
    source,
    DATE(created_at) as date,
    COUNT(*) as count,
    COUNT(DISTINCT user_id) as unique_users
FROM event_logs
GROUP BY event_type, source, DATE(created_at);

-- Refresh periodically
REFRESH MATERIALIZED VIEW CONCURRENTLY event_logs_stats;
```

### Error Summary View
```sql
CREATE MATERIALIZED VIEW error_logs_summary AS
SELECT
    error_type,
    severity,
    COUNT(*) as count,
    COUNT(DISTINCT source) as sources,
    MAX(created_at) as last_occurrence
FROM error_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY error_type, severity;
```

## Data Retention Policy

### Archive Old Records
```go
// Move old events to archive table
const archiveQuery = `
INSERT INTO event_logs_archive
SELECT * FROM event_logs
WHERE created_at < NOW() - INTERVAL '90 days';

DELETE FROM event_logs
WHERE created_at < NOW() - INTERVAL '90 days';
`

// Run daily
db.Exec(archiveQuery)
```

### Table Partitioning
```sql
-- Partition by date (for very large tables)
CREATE TABLE event_logs (
    id VARCHAR(36),
    event_type VARCHAR(100),
    created_at TIMESTAMP,
    ...
) PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION future VALUES LESS THAN MAXVALUE
);
```

## Caching Database Results

### Query Result Caching
```go
type CachedRepository struct {
    repo repository.EventLogRepository
    cache *Cache
}

func (cr *CachedRepository) GetByType(ctx context.Context, eventType string, limit, offset int) {
    cacheKey := fmt.Sprintf("events:type:%s:%d:%d", eventType, limit, offset)

    if cached, ok := cr.cache.Get(cacheKey); ok {
        return cached
    }

    result, err := cr.repo.GetByType(ctx, eventType, limit, offset)
    if err == nil {
        cr.cache.Set(cacheKey, result, 5*time.Minute)
    }

    return result, err
}
```

## Performance Monitoring Queries

### Index Usage Statistics
```sql
-- PostgreSQL: Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### Query Performance Metrics
```sql
-- PostgreSQL: Slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
WHERE query LIKE '%event_logs%'
ORDER BY mean_time DESC;
```

### Table Size Analysis
```sql
-- PostgreSQL: Table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Migration Strategy

### Safely Add Indexes
```sql
-- Non-blocking index creation (PostgreSQL)
CREATE INDEX CONCURRENTLY idx_event_logs_new ON event_logs(event_type);

-- Then remove old index if needed
DROP INDEX CONCURRENTLY idx_event_logs_old;
```

## Backup Strategy

### Regular Backups
```bash
# Full backup
pg_dump architect_db > backup_full_$(date +%Y%m%d).sql

# Incremental backup (WAL)
pg_basebackup -D ./backup_$(date +%Y%m%d) -Ft -z -P

# Point-in-time recovery
pg_restore -d architect_db backup_full_20240217.sql
```

## Performance Checklist

- [ ] Create all recommended indexes
- [ ] Set optimal connection pool settings
- [ ] Enable slow query logging
- [ ] Implement query result caching
- [ ] Set up data retention/archival
- [ ] Monitor index usage regularly
- [ ] Profile slow queries monthly
- [ ] Document query optimization decisions
- [ ] Set up alerting for performance degradation
- [ ] Plan capacity based on growth trends
