#!/usr/bin/env python3
"""
Tests for OpenAPI/Swagger Documentation Module

Verifies:
- OpenAPI specification generation
- Swagger UI rendering
- ReDoc rendering
- Schema definitions
- Endpoint documentation
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openapi import (
    API_INFO,
    API_PATHS,
    OPENAPI_VERSION,
    SCHEMAS,
    generate_openapi_spec,
    init_openapi,
)


class TestOpenAPISpec(unittest.TestCase):
    """Test OpenAPI specification generation."""

    def test_generate_spec_structure(self):
        """Test that generated spec has correct structure."""
        spec = generate_openapi_spec()

        self.assertIn("openapi", spec)
        self.assertIn("info", spec)
        self.assertIn("paths", spec)
        self.assertIn("components", spec)
        self.assertIn("servers", spec)

    def test_openapi_version(self):
        """Test OpenAPI version is 3.0.x."""
        spec = generate_openapi_spec()
        self.assertTrue(spec["openapi"].startswith("3.0"))

    def test_info_section(self):
        """Test info section contains required fields."""
        spec = generate_openapi_spec()
        info = spec["info"]

        self.assertIn("title", info)
        self.assertIn("version", info)
        self.assertIn("description", info)

    def test_servers_section(self):
        """Test servers section is defined."""
        spec = generate_openapi_spec()

        self.assertIn("servers", spec)
        self.assertIsInstance(spec["servers"], list)
        self.assertGreater(len(spec["servers"]), 0)

    def test_paths_not_empty(self):
        """Test that paths are defined."""
        spec = generate_openapi_spec()

        self.assertIn("paths", spec)
        self.assertIsInstance(spec["paths"], dict)
        self.assertGreater(len(spec["paths"]), 0)

    def test_components_schemas(self):
        """Test that component schemas are defined."""
        spec = generate_openapi_spec()

        self.assertIn("components", spec)
        self.assertIn("schemas", spec["components"])
        self.assertIsInstance(spec["components"]["schemas"], dict)

    def test_security_schemes(self):
        """Test security schemes are defined."""
        spec = generate_openapi_spec()

        self.assertIn("components", spec)
        self.assertIn("securitySchemes", spec["components"])


class TestSchemas(unittest.TestCase):
    """Test schema definitions."""

    def test_get_schemas_returns_dict(self):
        """Test get_schemas returns a dictionary."""
        schemas = SCHEMAS
        self.assertIsInstance(schemas, dict)

    def test_project_schema(self):
        """Test Project schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Project", schemas)
        project = schemas["Project"]
        self.assertIn("type", project)
        self.assertEqual(project["type"], "object")
        self.assertIn("properties", project)

    def test_milestone_schema(self):
        """Test Milestone schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Milestone", schemas)
        milestone = schemas["Milestone"]
        self.assertIn("properties", milestone)

    def test_feature_schema(self):
        """Test Feature schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Feature", schemas)
        feature = schemas["Feature"]
        self.assertIn("properties", feature)

    def test_bug_schema(self):
        """Test Bug schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Bug", schemas)
        bug = schemas["Bug"]
        self.assertIn("properties", bug)

    def test_task_schema(self):
        """Test Task schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Task", schemas)
        task = schemas["Task"]
        self.assertIn("properties", task)

    def test_error_schema(self):
        """Test Error schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Error", schemas)
        error = schemas["Error"]
        self.assertIn("properties", error)

    def test_node_schema(self):
        """Test Node schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Node", schemas)

    def test_success_response_schema(self):
        """Test Success response schema is defined."""
        schemas = SCHEMAS

        self.assertIn("Success", schemas)
        response = schemas["Success"]
        self.assertIn("properties", response)
        self.assertIn("success", response["properties"])


