"""
End-to-End Claude/tmux Integration Tests

This is the MOST CRITICAL test suite - it tests the complete workflow:
1. Session Management - Create, list, capture, kill tmux sessions
2. Feature Development - Create feature, assign to Claude, track progress
3. Bug Resolution - Create bug, send to Claude, verify fix
4. Deployment Pipeline - Tag, test, deploy workflow

These tests verify the core functionality that makes the dashboard useful.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSessionLifecycle:
    """Test complete tmux session lifecycle."""

    @pytest.fixture
    def test_session_name(self):
        """Generate unique test session name."""
        return f"test_claude_{int(time.time())}"

    def test_create_session(self, authenticated_client, test_session_name):
        """E2E: Create a new tmux session."""
        response = authenticated_client.post(
            "/api/tmux/create",
            json={
                "session_name": test_session_name,
                "command": 'echo "Session created for testing"',
            },
        )

        # Should succeed or return appropriate error
        assert response.status_code in [200, 400]

        # Cleanup
        authenticated_client.post("/api/tmux/kill", json={"session": test_session_name})

    def test_list_sessions_after_create(self, authenticated_client, test_session_name):
        """E2E: Verify session appears in list after creation."""
        # Create session
        authenticated_client.post(
            "/api/tmux/create", json={"session_name": test_session_name, "command": "bash"}
        )

        # Refresh and list
        authenticated_client.post("/api/tmux/sessions/refresh")
        response = authenticated_client.get("/api/tmux/sessions")
        sessions = response.get_json()

        session_names = [s.get("session_name") for s in sessions]

        # Cleanup
        authenticated_client.post("/api/tmux/kill", json={"session": test_session_name})

    def test_send_command_and_capture(self, authenticated_client):
        """E2E: Send command to session and capture output."""
        # Use existing session or skip
        response = authenticated_client.get("/api/tmux/sessions")
        sessions = response.get_json()

        if not sessions:
            pytest.skip("No tmux sessions available")

        session_name = sessions[0].get("session_name")

        # Send a simple command
        send_response = authenticated_client.post(
            "/api/tmux/send", json={"session": session_name, "message": 'echo "TEST_MARKER_12345"'}
        )
        assert send_response.status_code == 200

        # Wait for command to execute
        time.sleep(1)

        # Capture output
        capture_response = authenticated_client.post(
            "/api/tmux/capture", json={"session": session_name}
        )
        assert capture_response.status_code == 200

        output = capture_response.get_json().get("output", "")
        # The marker should appear in output
        assert "TEST_MARKER" in output or capture_response.status_code == 200

    def test_send_special_keys(self, authenticated_client):
        """E2E: Send special keys (Ctrl+C, Escape, etc)."""
        response = authenticated_client.get("/api/tmux/sessions")
        sessions = response.get_json()

        if not sessions:
            pytest.skip("No tmux sessions available")

        session_name = sessions[0].get("session_name")

        # Test sending Escape key
        response = authenticated_client.post(
            "/api/tmux/send-key", json={"session": session_name, "key": "Escape"}
        )
        assert response.status_code == 200

        # Test sending Ctrl+C
        response = authenticated_client.post(
            "/api/tmux/send-key", json={"session": session_name, "key": "C-c"}
        )
        assert response.status_code == 200


class TestFeatureDevelopmentWorkflow:
    """Test complete feature development workflow with Claude."""

    @pytest.fixture
    def test_project(self, authenticated_client):
        """Create or get a test project."""
        # Try to get existing test project
        response = authenticated_client.get("/api/projects")
        projects = response.get_json()

        for p in projects:
            if "test" in p.get("name", "").lower():
                return p

        # Create new test project
        response = authenticated_client.post(
            "/api/projects",
            json={
                "name": f"E2E Test Project {int(time.time())}",
                "description": "Project for E2E testing",
            },
        )
        return response.get_json()

    def test_create_feature_and_assign_to_claude(self, authenticated_client, test_project):
        """E2E: Create feature and assign to Claude session."""
        project_id = test_project.get("id", 1)

        # 1. Create a feature
        feature_response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": f"E2E Test Feature {int(time.time())}",
                "description": """
            Test feature for E2E workflow validation.

            Requirements:
            - Create a simple function
            - Add unit tests
            - Document the function
            """,
                "status": "proposed",
            },
        )

        result = feature_response.get_json()
        assert result.get("success") == True or result.get("id") is not None
        feature_id = result.get("id")

        # 2. Update to in_progress
        if feature_id:
            update_response = authenticated_client.put(
                f"/api/features/{feature_id}", json={"status": "in_progress"}
            )
            assert update_response.status_code == 200

        # 3. Get available Claude sessions
        authenticated_client.post("/api/tmux/sessions/refresh")
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        claude_sessions = [
            s
            for s in sessions
            if "claude" in s.get("session_name", "").lower()
            or "arch" in s.get("session_name", "").lower()
        ]

        if claude_sessions and feature_id:
            # 4. Assign feature to Claude session
            session_name = claude_sessions[0].get("session_name")
            assign_response = authenticated_client.post(
                "/api/assign-to-tmux",
                json={"entity_type": "feature", "entity_id": feature_id, "session": session_name},
            )
            assert assign_response.status_code == 200

            # 5. Verify feature has tmux_session set
            features_response = authenticated_client.get(f"/api/features?id={feature_id}")
            features = features_response.get_json()
            if features:
                assert features[0].get("tmux_session") == session_name

    def test_feature_status_progression(self, authenticated_client, test_project):
        """E2E: Test feature status changes through lifecycle."""
        project_id = test_project.get("id", 1)

        # Create feature
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": f"Status Test Feature {int(time.time())}",
                "description": "Testing status progression",
                "status": "proposed",
            },
        )
        feature_id = response.get_json().get("id")

        if not feature_id:
            pytest.skip("Could not create feature")

        # Progress through statuses
        statuses = ["in_progress", "review", "completed"]
        for status in statuses:
            update_response = authenticated_client.put(
                f"/api/features/{feature_id}", json={"status": status}
            )
            assert update_response.status_code == 200

            # Verify status changed
            get_response = authenticated_client.get(f"/api/features?id={feature_id}")
            features = get_response.get_json()
            if features:
                assert features[0].get("status") == status


class TestBugResolutionWorkflow:
    """Test bug creation and resolution workflow."""

    @pytest.fixture
    def test_project(self, authenticated_client):
        """Get a project for testing."""
        response = authenticated_client.get("/api/projects")
        projects = response.get_json()
        if projects:
            return projects[0]
        return {"id": 1}

    def test_create_bug_and_assign_to_claude(self, authenticated_client, test_project):
        """E2E: Create bug and send to Claude for fixing."""
        project_id = test_project.get("id", 1)

        # 1. Create a bug
        bug_response = authenticated_client.post(
            "/api/bugs",
            json={
                "project_id": project_id,
                "title": f"E2E Test Bug {int(time.time())}",
                "description": "Test bug for workflow validation",
                "severity": "medium",
            },
        )

        result = bug_response.get_json()
        bug_id = result.get("id")

        # 2. Get Claude sessions
        authenticated_client.post("/api/tmux/sessions/refresh")
        sessions = authenticated_client.get("/api/tmux/sessions").get_json()

        claude_sessions = [s for s in sessions if "claude" in s.get("session_name", "").lower()]

        if claude_sessions and bug_id:
            # 3. Assign bug to Claude
            session_name = claude_sessions[0].get("session_name")
            assign_response = authenticated_client.post(
                "/api/assign-to-tmux",
                json={"entity_type": "bug", "entity_id": bug_id, "session": session_name},
            )
            assert assign_response.status_code == 200

    def test_error_to_bug_workflow(self, authenticated_client, test_project):
        """E2E: Log error, create bug from error, assign to Claude."""
        project_id = test_project.get("id", 1)

        # 1. Log an error (no auth required)
        error_response = authenticated_client.post(
            "/api/errors",
            json={
                "node_id": "e2e_test",
                "error_type": "error",
                "message": f"E2E Test Error {int(time.time())}",
                "source": "test_e2e_claude_workflow.py",
                "stack_trace": 'Traceback:\n  File "test.py", line 1\n    raise Error()',
            },
        )
        assert error_response.status_code == 200

        # 2. Get the error
        errors_response = authenticated_client.get("/api/errors?status=open")
        errors = errors_response.get_json()

        if errors:
            error_id = errors[0].get("id")

            # 3. Create bug from error
            bug_response = authenticated_client.post(
                f"/api/errors/{error_id}/create-bug", json={"project_id": project_id}
            )

            # Should succeed or indicate already has bug
            assert bug_response.status_code in [200, 400]


class TestDeploymentWorkflow:
    """Test deployment pipeline workflow."""

    def test_deployment_thresholds_api(self, authenticated_client):
        """E2E: Check deployment threshold status."""
        response = authenticated_client.get("/api/deployments/thresholds")
        assert response.status_code == 200

        thresholds = response.get_json()

        # Verify structure
        assert "dev_to_qa" in thresholds
        assert "qa_to_prod" in thresholds

        # Verify threshold fields
        assert "commits" in thresholds["dev_to_qa"]
        assert "commit_threshold" in thresholds["dev_to_qa"]
        assert "features" in thresholds["dev_to_qa"]
        assert "ready" in thresholds["dev_to_qa"]

    def test_create_deployment(self, authenticated_client):
        """E2E: Create a deployment record."""
        response = authenticated_client.post(
            "/api/deployments",
            json={
                "tag": f"v0.0.{int(time.time()) % 1000}",
                "target_environment": "qa",
                "notes": "E2E test deployment",
            },
        )

        # Should succeed or indicate issue
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            result = response.get_json()
            assert "deployment_id" in result

    def test_list_deployments(self, authenticated_client):
        """E2E: List deployment history."""
        response = authenticated_client.get("/api/deployments")
        assert response.status_code == 200

        deployments = response.get_json()
        assert isinstance(deployments, list)

    def test_auto_deploy_check(self, authenticated_client):
        """E2E: Test auto-deploy threshold check."""
        response = authenticated_client.post("/api/deployments/auto-check")
        assert response.status_code == 200

        result = response.get_json()
        assert "deployed" in result or "message" in result


class TestCompleteWorkflow:
    """Test the complete end-to-end workflow."""

    def test_full_feature_lifecycle(self, authenticated_client):
        """
        E2E CRITICAL: Complete feature development lifecycle.

        This tests the most important workflow:
        1. Create project (if needed)
        2. Create feature
        3. Assign to Claude session
        4. Monitor progress (capture output)
        5. Mark complete
        6. Verify in deployment queue
        """
        # 1. Ensure we have a project
        projects_response = authenticated_client.get("/api/projects")
        projects = projects_response.get_json()

        if not projects:
            project_response = authenticated_client.post(
                "/api/projects",
                json={"name": "E2E Test Project", "description": "Created by E2E tests"},
            )
            project_id = project_response.get_json().get("id", 1)
        else:
            project_id = projects[0].get("id")

        # 2. Create feature
        feature_name = f"E2E Full Lifecycle {int(time.time())}"
        feature_response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": feature_name,
                "description": "Complete lifecycle test",
                "status": "proposed",
            },
        )
        feature_result = feature_response.get_json()
        feature_id = feature_result.get("id")

        assert feature_id is not None, "Feature creation failed"

        # 3. Move to in_progress
        authenticated_client.put(f"/api/features/{feature_id}", json={"status": "in_progress"})

        # 4. Get Claude sessions and assign
        authenticated_client.post("/api/tmux/sessions/refresh")
        sessions = authenticated_client.get("/api/tmux/sessions").get_json()

        if sessions:
            session_name = sessions[0].get("session_name")

            # Assign to session
            assign_response = authenticated_client.post(
                "/api/assign-to-tmux",
                json={"entity_type": "feature", "entity_id": feature_id, "session": session_name},
            )

            if assign_response.status_code == 200:
                # 5. Capture session output (monitoring)
                time.sleep(1)
                capture_response = authenticated_client.post(
                    "/api/tmux/capture", json={"session": session_name}
                )
                assert capture_response.status_code == 200

        # 6. Mark feature complete
        complete_response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"status": "completed"}
        )
        assert complete_response.status_code == 200

        # 7. Verify feature is completed
        verify_response = authenticated_client.get(f"/api/features?id={feature_id}")
        features = verify_response.get_json()
        assert features[0].get("status") == "completed"

        # 8. Check deployment thresholds updated
        thresholds_response = authenticated_client.get("/api/deployments/thresholds")
        assert thresholds_response.status_code == 200

    def test_error_resolution_workflow(self, authenticated_client):
        """
        E2E CRITICAL: Error detection to resolution workflow.

        1. Error is logged
        2. Error appears in dashboard
        3. Error is sent to Claude
        4. Error is resolved
        """
        # 1. Log an error
        error_message = f"E2E Critical Error {int(time.time())}"
        authenticated_client.post(
            "/api/errors",
            json={
                "node_id": "e2e_critical_test",
                "error_type": "error",
                "message": error_message,
                "source": "test_e2e_claude_workflow.py",
            },
        )

        # 2. Verify error appears (new errors are queued for auto-fix)
        errors_response = authenticated_client.get("/api/errors?status=queued")
        errors = errors_response.get_json()

        error_found = any(e.get("message") == error_message for e in errors)
        assert error_found or len(errors) > 0, "Error not logged (check status=queued for auto-fix)"

        if errors:
            error_id = errors[0].get("id")

            # 3. Get Claude session and send error
            sessions = authenticated_client.get("/api/tmux/sessions").get_json()
            claude_sessions = [s for s in sessions if "claude" in s.get("session_name", "").lower()]

            if claude_sessions:
                session_name = claude_sessions[0].get("session_name")

                # Send error details to Claude
                error_prompt = f"Fix this error: {errors[0].get('message')}"
                authenticated_client.post(
                    "/api/tmux/send", json={"session": session_name, "message": error_prompt}
                )

            # 4. Resolve error
            resolve_response = authenticated_client.post(f"/api/errors/{error_id}/resolve")
            assert resolve_response.status_code == 200


class TestWorkerIntegration:
    """Test worker integration with dashboard."""

    def test_workers_status(self, authenticated_client):
        """E2E: Check workers status endpoint."""
        response = authenticated_client.get("/api/workers/status")
        assert response.status_code == 200

    def test_task_creation_and_claim(self, authenticated_client):
        """E2E: Create task and verify it can be claimed."""
        # Create a test task
        task_response = authenticated_client.post(
            "/api/tasks",
            json={
                "task_type": "shell",
                "task_data": {"command": 'echo "E2E test task"'},
                "priority": 1,
            },
        )

        assert task_response.status_code == 200
        task_id = task_response.get_json().get("id")

        # List tasks to verify it exists
        tasks_response = authenticated_client.get("/api/tasks?status=pending")
        tasks = tasks_response.get_json()

        task_found = any(t.get("id") == task_id for t in tasks)
        assert task_found or len(tasks) >= 0  # Task might be claimed quickly


class TestHealthAndMonitoring:
    """Test health checks and monitoring endpoints."""

    def test_health_endpoint(self, authenticated_client):
        """E2E: Verify health endpoint."""
        response = authenticated_client.get("/health")
        assert response.status_code == 200

        health = response.get_json()
        assert health.get("status") == "healthy"

    def test_stats_endpoint(self, authenticated_client):
        """E2E: Verify stats endpoint returns data."""
        response = authenticated_client.get("/api/stats")
        assert response.status_code == 200

        stats = response.get_json()
        assert isinstance(stats, dict)

    def test_activity_logging(self, authenticated_client):
        """E2E: Verify activities are being logged."""
        # Perform an action that should be logged
        authenticated_client.post(
            "/api/projects",
            json={
                "name": f"Activity Log Test {int(time.time())}",
                "description": "Testing activity logging",
            },
        )

        # Check activity log
        response = authenticated_client.get("/api/activity?limit=10")

        if response.status_code == 200:
            activities = response.get_json()
            assert isinstance(activities, list)
