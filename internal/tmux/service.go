package tmux

import (
	"bytes"
	"context"
	"database/sql"
	"fmt"
	"log"
	"os/exec"
	"strings"
	"sync"
)

// Service manages tmux session grouping
type Service struct {
	db    *sql.DB
	mutex sync.RWMutex
}

// NewService creates a new tmux service
func NewService(db *sql.DB) *Service {
	return &Service{
		db: db,
	}
}

// GetSessionsGrouped returns all tmux sessions grouped by project, environment, and type
func (s *Service) GetSessionsGrouped(ctx context.Context) (*GroupedSessions, error) {
	s.mutex.RLock()
	defer s.mutex.RUnlock()

	// Sync tmux sessions with database
	if err := s.syncTmuxSessions(ctx); err != nil {
		log.Printf("[WARN] Failed to sync tmux sessions: %v", err)
		// Continue anyway - we can still return cached data
	}

	// Fetch all sessions from database
	sessions, err := s.getAllSessions(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get sessions: %w", err)
	}

	// Fetch all projects
	projects, err := s.getProjects(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get projects: %w", err)
	}

	// Group sessions
	grouped := s.groupSessions(sessions, projects)

	return grouped, nil
}

// syncTmuxSessions synchronizes tmux list-sessions with database
func (s *Service) syncTmuxSessions(ctx context.Context) error {
	// Get list of tmux sessions
	tmuxSessions, err := s.listTmuxSessions(ctx)
	if err != nil {
		// Gracefully handle if tmux server is not running
		log.Printf("[WARN] Failed to list tmux sessions: %v", err)
		return nil
	}

	// Create map of current sessions in tmux
	tmuxMap := make(map[string]bool)
	for _, session := range tmuxSessions {
		tmuxMap[session] = true

		// Upsert session into database
		_, err := s.db.ExecContext(ctx,
			`INSERT OR REPLACE INTO tmux_sessions (id, name, last_active)
			 VALUES (?, ?, CURRENT_TIMESTAMP)`,
			session, session)
		if err != nil {
			log.Printf("[WARN] Failed to upsert session %s: %v", session, err)
		}
	}

	// Mark sessions as inactive if they no longer exist in tmux
	rows, err := s.db.QueryContext(ctx, "SELECT id FROM tmux_sessions")
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var sessionID string
		if err := rows.Scan(&sessionID); err != nil {
			log.Printf("[WARN] Failed to scan session: %v", err)
			continue
		}

		if !tmuxMap[sessionID] {
			// Session no longer exists in tmux, keep record for history
			_, err := s.db.ExecContext(ctx,
				`UPDATE tmux_sessions SET attached = 0 WHERE id = ?`,
				sessionID)
			if err != nil {
				log.Printf("[WARN] Failed to mark session as detached: %v", err)
			}
		} else {
			// Session exists, mark as attached
			_, err := s.db.ExecContext(ctx,
				`UPDATE tmux_sessions SET attached = 1 WHERE id = ?`,
				sessionID)
			if err != nil {
				log.Printf("[WARN] Failed to mark session as attached: %v", err)
			}
		}
	}

	return rows.Err()
}

// listTmuxSessions returns list of tmux session names
func (s *Service) listTmuxSessions(ctx context.Context) ([]string, error) {
	cmd := exec.CommandContext(ctx, "tmux", "list-sessions", "-F", "#{session_name}")
	var out bytes.Buffer
	cmd.Stdout = &out

	if err := cmd.Run(); err != nil {
		// If tmux is not running, return empty list
		return []string{}, nil
	}

	sessions := strings.Fields(out.String())
	return sessions, nil
}

