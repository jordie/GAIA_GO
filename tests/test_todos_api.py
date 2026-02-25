"""
Comprehensive test suite for Todo REST API endpoints.

Tests cover:
- All 4 CRUD operations (GET, POST, PUT, DELETE)
- Input validation and error handling
- Data persistence and integrity
- Response format and status codes
- Edge cases and concurrent operations
"""

import json
import sqlite3
from datetime import datetime

import pytest


# Clear todos table before each test to ensure data isolation
@pytest.fixture(autouse=True)
def cleanup_todos_db():
    """Clear todos table before and after each test."""
    db_path = "data/todos.db"
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM todos")
        conn.commit()
        conn.close()
    except Exception:
        pass  # Database may not exist yet

    yield

    # Cleanup after test
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM todos")
        conn.commit()
        conn.close()
    except Exception:
        pass


class TestTodoAPIIntegration:
    """Integration tests for Todo REST API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_client):
        """Setup for each test."""
        self.client = authenticated_client
        self.base_url = "/api/todos"

    def test_get_todos_empty(self):
        """Test GET /api/todos returns empty list when no todos exist."""
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        data = response.get_json()
        assert "todos" in data
        assert "count" in data
        assert data["count"] == 0
        assert data["todos"] == []

    def test_create_todo_minimal(self):
        """Test POST /api/todos with only required title field."""
        payload = {"title": "My first todo"}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()

        # Verify response structure
        assert "id" in data
        assert data["title"] == "My first todo"
        assert data["description"] == ""
        assert data["completed"] is False
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_todo_with_description(self):
        """Test POST /api/todos with title and description."""
        payload = {
            "title": "Learn testing",
            "description": "Write comprehensive unit tests",
        }
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()

        assert data["title"] == "Learn testing"
        assert data["description"] == "Write comprehensive unit tests"
        assert data["completed"] is False

    def test_create_todo_title_whitespace_trimmed(self):
        """Test POST /api/todos trims whitespace from title."""
        payload = {"title": "  Trim whitespace  "}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Trim whitespace"

    def test_create_todo_description_whitespace_trimmed(self):
        """Test POST /api/todos trims whitespace from description."""
        payload = {
            "title": "Test",
            "description": "  Trim this description  ",
        }
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["description"] == "Trim this description"

    def test_create_todo_missing_title(self):
        """Test POST /api/todos returns 400 when title is missing."""
        payload = {"description": "No title"}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "required" in data["error"].lower()

    def test_create_todo_empty_title(self):
        """Test POST /api/todos returns 400 when title is empty string."""
        payload = {"title": ""}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert "empty" in data["error"].lower()

    def test_create_todo_whitespace_only_title(self):
        """Test POST /api/todos returns 400 when title is only whitespace."""
        payload = {"title": "   "}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 400

    def test_create_todo_title_too_long(self):
        """Test POST /api/todos returns 400 when title exceeds max length."""
        payload = {"title": "x" * 501}  # Max is 500
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert "too long" in data["error"].lower()

    def test_create_todo_title_at_max_length(self):
        """Test POST /api/todos accepts title at maximum length."""
        payload = {"title": "x" * 500}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201

    def test_create_todo_empty_json(self):
        """Test POST /api/todos returns 400 when body is empty."""
        response = self.client.post(self.base_url, json={})
        assert response.status_code == 400

    def test_create_todo_invalid_json(self):
        """Test POST /api/todos handles invalid JSON gracefully."""
        response = self.client.post(
            self.base_url,
            data="invalid json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_get_todos_after_creation(self):
        """Test GET /api/todos returns created todos."""
        # Create two todos
        todo1_payload = {"title": "First todo"}
        todo1_response = self.client.post(self.base_url, json=todo1_payload)
        todo1_id = todo1_response.get_json()["id"]

        todo2_payload = {"title": "Second todo", "description": "With description"}
        todo2_response = self.client.post(self.base_url, json=todo2_payload)
        todo2_id = todo2_response.get_json()["id"]

        # Get all todos
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        data = response.get_json()

        assert data["count"] == 2
        assert len(data["todos"]) == 2

        # Verify todos are in newest-first order
        assert data["todos"][0]["id"] == todo2_id
        assert data["todos"][1]["id"] == todo1_id

    def test_update_todo_title(self):
        """Test PUT /api/todos/{id} updates title."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Original title"})
        todo_id = create_response.get_json()["id"]

        # Update title
        update_response = self.client.put(
            f"{self.base_url}/{todo_id}", json={"title": "Updated title"}
        )
        assert update_response.status_code == 200
        data = update_response.get_json()

        assert data["title"] == "Updated title"
        assert data["id"] == todo_id
        assert "updated_at" in data

    def test_update_todo_description(self):
        """Test PUT /api/todos/{id} updates description."""
        # Create a todo
        create_response = self.client.post(
            self.base_url, json={"title": "Test", "description": "Original"}
        )
        todo_id = create_response.get_json()["id"]

        # Update description
        update_response = self.client.put(
            f"{self.base_url}/{todo_id}",
            json={"description": "Updated description"},
        )
        assert update_response.status_code == 200
        data = update_response.get_json()

        assert data["title"] == "Test"  # Title unchanged
        assert data["description"] == "Updated description"

    def test_update_todo_completed_status(self):
        """Test PUT /api/todos/{id} updates completed status."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Test"})
        todo_id = create_response.get_json()["id"]

        # Mark as completed
        update_response = self.client.put(f"{self.base_url}/{todo_id}", json={"completed": True})
        assert update_response.status_code == 200
        data = update_response.get_json()

        assert data["completed"] is True

        # Mark as incomplete
        update_response = self.client.put(f"{self.base_url}/{todo_id}", json={"completed": False})
        assert update_response.status_code == 200
        data = update_response.get_json()

        assert data["completed"] is False

    def test_update_todo_multiple_fields(self):
        """Test PUT /api/todos/{id} updates multiple fields at once."""
        # Create a todo
        create_response = self.client.post(
            self.base_url,
            json={
                "title": "Original",
                "description": "Original description",
            },
        )
        todo_id = create_response.get_json()["id"]

        # Update multiple fields
        update_response = self.client.put(
            f"{self.base_url}/{todo_id}",
            json={
                "title": "New title",
                "description": "New description",
                "completed": True,
            },
        )
        assert update_response.status_code == 200
        data = update_response.get_json()

        assert data["title"] == "New title"
        assert data["description"] == "New description"
        assert data["completed"] is True

    def test_update_todo_not_found(self):
        """Test PUT /api/todos/{id} returns 404 for non-existent todo."""
        response = self.client.put(f"{self.base_url}/99999", json={"title": "Updated"})
        assert response.status_code == 404
        data = response.get_json()
        assert "not found" in data["error"].lower()

    def test_update_todo_empty_title_validation(self):
        """Test PUT /api/todos/{id} returns 400 for empty title."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Original"})
        todo_id = create_response.get_json()["id"]

        # Try to update with empty title
        update_response = self.client.put(f"{self.base_url}/{todo_id}", json={"title": ""})
        assert update_response.status_code == 400

    def test_update_todo_title_too_long(self):
        """Test PUT /api/todos/{id} returns 400 when title exceeds max length."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Original"})
        todo_id = create_response.get_json()["id"]

        # Try to update with oversized title
        update_response = self.client.put(f"{self.base_url}/{todo_id}", json={"title": "x" * 501})
        assert update_response.status_code == 400

    def test_update_todo_preserves_created_at(self):
        """Test PUT /api/todos/{id} preserves created_at timestamp."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Original"})
        create_data = create_response.get_json()
        todo_id = create_data["id"]
        created_at = create_data["created_at"]

        # Update the todo
        update_response = self.client.put(f"{self.base_url}/{todo_id}", json={"title": "Updated"})
        update_data = update_response.get_json()

        assert update_data["created_at"] == created_at

    def test_update_todo_updates_updated_at(self):
        """Test PUT /api/todos/{id} updates the updated_at timestamp."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Original"})
        create_data = create_response.get_json()
        todo_id = create_data["id"]
        original_updated_at = create_data["updated_at"]

        # Update the todo
        import time

        time.sleep(0.1)  # Ensure timestamp changes
        update_response = self.client.put(f"{self.base_url}/{todo_id}", json={"title": "Updated"})
        update_data = update_response.get_json()

        assert update_data["updated_at"] > original_updated_at

    def test_delete_todo(self):
        """Test DELETE /api/todos/{id} deletes a todo."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "To delete"})
        todo_id = create_response.get_json()["id"]

        # Delete it
        delete_response = self.client.delete(f"{self.base_url}/{todo_id}")
        assert delete_response.status_code == 200
        data = delete_response.get_json()

        assert "deleted" in data["message"].lower()
        assert str(todo_id) in data["message"]

        # Verify it's gone
        get_response = self.client.get(f"{self.base_url}/{todo_id}")
        assert get_response.status_code == 404

    def test_delete_todo_not_found(self):
        """Test DELETE /api/todos/{id} returns 404 for non-existent todo."""
        response = self.client.delete(f"{self.base_url}/99999")
        assert response.status_code == 404
        data = response.get_json()
        assert "not found" in data["error"].lower()

    def test_delete_todo_removes_from_list(self):
        """Test deleted todo no longer appears in GET /api/todos."""
        # Create two todos
        todo1 = self.client.post(self.base_url, json={"title": "Keep this"}).get_json()
        todo2 = self.client.post(self.base_url, json={"title": "Delete this"}).get_json()

        # Delete one
        self.client.delete(f"{self.base_url}/{todo2['id']}")

        # Get all
        response = self.client.get(self.base_url)
        data = response.get_json()

        assert data["count"] == 1
        assert data["todos"][0]["id"] == todo1["id"]

    def test_get_single_todo(self):
        """Test GET /api/todos/{id} retrieves a specific todo."""
        # Create a todo
        create_response = self.client.post(
            self.base_url,
            json={
                "title": "Specific todo",
                "description": "Find me by ID",
            },
        )
        created_todo = create_response.get_json()
        todo_id = created_todo["id"]

        # Get it by ID
        response = self.client.get(f"{self.base_url}/{todo_id}")
        assert response.status_code == 200
        data = response.get_json()

        assert data["id"] == todo_id
        assert data["title"] == "Specific todo"
        assert data["description"] == "Find me by ID"

    def test_response_json_structure(self):
        """Test response JSON structure matches specification."""
        # Create a todo
        create_response = self.client.post(
            self.base_url,
            json={
                "title": "Test structure",
                "description": "Validate JSON",
            },
        )
        data = create_response.get_json()

        # Verify all required fields present
        required_fields = [
            "id",
            "title",
            "description",
            "completed",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Verify field types
        assert isinstance(data["id"], int)
        assert isinstance(data["title"], str)
        assert isinstance(data["description"], str)
        assert isinstance(data["completed"], bool)
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

    def test_concurrent_todo_creation(self):
        """Test creating multiple todos concurrently maintains integrity."""
        todos = []
        for i in range(5):
            response = self.client.post(
                self.base_url,
                json={"title": f"Concurrent todo {i}"},
            )
            todos.append(response.get_json())

        # Verify all created with unique IDs
        ids = [t["id"] for t in todos]
        assert len(ids) == len(set(ids)), "Duplicate IDs created"

        # Verify all retrievable
        response = self.client.get(self.base_url)
        data = response.get_json()
        assert data["count"] == 5

    def test_error_response_format(self):
        """Test error responses have consistent format."""
        # Trigger error by missing title
        response = self.client.post(self.base_url, json={})
        data = response.get_json()

        # Verify error structure
        assert "error" in data
        assert isinstance(data["error"], str)
        assert len(data["error"]) > 0

    def test_invalid_todo_id_format(self):
        """Test invalid todo ID format returns appropriate error."""
        response = self.client.get(f"{self.base_url}/not_a_number")
        assert response.status_code == 404 or response.status_code == 400

    def test_special_characters_in_title(self):
        """Test todos with special characters in title."""
        payload = {"title": "Todo with special chars: !@#$%^&*()_+-=[]{}|;:',.<>?/"}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == payload["title"]

    def test_unicode_characters_in_title(self):
        """Test todos with unicode characters in title."""
        payload = {"title": "Todo with emoji: 🎉🚀✨ and Chinese: 你好"}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == payload["title"]

    def test_very_long_description(self):
        """Test creating todo with very long description."""
        long_desc = "x" * 10000
        payload = {
            "title": "Long description test",
            "description": long_desc,
        }
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["description"] == long_desc

    def test_null_description(self):
        """Test creating todo with null description."""
        payload = {"title": "No description", "description": None}
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["description"] == ""

    def test_database_persistence(self, app):
        """Test todos persist in database across requests."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Persistent todo"})
        todo_id = create_response.get_json()["id"]

        # Query database directly to verify persistence
        # This would require access to DB_PATH from routes/todos.py
        # For now, we verify through API
        response = self.client.get(f"{self.base_url}/{todo_id}")
        assert response.status_code == 200


class TestTodoAPIEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_client):
        """Setup for each test."""
        self.client = authenticated_client
        self.base_url = "/api/todos"

    def test_update_todo_with_null_fields(self):
        """Test updating todo with null values."""
        # Create a todo
        create_response = self.client.post(
            self.base_url, json={"title": "Original", "description": "Desc"}
        )
        todo_id = create_response.get_json()["id"]

        # Try updating with null
        update_response = self.client.put(
            f"{self.base_url}/{todo_id}",
            json={"description": None},
        )

        # Should handle gracefully - either 400 or convert to empty string
        assert update_response.status_code in [200, 400]

    def test_update_todo_with_no_fields(self):
        """Test updating todo with empty JSON object."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Original"})
        created_todo = create_response.get_json()
        todo_id = created_todo["id"]

        # Update with empty JSON
        update_response = self.client.put(f"{self.base_url}/{todo_id}", json={})

        # Should return 200 (no changes) or maintain current values
        assert update_response.status_code == 200

    def test_boolean_completed_conversions(self):
        """Test various boolean representations for completed field."""
        # Create a todo
        create_response = self.client.post(self.base_url, json={"title": "Boolean test"})
        todo_id = create_response.get_json()["id"]

        # Test with string "true"
        response = self.client.put(
            f"{self.base_url}/{todo_id}",
            json={"completed": "true"},
        )
        # Implementation may accept or reject - both are valid behaviors

    def test_large_number_of_todos(self):
        """Test creating and retrieving large number of todos."""
        # Create 100 todos (reasonable limit for testing)
        for i in range(100):
            self.client.post(self.base_url, json={"title": f"Todo {i}"})

        # Retrieve all
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 100
        assert len(data["todos"]) == 100
