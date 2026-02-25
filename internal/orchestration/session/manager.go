package session

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// Manager handles GAIA session lifecycle management (separate from user authentication sessions)
// Uses dual-layer caching: in-memory + database
type Manager struct {
	db           *sql.DB
	tmuxClient   *TmuxClient
	sessions     map[string]*Session
	sessionMutex sync.RWMutex
	closeOnce    sync.Once
	closeChan    chan struct{}

	// Session settings
	maxSessions              int
	sessionCleanupInterval   time.Duration
	inactiveSessionThreshold time.Duration
}

// NewManager creates a new session manager
func NewManager(db *sql.DB, maxSessions int) (*Manager, error) {
	tmuxClient, err := NewTmuxClient()
	if err != nil {
		return nil, fmt.Errorf("failed to initialize tmux client: %w", err)
	}

	m := &Manager{
		db:                       db,
		tmuxClient:               tmuxClient,
		sessions:                 make(map[string]*Session),
		maxSessions:              maxSessions,
		sessionCleanupInterval:   1 * time.Hour,
		inactiveSessionThreshold: 24 * time.Hour,
		closeChan:                make(chan struct{}),
	}

	// Start cleanup goroutine
	go m.cleanupWorker()

	// Restore sessions from database on startup
	if err := m.restoreSessions(context.Background()); err != nil {
		// Log but don't fail - not critical to startup
		fmt.Printf("warning: failed to restore sessions from database: %v\n", err)
	}

	return m, nil
}

// CreateSession creates a new GAIA session with optional initial windows
func (m *Manager) CreateSession(ctx context.Context, config SessionConfig) (*Session, error) {
	m.sessionMutex.Lock()
	defer m.sessionMutex.Unlock()

	// Check session limit
	if len(m.sessions) >= m.maxSessions {
		return nil, fmt.Errorf("session limit reached (%d)", m.maxSessions)
	}

	// Generate session ID
	sessionID := uuid.New().String()

	// Create tmux session
	_, err := m.tmuxClient.NewSession(ctx, sessionID, config.ProjectPath)
	if err != nil {
		return nil, fmt.Errorf("failed to create tmux session: %w", err)
	}

	// Create session object
	now := time.Now()
	session := &Session{
		ID:          sessionID,
		Name:        config.Name,
		ProjectPath: config.ProjectPath,
		Status:      SessionStatusActive,
		Windows:     make(map[string]*Window),
		CreatedAt:   now,
		LastActive:  now,
		Metadata:    config.Metadata,
		Tags:        config.Tags,
	}

	// Persist to database
	if err := m.persistSession(session); err != nil {
		// Cleanup tmux session on database error
		_ = m.tmuxClient.KillSession(ctx, sessionID)
		return nil, fmt.Errorf("failed to persist session: %w", err)
	}

	// Add to in-memory cache
	m.sessions[sessionID] = session

	return session, nil
}

// GetSession retrieves a session by ID with in-memory cache lookup
func (m *Manager) GetSession(sessionID string) (*Session, error) {
	m.sessionMutex.RLock()
	session, exists := m.sessions[sessionID]
	m.sessionMutex.RUnlock()

	if !exists {
		// Fallback to database lookup
		var dbSession *Session
		var metadataJSON, tagsJSON string

		err := m.db.QueryRow(
			"SELECT id, name, project_path, status, metadata, tags, created_at, last_active FROM gaia_sessions WHERE id = ?",
			sessionID,
		).Scan(&dbSession.ID, &dbSession.Name, &dbSession.ProjectPath, &dbSession.Status, &metadataJSON, &tagsJSON, &dbSession.CreatedAt, &dbSession.LastActive)

		if err != nil {
			if err == sql.ErrNoRows {
				return nil, fmt.Errorf("session not found: %s", sessionID)
			}
			return nil, fmt.Errorf("failed to query session: %w", err)
		}

		// Deserialize metadata and tags
		if metadataJSON != "" {
			_ = json.Unmarshal([]byte(metadataJSON), &dbSession.Metadata)
		}
		if tagsJSON != "" {
			_ = json.Unmarshal([]byte(tagsJSON), &dbSession.Tags)
		}

		dbSession.Windows = make(map[string]*Window)

		// Cache in memory
		m.sessionMutex.Lock()
		m.sessions[sessionID] = dbSession
		m.sessionMutex.Unlock()

		return dbSession, nil
	}

	return session, nil
}

// ListSessions returns all active sessions
func (m *Manager) ListSessions() ([]*Session, error) {
	m.sessionMutex.RLock()
	sessions := make([]*Session, 0, len(m.sessions))
	for _, s := range m.sessions {
		if s.Status == SessionStatusActive {
			sessions = append(sessions, s)
		}
	}
	m.sessionMutex.RUnlock()

	return sessions, nil
}

