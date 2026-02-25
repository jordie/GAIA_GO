#!/usr/bin/env python3
"""
OpenAPI/Swagger Documentation Module

Provides OpenAPI 3.0 specification and Swagger UI for the Architect Dashboard API.

Features:
- Auto-generated OpenAPI 3.0 specification
- Swagger UI for interactive API exploration
- ReDoc for alternative documentation view
- Schema definitions for all data models
- Authentication documentation
- Response examples

Usage:
    from openapi import init_openapi, register_api_docs

    # Initialize with Flask app
    init_openapi(app)

    # Access documentation at:
    # - /api/docs - Swagger UI
    # - /api/docs/redoc - ReDoc
    # - /api/docs/openapi.json - Raw OpenAPI spec
"""

import json
import logging
import os
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import Blueprint, Flask, jsonify, render_template_string, request

logger = logging.getLogger(__name__)

# OpenAPI specification version
OPENAPI_VERSION = "3.0.3"

# API metadata
API_INFO = {
    "title": "Architect Dashboard API",
    "description": """
## Overview

The Architect Dashboard API provides comprehensive project management capabilities including:

- **Projects** - Create, update, and manage projects
- **Milestones** - Track project milestones and progress
- **Features & Bugs** - Manage features and bug tracking
- **Tasks** - Task queue management and worker coordination
- **tmux Sessions** - Remote terminal session management
- **Nodes** - Distributed node cluster management
- **Errors** - Centralized error aggregation

## Authentication

Most endpoints require authentication via session cookies or API keys.

### Session Authentication
1. POST to `/login` with username and password
2. Session cookie is set automatically
3. Include cookie in subsequent requests

### API Key Authentication
1. Generate API key in dashboard settings
2. Include in header: `Authorization: Bearer <api_key>`

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- General endpoints: 100 requests/minute
- Login: 10 requests/minute
- Write operations: 30 requests/minute

## Error Handling

All errors return JSON with:
```json
{
    "error": "Error message",
    "status_code": 400,
    "correlation_id": "request-tracking-id"
}
```
""",
    "version": "2.0.0",
    "contact": {
        "name": "Architect Dashboard Support",
        "url": "https://github.com/jordie/architect",
    },
    "license": {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
}

# Server configurations
SERVERS = [
    {
        "url": "/",
        "description": "Current server",
    },
]

# Security schemes
SECURITY_SCHEMES = {
    "sessionAuth": {
        "type": "apiKey",
        "in": "cookie",
        "name": "session",
        "description": "Session-based authentication via cookies",
    },
    "bearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "API Key",
        "description": "API key authentication",
    },
    "csrfToken": {
        "type": "apiKey",
        "in": "header",
        "name": "X-CSRF-Token",
        "description": "CSRF token for state-changing requests",
    },
}

# Common response schemas
COMMON_RESPONSES = {
    "Unauthorized": {
        "description": "Authentication required",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "example": {"error": "Authentication required", "status_code": 401},
            }
        },
    },
    "Forbidden": {
        "description": "Access denied",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "example": {"error": "Access denied", "status_code": 403},
            }
        },
    },
    "NotFound": {
        "description": "Resource not found",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "example": {"error": "Resource not found", "status_code": 404},
            }
        },
    },
    "ValidationError": {
        "description": "Validation error",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "example": {"error": "Invalid input", "status_code": 400},
            }
        },
    },
    "ServerError": {
        "description": "Internal server error",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "example": {"error": "Internal server error", "status_code": 500},
            }
        },
    },
}

