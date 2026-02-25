package cache

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// CacheLevel represents a cache tier
type CacheLevel int

const (
	L1 CacheLevel = iota // In-memory cache
	L2                    // Redis cache
	L3                    // Database cache
)

// CacheEntry represents a cached value with metadata
type CacheEntry struct {
	Value     interface{}
	ExpiresAt time.Time
	HitCount  int64
	CreatedAt time.Time
}

// IsExpired checks if entry is expired
func (ce *CacheEntry) IsExpired() bool {
	return time.Now().After(ce.ExpiresAt)
}

// L1Cache is an in-memory cache with TTL support
type L1Cache struct {
	mu      sync.RWMutex
	entries map[string]*CacheEntry
	maxSize int
}

// NewL1Cache creates a new L1 in-memory cache
func NewL1Cache(maxSize int) *L1Cache {
	return &L1Cache{
		entries: make(map[string]*CacheEntry),
		maxSize: maxSize,
	}
}

// Get retrieves value from L1 cache
func (l1 *L1Cache) Get(key string) (interface{}, bool) {
	l1.mu.RLock()
	defer l1.mu.RUnlock()

	entry, exists := l1.entries[key]
	if !exists {
		return nil, false
	}

	if entry.IsExpired() {
		go l1.Delete(key)
		return nil, false
	}

	entry.HitCount++
	return entry.Value, true
}

// Set stores value in L1 cache
func (l1 *L1Cache) Set(key string, value interface{}, ttl time.Duration) {
	l1.mu.Lock()
	defer l1.mu.Unlock()

	// Simple eviction: remove oldest entry if at capacity
	if len(l1.entries) >= l1.maxSize && l1.entries[key] == nil {
		oldestKey := ""
		var oldestTime time.Time
		for k, v := range l1.entries {
			if oldestTime.IsZero() || v.CreatedAt.Before(oldestTime) {
				oldestKey = k
				oldestTime = v.CreatedAt
			}
		}
		if oldestKey != "" {
			delete(l1.entries, oldestKey)
		}
	}

	l1.entries[key] = &CacheEntry{
		Value:     value,
		ExpiresAt: time.Now().Add(ttl),
		CreatedAt: time.Now(),
	}
}

// Delete removes entry from L1 cache
func (l1 *L1Cache) Delete(key string) {
	l1.mu.Lock()
	defer l1.mu.Unlock()
	delete(l1.entries, key)
}

// Clear clears all L1 cache entries
func (l1 *L1Cache) Clear() {
	l1.mu.Lock()
	defer l1.mu.Unlock()
	l1.entries = make(map[string]*CacheEntry)
}

// Stats returns cache statistics
func (l1 *L1Cache) Stats() map[string]interface{} {
	l1.mu.RLock()
	defer l1.mu.RUnlock()

	totalHits := int64(0)
	for _, entry := range l1.entries {
		totalHits += entry.HitCount
	}

	return map[string]interface{}{
		"size":        len(l1.entries),
		"max_size":    l1.maxSize,
		"total_hits":  totalHits,
		"utilization": float64(len(l1.entries)) / float64(l1.maxSize),
	}
}

// TieredCache implements 3-tier caching (L1, L2, L3)
type TieredCache struct {
	l1     *L1Cache
	l2     map[string]*CacheEntry // Simulated L2 (Redis equivalent)
	l3Map  map[string]*CacheEntry // Simulated L3 (Database equivalent)
	mu     sync.RWMutex
	stats  *CacheStats
}

// CacheStats tracks cache performance
type CacheStats struct {
	mu           sync.RWMutex
	L1Hits       int64
	L1Misses     int64
	L2Hits       int64
	L2Misses     int64
	L3Hits       int64
	L3Misses     int64
	TotalEvict   int64
}

// NewTieredCache creates a new 3-tier cache
func NewTieredCache(l1Size int) *TieredCache {
	return &TieredCache{
		l1:    NewL1Cache(l1Size),
		l2:    make(map[string]*CacheEntry),
		l3Map: make(map[string]*CacheEntry),
		stats: &CacheStats{},
	}
}

// Get retrieves value from cache hierarchy
func (tc *TieredCache) Get(ctx context.Context, key string) (interface{}, error) {
	// Try L1
	if val, ok := tc.l1.Get(key); ok {
		tc.stats.recordL1Hit()
		return val, nil
	}
	tc.stats.recordL1Miss()

	tc.mu.RLock()
	defer tc.mu.RUnlock()

	// Try L2
	if entry, ok := tc.l2[key]; ok && !entry.IsExpired() {
		tc.stats.recordL2Hit()
		// Promote to L1
		go tc.l1.Set(key, entry.Value, time.Until(entry.ExpiresAt))
		return entry.Value, nil
	}
	tc.stats.recordL2Miss()

	// Try L3
	if entry, ok := tc.l3Map[key]; ok && !entry.IsExpired() {
		tc.stats.recordL3Hit()
		// Promote to L1 and L2
		go tc.l1.Set(key, entry.Value, time.Until(entry.ExpiresAt))
		return entry.Value, nil
	}
	tc.stats.recordL3Miss()

	return nil, fmt.Errorf("key not found in cache hierarchy")
}

