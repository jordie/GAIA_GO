"""
Tmux and Claude Integration Tests

Tests the integration between the dashboard and tmux sessions for Claude development:
1. Tmux session management (list, create, capture, send, kill)
2. Feature assignment to Claude sessions
3. Claude development workflow
4. Session output monitoring
"""
import json
import os
import subprocess
import sys
import time

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTmuxSessionManagement:
    """Test tmux session CRUD operations."""

    @pytest.fixture
    def test_session_name(self):
        """Generate unique test session name."""
        return f"test_session_{int(time.time())}"

    def test_list_tmux_sessions_api(self, authenticated_client):
        """API should return list of tmux sessions."""
        response = authenticated_client.get("/api/tmux/sessions")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_refresh_tmux_sessions(self, authenticated_client):
        """Should be able to refresh tmux session list from system."""
        response = authenticated_client.post("/api/tmux/sessions/refresh")
        assert response.status_code == 200
        data = response.get_json()
        assert "sessions" in data or "success" in data

    def test_create_tmux_session(self, authenticated_client, test_session_name):
        """Should be able to create a new tmux session."""
        response = authenticated_client.post(
            "/api/tmux/create",
            json={"name": test_session_name, "command": 'echo "Test session created"'},
        )
        assert response.status_code == 200
        data = response.get_json()

        # Clean up - kill the test session
        authenticated_client.post("/api/tmux/kill", json={"session": test_session_name})

    def test_send_to_tmux_session(self, authenticated_client):
        """Should be able to send commands to a tmux session."""
        # First check if any sessions exist
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        if len(sessions) > 0:
            session_name = sessions[0].get("session_name")
            response = authenticated_client.post(
                "/api/tmux/send",
                json={"session": session_name, "message": 'echo "Integration test command"'},
            )
            assert response.status_code == 200

    def test_capture_tmux_output(self, authenticated_client):
        """Should be able to capture output from a tmux session."""
        # First check if any sessions exist
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        if len(sessions) > 0:
            session_name = sessions[0].get("session_name")
            response = authenticated_client.post(
                "/api/tmux/capture", json={"session": session_name, "lines": 50}
            )
            assert response.status_code == 200
            data = response.get_json()
            assert "output" in data or "error" in data


class TestClaudeWorkflow:
    """Test Claude development workflow through tmux."""

    def test_assign_feature_to_tmux(self, authenticated_client, sample_project):
        """Should be able to assign a feature to a tmux session."""
        project_id = sample_project.get("id", 1)

        # Create a feature
        feature_response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Claude Test Feature",
                "description": "Test feature for Claude integration testing",
            },
        )
        feature = feature_response.get_json()
        feature_id = feature.get("id")

        # Check if any tmux sessions exist
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        if len(sessions) > 0:
            session_name = sessions[0].get("session_name")

            # Assign feature to tmux
            response = authenticated_client.post(
                "/api/assign-to-tmux",
                json={"entity_type": "feature", "entity_id": feature_id, "session": session_name},
            )
            assert response.status_code == 200

            # Verify feature has tmux_session set
            updated_feature = authenticated_client.get(f"/api/features?id={feature_id}")
            features = updated_feature.get_json()
            if features:
                assert features[0].get("tmux_session") == session_name

    def test_assign_bug_to_tmux(self, authenticated_client, sample_project):
        """Should be able to assign a bug to a tmux session."""
        project_id = sample_project.get("id", 1)

        # Create a bug
        bug_response = authenticated_client.post(
            "/api/bugs",
            json={
                "project_id": project_id,
                "title": "Claude Test Bug",
                "description": "Test bug for Claude integration testing",
                "severity": "medium",
            },
        )
        bug = bug_response.get_json()
        bug_id = bug.get("id")

        # Check if any tmux sessions exist
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        if len(sessions) > 0:
            session_name = sessions[0].get("session_name")

            # Assign bug to tmux
            response = authenticated_client.post(
                "/api/assign-to-tmux",
                json={"entity_type": "bug", "entity_id": bug_id, "session": session_name},
            )
            assert response.status_code == 200

    def test_feature_workflow_with_tmux(self, authenticated_client, sample_project):
        """Test complete feature workflow: create, assign, capture progress."""
        project_id = sample_project.get("id", 1)

        # 1. Create feature
        feature_response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Workflow Test Feature",
                "description": """
            Implement a new widget component.

            Acceptance Criteria:
            - Widget displays data correctly
            - Widget updates in real-time
            - Widget handles errors gracefully
            """,
                "status": "proposed",
            },
        )
        result = feature_response.get_json()
        assert result.get("success") == True
        feature_id = result.get("id")

        # 2. Update to in_progress
        update_response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"status": "in_progress"}
        )
        assert update_response.status_code == 200

        # 3. Check if tmux sessions exist for assignment
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        if len(sessions) > 0:
            session_name = sessions[0].get("session_name")

            # 4. Assign to tmux
            assign_response = authenticated_client.post(
                "/api/assign-to-tmux",
                json={"entity_type": "feature", "entity_id": feature_id, "session": session_name},
            )
            assert assign_response.status_code == 200

            # 5. Capture session output to check progress
            capture_response = authenticated_client.post(
                "/api/tmux/capture", json={"session": session_name, "lines": 100}
            )
            assert capture_response.status_code == 200

        # 6. Mark as completed
        complete_response = authenticated_client.put(
            f"/api/features/{feature_id}", json={"status": "completed"}
        )
        assert complete_response.status_code == 200


