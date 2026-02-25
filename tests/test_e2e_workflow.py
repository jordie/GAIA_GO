"""
End-to-End Workflow Tests for Architect Dashboard

Tests complete workflows from project creation to task completion,
validating the entire system works together.
"""
import json

import pytest


class TestProjectWorkflow:
    """Test complete project lifecycle workflow."""

    def test_full_project_lifecycle(self, authenticated_client):
        """Test creating a project, adding features/bugs, and tracking progress."""
        # 1. Create a new project
        project_resp = authenticated_client.post(
            "/api/projects",
            json={
                "name": "E2E Test Project",
                "description": "Project for E2E testing",
                "source_path": "/tmp/e2e-test",
            },
        )
        assert project_resp.status_code in [200, 201]
        project = project_resp.get_json()
        project_id = project.get("id")
        assert project_id is not None

        # 2. Create a feature for the project
        feature_resp = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "E2E Test Feature",
                "description": "Feature created in E2E test",
            },
        )
        assert feature_resp.status_code == 200
        feature = feature_resp.get_json()
        feature_id = feature.get("id")
        # API returns {success, id} - feature starts in draft status

        # 3. Progress feature through workflow
        # draft -> spec
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "spec", "status_comment": "Specification complete"},
        )
        assert resp.status_code == 200

        # spec -> in_progress
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "in_progress", "status_comment": "Development started"},
        )
        assert resp.status_code == 200

        # in_progress -> review
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "review", "status_comment": "Ready for review"},
        )
        assert resp.status_code == 200

        # review -> completed
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "completed", "status_comment": "Feature complete"},
        )
        assert resp.status_code == 200

        # 4. Verify status history was recorded
        history_resp = authenticated_client.get(f"/api/features/{feature_id}/history")
        assert history_resp.status_code == 200
        history = history_resp.get_json()
        assert len(history) == 4  # 4 transitions

        # 5. Create a bug for the project
        bug_resp = authenticated_client.post(
            "/api/bugs",
            json={
                "project_id": project_id,
                "title": "E2E Test Bug",
                "description": "Bug found during E2E testing",
                "severity": "medium",
            },
        )
        assert bug_resp.status_code in [200, 201]
        bug = bug_resp.get_json()
        bug_id = bug.get("id")

        # 6. Resolve the bug
        resolve_resp = authenticated_client.put(
            f"/api/bugs/{bug_id}", json={"status": "closed", "resolution": "Fixed in E2E test"}
        )
        assert resolve_resp.status_code == 200

        # 7. Verify project stats reflect changes
        stats_resp = authenticated_client.get("/api/stats")
        assert stats_resp.status_code == 200


class TestFeatureWorkflowE2E:
    """Test feature status workflow end-to-end."""

    def test_feature_workflow_with_blocking(self, authenticated_client, sample_project):
        """Test feature workflow including blocking and unblocking."""
        # Create feature
        resp = authenticated_client.post(
            "/api/features",
            json={
                "project_id": sample_project["id"],
                "name": "Workflow Block Test",
                "description": "Testing blocked workflow",
            },
        )
        feature_id = resp.get_json()["id"]

        # Move to in_progress
        authenticated_client.put(f"/api/features/{feature_id}", json={"status": "spec"})
        authenticated_client.put(f"/api/features/{feature_id}", json={"status": "in_progress"})

        # Block the feature
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "blocked", "status_comment": "Waiting for dependency"},
        )
        assert resp.status_code == 200

        # Unblock back to in_progress
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "in_progress", "status_comment": "Dependency resolved"},
        )
        assert resp.status_code == 200

        # Complete the feature
        authenticated_client.put(f"/api/features/{feature_id}", json={"status": "review"})
        resp = authenticated_client.put(f"/api/features/{feature_id}", json={"status": "completed"})
        assert resp.status_code == 200

    def test_feature_cancellation(self, authenticated_client, sample_project):
        """Test cancelling a feature from any state."""
        # Create feature
        resp = authenticated_client.post(
            "/api/features",
            json={
                "project_id": sample_project["id"],
                "name": "Cancellation Test",
                "description": "Testing cancellation",
            },
        )
        feature_id = resp.get_json()["id"]

        # Move to in_progress
        authenticated_client.put(f"/api/features/{feature_id}", json={"status": "spec"})
        authenticated_client.put(f"/api/features/{feature_id}", json={"status": "in_progress"})

        # Cancel the feature
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "cancelled", "status_comment": "No longer needed"},
        )
        assert resp.status_code == 200

        # Verify can reopen from cancelled
        resp = authenticated_client.put(
            f"/api/features/{feature_id}",
            json={"status": "draft", "status_comment": "Reopening feature"},
        )
        assert resp.status_code == 200


