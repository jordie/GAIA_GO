#!/usr/bin/env python3
"""
Comet Auto-Integration - Automated task execution via Comet browser

Uses AppleScript to automate Comet browser interactions:
- Send queries to Comet
- Wait for responses
- Scrape results
- Store in database

Usage:
    from comet_auto_integration import CometIntegration

    comet = CometIntegration()
    result = comet.execute_task("What is quantum computing?")
    print(result['response'])
"""

import json
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Database setup
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "comet_integration"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "comet_results.db"


class CometIntegration:
    """Automated integration with Comet browser via AppleScript."""

    def __init__(self, browser_name: str = "Comet"):
        """
        Initialize Comet integration.

        Args:
            browser_name: Name of the Comet browser application
        """
        self.browser_name = browser_name
        self.db_path = DB_PATH
        self.init_database()

    def init_database(self):
        """Initialize SQLite database for storing results."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comet_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                html_content TEXT,
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
                FOREIGN KEY (result_id) REFERENCES comet_results(id)
            )
        """)

        conn.commit()
        conn.close()

    def check_browser_running(self) -> bool:
        """Check if Comet browser is running."""
        try:
            script = f'''
            tell application "System Events"
                return exists (processes where name is "{self.browser_name}")
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )

            return result.stdout.strip() == "true"

        except Exception as e:
            print(f"Error checking browser: {e}")
            return False

    def launch_browser(self) -> bool:
        """Launch Comet browser if not running."""
        try:
            script = f'''
            tell application "{self.browser_name}"
                activate
            end tell
            '''

            subprocess.run(
                ["osascript", "-e", script],
                timeout=10
            )

            # Wait for browser to launch
            time.sleep(2)
            return self.check_browser_running()

        except Exception as e:
            print(f"Error launching browser: {e}")
            return False

    def send_query(self, query: str) -> bool:
        """
        Send a query to Comet browser.

        Args:
            query: The query to send

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure browser is running
            if not self.check_browser_running():
                if not self.launch_browser():
                    return False

            # AppleScript to send query
            script = f'''
            tell application "{self.browser_name}"
                activate
                delay 0.5

                -- Focus on search/input field (adjust based on Comet's UI)
                tell application "System Events"
                    keystroke "n" using command down
                    delay 0.5
                    keystroke "{query}"
                    delay 0.3
                    keystroke return
                end tell
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=15
            )

            return result.returncode == 0

        except Exception as e:
            print(f"Error sending query: {e}")
            return False

    def wait_for_response(self, timeout: int = 60) -> bool:
        """
        Wait for Comet to finish generating response.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if response ready, False if timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            # Check if response is complete
            # This would need to be customized based on Comet's UI indicators
            # For now, we'll use a simple time-based approach

            time.sleep(2)

            # Check for completion indicators via AppleScript
            # (This is a placeholder - would need actual UI inspection)
            if (time.time() - start_time) > 10:  # Assume done after 10s
                return True

        return False

    def scrape_response(self) -> Optional[str]:
        """
        Scrape the response from Comet browser.

        Returns:
            Response text or None if failed
        """
        try:
            # AppleScript to get visible text from Comet
            script = f'''
            tell application "{self.browser_name}"
                activate
                delay 0.5

                tell application "System Events"
                    -- Select all text
                    keystroke "a" using command down
                    delay 0.3

                    -- Copy to clipboard
                    keystroke "c" using command down
                    delay 0.5
                end tell
            end tell

            -- Get clipboard content
            the clipboard as text
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None

        except Exception as e:
            print(f"Error scraping response: {e}")
            return None

    def scrape_html(self) -> Optional[str]:
        """
        Scrape HTML content from Comet browser.

        This uses more advanced AppleScript to access the DOM if possible.

        Returns:
            HTML content or None if failed
        """
        # This is a placeholder - actual implementation would depend on
        # whether Comet exposes AppleScript access to HTML/DOM
        # For now, we'll return None and rely on text scraping
        return None

    def execute_task(self, query: str, timeout: int = 60) -> Optional[Dict]:
        """
        High-level method to execute a query and get results.

        Args:
            query: The query for Comet
            timeout: Maximum seconds to wait

        Returns:
            Dictionary with results or None if failed
        """
        print(f"📤 Sending query to Comet: {query[:100]}...")
        start_time = time.time()

        # Send query
        if not self.send_query(query):
            print("❌ Failed to send query to Comet")
            return {
                "status": "error",
                "error": "Failed to send query to browser"
            }

        # Wait for response
        print("⏳ Waiting for response...")
        if not self.wait_for_response(timeout=timeout):
            print("⏱️  Timeout waiting for response")
            return {
                "status": "timeout",
                "message": f"No response after {timeout}s"
            }

        # Scrape response
        print("📥 Scraping response...")
        response = self.scrape_response()
        html = self.scrape_html()

        execution_time = time.time() - start_time

        if response:
            # Clean the response
            cleaned_response = self._clean_response(response, query)

            # Save to database
            result_id = self._save_result(
                query=query,
                response=cleaned_response,
                html_content=html,
                execution_time=execution_time
            )

            print(f"✅ Response received in {execution_time:.1f}s")

            return {
                "status": "success",
                "query": query,
                "response": cleaned_response,
                "html": html,
                "execution_time": execution_time,
                "result_id": result_id
            }
        else:
            print("❌ Failed to scrape response")
            return {
                "status": "error",
                "error": "Failed to scrape response from browser"
            }

    def _clean_response(self, raw_response: str, query: str) -> str:
        """
        Clean the scraped response to extract just the answer.

        Args:
            raw_response: Raw text from clipboard
            query: Original query (to help identify the answer portion)

        Returns:
            Cleaned response text
        """
        # Remove UI elements and controls
        lines = raw_response.split('\n')
        cleaned_lines = []

        for line in lines:
            # Skip common UI elements
            if any(skip in line.lower() for skip in [
                'new chat',
                'settings',
                'history',
                'menu',
                'toolbar',
                query.lower()  # Skip the query echo
            ]):
                continue

            # Skip very short lines (likely UI)
            if len(line.strip()) < 10:
                continue

            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines).strip()

    def _save_result(self, query: str, response: str, html_content: Optional[str],
                     execution_time: float) -> int:
        """
        Save result to database.

        Returns:
            Result ID
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Estimate tokens
        tokens_estimate = (len(query) + len(response)) // 4

        cursor.execute("""
            INSERT INTO comet_results
            (query, response, html_content, execution_time_seconds,
             tokens_estimate, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            query,
            response,
            html_content,
            execution_time,
            tokens_estimate,
            json.dumps({'version': '1.0', 'browser': self.browser_name})
        ))

        result_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return result_id

    def get_recent_results(self, limit: int = 10) -> List[Dict]:
        """Get recent results from database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM comet_results
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = dict(row)
            if result['metadata']:
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)

        return results

    def get_stats(self) -> Dict:
        """Get statistics about Comet executions."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM comet_results")
        total_results = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(execution_time_seconds) FROM comet_results")
        avg_time = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(tokens_estimate) FROM comet_results")
        total_tokens = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(*) FROM comet_results
            WHERE created_at >= datetime('now', '-24 hours')
        """)
        results_24h = cursor.fetchone()[0]

        conn.close()

        return {
            'total_results': total_results,
            'avg_execution_time': round(avg_time, 2),
            'total_tokens_estimate': total_tokens,
            'results_last_24h': results_24h,
            'browser_running': self.check_browser_running()
        }


