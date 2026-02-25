package docs

import (
	"net/http"

	"github.com/gin-gonic/gin"
	appmodule "github.com/jgirmay/GAIA_GO/internal/app"
	"github.com/jgirmay/GAIA_GO/internal/api"
)

// DocumentationHandler manages API documentation endpoints
type DocumentationHandler struct {
	apps      []appmodule.App
	metadata  map[string]*appmodule.Metadata
	openAPI   *OpenAPISpec
	directory []AppInfo
}

// NewDocumentationHandler creates a new documentation handler
func NewDocumentationHandler(apps []appmodule.App, metadata map[string]*appmodule.Metadata) *DocumentationHandler {
	return &DocumentationHandler{
		apps:      apps,
		metadata:  metadata,
		openAPI:   GenerateOpenAPISpec(apps, metadata),
		directory: GenerateAppDirectory(apps, metadata),
	}
}

// RegisterRoutes registers documentation endpoints
func (h *DocumentationHandler) RegisterRoutes(engine *gin.Engine) {
	docs := engine.Group("/api/docs")
	{
		docs.GET("", h.handleDocIndex)
		docs.GET("/openapi.json", h.handleOpenAPISpec)
		docs.GET("/swagger", h.handleSwaggerUI)
		docs.GET("/apps", h.handleAppDirectory)
		docs.GET("/apps/:appName", h.handleAppDetails)
	}
}

// handleDocIndex returns documentation index
func (h *DocumentationHandler) handleDocIndex(c *gin.Context) {
	api.RespondWith(c, http.StatusOK, gin.H{
		"message": "GAIA API Documentation",
		"links": gin.H{
			"openapi": "/api/docs/openapi.json",
			"swagger": "/api/docs/swagger",
			"apps":    "/api/docs/apps",
		},
		"description": "Complete API documentation and discovery for GAIA educational applications",
	})
}

// handleOpenAPISpec returns the OpenAPI 3.0 specification
func (h *DocumentationHandler) handleOpenAPISpec(c *gin.Context) {
	c.JSON(http.StatusOK, h.openAPI)
}

// handleSwaggerUI returns HTML for Swagger UI
func (h *DocumentationHandler) handleSwaggerUI(c *gin.Context) {
	swaggerHTML := `
<!DOCTYPE html>
<html>
<head>
    <title>GAIA API Documentation</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@3/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
    <script>
        const ui = SwaggerUIBundle({
            url: "/api/docs/openapi.json",
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true
        })
    </script>
</body>
</html>
`
	c.Header("Content-Type", "text/html; charset=utf-8")
	c.String(http.StatusOK, swaggerHTML)
}

// handleAppDirectory returns list of all apps and their routes
func (h *DocumentationHandler) handleAppDirectory(c *gin.Context) {
	api.RespondWith(c, http.StatusOK, gin.H{
		"apps":   h.directory,
		"count":  len(h.directory),
		"status": "complete",
	})
}

// handleAppDetails returns details for a specific app
func (h *DocumentationHandler) handleAppDetails(c *gin.Context) {
	appName := c.Param("appName")

	// Find app in directory
	for _, appInfo := range h.directory {
		if appInfo.Name == appName {
			api.RespondWith(c, http.StatusOK, appInfo)
			return
		}
	}

	api.RespondWithError(c, api.NewError(
		api.ErrCodeNotFound,
		"App not found: "+appName,
		http.StatusNotFound,
	))
}
