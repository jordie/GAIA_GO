#!/usr/bin/env python3
"""
Claude Auto-Approver Worker
Monitors Claude Code sessions and automatically approves prompts based on patterns.
"""

import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClaudeAutoApprover")


class ClaudeAutoApprover:
    """Automatically approve Claude Code prompts based on configured patterns."""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.db_path = self.base_path / "data" / "architect.db"
        self.check_interval = 5  # seconds
        self.session_cache = {}

    def get_patterns(self, session_name=None):
        """Get enabled auto-approval patterns, prioritizing session-specific ones."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, name, pattern_type, pattern, action, scope, priority
            FROM claude_patterns
            WHERE enabled = 1
            ORDER BY priority DESC, id ASC
        """
        )

        patterns = []
        for row in cursor.fetchall():
            pattern_id, name, ptype, pattern, action, scope, priority = row

            # Check if pattern applies to this session
            if scope and session_name:
                if scope.startswith("session:"):
                    if scope.split(":", 1)[1] != session_name:
                        continue
                elif scope.startswith("project:"):
                    # TODO: Check if current working directory matches
                    pass

            patterns.append(
                {
                    "id": pattern_id,
                    "name": name,
                    "type": ptype,
                    "pattern": pattern,
                    "action": action,
                    "priority": priority,
                }
            )

        conn.close()
        return patterns

    def parse_prompt(self, output):
        """Parse Claude Code output to detect prompts."""
        prompts = []

        # Detect file permission prompts
        # Pattern: "Do you want to proceed?" with file operations
        if "Do you want to proceed?" in output or "accept edits" in output.lower():
            # Look for file paths in the output
            file_matches = re.findall(
                r"([/\w\-_.]+\.(py|js|jsx|ts|tsx|json|yaml|yml|md|txt|sql|sh))", output
            )

            prompt_type = "edit_confirmation"
            if "Create" in output or "write" in output.lower():
                prompt_type = "file_create"
            elif "Edit" in output or "modify" in output.lower():
                prompt_type = "file_edit"
            elif "Read" in output:
                prompt_type = "file_read"

            prompts.append(
                {
                    "type": prompt_type,
                    "text": output,
                    "files": [f[0] for f in file_matches] if file_matches else [],
                    "action_requested": "write" if "Create" in output else "edit",
                }
            )

        # Detect command execution prompts
        if "Run command" in output or "Execute" in output:
            cmd_match = re.search(r"`([^`]+)`", output)
            if cmd_match:
                prompts.append(
                    {
                        "type": "command",
                        "text": output,
                        "command": cmd_match.group(1),
                        "action_requested": "execute",
                    }
                )

        return prompts

    def should_approve(self, prompt, patterns):
        """Check if prompt should be auto-approved based on patterns."""
        for pattern in patterns:
            # Match by prompt type
            if pattern["type"] != prompt["type"]:
                continue

            # Match by pattern regex
            try:
                # For file operations, check against file paths
                if prompt["type"] in ["file_edit", "file_create", "file_read"] and prompt.get(
                    "files"
                ):
                    for file_path in prompt["files"]:
                        if re.search(pattern["pattern"], file_path):
                            logger.info(
                                f"✓ Matched pattern '{pattern['name']}' for file: {file_path}"
                            )
                            return pattern["action"] == "approve", pattern["id"]

                # For commands, check against command text
                elif prompt["type"] == "command" and prompt.get("command"):
                    if re.search(pattern["pattern"], prompt["command"]):
                        logger.info(
                            f"✓ Matched pattern '{pattern['name']}' for command: {prompt['command']}"
                        )
                        return pattern["action"] == "approve", pattern["id"]

                # General text matching
                elif re.search(pattern["pattern"], prompt["text"]):
                    logger.info(f"✓ Matched pattern '{pattern['name']}'")
                    return pattern["action"] == "approve", pattern["id"]

            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern['pattern']}': {e}")
                continue

        return False, None

    def send_approval(self, session_name):
        """Send approval key to Claude Code session."""
        try:
            # Try Space first (main approval key)
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "Space"], check=True, capture_output=True
            )
            time.sleep(0.5)

            # Check if there's a confirmation dialog (e.g., "1. Yes / 2. No")
            output = subprocess.run(
                ["tmux", "capture-pane", "-t", session_name, "-p"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            if "Yes" in output and "1." in output:
                # Send "1" to select Yes
                subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, "1"], check=True, capture_output=True
                )
                logger.info(f"✓ Sent confirmation to {session_name}")

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send approval to {session_name}: {e}")
            return False

    def log_interaction(self, session_name, prompt, approved, pattern_id=None):
        """Log the interaction to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO claude_interactions
            (session_name, prompt_type, prompt_text, file_path, action_requested,
             response, matched_pattern_id, auto_approved, responded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_name,
                prompt.get("type", "unknown"),
                prompt.get("text", "")[:500],  # Truncate long text
                ",".join(prompt.get("files", []))[:200] if prompt.get("files") else None,
                prompt.get("action_requested"),
                "approved" if approved else "pending",
                pattern_id,
                1 if approved else 0,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def check_session(self, session_name):
        """Check a session for pending prompts and auto-approve if matched."""
        try:
            # Capture current pane output
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session_name, "-p"],
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout

            # Parse for prompts
            prompts = self.parse_prompt(output)

            if not prompts:
                return

            # Get patterns for this session
            patterns = self.get_patterns(session_name)

            # Check each prompt
            for prompt in prompts:
                should_approve, pattern_id = self.should_approve(prompt, patterns)

                if should_approve:
                    logger.info(f"🤖 Auto-approving prompt in {session_name}")
                    if self.send_approval(session_name):
                        self.log_interaction(session_name, prompt, True, pattern_id)
                    time.sleep(1)  # Wait between approvals
                else:
                    logger.debug(f"⏸ No matching pattern for prompt in {session_name}")
                    self.log_interaction(session_name, prompt, False)

        except subprocess.CalledProcessError:
            # Session doesn't exist or isn't accessible
            pass
        except Exception as e:
            logger.error(f"Error checking session {session_name}: {e}")

    def get_claude_sessions(self):
        """Get list of Claude Code sessions to monitor."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                check=True,
            )

            # Filter for Claude sessions
            sessions = []
            for line in result.stdout.strip().split("\n"):
                if line and (
                    "claude" in line.lower()
                    or line in ["codex", "comet", "concurrent_worker1", "task_worker1"]
                ):
                    sessions.append(line)

            return sessions

        except subprocess.CalledProcessError:
            logger.warning("tmux not available or no sessions running")
            return []

    def run(self):
        """Main monitoring loop."""
        logger.info("🤖 Claude Auto-Approver started")
        logger.info(f"Monitoring for Claude Code prompts every {self.check_interval}s")

        try:
            while True:
                sessions = self.get_claude_sessions()

                if sessions:
                    logger.debug(f"Monitoring {len(sessions)} sessions: {', '.join(sessions)}")

                    for session in sessions:
                        self.check_session(session)

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("Auto-approver stopped by user")
        except Exception as e:
            logger.error(f"Auto-approver error: {e}")
            raise


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Claude Auto-Approval Worker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=5, help="Check interval in seconds")

    args = parser.parse_args()

    approver = ClaudeAutoApprover()
    approver.check_interval = args.interval

    if args.daemon:
        # TODO: Implement proper daemonization
        logger.info("Running in foreground (daemon mode not yet implemented)")

    approver.run()


if __name__ == "__main__":
    main()
