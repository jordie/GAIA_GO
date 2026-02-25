# SQLite Development Setup Guide

## Quick Start (5 minutes)

### 1. Clone and Setup

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/educational-apps-go

# Create data directory
mkdir -p data

# Copy environment file
cp .env.example .env
```

### 2. Run Any App

**Math App (Port 2000):**
```bash
go run cmd/math/main.go
```

**Reading App (Port 2001):**
```bash
go run cmd/reading/main.go
```

**All Apps Together (Port 8080):**
```bash
go run cmd/unified/main.go
```

That's it! SQLite database will auto-create at `./data/educational_apps.db`

## Default Configuration

The apps use SQLite by default. No PostgreSQL needed!

**Automatic Setup:**
- ✅ Database file auto-created at `./data/educational_apps.db`
- ✅ Schemas auto-migrated on startup
- ✅ Ready to use immediately
- ✅ Memory efficient (<10MB)

## Development Workflow

### Starting Fresh

```bash
# Delete old database
rm ./data/educational_apps.db

# Run app - new database auto-created
go run cmd/math/main.go
```

### Backup Database

```bash
# Before major changes
cp ./data/educational_apps.db ./data/educational_apps.db.backup

# After testing, restore if needed
cp ./data/educational_apps.db.backup ./data/educational_apps.db
```

### View Database Contents

```bash
# Install sqlite3 if not present
# macOS: brew install sqlite3
# Linux: apt-get install sqlite3

# Open database
sqlite3 ./data/educational_apps.db

# View tables
.tables

# View schema
.schema

# Query data
SELECT * FROM users LIMIT 5;

# Exit
.quit
```

## File Structure

```
educational-apps-go/
├── data/                          # SQLite database storage
│   └── educational_apps.db       # Auto-created on first run
├── cmd/
│   ├── math/main.go             # Math app (port 2000)
│   ├── reading/main.go          # Reading app (port 2001)
│   └── unified/main.go          # All apps (port 8080)
├── .env                          # Environment config
└── .env.example                  # Example config
```

## Environment Setup

### No Configuration Needed!

The apps work out-of-the-box with SQLite. Just run them.

### Optional: Custom Settings

Create `.env` file in project root:

```bash
# Database (SQLite is default)
DB_TYPE=sqlite
SQLITE_PATH=./data/educational_apps.db

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
ENV=development

# App-specific ports
MATH_PORT=2000
READING_PORT=2001

# Session secret
SESSION_SECRET=dev-secret-key
```

## Testing the Apps

### Math App

```bash
# Start app
go run cmd/math/main.go

# Test in another terminal
# Generate problem
curl -X POST http://localhost:2000/api/v1/math/problems/generate \
  -H "Content-Type: application/json" \
  -d '{"mode": "addition", "difficulty": "easy"}'

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

### Reading App

```bash
# Start app
go run cmd/reading/main.go

# Test in another terminal
# Get words
curl http://localhost:2001/api/v1/reading/words

# Save reading result
curl -X POST http://localhost:2001/api/v1/reading/results \
  -H "Content-Type: application/json" \
  -H "user_id: 1" \
  -d '{
    "expected_words": ["the", "quick"],
    "recognized_text": "the quick",
    "accuracy": 100.0,
    "words_correct": 2,
    "words_total": 2,
    "reading_speed": 250.0,
    "session_duration": 60.0
  }'
```

## Running Multiple Apps

### In Separate Terminals

**Terminal 1 - Math App:**
```bash
go run cmd/math/main.go
```

**Terminal 2 - Reading App:**
```bash
READING_PORT=2001 go run cmd/reading/main.go
```

**Terminal 3 - Unified App:**
```bash
go run cmd/unified/main.go
```

All three share the same SQLite database file.

### With Docker Compose

```bash
# Start all apps
docker-compose up

# Logs
docker-compose logs -f math-app
docker-compose logs -f reading-app

# Stop
docker-compose down
```

