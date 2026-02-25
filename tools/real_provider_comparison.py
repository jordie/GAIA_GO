#!/usr/bin/env python3
"""
Real provider comparison by sending prompts through assigner worker.

This bypasses gaia CLI and sends prompts directly to tmux sessions
via the assigner worker, capturing full responses.
"""

import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional


class RealProviderComparison:
    """Compare providers using assigner worker."""

    PROMPTS = {
        "quick": [
            ("hello", "Say hello"),
            ("python_intro", "What is Python in 2-3 sentences?"),
            ("function", "Write a Python function that adds two numbers"),
        ],
        "moderate": [
            (
                "api_design",
                "Design a REST API for a simple todo app. List 4 endpoints with methods.",
            ),
            (
                "code_review",
                "Review this code: `def find_duplicate(arr):\n  seen = set()\n  for num in arr:\n    if num in seen:\n      return num\n    seen.add(num)`. What's wrong?",
            ),
            (
                "optimization",
                "How would you optimize processing 1 million items in Python? List 3 approaches.",
            ),
        ],
    }

    def __init__(self):
        self.results = []

    def send_via_assigner(self, provider: str, prompt: str, timeout: int = 60) -> Dict:
        """Send prompt via assigner worker and get results."""
        start = time.time()

        try:
            # Send prompt to assigner
            result = subprocess.run(
                [
                    "python3",
                    "workers/assigner_worker.py",
                    "--send",
                    prompt,
                    "--provider",
                    provider,
                    "--timeout",
                    str(timeout),
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 10,
            )

            duration = time.time() - start
            output = result.stdout + result.stderr

            # Parse output to check success
            success = result.returncode == 0 and "success" in output.lower()

            return {
                "success": success,
                "duration": duration,
                "response_length": len(output),
                "output_sample": output[:200],
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "duration": time.time() - start,
                "response_length": 0,
                "output_sample": "Timeout",
            }
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start,
                "response_length": 0,
                "output_sample": str(e)[:100],
            }

    def run_comparison(
        self,
        providers: List[str],
        complexity: str = "quick",
        limit: int = None,
    ) -> None:
        """Run comparison across providers."""
        prompts = self.PROMPTS.get(complexity, self.PROMPTS["quick"])
        if limit:
            prompts = prompts[:limit]

        print(f"\n{'='*80}")
        print(f"Real Provider Comparison (via Assigner)")
        print(f"Providers: {', '.join(providers)}")
        print(f"Complexity: {complexity}")
        print(f"Tests: {len(prompts)}")
        print(f"{'='*80}\n")

        for test_name, prompt in prompts:
            print(f"Test: {test_name}")
            print(f"Prompt: {prompt[:70]}...")
            print()

            test_results = {
                "test_name": test_name,
                "prompt_length": len(prompt),
                "timestamp": datetime.now().isoformat(),
                "providers": {},
            }

            for provider in providers:
                print(f"  {provider:12} ", end="", flush=True)
                result = self.send_via_assigner(provider, prompt)
                test_results["providers"][provider] = result

                if result["success"]:
                    status = "✓"
                    msg = f"{result['duration']:.2f}s"
                else:
                    status = "✗"
                    msg = result["output_sample"]

                print(f"{status} {msg}")

            print()
            self.results.append(test_results)

    def print_summary(self) -> None:
        """Print summary statistics."""
        if not self.results:
            return

        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}\n")

        providers = set()
        for result in self.results:
            providers.update(result["providers"].keys())

        summary = {
            p: {"success": 0, "total": 0, "avg_duration": 0, "total_duration": 0} for p in providers
        }

        for result in self.results:
            for provider, provider_result in result["providers"].items():
                if provider_result["success"]:
                    summary[provider]["success"] += 1
                    summary[provider]["total_duration"] += provider_result["duration"]
                summary[provider]["total"] += 1

        # Calculate averages
        for provider in summary:
            if summary[provider]["total"] > 0:
                summary[provider]["avg_duration"] = (
                    summary[provider]["total_duration"] / summary[provider]["total"]
                )

        # Print table
        print(f"{'Provider':<15} {'Success':<12} {'Avg Time':<15} {'Tests':<10}")
        print("-" * 52)

        for provider in sorted(providers):
            s = summary[provider]
            success_rate = f"{(s['success']/s['total']*100):.0f}%"
            avg_time = f"{s['avg_duration']:.2f}s"
            tests = f"{s['success']}/{s['total']}"
            print(f"{provider:<15} {success_rate:<12} {avg_time:<15} {tests:<10}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Real provider comparison")
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["claude", "gemini", "ollama", "codex"],
        help="Providers to test",
    )
    parser.add_argument(
        "--complexity",
        choices=["quick", "moderate"],
        default="quick",
        help="Test complexity",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit tests",
    )

    args = parser.parse_args()

    comp = RealProviderComparison()
    comp.run_comparison(
        providers=args.providers,
        complexity=args.complexity,
        limit=args.limit,
    )
    comp.print_summary()


if __name__ == "__main__":
    main()
