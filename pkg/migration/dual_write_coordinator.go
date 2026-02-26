package migration

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jgirmay/GAIA_GO/pkg/models"
)

// DualWriteCoordinator manages dual-write operations to keep GAIA_HOME and GAIA_GO synchronized
type DualWriteCoordinator struct {
	mu sync.RWMutex

	// Source (GAIA_HOME)
	pythonClient PythonSessionClient

	// Destination (GAIA_GO)
	goRepository GoSessionRepository

	// Dual-write state
	enabled         bool
	writeMode       DualWriteMode
	metrics         *DualWriteMetrics
	conflictHandler ConflictHandler

	// Observers
	observers map[string]DualWriteObserver
}

// DualWriteMode defines how writes are handled
type DualWriteMode string

const (
	DualWriteModeGOLeads     DualWriteMode = "go_leads"      // Write to GO first, then Python
	DualWriteModePythonLeads DualWriteMode = "python_leads"  // Write to Python first, then GO
	DualWriteModeParallel    DualWriteMode = "parallel"      // Write to both, handle conflicts
)

// DualWriteMetrics tracks dual-write operations
type DualWriteMetrics struct {
	TotalWrites        int64
	SuccessfulWrites   int64
	PartialWrites      int64
	FailedWrites       int64
	ConflictResolved   int64
	ConflictUnresolved int64
	SyncLag            time.Duration
	LastUpdateTime     time.Time
}

// ConflictHandler resolves conflicts between GAIA_HOME and GAIA_GO
type ConflictHandler interface {
	// ResolveSessionConflict returns which version should be used
	ResolveSessionConflict(pythonVersion, goVersion *models.ClaudeSession) (*models.ClaudeSession, error)

	// ResolveFieldConflict returns which field value should be used
	ResolveFieldConflict(field string, pythonValue, goValue interface{}) (interface{}, error)
}

// DualWriteObserver receives updates on dual-write operations
type DualWriteObserver interface {
	OnWriteAttempted(sessionID string, writeMode DualWriteMode)
	OnWriteSuccess(sessionID string, systems []string)
	OnWritePartial(sessionID string, succeededSystems, failedSystems []string)
	OnConflictDetected(sessionID string, field string)
	OnConflictResolved(sessionID string, resolution string)
}

// NewDualWriteCoordinator creates a new dual-write coordinator
func NewDualWriteCoordinator(
	pythonClient PythonSessionClient,
	goRepository GoSessionRepository,
	conflictHandler ConflictHandler,
) *DualWriteCoordinator {
	return &DualWriteCoordinator{
		pythonClient:    pythonClient,
		goRepository:    goRepository,
		conflictHandler: conflictHandler,
		writeMode:       DualWriteModeGOLeads, // Default: write to GO first
		metrics:         &DualWriteMetrics{},
		observers:       make(map[string]DualWriteObserver),
	}
}

// Enable enables dual-write mode
func (dc *DualWriteCoordinator) Enable() {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	dc.enabled = true
}

// Disable disables dual-write mode
func (dc *DualWriteCoordinator) Disable() {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	dc.enabled = false
}

// SetWriteMode sets the dual-write mode
func (dc *DualWriteCoordinator) SetWriteMode(mode DualWriteMode) error {
	if mode != DualWriteModeGOLeads && mode != DualWriteModePythonLeads && mode != DualWriteModeParallel {
		return fmt.Errorf("invalid write mode: %s", mode)
	}

	dc.mu.Lock()
	defer dc.mu.Unlock()

	dc.writeMode = mode
	return nil
}

// WriteSession writes a session to both systems
func (dc *DualWriteCoordinator) WriteSession(ctx context.Context, session *models.ClaudeSession) error {
	dc.mu.RLock()
	if !dc.enabled {
		dc.mu.RUnlock()
		return nil // Dual-write disabled, skip
	}

	writeMode := dc.writeMode
	dc.mu.RUnlock()

	atomic.AddInt64(&dc.metrics.TotalWrites, 1)

	switch writeMode {
	case DualWriteModeGOLeads:
		return dc.writeGOLeads(ctx, session)
	case DualWriteModePythonLeads:
		return dc.writePythonLeads(ctx, session)
	case DualWriteModeParallel:
		return dc.writeParallel(ctx, session)
	default:
		return fmt.Errorf("unknown write mode: %s", writeMode)
	}
}

