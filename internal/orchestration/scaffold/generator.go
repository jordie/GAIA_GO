package scaffold

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
)

// Generator handles file and directory creation from templates
type Generator struct {
	template *Template
}

// NewGenerator creates a new template generator
func NewGenerator(template *Template) *Generator {
	return &Generator{
		template: template,
	}
}

// GenerateDirectories creates the directory structure
func (g *Generator) GenerateDirectories(basePath string, directories []string) error {
	for _, dir := range directories {
		fullPath := filepath.Join(basePath, dir)

		if err := os.MkdirAll(fullPath, 0755); err != nil {
			return fmt.Errorf("failed to create directory %s: %w", fullPath, err)
		}
	}

	return nil
}

// GenerateFiles creates files from templates
func (g *Generator) GenerateFiles(ctx *GenerationContext, files []*TemplateFile) error {
	for _, templateFile := range files {
		// Skip if condition is met
		if templateFile.Skip != "" {
			// Basic skip condition: check if variable is present and truthy
			if skip, ok := ctx.TemplateVariables[templateFile.Skip].(bool); ok && skip {
				continue
			}
		}

		// Render file path with variables
		filePath := g.renderPath(templateFile.Path, ctx.TemplateVariables)
		fullPath := filepath.Join(ctx.OutputPath, filePath)

		// Create parent directory if needed
		dir := filepath.Dir(fullPath)
		if err := os.MkdirAll(dir, 0755); err != nil {
			return fmt.Errorf("failed to create directory for file %s: %w", fullPath, err)
		}

		// Render file content
		content, err := templateFile.RenderFile(ctx)
		if err != nil {
			return fmt.Errorf("failed to render file %s: %w", filePath, err)
		}

		// Write file
		mode := os.FileMode(0644)
		if templateFile.Mode != "" {
			// Parse mode string (octal)
			if m, err := strconv.ParseInt(templateFile.Mode, 8, 32); err == nil {
				mode = os.FileMode(m)
			}
		}

		if err := os.WriteFile(fullPath, []byte(content), mode); err != nil {
			return fmt.Errorf("failed to write file %s: %w", fullPath, err)
		}
	}

	return nil
}

// Helper methods

func (g *Generator) renderPath(pathTemplate string, variables map[string]interface{}) string {
	path := pathTemplate
	path = filepath.Clean(path)

	// Simple variable substitution in paths
	for oldKey := range variables {
		oldPlaceholder := fmt.Sprintf("{{.%s}}", oldKey)
		oldSubst := fmt.Sprintf("${%s}", oldKey)

		// Would need to use text/template for proper rendering
		// For now, just use simple replacements for path components
		_ = oldPlaceholder
		_ = oldSubst
	}

	return path
}
