package data

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// SessionStore handles database operations for process sessions
type SessionStore struct {
	db *sql.DB
}

// ProcessSession represents a single agent execution session
type ProcessSession struct {
	ID                       int64     `json:"id"`
	AgentName                string    `json:"agent_name"`
	SessionID                string    `json:"session_id"`
	Environment              string    `json:"environment"`
	StartedAt                time.Time `json:"started_at"`
	EndedAt                  *time.Time `json:"ended_at,omitempty"`
	ExitCode                 *int       `json:"exit_code,omitempty"`
	TotalLinesProcessed      int        `json:"total_lines_processed"`
	TotalExtractionEvents    int        `json:"total_extraction_events"`
	TotalFeedbackOutcomes    int        `json:"total_feedback_outcomes"`
	StdoutLogPath            string     `json:"stdout_log_path"`
	StderrLogPath            string     `json:"stderr_log_path"`
	ExtractionConfigVersion  string     `json:"extraction_config_version"`
	EnvironmentConfigVersion string     `json:"environment_config_version"`
}

// StateChange represents a state transition event
type StateChange struct {
	ID        int64                  `json:"id"`
	SessionID string                 `json:"session_id"`
	Timestamp time.Time              `json:"timestamp"`
	State     string                 `json:"state"`
	ExitCode  *int                   `json:"exit_code,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// SessionStats contains aggregate statistics for a session
type SessionStats struct {
	TotalLines       int `json:"total_lines"`
	TotalExtractions int `json:"total_extractions"`
	TotalFeedback    int `json:"total_feedback"`
}

// SessionUpdate contains fields that can be updated for a session
type SessionUpdate struct {
	TotalLinesProcessed   *int
	TotalExtractionEvents *int
	TotalFeedbackOutcomes *int
}

// NewSessionStore creates a new session store with database connection
func NewSessionStore(dbPath string) (*SessionStore, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	store := &SessionStore{db: db}

	// Initialize schema
	if err := store.initSchema(); err != nil {
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	return store, nil
}

// initSchema creates tables if they don't exist
func (ss *SessionStore) initSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS process_sessions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		agent_name TEXT NOT NULL,
		session_id TEXT NOT NULL UNIQUE,
		environment TEXT,
		started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		ended_at DATETIME,
		exit_code INTEGER,
		total_lines_processed INTEGER DEFAULT 0,
		total_extraction_events INTEGER DEFAULT 0,
		total_feedback_outcomes INTEGER DEFAULT 0,
		stdout_log_path TEXT,
		stderr_log_path TEXT,
		extraction_config_version TEXT,
		environment_config_version TEXT
	);

	CREATE INDEX IF NOT EXISTS idx_agent_started ON process_sessions(agent_name, started_at DESC);
	CREATE INDEX IF NOT EXISTS idx_session_id ON process_sessions(session_id);
	CREATE INDEX IF NOT EXISTS idx_ended_at ON process_sessions(ended_at);

	CREATE TABLE IF NOT EXISTS process_state_changes (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL,
		timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
		state TEXT,
		exit_code INTEGER,
		metadata_json TEXT,
		FOREIGN KEY (session_id) REFERENCES process_sessions(session_id)
	);

	CREATE INDEX IF NOT EXISTS idx_state_session ON process_state_changes(session_id, timestamp);
	`

	_, err := ss.db.Exec(schema)
	return err
}

// CreateSession creates a new session record
func (ss *SessionStore) CreateSession(agentName, sessionID, environment string) error {
	query := `
		INSERT INTO process_sessions (
			agent_name, session_id, environment, started_at
		) VALUES (?, ?, ?, ?)
	`

	_, err := ss.db.Exec(query, agentName, sessionID, environment, time.Now())
	if err != nil {
		return fmt.Errorf("failed to create session: %w", err)
	}

	// Record initial state change
	stateChange := &StateChange{
		SessionID: sessionID,
		Timestamp: time.Now(),
		State:     "started",
		Metadata:  map[string]interface{}{"environment": environment},
	}

	return ss.RecordStateChange(stateChange)
}

