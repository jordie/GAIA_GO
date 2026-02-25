package environments

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// Environment types
const (
	EnvDev     = "dev"
	EnvStaging = "staging"
	EnvProd    = "prod"
)

// EnvironmentHealth represents environment status
type EnvironmentHealth struct {
	Name          string
	Port          int
	Status        string // "healthy", "degraded", "down"
	Uptime        time.Duration
	LastCheck     time.Time
	CPUUsage      float64
	MemoryUsage   float64
	RequestCount  int64
	ErrorCount    int64
	ErrorRate     float64
	ResponseTime  time.Duration
	DatabaseSize  int64
	LogSize       int64
}

// EnvironmentManager manages all three environments
type EnvironmentManager struct {
	environmentsDir string
	environments    map[string]*EnvironmentHealth
	mu              sync.RWMutex
	ctx             context.Context
	cancel          context.CancelFunc
	monitorInterval time.Duration
}

// EnvironmentConfig represents environment configuration
type EnvironmentConfig struct {
	Name           string
	Port           int
	MetricsPort    int
	LogLevel       string
	DatabasePath   string
	ResetOnError   bool
	BackupInterval time.Duration
	LogRetention   time.Duration
}

// NewEnvironmentManager creates a new manager
func NewEnvironmentManager(environmentsDir string) *EnvironmentManager {
	ctx, cancel := context.WithCancel(context.Background())

	return &EnvironmentManager{
		environmentsDir: environmentsDir,
		environments: map[string]*EnvironmentHealth{
			EnvDev: {
				Name: EnvDev,
				Port: 8081,
				Status: "down",
			},
			EnvStaging: {
				Name: EnvStaging,
				Port: 8082,
				Status: "down",
			},
			EnvProd: {
				Name: EnvProd,
				Port: 8080,
				Status: "down",
			},
		},
		ctx:             ctx,
		cancel:          cancel,
		monitorInterval: 30 * time.Second,
	}
}

// StartMonitoring starts continuous health monitoring with goroutines
func (em *EnvironmentManager) StartMonitoring() {
	go em.monitoringLoop()
	go em.metricsCollector()
	go em.autoFailover()
	log.Println("✅ Started health monitoring (3 goroutines)")
}

// monitoringLoop continuously checks environment health
func (em *EnvironmentManager) monitoringLoop() {
	ticker := time.NewTicker(em.monitorInterval)
	defer ticker.Stop()

	for {
		select {
		case <-em.ctx.Done():
			return
		case <-ticker.C:
			em.checkAllEnvironments()
		}
	}
}

// checkAllEnvironments checks health of all environments in parallel
func (em *EnvironmentManager) checkAllEnvironments() {
	var wg sync.WaitGroup
	envs := []string{EnvDev, EnvStaging, EnvProd}

	for _, env := range envs {
		wg.Add(1)
		go func(e string) {
			defer wg.Done()
			em.checkEnvironmentHealth(e)
		}(env)
	}

	wg.Wait()
}

// checkEnvironmentHealth checks single environment health
func (em *EnvironmentManager) checkEnvironmentHealth(envName string) {
	em.mu.RLock()
	health := em.environments[envName]
	em.mu.RUnlock()

	if health == nil {
		return
	}

	// Check HTTP health endpoint
	url := fmt.Sprintf("http://localhost:%d/health", health.Port)
	client := &http.Client{Timeout: 5 * time.Second}

	startTime := time.Now()
	resp, err := client.Get(url)
	responseTime := time.Since(startTime)

	em.mu.Lock()
	defer em.mu.Unlock()

	health.LastCheck = time.Now()
	health.ResponseTime = responseTime

	if err != nil {
		health.Status = "down"
		health.ErrorCount++
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		health.Status = "healthy"
		health.RequestCount++
		// Read response for uptime info
		body, _ := io.ReadAll(resp.Body)
		log.Printf("[%s] Healthy - Response: %v bytes\n", envName, len(body))
	} else {
		health.Status = "degraded"
		health.ErrorCount++
		health.ErrorRate = float64(health.ErrorCount) / float64(health.RequestCount+health.ErrorCount)
	}
}

// metricsCollector collects performance metrics
func (em *EnvironmentManager) metricsCollector() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-em.ctx.Done():
			return
		case <-ticker.C:
			em.collectMetrics()
		}
	}
}

// collectMetrics gathers detailed metrics from all environments
func (em *EnvironmentManager) collectMetrics() {
	em.mu.RLock()
	defer em.mu.RUnlock()

	for _, health := range em.environments {
		// Collect metrics from metrics endpoint
		metricsURL := fmt.Sprintf("http://localhost:%d/metrics", health.Port+10) // metrics port = port + 10
		client := &http.Client{Timeout: 5 * time.Second}

		resp, err := client.Get(metricsURL)
		if err != nil {
			log.Printf("Failed to collect metrics for %s: %v\n", health.Name, err)
			continue
		}

		// Parse metrics (simplified - in production would parse Prometheus format)
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		log.Printf("[%s] Metrics collected: %d bytes\n", health.Name, len(body))

		// Check database size
		dbPath := filepath.Join(em.environmentsDir, health.Name, "data", fmt.Sprintf("%s_gaia.db", health.Name))
		if info, err := os.Stat(dbPath); err == nil {
			health.DatabaseSize = info.Size()
		}

		// Check log size
		logPath := filepath.Join(em.environmentsDir, health.Name, "logs", "gaia.log")
		if info, err := os.Stat(logPath); err == nil {
			health.LogSize = info.Size()
		}
	}
}

// autoFailover implements automatic failover between environments
func (em *EnvironmentManager) autoFailover() {
	ticker := time.NewTicker(2 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-em.ctx.Done():
			return
		case <-ticker.C:
			em.detectAndHandleFailures()
		}
	}
}

