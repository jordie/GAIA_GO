package data

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// ExtractionStore handles database operations for extraction events
type ExtractionStore struct {
	db *sql.DB
}

// ExtractionEvent represents a single extraction event
type ExtractionEvent struct {
	ID               int64                  `json:"id"`
	AgentName        string                 `json:"agent_name"`
	SessionID        string                 `json:"session_id"`
	Timestamp        time.Time              `json:"timestamp"`
	EventType        string                 `json:"event_type"`
	Pattern          string                 `json:"pattern"`
	MatchedValue     string                 `json:"matched_value"`
	OriginalLine     string                 `json:"original_line"`
	LineNumber       int                    `json:"line_number"`
	Metadata         map[string]interface{} `json:"metadata"`
	CodeBlockLang    string                 `json:"code_block_language,omitempty"`
	RiskLevel        string                 `json:"risk_level,omitempty"`
	AutoConfirmable  bool                   `json:"auto_confirmable"`
}

// CodeBlock represents an extracted code block
type CodeBlock struct {
	ID          int64                  `json:"id"`
	AgentName   string                 `json:"agent_name"`
	SessionID   string                 `json:"session_id"`
	Timestamp   time.Time              `json:"timestamp"`
	Language    string                 `json:"language"`
	Content     string                 `json:"content"`
	LineStart   int                    `json:"line_start"`
	LineEnd     int                    `json:"line_end"`
	Context     map[string]interface{} `json:"context"`
	Parseable   bool                   `json:"parseable"`
	Digest      string                 `json:"digest"` // SHA256 hash for deduplication
}

// ExtractionStats contains aggregate statistics
type ExtractionStats struct {
	AgentName         string            `json:"agent_name"`
	TotalExtractions  int               `json:"total_extractions"`
	ExtractionsByType map[string]int    `json:"extractions_by_type"`
	ExtractionsByRisk map[string]int    `json:"extractions_by_risk"`
	FirstSeen         time.Time         `json:"first_seen"`
	LastSeen          time.Time         `json:"last_seen"`
}

