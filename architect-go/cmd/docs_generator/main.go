package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"architect-go/internal/openapi"
)

func main() {
	outputDir := flag.String("output", "docs/generated", "Output directory for generated documentation")
	_ = flag.String("format", "json", "Output format: json, yaml, or markdown")
	flag.Parse()

	fmt.Println("Architect Dashboard - Documentation Generator")
	fmt.Println("============================================")
	fmt.Println()

	// Ensure output directory exists
	if err := os.MkdirAll(*outputDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Error creating output directory: %v\n", err)
		os.Exit(1)
	}

	// Generate OpenAPI spec
	fmt.Println("Generating OpenAPI specification...")
	registry := openapi.NewSpecRegistry()

	specData, err := registry.Build()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error generating OpenAPI spec: %v\n", err)
		os.Exit(1)
	}

	// Write OpenAPI spec
	specPath := filepath.Join(*outputDir, "openapi.json")
	if err := os.WriteFile(specPath, specData, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing OpenAPI spec: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✓ OpenAPI spec written to %s\n", specPath)

	// Generate Swagger UI HTML
	fmt.Println("Generating Swagger UI...")
	swaggerHTML := generateSwaggerUI(specPath)
	swaggerPath := filepath.Join(*outputDir, "swagger-ui.html")
	if err := os.WriteFile(swaggerPath, []byte(swaggerHTML), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing Swagger UI: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✓ Swagger UI written to %s\n", swaggerPath)

	// Generate ReDoc HTML
	fmt.Println("Generating ReDoc...")
	redocHTML := generateReDoc(specPath)
	redocPath := filepath.Join(*outputDir, "redoc.html")
	if err := os.WriteFile(redocPath, []byte(redocHTML), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing ReDoc: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✓ ReDoc written to %s\n", redocPath)

	// Generate postman collection
	fmt.Println("Generating Postman collection...")
	postmanJSON := generatePostmanCollection()
	postmanPath := filepath.Join(*outputDir, "postman-collection.json")
	if err := os.WriteFile(postmanPath, postmanJSON, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing Postman collection: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✓ Postman collection written to %s\n", postmanPath)

	// Generate API documentation index
	fmt.Println("Generating documentation index...")
	indexHTML := generateDocumentationIndex()
	indexPath := filepath.Join(*outputDir, "index.html")
	if err := os.WriteFile(indexPath, []byte(indexHTML), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing documentation index: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("✓ Documentation index written to %s\n", indexPath)

	fmt.Println()
	fmt.Println("Documentation generation complete!")
	fmt.Printf("View documentation at: file://%s/index.html\n", *outputDir)
}

func generateSwaggerUI(specPath string) string {
	return `<!DOCTYPE html>
<html>
  <head>
    <title>Architect Dashboard - Swagger UI</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@3/swagger-ui.css">
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@3/swagger-ui.js"></script>
    <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "` + specPath + `",
        dom_id: '#swagger-ui',
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "StandaloneLayout"
      })
    }
    </script>
  </body>
</html>`
}

func generateReDoc(specPath string) string {
	return `<!DOCTYPE html>
<html>
  <head>
    <title>Architect Dashboard - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
      body {
        margin: 0;
        padding: 0;
      }
    </style>
  </head>
  <body>
    <redoc spec-url='` + specPath + `'></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
  </body>
</html>`
}

func generateDocumentationIndex() string {
	return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Architect Dashboard - API Documentation</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 60px 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .content {
            padding: 60px 40px;
        }

        .section {
            margin-bottom: 40px;
        }

        .section h2 {
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }

        .card {
            background: #f5f5f5;
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #667eea;
            transition: all 0.3s ease;
            text-decoration: none;
            color: inherit;
        }

        .card:hover {
            background: #fff;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
            transform: translateY(-2px);
        }

        .card h3 {
            color: #667eea;
            margin-bottom: 10px;
        }

        .card p {
            color: #666;
            font-size: 0.9em;
        }

        .footer {
            background: #f5f5f5;
            padding: 20px 40px;
            text-align: center;
            color: #666;
            border-top: 1px solid #ddd;
        }

        .version {
            color: #999;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Architect Dashboard API</h1>
            <p>Comprehensive Documentation & Interactive Tools</p>
        </div>

        <div class="content">
            <div class="section">
                <h2>📚 Documentation</h2>
                <div class="grid">
                    <a href="swagger-ui.html" class="card">
                        <h3>Swagger UI</h3>
                        <p>Interactive API documentation with Try It Out feature</p>
                    </a>
                    <a href="redoc.html" class="card">
                        <h3>ReDoc</h3>
                        <p>Beautiful, responsive API documentation</p>
                    </a>
                    <a href="openapi.json" class="card">
                        <h3>OpenAPI Spec</h3>
                        <p>OpenAPI 3.0 specification in JSON format</p>
                    </a>
                    <a href="postman-collection.json" class="card">
                        <h3>Postman Collection</h3>
                        <p>Import into Postman for API testing</p>
                    </a>
                </div>
            </div>

            <div class="section">
                <h2>🚀 Quick Start</h2>
                <div class="grid">
                    <div class="card">
                        <h3>Authentication</h3>
                        <p>Learn how to authenticate your API requests</p>
                    </div>
                    <div class="card">
                        <h3>Rate Limiting</h3>
                        <p>Understand API rate limits and best practices</p>
                    </div>
                    <div class="card">
                        <h3>Error Handling</h3>
                        <p>Handle errors gracefully in your integration</p>
                    </div>
                    <div class="card">
                        <h3>SDKs</h3>
                        <p>Official client libraries for Go, Python, JavaScript</p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>📋 API Endpoints</h2>
                <p style="margin-bottom: 20px; color: #666;">
                    Version 3.2 includes 280+ endpoints across the following categories:
                </p>
                <div class="grid">
                    <div class="card">
                        <h3>Authentication</h3>
                        <p>Login, logout, and session management (5 endpoints)</p>
                    </div>
                    <div class="card">
                        <h3>Events</h3>
                        <p>Event tracking and audit logging (45 endpoints)</p>
                    </div>
                    <div class="card">
                        <h3>Errors</h3>
                        <p>Error aggregation and analysis (40 endpoints)</p>
                    </div>
                    <div class="card">
                        <h3>Notifications</h3>
                        <p>User notifications and alerts (35 endpoints)</p>
                    </div>
                    <div class="card">
                        <h3>Sessions</h3>
                        <p>Session tracking and management (30 endpoints)</p>
                    </div>
                    <div class="card">
                        <h3>Integrations</h3>
                        <p>Third-party integrations (50 endpoints)</p>
                    </div>
                    <div class="card">
                        <h3>Webhooks</h3>
                        <p>Webhook management and delivery (40 endpoints)</p>
                    </div>
                    <div class="card">
                        <h3>Health</h3>
                        <p>Health checks and monitoring (15 endpoints)</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Architect Dashboard API v3.2.0</p>
            <p class="version">Generated on: 2024-02-17</p>
        </div>
    </div>
</body>
</html>`
}

func generatePostmanCollection() []byte {
	return []byte(`{
  "info": {
    "name": "Architect Dashboard API",
    "description": "Comprehensive REST API for managing projects and coordinating development workflows",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Authentication",
      "item": [
        {
          "name": "Login",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\\n  \"username\": \"architect\",\\n  \"password\": \"password123\"\\n}"
            },
            "url": {
              "raw": "{{base_url}}/auth/login",
              "host": ["{{base_url}}"],
              "path": ["auth", "login"]
            }
          }
        },
        {
          "name": "Logout",
          "request": {
            "method": "POST",
            "url": {
              "raw": "{{base_url}}/auth/logout",
              "host": ["{{base_url}}"],
              "path": ["auth", "logout"]
            }
          }
        }
      ]
    },
    {
      "name": "Events",
      "item": [
        {
          "name": "List Events",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{base_url}}/events?limit=20&offset=0",
              "host": ["{{base_url}}"],
              "path": ["events"],
              "query": [
                {"key": "limit", "value": "20"},
                {"key": "offset", "value": "0"},
                {"key": "event_type", "value": "user_action", "disabled": true}
              ]
            }
          }
        },
        {
          "name": "Create Event",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\\n  \"event_type\": \"user_action\",\\n  \"source\": \"api\",\\n  \"data\": {}\\n}"
            },
            "url": {
              "raw": "{{base_url}}/events",
              "host": ["{{base_url}}"],
              "path": ["events"]
            }
          }
        }
      ]
    },
    {
      "name": "Errors",
      "item": [
        {
          "name": "List Errors",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{base_url}}/errors?limit=20&offset=0",
              "host": ["{{base_url}}"],
              "path": ["errors"],
              "query": [
                {"key": "limit", "value": "20"},
                {"key": "offset", "value": "0"}
              ]
            }
          }
        },
        {
          "name": "Create Error",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\\n  \"error_type\": \"runtime_error\",\\n  \"message\": \"Error message\",\\n  \"severity\": \"high\",\\n  \"source\": \"module.go:123\"\\n}"
            },
            "url": {
              "raw": "{{base_url}}/errors",
              "host": ["{{base_url}}"],
              "path": ["errors"]
            }
          }
        }
      ]
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8080/api",
      "type": "string"
    }
  ]
}`)
}
