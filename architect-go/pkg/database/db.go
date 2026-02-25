package database

import (
	"fmt"
	"log"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"architect-go/pkg/config"
	"architect-go/pkg/models"
)

// Database wraps the GORM DB instance
type Database struct {
	db *gorm.DB
}

// New creates a new database connection
func New(cfg *config.Config) (*Database, error) {
	dsn := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s connect_timeout=10",
		cfg.Database.Host,
		cfg.Database.Port,
		cfg.Database.User,
		cfg.Database.Password,
		cfg.Database.Database,
		cfg.Database.SSLMode,
	)

	gormConfig := &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	}

	db, err := gorm.Open(postgres.Open(dsn), gormConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Get underlying SQL DB to configure connection pool
	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("failed to get database instance: %w", err)
	}

	// Configure connection pool
	sqlDB.SetMaxIdleConns(cfg.Database.MinConnections)
	sqlDB.SetMaxOpenConns(cfg.Database.MaxConnections)
	sqlDB.SetConnMaxLifetime(time.Hour)

	return &Database{db: db}, nil
}

// Migrate runs all database migrations
func (d *Database) Migrate() error {
	models := []interface{}{
		&models.Project{},
		&models.User{},
		&models.Session{},
		&models.Task{},
		&models.Worker{},
		&models.WorkerQueue{},
		&models.EventLog{},
		&models.ErrorLog{},
		&models.Notification{},
		&models.Integration{},
	}

	if err := d.db.AutoMigrate(models...); err != nil {
		return fmt.Errorf("migration failed: %w", err)
	}

	log.Println("Database migrations completed successfully")
	return nil
}

// Health checks the database connection
func (d *Database) Health() error {
	sqlDB, err := d.db.DB()
	if err != nil {
		return fmt.Errorf("failed to get database instance: %w", err)
	}

	return sqlDB.Ping()
}

// Close closes the database connection
func (d *Database) Close() error {
	sqlDB, err := d.db.DB()
	if err != nil {
		return fmt.Errorf("failed to get database instance: %w", err)
	}

	return sqlDB.Close()
}

// GetDB returns the underlying GORM DB instance
func (d *Database) GetDB() *gorm.DB {
	return d.db
}

// BeginTx starts a new database transaction
func (d *Database) BeginTx() *gorm.DB {
	return d.db.Begin()
}

// Stats returns database connection pool statistics
func (d *Database) Stats() map[string]interface{} {
	sqlDB, err := d.db.DB()
	if err != nil {
		return nil
	}

	dbStats := sqlDB.Stats()
	return map[string]interface{}{
		"open_connections": dbStats.OpenConnections,
		"in_use":           dbStats.InUse,
		"idle":             dbStats.Idle,
		"wait_count":       dbStats.WaitCount,
		"wait_duration":    dbStats.WaitDuration,
		"max_idle_closed":  dbStats.MaxIdleClosed,
		"max_lifetime_closed": dbStats.MaxLifetimeClosed,
	}
}
