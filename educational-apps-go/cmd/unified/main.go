package main

import (
	"fmt"
	"log"

	"github.com/architect/educational-apps/internal/analytics/handlers"
	"github.com/architect/educational-apps/internal/common/database"
	commonHandlers "github.com/architect/educational-apps/internal/common/handlers"
	"github.com/architect/educational-apps/internal/common/health"
	"github.com/architect/educational-apps/internal/common/middleware"
	comprehensionHandlers "github.com/architect/educational-apps/internal/comprehension/handlers"
	mathHandlers "github.com/architect/educational-apps/internal/math/handlers"
	migrationHandlers "github.com/architect/educational-apps/internal/migration/handlers"
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

	// Initialize health checker with database instance
	healthChecker := health.NewHealthChecker(database.GetDB(), "1.0.0")

	// Health check endpoints (production-grade)
	healthHandler := commonHandlers.NewHealthHandler(healthChecker)
	router.GET("/health", healthHandler.Health)
	router.GET("/health/readiness", healthHandler.Readiness)
	router.GET("/health/liveness", healthHandler.Liveness)
	router.GET("/health/metrics", healthHandler.Metrics)
	router.GET("/health/detailed", healthHandler.Detailed)

	// Import piano handlers (will be used below)
	// NOTE: In production, move these imports to the top of the file
	// import "github.com/architect/educational-apps/internal/piano/handlers"

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Piano app routes (handlers to be imported)
		pianoGroup := v1.Group("/piano")
		{
			// Exercise endpoints
			pianoGroup.GET("/exercises", func(c *gin.Context) {
				c.JSON(200, gin.H{
					"message": "GET /api/v1/piano/exercises",
					"status":  "placeholder - handlers not wired yet",
				})
			})
			pianoGroup.GET("/exercises/:id", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/piano/exercises/:id"})
			})
			pianoGroup.POST("/exercises", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(201, gin.H{"message": "POST /api/v1/piano/exercises"})
			})
			pianoGroup.PUT("/exercises/:id", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "PUT /api/v1/piano/exercises/:id"})
			})
			pianoGroup.DELETE("/exercises/:id", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(204, nil)
			})

			// Attempt endpoints
			pianoGroup.POST("/attempts", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(201, gin.H{"message": "POST /api/v1/piano/attempts"})
			})
			pianoGroup.GET("/attempts", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/piano/attempts"})
			})
			pianoGroup.GET("/exercises/:id/attempts", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/piano/exercises/:id/attempts"})
			})
			pianoGroup.GET("/exercises/:id/stats", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/piano/exercises/:id/stats"})
			})

			// Progress endpoints
			pianoGroup.GET("/progress", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/piano/progress"})
			})
			pianoGroup.GET("/leaderboard", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/piano/leaderboard"})
			})
			pianoGroup.DELETE("/progress", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "DELETE /api/v1/piano/progress"})
			})
		}

		// Typing app routes
		typingGroup := v1.Group("/typing")
		{
			// User endpoints
			typingGroup.POST("/users", func(c *gin.Context) {
				c.JSON(201, gin.H{"message": "POST /api/v1/typing/users"})
			})
			typingGroup.GET("/users/current", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/typing/users/current"})
			})
			typingGroup.GET("/users", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/typing/users"})
			})
			typingGroup.POST("/users/switch", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "POST /api/v1/typing/users/switch"})
			})
			typingGroup.DELETE("/users/:id", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "DELETE /api/v1/typing/users/:id"})
			})

			// Text endpoints
			typingGroup.POST("/text", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "POST /api/v1/typing/text"})
			})
			typingGroup.GET("/stats", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/typing/stats"})
			})

			// Result endpoints
			typingGroup.POST("/results", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(201, gin.H{"message": "POST /api/v1/typing/results"})
			})
			typingGroup.GET("/results", middleware.AuthRequired(), func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/typing/results"})
			})
			typingGroup.GET("/leaderboard", func(c *gin.Context) {
				c.JSON(200, gin.H{"message": "GET /api/v1/typing/leaderboard"})
			})
		}

		// Math app routes
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

		// Reading app routes
		readingGroup := v1.Group("/reading")
		{
			readingGroup.GET("/words", readingHandlers.GetWords)
			readingGroup.POST("/words", middleware.AuthRequired(), readingHandlers.AddWord)
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

		// Comprehension app routes
		comprehensionGroup := v1.Group("/comprehension")
		{
			comprehensionGroup.GET("/question_types", comprehensionHandlers.GetQuestionTypes)
			comprehensionGroup.GET("/subjects", comprehensionHandlers.GetSubjects)
			comprehensionGroup.GET("/difficulty_levels", comprehensionHandlers.GetDifficultyLevels)
			comprehensionGroup.GET("/questions", comprehensionHandlers.ListQuestions)
			comprehensionGroup.GET("/questions/:id", comprehensionHandlers.GetQuestion)
			comprehensionGroup.POST("/check", middleware.AuthRequired(), comprehensionHandlers.CheckAnswer)
			comprehensionGroup.POST("/save_progress", middleware.AuthRequired(), comprehensionHandlers.SaveProgress)
			comprehensionGroup.GET("/stats", middleware.AuthRequired(), comprehensionHandlers.GetStats)
			comprehensionGroup.POST("/seed", comprehensionHandlers.SeedData)
		}

		// Analytics & Gamification routes
		analyticsGroup := v1.Group("/analytics")
		{
			// Gamification
			analyticsGroup.GET("/gamification/profile", middleware.AuthRequired(), handlers.GetGamificationProfile)
			analyticsGroup.POST("/xp", handlers.AwardXP)
			analyticsGroup.POST("/streak/checkin", middleware.AuthRequired(), handlers.CheckInStreak)
			analyticsGroup.GET("/achievements", handlers.GetAchievements)
			analyticsGroup.GET("/achievements/user", middleware.AuthRequired(), handlers.GetUserAchievements)

			// Profile & Dashboard
			analyticsGroup.GET("/profile", middleware.AuthRequired(), handlers.GetUserProfile)
			analyticsGroup.GET("/dashboard", middleware.AuthRequired(), handlers.GetDashboard)
			analyticsGroup.GET("/stats", middleware.AuthRequired(), handlers.GetUserStats)
			analyticsGroup.GET("/recommendations", middleware.AuthRequired(), handlers.GetRecommendations)

			// Leaderboards
			analyticsGroup.GET("/leaderboard", handlers.GetLeaderboard)

			// Goals
			analyticsGroup.GET("/goals", middleware.AuthRequired(), handlers.GetUserGoals)
			analyticsGroup.POST("/goals", middleware.AuthRequired(), handlers.CreateGoal)
			analyticsGroup.PUT("/goals/:id", middleware.AuthRequired(), handlers.UpdateGoal)
			analyticsGroup.DELETE("/goals/:id", middleware.AuthRequired(), handlers.DeleteGoal)

			// Activity
			analyticsGroup.GET("/activity", middleware.AuthRequired(), handlers.GetRecentActivity)

			// Seed
			analyticsGroup.POST("/seed", handlers.SeedAchievements)
		}

		// Data Migration routes
		migrationGroup := v1.Group("/migration")
		{
			migrationGroup.POST("/start", migrationHandlers.StartMigration)
			migrationGroup.POST("/dry-run", migrationHandlers.DryRunMigration)
			migrationGroup.POST("/validate", migrationHandlers.ValidateMigration)
			migrationGroup.GET("/:id/status", migrationHandlers.GetMigrationStatus)
			migrationGroup.GET("/:id/summary", migrationHandlers.GetMigrationSummary)
			migrationGroup.POST("/:id/rollback", migrationHandlers.RollbackMigration)
			migrationGroup.GET("/schema/:table", migrationHandlers.GetMigrationSchema)
			migrationGroup.GET("/tables", migrationHandlers.ListSupportedTables)
		}
	}

	// Start server
	address := fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port)
	logger.Info("Starting unified server", zap.String("address", address))
	logger.Info(fmt.Sprintf("Listening on %s", address))

	if err := router.Run(address); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