// detectAndHandleFailures detects environment failures and handles them
func (em *EnvironmentManager) detectAndHandleFailures() {
	em.mu.Lock()
	defer em.mu.Unlock()

	for _, health := range em.environments {
		if health.Status == "down" && health.Name == EnvProd {
			log.Printf("🚨 PROD environment down! Attempting recovery...\n")
			em.recoverEnvironment(EnvProd)
		} else if health.Status == "degraded" {
			log.Printf("⚠️  %s environment degraded (error rate: %.2f%%)\n",
				health.Name, health.ErrorRate*100)
		}
	}
}

// recoverEnvironment attempts to recover a failed environment
func (em *EnvironmentManager) recoverEnvironment(envName string) error {
	log.Printf("🔄 Recovering %s environment...\n", envName)

	envDir := filepath.Join(em.environmentsDir, envName)
	backupDir := filepath.Join(envDir, "data", "backups")

	// List backups (most recent first)
	entries, err := os.ReadDir(backupDir)
	if err != nil {
		return fmt.Errorf("failed to list backups: %w", err)
	}

	if len(entries) == 0 {
		return fmt.Errorf("no backups available for %s", envName)
	}

	// Restore from latest backup
	latestBackup := entries[len(entries)-1]
	backupPath := filepath.Join(backupDir, latestBackup.Name())
	dbPath := filepath.Join(envDir, "data", fmt.Sprintf("%s_gaia.db", envName))

	log.Printf("Restoring from backup: %s\n", latestBackup.Name())

	if err := os.Rename(backupPath, dbPath); err != nil {
		return fmt.Errorf("failed to restore backup: %w", err)
	}

	log.Printf("✅ %s recovered from backup\n", envName)
	return nil
}

// LoadBalance distributes traffic across environments
func (em *EnvironmentManager) LoadBalance(request string) (string, error) {
	em.mu.RLock()
	defer em.mu.RUnlock()

	// Find healthiest environment
	var healthiest *EnvironmentHealth
	var minLoad int64

	for _, health := range em.environments {
		if health.Status != "healthy" {
			continue
		}

		load := health.RequestCount - health.ErrorCount
		if healthiest == nil || load < minLoad {
			healthiest = health
			minLoad = load
		}
	}

	if healthiest == nil {
		return "", fmt.Errorf("no healthy environments available")
	}

	log.Printf("Load balanced to %s (load: %d)\n", healthiest.Name, minLoad)
	return healthiest.Name, nil
}

// GetStatus returns status of all environments
func (em *EnvironmentManager) GetStatus() map[string]EnvironmentHealth {
	em.mu.RLock()
	defer em.mu.RUnlock()

	status := make(map[string]EnvironmentHealth)
	for name, health := range em.environments {
		status[name] = *health
	}
	return status
}

// PrintStatus prints formatted status
func (em *EnvironmentManager) PrintStatus() {
	em.mu.RLock()
	defer em.mu.RUnlock()

	fmt.Println("═══════════════════════════════════════════════════════════")
	fmt.Println("GAIA_GO ENVIRONMENT STATUS")
	fmt.Println("═══════════════════════════════════════════════════════════")

	for _, health := range em.environments {
		statusIcon := "⚪"
		if health.Status == "healthy" {
			statusIcon = "🟢"
		} else if health.Status == "degraded" {
			statusIcon = "🟡"
		} else if health.Status == "down" {
			statusIcon = "🔴"
		}

		fmt.Printf("\n%s %s Environment (Port %d)\n", statusIcon, health.Name, health.Port)
		fmt.Printf("  Status: %s\n", health.Status)
		fmt.Printf("  Last Check: %v ago\n", time.Since(health.LastCheck).Round(time.Second))
		fmt.Printf("  Response Time: %v\n", health.ResponseTime)
		fmt.Printf("  Requests: %d (Errors: %d, Rate: %.2f%%)\n",
			health.RequestCount, health.ErrorCount, health.ErrorRate*100)
		fmt.Printf("  Database Size: %d bytes\n", health.DatabaseSize)
		fmt.Printf("  Log Size: %d bytes\n", health.LogSize)
	}

	fmt.Println("\n═══════════════════════════════════════════════════════════")
}

// Close stops monitoring
func (em *EnvironmentManager) Close() {
	em.cancel()
	log.Println("✅ Environment manager stopped")
}

// GetEnvironmentConfig returns config for an environment
func (em *EnvironmentManager) GetEnvironmentConfig(envName string) EnvironmentConfig {
	portMap := map[string]int{
		EnvDev:     8081,
		EnvStaging: 8082,
		EnvProd:    8080,
	}

	logLevelMap := map[string]string{
		EnvDev:     "DEBUG",
		EnvStaging: "INFO",
		EnvProd:    "WARN",
	}

	return EnvironmentConfig{
		Name:         envName,
		Port:         portMap[envName],
		MetricsPort:  portMap[envName] + 10,
		LogLevel:     logLevelMap[envName],
		DatabasePath: filepath.Join(em.environmentsDir, envName, "data", fmt.Sprintf("%s_gaia.db", envName)),
		ResetOnError: envName == EnvDev,
		BackupInterval: map[string]time.Duration{
			EnvDev:     0,
			EnvStaging: 24 * time.Hour,
			EnvProd:    1 * time.Hour,
		}[envName],
		LogRetention: map[string]time.Duration{
			EnvDev:     7 * 24 * time.Hour,
			EnvStaging: 30 * 24 * time.Hour,
			EnvProd:    90 * 24 * time.Hour,
		}[envName],
	}
}
