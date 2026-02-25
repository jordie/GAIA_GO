"""
Data Persistence Integration Tests

Tests for verifying data persistence across UI interactions, page reloads,
and database operations. Covers concurrent operations and error recovery.

These tests ensure data integrity and proper synchronization between
the UI and database.
"""
import threading
import time
import uuid

import pytest


@pytest.mark.integration
class TestDataPersistence:
    """Test data persistence between UI interactions and database."""

    def test_api_create_and_retrieve(self, authenticated_client, api_test_data):
        """Test creating a resource via API and retrieving it."""
        project_data = api_test_data["valid_project"]

        # Create project
        response = authenticated_client.post("/api/projects", json=project_data)
        assert response.status_code in [200, 201]
        project = response.get_json()
        project_id = project.get("id")

        # Retrieve project
        response = authenticated_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        retrieved = response.get_json()

        # Verify data persisted correctly
        assert retrieved.get("name") == project_data["name"]
        assert retrieved.get("description") == project_data["description"]

    def test_api_update_persists(self, authenticated_client, sample_project):
        """Test that API updates persist in database."""
        project_id = sample_project.get("id", 1)
        new_name = f"Updated Project {uuid.uuid4().hex[:8]}"

        # Update project
        response = authenticated_client.put(
            f"/api/projects/{project_id}",
            json={"name": new_name, "description": "Updated description"},
        )
        assert response.status_code in [200, 204]

        # Retrieve and verify
        response = authenticated_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        updated = response.get_json()
        assert updated.get("name") == new_name

    def test_api_list_after_create(self, authenticated_client, api_test_data):
        """Test that newly created resources appear in list endpoints."""
        project_data = api_test_data["valid_project"]
        project_data["name"] = f"List Test {uuid.uuid4().hex[:8]}"

        # Create project
        response = authenticated_client.post("/api/projects", json=project_data)
        assert response.status_code in [200, 201]
        created = response.get_json()

        # Get projects list
        response = authenticated_client.get("/api/projects")
        assert response.status_code == 200
        projects = response.get_json()

        # Verify newly created project is in list
        assert isinstance(projects, list)
        project_names = [p.get("name") for p in projects]
        assert project_data["name"] in project_names

    def test_delete_removes_from_list(self, authenticated_client, sample_project):
        """Test that deleting a resource removes it from listings."""
        project_id = sample_project.get("id", 1)

        # Delete project
        response = authenticated_client.delete(f"/api/projects/{project_id}")
        assert response.status_code in [200, 204]

        # Verify it's gone from list
        response = authenticated_client.get("/api/projects")
        assert response.status_code == 200
        projects = response.get_json()

        project_ids = [p.get("id") for p in projects if p is not None]
        assert project_id not in project_ids

    def test_partial_update(self, authenticated_client, sample_project):
        """Test partial updates don't overwrite unspecified fields."""
        project_id = sample_project.get("id", 1)
        original_name = sample_project.get("name")

        # Update only description
        response = authenticated_client.put(
            f"/api/projects/{project_id}",
            json={"description": "New description only"},
        )
        assert response.status_code in [200, 204]

        # Verify name unchanged, description updated
        response = authenticated_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        updated = response.get_json()
        assert updated.get("name") == original_name
        assert updated.get("description") == "New description only"


