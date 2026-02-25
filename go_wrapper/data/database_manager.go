package data

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	_ "github.com/mattn/go-sqlite3"
)

// DatabaseManager handles environment-isolated SQLite databases
type DatabaseManager struct {
	environment string
	dataDir     string
	connections map[string]*sql.DB
}

// NewDatabaseManager creates a database manager for an environment
func NewDatabaseManager(environment, dataDir string) (*DatabaseManager, error) {
	envDataDir := filepath.Join(dataDir, environment)
	if err := os.MkdirAll(envDataDir, 0750); err != nil {
		return nil, fmt.Errorf("failed to create environment data directory: %w", err)
	}

	// Set restrictive permissions on data directory
	if err := os.Chmod(envDataDir, 0750); err != nil {
		return nil, fmt.Errorf("failed to set permissions on data directory: %w", err)
	}

	fmt.Printf("[Database] Initialized for environment: %s\n", environment)
	fmt.Printf("[Database] Data directory: %s (permissions: 0750)\n", envDataDir)

	return &DatabaseManager{
		environment: environment,
		dataDir:     envDataDir,
		connections: make(map[string]*sql.DB),
	}, nil
}

// GetDatabase opens or returns an existing database connection
func (dm *DatabaseManager) GetDatabase(name string) (*sql.DB, error) {
	if db, exists := dm.connections[name]; exists {
		return db, nil
	}

	dbPath := filepath.Join(dm.dataDir, fmt.Sprintf("%s.db", name))

	// Open database with specific flags for safety
	connStr := fmt.Sprintf("file:%s?mode=rwc&_journal_mode=WAL&_foreign_keys=on", dbPath)
	db, err := sql.Open("sqlite3", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open database %s: %w", name, err)
	}

	// Test connection
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to ping database %s: %w", name, err)
	}

	// Set restrictive permissions on database file
	if err := os.Chmod(dbPath, 0640); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to set permissions on database file: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(5)
	db.SetMaxIdleConns(2)

	dm.connections[name] = db

	fmt.Printf("[Database] Opened: %s (permissions: 0640)\n", dbPath)

	return db, nil
}

// CreateDatabase creates a new database with initialization schema
func (dm *DatabaseManager) CreateDatabase(name string, schema string) (*sql.DB, error) {
	db, err := dm.GetDatabase(name)
	if err != nil {
		return nil, err
	}

	// Execute initialization schema
	if schema != "" {
		if _, err := db.Exec(schema); err != nil {
			return nil, fmt.Errorf("failed to initialize database schema: %w", err)
		}
		fmt.Printf("[Database] Schema initialized for %s\n", name)
	}

	return db, nil
}

// GetFeedbackDatabase returns the feedback tracking database
func (dm *DatabaseManager) GetFeedbackDatabase() (*sql.DB, error) {
	schema := `
		CREATE TABLE IF NOT EXISTS outcomes (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			outcome_id TEXT NOT NULL,
			timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
			agent_name TEXT NOT NULL,
			environment TEXT NOT NULL,
			task_type TEXT NOT NULL,
			action TEXT NOT NULL,
			success BOOLEAN NOT NULL,
			duration_ms INTEGER,
			error_msg TEXT,
			pattern TEXT,
			risk_level TEXT,
			was_blocked BOOLEAN DEFAULT 0,
			block_reason TEXT,
			context_json TEXT
		);

		CREATE INDEX IF NOT EXISTS idx_outcomes_agent ON outcomes(agent_name);
		CREATE INDEX IF NOT EXISTS idx_outcomes_success ON outcomes(success);
		CREATE INDEX IF NOT EXISTS idx_outcomes_timestamp ON outcomes(timestamp);
		CREATE INDEX IF NOT EXISTS idx_outcomes_pattern ON outcomes(pattern);

		CREATE TABLE IF NOT EXISTS feedback_stats (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			agent_name TEXT NOT NULL,
			environment TEXT NOT NULL,
			total_outcomes INTEGER DEFAULT 0,
			successful_outcomes INTEGER DEFAULT 0,
			failed_outcomes INTEGER DEFAULT 0,
			blocked_outcomes INTEGER DEFAULT 0,
			last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(agent_name, environment)
		);
	`

	return dm.CreateDatabase("feedback", schema)
}

