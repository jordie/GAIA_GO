"""
API Endpoint Tests for Architect Dashboard
"""
import json

import pytest


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert "database" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_page_loads(self, client):
        """Test login page is accessible."""
        response = client.get("/login")
        assert response.status_code == 200

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/login", data={"username": "testuser", "password": "testpass"}, follow_redirects=True
        )
        assert response.status_code == 200

    def test_login_failure(self, client):
        """Test failed login with wrong password."""
        response = client.post("/login", data={"username": "testuser", "password": "wrongpass"})
        # Login page returns 200 with error message, or 401
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            assert b"Invalid" in response.data or b"error" in response.data.lower()

    def test_unauthenticated_api_access(self, client):
        """Test API endpoints require authentication."""
        response = client.get("/api/projects")
        # Should redirect to login or return 401
        assert response.status_code in [302, 401]


class TestProjectsAPI:
    """Tests for /api/projects endpoints."""

    def test_list_projects(self, authenticated_client):
        """Test listing projects."""
        response = authenticated_client.get("/api/projects")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_create_project(self, authenticated_client):
        """Test creating a project."""
        response = authenticated_client.post(
            "/api/projects", json={"name": "New Test Project", "description": "Test description"}
        )
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert data.get("success") or "id" in data

    def test_create_duplicate_project(self, authenticated_client):
        """Test creating duplicate project fails."""
        # Create first project
        authenticated_client.post(
            "/api/projects", json={"name": "Duplicate Test", "description": "First"}
        )
        # Try to create duplicate
        response = authenticated_client.post(
            "/api/projects", json={"name": "Duplicate Test", "description": "Second"}
        )
        # Should fail or handle gracefully
        data = response.get_json()
        # Either error or renamed with suffix
        assert "error" in data or "id" in data


class TestFeaturesAPI:
    """Tests for /api/features endpoints."""

    def test_list_features(self, authenticated_client):
        """Test listing features."""
        response = authenticated_client.get("/api/features")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_filter_features_by_status(self, authenticated_client):
        """Test filtering features by status."""
        response = authenticated_client.get("/api/features?status=draft")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_feature_workflow_endpoint(self, authenticated_client):
        """Test getting feature workflow definition."""
        response = authenticated_client.get("/api/features/workflow")
        assert response.status_code == 200
        data = response.get_json()
        assert "statuses" in data
        assert "transitions" in data
        assert "initial_status" in data
        assert data["initial_status"] == "draft"
        assert "draft" in data["statuses"]
        assert "completed" in data["statuses"]

    def test_feature_status_workflow_valid_transition(self, authenticated_client, sample_project):
        """Test valid status transition in feature workflow."""
        # Create a feature
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": sample_project["id"],
                "name": "Workflow Test Feature",
                "description": "Testing status workflow",
            },
        )
        assert response.status_code == 200
        feature_id = response.get_json()["id"]

        # Valid transition: draft -> spec
        response = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "spec", "status_comment": "Moving to specification phase"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["status"] == "spec"

    def test_feature_status_workflow_invalid_transition(self, authenticated_client, sample_project):
        """Test invalid status transition is rejected."""
        # Create a feature (starts in draft)
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": sample_project["id"],
                "name": "Invalid Workflow Test",
                "description": "Testing invalid transition",
            },
        )
        feature_id = response.get_json()["id"]

        # Invalid transition: draft -> completed (skipping steps)
        response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"status": "completed"}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "allowed_transitions" in data

    def test_feature_status_history(self, authenticated_client, sample_project):
        """Test feature status history is recorded."""
        # Create and transition a feature
        response = authenticated_client.post(
            "/api/features",
            json={"project_id": sample_project["id"], "name": "History Test Feature"},
        )
        feature_id = response.get_json()["id"]

        # Make a transition
        authenticated_client.put(
            f"/api/features/{feature_id}", json={"status": "spec", "status_comment": "Test comment"}
        )

        # Get history
        response = authenticated_client.get(f"/api/features/{feature_id}/history")
        assert response.status_code == 200
        history = response.get_json()
        assert len(history) >= 1
        assert history[0]["from_status"] == "draft"
        assert history[0]["to_status"] == "spec"
        assert history[0]["comment"] == "Test comment"


