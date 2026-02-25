package config

import (
	"testing"
	"time"
)

func TestDefaultConfig_IsValid(t *testing.T) {
	cfg := defaultConfig()

	if err := cfg.Validate(); err != nil {
		t.Fatalf("default config should be valid, got: %v", err)
	}
}

func TestConfig_Validate_InvalidServerPort(t *testing.T) {
	tests := []struct {
		name      string
		port      int
		shouldErr bool
	}{
		{
			name:      "port 0 invalid",
			port:      0,
			shouldErr: true,
		},
		{
			name:      "port -1 invalid",
			port:      -1,
			shouldErr: true,
		},
		{
			name:      "port 65536 invalid",
			port:      65536,
			shouldErr: true,
		},
		{
			name:      "port 1 valid",
			port:      1,
			shouldErr: false,
		},
		{
			name:      "port 65535 valid",
			port:      65535,
			shouldErr: false,
		},
		{
			name:      "port 8080 valid",
			port:      8080,
			shouldErr: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			cfg := defaultConfig()
			cfg.Server.Port = tc.port

			err := cfg.Validate()
			if tc.shouldErr && err == nil {
				t.Errorf("expected error, got nil")
			}
			if !tc.shouldErr && err != nil {
				t.Errorf("expected no error, got: %v", err)
			}
		})
	}
}

func TestConfig_Validate_InvalidDatabase(t *testing.T) {
	tests := []struct {
		name      string
		setupCfg  func(*Config)
		shouldErr bool
	}{
		{
			name: "empty host",
			setupCfg: func(c *Config) {
				c.Database.Host = ""
			},
			shouldErr: true,
		},
		{
			name: "empty user",
			setupCfg: func(c *Config) {
				c.Database.User = ""
			},
			shouldErr: true,
		},
		{
			name: "empty database name",
			setupCfg: func(c *Config) {
				c.Database.Database = ""
			},
			shouldErr: true,
		},
		{
			name: "valid defaults",
			setupCfg: func(c *Config) {
				// Use defaults
			},
			shouldErr: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			cfg := defaultConfig()
			tc.setupCfg(cfg)

			err := cfg.Validate()
			if tc.shouldErr && err == nil {
				t.Errorf("expected error, got nil")
			}
			if !tc.shouldErr && err != nil {
				t.Errorf("expected no error, got: %v", err)
			}
		})
	}
}

func TestConfig_Validate_InvalidConnections(t *testing.T) {
	tests := []struct {
		name      string
		maxConns  int
		minConns  int
		shouldErr bool
	}{
		{
			name:      "max_conns 0 invalid",
			maxConns:  0,
			minConns:  1,
			shouldErr: true,
		},
		{
			name:      "min_conns > max_conns invalid",
			maxConns:  5,
			minConns:  10,
			shouldErr: true,
		},
		{
			name:      "min_conns == max_conns valid",
			maxConns:  10,
			minConns:  10,
			shouldErr: false,
		},
		{
			name:      "valid ranges",
			maxConns:  20,
			minConns:  2,
			shouldErr: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			cfg := defaultConfig()
			cfg.Database.MaxConnections = tc.maxConns
			cfg.Database.MinConnections = tc.minConns

			err := cfg.Validate()
			if tc.shouldErr && err == nil {
				t.Errorf("expected error, got nil")
			}
			if !tc.shouldErr && err != nil {
				t.Errorf("expected no error, got: %v", err)
			}
		})
	}
}

func TestConfig_Validate_InvalidLogging(t *testing.T) {
	tests := []struct {
		name      string
		level     string
		format    string
		shouldErr bool
	}{
		{
			name:      "unknown level",
			level:     "unknown",
			format:    "json",
			shouldErr: true,
		},
		{
			name:      "unknown format",
			level:     "info",
			format:    "unknown",
			shouldErr: true,
		},
		{
			name:      "uppercase level WARN valid",
			level:     "WARN",
			format:    "json",
			shouldErr: false,
		},
		{
			name:      "text format valid",
			level:     "info",
			format:    "text",
			shouldErr: false,
		},
		{
			name:      "debug level valid",
			level:     "debug",
			format:    "json",
			shouldErr: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			cfg := defaultConfig()
			cfg.Logging.Level = tc.level
			cfg.Logging.Format = tc.format

			err := cfg.Validate()
			if tc.shouldErr && err == nil {
				t.Errorf("expected error, got nil")
			}
			if !tc.shouldErr && err != nil {
				t.Errorf("expected no error, got: %v", err)
			}
		})
	}
}

func TestConfig_ApplyEnv_OverridesServer(t *testing.T) {
	t.Setenv("ARCHITECT_SERVER_HOST", "myhost")
	t.Setenv("ARCHITECT_SERVER_PORT", "9000")

	cfg := defaultConfig()
	cfg.applyEnv()

	if cfg.Server.Host != "myhost" {
		t.Errorf("expected Host myhost, got %s", cfg.Server.Host)
	}

	if cfg.Server.Port != 9000 {
		t.Errorf("expected Port 9000, got %d", cfg.Server.Port)
	}
}