# Data model schemas
SCHEMAS = {
    "Error": {
        "type": "object",
        "properties": {
            "error": {"type": "string", "description": "Error message"},
            "status_code": {"type": "integer", "description": "HTTP status code"},
            "correlation_id": {"type": "string", "description": "Request tracking ID"},
            "details": {"type": "object", "description": "Additional error details"},
        },
        "required": ["error"],
    },
    "Success": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "example": True},
            "message": {"type": "string"},
        },
    },
    "Project": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Project ID"},
            "name": {"type": "string", "description": "Project name"},
            "description": {"type": "string", "description": "Project description"},
            "status": {
                "type": "string",
                "enum": ["active", "archived", "completed", "on_hold"],
                "description": "Project status",
            },
            "source_path": {"type": "string", "description": "Source code path"},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
        },
        "required": ["name"],
    },
    "ProjectCreate": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Project name",
                "minLength": 1,
                "maxLength": 255,
            },
            "description": {"type": "string", "description": "Project description"},
            "source_path": {"type": "string", "description": "Source code path"},
        },
        "required": ["name"],
    },
    "Milestone": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "project_id": {"type": "integer"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "target_date": {"type": "string", "format": "date"},
            "status": {
                "type": "string",
                "enum": ["planned", "in_progress", "completed", "delayed"],
            },
            "progress": {"type": "integer", "minimum": 0, "maximum": 100},
        },
    },
    "Feature": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "project_id": {"type": "integer"},
            "milestone_id": {"type": "integer"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["planned", "in_progress", "review", "testing", "completed", "blocked"],
            },
            "priority": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
            },
            "assignee": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "Bug": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "project_id": {"type": "integer"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["open", "in_progress", "resolved", "closed", "wontfix"],
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
            },
            "assignee": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "Task": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "type": {
                "type": "string",
                "enum": ["shell", "python", "git", "deploy", "test", "build", "tmux"],
            },
            "status": {
                "type": "string",
                "enum": ["pending", "running", "completed", "failed", "cancelled"],
            },
            "priority": {"type": "integer", "minimum": 0, "maximum": 100},
            "data": {"type": "object", "description": "Task-specific data"},
            "result": {"type": "object", "description": "Task result"},
            "worker_id": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
            "started_at": {"type": "string", "format": "date-time"},
            "completed_at": {"type": "string", "format": "date-time"},
        },
    },
    "TmuxSession": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "node_id": {"type": "string"},
            "purpose": {"type": "string"},
            "is_protected": {"type": "boolean"},
            "last_activity": {"type": "string", "format": "date-time"},
        },
    },
    "Node": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "hostname": {"type": "string"},
            "ip_address": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["online", "offline", "degraded"],
            },
            "cpu_percent": {"type": "number"},
            "memory_percent": {"type": "number"},
            "disk_percent": {"type": "number"},
            "last_heartbeat": {"type": "string", "format": "date-time"},
        },
    },
    "ErrorLog": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "error_type": {"type": "string"},
            "message": {"type": "string"},
            "source": {"type": "string"},
            "stack_trace": {"type": "string"},
            "occurrence_count": {"type": "integer"},
            "first_seen": {"type": "string", "format": "date-time"},
            "last_seen": {"type": "string", "format": "date-time"},
            "resolved": {"type": "boolean"},
        },
    },
    "Worker": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "node_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["idle", "busy", "offline"],
            },
            "current_task_id": {"type": "integer"},
            "tasks_completed": {"type": "integer"},
            "last_heartbeat": {"type": "string", "format": "date-time"},
        },
    },
    "PaginationParams": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "per_page": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            "sort_by": {"type": "string"},
            "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
        },
    },
    "PaginatedResponse": {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {}},
            "total": {"type": "integer"},
            "page": {"type": "integer"},
            "per_page": {"type": "integer"},
            "pages": {"type": "integer"},
        },
    },
}

