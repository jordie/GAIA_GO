#!/usr/bin/env python3
"""
Local LLM Service

A unified service for interacting with local LLMs (Ollama, AnythingLLM)
for code generation, documentation, decision making, and assistance.

Usage:
    from services.local_llm_service import LocalLLMService

    llm = LocalLLMService()

    # Code generation
    code = llm.generate_code("Create a Python function to parse JSON")

    # Documentation
    docs = llm.generate_docs(code_snippet, style="technical")

    # Decision making
    decision = llm.make_decision(
        context="User wants to add authentication",
        options=["OAuth", "JWT", "Session-based"],
        criteria=["Security", "Ease of use", "Scalability"]
    )

    # General chat
    response = llm.chat("Explain how async/await works in Python")
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests

# Setup paths
SERVICE_DIR = Path(__file__).parent
BASE_DIR = SERVICE_DIR.parent
sys.path.insert(0, str(BASE_DIR))


@dataclass
class LLMResponse:
    """Response from LLM."""

    text: str
    model: str
    provider: str
    tokens: int
    elapsed_seconds: float
    success: bool
    error: Optional[str] = None


class LocalLLMService:
    """Service for interacting with local LLMs."""

    def __init__(self, ollama_host: str = None, ollama_model: str = None, timeout: int = 60):
        """
        Initialize Local LLM Service.

        Args:
            ollama_host: Ollama server URL (default: OLLAMA_HOST env or http://localhost:11434)
            ollama_model: Model to use (default: OLLAMA_MODEL env or llama3.2)
            timeout: Request timeout in seconds (default: 60)
        """
        self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.timeout = timeout

    def _call_ollama(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> LLMResponse:
        """
        Call Ollama API.

        Args:
            prompt: The prompt to send
            system: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            stream: Whether to stream the response

        Returns:
            LLMResponse object
        """
        start_time = time.time()

        try:
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": stream,
                "options": {"temperature": temperature},
            }

            if system:
                payload["system"] = system

            response = requests.post(
                f"{self.ollama_host}/api/generate", json=payload, timeout=self.timeout
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "").strip()

                return LLMResponse(
                    text=text,
                    model=self.ollama_model,
                    provider="ollama",
                    tokens=result.get("eval_count", 0),
                    elapsed_seconds=round(elapsed, 2),
                    success=True,
                )
            else:
                return LLMResponse(
                    text="",
                    model=self.ollama_model,
                    provider="ollama",
                    tokens=0,
                    elapsed_seconds=round(elapsed, 2),
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                )

        except requests.Timeout:
            return LLMResponse(
                text="",
                model=self.ollama_model,
                provider="ollama",
                tokens=0,
                elapsed_seconds=self.timeout,
                success=False,
                error=f"Timeout after {self.timeout}s",
            )
        except Exception as e:
            return LLMResponse(
                text="",
                model=self.ollama_model,
                provider="ollama",
                tokens=0,
                elapsed_seconds=time.time() - start_time,
                success=False,
                error=str(e),
            )

    def chat(
        self, message: str, context: Optional[str] = None, temperature: float = 0.7
    ) -> LLMResponse:
        """
        General chat with LLM.

        Args:
            message: The message/question to ask
            context: Optional context to provide
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            LLMResponse object
        """
        if context:
            prompt = f"Context:\n{context}\n\nQuestion:\n{message}"
        else:
            prompt = message

        return self._call_ollama(prompt, temperature=temperature)

    def generate_code(
        self,
        description: str,
        language: str = "python",
        context: Optional[str] = None,
        style: Literal["concise", "detailed", "with_comments"] = "detailed",
    ) -> LLMResponse:
        """
        Generate code based on description.

        Args:
            description: What the code should do
            language: Programming language (default: python)
            context: Optional context (existing code, requirements, etc.)
            style: Code style preference

        Returns:
            LLMResponse with generated code
        """
        style_instructions = {
            "concise": "Write concise code with minimal comments.",
            "detailed": "Write well-structured code with clear variable names.",
            "with_comments": "Write code with detailed comments explaining each section.",
        }

        system_prompt = f"""You are an expert {language} programmer.
Generate clean, efficient, production-ready code.
{style_instructions.get(style, style_instructions['detailed'])}
Only output the code, no explanations unless requested."""

        prompt = f"Create {language} code for:\n{description}"

        if context:
            prompt = f"Context:\n{context}\n\n{prompt}"

        return self._call_ollama(prompt, system=system_prompt, temperature=0.3)

    def generate_docs(
        self,
        code: str,
        style: Literal["technical", "user_guide", "api", "inline"] = "technical",
        format: Literal["markdown", "plain", "html"] = "markdown",
    ) -> LLMResponse:
        """
        Generate documentation for code.

        Args:
            code: The code to document
            style: Documentation style
            format: Output format

        Returns:
            LLMResponse with generated documentation
        """
        style_prompts = {
            "technical": "Create comprehensive technical documentation with architecture and implementation details.",
            "user_guide": "Create a clear, beginner-friendly user guide.",
            "api": "Create API documentation with endpoints, parameters, and examples.",
            "inline": "Add inline comments and docstrings to the code.",
        }

        system_prompt = (
            f"You are a technical writer creating {style} documentation in {format} format."
        )

        prompt = f"""{style_prompts.get(style, style_prompts['technical'])}

Code:
```
{code}
```

Generate documentation now:"""

        return self._call_ollama(prompt, system=system_prompt, temperature=0.5)

    def make_decision(
        self,
        context: str,
        options: List[str],
        criteria: Optional[List[str]] = None,
        return_json: bool = True,
    ) -> LLMResponse:
        """
        Help make a decision between options.

        Args:
            context: The situation/problem description
            options: List of possible options
            criteria: Optional list of criteria to evaluate against
            return_json: Whether to return structured JSON response

        Returns:
            LLMResponse with recommendation
        """
        system_prompt = "You are a decision-making assistant. Analyze options objectively and provide clear recommendations."

        prompt = f"""Context: {context}

Options:
"""
        for i, option in enumerate(options, 1):
            prompt += f"{i}. {option}\n"

        if criteria:
            prompt += f"\nEvaluation Criteria:\n"
            for criterion in criteria:
                prompt += f"- {criterion}\n"

        if return_json:
            prompt += """
Respond with JSON:
{
  "recommended": "option name",
  "reasoning": "why this is best",
  "trade_offs": "what you're giving up",
  "alternatives": ["alternative 1", "alternative 2"]
}"""
        else:
            prompt += "\nProvide your recommendation with reasoning:"

        return self._call_ollama(prompt, system=system_prompt, temperature=0.5)

    def analyze_error(
        self,
        error_message: str,
        stack_trace: Optional[str] = None,
        code_context: Optional[str] = None,
    ) -> LLMResponse:
        """
        Analyze an error and suggest fixes.

        Args:
            error_message: The error message
            stack_trace: Optional stack trace
            code_context: Optional relevant code

        Returns:
            LLMResponse with analysis and suggestions
        """
        system_prompt = (
            "You are a debugging expert. Analyze errors and provide actionable solutions."
        )

        prompt = f"Error: {error_message}"

        if stack_trace:
            prompt += f"\n\nStack Trace:\n{stack_trace}"

        if code_context:
            prompt += f"\n\nCode Context:\n```\n{code_context}\n```"

        prompt += "\n\nProvide:\n1. Root cause analysis\n2. Suggested fix\n3. Prevention tips"

        return self._call_ollama(prompt, system=system_prompt, temperature=0.3)

    def review_code(
        self, code: str, focus: Literal["security", "performance", "style", "all"] = "all"
    ) -> LLMResponse:
        """
        Review code for issues and improvements.

        Args:
            code: The code to review
            focus: What to focus the review on

        Returns:
            LLMResponse with review feedback
        """
        focus_prompts = {
            "security": "Focus on security vulnerabilities and best practices.",
            "performance": "Focus on performance optimization opportunities.",
            "style": "Focus on code style, readability, and maintainability.",
            "all": "Comprehensive review covering security, performance, and style.",
        }

        system_prompt = f"""You are a senior code reviewer.
{focus_prompts.get(focus, focus_prompts['all'])}
Be constructive and specific."""

        prompt = f"""Review this code:

```
{code}
```

Provide:
1. Issues found (if any)
2. Suggested improvements
3. Best practices to follow"""

        return self._call_ollama(prompt, system=system_prompt, temperature=0.4)

    def explain_code(
        self, code: str, audience: Literal["beginner", "intermediate", "expert"] = "intermediate"
    ) -> LLMResponse:
        """
        Explain what code does.

        Args:
            code: The code to explain
            audience: Target audience level

        Returns:
            LLMResponse with explanation
        """
        audience_styles = {
            "beginner": "Explain in simple terms for someone new to programming.",
            "intermediate": "Explain clearly with some technical detail.",
            "expert": "Provide concise technical explanation focusing on implementation details.",
        }

        system_prompt = f"You are a programming instructor. {audience_styles.get(audience, audience_styles['intermediate'])}"

        prompt = f"""Explain this code:

```
{code}
```"""

        return self._call_ollama(prompt, system=system_prompt, temperature=0.5)

    def refactor_suggestion(
        self, code: str, goal: Literal["simplify", "optimize", "modernize"] = "simplify"
    ) -> LLMResponse:
        """
        Suggest refactoring for code.

        Args:
            code: The code to refactor
            goal: Refactoring goal

        Returns:
            LLMResponse with refactored code and explanation
        """
        goal_prompts = {
            "simplify": "Simplify the code to make it more readable and maintainable.",
            "optimize": "Optimize for better performance and resource usage.",
            "modernize": "Update to use modern language features and best practices.",
        }

        system_prompt = (
            f"You are a refactoring expert. {goal_prompts.get(goal, goal_prompts['simplify'])}"
        )

        prompt = f"""Refactor this code:

```
{code}
```

Provide:
1. Refactored code
2. Explanation of changes
3. Benefits of the refactoring"""

        return self._call_ollama(prompt, system=system_prompt, temperature=0.4)

    def test_ollama_connection(self) -> Dict[str, Any]:
        """
        Test connection to Ollama server.

        Returns:
            Dictionary with connection status and available models
        """
        try:
            # Try to list models
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]

                return {
                    "success": True,
                    "host": self.ollama_host,
                    "available_models": model_names,
                    "selected_model": self.ollama_model,
                    "model_available": self.ollama_model in model_names
                    or any(self.ollama_model in m for m in model_names),
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "host": self.ollama_host,
                }

        except Exception as e:
            return {"success": False, "error": str(e), "host": self.ollama_host}


def main():
    """CLI for testing local LLM service."""
    import argparse

    parser = argparse.ArgumentParser(description="Local LLM Service CLI")
    parser.add_argument(
        "command",
        choices=[
            "chat",
            "code",
            "docs",
            "decide",
            "error",
            "review",
            "explain",
            "refactor",
            "test",
        ],
        help="Command to run",
    )
    parser.add_argument("input", nargs="?", help="Input text or file")
    parser.add_argument("--file", action="store_true", help="Input is a file path")
    parser.add_argument("--language", default="python", help="Programming language")
    parser.add_argument("--style", help="Output style")
    parser.add_argument("--options", nargs="+", help="Decision options")
    parser.add_argument("--criteria", nargs="+", help="Decision criteria")

    args = parser.parse_args()

    llm = LocalLLMService()

    # Get input
    if args.file and args.input:
        with open(args.input, "r") as f:
            content = f.read()
    else:
        content = args.input or ""

    # Execute command
    response = None

    if args.command == "test":
        result = llm.test_ollama_connection()
        print(json.dumps(result, indent=2))
        return

    elif args.command == "chat":
        response = llm.chat(content)

    elif args.command == "code":
        response = llm.generate_code(content, language=args.language)

    elif args.command == "docs":
        response = llm.generate_docs(content, style=args.style or "technical")

    elif args.command == "decide":
        if not args.options:
            print("Error: --options required for decide command")
            return
        response = llm.make_decision(content, args.options, args.criteria)

    elif args.command == "error":
        response = llm.analyze_error(content)

    elif args.command == "review":
        response = llm.review_code(content, focus=args.style or "all")

    elif args.command == "explain":
        response = llm.explain_code(content)

    elif args.command == "refactor":
        response = llm.refactor_suggestion(content, goal=args.style or "simplify")

    # Print response
    if response:
        print(f"\n{'='*60}")
        print(f"Model: {response.model} ({response.provider})")
        print(f"Time: {response.elapsed_seconds}s | Tokens: {response.tokens}")
        print(f"{'='*60}\n")

        if response.success:
            print(response.text)
        else:
            print(f"❌ Error: {response.error}")

        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
