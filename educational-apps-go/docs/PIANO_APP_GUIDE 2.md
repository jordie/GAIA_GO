# Piano App: Python-to-Go Implementation Guide

## Overview

This guide documents the complete Piano app migration from Python/Flask to Go/Gin, including code patterns, API endpoints, and testing strategies.

## Architecture

### Layer Structure

```
HTTP Request
    ↓
[Middleware] - Auth, CORS, logging
    ↓
[Handlers] - Parse input, call services
    ↓
[Services] - Business logic, validation
    ↓
[Repository] - Database access
    ↓
[Database] - PostgreSQL
```

### Directory Structure

```
internal/piano/
├── handlers/              # HTTP handlers
│   ├── exercise_handlers.go
│   ├── attempt_handlers.go
│   ├── progress_handlers.go
│   └── *_test.go
├── models/               # Data structures
│   └── piano_models.go
├── services/            # Business logic
│   ├── exercise_service.go
│   ├── attempt_service.go
│   ├── progress_service.go
│   └── *_test.go
└── repository/          # Database access
    ├── exercise_repository.go
    ├── attempt_repository.go
    └── progress_repository.go
```

## Code Translation Patterns

### Pattern 1: Python Flask Route → Go Gin Handler

#### Python (Flask)
```python
@app.route('/api/piano/exercises', methods=['GET'])
def get_exercises():
    difficulty = request.args.get('difficulty', type=int)
    page = request.args.get('page', default=1, type=int)

    if page < 1:
        return jsonify({'error': 'invalid page'}), 400

    exercises = db.query(Exercise).filter_by(
        difficulty_level=difficulty
    ).paginate(page=page, per_page=20)

    return jsonify({
        'total': exercises.total,
        'page': page,
        'data': exercises.items
    }), 200
```

#### Go (Gin)
```go
func GetExercises(c *gin.Context) {
    // Query parameters
    difficulty := c.Query("difficulty")
    page := c.DefaultQuery("page", "1")
    pageSize := c.DefaultQuery("page_size", "20")

    // Parse and validate
    pageNum, err := strconv.Atoi(page)
    if err != nil || pageNum < 1 {
        middleware.JSONErrorResponse(c, errors.BadRequest("invalid page"))
        return
    }

    pageSizeNum, err := strconv.Atoi(pageSize)
    if err != nil || pageSizeNum < 1 {
        pageSizeNum = 20
    }

    var difficultyLevel *int
    if difficulty != "" {
        d, _ := strconv.Atoi(difficulty)
        difficultyLevel = &d
    }

    // Call service
    result, err := services.GetExercises(difficultyLevel, pageNum, pageSizeNum)
    if err != nil {
        middleware.JSONErrorResponse(c, err)
        return
    }

    c.JSON(200, result)
}
```

**Key Differences**:
1. **Explicit type handling**: Python defaults types; Go requires explicit parsing
2. **Pointer semantics**: Go uses `*int` for optional values
3. **Error handling**: Go uses explicit error checking vs Python exceptions
4. **Service layer**: Go separates handler from business logic

### Pattern 2: Python Model → Go Struct

#### Python (SQLAlchemy)
```python
class Exercise(Base):
    __tablename__ = 'piano_exercises'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    difficulty_level = Column(Integer, default=1)
    notes_sequence = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'difficulty_level': self.difficulty_level,
            'notes_sequence': self.notes_sequence,
            'created_at': self.created_at.isoformat()
        }
```

#### Go (GORM)
```go
type Exercise struct {
    ID              uint      `gorm:"primaryKey" json:"id"`
    Title           string    `gorm:"not null" json:"title"`
    Description     string    `json:"description"`
    DifficultyLevel int       `gorm:"check:difficulty_level >= 1 AND difficulty_level <= 5" json:"difficulty_level"`
    NotesSequence   string    `gorm:"not null" json:"notes_sequence"`
    CreatedAt       time.Time `json:"created_at"`
    UpdatedAt       time.Time `json:"updated_at"`
}

// Go automatically marshals to JSON based on struct tags
```

**Key Differences**:
1. **Struct tags**: Go uses backtick tags for annotations (GORM, JSON)
2. **No methods on models**: Go models are data holders; logic is in services
3. **Explicit types**: No implicit type conversions
4. **Direct JSON**: No `to_dict()` needed; marshaling is built-in

### Pattern 3: Python Service Logic → Go Service

