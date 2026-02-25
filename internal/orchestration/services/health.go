package services

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os/exec"
	"sync"
	"time"
)

// HealthChecker monitors and reports service health status
type HealthChecker struct {
	service       *Service
	stopChan      chan struct{}
	stopOnce      sync.Once
	failureCount  int
	lastCheckTime *time.Time
}

// NewHealthChecker creates a new health checker for a service
func NewHealthChecker(service *Service) *HealthChecker {
	return &HealthChecker{
		service:  service,
		stopChan: make(chan struct{}),
	}
}

// StartMonitoring begins periodic health checks
func (hc *HealthChecker) StartMonitoring(ctx context.Context, coordinator *Coordinator) {
	if hc.service.HealthCheck == nil {
		return
	}

	// Wait for start delay if configured
	if hc.service.HealthCheck.StartDelay > 0 {
		select {
		case <-time.After(hc.service.HealthCheck.StartDelay):
		case <-hc.stopChan:
			return
		}
	}

	// Start periodic health checks
	interval := hc.service.HealthCheck.Interval
	if interval == 0 {
		interval = 30 * time.Second // Default interval
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-hc.stopChan:
			return
		case <-ticker.C:
			// Perform health check
			status, err := coordinator.HealthCheck(hc.service.ID)
			if err != nil {
				continue
			}

			if status.IsHealthy {
				hc.failureCount = 0
			} else {
				hc.failureCount++
				hc.lastCheckTime = status.LastCheckTime

				// Take action on repeated failures
				if hc.failureCount > hc.service.HealthCheck.Retries {
					if hc.service.AutoRestart {
						// Try to restart the service
						go func() {
							_ = coordinator.RestartService(context.Background(), hc.service.ID)
						}()
					}
				}
			}
		}
	}
}

// Stop stops monitoring health checks
func (hc *HealthChecker) Stop() {
	hc.stopOnce.Do(func() {
		close(hc.stopChan)
	})
}

// GetFailureCount returns the number of consecutive failures
func (hc *HealthChecker) GetFailureCount() int {
	return hc.failureCount
}

// ResetFailureCount resets the failure counter
func (hc *HealthChecker) ResetFailureCount() {
	hc.failureCount = 0
}

// HTTP Health Check Implementation

// HTTPHealthCheck performs an HTTP health check
func HTTPHealthCheck(endpoint string, timeout time.Duration) (bool, error) {
	client := &http.Client{
		Timeout: timeout,
	}

	resp, err := client.Get(endpoint)
	if err != nil {
		return false, fmt.Errorf("failed to reach endpoint: %w", err)
	}
	defer resp.Body.Close()

	// Consider 2xx and 3xx as healthy
	if resp.StatusCode >= 200 && resp.StatusCode < 400 {
		return true, nil
	}

	return false, fmt.Errorf("health check endpoint returned status %d", resp.StatusCode)
}

// TCP Health Check Implementation

// TCPHealthCheck performs a TCP connection health check
func TCPHealthCheck(host string, port int, timeout time.Duration) (bool, error) {
	address := fmt.Sprintf("%s:%d", host, port)

	conn, err := net.DialTimeout("tcp", address, timeout)
	if err != nil {
		return false, fmt.Errorf("failed to connect: %w", err)
	}
	defer conn.Close()

	return true, nil
}

// Exec Health Check Implementation

// ExecHealthCheck performs a health check by executing a command
func ExecHealthCheck(command string, timeout time.Duration) (bool, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "bash", "-c", command)
	err := cmd.Run()

	if err != nil {
		return false, fmt.Errorf("health check command failed: %w", err)
	}

	return true, nil
}

// HealthMonitor provides real-time health monitoring
type HealthMonitor struct {
	checks map[string]*HealthChecker
	mutex  sync.RWMutex
}

// NewHealthMonitor creates a new health monitor
func NewHealthMonitor() *HealthMonitor {
	return &HealthMonitor{
		checks: make(map[string]*HealthChecker),
	}
}

// RegisterChecker registers a health checker
func (hm *HealthMonitor) RegisterChecker(serviceID string, checker *HealthChecker) {
	hm.mutex.Lock()
	hm.checks[serviceID] = checker
	hm.mutex.Unlock()
}

// UnregisterChecker removes a health checker
func (hm *HealthMonitor) UnregisterChecker(serviceID string) {
	hm.mutex.Lock()
	delete(hm.checks, serviceID)
	hm.mutex.Unlock()
}

// GetHealthStatus returns the health status of all services
func (hm *HealthMonitor) GetHealthStatus() map[string]int {
	hm.mutex.RLock()
	defer hm.mutex.RUnlock()

	status := make(map[string]int)
	for serviceID, checker := range hm.checks {
		status[serviceID] = checker.GetFailureCount()
	}

	return status
}
