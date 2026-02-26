#!/usr/bin/env python3
"""
Codex Chat Worker

A Claude-powered chat worker that integrates with the Architect Dashboard's
session hierarchy system. Can run as:
- Interactive CLI chat interface
- Background worker receiving prompts from the assigner system
- tmux session worker detectable by the assigner

Part of the three-tier session hierarchy:
  High-Level → Manager (architect, wrapper_claude) → Worker (codex, dev_worker1, etc.)

Usage:
    # Interactive mode
    python3 codex_chat.py

    # Worker mode (for tmux sessions)
    python3 codex_chat.py --worker

    # Worker with custom session name
    python3 codex_chat.py --worker --session codex

    # Single command (non-interactive)
    python3 codex_chat.py -p ask "What is Python?"

    # Use specific provider
    python3 codex_chat.py --provider ollama

    # List available providers
    python3 codex_chat.py --list-providers
"""

import argparse
import datetime
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Import SessionStateManager for real-time monitoring
from workers.session_state_manager import SessionStateManager

# Worker configuration
WORKER_NAME = os.getenv("CODEX_WORKER_NAME", "codex")
STATE_FILE = Path(f"/tmp/codex_worker_{WORKER_NAME}_state.json")
HISTORY_FILE = SCRIPT_DIR / "data" / "codex" / f"{WORKER_NAME}_history.json"

# Ensure data directory exists
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)


class LLMBackend:
    """LLM backend with failover support.

    Default: Claude with automatic fallback to Ollama when approaching limits.
    Uses the rate limit handler to proactively switch at 80% of limit.
    """

    # Default provider order (Claude preferred, Ollama fallback)
    DEFAULT_PROVIDER_ORDER = ["claude", "ollama", "anythingllm", "gemini", "openai"]

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider  # None = auto-select based on rate limits
        self._client = None
        self._fallback_mode = False

    def _get_client(self):
        """Get or create the LLM client."""
        if self._client is None:
            try:
                from services.llm_provider import UnifiedLLMClient

                self._client = UnifiedLLMClient()

                # Check rate limits and set provider order
                try:
                    from services.rate_limit_handler import get_best_provider

                    best, endpoint = get_best_provider("claude")
                    if best == "ollama":
                        # Claude is limited, put Ollama first
                        self._client.failover_order = [
                            "ollama",
                            "claude",
                            "anythingllm",
                            "gemini",
                            "openai",
                        ]
                    else:
                        self._client.failover_order = self.DEFAULT_PROVIDER_ORDER.copy()
                except ImportError:
                    self._client.failover_order = self.DEFAULT_PROVIDER_ORDER.copy()

                # Override with explicit provider if specified
                if self.provider and self.provider in self._client.failover_order:
                    self._client.failover_order.remove(self.provider)
                    self._client.failover_order.insert(0, self.provider)
            except ImportError:
                self._fallback_mode = True
        return self._client

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> str:
        """Generate a response from the LLM."""
        messages = []

        # Add system message if provided
        if system:
            messages.append({"role": "user", "content": f"[System: {system}]"})
            messages.append({"role": "assistant", "content": "Understood."})

        # Add conversation history
        if history:
            messages.extend(history)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        if self._fallback_mode:
            return self._fallback_generate(prompt, system, history)

        client = self._get_client()
        if client is None:
            return self._fallback_generate(prompt, system, history)

        try:
            response = client.create(
                messages=messages,
                max_tokens=max_tokens,
                model=model,
            )
            # Extract text from response
            if hasattr(response, "content") and response.content:
                if isinstance(response.content, list):
                    # Handle list of content blocks
                    text_parts = []
                    for block in response.content:
                        if isinstance(block, dict) and "text" in block:
                            text_parts.append(block["text"])
                        elif hasattr(block, "text"):
                            text_parts.append(block.text)
                    return "\n".join(text_parts) if text_parts else str(response.content)
                return str(response.content)
            return "No response generated."
        except Exception as e:
            return f"Error generating response: {e}"

    def _fallback_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        """Fallback generation when LLM providers unavailable."""
        # Try direct Anthropic client
        try:
            import anthropic

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                client = anthropic.Anthropic(api_key=api_key)
                messages = []
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": prompt})

                response = client.messages.create(
                    model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
                    max_tokens=2048,
                    system=system or "You are a helpful coding assistant.",
                    messages=messages,
                )
                return response.content[0].text
        except Exception:
            pass

        # Try Ollama
        try:
            import requests

            endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})

            response = requests.post(
                f"{endpoint}/api/chat",
                json={
                    "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
                    "messages": messages,
                    "stream": False,
                },
                timeout=120,
            )
            if response.ok:
                return response.json().get("message", {}).get("content", "")
        except Exception:
            pass

        return "No LLM providers available. Please configure ANTHROPIC_API_KEY or ensure Ollama is running."

    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        client = self._get_client()
        if client and hasattr(client, "providers"):
            return list(client.providers.keys())
        return ["claude", "ollama", "openai", "gemini", "anythingllm"]


