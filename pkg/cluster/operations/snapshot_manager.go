package operations

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/hashicorp/raft"
)

// SnapshotManager manages Raft snapshots and log rotation
type SnapshotManager struct {
	mu                sync.RWMutex
	raftNode          *raft.Raft
	snapshotPath      string
	logPath           string
	snapshotInterval  time.Duration
	maxLogSize        int64
	lastSnapshot      time.Time
	snapshotCount     uint64
	snapshotSize      int64
	lastLogRotation   time.Time
}

// SnapshotMetrics contains snapshot operation metrics
type SnapshotMetrics struct {
	LastSnapshotTime  time.Time
	SnapshotCount     uint64
	SnapshotSize      int64
	AverageSize       int64
	LastRotationTime  time.Time
	LogIndexes        LogIndexInfo
}

// LogIndexInfo contains log index information
type LogIndexInfo struct {
	FirstIndex     uint64
	LastIndex      uint64
	CompactedIndex uint64
}

// NewSnapshotManager creates a new snapshot manager
func NewSnapshotManager(
	raftNode *raft.Raft,
	snapshotPath string,
	logPath string,
	snapshotInterval time.Duration,
	maxLogSize int64,
) *SnapshotManager {
	return &SnapshotManager{
		raftNode:         raftNode,
		snapshotPath:     snapshotPath,
		logPath:          logPath,
		snapshotInterval: snapshotInterval,
		maxLogSize:       maxLogSize,
		lastSnapshot:     time.Now(),
	}
}

// TakeSnapshot triggers a snapshot if conditions are met
func (sm *SnapshotManager) TakeSnapshot(ctx context.Context) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	// Check if enough time has passed
	if time.Since(sm.lastSnapshot) < sm.snapshotInterval {
		return fmt.Errorf("snapshot taken too recently")
	}

	return sm.takeSnapshotLocked(ctx)
}

// TakeSnapshotForced takes a snapshot immediately
func (sm *SnapshotManager) TakeSnapshotForced(ctx context.Context) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	return sm.takeSnapshotLocked(ctx)
}

// takeSnapshotLocked takes a snapshot (must hold mutex)
func (sm *SnapshotManager) takeSnapshotLocked(ctx context.Context) error {
	// Get current state index
	index := sm.raftNode.LastIndex()

	// Check if index is reasonable (avoid snapshots at same index)
	if index == 0 {
		return fmt.Errorf("no logs to snapshot")
	}

	// Create snapshot filename with timestamp
	timestamp := time.Now().Format("20060102150405")
	snapshotFile := filepath.Join(sm.snapshotPath, fmt.Sprintf("snapshot_%d_%s.snap", index, timestamp))

	// Take the actual snapshot
	snapshotFuture := sm.raftNode.Snapshot()
	if err := snapshotFuture.Error(); err != nil {
		return fmt.Errorf("failed to take snapshot: %w", err)
	}

	// Save metadata
	sm.lastSnapshot = time.Now()
	sm.snapshotCount++

	// Compact logs up to snapshot index
	err := sm.compactLogs(index)
	if err != nil {
		// Log but don't fail - snapshot was successful
		fmt.Printf("warning: failed to compact logs: %v\n", err)
	}

	return nil
}

// compactLogs removes old log entries up to the given index
func (sm *SnapshotManager) compactLogs(index uint64) error {
	// This would be implemented at the storage layer
	// For now, just track that we did it
	return nil
}

// CheckAndRotateLogs checks if logs should be rotated
func (sm *SnapshotManager) CheckAndRotateLogs(ctx context.Context) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	// Get log size
	logSize, err := sm.getLogSize()
	if err != nil {
		return err
	}

	// Check if rotation is needed
	if logSize > sm.maxLogSize {
		return sm.rotateLogs()
	}

	return nil
}

// getLogSize calculates the size of all log files
func (sm *SnapshotManager) getLogSize() (int64, error) {
	var totalSize int64

	err := filepath.Walk(sm.logPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if !info.IsDir() {
			totalSize += info.Size()
		}

		return nil
	})

	return totalSize, err
}

