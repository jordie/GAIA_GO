package main

import (
	"database/sql"
	"log"
	"os"
	"path/filepath"

	_ "github.com/mattn/go-sqlite3"

	"github.com/jgirmay/GAIA_GO/internal/session"
	"github.com/jgirmay/GAIA_GO/internal/tmux"
	"github.com/jgirmay/GAIA_GO/pkg/router"
)

func main() {
	// Configuration
	port := getEnv("PORT", "8080")
	dbPath := getEnv("DATABASE_URL", "./data/education_central.db")
	env := getEnv("APP_ENV", "development")

	// Initialize database
	db, err := initDB(dbPath)
	if err != nil {
		log.Fatalf("failed to initialize database: %v", err)
	}
	defer db.Close()

	log.Printf("[INFO] Database initialized at %s", dbPath)

	// Initialize session manager
	sessionMgr := session.NewManager(db)
	log.Printf("[INFO] Session manager initialized")

	// Initialize tmux session grouping service
	tmuxService := tmux.NewService(db)
	log.Printf("[INFO] Tmux session grouping service initialized")

	// Create router
	appRouter := router.NewAppRouter(sessionMgr)
	appRouter.RegisterMiddleware()

	// Register endpoints
	appRouter.RegisterAuthRoutes()
	appRouter.RegisterUserRoutes()

	// Auto-register all GAIA apps with discovery and dependency resolution
	if err := appRouter.RegisterAllApps(db, sessionMgr); err != nil {
		log.Printf("[WARN] Failed to auto-register apps: %v", err)
	}
	log.Printf("[INFO] All apps auto-registered")

	// Register tmux session grouping routes
	apiGroup := appRouter.GetEngine().Group("/api")
	tmux.RegisterRoutes(apiGroup, tmuxService)
	log.Printf("[INFO] Tmux session grouping routes registered")

	// Serve static files for each app
	staticDirs := map[string]string{
		"typing":  "./web/static/typing",
		"math":    "./web/static/math",
		"piano":   "./web/static/piano",
		"reading": "./web/static/reading",
	}
	for appName, staticDir := range staticDirs {
		appRouter.RegisterStaticFiles(appName, staticDir)
	}
	appRouter.RegisterSharedStaticFiles()
	log.Printf("[INFO] Static files registered for all apps")

	// Print routes
	printRoutes(env)

	// Start server
	addr := ":" + port
	log.Printf("[INFO] Starting server on %s (env: %s)", addr, env)

	if err := appRouter.GetEngine().Run(addr); err != nil {
		log.Fatalf("failed to start server: %v", err)
	}
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

// initDB initializes the database connection and runs migrations
func initDB(dbPath string) (*sql.DB, error) {
	// Create directory if it doesn't exist
	dir := filepath.Dir(dbPath)
	if dir != "." && dir != "" {
		os.MkdirAll(dir, 0755)
	}

	// Open connection
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, err
	}

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, err
	}

	// Enable WAL mode for better concurrency
	if _, err := db.Exec("PRAGMA journal_mode=WAL"); err != nil {
		return nil, err
	}

	// Set busy timeout
	if _, err := db.Exec("PRAGMA busy_timeout=30000"); err != nil {
		return nil, err
	}

	// Run migrations
	if err := runMigrations(db); err != nil {
		return nil, err
	}

	return db, nil
}

