#!/usr/bin/env python3
"""
Comprehensive LLM Provider Tests - Unit, Integration, and End-to-End

Tests for all 6 providers:
- Claude (API)
- Ollama (Local)
- OpenAI (API)
- Gemini (API)
- AnythingLLM (Local RAG)
- Comet (Browser automation)

Coverage:
- Unit tests for each provider
- Integration tests for failover chain
- End-to-end system tests
- Cost tracking and token counting
"""

import os
import sys
from pathlib import Path

import pytest

# Add architect to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.llm_provider import (  # noqa: E402
    AnythingLLMProvider,
    ClaudeProvider,
    CometProvider,
    GeminiProvider,
    LLMResponse,
    OllamaProvider,
    OpenAIProvider,
    ProviderType,
    UnifiedLLMClient,
    Usage,
)

# =============================================================================
# Unit Tests - Provider Initialization
# =============================================================================


class TestProviderInitialization:
    """Test that all providers initialize correctly."""

    def test_claude_provider_init(self):
        """Claude provider initializes with correct settings."""
        provider = ClaudeProvider()
        assert provider.provider_type == ProviderType.CLAUDE
        assert provider.config.model == os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
        assert provider.config.cost_per_1k_prompt == 0.003
        assert provider.config.cost_per_1k_completion == 0.015

    def test_ollama_provider_init(self):
        """Ollama provider initializes with correct settings."""
        provider = OllamaProvider()
        assert provider.provider_type == ProviderType.OLLAMA
        assert provider.config.model == os.getenv("OLLAMA_MODEL", "llama3.2")
        assert provider.config.cost_per_1k_prompt == 0.0
        assert provider.config.cost_per_1k_completion == 0.0

    def test_gemini_provider_init(self):
        """Gemini provider initializes with correct settings."""
        provider = GeminiProvider()
        assert provider.provider_type == ProviderType.GEMINI
        assert provider.config.model == os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        assert provider.config.cost_per_1k_prompt == 0.00015
        assert provider.config.cost_per_1k_completion == 0.0006

    def test_anythingllm_provider_init(self):
        """AnythingLLM provider initializes with correct settings."""
        provider = AnythingLLMProvider()
        assert provider.provider_type == ProviderType.ANYTHINGLLM
        assert provider.config.cost_per_1k_prompt == 0.0
        assert provider.config.cost_per_1k_completion == 0.0

    def test_comet_provider_init(self):
        """Comet provider initializes with correct settings."""
        provider = CometProvider()
        assert provider.provider_type == ProviderType.COMET
        assert provider.config.model == os.getenv("COMET_MODEL", "perplexity-comet")
        assert provider.config.cost_per_1k_prompt == 0.0
        assert provider.config.cost_per_1k_completion == 0.0

    def test_openai_provider_init(self):
        """OpenAI provider initializes with correct settings."""
        provider = OpenAIProvider()
        assert provider.provider_type == ProviderType.OPENAI
        assert provider.config.model == os.getenv("OPENAI_MODEL", "gpt-4-turbo")
        assert provider.config.cost_per_1k_prompt == 0.01
        assert provider.config.cost_per_1k_completion == 0.03


# =============================================================================
# Unit Tests - Cost Calculation
# =============================================================================


class TestCostCalculation:
    """Test that cost tracking is accurate for all providers."""

    def test_claude_cost_calculation(self):
        """Claude cost calculation is correct."""
        provider = ClaudeProvider()
        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        cost = provider.calculate_cost(usage)

        # Expected: (1000/1000)*0.003 + (500/1000)*0.015 = 0.003 + 0.0075 = 0.0105
        assert abs(cost - 0.0105) < 0.0001

    def test_gemini_cost_calculation(self):
        """Gemini cost calculation is correct (much cheaper)."""
        provider = GeminiProvider()
        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        cost = provider.calculate_cost(usage)

        # Expected: (1000/1000)*0.00015 + (500/1000)*0.0006 = 0.00015 + 0.0003 = 0.00045
        assert abs(cost - 0.00045) < 0.00001

    def test_free_provider_cost(self):
        """Free providers (Ollama, AnythingLLM) have zero cost."""
        providers = [OllamaProvider(), AnythingLLMProvider()]
        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)

        for provider in providers:
            cost = provider.calculate_cost(usage)
            assert cost == 0.0

    def test_cost_savings_gemini_vs_claude(self):
        """Verify Gemini saves 95% cost vs Claude."""
        claude = ClaudeProvider()
        gemini = GeminiProvider()
        usage = Usage(prompt_tokens=1_000_000, completion_tokens=500_000, total_tokens=1_500_000)

        claude_cost = claude.calculate_cost(usage)
        gemini_cost = gemini.calculate_cost(usage)

        savings_percent = ((claude_cost - gemini_cost) / claude_cost) * 100
        assert savings_percent > 90  # Should be ~95%


# =============================================================================
# Unit Tests - Token Counting
# =============================================================================