// DestroySession terminates a session and removes it from tracking
func (m *Manager) DestroySession(ctx context.Context, sessionID string) error {
	m.sessionMutex.Lock()
	session, exists := m.sessions[sessionID]
	if !exists {
		m.sessionMutex.Unlock()
		return fmt.Errorf("session not found: %s", sessionID)
	}
	delete(m.sessions, sessionID)
	m.sessionMutex.Unlock()

	// Kill tmux session
	if err := m.tmuxClient.KillSession(ctx, sessionID); err != nil {
		return fmt.Errorf("failed to kill tmux session: %w", err)
	}

	// Mark as stopped in database
	session.Status = SessionStatusStopped
	if err := m.persistSession(session); err != nil {
		return fmt.Errorf("failed to update session status: %w", err)
	}

	return nil
}

// CreateWindow adds a new window to a session
func (m *Manager) CreateWindow(ctx context.Context, sessionID string, config WindowConfig) (*Window, error) {
	m.sessionMutex.RLock()
	session, exists := m.sessions[sessionID]
	m.sessionMutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("session not found: %s", sessionID)
	}

	// Create tmux window
	windowIndex, err := m.tmuxClient.NewWindow(ctx, sessionID, config.Name)
	if err != nil {
		return nil, fmt.Errorf("failed to create tmux window: %w", err)
	}

	// Create window object
	windowID := uuid.New().String()
	window := &Window{
		ID:        windowID,
		SessionID: sessionID,
		Name:      config.Name,
		Index:     parseWindowIndex(windowIndex),
		Panes:     make(map[string]*Pane),
		CreatedAt: time.Now(),
	}

	// Persist window
	if err := m.persistWindow(window); err != nil {
		return nil, fmt.Errorf("failed to persist window: %w", err)
	}

	// Add to session's window map
	m.sessionMutex.Lock()
	session.Windows[windowID] = window
	m.sessionMutex.Unlock()

	// Update last activity
	m.updateLastActivity(sessionID)

	return window, nil
}

// CreatePane adds a new pane to a window
func (m *Manager) CreatePane(ctx context.Context, sessionID, windowID string, config PaneConfig) (*Pane, error) {
	m.sessionMutex.RLock()
	session, exists := m.sessions[sessionID]
	m.sessionMutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("session not found: %s", sessionID)
	}

	window, exists := session.Windows[windowID]
	if !exists {
		return nil, fmt.Errorf("window not found: %s", windowID)
	}

	// Create tmux pane via split
	target := fmt.Sprintf("%s:%d", sessionID, window.Index)
	_, err := m.tmuxClient.SplitPane(ctx, target, config.Vertical)
	if err != nil {
		return nil, fmt.Errorf("failed to split pane: %w", err)
	}

	// Create pane object
	paneID := uuid.New().String()
	pane := &Pane{
		ID:        paneID,
		WindowID:  windowID,
		SessionID: sessionID,
		Index:     len(window.Panes),
		Command:   config.Command,
		WorkDir:   config.WorkDir,
		CreatedAt: time.Now(),
	}

	// Persist pane
	if err := m.persistPane(pane); err != nil {
		return nil, fmt.Errorf("failed to persist pane: %w", err)
	}

	// Add to window's pane map
	m.sessionMutex.Lock()
	window.Panes[paneID] = pane
	m.sessionMutex.Unlock()

	// Send initial command if provided
	if config.Command != "" {
		target = fmt.Sprintf("%s:%d.%d", sessionID, window.Index, pane.Index)
		if err := m.tmuxClient.SendKeys(ctx, target, config.Command, true); err != nil {
			return nil, fmt.Errorf("failed to send initial command: %w", err)
		}
	}

	// Update last activity
	m.updateLastActivity(sessionID)

	return pane, nil
}

// SendKeys sends commands to a pane
func (m *Manager) SendKeys(ctx context.Context, sessionID, windowID, paneID string, keys string, sendEnter bool) error {
	session, err := m.GetSession(sessionID)
	if err != nil {
		return err
	}

	window, exists := session.Windows[windowID]
	if !exists {
		return fmt.Errorf("window not found: %s", windowID)
	}

	pane, exists := window.Panes[paneID]
	if !exists {
		return fmt.Errorf("pane not found: %s", paneID)
	}

	// Build tmux target string: session:window.pane
	target := fmt.Sprintf("%s:%d.%d", sessionID, window.Index, pane.Index)

	if err := m.tmuxClient.SendKeys(ctx, target, keys, sendEnter); err != nil {
		return fmt.Errorf("failed to send keys: %w", err)
	}

	// Update last activity
	m.updateLastActivity(sessionID)

	return nil
}

