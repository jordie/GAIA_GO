package services

import (
	"time"
)

// ServiceStatus represents the state of a service
type ServiceStatus string

const (
	ServiceStatusStopped    ServiceStatus = "stopped"
	ServiceStatusStarting   ServiceStatus = "starting"
	ServiceStatusRunning    ServiceStatus = "running"
	ServiceStatusUnhealthy  ServiceStatus = "unhealthy"
	ServiceStatusStopping   ServiceStatus = "stopping"
	ServiceStatusFailed     ServiceStatus = "failed"
)

// HealthCheckType specifies the kind of health check
type HealthCheckType string

const (
	HealthCheckTypeHTTP   HealthCheckType = "http"
	HealthCheckTypeTCP    HealthCheckType = "tcp"
	HealthCheckTypeExec   HealthCheckType = "exec"
	HealthCheckTypeNone   HealthCheckType = "none"
)

// Service represents a managed service/application
type Service struct {
	ID              string                 `json:"id"`
	Name            string                 `json:"name"`
	Type            string                 `json:"type"`
	Command         string                 `json:"command"`
	Args            []string               `json:"args"`
	WorkDir         string                 `json:"work_dir"`
	Port            int                    `json:"port"`
	Status          ServiceStatus          `json:"status"`
	Environment     map[string]string      `json:"environment"`
	HealthCheck     *HealthCheckConfig     `json:"health_check"`
	AutoRestart     bool                   `json:"auto_restart"`
	ProcessID       int                    `json:"process_id"`
	Restarts        int                    `json:"restarts"`
	StartedAt       *time.Time             `json:"started_at"`
	StoppedAt       *time.Time             `json:"stopped_at"`
	LastHealthCheck *time.Time             `json:"last_health_check"`
	HealthStatus    string                 `json:"health_status"`
	Error           string                 `json:"error"`
	Metadata        map[string]interface{} `json:"metadata"`
	CreatedAt       time.Time              `json:"created_at"`
}

// HealthCheckConfig specifies how to check service health
type HealthCheckConfig struct {
	Type      HealthCheckType   `json:"type"`
	Endpoint  string            `json:"endpoint"`   // For HTTP health checks
	Port      int               `json:"port"`      // For TCP health checks
	Command   string            `json:"command"`   // For Exec health checks
	Interval  time.Duration     `json:"interval"`
	Timeout   time.Duration     `json:"timeout"`
	Retries   int               `json:"retries"`
	StartDelay time.Duration    `json:"start_delay"` // Wait before first check
}

// ServiceConfig holds configuration for registering a service
type ServiceConfig struct {
	Name        string                 `json:"name"`
	Type        string                 `json:"type"`
	Command     string                 `json:"command"`
	Args        []string               `json:"args"`
	WorkDir     string                 `json:"work_dir"`
	Port        int                    `json:"port"`
	Environment map[string]string      `json:"environment"`
	HealthCheck *HealthCheckConfig     `json:"health_check"`
	AutoRestart bool                   `json:"auto_restart"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// ServiceMetrics holds performance metrics for a service
type ServiceMetrics struct {
	ServiceID      string    `json:"service_id"`
	CPUPercent     float64   `json:"cpu_percent"`
	MemoryMB       int64     `json:"memory_mb"`
	PID            int       `json:"pid"`
	Uptime         int64     `json:"uptime_seconds"`
	RestartCount   int       `json:"restart_count"`
	SuccessCount   int64     `json:"health_checks_passed"`
	FailureCount   int64     `json:"health_checks_failed"`
	LastCheckTime  *time.Time `json:"last_check_time"`
}

// ServiceEvent represents an event in service lifecycle
type ServiceEvent struct {
	ID        string        `json:"id"`
	ServiceID string        `json:"service_id"`
	Type      string        `json:"type"` // started, stopped, failed, health_check_passed, health_check_failed
	Message   string        `json:"message"`
	Timestamp time.Time     `json:"timestamp"`
}

// HealthStatus represents the current health of a service
type HealthStatus struct {
	ServiceID      string     `json:"service_id"`
	IsHealthy      bool       `json:"is_healthy"`
	LastCheckTime  *time.Time `json:"last_check_time"`
	FailureCount   int        `json:"failure_count"`
	LastError      string     `json:"last_error"`
	ResponseTime   int64      `json:"response_time_ms"`
}
