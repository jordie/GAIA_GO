package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// Config represents the application configuration
type Config struct {
	Server   ServerConfig   `yaml:"server"`
	Database DatabaseConfig `yaml:"database"`
	Logging  LoggingConfig  `yaml:"logging"`
	Auth     AuthConfig     `yaml:"auth"`
}

// ServerConfig represents server configuration
type ServerConfig struct {
	Host         string        `yaml:"host"`
	Port         int           `yaml:"port"`
	TLSEnabled   bool          `yaml:"tls_enabled"`
	TLSCert      string        `yaml:"tls_cert"`
	TLSKey       string        `yaml:"tls_key"`
	ReadTimeout  time.Duration `yaml:"read_timeout"`
	WriteTimeout time.Duration `yaml:"write_timeout"`
}

// DatabaseConfig represents database configuration
type DatabaseConfig struct {
	Host            string `yaml:"host"`
	Port            int    `yaml:"port"`
	User            string `yaml:"user"`
	Password        string `yaml:"password"`
	Database        string `yaml:"database"`
	MaxConnections  int    `yaml:"max_connections"`
	MinConnections  int    `yaml:"min_connections"`
	SSLMode         string `yaml:"ssl_mode"`
	MigrationPath   string `yaml:"migration_path"`
}

// LoggingConfig represents logging configuration
type LoggingConfig struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
}

// AuthConfig represents authentication configuration
type AuthConfig struct {
	SecretKey     string        `yaml:"secret_key"`
	TokenExpiry   time.Duration `yaml:"token_expiry"`
	SessionExpiry time.Duration `yaml:"session_expiry"`
	Issuer        string        `yaml:"issuer"`
}

// Load loads configuration from file and environment variables
func Load() (*Config, error) {
	// Start with defaults
	cfg := defaultConfig()

	// Load from YAML file if it exists
	configPath := getConfigPath()
	if _, err := os.Stat(configPath); err == nil {
		data, err := os.ReadFile(configPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}

		if err := yaml.Unmarshal(data, cfg); err != nil {
			return nil, fmt.Errorf("failed to parse config file: %w", err)
		}
	}

	// Override with environment variables
	cfg.applyEnv()

	// Validate configuration
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	return cfg, nil
}

// defaultConfig returns a configuration with default values
func defaultConfig() *Config {
	return &Config{
		Server: ServerConfig{
			Host:         "0.0.0.0",
			Port:         8080,
			TLSEnabled:   false,
			ReadTimeout:  15 * time.Second,
			WriteTimeout: 15 * time.Second,
		},
		Database: DatabaseConfig{
			Host:           "localhost",
			Port:           5432,
			User:           "architect",
			Password:       "architect_dev",
			Database:       "architect_dev",
			MaxConnections: 20,
			MinConnections: 2,
			SSLMode:        "disable",
			MigrationPath:  "./migrations",
		},
		Logging: LoggingConfig{
			Level:  "info",
			Format: "json",
		},
		Auth: AuthConfig{
			SecretKey:     "your-secret-key-change-in-production",
			TokenExpiry:   24 * time.Hour,
			SessionExpiry: 24 * time.Hour,
			Issuer:        "architect-dashboard",
		},
	}
}

// getConfigPath returns the configuration file path
func getConfigPath() string {
	// Check environment variable first
	if path := os.Getenv("ARCHITECT_CONFIG"); path != "" {
		return path
	}

	// Look for config.yaml in current directory
	return "config.yaml"
}

