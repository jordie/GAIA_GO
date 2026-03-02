package rate_limiting

import (
	"context"
	"crypto/sha256"
	"fmt"
	"sync"
	"time"

	"gorm.io/gorm"
)

// ReputationEvent represents a reputation-changing event that can be replicated
type ReputationEvent struct {
	ID              int       `json:"id" gorm:"primaryKey"`
	NodeID          string    `json:"node_id" gorm:"index"`
	UserID          int       `json:"user_id" gorm:"index"`
	EventType       string    `json:"event_type"`        // violation, clean_request, tier_change, vip_assigned
	ScoreDelta      float64   `json:"score_delta"`       // Change in score
	ReasonCode      string    `json:"reason_code"`       // Why this happened
	Severity        int       `json:"severity"`          // 1-3 for violations
	SourceService   string    `json:"source_service"`    // Which service recorded this
	EventHash       string    `json:"event_hash"`        // SHA256 hash for deduplication
	Timestamp       time.Time `json:"timestamp" gorm:"index"`
	SyncedAt        *time.Time `json:"synced_at"`        // When it was synced to other nodes
	LocalOnly       bool      `json:"local_only"`        // Don't replicate if true
	CreatedAt       time.Time `json:"created_at" gorm:"index"`
}

// ReputationSync tracks synchronization state between nodes
type ReputationSync struct {
	ID              int       `json:"id" gorm:"primaryKey"`
	NodeID          string    `json:"node_id" gorm:"index"`
	RemoteNodeID    string    `json:"remote_node_id" gorm:"index"`
	LastSyncTime    time.Time `json:"last_sync_time"`
	LastEventID     int       `json:"last_event_id"`        // Last event replicated
	PendingEvents   int       `json:"pending_events"`       // Events not yet synced
	SyncErrors      int       `json:"sync_errors"`          // Consecutive failures
	Status          string    `json:"status"`               // healthy, degraded, failed
	SyncFrequency   int       `json:"sync_frequency"`       // Seconds between syncs
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

// NodeReputation represents a node's view of a user's reputation
type NodeReputation struct {
	ID              int       `json:"id" gorm:"primaryKey"`
	UserID          int       `json:"user_id" gorm:"index"`
	NodeID          string    `json:"node_id" gorm:"index"`
	Score           float64   `json:"score"`
	Tier            string    `json:"tier"`
	LastUpdated     time.Time `json:"last_updated"`
	IsAuthoritative bool      `json:"is_authoritative"` // This node is source of truth for this user
	CreatedAt       time.Time `json:"created_at"`
}

// DistributedReputationManager manages reputation across multiple nodes
type DistributedReputationManager struct {
	db              *gorm.DB
	localNodeID     string
	remoteNodes     map[string]string // node_id -> API endpoint
	syncInterval    time.Duration
	mu              sync.RWMutex
	syncActive      bool
	stopChan        chan struct{}
	eventBuffer     []*ReputationEvent
	bufferMutex     sync.Mutex
	bufferSize      int
	conflictResolver ConflictResolver
}

// ConflictResolver defines strategy for handling reputation conflicts
type ConflictResolver interface {
	ResolveTierConflict(localTier, remoteTier string, localTime, remoteTime time.Time) string
	ResolveScoreConflict(localScore, remoteScore float64, localTime, remoteTime time.Time) float64
}

// TimestampResolver resolves conflicts using timestamp (most recent wins)
type TimestampResolver struct{}

func (tr *TimestampResolver) ResolveTierConflict(localTier, remoteTier string, localTime, remoteTime time.Time) string {
	if remoteTime.After(localTime) {
		return remoteTier
	}
	return localTier
}

func (tr *TimestampResolver) ResolveScoreConflict(localScore, remoteScore float64, localTime, remoteTime time.Time) float64 {
	if remoteTime.After(localTime) {
		return remoteScore
	}
	return localScore
}

// NewDistributedReputationManager creates a distributed reputation manager
func NewDistributedReputationManager(db *gorm.DB, nodeID string) *DistributedReputationManager {
	drm := &DistributedReputationManager{
		db:              db,
		localNodeID:     nodeID,
		remoteNodes:     make(map[string]string),
		syncInterval:    10 * time.Second,
		stopChan:        make(chan struct{}),
		eventBuffer:     make([]*ReputationEvent, 0, 1000),
		bufferSize:      1000,
		conflictResolver: &TimestampResolver{},
	}

	// Start background sync worker
	go drm.startSyncWorker()

	return drm
}

// RegisterRemoteNode adds a remote node to the replication network
func (drm *DistributedReputationManager) RegisterRemoteNode(nodeID, apiEndpoint string) error {
	drm.mu.Lock()
	drm.remoteNodes[nodeID] = apiEndpoint
	drm.mu.Unlock()

	// Initialize sync tracking
	sync := &ReputationSync{
		NodeID:        drm.localNodeID,
		RemoteNodeID:  nodeID,
		LastSyncTime:  time.Now(),
		LastEventID:   0,
		Status:        "healthy",
		SyncFrequency: 10,
		CreatedAt:     time.Now(),
		UpdatedAt:     time.Now(),
	}

	if err := drm.db.Create(sync).Error; err != nil && !isUniqueConstraintError(err) {
		return err
	}

	return nil
}

// RecordEvent records a reputation event for replication
func (drm *DistributedReputationManager) RecordEvent(ctx context.Context, event *ReputationEvent) error {
	// Set event metadata
	event.NodeID = drm.localNodeID
	event.Timestamp = time.Now()
	event.EventHash = drm.hashEvent(event)

	// Check for duplicate
	var existing ReputationEvent
	if err := drm.db.Where("event_hash = ?", event.EventHash).First(&existing).Error; err == nil {
		// Event already exists, skip it
		return nil
	}

	// Store locally
	if err := drm.db.Create(event).Error; err != nil {
		return err
	}

	// Buffer for async replication
	if !event.LocalOnly {
		drm.bufferMutex.Lock()
		drm.eventBuffer = append(drm.eventBuffer, event)
		if len(drm.eventBuffer) >= drm.bufferSize {
			drm.bufferMutex.Unlock()
			// Force flush if buffer is full
			drm.flushEventBuffer()
		} else {
			drm.bufferMutex.Unlock()
		}
	}

	return nil
}

// hashEvent creates a deterministic hash for deduplication
func (drm *DistributedReputationManager) hashEvent(event *ReputationEvent) string {
	hash := sha256.Sum256([]byte(
		fmt.Sprintf("%d:%s:%s:%f:%d", event.UserID, event.EventType, event.SourceService, event.ScoreDelta, event.Timestamp.Unix()),
	))
	return fmt.Sprintf("%x", hash)
}

// startSyncWorker runs the background synchronization worker
func (drm *DistributedReputationManager) startSyncWorker() {
	drm.mu.Lock()
	drm.syncActive = true
	drm.mu.Unlock()

	ticker := time.NewTicker(drm.syncInterval)
	defer ticker.Stop()

	for {
		select {
		case <-drm.stopChan:
			drm.mu.Lock()
			drm.syncActive = false
			drm.mu.Unlock()
			return
		case <-ticker.C:
			drm.flushEventBuffer()
			drm.syncWithRemoteNodes()
		}
	}
}

// flushEventBuffer sends buffered events to remote nodes
func (drm *DistributedReputationManager) flushEventBuffer() {
	drm.bufferMutex.Lock()
	if len(drm.eventBuffer) == 0 {
		drm.bufferMutex.Unlock()
		return
	}

	events := make([]*ReputationEvent, len(drm.eventBuffer))
	copy(events, drm.eventBuffer)
	drm.eventBuffer = drm.eventBuffer[:0] // Clear buffer
	drm.bufferMutex.Unlock()

	drm.mu.RLock()
	remoteNodes := make(map[string]string)
	for k, v := range drm.remoteNodes {
		remoteNodes[k] = v
	}
	drm.mu.RUnlock()

	// Send to each remote node
	for nodeID := range remoteNodes {
		go drm.replicateEventsToNode(nodeID, events)
	}

	// Mark events as synced
	now := time.Now()
	for _, event := range events {
		drm.db.Model(event).Update("synced_at", now)
	}
}

// replicateEventsToNode sends events to a specific remote node
func (drm *DistributedReputationManager) replicateEventsToNode(nodeID string, events []*ReputationEvent) {
	drm.mu.RLock()
	_, exists := drm.remoteNodes[nodeID]
	drm.mu.RUnlock()

	if !exists {
		return
	}

	// In production, this would use HTTP to send events
	// For now, we record the attempt in sync tracking
	drm.recordSyncAttempt(nodeID, len(events), true)
}

// recordSyncAttempt updates sync tracking for a node
func (drm *DistributedReputationManager) recordSyncAttempt(nodeID string, eventCount int, success bool) {
	sync := &ReputationSync{}
	if err := drm.db.Where("node_id = ? AND remote_node_id = ?", drm.localNodeID, nodeID).First(sync).Error; err != nil {
		return
	}

	if success {
		sync.LastSyncTime = time.Now()
		sync.PendingEvents = 0
		sync.SyncErrors = 0
		sync.Status = "healthy"
	} else {
		sync.SyncErrors++
		if sync.SyncErrors > 3 {
			sync.Status = "failed"
		} else {
			sync.Status = "degraded"
		}
	}
	sync.UpdatedAt = time.Now()

	drm.db.Save(sync)
}

// syncWithRemoteNodes pulls reputation updates from remote nodes
func (drm *DistributedReputationManager) syncWithRemoteNodes() {
	drm.mu.RLock()
	nodes := make([]string, 0, len(drm.remoteNodes))
	for nodeID := range drm.remoteNodes {
		nodes = append(nodes, nodeID)
	}
	drm.mu.RUnlock()

	for _, nodeID := range nodes {
		go drm.pullEventsFromNode(nodeID)
	}
}

// pullEventsFromNode retrieves new events from a remote node
func (drm *DistributedReputationManager) pullEventsFromNode(nodeID string) {
	// In production, this would fetch from remote node's API
	// For now, we just mark the attempt
	drm.recordSyncAttempt(nodeID, 0, true)
}

// GetUserReputationConsensus gets reputation with consensus across nodes
func (drm *DistributedReputationManager) GetUserReputationConsensus(ctx context.Context, userID int) (score float64, tier string, confidence float64, err error) {
	var nodeReps []NodeReputation

	// Get reputation from all nodes
	if err := drm.db.Where("user_id = ?", userID).Find(&nodeReps).Error; err != nil {
		return 0, "", 0, err
	}

	if len(nodeReps) == 0 {
		return 0, "unknown", 0, fmt.Errorf("no reputation data found")
	}

	// Calculate consensus
	scoreSum := 0.0
	tierCounts := make(map[string]int)
	authoritativeFound := false

	for _, rep := range nodeReps {
		scoreSum += rep.Score
		tierCounts[rep.Tier]++

		if rep.IsAuthoritative {
			authoritativeFound = true
			score = rep.Score
			tier = rep.Tier
		}
	}

	// If no authoritative source, use majority
	maxCount := 0
	if !authoritativeFound {
		score = scoreSum / float64(len(nodeReps))

		for t, count := range tierCounts {
			if count > maxCount {
				maxCount = count
				tier = t
			}
		}
	}

	// Confidence based on consistency
	confidence = 1.0 - (float64(len(nodeReps)-maxCount) / float64(len(nodeReps)))

	return score, tier, confidence, nil
}

// ResolveUserReputation resolves conflicts and updates reputation across nodes
func (drm *DistributedReputationManager) ResolveUserReputation(ctx context.Context, userID int) error {
	var reps []NodeReputation
	if err := drm.db.Where("user_id = ?", userID).Order("last_updated DESC").Find(&reps).Error; err != nil {
		return err
	}

	if len(reps) == 0 {
		return fmt.Errorf("no reputation data found")
	}

	// Find most recent
	authoritative := reps[0]

	// Update all others
	for _, rep := range reps[1:] {
		// Use conflict resolver
		resolvedScore := drm.conflictResolver.ResolveScoreConflict(
			rep.Score, authoritative.Score,
			rep.LastUpdated, authoritative.LastUpdated,
		)

		if resolvedScore != rep.Score {
			drm.db.Model(&rep).Updates(map[string]interface{}{
				"score":           resolvedScore,
				"tier":            authoritative.Tier,
				"last_updated":    time.Now(),
				"is_authoritative": false,
			})
		}
	}

	return nil
}

// GetSyncStatus returns synchronization status across the network
func (drm *DistributedReputationManager) GetSyncStatus(ctx context.Context) (map[string]interface{}, error) {
	var syncs []ReputationSync
	if err := drm.db.Where("node_id = ?", drm.localNodeID).Find(&syncs).Error; err != nil {
		return nil, err
	}

	healthyCount := 0
	degradedCount := 0
	failedCount := 0
	totalPending := 0

	for _, sync := range syncs {
		switch sync.Status {
		case "healthy":
			healthyCount++
		case "degraded":
			degradedCount++
		case "failed":
			failedCount++
		}
		totalPending += sync.PendingEvents
	}

	return map[string]interface{}{
		"node_id":           drm.localNodeID,
		"total_nodes":       len(syncs),
		"healthy_nodes":     healthyCount,
		"degraded_nodes":    degradedCount,
		"failed_nodes":      failedCount,
		"total_pending":     totalPending,
		"buffer_size":       len(drm.eventBuffer),
		"last_sync":         time.Now(),
		"syncs":             syncs,
	}, nil
}

// GetReplicationStats returns replication statistics
func (drm *DistributedReputationManager) GetReplicationStats(ctx context.Context) (map[string]interface{}, error) {
	var eventCount int64
	var unsyncedCount int64

	drm.db.Model(&ReputationEvent{}).Count(&eventCount)
	drm.db.Model(&ReputationEvent{}).Where("synced_at IS NULL").Count(&unsyncedCount)

	// Get local-only events count
	var localOnlyCount int64

	drm.db.Model(&ReputationEvent{}).Where("local_only = ?", true).Count(&localOnlyCount)

	return map[string]interface{}{
		"total_events":      eventCount,
		"unsynced_events":   unsyncedCount,
		"local_only_events": localOnlyCount,
		"buffer_size":       len(drm.eventBuffer),
		"sync_interval":     drm.syncInterval.Seconds(),
		"remote_nodes":      len(drm.remoteNodes),
	}, nil
}

// GetLocalNodeID returns the local node's ID
func (drm *DistributedReputationManager) GetLocalNodeID() string {
	return drm.localNodeID
}

// Close stops the distributed reputation manager
func (drm *DistributedReputationManager) Close() error {
	drm.mu.Lock()
	defer drm.mu.Unlock()

	if drm.syncActive {
		close(drm.stopChan)
		drm.syncActive = false
	}

	return nil
}

// Helper function to check if error is unique constraint violation
func isUniqueConstraintError(err error) bool {
	if err == nil {
		return false
	}
	return err == gorm.ErrDuplicatedKey || err.Error() == "UNIQUE constraint failed"
}
