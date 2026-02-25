package scaffold

import (
	"bytes"
	"fmt"
	"text/template"
)

// Template represents a project template with metadata and file definitions
type Template struct {
	Name              string          `yaml:"name"`
	DisplayName       string          `yaml:"display_name"`
	Description       string          `yaml:"description"`
	Version           string          `yaml:"version"`
	Language          string          `yaml:"language"`
	Framework         string          `yaml:"framework"`
	Variables         []*TemplateVar  `yaml:"variables"`
	DirectoryStructure []string        `yaml:"directories"`
	Files             []*TemplateFile `yaml:"files"`
	Hooks             *TemplateHooks  `yaml:"hooks"`
}

// TemplateVar represents a variable that can be substituted in a template
type TemplateVar struct {
	Name        string      `yaml:"name"`
	Description string      `yaml:"description"`
	Type        string      `yaml:"type"` // string, int, bool
	Required    bool        `yaml:"required"`
	Default     interface{} `yaml:"default"`
	Validation  string      `yaml:"validation"` // Optional regex pattern
}

// TemplateFile represents a file to be created from a template
type TemplateFile struct {
	Path     string `yaml:"path"`
	Template string `yaml:"template"` // Inline template content
	Mode     string `yaml:"mode"`     // File permissions, e.g., "0755"
	Skip     string `yaml:"skip"`     // Optional condition to skip file
}

// TemplateHooks represents pre/post generation hooks
type TemplateHooks struct {
	PreGenerate  []string `yaml:"pre_generate"`
	PostGenerate []string `yaml:"post_generate"`
}

// GenerationContext holds variables and context for template generation
type GenerationContext struct {
	TemplateVariables map[string]interface{}
	OutputPath        string
	Template          *Template
}

// RenderFile renders a template file with the given context
func (tf *TemplateFile) RenderFile(ctx *GenerationContext) (string, error) {
	// Parse the template
	tmpl, err := template.New(tf.Path).Parse(tf.Template)
	if err != nil {
		return "", fmt.Errorf("failed to parse template for %s: %w", tf.Path, err)
	}

	// Execute template with variables
	var result bytes.Buffer
	if err := tmpl.Execute(&result, ctx.TemplateVariables); err != nil {
		return "", fmt.Errorf("failed to render template for %s: %w", tf.Path, err)
	}

	return result.String(), nil
}

// ValidateTemplate checks if template has required structure
func (t *Template) ValidateTemplate() error {
	if t.Name == "" {
		return fmt.Errorf("template name is required")
	}
	if t.Language == "" {
		return fmt.Errorf("template language is required")
	}

	// Check variable names are unique
	varNames := make(map[string]bool)
	for _, v := range t.Variables {
		if varNames[v.Name] {
			return fmt.Errorf("duplicate variable name: %s", v.Name)
		}
		varNames[v.Name] = true
	}

	return nil
}

// ValidateVariables checks if provided variables satisfy template requirements
func (t *Template) ValidateVariables(provided map[string]interface{}) error {
	for _, templateVar := range t.Variables {
		if templateVar.Required {
			if _, exists := provided[templateVar.Name]; !exists {
				return fmt.Errorf("required variable missing: %s", templateVar.Name)
			}
		}
	}
	return nil
}

// MergeVariables merges provided variables with defaults
func (t *Template) MergeVariables(provided map[string]interface{}) map[string]interface{} {
	merged := make(map[string]interface{})

	// Add defaults first
	for _, templateVar := range t.Variables {
		if templateVar.Default != nil {
			merged[templateVar.Name] = templateVar.Default
		}
	}

	// Override with provided values
	for k, v := range provided {
		merged[k] = v
	}

	return merged
}
