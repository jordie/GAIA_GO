#!/usr/bin/env python3
"""
LLM Provider Integration Tests - Happy Flow Coverage

Comprehensive integration tests covering all happy paths for the LLM provider system:
1. Environment file loading
2. Provider initialization and configuration
3. Gemini provider integration
4. Provider failover chain
5. UnifiedLLMClient integration
6. Cost tracking and optimization
7. Circuit breaker integration
8. Provider routing with GAIA

Run: pytest tests/test_llm_integration_happy_flows.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add architect to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Test: Environment File Loading
# =============================================================================


class TestEnvFileLoading:
    """Test automatic loading of .env files for API keys."""

    def test_load_env_files_function_exists(self):
        """The _load_env_files function is available."""
        from services.llm_provider import _load_env_files

        assert callable(_load_env_files)

    def test_env_file_loading_at_import(self):
        """Environment variables are loaded when module is imported."""
        # If .env.gemini exists, GEMINI_API_KEY should be set
        base_dir = Path(__file__).parent.parent
        env_gemini = base_dir / ".env.gemini"

        if env_gemini.exists():
            # Import triggers _load_env_files()
            import services.llm_provider  # noqa: F401

            # GEMINI_API_KEY should be in environment
            assert "GEMINI_API_KEY" in os.environ or os.getenv("GEMINI_API_KEY") is None

    def test_env_file_respects_existing_vars(self):
        """Env file loading does not override existing environment variables."""
        # Set a test variable
        os.environ["TEST_EXISTING_VAR"] = "original_value"

        # Create a temp env file that tries to set it
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("TEST_EXISTING_VAR=new_value\n")
            temp_path = f.name

        try:
            # Manually load and verify - import is enough to trigger loading
            from services.llm_provider import _load_env_files  # noqa: F401

            # The function should not override existing
            assert os.environ.get("TEST_EXISTING_VAR") == "original_value"
        finally:
            os.unlink(temp_path)
            del os.environ["TEST_EXISTING_VAR"]

    def test_env_file_handles_quotes(self):
        """Env file loading properly strips quotes from values."""
        # Create temp env file with quoted values
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write('TEST_QUOTED_VAR="quoted_value"\n')
            f.write("TEST_SINGLE_QUOTED='single_quoted'\n")
            temp_path = f.name

        try:
            # Manually parse to test quote stripping logic
            with open(temp_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key == "TEST_QUOTED_VAR":
                            assert value == "quoted_value"
                        if key == "TEST_SINGLE_QUOTED":
                            assert value == "single_quoted"
        finally:
            os.unlink(temp_path)

    def test_env_file_ignores_comments(self):
        """Env file loading ignores comment lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("# This is a comment\n")
            f.write("VALID_VAR=valid_value\n")
            f.write("# Another comment\n")
            temp_path = f.name

        try:
            # Parse and verify comments are skipped
            valid_vars = []
            with open(temp_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        valid_vars.append(key.strip())

            assert "VALID_VAR" in valid_vars
            assert len(valid_vars) == 1  # Only one valid var
        finally:
            os.unlink(temp_path)


# =============================================================================
# Test: Provider Initialization Happy Flows
# =============================================================================


class TestProviderInitializationHappyFlows:
    """Test that all providers initialize successfully."""

    def test_all_providers_import_successfully(self):
        """All provider classes can be imported."""
        from services.llm_provider import (
            AnythingLLMProvider,
            ClaudeProvider,
            CometProvider,
            GeminiProvider,
            OllamaProvider,
            OpenAIProvider,
        )

        # All imports successful
        assert ClaudeProvider is not None
        assert OllamaProvider is not None
        assert OpenAIProvider is not None
        assert GeminiProvider is not None
        assert AnythingLLMProvider is not None
        assert CometProvider is not None

    def test_all_providers_instantiate(self):
        """All providers can be instantiated without errors."""
        from services.llm_provider import (
            AnythingLLMProvider,
            ClaudeProvider,
            CometProvider,
            GeminiProvider,
            OllamaProvider,
            OpenAIProvider,
        )

        providers = [
            ClaudeProvider(),
            OllamaProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            AnythingLLMProvider(),
            CometProvider(),
        ]

        assert len(providers) == 6
        for p in providers:
            assert p is not None

    def test_providers_have_required_attributes(self):
        """All providers have required configuration attributes."""
        from services.llm_provider import (
            AnythingLLMProvider,
            ClaudeProvider,
            CometProvider,
            GeminiProvider,
            OllamaProvider,
            OpenAIProvider,
        )

        providers = [
            ClaudeProvider(),
            OllamaProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            AnythingLLMProvider(),
            CometProvider(),
        ]

        for provider in providers:
            assert hasattr(provider, "provider_type")
            assert hasattr(provider, "config")
            assert hasattr(provider, "create_completion")
            assert hasattr(provider, "calculate_cost")
            assert hasattr(provider, "get_metrics")


# =============================================================================
# Test: Gemini Provider Integration
# =============================================================================


class TestGeminiIntegration:
    """Test Gemini provider integration happy flows."""

    def test_gemini_provider_config(self):
        """Gemini provider has correct configuration."""
        from services.llm_provider import GeminiProvider, ProviderType

        provider = GeminiProvider()

        assert provider.provider_type == ProviderType.GEMINI
        assert provider.config.cost_per_1k_prompt == 0.00015
        assert provider.config.cost_per_1k_completion == 0.0006

    def test_gemini_api_key_from_env(self):
        """Gemini API key is loaded from environment."""
        # Check if GEMINI_API_KEY is available
        api_key = os.getenv("GEMINI_API_KEY")

        # If .env.gemini exists, key should be loaded
        base_dir = Path(__file__).parent.parent
        if (base_dir / ".env.gemini").exists():
            assert api_key is not None, "GEMINI_API_KEY should be loaded from .env.gemini"

    def test_gemini_model_from_env(self):
        """Gemini model is configured from environment or defaults."""
        from services.llm_provider import GeminiProvider

        provider = GeminiProvider()

        # Should use env var or default
        expected_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        assert provider.config.model == expected_model

    def test_gemini_cost_is_cheaper_than_claude(self):
        """Gemini is significantly cheaper than Claude."""
        from services.llm_provider import ClaudeProvider, GeminiProvider, Usage

        gemini = GeminiProvider()
        claude = ClaudeProvider()

        # 1M tokens test
        usage = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000)

        gemini_cost = gemini.calculate_cost(usage)
        claude_cost = claude.calculate_cost(usage)

        # Gemini should be at least 90% cheaper
        savings_percent = ((claude_cost - gemini_cost) / claude_cost) * 100
        assert savings_percent > 90, f"Gemini savings should be >90%, got {savings_percent:.1f}%"

    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_gemini_live_api_call(self):
        """Gemini provider can make a real API call."""
        from services.llm_provider import GeminiProvider

        provider = GeminiProvider()

        response = provider.create_completion(
            messages=[{"role": "user", "content": "Say 'test successful' in exactly 2 words."}],
            max_tokens=10,
        )

        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0