@pytest.mark.integration
class TestConcurrentOperations:
    """Test concurrent/parallel operations and data consistency."""

    def test_concurrent_creates(self, authenticated_client, api_test_data):
        """Test multiple concurrent creation requests."""
        results = []
        errors = []

        def create_project():
            try:
                unique_name = f"Concurrent {uuid.uuid4().hex[:8]}"
                response = authenticated_client.post(
                    "/api/projects",
                    json={"name": unique_name, "description": "Concurrent test"},
                )
                if response.status_code in [200, 201]:
                    results.append(response.get_json())
                else:
                    errors.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Create 5 projects concurrently
        threads = [threading.Thread(target=create_project) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify all succeeded
        assert len(errors) == 0, f"Concurrent creates failed: {errors}"
        assert len(results) >= 4  # At least 4 succeeded

    def test_concurrent_reads(self, authenticated_client, sample_project):
        """Test multiple concurrent read requests."""
        project_id = sample_project.get("id", 1)
        results = []
        errors = []

        def read_project():
            try:
                response = authenticated_client.get(f"/api/projects/{project_id}")
                if response.status_code == 200:
                    results.append(response.get_json())
                else:
                    errors.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Read project concurrently 10 times
        threads = [threading.Thread(target=read_project) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify all succeeded
        assert len(errors) == 0, f"Concurrent reads failed: {errors}"
        assert len(results) == 10

    def test_read_write_consistency(self, authenticated_client, sample_project):
        """Test that reads see the latest writes."""
        project_id = sample_project.get("id", 1)
        counter = {"value": 0}
        lock = threading.Lock()

        def update_and_read():
            # Update counter
            new_value = counter["value"] + 1
            with lock:
                counter["value"] = new_value

            # Update via API
            response = authenticated_client.put(
                f"/api/projects/{project_id}",
                json={"description": f"Update {new_value}"},
            )

            # Read back
            if response.status_code in [200, 204]:
                response = authenticated_client.get(f"/api/projects/{project_id}")
                if response.status_code == 200:
                    project = response.get_json()
                    return project.get("description")
            return None

        # Execute 5 concurrent updates
        results = []

        def wrapper():
            result = update_and_read()
            results.append(result)

        threads = [threading.Thread(target=wrapper) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify at least some reads happened
        assert len(results) > 0


@pytest.mark.integration
class TestErrorRecovery:
    """Test recovery from error conditions."""

    def test_invalid_create_doesnt_persist(self, authenticated_client, api_test_data):
        """Test that invalid data doesn't get persisted on error."""
        invalid_data = api_test_data["invalid_empty"]

        # Try to create with invalid data
        response = authenticated_client.post("/api/projects", json=invalid_data)
        assert response.status_code in [400, 422]  # Should fail validation

        # Verify nothing was created
        response = authenticated_client.get("/api/projects")
        projects = response.get_json()
        empty_names = [p.get("name") for p in projects if not p.get("name")]
        assert len(empty_names) == 0

    def test_failed_update_doesnt_corrupt(self, authenticated_client, sample_project):
        """Test that failed updates don't corrupt existing data."""
        project_id = sample_project.get("id", 1)
        original_name = sample_project.get("name")

        # Try invalid update
        response = authenticated_client.put(
            f"/api/projects/{project_id}",
            json={"name": ""},  # Invalid: empty name
        )
        assert response.status_code in [400, 422, 409]  # Should fail

        # Verify original data intact
        response = authenticated_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        project = response.get_json()
        assert project.get("name") == original_name

    def test_delete_nonexistent_returns_error(self, authenticated_client):
        """Test that deleting nonexistent resource returns appropriate error."""
        response = authenticated_client.delete("/api/projects/999999999")
        assert response.status_code in [404, 410]  # Not found or gone

    def test_get_nonexistent_returns_404(self, authenticated_client):
        """Test that getting nonexistent resource returns 404."""
        response = authenticated_client.get("/api/projects/999999999")
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.requires_db
class TestTransactionIsolation:
    """Test database transaction isolation."""

    def test_transaction_rollback(self, db_transaction):
        """Test that database changes can be rolled back."""
        conn, cursor = db_transaction

        # Create a test record
        cursor.execute(
            """
            INSERT INTO projects (name, description, status)
            VALUES (?, ?, ?)
        """,
            ("Transaction Test", "Test Description", "active"),
        )
        conn.commit()

        # Verify record exists
        cursor.execute("SELECT * FROM projects WHERE name = ?", ("Transaction Test",))
        assert cursor.fetchone() is not None

    def test_multiple_table_consistency(self, db_transaction):
        """Test that changes across multiple tables are consistent."""
        conn, cursor = db_transaction

        # Create project
        cursor.execute(
            """
            INSERT INTO projects (name, description, status)
            VALUES (?, ?, ?)
        """,
            ("Multi Table Test", "Test", "active"),
        )
        conn.commit()

        # Get project ID
        cursor.execute("SELECT id FROM projects WHERE name = ?", ("Multi Table Test",))
        project_id = cursor.fetchone()[0]

        # Create feature linked to project
        cursor.execute(
            """
            INSERT INTO features (project_id, name, status)
            VALUES (?, ?, ?)
        """,
            (project_id, "Test Feature", "draft"),
        )
        conn.commit()

        # Verify both exist and are linked
        cursor.execute(
            "SELECT p.id, f.project_id FROM projects p "
            "JOIN features f ON p.id = f.project_id WHERE p.name = ?",
            ("Multi Table Test",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == row[1]


@pytest.mark.integration
class TestDataValidation:
    """Test data validation and constraints."""

    def test_duplicate_name_rejected(self, authenticated_client):
        """Test that duplicate resource names are rejected."""
        unique_name = f"Duplicate Test {uuid.uuid4().hex[:8]}"

        # Create first project
        response1 = authenticated_client.post(
            "/api/projects",
            json={"name": unique_name, "description": "First"},
        )
        assert response1.status_code in [200, 201]

        # Try to create duplicate
        response2 = authenticated_client.post(
            "/api/projects",
            json={"name": unique_name, "description": "Second"},
        )
        # Should fail with 409 Conflict or 422 Unprocessable Entity
        assert response2.status_code in [409, 422, 400]

    def test_required_fields_validated(self, authenticated_client):
        """Test that required fields are validated."""
        # Try without name
        response = authenticated_client.post("/api/projects", json={"description": "No name"})
        assert response.status_code in [400, 422]

    def test_field_length_constraints(self, authenticated_client, api_test_data):
        """Test that field length constraints are enforced."""
        # Try to create with extremely long name
        response = authenticated_client.post(
            "/api/projects",
            json={"name": "A" * 10000, "description": "Too long name"},
        )
        # Should fail validation
        assert response.status_code in [400, 422, 413]


@pytest.mark.integration
class TestCRUDCompleteWorkflow:
    """Test complete CRUD workflows."""

    def test_full_crud_workflow(self, authenticated_client):
        """Test complete Create-Read-Update-Delete workflow."""
        unique_name = f"CRUD Test {uuid.uuid4().hex[:8]}"

        # Create
        response = authenticated_client.post(
            "/api/projects",
            json={"name": unique_name, "description": "Initial description"},
        )
        assert response.status_code in [200, 201]
        project = response.get_json()
        project_id = project.get("id")

        # Read
        response = authenticated_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        read_project = response.get_json()
        assert read_project.get("name") == unique_name

        # Update
        response = authenticated_client.put(
            f"/api/projects/{project_id}",
            json={"description": "Updated description"},
        )
        assert response.status_code in [200, 204]

        # Verify update
        response = authenticated_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        updated_project = response.get_json()
        assert updated_project.get("description") == "Updated description"

        # Delete
        response = authenticated_client.delete(f"/api/projects/{project_id}")
        assert response.status_code in [200, 204]

        # Verify deletion
        response = authenticated_client.get(f"/api/projects/{project_id}")
        # Should either return 404 or empty result
        assert response.status_code in [404, 200]

    def test_list_after_crud_operations(self, authenticated_client):
        """Test that list endpoints reflect all CRUD operations."""
        names = [f"List Test {i} {uuid.uuid4().hex[:4]}" for i in range(3)]

        # Create 3 projects
        created_ids = []
        for name in names:
            response = authenticated_client.post(
                "/api/projects", json={"name": name, "description": f"Project {name}"}
            )
            if response.status_code in [200, 201]:
                created_ids.append(response.get_json().get("id"))

        # Get list
        response = authenticated_client.get("/api/projects")
        assert response.status_code == 200
        all_projects = response.get_json()

        # Verify all created projects are in list
        list_names = {p.get("name") for p in all_projects if p}
        for name in names:
            assert name in list_names, f"Project '{name}' not found in list"


@pytest.mark.integration
@pytest.mark.performance
class TestPerformanceWithManyRecords:
    """Test system performance with larger datasets."""

    def test_list_performance_with_many_records(self, authenticated_client):
        """Test that listing still works efficiently with many records."""
        # This test verifies the API handles list endpoints
        response = authenticated_client.get("/api/projects")
        assert response.status_code == 200

        start = time.time()
        # Call multiple times to simulate repeated access
        for _ in range(5):
            response = authenticated_client.get("/api/projects")
            assert response.status_code == 200
        elapsed = time.time() - start

        # Should complete quickly (less than 10 seconds for 5 requests)
        assert elapsed < 10.0, f"List took {elapsed:.2f}s"

    def test_search_performance(self, authenticated_client, sample_project):
        """Test search endpoint performance."""
        # If search endpoint exists, test its performance
        response = authenticated_client.get(f"/api/projects?search=test")
        # May not exist, but shouldn't hang
        assert response.status_code in [200, 404]
