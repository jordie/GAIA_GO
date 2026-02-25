package main

import (
	"fmt"
	"log"
	"os"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/middleware"
	mathHandlers "github.com/architect/educational-apps/internal/math/handlers"
	"github.com/architect/educational-apps/pkg/config"
	"github.com/architect/educational-apps/pkg/logger"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Override port for math app if MATH_PORT is set
	if mathPort := os.Getenv("MATH_PORT"); mathPort != "" {
		cfg.Server.Port = mathPort
	} else {
		// Default math app port
		cfg.Server.Port = "2000"
	}

	// Initialize logger
	if err := logger.Init(cfg.Server.Env); err != nil {
		log.Fatalf("Failed to initialize logger: %v", err)
	}

	// Initialize database (SQLite for development, PostgreSQL for production)
	if err := database.InitWithType(cfg.Database.Type, cfg.Database.DSN); err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	// Create Gin engine
	router := gin.Default()

	// Apply middleware
	router.Use(middleware.CORSMiddleware())
	router.Use(middleware.LoggerMiddleware())
	router.Use(middleware.ErrorHandler())

	// Health check endpoint
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status": "ok",
			"app":    "math",
		})
	})

	// API v1 routes - Math app only
	v1 := router.Group("/api/v1")
	{
		mathGroup := v1.Group("/math")
		{
			mathGroup.POST("/problems/generate", mathHandlers.GenerateProblem)
			mathGroup.POST("/problems/check", middleware.AuthRequired(), mathHandlers.CheckAnswer)
			mathGroup.POST("/sessions/save", middleware.AuthRequired(), mathHandlers.SaveSession)
			mathGroup.GET("/stats", middleware.AuthRequired(), mathHandlers.GetStats)
			mathGroup.GET("/weaknesses", middleware.AuthRequired(), mathHandlers.GetWeaknesses)
			mathGroup.GET("/practice-plan", middleware.AuthRequired(), mathHandlers.GetPracticePlan)
			mathGroup.GET("/learning-profile", middleware.AuthRequired(), mathHandlers.GetLearningProfile)
		}
	}

	// Start server
	address := fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port)
	logger.Info("Starting Math app server",
		zap.String("address", address),
		zap.String("env", cfg.Server.Env),
	)
	logger.Info(fmt.Sprintf("Math app listening on http://%s", address))

	if err := router.Run(address); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
