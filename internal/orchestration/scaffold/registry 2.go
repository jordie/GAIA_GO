package scaffold

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"gopkg.in/yaml.v3"
)

// Registry manages template loading and caching
type Registry struct {
	templatesDir string
	templates    map[string]*Template
	mutex        sync.RWMutex
}

// NewRegistry creates a new template registry
func NewRegistry(templatesDir string) (*Registry, error) {
	registry := &Registry{
		templatesDir: templatesDir,
		templates:    make(map[string]*Template),
	}

	// Ensure templates directory exists
	if err := os.MkdirAll(templatesDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create templates directory: %w", err)
	}

	// Load all templates from disk
	if err := registry.loadTemplates(); err != nil {
		return nil, fmt.Errorf("failed to load templates: %w", err)
	}

	return registry, nil
}

// GetTemplate retrieves a template by name
func (r *Registry) GetTemplate(name string) (*Template, error) {
	r.mutex.RLock()
	template, exists := r.templates[name]
	r.mutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("template not found: %s", name)
	}

	return template, nil
}

// ListTemplates returns all available templates
func (r *Registry) ListTemplates() ([]*TemplateMetadata, error) {
	r.mutex.RLock()
	defer r.mutex.RUnlock()

	metadata := make([]*TemplateMetadata, 0, len(r.templates))
	for _, template := range r.templates {
		metadata = append(metadata, &TemplateMetadata{
			Name:        template.Name,
			DisplayName: template.DisplayName,
			Description: template.Description,
			Version:     template.Version,
			Language:    template.Language,
			Framework:   template.Framework,
		})
	}

	return metadata, nil
}

// RegisterTemplate manually registers a template
func (r *Registry) RegisterTemplate(template *Template) error {
	if err := template.ValidateTemplate(); err != nil {
		return fmt.Errorf("invalid template: %w", err)
	}

	r.mutex.Lock()
	r.templates[template.Name] = template
	r.mutex.Unlock()

	return nil
}

// ReloadTemplates reloads all templates from disk
func (r *Registry) ReloadTemplates() error {
	r.mutex.Lock()
	r.templates = make(map[string]*Template)
	r.mutex.Unlock()

	return r.loadTemplates()
}

// Helper methods

func (r *Registry) loadTemplates() error {
	entries, err := os.ReadDir(r.templatesDir)
	if err != nil {
		// If directory doesn't exist yet, that's OK
		if os.IsNotExist(err) {
			return nil
		}
		return fmt.Errorf("failed to read templates directory: %w", err)
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		templatePath := filepath.Join(r.templatesDir, entry.Name())
		if err := r.loadTemplate(templatePath); err != nil {
			// Log but don't fail - other templates might be valid
			fmt.Printf("warning: failed to load template %s: %v\n", entry.Name(), err)
		}
	}

	return nil
}

func (r *Registry) loadTemplate(templatePath string) error {
	// Look for template.yaml or template.yml
	configPath := filepath.Join(templatePath, "template.yaml")
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		configPath = filepath.Join(templatePath, "template.yml")
	}

	data, err := os.ReadFile(configPath)
	if err != nil {
		return fmt.Errorf("failed to read template config: %w", err)
	}

	var template Template
	if err := yaml.Unmarshal(data, &template); err != nil {
		return fmt.Errorf("failed to parse template YAML: %w", err)
	}

	// Load template files from files/ subdirectory
	filesPath := filepath.Join(templatePath, "files")
	if err := r.loadTemplateFiles(&template, filesPath); err != nil {
		return fmt.Errorf("failed to load template files: %w", err)
	}

	// Validate template
	if err := template.ValidateTemplate(); err != nil {
		return fmt.Errorf("template validation failed: %w", err)
	}

	r.mutex.Lock()
	r.templates[template.Name] = &template
	r.mutex.Unlock()

	return nil
}

func (r *Registry) loadTemplateFiles(template *Template, filesPath string) error {
	entries, err := os.ReadDir(filesPath)
	if err != nil {
		// Files directory is optional
		if os.IsNotExist(err) {
			return nil
		}
		return fmt.Errorf("failed to read files directory: %w", err)
	}

	for _, entry := range entries {
		filePath := filepath.Join(filesPath, entry.Name())

		// Get relative path for the template file
		relativePath := entry.Name()

		// Read file content
		content, err := os.ReadFile(filePath)
		if err != nil {
			return fmt.Errorf("failed to read file %s: %w", filePath, err)
		}

		// Add to template files
		template.Files = append(template.Files, &TemplateFile{
			Path:     relativePath,
			Template: string(content),
		})
	}

	return nil
}
