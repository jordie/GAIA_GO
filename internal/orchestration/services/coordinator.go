package services

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// Coordinator manages the lifecycle of multiple services
type Coordinator struct {
	db             *sql.DB
	services       map[string]*Service
	serviceMutex   sync.RWMutex
	healthCheckers map[string]*HealthChecker
	healthMutex    sync.RWMutex
	maxServices    int
	closeOnce      sync.Once
	closeChan      chan struct{}
}

// NewCoordinator creates a new service coordinator
func NewCoordinator(db *sql.DB, maxServices int) *Coordinator {
	coordinator := &Coordinator{
		db:             db,
		services:       make(map[string]*Service),
		healthCheckers: make(map[string]*HealthChecker),
		maxServices:    maxServices,
		closeChan:      make(chan struct{}),
	}

	// Restore services from database on startup
	if err := coordinator.restoreServices(context.Background()); err != nil {
		fmt.Printf("warning: failed to restore services from database: %v\n", err)
	}

	return coordinator
}

// RegisterService registers and prepares a service for management
func (c *Coordinator) RegisterService(config ServiceConfig) (*Service, error) {
	c.serviceMutex.Lock()
	defer c.serviceMutex.Unlock()

	if len(c.services) >= c.maxServices {
		return nil, fmt.Errorf("service limit reached (%d)", c.maxServices)
	}

	// Create service object
	service := &Service{
		ID:          uuid.New().String(),
		Name:        config.Name,
		Type:        config.Type,
		Command:     config.Command,
		Args:        config.Args,
		WorkDir:     config.WorkDir,
		Port:        config.Port,
		Status:      ServiceStatusStopped,
		Environment: config.Environment,
		HealthCheck: config.HealthCheck,
		AutoRestart: config.AutoRestart,
		Metadata:    config.Metadata,
		CreatedAt:   time.Now(),
	}

	// Persist to database
	if err := c.persistService(service); err != nil {
		return nil, fmt.Errorf("failed to persist service: %w", err)
	}

	// Add to registry
	c.services[service.ID] = service

	// Initialize health checker if needed
	if service.HealthCheck != nil && service.HealthCheck.Type != HealthCheckTypeNone {
		checker := NewHealthChecker(service)
		c.healthMutex.Lock()
		c.healthCheckers[service.ID] = checker
		c.healthMutex.Unlock()
	}

	return service, nil
}

// UnregisterService removes a service from management
func (c *Coordinator) UnregisterService(serviceID string) error {
	c.serviceMutex.Lock()
	service, exists := c.services[serviceID]
	if !exists {
		c.serviceMutex.Unlock()
		return fmt.Errorf("service not found: %s", serviceID)
	}
	delete(c.services, serviceID)
	c.serviceMutex.Unlock()

	// Stop service if running
	if service.Status == ServiceStatusRunning {
		_ = c.StopService(serviceID, true)
	}

	// Remove health checker
	c.healthMutex.Lock()
	delete(c.healthCheckers, serviceID)
	c.healthMutex.Unlock()

	// Remove from database
	_, _ = c.db.Exec("DELETE FROM gaia_services WHERE id = ?", serviceID)

	return nil
}

// GetService retrieves a service by ID
func (c *Coordinator) GetService(serviceID string) (*Service, error) {
	c.serviceMutex.RLock()
	service, exists := c.services[serviceID]
	c.serviceMutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("service not found: %s", serviceID)
	}

	return service, nil
}

// ListServices returns all registered services
func (c *Coordinator) ListServices() ([]*Service, error) {
	c.serviceMutex.RLock()
	defer c.serviceMutex.RUnlock()

	services := make([]*Service, 0, len(c.services))
	for _, service := range c.services {
		services = append(services, service)
	}

	return services, nil
}