# API endpoint documentation
API_PATHS = {
    # Authentication
    "/login": {
        "post": {
            "tags": ["Authentication"],
            "summary": "Login to the dashboard",
            "description": "Authenticate with username and password to receive a session cookie.",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "username": {"type": "string"},
                                "password": {"type": "string"},
                            },
                            "required": ["username", "password"],
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Login successful",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "redirect": {"type": "string"},
                                },
                            },
                        },
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        },
    },
    "/logout": {
        "get": {
            "tags": ["Authentication"],
            "summary": "Logout from the dashboard",
            "description": "Clear session and logout.",
            "responses": {
                "302": {"description": "Redirect to login page"},
            },
        },
    },
    # Session
    "/api/session/status": {
        "get": {
            "tags": ["Session"],
            "summary": "Get session status",
            "description": "Get current session information including timeout.",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Session status",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "authenticated": {"type": "boolean"},
                                    "username": {"type": "string"},
                                    "role": {"type": "string"},
                                    "remaining_seconds": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        },
    },
    "/api/session/keepalive": {
        "post": {
            "tags": ["Session"],
            "summary": "Keep session alive",
            "description": "Refresh session timeout.",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {"description": "Session refreshed"},
            },
        },
    },
    # CSRF
    "/api/csrf/token": {
        "get": {
            "tags": ["Security"],
            "summary": "Get CSRF token",
            "description": "Get a fresh CSRF token for state-changing requests.",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "CSRF token",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "token": {"type": "string"},
                                    "header_name": {"type": "string"},
                                    "lifetime_seconds": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    # Projects
    "/api/projects": {
        "get": {
            "tags": ["Projects"],
            "summary": "List all projects",
            "description": "Get a list of all projects with optional filtering.",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "parameters": [
                {"name": "status", "in": "query", "schema": {"type": "string"}},
                {"name": "search", "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {
                "200": {
                    "description": "List of projects",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Project"},
                            },
                        },
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        },
        "post": {
            "tags": ["Projects"],
            "summary": "Create a new project",
            "description": "Create a new project with the specified details.",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ProjectCreate"},
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Project created",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Project"},
                        },
                    },
                },
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        },
    },
    "/api/projects/{project_id}": {
        "get": {
            "tags": ["Projects"],
            "summary": "Get a project by ID",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "parameters": [
                {
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Project details",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Project"},
                        },
                    },
                },
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        },
        "put": {
            "tags": ["Projects"],
            "summary": "Update a project",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "parameters": [
                {
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                },
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ProjectCreate"},
                    },
                },
            },
            "responses": {
                "200": {"description": "Project updated"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        },
        "delete": {
            "tags": ["Projects"],
            "summary": "Delete a project",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "parameters": [
                {
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                },
            ],
            "responses": {
                "200": {"description": "Project deleted"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        },
    },
    # Milestones
    "/api/milestones": {
        "get": {
            "tags": ["Milestones"],
            "summary": "List milestones",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "parameters": [
                {"name": "project_id", "in": "query", "schema": {"type": "integer"}},
            ],
            "responses": {
                "200": {
                    "description": "List of milestones",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Milestone"},
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "tags": ["Milestones"],
            "summary": "Create a milestone",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Milestone"},
                    },
                },
            },
            "responses": {
                "201": {"description": "Milestone created"},
            },
        },
    },
    # Features
    "/api/features": {
        "get": {
            "tags": ["Features"],
            "summary": "List features",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "parameters": [
                {"name": "project_id", "in": "query", "schema": {"type": "integer"}},
                {"name": "milestone_id", "in": "query", "schema": {"type": "integer"}},
                {"name": "status", "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {
                "200": {
                    "description": "List of features",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Feature"},
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "tags": ["Features"],
            "summary": "Create a feature",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Feature"},
                    },
                },
            },
            "responses": {
                "201": {"description": "Feature created"},
            },
        },
    },
    # Bugs
    "/api/bugs": {
        "get": {
            "tags": ["Bugs"],
            "summary": "List bugs",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "parameters": [
                {"name": "project_id", "in": "query", "schema": {"type": "integer"}},
                {"name": "status", "in": "query", "schema": {"type": "string"}},
                {"name": "severity", "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {
                "200": {
                    "description": "List of bugs",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Bug"},
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "tags": ["Bugs"],
            "summary": "Create a bug report",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Bug"},
                    },
                },
            },
            "responses": {
                "201": {"description": "Bug created"},
            },
        },
    },
    # Tasks
    "/api/tasks": {
        "get": {
            "tags": ["Tasks"],
            "summary": "List tasks in queue",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "parameters": [
                {"name": "status", "in": "query", "schema": {"type": "string"}},
                {"name": "type", "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {
                "200": {
                    "description": "List of tasks",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Task"},
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "tags": ["Tasks"],
            "summary": "Create a new task",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Task"},
                    },
                },
            },
            "responses": {
                "201": {"description": "Task created"},
            },
        },
    },
    # tmux Sessions
    "/api/tmux/sessions": {
        "get": {
            "tags": ["tmux"],
            "summary": "List tmux sessions",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "List of tmux sessions",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/TmuxSession"},
                            },
                        },
                    },
                },
            },
        },
    },
    "/api/tmux/send": {
        "post": {
            "tags": ["tmux"],
            "summary": "Send command to tmux session",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}, {"csrfToken": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "session": {"type": "string"},
                                "command": {"type": "string"},
                            },
                            "required": ["session", "command"],
                        },
                    },
                },
            },
            "responses": {
                "200": {"description": "Command sent"},
            },
        },
    },
    # Nodes
    "/api/nodes": {
        "get": {
            "tags": ["Nodes"],
            "summary": "List cluster nodes",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "List of nodes",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Node"},
                            },
                        },
                    },
                },
            },
        },
    },
    # Errors
    "/api/errors": {
        "get": {
            "tags": ["Errors"],
            "summary": "List aggregated errors",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "List of errors",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/ErrorLog"},
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "tags": ["Errors"],
            "summary": "Log an error",
            "description": "Log an error from any node. Does not require authentication.",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "node_id": {"type": "string"},
                                "error_type": {"type": "string"},
                                "message": {"type": "string"},
                                "source": {"type": "string"},
                                "stack_trace": {"type": "string"},
                            },
                            "required": ["message"],
                        },
                    },
                },
            },
            "responses": {
                "201": {"description": "Error logged"},
            },
        },
    },
    "/api/errors/summary": {
        "get": {
            "tags": ["Errors"],
            "summary": "Get error summary statistics",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Error summary",
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"},
                        },
                    },
                },
            },
        },
    },
    # Workers
    "/api/workers": {
        "get": {
            "tags": ["Workers"],
            "summary": "List workers",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "List of workers",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Worker"},
                            },
                        },
                    },
                },
            },
        },
    },
    # Stats
    "/api/stats": {
        "get": {
            "tags": ["Statistics"],
            "summary": "Get dashboard statistics",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Dashboard statistics",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "projects_count": {"type": "integer"},
                                    "features_count": {"type": "integer"},
                                    "bugs_count": {"type": "integer"},
                                    "tasks_pending": {"type": "integer"},
                                    "nodes_online": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    # Health
    "/health": {
        "get": {
            "tags": ["Health"],
            "summary": "Health check",
            "description": "Check if the API is healthy. Does not require authentication.",
            "responses": {
                "200": {
                    "description": "API is healthy",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string", "example": "healthy"},
                                    "timestamp": {"type": "string", "format": "date-time"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    # Tracing
    "/api/tracing/config": {
        "get": {
            "tags": ["Observability"],
            "summary": "Get tracing configuration",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {"description": "Tracing configuration"},
            },
        },
    },
    # Security Headers
    "/api/security/headers": {
        "get": {
            "tags": ["Security"],
            "summary": "Get security headers configuration",
            "security": [{"sessionAuth": []}, {"bearerAuth": []}],
            "responses": {
                "200": {"description": "Security headers config"},
            },
        },
    },
}

# Tag definitions
TAGS = [
    {"name": "Authentication", "description": "Login and logout operations"},
    {"name": "Session", "description": "Session management"},
    {"name": "Security", "description": "Security features (CSRF, headers)"},
    {"name": "Projects", "description": "Project management"},
    {"name": "Milestones", "description": "Milestone tracking"},
    {"name": "Features", "description": "Feature management"},
    {"name": "Bugs", "description": "Bug tracking"},
    {"name": "Tasks", "description": "Task queue management"},
    {"name": "tmux", "description": "Terminal session management"},
    {"name": "Nodes", "description": "Cluster node management"},
    {"name": "Errors", "description": "Error aggregation"},
    {"name": "Workers", "description": "Worker management"},
    {"name": "Statistics", "description": "Dashboard statistics"},
    {"name": "Health", "description": "Health checks"},
    {"name": "Observability", "description": "Tracing and monitoring"},
]


def generate_openapi_spec() -> Dict[str, Any]:
    """Generate the complete OpenAPI specification."""
    return {
        "openapi": OPENAPI_VERSION,
        "info": API_INFO,
        "servers": SERVERS,
        "tags": TAGS,
        "paths": API_PATHS,
        "components": {
            "schemas": SCHEMAS,
            "responses": COMMON_RESPONSES,
            "securitySchemes": SECURITY_SCHEMES,
        },
    }


# Swagger UI HTML template
SWAGGER_UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - API Documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
        .swagger-ui .topbar { display: none; }
        .swagger-ui .info .title { color: #3b4151; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "{{ spec_url }}",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                persistAuthorization: true,
            });
        };
    </script>
</body>
</html>
"""

# ReDoc HTML template
REDOC_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - API Documentation</title>
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body { margin: 0; padding: 0; }
    </style>
</head>
<body>
    <redoc spec-url='{{ spec_url }}'></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


# Blueprint for OpenAPI routes
openapi_bp = Blueprint("openapi", __name__)


@openapi_bp.route("/api/docs")
def swagger_ui():
    """Serve Swagger UI."""
    return render_template_string(
        SWAGGER_UI_TEMPLATE, title=API_INFO["title"], spec_url="/api/docs/openapi.json"
    )


@openapi_bp.route("/api/docs/redoc")
def redoc():
    """Serve ReDoc documentation."""
    return render_template_string(
        REDOC_TEMPLATE, title=API_INFO["title"], spec_url="/api/docs/openapi.json"
    )


@openapi_bp.route("/api/docs/openapi.json")
def openapi_spec():
    """Serve OpenAPI specification as JSON."""
    return jsonify(generate_openapi_spec())


@openapi_bp.route("/api/docs/openapi.yaml")
def openapi_spec_yaml():
    """Serve OpenAPI specification as YAML."""
    try:
        import yaml

        spec = generate_openapi_spec()
        yaml_content = yaml.dump(spec, default_flow_style=False, allow_unicode=True)
        return yaml_content, 200, {"Content-Type": "text/yaml"}
    except ImportError:
        return jsonify({"error": "PyYAML not installed"}), 500


def init_openapi(app: Flask) -> None:
    """
    Initialize OpenAPI documentation for a Flask app.

    Args:
        app: Flask application instance
    """
    app.register_blueprint(openapi_bp)
    logger.info("OpenAPI documentation initialized at /api/docs")


def document_endpoint(
    path: str,
    method: str,
    summary: str,
    description: str = None,
    tags: List[str] = None,
    request_schema: Dict = None,
    response_schema: Dict = None,
    parameters: List[Dict] = None,
    auth_required: bool = True,
) -> None:
    """
    Add documentation for an endpoint.

    Args:
        path: API path (e.g., "/api/users")
        method: HTTP method (get, post, put, delete)
        summary: Short description
        description: Detailed description
        tags: List of tags
        request_schema: Request body schema
        response_schema: Response schema
        parameters: Query/path parameters
        auth_required: Whether authentication is required
    """
    method = method.lower()

    if path not in API_PATHS:
        API_PATHS[path] = {}

    endpoint_doc = {
        "summary": summary,
        "tags": tags or ["Other"],
    }

    if description:
        endpoint_doc["description"] = description

    if auth_required:
        endpoint_doc["security"] = [{"sessionAuth": []}, {"bearerAuth": []}]

    if parameters:
        endpoint_doc["parameters"] = parameters

    if request_schema:
        endpoint_doc["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": request_schema,
                },
            },
        }

    if response_schema:
        endpoint_doc["responses"] = {
            "200": {
                "description": "Success",
                "content": {
                    "application/json": {
                        "schema": response_schema,
                    },
                },
            },
        }
    else:
        endpoint_doc["responses"] = {
            "200": {"description": "Success"},
        }

    if auth_required:
        endpoint_doc["responses"]["401"] = {"$ref": "#/components/responses/Unauthorized"}

    API_PATHS[path][method] = endpoint_doc
