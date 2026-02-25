package api

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/pprof"
	"runtime"
	"runtime/debug"
	runtimepprof "runtime/pprof"
	"strconv"
	"sync"
	"time"
)

// SystemMetricsSampler collects time-series samples of system-level performance metrics
// (distinct from MetricsCollector which handles agent-level application metrics)
type SystemMetricsSampler struct {
	samples    []MetricSample
	mu         sync.RWMutex
	maxSamples int
}

// MetricSample represents a point-in-time snapshot of metrics
type MetricSample struct {
	Timestamp   time.Time     `json:"timestamp"`
	Memory      MemoryMetrics `json:"memory"`
	CPU         CPUMetrics    `json:"cpu"`
	Goroutines  int           `json:"goroutines"`
	GC          GCMetrics     `json:"gc"`
	RequestRate float64       `json:"request_rate"`
	ErrorRate   float64       `json:"error_rate"`
}

// MemoryMetrics contains memory-related metrics
type MemoryMetrics struct {
	Alloc        uint64  `json:"alloc"`          // Bytes allocated and in use
	TotalAlloc   uint64  `json:"total_alloc"`    // Cumulative bytes allocated
	Sys          uint64  `json:"sys"`            // Bytes from system
	HeapAlloc    uint64  `json:"heap_alloc"`     // Heap bytes allocated
	HeapSys      uint64  `json:"heap_sys"`       // Heap bytes from system
	HeapInuse    uint64  `json:"heap_inuse"`     // Heap bytes in use
	HeapReleased uint64  `json:"heap_released"`  // Heap bytes released to OS
	StackInuse   uint64  `json:"stack_inuse"`    // Stack bytes in use
	StackSys     uint64  `json:"stack_sys"`      // Stack bytes from system
	UsagePercent float64 `json:"usage_percent"`  // Heap usage percentage
}

// CPUMetrics contains CPU-related metrics
type CPUMetrics struct {
	NumCPU     int     `json:"num_cpu"`
	NumCgoCall int64   `json:"num_cgo_call"`
	GOMAXPROCS int     `json:"gomaxprocs"`
}

// GCMetrics contains garbage collection metrics
type GCMetrics struct {
	NumGC          uint32  `json:"num_gc"`
	LastPause      uint64  `json:"last_pause"`      // Nanoseconds
	PauseTotal     uint64  `json:"pause_total"`     // Nanoseconds
	GCCPUFraction  float64 `json:"gc_cpu_fraction"`
	NextGC         uint64  `json:"next_gc"`
}

// ProfilingAPI handles performance profiling endpoints
type ProfilingAPI struct {
	metrics      *SystemMetricsSampler
	mu           sync.RWMutex
	startTime    time.Time
	requestCount int64
	errorCount   int64
}

// NewProfilingAPI creates a new profiling API handler
func NewProfilingAPI() *ProfilingAPI {
	api := &ProfilingAPI{
		metrics:   NewSystemMetricsSampler(60), // Keep 60 samples (2 minutes at 2s intervals)
		startTime: time.Now(),
	}

	// Start background metrics collection
	go api.collectMetricsPeriodically(2 * time.Second)

	return api
}

// NewSystemMetricsSampler creates a new metrics collector
func NewSystemMetricsSampler(maxSamples int) *SystemMetricsSampler {
	return &SystemMetricsSampler{
		samples:    make([]MetricSample, 0, maxSamples),
		maxSamples: maxSamples,
	}
}

// collectMetricsPeriodically collects metrics in the background
func (api *ProfilingAPI) collectMetricsPeriodically(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for range ticker.C {
		sample := api.collectCurrentMetrics()
		api.metrics.AddSample(sample)
	}
}

// collectCurrentMetrics gathers current system metrics
func (api *ProfilingAPI) collectCurrentMetrics() MetricSample {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	var gcStats debug.GCStats
	debug.ReadGCStats(&gcStats)

	api.mu.RLock()
	uptime := time.Since(api.startTime).Seconds()
	reqRate := float64(api.requestCount) / uptime
	errRate := float64(api.errorCount) / uptime
	api.mu.RUnlock()

	var lastPause uint64
	if len(gcStats.Pause) > 0 {
		lastPause = uint64(gcStats.Pause[0])
	}

	usagePercent := 0.0
	if m.HeapSys > 0 {
		usagePercent = (float64(m.HeapAlloc) / float64(m.HeapSys)) * 100
	}

	return MetricSample{
		Timestamp: time.Now(),
		Memory: MemoryMetrics{
			Alloc:        m.Alloc,
			TotalAlloc:   m.TotalAlloc,
			Sys:          m.Sys,
			HeapAlloc:    m.HeapAlloc,
			HeapSys:      m.HeapSys,
			HeapInuse:    m.HeapInuse,
			HeapReleased: m.HeapReleased,
			StackInuse:   m.StackInuse,
			StackSys:     m.StackSys,
			UsagePercent: usagePercent,
		},
		CPU: CPUMetrics{
			NumCPU:     runtime.NumCPU(),
			NumCgoCall: runtime.NumCgoCall(),
			GOMAXPROCS: runtime.GOMAXPROCS(0),
		},
		Goroutines: runtime.NumGoroutine(),
		GC: GCMetrics{
			NumGC:         m.NumGC,
			LastPause:     lastPause,
			PauseTotal:    uint64(gcStats.PauseTotal.Nanoseconds()),
			GCCPUFraction: m.GCCPUFraction,
			NextGC:        m.NextGC,
		},
		RequestRate: reqRate,
		ErrorRate:   errRate,
	}
}