// runMigrations runs all pending migrations
func runMigrations(db *sql.DB) error {
	// Migration 1: Phase 9 shared infrastructure
	migration1 := `
	CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT UNIQUE NOT NULL,
		email TEXT UNIQUE,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		xp INTEGER DEFAULT 0,
		level INTEGER DEFAULT 1,
		total_sessions INTEGER DEFAULT 0,
		preferred_app TEXT DEFAULT 'typing'
	);

	CREATE TABLE IF NOT EXISTS sessions (
		id TEXT PRIMARY KEY,
		user_id INTEGER NOT NULL,
		username TEXT NOT NULL,
		device_fingerprint TEXT,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		expires_at TIMESTAMP NOT NULL,
		active INTEGER DEFAULT 1,
		FOREIGN KEY (user_id) REFERENCES users(id)
	);

	CREATE TABLE IF NOT EXISTS typing_results (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		wpm INTEGER NOT NULL,
		raw_wpm INTEGER,
		accuracy REAL NOT NULL,
		test_type TEXT,
		test_mode TEXT,
		test_duration INTEGER,
		total_characters INTEGER,
		correct_characters INTEGER,
		incorrect_characters INTEGER,
		errors INTEGER,
		time_taken REAL,
		text_snippet TEXT,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (user_id) REFERENCES users(id)
	);

	CREATE TABLE IF NOT EXISTS typing_stats (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER UNIQUE,
		total_tests INTEGER DEFAULT 0,
		average_wpm REAL DEFAULT 0,
		average_accuracy REAL DEFAULT 0,
		best_wpm INTEGER DEFAULT 0,
		total_time_typed INTEGER DEFAULT 0,
		last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (user_id) REFERENCES users(id)
	);

	CREATE TABLE IF NOT EXISTS races (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		difficulty TEXT DEFAULT 'medium',
		placement INTEGER,
		wpm INTEGER,
		accuracy REAL,
		race_time REAL,
		xp_earned INTEGER DEFAULT 0,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (user_id) REFERENCES users(id)
	);

	CREATE TABLE IF NOT EXISTS racing_stats (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER UNIQUE,
		total_races INTEGER DEFAULT 0,
		wins INTEGER DEFAULT 0,
		podiums INTEGER DEFAULT 0,
		total_xp INTEGER DEFAULT 0,
		current_car TEXT DEFAULT '🚗',
		FOREIGN KEY (user_id) REFERENCES users(id)
	);

	CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
	CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
	CREATE INDEX IF NOT EXISTS idx_typing_results_user_id ON typing_results(user_id);
	`

	if _, err := db.Exec(migration1); err != nil {
		return err
	}

	// Create default guest user if not exists
	var guestID int64
	err := db.QueryRow("SELECT id FROM users WHERE username = 'Guest'").Scan(&guestID)
	if err == sql.ErrNoRows {
		result, err := db.Exec("INSERT INTO users (username) VALUES (?)", "Guest")
		if err != nil {
			return err
		}
		guestID, _ := result.LastInsertId()
		db.Exec("INSERT INTO typing_stats (user_id, total_tests) VALUES (?, 0)", guestID)
	}

	// Migration 4: Tmux Session Grouping
	migration4 := `
	CREATE TABLE IF NOT EXISTS projects (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		slug TEXT UNIQUE NOT NULL,
		name TEXT NOT NULL,
		icon TEXT,
		display_order INTEGER DEFAULT 0,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS tmux_sessions (
		id TEXT PRIMARY KEY,
		name TEXT UNIQUE NOT NULL,
		project_id INTEGER,
		environment TEXT DEFAULT 'dev',
		is_worker BOOLEAN DEFAULT 0,
		attached BOOLEAN DEFAULT 0,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY(project_id) REFERENCES projects(id)
	);

	CREATE TABLE IF NOT EXISTS session_group_prefs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		group_id TEXT NOT NULL,
		collapsed BOOLEAN DEFAULT 0,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY(user_id) REFERENCES users(id),
		UNIQUE(user_id, group_id)
	);

	CREATE INDEX IF NOT EXISTS idx_tmux_sessions_project_id ON tmux_sessions(project_id);
	CREATE INDEX IF NOT EXISTS idx_tmux_sessions_environment ON tmux_sessions(environment);
	CREATE INDEX IF NOT EXISTS idx_tmux_sessions_is_worker ON tmux_sessions(is_worker);
	CREATE INDEX IF NOT EXISTS idx_tmux_sessions_name ON tmux_sessions(name);
	CREATE INDEX IF NOT EXISTS idx_session_group_prefs_user_id ON session_group_prefs(user_id);

	INSERT OR IGNORE INTO projects (slug, name, icon, display_order) VALUES
		('basic_edu', 'Basic Education Apps', '🎓', 1),
		('rando', 'Rando Project', '🎲', 2),
		('architect', 'Architect System', '🏗️', 3),
		('gaia_improvements', 'GAIA Improvements', '⚡', 4);
	`

	if _, err := db.Exec(migration4); err != nil {
		return err
	}

	return nil
}

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// printRoutes logs available API routes
func printRoutes(env string) {
	log.Println("===============================================")
	log.Println("GAIA Education Platform - Phase 9")
	log.Println("===============================================")
	log.Println()
	log.Println("Available API Routes:")
	log.Println()
	log.Println("Authentication:")
	log.Println("  POST   /api/auth/login                 - Login")
	log.Println("  POST   /api/auth/register              - Register")
	log.Println("  POST   /api/auth/logout                - Logout")
	log.Println("  GET    /api/auth/me                    - Current user")
	log.Println()
	log.Println("Users:")
	log.Println("  GET    /api/users                      - List users")
	log.Println("  POST   /api/users                      - Create user")
	log.Println()
	log.Println("Typing App:")
	log.Println("  GET    /api/typing/current-user        - Current user")
	log.Println("  GET    /api/typing/users               - List users")
	log.Println("  POST   /api/typing/users               - Create user")
	log.Println("  GET    /api/typing/text                - Get typing text")
	log.Println("  POST   /api/typing/save-result         - Save test result")
	log.Println("  GET    /api/typing/stats               - User statistics")
	log.Println("  GET    /api/typing/leaderboard         - Leaderboard")
	log.Println("  POST   /api/typing/race/start          - Start race")
	log.Println("  POST   /api/typing/race/finish         - Finish race")
	log.Println("  GET    /api/typing/race/stats          - Race statistics")
	log.Println("  GET    /api/typing/race/leaderboard    - Race leaderboard")
	log.Println()
	log.Println("===============================================")
}