class ConversationManager:
    """Manages conversation history and persistence."""

    def __init__(self, session_name: str = "default"):
        self.session_name = session_name
        self.history: List[Dict[str, str]] = []
        self.history_file = SCRIPT_DIR / "data" / "codex" / f"{session_name}_history.json"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()

    def _load_history(self):
        """Load conversation history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    data = json.load(f)
                    self.history = data.get("messages", [])[-20:]  # Keep last 20 messages
            except (json.JSONDecodeError, IOError):
                self.history = []

    def save_history(self):
        """Save conversation history to file."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(
                    {
                        "session": self.session_name,
                        "updated_at": datetime.datetime.now().isoformat(),
                        "messages": self.history[-50:],  # Keep last 50 messages
                    },
                    f,
                    indent=2,
                )
        except IOError:
            pass

    def add_message(self, role: str, content: str):
        """Add a message to history."""
        self.history.append({"role": role, "content": content})
        self.save_history()

    def clear(self):
        """Clear conversation history."""
        self.history = []
        self.save_history()

    def get_context(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation context."""
        return self.history[-max_messages:]


class CodexWorker:
    """
    Codex Chat Worker for the Architect system.

    Integrates with:
    - Assigner worker (receives prompts via tmux)
    - Task queue (reports completion)
    - Session hierarchy (operates as worker level)
    """

    # Status patterns for tmux detection (from assigner_worker.py)
    IDLE_PROMPT = "codex> "
    BUSY_PREFIX = "Processing..."
    WORKING_PREFIX = "Working..."

    def __init__(
        self,
        session_name: str = "codex",
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        self.session_name = session_name
        self.llm = LLMBackend(provider=provider)
        self.conversation = ConversationManager(session_name)
        self.running = False
        self.current_task_id: Optional[int] = None

        self.system_prompt = system_prompt or self._default_system_prompt()

        # Session state management for real-time monitoring
        self.state_manager = SessionStateManager(session_name)
        self.state_manager.set_tool_info("codex_worker", "claude")

        # Built-in commands
        self.commands = {
            "help": self.cmd_help,
            "clear": self.cmd_clear,
            "history": self.cmd_history,
            "status": self.cmd_status,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
            "time": self.cmd_time,
            "date": self.cmd_date,
            "model": self.cmd_model,
            "providers": self.cmd_providers,
        }

    def _default_system_prompt(self) -> str:
        """Default system prompt for the worker."""
        return """You are Codex, a helpful coding assistant running as part of the Architect Dashboard system.

You help with:
- Writing and debugging code
- Explaining programming concepts
- Reviewing code for issues
- Suggesting improvements
- Answering technical questions

Keep responses concise and focused. Use code blocks with language tags for code examples.
When asked to perform tasks, complete them thoroughly and report when done."""

    def cmd_help(self, *args) -> str:
        """Show available commands."""
        return """Available commands:
  help      - Show this help message
  clear     - Clear conversation history
  history   - Show recent conversation history
  status    - Show worker status
  model     - Show/set current model
  providers - List available LLM providers
  time      - Show current time
  date      - Show current date
  exit/quit - Exit the chat

Any other input is sent to the LLM for processing."""

    def cmd_clear(self, *args) -> str:
        """Clear conversation history."""
        self.conversation.clear()
        return "Conversation history cleared."

    def cmd_history(self, *args) -> str:
        """Show conversation history."""
        history = self.conversation.get_context(max_messages=5)
        if not history:
            return "No conversation history."

        lines = ["Recent conversation:"]
        for msg in history:
            role = msg["role"].upper()
            content = msg["content"][:100]
            if len(msg["content"]) > 100:
                content += "..."
            lines.append(f"  [{role}] {content}")
        return "\n".join(lines)

    def cmd_status(self, *args) -> str:
        """Show worker status."""
        return f"""Codex Worker Status:
  Session: {self.session_name}
  Running: {self.running}
  Current Task: {self.current_task_id or 'None'}
  History Length: {len(self.conversation.history)}
  Provider: {self.llm.provider or 'auto (failover)'}"""

    def cmd_exit(self, *args) -> str:
        """Exit the chat."""
        self.running = False
        return "Goodbye!"

    def cmd_time(self, *args) -> str:
        """Show current time."""
        return f"Current time: {datetime.datetime.now().strftime('%H:%M:%S')}"

    def cmd_date(self, *args) -> str:
        """Show current date."""
        return f"Today's date: {datetime.date.today().strftime('%B %d, %Y')}"

    def cmd_model(self, *args) -> str:
        """Show or set current model."""
        if args:
            # Set model
            self.llm.provider = args[0]
            return f"Model set to: {args[0]}"
        return f"Current provider: {self.llm.provider or 'auto (failover)'}"

    def cmd_providers(self, *args) -> str:
        """List available providers."""
        providers = self.llm.get_available_providers()
        return "Available providers:\n  " + "\n  ".join(providers)

    def process_input(self, user_input: str) -> str:
        """Process user input and return response."""
        user_input = user_input.strip()

        if not user_input:
            return ""

        # Check for built-in commands
        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []

        if cmd in self.commands:
            return self.commands[cmd](*args)

        # Update session state: mark as working
        self.state_manager.set_task(f"Processing: {user_input[:80]}")
        self.state_manager.set_last_prompt(user_input)
        self.state_manager.increment_prompts()

        # Send to LLM
        print(self.WORKING_PREFIX, flush=True)

        response = self.llm.generate(
            prompt=user_input,
            system=self.system_prompt,
            history=self.conversation.get_context(),
        )

        # Update history
        self.conversation.add_message("user", user_input)
        self.conversation.add_message("assistant", response)

        return response

    def report_task_completion(self, task_id: int, response: str):
        """Report task completion to the assigner system."""
        try:
            from workers.assigner_worker import AssignerDatabase, PromptStatus

            db = AssignerDatabase()
            db.update_prompt_status(
                task_id,
                PromptStatus.COMPLETED,
                response=response[:1000],  # Truncate long responses
            )
            db.log_assignment(
                task_id, self.session_name, "completed", "Task completed by codex worker"
            )
        except Exception as e:
            print(f"Warning: Could not report completion: {e}", file=sys.stderr)

    def check_for_tasks(self) -> Optional[Dict[str, Any]]:
        """Check if there are pending tasks assigned to this session."""
        try:
            from workers.assigner_worker import AssignerDatabase

            db = AssignerDatabase()
            with db._get_conn() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM prompts
                    WHERE status = 'assigned'
                      AND assigned_session = ?
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    """,
                    (self.session_name,),
                ).fetchone()
                return dict(row) if row else None
        except Exception:
            return None

    def run_interactive(self):
        """Run in interactive mode."""
        print(f"Codex Chat Worker - Session: {self.session_name}")
        print("Type 'help' for commands, 'exit' to quit.")
        print("-" * 50)

        self.running = True

        # Signal handlers
        def handle_signal(signum, frame):
            print("\nReceived signal, exiting...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                # Show idle prompt (detectable by assigner)
                print(self.IDLE_PROMPT, end="", flush=True)
                user_input = input()

                if not user_input.strip():
                    continue

                response = self.process_input(user_input)
                if response:
                    print(response)

            except EOFError:
                break
            except KeyboardInterrupt:
                break

        print("\nGoodbye!")

    def run_worker(self):
        """
        Run in worker mode for tmux integration.

        In worker mode:
        - Continuously shows idle prompt for assigner detection
        - Processes input received via tmux send-keys
        - Reports task completion to the assigner
        """
        print(f"Codex Worker starting - Session: {self.session_name}")
        print("Worker mode: Waiting for prompts from assigner...")
        print("-" * 50)

        self.running = True
        self.state_manager.set_status("idle")
        self._save_state()

        # Signal handlers
        def handle_signal(signum, frame):
            print("\nReceived signal, stopping worker...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                # Update session state: idle and ready
                self.state_manager.set_status("idle")

                # Show idle prompt (detectable by assigner)
                # This pattern is matched by SessionDetector.IDLE_PATTERNS
                print(self.IDLE_PROMPT, end="", flush=True)

                # Read input (may come from stdin or tmux send-keys)
                user_input = input()

                if not user_input.strip():
                    continue

                # Check if this is an assigned task
                task = self.check_for_tasks()
                if task:
                    self.current_task_id = task["id"]

                # Show busy indicator (detectable by assigner)
                # Update session state: working
                self.state_manager.set_status("working")
                print(self.BUSY_PREFIX, flush=True)

                # Process the input
                response = self.process_input(user_input)

                if response:
                    print(response)

                # Report completion if this was an assigned task
                if self.current_task_id:
                    self.report_task_completion(self.current_task_id, response)
                    self.current_task_id = None

                # Update session state: clear task
                self.state_manager.clear_task()

                self._save_state()

            except EOFError:
                # Keep running - may get more input
                time.sleep(0.1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                self.state_manager.increment_errors()
                self.state_manager.set_metadata("last_error", str(e))
                time.sleep(1)

        # Update session state: stopped
        self.state_manager.set_status("stopped")
        self.state_manager.cleanup()
        self._save_state()
        print("\nWorker stopped.")

    def _save_state(self):
        """Save worker state to file."""
        state = {
            "session": self.session_name,
            "running": self.running,
            "current_task": self.current_task_id,
            "history_length": len(self.conversation.history),
            "provider": self.llm.provider,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        try:
            state_file = Path(f"/tmp/codex_worker_{self.session_name}_state.json")
            state_file.write_text(json.dumps(state, indent=2))
        except IOError:
            pass

    def run_single(self, command: str, prompt: str = "") -> str:
        """Run a single command and return the result."""
        if command in self.commands:
            return self.commands[command]()

        # For 'ask' or any other command, treat the whole thing as a prompt
        full_prompt = f"{command} {prompt}".strip() if prompt else command
        return self.process_input(full_prompt)


def main():
    parser = argparse.ArgumentParser(
        description="Codex Chat Worker - AI assistant for the Architect system"
    )

    # Mode selection
    parser.add_argument(
        "--worker",
        action="store_true",
        help="Run in worker mode (for tmux integration with assigner)",
    )
    parser.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="Non-interactive mode - run command and print result",
    )

    # Configuration
    parser.add_argument(
        "--session",
        type=str,
        default=os.getenv("CODEX_SESSION", "codex"),
        help="Session name for this worker (default: codex)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["claude", "ollama", "openai", "gemini", "anythingllm"],
        help="Preferred LLM provider (default: auto with failover)",
    )
    parser.add_argument("--system-prompt", type=str, help="Custom system prompt for the LLM")

    # Commands for non-interactive mode
    parser.add_argument("command", type=str, nargs="?", help="Command to execute (for -p mode)")
    parser.add_argument("prompt", type=str, nargs="*", help="Additional prompt text (for -p mode)")

    # Utility options
    parser.add_argument(
        "--list-providers", action="store_true", help="List available LLM providers"
    )
    parser.add_argument("--status", action="store_true", help="Show worker status")

    args = parser.parse_args()

    # Create worker instance
    worker = CodexWorker(
        session_name=args.session,
        provider=args.provider,
        system_prompt=args.system_prompt,
    )

    # Handle utility options
    if args.list_providers:
        print("Available LLM providers:")
        for provider in worker.llm.get_available_providers():
            print(f"  - {provider}")
        return

    if args.status:
        print(worker.cmd_status())
        return

    # Handle modes
    if getattr(args, "print"):
        # Non-interactive mode
        if args.command:
            prompt = " ".join(args.prompt) if args.prompt else ""
            result = worker.run_single(args.command, prompt)
            print(result)
        else:
            print("No command provided. Use --help for usage information.")
    elif args.worker:
        # Worker mode for tmux integration
        worker.run_worker()
    else:
        # Interactive mode
        worker.run_interactive()


if __name__ == "__main__":
    main()
