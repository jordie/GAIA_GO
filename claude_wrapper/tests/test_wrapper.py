#!/usr/bin/env python3
"""
Comprehensive test suite for Claude Code Wrapper.

Tests cover:
- Prompt pattern detection
- Dangerous command detection
- Response suggestion logic
- Auto-response functionality
- State management
- Integration with session assigner
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from wrapper_core import config, extractors, handlers, state


class TestPromptPatternDetection(unittest.TestCase):
    """Test prompt pattern detection in terminal output."""

    def test_bash_command_prompt(self):
        """Test detection of Bash command prompts."""
        terminal_output = """
────────────────────────────────────────────────────
Bash command

git status

Check git repository status

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, don't ask again for this command

Press enter to confirm, or Esc to cancel
"""
        prompts = extractors.parse_prompts(terminal_output)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["operation_type"], "Bash command")
        self.assertIn("git status", prompts[0]["command"])

    def test_edit_file_prompt(self):
        """Test detection of Edit file prompts."""
        terminal_output = """
────────────────────────────────────────────────────
Edit file

/path/to/file.py

Update function definition

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, don't ask again for this file

Press enter to confirm, or Esc to cancel
"""
        prompts = extractors.parse_prompts(terminal_output)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["operation_type"], "Edit file")

    def test_write_file_prompt(self):
        """Test detection of Write file prompts."""
        terminal_output = """
────────────────────────────────────────────────────
Write file

/path/to/newfile.py

Create new Python file

Do you want to proceed?
❯ 1. Yes, allow this once

Press enter to confirm, or Esc to cancel
"""
        prompts = extractors.parse_prompts(terminal_output)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["operation_type"], "Write file")

    def test_multiple_prompts(self):
        """Test detection of multiple prompts in output."""
        # Test that at least one prompt is detected from complex output
        # Note: Claude typically shows one prompt at a time, so sequential
        # detection (calling parse_prompts multiple times) is the normal flow
        terminal_output = """
Some output here...

────────────────────────────────────────────────────
Bash command

ls -la

List directory

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, don't ask again

Press enter to confirm, or Esc to cancel
"""
        prompts = extractors.parse_prompts(terminal_output)
        self.assertGreaterEqual(len(prompts), 1)

    def test_no_duplicate_prompts(self):
        """Test that duplicate prompts are not added."""
        terminal_output = """
────────────────────────────────────────────────────
Bash command

git status

Check status

Do you want to proceed?
❯ 1. Yes, allow this once

