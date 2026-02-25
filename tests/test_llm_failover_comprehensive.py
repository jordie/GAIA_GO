#!/usr/bin/env python3
"""
Comprehensive LLM Failover System Tests

Tests all failover scenarios, circuit breaker behavior, cost tracking,
and error handling for the 5-provider LLM failover system.

Task: A01 - Test LLM Failover System
"""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path first, before importing project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# flake8: noqa: E402 (module level imports after path modification)
from services.circuit_breaker import CircuitBreaker
from services.llm_provider import (
    AnythingLLMProvider,
    ClaudeProvider,
    GeminiProvider,
    LLMResponse,
    OllamaProvider,
    OpenAIProvider,
    ProviderConfig,
    UnifiedLLMClient,
    Usage,
)


class TestProviderInitialization(unittest.TestCase):
    """Test that all providers initialize correctly."""

    def setUp(self):
        """Reset circuit breakers before each test."""
        CircuitBreaker.reset_all()

    def test_claude_provider_init(self):
        """Test Claude provider initialization."""
        config = ProviderConfig(
            model="claude-sonnet-4-5",
            api_key="test-key",
            cost_per_1k_prompt=0.003,
            cost_per_1k_completion=0.015,
        )
        provider = ClaudeProvider(config)

        self.assertEqual(provider.config.model, "claude-sonnet-4-5")
        self.assertEqual(provider.config.cost_per_1k_prompt, 0.003)
        self.assertIsNotNone(provider.circuit)

    def test_ollama_provider_init(self):
        """Test Ollama provider initialization."""
        config = ProviderConfig(model="llama3.2", endpoint="http://localhost:11434")
        provider = OllamaProvider(config)

        self.assertEqual(provider.config.model, "llama3.2")
        self.assertEqual(provider.config.cost_per_1k_prompt, 0.0)  # Free
        self.assertIsNotNone(provider.circuit)

    def test_openai_provider_init(self):
        """Test OpenAI provider initialization."""
        config = ProviderConfig(model="gpt-4-turbo", api_key="test-key", cost_per_1k_prompt=0.01)
        provider = OpenAIProvider(config)

        self.assertEqual(provider.config.model, "gpt-4-turbo")
        self.assertEqual(provider.config.cost_per_1k_prompt, 0.01)

    def test_gemini_provider_init(self):
        """Test Gemini provider initialization."""
        config = ProviderConfig(
            model="gemini-2.0-flash-exp", api_key="test-key", cost_per_1k_prompt=0.00015
        )
        provider = GeminiProvider(config)

        self.assertEqual(provider.config.model, "gemini-2.0-flash-exp")
        self.assertEqual(provider.config.cost_per_1k_prompt, 0.00015)

    def test_anythingllm_provider_init(self):
        """Test AnythingLLM provider initialization."""
        config = ProviderConfig(endpoint="http://localhost:3001", cost_per_1k_prompt=0.0)
        provider = AnythingLLMProvider(config)

        self.assertEqual(provider.config.endpoint, "http://localhost:3001")
        self.assertEqual(provider.config.cost_per_1k_prompt, 0.0)  # Free


class TestUnifiedClientInitialization(unittest.TestCase):
    """Test unified client initialization."""

    def setUp(self):
        CircuitBreaker.reset_all()

    @patch.dict(os.environ, {"LLM_FAILOVER_ENABLED": "true"})
    def test_client_init_with_failover(self):
        """Test client initializes with failover enabled."""
        client = UnifiedLLMClient()

        self.assertTrue(client.failover_enabled)
        self.assertIn("claude", client.providers)
        self.assertIn("ollama", client.providers)
        self.assertIn("openai", client.providers)
        self.assertIn("gemini", client.providers)
        self.assertIn("anythingllm", client.providers)
        self.assertEqual(len(client.providers), 5)

    @patch.dict(os.environ, {"LLM_FAILOVER_ENABLED": "false"})
    def test_client_init_without_failover(self):
        """Test client initializes with failover disabled."""
        client = UnifiedLLMClient()

        self.assertFalse(client.failover_enabled)
        self.assertEqual(len(client.providers), 5)  # Providers still initialized

    @patch.dict(os.environ, {"LLM_DEFAULT_PROVIDER": "ollama"})
    def test_custom_default_provider(self):
        """Test client with custom default provider."""
        client = UnifiedLLMClient()

        self.assertEqual(client.failover_order[0], "ollama")
        self.assertIn("claude", client.failover_order)

    def test_messages_api_compatibility(self):
        """Test drop-in replacement for anthropic.messages API."""
        client = UnifiedLLMClient()

        # Should have messages attribute
        self.assertIsNotNone(client.messages)
        self.assertTrue(hasattr(client.messages, "create"))


