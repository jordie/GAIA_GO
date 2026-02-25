#!/usr/bin/env python3
"""
Claude Auto-Integration - Automated task execution via tmux Claude sessions

Features:
- Auto-send tasks to Claude Code sessions via tmux
- Parse responses automatically
- Extract code blocks, commands, and results
- Store results in database
- Compare with Perplexity results via quality scorer

Usage:
    from claude_auto_integration import ClaudeIntegration

    claude = ClaudeIntegration()
    result = claude.execute_task("Explain how Python generators work")
    print(result['response'])
"""

import json
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Database setup
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "claude_integration"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "claude_results.db"


class ClaudeIntegration:
    """Automated integration with Claude Code via tmux sessions."""

    def __init__(self, session_name: str = "claude_codex"):
        """
        Initialize Claude integration.

        Args:
            session_name: Name of the tmux session running Claude Code
        """
        self.session_name = session_name
        self.db_path = DB_PATH
        self.init_database()

    def init_database(self):
        """Initialize SQLite database for storing results."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claude_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                response TEXT NOT NULL,
                code_blocks TEXT,
                commands TEXT,
                session_name TEXT,
                execution_time_seconds REAL,
                tokens_estimate INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER,
                event_type TEXT,
                event_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (result_id) REFERENCES claude_results(id)
            )
        """)

        conn.commit()
        conn.close()

    def check_session_exists(self) -> bool:
        """Check if the Claude tmux session exists."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self.session_name],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error checking session: {e}")
            return False

    def check_session_ready(self) -> Tuple[bool, str]:
        """
        Check if Claude session is ready to receive tasks.

        Returns:
            (is_ready, status_message)
        """
        if not self.check_session_exists():
            return False, f"Session '{self.session_name}' does not exist"

        try:
            # Capture last 30 lines of output
            cmd = f"tmux capture-pane -t {self.session_name} -p -S -30"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return False, "Could not capture pane"

            output = result.stdout

            # Check for ready indicators
            ready_indicators = [
                "How can I help",
                "What would you like",
                "Ready to assist",
                "❯",  # Prompt ready
                "▶",  # Alternative prompt
            ]

            is_ready = any(ind in output for ind in ready_indicators)

            # Check for busy indicators
            busy_indicators = [
                "Thinking",
                "Analyzing",
                "Processing",
                "Running",
                "Please wait",
                "…",
            ]

            is_busy = any(ind in output for ind in busy_indicators)

            if is_busy:
                return False, "Claude is currently busy"

            if is_ready:
                return True, "Ready to receive tasks"

            # Check last line for prompt
            lines = output.strip().split('\n')
            last_line = lines[-1] if lines else ""

            if last_line.strip().endswith('❯') or last_line.strip() == '':
                return True, "Idle and ready"

            return False, f"Status unclear - last line: {last_line[:50]}"

        except Exception as e:
            return False, f"Error checking ready state: {e}"

    def send_task(self, task: str, wait_for_response: bool = True,
                  timeout: int = 120) -> Optional[Dict]:
        """
        Send a task to Claude and optionally wait for response.

        Args:
            task: The task/question to send to Claude
            wait_for_response: Whether to wait for Claude's response
            timeout: Maximum seconds to wait for response

        Returns:
            Dictionary with response data or None if failed
        """
        # Check if session is ready
        is_ready, status_msg = self.check_session_ready()
        if not is_ready:
            print(f"Session not ready: {status_msg}")
            return None

        start_time = time.time()

        try:
            # Send the task to Claude
            subprocess.run(
                ["tmux", "send-keys", "-t", self.session_name, task, "Enter"],
                timeout=5
            )

            if not wait_for_response:
                return {"status": "sent", "task": task}

            # Wait for response
            response = self._wait_for_response(timeout)
            execution_time = time.time() - start_time

            if response:
                # Parse the response
                parsed = self._parse_response(response)

                # Save to database
                result_id = self._save_result(
                    task=task,
                    response=response,
                    code_blocks=parsed.get('code_blocks'),
                    commands=parsed.get('commands'),
                    execution_time=execution_time
                )

                return {
                    "status": "success",
                    "task": task,
                    "response": response,
                    "parsed": parsed,
                    "execution_time": execution_time,
                    "result_id": result_id
                }
            else:
                return {
                    "status": "timeout",
                    "task": task,
                    "message": f"No response after {timeout}s"
                }

        except Exception as e:
            return {
                "status": "error",
                "task": task,
                "error": str(e)
            }

    def _wait_for_response(self, timeout: int = 120) -> Optional[str]:
        """
        Wait for Claude to finish responding.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            The response text or None if timeout
        """
        start_time = time.time()
        last_output = ""
        stable_count = 0
        required_stable_cycles = 3  # Output must be stable for 3 checks

        while (time.time() - start_time) < timeout:
            try:
                # Capture current output
                cmd = f"tmux capture-pane -t {self.session_name} -p -S -100"
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                current_output = result.stdout

                # Check if Claude is done (output is stable)
                if current_output == last_output:
                    stable_count += 1
                    if stable_count >= required_stable_cycles:
                        # Output is stable, Claude is done
                        return self._extract_response(current_output)
                else:
                    stable_count = 0
                    last_output = current_output

                time.sleep(1)  # Check every second

            except Exception as e:
                print(f"Error waiting for response: {e}")
                return None

        # Timeout
        return None

    def _extract_response(self, output: str) -> str:
        """
        Extract Claude's response from tmux output.

        Args:
            output: Raw tmux capture output

        Returns:
            Cleaned response text
        """
        lines = output.split('\n')

        # Find where the task was sent (look for our input)
        # Then extract everything after that until the next prompt

        response_lines = []
        capturing = False

        for i, line in enumerate(lines):
            # Skip ANSI codes and control characters
            clean_line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)

            # Look for Claude's response markers
            if capturing:
                # Stop at next prompt
                if clean_line.strip().endswith('❯') or 'How can I help' in clean_line:
                    break
                response_lines.append(clean_line)

            # Start capturing after seeing thinking/response indicators
            if any(ind in clean_line for ind in ['Thinking', 'Let me', 'I will', 'I can']):
                capturing = True
                response_lines.append(clean_line)

        return '\n'.join(response_lines).strip()

    def _parse_response(self, response: str) -> Dict:
        """
        Parse Claude's response to extract structured data.

        Args:
            response: Raw response text

        Returns:
            Dictionary with parsed components
        """
        parsed = {
            'code_blocks': [],
            'commands': [],
            'files_mentioned': [],
            'links': []
        }

        # Extract code blocks (```language ... ```)
        code_pattern = r'```(\w+)?\n(.*?)```'
        code_matches = re.findall(code_pattern, response, re.DOTALL)
        for lang, code in code_matches:
            parsed['code_blocks'].append({
                'language': lang or 'text',
                'code': code.strip()
            })

        # Extract shell commands (lines starting with $, >, or #)
        command_pattern = r'^[$>#]\s*(.+)$'
        command_matches = re.findall(command_pattern, response, re.MULTILINE)
        parsed['commands'] = command_matches

        # Extract file paths (common patterns)
        file_pattern = r'(?:^|\s)([\w\-/\.]+\.(?:py|js|md|txt|json|yaml|sh))'
        file_matches = re.findall(file_pattern, response)
        parsed['files_mentioned'] = list(set(file_matches))

        # Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        url_matches = re.findall(url_pattern, response)
        parsed['links'] = url_matches

        return parsed

    def _save_result(self, task: str, response: str, code_blocks: List[Dict],
                     commands: List[str], execution_time: float) -> int:
        """
        Save result to database.

        Returns:
            Result ID
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Estimate tokens (rough: ~4 chars per token)
        tokens_estimate = (len(task) + len(response)) // 4

        cursor.execute("""
            INSERT INTO claude_results
            (task, response, code_blocks, commands, session_name,
             execution_time_seconds, tokens_estimate, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task,
            response,
            json.dumps(code_blocks) if code_blocks else None,
            json.dumps(commands) if commands else None,
            self.session_name,
            execution_time,
            tokens_estimate,
            json.dumps({'version': '1.0'})
        ))

        result_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return result_id

    def execute_task(self, task: str, timeout: int = 120) -> Optional[Dict]:
        """
        High-level method to execute a task and get results.

        This is the main method to use for most cases.

        Args:
            task: The task/question for Claude
            timeout: Maximum seconds to wait

        Returns:
            Dictionary with results or None if failed
        """
        print(f"📤 Sending task to Claude: {task[:100]}...")
        result = self.send_task(task, wait_for_response=True, timeout=timeout)

        if result and result['status'] == 'success':
            print(f"✅ Response received in {result['execution_time']:.1f}s")
            print(f"📊 Parsed: {len(result['parsed']['code_blocks'])} code blocks, "
                  f"{len(result['parsed']['commands'])} commands")
            return result
        elif result and result['status'] == 'timeout':
            print(f"⏱️  Timeout after {timeout}s")
            return result
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error') if result else 'No result'}")
            return result

    def get_recent_results(self, limit: int = 10) -> List[Dict]:
        """Get recent results from database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM claude_results
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = dict(row)
            # Parse JSON fields
            if result['code_blocks']:
                result['code_blocks'] = json.loads(result['code_blocks'])
            if result['commands']:
                result['commands'] = json.loads(result['commands'])
            if result['metadata']:
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)

        return results

    def get_stats(self) -> Dict:
        """Get statistics about Claude executions."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM claude_results")
        total_results = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(execution_time_seconds) FROM claude_results")
        avg_time = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(tokens_estimate) FROM claude_results")
        total_tokens = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(*) FROM claude_results
            WHERE created_at >= datetime('now', '-24 hours')
        """)
        results_24h = cursor.fetchone()[0]

        conn.close()

        return {
            'total_results': total_results,
            'avg_execution_time': round(avg_time, 2),
            'total_tokens_estimate': total_tokens,
            'results_last_24h': results_24h,
            'session_name': self.session_name
        }


