package database

import (
	"fmt"

	"gorm.io/driver/postgres"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

// InitWithType initializes database connection based on type
func InitWithType(dbType string, dsn string) error {
	var err error

	if dbType == "postgres" {
		DB, err = gorm.Open(postgres.Open(dsn), &gorm.Config{
			Logger: logger.Default.LogMode(logger.Info),
		})
	} else {
		// Default to SQLite
		DB, err = gorm.Open(sqlite.Open(dsn), &gorm.Config{
			Logger: logger.Default.LogMode(logger.Info),
		})
	}

	if err != nil {
		return fmt.Errorf("failed to connect to database: %w", err)
	}

	// Get underlying SQL database to configure connection pool
	sqlDB, err := DB.DB()
	if err != nil {
		return err
	}

	// Set connection pool settings (conservative for SQLite)
	if dbType == "sqlite" {
		sqlDB.SetMaxIdleConns(5)
		sqlDB.SetMaxOpenConns(10)
	} else {
		sqlDB.SetMaxIdleConns(10)
		sqlDB.SetMaxOpenConns(100)
	}

	return nil
}

// Init initializes database with DSN (backwards compatible, defaults to PostgreSQL)
func Init(dsn string) error {
	return InitWithType("postgres", dsn)
}

// GetDB returns the database instance
func GetDB() *gorm.DB {
	return DB
}

// Close closes the database connection
func Close() error {
	sqlDB, err := DB.DB()
	if err != nil {
		return err
	}
	return sqlDB.Close()
}
