#!/usr/bin/env python3
"""
Quick comparison of gaia providers using tmux sessions.

Instead of making API calls directly, this routes prompts through
existing gaia sessions to compare real-world performance.

Usage:
    python3 tools/gaia_provider_test.py
    python3 tools/gaia_provider_test.py --sessions gaia_claude_1 gaia_gemini_1 --quick
"""

import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional


class GaiaProviderComparison:
    """Compare providers using existing gaia tmux sessions."""

    # Test prompts at different complexities
    PROMPTS = {
        "quick": [
            ("hello", "Hello, respond with 'Hello back!'"),
            ("python", "What is Python in one sentence?"),
            ("function", "Write a simple Python 'hello world' function"),
        ],
        "moderate": [
            (
                "api_design",
                "Design a simple REST API for a todo app. List 3-4 endpoints.",
            ),
            (
                "bug",
                "There's a Python bug: `def f(): x = []; [x.append(i) for i in range(3)]; return x`. What's wrong?",
            ),
            (
                "optimization",
                "How would you optimize a loop processing 1 million items?",
            ),
        ],
        "complex": [
            (
                "architecture",
                "Design a scalable caching system. Describe data structures, consistency model, and failure handling.",
            ),
            (
                "algorithm",
                "Implement Dijkstra's algorithm and explain time complexity.",
            ),
        ],
    }

    def __init__(self):
        self.results = []

    def get_available_sessions(self) -> List[str]:
        """Get list of available tmux sessions."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
            )
            return result.stdout.strip().split("\n")
        except Exception as e:
            print(f"Error getting sessions: {e}")
            return []

    def send_prompt_to_session(self, session: str, prompt: str, timeout: int = 30) -> Dict:
        """Send a prompt to a gaia session and capture response."""
        start = time.time()

        try:
            # Send prompt
            subprocess.run(
                ["tmux", "send-keys", "-t", session, prompt, "Enter"],
                check=True,
                timeout=5,
            )

            # Wait for response (simplified - just wait for timeout)
            time.sleep(timeout)

            # Capture output
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            duration = time.time() - start
            response = result.stdout

            return {
                "success": True,
                "duration": duration,
                "response_length": len(response),
                "sample": response[-200:],  # Last 200 chars
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "duration": time.time() - start,
                "error": "Timeout",
            }
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start,
                "error": str(e),
            }

    def compare_providers(
        self,
        sessions: Optional[List[str]] = None,
        complexity: str = "quick",
        limit: int = None,
    ) -> None:
        """Run comparison across providers."""
        if not sessions:
            # Auto-detect gaia sessions
            available = self.get_available_sessions()
            sessions = [s for s in available if "gaia" in s.lower()]

        if not sessions:
            print("No gaia sessions found. Please start some first:")
            print("  tmux new-session -d -s gaia_claude_1 'gaia --provider claude'")
            print("  tmux new-session -d -s gaia_gemini_1 'gaia --provider gemini'")
            print("  tmux new-session -d -s gaia_ollama_1 'gaia --provider ollama'")
            return

        prompts = self.PROMPTS.get(complexity, self.PROMPTS["quick"])
        if limit:
            prompts = prompts[:limit]

        print(f"\n{'='*70}")
        print(f"Gaia Provider Comparison")
        print(f"Sessions: {', '.join(sessions)}")
        print(f"Complexity: {complexity}")
        print(f"Tests: {len(prompts)}")
        print(f"{'='*70}\n")

        for test_name, prompt in prompts:
            print(f"Test: {test_name}")
            print(f"Prompt: {prompt[:60]}...")
            print()

            test_results = {
                "test_name": test_name,
                "prompt": prompt,
                "timestamp": datetime.now().isoformat(),
                "providers": {},
            }

            for session in sessions:
                result = self.send_prompt_to_session(session, prompt)
                test_results["providers"][session] = result

                status = "✓" if result["success"] else "✗"
                duration = f"{result['duration']:.1f}s"
                response_len = (
                    f"{result['response_length']} chars"
                    if result["success"]
                    else result.get("error", "error")
                )

                print(f"  {status} {session:20} {duration:10} {response_len}")

            print()
            self.results.append(test_results)

    def print_summary(self) -> None:
        """Print summary statistics."""
        if not self.results:
            return

        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}\n")

        sessions = set()
        for result in self.results:
            sessions.update(result["providers"].keys())

        summary = {s: {"success": 0, "avg_duration": 0, "total": 0} for s in sessions}

        for result in self.results:
            for session, provider_result in result["providers"].items():
                if provider_result["success"]:
                    summary[session]["success"] += 1
                    summary[session]["avg_duration"] += provider_result["duration"]
                summary[session]["total"] += 1

        # Calculate averages
        for session in summary:
            if summary[session]["total"] > 0:
                summary[session]["avg_duration"] /= summary[session]["total"]

        # Print table
        print(f"{'Session':<20} {'Success Rate':<15} {'Avg Time':<15}")
        print("-" * 50)

        for session in sorted(sessions):
            s = summary[session]
            success_rate = f"{(s['success']/s['total']*100):.0f}%"
            avg_time = f"{s['avg_duration']:.1f}s"
            print(f"{session:<20} {success_rate:<15} {avg_time:<15}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compare gaia providers")
    parser.add_argument(
        "--sessions",
        nargs="+",
        help="Session names to test",
    )
    parser.add_argument(
        "--complexity",
        choices=["quick", "moderate", "complex"],
        default="quick",
        help="Test complexity level",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of tests",
    )

    args = parser.parse_args()

    comp = GaiaProviderComparison()
    comp.compare_providers(
        sessions=args.sessions,
        complexity=args.complexity,
        limit=args.limit,
    )
    comp.print_summary()


if __name__ == "__main__":
    main()