// groupSessions groups sessions by project, environment, and type
func (s *Service) groupSessions(sessions []TmuxSession, projects []Project) *GroupedSessions {
	grouped := &GroupedSessions{
		Groups: make([]SessionGroup, 0),
	}

	// Create project groups
	projectMap := make(map[int]*Project)
	for i := range projects {
		projectMap[projects[i].ID] = &projects[i]
	}

	// Group sessions by project
	projectGroups := make(map[int][]TmuxSession)
	unassigned := make([]TmuxSession, 0)

	for _, session := range sessions {
		grouped.TotalSessions++
		if session.Attached {
			grouped.TotalAttached++
		}

		if session.ProjectID != nil {
			projectGroups[*session.ProjectID] = append(projectGroups[*session.ProjectID], session)
		} else {
			unassigned = append(unassigned, session)
		}
	}

	// Create groups for each project that has sessions
	for _, project := range projects {
		sessions := projectGroups[project.ID]
		if len(sessions) > 0 {
			group := SessionGroup{
				ID:        fmt.Sprintf("project_%d", project.ID),
				Name:      project.Name,
				Icon:      project.Icon,
				Sessions:  sessions,
				Collapsed: false,
			}
			group.TotalCount = len(sessions)
			for _, s := range sessions {
				if s.Attached {
					group.AttachedCount++
				}
			}
			grouped.Groups = append(grouped.Groups, group)
		}
	}

	// Add unassigned sessions group if any
	if len(unassigned) > 0 {
		grouped.UnassignedCount = len(unassigned)
		group := SessionGroup{
			ID:       "unassigned",
			Name:     "Unassigned Sessions",
			Icon:     "⚙️",
			Sessions: unassigned,
			Collapsed: false,
		}
		group.TotalCount = len(unassigned)
		for _, s := range unassigned {
			if s.Attached {
				group.AttachedCount++
			}
		}
		grouped.Groups = append(grouped.Groups, group)
	}

	return grouped
}