// StartService starts a service
func (c *Coordinator) StartService(ctx context.Context, serviceID string) error {
	service, err := c.GetService(serviceID)
	if err != nil {
		return err
	}

	if service.Status == ServiceStatusRunning {
		return fmt.Errorf("service is already running")
	}

	// Update status
	service.Status = ServiceStatusStarting
	now := time.Now()
	service.StartedAt = &now
	c.persistService(service)

	// Start the service using ProcessManager (integrated in Component 4)
	// For now, placeholder implementation
	service.ProcessID = 12345 // Would be real PID from ProcessManager
	service.Status = ServiceStatusRunning
	service.Restarts++

	// Persist updated service
	if err := c.persistService(service); err != nil {
		service.Status = ServiceStatusFailed
		service.Error = err.Error()
		c.persistService(service)
		return fmt.Errorf("failed to start service: %w", err)
	}

	// Start health checker if configured
	if service.HealthCheck != nil {
		checker := NewHealthChecker(service)
		c.healthMutex.Lock()
		c.healthCheckers[serviceID] = checker
		c.healthMutex.Unlock()

		go checker.StartMonitoring(ctx, c)
	}

	return nil
}

// StopService stops a running service
func (c *Coordinator) StopService(serviceID string, graceful bool) error {
	service, err := c.GetService(serviceID)
	if err != nil {
		return err
	}

	if service.Status == ServiceStatusStopped {
		return fmt.Errorf("service is not running")
	}

	service.Status = ServiceStatusStopping
	c.persistService(service)

	// Stop the service
	// Would use ProcessManager.TerminateProcess(service.ProcessID) if graceful
	// Otherwise ProcessManager.KillProcess(service.ProcessID)

	// Stop health checker
	c.healthMutex.Lock()
	if checker, exists := c.healthCheckers[serviceID]; exists {
		checker.Stop()
		delete(c.healthCheckers, serviceID)
	}
	c.healthMutex.Unlock()

	// Update status
	service.Status = ServiceStatusStopped
	now := time.Now()
	service.StoppedAt = &now
	service.ProcessID = 0

	return c.persistService(service)
}

// RestartService restarts a service
func (c *Coordinator) RestartService(ctx context.Context, serviceID string) error {
	if err := c.StopService(serviceID, true); err != nil {
		return fmt.Errorf("failed to stop service: %w", err)
	}

	// Wait a moment before restarting
	time.Sleep(1 * time.Second)

	if err := c.StartService(ctx, serviceID); err != nil {
		return fmt.Errorf("failed to start service: %w", err)
	}

	return nil
}

// HealthCheck performs a health check on a service
func (c *Coordinator) HealthCheck(serviceID string) (*HealthStatus, error) {
	service, err := c.GetService(serviceID)
	if err != nil {
		return nil, err
	}

	if service.HealthCheck == nil {
		return nil, fmt.Errorf("service has no health check configured")
	}

	status := &HealthStatus{
		ServiceID: serviceID,
		IsHealthy: false,
	}

	now := time.Now()
	status.LastCheckTime = &now

	// Perform health check based on type
	switch service.HealthCheck.Type {
	case HealthCheckTypeHTTP:
		status.IsHealthy, status.ResponseTime = checkHTTPHealth(service.HealthCheck.Endpoint, service.HealthCheck.Timeout)
	case HealthCheckTypeTCP:
		status.IsHealthy = checkTCPHealth(service.HealthCheck.Endpoint, service.HealthCheck.Port, service.HealthCheck.Timeout)
	case HealthCheckTypeExec:
		status.IsHealthy = checkExecHealth(service.HealthCheck.Command, service.HealthCheck.Timeout)
	}

	// Update service health status
	if status.IsHealthy {
		service.HealthStatus = "healthy"
		service.Status = ServiceStatusRunning
	} else {
		service.HealthStatus = "unhealthy"
		service.Status = ServiceStatusUnhealthy
		status.FailureCount++

		// Auto-restart if configured
		if service.AutoRestart && status.FailureCount > service.HealthCheck.Retries {
			_ = c.RestartService(context.Background(), serviceID)
		}
	}

	service.LastHealthCheck = status.LastCheckTime
	_ = c.persistService(service)

	return status, nil
}

