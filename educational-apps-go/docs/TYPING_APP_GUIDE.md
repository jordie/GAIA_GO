# Typing App: Go Implementation Guide

## Overview

Complete migration of the Typing app from Python/Flask to Go/Gin. Includes user management, text generation, WPM calculation, accuracy tracking, and global leaderboards.

## Architecture

### Layered Design

```
HTTP Request
    ↓
[Middleware] - Auth, CORS, logging
    ↓
[Handlers] - Parse input, validate, call services
    ↓
[Services] - Business logic, WPM/accuracy calculation
    ↓
[Repository] - Database queries (GORM)
    ↓
PostgreSQL
```

## Database Schema

### Tables

**users**
- id: uint, primary key
- username: string, unique, not null
- created_at: timestamp
- last_active: timestamp

**typing_results**
- id: uint, primary key
- user_id: uint, foreign key, indexed
- exercise_id: uint (optional)
- wpm: int
- accuracy: float64 (0-100)
- test_type: string (timed, words, accuracy)
- test_duration: int (seconds)
- total_characters: int
- correct_characters: int
- incorrect_characters: int
- created_at: timestamp

**user_stats**
- id: uint, primary key
- user_id: uint, unique, indexed, foreign key
- total_tests: int
- average_wpm: float64
- average_accuracy: float64
- best_wpm: int
- total_time_typed: int (seconds)
- last_updated: timestamp

### Indexes

- users.username
- typing_results.user_id
- typing_results.created_at
- user_stats.user_id

## API Endpoints (10 Total)

### User Management

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/typing/users` | None | Create new user |
| GET | `/api/v1/typing/users/current` | Optional | Get current session user |
| GET | `/api/v1/typing/users` | None | List all users |
| POST | `/api/v1/typing/users/switch` | None | Switch active user |
| DELETE | `/api/v1/typing/users/:id` | Auth | Delete user (admin) |

### Text & Statistics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/typing/text` | None | Generate typing text |
| GET | `/api/v1/typing/stats` | Auth | Get user stats |