## Troubleshooting

### "database is locked"

**Problem:** Multiple apps trying to write simultaneously

**Solution:** SQLite allows multiple readers, but only one writer at a time.
- Sequential writes are fine
- If running multiple apps, they'll wait for each other
- This is fine for development

```bash
# If truly stuck, find process
lsof | grep educational_apps.db

# Kill if needed
kill -9 <PID>
```

### "permission denied"

**Problem:** File permission issue

**Solution:**
```bash
# Fix permissions
chmod 644 ./data/educational_apps.db
chmod 755 ./data/
```

### App won't start

**Check:**
```bash
# Create data directory if missing
mkdir -p data

# Check disk space
df -h

# Check if port is in use
lsof -i :2000  # For math app
lsof -i :2001  # For reading app
lsof -i :8080  # For unified app
```

## Performance Tips

### SQLite Optimization for Development

SQLite is already optimized for development, but here are tips:

```bash
# Enable WAL mode (write-ahead logging) for better concurrency
sqlite3 ./data/educational_apps.db "PRAGMA journal_mode=WAL;"

# View WAL status
sqlite3 ./data/educational_apps.db "PRAGMA journal_mode;"

# Optimize for faster queries
sqlite3 ./data/educational_apps.db "PRAGMA optimize;"
```

### Connection Pool

SQLite uses conservative connection pooling by default:
```
Max Idle Connections: 5
Max Open Connections: 10
```

This prevents "database is locked" errors during development.

## Backup Strategy

### Daily Backup

```bash
# Create backups directory
mkdir -p backups

# Create backup
cp ./data/educational_apps.db ./backups/educational_apps_$(date +%Y%m%d_%H%M%S).db

# Keep last 7 days
find ./backups -name "*.db" -mtime +7 -delete
```

### Automated Backup Script

Create `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp ./data/educational_apps.db $BACKUP_DIR/educational_apps_$TIMESTAMP.db
echo "Backed up to $BACKUP_DIR/educational_apps_$TIMESTAMP.db"
```

Run before major changes:
```bash
chmod +x backup.sh
./backup.sh
```

## Migration to PostgreSQL

When you're ready for production:

### Step 1: Export from SQLite
```bash
# Built-in tool (coming in Week 11)
go run scripts/migrate_sqlite_to_postgres.go
```

### Step 2: Update Environment
```bash
# Change .env to PostgreSQL
export DB_TYPE=postgres
export DB_HOST=your-postgres-host
export DB_PORT=5432
export DB_NAME=educational_apps
export DB_USER=postgres
export DB_PASSWORD=secure-password
export DB_SSLMODE=require
```

### Step 3: Run with PostgreSQL
```bash
go run cmd/unified/main.go
```

### Rollback (if needed)
```bash
# Switch back to SQLite
export DB_TYPE=sqlite
go run cmd/unified/main.go
```

## Resource Usage

```
SQLite Development Setup:
├─ Memory: 5-10MB
├─ Disk: 10-50MB (grows with data)
├─ CPU: Minimal
└─ Network: Local only (no remote)

Total Impact: Negligible on your Mac mini (24GB RAM)
```

## What's Next?

- ✅ Apps are running locally with SQLite
- ✅ Use them to develop and test
- ✅ Run multiple apps on separate ports
- ✅ Data persists in `./data/educational_apps.db`
- ⏳ Week 11: Easy migration to PostgreSQL when ready

## Summary

| Task | Command |
|------|---------|
| Start Math | `go run cmd/math/main.go` |
| Start Reading | `go run cmd/reading/main.go` |
| Start All | `go run cmd/unified/main.go` |
| Backup DB | `cp ./data/educational_apps.db ./backups/` |
| Reset DB | `rm ./data/educational_apps.db` |
| View DB | `sqlite3 ./data/educational_apps.db` |

**Zero PostgreSQL needed for development!** 🎉