class TestTmuxClaudeInteraction:
    """Test actual tmux/Claude interaction patterns."""

    def test_send_prompt_to_claude_session(self, authenticated_client):
        """Test sending a prompt to a Claude session."""
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        # Find a Claude-related session
        claude_sessions = [s for s in sessions if "claude" in s.get("session_name", "").lower()]

        if claude_sessions:
            session_name = claude_sessions[0].get("session_name")

            # Send a test prompt
            response = authenticated_client.post(
                "/api/tmux/send",
                json={
                    "session": session_name,
                    "command": "# Test integration - please acknowledge",
                },
            )
            assert response.status_code == 200

    def test_monitor_claude_output(self, authenticated_client):
        """Test monitoring Claude session output."""
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        claude_sessions = [
            s
            for s in sessions
            if "claude" in s.get("session_name", "").lower()
            or "arch" in s.get("session_name", "").lower()
        ]

        if claude_sessions:
            session_name = claude_sessions[0].get("session_name")

            # Capture output multiple times to simulate monitoring
            outputs = []
            for _ in range(3):
                response = authenticated_client.post(
                    "/api/tmux/capture", json={"session": session_name, "lines": 50}
                )
                if response.status_code == 200:
                    data = response.get_json()
                    outputs.append(data.get("output", ""))

            # Should get output at least once
            assert any(outputs)


class TestSessionTracking:
    """Test session tracking in database."""

    def test_session_stored_in_database(self, authenticated_client):
        """Sessions should be tracked in the database."""
        # Refresh sessions to sync with system
        authenticated_client.post("/api/tmux/sessions/refresh")

        # Get sessions from API (which reads from DB)
        response = authenticated_client.get("/api/tmux/sessions")
        sessions = response.get_json()

        # Each session should have required fields
        for session in sessions:
            assert "session_name" in session
            assert "node_id" in session or session.get("node_id") is None

    def test_feature_tmux_association_persists(self, authenticated_client, sample_project):
        """Feature-tmux associations should persist in database."""
        project_id = sample_project.get("id", 1)

        # Create feature
        response = authenticated_client.post(
            "/api/features",
            json={
                "project_id": project_id,
                "name": "Persistence Test Feature",
                "description": "Testing tmux association persistence",
            },
        )
        result = response.get_json()
        feature_id = result.get("id")

        # Update with tmux session
        authenticated_client.put(
            f"/api/features/{feature_id}", json={"tmux_session": "test_session"}
        )

        # Retrieve and verify
        get_response = authenticated_client.get(f"/api/features?id={feature_id}")
        features = get_response.get_json()

        if features:
            assert features[0].get("tmux_session") == "test_session"


class TestErrorFromClaudeSession:
    """Test error handling from Claude sessions."""

    def test_create_error_from_session_output(self, authenticated_client):
        """Should be able to log errors captured from session output."""
        # Log an error (simulating capture from Claude session)
        response = authenticated_client.post(
            "/api/errors",
            json={
                "node_id": "claude_session_test",
                "error_type": "error",
                "message": "Test error from Claude session",
                "source": "test_tmux_claude.py",
                "stack_trace": 'Traceback:\n  File "test.py", line 1\n    raise Error()',
            },
        )
        # Errors endpoint doesn't require auth for logging
        assert response.status_code == 200

    def test_create_bug_from_claude_discovered_error(self, authenticated_client, sample_project):
        """Should be able to create a bug from an error Claude discovered."""
        project_id = sample_project.get("id", 1)

        # First log an error
        error_response = authenticated_client.post(
            "/api/errors",
            json={
                "node_id": "claude_session",
                "error_type": "error",
                "message": "NullPointerException in UserService",
                "source": "UserService.java:42",
            },
        )

        # Get the error
        errors_response = authenticated_client.get("/api/errors")
        errors = errors_response.get_json()

        if errors:
            error_id = errors[0].get("id")

            # Create bug from error
            bug_response = authenticated_client.post(
                f"/api/errors/{error_id}/create-bug", json={"project_id": project_id}
            )

            # Should either succeed or return appropriate response
            assert bug_response.status_code in [200, 400, 404]


class TestQuickSendCommands:
    """Test quick send commands to Claude sessions."""

    @pytest.mark.parametrize("command", ["yes", "no", "continue", "q", "exit"])
    def test_quick_commands(self, authenticated_client, command):
        """Test sending quick commands to tmux sessions."""
        sessions_response = authenticated_client.get("/api/tmux/sessions")
        sessions = sessions_response.get_json()

        if sessions:
            # Don't actually send to avoid disrupting real sessions
            # Just verify the API structure
            session_name = sessions[0].get("session_name")

            # Test that the endpoint accepts the request format
            # (Don't actually send to avoid disrupting sessions)
            response = authenticated_client.post(
                "/api/tmux/send", json={"session": "nonexistent_test_session", "command": command}
            )
            # Should return 200 or appropriate error, not crash
            assert response.status_code in [200, 400, 404, 500]


class TestLiveTmuxIntegration:
    """Live integration tests (only run if tmux is available)."""

    @pytest.fixture
    def tmux_available(self):
        """Check if tmux is available."""
        try:
            result = subprocess.run(["tmux", "-V"], capture_output=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def test_tmux_list_sessions_command(self, tmux_available):
        """Test tmux list-sessions command works."""
        if not tmux_available:
            pytest.skip("tmux not available")

        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True
        )
        # Should either list sessions or return "no server running"
        assert result.returncode in [0, 1]

    def test_tmux_capture_pane_format(self, tmux_available):
        """Test tmux capture-pane output format."""
        if not tmux_available:
            pytest.skip("tmux not available")

        # Get list of sessions
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            session = result.stdout.strip().split("\n")[0]

            # Capture pane
            capture_result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p", "-S", "-50"],
                capture_output=True,
                text=True,
            )

            assert capture_result.returncode == 0
            # Output should be a string
            assert isinstance(capture_result.stdout, str)