// GetLogs retrieves service logs
func (c *Coordinator) GetLogs(serviceID string, lines int) (string, error) {
	service, err := c.GetService(serviceID)
	if err != nil {
		return "", err
	}

	// Placeholder - would retrieve from process log capture
	return fmt.Sprintf("Logs for service %s (placeholder)\n", service.Name), nil
}

// GetMetrics returns service metrics
func (c *Coordinator) GetMetrics(serviceID string) (*ServiceMetrics, error) {
	service, err := c.GetService(serviceID)
	if err != nil {
		return nil, err
	}

	metrics := &ServiceMetrics{
		ServiceID:    serviceID,
		PID:          service.ProcessID,
		RestartCount: service.Restarts,
	}

	if service.StartedAt != nil {
		metrics.Uptime = int64(time.Since(*service.StartedAt).Seconds())
	}

	// Placeholder - would get real metrics from system
	return metrics, nil
}

// Close gracefully shuts down the coordinator
func (c *Coordinator) Close() error {
	var err error
	c.closeOnce.Do(func() {
		close(c.closeChan)

		// Stop all running services
		services, _ := c.ListServices()
		for _, service := range services {
			_ = c.StopService(service.ID, true)
		}
	})

	return err
}

// Helper methods

func (c *Coordinator) persistService(service *Service) error {
	metadataJSON, _ := json.Marshal(service.Metadata)
	envJSON, _ := json.Marshal(service.Environment)
	healthCheckJSON, _ := json.Marshal(service.HealthCheck)

	argsJSON, _ := json.Marshal(service.Args)

	_, err := c.db.Exec(
		"INSERT OR REPLACE INTO gaia_services (id, name, type, command, args, work_dir, port, status, environment, health_check, auto_restart, process_id, restarts, started_at, stopped_at, error, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
		service.ID, service.Name, service.Type, service.Command, string(argsJSON), service.WorkDir, service.Port, service.Status, string(envJSON), string(healthCheckJSON), service.AutoRestart, service.ProcessID, service.Restarts, service.StartedAt, service.StoppedAt, service.Error, string(metadataJSON), service.CreatedAt,
	)

	return err
}

func (c *Coordinator) restoreServices(ctx context.Context) error {
	rows, err := c.db.QueryContext(ctx, "SELECT id, name, type, command, args, work_dir, port, status, environment, health_check, auto_restart, metadata, created_at FROM gaia_services")
	if err != nil {
		return err
	}
	defer rows.Close()

	c.serviceMutex.Lock()
	defer c.serviceMutex.Unlock()

	for rows.Next() {
		var service Service
		var envJSON, healthCheckJSON, metadataJSON, argsJSON string

		err := rows.Scan(&service.ID, &service.Name, &service.Type, &service.Command, &argsJSON, &service.WorkDir, &service.Port, &service.Status, &envJSON, &healthCheckJSON, &service.AutoRestart, &metadataJSON, &service.CreatedAt)
		if err != nil {
			continue
		}

		if envJSON != "" {
			_ = json.Unmarshal([]byte(envJSON), &service.Environment)
		}
		if healthCheckJSON != "" {
			_ = json.Unmarshal([]byte(healthCheckJSON), &service.HealthCheck)
		}
		if metadataJSON != "" {
			_ = json.Unmarshal([]byte(metadataJSON), &service.Metadata)
		}
		if argsJSON != "" {
			_ = json.Unmarshal([]byte(argsJSON), &service.Args)
		}

		c.services[service.ID] = &service
	}

	return rows.Err()
}

// Health check helper functions (placeholders)

func checkHTTPHealth(endpoint string, timeout time.Duration) (bool, int64) {
	// Placeholder - would make HTTP request
	return true, 10
}

func checkTCPHealth(endpoint string, port int, timeout time.Duration) bool {
	// Placeholder - would attempt TCP connection
	return true
}

func checkExecHealth(command string, timeout time.Duration) bool {
	// Placeholder - would execute command
	return true
}
