# GAIA App Framework Documentation

The GAIA App Framework provides a standardized way to build and integrate educational apps into the GAIA platform. This document covers everything you need to create a new app or understand the existing framework.

## Overview

The app framework is a plugin-based system that allows developers to:
- Create modular, self-contained applications
- Automatically register routes and endpoints
- Track user statistics, scores, and achievements
- Access shared database infrastructure
- Implement leaderboards and progress tracking

## Core Concepts

### App Interface

Every GAIA app must implement the `App` interface defined in `internal/app/interface.go`:

```go
type App interface {
    // GetName returns the app's unique identifier (e.g., "typing", "math")
    GetName() string

    // GetDisplayName returns the human-readable name (e.g., "Typing Master")
    GetDisplayName() string

    // GetDescription returns a brief description of the app
    GetDescription() string

    // GetVersion returns the app version
    GetVersion() string

    // RegisterRoutes registers all HTTP endpoints for this app
    // Router is pre-scoped to /api/<app_name>
    RegisterRoutes(router *gin.RouterGroup)

    // InitDB initializes app-specific database tables
    InitDB() error

    // GetUserStats returns app-specific statistics for a user
    GetUserStats(userID int64) (map[string]interface{}, error)

    // GetLeaderboard returns top players for the app
    GetLeaderboard(limit int) ([]map[string]interface{}, error)
}
```

### App Registration

Apps are registered via the `Registry` (internal/app/registry.go):

```go
type AppConfig struct {
    Name        string
    DisplayName string
    Description string
    Version     string
    Instance    App         // Your app implementation
    DB          *sql.DB     // Database connection
    SessionMgr  *session.Manager  // Session manager
}

registry := app.NewRegistry()
err := registry.Register(AppConfig{
    Name:        "myapp",
    DisplayName: "My App",
    Description: "Description of my app",
    Version:     "1.0.0",
    Instance:    myAppInstance,
    DB:          db,
})
```

Routes are automatically created at `/api/<app_name>/*` after registration.

## Creating a New App

### Step 1: Create App Package

Create a new directory in `pkg/apps/<app_name>/`:

```bash
mkdir -p pkg/apps/myapp
```

### Step 2: Implement the App Interface

Create `pkg/apps/myapp/app.go`:

```go
package myapp

import (
    "database/sql"
    "github.com/gin-gonic/gin"
    "github.com/jgirmay/GAIA_GO/internal/app"
    "github.com/jgirmay/GAIA_GO/internal/api"
    "github.com/jgirmay/GAIA_GO/internal/middleware"
)

type MyApp struct {
    db             *sql.DB
    statsManager   *app.StatsManager
    achievementMgr *app.AchievementManager
}

func NewMyApp(db *sql.DB) *MyApp {
    return &MyApp{
        db:             db,
        statsManager:   app.NewStatsManager(db),
        achievementMgr: app.NewAchievementManager(db),
    }
}

func (a *MyApp) GetName() string {
    return "myapp"
}

func (a *MyApp) GetDisplayName() string {
    return "My App"
}

func (a *MyApp) GetDescription() string {
    return "A brief description of my app"
}

func (a *MyApp) GetVersion() string {
    return "1.0.0"
}

func (a *MyApp) RegisterRoutes(router *gin.RouterGroup) {
    router.GET("/status", a.handleStatus)
    router.GET("/stats", middleware.RequireAuth(), a.handleGetStats)
    router.GET("/leaderboard", a.handleGetLeaderboard)
    router.POST("/score", middleware.RequireAuth(), a.handleSaveScore)
}

func (a *MyApp) InitDB() error {
    _, err := a.db.Exec(`
        CREATE TABLE IF NOT EXISTS myapp_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    `)
    return err
}

func (a *MyApp) GetUserStats(userID int64) (map[string]interface{}, error) {
    var totalGames int
    var highScore int

    err := a.db.QueryRow(`
        SELECT COUNT(*), COALESCE(MAX(score), 0)
        FROM myapp_games
        WHERE user_id = ?
    `, userID).Scan(&totalGames, &highScore)

    if err != nil && err != sql.ErrNoRows {
        return nil, err
    }

    return map[string]interface{}{
        "total_games": totalGames,
        "high_score":  highScore,
    }, nil
}

func (a *MyApp) GetLeaderboard(limit int) ([]map[string]interface{}, error) {
    return a.statsManager.GetLeaderboard("myapp", limit)
}
```

### Step 3: Implement Handlers

Add handler methods to your app:

```go
func (a *MyApp) handleStatus(c *gin.Context) {
    api.RespondWith(c, 200, gin.H{
        "status": "ok",
        "app":    "myapp",
    })
}

func (a *MyApp) handleGetStats(c *gin.Context) {
    userID, _ := middleware.GetUserID(c)
    stats, err := a.GetUserStats(userID)
    if err != nil {
        api.RespondWithError(c, api.ErrInternalServer)
        return
    }
    api.RespondWith(c, 200, stats)
}

func (a *MyApp) handleGetLeaderboard(c *gin.Context) {
    board, err := a.GetLeaderboard(10)
    if err != nil {
        api.RespondWithError(c, api.ErrInternalServer)
        return
    }
    if board == nil {
        board = []map[string]interface{}{}
    }
    api.RespondWith(c, 200, gin.H{"leaderboard": board})
}

func (a *MyApp) handleSaveScore(c *gin.Context) {
    userID, _ := middleware.GetUserID(c)

    var req struct {
        Score int `json:"score"`
    }
    if err := c.ShouldBindJSON(&req); err != nil {
        api.RespondWithError(c, api.ErrBadRequest)
        return
    }

    err := a.statsManager.RecordScore(userID, "myapp", req.Score)
    if err != nil {
        api.RespondWithError(c, api.ErrInternalServer)
        return
    }

    api.RespondWith(c, 200, gin.H{"success": true})
}
```

### Step 4: Register App on Startup

In your main startup code (`cmd/server/main.go` or equivalent), register your app:

```go
import "github.com/jgirmay/GAIA_GO/pkg/apps/myapp"

// ... in main() ...
myAppInstance := myapp.NewMyApp(db)
err := appRegistry.Register(app.AppConfig{
    Name:        "myapp",
    DisplayName: "My App",
    Description: "A brief description",
    Version:     "1.0.0",
    Instance:    myAppInstance,
    DB:          db,
})
if err != nil {
    log.Fatalf("Failed to register myapp: %v", err)
}

// Then register all routes
apiRouter := engine.Group("/api")
appRegistry.RegisterRoutes(apiRouter)
```

## Shared Infrastructure

### StatsManager

The `StatsManager` provides common statistics tracking:

```go
statsManager := app.NewStatsManager(db)

// Increment a stat
statsManager.IncrementStat(userID, "myapp", "games_played", 1)

// Get a specific stat
count, err := statsManager.GetStat(userID, "myapp", "games_played")

// Get all stats for a user
allStats, err := statsManager.GetAllStats(userID, "myapp")

// Record a score
statsManager.RecordScore(userID, "myapp", 1500)

// Get high score
highScore, err := statsManager.GetHighScore(userID, "myapp")

// Get leaderboard
leaderboard, err := statsManager.GetLeaderboard("myapp", 10)
```

### AchievementManager

The `AchievementManager` tracks achievements:

```go
achievementMgr := app.NewAchievementManager(db)

// Register an achievement
achievementMgr.RegisterAchievement(app.Achievement{
    ID:          "first_win",
    AppName:     "myapp",
    Name:        "First Victory",
    Description: "Win your first game",
    Icon:        "trophy",
    Points:      10,
    Threshold:   1,
})

// Unlock an achievement
achievementMgr.UnlockAchievement(userID, "first_win")

// Check if user has achievement
has, err := achievementMgr.HasAchievement(userID, "first_win")

// Get all achievements for user in app
achievements, err := achievementMgr.GetUserAchievements(userID, "myapp")
```

## Database Tables

The framework provides shared tables for all apps:

### app_stats
Stores generic statistics for each app:
- `user_id`: Reference to users table
- `app_name`: App identifier
- `stat_name`: Name of the stat (e.g., "games_played", "total_time")
- `value`: Integer value of the stat

### app_scores
Stores score entries for leaderboards:
- `user_id`: Reference to users table
- `app_name`: App identifier
- `score`: The score value
- `created_at`: When the score was recorded

### achievements
Defines available achievements:
- `id`: Unique achievement identifier
- `app_name`: App identifier
- `name`: Human-readable name
- `description`: Description
- `icon`: Icon name or path
- `points`: Points awarded
- `threshold`: Threshold for automatic unlock

### user_achievements
Tracks which achievements users have unlocked:
- `user_id`: Reference to users table
- `achievement_id`: Reference to achievements
- `unlocked_at`: When unlocked

### app_progress
Tracks app-specific progress (levels, experience, streaks):
- `user_id`: Reference to users table
- `app_name`: App identifier
- `level`: Current level
- `experience`: Total experience
- `streak`: Current streak count
- `last_played`: Last play timestamp

## API Endpoints

Every app automatically gets these routes:

### GET /api/<app_name>/status
Health check endpoint for the app.

### GET /api/<app_name>/stats
Get current user's statistics for this app.
**Requires Authentication**

### GET /api/<app_name>/leaderboard
Get top 10 players on the leaderboard.

### POST /api/<app_name>/score
Record a new score for the current user.
**Requires Authentication**

Example request:
```json
{
    "score": 1500
}
```