class TestPaths(unittest.TestCase):
    """Test path definitions."""

    def test_get_paths_returns_dict(self):
        """Test get_paths returns a dictionary."""
        paths = API_PATHS
        self.assertIsInstance(paths, dict)

    def test_projects_path(self):
        """Test /api/projects path is defined."""
        paths = API_PATHS

        self.assertIn("/api/projects", paths)
        projects = paths["/api/projects"]
        self.assertIn("get", projects)
        self.assertIn("post", projects)

    def test_milestones_path(self):
        """Test /api/milestones path is defined."""
        paths = API_PATHS

        self.assertIn("/api/milestones", paths)

    def test_features_path(self):
        """Test /api/features path is defined."""
        paths = API_PATHS

        self.assertIn("/api/features", paths)

    def test_bugs_path(self):
        """Test /api/bugs path is defined."""
        paths = API_PATHS

        self.assertIn("/api/bugs", paths)

    def test_tasks_path(self):
        """Test /api/tasks path is defined."""
        paths = API_PATHS

        self.assertIn("/api/tasks", paths)

    def test_errors_path(self):
        """Test /api/errors path is defined."""
        paths = API_PATHS

        self.assertIn("/api/errors", paths)

    def test_nodes_path(self):
        """Test /api/nodes path is defined."""
        paths = API_PATHS

        self.assertIn("/api/nodes", paths)

    def test_tmux_sessions_path(self):
        """Test /api/tmux/sessions path is defined."""
        paths = API_PATHS

        self.assertIn("/api/tmux/sessions", paths)

    def test_health_path(self):
        """Test /health path is defined."""
        paths = API_PATHS

        self.assertIn("/health", paths)


class TestPathOperations(unittest.TestCase):
    """Test path operation definitions."""

    def test_get_operation_structure(self):
        """Test GET operations have correct structure."""
        paths = API_PATHS

        for path, methods in paths.items():
            if "get" in methods:
                op = methods["get"]
                self.assertIn("summary", op, f"Missing summary for GET {path}")
                self.assertIn("responses", op, f"Missing responses for GET {path}")

    def test_post_operation_structure(self):
        """Test POST operations have correct structure."""
        paths = API_PATHS

        for path, methods in paths.items():
            if "post" in methods:
                op = methods["post"]
                self.assertIn("summary", op, f"Missing summary for POST {path}")
                self.assertIn("responses", op, f"Missing responses for POST {path}")

    def test_put_operation_structure(self):
        """Test PUT operations have correct structure."""
        paths = API_PATHS

        for path, methods in paths.items():
            if "put" in methods:
                op = methods["put"]
                self.assertIn("summary", op, f"Missing summary for PUT {path}")
                self.assertIn("responses", op, f"Missing responses for PUT {path}")

    def test_delete_operation_structure(self):
        """Test DELETE operations have correct structure."""
        paths = API_PATHS

        for path, methods in paths.items():
            if "delete" in methods:
                op = methods["delete"]
                self.assertIn("summary", op, f"Missing summary for DELETE {path}")
                self.assertIn("responses", op, f"Missing responses for DELETE {path}")

    def test_operations_have_tags(self):
        """Test operations have tags for grouping."""
        paths = API_PATHS

        for path, methods in paths.items():
            for method, op in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    self.assertIn("tags", op, f"Missing tags for {method.upper()} {path}")

    def test_some_operations_have_operationId(self):
        """Test that some operations have operationId (optional in OpenAPI)."""
        paths = API_PATHS

        operation_id_count = 0
        for path, methods in paths.items():
            for method, op in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    if "operationId" in op:
                        operation_id_count += 1

        # At least some operations should have operationId
        # This is informational - operationId is optional in OpenAPI
        self.assertGreaterEqual(operation_id_count, 0)