// writeGOLeads writes to GO first, then Python (fails if GO fails)
func (dc *DualWriteCoordinator) writeGOLeads(ctx context.Context, session *models.ClaudeSession) error {
	sessionID := session.SessionName

	dc.notifyWriteAttempted(sessionID, DualWriteModeGOLeads)

	// Write to GAIA_GO first
	_, err := dc.goRepository.Create(ctx, session)
	if err != nil {
		atomic.AddInt64(&dc.metrics.FailedWrites, 1)
		dc.notifyWritePartial(sessionID, []string{}, []string{"go", "python"})
		return fmt.Errorf("failed to write to GAIA_GO: %w", err)
	}

	// Write to GAIA_HOME
	pythonSession := dc.convertGoSessionToPython(session)
	err = dc.pythonClient.UpdateSessionStatus(ctx, pythonSession.ID, pythonSession.Status)
	if err != nil {
		atomic.AddInt64(&dc.metrics.PartialWrites, 1)
		dc.notifyWritePartial(sessionID, []string{"go"}, []string{"python"})
		return fmt.Errorf("failed to write to Python: %w", err)
	}

	atomic.AddInt64(&dc.metrics.SuccessfulWrites, 1)
	dc.notifyWriteSuccess(sessionID, []string{"go", "python"})

	return nil
}

// writePythonLeads writes to Python first, then GO
func (dc *DualWriteCoordinator) writePythonLeads(ctx context.Context, session *models.ClaudeSession) error {
	sessionID := session.SessionName

	dc.notifyWriteAttempted(sessionID, DualWriteModePythonLeads)

	// Write to Python first
	pythonSession := dc.convertGoSessionToPython(session)
	err := dc.pythonClient.UpdateSessionStatus(ctx, pythonSession.ID, pythonSession.Status)
	if err != nil {
		atomic.AddInt64(&dc.metrics.FailedWrites, 1)
		dc.notifyWritePartial(sessionID, []string{}, []string{"python", "go"})
		return fmt.Errorf("failed to write to Python: %w", err)
	}

	// Write to GAIA_GO
	_, err = dc.goRepository.Create(ctx, session)
	if err != nil {
		atomic.AddInt64(&dc.metrics.PartialWrites, 1)
		dc.notifyWritePartial(sessionID, []string{"python"}, []string{"go"})
		return fmt.Errorf("failed to write to GAIA_GO: %w", err)
	}

	atomic.AddInt64(&dc.metrics.SuccessfulWrites, 1)
	dc.notifyWriteSuccess(sessionID, []string{"python", "go"})

	return nil
}

// writeParallel writes to both systems in parallel
func (dc *DualWriteCoordinator) writeParallel(ctx context.Context, session *models.ClaudeSession) error {
	sessionID := session.SessionName

	dc.notifyWriteAttempted(sessionID, DualWriteModeParallel)

	// Write to both in parallel
	var goErr, pythonErr error
	var wg sync.WaitGroup

	wg.Add(1)
	go func() {
		defer wg.Done()
		_, goErr = dc.goRepository.Create(ctx, session)
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		pythonSession := dc.convertGoSessionToPython(session)
		pythonErr = dc.pythonClient.UpdateSessionStatus(ctx, pythonSession.ID, pythonSession.Status)
	}()

	wg.Wait()

	// Determine success
	goSuccess := goErr == nil
	pythonSuccess := pythonErr == nil

	if goSuccess && pythonSuccess {
		atomic.AddInt64(&dc.metrics.SuccessfulWrites, 1)
		dc.notifyWriteSuccess(sessionID, []string{"go", "python"})
		return nil
	}

	if goSuccess || pythonSuccess {
		atomic.AddInt64(&dc.metrics.PartialWrites, 1)
		succeeded := []string{}
		failed := []string{}

		if goSuccess {
			succeeded = append(succeeded, "go")
		} else {
			failed = append(failed, "go")
		}

		if pythonSuccess {
			succeeded = append(succeeded, "python")
		} else {
			failed = append(failed, "python")
		}

		dc.notifyWritePartial(sessionID, succeeded, failed)
		return fmt.Errorf("partial write failure: %s failed", failed[0])
	}

	atomic.AddInt64(&dc.metrics.FailedWrites, 1)
	dc.notifyWritePartial(sessionID, []string{}, []string{"go", "python"})
	return fmt.Errorf("write failed on both systems: GO=%v, Python=%v", goErr, pythonErr)
}

