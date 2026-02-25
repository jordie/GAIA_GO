"""
Integration tests for workers/deploy_worker.py

Tests automated CI/CD pipeline, deployment state management, git operations,
server management, and cluster deployment.
"""

import json
import sys
from pathlib import Path

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """Create test environment for deploy worker."""
    # Create test directories
    state_file = tmp_path / "deploy_state.json"
    pid_file = tmp_path / "deploy_worker.pid"
    banner_file = tmp_path / "deployment_banner.json"

    # Patch paths
    monkeypatch.setattr("workers.deploy_worker.BASE_DIR", tmp_path)
    monkeypatch.setattr("workers.deploy_worker.STATE_FILE", state_file)
    monkeypatch.setattr("workers.deploy_worker.PID_FILE", pid_file)

    # Import after patching
    import workers.deploy_worker as dw

    # Mock run_cmd to avoid actual git/server operations
    def mock_run_cmd(cmd, timeout=None):
        """Mock command execution."""
        if "git rev-parse" in cmd:
            return (True, "abc123def456", "")
        elif "git describe" in cmd:
            return (True, "v1.0.5", "")
        elif "git tag" in cmd:
            return (True, "v1.0.5\nv1.0.4\nv1.0.3", "")
        elif "git fetch" in cmd:
            return (True, "", "")
        elif "git checkout" in cmd:
            return (True, "", "")
        elif "lsof" in cmd:
            return (True, "12345", "")
        elif "curl" in cmd:
            return (True, "ok", "")
        elif "ssh" in cmd and "echo ok" in cmd:
            return (True, "ok", "")
        else:
            return (True, "", "")

    monkeypatch.setattr("workers.deploy_worker.run_cmd", mock_run_cmd)

    yield {
        "base_dir": tmp_path,
        "state_file": state_file,
        "pid_file": pid_file,
        "banner_file": banner_file,
        "module": dw,
    }


@pytest.mark.integration
class TestStateManagement:
    """Test deployment state persistence."""

    def test_load_default_state(self, test_env):
        """Test loading default state when file doesn't exist."""
        dw = test_env["module"]

        state = dw.load_state()

        assert "last_commit" in state
        assert "last_tag" in state
        assert "deployments" in state
        assert "active_deployment" in state
        assert isinstance(state["last_commit"], dict)
        assert isinstance(state["deployments"], list)

    def test_save_and_load_state(self, test_env):
        """Test saving and loading state."""
        dw = test_env["module"]

        state = dw.load_state()
        state["last_commit"]["dev"] = "abc123"
        state["last_tag"]["qa"] = "v1.0.5"
        dw.save_state(state)

        # Reload
        new_state = dw.load_state()
        assert new_state["last_commit"]["dev"] == "abc123"
        assert new_state["last_tag"]["qa"] == "v1.0.5"

    def test_state_file_created(self, test_env):
        """Test state file is created on save."""
        dw = test_env["module"]

        state = dw.load_state()
        dw.save_state(state)

        assert test_env["state_file"].exists()
        content = json.loads(test_env["state_file"].read_text())
        assert "deployments" in content


@pytest.mark.integration
class TestGitOperations:
    """Test git-related operations."""

    def test_get_current_commit(self, test_env):
        """Test getting current commit hash."""
        dw = test_env["module"]

        commit = dw.get_current_commit()

        assert commit is not None
        assert len(commit) > 0
        # Mock returns abc123def456
        assert commit == "abc123def456"

    def test_get_latest_tag(self, test_env):
        """Test getting latest tag."""
        dw = test_env["module"]

        tag = dw.get_latest_tag()

        assert tag is not None
        # Mock returns v1.0.5
        assert tag == "v1.0.5"

    def test_get_all_tags(self, test_env):
        """Test getting all tags."""
        dw = test_env["module"]

        tags = dw.get_all_tags()

        assert isinstance(tags, list)
        assert len(tags) > 0
        # Mock returns multiple tags
        assert "v1.0.5" in tags


