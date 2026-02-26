package rate_limiting

import (
	"runtime"
	"time"
)

// ThrottleThresholds defines CPU/memory thresholds for throttling
type ThrottleThresholds struct {
	CPULow          float64 // <this: no throttling
	CPUMedium       float64 // <this: 80% speed
	CPUHigh         float64 // <this: 60% speed
	CPUVeryHigh     float64 // <this: 30% speed
	CPUCritical     float64 // >=this: blocked

	MemoryLow       float64
	MemoryMedium    float64
	MemoryHigh      float64
	MemoryVeryHigh  float64
	MemoryCritical  float64
}

// DefaultThrottleThresholds returns sensible defaults
func DefaultThrottleThresholds() ThrottleThresholds {
	return ThrottleThresholds{
		CPULow:         70.0,
		CPUMedium:      80.0,
		CPUHigh:        90.0,
		CPUVeryHigh:    95.0,
		CPUCritical:    98.0,
		MemoryLow:      75.0,
		MemoryMedium:   85.0,
		MemoryHigh:     90.0,
		MemoryVeryHigh: 95.0,
		MemoryCritical: 98.0,
	}
}

// ResourceMonitor tracks system resources and determines throttle factors
type ResourceMonitor struct {
	thresholds      ThrottleThresholds
	lastCPU         float64
	lastMemory      float64
	lastSampled     time.Time
	sampleInterval  time.Duration
}

// NewResourceMonitor creates a new resource monitor
func NewResourceMonitor() *ResourceMonitor {
	return &ResourceMonitor{
		thresholds:     DefaultThrottleThresholds(),
		sampleInterval: 5 * time.Second,
	}
}

// GetSystemCPUPercent returns current CPU usage percentage
func (rm *ResourceMonitor) GetSystemCPUPercent() float64 {
	// For now, return cached value
	// In production, this would use psutil or similar
	// For testing, return a simulated value
	return rm.lastCPU
}

// GetSystemMemoryPercent returns current memory usage percentage
func (rm *ResourceMonitor) GetSystemMemoryPercent() float64 {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	// Calculate memory usage percentage
	// Total allocatable memory is typically the heap limit or system memory
	totalMem := float64(m.Alloc) + float64(m.TotalAlloc)
	if totalMem == 0 {
		return 0
	}

	// Return percentage based on allocation
	// In production, this would be system memory percentage
	return rm.lastMemory
}

// UpdateMetrics updates the cached metrics
// This should be called periodically from a background goroutine
func (rm *ResourceMonitor) UpdateMetrics(cpuPercent float64, memPercent float64) {
	rm.lastCPU = cpuPercent
	rm.lastMemory = memPercent
	rm.lastSampled = time.Now()
}

// GetThrottleMultiplier returns a multiplier (0.0-1.0) based on system load
// 1.0 = no throttling, 0.0 = completely blocked
func (rm *ResourceMonitor) GetThrottleMultiplier() float64 {
	cpu := rm.GetSystemCPUPercent()
	mem := rm.GetSystemMemoryPercent()

	// Determine throttle factor based on CPU
	cpuFactor := rm.getThrottleFactorForCPU(cpu)

	// Determine throttle factor based on memory
	memFactor := rm.getThrottleFactorForMemory(mem)

	// Return the minimum (most restrictive) of the two
	if cpuFactor < memFactor {
		return cpuFactor
	}
	return memFactor
}

// ShouldThrottleCommands returns true if commands should be throttled
func (rm *ResourceMonitor) ShouldThrottleCommands() bool {
	return rm.GetThrottleMultiplier() < 1.0
}

// GetThrottleReason returns a human-readable reason for throttling
func (rm *ResourceMonitor) GetThrottleReason() string {
	cpu := rm.GetSystemCPUPercent()
	mem := rm.GetSystemMemoryPercent()

	if cpu >= rm.thresholds.CPUCritical {
		return "CPU usage critical (>98%)"
	}
	if cpu >= rm.thresholds.CPUVeryHigh {
		return "CPU usage very high (>95%)"
	}
	if cpu >= rm.thresholds.CPUHigh {
		return "CPU usage high (>90%)"
	}
	if cpu >= rm.thresholds.CPUMedium {
		return "CPU usage elevated (>80%)"
	}

	if mem >= rm.thresholds.MemoryCritical {
		return "Memory usage critical (>98%)"
	}
	if mem >= rm.thresholds.MemoryVeryHigh {
		return "Memory usage very high (>95%)"
	}
	if mem >= rm.thresholds.MemoryHigh {
		return "Memory usage high (>90%)"
	}
	if mem >= rm.thresholds.MemoryMedium {
		return "Memory usage elevated (>85%)"
	}

	return ""
}

// Helper methods

func (rm *ResourceMonitor) getThrottleFactorForCPU(cpuPercent float64) float64 {
	switch {
	case cpuPercent >= rm.thresholds.CPUCritical:
		return 0.0 // Blocked
	case cpuPercent >= rm.thresholds.CPUVeryHigh:
		return 0.3 // 30% speed
	case cpuPercent >= rm.thresholds.CPUHigh:
		return 0.6 // 60% speed
	case cpuPercent >= rm.thresholds.CPUMedium:
		return 0.8 // 80% speed
	default:
		return 1.0 // Full speed
	}
}

func (rm *ResourceMonitor) getThrottleFactorForMemory(memPercent float64) float64 {
	switch {
	case memPercent >= rm.thresholds.MemoryCritical:
		return 0.0 // Blocked
	case memPercent >= rm.thresholds.MemoryVeryHigh:
		return 0.3 // 30% speed
	case memPercent >= rm.thresholds.MemoryHigh:
		return 0.6 // 60% speed
	case memPercent >= rm.thresholds.MemoryMedium:
		return 0.8 // 80% speed
	default:
		return 1.0 // Full speed
	}
}