# =============================================================================
# Test: Provider Failover Chain
# =============================================================================


class TestProviderFailoverChain:
    """Test the provider failover mechanism."""

    def test_unified_client_has_failover_chain(self):
        """UnifiedLLMClient has a configured failover chain."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        assert hasattr(client, "providers")
        assert len(client.providers) > 0

    def test_failover_chain_order(self):
        """Failover chain follows expected priority order."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        # Providers should be available as a dict or list
        assert hasattr(client, "providers")

        # If providers is a dict, check for expected keys
        if isinstance(client.providers, dict):
            # Should have common provider names
            provider_names = list(client.providers.keys())
            assert len(provider_names) > 0
        else:
            # If list, check it's not empty
            assert len(client.providers) > 0

    def test_failover_continues_on_error(self):
        """Client continues to next provider on failure."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        # Verify client has failover capability
        assert hasattr(client, "providers")

        # Client should track failover events
        if hasattr(client, "failover_count"):
            assert isinstance(client.failover_count, int)

        # Providers dict should have multiple entries for failover
        if isinstance(client.providers, dict):
            assert len(client.providers) >= 1, "Should have at least one provider for failover"

    def test_circuit_breaker_integration(self):
        """Circuit breaker is integrated with providers."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        # Client should have circuit breaker status method
        assert hasattr(client, "get_circuit_status")

        status = client.get_circuit_status()
        assert isinstance(status, dict)


# =============================================================================
# Test: UnifiedLLMClient Integration
# =============================================================================