// AddSample adds a metric sample to the collector
func (pmc *SystemMetricsSampler) AddSample(sample MetricSample) {
	pmc.mu.Lock()
	defer pmc.mu.Unlock()

	pmc.samples = append(pmc.samples, sample)

	// Keep only maxSamples
	if len(pmc.samples) > pmc.maxSamples {
		pmc.samples = pmc.samples[1:]
	}
}

// GetSamples returns all stored samples
func (pmc *SystemMetricsSampler) GetSamples() []MetricSample {
	pmc.mu.RLock()
	defer pmc.mu.RUnlock()

	result := make([]MetricSample, len(pmc.samples))
	copy(result, pmc.samples)
	return result
}

// GetLatestSample returns the most recent sample
func (pmc *SystemMetricsSampler) GetLatestSample() *MetricSample {
	pmc.mu.RLock()
	defer pmc.mu.RUnlock()

	if len(pmc.samples) == 0 {
		return nil
	}

	sample := pmc.samples[len(pmc.samples)-1]
	return &sample
}

// RegisterProfilingRoutes registers all profiling endpoints
func (api *ProfilingAPI) RegisterProfilingRoutes(mux *http.ServeMux) {
	// Metrics endpoints
	mux.HandleFunc("/api/profiling/metrics", api.handleMetrics)
	mux.HandleFunc("/api/profiling/memory", api.handleMemory)
	mux.HandleFunc("/api/profiling/gc", api.handleGC)
	mux.HandleFunc("/api/profiling/goroutines", api.handleGoroutines)
	mux.HandleFunc("/api/profiling/runtime", api.handleRuntime)
	mux.HandleFunc("/api/profiling/health", api.handleHealth)

	// Profiling actions
	mux.HandleFunc("/api/profiling/heap-dump", api.handleHeapDump)
	mux.HandleFunc("/api/profiling/cpu-profile", api.handleCPUProfile)
	mux.HandleFunc("/api/profiling/force-gc", api.handleForceGC)

	// Standard pprof endpoints
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)

	log.Println("Profiling API routes registered")
}