#### Python
```python
def record_attempt(user_id, exercise_id, notes_played, is_correct):
    # Validate
    if not notes_played:
        raise ValueError("notes_played is required")

    exercise = db.query(Exercise).filter_by(id=exercise_id).first()
    if not exercise:
        raise NotFoundError("Exercise not found")

    # Create record
    attempt = Attempt(
        user_id=user_id,
        exercise_id=exercise_id,
        notes_played=notes_played,
        is_correct=is_correct
    )
    db.add(attempt)
    db.commit()

    # Update progress
    try:
        update_user_progress(user_id)
    except Exception as e:
        print(f"Failed to update progress: {e}")

    return attempt.to_dict()
```

#### Go
```go
func RecordAttempt(userID uint, req models.CreateAttemptRequest) (*models.Attempt, error) {
    // Validate exercise exists
    exercise, err := GetExerciseByID(req.ExerciseID)
    if err != nil {
        return nil, err
    }

    // Validate input
    if err := validation.ValidateStringRange(req.NotesPlayed, 1, 1000); err != nil {
        return nil, errors.BadRequest("invalid notes played: " + err.Error())
    }

    // Create attempt
    attempt := &models.Attempt{
        UserID:      userID,
        ExerciseID:  req.ExerciseID,
        NotesPlayed: req.NotesPlayed,
        IsCorrect:   req.IsCorrect,
    }

    if err := repository.CreateAttempt(attempt); err != nil {
        return nil, err
    }

    // Update progress (non-blocking)
    if err := updateProgressAfterAttempt(userID, exercise); err != nil {
        // Log but don't fail
        fmt.Printf("Failed to update progress: %v\n", err)
    }

    return attempt, nil
}
```

**Key Differences**:
1. **Error returns**: Go uses `(value, error)` tuples vs exceptions
2. **Validation**: Go validation is explicit and composable
3. **Explicit error propagation**: Every error is handled or returned
4. **No implicit side effects**: All operations are explicit

### Pattern 4: Python Database Query → Go Repository

#### Python (SQL Alchemy ORM)
```python
def get_user_exercise_stats(user_id, exercise_id):
    stats = db.query(
        func.count(Attempt.id).label('total_attempts'),
        func.sum(case((Attempt.is_correct, 1), else_=0)).label('correct_attempts'),
        func.avg(Attempt.accuracy_percentage).label('average_accuracy')
    ).filter(
        Attempt.user_id == user_id,
        Attempt.exercise_id == exercise_id
    ).first()

    return {
        'total_attempts': stats.total_attempts or 0,
        'correct_attempts': stats.correct_attempts or 0,
        'average_accuracy': stats.average_accuracy or 0
    }
```

#### Go (GORM)
```go
func GetUserExerciseStats(userID, exerciseID uint) (map[string]interface{}, error) {
    var stats map[string]interface{}

    result := database.DB.Model(&models.Attempt{}).
        Where("user_id = ? AND exercise_id = ?", userID, exerciseID).
        Select(
            "COUNT(*) as total_attempts",
            "SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_attempts",
            "AVG(accuracy_percentage) as average_accuracy",
        ).
        Scan(&stats)

    if result.Error != nil {
        return nil, errors.Internal("failed to fetch stats", result.Error.Error())
    }

    return stats, nil
}
```

**Key Differences**:
1. **Method chaining**: Go uses method chaining for query building
2. **Inline SQL**: Go prefers raw SQL in queries for complex operations
3. **No ORM magic**: Explicit `Scan()` required to map results
4. **Error handling**: Every query result must check for errors

## API Endpoints

### Exercise Management

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/piano/exercises` | Optional | List all exercises with pagination |
| GET | `/api/piano/exercises/:id` | Optional | Get single exercise |
| POST | `/api/piano/exercises` | Required | Create new exercise |
| PUT | `/api/piano/exercises/:id` | Required | Update exercise |
| DELETE | `/api/piano/exercises/:id` | Required | Delete exercise |

### Attempts & Statistics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/piano/attempts` | Required | Record new attempt |
| GET | `/api/piano/attempts` | Required | Get user's attempts |
| GET | `/api/piano/exercises/:id/attempts` | Optional | Get all attempts for exercise |
| GET | `/api/piano/exercises/:id/stats` | Required | Get user's stats on exercise |