Press enter to confirm, or Esc to cancel
"""
        # Parse once
        existing = extractors.parse_prompts(terminal_output)
        # Parse again with existing prompts
        new = extractors.parse_prompts(terminal_output, existing)
        self.assertEqual(len(new), 0)

    def test_ansi_stripping(self):
        """Test ANSI escape code stripping."""
        text_with_ansi = "\x1b[31mRed text\x1b[0m"
        stripped = extractors.strip_ansi(text_with_ansi)
        self.assertEqual(stripped, "Red text")


class TestDangerousCommandDetection(unittest.TestCase):
    """Test detection of dangerous commands."""

    def test_rm_rf_root(self):
        """Test detection of rm -rf /."""
        prompt = {"command": "rm -rf /"}
        dangerous, pattern = extractors.is_dangerous(prompt)
        self.assertTrue(dangerous)

    def test_rm_rf_wildcard(self):
        """Test detection of rm -rf *."""
        prompt = {"command": "rm -rf *"}
        dangerous, pattern = extractors.is_dangerous(prompt)
        self.assertTrue(dangerous)

    def test_sudo_rm(self):
        """Test detection of sudo rm."""
        prompt = {"command": "sudo rm -rf /var/log"}
        dangerous, pattern = extractors.is_dangerous(prompt)
        self.assertTrue(dangerous)

    def test_dd_command(self):
        """Test detection of dd command."""
        prompt = {"command": "dd if=/dev/zero of=/dev/sda"}
        dangerous, pattern = extractors.is_dangerous(prompt)
        self.assertTrue(dangerous)

    def test_chmod_777(self):
        """Test detection of chmod 777."""
        prompt = {"command": "chmod 777 /"}
        dangerous, pattern = extractors.is_dangerous(prompt)
        self.assertTrue(dangerous)

    def test_safe_command(self):
        """Test that safe commands are not flagged as dangerous."""
        safe_commands = [
            "git status",
            "ls -la",
            "cat /etc/hosts",
            "python3 app.py",
            "npm install",
        ]
        for cmd in safe_commands:
            prompt = {"command": cmd}
            dangerous, _ = extractors.is_dangerous(prompt)
            self.assertFalse(dangerous, f"'{cmd}' should not be dangerous")


class TestResponseSuggestion(unittest.TestCase):
    """Test response suggestion logic."""

    def test_git_commands(self):
        """Test suggestions for git commands."""
        git_commands = [
            "git status",
            "git add .",
            'git commit -m "test"',
            "git push origin main",
            "git diff",
            "git log",
        ]
        for cmd in git_commands:
            prompt = {"operation_type": "Bash command", "command": cmd}
            response, reason = extractors.suggest_response(prompt)
            self.assertIsNotNone(response, f"No response for: {cmd}")
            self.assertEqual(response, 1)

    def test_read_operations(self):
        """Test suggestions for read operations."""
        prompt = {"operation_type": "Read file", "command": "/path/to/file.py"}
        response, reason = extractors.suggest_response(prompt)
        self.assertEqual(response, 1)

    def test_edit_operations(self):
        """Test suggestions for edit operations."""
        prompt = {"operation_type": "Edit file", "command": "/path/to/file.py"}
        response, reason = extractors.suggest_response(prompt)
        self.assertEqual(response, 1)

    def test_write_operations(self):
        """Test suggestions for write operations."""
        prompt = {"operation_type": "Write file", "command": "/path/to/file.py"}
        response, reason = extractors.suggest_response(prompt)
        self.assertEqual(response, 1)

    def test_dangerous_blocked(self):
        """Test that dangerous commands return None response."""
        prompt = {"operation_type": "Bash command", "command": "rm -rf /"}
        response, reason = extractors.suggest_response(prompt)
        self.assertIsNone(response)
        self.assertIn("BLOCKED", reason)

    def test_auto_approve_all(self):
        """Test AUTO_APPROVE_ALL flag."""
        # Save original value
        original = config.AUTO_APPROVE_ALL

        try:
            config.AUTO_APPROVE_ALL = True
            prompt = {"operation_type": "Bash command", "command": "unknown_command"}
            response, reason = extractors.suggest_response(prompt)
            self.assertEqual(response, 1)
            self.assertIn("AUTO_APPROVE_ALL", reason)
        finally:
            config.AUTO_APPROVE_ALL = original

    def test_tmux_commands(self):
        """Test suggestions for tmux commands (session assigner integration)."""
        tmux_commands = [
            'tmux send-keys -t session "test"',
            "tmux capture-pane -t session",
            "tmux list-sessions",
        ]
        for cmd in tmux_commands:
            prompt = {"operation_type": "Bash command", "command": cmd}
            response, reason = extractors.suggest_response(prompt)
            self.assertIsNotNone(response, f"No response for: {cmd}")


class TestStateManagement(unittest.TestCase):
    """Test session state management."""

    def setUp(self):
        """Initialize state before each test."""
        state.init_session("test_session")

    def test_init_session(self):
        """Test session initialization."""
        current_state = state.get_state()
        self.assertEqual(current_state["session_id"], "test_session")
        self.assertEqual(current_state["status"], "running")
        self.assertEqual(current_state["prompts_detected"], 0)

    def test_increment_counter(self):
        """Test counter incrementing."""
        state.increment_counter("bytes_received", 100)
        current_state = state.get_state()
        self.assertEqual(current_state["bytes_received"], 100)

        state.increment_counter("bytes_received", 50)
        current_state = state.get_state()
        self.assertEqual(current_state["bytes_received"], 150)

    def test_record_prompt(self):
        """Test prompt recording."""
        state.record_prompt("Bash command", "git status", approved=True)
        current_state = state.get_state()
        self.assertEqual(current_state["prompts_detected"], 1)
        self.assertEqual(current_state["prompts_approved"], 1)
        self.assertIsNotNone(current_state["last_prompt"])

    def test_record_error(self):
        """Test error recording."""
        state.record_error("Test error message")
        current_state = state.get_state()
        self.assertEqual(len(current_state["errors"]), 1)
        self.assertEqual(current_state["errors"][0]["message"], "Test error message")

    def test_end_session(self):
        """Test session ending."""
        state.end_session()
        current_state = state.get_state()
        self.assertEqual(current_state["status"], "stopped")


class TestOutputHandler(unittest.TestCase):
    """Test OutputHandler functionality."""

    def setUp(self):
        """Set up handler for each test."""
        self.handler = handlers.OutputHandler(no_log=True, master_fd=None, auto_respond=False)

    def test_process_output(self):
        """Test output processing."""
        self.handler.process_output(b"Test output data")
        self.assertEqual(len(self.handler.output_buffer), 1)
        self.assertEqual(self.handler.output_buffer[0], "Test output data")

    def test_process_output_unicode(self):
        """Test output processing with unicode."""
        self.handler.process_output("Unicode: émojis 🎉")
        self.assertEqual(len(self.handler.output_buffer), 1)

    def test_get_stats(self):
        """Test stats retrieval."""
        self.handler.process_output(b"Test")
        stats = self.handler.get_stats()
        self.assertIn("buffer_size", stats)
        self.assertIn("prompts_found", stats)
        self.assertIn("auto_respond", stats)

    def test_save_buffer(self):
        """Test buffer saving."""
        self.handler.process_output(b"Test data")
        test_path = Path("/tmp/test_wrapper_buffer.txt")
        result = self.handler.save_buffer_to_file(test_path)
        self.assertTrue(result)
        self.assertTrue(test_path.exists())
        content = test_path.read_text()
        self.assertEqual(content, "Test data")
        test_path.unlink()


class TestAutoResponse(unittest.TestCase):
    """Test auto-response functionality."""

    def test_queue_response(self):
        """Test response queueing."""
        handler = handlers.OutputHandler(no_log=True, master_fd=None, auto_respond=True)
        prompt = {"operation_type": "Bash", "command": "git status"}
        handler._queue_response(prompt, 1, "test reason")
        self.assertIsNotNone(handler.pending_response)
        self.assertEqual(handler.pending_response["response"], 1)

    def test_default_response_safe_commands(self):
        """Test default response for safe commands."""
        handler = handlers.OutputHandler(no_log=True, master_fd=None, auto_respond=True)
        safe_prompts = [
            {"operation_type": "Bash", "command": "ls -la"},
            {"operation_type": "Bash", "command": "pwd"},
            {"operation_type": "Bash", "command": "git status"},
        ]
        for prompt in safe_prompts:
            response = handler._get_default_response(prompt)
            self.assertEqual(response, 1, f"Expected 1 for: {prompt['command']}")

    def test_send_response_no_fd(self):
        """Test send_response without master_fd."""
        handler = handlers.OutputHandler(no_log=True, master_fd=None, auto_respond=True)
        result = handler._send_response(1)
        self.assertFalse(result)

    @patch("os.write")
    def test_send_response_with_fd(self, mock_write):
        """Test send_response with mock master_fd."""
        mock_write.return_value = 1
        handler = handlers.OutputHandler(no_log=True, master_fd=5, auto_respond=True)  # Mock fd
        result = handler._send_response(1)
        self.assertTrue(result)
        mock_write.assert_called_once_with(5, b"1")


class TestTemplateClassification(unittest.TestCase):
    """Test prompt template classification."""

    def test_classify_bash_simple(self):
        """Test classification of simple bash prompt."""
        prompt = {
            "operation_type": "Bash command",
            "options": [
                {"number": 1, "text": "Yes, allow once"},
                {"number": 2, "text": "Yes, always allow"},
            ],
        }
        template = extractors.classify_template(prompt)
        self.assertEqual(template, "BASH_SIMPLE")

    def test_classify_edit(self):
        """Test classification of edit prompt."""
        prompt = {"operation_type": "Edit file", "options": []}
        template = extractors.classify_template(prompt)
        self.assertEqual(template, "EDIT_FILE")

    def test_classify_write(self):
        """Test classification of write prompt."""
        prompt = {"operation_type": "Write file", "options": []}
        template = extractors.classify_template(prompt)
        self.assertEqual(template, "WRITE_FILE")

    def test_classify_read(self):
        """Test classification of read prompt."""
        prompt = {"operation_type": "Read file", "options": []}
        template = extractors.classify_template(prompt)
        self.assertEqual(template, "READ_FILE")


class TestConfigPatterns(unittest.TestCase):
    """Test configuration patterns."""

    def test_response_rules_exist(self):
        """Test that response rules are defined."""
        self.assertIsInstance(config.RESPONSE_RULES, dict)
        self.assertGreater(len(config.RESPONSE_RULES), 0)

    def test_dangerous_patterns_exist(self):
        """Test that dangerous patterns are defined."""
        self.assertIsInstance(config.DANGEROUS_PATTERNS, list)
        self.assertGreater(len(config.DANGEROUS_PATTERNS), 0)

    def test_each_rule_has_required_fields(self):
        """Test that each rule has required fields."""
        for name, rule in config.RESPONSE_RULES.items():
            self.assertIn("pattern", rule, f"Rule '{name}' missing 'pattern'")
            self.assertIn("response", rule, f"Rule '{name}' missing 'response'")
            self.assertIn("description", rule, f"Rule '{name}' missing 'description'")


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows."""

    def test_full_prompt_workflow(self):
        """Test complete workflow from detection to response."""
        # Simulate terminal output with prompt
        terminal_output = """
────────────────────────────────────────────────────
Bash command

git add .

Stage all changes

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, don't ask again

Press enter to confirm, or Esc to cancel
"""
        # Initialize handler with a mock fd (required for auto-response queueing)
        handler = handlers.OutputHandler(
            no_log=True, master_fd=999, auto_respond=True  # Mock fd - responses won't actually send
        )

        # Process output
        handler.process_output(terminal_output)

        # Check prompts were detected
        self.assertEqual(len(handler.prompts_found), 1)

        # Check response was queued (requires valid master_fd)
        self.assertIsNotNone(handler.pending_response)
        self.assertEqual(handler.pending_response["response"], 1)

    def test_dangerous_command_blocked(self):
        """Test that dangerous commands are not auto-approved."""
        terminal_output = """
────────────────────────────────────────────────────
Bash command

rm -rf /

Delete everything

Do you want to proceed?
❯ 1. Yes, allow this once

Press enter to confirm, or Esc to cancel
"""
        handler = handlers.OutputHandler(no_log=True, master_fd=999, auto_respond=True)  # Mock fd

        handler.process_output(terminal_output)

        # Command detected but should not have pending response
        self.assertEqual(len(handler.prompts_found), 1)
        # No pending response for dangerous command (blocked even with valid fd)
        self.assertIsNone(handler.pending_response)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
