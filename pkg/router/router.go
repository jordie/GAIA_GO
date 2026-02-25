package router

import (
	"database/sql"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/app"
	"github.com/jgirmay/GAIA_GO/internal/codegen"
	"github.com/jgirmay/GAIA_GO/internal/docs"
	"github.com/jgirmay/GAIA_GO/internal/health"
	"github.com/jgirmay/GAIA_GO/internal/metrics"
	"github.com/jgirmay/GAIA_GO/internal/middleware"
	"github.com/jgirmay/GAIA_GO/internal/session"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// AppRouter handles all education app routes
type AppRouter struct {
	engine           *gin.Engine
	sessionManager   *session.Manager
	authMiddleware   gin.HandlerFunc
	requireAuth      gin.HandlerFunc
	metricsRegistry  *metrics.HTTPMetricsRegistry
	businessMetrics  *metrics.BusinessMetricsRegistry
}

// NewAppRouter creates a new unified application router
func NewAppRouter(sessionManager *session.Manager) *AppRouter {
	engine := gin.Default()

	return &AppRouter{
		engine:         engine,
		sessionManager: sessionManager,
		authMiddleware: middleware.AuthMiddleware(sessionManager),
		requireAuth:    middleware.RequireAuth(),
	}
}

// GetEngine returns the Gin engine for the router
func (r *AppRouter) GetEngine() *gin.Engine {
	return r.engine
}

// RegisterMiddleware registers global middleware
func (r *AppRouter) RegisterMiddleware() {
	// Add metrics middleware FIRST to capture all requests including errors
	if r.metricsRegistry != nil {
		r.engine.Use(middleware.MetricsMiddleware(r.metricsRegistry))
	}

	// Apply authentication middleware to all routes
	r.engine.Use(r.authMiddleware)

	// Add recovery middleware
	r.engine.Use(gin.Recovery())

	// Add CORS if needed
	r.engine.Use(corsMiddleware())
}

// RegisterAuthRoutes registers authentication endpoints
func (r *AppRouter) RegisterAuthRoutes() {
	auth := r.engine.Group("/api/auth")
	{
		// Login endpoints
		auth.POST("/login", r.handleLogin)
		auth.POST("/register", r.handleRegister)
		auth.POST("/logout", r.handleLogout)

		// Auto-login via device fingerprint
		auth.POST("/auto-login", r.handleAutoLogin)
		auth.POST("/remember-device", r.handleRememberDevice)
		auth.POST("/forget-device", r.handleForgetDevice)

		// Current user info
		auth.GET("/me", r.handleGetCurrentUser)
	}
}

// RegisterUserRoutes registers user management endpoints
func (r *AppRouter) RegisterUserRoutes() {
	users := r.engine.Group("/api/users")
	users.Use(r.authMiddleware)
	{
		users.GET("", r.handleListUsers)
		users.GET("/:id", r.handleGetUser)
		users.POST("", r.handleCreateUser)
		users.PUT("/:id", r.requireAuth, r.handleUpdateUser)
	}
}

// RegisterAppRoutes registers group for app-specific routes
func (r *AppRouter) RegisterAppRoutes(appName string) *gin.RouterGroup {
	group := r.engine.Group("/api/" + appName)
	group.Use(r.authMiddleware)
	return group
}

// RegisterStaticFiles serves static files for apps
func (r *AppRouter) RegisterStaticFiles(appName, staticDir string) {
	// App-specific static files
	r.engine.Static("/"+appName+"/static", staticDir)
}

// RegisterSharedStaticFiles serves shared static files (call once)
func (r *AppRouter) RegisterSharedStaticFiles() {
	r.engine.Static("/shared_static", "./web/static")
}

// RegisterTemplates sets up template rendering
func (r *AppRouter) RegisterTemplates(templateDir string) {
	r.engine.LoadHTMLGlob(templateDir)
}

// RegisterDocumentation registers API documentation routes
func (r *AppRouter) RegisterDocumentation(apps []app.App, metadata map[string]*app.Metadata) {
	docHandler := docs.NewDocumentationHandler(apps, metadata)
	docHandler.RegisterRoutes(r.engine)
}

// RegisterHealthCheck registers health check routes
func (r *AppRouter) RegisterHealthCheck(db *sql.DB, apps []app.App, metadata map[string]*app.Metadata) {
	checker := health.NewHealthChecker(db, apps, metadata)
	healthHandler := health.NewHealthHandler(checker)
	healthHandler.RegisterRoutes(r.engine)
}

// RegisterSDKGeneration registers SDK generation routes
func (r *AppRouter) RegisterSDKGeneration(spec *docs.OpenAPISpec) {
	codegenHandler := codegen.NewCodegenHandler(spec)
	codegenHandler.RegisterRoutes(r.engine)
}

// RegisterMetricsEndpoint registers the /metrics endpoint for HTTP API metrics
func (r *AppRouter) RegisterMetricsEndpoint(registry *metrics.HTTPMetricsRegistry) {
	r.engine.GET("/metrics", gin.WrapH(promhttp.HandlerFor(registry.GetPrometheusRegistry(), promhttp.HandlerOpts{
		EnableOpenMetrics: true,
	})))
}

// ============================================================================
// HANDLER FUNCTIONS
// ============================================================================

func (r *AppRouter) handleLogin(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "login handler not yet implemented"})
}

func (r *AppRouter) handleRegister(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "register handler not yet implemented"})
}

func (r *AppRouter) handleLogout(c *gin.Context) {
	sess, _ := middleware.GetSession(c)
	if sess != nil {
		_ = r.sessionManager.InvalidateSession(sess.ID)
	}
	middleware.ClearAuthCookie(c)
	c.JSON(200, gin.H{"success": true})
}

func (r *AppRouter) handleAutoLogin(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "auto-login handler not yet implemented"})
}

func (r *AppRouter) handleRememberDevice(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "remember-device handler not yet implemented"})
}

func (r *AppRouter) handleForgetDevice(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "forget-device handler not yet implemented"})
}

func (r *AppRouter) handleGetCurrentUser(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(401, gin.H{"error": "not authenticated"})
		return
	}

	user, err := r.sessionManager.GetUser(userID)
	if err != nil {
		c.JSON(404, gin.H{"error": "user not found"})
		return
	}

	c.JSON(200, user)
}

func (r *AppRouter) handleListUsers(c *gin.Context) {
	users, err := r.sessionManager.ListUsers()
	if err != nil {
		c.JSON(500, gin.H{"error": "failed to list users"})
		return
	}
	c.JSON(200, users)
}

func (r *AppRouter) handleGetUser(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "get user handler not yet implemented"})
}

func (r *AppRouter) handleCreateUser(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "create user handler not yet implemented"})
}

func (r *AppRouter) handleUpdateUser(c *gin.Context) {
	// To be implemented
	c.JSON(200, gin.H{"status": "update user handler not yet implemented"})
}

// ============================================================================
// MIDDLEWARE HELPERS
// ============================================================================

func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}
