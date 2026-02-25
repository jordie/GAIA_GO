package config

import (
	"fmt"
	"os"

	"github.com/joho/godotenv"
)

type Config struct {
	Server   ServerConfig
	Database DatabaseConfig
	Session  SessionConfig
}

type ServerConfig struct {
	Host string
	Port string
	Env  string
}

type DatabaseConfig struct {
	Type string // "sqlite" or "postgres"
	DSN  string
	Path string // For SQLite: file path
}

type SessionConfig struct {
	Secret string
}

func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	dbType := getEnv("DB_TYPE", "sqlite") // Default to SQLite for development
	dsn, dbPath := buildDSN(dbType)

	return &Config{
		Server: ServerConfig{
			Host: getEnv("SERVER_HOST", "0.0.0.0"),
			Port: getEnv("SERVER_PORT", "8080"),
			Env:  getEnv("ENV", "development"),
		},
		Database: DatabaseConfig{
			Type: dbType,
			DSN:  dsn,
			Path: dbPath,
		},
		Session: SessionConfig{
			Secret: getEnv("SESSION_SECRET", "your-secret-key-change-in-prod"),
		},
	}, nil
}

func buildDSN(dbType string) (string, string) {
	if dbType == "postgres" {
		// PostgreSQL configuration
		dbHost := getEnv("DB_HOST", "localhost")
		dbPort := getEnv("DB_PORT", "5432")
		dbUser := getEnv("DB_USER", "postgres")
		dbPassword := getEnv("DB_PASSWORD", "postgres")
		dbName := getEnv("DB_NAME", "educational_apps")
		sslMode := getEnv("DB_SSLMODE", "disable")

		dsn := fmt.Sprintf(
			"host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
			dbHost, dbPort, dbUser, dbPassword, dbName, sslMode,
		)
		return dsn, ""
	}

	// SQLite configuration (default for development)
	dbPath := getEnv("SQLITE_PATH", "./data/educational_apps.db")
	dsn := dbPath + "?mode=rwc&cache=shared&timeout=5000"
	return dsn, dbPath
}

func getEnv(key, defaultValue string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return defaultValue
}
