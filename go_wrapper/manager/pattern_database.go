package manager

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// Pattern represents a recognized pattern in agent output
type Pattern struct {
	ID              int                    `json:"id"`
	Name            string                 `json:"name"`
	Regex           string                 `json:"regex"`
	Category        string                 `json:"category"` // tool_use, state_change, error, etc.
	Confidence      float64                `json:"confidence"` // 0.0 to 1.0
	MatchCount      int                    `json:"match_count"`
	Action          string                 `json:"action,omitempty"` // What to do when matched
	TargetWorker    string                 `json:"target_worker,omitempty"` // Which worker to dispatch to
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt       time.Time              `json:"created_at"`
	LastMatched     *time.Time             `json:"last_matched,omitempty"`
	ProposedBy      string                 `json:"proposed_by,omitempty"` // learning_worker, manual, etc.
	Tested          bool                   `json:"tested"`
	TestSuccessRate float64                `json:"test_success_rate"`
}

// UnknownChunk represents an unrecognized chunk of log output
type UnknownChunk struct {
	ID           int       `json:"id"`
	Content      string    `json:"content"`
	ContextBefore string   `json:"context_before"`
	ContextAfter  string   `json:"context_after"`
	AgentName    string    `json:"agent_name"`
	LogFile      string    `json:"log_file"`
	LineNumber   int       `json:"line_number"`
	Timestamp    time.Time `json:"timestamp"`
	Analyzed     bool      `json:"analyzed"`
	ProposedPattern *int   `json:"proposed_pattern,omitempty"` // Pattern ID if one was proposed
}

// PatternMatch represents a successful pattern match
type PatternMatch struct {
	ID          int       `json:"id"`
	PatternID   int       `json:"pattern_id"`
	PatternName string    `json:"pattern_name"`
	Matched     string    `json:"matched"`
	AgentName   string    `json:"agent_name"`
	LogFile     string    `json:"log_file"`
	LineNumber  int       `json:"line_number"`
	Timestamp   time.Time `json:"timestamp"`
	Dispatched  bool      `json:"dispatched"`
	WorkerName  string    `json:"worker_name,omitempty"`
}

// PatternDatabase manages the pattern recognition database
type PatternDatabase struct {
	db *sql.DB
}

// NewPatternDatabase creates or opens the pattern database
func NewPatternDatabase(dbPath string) (*PatternDatabase, error) {
	db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL")
	if err != nil {
		return nil, fmt.Errorf("failed to open pattern database: %w", err)
	}

	// Create tables
	schema := `
		CREATE TABLE IF NOT EXISTS patterns (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL UNIQUE,
			regex TEXT NOT NULL,
			category TEXT NOT NULL,
			confidence REAL DEFAULT 0.5,
			match_count INTEGER DEFAULT 0,
			action TEXT,
			target_worker TEXT,
			metadata TEXT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			last_matched DATETIME,
			proposed_by TEXT,
			tested BOOLEAN DEFAULT 0,
			test_success_rate REAL DEFAULT 0.0
		);

		CREATE INDEX IF NOT EXISTS idx_patterns_category ON patterns(category);
		CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON patterns(confidence DESC);
		CREATE INDEX IF NOT EXISTS idx_patterns_tested ON patterns(tested);

		CREATE TABLE IF NOT EXISTS unknown_chunks (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			content TEXT NOT NULL,
			context_before TEXT,
			context_after TEXT,
			agent_name TEXT NOT NULL,
			log_file TEXT NOT NULL,
			line_number INTEGER,
			timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
			analyzed BOOLEAN DEFAULT 0,
			proposed_pattern INTEGER,
			FOREIGN KEY (proposed_pattern) REFERENCES patterns(id)
		);

		CREATE INDEX IF NOT EXISTS idx_unknowns_analyzed ON unknown_chunks(analyzed);
		CREATE INDEX IF NOT EXISTS idx_unknowns_agent ON unknown_chunks(agent_name);

		CREATE TABLE IF NOT EXISTS pattern_matches (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			pattern_id INTEGER NOT NULL,
			pattern_name TEXT NOT NULL,
			matched TEXT NOT NULL,
			agent_name TEXT NOT NULL,
			log_file TEXT NOT NULL,
			line_number INTEGER,
			timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
			dispatched BOOLEAN DEFAULT 0,
			worker_name TEXT,
			FOREIGN KEY (pattern_id) REFERENCES patterns(id)
		);

		CREATE INDEX IF NOT EXISTS idx_matches_pattern ON pattern_matches(pattern_id);
		CREATE INDEX IF NOT EXISTS idx_matches_timestamp ON pattern_matches(timestamp DESC);
		CREATE INDEX IF NOT EXISTS idx_matches_dispatched ON pattern_matches(dispatched);
	`

	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to create schema: %w", err)
	}

	return &PatternDatabase{db: db}, nil
}