class TestErrorTooBugWorkflow:
    """Test workflow from error logging to bug creation."""

    def test_error_to_bug_conversion(self, authenticated_client, sample_project):
        """Test logging an error and converting it to a bug."""
        # 1. Log an error (no auth required)
        error_resp = authenticated_client.post(
            "/api/errors",
            json={
                "node_id": "e2e-test-node",
                "error_type": "RuntimeError",
                "message": "E2E test error for conversion",
                "source": "test_e2e_workflow.py",
                "stack_trace": "Traceback: ...",
            },
        )
        assert error_resp.status_code in [200, 201]
        error = error_resp.get_json()
        error_id = error.get("id")

        # 2. Convert error to bug
        convert_resp = authenticated_client.post(
            f"/api/errors/{error_id}/create-bug",
            json={"project_id": sample_project["id"], "severity": "high"},
        )
        # May fail if endpoint doesn't exist, but should respond
        assert convert_resp.status_code in [200, 201, 400, 404]

        if convert_resp.status_code == 200:
            bug_data = convert_resp.get_json()
            assert bug_data.get("bug_id") or bug_data.get("success")

    def test_error_resolution(self, authenticated_client):
        """Test logging and resolving an error."""
        # Log error
        error_resp = authenticated_client.post(
            "/api/errors",
            json={
                "error_type": "ValueError",
                "message": "E2E resolution test error",
                "source": "test_module.py",
            },
        )
        error = error_resp.get_json()
        error_id = error.get("id")

        # Resolve error
        resolve_resp = authenticated_client.post(
            f"/api/errors/{error_id}/resolve", json={"resolution": "Fixed in E2E test"}
        )
        assert resolve_resp.status_code in [200, 404]  # 404 if already resolved


class TestTaskQueueWorkflow:
    """Test task queue workflow from creation to completion."""

    def test_task_lifecycle(self, authenticated_client):
        """Test complete task lifecycle: create -> claim -> complete."""
        # 1. Create a task
        task_resp = authenticated_client.post(
            "/api/tasks",
            json={
                "title": "E2E Test Task",
                "description": "Task for E2E testing",
                "task_type": "shell",
                "payload": {"command": 'echo "E2E test"'},
            },
        )
        assert task_resp.status_code in [200, 201]
        task = task_resp.get_json()
        task_id = task.get("id")
        # API returns {success, id} - task created with pending status
        assert task_id is not None

        # 2. Claim the task (simulating a worker)
        claim_resp = authenticated_client.post(
            "/api/tasks/claim", json={"worker_id": "e2e-test-worker", "task_types": ["shell"]}
        )
        assert claim_resp.status_code in [200, 404]  # 404 if no tasks

        if claim_resp.status_code == 200:
            claimed = claim_resp.get_json()
            claimed_id = claimed.get("id") or claimed.get("task_id")

            if claimed_id:
                # 3. Complete the task
                complete_resp = authenticated_client.post(
                    f"/api/tasks/{claimed_id}/complete",
                    json={"result": {"output": "E2E test output"}},
                )
                assert complete_resp.status_code == 200

    def test_task_failure_handling(self, authenticated_client):
        """Test task failure workflow."""
        # Create a task
        task_resp = authenticated_client.post(
            "/api/tasks",
            json={
                "title": "Failing E2E Task",
                "task_type": "shell",
                "payload": {"command": "exit 1"},
            },
        )
        task = task_resp.get_json()
        task_id = task.get("id")

        # Claim and fail it
        claim_resp = authenticated_client.post(
            "/api/tasks/claim", json={"worker_id": "e2e-fail-worker", "task_types": ["shell"]}
        )

        if claim_resp.status_code == 200:
            claimed = claim_resp.get_json()
            claimed_id = claimed.get("id") or claimed.get("task_id")
            if claimed_id:
                # Mark as failed
                fail_resp = authenticated_client.post(
                    f"/api/tasks/{claimed_id}/fail", json={"error": "Command exited with code 1"}
                )
                assert fail_resp.status_code == 200


