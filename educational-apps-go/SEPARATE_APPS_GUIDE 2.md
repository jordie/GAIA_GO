# Running Educational Apps on Separate Ports

This guide explains how to run Math and Reading apps independently on separate ports with isolated environments.

## Quick Start

### Option 1: Run Both Apps in Separate Terminals

**Terminal 1 - Math App (Port 2000):**
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/educational-apps-go
MATH_PORT=2000 go run cmd/math/main.go
```

**Terminal 2 - Reading App (Port 2001):**
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/educational-apps-go
READING_PORT=2001 go run cmd/reading/main.go
```

**Terminal 3 - Unified App (All Apps on Port 8080):**
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/educational-apps-go
go run cmd/unified/main.go
```

### Option 2: Run with Docker Compose

Create `docker-compose.yml` in the root of the project:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: educational_apps
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  math-app:
    build:
      context: .
      dockerfile: Dockerfile.math
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: educational_apps
      DB_USER: postgres
      DB_PASSWORD: postgres
      MATH_PORT: 2000
    ports:
      - "2000:2000"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:2000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  reading-app:
    build:
      context: .
      dockerfile: Dockerfile.reading
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: educational_apps
      DB_USER: postgres
      DB_PASSWORD: postgres
      READING_PORT: 2001
    ports:
      - "2001:2001"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:2001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  unified-app:
    build:
      context: .
      dockerfile: Dockerfile.unified
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: educational_apps
      DB_USER: postgres
      DB_PASSWORD: postgres
      PORT: 8080
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
```

Start all services:
```bash
docker-compose up
```

Stop all services:
```bash
docker-compose down
```

### Option 3: Custom Port Configuration

Each app can be configured with different ports and environments:

```bash
# Math app on custom port with custom database
DB_HOST=localhost \
DB_PORT=5432 \
DB_NAME=math_db \
MATH_PORT=3000 \
go run cmd/math/main.go

# Reading app on custom port with custom database
DB_HOST=localhost \
DB_PORT=5432 \
DB_NAME=reading_db \
READING_PORT=3001 \
go run cmd/reading/main.go
```

## Environment Variables

### Common Variables (All Apps)
```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=educational_apps
DB_USER=postgres
DB_PASSWORD=postgres

# Server Configuration
SERVER_ENV=development  # development, staging, production
```

### App-Specific Variables

**Math App:**
```bash
MATH_PORT=2000              # Default: 2000
MATH_MAX_DIFFICULTY=expert  # Default: expert
MATH_ENABLE_SMART_MODE=true # Default: true
```

**Reading App:**
```bash
READING_PORT=2001              # Default: 2001
READING_MAX_WORDS=100          # Default: 100
READING_PASS_THRESHOLD=70      # Default: 70
```

**Unified App:**
```bash
PORT=8080  # Default: 8080
```

## Health Check Endpoints

Each app provides a health check endpoint:

```bash
# Math app health
curl http://localhost:2000/health
# Response: {"status":"ok","app":"math"}

# Reading app health
curl http://localhost:2001/health
# Response: {"status":"ok","app":"reading"}

# Unified app health
curl http://localhost:8080/health
# Response: {"status":"ok"}
```

## API Endpoints by Port

### Math App (Port 2000)
```
POST   /api/v1/math/problems/generate
POST   /api/v1/math/problems/check
POST   /api/v1/math/sessions/save
GET    /api/v1/math/stats
GET    /api/v1/math/weaknesses
GET    /api/v1/math/practice-plan
GET    /api/v1/math/learning-profile
```

### Reading App (Port 2001)
```
GET    /api/v1/reading/words
POST   /api/v1/reading/results
GET    /api/v1/reading/stats
GET    /api/v1/reading/weaknesses
GET    /api/v1/reading/practice-plan
GET    /api/v1/reading/learning-profile
GET    /api/v1/reading/quizzes
POST   /api/v1/reading/quizzes
GET    /api/v1/reading/quizzes/:id
POST   /api/v1/reading/quizzes/:id/submit
GET    /api/v1/reading/quizzes/attempts/:attempt_id
```

### Unified App (Port 8080)
```
All endpoints from both apps above, plus future apps
```

## Building Docker Images

Create separate Dockerfiles for each app:

