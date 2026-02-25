package cache

import (
	"fmt"
	"sync"
	"time"
)

// CacheEntry represents a cached value with TTL
type CacheEntry struct {
	Value     interface{}
	ExpiresAt time.Time
}

// IsExpired checks if the cache entry has expired
func (ce *CacheEntry) IsExpired() bool {
	return time.Now().After(ce.ExpiresAt)
}

// LocalCache implements an in-memory cache with TTL support
type LocalCache struct {
	data  map[string]*CacheEntry
	mu    sync.RWMutex
	stats CacheStats
}

// CacheStats tracks cache performance metrics
type CacheStats struct {
	Hits     int64
	Misses   int64
	Sets     int64
	Deletes  int64
	Expires  int64
	mu       sync.RWMutex
}

// HitRate returns the cache hit rate as a percentage
func (cs *CacheStats) HitRate() float64 {
	cs.mu.RLock()
	defer cs.mu.RUnlock()

	total := cs.Hits + cs.Misses
	if total == 0 {
		return 0
	}
	return float64(cs.Hits) / float64(total) * 100
}

// NewLocalCache creates a new in-memory cache
func NewLocalCache() *LocalCache {
	cache := &LocalCache{
		data: make(map[string]*CacheEntry),
	}

	// Start background cleanup goroutine
	go cache.cleanupExpired()

	return cache
}

// Get retrieves a value from the cache
func (lc *LocalCache) Get(key string) (interface{}, bool) {
	lc.mu.RLock()
	entry, exists := lc.data[key]
	lc.mu.RUnlock()

	if !exists {
		lc.stats.mu.Lock()
		lc.stats.Misses++
		lc.stats.mu.Unlock()
		return nil, false
	}

	if entry.IsExpired() {
		lc.mu.Lock()
		delete(lc.data, key)
		lc.mu.Unlock()

		lc.stats.mu.Lock()
		lc.stats.Expires++
		lc.stats.Misses++
		lc.stats.mu.Unlock()
		return nil, false
	}

	lc.stats.mu.Lock()
	lc.stats.Hits++
	lc.stats.mu.Unlock()

	return entry.Value, true
}

// Set stores a value in the cache with TTL
func (lc *LocalCache) Set(key string, value interface{}, ttl time.Duration) {
	lc.mu.Lock()
	lc.data[key] = &CacheEntry{
		Value:     value,
		ExpiresAt: time.Now().Add(ttl),
	}
	lc.mu.Unlock()

	lc.stats.mu.Lock()
	lc.stats.Sets++
	lc.stats.mu.Unlock()
}

// Delete removes a value from the cache
func (lc *LocalCache) Delete(key string) {
	lc.mu.Lock()
	delete(lc.data, key)
	lc.mu.Unlock()

	lc.stats.mu.Lock()
	lc.stats.Deletes++
	lc.stats.mu.Unlock()
}

// Clear removes all entries from the cache
func (lc *LocalCache) Clear() {
	lc.mu.Lock()
	lc.data = make(map[string]*CacheEntry)
	lc.mu.Unlock()
}

// Size returns the number of entries in the cache
func (lc *LocalCache) Size() int {
	lc.mu.RLock()
	defer lc.mu.RUnlock()
	return len(lc.data)
}

// Stats returns a copy of the cache statistics
func (lc *LocalCache) Stats() CacheStats {
	lc.stats.mu.RLock()
	defer lc.stats.mu.RUnlock()
	return lc.stats
}

// cleanupExpired periodically removes expired entries
func (lc *LocalCache) cleanupExpired() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		lc.mu.Lock()
		now := time.Now()
		for key, entry := range lc.data {
			if now.After(entry.ExpiresAt) {
				delete(lc.data, key)

				lc.stats.mu.Lock()
				lc.stats.Expires++
				lc.stats.mu.Unlock()
			}
		}
		lc.mu.Unlock()
	}
}

// CacheManager coordinates local and optional Redis caching
type CacheManager struct {
	local *LocalCache
	mu    sync.RWMutex
}

// NewCacheManager creates a new cache manager
func NewCacheManager() *CacheManager {
	return &CacheManager{
		local: NewLocalCache(),
	}
}

// Get retrieves a value from the cache hierarchy
func (cm *CacheManager) Get(key string) (interface{}, bool) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	// Try local cache first
	if val, ok := cm.local.Get(key); ok {
		return val, true
	}

	return nil, false
}

// Set stores a value in the cache hierarchy
func (cm *CacheManager) Set(key string, value interface{}, ttl time.Duration) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	cm.local.Set(key, value, ttl)
}

// Delete removes a value from the cache hierarchy
func (cm *CacheManager) Delete(key string) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	cm.local.Delete(key)
}

// Clear removes all entries from the cache
func (cm *CacheManager) Clear() {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	cm.local.Clear()
}

// Stats returns cache statistics
func (cm *CacheManager) Stats() CacheStats {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	return cm.local.Stats()
}

// Size returns the number of entries in the cache
func (cm *CacheManager) Size() int {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	return cm.local.Size()
}

// CacheKey helper functions for generating cache keys
func CacheKeyUser(id string) string {
	return fmt.Sprintf("user:%s", id)
}

func CacheKeyProject(id string) string {
	return fmt.Sprintf("project:%s", id)
}

func CacheKeyTask(id string) string {
	return fmt.Sprintf("task:%s", id)
}

func CacheKeyUserList() string {
	return "users:list"
}

func CacheKeyProjectList() string {
	return "projects:list"
}

func CacheKeyTaskList() string {
	return "tasks:list"
}

// CacheTTL constants define TTL for different data types
const (
	// UserCacheTTL: Users change infrequently
	UserCacheTTL = 1 * time.Hour

	// ProjectCacheTTL: Projects may change during sprint
	ProjectCacheTTL = 30 * time.Minute

	// TaskCacheTTL: Tasks change frequently
	TaskCacheTTL = 5 * time.Minute

	// ListCacheTTL: Lists are smaller and change less frequently
	ListCacheTTL = 10 * time.Minute

	// SessionCacheTTL: Sessions expire based on auth duration
	SessionCacheTTL = 24 * time.Hour
)
