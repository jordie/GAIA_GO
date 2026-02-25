"""
Integration tests for workers/task_worker.py

Tests background task worker including task claiming, processing,
various task handlers, state management, and graceful shutdown.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """Create test environment for task worker."""
    # Create test directories
    pid_file = tmp_path / "worker.pid"
    state_file = tmp_path / "worker_state.json"
    log_file = tmp_path / "worker.log"

    # Patch file paths
    monkeypatch.setattr("workers.task_worker.PID_FILE", pid_file)
    monkeypatch.setattr("workers.task_worker.STATE_FILE", state_file)
    monkeypatch.setattr("workers.task_worker.LOG_FILE", log_file)

    # Mock graceful shutdown to avoid signal handlers
    mock_shutdown = MagicMock()
    mock_shutdown.register = MagicMock()
    mock_shutdown.phase = "running"

    # Import after patching
    import workers.task_worker as tw

    # Mock get_connection to avoid database access
    mock_conn = MagicMock()
    mock_conn_context = MagicMock()
    mock_conn_context.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn_context.__exit__ = MagicMock(return_value=None)

    def mock_get_connection():
        return mock_conn_context

    monkeypatch.setattr("workers.task_worker.get_connection", mock_get_connection)

    # Mock GracefulShutdown class
    def mock_graceful_shutdown(*args, **kwargs):
        return mock_shutdown

    monkeypatch.setattr("workers.task_worker.GracefulShutdown", mock_graceful_shutdown)

    yield {
        "tmp_path": tmp_path,
        "pid_file": pid_file,
        "state_file": state_file,
        "log_file": log_file,
        "module": tw,
        "mock_shutdown": mock_shutdown,
        "mock_conn": mock_conn,
    }


@pytest.mark.integration
class TestWorkerInitialization:
    """Test worker initialization and configuration."""

    def test_create_worker_default_config(self, test_env):
        """Test creating worker with default configuration."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        assert worker.worker_id is not None
        assert worker.node_id == "local"
        assert worker.worker_type == "general"
        assert worker.poll_interval == 5
        assert worker.heartbeat_interval == 30
        assert worker._running is False
        assert worker._current_task is None
        assert worker._tasks_completed == 0
        assert worker._tasks_failed == 0

    def test_create_worker_custom_config(self, test_env):
        """Test creating worker with custom configuration."""
        tw = test_env["module"]

        worker = tw.TaskWorker(
            worker_id="test-worker-123",
            node_id="node-1",
            worker_type="deploy",
            poll_interval=10,
            heartbeat_interval=60,
        )

        assert worker.worker_id == "test-worker-123"
        assert worker.node_id == "node-1"
        assert worker.worker_type == "deploy"
        assert worker.poll_interval == 10
        assert worker.heartbeat_interval == 60

    def test_worker_has_default_handlers(self, test_env):
        """Test worker has default task handlers registered."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        # Check default handlers
        assert "shell" in worker._handlers
        assert "python" in worker._handlers
        assert "git" in worker._handlers
        assert "deploy" in worker._handlers
        assert "test" in worker._handlers
        assert "build" in worker._handlers
        assert "tmux" in worker._handlers

    def test_register_custom_handler(self, test_env):
        """Test registering custom task handler."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        def custom_handler(data):
            return {"result": "custom"}

        worker.register_handler("custom", custom_handler)

        assert "custom" in worker._handlers
        assert worker._handlers["custom"] == custom_handler


@pytest.mark.integration
class TestStateManagement:
    """Test worker state persistence."""

    def test_save_state(self, test_env):
        """Test saving worker state to file."""
        tw = test_env["module"]

        worker = tw.TaskWorker(worker_id="test-123")
        worker._start_time = tw.datetime.now()
        worker._tasks_completed = 5
        worker._tasks_failed = 1
        worker._running = True

        worker._save_state()

        # Verify state file exists
        assert test_env["state_file"].exists()

        # Verify state content
        state = json.loads(test_env["state_file"].read_text())
        assert state["worker_id"] == "test-123"
        assert state["tasks_completed"] == 5
        assert state["tasks_failed"] == 1
        assert state["running"] is True

    def test_state_includes_current_task(self, test_env):
        """Test state includes current task info."""
        tw = test_env["module"]

        worker = tw.TaskWorker()
        worker._start_time = tw.datetime.now()
        worker._current_task = {"id": "task-123", "task_type": "shell"}

        worker._save_state()

        state = json.loads(test_env["state_file"].read_text())
        assert state["current_task"] is not None
        assert state["current_task"]["id"] == "task-123"