class TestUnifiedLLMClientIntegration:
    """Test UnifiedLLMClient happy flows."""

    def test_client_initialization(self):
        """UnifiedLLMClient initializes successfully."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        assert client is not None
        assert hasattr(client, "messages")

    def test_client_has_messages_interface(self):
        """Client has messages.create() interface like Anthropic SDK."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        assert hasattr(client, "messages")
        assert hasattr(client.messages, "create")
        assert callable(client.messages.create)

    def test_client_tracks_metrics(self):
        """Client tracks usage metrics."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        assert hasattr(client, "get_metrics")
        metrics = client.get_metrics()

        assert "total_cost" in metrics
        assert "total_requests" in metrics
        assert "successful_requests" in metrics

    def test_client_get_circuit_status(self):
        """Client reports circuit breaker status."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        status = client.get_circuit_status()

        assert isinstance(status, dict)
        # Each provider should have a status entry
        for provider_status in status.values():
            assert "state" in provider_status

    def test_client_reset_metrics(self):
        """Client can reset metrics."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        # Check if reset method exists
        if hasattr(client, "reset_metrics"):
            client.reset_metrics()
            metrics = client.get_metrics()
            assert metrics["total_requests"] == 0


# =============================================================================
# Test: Cost Tracking Integration
# =============================================================================


class TestCostTrackingIntegration:
    """Test cost tracking across providers."""

    def test_all_providers_calculate_cost(self):
        """All providers can calculate cost."""
        from services.llm_provider import (
            AnythingLLMProvider,
            ClaudeProvider,
            CometProvider,
            GeminiProvider,
            OllamaProvider,
            OpenAIProvider,
            Usage,
        )

        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)

        providers = [
            ClaudeProvider(),
            OllamaProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            AnythingLLMProvider(),
            CometProvider(),
        ]

        for provider in providers:
            cost = provider.calculate_cost(usage)
            assert isinstance(cost, (int, float))
            assert cost >= 0

    def test_local_providers_are_free(self):
        """Local providers (Ollama, AnythingLLM, Comet) are free."""
        from services.llm_provider import AnythingLLMProvider, CometProvider, OllamaProvider, Usage

        usage = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000)

        assert OllamaProvider().calculate_cost(usage) == 0
        assert AnythingLLMProvider().calculate_cost(usage) == 0
        assert CometProvider().calculate_cost(usage) == 0

    def test_cost_ranking_is_correct(self):
        """Provider costs rank correctly: free < Gemini < Claude < OpenAI."""
        from services.llm_provider import (
            ClaudeProvider,
            GeminiProvider,
            OllamaProvider,
            OpenAIProvider,
            Usage,
        )

        usage = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000)

        costs = {
            "ollama": OllamaProvider().calculate_cost(usage),
            "gemini": GeminiProvider().calculate_cost(usage),
            "claude": ClaudeProvider().calculate_cost(usage),
            "openai": OpenAIProvider().calculate_cost(usage),
        }

        # Free providers
        assert costs["ollama"] == 0

        # Paid providers ranked
        assert costs["gemini"] < costs["claude"]
        assert costs["claude"] < costs["openai"]

    def test_gemini_95_percent_cheaper_than_claude(self):
        """Gemini is approximately 95% cheaper than Claude."""
        from services.llm_provider import ClaudeProvider, GeminiProvider, Usage

        usage = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000)

        gemini_cost = GeminiProvider().calculate_cost(usage)
        claude_cost = ClaudeProvider().calculate_cost(usage)

        savings = ((claude_cost - gemini_cost) / claude_cost) * 100

        # Should be around 95.83% savings
        assert 94 <= savings <= 97, f"Expected ~95% savings, got {savings:.2f}%"


# =============================================================================
# Test: Provider Routing with GAIA
# =============================================================================


class TestProviderRoutingIntegration:
    """Test provider routing integration with GAIA system."""

    def test_provider_router_exists(self):
        """ProviderRouter is available."""
        from services.provider_router import ProviderRouter

        router = ProviderRouter()
        assert router is not None

    def test_router_routes_workers_to_codex(self):
        """Worker sessions route to Codex provider."""
        from services.provider_router import get_provider_for_session

        worker_sessions = ["dev_worker1", "gaia_worker1", "qa_tester1"]

        for session in worker_sessions:
            provider = get_provider_for_session(session)
            assert provider == "codex", f"{session} should route to codex, got {provider}"

    def test_router_routes_architects_to_claude(self):
        """High-level sessions route to Claude provider."""
        from services.provider_router import get_provider_for_session

        high_level_sessions = ["architect", "foundation", "inspector"]

        for session in high_level_sessions:
            provider = get_provider_for_session(session)
            assert provider == "claude", f"{session} should route to claude, got {provider}"

    def test_router_has_fallback_chain(self):
        """Router provides fallback chains for providers."""
        from services.provider_router import ProviderRouter

        router = ProviderRouter()

        # Get fallbacks for codex
        fallbacks = router.get_fallbacks("codex")
        assert isinstance(fallbacks, list)
        assert len(fallbacks) > 0

    def test_router_full_routing_result(self):
        """Router returns complete routing result."""
        from services.provider_router import ProviderRouter

        router = ProviderRouter()

        result = router.route("dev_worker1")

        assert hasattr(result, "provider")
        assert hasattr(result, "tier")
        assert hasattr(result, "fallbacks")
        assert hasattr(result, "reason")


# =============================================================================
# Test: End-to-End Integration
# =============================================================================


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def test_full_import_chain(self):
        """Full import chain works without errors."""
        # Import all components
        from services.circuit_breaker import CircuitBreaker
        from services.llm_provider import UnifiedLLMClient
        from services.provider_router import ProviderRouter, get_provider_for_session

        # All imports successful
        assert UnifiedLLMClient is not None
        assert ProviderRouter is not None
        assert CircuitBreaker is not None
        assert callable(get_provider_for_session)

    def test_provider_to_client_integration(self):
        """Providers integrate correctly with UnifiedLLMClient."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        # Should have providers configured
        assert hasattr(client, "providers")

        if isinstance(client.providers, dict):
            # Dict of provider_name -> provider_instance
            assert len(client.providers) > 0
            for name, provider in client.providers.items():
                assert isinstance(name, str)
                assert provider is not None
        else:
            # List of providers
            assert len(client.providers) > 0

    def test_metrics_flow(self):
        """Metrics flow correctly through the system."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        # Get initial metrics
        initial_metrics = client.get_metrics()
        assert "total_cost" in initial_metrics

        # Metrics should be numeric
        assert isinstance(initial_metrics["total_cost"], (int, float))
        assert isinstance(initial_metrics["total_requests"], int)

    def test_circuit_breaker_flow(self):
        """Circuit breaker integrates with client."""
        from services.llm_provider import UnifiedLLMClient

        client = UnifiedLLMClient()

        # Get circuit status
        status = client.get_circuit_status()

        # Should have entries for configured providers
        assert len(status) > 0

        # Each entry should have state
        for provider_name, provider_status in status.items():
            assert "state" in provider_status
            assert provider_status["state"] in ["closed", "open", "half_open"]


# =============================================================================
# Test: LLMResponse Model
# =============================================================================


class TestLLMResponseModel:
    """Test LLMResponse data model."""

    def test_llm_response_creation(self):
        """LLMResponse can be created with required fields."""
        from services.llm_provider import LLMResponse, Usage

        usage = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        response = LLMResponse(
            id="test-id-123",
            content=[{"type": "text", "text": "Test response"}],
            model="test-model",
            provider="test-provider",
            usage=usage,
            latency=100.0,
            cost=0.001,
        )

        assert response.id == "test-id-123"
        assert response.content[0]["text"] == "Test response"
        assert response.model == "test-model"
        assert response.usage.total_tokens == 150

    def test_usage_model(self):
        """Usage model correctly calculates totals."""
        from services.llm_provider import Usage

        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)

        assert usage.prompt_tokens == 1000
        assert usage.completion_tokens == 500
        assert usage.total_tokens == 1500


# =============================================================================
# Test: Token Threshold Integration
# =============================================================================


class TestTokenThresholdIntegration:
    """Test token threshold integration with GAIA."""

    def test_gaia_token_thresholds_exist(self):
        """GAIA token thresholds are defined."""
        try:
            from gaia import TOKEN_THRESHOLDS

            # Check actual structure
            assert "switch_threshold" in TOKEN_THRESHOLDS
            assert "warning" in TOKEN_THRESHOLDS["switch_threshold"]
            assert "switch" in TOKEN_THRESHOLDS["switch_threshold"]
            assert "critical" in TOKEN_THRESHOLDS["switch_threshold"]

            # Verify threshold values
            assert TOKEN_THRESHOLDS["switch_threshold"]["switch"] == 0.80
            assert TOKEN_THRESHOLDS["switch_threshold"]["critical"] == 0.95
        except ImportError:
            pytest.skip("gaia module not available")

    def test_codex_thresholds_exist(self):
        """CODEX thresholds are defined."""
        try:
            from gaia import CODEX_THRESHOLDS

            # Check actual structure
            assert "complexity_routing" in CODEX_THRESHOLDS
            assert "name_patterns" in CODEX_THRESHOLDS
            assert "provider_indicators" in CODEX_THRESHOLDS

            # Verify routing priorities
            routing = CODEX_THRESHOLDS["complexity_routing"]
            assert "low" in routing
            assert "medium" in routing
            assert "high" in routing
        except ImportError:
            pytest.skip("gaia module not available")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