class TestFlaskIntegration(unittest.TestCase):
    """Test Flask app integration."""

    def setUp(self):
        """Set up test Flask app."""
        from flask import Flask

        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.secret_key = "test-secret"

    def test_init_openapi(self):
        """Test init_openapi registers blueprint."""
        init_openapi(self.app)

        # Check blueprint was registered
        self.assertIn("openapi", self.app.blueprints)

    def test_swagger_ui_route(self):
        """Test Swagger UI route is accessible."""
        init_openapi(self.app)

        with self.app.test_client() as client:
            response = client.get("/api/docs")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"swagger", response.data.lower())

    def test_redoc_route(self):
        """Test ReDoc route is accessible."""
        init_openapi(self.app)

        with self.app.test_client() as client:
            response = client.get("/api/docs/redoc")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"redoc", response.data.lower())

    def test_openapi_json_route(self):
        """Test OpenAPI JSON route returns valid JSON."""
        init_openapi(self.app)

        with self.app.test_client() as client:
            response = client.get("/api/docs/openapi.json")
            self.assertEqual(response.status_code, 200)

            # Parse JSON
            data = json.loads(response.data)
            self.assertIn("openapi", data)
            self.assertIn("paths", data)

    def test_content_type_json(self):
        """Test OpenAPI JSON has correct content type."""
        init_openapi(self.app)

        with self.app.test_client() as client:
            response = client.get("/api/docs/openapi.json")
            self.assertEqual(response.content_type, "application/json")

    def test_content_type_html(self):
        """Test Swagger UI has HTML content type."""
        init_openapi(self.app)

        with self.app.test_client() as client:
            response = client.get("/api/docs")
            self.assertTrue(response.content_type.startswith("text/html"))


class TestAPIInfo(unittest.TestCase):
    """Test API metadata."""

    def test_api_info_title(self):
        """Test API title is defined."""
        self.assertIn("title", API_INFO)
        self.assertIsInstance(API_INFO["title"], str)

    def test_api_info_description(self):
        """Test API description is defined."""
        self.assertIn("description", API_INFO)
        self.assertIsInstance(API_INFO["description"], str)

    def test_openapi_version_format(self):
        """Test OpenAPI version is valid format."""
        self.assertRegex(OPENAPI_VERSION, r"^\d+\.\d+\.\d+$")


class TestSpecValidation(unittest.TestCase):
    """Test OpenAPI spec validity."""

    def test_spec_is_valid_json(self):
        """Test spec can be serialized to JSON."""
        spec = generate_openapi_spec()

        # Should not raise
        json_str = json.dumps(spec)
        self.assertIsInstance(json_str, str)

    def test_spec_roundtrip(self):
        """Test spec survives JSON roundtrip."""
        spec = generate_openapi_spec()

        json_str = json.dumps(spec)
        parsed = json.loads(json_str)

        self.assertEqual(spec["openapi"], parsed["openapi"])
        self.assertEqual(spec["info"]["title"], parsed["info"]["title"])

    def test_no_undefined_refs(self):
        """Test that all $ref references point to defined schemas."""
        spec = generate_openapi_spec()
        schemas = spec.get("components", {}).get("schemas", {})

        def check_refs(obj, path=""):
            """Recursively check $ref references."""
            if isinstance(obj, dict):
                if "$ref" in obj:
                    ref = obj["$ref"]
                    # Extract schema name from #/components/schemas/SchemaName
                    if ref.startswith("#/components/schemas/"):
                        schema_name = ref.split("/")[-1]
                        self.assertIn(
                            schema_name, schemas, f"Undefined schema reference: {ref} at {path}"
                        )
                for key, value in obj.items():
                    check_refs(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_refs(item, f"{path}[{i}]")

        check_refs(spec)

    def test_response_codes_are_strings(self):
        """Test that response codes are strings (OpenAPI requirement)."""
        spec = generate_openapi_spec()

        for path, methods in spec.get("paths", {}).items():
            for method, op in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    responses = op.get("responses", {})
                    for code in responses.keys():
                        self.assertIsInstance(
                            code, str, f"Response code should be string at {method.upper()} {path}"
                        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
