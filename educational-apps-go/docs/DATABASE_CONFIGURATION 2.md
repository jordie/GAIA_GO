# Database Configuration Guide

## Overview

The educational apps support both **SQLite** (development) and **PostgreSQL** (production) databases through a unified configuration system.

**Default for Development: SQLite** (zero extra resources)
**Default for Production: PostgreSQL** (scalable, multi-user)

## Quick Start

### Development (SQLite)

No setup required! SQLite is the default.

```bash
# Run any app - SQLite automatically creates ./data/educational_apps.db
go run cmd/math/main.go
go run cmd/reading/main.go
go run cmd/unified/main.go
```

**Resource Usage:**
- Memory: ~5-10MB
- Disk: ~5-50MB
- No additional processes needed

### Production (PostgreSQL)

Set `DB_TYPE=postgres` and provide connection details:

```bash
export DB_TYPE=postgres
export DB_HOST=your-postgres-host
export DB_PORT=5432
export DB_NAME=educational_apps
export DB_USER=postgres
export DB_PASSWORD=your-password
export DB_SSLMODE=require

go run cmd/unified/main.go
```

## Environment Variables

### Database Type Selection

```bash
# Development - SQLite (default)
DB_TYPE=sqlite
SQLITE_PATH=./data/educational_apps.db

# Production - PostgreSQL
DB_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=educational_apps
DB_USER=postgres
DB_PASSWORD=postgres
DB_SSLMODE=disable  # Use 'require' in production
```

### Complete .env Example

Create `.env` file in project root:

```bash
# Database Selection
DB_TYPE=sqlite
SQLITE_PATH=./data/educational_apps.db

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
ENV=development

# Session
SESSION_SECRET=your-secret-key

# App Ports (for separate entry points)
MATH_PORT=2000
READING_PORT=2001
```

## Database Files

### SQLite Database File

Location: `./data/educational_apps.db`

**Backup:**
```bash
# Simple file copy
cp ./data/educational_apps.db ./data/educational_apps.db.backup

# Or use SQLite tools
sqlite3 ./data/educational_apps.db ".backup ./data/educational_apps.db.backup"
```

**Restore:**
```bash
cp ./data/educational_apps.db.backup ./data/educational_apps.db
```

**Reset:**
```bash
rm ./data/educational_apps.db
# App will recreate on next run
```

### PostgreSQL Connection

**Test Connection:**
```bash
psql -h localhost -U postgres -d educational_apps -c "SELECT 1"
```

**Create Database:**
```bash
createdb -U postgres educational_apps
```

## Migration: SQLite → PostgreSQL

### Automatic Migration Path

When you're ready to scale to production:

1. **Export from SQLite:**
   ```bash
   # Use built-in migration tool (Week 11)
   go run scripts/migrate_sqlite_to_postgres.go
   ```

2. **Verify Data:**
   ```bash
   # Compare record counts
   sqlite3 ./data/educational_apps.db "SELECT COUNT(*) FROM users;"
   psql -d educational_apps -c "SELECT COUNT(*) FROM users;"
   ```

3. **Switch Configuration:**
   ```bash
   export DB_TYPE=postgres
   export DB_HOST=your-prod-host
   # ... other settings
   ```

## Database Drivers

### SQLite Driver

**Package:** `gorm.io/driver/sqlite`

**Features:**
- File-based (no server)
- Zero configuration
- ACID compliant
- WAL mode for concurrent access
- Perfect for development and small deployments

**Limitations:**
- Single process writer (but multiple readers)
- No remote access (local file only)
- Not suitable for high-concurrency scenarios

### PostgreSQL Driver

**Package:** `gorm.io/driver/postgres`

**Features:**
- Client-server architecture
- Full ACID transactions
- Multi-user support
- Advanced query optimization
- Replication and backup features
- Perfect for production

**Overhead:**
- Requires separate PostgreSQL server
- Consumes more memory (~200-500MB)
- Network latency for remote servers

## Performance Comparison

