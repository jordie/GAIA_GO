package main

import (
	"fmt"
	"log"
	"os"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/middleware"
	readingHandlers "github.com/architect/educational-apps/internal/reading/handlers"
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

	// Override port for reading app if READING_PORT is set
	if readingPort := os.Getenv("READING_PORT"); readingPort != "" {
		cfg.Server.Port = readingPort
	} else {
		// Default reading app port
		cfg.Server.Port = "2001"
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
			"app":    "reading",
		})
	})

	// API v1 routes - Reading app only
	v1 := router.Group("/api/v1")
	{
		readingGroup := v1.Group("/reading")
		{
			readingGroup.GET("/words", readingHandlers.GetWords)
			readingGroup.POST("/results", middleware.AuthRequired(), readingHandlers.SaveReadingResult)
			readingGroup.GET("/stats", middleware.AuthRequired(), readingHandlers.GetReadingStats)
			readingGroup.GET("/weaknesses", middleware.AuthRequired(), readingHandlers.GetWeaknesses)
			readingGroup.GET("/practice-plan", middleware.AuthRequired(), readingHandlers.GetPracticePlan)
			readingGroup.GET("/learning-profile", middleware.AuthRequired(), readingHandlers.GetLearningProfile)
			readingGroup.GET("/quizzes", readingHandlers.ListQuizzes)
			readingGroup.POST("/quizzes", middleware.AuthRequired(), readingHandlers.CreateQuiz)
			readingGroup.GET("/quizzes/:id", readingHandlers.GetQuiz)
			readingGroup.POST("/quizzes/:id/submit", middleware.AuthRequired(), readingHandlers.SubmitQuiz)
			readingGroup.GET("/quizzes/attempts/:attempt_id", readingHandlers.GetQuizResults)
		}
	}

	// Start server
	address := fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port)
	logger.Info("Starting Reading app server",
		zap.String("address", address),
		zap.String("env", cfg.Server.Env),
	)
	logger.Info(fmt.Sprintf("Reading app listening on http://%s", address))

	if err := router.Run(address); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
