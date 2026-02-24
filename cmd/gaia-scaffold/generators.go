package main

import (
	"fmt"
	"strings"
	"time"
)

// GenerateModels generates the models.go file
func GenerateModels(spec *Specification) (string, error) {
	var sb strings.Builder

	sb.WriteString("package generated\n\n")
	sb.WriteString("import (\n")
	sb.WriteString("\t\"time\"\n")
	sb.WriteString(")\n\n")

	// Generate each entity type
	for _, entity := range spec.Entities {
		sb.WriteString(fmt.Sprintf("// %s represents a %s\n", entity.Name, strings.ToLower(entity.Name)))
		sb.WriteString(fmt.Sprintf("type %s struct {\n", entity.Name))

		for _, field := range entity.Fields {
			tag := fmt.Sprintf("`json:\"%s\"`", field.JSONTag)
			sb.WriteString(fmt.Sprintf("\t%s %s %s\n", field.Name, field.Type, tag))
		}

		sb.WriteString("}\n\n")
	}

	// Add response types
	sb.WriteString("// ListResponse is a generic list response\n")
	sb.WriteString("type ListResponse struct {\n")
	sb.WriteString("\tItems interface{} `json:\"items\"`\n")
	sb.WriteString("\tTotal int `json:\"total\"`\n")
	sb.WriteString("}\n\n")

	sb.WriteString("// ErrorResponse represents an error response\n")
	sb.WriteString("type ErrorResponse struct {\n")
	sb.WriteString("\tCode    string `json:\"code\"`\n")
	sb.WriteString("\tMessage string `json:\"message\"`\n")
	sb.WriteString("}\n")

	return sb.String(), nil
}

// GenerateDTOs generates the dto.go file
func GenerateDTOs(spec *Specification) (string, error) {
	var sb strings.Builder

	sb.WriteString("package generated\n\n")
	sb.WriteString("// Request and Response DTOs for all endpoints\n\n")

	// Generate request/response pairs for each operation
	for _, op := range spec.Operations {
		entity := op.Entity

		switch op.Type {
		case "create":
			sb.WriteString(fmt.Sprintf("// Create%sRequest represents a request to create %s\n", entity, entity))
			sb.WriteString(fmt.Sprintf("type Create%sRequest struct {\n", entity))
			sb.WriteString("\tUserID int64 `json:\"user_id\" binding:\"required\"`\n")
			sb.WriteString("\tData string `json:\"data\" binding:\"required\"`\n")
			sb.WriteString("}\n\n")

			sb.WriteString(fmt.Sprintf("// %sResponse represents %s in responses\n", entity, entity))
			sb.WriteString(fmt.Sprintf("type %sResponse struct {\n", entity))
			sb.WriteString("\tID int64 `json:\"id\"`\n")
			sb.WriteString("\tUserID int64 `json:\"user_id\"`\n")
			sb.WriteString("\tData string `json:\"data\"`\n")
			sb.WriteString("\tCreatedAt string `json:\"created_at\"`\n")
			sb.WriteString("}\n\n")

		case "list":
			sb.WriteString(fmt.Sprintf("// List%sRequest represents a request to list %s\n", entity, entity))
			sb.WriteString(fmt.Sprintf("type List%sRequest struct {\n", entity))
			sb.WriteString("\tLimit int `form:\"limit\" binding:\"max=100\"`\n")
			sb.WriteString("\tOffset int `form:\"offset\"`\n")
			sb.WriteString("}\n\n")

		case "update":
			sb.WriteString(fmt.Sprintf("// Update%sRequest represents a request to update %s\n", entity, entity))
			sb.WriteString(fmt.Sprintf("type Update%sRequest struct {\n", entity))
			sb.WriteString("\tID int64 `json:\"id\" binding:\"required\"`\n")
			sb.WriteString("\tData string `json:\"data\" binding:\"required\"`\n")
			sb.WriteString("}\n\n")

		case "delete":
			sb.WriteString(fmt.Sprintf("// Delete%sRequest represents a request to delete %s\n", entity, entity))
			sb.WriteString(fmt.Sprintf("type Delete%sRequest struct {\n", entity))
			sb.WriteString("\tID int64 `json:\"id\" binding:\"required\"`\n")
			sb.WriteString("}\n\n")
		}
	}

	return sb.String(), nil
}