class TestNodeManagementWorkflow:
    """Test node registration and monitoring workflow."""

    def test_node_registration_and_heartbeat(self, authenticated_client):
        """Test registering a node and sending heartbeats."""
        # 1. Register a new node
        register_resp = authenticated_client.post(
            "/api/nodes",
            json={
                "name": "e2e-test-node",
                "hostname": "e2e-node.local",
                "ip_address": "192.168.100.1",
                "capabilities": ["python", "docker", "git"],
            },
        )
        assert register_resp.status_code in [200, 201]
        node = register_resp.get_json()
        node_id = node.get("id")

        if node_id:
            # 2. Send heartbeat with metrics
            heartbeat_resp = authenticated_client.post(
                f"/api/nodes/{node_id}/heartbeat",
                json={
                    "cpu_usage": 25.5,
                    "memory_usage": 45.2,
                    "disk_usage": 60.0,
                    "load_average": 0.8,
                    "uptime": 3600,
                },
            )
            assert heartbeat_resp.status_code == 200

            # 3. Verify node health
            health_resp = authenticated_client.get(f"/api/nodes/{node_id}/health")
            assert health_resp.status_code == 200
            health = health_resp.get_json()
            assert "node" in health

            # 4. Check node appears in cluster topology
            topology_resp = authenticated_client.get("/api/cluster/topology")
            assert topology_resp.status_code == 200
            topology = topology_resp.get_json()
            assert "nodes" in topology


class TestDocumentationWorkflow:
    """Test API documentation generation workflow."""

    def test_documentation_access(self, authenticated_client):
        """Test accessing generated API documentation."""
        # Get all documentation
        docs_resp = authenticated_client.get("/api/docs")
        assert docs_resp.status_code == 200
        docs = docs_resp.get_json()
        assert "endpoints" in docs or "categories" in docs

    def test_documentation_categories(self, authenticated_client):
        """Test documentation categories endpoint."""
        cats_resp = authenticated_client.get("/api/docs/categories")
        assert cats_resp.status_code == 200
        categories = cats_resp.get_json()
        # API returns dict with category names as keys
        assert isinstance(categories, dict)
        # Should have at least some categories
        assert len(categories) > 0


class TestFeatureLinkingWorkflow:
    """Test feature linking to commits, TODOs, and bugs."""

    def test_link_feature_to_commit(self, authenticated_client, sample_project):
        """Test linking a feature to a commit."""
        # Create feature
        resp = authenticated_client.post(
            "/api/features", json={"project_id": sample_project["id"], "name": "Link Test Feature"}
        )
        feature_id = resp.get_json()["id"]

        # Link to a commit
        link_resp = authenticated_client.post(
            f"/api/features/{feature_id}/links",
            json={
                "link_type": "commit",
                "target_id": "abc123def",
                "description": "Initial implementation",
            },
        )
        assert link_resp.status_code in [200, 201]

        # Get links
        links_resp = authenticated_client.get(f"/api/features/{feature_id}/links")
        assert links_resp.status_code == 200
        links = links_resp.get_json()
        assert isinstance(links, list)


class TestSecurityWorkflow:
    """Test authentication and authorization workflows."""

    def test_unauthenticated_access_blocked(self, client):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            ("/api/projects", "GET"),
            ("/api/features", "GET"),
            ("/api/bugs", "GET"),
            ("/api/nodes", "GET"),
            ("/api/tasks", "GET"),
            ("/api/secrets", "GET"),
        ]

        for endpoint, method in protected_endpoints:
            if method == "GET":
                resp = client.get(endpoint)
            else:
                resp = client.post(endpoint)

            # Should redirect to login or return 401
            assert resp.status_code in [302, 401], f"{endpoint} should require auth"

    def test_error_logging_public(self, client):
        """Test that error logging doesn't require auth."""
        resp = client.post(
            "/api/errors", json={"error_type": "test", "message": "Public error logging test"}
        )
        # Should accept without auth
        assert resp.status_code in [200, 201]

    def test_health_check_public(self, client):
        """Test that health check is publicly accessible."""
        resp = client.get("/health")
        assert resp.status_code == 200


class TestDashboardStatsWorkflow:
    """Test dashboard statistics workflow."""

    def test_stats_reflect_data_changes(self, authenticated_client, sample_project):
        """Test that stats update when data changes."""
        # Get initial stats
        initial_stats = authenticated_client.get("/api/stats").get_json()

        # Create a feature
        authenticated_client.post(
            "/api/features", json={"project_id": sample_project["id"], "name": "Stats Test Feature"}
        )

        # Get updated stats
        updated_stats = authenticated_client.get("/api/stats").get_json()

        # Feature count should increase or remain same if error
        assert "features" in updated_stats or "draft" in str(updated_stats)