## Built-in Middleware

### RequireAuth()
Validates user session and enforces authentication.

```go
router.GET("/protected", middleware.RequireAuth(), handler)
```

### GetUserID()
Extracts the user ID from the context.

```go
func (a *MyApp) someHandler(c *gin.Context) {
    userID, _ := middleware.GetUserID(c)
    // userID is now available
}
```

## Error Handling

Use the `api` package for consistent error responses:

```go
import "github.com/jgirmay/GAIA_GO/internal/api"

// Success response
api.RespondWith(c, 200, data)

// Error responses
api.RespondWithError(c, api.ErrBadRequest)
api.RespondWithError(c, api.ErrNotFound)
api.RespondWithError(c, api.ErrConflict)
api.RespondWithError(c, api.ErrInternalServer)
api.RespondWithError(c, api.ErrUnauthorized)
```

## Testing Your App

### Unit Tests

Create `pkg/apps/myapp/app_test.go`:

```go
package myapp

import (
    "database/sql"
    "testing"
    _ "github.com/mattn/go-sqlite3"
)

func TestMyAppInterface(t *testing.T) {
    db, _ := sql.Open("sqlite3", ":memory:")
    defer db.Close()

    app := NewMyApp(db)

    if app.GetName() != "myapp" {
        t.Error("GetName() should return 'myapp'")
    }
}
```

### Manual Testing

Test endpoints with curl:

```bash
# Status check
curl http://localhost:8080/api/myapp/status

# Get stats (requires auth token)
curl -H "Authorization: Bearer TOKEN" \
    http://localhost:8080/api/myapp/stats

# Get leaderboard
curl http://localhost:8080/api/myapp/leaderboard

# Save score
curl -X POST http://localhost:8080/api/myapp/score \
    -H "Authorization: Bearer TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"score": 1500}'
```

## Troubleshooting

### App not appearing in registry?
- Ensure app is registered before `RegisterRoutes()` is called
- Check app name matches between config and `GetName()`
- Verify no duplicate app names

### Database errors?
- Run migrations: `sqlite3 app.db < migrations/003_app_framework.sql`
- Check foreign key constraints match users table
- Verify table names don't conflict with existing tables

### Routes not working?
- Verify routes are registered in `RegisterRoutes()`
- Check middleware (auth) isn't blocking routes that should be public
- Test with curl using the correct path: `/api/<app_name>/endpoint`
- Check if port 8080 is correct in your configuration

### Stats not appearing?
- Verify `StatsManager` is initialized properly
- Check app name is consistent across calls
- Ensure user ID is valid and exists in users table

### Leaderboard is empty?
- Check if scores have been recorded
- Verify user IDs in app_scores match users table
- Ensure `GetLeaderboard()` is calling `statsManager.GetLeaderboard()` correctly

## Example Apps

Complete example apps in the repository:

- **Typing App** (`pkg/apps/typing/`): Real-time typing practice with multiplayer support
- **Math App** (`pkg/apps/math/`): Mathematical problem solving
- **Reading App** (`pkg/apps/reading/`): Reading comprehension
- **Piano App** (`pkg/apps/piano/`): Piano learning game
- **Guessing App** (`pkg/apps/guessing/`): Number guessing game

Study these implementations for reference when building your own apps.

## Framework Code Reference

- **Core Framework**: `internal/app/`
  - `interface.go`: App interface definition
  - `registry.go`: App registration and discovery
  - `stats_manager.go`: Statistics tracking
  - `achievements.go`: Achievement system
- **Database Migrations**: `migrations/003_app_framework.sql`
- **Example Apps**: `pkg/apps/*/`

## Best Practices

1. **Namespace your stats**: Use descriptive names like "games_played", "total_score", "win_rate"
2. **Error handling**: Always handle database errors gracefully
3. **Input validation**: Validate all JSON requests with `ShouldBindJSON`
4. **Authentication**: Use `RequireAuth()` for user-specific endpoints
5. **Atomic operations**: Use database transactions for critical operations
6. **Connection pooling**: Let the main server handle database connection pooling
7. **Testing**: Write unit tests for your app logic
8. **Documentation**: Document custom endpoints and stats names

## API Discovery

The framework provides a discovery endpoint at `/api/apps` that lists all registered apps:

```json
{
    "apps": {
        "typing": {
            "name": "typing",
            "display_name": "Typing Master",
            "description": "Practice typing...",
            "version": "1.0.0",
            "status": "active"
        },
        "math": {
            "name": "math",
            "display_name": "Math Master",
            "description": "Practice math...",
            "version": "1.0.0",
            "status": "active"
        }
    },
    "count": 2
}
```

## Support

For issues or questions:
- Framework code: `internal/app/`
- Example implementations: `pkg/apps/`
- Database schema: `migrations/003_app_framework.sql`