// GenerateApp generates the app.go file
func GenerateApp(spec *Specification) (string, error) {
	var sb strings.Builder

	appName := spec.Name + "App"

	sb.WriteString("package generated\n\n")
	sb.WriteString("import (\n")
	sb.WriteString("\t\"database/sql\"\n")
	sb.WriteString("\t\"fmt\"\n")
	sb.WriteString(")\n\n")

	sb.WriteString(fmt.Sprintf("// %s is the main application struct\n", appName))
	sb.WriteString(fmt.Sprintf("type %s struct {\n", appName))
	sb.WriteString("\tdb *sql.DB\n")
	sb.WriteString("}\n\n")

	sb.WriteString(fmt.Sprintf("// New%s creates a new %s\n", appName, appName))
	sb.WriteString(fmt.Sprintf("func New%s(db *sql.DB) *%s {\n", appName, appName))
	sb.WriteString(fmt.Sprintf("\treturn &%s{db: db}\n", appName))
	sb.WriteString("}\n\n")

	// Generate methods for each operation
	for _, op := range spec.Operations {
		entity := op.Entity
		methodName := fmt.Sprintf("%s%s", strings.ToUpper(op.Type[:1])+strings.ToLower(op.Type[1:]), entity)

		sb.WriteString(fmt.Sprintf("// %s handles %s operation for %s\n", methodName, op.Type, entity))
		sb.WriteString(fmt.Sprintf("func (app *%s) %s(id int64) (interface{}, error) {\n", appName, methodName))
		sb.WriteString(fmt.Sprintf("\t// TODO: Implement %s logic\n", op.Type))
		sb.WriteString("\treturn nil, fmt.Errorf(\"not implemented\")\n")
		sb.WriteString("}\n\n")
	}

	return sb.String(), nil
}

// GenerateHandlers generates the handlers.go file
func GenerateHandlers(spec *Specification) (string, error) {
	var sb strings.Builder

	sb.WriteString("package generated\n\n")
	sb.WriteString("import (\n")
	sb.WriteString("\t\"net/http\"\n")
	sb.WriteString("\t\"github.com/gin-gonic/gin\"\n")
	sb.WriteString(")\n\n")

	// Generate handler functions
	for _, op := range spec.Operations {
		entity := op.Entity
		handlerName := fmt.Sprintf("handle%s%s", strings.ToUpper(op.Type[:1])+strings.ToLower(op.Type[1:]), entity)

		sb.WriteString(fmt.Sprintf("// %s handles %s requests for %s\n", handlerName, op.Type, entity))
		sb.WriteString(fmt.Sprintf("func %s(c *gin.Context) {\n", handlerName))
		sb.WriteString(fmt.Sprintf("\t// TODO: Implement %s handler\n", op.Type))
		sb.WriteString("\tc.JSON(http.StatusOK, gin.H{\"status\": \"not implemented\"})\n")
		sb.WriteString("}\n\n")
	}

	// Register function
	sb.WriteString("// RegisterHandlers registers all handlers\n")
	sb.WriteString("func RegisterHandlers(router *gin.RouterGroup) {\n")

	for _, op := range spec.Operations {
		entity := op.Entity
		handlerName := fmt.Sprintf("handle%s%s", strings.ToUpper(op.Type[:1])+strings.ToLower(op.Type[1:]), entity)
		path := fmt.Sprintf("/%s", strings.ToLower(op.Entity))

		switch op.Type {
		case "create":
			sb.WriteString(fmt.Sprintf("\trouter.POST(\"%s\", %s)\n", path, handlerName))
		case "list":
			sb.WriteString(fmt.Sprintf("\trouter.GET(\"%s\", %s)\n", path, handlerName))
		case "read":
			sb.WriteString(fmt.Sprintf("\trouter.GET(\"%s/:id\", %s)\n", path, handlerName))
		case "update":
			sb.WriteString(fmt.Sprintf("\trouter.PUT(\"%s/:id\", %s)\n", path, handlerName))
		case "delete":
			sb.WriteString(fmt.Sprintf("\trouter.DELETE(\"%s/:id\", %s)\n", path, handlerName))
		}
	}

	sb.WriteString("}\n")

	return sb.String(), nil
}

