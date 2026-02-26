#!/usr/bin/env python3
"""
LLM Provider Failover System
Drop-in replacement for anthropic.Anthropic() with automatic failover.
Chain: Claude (Anthropic) → Ollama (local) → OpenAI GPT-4

Features:
    - Automatic failover across multiple LLM providers
    - Circuit breaker protection for each provider
    - Cost tracking and optimization
    - Metrics collection
    - Thread-safe operation
    - Drop-in replacement for anthropic.messages.create()

Usage:
    from services.llm_provider import UnifiedLLMClient

    # Initialize client (automatically detects environment)
    client = UnifiedLLMClient()

    # Use like anthropic client
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello!"}]
    )

Environment Variables:
    LLM_FAILOVER_ENABLED - Enable/disable failover (default: true)
    LLM_DEFAULT_PROVIDER - Primary provider (claude, ollama, openai)
    ANTHROPIC_API_KEY - Claude API key
    OPENAI_API_KEY - OpenAI API key
    OLLAMA_ENDPOINT - Ollama endpoint (default: http://localhost:11434)
"""

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitOpenError


# Load environment variables from .env files
def _load_env_files():
    """Load environment variables from .env files."""
    base_dir = Path(__file__).parent.parent
    env_files = [
        base_dir / ".env",
        base_dir / ".env.gemini",
        base_dir / ".env.ai_browser",
    ]
    for env_file in env_files:
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value


_load_env_files()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMProvider")


# =============================================================================
# Data Models
# =============================================================================


class ProviderType(Enum):
    """Supported LLM providers."""

    CLAUDE = "claude"
    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"
    ANYTHINGLLM = "anythingllm"
    COMET = "comet"


@dataclass
class Usage:
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class Message:
    """Normalized message format."""

    role: str
    content: str


@dataclass
class LLMResponse:
    """Normalized LLM response."""

    id: str
    content: List[Dict[str, str]] = field(default_factory=list)
    model: str = ""
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Usage = field(default_factory=Usage)
    provider: str = ""
    cost: float = 0.0
    latency: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    enabled: bool = True
    model: str = ""
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    timeout: float = 120.0
    max_retries: int = 3

    # Cost tracking (per 1K tokens)
    cost_per_1k_prompt: float = 0.0
    cost_per_1k_completion: float = 0.0

    # Circuit breaker config
    circuit_breaker: CircuitConfig = field(
        default_factory=lambda: CircuitConfig.for_service("slow")
    )


# =============================================================================
# Provider Adapters
# =============================================================================


class BaseProvider:
    """Base class for LLM providers."""

    def __init__(self, config: ProviderConfig, provider_type: ProviderType):
        self.config = config
        self.provider_type = provider_type
        self.circuit = CircuitBreaker.get(f"llm-{provider_type.value}", config.circuit_breaker)

        # Metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_cost = 0.0
        self.total_tokens = 0

    def create_completion(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Create completion with circuit breaker protection."""
        if not self.circuit.allow_request():
            raise CircuitOpenError(f"llm-{self.provider_type.value}")

        self.total_requests += 1
        start_time = time.time()

        try:
            response = self._create_completion_impl(messages, **kwargs)
            latency = time.time() - start_time
            response.latency = latency
            response.provider = self.provider_type.value

            # Calculate cost
            response.cost = self.calculate_cost(response.usage)

            # Update metrics
            self.successful_requests += 1
            self.total_cost += response.cost
            self.total_tokens += response.usage.total_tokens

            self.circuit.record_success()
            logger.info(
                f"{self.provider_type.value} completion successful: "
                f"{response.usage.total_tokens} tokens, "
                f"${response.cost:.4f}, {latency:.2f}s"
            )

            return response

        except Exception as e:
            self.failed_requests += 1
            self.circuit.record_failure(e)
            logger.error(f"{self.provider_type.value} completion failed: {e}")
            raise

    def _create_completion_impl(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Provider-specific implementation."""
        raise NotImplementedError

    def calculate_cost(self, usage: Usage) -> float:
        """Calculate cost based on usage."""
        prompt_cost = (usage.prompt_tokens / 1000.0) * self.config.cost_per_1k_prompt
        completion_cost = (usage.completion_tokens / 1000.0) * self.config.cost_per_1k_completion
        return prompt_cost + completion_cost

    def count_tokens(self, text: str) -> int:
        """Approximate token count (override for accurate counting)."""
        # Rough estimate: ~4 characters per token
        return len(text) // 4

    def get_metrics(self) -> Dict[str, Any]:
        """Get provider metrics."""
        return {
            "provider": self.provider_type.value,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0
            ),
            "total_cost": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
            "circuit": self.circuit.get_status(),
        }