// SyncSession synchronizes a session between systems
func (dc *DualWriteCoordinator) SyncSession(ctx context.Context, sessionID string) error {
	// Get session from both systems
	pythonSession, err := dc.pythonClient.GetSession(ctx, sessionID)
	if err != nil {
		return fmt.Errorf("failed to get session from Python: %w", err)
	}

	goSession, err := dc.goRepository.GetByID(ctx, sessionID)
	if err != nil {
		return fmt.Errorf("failed to get session from GO: %w", err)
	}

	// Convert and compare
	pythonAsGo := dc.convertPythonSessionToGo(pythonSession)

	// Check for conflicts
	if !dc.sessionsEqual(pythonAsGo, goSession) {
		// Resolve conflict
		resolvedSession, err := dc.conflictHandler.ResolveSessionConflict(goSession, pythonAsGo)
		if err != nil {
			atomic.AddInt64(&dc.metrics.ConflictUnresolved, 1)
			return fmt.Errorf("failed to resolve conflict: %w", err)
		}

		atomic.AddInt64(&dc.metrics.ConflictResolved, 1)
		dc.notifyConflictResolved(sessionID, "resolved")

		// Apply resolution to both systems
		return dc.WriteSession(ctx, resolvedSession)
	}

	return nil
}

// GetMetrics returns dual-write metrics
func (dc *DualWriteCoordinator) GetMetrics() *DualWriteMetrics {
	dc.mu.RLock()
	defer dc.mu.RUnlock()

	metrics := *dc.metrics
	metrics.LastUpdateTime = time.Now()
	return &metrics
}

// RegisterObserver registers a dual-write observer
func (dc *DualWriteCoordinator) RegisterObserver(name string, observer DualWriteObserver) {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	dc.observers[name] = observer
}

// Helper methods

func (dc *DualWriteCoordinator) convertGoSessionToPython(session *models.ClaudeSession) *PythonSession {
	return &PythonSession{
		ID:                 session.ID,
		UserID:             session.UserID,
		SessionName:        session.SessionName,
		Tier:               session.Tier,
		Provider:           session.Provider,
		Status:             session.Status,
		LessonID:           session.LessonID,
		TimeWindowStart:    session.TimeWindowStart,
		TimeWindowEnd:      session.TimeWindowEnd,
		LastHeartbeat:      session.LastHeartbeat,
		HealthStatus:       session.HealthStatus,
		MaxConcurrentTasks: session.MaxConcurrentTasks,
		CurrentTaskCount:   session.CurrentTaskCount,
		CreatedAt:          session.CreatedAt,
		UpdatedAt:          session.UpdatedAt,
	}
}

func (dc *DualWriteCoordinator) convertPythonSessionToGo(session *PythonSession) *models.ClaudeSession {
	return &models.ClaudeSession{
		ID:                 session.ID,
		UserID:             session.UserID,
		SessionName:        session.SessionName,
		Tier:               session.Tier,
		Provider:           session.Provider,
		Status:             session.Status,
		LessonID:           session.LessonID,
		TimeWindowStart:    session.TimeWindowStart,
		TimeWindowEnd:      session.TimeWindowEnd,
		LastHeartbeat:      session.LastHeartbeat,
		HealthStatus:       session.HealthStatus,
		MaxConcurrentTasks: session.MaxConcurrentTasks,
		CurrentTaskCount:   session.CurrentTaskCount,
		CreatedAt:          session.CreatedAt,
		UpdatedAt:          session.UpdatedAt,
	}
}

func (dc *DualWriteCoordinator) sessionsEqual(a, b *models.ClaudeSession) bool {
	return a.SessionName == b.SessionName &&
		a.Status == b.Status &&
		a.HealthStatus == b.HealthStatus &&
		a.CurrentTaskCount == b.CurrentTaskCount
}

// Notification methods

func (dc *DualWriteCoordinator) notifyWriteAttempted(sessionID string, mode DualWriteMode) {
	for _, observer := range dc.observers {
		go observer.OnWriteAttempted(sessionID, mode)
	}
}

func (dc *DualWriteCoordinator) notifyWriteSuccess(sessionID string, systems []string) {
	for _, observer := range dc.observers {
		go observer.OnWriteSuccess(sessionID, systems)
	}
}

func (dc *DualWriteCoordinator) notifyWritePartial(sessionID string, succeeded, failed []string) {
	for _, observer := range dc.observers {
		go observer.OnWritePartial(sessionID, succeeded, failed)
	}
}

func (dc *DualWriteCoordinator) notifyConflictDetected(sessionID, field string) {
	for _, observer := range dc.observers {
		go observer.OnConflictDetected(sessionID, field)
	}
}

func (dc *DualWriteCoordinator) notifyConflictResolved(sessionID, resolution string) {
	for _, observer := range dc.observers {
		go observer.OnConflictResolved(sessionID, resolution)
	}
}