// UpdateSession updates session fields
func (ss *SessionStore) UpdateSession(sessionID string, updates SessionUpdate) error {
	// Build dynamic query based on provided fields
	query := "UPDATE process_sessions SET "
	args := []interface{}{}
	updates_added := 0

	if updates.TotalLinesProcessed != nil {
		if updates_added > 0 {
			query += ", "
		}
		query += "total_lines_processed = ?"
		args = append(args, *updates.TotalLinesProcessed)
		updates_added++
	}

	if updates.TotalExtractionEvents != nil {
		if updates_added > 0 {
			query += ", "
		}
		query += "total_extraction_events = ?"
		args = append(args, *updates.TotalExtractionEvents)
		updates_added++
	}

	if updates.TotalFeedbackOutcomes != nil {
		if updates_added > 0 {
			query += ", "
		}
		query += "total_feedback_outcomes = ?"
		args = append(args, *updates.TotalFeedbackOutcomes)
		updates_added++
	}

	if updates_added == 0 {
		return nil // Nothing to update
	}

	query += " WHERE session_id = ?"
	args = append(args, sessionID)

	_, err := ss.db.Exec(query, args...)
	if err != nil {
		return fmt.Errorf("failed to update session: %w", err)
	}

	return nil
}

// CompleteSession marks a session as completed
func (ss *SessionStore) CompleteSession(sessionID string, exitCode int, stats SessionStats) error {
	query := `
		UPDATE process_sessions
		SET ended_at = ?,
		    exit_code = ?,
		    total_lines_processed = ?,
		    total_extraction_events = ?,
		    total_feedback_outcomes = ?
		WHERE session_id = ?
	`

	endedAt := time.Now()
	_, err := ss.db.Exec(query,
		endedAt,
		exitCode,
		stats.TotalLines,
		stats.TotalExtractions,
		stats.TotalFeedback,
		sessionID,
	)
	if err != nil {
		return fmt.Errorf("failed to complete session: %w", err)
	}

	// Record state change
	stateChange := &StateChange{
		SessionID: sessionID,
		Timestamp: endedAt,
		State:     "completed",
		ExitCode:  &exitCode,
		Metadata: map[string]interface{}{
			"total_lines":       stats.TotalLines,
			"total_extractions": stats.TotalExtractions,
		},
	}

	return ss.RecordStateChange(stateChange)
}

// GetSession retrieves a session by ID
func (ss *SessionStore) GetSession(sessionID string) (*ProcessSession, error) {
	query := `
		SELECT id, agent_name, session_id, environment, started_at, ended_at,
		       exit_code, total_lines_processed, total_extraction_events,
		       total_feedback_outcomes, stdout_log_path, stderr_log_path,
		       extraction_config_version, environment_config_version
		FROM process_sessions
		WHERE session_id = ?
	`

	var session ProcessSession
	var endedAt sql.NullTime
	var exitCode sql.NullInt64
	var stdoutPath, stderrPath, extractConfig, envConfig sql.NullString

	err := ss.db.QueryRow(query, sessionID).Scan(
		&session.ID,
		&session.AgentName,
		&session.SessionID,
		&session.Environment,
		&session.StartedAt,
		&endedAt,
		&exitCode,
		&session.TotalLinesProcessed,
		&session.TotalExtractionEvents,
		&session.TotalFeedbackOutcomes,
		&stdoutPath,
		&stderrPath,
		&extractConfig,
		&envConfig,
	)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("session not found: %s", sessionID)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	if endedAt.Valid {
		session.EndedAt = &endedAt.Time
	}
	if exitCode.Valid {
		code := int(exitCode.Int64)
		session.ExitCode = &code
	}
	if stdoutPath.Valid {
		session.StdoutLogPath = stdoutPath.String
	}
	if stderrPath.Valid {
		session.StderrLogPath = stderrPath.String
	}
	if extractConfig.Valid {
		session.ExtractionConfigVersion = extractConfig.String
	}
	if envConfig.Valid {
		session.EnvironmentConfigVersion = envConfig.String
	}

	return &session, nil
}

// GetSessionsByAgent retrieves recent sessions for an agent
func (ss *SessionStore) GetSessionsByAgent(agentName string, limit int) ([]*ProcessSession, error) {
	query := `
		SELECT id, agent_name, session_id, environment, started_at, ended_at,
		       exit_code, total_lines_processed, total_extraction_events,
		       total_feedback_outcomes, stdout_log_path, stderr_log_path,
		       extraction_config_version, environment_config_version
		FROM process_sessions
		WHERE agent_name = ?
		ORDER BY started_at DESC
		LIMIT ?
	`

	rows, err := ss.db.Query(query, agentName, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query sessions: %w", err)
	}
	defer rows.Close()

	return ss.scanSessions(rows)
}