class ClaudeProvider(BaseProvider):
    """Claude (Anthropic) provider adapter."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                cost_per_1k_prompt=0.003,  # $3 per million
                cost_per_1k_completion=0.015,  # $15 per million
            )
        super().__init__(config, ProviderType.CLAUDE)

    def _create_completion_impl(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Create Claude completion."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

        if not self.config.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=self.config.api_key)

        # Call Claude API
        response = client.messages.create(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", 1024),
            messages=messages,
            **{k: v for k, v in kwargs.items() if k not in ["model", "max_tokens"]},
        )

        # Normalize response
        return LLMResponse(
            id=response.id,
            content=response.content,
            model=response.model,
            stop_reason=response.stop_reason,
            stop_sequence=response.stop_sequence,
            usage=Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
        )


class OllamaProvider(BaseProvider):
    """Ollama (local LLM) provider adapter."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                model=os.getenv("OLLAMA_MODEL", "llama3.2"),
                endpoint=os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"),
                cost_per_1k_prompt=0.0,  # Free (local)
                cost_per_1k_completion=0.0,
            )
        super().__init__(config, ProviderType.OLLAMA)

    def _create_completion_impl(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Create Ollama completion."""
        import requests

        url = f"{self.config.endpoint}/api/chat"

        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": messages,
            "stream": False,
        }

        response = requests.post(url, json=payload, timeout=self.config.timeout)
        response.raise_for_status()

        data = response.json()

        # Extract content
        content = data.get("message", {}).get("content", "")

        # Approximate token counts
        prompt_text = " ".join([m.get("content", "") for m in messages])
        prompt_tokens = self.count_tokens(prompt_text)
        completion_tokens = self.count_tokens(content)

        return LLMResponse(
            id=f"ollama-{int(time.time())}",
            content=[{"type": "text", "text": content}],
            model=self.config.model,
            stop_reason=data.get("done_reason", "stop"),
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )


class OpenAIProvider(BaseProvider):
    """OpenAI GPT provider adapter."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                model=os.getenv("OPENAI_MODEL", "gpt-4-turbo"),
                api_key=os.getenv("OPENAI_API_KEY"),
                cost_per_1k_prompt=0.01,  # $10 per million
                cost_per_1k_completion=0.03,  # $30 per million
            )
        super().__init__(config, ProviderType.OPENAI)

    def _create_completion_impl(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Create OpenAI completion."""
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

        if not self.config.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        client = openai.OpenAI(api_key=self.config.api_key)

        response = client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            max_tokens=kwargs.get("max_tokens"),
            **{k: v for k, v in kwargs.items() if k not in ["model", "max_tokens"]},
        )

        # Normalize response
        choice = response.choices[0]

        return LLMResponse(
            id=response.id,
            content=[{"type": "text", "text": choice.message.content}],
            model=response.model,
            stop_reason=choice.finish_reason,
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
        )


class GeminiProvider(BaseProvider):
    """Google Gemini provider adapter."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
                api_key=os.getenv("GEMINI_API_KEY"),
                cost_per_1k_prompt=0.00015,  # $0.15 per million (flash)
                cost_per_1k_completion=0.0006,  # $0.60 per million
            )
        super().__init__(config, ProviderType.GEMINI)

    def _create_completion_impl(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Create Gemini completion."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            )

        if not self.config.api_key:
            raise ValueError("GEMINI_API_KEY not set")

        genai.configure(api_key=self.config.api_key)

        # Convert messages to Gemini format
        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        # Last message is the prompt
        prompt = messages[-1]["content"]

        # Create model
        model = genai.GenerativeModel(kwargs.get("model", self.config.model))

        # Start chat
        chat = model.start_chat(history=history)

        # Generate response
        response = chat.send_message(prompt)

        # Extract text
        content = response.text

        # Approximate token counts
        prompt_text = " ".join([m.get("content", "") for m in messages])
        prompt_tokens = self.count_tokens(prompt_text)
        completion_tokens = self.count_tokens(content)

        return LLMResponse(
            id=f"gemini-{int(time.time())}",
            content=[{"type": "text", "text": content}],
            model=self.config.model,
            stop_reason="stop",
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )


class AnythingLLMProvider(BaseProvider):
    """AnythingLLM provider adapter (compatible with OpenAI API)."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                model=os.getenv("ANYTHINGLLM_MODEL", "default"),
                endpoint=os.getenv("ANYTHINGLLM_ENDPOINT", "http://localhost:3001"),
                api_key=os.getenv("ANYTHINGLLM_API_KEY"),
                cost_per_1k_prompt=0.0,  # Usually free (local or self-hosted)
                cost_per_1k_completion=0.0,
            )
        super().__init__(config, ProviderType.ANYTHINGLLM)

    def _create_completion_impl(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Create AnythingLLM completion."""
        import requests

        url = f"{self.config.endpoint}/api/v1/workspace/chat"

        # AnythingLLM format
        payload = {
            "message": messages[-1]["content"],  # Last message
            "mode": "chat",
        }

        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        response = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout)
        response.raise_for_status()

        data = response.json()

        # Extract content
        content = data.get("textResponse", "")

        # Approximate token counts
        prompt_text = " ".join([m.get("content", "") for m in messages])
        prompt_tokens = self.count_tokens(prompt_text)
        completion_tokens = self.count_tokens(content)

        return LLMResponse(
            id=f"anythingllm-{int(time.time())}",
            content=[{"type": "text", "text": content}],
            model=self.config.model,
            stop_reason="stop",
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )


