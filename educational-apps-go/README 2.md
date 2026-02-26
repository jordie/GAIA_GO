# Educational Apps - Go Migration

A high-performance migration of Python/Flask educational applications to Go/Gin, targeting 20-30x performance improvement.

## Project Structure

```
educational-apps-go/
├── cmd/                    # Application entry points
│   ├── reading/           # Reading app CLI
│   ├── math/              # Math app CLI
│   ├── piano/             # Piano app CLI
│   ├── typing/            # Typing app CLI
│   ├── comprehension/     # Comprehension app CLI
│   └── unified/           # Unified server entry point
├── internal/              # Private application code
│   ├── {app}/handlers/    # HTTP handlers per app
│   ├── {app}/models/      # Data models per app
│   ├── {app}/services/    # Business logic per app
│   ├── {app}/repository/  # Database access per app
│   └── common/            # Shared utilities
├── pkg/                   # Public packages
│   ├── config/           # Configuration management
│   └── logger/           # Logging utilities
├── web/                   # Web assets
│   ├── templates/        # Go templates (html/template)
│   └── static/           # CSS, JS, images
├── migrations/           # Database migrations
├── deploy/               # Docker and deployment
└── Makefile             # Development commands
```

## Technology Stack

- **Language**: Go 1.21+
- **Framework**: Gin 1.9+ (HTTP web framework)
- **Database**: PostgreSQL 15+ with GORM ORM
- **Templates**: html/template (Go standard library)
- **Session**: gorilla/sessions
- **Validation**: validator/v10
- **Logging**: Uber zap
- **Deployment**: Docker & Docker Compose

## Getting Started

### Prerequisites

- Go 1.21 or higher
- PostgreSQL 15+
- Docker & Docker Compose (optional)

### Local Setup

1. **Clone the repository**
   ```bash
   cd educational-apps-go
   ```

2. **Copy environment variables**
   ```bash
   cp .env.example .env
   ```

3. **Download dependencies**
   ```bash
   make deps
   ```

4. **Start PostgreSQL (via Docker)**
   ```bash
   make docker-up
   ```

5. **Run database migrations**
   ```bash
   make migrate
   ```

6. **Run the app**
   ```bash
   make run
   ```

The app will start on `http://localhost:8080`

### Docker Setup (Recommended)

```bash
# Start all services
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

## Development

### Available Commands

```bash
make help              # Show all available commands
make build             # Build the binary
make run               # Run the app
make test              # Run all tests
make test-coverage     # Run tests with coverage report
make lint              # Run linter
make clean             # Remove build artifacts
make dev               # Run with hot reload (requires air)
make fmt               # Format code
```

### Project Layout

Each educational app follows this structure:

```
internal/{app}/
├── handlers/           # HTTP request handlers
│   └── {endpoint}_handler.go
├── models/             # Data structures
│   └── {model}.go
├── services/           # Business logic
│   └── {service}_service.go
└── repository/         # Database access
    └── {entity}_repository.go