class TestClaudeToOllamaFailover(unittest.TestCase):
    """Test Claude → Ollama failover scenario."""

    def setUp(self):
        CircuitBreaker.reset_all()

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    def test_claude_fails_ollama_succeeds(self, mock_ollama, mock_claude):
        """Test failover when Claude fails and Ollama succeeds."""
        # Claude fails
        mock_claude.side_effect = Exception("Claude API error")

        # Ollama succeeds
        mock_ollama.return_value = LLMResponse(
            id="ollama-123",
            content=[{"type": "text", "text": "Ollama response"}],
            model="llama3.2",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="ollama",
            cost=0.0,
            latency=0.5,
        )

        client = UnifiedLLMClient()
        messages = [{"role": "user", "content": "Test"}]

        response = client.create(messages)

        # Should have failed over to Ollama
        self.assertEqual(response.provider, "ollama")
        self.assertEqual(client.failover_count, 1)
        self.assertEqual(client.successful_requests, 1)
        self.assertEqual(client.failed_requests, 0)

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    def test_claude_timeout_ollama_succeeds(self, mock_ollama, mock_claude):
        """Test failover on timeout."""
        # Claude times out
        mock_claude.side_effect = TimeoutError("Request timed out")

        # Ollama succeeds
        mock_ollama.return_value = LLMResponse(
            id="ollama-123",
            content=[{"type": "text", "text": "Success"}],
            model="llama3.2",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="ollama",
            cost=0.0,
            latency=0.3,
        )

        client = UnifiedLLMClient()
        response = client.create([{"role": "user", "content": "Test"}])

        self.assertEqual(response.provider, "ollama")
        self.assertEqual(client.failover_count, 1)


class TestOllamaToAnythingLLMFailover(unittest.TestCase):
    """Test Ollama → AnythingLLM failover scenario."""

    def setUp(self):
        CircuitBreaker.reset_all()

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    @patch("services.llm_provider.AnythingLLMProvider.create_completion")
    def test_claude_ollama_fail_anythingllm_succeeds(
        self, mock_anythingllm, mock_ollama, mock_claude
    ):
        """Test failover when Claude and Ollama fail, AnythingLLM succeeds."""
        # Claude and Ollama fail
        mock_claude.side_effect = Exception("Claude error")
        mock_ollama.side_effect = Exception("Ollama error")

        # AnythingLLM succeeds
        mock_anythingllm.return_value = LLMResponse(
            id="anythingllm-123",
            content=[{"type": "text", "text": "AnythingLLM response"}],
            model="default",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="anythingllm",
            cost=0.0,
            latency=0.4,
        )

        client = UnifiedLLMClient()
        response = client.create([{"role": "user", "content": "Test"}])

        # Should have failed over to AnythingLLM
        self.assertEqual(response.provider, "anythingllm")
        self.assertEqual(client.failover_count, 1)