class CometProvider(BaseProvider):
    """Comet browser automation provider (wraps Perplexity via web UI automation)."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                model=os.getenv("COMET_MODEL", "perplexity-comet"),
                endpoint=os.getenv("COMET_ENDPOINT", "ws://localhost:8765"),
                cost_per_1k_prompt=0.0,  # Free (uses Perplexity subscription)
                cost_per_1k_completion=0.0,
            )
        super().__init__(config, ProviderType.COMET)

    def _create_completion_impl(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Create Comet completion via browser automation."""
        try:
            from comet_auto_integration import CometIntegration
        except ImportError:
            raise RuntimeError(
                "comet_auto_integration module not found. "
                "Make sure Comet browser and integration files are installed."
            )

        try:
            # Initialize Comet automation
            comet = CometIntegration()

            # Check if browser is running
            if not comet.check_browser_running():
                if not comet.launch_browser():
                    raise RuntimeError("Could not launch Comet browser")

            # Use last message as query
            query = messages[-1]["content"]

            # Execute via Comet browser automation
            result = comet.execute_task(query)

            # Extract response
            content = result.get("response", "")
            if not content:
                raise RuntimeError("No response from Comet")

            # Approximate token counts
            prompt_text = " ".join([m.get("content", "") for m in messages])
            prompt_tokens = self.count_tokens(prompt_text)
            completion_tokens = self.count_tokens(content)

            return LLMResponse(
                id=f"comet-{int(time.time())}",
                content=[{"type": "text", "text": content}],
                model=self.config.model,
                stop_reason="stop",
                usage=Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )
        except Exception as e:
            logger.error(f"Comet execution failed: {e}")
            raise


# =============================================================================
# Unified Client
# =============================================================================