### Progress & Leaderboard

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/piano/progress` | Required | Get user's progress |
| GET | `/api/piano/leaderboard` | Optional | Get top performers |
| DELETE | `/api/piano/progress` | Required | Reset user's progress |

## Request/Response Examples

### Create Exercise
**Request**:
```json
POST /api/v1/piano/exercises
{
  "title": "C Major Scale",
  "description": "Practice C major scale",
  "difficulty_level": 1,
  "notes_sequence": "C,D,E,F,G,A,B,C"
}
```

**Response** (201 Created):
```json
{
  "id": 1,
  "title": "C Major Scale",
  "description": "Practice C major scale",
  "difficulty_level": 1,
  "notes_sequence": "C,D,E,F,G,A,B,C",
  "created_at": "2026-02-20T10:30:00Z"
}
```

### Record Attempt
**Request**:
```json
POST /api/v1/piano/attempts
{
  "exercise_id": 1,
  "notes_played": "C,D,E,F,G,A,B,C",
  "is_correct": true,
  "accuracy_percentage": 98.5,
  "response_time_ms": 2400
}
```

**Response** (201 Created):
```json
{
  "id": 42,
  "exercise_id": 1,
  "notes_played": "C,D,E,F,G,A,B,C",
  "is_correct": true,
  "accuracy_percentage": 98.5,
  "response_time_ms": 2400,
  "attempted_at": "2026-02-20T10:35:00Z"
}
```

### Get Leaderboard
**Request**:
```
GET /api/v1/piano/leaderboard?limit=5
```

**Response** (200 OK):
```json
{
  "leaderboard": [
    {
      "rank": 1,
      "user_id": 101,
      "current_difficulty_level": 5,
      "total_exercises_completed": 45,
      "average_accuracy_percentage": 96.2
    },
    {
      "rank": 2,
      "user_id": 102,
      "current_difficulty_level": 4,
      "total_exercises_completed": 38,
      "average_accuracy_percentage": 92.1
    }
  ],
  "total": 2
}
```

## Testing Strategy

### Unit Tests (80%+ coverage)

**Location**: `*_test.go` files in each package

**Test Structure**:
```go
func TestFunctionName_Scenario(t *testing.T) {
    // Arrange
    input := prepareTestInput()

    // Act
    result, err := FunctionUnderTest(input)

    // Assert
    assert.NoError(t, err)
    assert.Equal(t, expectedValue, result)
}
```

**Run Tests**:
```bash
go test -v ./internal/piano/...
go test -v -cover ./internal/piano/...
```

### Integration Tests

**Location**: `*_integration_test.go` files

**Test Structure**:
```go
func TestEndpoint_Success(t *testing.T) {
    router := setupTestRouter()

    req, _ := http.NewRequest("GET", "/api/piano/exercises", nil)
    w := httptest.NewRecorder()

    router.ServeHTTP(w, req)

    assert.Equal(t, http.StatusOK, w.Code)
}
```

### Test Coverage

**Target**: 80%+ coverage for services, 60%+ for handlers

**Generate Coverage Report**:
```bash
go test -coverprofile=coverage.out ./internal/piano/...
go tool cover -html=coverage.out
```

## Performance Optimization

### Database Optimization

1. **Indexes**: All frequently queried columns are indexed
2. **Query efficiency**: Use `Preload` for related data
3. **Pagination**: Always limit query results

### API Optimization

1. **Caching**: Cache leaderboard (TTL: 5 minutes)
2. **Connection pooling**: Max 100 concurrent DB connections
3. **Response compression**: Gzip enabled for responses >1KB

### Go Runtime Optimization

1. **Goroutines**: Lightweight concurrency for I/O operations
2. **Memory management**: Efficient GC tuning
3. **CPU profiling**: Use `pprof` for bottleneck identification

## Debugging

### Enable Debug Logging

```bash
DEBUG=true ./unified-app
```

### View Database Queries

```go
import "gorm.io/logger"

db := gorm.Open(postgres.Open(dsn), &gorm.Config{
    Logger: logger.Default.LogMode(logger.Info),
})
```

### Profiling

```go
import _ "net/http/pprof"

// In main():
go func() {
    log.Println(http.ListenAndServe("localhost:6060", nil))
}()
```

Then visit: `http://localhost:6060/debug/pprof/`

## Migration Checklist

- [x] Models defined (GORM structs)
- [x] Repositories implemented (CRUD operations)
- [x] Services implemented (business logic)
- [x] Handlers implemented (HTTP endpoints)
- [x] Middleware integrated (auth, CORS)
- [x] Database migrations created (up/down)
- [x] Unit tests written (80%+ coverage)
- [x] Integration tests written
- [x] Performance benchmarks documented
- [ ] End-to-end tests
- [ ] Load testing completed
- [ ] Documentation complete
- [ ] Code review approved
- [ ] Deployed to staging
- [ ] Production cutover completed

## References

- [GORM Documentation](https://gorm.io/)
- [Gin Framework](https://gin-gonic.com/)
- [Go Error Handling](https://golang.org/doc/effective_go#errors)
- [HTTP Status Codes](https://httpwg.org/specs/rfc7231.html#status.codes)