// NewExtractionStore creates a new extraction store with database connection
func NewExtractionStore(dbPath string) (*ExtractionStore, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	store := &ExtractionStore{db: db}

	// Initialize schema
	if err := store.initSchema(); err != nil {
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	return store, nil
}

// initSchema creates tables if they don't exist
func (es *ExtractionStore) initSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS extraction_events (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		agent_name TEXT NOT NULL,
		session_id TEXT NOT NULL,
		timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
		event_type TEXT NOT NULL,
		pattern TEXT NOT NULL,
		matched_value TEXT,
		original_line TEXT,
		line_number INTEGER,
		metadata_json TEXT,
		code_block_language TEXT,
		risk_level TEXT,
		auto_confirmable BOOLEAN DEFAULT 0
	);

	CREATE INDEX IF NOT EXISTS idx_agent_session ON extraction_events(agent_name, session_id);
	CREATE INDEX IF NOT EXISTS idx_type_pattern ON extraction_events(event_type, pattern);
	CREATE INDEX IF NOT EXISTS idx_timestamp ON extraction_events(timestamp);
	CREATE INDEX IF NOT EXISTS idx_risk_level ON extraction_events(risk_level);

	CREATE TABLE IF NOT EXISTS code_blocks (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		agent_name TEXT NOT NULL,
		session_id TEXT NOT NULL,
		timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
		language TEXT,
		content TEXT,
		line_start INTEGER,
		line_end INTEGER,
		context_json TEXT,
		parseable BOOLEAN,
		digest TEXT UNIQUE
	);

	CREATE INDEX IF NOT EXISTS idx_agent_language ON code_blocks(agent_name, language);
	CREATE INDEX IF NOT EXISTS idx_digest ON code_blocks(digest);
	CREATE INDEX IF NOT EXISTS idx_block_timestamp ON code_blocks(timestamp);
	`

	_, err := es.db.Exec(schema)
	return err
}

// SaveExtraction saves a single extraction event to the database
func (es *ExtractionStore) SaveExtraction(event *ExtractionEvent) error {
	metadataJSON, err := json.Marshal(event.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `
		INSERT INTO extraction_events (
			agent_name, session_id, timestamp, event_type, pattern,
			matched_value, original_line, line_number, metadata_json,
			code_block_language, risk_level, auto_confirmable
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	result, err := es.db.Exec(query,
		event.AgentName,
		event.SessionID,
		event.Timestamp,
		event.EventType,
		event.Pattern,
		event.MatchedValue,
		event.OriginalLine,
		event.LineNumber,
		string(metadataJSON),
		event.CodeBlockLang,
		event.RiskLevel,
		event.AutoConfirmable,
	)
	if err != nil {
		return fmt.Errorf("failed to insert extraction: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get insert ID: %w", err)
	}

	event.ID = id
	return nil
}

// SaveExtractionBatch saves multiple extraction events in a single transaction
func (es *ExtractionStore) SaveExtractionBatch(events []*ExtractionEvent) error {
	if len(events) == 0 {
		return nil
	}

	tx, err := es.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	stmt, err := tx.Prepare(`
		INSERT INTO extraction_events (
			agent_name, session_id, timestamp, event_type, pattern,
			matched_value, original_line, line_number, metadata_json,
			code_block_language, risk_level, auto_confirmable
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare statement: %w", err)
	}
	defer stmt.Close()

	for _, event := range events {
		metadataJSON, err := json.Marshal(event.Metadata)
		if err != nil {
			return fmt.Errorf("failed to marshal metadata: %w", err)
		}

		_, err = stmt.Exec(
			event.AgentName,
			event.SessionID,
			event.Timestamp,
			event.EventType,
			event.Pattern,
			event.MatchedValue,
			event.OriginalLine,
			event.LineNumber,
			string(metadataJSON),
			event.CodeBlockLang,
			event.RiskLevel,
			event.AutoConfirmable,
		)
		if err != nil {
			return fmt.Errorf("failed to insert extraction: %w", err)
		}
	}

	return tx.Commit()
}

// GetExtractionsByAgent retrieves recent extractions for an agent
func (es *ExtractionStore) GetExtractionsByAgent(agentName string, limit int) ([]*ExtractionEvent, error) {
	query := `
		SELECT id, agent_name, session_id, timestamp, event_type, pattern,
		       matched_value, original_line, line_number, metadata_json,
		       code_block_language, risk_level, auto_confirmable
		FROM extraction_events
		WHERE agent_name = ?
		ORDER BY timestamp DESC
		LIMIT ?
	`

	rows, err := es.db.Query(query, agentName, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query extractions: %w", err)
	}
	defer rows.Close()

	return es.scanExtractions(rows)
}

// GetExtractionsByType retrieves extractions filtered by event type
func (es *ExtractionStore) GetExtractionsByType(agentName, eventType string, limit int) ([]*ExtractionEvent, error) {
	query := `
		SELECT id, agent_name, session_id, timestamp, event_type, pattern,
		       matched_value, original_line, line_number, metadata_json,
		       code_block_language, risk_level, auto_confirmable
		FROM extraction_events
		WHERE agent_name = ? AND event_type = ?
		ORDER BY timestamp DESC
		LIMIT ?
	`

	rows, err := es.db.Query(query, agentName, eventType, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query extractions: %w", err)
	}
	defer rows.Close()

	return es.scanExtractions(rows)
}

// GetExtractionsByPattern retrieves extractions filtered by pattern
func (es *ExtractionStore) GetExtractionsByPattern(agentName, pattern string, limit int) ([]*ExtractionEvent, error) {
	query := `
		SELECT id, agent_name, session_id, timestamp, event_type, pattern,
		       matched_value, original_line, line_number, metadata_json,
		       code_block_language, risk_level, auto_confirmable
		FROM extraction_events
		WHERE agent_name = ? AND pattern = ?
		ORDER BY timestamp DESC
		LIMIT ?
	`

	rows, err := es.db.Query(query, agentName, pattern, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query extractions: %w", err)
	}
	defer rows.Close()

	return es.scanExtractions(rows)
}

// GetExtractionsBySession retrieves all extractions for a specific session
func (es *ExtractionStore) GetExtractionsBySession(sessionID string) ([]*ExtractionEvent, error) {
	query := `
		SELECT id, agent_name, session_id, timestamp, event_type, pattern,
		       matched_value, original_line, line_number, metadata_json,
		       code_block_language, risk_level, auto_confirmable
		FROM extraction_events
		WHERE session_id = ?
		ORDER BY timestamp ASC
	`

	rows, err := es.db.Query(query, sessionID)
	if err != nil {
		return nil, fmt.Errorf("failed to query extractions: %w", err)
	}
	defer rows.Close()

	return es.scanExtractions(rows)
}

// GetExtractionStats returns aggregate statistics for an agent
func (es *ExtractionStore) GetExtractionStats(agentName string) (*ExtractionStats, error) {
	stats := &ExtractionStats{
		AgentName:         agentName,
		ExtractionsByType: make(map[string]int),
		ExtractionsByRisk: make(map[string]int),
	}

	// Get total count (SQLite returns timestamp as string)
	var firstSeen, lastSeen sql.NullString
	err := es.db.QueryRow(`
		SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
		FROM extraction_events
		WHERE agent_name = ?
	`, agentName).Scan(&stats.TotalExtractions, &firstSeen, &lastSeen)
	if err != nil && err != sql.ErrNoRows {
		return nil, fmt.Errorf("failed to get total count: %w", err)
	}

	// Parse timestamps
	if firstSeen.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", firstSeen.String); err == nil {
			stats.FirstSeen = t
		}
	}
	if lastSeen.Valid {
		if t, err := time.Parse("2006-01-02 15:04:05", lastSeen.String); err == nil {
			stats.LastSeen = t
		}
	}

	// Get counts by type
	rows, err := es.db.Query(`
		SELECT event_type, COUNT(*)
		FROM extraction_events
		WHERE agent_name = ?
		GROUP BY event_type
	`, agentName)
	if err != nil {
		return nil, fmt.Errorf("failed to get type counts: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var eventType string
		var count int
		if err := rows.Scan(&eventType, &count); err != nil {
			return nil, fmt.Errorf("failed to scan type count: %w", err)
		}
		stats.ExtractionsByType[eventType] = count
	}

	// Get counts by risk level
	rows, err = es.db.Query(`
		SELECT risk_level, COUNT(*)
		FROM extraction_events
		WHERE agent_name = ? AND risk_level IS NOT NULL
		GROUP BY risk_level
	`, agentName)
	if err != nil {
		return nil, fmt.Errorf("failed to get risk counts: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var riskLevel string
		var count int
		if err := rows.Scan(&riskLevel, &count); err != nil {
			return nil, fmt.Errorf("failed to scan risk count: %w", err)
		}
		stats.ExtractionsByRisk[riskLevel] = count
	}

	return stats, nil
}

// SaveCodeBlock saves a code block to the database
func (es *ExtractionStore) SaveCodeBlock(block *CodeBlock) error {
	contextJSON, err := json.Marshal(block.Context)
	if err != nil {
		return fmt.Errorf("failed to marshal context: %w", err)
	}

	query := `
		INSERT OR IGNORE INTO code_blocks (
			agent_name, session_id, timestamp, language, content,
			line_start, line_end, context_json, parseable, digest
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	result, err := es.db.Exec(query,
		block.AgentName,
		block.SessionID,
		block.Timestamp,
		block.Language,
		block.Content,
		block.LineStart,
		block.LineEnd,
		string(contextJSON),
		block.Parseable,
		block.Digest,
	)
	if err != nil {
		return fmt.Errorf("failed to insert code block: %w", err)
	}

	id, err := result.LastInsertId()
	if err == nil {
		block.ID = id
	}

	return nil
}

// GetCodeBlocks retrieves code blocks filtered by agent and language
func (es *ExtractionStore) GetCodeBlocks(agentName, language string, limit int) ([]*CodeBlock, error) {
	var query string
	var rows *sql.Rows
	var err error

	if language != "" {
		query = `
			SELECT id, agent_name, session_id, timestamp, language, content,
			       line_start, line_end, context_json, parseable, digest
			FROM code_blocks
			WHERE agent_name = ? AND language = ?
			ORDER BY timestamp DESC
			LIMIT ?
		`
		rows, err = es.db.Query(query, agentName, language, limit)
	} else {
		query = `
			SELECT id, agent_name, session_id, timestamp, language, content,
			       line_start, line_end, context_json, parseable, digest
			FROM code_blocks
			WHERE agent_name = ?
			ORDER BY timestamp DESC
			LIMIT ?
		`
		rows, err = es.db.Query(query, agentName, limit)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to query code blocks: %w", err)
	}
	defer rows.Close()

	var blocks []*CodeBlock
	for rows.Next() {
		var block CodeBlock
		var contextJSON string

		err := rows.Scan(
			&block.ID,
			&block.AgentName,
			&block.SessionID,
			&block.Timestamp,
			&block.Language,
			&block.Content,
			&block.LineStart,
			&block.LineEnd,
			&contextJSON,
			&block.Parseable,
			&block.Digest,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan code block: %w", err)
		}

		if err := json.Unmarshal([]byte(contextJSON), &block.Context); err != nil {
			return nil, fmt.Errorf("failed to unmarshal context: %w", err)
		}

		blocks = append(blocks, &block)
	}

	return blocks, rows.Err()
}

// Close closes the database connection
func (es *ExtractionStore) Close() error {
	if es.db != nil {
		return es.db.Close()
	}
	return nil
}

// GetDB returns the database connection for advanced queries
func (es *ExtractionStore) GetDB() *sql.DB {
	return es.db
}

// Helper function to scan extraction rows
func (es *ExtractionStore) scanExtractions(rows *sql.Rows) ([]*ExtractionEvent, error) {
	var extractions []*ExtractionEvent

	for rows.Next() {
		var event ExtractionEvent
		var metadataJSON sql.NullString
		var codeBlockLang sql.NullString
		var riskLevel sql.NullString

		err := rows.Scan(
			&event.ID,
			&event.AgentName,
			&event.SessionID,
			&event.Timestamp,
			&event.EventType,
			&event.Pattern,
			&event.MatchedValue,
			&event.OriginalLine,
			&event.LineNumber,
			&metadataJSON,
			&codeBlockLang,
			&riskLevel,
			&event.AutoConfirmable,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan extraction: %w", err)
		}

		// Parse metadata JSON
		if metadataJSON.Valid {
			if err := json.Unmarshal([]byte(metadataJSON.String), &event.Metadata); err != nil {
				return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}
		}

		if codeBlockLang.Valid {
			event.CodeBlockLang = codeBlockLang.String
		}

		if riskLevel.Valid {
			event.RiskLevel = riskLevel.String
		}

		extractions = append(extractions, &event)
	}

	return extractions, rows.Err()
}
