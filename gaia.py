#!/usr/bin/env python3
"""
GAIA - Generic AI Agent

A unified CLI wrapper that transparently routes to the best available
AI backend via tmux sessions, with automatic session management based
on token thresholds and provider availability.

    "One command to rule them all"

Architecture:
    gaia → [token threshold check] → tmux session routing
           [session pool manager]  → start/stop sessions on demand
           [provider abstraction]  → claude/ollama/codex sessions

    NOT direct CLI calls - always through managed tmux sessions.

Installation (run from any directory):
    # Option 1: Create symlink (recommended)
    sudo ln -sf /path/to/architect/gaia.py /usr/local/bin/gaia
    sudo ln -sf /path/to/architect/gaia.py /usr/local/bin/GAIA
    sudo ln -sf /path/to/architect/gaia.py /usr/local/bin/Gaia

    # Option 2: Add alias to shell profile
    alias gaia='/path/to/architect/gaia.py'
    alias GAIA='/path/to/architect/gaia.py'
    alias Gaia='/path/to/architect/gaia.py'

    # Option 3: Run setup script
    ./scripts/setup_gaia.sh

Usage:
    # Start GAIA interactive REPL (default mode)
    gaia
    GAIA
    Gaia

    # Attach directly to tmux session (legacy mode)
    gaia --attach
    gaia -a

    # Force specific provider
    gaia --provider claude
    gaia --provider ollama

    # Target specific session
    gaia --session dev_worker1

    # Single prompt mode
    gaia -p "What is Python?"

    # Check status
    gaia --status

    # Run in specific working directory
    gaia --workdir /path/to/project

Interactive Commands:
    /help, /h         Show help and available commands
    /status, /s       Show session pool and system status
    /sessions, /ls    List available tmux sessions
    /attach, /a       Attach to best available session
    /attach <name>    Attach to specific session
    /provider <name>  Set preferred provider
    /complexity <lvl> Set routing (low/medium/high/auto)
    /history          Show conversation history
    /clear            Clear conversation history
    /quit, /q         Exit GAIA

Features:
    - Interactive REPL mode with command history (like Claude Code)
    - Automatic complexity detection and smart routing
    - Routes through tmux sessions (never direct Claude calls)
    - Automatic session start/stop based on token thresholds
    - Provider-agnostic session pool management
    - Full PTY support for interactive use
    - Token budget awareness and throttling
    - Run from any directory with working directory support
    - Conversation history persistence
"""

import argparse
import json
import os
import re
import readline  # noqa: F401 - enables input history
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Resolve SCRIPT_DIR even when called via symlink
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Import session status manager
try:
    from services.session_status import (
        get_all_status,
        get_busy_sessions,
        get_idle_sessions,
        get_session_status,
        get_system_summary,
        mark_session_busy,
    )

    SESSION_STATUS_AVAILABLE = True
except ImportError:
    SESSION_STATUS_AVAILABLE = False

# State directory (always in architect project)
STATE_DIR = SCRIPT_DIR / "data" / "gaia"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Configuration directory
CONFIG_DIR = SCRIPT_DIR / "config"

# User's working directory (where gaia was called from)
WORKING_DIR = Path.cwd()


# ============================================================================
# High-Level Session Protection
# ============================================================================

# These sessions are reserved for direct user interaction and should NEVER
# be included in GAIA routing or task assignment
HIGH_LEVEL_SESSIONS = {
    "architect",  # System oversight and strategic decisions
    "foundation",  # System oversight and strategic decisions
    "inspector",  # System oversight and strategic decisions
}


# ============================================================================
# Token Threshold Configuration
# ============================================================================

# Default token thresholds for session management
TOKEN_THRESHOLDS = {
    # When to start additional sessions (tokens used)
    "start_session": {
        "low": 10000,  # Start thinking about new sessions
        "medium": 50000,  # Definitely need more capacity
        "high": 100000,  # Urgently need sessions
    },
    # When to stop idle sessions (tokens remaining in budget)
    "stop_session": {
        "idle_minutes": 30,  # Stop after idle this long
        "low_budget": 5000,  # Stop if budget this low
    },
    # Per-session token limits before switching
    "switch_threshold": {
        "warning": 0.70,  # Warn at 70% of limit
        "switch": 0.80,  # Switch sessions at 80%
        "critical": 0.95,  # Critical - must switch
    },
    # Provider-specific limits (tokens per hour)
    "provider_limits": {
        "claude": 100000,  # 100K tokens/hour for Claude
        "ollama": 500000,  # 500K tokens/hour for Ollama (local, fast)
        "codex": 50000,  # 50K tokens/hour for Codex
        "comet": 50000,  # 50K tokens/hour for Comet
        "gemini": 200000,  # 200K tokens/hour for Gemini (affordable fallback)
        "anythingllm": 500000,  # 500K tokens/hour for AnythingLLM (local, free)
    },
}