@pytest.mark.integration
class TestTaskHandlerShell:
    """Test shell task handler."""

    def test_handle_shell_task_success(self, test_env):
        """Test executing successful shell command."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        data = {"command": "echo 'Hello World'"}

        result = worker._handle_shell_task(data)

        assert result["returncode"] == 0
        assert "Hello World" in result["stdout"]

    def test_handle_shell_task_failure(self, test_env):
        """Test executing failing shell command."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        data = {"command": "exit 1"}

        result = worker._handle_shell_task(data)

        assert result["returncode"] == 1

    def test_handle_shell_task_no_command(self, test_env):
        """Test shell handler with missing command."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        data = {}

        with pytest.raises(ValueError, match="No command specified"):
            worker._handle_shell_task(data)

    def test_handle_shell_task_with_cwd(self, test_env):
        """Test shell command with working directory."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        data = {"command": "pwd", "cwd": str(test_env["tmp_path"])}

        result = worker._handle_shell_task(data)

        assert result["returncode"] == 0
        assert str(test_env["tmp_path"]) in result["stdout"]


@pytest.mark.integration
class TestTaskHandlerPython:
    """Test Python task handler."""

    def test_handle_python_code(self, test_env):
        """Test executing Python code."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        data = {"code": "print('Hello from Python')"}

        result = worker._handle_python_task(data)

        assert result["returncode"] == 0
        assert "Hello from Python" in result["stdout"]

    def test_handle_python_script(self, test_env):
        """Test executing Python script."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        # Create test script
        script_path = test_env["tmp_path"] / "test_script.py"
        script_path.write_text("print('Script executed')")

        data = {"script": str(script_path)}

        result = worker._handle_python_task(data)

        assert result["returncode"] == 0
        assert "Script executed" in result["stdout"]

    def test_handle_python_no_script_or_code(self, test_env):
        """Test Python handler with missing script/code."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        data = {}

        with pytest.raises(ValueError, match="No script or code specified"):
            worker._handle_python_task(data)


@pytest.mark.integration
class TestTaskHandlerGit:
    """Test Git task handler."""

    def test_handle_git_status(self, test_env):
        """Test git status operation."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        # Use current repo
        data = {"operation": "status", "repo_path": str(Path.cwd())}

        result = worker._handle_git_task(data)

        # Status should succeed
        assert result["returncode"] == 0

    def test_handle_git_unknown_operation(self, test_env):
        """Test git handler with unknown operation."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        data = {"operation": "unknown", "repo_path": str(Path.cwd())}

        with pytest.raises(ValueError, match="Unknown git operation"):
            worker._handle_git_task(data)


@pytest.mark.integration
class TestTaskHandlerTest:
    """Test test task handler."""

    def test_handle_test_task_success(self, test_env):
        """Test running successful tests."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        # Use echo as a simple test that succeeds
        data = {"command": "echo 'Tests passed'", "path": ""}

        result = worker._handle_test_task(data)

        assert result["returncode"] == 0
        assert result["passed"] is True
        assert "Tests passed" in result["stdout"]

    def test_handle_test_task_failure(self, test_env):
        """Test running failing tests."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        # Use false command to simulate test failure
        data = {"command": "false", "path": ""}

        result = worker._handle_test_task(data)

        assert result["returncode"] != 0
        assert result["passed"] is False


@pytest.mark.integration
class TestTaskHandlerBuild:
    """Test build task handler."""

    def test_handle_build_task(self, test_env):
        """Test running build command."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        # Use echo as simple build command
        data = {"command": "echo 'Build successful'"}

        result = worker._handle_build_task(data)

        assert result["returncode"] == 0
        assert "Build successful" in result["stdout"]


@pytest.mark.integration
class TestTaskCompletion:
    """Test task completion and failure handling."""

    @patch("requests.post")
    def test_complete_task(self, mock_post, test_env):
        """Test completing a task."""
        tw = test_env["module"]

        # Make requests fail to trigger DB fallback
        mock_post.side_effect = Exception("API unavailable")

        worker = tw.TaskWorker()

        task_id = "task-123"
        result = {"status": "success"}

        worker._complete_task(task_id, result)

        # Verify database update was called (fallback)
        test_env["mock_conn"].execute.assert_called()

    @patch("requests.post")
    def test_fail_task(self, mock_post, test_env):
        """Test failing a task."""
        tw = test_env["module"]

        # Make requests fail to trigger DB fallback
        mock_post.side_effect = Exception("API unavailable")

        worker = tw.TaskWorker()

        task_id = "task-456"
        error = "Task failed due to timeout"

        worker._fail_task(task_id, error)

        # Verify database update was called (fallback)
        test_env["mock_conn"].execute.assert_called()