// Set stores value in cache hierarchy
func (tc *TieredCache) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	expiresAt := time.Now().Add(ttl)
	entry := &CacheEntry{
		Value:     value,
		ExpiresAt: expiresAt,
		CreatedAt: time.Now(),
	}

	// Store in all tiers
	tc.l1.Set(key, value, ttl)
	tc.l2[key] = entry
	tc.l3Map[key] = entry

	return nil
}

// Delete removes from all cache tiers
func (tc *TieredCache) Delete(ctx context.Context, key string) error {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	tc.l1.Delete(key)
	delete(tc.l2, key)
	delete(tc.l3Map, key)

	return nil
}

// InvalidateTier invalidates a specific cache tier
func (tc *TieredCache) InvalidateTier(level CacheLevel) error {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	switch level {
	case L1:
		tc.l1.Clear()
	case L2:
		tc.l2 = make(map[string]*CacheEntry)
	case L3:
		tc.l3Map = make(map[string]*CacheEntry)
	}
	return nil
}

// InvalidateAll clears all cache tiers
func (tc *TieredCache) InvalidateAll(ctx context.Context) error {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	tc.l1.Clear()
	tc.l2 = make(map[string]*CacheEntry)
	tc.l3Map = make(map[string]*CacheEntry)

	return nil
}

// GetStats returns cache performance statistics
func (tc *TieredCache) GetStats() map[string]interface{} {
	l1Stats := tc.l1.Stats()

	tc.mu.RLock()
	defer tc.mu.RUnlock()

	tc.stats.mu.RLock()
	defer tc.stats.mu.RUnlock()

	totalHits := tc.stats.L1Hits + tc.stats.L2Hits + tc.stats.L3Hits
	totalMisses := tc.stats.L1Misses + tc.stats.L2Misses + tc.stats.L3Misses
	hitRate := 0.0
	if totalHits+totalMisses > 0 {
		hitRate = float64(totalHits) / float64(totalHits+totalMisses)
	}

	return map[string]interface{}{
		"l1_stats":       l1Stats,
		"l2_size":        len(tc.l2),
		"l3_size":        len(tc.l3Map),
		"l1_hits":        tc.stats.L1Hits,
		"l1_misses":      tc.stats.L1Misses,
		"l2_hits":        tc.stats.L2Hits,
		"l2_misses":      tc.stats.L2Misses,
		"l3_hits":        tc.stats.L3Hits,
		"l3_misses":      tc.stats.L3Misses,
		"total_hits":     totalHits,
		"total_misses":   totalMisses,
		"hit_rate":       hitRate,
		"total_evictions": tc.stats.TotalEvict,
	}
}

// Stats helper methods
func (cs *CacheStats) recordL1Hit() {
	cs.mu.Lock()
	defer cs.mu.Unlock()
	cs.L1Hits++
}

func (cs *CacheStats) recordL1Miss() {
	cs.mu.Lock()
	defer cs.mu.Unlock()
	cs.L1Misses++
}

func (cs *CacheStats) recordL2Hit() {
	cs.mu.Lock()
	defer cs.mu.Unlock()
	cs.L2Hits++
}

func (cs *CacheStats) recordL2Miss() {
	cs.mu.Lock()
	defer cs.mu.Unlock()
	cs.L2Misses++
}

func (cs *CacheStats) recordL3Hit() {
	cs.mu.Lock()
	defer cs.mu.Unlock()
	cs.L3Hits++
}

func (cs *CacheStats) recordL3Miss() {
	cs.mu.Lock()
	defer cs.mu.Unlock()
	cs.L3Misses++
}

// BulkOperation represents a bulk operation
type BulkOperation struct {
	Operations []BulkOp
	ctx        context.Context
}

// BulkOp represents a single bulk operation
type BulkOp struct {
	Type  string      // "set", "delete", "get"
	Key   string
	Value interface{}
	TTL   time.Duration
}

// ExecuteBulk executes multiple cache operations atomically
func (tc *TieredCache) ExecuteBulk(ctx context.Context, ops []BulkOp) error {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	for _, op := range ops {
		switch op.Type {
		case "set":
			tc.l1.Set(op.Key, op.Value, op.TTL)
			tc.l2[op.Key] = &CacheEntry{
				Value:     op.Value,
				ExpiresAt: time.Now().Add(op.TTL),
				CreatedAt: time.Now(),
			}
		case "delete":
			tc.l1.Delete(op.Key)
			delete(tc.l2, op.Key)
		}
	}

	return nil
}