// GetExtractionDatabase returns the extraction events database
func (dm *DatabaseManager) GetExtractionDatabase() (*sql.DB, error) {
	schema := `
		CREATE TABLE IF NOT EXISTS extraction_events (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			event_id TEXT NOT NULL,
			timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
			agent_name TEXT NOT NULL,
			event_type TEXT NOT NULL,
			pattern TEXT NOT NULL,
			matched TEXT,
			fields_json TEXT,
			metadata_json TEXT,
			auto_confirmable BOOLEAN DEFAULT 0,
			risk_level TEXT
		);

		CREATE INDEX IF NOT EXISTS idx_events_agent ON extraction_events(agent_name);
		CREATE INDEX IF NOT EXISTS idx_events_type ON extraction_events(event_type);
		CREATE INDEX IF NOT EXISTS idx_events_pattern ON extraction_events(pattern);
		CREATE INDEX IF NOT EXISTS idx_events_timestamp ON extraction_events(timestamp);

		CREATE TABLE IF NOT EXISTS pattern_stats (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			pattern TEXT NOT NULL,
			agent_name TEXT NOT NULL,
			total_matches INTEGER DEFAULT 0,
			auto_confirmable_matches INTEGER DEFAULT 0,
			avg_confidence REAL,
			last_matched DATETIME DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(pattern, agent_name)
		);
	`

	return dm.CreateDatabase("extraction", schema)
}

// GetAgentDatabase returns an agent-specific database
func (dm *DatabaseManager) GetAgentDatabase(agentName string) (*sql.DB, error) {
	schema := `
		CREATE TABLE IF NOT EXISTS agent_sessions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			session_id TEXT NOT NULL UNIQUE,
			started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			ended_at DATETIME,
			exit_code INTEGER,
			total_lines INTEGER DEFAULT 0,
			total_events INTEGER DEFAULT 0
		);

		CREATE TABLE IF NOT EXISTS agent_actions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			session_id TEXT NOT NULL,
			timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
			action_type TEXT NOT NULL,
			action_data TEXT,
			success BOOLEAN DEFAULT 1,
			FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
		);

		CREATE INDEX IF NOT EXISTS idx_actions_session ON agent_actions(session_id);
		CREATE INDEX IF NOT EXISTS idx_actions_timestamp ON agent_actions(timestamp);
	`

	return dm.CreateDatabase(fmt.Sprintf("agent_%s", agentName), schema)
}

// CloseAll closes all database connections
func (dm *DatabaseManager) CloseAll() error {
	var errs []error

	for name, db := range dm.connections {
		if err := db.Close(); err != nil {
			errs = append(errs, fmt.Errorf("failed to close %s: %w", name, err))
		} else {
			fmt.Printf("[Database] Closed: %s\n", name)
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("errors closing databases: %v", errs)
	}

	return nil
}

// GetDatabasePath returns the path to a database file
func (dm *DatabaseManager) GetDatabasePath(name string) string {
	return filepath.Join(dm.dataDir, fmt.Sprintf("%s.db", name))
}

// ListDatabases returns all database files in the environment
func (dm *DatabaseManager) ListDatabases() ([]string, error) {
	files, err := os.ReadDir(dm.dataDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read data directory: %w", err)
	}

	databases := make([]string, 0)
	for _, file := range files {
		if !file.IsDir() && filepath.Ext(file.Name()) == ".db" {
			databases = append(databases, file.Name())
		}
	}

	return databases, nil
}

// GetEnvironment returns the environment name
func (dm *DatabaseManager) GetEnvironment() string {
	return dm.environment
}