class TestCircuitBreakerBehavior(unittest.TestCase):
    """Test circuit breaker protection."""

    def setUp(self):
        CircuitBreaker.reset_all()

    def test_circuit_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        config = ProviderConfig()
        provider = ClaudeProvider(config)

        # Record failures to open circuit
        for _ in range(5):
            provider.circuit.record_failure(Exception("Test error"))

        # Circuit should be open
        self.assertTrue(provider.circuit.is_open)
        self.assertFalse(provider.circuit.allow_request())

    def test_circuit_skipped_during_failover(self):
        """Test that open circuits are skipped during failover."""
        client = UnifiedLLMClient()

        # Open Claude circuit
        client.providers["claude"].circuit.force_open(duration=60)

        # Verify circuit is open
        self.assertTrue(client.providers["claude"].circuit.is_open)

        # Client should skip Claude and try next provider
        # (We can't test actual failover without mocking, but we can verify state)
        circuit_status = client.get_circuit_status()
        self.assertEqual(circuit_status["claude"]["state"], "open")

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    def test_circuit_breaker_prevents_requests(self, mock_ollama, mock_claude):
        """Test circuit breaker blocks requests when open."""
        client = UnifiedLLMClient()

        # Force Claude circuit open
        client.providers["claude"].circuit.force_open(duration=60)

        # Ollama succeeds
        mock_ollama.return_value = LLMResponse(
            id="ollama-123",
            content=[{"type": "text", "text": "Success"}],
            model="llama3.2",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="ollama",
            cost=0.0,
            latency=0.5,
        )

        response = client.create([{"role": "user", "content": "Test"}])

        # Should have skipped Claude and gone to Ollama
        self.assertEqual(response.provider, "ollama")
        # Claude's create_completion should NOT have been called
        mock_claude.assert_not_called()

    def test_circuit_half_open_recovery(self):
        """Test circuit transitions to half-open for recovery."""
        from services.circuit_breaker import CircuitConfig

        # Remove any existing circuit to ensure we use custom config
        CircuitBreaker.remove("llm-claude")

        # Create custom circuit config with short timeout and no backoff
        circuit_config = CircuitConfig(
            failure_threshold=3,
            recovery_timeout=0.1,
            success_threshold=1,
            backoff_multiplier=1.0,  # Disable exponential backoff for testing
        )

        config = ProviderConfig(circuit_breaker=circuit_config)
        provider = ClaudeProvider(config)

        # Verify circuit is closed initially
        self.assertTrue(provider.circuit.is_closed)

        # Open circuit with failures
        for _ in range(3):
            provider.circuit.record_failure(Exception("Test error"))

        # Circuit should be open
        self.assertTrue(provider.circuit.is_open)

        # Wait for recovery timeout (100ms + buffer)
        time.sleep(0.15)

        # Check state - should transition to half-open
        state = provider.circuit.state
        self.assertEqual(state.value, "half_open", f"Expected half_open, got {state.value}")


