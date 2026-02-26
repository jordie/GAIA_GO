package migration

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jgirmay/GAIA_GO/pkg/models"
)

// SessionMigrator handles migration of sessions from GAIA_HOME to GAIA_GO
type SessionMigrator struct {
	mu sync.RWMutex

	// Source (GAIA_HOME Python)
	pythonClient PythonSessionClient

	// Destination (GAIA_GO)
	goRepository GoSessionRepository

	// Migration state
	metrics        *MigrationMetrics
	migrationState MigrationPhase
	startTime      time.Time
	trafficPercent int // Percentage of traffic to route to GAIA_GO

	// Validators
	validators []SessionValidator

	// Observers for status updates
	observers map[string]MigrationObserver
}

// MigrationPhase represents the current migration phase
type MigrationPhase string

const (
	PhasePreparing      MigrationPhase = "preparing"      // Initial setup
	PhaseValidating     MigrationPhase = "validating"     // Data validation
	PhaseDualWrite      MigrationPhase = "dual_write"     // Both systems synchronized
	PhaseGradualRollout MigrationPhase = "gradual_rollout" // 10% → 50% → 100%
	PhaseMonitoring     MigrationPhase = "monitoring"     // Post-migration monitoring
	PhaseCompleted      MigrationPhase = "completed"      // Migration finished
)

// MigrationMetrics tracks migration progress
type MigrationMetrics struct {
	TotalSessions      int64
	MigratedSessions   int64
	FailedMigrations   int64
	ValidatedSessions  int64
	DualWriteErrors    int64
	StartTime          time.Time
	LastUpdateTime     time.Time
	EstimatedDuration  time.Duration
	EstimatedComplete  time.Time
}

// MigrationObserver receives migration status updates
type MigrationObserver interface {
	OnPhaseChange(phase MigrationPhase)
	OnProgressUpdate(metrics *MigrationMetrics)
	OnError(sessionID string, err error)
	OnValidationFailed(sessionID string, reason string)
}

// SessionValidator validates session data integrity
type SessionValidator interface {
	ValidateSession(ctx context.Context, session *models.ClaudeSession) (bool, []string)
}

// PythonSessionClient represents a GAIA_HOME Python client
type PythonSessionClient interface {
	GetSession(ctx context.Context, sessionID string) (*PythonSession, error)
	ListSessions(ctx context.Context, filters map[string]string) ([]*PythonSession, error)
	UpdateSessionStatus(ctx context.Context, sessionID string, status string) error
}

// GoSessionRepository represents a GAIA_GO session repository
type GoSessionRepository interface {
	Create(ctx context.Context, session *models.ClaudeSession) (*models.ClaudeSession, error)
	Update(ctx context.Context, session *models.ClaudeSession) (*models.ClaudeSession, error)
	GetByID(ctx context.Context, id string) (*models.ClaudeSession, error)
}

// PythonSession represents a session from GAIA_HOME
type PythonSession struct {
	ID                string
	UserID            string
	SessionName       string
	Tier              string
	Provider          string
	Status            string
	LessonID          string
	TimeWindowStart   time.Time
	TimeWindowEnd     time.Time
	LastHeartbeat     time.Time
	HealthStatus      string
	MaxConcurrentTasks int
	CurrentTaskCount  int
	Metadata          map[string]interface{}
	CreatedAt         time.Time
	UpdatedAt         time.Time
}

// NewSessionMigrator creates a new session migrator
func NewSessionMigrator(pythonClient PythonSessionClient, goRepository GoSessionRepository) *SessionMigrator {
	return &SessionMigrator{
		pythonClient:   pythonClient,
		goRepository:   goRepository,
		metrics:        &MigrationMetrics{},
		migrationState: PhasePreparing,
		observers:      make(map[string]MigrationObserver),
		validators:     make([]SessionValidator, 0),
	}
}

// RegisterValidator adds a validator to the migration process
func (sm *SessionMigrator) RegisterValidator(validator SessionValidator) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.validators = append(sm.validators, validator)
}

// RegisterObserver registers a migration observer
func (sm *SessionMigrator) RegisterObserver(name string, observer MigrationObserver) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.observers[name] = observer
}

// Start initiates the migration process
func (sm *SessionMigrator) Start(ctx context.Context) error {
	sm.mu.Lock()
	sm.migrationState = PhaseValidating
	sm.startTime = time.Now()
	sm.notifyPhaseChange(PhaseValidating)
	sm.mu.Unlock()

	// Phase 1: Validate all sessions
	sessions, err := sm.pythonClient.ListSessions(ctx, map[string]string{"status": "active"})
	if err != nil {
		return fmt.Errorf("failed to list sessions: %w", err)
	}

	sm.metrics.TotalSessions = int64(len(sessions))

	// Phase 2: Begin migration with validation
	return sm.migrateSessionsBatch(ctx, sessions)
}