# Codex identification thresholds
CODEX_THRESHOLDS = {
    # Session name patterns that indicate Codex/worker sessions
    "name_patterns": [
        r"codex",
        r"code_worker",
        r"code-worker",
        r"coder",
        r"dev_worker\d*",  # dev_worker1, dev_worker2, etc.
        r"dev\d+_worker",  # dev1_worker through dev5_worker (multi-env)
        r"qa_tester\d*",  # qa_tester1, qa_tester2, etc.
        r"mcp_worker\d*",  # mcp_worker1, mcp_worker2, etc.
        r"task_worker\d*",  # task_worker1, etc.
        r"concurrent_worker",
        r"edu_worker",
        r"pr_impl\d*",  # pr_impl1 through pr_impl4 (PR implementation)
        r"pr_review\d*",  # pr_review1 through pr_review3 (PR review)
        r"pr_integ\d*",  # pr_integ1 through pr_integ3 (PR integration)
        r"gemini",
        r"gaia_worker",  # GAIA worker sessions
    ],
    # Output patterns that indicate Codex-style session
    "output_patterns": [
        r"codex>",
        r"Code\s*assistant",
        r"OpenAI",
        r"gpt-",
        r"\[codex\]",
        r">>>",  # Python/Codex prompt
    ],
    # Provider detection - ORDER MATTERS (first match wins)
    # Workers default to codex, high-level to claude
    "provider_indicators": {
        "codex": [
            r"codex",
            r"dev_worker",
            r"qa_tester",
            r"mcp_worker",
            r"task_worker",
            r"concurrent_worker",
            r"edu_worker",
            r"gaia_worker",
            r"pr_impl\d*",  # PR implementation workers
            r"worker\d*",
        ],
        "ollama": [
            r"ollama",
            r"llama",
            r"mistral",
            r"phi",
            r"gemma",
            r"local",
            r"dev\d+_worker",  # Multi-env dev workers
            r"pr_review\d*",  # PR review workers (mixed)
            r"pr_integ\d*",  # PR integration workers (fast local)
        ],
        "claude": [
            r"^architect$",
            r"^foundation$",
            r"^inspector$",
            r"^manager\d*$",
            r"claude",
            r"anthropic",
            r"pr_review[12]$",  # High-quality PR reviewers
        ],
        "comet": [r"comet", r"ui_worker", r"frontend"],
        "gemini": [r"gemini", r"google", r"generative"],
        "anythingllm": [r"anythingllm", r"anything-llm", r"rag"],
    },
    # Complexity thresholds for routing - CODEX FIRST for cost savings
    "complexity_routing": {
        "low": ["codex", "ollama"],  # Simple tasks → codex first
        "medium": ["codex", "ollama", "claude"],  # Medium → codex preferred
        "high": ["codex", "claude"],  # Complex → try codex, fallback claude
    },
}


# ============================================================================
# Session Pool Manager
# ============================================================================