class TestCostTracking(unittest.TestCase):
    """Test cost tracking accuracy."""

    def setUp(self):
        CircuitBreaker.reset_all()

    def test_claude_cost_calculation(self):
        """Test Claude cost calculation."""
        config = ProviderConfig(cost_per_1k_prompt=0.003, cost_per_1k_completion=0.015)
        provider = ClaudeProvider(config)

        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        cost = provider.calculate_cost(usage)

        # (1000/1000 * 0.003) + (500/1000 * 0.015) = 0.003 + 0.0075 = 0.0105
        self.assertAlmostEqual(cost, 0.0105, places=4)

    def test_ollama_cost_is_zero(self):
        """Test Ollama (free) cost is zero."""
        provider = OllamaProvider()

        usage = Usage(prompt_tokens=10000, completion_tokens=5000, total_tokens=15000)
        cost = provider.calculate_cost(usage)

        self.assertEqual(cost, 0.0)

    def test_gemini_cost_calculation(self):
        """Test Gemini cost calculation (cheaper than Claude)."""
        config = ProviderConfig(cost_per_1k_prompt=0.00015, cost_per_1k_completion=0.0006)
        provider = GeminiProvider(config)

        usage = Usage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000)
        cost = provider.calculate_cost(usage)

        # (1000/1000 * 0.00015) + (1000/1000 * 0.0006) = 0.00075
        self.assertAlmostEqual(cost, 0.00075, places=5)

    def test_openai_cost_calculation(self):
        """Test OpenAI cost calculation."""
        config = ProviderConfig(cost_per_1k_prompt=0.01, cost_per_1k_completion=0.03)
        provider = OpenAIProvider(config)

        usage = Usage(prompt_tokens=500, completion_tokens=250, total_tokens=750)
        cost = provider.calculate_cost(usage)

        # (500/1000 * 0.01) + (250/1000 * 0.03) = 0.005 + 0.0075 = 0.0125
        self.assertAlmostEqual(cost, 0.0125, places=4)

    @patch("services.llm_provider.OllamaProvider.create_completion")
    def test_total_cost_tracking(self, mock_ollama):
        """Test that total cost is tracked across requests."""
        mock_ollama.return_value = LLMResponse(
            id="ollama-123",
            content=[{"type": "text", "text": "Response"}],
            model="llama3.2",
            usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            provider="ollama",
            cost=0.0,
            latency=0.5,
        )

        client = UnifiedLLMClient()

        # Make multiple requests
        for _ in range(3):
            client.create([{"role": "user", "content": "Test"}])

        metrics = client.get_metrics()

        # Ollama is free, so total cost should be 0
        self.assertEqual(metrics["total_cost"], 0.0)
        self.assertEqual(metrics["successful_requests"], 3)


class TestAPIFailureHandling(unittest.TestCase):
    """Test handling of various API failures."""

    def setUp(self):
        CircuitBreaker.reset_all()

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    @patch("services.llm_provider.AnythingLLMProvider.create_completion")
    @patch("services.llm_provider.GeminiProvider.create_completion")
    @patch("services.llm_provider.OpenAIProvider.create_completion")
    def test_all_providers_fail(
        self, mock_openai, mock_gemini, mock_anythingllm, mock_ollama, mock_claude
    ):
        """Test when all providers fail."""
        # All providers fail
        mock_claude.side_effect = Exception("Claude error")
        mock_ollama.side_effect = Exception("Ollama error")
        mock_anythingllm.side_effect = Exception("AnythingLLM error")
        mock_gemini.side_effect = Exception("Gemini error")
        mock_openai.side_effect = Exception("OpenAI error")

        client = UnifiedLLMClient()
        messages = [{"role": "user", "content": "Test"}]

        with self.assertRaises(RuntimeError) as context:
            client.create(messages)

        self.assertIn("All providers failed", str(context.exception))
        self.assertEqual(client.failed_requests, 1)

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    def test_network_error_handling(self, mock_ollama, mock_claude):
        """Test handling of network errors."""
        import requests

        # Claude has network error
        mock_claude.side_effect = requests.exceptions.ConnectionError("Network error")

        # Ollama succeeds
        mock_ollama.return_value = LLMResponse(
            id="ollama-123",
            content=[{"type": "text", "text": "Success"}],
            model="llama3.2",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="ollama",
            cost=0.0,
            latency=0.5,
        )

        client = UnifiedLLMClient()
        response = client.create([{"role": "user", "content": "Test"}])

        # Should have failed over successfully
        self.assertEqual(response.provider, "ollama")

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    @patch("services.llm_provider.OllamaProvider.create_completion")
    def test_timeout_error_handling(self, mock_ollama, mock_claude):
        """Test handling of timeout errors."""
        # Claude times out
        mock_claude.side_effect = TimeoutError("Request timed out")

        # Ollama succeeds
        mock_ollama.return_value = LLMResponse(
            id="ollama-123",
            content=[{"type": "text", "text": "Success"}],
            model="llama3.2",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="ollama",
            cost=0.0,
            latency=0.3,
        )

        client = UnifiedLLMClient()
        response = client.create([{"role": "user", "content": "Test"}])

        self.assertEqual(response.provider, "ollama")