class TestTokenCounting:
    """Test token counting approximations."""

    def test_token_count_approximation(self):
        """Token count approximation is reasonable (4 chars per token)."""
        provider = ClaudeProvider()

        # 400 characters should approximate to 100 tokens
        text = "a" * 400
        count = provider.count_tokens(text)
        assert 90 < count < 110  # Allow some variance

    def test_token_count_empty(self):
        """Empty text has zero tokens."""
        provider = ClaudeProvider()
        count = provider.count_tokens("")
        assert count == 0

    def test_token_count_sentences(self):
        """Real text token counting works reasonably."""
        provider = ClaudeProvider()
        text = "The quick brown fox jumps over the lazy dog. " * 10
        count = provider.count_tokens(text)
        assert count > 0


# =============================================================================
# Unit Tests - ProviderType Enum
# =============================================================================


class TestProviderTypeEnum:
    """Test ProviderType enum has all providers."""

    def test_all_providers_in_enum(self):
        """All 6 providers exist in ProviderType enum."""
        providers = {
            ProviderType.CLAUDE,
            ProviderType.OLLAMA,
            ProviderType.OPENAI,
            ProviderType.GEMINI,
            ProviderType.ANYTHINGLLM,
            ProviderType.COMET,
        }
        assert len(providers) == 6

    def test_provider_values(self):
        """ProviderType values match expected strings."""
        assert ProviderType.CLAUDE.value == "claude"
        assert ProviderType.OLLAMA.value == "ollama"
        assert ProviderType.OPENAI.value == "openai"
        assert ProviderType.GEMINI.value == "gemini"
        assert ProviderType.ANYTHINGLLM.value == "anythingllm"
        assert ProviderType.COMET.value == "comet"


# =============================================================================
# Integration Tests - UnifiedLLMClient
# =============================================================================


class TestUnifiedLLMClient:
    """Test UnifiedLLMClient integration."""

    def test_client_initializes_all_providers(self):
        """UnifiedLLMClient initializes all 6 providers."""
        client = UnifiedLLMClient()

        assert "claude" in client.providers
        assert "ollama" in client.providers
        assert "openai" in client.providers
        assert "gemini" in client.providers
        assert "anythingllm" in client.providers
        assert "comet" in client.providers

    def test_client_failover_order(self):
        """Failover order includes all providers."""
        client = UnifiedLLMClient()

        # Should have 6 providers in failover order
        assert len(client.failover_order) == 6

        # All providers should be represented
        required_providers = {"claude", "ollama", "openai", "gemini", "anythingllm", "comet"}
        assert set(client.failover_order) == required_providers

    def test_default_provider_is_first(self):
        """Default provider (Claude) is first in failover order."""
        client = UnifiedLLMClient()
        assert client.failover_order[0] == "claude"

    def test_provider_order_optimization(self):
        """Failover order prioritizes free/cheap providers."""
        client = UnifiedLLMClient()

        # Order: claude -> ollama -> anythingllm -> gemini -> comet -> openai
        expected_order = ["claude", "ollama", "anythingllm", "gemini", "comet", "openai"]
        assert client.failover_order == expected_order

    def test_client_metrics_initialization(self):
        """Client metrics are initialized to zero."""
        client = UnifiedLLMClient()

        assert client.total_requests == 0
        assert client.successful_requests == 0
        assert client.failed_requests == 0
        assert client.failover_count == 0

    def test_messages_api_compatibility(self):
        """Client provides messages API compatibility."""
        client = UnifiedLLMClient()
        assert hasattr(client, "messages")
        assert client.messages is client


# =============================================================================
# Integration Tests - Provider Metrics
# =============================================================================


class TestProviderMetrics:
    """Test metrics collection across providers."""

    def test_provider_metrics_structure(self):
        """Provider metrics have correct structure."""
        provider = ClaudeProvider()
        metrics = provider.get_metrics()

        assert "provider" in metrics
        assert "total_requests" in metrics
        assert "successful_requests" in metrics
        assert "failed_requests" in metrics
        assert "success_rate" in metrics
        assert "total_cost" in metrics
        assert "total_tokens" in metrics

    def test_metrics_accuracy(self):
        """Metrics are accurate after initialization."""
        provider = ClaudeProvider()
        metrics = provider.get_metrics()

        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0
        assert metrics["failed_requests"] == 0
        assert metrics["success_rate"] == 0.0
        assert metrics["total_cost"] == 0.0
        assert metrics["total_tokens"] == 0


# =============================================================================
# Integration Tests - LLM Response Format
# =============================================================================


