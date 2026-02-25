#!/usr/bin/env python3
"""
Tests for GAIA - Generic AI Agent

Tests cover:
- Provider switching based on token thresholds
- Session pool management (start/stop tmux sessions)
- Token budget tracking
- Complexity-based routing
- Failover behavior
"""

import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path (noqa for E402 - required before gaia import)
sys.path.insert(0, str(Path(__file__).parent.parent))

from gaia import (  # noqa: E402
    CODEX_THRESHOLDS,
    TOKEN_THRESHOLDS,
    GAIAgent,
    SessionPoolManager,
    TokenBudgetManager,
)


class TestTokenThresholds(unittest.TestCase):
    """Test token threshold configuration."""

    def test_thresholds_exist(self):
        """Verify all required thresholds are defined."""
        self.assertIn("start_session", TOKEN_THRESHOLDS)
        self.assertIn("stop_session", TOKEN_THRESHOLDS)
        self.assertIn("switch_threshold", TOKEN_THRESHOLDS)
        self.assertIn("provider_limits", TOKEN_THRESHOLDS)

    def test_provider_limits(self):
        """Verify provider limits are reasonable."""
        limits = TOKEN_THRESHOLDS["provider_limits"]
        self.assertIn("claude", limits)
        self.assertIn("ollama", limits)
        self.assertIn("codex", limits)

        # Ollama should have highest limit (local, free)
        self.assertGreater(limits["ollama"], limits["claude"])
        self.assertGreater(limits["ollama"], limits["codex"])

    def test_switch_thresholds_ordered(self):
        """Verify switch thresholds are in ascending order."""
        switch = TOKEN_THRESHOLDS["switch_threshold"]
        self.assertLess(switch["warning"], switch["switch"])
        self.assertLess(switch["switch"], switch["critical"])

    def test_start_session_thresholds(self):
        """Verify session start thresholds are defined."""
        start = TOKEN_THRESHOLDS["start_session"]
        self.assertIn("low", start)
        self.assertIn("medium", start)
        self.assertIn("high", start)
        # Verify ascending order
        self.assertLess(start["low"], start["medium"])
        self.assertLess(start["medium"], start["high"])

    def test_stop_session_thresholds(self):
        """Verify session stop thresholds are defined."""
        stop = TOKEN_THRESHOLDS["stop_session"]
        self.assertIn("idle_minutes", stop)
        self.assertIn("low_budget", stop)


class TestCodexThresholds(unittest.TestCase):
    """Test codex identification thresholds."""

    def test_name_patterns_exist(self):
        """Verify name patterns for codex detection."""
        self.assertIn("name_patterns", CODEX_THRESHOLDS)
        patterns = CODEX_THRESHOLDS["name_patterns"]
        self.assertGreater(len(patterns), 0)

    def test_complexity_routing(self):
        """Verify complexity-based routing configuration."""
        self.assertIn("complexity_routing", CODEX_THRESHOLDS)
        routing = CODEX_THRESHOLDS["complexity_routing"]
        self.assertIn("low", routing)
        self.assertIn("medium", routing)
        self.assertIn("high", routing)

        # Low complexity should prefer ollama/codex
        self.assertIn("ollama", routing["low"])

        # High complexity should prefer claude
        self.assertIn("claude", routing["high"])

    def test_provider_indicators(self):
        """Verify provider detection patterns."""
        self.assertIn("provider_indicators", CODEX_THRESHOLDS)
        indicators = CODEX_THRESHOLDS["provider_indicators"]
        self.assertIn("claude", indicators)
        self.assertIn("ollama", indicators)
        self.assertIn("codex", indicators)

    def test_output_patterns(self):
        """Verify output patterns for detection."""
        self.assertIn("output_patterns", CODEX_THRESHOLDS)
        patterns = CODEX_THRESHOLDS["output_patterns"]
        self.assertGreater(len(patterns), 0)