@pytest.mark.integration
class TestTaskProcessing:
    """Test task processing flow."""

    def test_process_task_success(self, test_env):
        """Test successfully processing a task."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        task = {
            "id": "task-789",
            "task_type": "shell",
            "task_data": json.dumps({"command": "echo 'Success'"}),
        }

        success = worker._process_task(task)

        assert success is True
        assert worker._tasks_completed == 1
        assert worker._tasks_failed == 0
        assert worker._current_task is None  # Should be cleared

    @patch("requests.post")
    def test_process_task_unknown_type(self, mock_post, test_env):
        """Test processing task with unknown type."""
        tw = test_env["module"]

        # Make requests fail to trigger DB fallback
        mock_post.side_effect = Exception("API unavailable")

        worker = tw.TaskWorker()

        task = {
            "id": "task-unknown",
            "task_type": "nonexistent",
            "task_data": json.dumps({}),
        }

        success = worker._process_task(task)

        # Unknown handler returns False but doesn't increment _tasks_failed
        # (that's only incremented on handler exceptions)
        assert success is False

    def test_process_task_handler_exception(self, test_env):
        """Test processing task when handler throws exception."""
        tw = test_env["module"]

        worker = tw.TaskWorker()

        # Register handler that raises
        def failing_handler(data):
            raise Exception("Handler failed")

        worker.register_handler("failing", failing_handler)

        task = {
            "id": "task-fail",
            "task_type": "failing",
            "task_data": json.dumps({}),
        }

        success = worker._process_task(task)

        assert success is False
        assert worker._tasks_failed == 1


@pytest.mark.integration
class TestWorkerRegistration:
    """Test worker registration with dashboard."""

    @patch("requests.post")
    def test_register_with_server_success(self, mock_post, test_env):
        """Test successful registration with server."""
        tw = test_env["module"]

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        worker = tw.TaskWorker(worker_id="test-123")

        result = worker._register_with_server()

        assert result is True
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_register_with_server_failure(self, mock_post, test_env):
        """Test failed registration with server."""
        tw = test_env["module"]

        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        worker = tw.TaskWorker()

        result = worker._register_with_server()

        assert result is False


@pytest.mark.integration
class TestHeartbeat:
    """Test heartbeat mechanism."""

    @patch("requests.post")
    def test_send_heartbeat_idle(self, mock_post, test_env):
        """Test sending heartbeat when idle."""
        tw = test_env["module"]

        worker = tw.TaskWorker(worker_id="test-123")
        worker._tasks_completed = 5
        worker._tasks_failed = 1

        worker._send_heartbeat()

        # Verify heartbeat was sent
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "heartbeat" in call_args[0][0]

        # Verify payload
        payload = call_args[1]["json"]
        assert payload["status"] == "idle"
        assert payload["tasks_completed"] == 5
        assert payload["tasks_failed"] == 1

    @patch("requests.post")
    def test_send_heartbeat_busy(self, mock_post, test_env):
        """Test sending heartbeat when busy."""
        tw = test_env["module"]

        worker = tw.TaskWorker()
        worker._current_task = {"id": "task-123"}

        worker._send_heartbeat()

        # Verify status is busy
        payload = mock_post.call_args[1]["json"]
        assert payload["status"] == "busy"
        assert payload["current_task_id"] == "task-123"


@pytest.mark.integration
class TestGracefulShutdown:
    """Test graceful shutdown integration."""

    def test_on_shutdown_callback(self, test_env):
        """Test shutdown callback sets running to False."""
        tw = test_env["module"]

        worker = tw.TaskWorker()
        worker._running = True

        worker._on_shutdown()

        assert worker._running is False

    def test_on_cleanup_saves_state(self, test_env):
        """Test cleanup callback saves state."""
        tw = test_env["module"]

        worker = tw.TaskWorker()
        worker._start_time = tw.datetime.now()

        worker._on_cleanup()

        # Verify state file created
        assert test_env["state_file"].exists()


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("requests.post")
    def test_process_task_with_empty_data(self, mock_post, test_env):
        """Test processing task with empty task_data."""
        tw = test_env["module"]

        # Make requests fail to trigger DB fallback
        mock_post.side_effect = Exception("API unavailable")

        worker = tw.TaskWorker()

        # Use valid JSON but empty dict - shell handler will fail due to missing command
        task = {"id": "task-empty", "task_type": "shell", "task_data": "{}"}

        # Shell handler will fail due to missing command
        success = worker._process_task(task)

        assert success is False

    def test_state_file_survives_multiple_saves(self, test_env):
        """Test state file can be saved multiple times."""
        tw = test_env["module"]

        worker = tw.TaskWorker()
        worker._start_time = tw.datetime.now()

        # Save multiple times
        for i in range(5):
            worker._tasks_completed = i
            worker._save_state()

            state = json.loads(test_env["state_file"].read_text())
            assert state["tasks_completed"] == i


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