class UnifiedLLMClient:
    """
    Unified LLM client with automatic failover.

    Drop-in replacement for anthropic.Anthropic() with automatic failover
    to Ollama (local) and OpenAI when Claude is unavailable.

    Example:
        client = UnifiedLLMClient()
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    def __init__(self, failover_enabled: bool = None):
        """
        Initialize unified LLM client.

        Args:
            failover_enabled: Enable automatic failover (default: from env LLM_FAILOVER_ENABLED)
        """
        if failover_enabled is None:
            failover_enabled = os.getenv("LLM_FAILOVER_ENABLED", "true").lower() == "true"

        self.failover_enabled = failover_enabled

        # Initialize providers
        self.providers: Dict[str, BaseProvider] = {
            "claude": ClaudeProvider(),
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "anythingllm": AnythingLLMProvider(),
            "comet": CometProvider(),
        }

        # Determine failover order
        default_provider = os.getenv("LLM_DEFAULT_PROVIDER", "claude")
        self.failover_order = [default_provider]

        # Add other providers in failover order
        # Prioritize free/local providers, then paid
        for provider in ["claude", "ollama", "anythingllm", "gemini", "comet", "openai"]:
            if provider not in self.failover_order:
                self.failover_order.append(provider)

        # Metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.failover_count = 0

        # Messages API compatibility (drop-in replacement for anthropic)
        self.messages = self

        logger.info(f"LLM Client initialized. Failover: {failover_enabled}")
        logger.info(f"Provider order: {' → '.join(self.failover_order)}")

    def create(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        Create completion with automatic failover and rate limit handling.

        This method provides drop-in compatibility with anthropic.messages.create()
        When Claude hits rate limits, automatically falls back to codex/ollama.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional arguments (model, max_tokens, etc.)

        Returns:
            LLMResponse with normalized response

        Raises:
            RuntimeError: If all providers fail
        """
        self.total_requests += 1

        # Import rate limit handler
        try:
            from services.rate_limit_handler import (
                get_rate_limiter,
                record_rate_limit,
                record_success,
            )

            rate_limiter = get_rate_limiter()
            use_rate_limiter = True
        except ImportError:
            use_rate_limiter = False

        if not self.failover_enabled:
            # No failover - use primary provider only
            try:
                response = self.providers[self.failover_order[0]].create_completion(
                    messages, **kwargs
                )
                self.successful_requests += 1
                if use_rate_limiter:
                    record_success(self.failover_order[0])
                return response
            except Exception as e:
                self.failed_requests += 1
                # Check for rate limit errors
                if use_rate_limiter and self._is_rate_limit_error(e):
                    record_rate_limit(self.failover_order[0])
                raise

        # Try providers in order
        errors = []

        # Reorder providers based on rate limit status
        provider_order = self.failover_order.copy()
        if use_rate_limiter:
            # Move rate-limited providers to the end
            limited = [p for p in provider_order if rate_limiter.is_rate_limited(p)]
            available = [p for p in provider_order if p not in limited]
            provider_order = available + limited
            if limited:
                logger.info(f"Rate-limited providers moved to end: {limited}")

        for provider_name in provider_order:
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            try:
                # Skip if circuit breaker is open
                if provider.circuit.is_open:
                    logger.warning(f"Skipping {provider_name}: circuit breaker open")
                    continue

                # Skip if rate limited (but still try if it's the only option)
                if use_rate_limiter and rate_limiter.is_rate_limited(provider_name):
                    remaining = rate_limiter.get_cooldown_remaining(provider_name)
                    logger.info(f"Skipping {provider_name}: rate limited ({remaining}s remaining)")
                    continue

                response = provider.create_completion(messages, **kwargs)

                # Track success
                if use_rate_limiter:
                    record_success(provider_name)

                # Track failover
                if provider_name != self.failover_order[0]:
                    self.failover_count += 1
                    logger.warning(f"Failover to {provider_name} successful")

                self.successful_requests += 1
                return response

            except CircuitOpenError as e:
                logger.warning(f"{provider_name} circuit breaker open, trying next provider")
                errors.append((provider_name, str(e)))
                continue

            except Exception as e:
                # Check for rate limit errors
                if use_rate_limiter and self._is_rate_limit_error(e):
                    record_rate_limit(provider_name)
                    logger.warning(f"{provider_name} rate limited, switching to fallback")
                else:
                    logger.error(f"{provider_name} failed: {e}")
                errors.append((provider_name, str(e)))
                continue

        # All providers failed
        self.failed_requests += 1
        error_summary = "; ".join([f"{p}: {e}" for p, e in errors])
        raise RuntimeError(f"All providers failed: {error_summary}")

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if an error is a rate limit error."""
        error_str = str(error).lower()
        rate_limit_indicators = [
            "rate limit",
            "rate_limit",
            "ratelimit",
            "too many requests",
            "429",
            "quota exceeded",
            "quota_exceeded",
            "overloaded",
            "capacity",
            "try again later",
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)

    def create_completion(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Alias for create() for consistency."""
        return self.create(messages, **kwargs)

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all providers."""
        provider_metrics = {
            name: provider.get_metrics() for name, provider in self.providers.items()
        }

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0
            ),
            "failover_count": self.failover_count,
            "total_cost": sum(p.total_cost for p in self.providers.values()),
            "total_tokens": sum(p.total_tokens for p in self.providers.values()),
            "providers": provider_metrics,
        }

    def get_circuit_status(self) -> Dict[str, Dict]:
        """Get circuit breaker status for all providers."""
        return {name: provider.circuit.get_status() for name, provider in self.providers.items()}

    def reset_circuits(self):
        """Reset all circuit breakers."""
        for provider in self.providers.values():
            provider.circuit.reset()
        logger.info("All circuit breakers reset")


# =============================================================================
# Backwards Compatibility (Note: CircuitBreaker imported from circuit_breaker.py)
# =============================================================================


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("LLM Failover System Demo")
    print("=" * 60)
    print()

    client = UnifiedLLMClient()

    print("Circuit Status:")
    status = client.get_circuit_status()
    for provider, info in status.items():
        print(f"  {provider}: {info['state']}")

    print()
    print("Metrics:")
    metrics = client.get_metrics()
    print(f"  Total Requests: {metrics['total_requests']}")
    print(f"  Successful: {metrics['successful_requests']}")
    print(f"  Failed: {metrics['failed_requests']}")
    print(f"  Failover Count: {metrics['failover_count']}")
    print(f"  Total Cost: ${metrics['total_cost']:.4f}")

    print()
    print("LLM Failover System ready")