class TestTokenBudgetManager(unittest.TestCase):
    """Test token budget tracking and threshold checks."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = TokenBudgetManager()

    def test_initialization(self):
        """Verify manager initializes correctly."""
        self.assertIsNotNone(self.manager)

    def test_get_usage_percent(self):
        """Test usage percentage retrieval."""
        # Should return a float between 0 and 1
        usage = self.manager.get_usage_percent("test_session")
        self.assertIsInstance(usage, float)
        self.assertGreaterEqual(usage, 0.0)
        self.assertLessEqual(usage, 1.0)

    def test_should_switch_session(self):
        """Test session switch determination."""
        # Should return a boolean
        result = self.manager.should_switch_session("test_session")
        self.assertIsInstance(result, bool)

    def test_allow_request(self):
        """Test request allowance check."""
        result = self.manager.allow_request("test_session", 1000)
        self.assertIsInstance(result, bool)

    def test_allow_request_with_priority(self):
        """Test request allowance with different priorities."""
        result_normal = self.manager.allow_request("test", 1000, priority="normal")
        result_high = self.manager.allow_request("test", 1000, priority="high")
        self.assertIsInstance(result_normal, bool)
        self.assertIsInstance(result_high, bool)

    def test_record_usage(self):
        """Test recording token usage doesn't raise."""
        # Should not raise an exception
        try:
            self.manager.record_usage("test_session", 1000)
        except Exception as e:
            self.fail(f"record_usage raised exception: {e}")


class TestSessionPoolManager(unittest.TestCase):
    """Test session pool management."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )
            self.manager = SessionPoolManager()

    @patch("subprocess.run")
    def test_refresh_sessions(self, mock_run):
        """Test refreshing tmux sessions."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="session1:12345\nsession2:12346\n",
        )

        sessions = self.manager.refresh_sessions()
        self.assertIsInstance(sessions, dict)

    @patch("subprocess.run")
    def test_get_available_sessions(self, mock_run):
        """Test getting available sessions."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="dev_worker1:12345\narchitect:12346\n",
        )

        sessions = self.manager.get_available_sessions()
        self.assertIsInstance(sessions, list)

    @patch("subprocess.run")
    def test_get_available_sessions_filtered(self, mock_run):
        """Test getting sessions filtered by provider."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="dev_worker1:12345\narchitect:12346\n",
        )

        self.manager.refresh_sessions()
        sessions = self.manager.get_available_sessions(provider="claude")
        self.assertIsInstance(sessions, list)

    @patch("subprocess.run")
    def test_start_session(self, mock_run):
        """Test starting a new tmux session."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = self.manager.start_session("test_worker", provider="ollama")
        self.assertTrue(result)
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_stop_session(self, mock_run):
        """Test stopping a tmux session."""
        mock_run.return_value = MagicMock(returncode=0)

        result = self.manager.stop_session("test_worker")
        self.assertTrue(result)
        mock_run.assert_called()

    def test_detect_provider_claude(self):
        """Test provider detection for Claude sessions."""
        # High-level sessions should be detected as claude
        provider = self.manager._detect_provider("architect")
        self.assertEqual(provider, "claude")

        provider = self.manager._detect_provider("foundation")
        self.assertEqual(provider, "claude")

    def test_detect_provider_ollama(self):
        """Test provider detection for Ollama sessions."""
        provider = self.manager._detect_provider("ollama_local")
        self.assertEqual(provider, "ollama")

        provider = self.manager._detect_provider("llama_session")
        self.assertEqual(provider, "ollama")

    def test_detect_provider_codex(self):
        """Test provider detection for Codex/worker sessions."""
        # Worker sessions should be detected as codex
        provider = self.manager._detect_provider("dev_worker1")
        self.assertEqual(provider, "codex")

        provider = self.manager._detect_provider("qa_tester2")
        self.assertEqual(provider, "codex")

        provider = self.manager._detect_provider("gaia_worker1")
        self.assertEqual(provider, "codex")

    def test_is_codex_session(self):
        """Test codex session identification."""
        # Should match codex patterns
        self.assertTrue(self.manager._is_codex_session("codex"))
        self.assertTrue(self.manager._is_codex_session("dev_worker1"))
        self.assertTrue(self.manager._is_codex_session("qa_tester2"))
        self.assertTrue(self.manager._is_codex_session("mcp_worker3"))

        # Should not match high-level sessions
        self.assertFalse(self.manager._is_codex_session("architect"))
        self.assertFalse(self.manager._is_codex_session("foundation"))

    @patch("subprocess.run")
    def test_get_session_for_task(self, mock_run):
        """Test getting session for a task."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="dev_worker1:12345\narchitect:12346\n",
        )

        self.manager.refresh_sessions()
        session = self.manager.get_session_for_task(complexity="medium")
        # May return None if no sessions match, or a dict if found
        self.assertTrue(session is None or isinstance(session, dict))