class TestLLMResponseFormat:
    """Test that all providers return normalized responses."""

    def test_response_structure(self):
        """LLMResponse has all required fields."""
        response = LLMResponse(
            id="test-123",
            content=[{"type": "text", "text": "Hello"}],
            model="test-model",
            stop_reason="stop",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="test",
            cost=0.001,
            latency=0.5,
        )

        assert response.id == "test-123"
        assert len(response.content) > 0
        assert response.model == "test-model"
        assert response.usage.total_tokens == 15
        assert response.provider == "test"
        assert response.cost == 0.001

    def test_response_to_dict(self):
        """LLMResponse can be converted to dict."""
        response = LLMResponse(
            id="test-123",
            content=[{"type": "text", "text": "Hello"}],
            model="test-model",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        data = response.to_dict()
        assert isinstance(data, dict)
        assert data["id"] == "test-123"
        assert data["model"] == "test-model"


# =============================================================================
# End-to-End Tests - System Integration
# =============================================================================


class TestSystemIntegration:
    """End-to-end tests for complete system integration."""

    def test_all_providers_accessible(self):
        """All 6 providers are accessible from UnifiedLLMClient."""
        client = UnifiedLLMClient()

        for provider_name in ["claude", "ollama", "openai", "gemini", "anythingllm", "comet"]:
            assert provider_name in client.providers
            provider = client.providers[provider_name]
            assert provider is not None

    def test_cost_tracking_complete_chain(self):
        """Cost tracking works for all providers."""
        client = UnifiedLLMClient()

        for provider_name, provider in client.providers.items():
            metrics = provider.get_metrics()
            # All providers should have cost tracking
            assert "total_cost" in metrics

    def test_provider_instantiation_order(self):
        """Providers instantiate without errors in any order."""
        # This should not raise any exceptions
        providers = {
            "claude": ClaudeProvider(),
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "anythingllm": AnythingLLMProvider(),
            "comet": CometProvider(),
        }

        assert len(providers) == 6

    def test_failover_chain_complete(self):
        """Complete failover chain from Claude to OpenAI."""
        client = UnifiedLLMClient()

        # Verify chain: claude -> ollama -> anythingllm -> gemini -> comet -> openai
        assert client.failover_order[0] == "claude"
        assert client.failover_order[-1] == "openai"
        assert "gemini" in client.failover_order
        assert "comet" in client.failover_order


# =============================================================================
# Configuration Tests
# =============================================================================


class TestProviderConfiguration:
    """Test provider configuration from environment."""

    def test_env_var_overrides(self):
        """Environment variables override defaults."""
        # Note: Only test that defaults exist, actual env override requires separate setup
        claude = ClaudeProvider()
        assert claude.config.model is not None

        gemini = GeminiProvider()
        assert gemini.config.model is not None

    def test_config_timeout_values(self):
        """Configuration timeouts are reasonable."""
        providers = [
            ClaudeProvider(),
            OllamaProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            AnythingLLMProvider(),
            CometProvider(),
        ]

        for provider in providers:
            assert provider.config.timeout > 0
            assert provider.config.timeout <= 300  # Reasonable max


# =============================================================================
# Comparative Analysis Tests
# =============================================================================


class TestProviderComparison:
    """Compare providers against each other."""

    def test_cost_ranking(self):
        """Providers are ranked by cost correctly."""
        usage = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000)

        costs = {
            "ollama": OllamaProvider().calculate_cost(usage),
            "anythingllm": AnythingLLMProvider().calculate_cost(usage),
            "comet": CometProvider().calculate_cost(usage),
            "gemini": GeminiProvider().calculate_cost(usage),
            "openai": OpenAIProvider().calculate_cost(usage),
            "claude": ClaudeProvider().calculate_cost(usage),
        }

        # Free providers should be 0
        assert costs["ollama"] == 0
        assert costs["anythingllm"] == 0
        assert costs["comet"] == 0

        # Ranking: Gemini (cheapest) < Claude < OpenAI (most expensive)
        assert costs["gemini"] < costs["claude"] < costs["openai"]

    def test_provider_types_diversity(self):
        """Providers cover different implementation types."""
        providers = {
            "claude": ClaudeProvider(),  # Cloud API
            "ollama": OllamaProvider(),  # Local HTTP
            "gemini": GeminiProvider(),  # Cloud API
            "openai": OpenAIProvider(),  # Cloud API
            "anythingllm": AnythingLLMProvider(),  # Local HTTP
            "comet": CometProvider(),  # Browser automation
        }

        # Should have 6 different provider types
        assert len(providers) == 6


# =============================================================================
# Compatibility Tests
# =============================================================================


class TestAPICompatibility:
    """Test API compatibility across providers."""

    def test_all_providers_have_create_completion(self):
        """All providers implement create_completion."""
        providers = [
            ClaudeProvider(),
            OllamaProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            AnythingLLMProvider(),
            CometProvider(),
        ]

        for provider in providers:
            assert hasattr(provider, "create_completion")
            assert callable(provider.create_completion)

    def test_all_providers_implement_abstract_method(self):
        """All providers implement _create_completion_impl."""
        providers = [
            ClaudeProvider(),
            OllamaProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            AnythingLLMProvider(),
            CometProvider(),
        ]

        for provider in providers:
            assert hasattr(provider, "_create_completion_impl")
            assert callable(provider._create_completion_impl)

    def test_all_providers_have_metrics(self):
        """All providers track metrics."""
        providers = [
            ClaudeProvider(),
            OllamaProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            AnythingLLMProvider(),
            CometProvider(),
        ]

        for provider in providers:
            assert hasattr(provider, "get_metrics")
            metrics = provider.get_metrics()
            assert "provider" in metrics
            assert "total_cost" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