class TestBugsAPI:
    """Tests for /api/bugs endpoints."""

    def test_list_bugs(self, authenticated_client):
        """Test listing bugs."""
        response = authenticated_client.get("/api/bugs")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_filter_bugs_by_severity(self, authenticated_client):
        """Test filtering bugs by severity."""
        response = authenticated_client.get("/api/bugs?severity=critical")
        assert response.status_code == 200


class TestErrorsAPI:
    """Tests for /api/errors endpoints."""

    def test_list_errors(self, authenticated_client):
        """Test listing errors with pagination."""
        response = authenticated_client.get("/api/errors")
        assert response.status_code == 200
        data = response.get_json()
        assert "errors" in data
        assert isinstance(data["errors"], list)
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data

    def test_list_errors_with_search(self, authenticated_client):
        """Test listing errors with search filter."""
        # First log a test error
        authenticated_client.post(
            "/api/errors",
            json={
                "error_type": "test_searchable",
                "message": "Unique search test message xyz123",
                "source": "test_search.py",
            },
        )
        # Search for it
        response = authenticated_client.get("/api/errors?search=xyz123&status=all")
        assert response.status_code == 200
        data = response.get_json()
        assert "errors" in data
        # Should find the error we just created
        assert any("xyz123" in e.get("message", "") for e in data["errors"])

    def test_list_errors_with_type_filter(self, authenticated_client):
        """Test listing errors filtered by error_type."""
        response = authenticated_client.get("/api/errors?error_type=test&status=all")
        assert response.status_code == 200
        data = response.get_json()
        assert "errors" in data

    def test_error_stats(self, authenticated_client):
        """Test error statistics endpoint."""
        response = authenticated_client.get("/api/errors/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "by_type" in data
        assert "by_status" in data
        assert "by_severity" in data
        assert "trending" in data
        assert "total_open" in data

    def test_error_summary(self, authenticated_client):
        """Test error summary endpoint."""
        response = authenticated_client.get("/api/errors/summary")
        assert response.status_code == 200
        data = response.get_json()
        assert "counts" in data
        assert "metrics" in data
        assert "top_sources" in data
        assert "top_types" in data
        assert "recent" in data

    def test_log_error_no_auth(self, client):
        """Test logging errors doesn't require auth."""
        response = client.post(
            "/api/errors",
            json={"error_type": "test", "message": "Test error", "source": "test_api.py"},
        )
        # Should accept error log
        assert response.status_code in [200, 201]


class TestNodesAPI:
    """Tests for /api/nodes endpoints."""

    def test_list_nodes(self, authenticated_client):
        """Test listing nodes."""
        response = authenticated_client.get("/api/nodes")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_register_node(self, authenticated_client):
        """Test registering a new node."""
        response = authenticated_client.post(
            "/api/nodes",
            json={
                "name": "test-node-1",
                "hostname": "node1.local",
                "ip_address": "192.168.1.100",
                "capabilities": ["python", "docker"],
            },
        )
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert data.get("success") or "id" in data

    def test_node_heartbeat(self, authenticated_client):
        """Test node heartbeat updates metrics."""
        # First register a node
        create_resp = authenticated_client.post(
            "/api/nodes",
            json={
                "name": "heartbeat-test-node",
                "hostname": "hbnode.local",
                "ip_address": "192.168.1.101",
            },
        )
        node_id = create_resp.get_json().get("id")
        if not node_id:
            # Node may already exist, skip this test
            return

        # Send heartbeat with metrics
        response = authenticated_client.post(
            f"/api/nodes/{node_id}/heartbeat",
            json={
                "cpu_usage": 45.5,
                "memory_usage": 62.3,
                "disk_usage": 55.0,
                "load_average": 1.2,
                "uptime": 86400,
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True


class TestNodesHealthAPI:
    """Tests for node health monitoring endpoints."""

    def test_get_all_nodes_health(self, authenticated_client):
        """Test getting health status of all nodes."""
        response = authenticated_client.get("/api/nodes/health")
        assert response.status_code == 200
        data = response.get_json()
        # API returns object with nodes list and summary
        assert "nodes" in data
        assert "summary" in data
        assert isinstance(data["nodes"], list)

    def test_get_single_node_health(self, authenticated_client):
        """Test getting detailed health for a single node."""
        # First register a node
        create_resp = authenticated_client.post(
            "/api/nodes",
            json={
                "name": "health-test-node",
                "hostname": "healthnode.local",
                "ip_address": "192.168.1.102",
            },
        )
        node_id = create_resp.get_json().get("id")
        if not node_id:
            return

        response = authenticated_client.get(f"/api/nodes/{node_id}/health")
        assert response.status_code == 200
        data = response.get_json()
        # API returns nested structure with node and health info
        assert "node" in data
        assert "thresholds" in data
        assert "health" in data
        assert data["node"].get("health_status") is not None

    def test_get_node_alerts(self, authenticated_client):
        """Test getting node alerts."""
        response = authenticated_client.get("/api/nodes/alerts")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_node_alerts_filter_by_severity(self, authenticated_client):
        """Test filtering alerts by severity."""
        response = authenticated_client.get("/api/nodes/alerts?severity=critical")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # All returned alerts should be critical
        for alert in data:
            assert alert.get("severity") == "critical"

    def test_node_alerts_filter_by_status(self, authenticated_client):
        """Test filtering alerts by status."""
        response = authenticated_client.get("/api/nodes/alerts?status=active")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)


class TestLoadBalancerAPI:
    """Tests for load balancer endpoints."""

    def test_get_node_recommendations(self, authenticated_client):
        """Test getting recommended nodes for task assignment."""
        response = authenticated_client.get("/api/nodes/recommend")
        # 200 if nodes exist, 404 if no online nodes available
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert "recommendations" in data
            assert isinstance(data["recommendations"], list)

    def test_get_node_recommendations_with_count(self, authenticated_client):
        """Test getting specific number of recommendations."""
        response = authenticated_client.get("/api/nodes/recommend?count=3")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert len(data["recommendations"]) <= 3

    def test_get_task_distribution(self, authenticated_client):
        """Test getting current task distribution across nodes."""
        response = authenticated_client.get("/api/nodes/distribution")
        assert response.status_code == 200
        data = response.get_json()
        assert "distribution" in data
        # API returns summary with aggregated stats
        assert "summary" in data

    def test_rebalance_tasks(self, authenticated_client):
        """Test task rebalancing suggestions."""
        # Requires task_id parameter
        response = authenticated_client.post("/api/nodes/rebalance", json={"task_id": 1})
        # May return 400 if task not found or 200 with suggestions
        assert response.status_code in [200, 400, 404]
        data = response.get_json()
        # Should return either error or suggestions
        assert "error" in data or "suggestions" in data or "success" in data

    def test_assign_task_optimal(self, authenticated_client):
        """Test optimal task assignment endpoint."""
        response = authenticated_client.post(
            "/api/tasks/assign-optimal", json={"task_type": "shell", "requirements": ["python"]}
        )
        # 200 success, 404 no nodes, 503 service unavailable (no online nodes)
        assert response.status_code in [200, 404, 503]


class TestClusterAPI:
    """Tests for cluster visualization endpoints."""

    def test_get_cluster_topology(self, authenticated_client):
        """Test getting cluster topology graph."""
        response = authenticated_client.get("/api/cluster/topology")
        assert response.status_code == 200
        data = response.get_json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_get_cluster_flow(self, authenticated_client):
        """Test getting task flow visualization data."""
        response = authenticated_client.get("/api/cluster/flow")
        assert response.status_code == 200
        data = response.get_json()
        # API returns recent_tasks for flow visualization
        assert "recent_tasks" in data or "flows" in data
        assert "timestamp" in data

    def test_get_cluster_stats(self, authenticated_client):
        """Test getting cluster-wide statistics."""
        response = authenticated_client.get("/api/cluster/stats")
        assert response.status_code == 200
        data = response.get_json()
        # API returns nested structure with nodes and tasks
        assert "nodes" in data
        assert "tasks" in data


class TestSSHPoolAPI:
    """Tests for SSH connection pool endpoints."""

    def test_get_pool_stats(self, authenticated_client):
        """Test getting SSH pool statistics."""
        response = authenticated_client.get("/api/ssh/pool/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "total_created" in data
        assert "total_reused" in data
        assert "total_closed" in data
        assert "active_connections" in data
        assert "pools" in data

    def test_cleanup_pool(self, authenticated_client):
        """Test cleaning up idle SSH connections."""
        response = authenticated_client.post("/api/ssh/pool/cleanup", json={})
        assert response.status_code == 200
        data = response.get_json()
        assert "closed" in data or "success" in data

    def test_execute_requires_node_id(self, authenticated_client):
        """Test SSH execute requires node_id parameter."""
        response = authenticated_client.post("/api/ssh/execute", json={"command": "echo test"})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_broadcast_command(self, authenticated_client):
        """Test broadcasting command to all nodes."""
        response = authenticated_client.post("/api/ssh/broadcast", json={"command": "uptime"})
        # May fail if no nodes are online, but endpoint should work
        assert response.status_code in [200, 404]
        data = response.get_json()
        if response.status_code == 200:
            assert "results" in data


class TestStatsAPI:
    """Tests for /api/stats endpoint."""

    def test_get_stats(self, authenticated_client):
        """Test getting dashboard stats."""
        response = authenticated_client.get("/api/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "projects" in data or "features" in data


class TestTmuxAPI:
    """Tests for /api/tmux endpoints."""

    def test_list_tmux_sessions(self, authenticated_client):
        """Test listing tmux sessions."""
        response = authenticated_client.get("/api/tmux/sessions")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)


class TestTasksAPI:
    """Tests for /api/tasks endpoints."""

    def test_list_tasks(self, authenticated_client):
        """Test listing tasks."""
        response = authenticated_client.get("/api/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)


class TestSecretsAPI:
    """Tests for /api/secrets endpoints (Secure Vault)."""

    def test_list_secrets(self, authenticated_client):
        """Test listing secrets returns empty list or existing secrets."""
        response = authenticated_client.get("/api/secrets")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_create_secret(self, authenticated_client):
        """Test creating a new secret."""
        response = authenticated_client.post(
            "/api/secrets",
            json={
                "name": "TEST_SECRET_KEY",
                "value": "super-secret-value-123",
                "category": "api_key",
                "description": "Test API key for unit tests",
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True
        assert "id" in data

    def test_create_secret_requires_name_and_value(self, authenticated_client):
        """Test creating secret without required fields fails."""
        # Missing value
        response = authenticated_client.post("/api/secrets", json={"name": "INCOMPLETE_SECRET"})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

        # Missing name
        response = authenticated_client.post("/api/secrets", json={"value": "some-value"})
        assert response.status_code == 400

    def test_create_duplicate_secret_fails(self, authenticated_client):
        """Test creating duplicate secret returns error."""
        # Create first secret
        authenticated_client.post(
            "/api/secrets", json={"name": "DUPLICATE_TEST_SECRET", "value": "first-value"}
        )
        # Try to create duplicate
        response = authenticated_client.post(
            "/api/secrets", json={"name": "DUPLICATE_TEST_SECRET", "value": "second-value"}
        )
        assert response.status_code == 409
        data = response.get_json()
        assert "error" in data
        assert "already exists" in data["error"]

    def test_view_secret_returns_decrypted_value(self, authenticated_client):
        """Test viewing a secret returns decrypted value."""
        # Create a secret first
        create_response = authenticated_client.post(
            "/api/secrets",
            json={
                "name": "VIEW_TEST_SECRET",
                "value": "my-secret-value-xyz",
                "category": "password",
            },
        )
        secret_id = create_response.get_json()["id"]

        # View the secret
        response = authenticated_client.get(f"/api/secrets/{secret_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "VIEW_TEST_SECRET"
        assert data["value"] == "my-secret-value-xyz"
        assert data["category"] == "password"

    def test_update_secret(self, authenticated_client):
        """Test updating a secret."""
        # Create a secret first
        create_response = authenticated_client.post(
            "/api/secrets",
            json={
                "name": "UPDATE_TEST_SECRET",
                "value": "original-value",
                "category": "token",
                "description": "Original description",
            },
        )
        secret_id = create_response.get_json()["id"]

        # Update the secret
        response = authenticated_client.put(
            f"/api/secrets/{secret_id}",
            json={"description": "Updated description", "category": "api_key"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True

        # Verify update
        list_response = authenticated_client.get("/api/secrets")
        secrets = list_response.get_json()
        updated = next((s for s in secrets if s["id"] == secret_id), None)
        assert updated is not None
        assert updated["description"] == "Updated description"
        assert updated["category"] == "api_key"

    def test_update_secret_value(self, authenticated_client):
        """Test updating a secret's encrypted value."""
        # Create a secret first
        create_response = authenticated_client.post(
            "/api/secrets", json={"name": "VALUE_UPDATE_SECRET", "value": "old-secret-value"}
        )
        secret_id = create_response.get_json()["id"]

        # Update the value
        authenticated_client.put(f"/api/secrets/{secret_id}", json={"value": "new-secret-value"})

        # Verify new value is decrypted correctly
        response = authenticated_client.get(f"/api/secrets/{secret_id}")
        data = response.get_json()
        assert data["value"] == "new-secret-value"

    def test_delete_secret(self, authenticated_client):
        """Test deleting a secret."""
        # Create a secret first
        create_response = authenticated_client.post(
            "/api/secrets", json={"name": "DELETE_TEST_SECRET", "value": "to-be-deleted"}
        )
        secret_id = create_response.get_json()["id"]

        # Delete the secret
        response = authenticated_client.delete(f"/api/secrets/{secret_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True

        # Verify deletion
        get_response = authenticated_client.get(f"/api/secrets/{secret_id}")
        assert get_response.status_code == 404

    def test_view_nonexistent_secret_returns_404(self, authenticated_client):
        """Test viewing non-existent secret returns 404."""
        response = authenticated_client.get("/api/secrets/99999")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_delete_nonexistent_secret_returns_404(self, authenticated_client):
        """Test deleting non-existent secret returns 404."""
        response = authenticated_client.delete("/api/secrets/99999")
        assert response.status_code == 404

    def test_secret_access_count_increments(self, authenticated_client):
        """Test that viewing a secret increments access count."""
        # Create a secret
        create_response = authenticated_client.post(
            "/api/secrets", json={"name": "ACCESS_COUNT_SECRET", "value": "count-me"}
        )
        secret_id = create_response.get_json()["id"]

        # View it twice
        authenticated_client.get(f"/api/secrets/{secret_id}")
        authenticated_client.get(f"/api/secrets/{secret_id}")

        # Check access count
        list_response = authenticated_client.get("/api/secrets")
        secrets = list_response.get_json()
        secret = next((s for s in secrets if s["id"] == secret_id), None)
        assert secret is not None
        assert secret["access_count"] == 2

    def test_secret_categories(self, authenticated_client):
        """Test creating secrets with different categories."""
        categories = [
            "api_key",
            "password",
            "token",
            "certificate",
            "ssh_key",
            "env_var",
            "general",
        ]

        for category in categories:
            response = authenticated_client.post(
                "/api/secrets",
                json={
                    "name": f"CATEGORY_TEST_{category.upper()}",
                    "value": f"value-for-{category}",
                    "category": category,
                },
            )
            assert response.status_code == 200, f"Failed to create secret with category: {category}"

    def test_secrets_list_hides_values(self, authenticated_client):
        """Test that listing secrets does not expose encrypted values."""
        # Create a secret
        authenticated_client.post(
            "/api/secrets",
            json={"name": "HIDDEN_VALUE_SECRET", "value": "this-should-not-appear-in-list"},
        )

        # List secrets
        response = authenticated_client.get("/api/secrets")
        data = response.get_json()

        # Verify no 'value' or 'encrypted_value' in list response
        for secret in data:
            assert "value" not in secret, "Secret value should not be in list response"
            # encrypted_value should also not be exposed
            if "encrypted_value" in secret:
                assert secret["encrypted_value"] != "this-should-not-appear-in-list"
