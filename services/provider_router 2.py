#!/usr/bin/env python3
"""
Provider Router

Routes sessions and tasks to the appropriate LLM provider based on configuration.
Default: Codex/Ollama for workers, Claude for high-level coordination.

Usage:
    from services.provider_router import get_provider_for_session, ProviderRouter

    # Get provider for a session
    provider = get_provider_for_session("dev_worker1")  # Returns "ollama"
    provider = get_provider_for_session("architect")     # Returns "claude"

    # Get provider with fallbacks
    router = ProviderRouter()
    provider, fallbacks = router.get_provider_with_fallbacks("qa_tester1")
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ProviderRouter")

# Configuration paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config" / "session_providers.yaml"


class Provider(str, Enum):
    """Supported LLM providers."""

    CLAUDE = "claude"
    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"
    COMET = "comet"
    CODEX = "codex"
    ANYTHINGLLM = "anythingllm"


class SessionTier(str, Enum):
    """Session hierarchy tiers."""

    HIGH_LEVEL = "high_level"
    MANAGER = "manager"
    WORKER = "worker"
    QA = "qa"
    MCP = "mcp"
    UI = "ui"
    UNKNOWN = "unknown"


@dataclass
class RoutingResult:
    """Result of provider routing decision."""

    provider: str
    tier: str
    fallbacks: List[str]
    reason: str


class ProviderRouter:
    """
    Routes sessions to appropriate LLM providers.

    Default behavior:
    - High-level/Manager sessions → Claude (complex reasoning)
    - Worker sessions → Ollama/Codex (cost savings)
    - UI sessions → Comet
    - Unknown → Ollama (safe default)
    """

    # Default configuration if YAML not available
    # Priority: codex → ollama → comet → claude (to avoid Claude API limits)
    DEFAULT_CONFIG = {
        "default_provider": "codex",
        "tiers": {
            "high_level": {
                "provider": "claude",
                "sessions": ["architect", "foundation", "inspector", "claude_orchestrator"],
                "patterns": [r"^architect", r"^foundation", r"orchestrator"],
            },
            "manager": {
                "provider": "claude",
                "sessions": ["manager1", "manager2", "manager3", "wrapper_claude"],
                "patterns": [r"^manager\d+", r"^claude-.*-agent"],
            },
            "worker": {
                "provider": "codex",  # Codex first to avoid Claude API limits
                "sessions": ["codex", "dev_worker1", "dev_worker2", "dev_worker3", "gaia_worker1"],
                "patterns": [
                    r"^dev_worker\d+",
                    r"^worker\d+",
                    r"^concurrent_worker",
                    r"^codex",
                    r"^gaia_worker",
                    r"^gaia_",
                ],
            },
            "qa": {
                "provider": "codex",  # Codex first
                "sessions": ["qa_tester1", "qa_tester2", "qa_tester3"],
                "patterns": [r"^qa_", r"_tester\d+"],
            },
            "mcp": {
                "provider": "codex",  # Codex first
                "sessions": ["mcp_worker1", "mcp_worker2"],
                "patterns": [r"^mcp_"],
            },
            "ui": {
                "provider": "comet",
                "sessions": ["claude_comet", "ui_worker"],
                "patterns": [r"comet", r"^ui_", r"^frontend"],
            },
        },
        "fallback_chain": {
            "codex": ["ollama", "comet", "claude"],
            "ollama": ["codex", "comet", "claude"],
            "comet": ["codex", "ollama", "claude"],
            "claude": ["codex", "ollama", "openai", "gemini"],
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.config = self._load_config()
        self._compile_patterns()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if self.config_path.exists():
            try:
                import yaml

                with open(self.config_path) as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Loaded provider config from {self.config_path}")
                    return config
            except ImportError:
                logger.warning("PyYAML not installed, using default config")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")

        return self.DEFAULT_CONFIG

    def _compile_patterns(self):
        """Compile regex patterns for each tier."""
        self._tier_patterns: Dict[str, List[re.Pattern]] = {}

        for tier_name, tier_config in self.config.get("tiers", {}).items():
            patterns = tier_config.get("patterns", [])
            self._tier_patterns[tier_name] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def get_tier(self, session_name: str) -> str:
        """Determine the tier for a session."""
        session_lower = session_name.lower()

        for tier_name, tier_config in self.config.get("tiers", {}).items():
            # Check explicit session list
            sessions = [s.lower() for s in tier_config.get("sessions", [])]
            if session_lower in sessions:
                return tier_name

            # Check patterns
            for pattern in self._tier_patterns.get(tier_name, []):
                if pattern.search(session_name):
                    return tier_name

        return SessionTier.UNKNOWN.value

    def get_provider(self, session_name: str) -> str:
        """Get the provider for a session."""
        tier = self.get_tier(session_name)

        if tier == SessionTier.UNKNOWN.value:
            return self.config.get("default_provider", "ollama")

        tier_config = self.config.get("tiers", {}).get(tier, {})
        return tier_config.get("provider", "ollama")

    def get_fallbacks(self, provider: str) -> List[str]:
        """Get fallback providers for a given provider."""
        fallback_chain = self.config.get("fallback_chain", {})
        return fallback_chain.get(provider, ["claude", "ollama"])

    def get_provider_with_fallbacks(self, session_name: str) -> Tuple[str, List[str]]:
        """Get provider and fallback chain for a session."""
        provider = self.get_provider(session_name)
        fallbacks = self.get_fallbacks(provider)
        return provider, fallbacks

    def route(self, session_name: str) -> RoutingResult:
        """Get full routing result for a session."""
        tier = self.get_tier(session_name)
        provider = self.get_provider(session_name)
        fallbacks = self.get_fallbacks(provider)

        if tier == SessionTier.UNKNOWN.value:
            reason = f"Unknown session, using default provider: {provider}"
        else:
            reason = f"Tier '{tier}' routes to {provider}"

        return RoutingResult(
            provider=provider,
            tier=tier,
            fallbacks=fallbacks,
            reason=reason,
        )

    def get_sessions_by_provider(self) -> Dict[str, List[str]]:
        """Get all configured sessions grouped by provider."""
        result: Dict[str, List[str]] = {}

        for tier_name, tier_config in self.config.get("tiers", {}).items():
            provider = tier_config.get("provider", "unknown")
            sessions = tier_config.get("sessions", [])

            if provider not in result:
                result[provider] = []
            result[provider].extend(sessions)

        return result

    def get_cost_estimate(self, provider: str, tokens: int = 1_000_000) -> float:
        """Get cost estimate for a provider (per tokens)."""
        costs = self.config.get("costs", {})
        cost_per_million = costs.get(provider, 0.0)
        return (tokens / 1_000_000) * cost_per_million

    def should_use_claude(self, session_name: str, task_type: Optional[str] = None) -> bool:
        """Determine if Claude should be used for this session/task."""
        # Check task type overrides
        if task_type:
            overrides = self.config.get("routing", {}).get("task_type_overrides", {})
            if task_type in overrides:
                return overrides[task_type] == "claude"

        # Check session tier
        provider = self.get_provider(session_name)
        return provider == "claude"


# Global router instance
_router: Optional[ProviderRouter] = None


def get_router() -> ProviderRouter:
    """Get the global provider router instance."""
    global _router
    if _router is None:
        _router = ProviderRouter()
    return _router


def get_provider_for_session(session_name: str) -> str:
    """Get the provider for a session (convenience function)."""
    return get_router().get_provider(session_name)


def get_tier_for_session(session_name: str) -> str:
    """Get the tier for a session (convenience function)."""
    return get_router().get_tier(session_name)


def should_use_claude(session_name: str, task_type: Optional[str] = None) -> bool:
    """Check if Claude should be used (convenience function)."""
    return get_router().should_use_claude(session_name, task_type)


# ============================================================================
# CLI
# ============================================================================


def print_routing_table():
    """Print the current routing configuration."""
    router = get_router()

    print("\n" + "=" * 70)
    print("Provider Routing Configuration")
    print("=" * 70)

    print(f"\nDefault Provider: {router.config.get('default_provider', 'ollama')}")

    print("\nTier Configuration:")
    print("-" * 70)
    print(f"{'Tier':<15} {'Provider':<10} {'Sessions'}")
    print("-" * 70)

    for tier_name, tier_config in router.config.get("tiers", {}).items():
        provider = tier_config.get("provider", "?")
        sessions = tier_config.get("sessions", [])
        sessions_str = ", ".join(sessions[:3])
        if len(sessions) > 3:
            sessions_str += f" (+{len(sessions)-3} more)"
        print(f"{tier_name:<15} {provider:<10} {sessions_str}")

    print("\nCost Estimates (per 1M tokens):")
    print("-" * 70)
    for provider, cost in router.config.get("costs", {}).items():
        print(f"  {provider:<12} ${cost:.2f}")


def test_routing(sessions: List[str]):
    """Test routing for a list of sessions."""
    router = get_router()

    print("\n" + "=" * 70)
    print("Session Routing Test")
    print("=" * 70)
    print(f"{'Session':<25} {'Tier':<15} {'Provider':<10}")
    print("-" * 70)

    for session in sessions:
        result = router.route(session)
        print(f"{session:<25} {result.tier:<15} {result.provider:<10}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test with sample sessions
        test_sessions = [
            "architect",
            "manager1",
            "dev_worker1",
            "dev_worker2",
            "qa_tester1",
            "mcp_worker1",
            "claude_comet",
            "codex",
            "unknown_session",
            "concurrent_worker1",
        ]
        test_routing(test_sessions)
    else:
        print_routing_table()