### Results & Leaderboard

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/typing/results` | Auth | Save typing result |
| GET | `/api/v1/typing/results` | Auth | Get user's results |
| GET | `/api/v1/typing/leaderboard` | None | Get global leaderboard |

## Models

### User
```go
type User struct {
    ID         uint
    Username   string    // Unique, 2-20 chars
    CreatedAt  time.Time
    LastActive time.Time
}
```

### TypingResult
```go
type TypingResult struct {
    ID                  uint
    UserID              uint
    ExerciseID          *uint
    WPM                 int       // 0-500
    Accuracy            float64   // 0-100
    TestType            string    // timed, words, accuracy
    TestDuration        int       // seconds
    TotalCharacters     int
    CorrectCharacters   int
    IncorrectCharacters int
    CreatedAt           time.Time
}
```

### UserStats
```go
type UserStats struct {
    ID              uint
    UserID          uint
    TotalTests      int
    AverageWPM      float64
    AverageAccuracy float64
    BestWPM         int
    TotalTimeTyped  int       // seconds
    LastUpdated     time.Time
}
```

## Services

### User Service
- **CreateUser** - Create with username validation
- **GetUser** - Get user by ID
- **GetUsers** - List all users
- **SwitchUser** - Switch active user
- **DeleteUser** - Remove user and associated data

### Text Service
- **GenerateText** - Generate typing text from categories or random words
- **GetUserStats** - Aggregated user statistics

### Result Service
- **SaveResult** - Save test result and update stats
- **GetUserResults** - Paginated results for user
- **GetLeaderboard** - Top WPM and accuracy scores

## Text Generation

### Categories Available

1. **common_words** - Pangram sentences and basic English
2. **programming** - Code snippets and technical content
3. **quotes** - Famous quotes and sayings
4. **numbers** - Numeric sequences and formatted numbers
5. **special_characters** - Punctuation and symbols

### Generation Modes

| Mode | Description | Usage |
|------|-------------|-------|
| words | Generate N random common words | WPM practice |
| time | Generate text for timed test | 60-second challenge |
| category | Select random text from category | Specific content |

## Calculation Logic

### WPM (Words Per Minute)
```
WPM = (Total Characters Typed / 5) / (Time in Minutes)
- Standard: 5 characters = 1 word
- Example: 300 chars in 1 min = 60 WPM
```

### Accuracy
```
Accuracy = (Correct Characters / Total Characters) * 100
- Range: 0-100%
- Calculates character-by-character match
```

### User Stats Updates
After each test result:
1. Calculate new averages
2. Update best WPM if current > previous
3. Add test duration to total time
4. Update last_updated timestamp

**Formula for New Average**:
```
new_avg = ((old_avg * old_count) + new_value) / (old_count + 1)
```

## Request/Response Examples

### Create User
**Request**:
```json
POST /api/v1/typing/users
{
  "username": "speedtyper"
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "user_id": 1,
  "username": "speedtyper"
}
```

### Generate Text
**Request**:
```json
POST /api/v1/typing/text
{
  "type": "words",
  "word_count": 50
}
```

**Response** (200 OK):
```json
{
  "text": "the quick brown fox jumps over lazy dogs pack my box with five dozen liquor jugs...",
  "word_count": 50,
  "character_count": 287,
  "category": "common_words"
}
```

### Save Result
**Request**:
```json
POST /api/v1/typing/results
{
  "wpm": 85,
  "accuracy": 92.5,
  "test_type": "timed",
  "test_duration": 60,
  "total_characters": 500,
  "correct_characters": 462,
  "incorrect_characters": 38
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "result": {
    "id": 42,
    "wpm": 85,
    "accuracy": 92.5,
    "test_type": "timed",
    "test_duration": 60,
    "created_at": "2026-02-20T15:30:00Z"
  }
}
```

### Get Leaderboard
**Request**:
```
GET /api/v1/typing/leaderboard?limit=10
```

**Response** (200 OK):
```json
{
  "top_wpm": [
    {
      "rank": 1,
      "username": "speedtyper",
      "wpm": 145,
      "accuracy": 98.5,
      "test_type": "timed",
      "date": "2026-02-20T14:22:00Z"
    },
    {
      "rank": 2,
      "username": "quickfingers",
      "wpm": 138,
      "accuracy": 97.2,
      "test_type": "timed",
      "date": "2026-02-20T13:45:00Z"
    }
  ],
  "top_accuracy": [
    {
      "rank": 1,
      "username": "perfecttype",
      "wpm": 75,
      "accuracy": 99.8,
      "test_type": "words",
      "date": "2026-02-20T12:30:00Z"
    }
  ]
}
```

## Testing

### Unit Tests
- **40+ tests** covering all services
- Text generation for all categories
- WPM/accuracy calculation validation
- Statistics aggregation logic
- Boundary value testing

**Run Tests**:
```bash
go test -v ./internal/typing/...
go test -v -cover ./internal/typing/...
```

### Integration Tests
- HTTP handler verification
- Request/response validation
- Error handling
- Status code verification

**Coverage Target**: 75-85%

## Performance Characteristics

### Expected Results vs Python

| Metric | Python | Go | Improvement |
|--------|--------|-----|------------|
| Startup | 2,000ms | <100ms | 20x |
| Memory | 50MB | 12MB | 4x |
| Request Latency | 100ms | <10ms | 10x |
| Throughput | 1,000 req/s | 20,000 req/s | 20x |

### Optimizations

1. **Pagination** - All list endpoints limit results
2. **Indexes** - Database indexes on frequently queried columns
3. **Connection Pool** - Max 100 concurrent connections
4. **Leaderboard Caching** - 5-minute TTL (can be added)
5. **Goroutines** - Lightweight concurrency for I/O

## Code Patterns

### Pattern: Service Validation
```go
// Validate input before database operations
func SaveResult(userID uint, req SaveResultRequest) error {
    // Type validation
    if err := validation.ValidateIntRange(req.WPM, 0, 500); err != nil {
        return errors.BadRequest("invalid WPM")
    }

    // Business logic validation
    if req.TotalCharacters < req.CorrectCharacters {
        return errors.BadRequest("invalid character counts")
    }

    // Database operation
    return repository.CreateResult(result)
}
```

### Pattern: Stats Update
```go
// Update stats after result saved
func UpdateStats(userID uint, result *TypingResult) error {
    stats, err := repository.GetStatsByUserID(userID)
    if err != nil {
        // Create new stats if doesn't exist
        stats = &UserStats{UserID: userID}
        return repository.CreateStats(stats)
    }

    // Calculate new averages
    newAvgWPM := ((stats.AverageWPM * count) + result.WPM) / (count + 1)

    // Update database
    return repository.UpdateStats(userID, newAvgWPM, ...)
}
```

## File Structure

```
internal/typing/
├── handlers/
│   ├── user_handlers.go           (100 lines)
│   ├── result_handlers.go         (90 lines)
│   ├── text_handlers.go           (70 lines)
│   └── handlers_integration_test.go (300 lines)
│
├── models/
│   └── typing_models.go           (250 lines)
│
├── services/
│   ├── user_service.go            (60 lines)
│   ├── result_service.go          (120 lines)
│   ├── text_service.go            (220 lines)
│   └── typing_service_test.go     (250 lines)
│
└── repository/
    ├── user_repository.go         (100 lines)
    ├── result_repository.go       (120 lines)
    └── stats_repository.go        (100 lines)
