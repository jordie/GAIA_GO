package metrics

import "sync"

// Metrics represents system metrics
type Metrics struct {
	mu sync.RWMutex

	// Request metrics
	RequestCount   int64
	AverageLatency float64
	ErrorCount     int64

	// Resource metrics
	CPUUsage    float64
	MemoryUsage float64
	DiskUsage   float64

	// Database metrics
	ConnectionsActive int64
	QueryCount        int64
	QueryErrors       int64

	// Cache metrics
	CacheHits   int64
	CacheMisses int64
}

// NewMetrics creates a new metrics instance
func NewMetrics() *Metrics {
	return &Metrics{}
}

// RecordRequest records a request metric
func (m *Metrics) RecordRequest(latency float64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.RequestCount++
	m.AverageLatency = (m.AverageLatency*float64(m.RequestCount-1) + latency) / float64(m.RequestCount)
}

// RecordError records an error metric
func (m *Metrics) RecordError() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.ErrorCount++
}

// GetMetrics returns current metrics
func (m *Metrics) GetMetrics() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return map[string]interface{}{
		"request_count":        m.RequestCount,
		"average_latency":      m.AverageLatency,
		"error_count":          m.ErrorCount,
		"cpu_usage":            m.CPUUsage,
		"memory_usage":         m.MemoryUsage,
		"disk_usage":           m.DiskUsage,
		"connections_active":   m.ConnectionsActive,
		"query_count":          m.QueryCount,
		"query_errors":         m.QueryErrors,
		"cache_hits":           m.CacheHits,
		"cache_misses":         m.CacheMisses,
	}
}
