#!/usr/bin/env python3
"""
Rate Limit Handler

Tracks Claude API usage and proactively switches to fallback providers
(codex/ollama) at 80% of limit to avoid hitting hard limits.

Features:
- Proactive switching at 80% of limit (before hitting hard limit)
- Multiple Ollama endpoint support (local + pinklaptop)
- Token usage tracking per provider
- Automatic recovery when limits reset

Usage:
    from services.rate_limit_handler import get_rate_limiter, should_use_claude

    # Check if Claude should be used (considers 80% threshold)
    if should_use_claude():
        use_claude()
    else:
        use_fallback()  # codex/ollama

    # Record usage
    rate_limiter = get_rate_limiter()
    rate_limiter.record_usage("claude", tokens=1500)

    # Get best Ollama endpoint
    endpoint = rate_limiter.get_best_ollama_endpoint()
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("RateLimitHandler")

# Configuration
BASE_DIR = Path(__file__).parent.parent
STATE_FILE = BASE_DIR / "data" / "rate_limits.json"

# Ensure data directory exists
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Ollama endpoints (local + remote)
OLLAMA_ENDPOINTS = [
    {
        "name": "local",
        "url": os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"),
        "priority": 1,
    },
    {
        "name": "pinklaptop",
        "url": os.getenv("OLLAMA_PINKLAPTOP", "http://pinklaptop.local:11434"),
        "priority": 2,
    },
]

# Claude API limits (approximate - adjust based on your tier)
# These are conservative estimates for the free/basic tier
CLAUDE_LIMITS = {
    "requests_per_minute": 50,  # Requests per minute
    "tokens_per_minute": 40000,  # Tokens per minute
    "tokens_per_day": 300000,  # Tokens per day (conservative)
}

# Threshold for proactive switching (80% = switch before hitting limit)
PROACTIVE_THRESHOLD = 0.80
SOFT_THRESHOLD = 0.75  # Start distributing load at 75%


@dataclass
class UsageWindow:
    """Tracks usage within a time window."""

    requests: int = 0
    tokens: int = 0
    window_start: Optional[str] = None  # ISO timestamp

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageWindow":
        return cls(**data)


@dataclass
class RateLimitState:
    """Tracks rate limit state for a provider."""

    provider: str
    is_limited: bool = False
    limit_hit_at: Optional[str] = None
    limit_resets_at: Optional[str] = None
    consecutive_limits: int = 0
    total_limits_today: int = 0
    last_success_at: Optional[str] = None
    requests_since_limit: int = 0

    # Usage tracking
    minute_requests: int = 0
    minute_tokens: int = 0
    minute_start: Optional[str] = None
    daily_tokens: int = 0
    daily_start: Optional[str] = None
    total_tokens_used: int = 0
    total_requests: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RateLimitState":
        return cls(**data)


@dataclass
class OllamaEndpoint:
    """Tracks Ollama endpoint status."""

    name: str
    url: str
    is_available: bool = True
    last_check: Optional[str] = None
    response_time_ms: int = 0
    error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OllamaEndpoint":
        return cls(**data)


class RateLimitHandler:
    """
    Handles Claude API rate limits with proactive fallback.

    Strategy:
    1. Track usage toward limits
    2. At 75% of limit, start distributing load to Ollama
    3. At 80% of limit, switch primarily to Ollama
    4. At 100% (hard limit), use Ollama exclusively
    5. Multiple Ollama endpoints for redundancy
    """

    DEFAULT_COOLDOWN_MINUTES = 5
    MAX_COOLDOWN_MINUTES = 60

    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self.states: Dict[str, RateLimitState] = {}
        self.ollama_endpoints: Dict[str, OllamaEndpoint] = {}
        self._load_state()
        self._init_ollama_endpoints()

    def _init_ollama_endpoints(self):
        """Initialize Ollama endpoint tracking."""
        for endpoint in OLLAMA_ENDPOINTS:
            name = endpoint["name"]
            if name not in self.ollama_endpoints:
                self.ollama_endpoints[name] = OllamaEndpoint(name=name, url=endpoint["url"])

    def _load_state(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                    for provider, state_data in data.get("providers", {}).items():
                        self.states[provider] = RateLimitState.from_dict(state_data)
                    for name, endpoint_data in data.get("ollama_endpoints", {}).items():
                        self.ollama_endpoints[name] = OllamaEndpoint.from_dict(endpoint_data)
            except (json.JSONDecodeError, IOError, TypeError) as e:
                logger.warning(f"Failed to load rate limit state: {e}")

        if "claude" not in self.states:
            self.states["claude"] = RateLimitState(provider="claude")

    def _save_state(self):
        """Save state to file."""
        try:
            data = {
                "providers": {p: s.to_dict() for p, s in self.states.items()},
                "ollama_endpoints": {n: e.to_dict() for n, e in self.ollama_endpoints.items()},
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.warning(f"Failed to save rate limit state: {e}")

    def _reset_minute_window(self, state: RateLimitState):
        """Reset the minute window if expired."""
        now = datetime.now()
        if state.minute_start:
            start = datetime.fromisoformat(state.minute_start)
            if (now - start).total_seconds() >= 60:
                state.minute_requests = 0
                state.minute_tokens = 0
                state.minute_start = now.isoformat()
        else:
            state.minute_start = now.isoformat()

    def _reset_daily_window(self, state: RateLimitState):
        """Reset the daily window if new day."""
        now = datetime.now()
        if state.daily_start:
            start = datetime.fromisoformat(state.daily_start)
            if start.date() != now.date():
                state.daily_tokens = 0
                state.daily_start = now.isoformat()
                state.total_limits_today = 0
        else:
            state.daily_start = now.isoformat()

    def record_usage(self, provider: str = "claude", tokens: int = 0, requests: int = 1):
        """Record usage for a provider."""
        if provider not in self.states:
            self.states[provider] = RateLimitState(provider=provider)

        state = self.states[provider]
        self._reset_minute_window(state)
        self._reset_daily_window(state)

        state.minute_requests += requests
        state.minute_tokens += tokens
        state.daily_tokens += tokens
        state.total_tokens_used += tokens
        state.total_requests += requests

        self._save_state()

    def record_rate_limit(self, provider: str = "claude"):
        """Record that a rate limit was hit."""
        if provider not in self.states:
            self.states[provider] = RateLimitState(provider=provider)

        state = self.states[provider]
        now = datetime.now()

        state.is_limited = True
        state.limit_hit_at = now.isoformat()
        state.consecutive_limits += 1
        state.total_limits_today += 1

        # Exponential backoff
        cooldown_minutes = min(
            self.DEFAULT_COOLDOWN_MINUTES * (2 ** (state.consecutive_limits - 1)),
            self.MAX_COOLDOWN_MINUTES,
        )
        state.limit_resets_at = (now + timedelta(minutes=cooldown_minutes)).isoformat()

        logger.warning(
            f"{provider} rate limit hit (#{state.consecutive_limits}). "
            f"Cooldown: {cooldown_minutes}min"
        )
        self._save_state()

    def record_success(self, provider: str = "claude"):
        """Record a successful request."""
        if provider not in self.states:
            self.states[provider] = RateLimitState(provider=provider)

        state = self.states[provider]
        state.is_limited = False
        state.consecutive_limits = 0
        state.last_success_at = datetime.now().isoformat()
        state.requests_since_limit += 1
        self._save_state()

    def get_usage_percentage(self, provider: str = "claude") -> Dict[str, float]:
        """Get current usage as percentage of limits."""
        if provider not in self.states:
            return {"minute_requests": 0, "minute_tokens": 0, "daily_tokens": 0}

        state = self.states[provider]
        self._reset_minute_window(state)
        self._reset_daily_window(state)

        limits = (
            CLAUDE_LIMITS
            if provider == "claude"
            else {
                "requests_per_minute": 1000,
                "tokens_per_minute": 100000,
                "tokens_per_day": 10000000,
            }
        )

        return {
            "minute_requests": state.minute_requests / limits["requests_per_minute"],
            "minute_tokens": state.minute_tokens / limits["tokens_per_minute"],
            "daily_tokens": state.daily_tokens / limits["tokens_per_day"],
        }

    def is_approaching_limit(
        self, provider: str = "claude", threshold: float = SOFT_THRESHOLD
    ) -> bool:
        """Check if approaching rate limit threshold."""
        usage = self.get_usage_percentage(provider)
        return any(v >= threshold for v in usage.values())

    def is_rate_limited(self, provider: str = "claude") -> bool:
        """Check if provider is currently rate limited."""
        if provider not in self.states:
            return False

        state = self.states[provider]

        # Check hard limit
        if state.is_limited:
            if state.limit_resets_at:
                reset_time = datetime.fromisoformat(state.limit_resets_at)
                if datetime.now() >= reset_time:
                    state.is_limited = False
                    self._save_state()
                    return False
            return True

        # Check proactive threshold (80%)
        if self.is_approaching_limit(provider, PROACTIVE_THRESHOLD):
            logger.info(f"{provider} at {PROACTIVE_THRESHOLD*100}% of limit, proactively limiting")
            return True

        return False

    def should_distribute_load(self, provider: str = "claude") -> bool:
        """Check if load should be distributed (at 75% threshold)."""
        return self.is_approaching_limit(provider, SOFT_THRESHOLD)

    def check_ollama_endpoint(self, endpoint: OllamaEndpoint) -> bool:
        """Check if an Ollama endpoint is available."""
        try:
            start = time.time()
            response = requests.get(f"{endpoint.url}/api/tags", timeout=5)
            elapsed = int((time.time() - start) * 1000)

            endpoint.is_available = response.ok
            endpoint.response_time_ms = elapsed
            endpoint.last_check = datetime.now().isoformat()
            endpoint.error_count = 0 if response.ok else endpoint.error_count + 1

            return response.ok
        except Exception as e:
            endpoint.is_available = False
            endpoint.error_count += 1
            endpoint.last_check = datetime.now().isoformat()
            logger.debug(f"Ollama endpoint {endpoint.name} unavailable: {e}")
            return False

    def get_best_ollama_endpoint(self) -> Optional[str]:
        """Get the best available Ollama endpoint URL."""
        available = []

        for endpoint in self.ollama_endpoints.values():
            # Check if we need to refresh status
            should_check = True
            if endpoint.last_check:
                last = datetime.fromisoformat(endpoint.last_check)
                should_check = (datetime.now() - last).total_seconds() > 30

            if should_check:
                self.check_ollama_endpoint(endpoint)

            if endpoint.is_available:
                available.append(endpoint)

        self._save_state()

        if not available:
            # Return local as fallback
            return OLLAMA_ENDPOINTS[0]["url"]

        # Sort by response time
        available.sort(key=lambda e: e.response_time_ms)
        return available[0].url

    def get_all_ollama_endpoints(self) -> List[str]:
        """Get all available Ollama endpoint URLs."""
        available = []
        for endpoint in self.ollama_endpoints.values():
            if endpoint.is_available or endpoint.last_check is None:
                available.append(endpoint.url)
        return available if available else [OLLAMA_ENDPOINTS[0]["url"]]

    def get_best_provider(self, preferred: str = "claude") -> Tuple[str, Optional[str]]:
        """
        Get the best available provider and endpoint.

        Returns: (provider_name, endpoint_url or None)
        """
        # Check if Claude is available
        if preferred == "claude" and not self.is_rate_limited("claude"):
            # Check if we should distribute load
            if self.should_distribute_load("claude"):
                # 50% chance to use Ollama when at 75%+
                import random

                if random.random() < 0.5:
                    endpoint = self.get_best_ollama_endpoint()
                    logger.debug("Distributing load to Ollama")
                    return ("ollama", endpoint)
            return ("claude", None)

        # Claude limited or should use fallback
        endpoint = self.get_best_ollama_endpoint()
        return ("ollama", endpoint)

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status."""
        claude_usage = self.get_usage_percentage("claude")
        claude_state = self.states.get("claude", RateLimitState(provider="claude"))

        return {
            "claude": {
                "is_limited": self.is_rate_limited("claude"),
                "approaching_limit": self.is_approaching_limit("claude"),
                "should_distribute": self.should_distribute_load("claude"),
                "usage_percent": {
                    "minute_requests": f"{claude_usage['minute_requests']*100:.1f}%",
                    "minute_tokens": f"{claude_usage['minute_tokens']*100:.1f}%",
                    "daily_tokens": f"{claude_usage['daily_tokens']*100:.1f}%",
                },
                "raw_usage": {
                    "minute_requests": claude_state.minute_requests,
                    "minute_tokens": claude_state.minute_tokens,
                    "daily_tokens": claude_state.daily_tokens,
                },
                "limits": CLAUDE_LIMITS,
                "total_requests": claude_state.total_requests,
                "total_tokens": claude_state.total_tokens_used,
            },
            "ollama_endpoints": {
                name: {
                    "url": e.url,
                    "available": e.is_available,
                    "response_time_ms": e.response_time_ms,
                    "last_check": e.last_check,
                }
                for name, e in self.ollama_endpoints.items()
            },
            "recommendation": self.get_best_provider()[0],
        }

    def reset_provider(self, provider: str = "claude"):
        """Reset a provider's state."""
        self.states[provider] = RateLimitState(provider=provider)
        self._save_state()

    def reset_all(self):
        """Reset all states."""
        self.states = {"claude": RateLimitState(provider="claude")}
        self._save_state()