```

## Deployment

### Database Migration
Run migrations before startup:
```sql
-- Schema already defined in migrations/001_initial_schema.up.sql
-- Tables: users, typing_results, user_stats
```

### Environment Variables
```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=educational_apps
```

### Health Checks
```bash
GET /health - Returns 200 OK if healthy
```

## Debugging

### Enable SQL Logging
```go
DB := gorm.Open(postgres.Open(dsn), &gorm.Config{
    Logger: logger.Default.LogMode(logger.Info),
})
```

### Check Query Performance
```bash
# Use EXPLAIN ANALYZE for slow queries
EXPLAIN ANALYZE
SELECT * FROM typing_results
WHERE user_id = 1
ORDER BY created_at DESC
LIMIT 20;
```

## Migration Checklist

- [x] Models defined (GORM structs)
- [x] Repositories implemented (CRUD + aggregates)
- [x] Services implemented (business logic)
- [x] Handlers implemented (HTTP endpoints)
- [x] Request/response models
- [x] Error handling (typed errors)
- [x] Validation (input constraints)
- [x] Unit tests (40+ tests)
- [x] Integration tests (10 endpoints)
- [x] Documentation complete
- [x] Routes wired in main.go
- [ ] End-to-end testing
- [ ] Load testing
- [ ] Production deployment
- [ ] Performance validation

## Comparison: Python → Go

### Key Improvements

1. **Concurrency**: Python single-threaded → Go goroutines (millions possible)
2. **Memory**: Python GC overhead → Go efficient GC
3. **Speed**: Interpreted → Compiled native code
4. **Type Safety**: Dynamic → Compile-time type checking
5. **Deployment**: Runtime + dependencies → Single binary

### Architectural Changes

1. **Explicit Error Handling**: Exceptions → error returns
2. **Validation Layer**: Flask decorators → Service validation
3. **Type Safety**: Dynamic types → Go structs
4. **Concurrency**: Threading → Goroutines

## References

- [GORM Documentation](https://gorm.io/)
- [Gin Framework](https://gin-gonic.com/)
- [Go Error Handling](https://golang.org/doc/effective_go#errors)
- [PostgreSQL Queries](https://www.postgresql.org/docs/15/queries.html)