// getAllSessions retrieves all sessions from database
func (s *Service) getAllSessions(ctx context.Context) ([]TmuxSession, error) {
	rows, err := s.db.QueryContext(ctx,
		`SELECT id, name, project_id, environment, is_worker, attached, created_at, last_active
		 FROM tmux_sessions WHERE attached = 1`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	sessions := make([]TmuxSession, 0)
	for rows.Next() {
		var session TmuxSession
		if err := rows.Scan(&session.ID, &session.Name, &session.ProjectID, &session.Environment,
			&session.IsWorker, &session.Attached, &session.CreatedAt, &session.LastActive); err != nil {
			log.Printf("[WARN] Failed to scan session: %v", err)
			continue
		}
		sessions = append(sessions, session)
	}

	return sessions, rows.Err()
}

// getProjects retrieves all projects from database
func (s *Service) getProjects(ctx context.Context) ([]Project, error) {
	rows, err := s.db.QueryContext(ctx,
		`SELECT id, slug, name, icon, display_order, created_at
		 FROM projects ORDER BY display_order`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	projects := make([]Project, 0)
	for rows.Next() {
		var project Project
		if err := rows.Scan(&project.ID, &project.Slug, &project.Name, &project.Icon,
			&project.DisplayOrder, &project.CreatedAt); err != nil {
			log.Printf("[WARN] Failed to scan project: %v", err)
			continue
		}
		projects = append(projects, project)
	}

	return projects, rows.Err()
}

// AssignSessionToProject assigns a session to a project
func (s *Service) AssignSessionToProject(ctx context.Context, sessionName string, projectID int) error {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	_, err := s.db.ExecContext(ctx,
		`UPDATE tmux_sessions SET project_id = ? WHERE name = ?`,
		projectID, sessionName)
	return err
}

// SetSessionEnvironment sets the environment for a session
func (s *Service) SetSessionEnvironment(ctx context.Context, sessionName string, environment string) error {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	// Validate environment
	validEnvs := map[string]bool{"dev": true, "staging": true, "prod": true}
	if !validEnvs[environment] {
		return fmt.Errorf("invalid environment: %s", environment)
	}

	_, err := s.db.ExecContext(ctx,
		`UPDATE tmux_sessions SET environment = ? WHERE name = ?`,
		environment, sessionName)
	return err
}

// SetSessionWorker marks a session as a worker or not
func (s *Service) SetSessionWorker(ctx context.Context, sessionName string, isWorker bool) error {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	_, err := s.db.ExecContext(ctx,
		`UPDATE tmux_sessions SET is_worker = ? WHERE name = ?`,
		isWorker, sessionName)
	return err
}

// ToggleGroupCollapsed toggles the collapsed state of a group
func (s *Service) ToggleGroupCollapsed(ctx context.Context, userID int, groupID string) (bool, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	// Get current state
	var collapsed bool
	err := s.db.QueryRowContext(ctx,
		`SELECT collapsed FROM session_group_prefs WHERE user_id = ? AND group_id = ?`,
		userID, groupID).Scan(&collapsed)

	if err == sql.ErrNoRows {
		// Preference doesn't exist, create it with collapsed=true
		_, err := s.db.ExecContext(ctx,
			`INSERT INTO session_group_prefs (user_id, group_id, collapsed, created_at, updated_at)
			 VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)`,
			userID, groupID)
		return true, err
	}

	if err != nil {
		return collapsed, err
	}

	// Toggle state
	newState := !collapsed
	_, err = s.db.ExecContext(ctx,
		`UPDATE session_group_prefs SET collapsed = ?, updated_at = CURRENT_TIMESTAMP
		 WHERE user_id = ? AND group_id = ?`,
		newState, userID, groupID)

	return newState, err
}

// GetGroupPreferences returns all group preferences for a user
func (s *Service) GetGroupPreferences(ctx context.Context, userID int) (map[string]bool, error) {
	s.mutex.RLock()
	defer s.mutex.RUnlock()

	rows, err := s.db.QueryContext(ctx,
		`SELECT group_id, collapsed FROM session_group_prefs WHERE user_id = ?`,
		userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	prefs := make(map[string]bool)
	for rows.Next() {
		var groupID string
		var collapsed bool
		if err := rows.Scan(&groupID, &collapsed); err != nil {
			log.Printf("[WARN] Failed to scan preference: %v", err)
			continue
		}
		prefs[groupID] = collapsed
	}

	return prefs, rows.Err()
}

// AutoAssignSessions performs pattern-based auto-assignment of sessions
func (s *Service) AutoAssignSessions(ctx context.Context) (*AutoAssignResult, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	result := &AutoAssignResult{Success: true}

	// Get all unassigned sessions
	rows, err := s.db.QueryContext(ctx,
		`SELECT id, name FROM tmux_sessions WHERE project_id IS NULL`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	// Project slug mapping
	projectMap := make(map[string]int)
	projects, err := s.getProjects(ctx)
	if err != nil {
		return nil, err
	}

	for _, p := range projects {
		projectMap[p.Slug] = p.ID
	}

	assigned := 0
	for rows.Next() {
		var sessionID, sessionName string
		if err := rows.Scan(&sessionID, &sessionName); err != nil {
			log.Printf("[WARN] Failed to scan session: %v", err)
			continue
		}

		projectID, environment, isWorker := s.autoAssignLogic(sessionName, projectMap)

		// Update session with assignments
		_, err := s.db.ExecContext(ctx,
			`UPDATE tmux_sessions SET project_id = ?, environment = ?, is_worker = ? WHERE id = ?`,
			projectID, environment, isWorker, sessionID)
		if err != nil {
			log.Printf("[WARN] Failed to auto-assign session %s: %v", sessionName, err)
		} else {
			assigned++
		}
	}

	result.Assigned = assigned
	result.Message = fmt.Sprintf("Successfully auto-assigned %d sessions", assigned)
	return result, rows.Err()
}

// autoAssignLogic determines project assignment and flags based on session name
func (s *Service) autoAssignLogic(sessionName string, projectMap map[string]int) (*int, string, bool) {
	lower := strings.ToLower(sessionName)

	// Priority 1: Worker detection
	if strings.Contains(lower, "worker") || strings.Contains(lower, "queue") || strings.Contains(lower, "daemon") {
		env := s.extractEnvironment(lower)
		return nil, env, true
	}

	// Priority 2: Project slug matching
	for slug, projectID := range projectMap {
		if strings.HasPrefix(lower, slug) {
			env := s.extractEnvironment(lower)
			return &projectID, env, false
		}
	}

	// No match found
	env := s.extractEnvironment(lower)
	return nil, env, false
}

// extractEnvironment extracts environment from session name
func (s *Service) extractEnvironment(sessionName string) string {
	if strings.HasSuffix(sessionName, "_prod") {
		return "prod"
	}
	if strings.HasSuffix(sessionName, "_staging") {
		return "staging"
	}
	return "dev"
}

// GetProjects returns all projects
func (s *Service) GetProjects(ctx context.Context) ([]Project, error) {
	s.mutex.RLock()
	defer s.mutex.RUnlock()

	return s.getProjects(ctx)
}

// SetCollapsedBulk sets collapsed state for multiple groups
func (s *Service) SetCollapsedBulk(ctx context.Context, userID int, groupIDs []string, collapsed bool) error {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	for _, groupID := range groupIDs {
		_, err := s.db.ExecContext(ctx,
			`INSERT INTO session_group_prefs (user_id, group_id, collapsed, created_at, updated_at)
			 VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
			 ON CONFLICT(user_id, group_id) DO UPDATE SET collapsed = ?, updated_at = CURRENT_TIMESTAMP`,
			userID, groupID, collapsed, collapsed)
		if err != nil {
			return err
		}
	}

	return nil
}