| Metric | SQLite | PostgreSQL |
|--------|--------|-----------|
| Memory | 5-10MB | 200-500MB |
| Startup | <100ms | <200ms (with remote, +latency) |
| Local Latency | 1-2ms | 2-5ms |
| Max Connections | ~1 writer | Unlimited |
| Best For | Development | Production |
| Setup | Zero config | Requires server |
| Backup | File copy | Database dump |

## Usage Examples

### Math App with SQLite (Default)

```bash
# No configuration needed
go run cmd/math/main.go

# Or explicit:
DB_TYPE=sqlite SQLITE_PATH=./data/math.db go run cmd/math/main.go
```

### Reading App with PostgreSQL

```bash
DB_TYPE=postgres \
DB_HOST=localhost \
DB_PORT=5432 \
DB_NAME=reading_app \
DB_USER=postgres \
DB_PASSWORD=postgres \
go run cmd/reading/main.go
```

### Unified App with Different Database Per Env

```bash
# Development
go run cmd/unified/main.go  # Uses SQLite

# Production
DB_TYPE=postgres \
DB_HOST=prod.example.com \
DB_PORT=5432 \
DB_NAME=educational_apps \
DB_USER=app_user \
DB_PASSWORD=secure_password \
go run cmd/unified/main.go
```

## Troubleshooting

### SQLite "database is locked"

**Cause:** Another process is writing to the database

**Solution:**
```bash
# Kill competing process
lsof | grep educational_apps.db

# Or restart the app
```

### PostgreSQL Connection Refused

**Cause:** PostgreSQL server not running

**Solution:**
```bash
# Check if PostgreSQL is running
pg_isready -h localhost

# Start PostgreSQL
brew services start postgresql  # macOS
sudo systemctl start postgresql  # Linux
```

### "permission denied" on SQLite file

**Cause:** File permissions issue

**Solution:**
```bash
chmod 644 ./data/educational_apps.db
chmod 755 ./data/
```

### Out of Memory with PostgreSQL

**Check Server Resources:**
```bash
# Show memory usage
top -b | head -20

# Show database size
psql -d educational_apps -c "SELECT pg_size_pretty(pg_database_size('educational_apps'));"
```

**Reduce Memory:**
```bash
# Reduce PostgreSQL shared_buffers
# In postgresql.conf:
shared_buffers = 64MB        # Default ~128MB
```

## Docker Support

### SQLite with Docker

```dockerfile
FROM golang:1.21-alpine
WORKDIR /app
COPY . .
RUN go build -o app cmd/math/main.go
VOLUME ["/app/data"]
CMD ["./app"]
```

### PostgreSQL with Docker Compose

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: educational_apps
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  app:
    build: .
    environment:
      DB_TYPE: postgres
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: educational_apps
      DB_USER: postgres
      DB_PASSWORD: postgres
    depends_on:
      - postgres

volumes:
  postgres_data:
```

## Best Practices

### Development
- ✅ Use SQLite by default
- ✅ Store in `./data/` directory
- ✅ Add `data/` to `.gitignore`
- ✅ Backup before major changes
- ✅ Use WAL mode for better concurrency

### Production
- ✅ Use PostgreSQL
- ✅ Enable SSL/TLS (`DB_SSLMODE=require`)
- ✅ Use strong passwords
- ✅ Regular backups
- ✅ Monitor disk space
- ✅ Enable replication
- ✅ Use connection pooling (PgBouncer)

### Migration
- ✅ Test on staging first
- ✅ Backup SQLite database
- ✅ Verify record counts post-migration
- ✅ Keep old database for rollback
- ✅ Document migration steps

## Summary

| Use Case | Database | Configuration |
|----------|----------|----------------|
| Local Development | SQLite | DB_TYPE=sqlite (default) |
| Testing | SQLite | DB_TYPE=sqlite |
| Staging | PostgreSQL | DB_TYPE=postgres + credentials |
| Production | PostgreSQL | DB_TYPE=postgres + secure credentials |

Both are fully supported and can be switched with a single environment variable!
