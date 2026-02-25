"""
Message handlers for Claude Code wrapper.

This module handles processing of terminal I/O and prompt logging.
Supports auto-response to permission prompts for autonomous operation.
"""

import os
import re
import time
from pathlib import Path

from . import config, extractors, state

__version__ = "2.0.0"


class OutputHandler:
    """Handles output from Claude session with auto-response capability."""

    def __init__(self, log_file=None, no_log=False, master_fd=None, auto_respond=False):
        self.log_file = Path(log_file) if log_file else config.SESSION_LOG_PATH
        self.no_log = no_log
        self.output_buffer = []
        self.prompts_found = []
        self.master_fd = master_fd  # PTY master fd for sending responses
        self.auto_respond = auto_respond  # Enable auto-response mode
        self.pending_response = None  # Response waiting to be sent
        self.response_delay = 0.2  # Delay before sending response (seconds)
        self.last_response_time = 0

    def process_output(self, data):
        """Process output data from Claude session."""
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")

        self.output_buffer.append(data)
        state.increment_counter("bytes_received", len(data))

        # Check for prompts in recent output
        self._check_for_prompts()

    def _check_for_prompts(self):
        """Check buffer for new prompts and auto-respond if enabled."""
        raw_output = "".join(self.output_buffer)

        new_prompts = extractors.parse_prompts(raw_output, self.prompts_found)

        for prompt in new_prompts:
            self.prompts_found.append(prompt)

            # Determine response
            response_num, reason = extractors.suggest_response(prompt)
            approved = response_num is not None

            state.record_prompt(prompt["operation_type"], prompt["command"], approved=approved)

            if not self.no_log:
                self._save_prompt_to_log(prompt)

            # Auto-respond if enabled and we have a master_fd
            if self.auto_respond and self.master_fd is not None:
                self._queue_response(prompt, response_num, reason)

    def _get_next_prompt_number(self):
        """Get the next prompt number from the existing log."""
        if not self.log_file.exists():
            return 1

        content = self.log_file.read_text()
        numbers = re.findall(r"^\| (\d+) \|", content, re.MULTILINE)
        if numbers:
            return max(int(n) for n in numbers) + 1
        return 1

    def _save_prompt_to_log(self, prompt):
        """Append a prompt to the session log."""
        num = self._get_next_prompt_number()
        row = extractors.format_prompt_for_log(prompt, num)

        if self.log_file.exists():
            content = self.log_file.read_text()

            # Find the table and append
            table_pattern = r"(\| \d+ \| [^|]+ \| [^|]+ \| [^|]+ \|)\n"
            matches = list(re.finditer(table_pattern, content))

            if matches:
                last_match = matches[-1]
                insert_pos = last_match.end()
                content = content[:insert_pos] + row + "\n" + content[insert_pos:]
                self.log_file.write_text(content)

    def get_stats(self):
        """Get handler statistics."""
        return {
            "buffer_size": len("".join(self.output_buffer)),
            "prompts_found": len(self.prompts_found),
            "last_prompt": self.prompts_found[-1] if self.prompts_found else None,
            "auto_respond": self.auto_respond,
            "pending_response": self.pending_response,
        }

    def save_buffer_to_file(self, filepath=None):
        """Save the output buffer to a file for debugging."""
        filepath = filepath or config.OUTPUT_BUFFER_PATH
        if self.output_buffer:
            Path(filepath).write_text("".join(self.output_buffer))
            return True
        return False

    def _queue_response(self, prompt, response_num, reason):
        """Queue a response to be sent after a short delay."""
        if response_num is None:
            # No matching rule - check for default behavior
            response_num = self._get_default_response(prompt)
            reason = "default response"

        if response_num is not None:
            self.pending_response = {
                "prompt": prompt,
                "response": response_num,
                "reason": reason,
                "queued_at": time.time(),
            }

    def _get_default_response(self, prompt):
        """Get default response for prompts without specific rules."""
        # Check if auto_approve_all is enabled in config
        if getattr(config, "AUTO_APPROVE_ALL", False):
            return 1  # Always approve with option 1

        # Default: approve common safe operations
        op_type = prompt.get("operation_type", "").lower()
        command = prompt.get("command", "").lower()

        # Safe operations that can be auto-approved
        safe_patterns = [
            r"^read",  # Read file
            r"^ls\b",  # List directory
            r"^cat\b",  # View file
            r"^pwd$",  # Print working directory
            r"^echo\b",  # Echo (usually safe)
            r"^git status",  # Git status
            r"^git diff",  # Git diff
            r"^git log",  # Git log
            r"^head\b",  # Head
            r"^tail\b",  # Tail
        ]

        for pattern in safe_patterns:
            if re.search(pattern, command):
                return 1

        return None  # No auto-response, let user decide

    def process_pending_response(self):
        """
        Process and send any pending response.
        Call this periodically from the main loop.
        Returns True if a response was sent.
        """
        if not self.pending_response:
            return False

        # Check if enough time has passed
        elapsed = time.time() - self.pending_response["queued_at"]
        if elapsed < self.response_delay:
            return False

        # Send the response
        response = self.pending_response["response"]
        prompt = self.pending_response["prompt"]
        reason = self.pending_response["reason"]

        success = self._send_response(response)

        if success:
            # Log the auto-response
            if not self.no_log:
                self._log_auto_response(prompt, response, reason)

        self.pending_response = None
        self.last_response_time = time.time()
        return success

    def _send_response(self, response):
        """
        Send a response to Claude via the PTY.

        Args:
            response: Option number (1, 2, 3) or special response ('y', 'n', 'esc')

        Returns:
            True if sent successfully
        """
        if self.master_fd is None:
            return False

        try:
            if isinstance(response, int):
                # Send the number key
                os.write(self.master_fd, str(response).encode())
            elif response == "esc":
                # Send Escape key
                os.write(self.master_fd, b"\x1b")
            elif response in ("y", "n"):
                # Send y or n
                os.write(self.master_fd, response.encode())
            else:
                # Send as-is
                os.write(self.master_fd, str(response).encode())

            state.increment_counter("bytes_sent", 1)
            return True

        except OSError as e:
            state.record_error(f"Failed to send response: {e}")
            return False

    def _log_auto_response(self, prompt, response, reason):
        """Log an auto-response to the session log."""
        import sys

        msg = f"[AutoResponse] {prompt['operation_type']}: {prompt['command'][:50]} -> option {response} ({reason})"
        print(f"\n{msg}", file=sys.stderr)


class InputHandler:
    """Handles input to Claude session."""

    def __init__(self):
        self.bytes_sent = 0

    def process_input(self, data):
        """Process input data being sent to Claude."""
        if isinstance(data, bytes):
            size = len(data)
        else:
            size = len(data.encode("utf-8"))

        self.bytes_sent += size
        state.increment_counter("bytes_sent", size)
        return data


class ReloadHandler:
    """Handles hot-reload of wrapper_core modules."""

    def __init__(self):
        self.last_check = None

    def check_reload_signal(self):
        """Check if a reload has been requested via signal file."""
        if config.RELOAD_SIGNAL_PATH.exists():
            try:
                config.RELOAD_SIGNAL_PATH.unlink()
                return True
            except:
                pass
        return False

    def reload_modules(self):
        """Reload all wrapper_core modules."""
        import wrapper_core

        success, message = wrapper_core.reload_all()
        if success:
            state.increment_reload()
        return success, message