# Global instance
_handler: Optional[RateLimitHandler] = None


def get_rate_limiter() -> RateLimitHandler:
    """Get the global rate limit handler."""
    global _handler
    if _handler is None:
        _handler = RateLimitHandler()
    return _handler


def should_use_claude() -> bool:
    """Check if Claude should be used."""
    return not get_rate_limiter().is_rate_limited("claude")


def get_best_provider(preferred: str = "claude") -> Tuple[str, Optional[str]]:
    """Get the best available provider."""
    return get_rate_limiter().get_best_provider(preferred)


def record_rate_limit(provider: str = "claude"):
    """Record a rate limit hit."""
    get_rate_limiter().record_rate_limit(provider)


def record_success(provider: str = "claude"):
    """Record a successful request."""
    get_rate_limiter().record_success(provider)


def record_usage(provider: str = "claude", tokens: int = 0):
    """Record usage."""
    get_rate_limiter().record_usage(provider, tokens=tokens)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    handler = get_rate_limiter()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            status = handler.get_status()
            print("\n" + "=" * 60)
            print("Rate Limit Status")
            print("=" * 60)

            print("\nClaude API:")
            claude = status["claude"]
            print(f"  Status: {'LIMITED' if claude['is_limited'] else 'OK'}")
            print(f"  Approaching limit: {claude['approaching_limit']}")
            print(f"  Should distribute: {claude['should_distribute']}")
            print("\n  Usage (of limits):")
            for k, v in claude["usage_percent"].items():
                print(f"    {k}: {v}")
            print(
                f"\n  Total: {claude['total_requests']} requests, {claude['total_tokens']} tokens"
            )

            print("\nOllama Endpoints:")
            for name, info in status["ollama_endpoints"].items():
                avail = "OK" if info["available"] else "DOWN"
                print(f"  {name}: {avail} ({info['response_time_ms']}ms) - {info['url']}")

            print(f"\nRecommendation: Use {status['recommendation']}")

        elif cmd == "check-ollama":
            print("Checking Ollama endpoints...")
            for endpoint in handler.ollama_endpoints.values():
                ok = handler.check_ollama_endpoint(endpoint)
                status = "OK" if ok else "FAILED"
                print(f"  {endpoint.name}: {status} ({endpoint.response_time_ms}ms)")

        elif cmd == "reset":
            provider = sys.argv[2] if len(sys.argv) > 2 else "claude"
            handler.reset_provider(provider)
            print(f"Reset {provider}")

        elif cmd == "simulate-usage":
            tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
            handler.record_usage("claude", tokens=tokens)
            print(f"Recorded {tokens} tokens for Claude")
            status = handler.get_status()
            print(f"Now at: {status['claude']['usage_percent']['daily_tokens']} of daily limit")

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: rate_limit_handler.py [status|check-ollama|reset|simulate-usage]")
    else:
        # Default: show status
        status = handler.get_status()
        claude = status["claude"]
        print(
            f"\nClaude: {'LIMITED' if claude['is_limited'] else 'OK'} "
            f"({claude['usage_percent']['daily_tokens']} of daily limit)"
        )
        print(f"Best provider: {status['recommendation']}")
        print("\nRun with 'status' for full details")