class SessionPoolManager:
    """Manages a pool of tmux sessions for AI workloads."""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.refresh_sessions()

    def refresh_sessions(self) -> Dict[str, Dict]:
        """Get current tmux sessions and their status."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_activity}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self.sessions = {}
                for line in result.stdout.strip().split("\n"):
                    if ":" in line:
                        name, activity = line.rsplit(":", 1)
                        self.sessions[name] = {
                            "name": name,
                            "last_activity": activity,
                            "provider": self._detect_provider(name),
                            "is_codex": self._is_codex_session(name),
                            "is_high_level": self._is_high_level_session(name),
                        }
        except Exception as e:
            print(f"Error refreshing sessions: {e}", file=sys.stderr)
        return self.sessions

    def _detect_provider(self, session_name: str) -> str:
        """Detect provider from session name."""
        name_lower = session_name.lower()
        for provider, patterns in CODEX_THRESHOLDS["provider_indicators"].items():
            for pattern in patterns:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return provider
        return "unknown"

    def _is_codex_session(self, session_name: str) -> bool:
        """Check if session matches Codex thresholds."""
        name_lower = session_name.lower()
        for pattern in CODEX_THRESHOLDS["name_patterns"]:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return True
        return False

    def _is_high_level_session(self, session_name: str) -> bool:
        """Check if session is protected high-level session (not for GAIA routing)."""
        return session_name.lower() in HIGH_LEVEL_SESSIONS

    def get_all_sessions(self) -> List[Dict]:
        """Get all sessions including high-level protected ones."""
        self.refresh_sessions()
        return list(self.sessions.values())

    def get_available_sessions(self, provider: str = None) -> List[Dict]:
        """Get available sessions for routing, optionally filtered by provider.

        NOTE: High-level sessions (architect, foundation, inspector) are EXCLUDED
        from routing and task assignment. They are reserved for direct user interaction.
        """
        self.refresh_sessions()
        # Exclude high-level protected sessions
        sessions = [s for s in self.sessions.values() if not s.get("is_high_level", False)]
        if provider:
            sessions = [s for s in sessions if s["provider"] == provider]
        return sessions

    def get_session_for_task(
        self, complexity: str = "medium", prefer_provider: str = None
    ) -> Optional[Dict]:
        """Get best session for a task based on complexity and preferences."""
        self.refresh_sessions()

        # Get provider order based on complexity
        provider_order = CODEX_THRESHOLDS["complexity_routing"].get(
            complexity, ["ollama", "claude"]
        )

        # If preferred provider specified, put it first
        if prefer_provider and prefer_provider in provider_order:
            provider_order = [prefer_provider] + [p for p in provider_order if p != prefer_provider]

        # Find first available session matching provider order
        for provider in provider_order:
            for session in self.sessions.values():
                if session["provider"] == provider:
                    return session

        # Fallback to any available session
        if self.sessions:
            return list(self.sessions.values())[0]

        return None

    def start_session(self, name: str, provider: str = "codex") -> bool:
        """Start a new tmux session with specified provider."""
        try:
            # Determine command based on provider - CODEX IS DEFAULT
            if provider == "codex":
                # Use codex_chat.py for codex sessions
                script_dir = Path(__file__).resolve().parent
                cmd = f"python3 {script_dir}/codex_chat.py --worker --session {name}"
            elif provider == "ollama":
                model = os.getenv("OLLAMA_MODEL", "llama3.2")
                cmd = f"ollama run {model}"
            elif provider == "claude":
                cmd = "claude"
            else:
                # Default to codex (not claude!) for unknown providers
                script_dir = Path(__file__).resolve().parent
                cmd = f"python3 {script_dir}/codex_chat.py --worker --session {name}"

            # Create tmux session
            result = subprocess.run(
                ["tmux", "new-session", "-d", "-s", name, cmd],
                capture_output=True,
                timeout=10,
            )

            if result.returncode == 0:
                print(f"[GAIA] Started session: {name} ({provider})", file=sys.stderr)
                self.refresh_sessions()
                return True
            return False

        except Exception as e:
            print(f"Error starting session: {e}", file=sys.stderr)
            return False

    def stop_session(self, name: str) -> bool:
        """Stop a tmux session."""
        try:
            result = subprocess.run(
                ["tmux", "kill-session", "-t", name],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                print(f"[GAIA] Stopped session: {name}", file=sys.stderr)
                self.refresh_sessions()
                return True
            return False
        except Exception as e:
            print(f"Error stopping session: {e}", file=sys.stderr)
            return False


# ============================================================================
# Token Budget Manager
# ============================================================================


class TokenBudgetManager:
    """Manages token budgets and thresholds for sessions."""

    def __init__(self):
        self.throttler = self._get_throttler()

    def _get_throttler(self):
        """Get token throttler if available."""
        try:
            from services.token_throttle import get_throttler

            return get_throttler()
        except ImportError:
            return None

    def get_usage_percent(self, session_id: str) -> float:
        """Get usage percentage for a session."""
        if self.throttler:
            try:
                level = self.throttler.get_throttle_level(session_id, estimated_tokens=0)
                # Map throttle level to percentage
                level_map = {
                    "none": 0.0,
                    "warning": 0.70,
                    "soft": 0.80,
                    "hard": 0.90,
                    "critical": 0.95,
                }
                return level_map.get(level.value, 0.0)
            except Exception:
                pass
        return 0.0

    def should_switch_session(self, session_id: str) -> bool:
        """Check if we should switch away from this session."""
        usage = self.get_usage_percent(session_id)
        return usage >= TOKEN_THRESHOLDS["switch_threshold"]["switch"]

    def allow_request(
        self, session_id: str, estimated_tokens: int, priority: str = "normal"
    ) -> bool:
        """Check if a request is allowed for this session."""
        if self.throttler:
            try:
                return self.throttler.allow_request(session_id, estimated_tokens, priority)
            except Exception:
                pass
        return True

    def record_usage(self, session_id: str, tokens: int):
        """Record token usage."""
        if self.throttler:
            try:
                self.throttler.record_usage(session_id, tokens)
            except Exception:
                pass


# ============================================================================
# GAIA Agent (Refactored)
# ============================================================================


class GAIAgent:
    """
    GAIA - Generic AI Agent

    Routes through tmux sessions instead of direct CLI calls.
    Manages sessions based on token thresholds.
    """

    def __init__(
        self,
        session_name: str = None,
        provider: Optional[str] = None,
        verbose: bool = False,
    ):
        self.target_session = session_name
        self.preferred_provider = provider
        self.verbose = verbose
        self.state_file = STATE_DIR / "gaia_state.json"

        # Managers
        self.session_pool = SessionPoolManager()
        self.budget_manager = TokenBudgetManager()

    def select_session(self, complexity: str = "medium") -> Optional[Dict]:
        """Select best session for the current task."""
        # If specific session requested, use it
        if self.target_session:
            sessions = self.session_pool.get_available_sessions()
            for s in sessions:
                if s["name"] == self.target_session:
                    # Check if we should switch due to token limits
                    if self.budget_manager.should_switch_session(s["name"]):
                        if self.verbose:
                            print(
                                f"[GAIA] Session {s['name']} at token limit, finding alternative",
                                file=sys.stderr,
                            )
                        break  # Fall through to auto-selection
                    return s
            # Session not found or at limit, fall through to auto-selection

        # Auto-select based on complexity and provider preference
        session = self.session_pool.get_session_for_task(
            complexity=complexity,
            prefer_provider=self.preferred_provider,
        )

        if session:
            # Check token budget
            if self.budget_manager.should_switch_session(session["name"]):
                # Try to find an alternative
                all_sessions = self.session_pool.get_available_sessions()
                for s in all_sessions:
                    if s["name"] != session[
                        "name"
                    ] and not self.budget_manager.should_switch_session(s["name"]):
                        if self.verbose:
                            print(
                                f"[GAIA] Switching from {session['name']} "
                                f"to {s['name']} (token limit)",
                                file=sys.stderr,
                            )
                        return s

        return session

    def send_to_session(self, session_name: str, content: str, provider: str = None) -> bool:
        """Send content to a tmux session and report status."""
        try:
            # Report session as busy with this task
            if SESSION_STATUS_AVAILABLE:
                task_preview = content[:100] + "..." if len(content) > 100 else content
                mark_session_busy(session_name, task_preview, provider=provider)

            result = subprocess.run(
                ["tmux", "send-keys", "-t", session_name, content, "Enter"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error sending to session: {e}", file=sys.stderr)
            return False

    def attach_to_session(self, session_name: str):
        """Attach to a tmux session interactively."""
        os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])

    def run_interactive(self, complexity: str = "medium", attach_mode: bool = False):
        """Run in interactive mode.

        Args:
            complexity: Task complexity for routing (low/medium/high)
            attach_mode: If True, attach to tmux session. If False, use REPL mode.
        """
        if not attach_mode:
            # Use the new REPL mode
            return self.run_repl()

        # Legacy attach mode - attach to best available session
        session = self.select_session(complexity=complexity)

        if not session:
            # No sessions available, start one - DEFAULT TO CODEX (not claude!)
            provider = self.preferred_provider or "codex"
            new_name = f"gaia_{provider}_{int(time.time())}"
            print(f"[GAIA] No sessions available, starting new {provider} session...")
            if self.session_pool.start_session(new_name, provider):
                session = {"name": new_name, "provider": provider}
            else:
                print(
                    "Error: No sessions available and failed to start new session",
                    file=sys.stderr,
                )
                return 1

        print(
            f"[GAIA] Routing to session: {session['name']} ({session.get('provider', 'unknown')})"
        )
        print("-" * 50)

        # Attach to session
        self.attach_to_session(session["name"])
        return 0

    def run_single_prompt(self, prompt: str, complexity: str = "medium") -> int:
        """Send a single prompt to the best available session."""
        session = self.select_session(complexity=complexity)

        if not session:
            print("Error: No sessions available", file=sys.stderr)
            return 1

        # Check budget
        estimated_tokens = len(prompt) // 4 + 500  # Rough estimate
        if not self.budget_manager.allow_request(session["name"], estimated_tokens):
            print(
                f"[GAIA] Request throttled for session {session['name']}",
                file=sys.stderr,
            )
            # Try alternative session
            all_sessions = self.session_pool.get_available_sessions()
            for s in all_sessions:
                if s["name"] != session["name"]:
                    if self.budget_manager.allow_request(s["name"], estimated_tokens):
                        session = s
                        break
            else:
                print("Error: All sessions throttled", file=sys.stderr)
                return 1

        if self.verbose:
            print(
                f"[GAIA] Sending to: {session['name']} ({session.get('provider', 'unknown')})",
                file=sys.stderr,
            )

        # Send prompt
        provider = session.get("provider", "unknown")
        if self.send_to_session(session["name"], prompt, provider=provider):
            # Record usage estimate
            self.budget_manager.record_usage(session["name"], estimated_tokens)
            print(f"[GAIA] Prompt sent to {session['name']}")
            return 0
        else:
            print(f"Error: Failed to send to session {session['name']}", file=sys.stderr)
            return 1

    def _detect_complexity(self, prompt: str) -> str:
        """Detect task complexity from prompt content."""
        prompt_lower = prompt.lower()

        # High complexity indicators
        high_patterns = [
            r"refactor",
            r"architect",
            r"design.*system",
            r"implement.*feature",
            r"complex",
            r"multi.*file",
            r"integration",
            r"security",
            r"performance.*optim",
            r"database.*schema",
            r"api.*design",
            r"test.*coverage",
            r"debug.*issue",
            r"fix.*bug.*in",
        ]

        # Low complexity indicators
        low_patterns = [
            r"^what\s+is",
            r"^how\s+do\s+i",
            r"^explain",
            r"^define",
            r"simple",
            r"quick",
            r"^list",
            r"^show",
            r"hello",
            r"thanks",
            r"^hi\b",
        ]

        for pattern in high_patterns:
            if re.search(pattern, prompt_lower):
                return "high"

        for pattern in low_patterns:
            if re.search(pattern, prompt_lower):
                return "low"

        # Default to medium
        return "medium"

    def _handle_repl_command(self, cmd: str) -> bool:
        """Handle REPL commands. Returns True if command was handled."""
        cmd = cmd.strip().lower()

        if cmd in ("/help", "/h", "/?"):
            self._print_repl_help()
            return True

        elif cmd in ("/status", "/s"):
            self.show_status()
            return True

        elif cmd in ("/sessions", "/ls"):
            self._show_sessions_brief()
            return True

        elif cmd in ("/quit", "/q", "/exit"):
            print("\nGoodbye!")
            sys.exit(0)

        elif cmd in ("/attach", "/a"):
            session = self.select_session()
            if session:
                print(f"Attaching to {session['name']}...")
                self.attach_to_session(session["name"])
            else:
                print("No sessions available to attach.")
            return True

        elif cmd.startswith("/attach ") or cmd.startswith("/a "):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1:
                session_name = parts[1]
                sessions = self.session_pool.get_available_sessions()
                for s in sessions:
                    if s["name"] == session_name:
                        print(f"Attaching to {session_name}...")
                        self.attach_to_session(session_name)
                        return True
                print(f"Session '{session_name}' not found.")
            return True

        elif cmd in ("/history", "/hist"):
            self._show_history()
            return True

        elif cmd in ("/clear",):
            self.conversation_history = []
            print("Conversation history cleared.")
            return True

        elif cmd.startswith("/provider ") or cmd.startswith("/p "):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1:
                provider = parts[1]
                if provider in [
                    "claude",
                    "ollama",
                    "codex",
                    "comet",
                    "gemini",
                    "anythingllm",
                ]:
                    self.preferred_provider = provider
                    print(f"Preferred provider set to: {provider}")
                else:
                    print(f"Unknown provider: {provider}")
                    print("Available: claude, ollama, codex, comet, gemini, anythingllm")
            return True

        elif cmd.startswith("/complexity ") or cmd.startswith("/c "):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1:
                level = parts[1]
                if level in ["low", "medium", "high", "auto"]:
                    self.fixed_complexity = None if level == "auto" else level
                    print(f"Complexity routing set to: {level}")
                else:
                    print("Valid options: low, medium, high, auto")
            return True

        elif cmd in ("/watch", "/w"):
            self.show_live_status()
            return True

        elif cmd in ("/tokens", "/t"):
            self._show_token_stats()
            return True

        elif cmd in ("/detailed", "/d"):
            self.show_status(detailed=True)
            return True

        return False

    def _print_repl_help(self):
        """Print REPL help message."""
        print(
            """
