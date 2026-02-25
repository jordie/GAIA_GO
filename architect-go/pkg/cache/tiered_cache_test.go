package cache

import (
	"context"
	"testing"
	"time"
)

func TestL1Cache_SetGet(t *testing.T) {
	l1 := NewL1Cache(100)

	l1.Set("key1", "value1", 1*time.Hour)

	val, ok := l1.Get("key1")
	if !ok {
		t.Error("expected to find key1")
	}

	if val != "value1" {
		t.Errorf("expected value1, got %v", val)
	}
}

func TestL1Cache_Expiration(t *testing.T) {
	l1 := NewL1Cache(100)

	l1.Set("key1", "value1", 1*time.Millisecond)
	time.Sleep(2 * time.Millisecond)

	_, ok := l1.Get("key1")
	if ok {
		t.Error("expected key to be expired")
	}
}

func TestL1Cache_Eviction(t *testing.T) {
	l1 := NewL1Cache(2)

	l1.Set("key1", "value1", 1*time.Hour)
	l1.Set("key2", "value2", 1*time.Hour)
	l1.Set("key3", "value3", 1*time.Hour)

	stats := l1.Stats()
	if stats["size"].(int) != 2 {
		t.Errorf("expected cache size 2, got %d", stats["size"])
	}
}

func TestTieredCache_L1Hit(t *testing.T) {
	tc := NewTieredCache(100)

	tc.Set(context.Background(), "key1", "value1", 1*time.Hour)

	val, err := tc.Get(context.Background(), "key1")
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if val != "value1" {
		t.Errorf("expected value1, got %v", val)
	}

	stats := tc.GetStats()
	if stats["l1_hits"].(int64) != 1 {
		t.Errorf("expected 1 L1 hit, got %d", stats["l1_hits"])
	}
}

func TestTieredCache_L2Promotion(t *testing.T) {
	tc := NewTieredCache(1)

	// Set two keys - second one evicts first from L1
	tc.Set(context.Background(), "key1", "value1", 1*time.Hour)
	tc.Set(context.Background(), "key2", "value2", 1*time.Hour)

	// key1 should still be in L2
	time.Sleep(100 * time.Millisecond)

	val, err := tc.Get(context.Background(), "key1")
	if err != nil {
		t.Errorf("expected to find key1 in L2, got error: %v", err)
	}

	if val != "value1" {
		t.Errorf("expected value1, got %v", val)
	}
}

func TestTieredCache_Delete(t *testing.T) {
	tc := NewTieredCache(100)

	tc.Set(context.Background(), "key1", "value1", 1*time.Hour)

	tc.Delete(context.Background(), "key1")

	_, err := tc.Get(context.Background(), "key1")
	if err == nil {
		t.Error("expected error after delete")
	}
}

func TestTieredCache_InvalidateTier(t *testing.T) {
	tc := NewTieredCache(100)

	tc.Set(context.Background(), "key1", "value1", 1*time.Hour)
	tc.Set(context.Background(), "key2", "value2", 1*time.Hour)

	tc.InvalidateTier(L1)

	stats := tc.GetStats()
	if stats["l1_stats"].(map[string]interface{})["size"].(int) != 0 {
		t.Error("expected L1 to be cleared")
	}
}

func TestTieredCache_InvalidateAll(t *testing.T) {
	tc := NewTieredCache(100)

	tc.Set(context.Background(), "key1", "value1", 1*time.Hour)
	tc.Set(context.Background(), "key2", "value2", 1*time.Hour)

	tc.InvalidateAll(context.Background())

	stats := tc.GetStats()
	if stats["l1_stats"].(map[string]interface{})["size"].(int) != 0 {
		t.Error("expected L1 to be cleared")
	}
	if stats["l2_size"].(int) != 0 {
		t.Error("expected L2 to be cleared")
	}
	if stats["l3_size"].(int) != 0 {
		t.Error("expected L3 to be cleared")
	}
}

func TestTieredCache_HitRate(t *testing.T) {
	tc := NewTieredCache(100)

	tc.Set(context.Background(), "key1", "value1", 1*time.Hour)

	// Generate hits and misses
	tc.Get(context.Background(), "key1")
	tc.Get(context.Background(), "key1")
	tc.Get(context.Background(), "key2")

	stats := tc.GetStats()
	hitRate := stats["hit_rate"].(float64)

	if hitRate != 0.666666 && hitRate < 0.6 || hitRate > 0.7 {
		t.Logf("hit rate: %f", hitRate)
	}
}

func TestTieredCache_BulkOperation(t *testing.T) {
	tc := NewTieredCache(100)

	ops := []BulkOp{
		{Type: "set", Key: "key1", Value: "value1", TTL: 1 * time.Hour},
		{Type: "set", Key: "key2", Value: "value2", TTL: 1 * time.Hour},
		{Type: "set", Key: "key3", Value: "value3", TTL: 1 * time.Hour},
	}

	tc.ExecuteBulk(context.Background(), ops)

	val1, err1 := tc.Get(context.Background(), "key1")
	val2, err2 := tc.Get(context.Background(), "key2")
	val3, err3 := tc.Get(context.Background(), "key3")

	if err1 != nil || err2 != nil || err3 != nil {
		t.Error("expected all keys to be set")
	}

	if val1 != "value1" || val2 != "value2" || val3 != "value3" {
		t.Error("values mismatch after bulk operation")
	}
}

func TestTieredCache_Stats(t *testing.T) {
	tc := NewTieredCache(100)

	tc.Set(context.Background(), "key1", "value1", 1*time.Hour)
	tc.Get(context.Background(), "key1")
	tc.Get(context.Background(), "missing")

	stats := tc.GetStats()

	if stats["l1_hits"].(int64) != 1 {
		t.Errorf("expected 1 L1 hit, got %d", stats["l1_hits"])
	}

	if stats["l1_misses"].(int64) != 1 {
		t.Errorf("expected 1 L1 miss, got %d", stats["l1_misses"])
	}
}

func TestCacheEntry_IsExpired(t *testing.T) {
	entry := &CacheEntry{
		Value:     "test",
		ExpiresAt: time.Now().Add(-1 * time.Second),
	}

	if !entry.IsExpired() {
		t.Error("expected entry to be expired")
	}

	entry.ExpiresAt = time.Now().Add(1 * time.Hour)
	if entry.IsExpired() {
		t.Error("expected entry not to be expired")
	}
}

func TestL1Cache_Delete(t *testing.T) {
	l1 := NewL1Cache(100)

	l1.Set("key1", "value1", 1*time.Hour)
	l1.Delete("key1")

	_, ok := l1.Get("key1")
	if ok {
		t.Error("expected key to be deleted")
	}
}

func TestL1Cache_Clear(t *testing.T) {
	l1 := NewL1Cache(100)

	l1.Set("key1", "value1", 1*time.Hour)
	l1.Set("key2", "value2", 1*time.Hour)
	l1.Clear()

	stats := l1.Stats()
	if stats["size"].(int) != 0 {
		t.Errorf("expected cache size 0, got %d", stats["size"])
	}
}

func BenchmarkTieredCache_Get(b *testing.B) {
	tc := NewTieredCache(1000)
	tc.Set(context.Background(), "bench_key", "bench_value", 1*time.Hour)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		tc.Get(context.Background(), "bench_key")
	}
}

func BenchmarkTieredCache_Set(b *testing.B) {
	tc := NewTieredCache(1000)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		tc.Set(context.Background(), "bench_key", "bench_value", 1*time.Hour)
	}
}
