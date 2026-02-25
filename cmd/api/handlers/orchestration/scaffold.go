package orchestration

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api/dtos"
	"github.com/jgirmay/GAIA_GO/internal/orchestration/scaffold"
)

// ScaffoldHandler handles project scaffolding HTTP requests
type ScaffoldHandler struct {
	scaffolder *scaffold.Scaffolder
}

// NewScaffoldHandler creates a new scaffold handler
func NewScaffoldHandler(scaffolder *scaffold.Scaffolder) *ScaffoldHandler {
	return &ScaffoldHandler{
		scaffolder: scaffolder,
	}
}

// RegisterRoutes registers scaffold routes
func (h *ScaffoldHandler) RegisterRoutes(router *gin.RouterGroup) {
	scaffoldGroup := router.Group("/scaffold")
	{
		scaffoldGroup.GET("/templates", h.ListTemplates)
		scaffoldGroup.GET("/templates/:templateName", h.GetTemplate)
		scaffoldGroup.POST("", h.GenerateProject)
		scaffoldGroup.POST("/validate", h.ValidateProject)
	}
}

// ListTemplates lists all available templates
// @Summary List templates
// @Description Returns all available project templates
// @Tags Scaffold
// @Produce json
// @Success 200 {array} dtos.TemplateResponse
// @Router /api/orchestration/scaffold/templates [get]
func (h *ScaffoldHandler) ListTemplates(c *gin.Context) {
	templates, err := h.scaffolder.ListTemplates()
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "list_templates_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	var responses []*dtos.TemplateResponse
	for _, tmpl := range templates {
		responses = append(responses, &dtos.TemplateResponse{
			Name:        tmpl.Name,
			DisplayName: tmpl.DisplayName,
			Description: tmpl.Description,
			Version:     tmpl.Version,
			Language:    tmpl.Language,
			Framework:   tmpl.Framework,
		})
	}

	c.JSON(http.StatusOK, responses)
}

// GetTemplate retrieves a specific template with full details
// @Summary Get template
// @Description Retrieves details of a specific template
// @Tags Scaffold
// @Produce json
// @Param templateName path string true "Template name"
// @Success 200 {object} dtos.TemplateDetailsResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/scaffold/templates/{templateName} [get]
func (h *ScaffoldHandler) GetTemplate(c *gin.Context) {
	templateName := c.Param("templateName")

	tmpl, err := h.scaffolder.GetTemplate(templateName)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "template_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	// Build response with full details
	response := &dtos.TemplateDetailsResponse{
		TemplateResponse: &dtos.TemplateResponse{
			Name:        tmpl.Name,
			DisplayName: tmpl.DisplayName,
			Description: tmpl.Description,
			Version:     tmpl.Version,
			Language:    tmpl.Language,
			Framework:   tmpl.Framework,
		},
		Variables: make([]*dtos.TemplateVariableResponse, 0),
		Hooks:     make(map[string][]string),
	}

	// Convert variables
	for _, v := range tmpl.Variables {
		response.Variables = append(response.Variables, &dtos.TemplateVariableResponse{
			Name:        v.Name,
			Description: v.Description,
			Type:        v.Type,
			Required:    v.Required,
			Default:     v.Default,
		})
	}

	// Add hooks
	if tmpl.Hooks != nil {
		response.Hooks["pre_generate"] = tmpl.Hooks.PreGenerate
		response.Hooks["post_generate"] = tmpl.Hooks.PostGenerate
	}

	c.JSON(http.StatusOK, response)
}

// GenerateProject generates a new project from a template
// @Summary Generate project
// @Description Creates a new project from a specified template
// @Tags Scaffold
// @Accept json
// @Produce json
// @Param request body dtos.GenerateProjectRequest true "Project configuration"
// @Success 201 {object} dtos.ProjectGenerationResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/scaffold [post]
func (h *ScaffoldHandler) GenerateProject(c *gin.Context) {
	var req dtos.GenerateProjectRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	config := &scaffold.ScaffoldConfig{
		Name:         req.Name,
		TemplateName: req.TemplateName,
		OutputPath:   req.OutputPath,
		Variables:    req.Variables,
	}

	if err := h.scaffolder.GenerateProject(config); err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "project_generation_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	// Validate project to get file/dir counts
	if err := h.scaffolder.ValidateProject(config.OutputPath); err != nil {
		// Generation succeeded even if validation fails
	}

	response := &dtos.ProjectGenerationResponse{
		ProjectName: req.Name,
		ProjectPath: req.OutputPath,
		Template:    req.TemplateName,
		CreatedAt:   time.Now(),
		FilesCount:  0, // Would be actual count if we implement directory walking
		DirsCount:   0,
	}

	c.JSON(http.StatusCreated, response)
}

// ValidateProject validates that a project has proper structure
// @Summary Validate project
// @Description Checks if a generated project is valid
// @Tags Scaffold
// @Accept json
// @Produce json
// @Param request body dtos.ValidateProjectRequest true "Project path"
// @Success 200 {object} dtos.ValidateProjectResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/scaffold/validate [post]
func (h *ScaffoldHandler) ValidateProject(c *gin.Context) {
	var req dtos.ValidateProjectRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	err := h.scaffolder.ValidateProject(req.Path)
	response := &dtos.ValidateProjectResponse{
		Path: req.Path,
	}

	if err != nil {
		response.IsValid = false
		response.Message = err.Error()
	} else {
		response.IsValid = true
		response.Message = "Project is valid"
	}

	c.JSON(http.StatusOK, response)
}