// migrateSessionsBatch migrates a batch of sessions
func (sm *SessionMigrator) migrateSessionsBatch(ctx context.Context, sessions []*PythonSession) error {
	sm.mu.Lock()
	sm.migrationState = PhaseDualWrite
	sm.notifyPhaseChange(PhaseDualWrite)
	sm.mu.Unlock()

	var wg sync.WaitGroup
	semaphore := make(chan struct{}, 10) // Max 10 concurrent migrations

	for _, pythonSession := range sessions {
		wg.Add(1)

		go func(ps *PythonSession) {
			defer wg.Done()

			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Convert and migrate session
			goSession := sm.convertPythonSessionToGo(ps)

			// Create in GAIA_GO
			createdSession, err := sm.goRepository.Create(ctx, goSession)
			if err != nil {
				atomic.AddInt64(&sm.metrics.FailedMigrations, 1)
				sm.notifyError(ps.ID, fmt.Errorf("failed to create: %w", err))
				return
			}

			// Validate the migrated session
			isValid := true
			var validationErrors []string
			for _, validator := range sm.validators {
				valid, errs := validator.ValidateSession(ctx, createdSession)
				if !valid {
					isValid = false
					validationErrors = append(validationErrors, errs...)
				}
			}

			if !isValid {
				atomic.AddInt64(&sm.metrics.FailedMigrations, 1)
				for _, errMsg := range validationErrors {
					sm.notifyValidationFailed(ps.ID, errMsg)
				}
				return
			}

			atomic.AddInt64(&sm.metrics.MigratedSessions, 1)
			atomic.AddInt64(&sm.metrics.ValidatedSessions, 1)
			sm.notifyProgress()
		}(pythonSession)
	}

	wg.Wait()

	// Check if migration was successful
	if sm.metrics.FailedMigrations > 0 {
		return fmt.Errorf("migration had %d failures out of %d sessions",
			sm.metrics.FailedMigrations, sm.metrics.TotalSessions)
	}

	sm.mu.Lock()
	sm.migrationState = PhaseGradualRollout
	sm.notifyPhaseChange(PhaseGradualRollout)
	sm.mu.Unlock()

	return nil
}

// convertPythonSessionToGo converts a Python session to Go model
func (sm *SessionMigrator) convertPythonSessionToGo(ps *PythonSession) *models.ClaudeSession {
	// Map Python session to Go model
	goSession := &models.ClaudeSession{
		SessionName:       ps.SessionName,
		UserID:            ps.UserID,
		Tier:              ps.Tier,
		Provider:          ps.Provider,
		Status:            ps.Status,
		LessonID:          ps.LessonID,
		TimeWindowStart:   ps.TimeWindowStart,
		TimeWindowEnd:     ps.TimeWindowEnd,
		LastHeartbeat:     ps.LastHeartbeat,
		HealthStatus:      ps.HealthStatus,
		MaxConcurrentTasks: ps.MaxConcurrentTasks,
		CurrentTaskCount:  ps.CurrentTaskCount,
		CreatedAt:         ps.CreatedAt,
		UpdatedAt:         ps.UpdatedAt,
	}

	return goSession
}

// SetTrafficPercent sets the percentage of traffic to route to GAIA_GO
func (sm *SessionMigrator) SetTrafficPercent(percent int) error {
	if percent < 0 || percent > 100 {
		return fmt.Errorf("traffic percent must be between 0 and 100")
	}

	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.trafficPercent = percent

	// Notify observers of phase change if at new milestone
	if percent == 10 {
		sm.notifyPhaseChange(PhaseGradualRollout)
	}

	return nil
}

// GetTrafficPercent returns the current traffic percentage
func (sm *SessionMigrator) GetTrafficPercent() int {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return sm.trafficPercent
}

// GetMetrics returns migration metrics
func (sm *SessionMigrator) GetMetrics() *MigrationMetrics {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	metrics := *sm.metrics
	metrics.LastUpdateTime = time.Now()

	// Calculate estimated completion time
	if sm.metrics.MigratedSessions > 0 && sm.metrics.TotalSessions > 0 {
		elapsedPerSession := time.Since(sm.startTime) / time.Duration(sm.metrics.MigratedSessions)
		remainingSessions := sm.metrics.TotalSessions - sm.metrics.MigratedSessions
		estimatedRemaining := elapsedPerSession * time.Duration(remainingSessions)
		metrics.EstimatedDuration = time.Since(sm.startTime) + estimatedRemaining
		metrics.EstimatedComplete = sm.startTime.Add(metrics.EstimatedDuration)
	}

	return &metrics
}

// GetState returns the current migration state
func (sm *SessionMigrator) GetState() MigrationPhase {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return sm.migrationState
}

// Complete finalizes the migration
func (sm *SessionMigrator) Complete(ctx context.Context) error {
	sm.mu.Lock()
	sm.migrationState = PhaseCompleted
	sm.notifyPhaseChange(PhaseCompleted)
	sm.mu.Unlock()

	return nil
}

// Rollback reverts the migration
func (sm *SessionMigrator) Rollback(ctx context.Context) error {
	sm.mu.Lock()
	sm.migrationState = PhasePreparing
	sm.trafficPercent = 0
	sm.notifyPhaseChange(PhasePreparing)
	sm.mu.Unlock()

	// Notify clients to use Python backend again
	// (Actual implementation depends on routing layer)

	return nil
}

// Private notification methods

func (sm *SessionMigrator) notifyPhaseChange(phase MigrationPhase) {
	for _, observer := range sm.observers {
		go observer.OnPhaseChange(phase)
	}
}

func (sm *SessionMigrator) notifyProgress() {
	for _, observer := range sm.observers {
		go observer.OnProgressUpdate(sm.metrics)
	}
}

func (sm *SessionMigrator) notifyError(sessionID string, err error) {
	for _, observer := range sm.observers {
		go observer.OnError(sessionID, err)
	}
}

func (sm *SessionMigrator) notifyValidationFailed(sessionID string, reason string) {
	for _, observer := range sm.observers {
		go observer.OnValidationFailed(sessionID, reason)
	}
}