def main():
    """CLI interface for testing."""
    import sys

    claude = ClaudeIntegration()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == '--check':
            # Check if session is ready
            is_ready, msg = claude.check_session_ready()
            print(f"Session status: {msg}")
            print(f"Ready: {is_ready}")

        elif command == '--execute':
            # Execute a task
            if len(sys.argv) < 3:
                print("Usage: --execute '<task>'")
                sys.exit(1)

            task = sys.argv[2]
            result = claude.execute_task(task)

            if result and result['status'] == 'success':
                print("\n" + "="*80)
                print("RESPONSE:")
                print("="*80)
                print(result['response'])
                print("\n" + "="*80)
                print("PARSED DATA:")
                print("="*80)
                print(json.dumps(result['parsed'], indent=2))

        elif command == '--stats':
            # Show statistics
            stats = claude.get_stats()
            print(json.dumps(stats, indent=2))

        elif command == '--recent':
            # Show recent results
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            results = claude.get_recent_results(limit=limit)

            for i, result in enumerate(results, 1):
                print(f"\n{'='*80}")
                print(f"Result {i} (ID: {result['id']})")
                print(f"{'='*80}")
                print(f"Task: {result['task'][:100]}...")
                print(f"Time: {result['execution_time_seconds']:.1f}s")
                print(f"Created: {result['created_at']}")
                print(f"Response length: {len(result['response'])} chars")

        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  --check              Check if Claude session is ready")
            print("  --execute '<task>'   Execute a task")
            print("  --stats              Show statistics")
            print("  --recent [N]         Show N recent results (default: 5)")
            sys.exit(1)
    else:
        print("Claude Auto-Integration")
        print("\nUsage:")
        print("  python3 claude_auto_integration.py --check")
        print("  python3 claude_auto_integration.py --execute 'Your task here'")
        print("  python3 claude_auto_integration.py --stats")
        print("  python3 claude_auto_integration.py --recent [N]")


if __name__ == "__main__":
    main()