GAIA Interactive Mode - Commands
================================

Navigation:
  /status, /s        Show session pool and system status
  /sessions, /ls     List available tmux sessions
  /attach, /a        Attach to best available session
  /attach <name>     Attach to specific session
  /quit, /q          Exit GAIA

Monitoring:
  /watch, /w         Live updating status dashboard
  /tokens, /t        Show token usage and limits for all providers
  /detailed, /d      Show detailed status with thresholds

Configuration:
  /provider <name>   Set preferred provider (claude, ollama, codex, etc.)
  /complexity <lvl>  Set routing complexity (low, medium, high, auto)

History:
  /history, /hist    Show conversation history
  /clear             Clear conversation history

Routing:
  - Tasks are auto-routed based on complexity detection
  - LOW: Simple questions -> codex/ollama
  - MEDIUM: Standard tasks -> codex preferred
  - HIGH: Complex work -> codex first, claude fallback

Tips:
  - Press Ctrl+C to cancel current input
  - Press Ctrl+D or type /quit to exit
  - Use arrow keys for command history
"""
        )

    def _show_sessions_brief(self):
        """Show brief session list."""
        sessions = self.session_pool.get_available_sessions()
        if not sessions:
            print("No active sessions.")
            return

        print(f"\nActive Sessions ({len(sessions)}):")
        print("-" * 40)
        for s in sessions:
            provider = s.get("provider", "unknown")
            usage = self.budget_manager.get_usage_percent(s["name"]) * 100
            codex_tag = " [codex]" if s.get("is_codex") else ""
            # Get task info from status DB
            task_info = ""
            if SESSION_STATUS_AVAILABLE:
                db_status = get_session_status(s["name"])
                if db_status and db_status.task:
                    task_info = f" → {db_status.task[:20]}"
            print(f"  {s['name']:20} {provider:10} {usage:5.0f}%{codex_tag}{task_info}")

    def _show_token_stats(self):
        """Show token usage statistics for all providers."""
        print("\nToken Usage Statistics")
        print("=" * 70)

        # Provider limits and usage
        print("\nProvider Token Limits (per hour):")
        print("-" * 70)
        print(f"  {'Provider':<15} {'Limit':>12} {'Used':>12} {'Remaining':>12} {'%':>8}")
        print("-" * 70)

        total_used = 0
        total_limit = 0

        for provider, limit in TOKEN_THRESHOLDS["provider_limits"].items():
            # Get sessions for this provider
            sessions = [
                s
                for s in self.session_pool.get_available_sessions()
                if s.get("provider") == provider
            ]

            # Calculate usage from budget manager and status DB
            provider_used = 0
            if SESSION_STATUS_AVAILABLE:
                for s in sessions:
                    db_status = get_session_status(s["name"])
                    if db_status:
                        provider_used += db_status.tokens_used

            remaining = max(0, limit - provider_used)
            pct = (provider_used / limit * 100) if limit > 0 else 0

            # Color coding
            if pct >= 90:
                color = "\033[91m"  # Red
            elif pct >= 70:
                color = "\033[93m"  # Yellow
            else:
                color = "\033[92m"  # Green
            reset = "\033[0m"

            print(
                f"  {provider:<15} {limit:>12,} {provider_used:>12,} "
                f"{remaining:>12,} {color}{pct:>7.1f}%{reset}"
            )

            total_used += provider_used
            total_limit += limit

        print("-" * 70)
        total_pct = (total_used / total_limit * 100) if total_limit > 0 else 0
        print(
            f"  {'TOTAL':<15} {total_limit:>12,} {total_used:>12,} "
            f"{total_limit - total_used:>12,} {total_pct:>7.1f}%"
        )

        # Per-session breakdown if available
        if SESSION_STATUS_AVAILABLE:
            all_status = get_all_status()
            active = [s for s in all_status if s.tokens_used > 0]

            if active:
                print("\nSession Token Usage:")
                print("-" * 70)
                print(f"  {'Session':<25} {'Provider':<12} {'Tokens':>10} {'Cost':>10}")
                print("-" * 70)

                total_cost = 0
                for s in sorted(active, key=lambda x: x.tokens_used, reverse=True)[:15]:
                    print(
                        f"  {s.session_name:<25} {s.provider:<12} "
                        f"{s.tokens_used:>10,} ${s.cost:>9.4f}"
                    )
                    total_cost += s.cost

                print("-" * 70)
                print(f"  {'TOTAL':<25} {'':<12} {total_used:>10,} ${total_cost:>9.4f}")

        # Threshold warnings
        print("\nThreshold Status:")
        switch_pct = TOKEN_THRESHOLDS["switch_threshold"]["switch"] * 100
        critical_pct = TOKEN_THRESHOLDS["switch_threshold"]["critical"] * 100
        print(f"  Session switch at: {switch_pct:.0f}%")
        print(f"  Critical at: {critical_pct:.0f}%")

    def _show_history(self):
        """Show conversation history."""
        if not hasattr(self, "conversation_history") or not self.conversation_history:
            print("No conversation history.")
            return

        print(f"\nConversation History ({len(self.conversation_history)} messages):")
        print("-" * 50)
        for i, entry in enumerate(self.conversation_history[-10:], 1):
            timestamp = entry.get("timestamp", "")
            session = entry.get("session", "unknown")
            prompt = entry.get("prompt", "")[:60]
            if len(entry.get("prompt", "")) > 60:
                prompt += "..."
            print(f"  {i}. [{timestamp}] -> {session}")
            print(f"     {prompt}")

    def _save_history(self):
        """Save conversation history to file."""
        if not hasattr(self, "conversation_history"):
            return

        history_file = STATE_DIR / "repl_history.json"
        try:
            with open(history_file, "w") as f:
                json.dump(self.conversation_history[-100:], f, indent=2)  # Keep last 100
        except Exception:
            pass

    def _load_history(self):
        """Load conversation history from file."""
        history_file = STATE_DIR / "repl_history.json"
        try:
            if history_file.exists():
                with open(history_file) as f:
                    self.conversation_history = json.load(f)
            else:
                self.conversation_history = []
        except Exception:
            self.conversation_history = []

    def run_repl(self) -> int:
        """Run true interactive REPL mode with routing."""
        self._load_history()
        self.fixed_complexity = None  # Auto-detect by default

        # Print banner
        print("\n" + "=" * 60)
        print("GAIA v1.0 - Interactive Orchestrator")
        print("=" * 60)
        print("Type /help for commands, /quit to exit")
        print(f"Working directory: {WORKING_DIR}")

        # Show quick status
        sessions = self.session_pool.get_available_sessions()
        providers = {}
        for s in sessions:
            p = s.get("provider", "unknown")
            providers[p] = providers.get(p, 0) + 1
        provider_str = ", ".join(f"{k}:{v}" for k, v in sorted(providers.items()))
        print(f"Sessions: {len(sessions)} ({provider_str})")
        print("-" * 60 + "\n")

        try:
            while True:
                try:
                    # Get input with prompt
                    prompt = input("\033[1;36mgaia>\033[0m ").strip()

                    # Skip empty input
                    if not prompt:
                        continue

                    # Handle commands
                    if prompt.startswith("/"):
                        if self._handle_repl_command(prompt):
                            continue

                    # Detect complexity (or use fixed)
                    if self.fixed_complexity:
                        complexity = self.fixed_complexity
                    else:
                        complexity = self._detect_complexity(prompt)

                    # Select session based on complexity
                    session = self.select_session(complexity=complexity)

                    if not session:
                        # Try to start a new session
                        provider = self.preferred_provider or "codex"
                        new_name = f"gaia_{provider}_{int(time.time())}"
                        print(f"[Starting new {provider} session...]")
                        if self.session_pool.start_session(new_name, provider):
                            session = {"name": new_name, "provider": provider}
                            time.sleep(1)  # Give session time to start
                        else:
                            print("Error: No sessions available and failed to start new one.")
                            continue

                    # Show routing decision
                    provider = session.get("provider", "unknown")
                    print(
                        f"\033[90m[{complexity.upper()} -> {session['name']} ({provider})]\033[0m"
                    )

                    # Send prompt to session
                    if self.send_to_session(session["name"], prompt, provider=provider):
                        # Record in history
                        self.conversation_history.append(
                            {
                                "timestamp": datetime.now().strftime("%H:%M:%S"),
                                "prompt": prompt,
                                "session": session["name"],
                                "provider": provider,
                                "complexity": complexity,
                            }
                        )
                        self._save_history()

                        # Record token usage
                        estimated_tokens = len(prompt) // 4 + 500
                        self.budget_manager.record_usage(session["name"], estimated_tokens)

                        print(f"\033[90m[Sent to {session['name']}]\033[0m")
                        print()
                    else:
                        print(f"Error: Failed to send to {session['name']}")

                except KeyboardInterrupt:
                    print("\n(Use /quit to exit)")
                    continue

        except EOFError:
            print("\nGoodbye!")
            return 0

        return 0

    def show_status(self, detailed: bool = False):
        """Show status of sessions and thresholds."""
        print("\nGAIA - Generic AI Agent Status")
        print("=" * 60)

        # Show session status from database if available
        if SESSION_STATUS_AVAILABLE:
            summary = get_system_summary()
            print("\nSystem Summary:")
            print(f"  Active Sessions: {summary.get('active_sessions', 0)}")
            print(f"  Busy: {summary.get('busy_sessions', 0)}")
            print(f"  Idle: {summary.get('idle_sessions', 0)}")
            print(f"  Errors: {summary.get('error_sessions', 0)}")
            print(f"  Total Tokens: {summary.get('total_tokens', 0):,}")
            print(f"  Total Cost: ${summary.get('total_cost', 0):.4f}")

            # Show busy sessions with their current tasks
            busy = get_busy_sessions()
            if busy:
                print(f"\n  Currently Working ({len(busy)}):")
                for s in busy:
                    task_preview = s.task[:40] + "..." if len(s.task) > 40 else s.task
                    progress = f" [{s.progress}%]" if s.progress > 0 else ""
                    print(f"    🔵 {s.session_name:20} {task_preview}{progress}")

            # Show idle sessions
            idle = get_idle_sessions()
            if idle:
                print(f"\n  Available ({len(idle)}):")
                for s in idle[:10]:  # Limit to 10
                    print(f"    🟢 {s.session_name:20} ({s.provider})")
                if len(idle) > 10:
                    print(f"    ... and {len(idle) - 10} more")

            print("\n" + "-" * 60)

        # Session pool from tmux
        all_sessions = self.session_pool.get_all_sessions()
        available_sessions = self.session_pool.get_available_sessions()

        # Separate high-level sessions
        high_level = [s for s in all_sessions if s.get("is_high_level", False)]

        print(f"\nTmux Sessions: {len(all_sessions)} total")
        if high_level:
            print(f"  HIGH-LEVEL (Protected): {len(high_level)}")
            for s in high_level:
                print(f"    🔒 {s['name']} (reserved for direct use)")
        print(f"  AVAILABLE FOR GAIA: {len(available_sessions)}")

        # Group available sessions by provider
        by_provider = {}
        for s in available_sessions:
            provider = s.get("provider", "unknown")
            by_provider.setdefault(provider, []).append(s)

        for provider, sess_list in sorted(by_provider.items()):
            print(f"\n  {provider.upper()} ({len(sess_list)}):")
            for s in sess_list[:5]:  # Limit display
                usage = self.budget_manager.get_usage_percent(s["name"]) * 100
                codex_tag = " [codex]" if s.get("is_codex") else ""
                # Get status from database if available
                state_icon = "⚪"
                task_info = ""
                if SESSION_STATUS_AVAILABLE:
                    db_status = get_session_status(s["name"])
                    if db_status:
                        state_icon = {
                            "idle": "🟢",
                            "busy": "🔵",
                            "thinking": "🟡",
                            "error": "🔴",
                            "offline": "⚫",
                        }.get(db_status.state.value, "⚪")
                        if db_status.task:
                            task_info = f" → {db_status.task[:30]}"
                print(f"    {state_icon} {s['name']}: {usage:.0f}%{codex_tag}{task_info}")
            if len(sess_list) > 5:
                print(f"    ... and {len(sess_list) - 5} more")

        # Token thresholds (only in detailed mode)
        if detailed:
            print("\n" + "-" * 60)
            print("Token Thresholds:")
            print(f"  Switch session at: {TOKEN_THRESHOLDS['switch_threshold']['switch']*100:.0f}%")
            print(f"  Critical at: {TOKEN_THRESHOLDS['switch_threshold']['critical']*100:.0f}%")

            print("\nProvider Limits (tokens/hour):")
            for provider, limit in TOKEN_THRESHOLDS["provider_limits"].items():
                print(f"  {provider}: {limit:,}")

        # Recommendation
        print("\n" + "-" * 60)
        session = self.select_session()
        if session:
            print(f"Recommended session: {session['name']} ({session.get('provider', 'unknown')})")
        else:
            print("No sessions available - will start new session on demand")

    def show_live_status(self, refresh_interval: int = 2):
        """Show live updating status display."""
        if not SESSION_STATUS_AVAILABLE:
            print("Session status tracking not available.")
            return

        print("\033[2J\033[H")  # Clear screen
        print("GAIA Live Status (Press Ctrl+C to exit)")
        print("=" * 60)

        try:
            while True:
                # Move cursor to top
                print("\033[3;1H")

                summary = get_system_summary()
                now = datetime.now().strftime("%H:%M:%S")

                print(f"Last Update: {now}")
                print(f"\nActive: {summary.get('active_sessions', 0):3}  ", end="")
                print(f"Busy: {summary.get('busy_sessions', 0):3}  ", end="")
                print(f"Idle: {summary.get('idle_sessions', 0):3}  ", end="")
                print(f"Errors: {summary.get('error_sessions', 0):3}")
                print(f"Tokens: {summary.get('total_tokens', 0):,}  ", end="")
                print(f"Cost: ${summary.get('total_cost', 0):.4f}")

                print("\n" + "-" * 60)
                print("Current Tasks:")

                busy = get_busy_sessions()
                if busy:
                    for s in busy[:15]:
                        task = s.task[:45] + "..." if len(s.task) > 45 else s.task
                        progress = f"[{s.progress:3}%]" if s.progress > 0 else "[    ]"
                        print(f"  🔵 {s.session_name:18} {progress} {task}")
                else:
                    print("  (No active tasks)")

                # Clear remaining lines
                print("\033[J", end="")

                time.sleep(refresh_interval)

        except KeyboardInterrupt:
            print("\n\nExiting live status...")

    def show_group_status(self):
        """Show sessions organized by functional groups (multi-environment setup)."""
        print("\nGAIA - Multi-Environment Status Report")
        print("=" * 70)

        all_sessions = self.session_pool.get_all_sessions()

        # Define session groups
        groups = {
            "High-Level (Protected)": {
                "pattern": r"^(architect|foundation|inspector|manager\d+|claude_architect)$",
                "icon": "🔒",
                "description": "System oversight and strategy",
            },
            "Dev Environment Workers": {
                "pattern": r"dev\d+_worker",
                "icon": "🔧",
                "description": "Development environment workers (ollama)",
            },
            "PR Review (PRR)": {
                "pattern": r"pr_review\d+",
                "icon": "👁️",
                "description": "Code review agents",
            },
            "PR Implementation (PRI)": {
                "pattern": r"pr_impl\d+",
                "icon": "✏️",
                "description": "Implementation workers",
            },
            "PR Integration (PRIG)": {
                "pattern": r"pr_integ\d+",
                "icon": "🔀",
                "description": "Integration and testing",
            },
            "Existing Workers": {
                "pattern": r"(dev_worker|qa_worker|codex|edu_worker|comet)",
                "icon": "⚙️",
                "description": "Existing worker sessions",
            },
        }

        # Categorize sessions
        categorized = {}
        uncategorized = []

        for session in all_sessions:
            name = session.get("name", "")
            found = False

            for group_name, group_info in groups.items():
                if re.match(group_info["pattern"], name):
                    if group_name not in categorized:
                        categorized[group_name] = []
                    categorized[group_name].append(session)
                    found = True
                    break

            if not found:
                uncategorized.append(session)

        # Display grouped sessions
        for group_name, group_info in groups.items():
            if group_name in categorized:
                sessions = categorized[group_name]
                print(f"\n{group_info['icon']} {group_name} - {group_info['description']}")
                print("-" * 70)

                for session in sorted(sessions, key=lambda s: s.get("name", "")):
                    name = session.get("name", "unknown")
                    provider = session.get("provider", "unknown")
                    state_icon = "⚪"

                    if SESSION_STATUS_AVAILABLE:
                        db_status = get_session_status(name)
                        if db_status:
                            state_icon = {
                                "idle": "🟢",
                                "busy": "🔵",
                                "thinking": "🟡",
                                "error": "🔴",
                                "offline": "⚫",
                            }.get(db_status.state.value, "⚪")
                            if db_status.task:
                                task_preview = db_status.task[:40]
                                print(f"  {state_icon} {name:20} [{provider:10}] → {task_preview}")
                            else:
                                print(f"  {state_icon} {name:20} [{provider:10}]")
                        else:
                            print(f"  {state_icon} {name:20} [{provider:10}]")
                    else:
                        print(f"  {state_icon} {name:20} [{provider:10}]")

        # Show uncategorized
        if uncategorized:
            print(f"\n🔹 Other Sessions ({len(uncategorized)})")
            print("-" * 70)
            for session in sorted(uncategorized, key=lambda s: s.get("name", "")):
                name = session.get("name", "unknown")
                provider = session.get("provider", "unknown")
                print(f"  ⚪ {name:20} [{provider:10}]")

        print("\n" + "=" * 70)
        print(f"Total Sessions: {len(all_sessions)}")


def setup_global_command():
    """Set up gaia/GAIA/Gaia as global commands."""
    script_path = Path(__file__).resolve()
    bin_dir = Path("/usr/local/bin")

    print("=" * 60)
    print("GAIA Global Setup")
    print("=" * 60)
    print(f"\nScript location: {script_path}")
    print(f"Target directory: {bin_dir}")

    # Check if we have write access
    if not os.access(bin_dir, os.W_OK):
        print("\nNo write access to /usr/local/bin. Run with sudo:")
        print(f"  sudo {script_path} --setup")
        print("\nOr add to your shell profile (~/.bashrc or ~/.zshrc):")
        print(f'  alias gaia="{script_path}"')
        print(f'  alias GAIA="{script_path}"')
        print(f'  alias Gaia="{script_path}"')
        return 1

    # Create symlinks
    for name in ["gaia", "GAIA", "Gaia"]:
        link_path = bin_dir / name
        try:
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(script_path)
            print(f"  Created: {link_path} -> {script_path}")
        except Exception as e:
            print(f"  Failed to create {link_path}: {e}")

    print("\nSetup complete! You can now run 'gaia', 'GAIA', or 'Gaia' from anywhere.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=(
            "GAIA - Generic AI Agent: Routes through tmux sessions "
            "with token threshold management"
        ),
        epilog="Run 'gaia --status' to see session pool and thresholds.",
    )

    parser.add_argument("--session", "-s", help="Target specific tmux session")
    parser.add_argument(
        "--provider",
        "-b",
        choices=["claude", "ollama", "codex", "comet", "gemini", "anythingllm"],
        help="Preferred provider",
    )
    parser.add_argument(
        "--complexity",
        "-c",
        choices=["low", "medium", "high"],
        default="medium",
        help="Task complexity for routing (default: medium)",
    )
    parser.add_argument("--prompt", "-p", help="Single prompt to send (non-interactive)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show routing decisions")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument(
        "--tokens",
        "-t",
        action="store_true",
        help="Show token usage statistics for all providers",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Show live updating status dashboard",
    )
    parser.add_argument(
        "--attach",
        "-a",
        action="store_true",
        help="Attach to tmux session instead of REPL mode",
    )
    parser.add_argument(
        "--workdir",
        "-w",
        type=Path,
        default=None,
        help="Working directory for the session (default: current directory)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Set up gaia/GAIA/Gaia as global commands",
    )
    parser.add_argument(
        "--multi-env-status",
        action="store_true",
        help="Show multi-environment status (directories, environments, PR groups)",
    )
    parser.add_argument(
        "--group-status",
        action="store_true",
        help="Show sessions organized by functional groups",
    )
    parser.add_argument(
        "--pr-attribution",
        action="store_true",
        help="Show PR provider attribution (which provider worked on each PR)",
    )
    parser.add_argument("args", nargs="*", help="Additional arguments (not used in session mode)")

    args = parser.parse_args()

    # Handle setup command
    if args.setup:
        return setup_global_command()

    # Set working directory
    if args.workdir:
        os.chdir(args.workdir)

    agent = GAIAgent(
        session_name=args.session,
        provider=args.provider,
        verbose=args.verbose,
    )

    if args.status:
        agent.show_status()
        return 0

    if args.tokens:
        agent._show_token_stats()
        return 0

    if args.watch:
        agent.show_live_status()
        return 0

    if args.group_status:
        agent.show_group_status()
        return 0

    if args.multi_env_status:
        try:
            from services.multi_env_status import MultiEnvStatusManager

            manager = MultiEnvStatusManager()
            print(manager.export_summary_text())
        except ImportError:
            print("Error: multi_env_status module not available")
            return 1
        return 0

    if args.pr_attribution:
        try:
            from services.multi_env_status import MultiEnvStatusManager

            manager = MultiEnvStatusManager()
            print(manager.format_pr_attribution_report())
        except ImportError:
            print("Error: multi_env_status module not available")
            return 1
        return 0

    if args.prompt:
        return agent.run_single_prompt(args.prompt, complexity=args.complexity)

    return agent.run_interactive(complexity=args.complexity, attach_mode=args.attach)


if __name__ == "__main__":
    sys.exit(main())