def main():
    """CLI interface for testing."""
    import sys

    comet = CometIntegration()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == '--check':
            # Check if browser is running
            running = comet.check_browser_running()
            print(f"Comet browser running: {running}")

        elif command == '--launch':
            # Launch browser
            success = comet.launch_browser()
            print(f"Launch {'successful' if success else 'failed'}")

        elif command == '--execute':
            # Execute a query
            if len(sys.argv) < 3:
                print("Usage: --execute '<query>'")
                sys.exit(1)

            query = sys.argv[2]
            result = comet.execute_task(query)

            if result and result['status'] == 'success':
                print("\n" + "="*80)
                print("RESPONSE:")
                print("="*80)
                print(result['response'])

        elif command == '--stats':
            # Show statistics
            stats = comet.get_stats()
            print(json.dumps(stats, indent=2))

        elif command == '--recent':
            # Show recent results
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            results = comet.get_recent_results(limit=limit)

            for i, result in enumerate(results, 1):
                print(f"\n{'='*80}")
                print(f"Result {i} (ID: {result['id']})")
                print(f"{'='*80}")
                print(f"Query: {result['query'][:100]}...")
                print(f"Time: {result['execution_time_seconds']:.1f}s")
                print(f"Created: {result['created_at']}")

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("Comet Auto-Integration")
        print("\nUsage:")
        print("  python3 comet_auto_integration.py --check")
        print("  python3 comet_auto_integration.py --launch")
        print("  python3 comet_auto_integration.py --execute '<query>'")
        print("  python3 comet_auto_integration.py --stats")
        print("  python3 comet_auto_integration.py --recent [N]")


if __name__ == "__main__":
    main()