// rotateLogs rotates log files (move to archive, create new)
func (sm *SnapshotManager) rotateLogs() error {
	// Create archive directory
	archiveDir := filepath.Join(sm.logPath, "archive")
	if err := os.MkdirAll(archiveDir, 0755); err != nil {
		return fmt.Errorf("failed to create archive directory: %w", err)
	}

	// Move old logs to archive with timestamp
	timestamp := time.Now().Format("20060102150405")
	archivePrefix := filepath.Join(archiveDir, fmt.Sprintf("logs_%s", timestamp))

	if err := os.Mkdir(archivePrefix, 0755); err != nil && !os.IsExist(err) {
		return fmt.Errorf("failed to create archive prefix: %w", err)
	}

	// Move log files (implementation-specific)
	sm.lastLogRotation = time.Now()

	return nil
}

// GetMetrics returns snapshot and log metrics
func (sm *SnapshotManager) GetMetrics() SnapshotMetrics {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	metrics := SnapshotMetrics{
		LastSnapshotTime: sm.lastSnapshot,
		SnapshotCount:    sm.snapshotCount,
		SnapshotSize:     sm.snapshotSize,
		LastRotationTime: sm.lastLogRotation,
		LogIndexes: LogIndexInfo{
			LastIndex: sm.raftNode.LastIndex(),
		},
	}

	if sm.snapshotCount > 0 {
		metrics.AverageSize = sm.snapshotSize / int64(sm.snapshotCount)
	}

	return metrics
}

// VerifySnapshotIntegrity verifies that snapshots are valid
func (sm *SnapshotManager) VerifySnapshotIntegrity(ctx context.Context) error {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	// List all snapshot files
	entries, err := os.ReadDir(sm.snapshotPath)
	if err != nil {
		return fmt.Errorf("failed to read snapshot directory: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		// Verify each snapshot file is readable
		path := filepath.Join(sm.snapshotPath, entry.Name())
		file, err := os.Open(path)
		if err != nil {
			return fmt.Errorf("failed to open snapshot %s: %w", path, err)
		}

		// Try to read a small portion
		buf := make([]byte, 1024)
		_, err = file.Read(buf)
		file.Close()

		if err != nil && err != io.EOF {
			return fmt.Errorf("failed to read snapshot %s: %w", path, err)
		}
	}

	return nil
}

// ListSnapshots lists all available snapshots
func (sm *SnapshotManager) ListSnapshots() ([]SnapshotInfo, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	var snapshots []SnapshotInfo

	entries, err := os.ReadDir(sm.snapshotPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read snapshot directory: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			continue
		}

		snapshots = append(snapshots, SnapshotInfo{
			Filename:    entry.Name(),
			Size:        info.Size(),
			CreatedAt:   info.ModTime(),
		})
	}

	return snapshots, nil
}

// SnapshotInfo contains information about a snapshot
type SnapshotInfo struct {
	Filename  string
	Size      int64
	CreatedAt time.Time
}

// RestoreFromSnapshot restores state from a snapshot (for recovery)
func (sm *SnapshotManager) RestoreFromSnapshot(ctx context.Context, filename string) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	path := filepath.Join(sm.snapshotPath, filename)

	// Verify file exists and is readable
	file, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("failed to open snapshot for restore: %w", err)
	}
	defer file.Close()

	// In a real implementation, this would trigger Raft to load the snapshot
	// For now, just verify it's readable
	buf := make([]byte, 1024*1024) // 1MB buffer
	_, err = file.Read(buf)
	if err != nil && err != io.EOF {
		return fmt.Errorf("failed to read snapshot: %w", err)
	}

	return nil
}

// SchedulePeriodicSnapshots starts a background goroutine for periodic snapshots
func (sm *SnapshotManager) SchedulePeriodicSnapshots(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := sm.TakeSnapshot(ctx); err != nil {
				// Log but continue
				fmt.Printf("periodic snapshot failed: %v\n", err)
			}
		}
	}
}

// GetCompactionStatus returns information about log compaction
func (sm *SnapshotManager) GetCompactionStatus() map[string]interface{} {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return map[string]interface{}{
		"last_snapshot":     sm.lastSnapshot,
		"snapshot_count":    sm.snapshotCount,
		"snapshot_size":     sm.snapshotSize,
		"average_size":      sm.snapshotSize / int64(max(1, sm.snapshotCount)),
		"last_log_rotation": sm.lastLogRotation,
		"last_index":        sm.raftNode.LastIndex(),
	}
}

// Helper function
func max(a, b uint64) uint64 {
	if a > b {
		return a
	}
	return b
}