**Dockerfile.math:**
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /build
COPY . .
RUN go build -o math-app cmd/math/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /build/math-app .
EXPOSE 2000
CMD ["./math-app"]
```

**Dockerfile.reading:**
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /build
COPY . .
RUN go build -o reading-app cmd/reading/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /build/reading-app .
EXPOSE 2001
CMD ["./reading-app"]
```

**Dockerfile.unified:**
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /build
COPY . .
RUN go build -o unified-app cmd/unified/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /build/unified-app .
EXPOSE 8080
CMD ["./unified-app"]
```

Build images:
```bash
# Build Math app
docker build -f Dockerfile.math -t educational-apps:math .

# Build Reading app
docker build -f Dockerfile.reading -t educational-apps:reading .

# Build Unified app
docker build -f Dockerfile.unified -t educational-apps:unified .
```

## Testing the Apps

### Test Math App
```bash
# Health check
curl http://localhost:2000/health

# Generate problem
curl -X POST http://localhost:2000/api/v1/math/problems/generate \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "addition",
    "difficulty": "easy"
  }'

# Check answer
curl -X POST http://localhost:2000/api/v1/math/problems/check \
  -H "Content-Type: application/json" \
  -H "user_id: 1" \
  -d '{
    "question": "5 + 3",
    "user_answer": "8",
    "correct_answer": "8",
    "time_taken": 2.5,
    "fact_family": "plus_one",
    "mode": "addition"
  }'
```

### Test Reading App
```bash
# Health check
curl http://localhost:2001/health

# Get words
curl http://localhost:2001/api/v1/reading/words?limit=10

# Save reading result
curl -X POST http://localhost:2001/api/v1/reading/results \
  -H "Content-Type: application/json" \
  -H "user_id: 1" \
  -d '{
    "expected_words": ["the", "quick", "brown"],
    "recognized_text": "the quick brown",
    "accuracy": 100.0,
    "words_correct": 3,
    "words_total": 3,
    "reading_speed": 250.0,
    "session_duration": 60.0
  }'

# List quizzes
curl http://localhost:2001/api/v1/reading/quizzes
```

## Database Isolation (Optional)

For complete isolation, use separate databases:

```bash
# Create separate databases
createdb math_practice
createdb reading_practice

# Run Math app with isolated database
DB_NAME=math_practice MATH_PORT=2000 go run cmd/math/main.go

# Run Reading app with isolated database
DB_NAME=reading_practice READING_PORT=2001 go run cmd/reading/main.go
```

## Production Deployment

### Kubernetes Configuration (Optional)

Create separate deployments for each app:

**math-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: math-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: math
  template:
    metadata:
      labels:
        app: math
    spec:
      containers:
      - name: math
        image: educational-apps:math
        ports:
        - containerPort: 2000
        env:
        - name: MATH_PORT
          value: "2000"
        - name: DB_HOST
          value: postgres-service
        livenessProbe:
          httpGet:
            path: /health
            port: 2000
          initialDelaySeconds: 10
          periodSeconds: 10
```

**reading-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reading-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: reading
  template:
    metadata:
      labels:
        app: reading
    spec:
      containers:
      - name: reading
        image: educational-apps:reading
        ports:
        - containerPort: 2001
        env:
        - name: READING_PORT
          value: "2001"
        - name: DB_HOST
          value: postgres-service
        livenessProbe:
          httpGet:
            path: /health
            port: 2001
          initialDelaySeconds: 10
          periodSeconds: 10
```

Deploy to Kubernetes:
```bash
kubectl apply -f math-deployment.yaml
kubectl apply -f reading-deployment.yaml
```

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 2000
lsof -i :2000

# Kill process
kill -9 <PID>
```

### Database Connection Error
```bash
# Check PostgreSQL is running
psql -h localhost -U postgres -d educational_apps -c "SELECT 1"

# Verify environment variables
echo $DB_HOST
echo $DB_PORT
echo $DB_NAME
```

### Health Check Failing
```bash
# Check if app is listening
curl -v http://localhost:2000/health
curl -v http://localhost:2001/health

# Check app logs
docker logs math-app
docker logs reading-app
```

## Summary

| Component | Port | Environment | Command |
|-----------|------|-------------|---------|
| Math App | 2000 | MATH_PORT=2000 | `go run cmd/math/main.go` |
| Reading App | 2001 | READING_PORT=2001 | `go run cmd/reading/main.go` |
| Unified App | 8080 | PORT=8080 | `go run cmd/unified/main.go` |

All three configurations share the same PostgreSQL database but run as independent services with isolated HTTP ports and environment configurations.
