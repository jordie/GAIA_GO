package docs

import (
	"fmt"

	appmodule "github.com/jgirmay/GAIA_GO/internal/app"
)

// OpenAPISpec represents an OpenAPI 3.0 specification
type OpenAPISpec struct {
	OpenAPI    string                 `json:"openapi"`
	Info       Info                   `json:"info"`
	Servers    []Server               `json:"servers"`
	Paths      map[string]PathItem    `json:"paths"`
	Components *Components            `json:"components,omitempty"`
	Tags       []Tag                  `json:"tags"`
}

// Info contains metadata about the API
type Info struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Version     string `json:"version"`
	Contact     Contact `json:"contact,omitempty"`
	License     License `json:"license,omitempty"`
}

// Contact information for the API
type Contact struct {
	Name  string `json:"name,omitempty"`
	Email string `json:"email,omitempty"`
	URL   string `json:"url,omitempty"`
}

// License information
type License struct {
	Name string `json:"name"`
	URL  string `json:"url,omitempty"`
}

// Server information
type Server struct {
	URL         string `json:"url"`
	Description string `json:"description,omitempty"`
}

// PathItem represents an API path
type PathItem struct {
	Get    *Operation `json:"get,omitempty"`
	Post   *Operation `json:"post,omitempty"`
	Put    *Operation `json:"put,omitempty"`
	Delete *Operation `json:"delete,omitempty"`
	Patch  *Operation `json:"patch,omitempty"`
}

// Operation represents an HTTP operation
type Operation struct {
	Summary     string            `json:"summary,omitempty"`
	Description string            `json:"description,omitempty"`
	Tags        []string          `json:"tags,omitempty"`
	Parameters  []Parameter       `json:"parameters,omitempty"`
	RequestBody *RequestBody      `json:"requestBody,omitempty"`
	Responses   map[string]Response `json:"responses"`
	OperationID string            `json:"operationId,omitempty"`
}

// Parameter represents a query, path, or header parameter
type Parameter struct {
	Name        string `json:"name"`
	In          string `json:"in"` // query, path, header, cookie
	Description string `json:"description,omitempty"`
	Required    bool   `json:"required"`
	Schema      Schema `json:"schema"`
}

// RequestBody represents request body specification
type RequestBody struct {
	Description string `json:"description,omitempty"`
	Required    bool   `json:"required"`
	Content     map[string]MediaType `json:"content"`
}

// MediaType represents content type specification
type MediaType struct {
	Schema Schema `json:"schema"`
}

// Response represents an HTTP response
type Response struct {
	Description string `json:"description"`
	Content     map[string]MediaType `json:"content,omitempty"`
}

// Schema represents a JSON schema
type Schema struct {
	Type        string            `json:"type,omitempty"`
	Description string            `json:"description,omitempty"`
	Properties  map[string]Schema `json:"properties,omitempty"`
	Required    []string          `json:"required,omitempty"`
	Items       *Schema           `json:"items,omitempty"`
	Ref         string            `json:"$ref,omitempty"`
}

// Components contains reusable components
type Components struct {
	Schemas map[string]Schema `json:"schemas,omitempty"`
}

// Tag represents an OpenAPI tag
type Tag struct {
	Name        string `json:"name"`
	Description string `json:"description,omitempty"`
}

// GenerateOpenAPISpec creates an OpenAPI 3.0 specification from discovered apps
func GenerateOpenAPISpec(apps []appmodule.App, metadata map[string]*appmodule.Metadata) *OpenAPISpec {
	spec := &OpenAPISpec{
		OpenAPI: "3.0.0",
		Info: Info{
			Title:       "GAIA Education Platform API",
			Description: "Complete API documentation for all GAIA educational applications",
			Version:     "1.0.0",
			Contact: Contact{
				Name: "GAIA Development Team",
			},
			License: License{
				Name: "MIT",
			},
		},
		Servers: []Server{
			{
				URL:         "http://localhost:8080",
				Description: "Local development server",
			},
			{
				URL:         "https://api.gaia.local",
				Description: "Production server",
			},
		},
		Paths:      make(map[string]PathItem),
		Components: &Components{Schemas: make(map[string]Schema)},
		Tags:       make([]Tag, 0),
	}

	// Process each app
	for _, app := range apps {
		appMeta, exists := metadata[app.GetName()]
		if !exists {
			continue
		}

		// Add app as a tag
		spec.Tags = append(spec.Tags, Tag{
			Name:        app.GetName(),
			Description: appMeta.Description,
		})
	}

	return spec
}

// sanitizeOperationID converts a description to a valid operation ID
func sanitizeOperationID(description string) string {
	// Remove special characters and convert to camelCase
	result := ""
	capitalizeNext := false

	for _, char := range description {
		if (char >= 'a' && char <= 'z') || (char >= 'A' && char <= 'Z') || (char >= '0' && char <= '9') {
			if capitalizeNext {
				result += string(char - 32) // Convert to uppercase
				capitalizeNext = false
			} else {
				result += string(char)
			}
		} else {
			capitalizeNext = true
		}
	}

	return result
}

// AppInfo contains simplified app information for discovery
type AppInfo struct {
	Name        string              `json:"name"`
	Description string              `json:"description"`
	Version     string              `json:"version"`
	BasePath    string              `json:"base_path"`
	Status      string              `json:"status"`
	RouteGroups []RouteGroupInfo    `json:"route_groups"`
}

// RouteGroupInfo contains route group information
type RouteGroupInfo struct {
	Path        string     `json:"path"`
	Description string     `json:"description"`
	Routes      []RouteInfoOutput `json:"routes"`
}

// RouteInfoOutput contains route information
type RouteInfoOutput struct {
	Method      string `json:"method"`
	Path        string `json:"path"`
	Description string `json:"description"`
	FullPath    string `json:"full_path"`
}

// GenerateAppDirectory creates a discovery document listing all apps and routes
func GenerateAppDirectory(apps []appmodule.App, metadata map[string]*appmodule.Metadata) []AppInfo {
	directory := make([]AppInfo, 0)

	for _, app := range apps {
		appMeta, exists := metadata[app.GetName()]
		if !exists {
			continue
		}

		appInfo := AppInfo{
			Name:        appMeta.Name,
			Description: appMeta.Description,
			Version:     appMeta.Version,
			BasePath:    fmt.Sprintf("/api/%s", appMeta.Name),
			Status:      appMeta.Status,
			RouteGroups: make([]RouteGroupInfo, 0),
		}

		directory = append(directory, appInfo)
	}

	return directory
}