func TestConfig_ApplyEnv_IgnoresInvalidPort(t *testing.T) {
	originalPort := 8080
	t.Setenv("ARCHITECT_SERVER_PORT", "abc")

	cfg := defaultConfig()
	cfg.Server.Port = originalPort
	cfg.applyEnv()

	if cfg.Server.Port != originalPort {
		t.Errorf("expected Port to remain %d, got %d", originalPort, cfg.Server.Port)
	}
}

func TestConfig_ApplyEnv_OverridesDatabase(t *testing.T) {
	t.Setenv("ARCHITECT_DATABASE_HOST", "dbhost")
	t.Setenv("ARCHITECT_DATABASE_USER", "dbuser")
	t.Setenv("ARCHITECT_DATABASE_PASSWORD", "dbpass")
	t.Setenv("ARCHITECT_DATABASE_DATABASE", "dbname")

	cfg := defaultConfig()
	cfg.applyEnv()

	if cfg.Database.Host != "dbhost" {
		t.Errorf("expected Host dbhost, got %s", cfg.Database.Host)
	}

	if cfg.Database.User != "dbuser" {
		t.Errorf("expected User dbuser, got %s", cfg.Database.User)
	}

	if cfg.Database.Password != "dbpass" {
		t.Errorf("expected Password dbpass, got %s", cfg.Database.Password)
	}

	if cfg.Database.Database != "dbname" {
		t.Errorf("expected Database dbname, got %s", cfg.Database.Database)
	}
}

func TestConfig_ApplyEnv_OverridesAuth(t *testing.T) {
	t.Setenv("ARCHITECT_AUTH_SECRET_KEY", "mysecret")
	t.Setenv("ARCHITECT_AUTH_TOKEN_EXPIRY", "48h")

	cfg := defaultConfig()
	cfg.applyEnv()

	if cfg.Auth.SecretKey != "mysecret" {
		t.Errorf("expected SecretKey mysecret, got %s", cfg.Auth.SecretKey)
	}

	expected := 48 * time.Hour
	if cfg.Auth.TokenExpiry != expected {
		t.Errorf("expected TokenExpiry %v, got %v", expected, cfg.Auth.TokenExpiry)
	}
}

func TestConfig_ApplyEnv_IgnoresInvalidDuration(t *testing.T) {
	originalExpiry := 24 * time.Hour
	t.Setenv("ARCHITECT_AUTH_TOKEN_EXPIRY", "invalid")

	cfg := defaultConfig()
	cfg.Auth.TokenExpiry = originalExpiry
	cfg.applyEnv()

	if cfg.Auth.TokenExpiry != originalExpiry {
		t.Errorf("expected TokenExpiry to remain %v, got %v", originalExpiry, cfg.Auth.TokenExpiry)
	}
}

func TestConfig_GetDatabaseURL(t *testing.T) {
	cfg := defaultConfig()

	url := cfg.GetDatabaseURL()

	// Expected format: postgres://user:pass@host:port/db?sslmode=mode
	if url == "" {
		t.Fatalf("expected non-empty URL")
	}

	// Verify it contains required parts
	expectedParts := []string{
		"postgres://",
		"localhost",
		"5432",
		"architect_dev",
		"sslmode=disable",
	}

	for _, part := range expectedParts {
		if !contains(url, part) {
			t.Errorf("expected URL to contain %s", part)
		}
	}
}

func TestConfig_GetDatabaseURL_CustomValues(t *testing.T) {
	cfg := defaultConfig()
	cfg.Database.User = "myuser"
	cfg.Database.Password = "mypass"
	cfg.Database.Host = "myhost"
	cfg.Database.Port = 5433
	cfg.Database.Database = "mydb"
	cfg.Database.SSLMode = "require"

	url := cfg.GetDatabaseURL()

	expectedParts := []string{
		"postgres://",
		"myuser:mypass",
		"myhost:5433",
		"mydb",
		"sslmode=require",
	}

	for _, part := range expectedParts {
		if !contains(url, part) {
			t.Errorf("expected URL to contain %s", part)
		}
	}
}

func TestConfig_Validate_ReadWriteTimeouts(t *testing.T) {
	cfg := defaultConfig()
	cfg.Server.ReadTimeout = -1 * time.Second

	err := cfg.Validate()
	if err == nil {
		t.Errorf("expected error for negative read timeout")
	}

	cfg = defaultConfig()
	cfg.Server.WriteTimeout = 0 * time.Second

	err = cfg.Validate()
	if err == nil {
		t.Errorf("expected error for zero write timeout")
	}
}

// helper function
func contains(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