// handleMetrics returns current metrics snapshot
func (api *ProfilingAPI) handleMetrics(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	latest := api.metrics.GetLatestSample()
	if latest == nil {
		latest = &MetricSample{Timestamp: time.Now()}
	}

	api.mu.RLock()
	uptime := time.Since(api.startTime).Seconds()
	api.mu.RUnlock()

	response := map[string]interface{}{
		"metrics": latest,
		"uptime":  uptime,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleMemory returns memory-specific metrics
func (api *ProfilingAPI) handleMemory(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	usagePercent := 0.0
	if m.HeapSys > 0 {
		usagePercent = (float64(m.HeapAlloc) / float64(m.HeapSys)) * 100
	}

	memory := MemoryMetrics{
		Alloc:        m.Alloc,
		TotalAlloc:   m.TotalAlloc,
		Sys:          m.Sys,
		HeapAlloc:    m.HeapAlloc,
		HeapSys:      m.HeapSys,
		HeapInuse:    m.HeapInuse,
		HeapReleased: m.HeapReleased,
		StackInuse:   m.StackInuse,
		StackSys:     m.StackSys,
		UsagePercent: usagePercent,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(memory)
}

// handleGC returns garbage collection metrics
func (api *ProfilingAPI) handleGC(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	var gcStats debug.GCStats
	debug.ReadGCStats(&gcStats)

	var lastPause uint64
	if len(gcStats.Pause) > 0 {
		lastPause = uint64(gcStats.Pause[0])
	}

	gc := GCMetrics{
		NumGC:         m.NumGC,
		LastPause:     lastPause,
		PauseTotal:    uint64(gcStats.PauseTotal),
		GCCPUFraction: m.GCCPUFraction,
		NextGC:        m.NextGC,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(gc)
}

// handleGoroutines returns goroutine information
func (api *ProfilingAPI) handleGoroutines(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	count := runtime.NumGoroutine()

	// Get stack trace
	buf := make([]byte, 1<<20) // 1MB buffer
	stackLen := runtime.Stack(buf, true)
	stackTrace := string(buf[:stackLen])

	response := map[string]interface{}{
		"count":       count,
		"stack_trace": stackTrace,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleRuntime returns general runtime information
func (api *ProfilingAPI) handleRuntime(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	api.mu.RLock()
	uptime := time.Since(api.startTime).Seconds()
	api.mu.RUnlock()

	response := map[string]interface{}{
		"go_version":   runtime.Version(),
		"go_os":        runtime.GOOS,
		"go_arch":      runtime.GOARCH,
		"num_cpu":      runtime.NumCPU(),
		"gomaxprocs":   runtime.GOMAXPROCS(0),
		"num_cgo_call": runtime.NumCgoCall(),
		"compiler":     runtime.Compiler,
		"uptime":       uptime,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleHealth returns system health status
func (api *ProfilingAPI) handleHealth(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	latest := api.metrics.GetLatestSample()
	if latest == nil {
		http.Error(w, "No metrics available", http.StatusServiceUnavailable)
		return
	}

	// Health thresholds
	const (
		maxGoroutines     = 1000
		maxMemoryPercent  = 90.0
		maxGCPauseMs      = 100.0
	)

	status := "healthy"
	issues := []string{}

	// Check goroutine count
	if latest.Goroutines > maxGoroutines {
		status = "degraded"
		issues = append(issues, fmt.Sprintf("High goroutine count: %d", latest.Goroutines))
	}

	// Check memory usage
	if latest.Memory.UsagePercent > maxMemoryPercent {
		status = "unhealthy"
		issues = append(issues, fmt.Sprintf("High memory usage: %.1f%%", latest.Memory.UsagePercent))
	}

	// Check GC pause time
	pauseMs := float64(latest.GC.LastPause) / 1e6
	if pauseMs > maxGCPauseMs {
		if status == "healthy" {
			status = "degraded"
		}
		issues = append(issues, fmt.Sprintf("High GC pause: %.2fms", pauseMs))
	}

	response := map[string]interface{}{
		"status": status,
		"issues": issues,
		"checks": map[string]interface{}{
			"goroutines":      latest.Goroutines,
			"memory_percent":  latest.Memory.UsagePercent,
			"gc_pause_ms":     pauseMs,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleHeapDump generates and serves a heap dump
func (api *ProfilingAPI) handleHeapDump(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=heap_%d.prof", time.Now().Unix()))

	runtime.GC() // Force GC before dump for accurate data
	runtimepprof.Lookup("heap").WriteTo(w, 0)
}

// handleCPUProfile generates and serves a CPU profile
func (api *ProfilingAPI) handleCPUProfile(w http.ResponseWriter, r *http.Request) {
	api.trackRequest()

	// Get duration from query params (default 30 seconds)
	durationStr := r.URL.Query().Get("duration")
	duration := 30
	if durationStr != "" {
		if d, err := strconv.Atoi(durationStr); err == nil {
			duration = d
		}
	}

	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=cpu_%d.prof", time.Now().Unix()))

	runtimepprof.StartCPUProfile(w)
	time.Sleep(time.Duration(duration) * time.Second)
	runtimepprof.StopCPUProfile()
}

// handleForceGC forces a garbage collection
func (api *ProfilingAPI) handleForceGC(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	api.trackRequest()

	var beforeMem runtime.MemStats
	runtime.ReadMemStats(&beforeMem)

	startTime := time.Now()
	runtime.GC()
	duration := time.Since(startTime)

	var afterMem runtime.MemStats
	runtime.ReadMemStats(&afterMem)

	response := map[string]interface{}{
		"gc_duration_ms":  duration.Milliseconds(),
		"heap_before_mb":  float64(beforeMem.HeapAlloc) / 1024 / 1024,
		"heap_after_mb":   float64(afterMem.HeapAlloc) / 1024 / 1024,
		"heap_freed_mb":   float64(beforeMem.HeapAlloc-afterMem.HeapAlloc) / 1024 / 1024,
		"heap_alloc_mb":   float64(afterMem.HeapAlloc) / 1024 / 1024,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// trackRequest increments request counter
func (api *ProfilingAPI) trackRequest() {
	api.mu.Lock()
	defer api.mu.Unlock()
	api.requestCount++
}

// trackError increments error counter
func (api *ProfilingAPI) trackError() {
	api.mu.Lock()
	defer api.mu.Unlock()
	api.errorCount++
}