// CapturePane reads the current contents of a pane
func (m *Manager) CapturePane(ctx context.Context, sessionID, windowID, paneID string) (string, error) {
	session, err := m.GetSession(sessionID)
	if err != nil {
		return "", err
	}

	window, exists := session.Windows[windowID]
	if !exists {
		return "", fmt.Errorf("window not found: %s", windowID)
	}

	pane, exists := window.Panes[paneID]
	if !exists {
		return "", fmt.Errorf("pane not found: %s", paneID)
	}

	// Build tmux target string
	target := fmt.Sprintf("%s:%d.%d", sessionID, window.Index, pane.Index)

	output, err := m.tmuxClient.CapturePane(ctx, target)
	if err != nil {
		return "", fmt.Errorf("failed to capture pane: %w", err)
	}

	// Update last activity
	m.updateLastActivity(sessionID)

	return output, nil
}

// Close gracefully shuts down the session manager
func (m *Manager) Close() error {
	var err error
	m.closeOnce.Do(func() {
		close(m.closeChan)

		// Kill all active sessions
		m.sessionMutex.Lock()
		sessions := make([]*Session, 0, len(m.sessions))
		for _, s := range m.sessions {
			if s.Status == SessionStatusActive {
				sessions = append(sessions, s)
			}
		}
		m.sessionMutex.Unlock()

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		for _, session := range sessions {
			_ = m.DestroySession(ctx, session.ID)
		}
	})

	return err
}

// Helper methods

func (m *Manager) persistSession(session *Session) error {
	metadataJSON, _ := json.Marshal(session.Metadata)
	tagsJSON, _ := json.Marshal(session.Tags)

	_, err := m.db.Exec(
		"INSERT OR REPLACE INTO gaia_sessions (id, name, project_path, status, metadata, tags, created_at, last_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
		session.ID, session.Name, session.ProjectPath, session.Status, string(metadataJSON), string(tagsJSON), session.CreatedAt, session.LastActive,
	)
	return err
}

func (m *Manager) persistWindow(window *Window) error {
	_, err := m.db.Exec(
		"INSERT OR REPLACE INTO gaia_session_windows (id, session_id, name, window_index, active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
		window.ID, window.SessionID, window.Name, window.Index, window.Active, window.CreatedAt,
	)
	return err
}

func (m *Manager) persistPane(pane *Pane) error {
	_, err := m.db.Exec(
		"INSERT OR REPLACE INTO gaia_session_panes (id, window_id, session_id, pane_index, command, work_dir, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
		pane.ID, pane.WindowID, pane.SessionID, pane.Index, pane.Command, pane.WorkDir, pane.Active, pane.CreatedAt,
	)
	return err
}

func (m *Manager) updateLastActivity(sessionID string) {
	m.sessionMutex.Lock()
	session, exists := m.sessions[sessionID]
	m.sessionMutex.Unlock()

	if exists {
		session.LastActive = time.Now()
		_ = m.persistSession(session)
	}
}

func (m *Manager) restoreSessions(ctx context.Context) error {
	rows, err := m.db.QueryContext(ctx, "SELECT id, name, project_path, status, metadata, tags, created_at, last_active FROM gaia_sessions WHERE status = 'active'")
	if err != nil {
		return err
	}
	defer rows.Close()

	m.sessionMutex.Lock()
	defer m.sessionMutex.Unlock()

	for rows.Next() {
		var session Session
		var metadataJSON, tagsJSON string

		if err := rows.Scan(&session.ID, &session.Name, &session.ProjectPath, &session.Status, &metadataJSON, &tagsJSON, &session.CreatedAt, &session.LastActive); err != nil {
			continue
		}

		if metadataJSON != "" {
			_ = json.Unmarshal([]byte(metadataJSON), &session.Metadata)
		}
		if tagsJSON != "" {
			_ = json.Unmarshal([]byte(tagsJSON), &session.Tags)
		}

		session.Windows = make(map[string]*Window)
		m.sessions[session.ID] = &session
	}

	return rows.Err()
}

func (m *Manager) cleanupWorker() {
	ticker := time.NewTicker(m.sessionCleanupInterval)
	defer ticker.Stop()

	for {
		select {
		case <-m.closeChan:
			return
		case <-ticker.C:
			m.cleanupInactiveSessions()
		}
	}
}

func (m *Manager) cleanupInactiveSessions() {
	m.sessionMutex.Lock()
	sessionsToCleanup := []string{}
	now := time.Now()

	for sessionID, session := range m.sessions {
		if session.Status == SessionStatusActive && now.Sub(session.LastActive) > m.inactiveSessionThreshold {
			sessionsToCleanup = append(sessionsToCleanup, sessionID)
		}
	}
	m.sessionMutex.Unlock()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	for _, sessionID := range sessionsToCleanup {
		_ = m.DestroySession(ctx, sessionID)
	}
}

// parseWindowIndex converts window index string to int
func parseWindowIndex(indexStr string) int {
	var index int
	fmt.Sscanf(indexStr, "%d", &index)
	return index
}
