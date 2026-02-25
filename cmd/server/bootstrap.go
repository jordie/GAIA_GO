package main

import (
	"log"
	"os"
	"strconv"
	"time"
)

// LoadDistributedGAIAConfig loads configuration from environment variables
func LoadDistributedGAIAConfig() DistributedGAIAConfig {
	return DistributedGAIAConfig{
		DatabaseURL: getEnv("DATABASE_URL", "postgres://user:password@localhost:5432/gaia_go"),
		RaftEnabled: getEnvBool("CLUSTER_ENABLED", false),
		RaftNodeID: getEnv("CLUSTER_NODE_ID", "node-1"),
		RaftBindAddr: getEnv("CLUSTER_BIND_ADDR", "127.0.0.1:8300"),
		RaftAdvertiseAddr: getEnv("CLUSTER_ADVERTISE_ADDR", "127.0.0.1:8300"),
		RaftDiscoveryNodes: getEnv("CLUSTER_DISCOVERY_NODES", "127.0.0.1:8300"),
		ClusterSnapshotDir: getEnv("CLUSTER_SNAPSHOT_DIR", "./data/raft"),
		SessionLeaseTimeout: getEnvDuration("SESSION_LEASE_TIMEOUT", 30*time.Second),
		SessionHeartbeatInterval: getEnvDuration("SESSION_HEARTBEAT_INTERVAL", 10*time.Second),
		TaskQueueMaxRetries: getEnvInt("TASK_MAX_RETRIES", 3),
		UsabilityMetricsEnabled: getEnvBool("USABILITY_METRICS_ENABLED", true),
	}
}

// LogConfiguration logs the loaded configuration
func LogConfiguration(config DistributedGAIAConfig) {
	log.Println("===============================================================")
	log.Println("DISTRIBUTED GAIA_GO CONFIGURATION")
	log.Println("===============================================================")
	log.Printf("Database URL:                   %s", maskDatabaseURL(config.DatabaseURL))
	log.Printf("Raft Enabled:                   %v", config.RaftEnabled)
	if config.RaftEnabled {
		log.Printf("  Node ID:                      %s", config.RaftNodeID)
		log.Printf("  Bind Address:                 %s", config.RaftBindAddr)
		log.Printf("  Advertise Address:            %s", config.RaftAdvertiseAddr)
		log.Printf("  Discovery Nodes:              %s", config.RaftDiscoveryNodes)
	}
	log.Printf("Session Lease Timeout:          %v", config.SessionLeaseTimeout)
	log.Printf("Session Heartbeat Interval:     %v", config.SessionHeartbeatInterval)
	log.Printf("Task Queue Max Retries:         %d", config.TaskQueueMaxRetries)
	log.Printf("Usability Metrics Enabled:      %v", config.UsabilityMetricsEnabled)
	log.Println("===============================================================")
}

// maskDatabaseURL masks sensitive information in database URL
func maskDatabaseURL(dsn string) string {
	if len(dsn) > 20 {
		return dsn[:10] + "..." + dsn[len(dsn)-10:]
	}
	return "***"
}

// getEnvBool gets an environment variable as boolean with a default value
func getEnvBool(key string, defaultValue bool) bool {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	boolVal, err := strconv.ParseBool(value)
	if err != nil {
		log.Printf("[WARN] Invalid boolean value for %s: %s, using default: %v", key, value, defaultValue)
		return defaultValue
	}
	return boolVal
}

// getEnvInt gets an environment variable as integer with a default value
func getEnvInt(key string, defaultValue int) int {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	intVal, err := strconv.Atoi(value)
	if err != nil {
		log.Printf("[WARN] Invalid integer value for %s: %s, using default: %d", key, value, defaultValue)
		return defaultValue
	}
	return intVal
}

// getEnvDuration gets an environment variable as duration with a default value
func getEnvDuration(key string, defaultValue time.Duration) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	duration, err := time.ParseDuration(value)
	if err != nil {
		log.Printf("[WARN] Invalid duration value for %s: %s, using default: %v", key, value, defaultValue)
		return defaultValue
	}
	return duration
}
