package scaffold

import (
	"fmt"
	"os"
	"os/exec"
	"sync"
)

// Scaffolder manages project generation from templates
type Scaffolder struct {
	registry      *Registry
	templatesMutex sync.RWMutex
}

// NewScaffolder creates a new project scaffolder
func NewScaffolder(templatesDir string) (*Scaffolder, error) {
	registry, err := NewRegistry(templatesDir)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize template registry: %w", err)
	}

	return &Scaffolder{
		registry: registry,
	}, nil
}

// GenerateProject creates a new project from a template
func (s *Scaffolder) GenerateProject(config *ScaffoldConfig) error {
	// Validate config
	if config.Name == "" {
		return fmt.Errorf("project name is required")
	}
	if config.TemplateName == "" {
		return fmt.Errorf("template name is required")
	}
	if config.OutputPath == "" {
		return fmt.Errorf("output path is required")
	}

	// Get template
	template, err := s.registry.GetTemplate(config.TemplateName)
	if err != nil {
		return fmt.Errorf("failed to load template: %w", err)
	}

	// Validate template
	if err := template.ValidateTemplate(); err != nil {
		return fmt.Errorf("template validation failed: %w", err)
	}

	// Merge and validate variables
	if err := template.ValidateVariables(config.Variables); err != nil {
		return fmt.Errorf("variable validation failed: %w", err)
	}

	variables := template.MergeVariables(config.Variables)
	variables["ProjectName"] = config.Name
	variables["ProjectPath"] = config.OutputPath

	// Create output directory
	if err := os.MkdirAll(config.OutputPath, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}

	// Run pre-generation hooks
	if template.Hooks != nil {
		for _, hook := range template.Hooks.PreGenerate {
			if err := s.executeHook(hook, config.OutputPath); err != nil {
				return fmt.Errorf("pre-generation hook failed: %w", err)
			}
		}
	}

	// Create directory structure
	generator := NewGenerator(template)
	if err := generator.GenerateDirectories(config.OutputPath, template.DirectoryStructure); err != nil {
		return fmt.Errorf("failed to create directories: %w", err)
	}

	// Generate files
	ctx := &GenerationContext{
		TemplateVariables: variables,
		OutputPath:        config.OutputPath,
		Template:          template,
	}

	if err := generator.GenerateFiles(ctx, template.Files); err != nil {
		return fmt.Errorf("failed to generate files: %w", err)
	}

	// Run post-generation hooks
	if template.Hooks != nil {
		for _, hook := range template.Hooks.PostGenerate {
			if err := s.executeHook(hook, config.OutputPath); err != nil {
				return fmt.Errorf("post-generation hook failed: %w", err)
			}
		}
	}

	return nil
}

// GetTemplate retrieves a template by name
func (s *Scaffolder) GetTemplate(name string) (*Template, error) {
	return s.registry.GetTemplate(name)
}

// ListTemplates returns all available templates
func (s *Scaffolder) ListTemplates() ([]*TemplateMetadata, error) {
	return s.registry.ListTemplates()
}

// RegisterTemplate manually registers a template
func (s *Scaffolder) RegisterTemplate(template *Template) error {
	return s.registry.RegisterTemplate(template)
}

// ValidateProject checks if a generated project has valid structure
func (s *Scaffolder) ValidateProject(projectPath string) error {
	// Check if path exists
	info, err := os.Stat(projectPath)
	if err != nil {
		return fmt.Errorf("project path does not exist: %w", err)
	}

	if !info.IsDir() {
		return fmt.Errorf("project path is not a directory")
	}

	// Check for required files (varies by template)
	// This is a basic check - specific validations would depend on project type
	hasContent := false
	entries, err := os.ReadDir(projectPath)
	if err != nil {
		return fmt.Errorf("failed to read project directory: %w", err)
	}

	if len(entries) > 0 {
		hasContent = true
	}

	if !hasContent {
		return fmt.Errorf("project directory is empty")
	}

	return nil
}

// Helper methods

func (s *Scaffolder) executeHook(hookCmd string, workDir string) error {
	cmd := exec.Command("bash", "-c", hookCmd)
	cmd.Dir = workDir

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("hook execution failed: %w", err)
	}

	return nil
}

// ScaffoldConfig holds configuration for project generation
type ScaffoldConfig struct {
	Name         string                 `json:"name"`
	TemplateName string                 `json:"template"`
	OutputPath   string                 `json:"path"`
	Variables    map[string]interface{} `json:"variables"`
}

// TemplateMetadata represents template summary information
type TemplateMetadata struct {
	Name        string `json:"name"`
	DisplayName string `json:"display_name"`
	Description string `json:"description"`
	Version     string `json:"version"`
	Language    string `json:"language"`
	Framework   string `json:"framework"`
}