```

### Common Patterns

**1. Handler (HTTP endpoint)**
```go
func CreateUser(c *gin.Context) {
    var req CreateUserRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        middleware.JSONErrorResponse(c, errors.Validation("invalid request", err.Error()))
        return
    }

    user, err := services.CreateUser(req)
    if err != nil {
        middleware.JSONErrorResponse(c, err)
        return
    }

    c.JSON(201, user)
}
```

**2. Service (Business Logic)**
```go
func CreateUser(req CreateUserRequest) (*User, error) {
    if err := validation.ValidateStringRange(req.Username, 3, 50); err != nil {
        return nil, errors.BadRequest("invalid username")
    }

    user := &User{
        Username: req.Username,
        Email:    req.Email,
    }

    if err := db.Create(user).Error; err != nil {
        return nil, errors.Internal("failed to create user", err.Error())
    }

    return user, nil
}
```

**3. Repository (Database Access)**
```go
func GetUserByID(id uint) (*User, error) {
    var user User
    result := db.DB.First(&user, id)
    if result.Error != nil {
        if errors.Is(result.Error, gorm.ErrRecordNotFound) {
            return nil, errors.NotFound("user")
        }
        return nil, errors.Internal("database error", result.Error.Error())
    }
    return &user, nil
}
```

## API Endpoints

### Reading App
- `GET /api/reading/lessons` - Get all lessons
- `GET /api/reading/lessons/:id` - Get lesson by ID
- `POST /api/reading/word-mastery` - Record word mastery
- `GET /api/reading/word-mastery` - Get word mastery progress

### Math App
- `GET /api/math/problems/:difficulty` - Get problems by difficulty
- `POST /api/math/attempts` - Record attempt
- `GET /api/math/progress` - Get user progress

### Piano App
- `GET /api/piano/exercises` - Get all exercises
- `POST /api/piano/attempts` - Record attempt
- `GET /api/piano/progress` - Get progress

### Typing App
- `GET /api/typing/exercises` - Get all exercises
- `POST /api/typing/attempts` - Record attempt
- `GET /api/typing/progress` - Get progress

### Comprehension App
- `GET /api/comprehension/passages` - Get passages
- `GET /api/comprehension/passages/:id/questions` - Get questions
- `POST /api/comprehension/answers` - Submit answer
- `GET /api/comprehension/progress` - Get progress

## Database Schema

### Core Tables
- `users` - User accounts
- `sessions` - User sessions

### App-Specific Tables
- Reading: `reading_lessons`, `reading_word_mastery`, `reading_comprehension_answers`
- Math: `math_problems`, `math_attempts`, `math_progress`
- Piano: `piano_notes`, `piano_exercises`, `piano_attempts`
- Typing: `typing_exercises`, `typing_attempts`, `typing_progress`
- Comprehension: `comprehension_passages`, `comprehension_questions`, `comprehension_answers`

See `migrations/001_initial_schema.up.sql` for full schema.

## Performance Benchmarks

**Expected Improvements** (Python → Go):
| Metric | Python | Go | Improvement |
|--------|--------|-----|------------|
| Startup Time | 2,000ms | <100ms | 20x |
| Memory (idle) | 50MB | <15MB | 3-5x |
| Request Latency (p50) | 100ms | <10ms | 10x |
| Throughput | 1,000 req/s | 25,000 req/s | 25x |

## Testing

Run the test suite:
```bash
make test              # Run all tests
make test-coverage     # Generate coverage report
```

Tests should have:
- 80%+ unit test coverage
- 60%+ integration test coverage
- All critical paths with E2E tests

## Deployment

### Docker Deployment
```bash
docker-compose -f deploy/docker-compose.yml up -d
```

### Environment Variables
See `.env.example` for all configuration options.

### Production Considerations
- Set `SESSION_SECRET` to a strong random value
- Configure PostgreSQL backups
- Set up monitoring and logging
- Use HTTPS in production
- Configure CORS appropriately

## Migration from Python

The original Python applications are located at:
```
/Users/jgirmay/Desktop/gitrepo/pyWork/archive/basic_edu_apps_20251220/
```

### Phased Migration Plan
1. **Week 1-2**: Infrastructure setup ✓
2. **Week 3-4**: Piano app pilot (simplest)
3. **Week 5-6**: Typing app
4. **Week 7**: Math app
5. **Week 8**: Reading app
6. **Week 9**: Dashboard & unified router
7. **Week 10**: Unified app & advanced features
8. **Week 11**: Data migration (SQLite → PostgreSQL)
9. **Week 12**: Production cutover

## Contributing

- Follow Go code style guidelines (`gofmt`, `golangci-lint`)
- Add tests for new features
- Update documentation
- Use feature branches for new work

## Support & Troubleshooting

### Common Issues

**Database connection failed**
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Verify connection settings
cat .env | grep DB_
```

**Port already in use**
```bash
# Change port in .env
SERVER_PORT=8081

# Or kill existing process
lsof -i :8080 | grep -v PID | awk '{print $2}' | xargs kill -9
```

**Tests failing**
```bash
# Make sure PostgreSQL test database is running
make docker-up

# Run with verbose output
make test
```

## License

Proprietary - Architect Project

## References

- [Go Documentation](https://golang.org/doc/)
- [Gin Documentation](https://github.com/gin-gonic/gin)
- [GORM Documentation](https://gorm.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