// AddPattern adds a new pattern to the database
func (pd *PatternDatabase) AddPattern(pattern Pattern) (int, error) {
	metadataJSON, _ := json.Marshal(pattern.Metadata)

	result, err := pd.db.Exec(`
		INSERT INTO patterns (name, regex, category, confidence, action, target_worker, metadata, proposed_by, tested, test_success_rate)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, pattern.Name, pattern.Regex, pattern.Category, pattern.Confidence, pattern.Action, pattern.TargetWorker, string(metadataJSON), pattern.ProposedBy, pattern.Tested, pattern.TestSuccessRate)

	if err != nil {
		return 0, fmt.Errorf("failed to insert pattern: %w", err)
	}

	id, _ := result.LastInsertId()
	return int(id), nil
}

// GetPattern retrieves a pattern by ID
func (pd *PatternDatabase) GetPattern(id int) (*Pattern, error) {
	var pattern Pattern
	var metadataJSON string
	var lastMatched sql.NullTime

	err := pd.db.QueryRow(`
		SELECT id, name, regex, category, confidence, match_count, action, target_worker, metadata,
		       created_at, last_matched, proposed_by, tested, test_success_rate
		FROM patterns WHERE id = ?
	`, id).Scan(&pattern.ID, &pattern.Name, &pattern.Regex, &pattern.Category, &pattern.Confidence,
		&pattern.MatchCount, &pattern.Action, &pattern.TargetWorker, &metadataJSON,
		&pattern.CreatedAt, &lastMatched, &pattern.ProposedBy, &pattern.Tested, &pattern.TestSuccessRate)

	if err != nil {
		return nil, err
	}

	if lastMatched.Valid {
		pattern.LastMatched = &lastMatched.Time
	}

	if metadataJSON != "" {
		json.Unmarshal([]byte(metadataJSON), &pattern.Metadata)
	}

	return &pattern, nil
}

// GetAllPatterns returns all patterns, ordered by confidence
func (pd *PatternDatabase) GetAllPatterns() ([]Pattern, error) {
	rows, err := pd.db.Query(`
		SELECT id, name, regex, category, confidence, match_count, action, target_worker, metadata,
		       created_at, last_matched, proposed_by, tested, test_success_rate
		FROM patterns
		WHERE tested = 1
		ORDER BY confidence DESC, match_count DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	patterns := make([]Pattern, 0)
	for rows.Next() {
		var pattern Pattern
		var metadataJSON string
		var lastMatched sql.NullTime

		if err := rows.Scan(&pattern.ID, &pattern.Name, &pattern.Regex, &pattern.Category, &pattern.Confidence,
			&pattern.MatchCount, &pattern.Action, &pattern.TargetWorker, &metadataJSON,
			&pattern.CreatedAt, &lastMatched, &pattern.ProposedBy, &pattern.Tested, &pattern.TestSuccessRate); err != nil {
			continue
		}

		if lastMatched.Valid {
			pattern.LastMatched = &lastMatched.Time
		}

		if metadataJSON != "" {
			json.Unmarshal([]byte(metadataJSON), &pattern.Metadata)
		}

		patterns = append(patterns, pattern)
	}

	return patterns, nil
}

// RecordMatch records a successful pattern match
func (pd *PatternDatabase) RecordMatch(match PatternMatch) (int, error) {
	result, err := pd.db.Exec(`
		INSERT INTO pattern_matches (pattern_id, pattern_name, matched, agent_name, log_file, line_number, dispatched, worker_name)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`, match.PatternID, match.PatternName, match.Matched, match.AgentName, match.LogFile, match.LineNumber, match.Dispatched, match.WorkerName)

	if err != nil {
		return 0, fmt.Errorf("failed to record match: %w", err)
	}

	// Update pattern match count and last matched
	pd.db.Exec(`
		UPDATE patterns
		SET match_count = match_count + 1, last_matched = CURRENT_TIMESTAMP
		WHERE id = ?
	`, match.PatternID)

	id, _ := result.LastInsertId()
	return int(id), nil
}

// AddUnknownChunk adds an unrecognized chunk to be analyzed
func (pd *PatternDatabase) AddUnknownChunk(chunk UnknownChunk) (int, error) {
	result, err := pd.db.Exec(`
		INSERT INTO unknown_chunks (content, context_before, context_after, agent_name, log_file, line_number)
		VALUES (?, ?, ?, ?, ?, ?)
	`, chunk.Content, chunk.ContextBefore, chunk.ContextAfter, chunk.AgentName, chunk.LogFile, chunk.LineNumber)

	if err != nil {
		return 0, fmt.Errorf("failed to insert unknown chunk: %w", err)
	}

	id, _ := result.LastInsertId()
	return int(id), nil
}

// GetUnanalyzedChunks returns unknown chunks that haven't been analyzed
func (pd *PatternDatabase) GetUnanalyzedChunks(limit int) ([]UnknownChunk, error) {
	rows, err := pd.db.Query(`
		SELECT id, content, context_before, context_after, agent_name, log_file, line_number, timestamp, analyzed
		FROM unknown_chunks
		WHERE analyzed = 0
		ORDER BY timestamp DESC
		LIMIT ?
	`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	chunks := make([]UnknownChunk, 0)
	for rows.Next() {
		var chunk UnknownChunk
		if err := rows.Scan(&chunk.ID, &chunk.Content, &chunk.ContextBefore, &chunk.ContextAfter,
			&chunk.AgentName, &chunk.LogFile, &chunk.LineNumber, &chunk.Timestamp, &chunk.Analyzed); err != nil {
			continue
		}
		chunks = append(chunks, chunk)
	}

	return chunks, nil
}

// MarkChunkAnalyzed marks an unknown chunk as analyzed
func (pd *PatternDatabase) MarkChunkAnalyzed(id int, proposedPatternID *int) error {
	_, err := pd.db.Exec(`
		UPDATE unknown_chunks
		SET analyzed = 1, proposed_pattern = ?
		WHERE id = ?
	`, proposedPatternID, id)
	return err
}

// UpdatePatternConfidence updates a pattern's confidence score
func (pd *PatternDatabase) UpdatePatternConfidence(id int, confidence float64) error {
	_, err := pd.db.Exec(`
		UPDATE patterns SET confidence = ? WHERE id = ?
	`, confidence, id)
	return err
}

// MarkPatternTested marks a pattern as tested with success rate
func (pd *PatternDatabase) MarkPatternTested(id int, successRate float64) error {
	_, err := pd.db.Exec(`
		UPDATE patterns SET tested = 1, test_success_rate = ? WHERE id = ?
	`, successRate, id)
	return err
}

// GetStats returns database statistics
func (pd *PatternDatabase) GetStats() map[string]interface{} {
	var totalPatterns, testedPatterns, totalMatches, unknownChunks, analyzedChunks int

	pd.db.QueryRow("SELECT COUNT(*) FROM patterns").Scan(&totalPatterns)
	pd.db.QueryRow("SELECT COUNT(*) FROM patterns WHERE tested = 1").Scan(&testedPatterns)
	pd.db.QueryRow("SELECT COUNT(*) FROM pattern_matches").Scan(&totalMatches)
	pd.db.QueryRow("SELECT COUNT(*) FROM unknown_chunks").Scan(&unknownChunks)
	pd.db.QueryRow("SELECT COUNT(*) FROM unknown_chunks WHERE analyzed = 1").Scan(&analyzedChunks)

	return map[string]interface{}{
		"total_patterns":    totalPatterns,
		"tested_patterns":   testedPatterns,
		"total_matches":     totalMatches,
		"unknown_chunks":    unknownChunks,
		"analyzed_chunks":   analyzedChunks,
		"unanalyzed_chunks": unknownChunks - analyzedChunks,
	}
}

// Close closes the database connection
func (pd *PatternDatabase) Close() error {
	return pd.db.Close()
}
