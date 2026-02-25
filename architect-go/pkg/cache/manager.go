package cache

import (
	"context"
	"sync"
	"time"
)

// CacheManager coordinates caching across all tiers
type CacheManager struct {
	tieredCache *TieredCache
	mu          sync.RWMutex
	strategies  map[string]CacheStrategy
}

// CacheStrategy defines caching behavior for different data types
type CacheStrategy interface {
	GetTTL() time.Duration
	ShouldCache(key string, value interface{}) bool
}

// DefaultStrategy provides default caching configuration
type DefaultStrategy struct {
	TTL time.Duration
}

// GetTTL returns the TTL for this strategy
func (ds *DefaultStrategy) GetTTL() time.Duration {
	return ds.TTL
}

// ShouldCache determines if a value should be cached
func (ds *DefaultStrategy) ShouldCache(key string, value interface{}) bool {
	return value != nil && key != ""
}

// NewCacheManager creates a new cache manager
func NewCacheManager() *CacheManager {
	return &CacheManager{
		tieredCache: NewTieredCache(1000),
		strategies:  make(map[string]CacheStrategy),
	}
}

// Get retrieves a value from cache
func (cm *CacheManager) Get(ctx context.Context, key string) (interface{}, error) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return cm.tieredCache.Get(ctx, key)
}

// Set stores a value in cache with default TTL
func (cm *CacheManager) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	return cm.tieredCache.Set(ctx, key, value, ttl)
}

// Delete removes a value from cache
func (cm *CacheManager) Delete(ctx context.Context, key string) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	return cm.tieredCache.Delete(ctx, key)
}

// InvalidateAll clears all cache tiers
func (cm *CacheManager) InvalidateAll(ctx context.Context) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	return cm.tieredCache.InvalidateAll(ctx)
}

// GetStats returns cache statistics
func (cm *CacheManager) GetStats() map[string]interface{} {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return cm.tieredCache.GetStats()
}

// RegisterStrategy registers a caching strategy for a key pattern
func (cm *CacheManager) RegisterStrategy(pattern string, strategy CacheStrategy) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	cm.strategies[pattern] = strategy
}

// GetStrategy retrieves a caching strategy for a key
func (cm *CacheManager) GetStrategy(key string) CacheStrategy {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	if strategy, ok := cm.strategies[key]; ok {
		return strategy
	}
	// Return default strategy
	return &DefaultStrategy{TTL: 1 * time.Hour}
}

// CacheWithStrategy stores a value using a specific strategy
func (cm *CacheManager) CacheWithStrategy(ctx context.Context, key string, value interface{}, strategyKey string) error {
	strategy := cm.GetStrategy(strategyKey)
	if !strategy.ShouldCache(key, value) {
		return nil
	}
	return cm.Set(ctx, key, value, strategy.GetTTL())
}