// applyEnv overrides configuration with environment variables
func (c *Config) applyEnv() {
	// Server configuration
	if host := os.Getenv("ARCHITECT_SERVER_HOST"); host != "" {
		c.Server.Host = host
	}
	if port := os.Getenv("ARCHITECT_SERVER_PORT"); port != "" {
		if p, err := strconv.Atoi(port); err == nil {
			c.Server.Port = p
		}
	}
	if readTimeout := os.Getenv("ARCHITECT_SERVER_READ_TIMEOUT"); readTimeout != "" {
		if d, err := time.ParseDuration(readTimeout); err == nil {
			c.Server.ReadTimeout = d
		}
	}
	if writeTimeout := os.Getenv("ARCHITECT_SERVER_WRITE_TIMEOUT"); writeTimeout != "" {
		if d, err := time.ParseDuration(writeTimeout); err == nil {
			c.Server.WriteTimeout = d
		}
	}

	// Database configuration
	if host := os.Getenv("ARCHITECT_DATABASE_HOST"); host != "" {
		c.Database.Host = host
	}
	if port := os.Getenv("ARCHITECT_DATABASE_PORT"); port != "" {
		if p, err := strconv.Atoi(port); err == nil {
			c.Database.Port = p
		}
	}
	if user := os.Getenv("ARCHITECT_DATABASE_USER"); user != "" {
		c.Database.User = user
	}
	if password := os.Getenv("ARCHITECT_DATABASE_PASSWORD"); password != "" {
		c.Database.Password = password
	}
	if database := os.Getenv("ARCHITECT_DATABASE_DATABASE"); database != "" {
		c.Database.Database = database
	}
	if maxConns := os.Getenv("ARCHITECT_DATABASE_MAX_CONNECTIONS"); maxConns != "" {
		if m, err := strconv.Atoi(maxConns); err == nil {
			c.Database.MaxConnections = m
		}
	}
	if minConns := os.Getenv("ARCHITECT_DATABASE_MIN_CONNECTIONS"); minConns != "" {
		if m, err := strconv.Atoi(minConns); err == nil {
			c.Database.MinConnections = m
		}
	}
	if sslMode := os.Getenv("ARCHITECT_DATABASE_SSL_MODE"); sslMode != "" {
		c.Database.SSLMode = sslMode
	}

	// Logging configuration
	if level := os.Getenv("ARCHITECT_LOGGING_LEVEL"); level != "" {
		c.Logging.Level = level
	}
	if format := os.Getenv("ARCHITECT_LOGGING_FORMAT"); format != "" {
		c.Logging.Format = format
	}

	// Auth configuration
	if secretKey := os.Getenv("ARCHITECT_AUTH_SECRET_KEY"); secretKey != "" {
		c.Auth.SecretKey = secretKey
	}
	if tokenExpiry := os.Getenv("ARCHITECT_AUTH_TOKEN_EXPIRY"); tokenExpiry != "" {
		if d, err := time.ParseDuration(tokenExpiry); err == nil {
			c.Auth.TokenExpiry = d
		}
	}
	if sessionExpiry := os.Getenv("ARCHITECT_AUTH_SESSION_EXPIRY"); sessionExpiry != "" {
		if d, err := time.ParseDuration(sessionExpiry); err == nil {
			c.Auth.SessionExpiry = d
		}
	}
	if issuer := os.Getenv("ARCHITECT_AUTH_ISSUER"); issuer != "" {
		c.Auth.Issuer = issuer
	}
}

// Validate validates the configuration
func (c *Config) Validate() error {
	// Validate server configuration
	if c.Server.Port <= 0 || c.Server.Port > 65535 {
		return fmt.Errorf("invalid server port: %d", c.Server.Port)
	}

	if c.Server.ReadTimeout <= 0 {
		return fmt.Errorf("read timeout must be positive")
	}

	if c.Server.WriteTimeout <= 0 {
		return fmt.Errorf("write timeout must be positive")
	}

	// Validate database configuration
	if c.Database.Host == "" {
		return fmt.Errorf("database host is required")
	}

	if c.Database.Port <= 0 || c.Database.Port > 65535 {
		return fmt.Errorf("invalid database port: %d", c.Database.Port)
	}

	if c.Database.User == "" {
		return fmt.Errorf("database user is required")
	}

	if c.Database.Database == "" {
		return fmt.Errorf("database name is required")
	}

	if c.Database.MaxConnections < 1 {
		return fmt.Errorf("max connections must be at least 1")
	}

	if c.Database.MinConnections < 0 {
		return fmt.Errorf("min connections cannot be negative")
	}

	if c.Database.MinConnections > c.Database.MaxConnections {
		return fmt.Errorf("min connections cannot be greater than max connections")
	}

	// Validate logging configuration
	validLevels := map[string]bool{
		"debug": true,
		"info":  true,
		"warn":  true,
		"error": true,
		"fatal": true,
		"panic": true,
	}

	if !validLevels[strings.ToLower(c.Logging.Level)] {
		return fmt.Errorf("invalid logging level: %s", c.Logging.Level)
	}

	validFormats := map[string]bool{
		"json": true,
		"text": true,
	}

	if !validFormats[strings.ToLower(c.Logging.Format)] {
		return fmt.Errorf("invalid logging format: %s", c.Logging.Format)
	}

	return nil
}

// String returns a string representation of the configuration
func (c *Config) String() string {
	return fmt.Sprintf(
		"Config{Server: %s:%d, Database: %s@%s:%d/%s, Logging: %s/%s}",
		c.Server.Host, c.Server.Port,
		c.Database.User, c.Database.Host, c.Database.Port, c.Database.Database,
		c.Logging.Level, c.Logging.Format,
	)
}

// GetDatabaseURL returns the PostgreSQL connection string
func (c *Config) GetDatabaseURL() string {
	return fmt.Sprintf(
		"postgres://%s:%s@%s:%d/%s?sslmode=%s",
		c.Database.User,
		c.Database.Password,
		c.Database.Host,
		c.Database.Port,
		c.Database.Database,
		c.Database.SSLMode,
	)
}
