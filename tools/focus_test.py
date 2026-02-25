#!/usr/bin/env python3
"""
Test which provider stays most focused on the prompt.

Send the same specific prompt to each provider and evaluate focus level.
"""

import subprocess
import time
from datetime import datetime


class FocusTest:
    """Test provider focus."""

    # Very specific, focused prompts
    TEST_CASES = [
        {
            "name": "api_endpoints",
            "prompt": "List exactly 3 REST API endpoints for a todo app. Format: METHOD /path - description",
            "expected_focus": ["3 endpoints", "REST API", "todo", "METHOD", "/path"],
            "off_topic_signs": [
                "database",
                "authentication",
                "deployment",
                "testing",
                "frontend",
            ],
        },
        {
            "name": "function_write",
            "prompt": "Write ONLY a Python function that adds two numbers. No explanation, just code.",
            "expected_focus": ["def ", "return", "+", "()"],
            "off_topic_signs": [
                "explanation",
                "tutorial",
                "import",
                "class",
                "if __name__",
            ],
        },
        {
            "name": "bug_fix",
            "prompt": "This code has a bug: x = [1,2,3]; print(x[10]). What is the bug? Answer in 1 sentence.",
            "expected_focus": ["IndexError", "range", "index", "1 sentence"],
            "off_topic_signs": ["how to fix", "best practices", "exception handling"],
        },
    ]

    def __init__(self):
        self.results = []

    def evaluate_focus(self, prompt: str, response: str, case: dict) -> dict:
        """Evaluate how focused the response is."""
        response_lower = response.lower()

        # Count expected focus terms
        focus_hits = sum(1 for term in case["expected_focus"] if term.lower() in response_lower)

        # Count off-topic terms
        off_topic_hits = sum(
            1 for term in case["off_topic_signs"] if term.lower() in response_lower
        )

        # Calculate focus score
        total_expected = len(case["expected_focus"])
        focus_score = (focus_hits / total_expected * 100) if total_expected > 0 else 0

        # Penalize off-topic content
        off_topic_penalty = off_topic_hits * 10

        final_score = max(0, focus_score - off_topic_penalty)

        return {
            "focus_score": focus_score,
            "off_topic_penalty": off_topic_penalty,
            "final_score": final_score,
            "focus_hits": focus_hits,
            "off_topic_hits": off_topic_hits,
            "response_length": len(response),
            "response_sample": response[:150] + "..." if len(response) > 150 else response,
        }

    def test_provider(self, provider: str, prompt: str) -> dict:
        """Test provider with prompt."""
        start = time.time()

        try:
            result = subprocess.run(
                ["gaia", "--provider", provider, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )

            duration = time.time() - start

            # Get full output
            output = result.stdout + result.stderr

            return {
                "success": True,
                "duration": duration,
                "output": output,
                "return_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "duration": time.time() - start,
                "output": "Timeout",
                "error": "Timeout",
            }
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start,
                "output": str(e),
                "error": str(e),
            }

    def run_focus_test(self, providers=None, test_case=None):
        """Run focus test."""
        if not providers:
            providers = ["claude", "gemini", "ollama", "codex"]

        if not test_case:
            test_case = self.TEST_CASES[0]

        print(f"\n{'='*80}")
        print(f"FOCUS TEST: {test_case['name']}")
        print(f"{'='*80}")
        print(f"\nPrompt: {test_case['prompt']}\n")

        focus_results = {}

        for provider in providers:
            print(f"Testing {provider}...", end=" ", flush=True)

            # Send prompt
            result = self.test_provider(provider, test_case["prompt"])

            if not result["success"]:
                print(f"✗ Failed: {result.get('error', 'Unknown error')}")
                focus_results[provider] = {
                    "success": False,
                    "error": result.get("error"),
                }
                continue

            # Note: gaia -p returns immediately, we're just checking it ran
            print(f"✓ Prompt sent")

            # For real comparison, we'd need to wait and capture from tmux
            focus_results[provider] = {
                "success": True,
                "duration": result["duration"],
                "note": "Sent to provider session (check tmux for full response)",
            }

        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}\n")

        for provider, result in focus_results.items():
            if result["success"]:
                print(f"✓ {provider:10} - Ready for manual evaluation")
            else:
                print(f"✗ {provider:10} - {result.get('error', 'Failed')}")

        print(f"\n{'='*80}")
        print("NEXT STEPS")
        print(f"{'='*80}\n")
        print("1. Open: tmux attach-session -t comparison")
        print("2. Test each provider manually with this prompt:")
        print(f'   "{test_case["prompt"]}"')
        print(f"\n3. Evaluate focus using this criteria:")
        print(f"   Expected terms: {', '.join(test_case['expected_focus'])}")
        print(f"   Off-topic signs: {', '.join(test_case['off_topic_signs'])}")
        print("\n4. Score (0-100):")
        print("   - 90-100: Laser-focused, perfect answer")
        print("   - 70-89:  Mostly focused, minor tangents")
        print("   - 50-69:  On-topic, some drift")
        print("   - Below 50: Unfocused, lots of extra info")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test provider focus")
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["claude", "gemini", "ollama", "codex"],
        help="Providers to test",
    )
    parser.add_argument(
        "--test",
        choices=["api_endpoints", "function_write", "bug_fix"],
        default="api_endpoints",
        help="Test case",
    )

    args = parser.parse_args()

    test = FocusTest()

    # Find the test case
    case = next((c for c in test.TEST_CASES if c["name"] == args.test), None)
    if not case:
        print(f"Test case '{args.test}' not found")
        return

    test.run_focus_test(providers=args.providers, test_case=case)


if __name__ == "__main__":
    main()
