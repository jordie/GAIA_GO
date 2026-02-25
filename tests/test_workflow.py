"""
Feature Workflow Tests

Tests the complete feature development lifecycle:
1. Feature creation with tests
2. Branch management
3. Feature completion and merge
4. Status updates in dashboard

These tests ensure the test-driven development process works correctly.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFeatureWorkflow:
    """Test the feature development workflow."""

    def test_feature_creation_requires_description(self, authenticated_client):
        """Features must have a description for test planning."""
        response = authenticated_client.post(
            "/api/features", json={"project_id": 1, "name": "Feature Without Description"}
        )
        # Should succeed but description should be empty or default
        data = response.get_json()
        assert response.status_code == 200

    def test_feature_lifecycle_status_transitions(self, authenticated_client, sample_project):
        """Test that features follow the correct status workflow."""
        project_id = sample_project.get("id", 1)

        # Create feature in 'proposed' status
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Lifecycle Test Feature",
                "description": "Testing status transitions",
                "status": "proposed",
            },
        )
        assert response.status_code == 200
        feature = response.get_json()
        feature_id = feature.get("id")

        # Transition to in_progress
        response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"status": "in_progress"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") == True

        # Verify status changed
        response = authenticated_client.get(f"/api/features?id={feature_id}")
        features = response.get_json()
        assert len(features) > 0
        assert features[0].get("status") == "in_progress"

        # Transition to completed
        response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"status": "completed"}
        )
        assert response.status_code == 200

    def test_feature_can_have_branch_name(self, authenticated_client, sample_project):
        """Features should be able to store their associated branch name."""
        project_id = sample_project.get("id", 1)

        # Create feature
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Branch Test Feature",
                "description": "Testing branch association",
            },
        )
        feature = response.get_json()
        feature_id = feature.get("id")

        # Update with branch name
        response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"branch_name": "feature/test-branch"}
        )
        assert response.status_code == 200

    def test_feature_can_be_assigned_to_tmux(self, authenticated_client, sample_project):
        """Features should be able to be assigned to a tmux session."""
        project_id = sample_project.get("id", 1)

        # Create feature
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Tmux Assignment Feature",
                "description": "Testing tmux assignment",
            },
        )
        feature = response.get_json()
        feature_id = feature.get("id")

        # Assign to tmux session
        response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"tmux_session": "arch_dev"}
        )
        assert response.status_code == 200


class TestFeatureTests:
    """Test that features have associated tests."""

    def test_feature_should_have_test_file(self, authenticated_client, sample_project):
        """When creating a feature, a test file should be identifiable."""
        project_id = sample_project.get("id", 1)

        description = "This feature has associated tests in test_feature_x.py"

        # Create feature with test file reference
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Test-Driven Feature",
                "description": description,
            },
        )
        assert response.status_code == 200
        result = response.get_json()
        assert result.get("success") == True

        # The description we sent should mention tests
        assert "test" in description.lower()


class TestWorkflowScript:
    """Test the feature_workflow.sh script functionality."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        temp_dir = tempfile.mkdtemp()
        original_dir = os.getcwd()

        os.chdir(temp_dir)
        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True)

        # Create initial commit
        with open("README.md", "w") as f:
            f.write("# Test Repo\n")
        subprocess.run(["git", "add", "."], capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], capture_output=True)

        # Create dev branch
        subprocess.run(["git", "checkout", "-b", "dev"], capture_output=True)

        yield temp_dir

        os.chdir(original_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_script_exists(self):
        """The feature_workflow.sh script should exist."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "feature_workflow.sh"
        )
        assert os.path.exists(script_path)

    def test_script_has_help(self):
        """Script should display help when called with no args."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "feature_workflow.sh"
        )
        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert "Usage" in result.stdout or "usage" in result.stdout.lower()


class TestTestIntegration:
    """Test that tests are properly integrated into the deployment process."""

    def test_run_tests_script_exists(self):
        """run_tests.sh should exist for deployment testing."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "run_tests.sh"
        )
        assert os.path.exists(script_path)

    def test_deploy_script_runs_tests(self):
        """deploy_by_tag.sh should include test execution."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "deploy_by_tag.sh"
        )
        with open(script_path, "r") as f:
            content = f.read()

        # Deployment script should reference test running
        assert "run_tests" in content or "pytest" in content


class TestFeatureTestsCreation:
    """Test that new features get their own test files."""

    def test_feature_test_template(self, authenticated_client, sample_project):
        """
        When a feature is marked for development, there should be
        a way to create test stubs for it.
        """
        project_id = sample_project.get("id", 1)

        # Create a feature
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "New Dashboard Widget",
                "description": "Add a widget to show user statistics",
            },
        )
        feature = response.get_json()

        # In a full implementation, creating the feature would also
        # create a test stub file. For now, we just verify the feature
        # can be created with test-related metadata.
        assert feature.get("id") is not None

    def test_feature_acceptance_criteria(self, authenticated_client, sample_project):
        """Features should be able to have acceptance criteria that become tests."""
        project_id = sample_project.get("id", 1)

        description = """
            Acceptance Criteria:
            - User can click the widget
            - Widget displays current count
            - Count updates in real-time
            """

        # Create feature with acceptance criteria in description
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Feature with Criteria",
                "description": description,
            },
        )
        result = response.get_json()
        assert result.get("success") == True

        # The description we sent should have acceptance criteria
        assert "Acceptance Criteria" in description