// GetSessionHistory retrieves sessions within a time range
func (ss *SessionStore) GetSessionHistory(agentName string, days int) ([]*ProcessSession, error) {
	since := time.Now().AddDate(0, 0, -days)

	query := `
		SELECT id, agent_name, session_id, environment, started_at, ended_at,
		       exit_code, total_lines_processed, total_extraction_events,
		       total_feedback_outcomes, stdout_log_path, stderr_log_path,
		       extraction_config_version, environment_config_version
		FROM process_sessions
		WHERE agent_name = ? AND started_at >= ?
		ORDER BY started_at DESC
	`

	rows, err := ss.db.Query(query, agentName, since)
	if err != nil {
		return nil, fmt.Errorf("failed to query session history: %w", err)
	}
	defer rows.Close()

	return ss.scanSessions(rows)
}

// GetActiveSessions retrieves sessions that haven't ended yet
func (ss *SessionStore) GetActiveSessions() ([]*ProcessSession, error) {
	query := `
		SELECT id, agent_name, session_id, environment, started_at, ended_at,
		       exit_code, total_lines_processed, total_extraction_events,
		       total_feedback_outcomes, stdout_log_path, stderr_log_path,
		       extraction_config_version, environment_config_version
		FROM process_sessions
		WHERE ended_at IS NULL
		ORDER BY started_at DESC
	`

	rows, err := ss.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query active sessions: %w", err)
	}
	defer rows.Close()

	return ss.scanSessions(rows)
}

// RecordStateChange records a state transition
func (ss *SessionStore) RecordStateChange(change *StateChange) error {
	metadataJSON, err := json.Marshal(change.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `
		INSERT INTO process_state_changes (
			session_id, timestamp, state, exit_code, metadata_json
		) VALUES (?, ?, ?, ?, ?)
	`

	result, err := ss.db.Exec(query,
		change.SessionID,
		change.Timestamp,
		change.State,
		change.ExitCode,
		string(metadataJSON),
	)
	if err != nil {
		return fmt.Errorf("failed to record state change: %w", err)
	}

	id, err := result.LastInsertId()
	if err == nil {
		change.ID = id
	}

	return nil
}

// GetStateChanges retrieves state changes for a session
func (ss *SessionStore) GetStateChanges(sessionID string) ([]*StateChange, error) {
	query := `
		SELECT id, session_id, timestamp, state, exit_code, metadata_json
		FROM process_state_changes
		WHERE session_id = ?
		ORDER BY timestamp ASC
	`

	rows, err := ss.db.Query(query, sessionID)
	if err != nil {
		return nil, fmt.Errorf("failed to query state changes: %w", err)
	}
	defer rows.Close()

	var changes []*StateChange
	for rows.Next() {
		var change StateChange
		var exitCode sql.NullInt64
		var metadataJSON string

		err := rows.Scan(
			&change.ID,
			&change.SessionID,
			&change.Timestamp,
			&change.State,
			&exitCode,
			&metadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan state change: %w", err)
		}

		if exitCode.Valid {
			code := int(exitCode.Int64)
			change.ExitCode = &code
		}

		if err := json.Unmarshal([]byte(metadataJSON), &change.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		changes = append(changes, &change)
	}

	return changes, rows.Err()
}

// Close closes the database connection
func (ss *SessionStore) Close() error {
	if ss.db != nil {
		return ss.db.Close()
	}
	return nil
}

// Helper function to scan session rows
func (ss *SessionStore) scanSessions(rows *sql.Rows) ([]*ProcessSession, error) {
	var sessions []*ProcessSession

	for rows.Next() {
		var session ProcessSession
		var endedAt sql.NullTime
		var exitCode sql.NullInt64
		var stdoutPath, stderrPath, extractConfig, envConfig sql.NullString

		err := rows.Scan(
			&session.ID,
			&session.AgentName,
			&session.SessionID,
			&session.Environment,
			&session.StartedAt,
			&endedAt,
			&exitCode,
			&session.TotalLinesProcessed,
			&session.TotalExtractionEvents,
			&session.TotalFeedbackOutcomes,
			&stdoutPath,
			&stderrPath,
			&extractConfig,
			&envConfig,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan session: %w", err)
		}

		if endedAt.Valid {
			session.EndedAt = &endedAt.Time
		}
		if exitCode.Valid {
			code := int(exitCode.Int64)
			session.ExitCode = &code
		}
		if stdoutPath.Valid {
			session.StdoutLogPath = stdoutPath.String
		}
		if stderrPath.Valid {
			session.StderrLogPath = stderrPath.String
		}
		if extractConfig.Valid {
			session.ExtractionConfigVersion = extractConfig.String
		}
		if envConfig.Valid {
			session.EnvironmentConfigVersion = envConfig.String
		}

		sessions = append(sessions, &session)
	}

	return sessions, rows.Err()
}