class TestMetricsCollection(unittest.TestCase):
    """Test metrics collection and reporting."""

    def setUp(self):
        CircuitBreaker.reset_all()

    def test_metrics_structure(self):
        """Test metrics have correct structure."""
        client = UnifiedLLMClient()
        metrics = client.get_metrics()

        # Check top-level metrics
        self.assertIn("total_requests", metrics)
        self.assertIn("successful_requests", metrics)
        self.assertIn("failed_requests", metrics)
        self.assertIn("failover_count", metrics)
        self.assertIn("total_cost", metrics)
        self.assertIn("total_tokens", metrics)
        self.assertIn("providers", metrics)

        # Check provider metrics
        self.assertEqual(len(metrics["providers"]), 5)
        for provider_name in ["claude", "ollama", "openai", "gemini", "anythingllm"]:
            self.assertIn(provider_name, metrics["providers"])

    def test_circuit_status_structure(self):
        """Test circuit status has correct structure."""
        client = UnifiedLLMClient()
        status = client.get_circuit_status()

        # Should have status for all 5 providers
        self.assertEqual(len(status), 5)

        for provider_name in ["claude", "ollama", "openai", "gemini", "anythingllm"]:
            self.assertIn(provider_name, status)
            self.assertIn("state", status[provider_name])
            self.assertIn("metrics", status[provider_name])

    @patch("services.llm_provider.ClaudeProvider.create_completion")
    def test_success_rate_calculation(self, mock_claude):
        """Test success rate calculation."""
        mock_claude.return_value = LLMResponse(
            id="claude-123",
            content=[{"type": "text", "text": "Success"}],
            model="claude-sonnet-4-5",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="claude",
            cost=0.001,
            latency=1.0,
        )

        client = UnifiedLLMClient()

        # Make 3 successful requests
        for _ in range(3):
            client.create([{"role": "user", "content": "Test"}])

        metrics = client.get_metrics()

        self.assertEqual(metrics["total_requests"], 3)
        self.assertEqual(metrics["successful_requests"], 3)
        self.assertEqual(metrics["success_rate"], 1.0)


class TestProviderPriority(unittest.TestCase):
    """Test provider priority and ordering."""

    def setUp(self):
        CircuitBreaker.reset_all()

    @patch.dict(os.environ, {"LLM_DEFAULT_PROVIDER": "ollama"})
    def test_custom_failover_order(self):
        """Test custom failover order."""
        client = UnifiedLLMClient()

        # Ollama should be first
        self.assertEqual(client.failover_order[0], "ollama")
        # Others should follow
        self.assertIn("claude", client.failover_order)
        self.assertIn("anythingllm", client.failover_order)

    @patch.dict(os.environ, {"LLM_DEFAULT_PROVIDER": "gemini"})
    def test_gemini_primary(self):
        """Test Gemini as primary provider."""
        client = UnifiedLLMClient()

        self.assertEqual(client.failover_order[0], "gemini")

    def test_default_failover_order(self):
        """Test default failover order prioritizes free providers."""
        client = UnifiedLLMClient()

        # Default should be claude first
        self.assertEqual(client.failover_order[0], "claude")
        # Free providers should be prioritized after
        # Expected order: claude → ollama → anythingllm → gemini → openai
        self.assertIn("ollama", client.failover_order[:3])
        self.assertIn("anythingllm", client.failover_order[:3])


# =============================================================================
# Test Runner
# =============================================================================


def run_tests(verbose=True):
    """Run all tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestProviderInitialization,
        TestUnifiedClientInitialization,
        TestClaudeToOllamaFailover,
        TestOllamaToAnythingLLMFailover,
        TestCircuitBreakerBehavior,
        TestCostTracking,
        TestAPIFailureHandling,
        TestMetricsCollection,
        TestProviderPriority,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    print("=" * 80)
    print("LLM Failover System - Comprehensive Test Suite")
    print("Task: A01 - Test LLM Failover System")
    print("=" * 80)
    print()

    result = run_tests(verbose=True)

    print()
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print()

    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