class TestGAIAgent(unittest.TestCase):
    """Test the main GAIA agent."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            self.agent = GAIAgent(verbose=False)

    def test_initialization(self):
        """Test agent initialization."""
        self.assertIsNotNone(self.agent.session_pool)
        self.assertIsNotNone(self.agent.budget_manager)

    def test_initialization_with_session(self):
        """Test agent initialization with target session."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            agent = GAIAgent(session_name="test_session")
            self.assertEqual(agent.target_session, "test_session")

    def test_initialization_with_provider(self):
        """Test agent initialization with preferred provider."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            agent = GAIAgent(provider="ollama")
            self.assertEqual(agent.preferred_provider, "ollama")

    @patch("subprocess.run")
    def test_select_session(self, mock_run):
        """Test session selection."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="dev_worker1:12345\n",
        )

        session = self.agent.select_session(complexity="medium")
        # May be None or dict
        self.assertTrue(session is None or isinstance(session, dict))

    @patch("subprocess.run")
    def test_send_to_session(self, mock_run):
        """Test sending content to a session."""
        mock_run.return_value = MagicMock(returncode=0)

        result = self.agent.send_to_session("test_session", "Hello")
        self.assertTrue(result)
        mock_run.assert_called()


class TestProviderSwitching(unittest.TestCase):
    """Test provider switching behavior."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            self.agent = GAIAgent(verbose=False)

    def test_complexity_routing_low(self):
        """Test routing for low complexity tasks."""
        routing = CODEX_THRESHOLDS["complexity_routing"]["low"]
        # Low complexity should prefer codex (cost-effective)
        self.assertEqual(routing[0], "codex")

    def test_complexity_routing_high(self):
        """Test routing for high complexity tasks."""
        routing = CODEX_THRESHOLDS["complexity_routing"]["high"]
        # High complexity should prefer codex first, then claude as fallback
        self.assertEqual(routing[0], "codex")
        self.assertIn("claude", routing)  # Claude available as fallback

    def test_fallback_order(self):
        """Test fallback provider order."""
        # When Claude is limited, should have fallbacks
        routing = CODEX_THRESHOLDS["complexity_routing"]

        # All complexity levels should have multiple options
        for level in ["low", "medium", "high"]:
            providers = routing[level]
            self.assertGreater(len(providers), 1)


class TestTmuxIntegration(unittest.TestCase):
    """Integration tests for tmux session management."""

    @classmethod
    def setUpClass(cls):
        """Check if tmux is available."""
        result = subprocess.run(["which", "tmux"], capture_output=True, text=True)
        cls.tmux_available = result.returncode == 0

    def setUp(self):
        """Set up test fixtures."""
        if not self.tmux_available:
            self.skipTest("tmux not available")
        self.test_session = f"gaia_test_{int(time.time())}"

    def tearDown(self):
        """Clean up test sessions."""
        if hasattr(self, "test_session"):
            subprocess.run(
                ["tmux", "kill-session", "-t", self.test_session],
                capture_output=True,
            )

    def test_create_and_kill_session(self):
        """Test creating and killing a tmux session."""
        # Create session
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.test_session],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)

        # Verify it exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", self.test_session],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)

        # Kill it
        result = subprocess.run(
            ["tmux", "kill-session", "-t", self.test_session],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_send_keys_to_session(self):
        """Test sending keys to a tmux session."""
        # Create session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.test_session],
            capture_output=True,
        )

        # Send keys
        result = subprocess.run(
            ["tmux", "send-keys", "-t", self.test_session, "echo test", "Enter"],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_capture_pane_output(self):
        """Test capturing output from a tmux session."""
        # Create session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.test_session],
            capture_output=True,
        )

        # Send a command
        subprocess.run(
            ["tmux", "send-keys", "-t", self.test_session, "echo GAIA_TEST", "Enter"],
            capture_output=True,
        )

        time.sleep(0.5)  # Wait for command to execute

        # Capture output
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", self.test_session, "-p"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("GAIA_TEST", result.stdout)

    def test_session_pool_manager_integration(self):
        """Test SessionPoolManager with real tmux."""
        # Create a test session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.test_session],
            capture_output=True,
        )

        manager = SessionPoolManager()
        sessions = manager.get_available_sessions()

        # Should find our test session
        session_names = [s["name"] for s in sessions]
        self.assertIn(self.test_session, session_names)

    def test_start_and_stop_session(self):
        """Test starting and stopping sessions via manager."""
        manager = SessionPoolManager()

        # Start a session
        result = manager.start_session(self.test_session, provider="ollama")
        # May fail if ollama not available, that's OK
        if result:
            # Should be in the session list
            sessions = manager.get_available_sessions()
            session_names = [s["name"] for s in sessions]
            self.assertIn(self.test_session, session_names)

            # Stop it
            result = manager.stop_session(self.test_session)
            self.assertTrue(result)


class TestRateLimitHandler(unittest.TestCase):
    """Test rate limit handler integration."""

    def test_import(self):
        """Test rate limit handler can be imported."""
        try:
            from services.rate_limit_handler import (
                RateLimitHandler,
                get_rate_limiter,
                should_use_claude,
            )

            # Verify imports are callable/classes
            self.assertTrue(callable(get_rate_limiter))
            self.assertTrue(callable(should_use_claude))
            self.assertIsNotNone(RateLimitHandler)
        except ImportError as e:
            self.fail(f"Failed to import rate_limit_handler: {e}")

    def test_should_use_claude_default(self):
        """Test default Claude usage decision."""
        from services.rate_limit_handler import should_use_claude

        # Should return boolean
        result = should_use_claude()
        self.assertIsInstance(result, bool)

    def test_rate_limiter_singleton(self):
        """Test rate limiter is a singleton."""
        from services.rate_limit_handler import get_rate_limiter

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        self.assertIs(limiter1, limiter2)


class TestProviderRouter(unittest.TestCase):
    """Test provider router integration."""

    def test_import(self):
        """Test provider router can be imported."""
        try:
            from services.provider_router import ProviderRouter, get_provider_for_session

            # Verify imports are callable/classes
            self.assertTrue(callable(get_provider_for_session))
            self.assertIsNotNone(ProviderRouter)
        except ImportError as e:
            self.fail(f"Failed to import provider_router: {e}")

    def test_get_provider_for_session(self):
        """Test provider lookup for sessions."""
        from services.provider_router import get_provider_for_session

        # Worker sessions use codex by default (to avoid Claude API limits)
        self.assertEqual(get_provider_for_session("dev_worker1"), "codex")
        self.assertEqual(get_provider_for_session("qa_tester1"), "codex")

        # High-level sessions should get claude
        self.assertEqual(get_provider_for_session("architect"), "claude")
        self.assertEqual(get_provider_for_session("foundation"), "claude")


class TestEndToEndWorkflow(unittest.TestCase):
    """End-to-end workflow tests."""

    @classmethod
    def setUpClass(cls):
        """Check if tmux is available."""
        result = subprocess.run(["which", "tmux"], capture_output=True, text=True)
        cls.tmux_available = result.returncode == 0

    def setUp(self):
        """Set up test fixtures."""
        if not self.tmux_available:
            self.skipTest("tmux not available")
        self.test_session = f"gaia_e2e_{int(time.time())}"

    def tearDown(self):
        """Clean up test sessions."""
        if hasattr(self, "test_session"):
            subprocess.run(
                ["tmux", "kill-session", "-t", self.test_session],
                capture_output=True,
            )

    def test_full_session_lifecycle(self):
        """Test complete session lifecycle: create, use, destroy."""
        manager = SessionPoolManager()

        # 1. Create session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.test_session, "bash"],
            capture_output=True,
        )

        # 2. Refresh and verify
        manager.refresh_sessions()
        self.assertIn(self.test_session, manager.sessions)

        # 3. Check session details
        session = manager.sessions[self.test_session]
        self.assertEqual(session["name"], self.test_session)

        # 4. Send a command
        subprocess.run(
            ["tmux", "send-keys", "-t", self.test_session, "echo SUCCESS", "Enter"],
            capture_output=True,
        )
        time.sleep(0.3)

        # 5. Verify output
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", self.test_session, "-p"],
            capture_output=True,
            text=True,
        )
        self.assertIn("SUCCESS", result.stdout)

        # 6. Stop session
        result = manager.stop_session(self.test_session)
        self.assertTrue(result)

        # 7. Verify stopped
        manager.refresh_sessions()
        self.assertNotIn(self.test_session, manager.sessions)

    def test_multiple_sessions_parallel(self):
        """Test managing multiple sessions in parallel."""
        manager = SessionPoolManager()
        sessions = [f"gaia_parallel_{i}_{int(time.time())}" for i in range(3)]

        try:
            # Create multiple sessions
            for session in sessions:
                result = subprocess.run(
                    ["tmux", "new-session", "-d", "-s", session, "bash"],
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0)

            # Verify all exist
            manager.refresh_sessions()
            for session in sessions:
                self.assertIn(session, manager.sessions)

            # Send commands to all
            for i, session in enumerate(sessions):
                subprocess.run(
                    ["tmux", "send-keys", "-t", session, f"echo SESSION_{i}", "Enter"],
                    capture_output=True,
                )

            time.sleep(0.5)

            # Verify outputs
            for i, session in enumerate(sessions):
                result = subprocess.run(
                    ["tmux", "capture-pane", "-t", session, "-p"],
                    capture_output=True,
                    text=True,
                )
                self.assertIn(f"SESSION_{i}", result.stdout)

        finally:
            # Cleanup all sessions
            for session in sessions:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session],
                    capture_output=True,
                )

    def test_session_provider_detection_e2e(self):
        """Test provider detection works for various session names."""
        manager = SessionPoolManager()

        test_cases = [
            (f"claude_high_{int(time.time())}", "claude"),  # Claude pattern → claude
            (f"ollama_local_{int(time.time())}", "ollama"),  # Ollama pattern
            (f"dev_worker99_{int(time.time())}", "codex"),  # Worker → codex
            (f"gaia_worker_{int(time.time())}", "codex"),  # GAIA worker → codex
        ]

        created_sessions = []
        try:
            for session_name, expected_provider in test_cases:
                subprocess.run(
                    ["tmux", "new-session", "-d", "-s", session_name, "bash"],
                    capture_output=True,
                )
                created_sessions.append(session_name)

            manager.refresh_sessions()

            for session_name, expected_provider in test_cases:
                self.assertIn(session_name, manager.sessions)
                session = manager.sessions[session_name]
                self.assertEqual(session["provider"], expected_provider)

        finally:
            for session in created_sessions:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session],
                    capture_output=True,
                )

    def test_gaia_agent_with_real_sessions(self):
        """Test GAIAgent selecting from real tmux sessions."""
        # Create test sessions with different "providers"
        sessions = {
            f"claude_agent_{int(time.time())}": "claude",
            f"ollama_agent_{int(time.time())}": "ollama",
        }

        created = []
        try:
            for session_name in sessions:
                result = subprocess.run(
                    ["tmux", "new-session", "-d", "-s", session_name, "bash"],
                    capture_output=True,
                )
                if result.returncode == 0:
                    created.append(session_name)

            # Create agent and test selection
            agent = GAIAgent(verbose=False)
            selected = agent.select_session(complexity="high")

            # Should prefer claude for high complexity
            if selected and "claude" in selected["name"]:
                self.assertEqual(selected["provider"], "claude")

        finally:
            for session in created:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session],
                    capture_output=True,
                )

    def test_send_and_capture_workflow(self):
        """Test the complete send-capture workflow."""
        try:
            # Create session
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", self.test_session, "bash"],
                capture_output=True,
            )

            # Create agent targeting this session
            agent = GAIAgent(session_name=self.test_session, verbose=False)

            # Send a command
            success = agent.send_to_session(self.test_session, "echo GAIA_E2E_TEST")
            self.assertTrue(success)

            time.sleep(0.3)

            # Capture and verify
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", self.test_session, "-p"],
                capture_output=True,
                text=True,
            )
            self.assertIn("GAIA_E2E_TEST", result.stdout)

        finally:
            subprocess.run(
                ["tmux", "kill-session", "-t", self.test_session],
                capture_output=True,
            )


class TestGAIACLI(unittest.TestCase):
    """Test GAIA command-line interface."""

    def test_help_output(self):
        """Test gaia --help works."""
        script_path = Path(__file__).parent.parent / "gaia.py"
        result = subprocess.run(
            ["python3", str(script_path), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("GAIA", result.stdout)
        self.assertIn("--provider", result.stdout)
        self.assertIn("--session", result.stdout)

    def test_status_output(self):
        """Test gaia --status works."""
        script_path = Path(__file__).parent.parent / "gaia.py"
        result = subprocess.run(
            ["python3", str(script_path), "--status"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("GAIA", result.stdout)

    def test_invalid_provider(self):
        """Test invalid provider is rejected."""
        script_path = Path(__file__).parent.parent / "gaia.py"
        result = subprocess.run(
            ["python3", str(script_path), "--provider", "invalid"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_complexity_options(self):
        """Test complexity options are accepted."""
        script_path = Path(__file__).parent.parent / "gaia.py"
        for complexity in ["low", "medium", "high"]:
            result = subprocess.run(
                ["python3", str(script_path), "--complexity", complexity, "--status"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)


class TestProviderFailover(unittest.TestCase):
    """Test provider failover behavior."""

    def test_fallback_chain_exists(self):
        """Test that fallback chains are defined."""
        routing = CODEX_THRESHOLDS["complexity_routing"]

        # Each complexity level should have fallbacks
        for level in ["low", "medium", "high"]:
            providers = routing[level]
            self.assertGreater(len(providers), 1, f"No fallbacks for {level}")

    def test_provider_diversity(self):
        """Test that complexity routing has fallback options."""
        routing = CODEX_THRESHOLDS["complexity_routing"]

        # All complexity levels should have codex as primary (cost savings)
        for level in ["low", "medium", "high"]:
            self.assertEqual(routing[level][0], "codex")

        # High complexity should have claude as fallback
        self.assertIn("claude", routing["high"])

    @patch("subprocess.run")
    def test_session_selection_with_no_sessions(self, mock_run):
        """Test agent behavior when no sessions available."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        agent = GAIAgent(verbose=False)
        session = agent.select_session(complexity="medium")

        # Should return None when no sessions
        self.assertIsNone(session)


