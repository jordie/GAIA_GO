#!/usr/bin/env python3
"""
Google Gemini AI Pro 2 Integration
Documentation generation, code analysis, and NotebookLM-style summaries
"""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    print("⚠️  Install: pip install google-generativeai")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))


class GeminiService:
    """Google Gemini AI service for documentation and analysis."""

    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not api_key:
            try:
                # Get from vault database directly
                import sqlite3

                conn = sqlite3.connect("data/architect.db")
                cursor = conn.cursor()
                cursor.execute("SELECT encrypted_value FROM secrets WHERE name = 'gemini_api_key'")
                result = cursor.fetchone()
                conn.close()
                if result:
                    api_key = result[0]  # Already decrypted/plain text
            except Exception as e:
                print(f"Warning: Could not retrieve from vault: {e}")
                pass

        if not api_key:
            raise ValueError(
                "No Gemini API key. Set GOOGLE_API_KEY or store in vault as 'gemini_api_key'"
            )

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def generate_documentation(self, content: str, doc_type: str = "technical") -> str:
        """Generate documentation using Gemini 2.0."""
        prompts = {
            "technical": (
                "Create comprehensive technical documentation with "
                "architecture, implementation, and examples:"
            ),
            "user_guide": "Create a clear user guide:",
            "api": (
                "Create complete API documentation with endpoints, "
                "parameters, and examples:"
            ),
            "sop": "Create a Standard Operating Procedure (SOP):",
        }

        prompt = f"{prompts.get(doc_type, prompts['technical'])}\n\n{content}"
        response = self.model.generate_content(prompt)
        return response.text

    def chat(self, message: str, context: Optional[str] = None) -> str:
        """Chat with Gemini."""
        full_message = f"{context}\n\n{message}" if context else message
        response = self.model.generate_content(full_message)
        return response.text


def main():
    """CLI for Gemini service."""
    import argparse

    parser = argparse.ArgumentParser(description="Google Gemini AI")
    parser.add_argument("command", choices=["doc", "chat"], help="Command")
    parser.add_argument("input", help="Input text or file")
    parser.add_argument("--type", default="technical", help="Documentation type")
    parser.add_argument("--output", help="Output file")

    args = parser.parse_args()

    gemini = GeminiService()

    if args.command == "doc":
        if Path(args.input).exists():
            with open(args.input, "r") as f:
                content = f.read()
        else:
            content = args.input

        result = gemini.generate_documentation(content, args.type)

        if args.output:
            with open(args.output, "w") as f:
                f.write(result)
            print(f"✅ Saved to {args.output}")
        else:
            print(result)

    elif args.command == "chat":
        result = gemini.chat(args.input)
        print(result)


if __name__ == "__main__":
    main()
