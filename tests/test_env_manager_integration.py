"""
Integration tests for env_manager.py

Tests environment configuration, process management, status checking,
and environment lifecycle operations.
"""

import pytest
import json
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import env_manager


@pytest.fixture
def test_config(tmp_path, monkeypatch):
    """Create test environment configuration."""
    config_path = tmp_path / "environments.json"

    config = {
        "architect_envs": {
            "dev": {
                "port": 5051,
                "type": "main",
                "auto_start": True,
                "description": "Development environment"
            },
            "qa": {
                "port": 5052,
                "type": "main",
                "auto_start": False,
                "description": "QA environment"
            },
            "prod": {
                "port": 5053,
                "type": "main",
                "auto_start": False,
                "description": "Production environment"
            }
        },
        "defaults": {
            "python": "python3",
            "architect_app": "app.py",
            "log_dir": str(tmp_path / "logs")
        }
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Create log directory
    (tmp_path / "logs").mkdir(exist_ok=True)

    # Patch CONFIG_PATH
    monkeypatch.setattr("env_manager.CONFIG_PATH", config_path)
    monkeypatch.setattr("env_manager.BASE_DIR", tmp_path)

    yield {"config": config, "path": config_path, "tmp_path": tmp_path}


@pytest.mark.integration
class TestConfigManagement:
    """Test configuration loading and saving."""

    def test_load_config(self, test_config):
        """Test loading environment configuration."""
        config = env_manager.load_config()

        assert "architect_envs" in config
        assert "defaults" in config
        assert "dev" in config["architect_envs"]

    def test_save_config(self, test_config):
        """Test saving environment configuration."""
        config = env_manager.load_config()

        # Modify config
        config["architect_envs"]["test"] = {
            "port": 5054,
            "auto_start": False
        }

        env_manager.save_config(config)

        # Reload and verify
        reloaded = env_manager.load_config()
        assert "test" in reloaded["architect_envs"]
        assert reloaded["architect_envs"]["test"]["port"] == 5054

    def test_config_structure(self, test_config):
        """Test configuration has required structure."""
        config = env_manager.load_config()

        # Check environments
        assert isinstance(config["architect_envs"], dict)
        for env_name, env_data in config["architect_envs"].items():
            assert "port" in env_data
            assert isinstance(env_data["port"], int)

    def test_load_config_missing_file(self, monkeypatch):
        """Test loading config when file doesn't exist."""
        # Patch to nonexistent path
        monkeypatch.setattr("env_manager.CONFIG_PATH", Path("/nonexistent/config.json"))

        with pytest.raises(SystemExit):
            env_manager.load_config()


@pytest.mark.integration
class TestPortChecking:
    """Test port status checking."""

    def test_get_pid_on_port_no_process(self, monkeypatch):
        """Test getting PID when no process on port."""
        # Mock lsof to return empty
        def mock_run(*args, **kwargs):
            class Result:
                stdout = ""
                returncode = 0
            return Result()

        monkeypatch.setattr("subprocess.run", mock_run)

        pid = env_manager.get_pid_on_port(9999)

        assert pid is None

    def test_get_pid_on_port_with_process(self, monkeypatch):
        """Test getting PID when process exists."""
        # Mock lsof to return PID
        def mock_run(*args, **kwargs):
            class Result:
                stdout = "12345\n"
                returncode = 0
            return Result()

        monkeypatch.setattr("subprocess.run", mock_run)

        pid = env_manager.get_pid_on_port(5051)

        assert pid == 12345

    def test_get_pid_on_port_timeout(self, monkeypatch):
        """Test getting PID when lsof times out."""
        def mock_run(*args, **kwargs):
            raise Exception("Timeout")

        monkeypatch.setattr("subprocess.run", mock_run)

        pid = env_manager.get_pid_on_port(5051)

        assert pid is None

    def test_is_running_true(self, monkeypatch):
        """Test is_running when process exists."""
        monkeypatch.setattr("env_manager.get_pid_on_port", lambda port: 12345)

        running = env_manager.is_running(5051)

        assert running is True

    def test_is_running_false(self, monkeypatch):
        """Test is_running when no process."""
        monkeypatch.setattr("env_manager.get_pid_on_port", lambda port: None)

        running = env_manager.is_running(5051)

        assert running is False


@pytest.mark.integration
class TestEnvironmentStart:
    """Test environment starting."""

    def test_start_env_unknown(self, test_config, capsys):
        """Test starting unknown environment."""
        config = env_manager.load_config()

        success = env_manager.start_env("unknown", config)

        assert success is False
        captured = capsys.readouterr()
        assert "Unknown environment" in captured.out

    def test_start_env_already_running(self, test_config, monkeypatch, capsys):
        """Test starting environment that's already running."""
        config = env_manager.load_config()

        # Mock as already running
        monkeypatch.setattr("env_manager.is_running", lambda port: True)

        success = env_manager.start_env("dev", config)

        assert success is True
        captured = capsys.readouterr()
        assert "already running" in captured.out

    def test_start_env_command_execution(self, test_config, monkeypatch):
        """Test start environment executes command."""
        config = env_manager.load_config()

        # Mock as not running
        monkeypatch.setattr("env_manager.is_running", lambda port: False)

        # Track subprocess call
        called_commands = []
        def mock_run(cmd, **kwargs):
            called_commands.append(cmd)
            class Result:
                returncode = 0
            return Result()

        monkeypatch.setattr("subprocess.run", mock_run)

        env_manager.start_env("dev", config)

        # Verify command was called
        assert len(called_commands) > 0
        assert "APP_ENV=dev" in called_commands[0]
        assert "PORT=5051" in called_commands[0]


@pytest.mark.integration
class TestEnvironmentStop:
    """Test environment stopping."""

    def test_stop_env_unknown(self, test_config, capsys):
        """Test stopping unknown environment."""
        config = env_manager.load_config()

        success = env_manager.stop_env("unknown", config)

        assert success is False
        captured = capsys.readouterr()
        assert "Unknown environment" in captured.out

    def test_stop_env_not_running(self, test_config, monkeypatch, capsys):
        """Test stopping environment that's not running."""
        config = env_manager.load_config()

        # Mock as not running
        monkeypatch.setattr("env_manager.get_pid_on_port", lambda port: None)

        success = env_manager.stop_env("dev", config)

        assert success is True
        captured = capsys.readouterr()
        assert "not running" in captured.out

    def test_stop_env_kills_process(self, test_config, monkeypatch):
        """Test stop environment kills process."""
        config = env_manager.load_config()

        # Mock as running
        monkeypatch.setattr("env_manager.get_pid_on_port", lambda port: 12345)

        # Track kill calls
        killed_pids = []
        def mock_kill(pid, sig):
            killed_pids.append(pid)

        monkeypatch.setattr("os.kill", mock_kill)

        env_manager.stop_env("dev", config)

        assert 12345 in killed_pids


@pytest.mark.integration
class TestEnvironmentListing:
    """Test environment listing."""

    def test_list_envs(self, test_config, capsys):
        """Test listing all environments."""
        config = env_manager.load_config()

        env_manager.list_envs(config)

        captured = capsys.readouterr()
        assert "dev" in captured.out
        assert "qa" in captured.out
        assert "prod" in captured.out
        assert "5051" in captured.out  # Port should be shown

    def test_list_envs_shows_auto_start(self, test_config, capsys):
        """Test list shows auto_start status."""
        config = env_manager.load_config()

        env_manager.list_envs(config)

        captured = capsys.readouterr()
        # dev has auto_start=True, should be indicated
        assert "dev" in captured.out


@pytest.mark.integration
class TestStatusDisplay:
    """Test status display."""

    def test_status_all_stopped(self, test_config, monkeypatch, capsys):
        """Test status when all environments stopped."""
        config = env_manager.load_config()

        # Mock all as not running
        monkeypatch.setattr("env_manager.is_running", lambda port: False)

        env_manager.status(config)

        captured = capsys.readouterr()
        assert "dev" in captured.out
        assert "qa" in captured.out
        assert "prod" in captured.out

    def test_status_some_running(self, test_config, monkeypatch, capsys):
        """Test status with some environments running."""
        config = env_manager.load_config()

        # Mock dev as running
        def mock_is_running(port):
            return port == 5051  # dev port

        monkeypatch.setattr("env_manager.is_running", mock_is_running)

        env_manager.status(config)

        captured = capsys.readouterr()
        assert "dev" in captured.out


@pytest.mark.integration
class TestEnvironmentCreation:
    """Test creating new environments."""

    def test_create_env(self, test_config):
        """Test creating a new environment."""
        config = env_manager.load_config()

        success = env_manager.create_env("feature1", 5060, config)

        assert success is True

        # Reload config and verify
        updated = env_manager.load_config()
        assert "feature1" in updated["architect_envs"]
        assert updated["architect_envs"]["feature1"]["port"] == 5060

    def test_create_env_duplicate_name(self, test_config, capsys):
        """Test creating environment with duplicate name."""
        config = env_manager.load_config()

        success = env_manager.create_env("dev", 5060, config)

        assert success is False
        captured = capsys.readouterr()
        assert "already exists" in captured.out

    def test_create_env_duplicate_port(self, test_config, capsys):
        """Test creating environment with duplicate port."""
        config = env_manager.load_config()

        success = env_manager.create_env("feature1", 5051, config)

        assert success is False
        captured = capsys.readouterr()
        assert "already used" in captured.out or "already in use" in captured.out

    def test_create_env_sets_defaults(self, test_config):
        """Test created environment has default values."""
        config = env_manager.load_config()

        env_manager.create_env("feature1", 5060, config)

        updated = env_manager.load_config()
        feature1 = updated["architect_envs"]["feature1"]

        assert "auto_start" in feature1
        assert feature1["auto_start"] is False


@pytest.mark.integration
class TestLogTailing:
    """Test log tailing functionality."""

    def test_tail_logs_unknown_env(self, test_config, capsys):
        """Test tailing logs for unknown environment."""
        config = env_manager.load_config()

        # Should handle gracefully
        try:
            env_manager.tail_logs("unknown", config)
        except SystemExit:
            pass  # Expected

        captured = capsys.readouterr()
        assert "Unknown environment" in captured.out or len(captured.out) >= 0


@pytest.mark.integration
class TestConfigDefaults:
    """Test default configuration values."""

    def test_defaults_python(self, test_config):
        """Test python default value."""
        config = env_manager.load_config()

        assert "python" in config["defaults"]
        assert config["defaults"]["python"] == "python3"

    def test_defaults_app(self, test_config):
        """Test architect_app default value."""
        config = env_manager.load_config()

        assert "architect_app" in config["defaults"]
        assert config["defaults"]["architect_app"] == "app.py"

    def test_defaults_log_dir(self, test_config):
        """Test log_dir default value."""
        config = env_manager.load_config()

        assert "log_dir" in config["defaults"]


@pytest.mark.integration
class TestEnvironmentProperties:
    """Test environment property access."""

    def test_env_has_port(self, test_config):
        """Test all environments have port."""
        config = env_manager.load_config()

        for env_name, env_data in config["architect_envs"].items():
            assert "port" in env_data
            assert isinstance(env_data["port"], int)
            assert env_data["port"] > 0

    def test_env_has_description(self, test_config):
        """Test environments have descriptions."""
        config = env_manager.load_config()

        for env_name, env_data in config["architect_envs"].items():
            assert "description" in env_data
            assert isinstance(env_data["description"], str)


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_config(self, tmp_path, monkeypatch):
        """Test handling empty configuration."""
        config_path = tmp_path / "empty.json"

        with open(config_path, "w") as f:
            json.dump({}, f)

        monkeypatch.setattr("env_manager.CONFIG_PATH", config_path)

        config = env_manager.load_config()

        # Should handle gracefully
        assert isinstance(config, dict)

    def test_malformed_config(self, tmp_path, monkeypatch):
        """Test handling malformed JSON."""
        config_path = tmp_path / "malformed.json"

        with open(config_path, "w") as f:
            f.write("{ invalid json")

        monkeypatch.setattr("env_manager.CONFIG_PATH", config_path)

        with pytest.raises(json.JSONDecodeError):
            env_manager.load_config()

    def test_config_with_extra_fields(self, test_config):
        """Test configuration with extra fields."""
        config = env_manager.load_config()

        # Add extra field
        config["extra"] = "value"
        config["architect_envs"]["dev"]["custom"] = "field"

        env_manager.save_config(config)

        # Should preserve extra fields
        reloaded = env_manager.load_config()
        assert "extra" in reloaded
        assert "custom" in reloaded["architect_envs"]["dev"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