// GenerateMigrations generates the migrations.sql file
func GenerateMigrations(spec *Specification) (string, error) {
	var sb strings.Builder

	sb.WriteString("-- Auto-generated migrations for " + spec.Name + "\n")
	sb.WriteString("-- Generated: " + time.Now().Format(time.RFC3339) + "\n\n")

	// Create table for each entity
	for _, entity := range spec.Entities {
		tableName := strings.ToLower(entity.Name) + "s"

		sb.WriteString(fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (\n", tableName))
		sb.WriteString("\tid INTEGER PRIMARY KEY AUTOINCREMENT,\n")

		// Add fields
		for _, field := range entity.Fields {
			if field.Name == "ID" || field.Name == "CreatedAt" {
				continue
			}

			sqlType := "TEXT"
			if field.Type == "int64" || field.Type == "int" {
				sqlType = "INTEGER"
			} else if field.Type == "float64" {
				sqlType = "REAL"
			} else if field.Type == "time.Time" {
				sqlType = "TIMESTAMP"
			}

			sb.WriteString(fmt.Sprintf("\t%s %s,\n", strings.ToLower(field.Name), sqlType))
		}

		sb.WriteString("\tcreated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n")
		sb.WriteString(");\n\n")

		// Create indexes
		sb.WriteString(fmt.Sprintf("CREATE INDEX IF NOT EXISTS idx_%s_user_id ON %s(user_id);\n", tableName, tableName))
		sb.WriteString(fmt.Sprintf("CREATE INDEX IF NOT EXISTS idx_%s_created_at ON %s(created_at);\n\n", tableName, tableName))
	}

	return sb.String(), nil
}

// GenerateTests generates the handlers_test.go file
func GenerateTests(spec *Specification) (string, error) {
	var sb strings.Builder

	sb.WriteString("package generated\n\n")
	sb.WriteString("import (\n")
	sb.WriteString("\t\"testing\"\n")
	sb.WriteString(")\n\n")

	testCount := 1
	for _, op := range spec.Operations {
		entity := op.Entity

		// Generate 4 tests per operation
		tests := []string{
			fmt.Sprintf("Test%sSuccess", strings.ToUpper(op.Type[:1])+op.Type[1:]),
			fmt.Sprintf("Test%sMissingFields", strings.ToUpper(op.Type[:1])+op.Type[1:]),
			fmt.Sprintf("Test%sInvalidInput", strings.ToUpper(op.Type[:1])+op.Type[1:]),
			fmt.Sprintf("Test%sNotFound", strings.ToUpper(op.Type[:1])+op.Type[1:]),
		}

		for _, testName := range tests {
			sb.WriteString(fmt.Sprintf("func %s(t *testing.T) {\n", testName+entity))
			sb.WriteString("\t// TODO: Implement test\n")
			sb.WriteString("\tt.Skip(\"Not implemented\")\n")
			sb.WriteString("}\n\n")
			testCount++
		}
	}

	return sb.String(), nil
}

// GenerateGoMod generates the go.mod file
func GenerateGoMod(spec *Specification) string {
	return `module github.com/jgirmay/GAIA_GO/generated

go 1.21

require (
	github.com/gin-gonic/gin v1.9.1
	github.com/google/uuid v1.3.0
)
`
}