@pytest.mark.integration
class TestDeploymentBanner:
    """Test deployment banner management."""

    def test_set_deployment_banner(self, test_env):
        """Test setting deployment banner."""
        dw = test_env["module"]

        dw.set_deployment_banner("dev", "Deploying v1.0.5", "deploying")

        # Check state
        state = dw.load_state()
        assert state["active_deployment"] is not None
        assert state["active_deployment"]["environment"] == "dev"
        assert state["active_deployment"]["message"] == "Deploying v1.0.5"
        assert state["active_deployment"]["status"] == "deploying"

        # Check banner file
        banner_file = test_env["base_dir"] / "deployment_banner.json"
        assert banner_file.exists()
        banner = json.loads(banner_file.read_text())
        assert banner["environment"] == "dev"

    def test_clear_deployment_banner(self, test_env):
        """Test clearing deployment banner."""
        dw = test_env["module"]

        # Set banner first
        dw.set_deployment_banner("dev", "Test", "deploying")

        # Clear it
        dw.clear_deployment_banner()

        # Verify cleared
        state = dw.load_state()
        assert state["active_deployment"] is None

        banner_file = test_env["base_dir"] / "deployment_banner.json"
        assert not banner_file.exists()

    def test_update_deployment_progress(self, test_env):
        """Test updating deployment progress."""
        dw = test_env["module"]

        # Set banner first
        dw.set_deployment_banner("dev", "Deploying", "deploying")

        # Update progress
        dw.update_deployment_progress(50, "Running migrations...")

        state = dw.load_state()
        assert state["active_deployment"]["progress"] == 50
        assert state["active_deployment"]["message"] == "Running migrations..."


@pytest.mark.integration
class TestServerManagement:
    """Test server management operations."""

    def test_restart_server_unknown_env(self, test_env):
        """Test restarting server with unknown environment."""
        dw = test_env["module"]

        result = dw.restart_server("unknown")

        assert result is False

    def test_restart_server_valid_env(self, test_env):
        """Test restarting server with valid environment."""
        dw = test_env["module"]

        # Mock returns PID, so should succeed
        result = dw.restart_server("dev")

        assert result is True


@pytest.mark.integration
class TestDeployment:
    """Test main deployment flow."""

    def test_deploy_to_unknown_env(self, test_env):
        """Test deploying to unknown environment."""
        dw = test_env["module"]

        result = dw.deploy_to_env("unknown")

        assert result is False

    def test_deploy_to_dev(self, test_env, monkeypatch):
        """Test deploying to dev environment."""
        dw = test_env["module"]

        # Disable cluster deployment for simplicity
        monkeypatch.setattr("workers.deploy_worker.CLUSTER_DEPLOY_ENABLED", False)

        result = dw.deploy_to_env("dev")

        assert result is True

        # Check state updated
        state = dw.load_state()
        assert "dev" in state["last_commit"]
        assert len(state["deployments"]) > 0

        # Check latest deployment
        latest = state["deployments"][-1]
        assert latest["environment"] == "dev"
        assert latest["status"] == "success"

    def test_deploy_with_version(self, test_env, monkeypatch):
        """Test deploying with specific version."""
        dw = test_env["module"]

        monkeypatch.setattr("workers.deploy_worker.CLUSTER_DEPLOY_ENABLED", False)

        result = dw.deploy_to_env("qa", version="v1.0.5")

        assert result is True

        state = dw.load_state()
        assert state["last_tag"].get("qa") == "v1.0.5"

    def test_deploy_sets_banner(self, test_env, monkeypatch):
        """Test deployment sets and clears banner."""
        dw = test_env["module"]

        monkeypatch.setattr("workers.deploy_worker.CLUSTER_DEPLOY_ENABLED", False)
        # Speed up test by reducing sleep
        import time

        original_sleep = time.sleep
        monkeypatch.setattr("time.sleep", lambda s: original_sleep(0.1))

        # Deploy
        dw.deploy_to_env("dev")

        # Banner should be cleared (after short delay in deploy_to_env)
        state = dw.load_state()
        assert state["active_deployment"] is None

    def test_deploy_failure_handling(self, test_env, monkeypatch):
        """Test deployment failure is handled gracefully."""
        dw = test_env["module"]

        # Make git checkout fail
        def failing_run_cmd(cmd, timeout=None):
            if "git checkout" in cmd:
                return (False, "", "checkout failed")
            return (True, "", "")

        monkeypatch.setattr("workers.deploy_worker.run_cmd", failing_run_cmd)

        result = dw.deploy_to_env("dev")

        assert result is False