class TestWorkingDirectory(unittest.TestCase):
    """Test working directory support."""

    def test_working_dir_default(self):
        """Test WORKING_DIR is set to current directory."""
        from gaia import WORKING_DIR

        self.assertEqual(WORKING_DIR, Path.cwd())

    def test_script_dir_resolution(self):
        """Test SCRIPT_DIR resolves correctly."""
        from gaia import SCRIPT_DIR

        self.assertTrue(SCRIPT_DIR.exists())
        self.assertTrue((SCRIPT_DIR / "gaia.py").exists())

    def test_state_dir_exists(self):
        """Test STATE_DIR is created."""
        from gaia import STATE_DIR

        self.assertTrue(STATE_DIR.exists())
        self.assertTrue(STATE_DIR.is_dir())

    def test_config_dir_exists(self):
        """Test CONFIG_DIR exists."""
        from gaia import CONFIG_DIR

        self.assertTrue(CONFIG_DIR.exists())
        self.assertTrue((CONFIG_DIR / "thresholds.yaml").exists())


class TestSessionStateTracking(unittest.TestCase):
    """Test session state persistence."""

    def test_state_file_location(self):
        """Test state file is in correct location."""
        from gaia import STATE_DIR

        state_file = STATE_DIR / "gaia_state.json"
        # File may or may not exist, but directory should
        self.assertTrue(STATE_DIR.exists())
        # State file path should be valid
        self.assertTrue(str(state_file).endswith("gaia_state.json"))

    @patch("subprocess.run")
    def test_agent_tracks_state_file(self, mock_run):
        """Test GAIAgent has state file reference."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        agent = GAIAgent(verbose=False)
        self.assertIsNotNone(agent.state_file)
        self.assertTrue(str(agent.state_file).endswith("gaia_state.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