@pytest.mark.integration
class TestClusterOperations:
    """Test cluster deployment operations."""

    def test_get_nodes_for_environment(self, test_env, monkeypatch):
        """Test getting cluster nodes for environment."""
        dw = test_env["module"]

        # Enable cluster deployment
        monkeypatch.setattr("workers.deploy_worker.CLUSTER_DEPLOY_ENABLED", True)

        # Mock cluster nodes
        mock_nodes = {
            "node1": {"enabled": True, "environments": ["dev", "qa"]},
            "node2": {"enabled": True, "environments": ["prod"]},
        }
        monkeypatch.setattr("workers.deploy_worker.CLUSTER_NODES", mock_nodes)

        nodes = dw.get_nodes_for_environment("dev")

        assert "node1" in nodes
        assert "node2" not in nodes

    def test_get_nodes_disabled_cluster(self, test_env, monkeypatch):
        """Test getting nodes when cluster disabled."""
        dw = test_env["module"]

        monkeypatch.setattr("workers.deploy_worker.CLUSTER_DEPLOY_ENABLED", False)

        nodes = dw.get_nodes_for_environment("dev")

        assert nodes == []

    def test_check_node_reachable(self, test_env):
        """Test checking node reachability."""
        dw = test_env["module"]

        node = {"ssh": "user@host", "host": "192.168.1.100", "port": 5051}

        # Mock returns "ok", so should be reachable
        result = dw.check_node_reachable("node1", node)

        assert result is True

    def test_check_node_unreachable(self, test_env, monkeypatch):
        """Test checking unreachable node."""
        dw = test_env["module"]

        # Make ssh fail
        def failing_run_cmd(cmd, timeout=None):
            if "ssh" in cmd and "echo ok" in cmd:
                return (False, "", "connection refused")
            return (True, "", "")

        monkeypatch.setattr("workers.deploy_worker.run_cmd", failing_run_cmd)

        node = {"ssh": "user@host", "host": "192.168.1.100", "port": 5051}
        result = dw.check_node_reachable("node1", node)

        assert result is False


@pytest.mark.integration
class TestDeploymentDetection:
    """Test deployment detection logic."""

    def test_check_for_deployments_no_changes(self, test_env):
        """Test checking for deployments when no changes."""
        dw = test_env["module"]

        # Set current state to match
        state = dw.load_state()
        state["last_commit"]["dev"] = "abc123def456"
        state["last_tag"]["qa"] = "v1.0.5"
        dw.save_state(state)

        # Should not trigger deployment (returns None)
        dw.check_for_deployments()

        # State unchanged
        new_state = dw.load_state()
        assert len(new_state["deployments"]) == 0


@pytest.mark.integration
class TestConfigurationHandling:
    """Test configuration and environment handling."""

    def test_environments_config_exists(self, test_env):
        """Test ENVIRONMENTS config is defined."""
        dw = test_env["module"]

        assert hasattr(dw, "ENVIRONMENTS")
        assert "dev" in dw.ENVIRONMENTS
        assert "qa" in dw.ENVIRONMENTS
        assert "prod" in dw.ENVIRONMENTS

    def test_environment_has_required_fields(self, test_env):
        """Test environment configs have required fields."""
        dw = test_env["module"]

        for env_name, env in dw.ENVIRONMENTS.items():
            assert "port" in env
            assert "trigger" in env
            assert isinstance(env["port"], int)

            # Tag pattern required for tag-based deployments
            if env.get("trigger") == "tag":
                assert "tag_pattern" in env


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_load_corrupted_state(self, test_env):
        """Test loading corrupted state file."""
        dw = test_env["module"]

        # Write invalid JSON
        test_env["state_file"].write_text("{ invalid json")

        # Should return default state
        state = dw.load_state()

        assert "deployments" in state
        assert isinstance(state["deployments"], list)

    def test_update_progress_no_active_deployment(self, test_env):
        """Test updating progress when no active deployment."""
        dw = test_env["module"]

        # Should not crash
        dw.update_deployment_progress(50, "Test")

        # State should still be clean
        state = dw.load_state()
        assert state.get("active_deployment") is None

    def test_multiple_deployments_logged(self, test_env, monkeypatch):
        """Test multiple deployments are logged."""
        dw = test_env["module"]

        monkeypatch.setattr("workers.deploy_worker.CLUSTER_DEPLOY_ENABLED", False)

        # Deploy multiple times
        dw.deploy_to_env("dev")
        dw.deploy_to_env("dev")

        state = dw.load_state()
        assert len(state["deployments"]) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
